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
"""
import argparse, os, re, subprocess, sys, time, urllib.parse
from collections import defaultdict

import common
from common import http_json, set_user_agent


def crossref_refs(doi):
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"
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
    """Get title/author/year/journal for a DOI via CrossRef."""
    try:
        url = f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"
        d = http_json(url)["message"]
        au = (d.get("author") or [{}])[0]
        first = f"{au.get('family','?')} {au.get('given','')[:1]}"
        year = ""
        for k in ("published-print", "published-online", "issued"):
            if k in d and d[k].get("date-parts", [[]])[0]:
                year = str(d[k]["date-parts"][0][0])
                break
        return {
            "title": (d.get("title") or [""])[0],
            "year": year,
            "first_author": first,
            "journal": (d.get("container-title") or [""])[0],
        }
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", required=True, help="JSON list of papers (slug + doi or pdf)")
    ap.add_argument("--out", required=True, help="JSON output path")
    ap.add_argument("--exclude", help="JSON list of DOIs to exclude (already in spreadsheet)")
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

    # Filter excludes and threshold
    ranked = sorted(
        ((d, slugs) for d, slugs in counts.items()
         if len(slugs) >= args.min_cites and d not in excludes),
        key=lambda kv: -len(kv[1]),
    )

    # Optionally resolve unknowns
    if args.resolve_unknown:
        print(f"\nResolving titles for {sum(1 for d,_ in ranked if not meta[d].get('title'))} unknown DOIs...", file=sys.stderr)
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
