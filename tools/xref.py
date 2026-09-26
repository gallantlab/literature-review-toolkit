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

arXiv papers' reference lists come from Semantic Scholar (CrossRef has none); so
do those of papers whose CrossRef record has no list. Set S2_API_KEY. A CrossRef
fetch that fails transiently gets a second try at the end of the run, after
--retry-wait.
"""
import argparse
import os
import re
import subprocess
import sys
import time
import urllib.error
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
        aid = common.arxiv_id_of(r)
        doi = common.doi_of(r) or (f"10.48550/arXiv.{common.norm_arxiv(aid)}" if aid else None)
        if not doi and not r.get("pdf"):
            continue
        p = {"slug": r.get(keyf, "?"), "doi": doi}
        if r.get("pdf"):
            p["pdf"] = r["pdf"]
        out.append(p)
    return out


def crossref_refs(doi):
    """Reference list for a DOI, or None when the fetch could not COMPLETE.

    The distinction mirrors verify.py's NOT-FOUND vs ERROR: a DOI genuinely
    absent from CrossRef (404 — arXiv DOIs, some publishers) returns [] —
    the lookup completed and there is no reference list. A throttle/network
    failure that exhausts http_json's backoff returns None — incomplete; the
    caller must NOT count it as "this paper cites nothing", which silently
    deflates the frequency table and the --internal-out in-degrees."""
    url = f"{common.CROSSREF_API}{urllib.parse.quote(doi)}"
    try:
        d = http_json(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        print(f"  CR fail {doi}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  CR fail {doi}: {e}", file=sys.stderr)
        return None
    refs = d["message"].get("reference", [])
    return [{
        "doi": (r.get("DOI") or "").lower(),
        "author": (r.get("author") or "").strip(),
        "year": (r.get("year") or "").strip(),
        "title": (r.get("article-title") or "").strip(),
        "journal": (r.get("journal-title") or "").strip(),
        "raw": (r.get("unstructured") or "").strip(),
    } for r in refs]


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


S2_REF_FIELDS = "paperId,referenceCount,references.externalIds,references.title"


def s2_id_for(doi):
    m = common.ARXIV_DOI.match(doi)
    return f"ARXIV:{common.norm_arxiv(m.group(1))}" if m else f"DOI:{doi}"


def _ref_doi(ext):
    """A cited paper's DOI in the form corpus DOIs take (arXiv as 10.48550/arxiv.<id>)."""
    ext = ext or {}
    if ext.get("DOI"):
        return ext["DOI"].lower()
    if ext.get("ArXiv"):
        return f"10.48550/arxiv.{ext['ArXiv']}".lower()
    return ""


def _s2_ref(r):
    return {"doi": _ref_doi((r or {}).get("externalIds")), "author": "", "year": "",
            "title": (r or {}).get("title") or "", "journal": "", "raw": ""}


def _s2_all_refs(pid):
    refs, offset = [], 0
    while True:
        page = common.s2_request(f"paper/{urllib.parse.quote(pid, safe=':')}/references"
                                 f"?fields=externalIds,title&limit=1000&offset={offset}")
        refs += [x.get("citedPaper") for x in page.get("data") or []]
        if "next" not in page:
            return refs
        offset = page["next"]


def s2_refs(dois, chunk=100):
    """Reference lists from Semantic Scholar -> {doi: [refs] | None}. None = the
    fetch could not complete; [] = S2 has no such paper, rejects its id (named
    on stderr), or has no list (complete). Batched through common.s2_batch."""
    out = {}
    res, failed, rejected = common.s2_batch(f"paper/batch?fields={S2_REF_FIELDS}",
                                            [s2_id_for(d) for d in dois], chunk)
    if rejected:
        print(f"  S2 rejected {len(rejected)} id(s) as invalid (treated as not in S2, no references): "
              f"{', '.join(sorted(rejected))}", file=sys.stderr)
    if failed:
        print(f"  S2 references failed for {len(failed)} id(s) (rate-limit/network)", file=sys.stderr)
    for d in dois:
        sid = s2_id_for(d)
        if sid in failed:
            out[d] = None
            continue
        p = res.get(sid)
        if not p:                 # S2 has no such paper, or rejected the id: complete, empty
            out[d] = []
            continue
        refs = p.get("references") or []
        if (p.get("referenceCount") or 0) > len(refs) and p.get("paperId"):
            try:
                refs = _s2_all_refs(p["paperId"])
            except Exception as e:
                print(f"  S2 references {d}: {type(e).__name__}: {e}", file=sys.stderr)
                out[d] = None
                continue
        out[d] = [_s2_ref(r) for r in refs if r]
    return out


def fetch_all(papers, sleep=0.4, retry_wait=60.0):
    """Reference lists for every paper -> ({slug: refs}, [slugs still incomplete]).

    CrossRef first for journal DOIs (one more try after `retry_wait` for an
    incomplete fetch); Semantic Scholar, batched, for arXiv DOIs and for any
    paper CrossRef holds no reference list for."""
    all_refs, incomplete, to_s2 = {}, [], []
    for p in papers:
        doi = p.get("doi")
        if doi and common.ARXIV_DOI.match(doi):
            to_s2.append(p)
            continue
        before = common.request_count()
        refs = crossref_refs(doi) if doi else pdf_refs(p.get("pdf"))
        if refs is None:
            incomplete.append(p)
            refs = []
        elif doi and not refs:
            to_s2.append(p)
        print(f"  {p['slug']:50s} {len(refs):>4d} refs ({'crossref' if doi else 'pdf'})", file=sys.stderr)
        all_refs[p["slug"]] = refs
        if common.request_count() != before:
            time.sleep(sleep)
    if incomplete:
        print(f"  [retry] {len(incomplete)} incomplete CrossRef fetch(es); cooling down {retry_wait:.0f}s…",
              file=sys.stderr)
        time.sleep(retry_wait)
        still = []
        for p in incomplete:
            refs = crossref_refs(p["doi"])
            if refs is None:
                still.append(p)
            elif not refs:
                to_s2.append(p)
            all_refs[p["slug"]] = refs or []
            time.sleep(sleep)
        incomplete = still
    if to_s2:
        got = s2_refs([p["doi"] for p in to_s2])
        for p in to_s2:
            refs = got.get(p["doi"])
            if refs is None:
                incomplete.append(p)
                all_refs.setdefault(p["slug"], [])
                continue
            if refs:
                all_refs[p["slug"]] = refs
            all_refs.setdefault(p["slug"], [])
            print(f"  {p['slug']:50s} {len(all_refs[p['slug']]):>4d} refs (s2)", file=sys.stderr)
    return all_refs, [p["slug"] for p in incomplete]


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
    ap.add_argument("--sleep", type=float, default=0.4,
                    help="pause after each paper that made a request (default 0.4 s)")
    ap.add_argument("--retry-wait", type=float, default=60.0,
                    help="cool-down before incomplete fetches get their second try (default 60 s)")
    ap.add_argument("--allow-incomplete", action="store_true",
                    help="exit 0 even when some reference lists could not be fetched (said in the output)")
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"),
                    help="Contact email for CrossRef User-Agent (required; "
                         "or set LITREVIEW_EMAIL env var)")
    args = ap.parse_args()

    if not args.email:
        ap.error("--email or LITREVIEW_EMAIL required "
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
    all_refs, incomplete = fetch_all(papers, sleep=args.sleep, retry_wait=args.retry_wait)

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
    if incomplete:
        print(f"\nWARNING: {len(incomplete)} reference-list fetch(es) could not complete "
              f"(throttle/network) even after a retry: {', '.join(incomplete)}\n"
              "Their papers contributed ZERO references above — the frequency table and "
              "any --internal-out in-degrees are undercounted. Re-run.", file=sys.stderr)
        sys.exit(0 if args.allow_incomplete else 1)


if __name__ == "__main__":
    main()
