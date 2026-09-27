#!/usr/bin/env python3
"""Measure a rerun's recall against the old build, and list the papers it missed.

A redo of an old bibliography should find what the old build had. This tool
matches every old row against the new table (by DOI, then arXiv id, then title
via common.title_match) and writes the misses as the input for ONE recovery lane,
whose agent decides each miss again (include, with a claim read off the landing
page, or exclude, with a reason). The old reference is a pointer, not a claim.

    python3 tools/recall.py --rows rows.json --old ../old_build/rows.json \\
            --where source=search --out manual_check/recovery_input.json

--where KEY=VALUE keeps only the old rows whose field matches (repeatable), e.g.
source=search to compare field papers only. Prints the recall and writes
[{"old_ref", "doi", "reference_in_old_build", "old_family"}] for the misses, to
recovery_input.json beside --rows unless --out names another file. Add the
recovery lane's file to the table with `merge_lanes.py --append`.
"""
import argparse
import os
import sys

import common

PHASE = "2c"   # pipeline phase, read by tools/gen_docs.py for the tool index


def _title(r):
    return (r.get("search_title") or (common.parse_apa(r.get("apa") or "") or {}).get("title") or "").strip()


def misses(new_rows, old_rows):
    """(found count, [missed old rows]) matching by DOI, arXiv id, then title."""
    dois = {d for d in (common.doi_of(r, lower=True) for r in new_rows) if d}
    aids = {common.norm_arxiv(a).lower() for a in (common.arxiv_id_of(r) for r in new_rows) if a}
    titles = [t for t in (_title(r) for r in new_rows) if t]
    found, missed = 0, []
    for r in old_rows:
        d = common.doi_of(r, lower=True)
        a = common.norm_arxiv(common.arxiv_id_of(r) or "").lower()
        t = _title(r)
        if (d and d in dois) or (a and a in aids) or (t and any(common.title_match(t, x) for x in titles)):
            found += 1
        else:
            missed.append(r)
    return found, missed


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--rows", required=True, help="the new table")
    ap.add_argument("--old", required=True, help="the old build's rows.json")
    ap.add_argument("--where", action="append", default=[], metavar="KEY=VALUE",
                    help="compare only old rows whose field equals the value (repeatable)")
    ap.add_argument("--out", help="recovery-lane input to write (default: recovery_input.json beside --rows)")
    ap.add_argument("--key", default=None, help="old table's row key field (default: ref, else label)")
    args = ap.parse_args()
    new, old = common.load_json(args.rows), common.load_json(args.old)
    for w in args.where:
        if "=" not in w:
            ap.error(f"--where needs KEY=VALUE, got {w!r}")
        k, v = w.split("=", 1)
        old = [r for r in old if str(r.get(k, "")) == v]
    if not old:
        sys.exit("✗ no old rows to compare (check --old and --where)")
    keyf = common.key_field(old, args.key)
    found, missed = misses(new, old)
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.rows)), "recovery_input.json")
    common.dump_json([{"old_ref": r.get(keyf), "doi": common.doi_of(r) or "",
                       "reference_in_old_build": r.get("apa") or _title(r),
                       "old_family": r.get("family") or r.get("topic") or ""} for r in missed], out)
    print(f"recall: the new table has {found} of the old build's {len(old)} papers "
          f"({100 * found / len(old):.0f}%); {len(missed)} missed -> {out}")
    if missed:
        print("  send them to ONE recovery lane: its agent decides each again (include with a claim "
              "read off the landing page, or exclude with a reason), then merge_lanes.py --append")
    return 0


if __name__ == "__main__":
    sys.exit(main())
