#!/usr/bin/env python3
"""Fetch the abstract of every row, in batches, into abstracts.json.

Summaries are checked against these (summary_audit.py), so each row's abstract
comes from the most authoritative source that has it: the arXiv API for arXiv
papers, then OpenAlex (50 DOIs per request), then Semantic Scholar (500 per
request), then PubMed for rows with a PMID. An existing entry is never
overwritten, so an abstract added by hand ("source": "landing-page") stays.

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
    entries, _err = common.arxiv_batch(aids)
    return {a: e["summary"] for a, e in entries.items() if e.get("summary")}


def make_fetch_openalex(email):
    def fetch(dois):
        out = {}
        for i in range(0, len(dois), 50):
            filt = "doi:" + "|".join(dois[i:i + 50])
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
        return out
    return fetch


def fetch_s2(ids):
    out = {}
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        try:
            res = common.s2_request("paper/batch?fields=abstract", {"ids": part})
        except Exception as e:
            print(f"  S2 batch {i}: {type(e).__name__}: {e}", file=sys.stderr)
            break
        for sid, p in zip(part, res):
            if p and p.get("abstract"):
                out[sid] = p["abstract"]
    return out


def fetch_pubmed(pmids):
    out = {}
    for i in range(0, len(pmids), 200):
        part = pmids[i:i + 200]
        url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id="
               + ",".join(part))
        try:
            root = ET.fromstring(common.http(url))
        except Exception as e:
            print(f"  PubMed batch {i}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        for art in root.findall(".//PubmedArticle"):
            pmid = art.findtext(".//PMID") or ""
            text = " ".join("".join(t.itertext()).strip() for t in art.findall(".//Abstract/AbstractText"))
            if pmid and text.strip():
                out[pmid] = " ".join(text.split())
    return out


def _s2_id(row):
    aid = common.arxiv_id_of(row)
    if aid:
        return f"ARXIV:{common.norm_arxiv(aid)}"
    d = common.doi_of(row)
    return f"DOI:{d}" if d else ""


def collect(rows, keyf, existing, fetchers):
    """-> ({ref: {text, source, url}}, [refs with a summary and no abstract])."""
    ab = dict(existing)
    todo = [r for r in rows if r.get(keyf) not in ab]

    def take(source, key_of, fetch):
        nonlocal todo
        want = {r.get(keyf): key_of(r) for r in todo if key_of(r)}
        if not want:
            return
        got = fetch(sorted(set(want.values())))
        for ref, k in want.items():
            if got.get(k):
                ab[ref] = {"text": got[k], "source": source, "url": ""}
        todo = [r for r in todo if r.get(keyf) not in ab]

    take("arxiv", lambda r: common.norm_arxiv(common.arxiv_id_of(r) or ""), fetchers["arxiv"])
    take("openalex", lambda r: (common.doi_of(r) or "").lower(), fetchers["openalex"])
    take("s2", _s2_id, fetchers["s2"])
    take("pubmed", lambda r: str(r.get("pmid") or ""), fetchers["pubmed"])
    missing = [r.get(keyf) for r in rows if (r.get("summary") or "").strip() and r.get(keyf) not in ab]
    return ab, missing


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
    ab, missing = collect(rows, keyf, existing, fetchers)
    common.dump_json(ab, out)
    by = {}
    for v in ab.values():
        by[v["source"]] = by.get(v["source"], 0) + 1
    print(f"{len(ab)} abstracts -> {out} ({', '.join(f'{k} {n}' for k, n in sorted(by.items()))})")
    if missing:
        print(f"  {len(missing)} row(s) with a summary and no abstract (add a landing-page entry, "
              f"or acknowledge no-abstract later): {', '.join(missing)}")


if __name__ == "__main__":
    main()
