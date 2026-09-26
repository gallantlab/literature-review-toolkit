#!/usr/bin/env python3
"""Find papers that cite the corpus's landmark papers but are not in the corpus.

xref.py looks backward (what corpus papers cite); this looks forward. It takes the
landmarks (top N by within-corpus in-degree, then citation count), asks OpenAlex
for the most-cited papers citing each (up to --per-landmark), and scores each
citing paper by how many corpus papers it cites. Papers citing at least
--min-shared corpus papers become candidates for candidates.py. A citing paper is
recognized as already being in the corpus by its OpenAlex id or its DOI, so a
corpus row with no DOI (and whose id lookup failed) cannot be excluded from the
candidates. Because each pull is ordered by citation count, very recent papers
are under-represented.

    python3 tools/forward.py --rows rows.json --out forward_candidates.json --email you@inst.edu

Also writes `<out>.run.json` = {"complete", "incomplete": [refs whose landmark
pull failed], "at"} beside --out, so candidates.py --add can tell a partial run
from a full one.
"""
import argparse
import datetime
import os
import sys
import time
import urllib.parse

import common

PHASE = "6"   # pipeline phase, read by tools/gen_docs.py for the tool index

OA = "https://api.openalex.org/works"


def _short(wid):
    return (wid or "").rsplit("/", 1)[-1]


def pick_landmarks(rows, keyf, indeg, n):
    cand = [r for r in rows if common.doi_of(r)]
    cand.sort(key=lambda r: (-(indeg.get(r.get(keyf)) or 0), -(r.get("cite_openalex") or 0)))
    return cand[:n]


def openalex_ids(dois, email):
    out = {}
    for i in range(0, len(dois), 50):
        filt = "doi:" + "|".join(dois[i:i + 50])
        url = (f"{OA}?filter={urllib.parse.quote(filt, safe=':|/.')}"
               f"&per-page=100&select=id,doi&mailto={email}")
        for w in common.http_json(url).get("results", []):
            d = (w.get("doi") or "").lower().replace("https://doi.org/", "")
            if d:
                out[d] = _short(w.get("id"))
        time.sleep(0.2)
    return out


def citing(wid, per, email):
    url = (f"{OA}?filter=cites:{wid}&sort=cited_by_count:desc&per-page={min(per, 200)}"
           "&select=id,doi,display_name,publication_year,cited_by_count,authorships,referenced_works"
           f"&mailto={email}")
    return common.http_json(url).get("results", [])


def score(citing_by_landmark, corpus_wids, corpus_dois, min_shared):
    cands = {}
    for lref, works in citing_by_landmark.items():
        for w in works:
            wid = _short(w.get("id"))
            doi = (w.get("doi") or "").lower().replace("https://doi.org/", "")
            if wid in corpus_wids or (doi and doi in corpus_dois):
                continue
            shared = len({_short(x) for x in w.get("referenced_works") or []} & corpus_wids)
            if shared < min_shared:
                continue
            au = ((w.get("authorships") or [{}])[0].get("author") or {}).get("display_name", "")
            c = cands.setdefault(wid, {
                "doi": doi, "openalex_id": wid, "title": w.get("display_name") or "",
                "year": w.get("publication_year"), "first_author": au, "shared": shared,
                "cited_by_count": w.get("cited_by_count") or 0, "cites_landmarks": []})
            if lref not in c["cites_landmarks"]:
                c["cites_landmarks"].append(lref)
    out = sorted(cands.values(), key=lambda c: (-c["shared"], -c["cited_by_count"]))
    with_doi = [c for c in out if c["doi"]]
    return with_doi, len(out) - len(with_doi)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--key", default=None, help="row key field (default: ref, else label)")
    ap.add_argument("--internal",
                     help="xref --internal-out file (default: internal_citations.json beside --rows)")
    ap.add_argument("--out", help="default: forward_candidates.json beside --rows")
    ap.add_argument("--landmarks", type=int, default=30)
    ap.add_argument("--per-landmark", type=int, default=200)
    ap.add_argument("--min-shared", type=int, default=3)
    ap.add_argument("--allow-incomplete", action="store_true",
                    help="exit 0 even when some landmark pulls failed (said in the output)")
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"))
    args = ap.parse_args()
    if not args.email:
        ap.error("--email or LITREVIEW_EMAIL required (OpenAlex polite pool)")
    rows = common.load_json(args.rows)
    keyf = common.key_field(rows, args.key)
    here = os.path.dirname(os.path.abspath(args.rows))
    indeg = common.load_optional_json(args.internal or os.path.join(here, "internal_citations.json"), {})
    dois = sorted({common.doi_of(r, lower=True) for r in rows if common.doi_of(r)})
    wids = openalex_ids(dois, args.email)
    marks = pick_landmarks(rows, keyf, indeg, args.landmarks)
    by_landmark, failed = {}, []
    for r in marks:
        wid = wids.get(common.doi_of(r, lower=True))
        if not wid:
            print(f"  · {r.get(keyf)}: not in OpenAlex", file=sys.stderr)
            continue
        try:
            by_landmark[r.get(keyf)] = citing(wid, args.per_landmark, args.email)
        except Exception as e:
            print(f"  ✗ {r.get(keyf)}: {type(e).__name__}: {e}", file=sys.stderr)
            failed.append(r.get(keyf))
        time.sleep(0.2)
    cands, n_nodoi = score(by_landmark, set(wids.values()), set(dois), args.min_shared)
    out = args.out or os.path.join(here, "forward_candidates.json")
    common.dump_json(cands, out)
    common.dump_json({"complete": not failed, "incomplete": list(failed),
                      "at": datetime.date.today().isoformat()}, f"{out}.run.json")
    print(f"{len(cands)} candidate(s) from {len(by_landmark)} landmark(s) -> {out} "
          f"({n_nodoi} more had no DOI). Recent papers are under-represented (pulls are citation-ordered).")
    if failed:
        print(f"WARNING: {len(failed)} landmark pull(s) failed, so their citing papers are missing from "
              f"the candidates: {', '.join(failed)}. Re-run.", file=sys.stderr)
        sys.exit(0 if args.allow_incomplete else 1)


if __name__ == "__main__":
    main()
