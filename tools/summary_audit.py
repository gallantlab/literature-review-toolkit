#!/usr/bin/env python3
"""Check every row's summary against its abstract, by checking agents with no web access.

  --prepare   write summary_audit/batch_NN.json (summary + abstract pairs), a
              brief for the checking agents, and a manifest
  --ingest    read summary_audit/result_NN.json and record `summary_check` on
              each row, with a hash of the summary it checked

A row with no abstract is recorded as `no-abstract` (a warning the audit makes
you acknowledge). A row whose abstract fetch FAILED (abstracts_failed.json) or
whose abstract entry was recorded for other ids is refused at --prepare, which
then exits 1. A summary edited after --prepare is refused at --ingest.

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
    if (not isinstance(sc, dict) or sc.get("summary_sha") != common.summary_sha(s)
            or common.stamp_ids(sc) != common.ids_of(row)):
        return False
    has_abs = bool(((abstracts.get(key) or {}).get("text") or "").strip())
    return sc.get("verdict") == "supported" or (sc.get("verdict") == "no-abstract" and not has_abs)


def prepare(rows, keyf, abstracts, batch=40, recheck=False, failed=None):
    """-> (batches, no_abs, manifest). manifest["refused"] maps each ref that
    cannot be checked yet to why: its abstract entry records other ids than the
    row has (it is not this paper's abstract), or its abstract fetch failed
    (`failed`, from abstracts_failed.json) — a failed fetch is not "no abstract"."""
    failed = failed or {}
    todo, no_abs, sha, refused = [], [], {}, {}
    for r in rows:
        k, s = r.get(keyf), (r.get("summary") or "").strip()
        if not s or (not recheck and _checked(r, abstracts, k)):
            continue
        a = abstracts.get(k) or {}
        if a and common.stamp_ids(a) != common.ids_of(r):
            refused[k] = ("its abstracts.json entry was recorded for other ids than the row has; "
                          "re-run abstracts.py, or fix the landing-page entry")
            continue
        if k in failed and not (a.get("text") or "").strip():
            refused[k] = (f"its abstract fetch failed ({failed[k]}); "
                          "re-run abstracts.py or add a landing-page entry")
            continue
        sha[k] = common.summary_sha(s)
        if not (a.get("text") or "").strip():
            no_abs.append(k)
            continue
        todo.append({"ref": k, "summary": s, "abstract": a["text"], "abstract_source": a.get("source")})
    batches = [todo[i:i + batch] for i in range(0, len(todo), batch)]
    manifest = {"refs": [x["ref"] for x in todo], "sha": sha, "no_abstract": no_abs, "refused": refused}
    return batches, no_abs, manifest


def ingest(rows, keyf, results, abstracts, manifest, asof):
    by = {r.get(keyf): r for r in rows}
    n, errors, seen = 0, [], set()

    def stamp(row, k, verdict, note):
        # bound to the paper (its ids) and to the exact abstract text it was checked against
        doi, aid = common.ids_of(row)
        text = (abstracts.get(k) or {}).get("text") or ""
        row["summary_check"] = {"verdict": verdict, "note": note,
                                "abstract_source": (abstracts.get(k) or {}).get("source"),
                                "summary_sha": common.summary_sha(row.get("summary")),
                                "doi": doi, "arxiv": aid,
                                "abstract_sha": common.summary_sha(text) if text.strip() else "", "at": asof}

    counts = {}
    for res in results:
        counts[res.get("ref")] = counts.get(res.get("ref"), 0) + 1
    dupes, reported = {k for k, c in counts.items() if c > 1}, set()
    for res in results:
        k, v = res.get("ref"), res.get("verdict")
        seen.add(k)
        if k in dupes:
            if k not in reported:
                errors.append(f"{k}: more than one result; keep one")
                reported.add(k)
            continue
        row = by.get(k)
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
        if row is None or common.summary_sha(row.get("summary")) != manifest["sha"].get(k):
            continue
        if ((abstracts.get(k) or {}).get("text") or "").strip():
            errors.append(f"{k}: an abstract is now available; re-run --prepare")
            continue
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
    loaded = os.path.getmtime(args.rows)         # --ingest refuses a file changed since
    keyf = common.key_field(rows, args.key)
    ab_path = args.abstracts or os.path.join(here, "abstracts.json")
    ab = common.load_optional_json(ab_path, {})
    if args.prepare:
        failed = common.load_optional_json(
            os.path.join(os.path.dirname(os.path.abspath(ab_path)), "abstracts_failed.json"), {})
        batches, no_abs, manifest = prepare(rows, keyf, ab, args.batch, args.recheck, failed)
        os.makedirs(d, exist_ok=True)
        for old in glob.glob(os.path.join(d, "batch_*.json")) + glob.glob(os.path.join(d, "result_*.json")):
            os.remove(old)
        for i, b in enumerate(batches, start=1):
            common.dump_json(b, os.path.join(d, f"batch_{i:02d}.json"))
        common.dump_json(manifest, os.path.join(d, "manifest.json"))
        with open(os.path.join(d, "brief.md"), "w", encoding="utf-8") as f:
            f.write(BRIEF)
        print(f"{len(batches)} batch(es) of up to {args.batch} in {d}; {len(no_abs)} row(s) have no abstract")
        for k, why in manifest["refused"].items():
            print(f"  ✗ {k}: not queued — {why}")
        sys.exit(1 if manifest["refused"] else 0)
    manifest = common.load_json(os.path.join(d, "manifest.json"))
    results = []
    for p in sorted(glob.glob(os.path.join(d, "result_*.json"))):
        results += common.load_json(p)
    n, errors = ingest(rows, keyf, results, ab, manifest, args.asof)
    common.save_rows(args.rows, rows, loaded)
    flagged = [r.get(keyf) for r in rows if (r.get("summary_check") or {}).get("verdict") == "unsupported"]
    print(f"recorded {n} summary check(s); {len(flagged)} flagged")
    for e in errors:
        print(f"  ✗ {e}")
    for k in flagged:
        print(f"  ✗ {k}: summary claims something its abstract does not; fix it, then --prepare again")
    sys.exit(1 if errors or flagged else 0)


if __name__ == "__main__":
    main()
