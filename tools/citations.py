#!/usr/bin/env python3
"""Fetch citation counts for every row from OpenAlex and Semantic Scholar.

Google Scholar has no public API and blocks automated queries after a few
requests, so it cannot be queried for a whole bibliography. OpenAlex and Semantic
Scholar are the queryable proxies.

OpenAlex is the primary source, with near-complete coverage by DOI. Without
OPENALEX_API_KEY, every client on the same IP address shares one daily budget,
and a spent budget stops the run with OpenAlexBudgetError (run preflight.py
first). Semantic Scholar is the secondary source. It often counts higher for
CS/AI venues and adds an "influential citations" count, but it throttles hard
without S2_API_KEY, so treat its column as best-effort. One S2_API_KEY serves
xref, citations and abstracts; their requests take turns through a pacer shared
across processes, so they may run at the same time.

INPUT: a JSON list of rows. Each row needs a key (default: "ref", else "label")
and a DOI, from a "doi" field or a https://doi.org/... "link"; a row without one
gets empty counts. arXiv DOIs (10.48550/arXiv.<id>) are looked up in Semantic
Scholar by arXiv id.

OUTPUT: {key: {"openalex": int|None, "s2": int|None, "s2_influential": int|None,
               "asof": "YYYY-MM-DD"}}
The spreadsheet and the figure read the counts from the rows, not from this
file. Pass --attach to write them onto --rows as cite_openalex, cite_s2,
cite_s2_influential and cite_asof (through the guarded save, so it refuses to
overwrite a rows.json another tool changed meanwhile), or --attach-only to attach
an existing --out without fetching.

A re-run keeps what an earlier run found: when a lookup returns nothing but the
existing --out has a count for that row, the earlier count stays (a throttled
Semantic Scholar batch is not "no citations").

  python3 tools/citations.py --rows rows.json --out citation_counts.json --attach \\
          --email you@inst.edu
  python3 tools/citations.py --rows rows.json --out citation_counts.json --attach-only

OpenAlex's batch filter sometimes returns a low-count duplicate record. So the
tool keeps the highest count per DOI, retries each miss by single-work lookup,
and re-queries a count far below Semantic Scholar's. Counts are a snapshot at run
time; re-run to refresh. See PLAYBOOK Phase 5b.
"""
import argparse
import datetime
import os
import sys
import time
import urllib.parse

import common
from common import ARXIV_DOI, OpenAlexBudgetError, doi_of, http_json

PHASE = "5b"   # pipeline phase, read by tools/gen_docs.py for the tool index


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
    except OpenAlexBudgetError:
        raise
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
        except OpenAlexBudgetError:
            raise
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


S2_BATCH = 500   # the /paper/batch endpoint's documented cap on ids per request


def fetch_s2(items):
    """items: list of (key, doi). Returns {key: (count, influential)}. Best-effort.

    One POST per <=500 ids, through common.s2_batch: an id S2 rejects (400) is
    isolated and named, and a chunk that fails after the backoff is named and
    skipped; either way the OpenAlex counts stand for those papers."""
    out = {}
    pairs = [(key, s2_id(doi)) for key, doi in items]
    res, failed, rejected = common.s2_batch("paper/batch?fields=citationCount,influentialCitationCount",
                                            [sid for _, sid in pairs], S2_BATCH)
    for key, sid in pairs:
        e = res.get(sid)
        if e and e.get("citationCount") is not None:
            out[key] = (e.get("citationCount"), e.get("influentialCitationCount"))
    if rejected:
        print(f"  S2 rejected {len(rejected)} id(s) as invalid (treated as not in S2): "
              f"{', '.join(sorted(rejected))}", file=sys.stderr)
    if failed:
        print(f"  S2 lookups failed for {len(failed)} id(s) (rate-limit/network); OpenAlex counts stand. "
              f"Set S2_API_KEY to make S2 reliable: {', '.join(sorted(failed))}", file=sys.stderr)
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
    ap.add_argument("--attach", action="store_true",
                    help="also write the counts onto --rows (cite_openalex, cite_s2, ...)")
    ap.add_argument("--attach-only", action="store_true",
                    help="attach an existing --out onto --rows without fetching")
    args = ap.parse_args()
    if args.attach_only:
        return attach(args.rows, args.out, args.key)
    if not args.email:
        ap.error("--email or LITREVIEW_EMAIL required (OpenAlex polite pool)")

    rows = common.load_json(args.rows)
    keyf = common.key_field(rows, args.key)
    items, no_doi = [], []
    for r in rows:
        k = r.get(keyf)
        doi = row_doi(r)
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

    kept = keep_previous(counts, common.load_optional_json(args.out, {}))
    common.dump_json(counts, args.out)
    if kept:
        print(f"  kept {kept} earlier count(s) that this run's lookups did not return")
    oa = sum(1 for c in counts.values() if c["openalex"] is not None)
    s2 = sum(1 for c in counts.values() if c["s2"] is not None)
    print(f"{len(rows)} rows -> {args.out}")
    print(f"  OpenAlex: {oa}/{len(rows)}   Semantic Scholar: {s2}/{len(rows)}   no-DOI: {len(no_doi)}")
    if no_doi:
        print(f"  no-DOI (blank, e.g. books/blogs/reports): {no_doi}")


    if args.attach:
        return attach(args.rows, args.out, args.key)
    return 0


def row_doi(r):
    """Lowercase DOI to look a row up by: its DOI, else the arXiv DOI of its arXiv id."""
    doi = doi_of(r, lower=True)          # OpenAlex/S2 match lowercase DOIs
    if doi:
        return doi
    aid = common.norm_arxiv(common.arxiv_id_of(r) or "")
    return f"10.48550/arxiv.{aid}".lower() if aid else None


def keep_previous(counts, previous):
    """Keep an earlier non-empty count where this run's lookup came back empty.
    Returns how many values were kept. The asof date stays this run's."""
    kept = 0
    for k, c in counts.items():
        old = previous.get(k) or {}
        for f in ("openalex", "s2", "s2_influential"):
            if c.get(f) is None and old.get(f) is not None:
                c[f] = old[f]
                kept += 1
    return kept


def attach(rows_path, counts_path, key=None):
    """Write counts_path's counts onto rows_path through common.save_rows."""
    rows = common.load_json(rows_path)
    mtime = os.path.getmtime(rows_path)
    counts = common.load_json(counts_path)
    n = common.attach_counts(rows, counts, common.key_field(rows, key))
    common.save_rows(rows_path, rows, mtime)
    print(f"attached counts to {n} of {len(rows)} rows in {rows_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
