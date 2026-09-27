#!/usr/bin/env python3
"""Render every search lane's brief from one lane spec, so no brief goes out incomplete.

The search agents are only as good as their briefs, and a hand-filled brief drifts:
a lane missing the verification duty, a leftover {PLACEHOLDER}, a capped-search rule
left in an uncapped build. This tool fills tools/search_prompt_template.md for each
lane, builds the shared lane table, keeps or drops the template's conditional blocks
(forward/antecedent, capped/uncapped, lab, seeds), and refuses to write any brief
with a placeholder or block marker left in it.

    python3 tools/lane_briefs.py --spec lanes.json

It writes briefs/brief_<KEY>.md, lane_manifest.json (key, name, brief, out, target,
kind) and an empty search_raw/ and scratch/<KEY>/ per lane, all beside the spec, and
prints the one-line prompt to give each search agent.

The spec (JSON):
  {"title": "The Gallant lab in the context of its field",
   "for": "Jack Gallant at UC Berkeley",
   "description": "What the bibliography covers, what is out of scope for all lanes.",
   "today": "2026-09-27",            # optional, default today
   "tier": 2021,                     # optional, default today's year minus 5
   "scale": "standard",              # scan | focused | standard | exhaustive | a number of papers
   "capped": false,                  # optional; follows from the scale
   "lab": {"pi": "Jack L. Gallant", "lane": "L"},      # optional: lab mode
   "already_have": ["Author Year - title", ...],        # optional, every lane
   "lanes": [{"key": "V", "name": "...", "short": "one line for the lane table",
              "kind": "forward" | "antecedent", "target": 40,     # target optional: from the scale
              "definition": "...", "exclusions": ["...", ...] or "...",
              "queries": ["...", ...], "seeds": ["title", ...],   # seeds optional
              "already_have": [...]}]}                            # optional, this lane

The scale is how big a search the user asked for (common.SEARCH_SCALES): it sets
each lane's target (a lane may set its own), whether lanes are capped, and the
number of lanes allowed. A numeric scale is a capped total spread over the lanes.
Every scale still needs at least one antecedent lane (contract rule 4). When the
project's preflight.json records that the user chose to cap the search, an uncapped
scale is refused. The tool prints the plan and the preflight command sized to it.

Seeds are TITLES only: a seed that carries an author name is refused, because
remembered author names have injected fabricated attributions into past builds.
Exit 1 on a spec error, naming every problem.
"""
import argparse
import datetime
import json
import os
import re
import sys

import common

PHASE = "2"   # pipeline phase, read by tools/gen_docs.py for the tool index

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "search_prompt_template.md")
MARK = "<!-- BRIEF STARTS -->"
PLACEHOLDER = re.compile(r"\{[A-Z][A-Z_]+\}")
BLOCK = re.compile(r"<!-- IF:(\w+) -->\n?(.*?)<!-- ENDIF:\1 -->\n?", re.S)
# a seed like "Smith 2020 - title" or "title (Smith et al., 2020)" names an author
SEED_AUTHOR = re.compile(r"\bet al\b|\(\s*[A-Z][a-z]+,? \d{4}|^[A-Z][a-z]+ \d{4}\b")


def _bullets(items):
    items = [items] if isinstance(items, str) else list(items or [])
    return "\n".join(f"- {x}" for x in items if str(x).strip())


def plan_of(spec):
    """The scale plan for this spec (common.scale_plan), or raise ValueError."""
    return common.scale_plan(spec.get("scale", "standard"), len(spec.get("lanes") or []) or None)


def apply_scale(spec, preflight_record=None):
    """Fill each lane's target and the spec's `capped` from its scale. Returns the
    problems ([] when consistent): an explicit `capped` that contradicts the scale,
    a lane count outside the scale's range, no antecedent lane, or an uncapped
    scale after the user chose, at the preflight, to cap the search."""
    try:
        plan = plan_of(spec)
    except ValueError as e:
        return [str(e)]
    errs = []
    if "capped" in spec and bool(spec["capped"]) != plan["capped"]:
        errs.append(f"'capped': {spec['capped']} contradicts scale {plan['name']!r} "
                    f"({'capped' if plan['capped'] else 'uncapped'}); drop 'capped' or change the scale")
    spec["capped"] = plan["capped"]
    lanes = spec.get("lanes") or []
    lo, hi = plan["lanes"]
    if lanes and not lo <= len(lanes) <= hi:
        errs.append(f"scale {plan['name']!r} takes {lo}-{hi} lanes; the spec has {len(lanes)} "
                    "(pick another scale, or merge or split lanes)")
    if lanes and not any(ln.get("kind") == "antecedent" for ln in lanes):
        errs.append("no antecedent lane: every review needs one (contract rule 4), at every scale")
    for ln in lanes:
        ln.setdefault("target", plan["lane_target"])
    if plan["capped"] and isinstance(spec.get("scale"), int):
        total = sum(ln.get("target", 0) for ln in lanes if isinstance(ln.get("target"), int))
        if total > spec["scale"]:
            errs.append(f"lane targets add up to {total}, over the scale's {spec['scale']} papers")
    rec = preflight_record or {}
    if "cap" in (rec.get("accepted") or []) and not plan["capped"]:
        errs.append(f"the preflight recorded that the user chose to CAP the search, but scale "
                    f"{plan['name']!r} is uncapped: use scan, focused or a number of papers")
    return errs


def check_spec(spec):
    """Every problem with the spec, as a list of messages ([] when it is usable)."""
    errs = []
    for f in ("title", "for", "description", "lanes"):
        if not spec.get(f):
            errs.append(f"spec is missing {f!r}")
    lab = spec.get("lab") or {}
    if lab and not (lab.get("pi") and lab.get("lane")):
        errs.append("lab needs both 'pi' and 'lane'")
    keys = []
    for i, ln in enumerate(spec.get("lanes") or []):
        k = str(ln.get("key") or "")
        where = f"lane {k or i}"
        if not re.fullmatch(r"[A-Z][A-Z0-9]{0,3}", k):
            errs.append(f"{where}: key must be 1-4 capital letters/digits (it prefixes every ref)")
        keys.append(k)
        for f in ("name", "short", "definition", "exclusions", "queries", "target"):
            if not ln.get(f):
                errs.append(f"{where}: missing {f!r}")
        if ln.get("kind") not in ("forward", "antecedent"):
            errs.append(f"{where}: kind must be 'forward' or 'antecedent'")
        if not isinstance(ln.get("target"), int) or ln.get("target", 0) <= 0:
            errs.append(f"{where}: target must be a positive integer")
        for s in ln.get("seeds") or []:
            if SEED_AUTHOR.search(str(s)):
                errs.append(f"{where}: seed {s!r} names an author; seeds are titles only")
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        errs.append(f"duplicate lane keys: {', '.join(dup)}")
    if lab and lab.get("lane") in keys:
        errs.append(f"the lab lane {lab['lane']!r} is also a search lane key")
    return errs


def lane_table(spec, me):
    lines = ["| Lane | Covers |", "|---|---|"]
    for ln in spec["lanes"]:
        mark = " **(yours)**" if ln["key"] == me else ""
        lines.append(f"| `{ln['key']}`{mark} | {ln['short']} |")
    lab = spec.get("lab")
    if lab:
        lines.append(f"| `{lab['lane']}` | The lab's OWN papers, from its publication record "
                     "(not a search lane) |")
    return "\n".join(lines)


def render(template, spec, ln, outpath, scratch):
    """One lane's brief. Raises ValueError if anything is left unfilled."""
    body = template.split(MARK, 1)[1].lstrip("\n")
    lab = spec.get("lab") or {}
    on = {"forward": ln["kind"] == "forward", "antecedent": ln["kind"] == "antecedent",
          "capped": bool(spec.get("capped")), "uncapped": not spec.get("capped"),
          "lab": bool(lab), "seeds": bool(ln.get("seeds"))}
    body = BLOCK.sub(lambda m: m.group(2) if on.get(m.group(1)) else "", body)
    today = spec.get("today") or datetime.date.today().isoformat()
    have = list(spec.get("already_have") or []) + list(ln.get("already_have") or [])
    fill = {
        "LANE_KEY": ln["key"], "TOPIC_NAME": ln["name"], "REVIEW_TITLE": spec["title"],
        "REVIEW_FOR": spec["for"], "BIBLIOGRAPHY_DESCRIPTION": spec["description"].strip(),
        "TOPIC_DEFINITION": ln["definition"].strip(), "EXCLUSIONS": _bullets(ln["exclusions"]),
        "LANE_TABLE": lane_table(spec, ln["key"]),
        "ALREADY_HAVE_LIST": _bullets(have) or "(nothing yet: this is a new bibliography)",
        "TIER_BOUNDARY_YEAR": str(spec.get("tier") or int(today[:4]) - 5), "TODAY": today,
        "TARGET_COUNT": str(ln["target"]), "SEARCH_QUERIES": _bullets(ln["queries"]),
        "SEED_TITLES": _bullets(ln.get("seeds")), "OUTPATH": outpath, "SCRATCH_DIR": scratch,
        "SOURCE_TAG": "anteced" if ln["kind"] == "antecedent" else "search",
        "LAB_PI": lab.get("pi", ""), "LAB_LANE": lab.get("lane", ""),
    }
    out = PLACEHOLDER.sub(lambda m: fill.get(m.group(0)[1:-1], m.group(0)), body)
    left = sorted(set(PLACEHOLDER.findall(out)) | set(re.findall(r"<!-- (?:END)?IF:\w+ -->", out)))
    if left:
        raise ValueError(f"lane {ln['key']}: unfilled after rendering: {', '.join(left)}")
    return re.sub(r"\n{3,}", "\n\n", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--spec", required=True, help="the lane spec (JSON); outputs go beside it")
    args = ap.parse_args()
    spec = common.load_json(args.spec)
    here = os.path.dirname(os.path.abspath(args.spec))
    rec = common.load_optional_json(os.path.join(here, "preflight.json"), {})
    errs = apply_scale(spec, rec) + check_spec(spec)
    if errs:
        sys.exit("✗ lane spec problems:\n" + "\n".join(f"  - {e}" for e in errs))
    plan = plan_of(spec)
    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()
    briefs, raw = os.path.join(here, "briefs"), os.path.join(here, "search_raw")
    os.makedirs(briefs, exist_ok=True)
    os.makedirs(raw, exist_ok=True)
    manifest = []
    for ln in spec["lanes"]:
        k = ln["key"]
        scratch = os.path.join(here, "scratch", k)
        os.makedirs(scratch, exist_ok=True)
        outpath = os.path.join(raw, f"{k}.json")
        text = render(template, spec, ln, outpath, scratch)
        path = os.path.join(briefs, f"brief_{k}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        manifest.append({"key": k, "name": ln["name"], "brief": path, "out": outpath,
                         "target": ln["target"], "kind": ln["kind"], "capped": bool(spec["capped"]),
                         "scale": plan["name"]})
    with open(os.path.join(here, "lane_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    planned = sum(m["target"] for m in manifest) * (1 if spec["capped"] else common.UNCAPPED_YIELD)
    print(f"scale {plan['name']}: {plan['about']}")
    targets = ", ".join(f"{m['key']} {m['target']}" for m in manifest)
    print(f"  {len(manifest)} lanes, targets {targets}; "
          f"{'capped' if spec['capped'] else 'uncapped (targets are floors)'}; about {planned} papers")
    print(f"  size the preflight to it: python3 tools/preflight.py --project {here} --papers {planned}")
    print(f"wrote {len(manifest)} brief(s) to {briefs} (+ lane_manifest.json)")
    print("Launch one general-purpose agent per lane, all in one message, with the prompt:")
    print('  "Read the literature-search brief at <brief path> and carry it out exactly as written. '
          'It is your complete instructions. Do not delegate to subagents."')


if __name__ == "__main__":
    main()
