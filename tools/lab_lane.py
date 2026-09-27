#!/usr/bin/env python3
"""Lab mode, Phase L2: check the lab's record by content, then turn it into lane L.

An author id's record (lab_corpus.py) holds meeting abstracts, errata, peer-review
reports, a preprint and its published version as two works, and sometimes a
namesake's papers. Classifying it from database tags mislabels papers, so agents
read each item and decide; this tool does the mechanics around them.

  --prepare   split lab_papers.json into batches (with any abstracts fetched by
              abstracts.py) and write lab_check/brief.md for the checking agents,
              who write lab_check/result_NN.json: per item is_gallant-style
              authorship, kind, species, duplicate_of, include, theme, reason.
  --build     join the record with every result into search_raw/0_L.json, a
              schema-2 lane (source "lab", the record's OpenAlex claim as the row's
              claim), refusing a record with no check, an included duplicate, an
              included item not by the PI, or a theme not in --themes. The file
              sorts first, so a lab paper a field lane also found keeps its lab row.

    python3 tools/lab_lane.py --prepare --papers lab_papers.json --abstracts lab_abstracts.json \\
            --themes themes.json --pi "Jack L. Gallant"
    python3 tools/lab_lane.py --build --papers lab_papers.json --themes themes.json

themes.json: [{"key": "V", "name": "...", "claim": "..."}] (the lab's approved
themes, Phase L3). Field lanes defer the lab's papers to lane L, so the merge
then fails on any lab paper the record lacks: that is the completeness check.
"""
import argparse
import glob
import os
import sys
from collections import Counter

import common

PHASE = "L2"   # pipeline phase, read by tools/gen_docs.py for the tool index

KINDS = ("research-article", "review", "book-chapter", "preprint", "conference-paper", "software",
         "dataset", "meeting-abstract", "erratum", "peer-review", "other")

BRIEF = """# Lab-record check (lab mode, Phase L2)

You are checking part of the publication record of **{PI}**, as pulled from OpenAlex, for an
annotated bibliography. OpenAlex author records are unreliable: they merge namesakes, hold meeting
abstracts, errata and peer-review reports, and list a preprint and its published version as two works.
Decide, **from each item's actual content**, what it is and whether it belongs in the lab's record.
Do not classify from database topic tags or from the title alone.

Input: `lab_check/input_NN.json` (your batch number is in the message that sent you): items with ref,
openalex id, doi, title, year, venue, OpenAlex type, author names and abstract (empty when none was
found). A duplicate may point to a ref in another batch; say so if you can tell from the title.

## For every item decide

1. **by_pi**: is {PI} really an author? Check the landing page (DOI, PubMed, arXiv) when the author list
   or the topic makes it doubtful. Being off the research program is NOT evidence against authorship.
2. **kind**: one of {KINDS}. A meeting-abstract is a conference abstract, a 1-2 page summary, a talk or
   keynote abstract.
3. **species**: the subjects: `human`, `primate` (non-human primate), `other`, or `none` (a method,
   software, dataset or theory paper with no subjects).
4. **duplicate_of**: the ref of the version to KEEP when this item is the same work as another (the
   version of record over its preprint); empty otherwise.
5. **include**: true/false with a `reason`. Include research articles, reviews, chapters, full conference
   papers, unpublished preprints, and the lab's software papers (one record per tool). Include the lab's
   earlier-method and other-species work (it is the lab's own antecedent). Exclude meeting abstracts,
   errata, peer-review reports, duplicates, and items not by {PI}. Real authorship that is off the lab's
   program stays in, with `"off_program": true`.
6. **theme**: for an included item, the ONE theme key it fits best:
{THEMES}
7. For an item whose abstract is empty, fetch its landing page and decide from what you read; record the
   URL in `checked_url`.

Write `lab_check/result_NN.json` (same NN), a JSON list, one object per input item, in input order:
  {{"ref": "L1", "by_pi": true, "kind": "research-article", "species": "human", "duplicate_of": "",
   "include": true, "off_program": false, "theme": "V", "reason": "...", "checked_url": "", "note": ""}}
Write it incrementally, parse it back with python3, keep shell and fetch commands short, and do not
delegate to subagents. Reply with only: items classified, included, excluded (by kind), duplicates,
not by the PI.
"""


def load_themes(path):
    th = common.load_json(path)
    th = th.get("families", th) if isinstance(th, dict) else th
    if not th or not all(isinstance(t, dict) and t.get("key") and t.get("name") for t in th):
        raise ValueError(f"{path}: expected a list of {{key, name, claim}} themes")
    return th


def first_author(apa):
    """'Family, I. I.' of the lead author of an OpenAlex-built apa."""
    parts = ((common.parse_apa(apa) or {}).get("authors") or "").split(", ")
    return ", ".join(parts[:2]) if len(parts) >= 2 else parts[0]


def prepare(papers, abstracts, themes, pi, outdir, batch):
    os.makedirs(outdir, exist_ok=True)
    items = [{"ref": p["ref"], "openalex": p.get("openalex", ""), "doi": p.get("doi") or "",
              "title": p.get("title", ""), "year": p.get("year"), "venue": p.get("venue") or "",
              "openalex_type": p.get("type"), "authors": p.get("coauthors") or [],
              "abstract": (abstracts.get(p["ref"]) or {}).get("text", "")} for p in papers]
    for old in glob.glob(os.path.join(outdir, "input_*.json")):
        os.remove(old)
    n = 0
    for i in range(0, len(items), batch):
        n += 1
        common.dump_json(items[i:i + batch], os.path.join(outdir, f"input_{n:02d}.json"))
    lines = "\n".join(f"   - `{t['key']}` {t['name']}" + (f": {t['claim']}" if t.get("claim") else "")
                      for t in themes)
    with open(os.path.join(outdir, "brief.md"), "w", encoding="utf-8") as f:
        f.write(BRIEF.format(PI=pi, KINDS=", ".join(f"`{k}`" for k in KINDS), THEMES=lines))
    return n, sum(1 for x in items if not x["abstract"])


def build(papers, checks, themes, lane="L"):
    """-> (lane file dict, problems). Refuses what the merge could not trust."""
    by = {p["ref"]: p for p in papers}
    tkeys = {t["key"]: t["name"] for t in themes}
    problems = [f"{r}: no check result" for r in by if r not in checks]
    problems += [f"{r}: checked but not in the record" for r in checks if r not in by]
    kept = [c for r, c in checks.items() if r in by and c.get("include")]
    for c in kept:
        if c.get("duplicate_of"):
            problems.append(f"{c['ref']}: included but marked a duplicate of {c['duplicate_of']}")
        if c.get("by_pi", c.get("is_gallant")) is False:
            problems.append(f"{c['ref']}: included but not by the PI")
        if c.get("theme") not in tkeys:
            problems.append(f"{c['ref']}: theme {c.get('theme')!r} is not one of {sorted(tkeys)}")
    if problems:
        return None, problems
    def refnum(r):                                   # L9 before L10
        digits = "".join(ch for ch in r if ch.isdigit())
        return (int(digits) if digits else 0, r)
    kept.sort(key=lambda c: (by[c["ref"]].get("year") or 0, refnum(c["ref"])))
    out = []
    for i, c in enumerate(kept, 1):
        p = by[c["ref"]]
        doi = p.get("doi") or ""
        m = common.ARXIV_DOI.match(doi)
        out.append({
            "ref": f"{lane}-{i:03d}", "lane": lane, "doi": doi, "arxiv": m.group(1) if m else "",
            "link": p.get("link") or (f"https://doi.org/{doi}" if doi else ""),
            "first_author": first_author(p.get("apa", "")), "year": p.get("year"),
            "title": p.get("title", ""), "apa": "" if doi else p.get("apa", ""), "summary": "",
            "tag": "lab", "topic": tkeys[c["theme"]], "source": "lab", "lane_fit": c["theme"],
            "note": f"lab record {c['ref']} ({p.get('openalex', '')}); {c.get('kind')}, {c.get('species')}"
                    + ("; off program" if c.get("off_program") else "")
                    + (f"; {c['note']}" if c.get("note") else "")})
    excluded = [{"title": by[r].get("title", ""), "doi": by[r].get("doi") or "",
                 "first_author": first_author(by[r].get("apa", "")), "year": by[r].get("year"),
                 "reason": f"lab record {r}: {c.get('kind')}"
                           + (f", duplicate of {c['duplicate_of']}" if c.get("duplicate_of") else "")
                           + (f" — {c['reason']}" if c.get("reason") else "")}
                for r, c in checks.items() if r in by and not c.get("include")]
    return {"schema": 2, "lane": lane,
            "status": {"target": len(out), "returned": len(out), "websearch_exhausted": False,
                       "notes": "the lab's own record: lab_corpus.py + the Phase L2 content check"},
            "papers": out, "deferred": [], "excluded": excluded, "could_not_confirm": []}, []


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--papers", required=True, help="lab_papers.json from lab_corpus.py")
    ap.add_argument("--themes", required=True, help="the lab's themes: [{key, name, claim}]")
    ap.add_argument("--abstracts", help="abstracts.json for the record (--prepare)")
    ap.add_argument("--pi", help="the PI's name as it appears on papers (--prepare)")
    ap.add_argument("--dir", default="lab_check", help="batch/brief/result folder (default: lab_check)")
    ap.add_argument("--batch", type=int, default=90)
    ap.add_argument("--lane", default="L")
    ap.add_argument("--out", help="lane file (default: search_raw/0_<lane>.json)")
    args = ap.parse_args()
    if args.prepare == args.build:
        ap.error("give exactly one of --prepare, --build")
    papers, themes = common.load_json(args.papers), load_themes(args.themes)
    if args.prepare:
        if not args.pi:
            ap.error("--prepare needs --pi")
        n, noab = prepare(papers, common.load_optional_json(args.abstracts, {}), themes, args.pi,
                          args.dir, args.batch)
        print(f"{n} batch(es) of up to {args.batch} in {args.dir}/ ({noab} item(s) without an abstract); "
              f"dispatch one checking agent per batch with {args.dir}/brief.md")
        return 0
    checks = {}
    for f in sorted(glob.glob(os.path.join(args.dir, "result_*.json"))):
        for c in common.load_json(f):
            if c.get("ref") in checks:
                sys.exit(f"✗ {c['ref']} is checked twice")
            checks[c["ref"]] = c
    lane, problems = build(papers, checks, themes, args.lane)
    if problems:
        sys.exit("✗ lane not written:\n" + "\n".join(f"  - {p}" for p in problems))
    out = args.out or os.path.join("search_raw", f"0_{args.lane}.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    common.dump_json(lane, out)
    kinds = Counter(c.get("kind") for c in checks.values() if not c.get("include"))
    print(f"lane {args.lane}: {len(lane['papers'])} papers, {len(lane['excluded'])} excluded "
          f"({', '.join(f'{k} {n}' for k, n in kinds.most_common())}) -> {out}")
    nodoi = [x["ref"] for x in lane["papers"] if not x["doi"]]
    if nodoi:
        print(f"  {len(nodoi)} without a DOI (they get a hand check, Phase 3e): {', '.join(nodoi)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
