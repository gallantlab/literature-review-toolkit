#!/usr/bin/env python3
"""Build a cross-citation index from a list of papers.

For each paper with a DOI, fetch its reference list from CrossRef.
Build a frequency table: which DOIs are cited by ≥N of the input papers.
Resolve unknown DOIs to titles via CrossRef metadata.

Input format (JSON list):
[
  {"slug": "Tang2023_decoder",
   "doi":  "10.1038/s41593-023-01304-9"},   # optional but strongly preferred
  {"slug": "JainHuth_arxiv",
   "doi":  null,
   "pdf":  "papers/topic_X/JainHuth_arxiv.pdf"},  # used as fallback
  ...
]

Run:  python3 xref.py --papers list.json --out xref.json --min-cites 3
Or:   python3 xref.py --rows rows.json --out xref.json     # slug = row key, DOI from link
"""
import argparse
import os
import re
import subprocess
import sys
import time
import urllib.parse
from collections import defaultdict

import common
from common import http_json, set_user_agent

PHASE = "6"   # pipeline phase, read by tools/gen_docs.py for the tool index


def rows_to_papers(rows, keyf=None):
    """rows.json -> the {slug, doi[, pdf]} list this tool reads; rows with
    neither a DOI nor a pdf are skipped (nothing to fetch references from)."""
    keyf = keyf or common.key_field(rows)
    out = []
    for r in rows:
        doi = common.doi_of(r)
        if not doi and not r.get("pdf"):
            continue
        p = {"slug": r.get(keyf, "?"), "doi": doi}
        if r.get("pdf"):
            p["pdf"] = r["pdf"]
        out.append(p)
    return out


def crossref_refs(doi):
    url = f"{common.CROSSREF_API}{urllib.parse.quote(doi)}"
    try:
        d = http_json(url)
        refs = d["message"].get("reference", [])
        return [{
            "doi": (r.get("DOI") or "").lower(),
            "author": (r.get("author") or "").strip(),
            "year": (r.get("year") or "").strip(),
            "title": (r.get("article-title") or "").strip(),
            "journal": (r.get("journal-title") or "").strip(),
            "raw": (r.get("unstructured") or "").strip(),
        } for r in refs]
    except Exception as e:
        print(f"  CR fail {doi}: {e}", file=sys.stderr)
        return None


def pdf_refs(pdf_path):
    """Extract DOIs from references section of a PDF as a fallback."""
    if not (pdf_path and os.path.exists(pdf_path)):
        return []
    try:
        text = subprocess.run(["pdftotext", "-layout", pdf_path, "-"],
                              capture_output=True, timeout=60).stdout.decode("utf-8", errors="ignore")
    except Exception:
        return []
    m = re.search(r"\n\s*(References|REFERENCES|Bibliography|BIBLIOGRAPHY)\s*\n", text)
    refs_text = text[m.end():] if m else text  # if no header, scan whole doc
    seen = set()
    out = []
    for d in re.findall(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", refs_text):
        d = d.rstrip(".,;)").lower()
        if d not in seen:
            seen.add(d)
            out.append({"doi": d, "raw": d})
    return out


def resolve_doi(doi):
    """Get title/first_author/year/journal for a DOI via CrossRef (best-effort:
    None on any failure — this only decorates the ranked list)."""
    try:
        r = common.crossref_work(doi)
    except Exception:
        return None
    return {k: r[k] for k in ("title", "year", "first_author", "journal")} if r else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", help="JSON list of papers (slug + doi or pdf)")
    ap.add_argument("--rows", help="or a rows.json: slug = row key, DOI from doi/link")
    ap.add_argument("--key", default=None, help="row key field for --rows (default: ref, else label)")
    ap.add_argument("--out", required=True, help="JSON output path")
    ap.add_argument("--exclude", help="JSON list of DOIs to exclude (already in spreadsheet)")
    ap.add_argument("--internal-out", help="also write {slug: internal_indegree} — how many OTHER "
                    "corpus papers cite each corpus paper. Feeds families_figure.py auto-landmark "
                    "selection (a paper cited by many of its own siblings is foundational within "
                    "the review).")
    ap.add_argument("--min-cites", type=int, default=3)
    ap.add_argument("--resolve-unknown", action="store_true",
                    help="Look up titles for top-cited DOIs via CrossRef")
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"),
                    help="Contact email for CrossRef User-Agent (required; "
                         "or set LITREVIEW_EMAIL env var)")
    args = ap.parse_args()

    if not args.email:
        sys.exit("error: provide --email or set LITREVIEW_EMAIL "
                 "(CrossRef polite pool expects a contact email in the User-Agent)")
    set_user_agent(args.email)

    if bool(args.papers) == bool(args.rows):
        ap.error("give exactly one of --papers or --rows")
    if args.rows:
        rows = common.load_json(args.rows)
        papers = rows_to_papers(rows, common.key_field(rows, args.key))
    else:
        papers = common.load_json(args.papers)
    excludes = set(d.lower() for d in (common.load_json(args.exclude) if args.exclude else []))

    print(f"Fetching reference lists for {len(papers)} papers...", file=sys.stderr)
    all_refs = {}
    for p in papers:
        slug = p["slug"]
        if p.get("doi"):
            refs = crossref_refs(p["doi"]) or []
            src = "crossref"
        else:
            refs = pdf_refs(p.get("pdf"))
            src = "pdf"
        print(f"  {slug:50s} {len(refs):>4d} refs ({src})", file=sys.stderr)
        all_refs[slug] = refs
        time.sleep(args.sleep)

    # Build frequency table
    counts = defaultdict(list)   # doi -> list of citing slugs
    meta = {}
    for slug, refs in all_refs.items():
        seen_in_paper = set()
        for r in refs:
            d = (r.get("doi") or "").lower()
            if not d or d in seen_in_paper:
                continue
            seen_in_paper.add(d)
            counts[d].append(slug)
            if d not in meta:
                meta[d] = {k: r.get(k, "") for k in ("title", "year", "author", "journal", "raw")}

    # Internal citation graph: how many OTHER corpus papers cite each corpus paper.
    # (Reuses `counts` — no extra fetching. Independent of the --exclude filter, which
    # only governs the external candidate ranking below.)
    if args.internal_out:
        doi_to_slug = {p["doi"].lower(): p["slug"] for p in papers if p.get("doi")}
        indeg = {p["slug"]: 0 for p in papers}
        for d, citing in counts.items():
            tgt = doi_to_slug.get(d)
            if tgt is not None:
                indeg[tgt] = len(set(citing) - {tgt})   # exclude any self-citation
        common.dump_json(indeg, args.internal_out, indent=1)
        top = sorted(indeg.items(), key=lambda kv: -kv[1])[:10]
        print(f"Wrote internal in-degrees -> {args.internal_out} "
              f"(top: {', '.join(f'{s}:{n}' for s, n in top if n)})", file=sys.stderr)

    # Filter excludes and threshold
    ranked = sorted(
        ((d, slugs) for d, slugs in counts.items()
         if len(slugs) >= args.min_cites and d not in excludes),
        key=lambda kv: -len(kv[1]),
    )

    # Optionally resolve unknowns
    if args.resolve_unknown:
        n_unknown = sum(1 for d, _ in ranked if not meta[d].get("title"))
        print(f"\nResolving titles for {n_unknown} unknown DOIs...", file=sys.stderr)
        for doi, _ in ranked:
            if not meta[doi].get("title"):
                m = resolve_doi(doi)
                if m:
                    meta[doi]["title"] = m["title"]
                    meta[doi]["year"] = m["year"]
                    meta[doi]["first_author"] = m["first_author"]
                    meta[doi]["journal"] = m["journal"]
                time.sleep(args.sleep)

    out = []
    for doi, slugs in ranked:
        out.append({"doi": doi, "n_citations": len(slugs), "cited_by": slugs, **meta.get(doi, {})})

    common.dump_json(out, args.out, indent=1)

    # Summary to stderr
    print(f"\n{'cnt':>3}  {'doi':40s}  {'auth/year':25s}  title", file=sys.stderr)
    print("-" * 120, file=sys.stderr)
    for r in out[:80]:
        au = r.get("first_author") or r.get("author") or "?"
        ti = (r.get("title") or r.get("raw", ""))[:80]
        yr = r.get("year", "?")
        print(f"{r['n_citations']:>3}  {r['doi']:40s}  {(au + ' ' + yr)[:25]:25s}  {ti}", file=sys.stderr)
    print(f"\nTotal DOIs cited by >= {args.min_cites}: {len(out)}", file=sys.stderr)
    print(f"Wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
