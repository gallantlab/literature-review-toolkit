#!/usr/bin/env python3
"""Fetch the abstract of every row, in batches, into abstracts.json.

Summaries are checked against these (summary_audit.py), so each row's abstract
comes from the most authoritative source that has it: the arXiv API for arXiv
papers, then OpenAlex (50 DOIs per request), then Semantic Scholar (500 per
request), then PubMed for rows with a PMID. Each entry records the `doi` and
`arxiv` it was fetched for; an entry whose ids no longer match its row is
refetched, except one added by hand ("source": "landing-page"), which is never
overwritten and is reported as stale instead (fix it, with the row's ids).
abstracts_failed.json, beside abstracts.json, maps each ref whose fetch could
not complete to why ({} when none); summary_audit.py --prepare refuses those
refs rather than filing them as having no abstract.

    python3 tools/abstracts.py --rows rows.json --email you@inst.edu
"""
import argparse
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

import common

PHASE = "5c"   # pipeline phase, read by tools/gen_docs.py for the tool index


def reconstruct(inv):
    """OpenAlex abstract_inverted_index -> text."""
    if not inv:
        return ""
    return " ".join(w for _, w in sorted((p, w) for w, ps in inv.items() for p in ps))


def fetch_arxiv(aids):
    """-> ({id: text}, {id that a batch could not complete for})."""
    entries, err = common.arxiv_batch(aids)
    return {a: e["summary"] for a, e in entries.items() if e.get("summary")}, set(err)


def make_fetch_openalex(email):
    def fetch(dois):
        out, failed = {}, set()
        for i in range(0, len(dois), 50):
            batch = dois[i:i + 50]
            filt = "doi:" + "|".join(batch)
            url = (f"https://api.openalex.org/works?filter={urllib.parse.quote(filt, safe=':|/.')}"
                   f"&per-page=100&select=doi,abstract_inverted_index&mailto={email}")
            try:
                for w in common.http_json(url).get("results", []):
                    d = (w.get("doi") or "").lower().replace("https://doi.org/", "")
                    t = reconstruct(w.get("abstract_inverted_index"))
                    if d and t:
                        out[d] = t
            except Exception as e:
                print(f"  OpenAlex batch {i}: {type(e).__name__}: {e}", file=sys.stderr)
                failed.update(batch)
        return out, failed
    return fetch


def fetch_s2(ids):
    """-> ({id: abstract}, failed). An id S2 rejects (400) is 'not in S2' — a
    complete lookup — and is named; a chunk that fails transiently is failed."""
    res, failed, rejected = common.s2_batch("paper/batch?fields=abstract", ids, 500)
    if rejected:
        print(f"  S2 rejected {len(rejected)} id(s) as invalid (treated as not in S2): "
              f"{', '.join(sorted(rejected))}", file=sys.stderr)
    if failed:
        print(f"  S2 lookups failed for {len(failed)} id(s)", file=sys.stderr)
    return {sid: p["abstract"] for sid, p in res.items() if p and p.get("abstract")}, failed


def fetch_pubmed(pmids):
    out, failed = {}, set()
    for i in range(0, len(pmids), 200):
        part = pmids[i:i + 200]
        url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id="
               + ",".join(part))
        try:
            root = ET.fromstring(common.http(url))
        except Exception as e:
            print(f"  PubMed batch {i}: {type(e).__name__}: {e}", file=sys.stderr)
            failed.update(part)
            continue
        for art in root.findall(".//PubmedArticle"):
            pmid = art.findtext(".//PMID") or ""
            text = " ".join("".join(t.itertext()).strip() for t in art.findall(".//Abstract/AbstractText"))
            if pmid and text.strip():
                out[pmid] = " ".join(text.split())
    return out, failed


def _s2_id(row):
    aid = common.arxiv_id_of(row)
    if aid:
        return f"ARXIV:{common.norm_arxiv(aid)}"
    d = common.doi_of(row, lower=True)
    return f"DOI:{d}" if d else ""


def collect(rows, keyf, existing, fetchers):
    """-> ({ref: {text, source, url, doi, arxiv}}, missing, failed {ref: reason}, stale).

    `missing` is every ref with a summary whose lookup completed at every
    source and found no abstract. `failed` is every ref whose lookup could not
    complete at some source (a batch that raised) and that no later source
    filled — reported separately because a failed fetch is not "no abstract"
    and must not be silently folded into `missing`. `stale` is every ref whose
    hand-added (landing-page) entry records other ids than the row now has: it
    is kept as it is, but it is not this paper's abstract any more.
    """
    ab, stale = dict(existing), []
    for r in rows:
        k, e = r.get(keyf), ab.get(r.get(keyf))
        if isinstance(e, dict) and common.stamp_ids(e) != common.ids_of(r):
            if e.get("source") == "landing-page":
                stale.append(k)
            else:
                del ab[k]            # fetched for other ids: fetch it again for these
    todo = [r for r in rows if r.get(keyf) not in ab]
    by = {r.get(keyf): r for r in rows}
    failed_refs = {}

    def take(source, key_of, fetch):
        nonlocal todo
        want = {r.get(keyf): key_of(r) for r in todo if key_of(r)}
        if not want:
            return
        got, failed_keys = fetch(sorted(set(want.values())))
        for ref, k in want.items():
            if got.get(k):
                d, a = common.ids_of(by[ref])
                ab[ref] = {"text": got[k], "source": source, "url": "", "doi": d, "arxiv": a}
            elif k in failed_keys:
                failed_refs.setdefault(ref, []).append(source)
        todo = [r for r in todo if r.get(keyf) not in ab]

    take("arxiv", lambda r: common.norm_arxiv(common.arxiv_id_of(r) or ""), fetchers["arxiv"])
    take("openalex", lambda r: common.doi_of(r, lower=True) or "", fetchers["openalex"])
    take("s2", _s2_id, fetchers["s2"])
    take("pubmed", lambda r: str(r.get("pmid") or ""), fetchers["pubmed"])
    # a later source may still have found it
    failed = {r.get(keyf): f"{'/'.join(failed_refs[r.get(keyf)])} lookup could not complete"
              for r in rows if r.get(keyf) in failed_refs and r.get(keyf) not in ab}
    missing = [r.get(keyf) for r in rows if (r.get("summary") or "").strip()
               and r.get(keyf) not in ab and r.get(keyf) not in failed_refs]
    return ab, missing, failed, stale


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", help="default: abstracts.json beside --rows")
    ap.add_argument("--key", default=None, help="row key field (default: ref, else label)")
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"))
    args = ap.parse_args()
    if not args.email:
        ap.error("--email or LITREVIEW_EMAIL required (arXiv/OpenAlex polite pool)")
    common.set_user_agent(args.email)
    rows = common.load_json(args.rows)
    keyf = common.key_field(rows, args.key)
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.rows)), "abstracts.json")
    existing = common.load_optional_json(out, {})
    fetchers = {"arxiv": fetch_arxiv, "openalex": make_fetch_openalex(re.sub(r"\s", "", args.email)),
                "s2": fetch_s2, "pubmed": fetch_pubmed}
    ab, missing, failed, stale = collect(rows, keyf, existing, fetchers)
    common.dump_json(ab, out)
    common.dump_json(failed, os.path.join(os.path.dirname(os.path.abspath(out)), "abstracts_failed.json"))
    by = {}
    for v in ab.values():
        by[v["source"]] = by.get(v["source"], 0) + 1
    print(f"{len(ab)} abstracts -> {out} ({', '.join(f'{k} {n}' for k, n in sorted(by.items()))})")
    if missing:
        print(f"  {len(missing)} row(s) with a summary and no abstract (add a landing-page entry, "
              f"or acknowledge no-abstract later): {', '.join(missing)}")
    for k in stale:
        print(f"  ✗ {k}: its landing-page abstract records other ids than the row now has; check it is "
              "this paper's, then set its doi/arxiv to the row's (or delete it and re-run)", file=sys.stderr)
    if failed:
        print(f"  {len(failed)} row(s) fetch failed — re-run abstracts.py; this is not 'no abstract': "
              f"{', '.join(failed)}", file=sys.stderr)
    if failed or stale:
        sys.exit(1)


if __name__ == "__main__":
    main()
