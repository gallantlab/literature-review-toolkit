#!/usr/bin/env python3
"""The candidate ledger: every paper xref or forward citations suggest gets a recorded decision.

candidates.json maps DOI -> {title, year, first_author, sources, decision, reason, at},
plus `_runs`: {source: {at, n}}, recorded by each --add, so the audit can tell
that xref and forward citations were actually run. Keys starting with "_" are
records, not candidates.
The audit fails while any candidate is pending, and the spreadsheet lists every
excluded one with its reason, so a paper that is not in the review was visibly
considered and set aside.

    python3 tools/candidates.py --rows rows.json --add xref.json --source xref
    python3 tools/candidates.py --rows rows.json --add forward_candidates.json --source forward
    python3 tools/candidates.py --rows rows.json --list pending
    python3 tools/candidates.py --rows rows.json --decide 10.1/x --decision exclude --reason "methods paper"
    python3 tools/candidates.py --rows rows.json --export-included xref_lane.json --lane X
"""
import argparse
import datetime
import os
import re
import sys

import common

PHASE = "6"   # pipeline phase, read by tools/gen_docs.py for the tool index


def _doi(d):
    return re.sub(r"(?i)^https?://(dx\.)?doi\.org/", "", (d or "").strip()).lower()


def entries(ledger):
    """(doi, candidate) pairs, sorted; skips "_" record keys such as _runs."""
    return [(d, c) for d, c in sorted(ledger.items()) if not d.startswith("_")]


def corpus_dois(rows):
    """Every row's DOI, lowercased; an arXiv-only row counts by its arXiv DOI."""
    out = set()
    for r in rows:
        aid = common.arxiv_id_of(r)
        d = common.doi_of(r) or (f"10.48550/arXiv.{common.norm_arxiv(aid)}" if aid else "")
        if d:
            out.add(_doi(d))
    return out


def add(ledger, found, source, corpus, asof=None):
    """Record `found` (xref / forward output) as candidates, and the run itself
    under ledger["_runs"][source]."""
    runs = ledger.setdefault("_runs", {})
    runs[source] = {"at": asof or datetime.date.today().isoformat(), "n": len(found)}
    added = skipped = 0
    for e in found:
        d = _doi(e.get("doi"))
        if not d:
            continue
        if d in corpus:
            skipped += 1
            continue
        score = e.get("shared") if source == "forward" else e.get("n_citations")
        c = ledger.get(d)
        if c is None:
            ledger[d] = {"title": e.get("title") or "", "year": str(e.get("year") or ""),
                         "first_author": e.get("first_author") or e.get("author") or "",
                         "sources": {source: score}, "decision": "pending", "reason": "", "at": ""}
            added += 1
        else:
            c["sources"][source] = score
            for f, v in (("title", e.get("title")), ("year", str(e.get("year") or "")),
                         ("first_author", e.get("first_author") or e.get("author"))):
                c[f] = c.get(f) or v or ""
    return added, skipped


def decide(ledger, doi, decision, reason, asof):
    d = _doi(doi)
    if d not in ledger or d.startswith("_"):
        raise ValueError(f"{doi} is not in the ledger")
    if decision not in ("include", "exclude"):
        raise ValueError("--decision must be include or exclude")
    if not (reason or "").strip():
        raise ValueError("--reason is required")
    ledger[d].update(decision=decision, reason=reason.strip(), at=asof)


def export_included(ledger, corpus, lane):
    papers = []
    for d, c in entries(ledger):
        if c.get("decision") == "include" and d not in corpus:
            papers.append({"ref": f"{lane}-{len(papers) + 1:02d}", "doi": d, "arxiv": "",
                           "link": f"https://doi.org/{d}", "first_author": c.get("first_author", ""),
                           "year": c.get("year", ""), "title": c.get("title", ""), "apa": "", "summary": "",
                           "tag": "xref", "topic": "", "source": "xref", "note": "", "lane_fit": ""})
    return {"schema": 2, "lane": lane, "status": {"target": len(papers), "returned": len(papers),
                                                  "websearch_exhausted": False, "notes": "candidate ledger"},
            "papers": papers, "deferred": [], "could_not_confirm": []}


def candidate_defects(ledger, corpus):
    out = []
    pending = [d for d, c in entries(ledger) if c.get("decision") not in ("include", "exclude")]
    if pending:
        out.append(f"candidates-pending: {len(pending)} undecided (candidates.py --list pending)")
    for d, c in entries(ledger):
        if c.get("decision") == "include" and d not in corpus:
            out.append(f"candidate {d} is marked include but is not in the table (export, append, verify)")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--ledger", help="default: candidates.json beside --rows")
    ap.add_argument("--add", metavar="FILE")
    ap.add_argument("--source", choices=("xref", "forward", "survey"))
    ap.add_argument("--list", choices=("pending", "include", "exclude", "all"))
    ap.add_argument("--decide", metavar="DOI")
    ap.add_argument("--decision", choices=("include", "exclude"))
    ap.add_argument("--reason")
    ap.add_argument("--export-included", metavar="OUT")
    ap.add_argument("--lane", default="X", help="lane key for --export-included refs (default X)")
    ap.add_argument("--asof", default=datetime.date.today().isoformat())
    args = ap.parse_args()
    rows = common.load_json(args.rows)
    path = args.ledger or os.path.join(os.path.dirname(os.path.abspath(args.rows)), "candidates.json")
    ledger = common.load_optional_json(path, {})
    corpus = corpus_dois(rows)
    if args.add:
        if not args.source:
            ap.error("--add needs --source")
        a, s = add(ledger, common.load_json(args.add), args.source, corpus, args.asof)
        common.dump_json(ledger, path)
        print(f"added {a} candidate(s), skipped {s} already in the corpus -> {path}")
    elif args.decide:
        try:
            decide(ledger, args.decide, args.decision, args.reason, args.asof)
        except ValueError as e:
            ap.error(str(e))
        common.dump_json(ledger, path)
        print(f"{args.decide}: {args.decision}")
    elif args.export_included:
        lane = export_included(ledger, corpus, args.lane)
        common.dump_json(lane, args.export_included)
        print(f"{len(lane['papers'])} included paper(s) -> {args.export_included}; "
              f"next: merge_lanes.py --append {args.export_included} --into {args.rows}")
    elif args.list:
        for d, c in entries(ledger):
            if args.list == "all" or c.get("decision") == args.list:
                print(f"{d}\t{c.get('decision')}\t{c.get('year')}\t{c.get('first_author')}\t{c.get('title')}\t"
                      f"{c.get('sources')}\t{c.get('reason')}")
    else:
        ap.error("give one of --add, --decide, --export-included, --list")
    for x in candidate_defects(ledger, corpus):
        print(f"  · {x}", file=sys.stderr)


if __name__ == "__main__":
    main()
