#!/usr/bin/env python3
"""Check every row's summary against its abstract, by checking agents with no web access.

  --prepare   write summary_audit/batch_NN.json (summary + abstract pairs), a
              brief for the checking agents, and a manifest
  --ingest    read summary_audit/result_NN.json and record `summary_check` on
              each row, with a hash of the summary it checked

A row with no abstract is recorded as `no-abstract` (a warning the audit makes
you acknowledge). A summary edited after --prepare is refused at --ingest.

    python3 tools/summary_audit.py --rows rows.json --prepare
    python3 tools/summary_audit.py --rows rows.json --ingest
"""
import argparse
import datetime
import glob
import os
import sys

import common

PHASE = "5c"   # pipeline phase, read by tools/gen_docs.py for the tool index

BRIEF = """# Summary check

Each file summary_audit/batch_NN.json holds rows of {ref, summary, abstract}. For every
row, decide whether the SUMMARY is supported by the ABSTRACT. You have no web access
and need none: judge only against the abstract given.

- "supported": every factual claim in the summary (what was done, what was found, the
  direction of every effect, every number) is stated in or directly implied by the
  abstract. Paraphrase is fine. A closing sentence on why the paper matters for the
  review's topic is fine if it asserts no finding.
- "unsupported": anything else, including an inverted finding, a number or method the
  abstract does not give, or a claim of priority or impact the abstract does not make.
  Quote the unsupported clause exactly.

Write summary_audit/result_NN.json (same NN) as a JSON list of
  {"ref": "...", "verdict": "supported" | "unsupported", "unsupported_clause": "..."}
with one entry for every row in the batch. Do not delegate to subagents.
"""


def _checked(row, abstracts, key):
    s = (row.get("summary") or "").strip()
    sc = row.get("summary_check")
    if not isinstance(sc, dict) or sc.get("summary_sha") != common.summary_sha(s):
        return False
    has_abs = bool(((abstracts.get(key) or {}).get("text") or "").strip())
    return sc.get("verdict") == "supported" or (sc.get("verdict") == "no-abstract" and not has_abs)


def prepare(rows, keyf, abstracts, batch=40, recheck=False):
    todo, no_abs, sha = [], [], {}
    for r in rows:
        k, s = r.get(keyf), (r.get("summary") or "").strip()
        if not s or (not recheck and _checked(r, abstracts, k)):
            continue
        sha[k] = common.summary_sha(s)
        a = abstracts.get(k) or {}
        if not (a.get("text") or "").strip():
            no_abs.append(k)
            continue
        todo.append({"ref": k, "summary": s, "abstract": a["text"], "abstract_source": a.get("source")})
    batches = [todo[i:i + batch] for i in range(0, len(todo), batch)]
    manifest = {"refs": [x["ref"] for x in todo], "sha": sha, "no_abstract": no_abs}
    return batches, no_abs, manifest


def ingest(rows, keyf, results, abstracts, manifest, asof):
    by = {r.get(keyf): r for r in rows}
    n, errors, seen = 0, [], set()

    def stamp(row, k, verdict, note):
        row["summary_check"] = {"verdict": verdict, "note": note,
                                "abstract_source": (abstracts.get(k) or {}).get("source"),
                                "summary_sha": common.summary_sha(row.get("summary")), "at": asof}

    for res in results:
        k, v = res.get("ref"), res.get("verdict")
        row = by.get(k)
        seen.add(k)
        if row is None or k not in manifest["refs"]:
            errors.append(f"{k}: not in this summary audit")
            continue
        if common.summary_sha(row.get("summary")) != manifest["sha"].get(k):
            errors.append(f"{k}: summary changed since --prepare; re-run --prepare")
            continue
        if v not in ("supported", "unsupported"):
            errors.append(f"{k}: verdict {v!r} is not supported/unsupported")
            continue
        clause = str(res.get("unsupported_clause") or "").strip()
        if v == "unsupported" and not clause:
            errors.append(f"{k}: unsupported without the unsupported clause")
            continue
        stamp(row, k, v, clause)
        n += 1
    for k in manifest["refs"]:
        if k not in seen:
            errors.append(f"{k}: no result returned")
    for k in manifest["no_abstract"]:
        row = by.get(k)
        if row is not None and common.summary_sha(row.get("summary")) == manifest["sha"].get(k):
            stamp(row, k, "no-abstract", "")
            n += 1
    return n, errors


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--key", default=None, help="row key field (default: ref, else label)")
    ap.add_argument("--abstracts", help="default: abstracts.json beside --rows")
    ap.add_argument("--dir", help="batch/result directory (default: summary_audit/ beside --rows)")
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--ingest", action="store_true")
    ap.add_argument("--batch", type=int, default=40, help="rows per checking agent (default 40)")
    ap.add_argument("--recheck", action="store_true", help="re-check rows that already passed")
    ap.add_argument("--asof", default=datetime.date.today().isoformat())
    args = ap.parse_args()
    if args.prepare == args.ingest:
        ap.error("give exactly one of --prepare, --ingest")
    here = os.path.dirname(os.path.abspath(args.rows))
    d = args.dir or os.path.join(here, "summary_audit")
    rows = common.load_json(args.rows)
    keyf = common.key_field(rows, args.key)
    ab = common.load_optional_json(args.abstracts or os.path.join(here, "abstracts.json"), {})
    if args.prepare:
        batches, no_abs, manifest = prepare(rows, keyf, ab, args.batch, args.recheck)
        os.makedirs(d, exist_ok=True)
        for old in glob.glob(os.path.join(d, "batch_*.json")) + glob.glob(os.path.join(d, "result_*.json")):
            os.remove(old)
        for i, b in enumerate(batches, start=1):
            common.dump_json(b, os.path.join(d, f"batch_{i:02d}.json"))
        common.dump_json(manifest, os.path.join(d, "manifest.json"))
        with open(os.path.join(d, "brief.md"), "w", encoding="utf-8") as f:
            f.write(BRIEF)
        print(f"{len(batches)} batch(es) of up to {args.batch} in {d}; {len(no_abs)} row(s) have no abstract")
        return
    manifest = common.load_json(os.path.join(d, "manifest.json"))
    results = []
    for p in sorted(glob.glob(os.path.join(d, "result_*.json"))):
        results += common.load_json(p)
    n, errors = ingest(rows, keyf, results, ab, manifest, args.asof)
    common.dump_json(rows, args.rows)
    flagged = [r.get(keyf) for r in rows if (r.get("summary_check") or {}).get("verdict") == "unsupported"]
    print(f"recorded {n} summary check(s); {len(flagged)} flagged")
    for e in errors:
        print(f"  ✗ {e}")
    for k in flagged:
        print(f"  ✗ {k}: summary claims something its abstract does not; fix it, then --prepare again")
    sys.exit(1 if errors or flagged else 0)


if __name__ == "__main__":
    main()
