#!/usr/bin/env python3
"""Merge search-lane files into rows.json, and fail when a paper fell between lanes.

Reads every schema-2 lane file (tools/search_prompt_template.md) in --raw and:
  - dedups by DOI, then arXiv id, then normalized title + year, recording the
    other lanes that returned a paper (`also_lanes`);
  - keeps each agent's claim as search_author / search_year / search_title, which
    verify.py checks the DOI against;
  - rejects a paper with no DOI, arXiv id or APA string (it can be neither
    verified nor hand-checked);
  - matches every `deferred` entry against the merged table and exits 1 on any
    that no lane kept — send those to a recovery lane and re-merge;
  - flags thin lanes (under 60% of target, or out of search budget) to resume.

    python3 tools/merge_lanes.py --raw search_raw --out rows.json
    python3 tools/merge_lanes.py --append recovery.json --into rows.json   # late rows
"""
import argparse
import datetime
import glob
import os
import re
import sys

import common
import verify

PHASE = "2c"   # pipeline phase, read by tools/gen_docs.py for the tool index

THIN = 0.6
DEFERRAL_TITLE_MATCH = 0.9   # a title-only deferral match needs a closer score than a DOI/arXiv one
PAIR_MATCH = 0.9


def load_lane(path, allow_v1=False):
    d = common.load_json(path)
    name = os.path.splitext(os.path.basename(path))[0]
    if isinstance(d, list):
        if not allow_v1:
            raise ValueError(f"{path}: schema-1 lane file (a bare list, no deferred list); "
                             "ask the lane for the schema-2 object, or pass --allow-v1")
        return {"schema": 1, "lane": name, "status": {}, "papers": d, "deferred": None,
                "could_not_confirm": []}
    if not isinstance(d, dict) or d.get("schema") != 2:
        raise ValueError(f"{path}: not a schema-2 lane file")
    for k in ("lane", "papers", "deferred"):
        if k not in d:
            raise ValueError(f"{path}: missing {k!r}")
    return d


def _bare(d):
    return re.sub(r"(?i)^https?://(dx\.)?doi\.org/", "", (d or "").strip())


def _tkey(title, year):
    t = " ".join(re.sub(r"[^a-z0-9 ]", " ", (title or "").lower()).split())
    return f"{t}|{year}" if t else ""


def to_row(p, lane):
    link = p.get("link") or ""
    doi = _bare(p.get("doi") or "") or (_bare(link) if "doi.org/" in link else "")
    m = common.ARXIV_DOI.match(doi)
    arxiv = common.norm_arxiv(p.get("arxiv") or (m.group(1) if m else ""))
    sourced = bool(doi or arxiv)
    return {"ref": p.get("ref"), "lane": lane, "topic": p.get("topic", ""), "doi": doi, "arxiv": arxiv,
            "link": f"https://doi.org/{doi}" if doi else (p.get("link") or ""),
            "apa": "" if sourced else (p.get("apa") or ""), "search_apa": p.get("apa") or "",
            "search_author": p.get("first_author") or "", "search_year": p.get("year") or "",
            "search_title": p.get("title") or "", "summary": p.get("summary") or "",
            "tag": p.get("tag") or "", "source": p.get("source") or "search", "note": p.get("note") or "",
            "lane_fit": p.get("lane_fit") or "",
            # the build date gates the table (common.is_gated) even if verify is never run
            "built_at": datetime.date.today().isoformat()}


def _keys(row):
    ks = []
    if row.get("doi"):
        ks.append(("doi", row["doi"].lower()))
    if row.get("arxiv"):
        ks.append(("arxiv", row["arxiv"].lower()))
    title = row.get("search_title") or ((common.parse_apa(row.get("apa") or "") or {}).get("title") or "")
    year = row.get("search_year") or ((common.parse_apa(row.get("apa") or "") or {}).get("year") or "")
    tk = _tkey(title, year)
    if tk:
        ks.append(("title", tk))
    return ks


def index_rows(rows):
    """{(kind, value): row} over DOI, arXiv id and title+year. Also used by
    --append (Task 13) to check a late lane's papers against the existing table."""
    idx = {}
    for r in rows:
        for k in _keys(r):
            idx.setdefault(k, r)
    return idx


def _conflict(a, b):
    sa = verify.claim_surname(a.get("search_author")).lower()
    sb = verify.claim_surname(b.get("search_author")).lower()
    ya, yb = str(a.get("search_year") or ""), str(b.get("search_year") or "")
    if sa and sb and sa not in sb and sb not in sa:
        return f"first author {a.get('search_author')!r} vs {b.get('search_author')!r}"
    if ya.isdigit() and yb.isdigit() and abs(int(ya) - int(yb)) > 1:
        return f"year {ya} vs {yb}"
    return ""


def _is_journal_doi(doi):
    """True for a real (non-arXiv) DOI: a paper's arXiv DOI and its journal DOI
    are the same paper, so only two DIFFERENT journal DOIs are a real conflict."""
    return bool(doi) and not common.ARXIV_DOI.match(doi)


def _title_only_gate(hit, row):
    """A title+year key hit alone is only a strong hint — a conflicting claimed
    author/year, or two different journal DOIs (an arXiv preprint's DOI + its
    own journal DOI is not a conflict), means `hit` and `row` are two distinct
    papers that happen to share a title+year, not a duplicate. Returns a reason
    string in that case (the gate FAILS: don't treat them as the same paper),
    or "" when the gate passes (treat `hit` as the same paper as `row`).
    Shared by merge()'s dedup pass and append()'s existing-table check."""
    why = _conflict(hit, row)
    diff_dois = _is_journal_doi(hit.get("doi")) and _is_journal_doi(row.get("doi")) \
        and hit["doi"].lower() != row["doi"].lower()
    if why or diff_dois:
        return f"same title and year, {why or 'different DOIs'}"
    return ""


def _defer_agrees(d, row):
    """True unless a deferred entry's OPTIONAL first_author/year contradicts the
    claim on `row`, a candidate it might match by title alone. Absent fields
    impose no constraint; a given field must agree (surname containment either
    way for the author, within a year for the year) or the match is refused —
    a title-only hit is too weak to accept over a claim mismatch."""
    fa = d.get("first_author")
    if fa:
        sa = verify.claim_surname(fa).lower()
        sb = verify.claim_surname(row.get("search_author")).lower()
        if not (sa and sb and (sa in sb or sb in sa)):
            return False
    dy = d.get("year")
    if dy not in (None, ""):
        ry = str(row.get("search_year") or "")
        if not (str(dy).isdigit() and ry.isdigit() and abs(int(dy) - int(ry)) <= 1):
            return False
    return True


def merge(lanes):
    rows, idx, refs = [], {}, set()
    rep = {"lanes": [], "duplicates": [], "conflicts": [], "possible_pairs": [], "rejected": [],
           "deferrals_matched": [], "matched_by_title": [], "lost": [], "thin": [], "no_deferral_check": []}
    for lane in lanes:
        name = lane["lane"]
        for p in lane["papers"]:
            row = to_row(p, name)
            if row["ref"] in refs:
                raise ValueError(f"ref {row['ref']!r} appears twice; lane refs must be unique")
            refs.add(row["ref"])
            if not (row["doi"] or row["arxiv"] or row["apa"]):
                rep["rejected"].append({"ref": row["ref"], "lane": name,
                                        "reason": "no DOI, arXiv id or APA string: it can be neither "
                                                  "verified nor hand-checked"})
                continue
            ks = _keys(row)
            hit, hit_kind = None, None
            for k in ks:
                if k in idx:
                    hit, hit_kind = idx[k], k[0]
                    break
            if hit is not None:
                why = _conflict(hit, row)
                if hit_kind == "title":
                    # A DOI or arXiv key hit IS the same paper; a title+year key
                    # hit alone goes through the shared gate — if it fails, keep
                    # both and flag the pair instead.
                    reason = _title_only_gate(hit, row)
                    if reason:
                        rep["possible_pairs"].append({"a": hit["ref"], "b": row["ref"], "why": reason})
                        hit = None
            if hit is not None:
                if name != hit["lane"] and name not in hit.setdefault("also_lanes", []):
                    hit["also_lanes"].append(name)
                rep["duplicates"].append({"ref": row["ref"], "same_as": hit["ref"]})
                if why:
                    rep["conflicts"].append({"ref": row["ref"], "same_as": hit["ref"], "why": why})
                continue
            rows.append(row)
            for k in ks:
                idx.setdefault(k, row)
        st = lane.get("status") or {}
        target, returned = st.get("target") or 0, len(lane["papers"])
        rep["lanes"].append({"lane": name, "target": target, "returned": returned})
        if (target and returned < THIN * target) or st.get("websearch_exhausted"):
            rep["thin"].append({"lane": name, "target": target, "returned": returned,
                                "websearch_exhausted": bool(st.get("websearch_exhausted"))})
    titles = [(r["ref"], r.get("search_title") or "") for r in rows]
    for i, (ka, ta) in enumerate(titles):
        for kb, tb in titles[i + 1:]:
            s = common.title_score(ta, tb)
            if s is not None and s >= PAIR_MATCH:
                rep["possible_pairs"].append({"a": ka, "b": kb, "score": round(s, 3)})
    for lane in lanes:
        if lane["deferred"] is None:
            rep["no_deferral_check"].append(lane["lane"])
            continue
        for d in lane["deferred"]:
            doi = _bare(d.get("doi") or "").lower()
            match, score = (idx.get(("doi", doi)) if doi else None), None
            if match is None:
                for r in rows:
                    s = common.title_score(d.get("title"), r.get("search_title")) or 0
                    if s >= DEFERRAL_TITLE_MATCH and _defer_agrees(d, r):
                        match, score = r, s
                        break
            entry = dict(d, from_lane=lane["lane"])
            (rep["deferrals_matched"] if match is not None else rep["lost"]).append(
                dict(entry, found_as=match["ref"]) if match is not None else entry)
            if match is not None and score is not None:
                rep["matched_by_title"].append({"title": d.get("title"), "from_lane": lane["lane"],
                                                "found_as": match["ref"], "score": round(score, 3)})
    return rows, rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", help="directory of lane files (*.json)")
    ap.add_argument("--out", help="rows.json to write (refuses a canonical table)")
    ap.add_argument("--report", help="default: merge_report.json beside --out")
    ap.add_argument("--allow-v1", action="store_true", help="accept schema-1 lane files (no deferral check)")
    ap.add_argument("--force", action="store_true", help="overwrite even a canonical rows.json")
    ap.add_argument("--append", metavar="LANE_FILE", help="add a lane file's papers to an existing table")
    ap.add_argument("--into", metavar="ROWS", help="the table --append adds to")
    args = ap.parse_args()
    if args.append:
        return main_append(ap, args)
    if not (args.raw and args.out):
        ap.error("give --raw and --out (or --append and --into)")
    lanes = [load_lane(p, args.allow_v1) for p in sorted(glob.glob(os.path.join(args.raw, "*.json")))]
    if not lanes:
        ap.error(f"no lane files in {args.raw}")
    rows, rep = merge(lanes)
    common.write_rows(args.out, rows, force=args.force)
    rp = args.report or os.path.join(os.path.dirname(os.path.abspath(args.out)), "merge_report.json")
    common.dump_json(rep, rp)
    print(f"{len(rows)} rows from {len(lanes)} lanes -> {args.out} | {len(rep['duplicates'])} duplicates | "
          f"{len(rep['possible_pairs'])} possible preprint/published pairs | report {rp}")
    for c in rep["conflicts"]:
        print(f"  ⚠ {c['ref']} = {c['same_as']} but the claims differ: {c['why']}")
    for t in rep["thin"]:
        budget = ", out of search budget" if t["websearch_exhausted"] else ""
        print(f"  ⚠ lane {t['lane']} is thin ({t['returned']}/{t['target']}{budget}): "
              "resume it via SendMessage")
    for lane in rep["no_deferral_check"]:
        print(f"  ⚠ lane {lane} is schema 1: its deferrals could not be checked")
    for m in rep["matched_by_title"]:
        print(f"  · deferral \"{m['title']}\" ({m['from_lane']}) matched {m['found_as']} by title only "
              f"({m['score']}) — check it")
    for x in rep["rejected"]:
        print(f"  ✗ {x['ref']} ({x['lane']}): {x['reason']}")
    for d in rep["lost"]:
        print(f"  ✗ LOST: {d.get('title')!r} (deferred by {d['from_lane']}: {d.get('reason', '')}); "
              "no lane kept it — send it to a recovery lane")
    sys.exit(1 if rep["lost"] or rep["rejected"] else 0)


def append(rows, keyf, lane):
    """Add a lane's papers to an existing (possibly canonical) table; never
    touch an existing row. A hit against only the title+year key goes through
    the same gate merge() uses (`_title_only_gate`): if it fails — a
    conflicting claim, or two different non-arXiv DOIs — the papers are two
    distinct works that happen to share a title+year, so the new one is
    appended (not skipped) and the pair is recorded for a human verdict.
    Returns (added [ref], skipped [{ref, reason}], pairs [{a, b, why}])."""
    idx = index_rows(rows)
    refs = {r.get(keyf) for r in rows}
    added, skipped, pairs = [], [], []
    for p in lane["papers"]:
        row = to_row(p, lane["lane"])
        if not (row["doi"] or row["arxiv"] or row["apa"]):
            skipped.append({"ref": row["ref"], "reason": "no DOI, arXiv id or APA string"})
            continue
        hit, hit_kind = None, None
        for k in _keys(row):
            if k in idx:
                hit, hit_kind = idx[k], k[0]
                break
        if hit is not None and hit_kind == "title":
            reason = _title_only_gate(hit, row)
            if reason:
                pairs.append({"a": hit.get(keyf), "b": row["ref"], "why": reason})
                hit = None
        if hit is not None:
            skipped.append({"ref": row["ref"], "reason": f"already in the table as {hit.get(keyf)}"})
            continue
        if row["ref"] in refs:
            raise ValueError(f"ref {row['ref']!r} is already used in the table; renumber the lane")
        row[keyf] = row.pop("ref") if keyf != "ref" else row["ref"]
        rows.append(row)
        refs.add(row[keyf])
        for k in _keys(row):
            idx.setdefault(k, row)
        added.append(row[keyf])
    return added, skipped, pairs


def main_append(ap, args):
    if not args.into:
        ap.error("--append needs --into rows.json")
    rows = common.load_json(args.into)
    keyf = common.key_field(rows)
    added, skipped, pairs = append(rows, keyf, load_lane(args.append, args.allow_v1))
    common.dump_json(rows, args.into)
    print(f"appended {len(added)} row(s) to {args.into}; run verify.py --rows --only {','.join(added)}")
    for s in skipped:
        print(f"  · {s['ref']}: {s['reason']}")
    for pr in pairs:
        print(f"  ⚠ {pr['b']}: possible duplicate of {pr['a']} kept for a human verdict: {pr['why']}")


if __name__ == "__main__":
    main()
