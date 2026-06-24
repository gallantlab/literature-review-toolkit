#!/usr/bin/env python3
"""Fetch citation counts for a bibliography from OpenAlex + Semantic Scholar.

WHY NOT GOOGLE SCHOLAR: Google Scholar has no public API and CAPTCHA-blocks
automated queries after a handful of requests, so it cannot be queried for a
whole bibliography. OpenAlex and Semantic Scholar are the queryable proxies.
OpenAlex is the primary source (free, no key, reliable, near-complete coverage
by DOI). Semantic Scholar is a useful secondary (often higher for CS/AI venues,
and gives an "influential citations" sub-count) but its free endpoints
rate-limit hard (429/400) from shared IPs — treat it as best-effort and set a
key in S2_API_KEY to make it reliable.

INPUT: a JSON list of rows. Each row needs a stable key (default: "ref" else
"label") and a DOI, taken from a "doi" field or parsed from a "link" that is a
https://doi.org/... URL. arXiv DOIs (10.48550/arXiv.<id>) are auto-mapped to
the arXiv id for the Semantic Scholar lookup.

OUTPUT: {key: {"openalex": int|None, "s2": int|None, "s2_influential": int|None,
               "asof": "YYYY-MM-DD"}}  -> attach to rows before spreadsheet.py.

  python3 tools/citations.py --rows rows.json --out citation_counts.json \
          --email you@inst.edu

Counts are a snapshot at run time; re-run to refresh. See PLAYBOOK Phase 5b.
"""
import argparse, datetime, json, os, sys, time, urllib.parse, urllib.error

import common
from common import ARXIV_DOI, doi_of, http_json


def parse_doi(row):
    """Return a bare lowercase DOI from row['doi'] or a doi.org link, else None."""
    return doi_of(row, lower=True)


def s2_id(doi):
    """Map a DOI to the best Semantic Scholar id (ARXIV: for arXiv DOIs)."""
    m = ARXIV_DOI.match(doi)
    return ("ARXIV:" + m.group(1)) if m else ("DOI:" + doi)


def openalex_single(doi, email):
    """Canonical cited_by_count for one DOI via the single-work endpoint, or None.
    OpenAlex resolves /works/doi:<doi> to the merged primary record, so this is
    more reliable than the batch filter (which can return a low-count duplicate)."""
    try:
        w = http_json(f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi, safe='/.:')}"
                      f"?mailto={email}&select=cited_by_count")
        return w.get("cited_by_count")
    except Exception:
        return None


def fetch_openalex(items, email):
    """items: list of (key, doi). Returns {key: count}. Batch + single retry."""
    out, by_doi = {}, {}
    dois = [doi for _, doi in items]
    for i in range(0, len(dois), 50):
        batch = dois[i:i + 50]
        filt = "doi:" + "|".join(batch)
        url = (f"https://api.openalex.org/works?filter={urllib.parse.quote(filt, safe=':|/.')}"
               f"&per-page=100&mailto={email}")
        try:
            for w in http_json(url).get("results", []):
                doi = (w.get("doi") or "").lower().replace("https://doi.org/", "")
                c = w.get("cited_by_count")
                if doi and c is not None:
                    # OpenAlex can return several works for one DOI (a merged primary
                    # plus stub duplicates); keep the highest count, never last-wins.
                    by_doi[doi] = max(by_doi.get(doi, 0), c)
        except Exception as e:
            print(f"  OpenAlex batch {i}: {type(e).__name__}: {e}", file=sys.stderr)
        time.sleep(0.4)
    for key, doi in items:
        if doi in by_doi:
            out[key] = by_doi[doi]
    # single-work retry for misses (batch silently drops some)
    for key, doi in items:
        if key in out:
            continue
        c = openalex_single(doi, email)
        if c is not None:
            out[key] = c
        time.sleep(0.3)
    return out


def fetch_s2(items, retries=4):
    """items: list of (key, doi). Returns {key: (count, influential)}. Best-effort."""
    out = {}
    pairs = [(key, s2_id(doi)) for key, doi in items]
    ids = [sid for _, sid in pairs]
    headers = {"Content-Type": "application/json"}
    if os.environ.get("S2_API_KEY"):
        headers["x-api-key"] = os.environ["S2_API_KEY"]
    url = ("https://api.semanticscholar.org/graph/v1/paper/batch"
           "?fields=citationCount,influentialCitationCount")
    body = json.dumps({"ids": ids}).encode()
    for att in range(retries):
        try:
            res = http_json(url, data=body, headers=headers)
            for (key, _), e in zip(pairs, res):
                if e and e.get("citationCount") is not None:
                    out[key] = (e.get("citationCount"), e.get("influentialCitationCount"))
            return out
        except urllib.error.HTTPError as e:
            wait = 15 * (att + 1)
            print(f"  S2 batch HTTP {e.code} (attempt {att+1}); retry in {wait}s", file=sys.stderr)
            time.sleep(wait)
        except Exception as e:
            print(f"  S2 batch error: {e}", file=sys.stderr)
            time.sleep(10)
    print("  S2 unavailable (rate-limited); OpenAlex counts stand. Set S2_API_KEY to fix.",
          file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True, help="rows.json (or any list of rows with doi/link)")
    ap.add_argument("--out", default="citation_counts.json")
    ap.add_argument("--key", default=None, help="row key field (default: ref, else label)")
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"),
                    help="contact email for OpenAlex polite pool (or set LITREVIEW_EMAIL)")
    ap.add_argument("--asof", default=datetime.date.today().isoformat(),
                    help="snapshot date for the record (default: today)")
    ap.add_argument("--sources", default="openalex,s2", help="comma list: openalex,s2")
    args = ap.parse_args()
    if not args.email:
        ap.error("--email or LITREVIEW_EMAIL required (OpenAlex polite pool)")

    rows = common.load_json(args.rows)
    keyf = args.key or ("ref" if rows and "ref" in rows[0] else "label")
    items, no_doi = [], []
    for r in rows:
        k = r.get(keyf)
        doi = parse_doi(r)
        (items if doi else no_doi).append((k, doi) if doi else k)

    counts = {k: {"openalex": None, "s2": None, "s2_influential": None, "asof": args.asof}
              for k, _ in items}
    for k in no_doi:
        counts[k] = {"openalex": None, "s2": None, "s2_influential": None, "asof": args.asof}

    srcs = [s.strip() for s in args.sources.split(",")]
    if "openalex" in srcs:
        for k, n in fetch_openalex(items, args.email).items():
            counts[k]["openalex"] = n
    if "s2" in srcs:
        for k, (n, infl) in fetch_s2(items).items():
            counts[k]["s2"] = n
            counts[k]["s2_influential"] = infl

    # Reconcile suspiciously-low OpenAlex counts against S2. OpenAlex's batch filter
    # sometimes returns a low-count duplicate record for a DOI; when S2 reports many
    # more citations, re-query the canonical single-work endpoint and keep the higher.
    if "openalex" in srcs and "s2" in srcs:
        doi_by_key = {k: d for k, d in items}
        for k, c in counts.items():
            oa, s2c = c["openalex"], c["s2"]
            if oa is not None and s2c is not None and s2c >= 50 and oa < 0.5 * s2c:
                canon = openalex_single(doi_by_key.get(k, ""), args.email)
                if canon is not None and canon > oa:
                    c["openalex"] = canon

    common.dump_json(counts, args.out)
    oa = sum(1 for c in counts.values() if c["openalex"] is not None)
    s2 = sum(1 for c in counts.values() if c["s2"] is not None)
    print(f"{len(rows)} rows -> {args.out}")
    print(f"  OpenAlex: {oa}/{len(rows)}   Semantic Scholar: {s2}/{len(rows)}   no-DOI: {len(no_doi)}")
    if no_doi:
        print(f"  no-DOI (blank, e.g. books/blogs/reports): {no_doi}")


if __name__ == "__main__":
    main()
