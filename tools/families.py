#!/usr/bin/env python3
"""Validate a family taxonomy, stamp `family` onto rows.json, and write families.json and families.md.

The carving is judgment: the agent proposes a few families and assigns every
paper, with a human checkpoint on the family definitions (see
family_prompt_template.md and PLAYBOOK Phase 6b). On every review the agent
proposes families and pitches the timeline built from them. The user uses the
families, changes them, or skips the timeline. This tool does the mechanical
half. It checks that the assignment is exhaustive and exclusive, warns when it is
unbalanced, stamps the rows, and renders families.md (tables by family plus a
family x topic cross-tab). families.json is the reproducible cache, like
citation_counts.json, so re-run only when the taxonomy changes.

Do not cluster embeddings to make families. Good theoretical families cut across
textual similarity: they unite dissimilar papers and split similar ones. So the
proposal must be an LLM synthesis, not a distance metric. See PLAYBOOK.

INPUT (--assign FILE): the JSON the agent produced and the user approved:
  { "principle": "one line naming the organizing axis (orthogonal to Topic)",
    "families": [ {"key":"compress", "name":"Compress",
                   "claim":"one-line claim", "lineage":"A -> B -> C"}, ... ],
    "assignments": { "<ref>": "<family key>", ... },    # every rows.json ref, once
    "hard_calls": [ {"ref", "assigned", "also_fits", "why"}, ... ] }

The hard calls are the papers the assignment agents found a poor fit, or a fit
to two families. The agents do not argue with the spec, so these are the only
place a wrong family definition shows. The tool prints each one to read before
rendering, and warns when the input records no `hard_calls` at all.

It stops with an error on a duplicate family key, fewer than 2 or more than 9
families (3-8 recommended), an unassigned paper, a ref not in rows.json, or an
unknown family key. An assignment may name a family by key or by display name,
in any case, so it can be rebuilt from the `family` already stamped on the rows.
It warns on a one-paper family or one holding more than 60% of the papers, and
drops empty families.

--results GLOB (repeatable) merges the assignment agents' result files into the
spec's assignments. Each file is {ref: key}, or {"assignments": {...},
"hard_calls": [...]}, and a file that re-assigns a ref differently is refused.
--default-from-lanes is for lab mode, where each lane is a theme. It assigns each
row that no result covered to its `lane_fit` when that is a family key, else to
its lane key when that is one.

--prepare DIR writes every row that no assignment, result or lane default covers
as DIR/batch_NN.json (--per rows each, default 110), and DIR/BRIEF.md for the
assignment agents, rendered from family_assign_template.md and the spec. Each
agent writes DIR/result_NN.json; merge them with --results.

A family whose `lineage` is empty gets one mechanically: its six rows with the
most within-corpus citations (internal_citations.json beside --rows, with the
OpenAlex count breaking ties), oldest first, marked `lineage_source`.

  python3 tools/families.py --rows rows.json --digest     # compact corpus for the proposal
  python3 tools/families.py --rows rows.json --assign families_input.json \\
          --out families.json
  python3 tools/families.py --rows rows.json --assign spec.json --default-from-lanes \\
          --prepare batches                             # batches + brief for the agents
  python3 tools/families.py --rows rows.json --assign spec.json --results 'batches/result_*.json' \\
          --default-from-lanes --out families.json      # merge agent results; lab mode
"""
import argparse
import datetime
import glob
import os
import re
import sys
from collections import Counter, defaultdict

import common

PHASE = "6b"   # pipeline phase, read by tools/gen_docs.py for the tool index

MIN_FAMILIES, MAX_FAMILIES = 2, 9
DOMINANT_WARN = 0.60   # warn if one family holds > this fraction of papers


def lead_year(apa):
    """(lead surname, year) for the digest and the per-family tables; year 0 if
    the reference has no parseable year. Uses the shared APA grammar so a
    2025a-suffixed row is not misread as year 0."""
    return common.lead_surname(apa), common.year_of(apa) or 0


def topic_codes(topics):
    """Stable short code per distinct topic for the cross-tab header."""
    codes, used = {}, {}
    for t in topics:
        m = re.match(r"\s*([A-Za-z0-9]+)[.)]", t)
        base = m.group(1) if m else re.sub(r"[^A-Za-z0-9]+", "", (t.split() or ["?"])[0])[:4] or "?"
        code, n = base, used.get(base, 0)
        if n:
            code = f"{base}{n+1}"
        used[base] = n + 1
        codes[t] = code
    return codes


ASSIGN_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "family_assign_template.md")


def prepare(todo, spec, outdir, per=110, project=None):
    """Write `todo` rows as outdir/batch_NN.json and outdir/BRIEF.md (from
    ASSIGN_TEMPLATE and the approved spec). Refuses a folder that already holds
    batch or result files. Returns the batch paths."""
    if glob.glob(os.path.join(outdir, "batch_*.json")) + glob.glob(os.path.join(outdir, "result_*.json")):
        sys.exit(f"ERROR: {outdir} already holds batch or result files; merge or move them first")
    os.makedirs(outdir, exist_ok=True)
    items = [{"ref": r["ref"], "year": lead_year(r.get("apa") or "")[1],
              "title": ((common.parse_apa(r.get("apa") or "") or {}).get("title")
                        or r.get("search_title") or ""),
              "summary": r.get("summary") or "", "lane_hint": (r.get("lane_fit") or r["ref"].split("-")[0])}
             for r in todo]
    paths = []
    for i in range(0, len(items), per):
        p = os.path.join(outdir, f"batch_{i // per + 1:02d}.json")
        common.dump_json(items[i:i + per], p)
        paths.append(p)
    fams = "\n".join(f"- `{f['key']}` **{f['name']}**: {f.get('claim', '')}"
                     for f in spec.get("families", []))
    with open(ASSIGN_TEMPLATE, encoding="utf-8") as fh:
        text = fh.read().split("<!-- BRIEF STARTS -->", 1)[1].lstrip()
    for k, v in {"PRINCIPLE": spec.get("principle", ""), "FAMILIES": fams,
                 "INPUT_DIR": os.path.abspath(outdir),
                 "PROJECT_DIR": os.path.abspath(project or os.path.dirname(os.path.abspath(outdir)))}.items():
        text = text.replace("{" + k + "}", v)
    left = re.findall(r"\{[A-Z_]+\}", text)
    if left:
        sys.exit(f"ERROR: template placeholders left unfilled: {sorted(set(left))}")
    with open(os.path.join(outdir, "BRIEF.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True, help="rows.json (stamped in place with `family`)")
    ap.add_argument("--assign", help="families_input.json (principle/families/assignments)")
    ap.add_argument("--out", default="families.json", help="canonical cache to write")
    ap.add_argument("--md", default="families.md", help="human-readable grouping to write")
    ap.add_argument("--asof", default=datetime.date.today().isoformat())
    ap.add_argument("--results", action="append", default=[], metavar="GLOB",
                    help="assignment agents' result files to merge into --assign's assignments: each "
                         "{ref: key} or {\"assignments\": {...}, \"hard_calls\": [...]} (repeatable)")
    ap.add_argument("--default-from-lanes", action="store_true",
                    help="lab mode, where the lanes ARE the themes: a row no result assigned takes "
                         "its lane_fit when that is a family key, else its lane key")
    ap.add_argument("--prepare", metavar="DIR",
                    help="write every row no assignment covers yet as DIR/batch_NN.json, plus "
                         "DIR/BRIEF.md for the assignment agents, and stop")
    ap.add_argument("--per", type=int, default=110, help="with --prepare: rows per batch")
    ap.add_argument("--digest", action="store_true",
                    help="instead of validating, print a compact corpus digest "
                         "(ref / topic / cite / lead-year / summary) for the proposal step")
    args = ap.parse_args()

    rows = common.load_json(args.rows)
    loaded = os.path.getmtime(args.rows)         # the stamp write refuses a file changed since

    # --- digest mode: help the agent propose families without re-reading rows.json
    if args.digest:
        for r in rows:
            lead, yr = lead_year(r["apa"])
            cite = r.get("cite_openalex")
            print(f"{r['ref']}\t{r.get('topic','')}\t{cite if isinstance(cite,int) else ''}"
                  f"\t{lead} ({yr})\t{r.get('summary','')[:240]}")
        return

    if not args.assign:
        ap.error("--assign is required (unless --digest)")
    spec = common.load_json(args.assign)
    principle = spec.get("principle", "")
    families = spec.get("families", [])
    assign = dict(spec.get("assignments", {}))
    hard_from_results = []
    for pattern in args.results:
        paths = sorted(glob.glob(pattern))
        if not paths:
            sys.exit(f"ERROR: --results {pattern!r} matches no file")
        for p in paths:
            res = common.load_json(p)
            if isinstance(res, dict) and "assignments" in res:
                hard_from_results += res.get("hard_calls") or []
                res = res["assignments"]
            clash = {r for r in res if r in assign and assign[r] != res[r]}
            if clash:
                sys.exit(f"ERROR: {p} re-assigns {len(clash)} ref(s) differently, e.g. {sorted(clash)[:5]}")
            assign.update(res)
    if args.default_from_lanes:
        fkeys = {f["key"] for f in spec.get("families", [])}
        for r in rows:
            if r["ref"] in assign:
                continue
            lane, fit = r["ref"].split("-")[0], (r.get("lane_fit") or "").strip()[:1]
            if lane in fkeys:
                assign[r["ref"]] = fit if fit in fkeys else lane
            elif fit in fkeys:
                assign[r["ref"]] = fit
    if args.prepare:
        todo = [r for r in rows if r["ref"] not in assign]
        if not todo:
            sys.exit("nothing to prepare: every row already has a family")
        paths = prepare(todo, spec, args.prepare, args.per,
                        project=os.path.dirname(os.path.abspath(args.rows)))
        print(f"{len(todo)} unassigned row(s) -> {len(paths)} batch file(s) + BRIEF.md in {args.prepare}; "
              f"one agent per batch, then --results '{os.path.join(args.prepare, 'result_*.json')}'")
        return
    if hard_from_results:
        spec["hard_calls"] = list(spec.get("hard_calls") or []) + hard_from_results
    # The assignment agents are told not to argue with the spec, so their hard calls
    # (papers that fit it badly) are the only place a wrong family definition shows.
    hard = spec.get("hard_calls")
    if hard is None:
        print("WARNING: the assignment records no hard_calls; ask the assignment agents for them "
              "(family_prompt_template.md, Step 2) — a wrong family definition shows up only there",
              file=sys.stderr)
    elif hard:
        print(f"{len(hard)} hard call(s) to read before rendering:", file=sys.stderr)
        for h in hard:
            print(f"  {h.get('ref')}: {h.get('assigned')} (also fits {h.get('also_fits') or '-'}) — "
                  f"{h.get('why', '')}", file=sys.stderr)

    # ---- validate -----------------------------------------------------------
    keys = [f["key"] for f in families]
    if len(keys) != len(set(keys)):
        sys.exit("ERROR: duplicate family keys in spec.")
    if not (MIN_FAMILIES <= len(keys) <= MAX_FAMILIES):
        sys.exit(f"ERROR: {len(keys)} families; hard limit {MIN_FAMILIES}-{MAX_FAMILIES}, "
                 "recommended 3-8 (too few = trivial; too many = you've re-created the "
                 "Topic column).")
    keyset, name_of = set(keys), {f["key"]: f["name"] for f in families}

    # Accept assignment values case-insensitively and by display name, not just
    # the exact lowercase key: rows.json stores the display name ("Infer"), so
    # re-running families straight off the stamped `family` field would otherwise
    # fail with "unknown family keys". Anything that doesn't resolve is left as-is
    # and caught by the badkey check below.
    resolve = {}
    for f in families:
        resolve[str(f["key"]).strip().lower()] = f["key"]
        resolve[str(f["name"]).strip().lower()] = f["key"]
    assign = {r: resolve.get(str(v).strip().lower(), v) for r, v in assign.items()}

    refs = [r["ref"] for r in rows]
    refset = set(refs)
    missing = [r for r in refs if r not in assign]
    extra = [a for a in assign if a not in refset]
    badkey = sorted({k for k in assign.values() if k not in keyset})
    if missing:
        sys.exit(f"ERROR: {len(missing)} papers unassigned, e.g. {missing[:8]}")
    if extra:
        sys.exit(f"ERROR: assignment names {len(extra)} refs not in rows.json, e.g. {extra[:8]}")
    if badkey:
        sys.exit(f"ERROR: assignments use unknown family keys: {badkey}")

    counts = Counter(assign[r] for r in refs)
    empty = [k for k in keys if counts[k] == 0]
    if empty:
        print(f"WARNING: dropping {len(empty)} empty families: {empty}", file=sys.stderr)
        families = [f for f in families if counts[f["key"]] > 0]
        keys = [f["key"] for f in families]
    for k in keys:
        if counts[k] == 1:
            print(f"WARNING: family '{k}' has only 1 paper — likely a bad cut.", file=sys.stderr)
    top_key, top_n = counts.most_common(1)[0]
    if top_n / len(refs) > DOMINANT_WARN:
        print(f"WARNING: family '{top_key}' holds {top_n}/{len(refs)} "
              f"({top_n/len(refs):.0%}) — consider splitting.", file=sys.stderr)

    # ---- lineage: filled mechanically where the spec left it empty -----------
    # The six rows with the most within-corpus citations (internal_citations.json
    # from xref --internal-out; OpenAlex count to break ties), oldest first, named
    # from their canonical apa: nothing invented, but a selection, not an argument.
    indeg = common.load_optional_json(os.path.join(os.path.dirname(os.path.abspath(args.rows)),
                                                   "internal_citations.json"), {})
    by_ref = {r["ref"]: r for r in rows}
    for fam in families:
        if (fam.get("lineage") or "").strip():
            continue
        members = [r for r in refs if assign[r] == fam["key"] and by_ref[r].get("apa")]
        def weight(r):
            return (-(indeg.get(r) or 0), -(by_ref[r].get("cite_openalex") or 0))
        top = sorted(members, key=weight)[:6]
        top.sort(key=lambda r: common.year_of(by_ref[r]["apa"]) or 0)
        fam["lineage"] = " -> ".join(
            f"{common.lead_surname(by_ref[r]['apa'])} {common.year_of(by_ref[r]['apa'])}" for r in top)
        fam["lineage_source"] = "mechanical: top within-corpus citations, oldest first"

    # ---- stamp rows.json (display name) + persist canonical cache ------------
    for r in rows:
        r["family"] = name_of[assign[r["ref"]]]
    common.save_rows(args.rows, rows, loaded)   # ensure_ascii=False: don't undo references.py's UTF-8
    cache = {"principle": principle, "generated": args.asof,
             "families": families, "assignments": {r: assign[r] for r in refs}}
    common.dump_json(cache, args.out)

    # ---- families.md : grouped tables + family x topic cross-tab ------------
    topics = sorted({r.get("topic", "") for r in rows})
    tcode = topic_codes(topics)
    xt = defaultdict(Counter)
    for r in rows:
        xt[assign[r["ref"]]][r.get("topic", "")] += 1

    with open(args.md, "w", encoding="utf-8") as f:
        f.write("# Theoretical families\n\n")
        if principle:
            f.write(f"**Organizing principle.** {principle}\n\n")
        f.write(f"{len(rows)} papers, each in one family — a grouping orthogonal to the "
                f"Topic column. Generated {args.asof}.\n\n")
        # cross-tab
        f.write("## Families × topics\n\n")
        f.write("| Family | " + " | ".join(tcode[t] for t in topics) + " | **Total** |\n")
        f.write("|" + "---|" * (len(topics) + 2) + "\n")
        for fam in families:
            cells = [str(xt[fam["key"]].get(t, "") or "") for t in topics]
            f.write(f"| **{fam['name']}** | " + " | ".join(cells)
                    + f" | {sum(xt[fam['key']].values())} |\n")
        f.write("\n*Topic legend: " + "; ".join(f"`{tcode[t]}` = {t}" for t in topics) + "*\n\n")
        # per-family
        for fam in families:
            members = sorted((r for r in rows if assign[r["ref"]] == fam["key"]),
                             key=lambda r: (lead_year(r["apa"])[1], r["ref"]))
            f.write(f"## {fam['name']} ({len(members)})\n\n")
            if fam.get("claim"):
                f.write(f"**Claim.** {fam['claim']}\n\n")
            if fam.get("lineage"):
                f.write(f"**Spine.** {fam['lineage']}\n\n")
            f.write("| Ref# | Topic | Study | Cites (OA) |\n|---|---|---|---|\n")
            for r in members:
                lead, yr = lead_year(r["apa"])
                oa = r.get("cite_openalex")
                f.write(f"| {r['ref']} | {tcode[r.get('topic','')]} | {lead} ({yr}) | "
                        f"{oa if isinstance(oa, int) else '—'} |\n")
            f.write("\n")

    print(f"{len(rows)} papers -> {len(families)} families; stamped {args.rows}, "
          f"wrote {args.out} + {args.md}")
    for fam in families:
        print(f"  {fam['name']:14s} {counts[fam['key']]:3d}")


if __name__ == "__main__":
    main()
