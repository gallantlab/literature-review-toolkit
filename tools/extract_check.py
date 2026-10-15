#!/usr/bin/env python3
"""Gate for numbers extracted from abstracts: batch only checked abstracts, refuse unquoted numbers.

When a review reports statistics (accuracy, effect sizes, yields) pulled from the
papers, agents extract each figure with a verbatim quote from the abstract. This
tool frames that work and checks it, the same way verify.py checks citations.

  --prepare DIR   writes DIR/input_NN.json ({ref, cite, title, abstract}, --per rows
                  each) for every row with a summary and an abstract. It REFUSES (exit
                  1, naming them) rows whose summary check is not "supported" for the
                  abstract text now on file: run summary_audit.py first. Why: on two
                  2026-10-14 builds, 37 abstracts on file were truncated, garbled or
                  another paper's; 18 of them fed wrong numbers into an extraction
                  before the summary check caught them. --skip-family PREFIX leaves
                  out rows whose `family` starts with PREFIX (e.g. a methods family);
                  --only REF,REF limits the batch (a re-extraction).
  --check DIR     reads DIR/input_*.json and DIR/result_*.json (plus DIR/effect_result*.json),
                  and writes DIR/records.json and DIR/rejected.json. A record passes
                  only if every " ... "-separated piece of its `quote` occurs in the
                  abstract now on file (after whitespace, dash, middle-dot and
                  narrow-space normalization) and every numeric field it fills appears
                  in the quote, as a percentage or a proportion (up to 4 decimals),
                  a word number ("sixteen percent"), or one end of a range written
                  with a hyphen ("0.86-0.88"). With --vocab FILE ({field: [allowed
                  values]}) it also refuses values outside the vocabularies. Exit 1 on
                  any rejected record, any input ref with no result, or an abstract
                  that changed since --prepare.

The extraction brief (what to extract, field meanings) is project-specific and is
the agents' job; this tool owns only what code can check. A semantic audit of each
record's fields (is the 0.88 the sensitivity, not a CI bound?) still needs a second,
independent agent pass.

  python3 tools/extract_check.py --rows rows.json --prepare extraction --skip-family Foundations
  python3 tools/extract_check.py --rows rows.json --check extraction --vocab extraction/vocab.json

Result files (one per input batch): {"papers": [{"ref", "evidence", "records": [ {...,
"quote", numeric fields} ], "why_none"}]}. Effect-size files: the same shape with
records carrying `effect_type` and `value` (sign ignored when matching the quote).
"""
import argparse
import glob
import os
import re
import sys

import common

PHASE = "5d"   # pipeline phase, read by tools/gen_docs.py for the tool index

NUMS = ("sens", "spec", "auc", "acc", "kappa", "icc", "yield", "ppv", "npv", "misdx")
SIGNED = {"kappa", "icc"}

ONES = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in
        enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if i > 1}
_WORDS = re.compile(r"\b(%s)(?:[- ](%s))?\b|\b(%s)\b" % (
    "|".join(TENS), "|".join(list(ONES)[1:10]), "|".join(ONES)))


def norm(s):
    """Normalize text so a verbatim quote matches across encoding variants."""
    s = (s or "").replace("·", ".").replace(" ", " ").replace(" ", " ").replace(" ", " ")
    s = re.sub(r"[‐-―−]", "-", s)
    s = s.replace("≤", "<=").replace("≥", ">=")
    return re.sub(r"\s+", " ", s).strip().lower()


def number_forms(v):
    """Strings a value may be written as in an abstract (percent or proportion)."""
    out = set()
    for x in (v * 100, v):
        for d in range(5):
            t = f"{x:.{d}f}"
            out.add(t)
            if t.startswith("0."):
                out.add(t[1:])
            if t.startswith("-0."):
                out.add("-" + t[2:])
    return out


def nums_in(text):
    """Every number written in `text`, as strings; a hyphen after a digit is a range, not a sign."""
    found = set(re.findall(r"(?:(?<![\d.])-)?\d*\.?\d+", text))
    for m in _WORDS.finditer(text):
        found.add(str(TENS[m.group(1)] + (ONES[m.group(2)] if m.group(2) else 0)) if m.group(1)
                  else str(ONES[m.group(3)]))
    return found


def quote_problem(quote, abstract):
    if not quote:
        return "no quote"
    a = norm(abstract)
    for piece in re.split(r"\s*(?:\.\.\.|…)\s*", quote):
        if piece.strip() and norm(piece) not in a:
            return f"quote not in abstract: {piece[:80]!r}"
    return ""


def check_record(rec, abstract, vocab=None, fields=NUMS):
    """'' if the record passes, else the reason."""
    why = quote_problem(rec.get("quote"), abstract)
    if why:
        return why
    found = nums_in(norm(rec["quote"]))
    filled = 0
    for k in fields:
        v = rec.get(k)
        if v is None:
            continue
        filled += 1
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return f"{k} is not numeric"
        if k not in SIGNED and not 0 <= v <= 1:
            return f"{k}={v} is outside [0, 1]"
        if not number_forms(v) & found:
            return f"{k}={v} is not in the quote"
    if not filled:
        return "no numeric field"
    for field, allowed in (vocab or {}).items():
        if rec.get(field) not in (None, "") and rec.get(field) not in allowed:
            return f"{field}={rec.get(field)!r} is not in the vocabulary"
    return ""


def check_effect(rec, abstract, vocab=None):
    why = quote_problem(rec.get("quote"), abstract)
    if why:
        return why
    v = rec.get("value")
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return "value is not numeric"
    found = {s.lstrip("-") for s in nums_in(norm(rec["quote"]))}
    if not {f.lstrip("-") for f in number_forms(abs(v))} & found:
        return f"value={v} is not in the quote"
    for field, allowed in (vocab or {}).items():
        if rec.get(field) not in (None, "") and rec.get(field) not in allowed:
            return f"{field}={rec.get(field)!r} is not in the vocabulary"
    return ""


def prepare(rows, ab, keyf, out_dir, per=40, skip_family=(), only=None):
    """-> (number of batches written, refused [(ref, reason)])."""
    todo, refused = [], []
    for r in rows:
        k = r.get(keyf)
        if only and k not in only:
            continue
        if any((r.get("family") or "").startswith(p) for p in skip_family):
            continue
        text = ((ab.get(k) or {}).get("text") or "").strip()
        if not text or not (r.get("summary") or "").strip():
            continue
        sc = r.get("summary_check") or {}
        if sc.get("verdict") != "supported":
            refused.append((k, f"summary check is {sc.get('verdict') or 'missing'}"))
            continue
        if sc.get("abstract_sha") and sc["abstract_sha"] != common.summary_sha(text):
            refused.append((k, "the abstract changed since its summary was checked"))
            continue
        apa = r.get("apa") or ""
        todo.append({keyf: k, "cite": f"{common.lead_surname(apa)} {common.year_of(apa)}".strip(),
                     "title": r.get("search_title") or "", "abstract": text,
                     "abstract_sha": common.summary_sha(text)})
    if refused:
        return 0, refused
    os.makedirs(out_dir, exist_ok=True)
    start = len(glob.glob(os.path.join(out_dir, "input_*.json")))
    n = 0
    for i in range(0, len(todo), per):
        n += 1
        common.dump_json(todo[i:i + per], os.path.join(out_dir, f"input_{start + n:02d}.json"))
    return n, []


def check(ab, keyf, d, vocab=None):
    """-> (records, effects, rejected, missing, drifted, papers)."""
    expected, sha = set(), {}
    for f in glob.glob(os.path.join(d, "input_*.json")):
        for p in common.load_json(f):
            expected.add(p[keyf])
            sha[p[keyf]] = p.get("abstract_sha")
    ok, eff, bad, seen, papers = [], [], [], set(), {}
    drifted = sorted(k for k, s in sha.items()
                     if s and s != common.summary_sha(((ab.get(k) or {}).get("text") or "").strip()))
    for f in sorted(glob.glob(os.path.join(d, "result_*.json"))):
        for p in common.load_json(f)["papers"]:
            k = p[keyf]
            seen.add(k)
            papers[k] = {"evidence": p.get("evidence"), "why_none": p.get("why_none", "")}
            text = (ab.get(k) or {}).get("text", "")
            for i, rec in enumerate(p.get("records") or []):
                why = check_record(rec, text, vocab) if text else "no abstract on file"
                rec = dict(rec, **{keyf: k, "idx": i, "evidence": p.get("evidence")})
                (bad if why else ok).append(dict(rec, reject=why) if why else rec)
    for f in sorted(glob.glob(os.path.join(d, "effect_result*.json"))):
        for p in common.load_json(f)["papers"]:
            k = p[keyf]
            text = (ab.get(k) or {}).get("text", "")
            for i, rec in enumerate(p.get("records") or []):
                why = check_effect(rec, text, vocab) if text else "no abstract on file"
                rec = dict(rec, **{keyf: k, "idx": i})
                (bad if why else eff).append(dict(rec, reject=why) if why else rec)
    return ok, eff, bad, sorted(expected - seen), drifted, papers


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rows", required=True, help="rows.json (abstracts.json is read from beside it)")
    ap.add_argument("--abstracts", help="abstracts.json (default: beside --rows)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", metavar="DIR", help="write extraction input batches into DIR")
    mode.add_argument("--check", metavar="DIR", help="check DIR/result_*.json and write DIR/records.json")
    ap.add_argument("--per", type=int, default=40, help="rows per input batch (default 40)")
    ap.add_argument("--skip-family", action="append", default=[], metavar="PREFIX",
                    help="--prepare: leave out rows whose family starts with PREFIX (repeatable)")
    ap.add_argument("--only", help="--prepare: comma-separated refs to batch (a re-extraction)")
    ap.add_argument("--vocab", help="--check: JSON {field: [allowed values]}")
    ap.add_argument("--key", help="row key field (default: ref, else label)")
    args = ap.parse_args()

    rows = common.load_json(args.rows)
    keyf = common.key_field(rows, args.key)
    ab = common.load_optional_json(args.abstracts or os.path.join(os.path.dirname(os.path.abspath(args.rows)),
                                                                   "abstracts.json"), {})
    if args.prepare:
        only = set(args.only.split(",")) if args.only else None
        n, refused = prepare(rows, ab, keyf, args.prepare, args.per, args.skip_family, only)
        if refused:
            for k, why in refused:
                print(f"  ✗ {k}: {why}", file=sys.stderr)
            print(f"refused: {len(refused)} row(s) have no current 'supported' summary check. Run "
                  "summary_audit.py (--prepare, the checking agents, --ingest), fix flagged and "
                  "wrong-abstract rows, then rerun. Nothing was written.", file=sys.stderr)
            return 1
        print(f"wrote {n} input batch(es) to {args.prepare}")
        return 0
    vocab = common.load_json(args.vocab) if args.vocab else None
    ok, eff, bad, missing, drifted, papers = check(ab, keyf, args.check, vocab)
    common.dump_json({"records": ok, "effects": eff, "papers": papers},
                     os.path.join(args.check, "records.json"))
    common.dump_json(bad, os.path.join(args.check, "rejected.json"))
    print(f"{len(papers)} papers | {len(ok)} records and {len(eff)} effect records pass | "
          f"{len(bad)} rejected | {sum(1 for p in papers.values() if p['why_none'])} papers with no records")
    for r in bad:
        print(f"  ✗ {r[keyf]}#{r['idx']}: {r['reject']}", file=sys.stderr)
    if missing:
        print(f"  ✗ no result for {len(missing)} input ref(s): {', '.join(missing)}", file=sys.stderr)
    if drifted:
        print(f"  ✗ abstract changed since --prepare for: {', '.join(drifted)}; re-extract them "
              "(--prepare --only)", file=sys.stderr)
    return 1 if (bad or missing or drifted) else 0


if __name__ == "__main__":
    sys.exit(main())
