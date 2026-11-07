#!/usr/bin/env python3
"""Phase 8: assemble the hand-off report from the files beside the table.

Every figure Phase 8 asks for is already on disk when the run ends — in
rows.json, the preflight record, the merge report, the candidate ledger, the
run sidecars, the acknowledgments and the hand fixes. Asking the agent to
remember them is asking for the least reliable summary of the run, written at
the point where it has least left, of the one part the user actually reads.

  python3 tools/handoff.py --project .
  python3 tools/handoff.py --project . --out HANDOFF.md

It reads; it never writes into the project except the `--out` file you name.
Each line is a fact from a file, and a file that is missing is reported as
missing rather than filled in: "no preflight.json" is information about the run.

Exit 1 when the deliverable is not ready to hand off — no spreadsheet, or only
a `_DRAFT`. That is the one condition under which the report should not be
read out to the user. Everything else is reported, never gated: a capped pass
or a declined timeline is a thing to say, not a thing to stop for.

What it cannot know stays with the agent: whether the timeline was offered and
declined (it can only see that none was built), and the reason behind a
`--no-preflight` run, which is recorded nowhere.
"""
import argparse
import glob
import os
import sys

import common
import spreadsheet

PHASE = "8"   # pipeline phase, read by tools/gen_docs.py for the tool index

# Warning ids that mean a pass ran short. Their meanings are in
# references.WARNINGS; this is the subset Phase 8 has to report.
SHORT_RUN = ("incomplete-", "partial-", "capped")


def load(project, name, default=None):
    path = os.path.join(project, name)
    return common.load_json(path) if os.path.exists(path) else default


def find(project, pattern, exclude=()):
    """Project files matching a glob, newest first, excluding marked drafts."""
    hits = [p for p in glob.glob(os.path.join(project, pattern))
            if not any(x in os.path.basename(p) for x in exclude)]
    return sorted(hits, key=os.path.getmtime, reverse=True)


def corpus(out, rows, keyf, ledger):
    """Total rows by source, and the candidates considered."""
    counts = {}
    for r in rows:
        counts[r.get("source") or "(no source)"] = counts.get(r.get("source") or "(no source)", 0) + 1
    out.append(f"## Corpus\n\n**{len(rows)} papers.** By source:\n")
    for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        # SOURCES is spreadsheet.py's registry, the same one that colors the
        # rows; a source it does not know is reported, not silently relabeled.
        why = spreadsheet.SOURCES.get(name, (None, "not a known row source"))[1]
        out.append(f"- **{n}** {name} — {why}")
    if ledger is None:
        out.append("\nNo candidate ledger (`candidates.json`): no cross-citation "
                   "or forward-citation pass is recorded.")
        return
    decided = {}
    for _doi, c in candidates_in(ledger):
        decided[c.get("decision") or "pending"] = decided.get(c.get("decision") or "pending", 0) + 1
    total = sum(decided.values())
    out.append(f"\n**{total} candidates considered**: "
               + ", ".join(f"{n} {d}" for d, n in sorted(decided.items(), key=lambda kv: -kv[1]))
               + ". Every exclusion is listed with its reason on the "
                 "spreadsheet's \"Considered and excluded\" sheet.")
    if decided.get("pending"):
        out.append(f"\n> {decided['pending']} candidate(s) are still undecided. "
                   "The audit fails while any is pending.")


def candidates_in(ledger):
    """(doi, entry) pairs; keys starting with '_' are records, not candidates."""
    return [(k, v) for k, v in sorted((ledger or {}).items())
            if not k.startswith("_") and isinstance(v, dict)]


def deliverables(out, project, families):
    """The paths to hand over. Returns False when there is nothing to hand over."""
    out.append("## Deliverables\n")
    ready = True
    books = find(project, "*.xlsx", exclude=("_DRAFT", "~$"))
    drafts = find(project, "*_DRAFT.xlsx")
    if books:
        out.append(f"- Spreadsheet: `{os.path.basename(books[0])}`")
    elif drafts:
        out.append(f"- ✗ Only a draft workbook exists (`{os.path.basename(drafts[0])}`). "
                   "A draft is never the deliverable: fix the audit and rerun "
                   "`spreadsheet.py` without `--draft`.")
        ready = False
    else:
        out.append("- ✗ No spreadsheet. `spreadsheet.py` has not written one.")
        ready = False

    timelines = find(project, "*_families.html")
    if timelines:
        names = [f["name"] for f in (families or {}).get("families", [])]
        out.append(f"- Timeline: `{os.path.basename(timelines[0])}` (open in a browser)"
                   + (f" — {len(names)} families: {', '.join(names)}" if names else ""))
    else:
        out.append("- No timeline was built. Say whether it was offered and declined; "
                   "this tool cannot tell those apart.")
    for pattern, what in (("*_review.html", "Review page"), ("*review*.docx", "Review document")):
        hit = find(project, pattern, exclude=("~$",))
        if hit:
            out.append(f"- {what}: `{os.path.basename(hit[0])}`")
    return ready


def how_it_ran(out, project, pre, merge, ledger, acks, n_rows):
    out.append("## How it was run\n")
    if pre:
        out.append(f"- Scale: **{pre.get('scale', '?')}** "
                   f"(preflight {pre.get('at', '?')}, toolkit {pre.get('version', '?')})")
        acc = pre.get("accepted") or []
        out.append(f"- Recorded at the preflight: {', '.join(acc)}" if acc
                   else "- No choice was recorded at the preflight (`--accept`).")
        if pre.get("offline"):
            out.append("- The preflight ran offline, so no key or budget was probed.")
        if not pre.get("cleared", True):
            out.append("- ✗ The preflight was not cleared.")
    else:
        out.append("- No `preflight.json`: the run recorded no scale and no "
                   "preflight choice. Say why the preflight was skipped.")

    for lane in (merge or {}).get("lanes", []):
        if lane.get("returned", 0) < lane.get("target", 0):
            out.append(f"- Lane {lane['lane']} returned {lane['returned']} "
                       f"of a target {lane['target']}.")
    if (merge or {}).get("over_cap"):
        out.append(f"- {len(merge['over_cap'])} lane(s) ran over the cap.")

    short = []
    for src, run in sorted(((ledger or {}).get("_runs") or {}).items()):
        if not run.get("complete", True):
            short.append(f"The {src} pass did not finish: some fetches failed.")
        elif run.get("n_papers") is not None and run["n_papers"] < n_rows:
            # A pass that read fewer papers than the table now holds is the
            # normal shape after candidates are appended, not a fault — but it
            # is exactly what Phase 8 has to say out loud.
            short.append(f"The {src} pass read {run['n_papers']} of the "
                         f"{n_rows} papers now in the table, and proposed "
                         f"{run.get('n', '?')} candidates.")
    for ref, entries in sorted((acks or {}).items()):
        for wid, why in sorted((entries or {}).items()):
            if wid.startswith(SHORT_RUN):
                where = "corpus" if ref == "*" else ref
                short.append(f"Acknowledged `{wid}` ({where}): {why}")
    out.append("- " + "\n- ".join(short) if short
               else "- No pass ran capped or incomplete.")

    misses = find(project, "*recovery_input.json")
    if misses:
        n = len(common.load_json(misses[0]) or [])
        out.append(f"- Rerun of an older build: {n} paper(s) from it were missed and "
                   f"sent to a recovery lane (`{os.path.basename(misses[0])}`). "
                   "Report the recall `recall.py` printed.")


def corrections(out, rows, keyf, fixes, handchecks):
    out.append("## Corrections made while verifying\n")
    overs = [r for r in rows if r.get("verify_override")]
    if overs:
        out.append(f"**{len(overs)} verification override(s)** — each a verdict "
                   "judged a false alarm, with its reason:\n")
        for r in overs:
            ov = r["verify_override"]
            out.append(f"- `{r.get(keyf, '?')}` (overrode {ov.get('overrode', '?')}): "
                       f"{ov.get('reason', '(no reason recorded)')}")
    else:
        out.append("No verification verdict was overridden.")
    n_fix = sum(len(v) for v in (fixes or {}).values())
    if n_fix:
        out.append(f"\n**{n_fix} reference correction(s)** recorded in "
                   f"`hand_fixes.json`, across {len(fixes)} paper(s).")
    if handchecks:
        kinds = {}
        for h in handchecks:
            kinds[h.get("verdict", "?")] = kinds.get(h.get("verdict", "?"), 0) + 1
        out.append("\n**Hand checks** (rows with no DOI or arXiv id): "
                   + ", ".join(f"{n} {v}" for v, n in sorted(kinds.items())) + ".")


def pdfs(out, project):
    manual = find(project, "**/_needs_manual.txt")
    dirs = [d for d in glob.glob(os.path.join(project, "**", "*.pdf"), recursive=True)]
    if not manual and not dirs:
        return
    out.append("## PDFs\n")
    out.append(f"- {len(dirs)} PDF(s) on disk.")
    if manual:
        lines = [ln for ln in open(manual[0], encoding="utf-8").read().split("\n") if ln.strip()]
        out.append(f"- {len(lines)} could not be fetched; the list is in "
                   f"`{os.path.relpath(manual[0], project)}`.")


def report(project, rows_name):
    rows = common.load_json(os.path.join(project, rows_name))
    keyf = common.key_field(rows)
    ledger = load(project, "candidates.json")
    out = [f"# Hand-off: {os.path.basename(os.path.abspath(project))}\n"]
    corpus(out, rows, keyf, ledger)
    out.append("")
    ready = deliverables(out, project, load(project, "families.json"))
    out.append("")
    how_it_ran(out, project, load(project, "preflight.json"),
               load(project, "merge_report.json"), ledger,
               load(project, "audit_acks.json"), len(rows))
    out.append("")
    corrections(out, rows, keyf, load(project, "hand_fixes.json"),
                load(project, "handcheck_result.json"))
    out.append("")
    pdfs(out, project)
    return "\n".join(out).rstrip() + "\n", ready


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".", help="the project directory (default: .)")
    ap.add_argument("--rows", default="rows.json", help="table file name inside --project")
    ap.add_argument("--out", help="also write the report to this file")
    args = ap.parse_args()

    if not os.path.exists(os.path.join(args.project, args.rows)):
        sys.exit(f"no {args.rows} in {args.project}: there is no table to hand off")
    text, ready = report(args.project, args.rows)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {args.out}", file=sys.stderr)
    if not ready:
        sys.exit(1)


if __name__ == "__main__":
    main()
