#!/usr/bin/env python3
"""Phase 6b — thematic families. Validate an LLM-proposed family taxonomy against
the bibliography, stamp `family` onto rows.json, and emit families.json (the
reproducible cache) + families.md (grouped tables + a family x topic cross-tab).

WHAT THIS TOOL DOES (the deterministic half). The *carving* — proposing a few
families and assigning every paper — is judgment, done by the agent with a human
checkpoint on the ~N family definitions (see family_prompt_template.md, PLAYBOOK
Phase 6b). This tool owns only the mechanical part: validate the assignment is
exhaustive / exclusive / balanced, stamp the rows, and render. Re-run only when
the taxonomy changes — families.json is the cache (like citation_counts.json).

DON'T cluster embeddings to make families: good theoretical families cut across
textual similarity (they unite dissimilar papers and split similar ones), so the
proposal must be an LLM synthesis, not a distance metric. See PLAYBOOK.

INPUT (--assign FILE): JSON the agent produced and the user approved:
  { "principle": "one line naming the organizing axis (orthogonal to Topic)",
    "families": [ {"key":"compress", "name":"Compress",
                   "claim":"one-line claim", "lineage":"A -> B -> C"}, ... ],
    "assignments": { "<ref>": "<family key>", ... } }   # every rows.json ref, once

  python3 tools/families.py --rows rows.json --assign families_input.json \
          --out families.json
"""
import argparse, datetime, re, sys
from collections import Counter, defaultdict

import common

MIN_FAMILIES, MAX_FAMILIES = 2, 9
DOMINANT_WARN = 0.60   # warn if one family holds > this fraction of papers


def lead_year(apa):
    yr = re.search(r"\((\d{4})\)", apa)
    return apa.split(",")[0], int(yr.group(1)) if yr else 0


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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True, help="rows.json (stamped in place with `family`)")
    ap.add_argument("--assign", help="families_input.json (principle/families/assignments)")
    ap.add_argument("--out", default="families.json", help="canonical cache to write")
    ap.add_argument("--md", default="families.md", help="human-readable grouping to write")
    ap.add_argument("--asof", default=datetime.date.today().isoformat())
    ap.add_argument("--digest", action="store_true",
                    help="instead of validating, print a compact corpus digest "
                         "(ref / topic / cite / lead-year / summary) for the proposal step")
    args = ap.parse_args()

    rows = common.load_json(args.rows)

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
    assign = spec.get("assignments", {})

    # ---- validate -----------------------------------------------------------
    keys = [f["key"] for f in families]
    if len(keys) != len(set(keys)):
        sys.exit("ERROR: duplicate family keys in spec.")
    if not (MIN_FAMILIES <= len(keys) <= MAX_FAMILIES):
        sys.exit(f"ERROR: {len(keys)} families; hard limit {MIN_FAMILIES}-{MAX_FAMILIES}, "
                 "recommended 3-8 (too few = trivial; too many = you've re-created the "
                 "Topic column).")
    keyset, name_of = set(keys), {f["key"]: f["name"] for f in families}

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

    # ---- stamp rows.json (display name) + persist canonical cache ------------
    for r in rows:
        r["family"] = name_of[assign[r["ref"]]]
    common.dump_json(rows, args.rows)   # ensure_ascii=False: don't undo references.py's UTF-8
    cache = {"principle": principle, "generated": args.asof,
             "families": families, "assignments": {r: assign[r] for r in refs}}
    common.dump_json(cache, args.out)

    # ---- families.md : grouped tables + family x topic cross-tab ------------
    topics = sorted({r.get("topic", "") for r in rows})
    tcode = topic_codes(topics)
    xt = defaultdict(Counter)
    for r in rows:
        xt[assign[r["ref"]]][r.get("topic", "")] += 1

    with open(args.md, "w") as f:
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
