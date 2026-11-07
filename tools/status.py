#!/usr/bin/env python3
"""Read a project directory and print what is done, what is left, and the next command.

Every phase of a build leaves a trace on disk: a preflight record, a lane
manifest, verify stamps on rows, canonical reference strings, counts, abstracts,
summary checks, run sidecars, a candidate ledger, a families file, the
spreadsheet. The state of a build is therefore readable, and until now nothing
read it. An agent that lost its place had to notice; with this it can ask.

  python3 tools/status.py --project .
  python3 tools/status.py --project . --next     # just the next command
  python3 tools/status.py --project . --writers  # what may run at the same time

Each step reports one of:

  done     the artifact is there and covers the table
  part     it ran, but not over everything now in the table
  todo     no trace of it
  n/a      optional, and not started (PDFs, the written review)

`part` is the state that matters. A pass that ran before candidates were
appended is the normal shape of a real build, and it is invisible in a file
listing: only the counts show it.

This tool reads. It never writes, never fetches, and never decides anything a
gate decides — it cannot tell you the audit passes, only that you have not run
it. The next command it prints is the first step that is not done.
"""
import argparse
import ast
import glob
import os
import sys

import common

PHASE = "—"   # a helper: it belongs to no phase, and reads them all

# The tools that WRITE rows.json, derived from their own source rather than
# listed by hand. Contract: one writer of the table at a time; a reader may run
# beside a writer (PLAYBOOK "Running steps at the same time"). The regression
# suite compares this against the playbook's prose, which is the copy that drifts.
SAVERS = ("save_rows", "write_rows")


def _called(tree):
    """Every function name called in a module, attribute calls flattened."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            names.add(f.attr if isinstance(f, ast.Attribute) else
                      f.id if isinstance(f, ast.Name) else "")
    return names


def table_writers(tools_dir=None):
    """Tool file names that save rows.json, by reading what each one CALLS.

    Parsed, not grepped: the same names appear in docstrings and comments all
    over the toolkit, and a tool that only documents the rule is not a writer.
    """
    tools_dir = tools_dir or os.path.dirname(os.path.abspath(__file__))
    out = []
    for path in sorted(glob.glob(os.path.join(tools_dir, "*.py"))):
        name = os.path.basename(path)
        if name in ("common.py", "status.py"):
            continue
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        if _called(tree) & set(SAVERS):
            out.append(name)
    return out


class Project:
    """Everything on disk, read once."""

    def __init__(self, path, rows_name="rows.json"):
        self.path = path
        self.rows_name = rows_name
        self.rows = []
        rp = os.path.join(path, rows_name)
        if os.path.exists(rp):
            self.rows = common.load_json(rp)
        self.keyf = common.key_field(self.rows) if self.rows else "ref"

    def has(self, name):
        return os.path.exists(os.path.join(self.path, name))

    def json(self, name, default=None):
        return common.load_json(os.path.join(self.path, name)) if self.has(name) else default

    def glob(self, pattern, exclude=()):
        return [p for p in glob.glob(os.path.join(self.path, pattern))
                if not any(x in os.path.basename(p) for x in exclude)]

    def count(self, pred):
        return sum(1 for r in self.rows if pred(r))

    @property
    def n(self):
        return len(self.rows)


def _part(done, total, what, cmd):
    """done/part/todo from a count, so 'ran, but not over everything' shows."""
    if total and done >= total:
        return ("done", f"all {total} {what}", None)
    if done:
        return ("part", f"{done} of {total} {what}", cmd)
    return ("todo", f"no {what}", cmd)


# --------------------------------------------------------------------------
# One function per step. Each returns (state, detail, next command or None).
# --------------------------------------------------------------------------

def s_preflight(p):
    pre = p.json("preflight.json")
    if not pre:
        return ("todo", "no preflight.json",
                "python3 tools/preflight.py --project . --scale <scale>")
    if not pre.get("cleared", True):
        return ("todo", f"preflight at {pre.get('at', '?')} was NOT cleared",
                "python3 tools/preflight.py --project . --scale "
                f"{pre.get('scale', '<scale>')} --accept cap|wait")
    acc = ", ".join(pre.get("accepted") or []) or "no --accept recorded"
    return ("done", f"scale {pre.get('scale', '?')}, toolkit "
                    f"{pre.get('version', '?')}, {acc}", None)


def s_lanes(p):
    spec = p.json("lanes.json")
    if not spec:
        return ("todo", "no lanes.json", "write lanes.json (Phase 1), then "
                "python3 tools/lane_briefs.py --spec lanes.json")
    lanes = spec.get("lanes", spec if isinstance(spec, list) else [])
    raw = p.glob("search_raw/*.json")
    return _part(len(raw), len(lanes), "lane file(s) in search_raw/",
                 "python3 tools/lane_briefs.py --spec lanes.json "
                 "(then launch one agent per lane, in one message)")


def s_merge(p):
    if not p.rows:
        return ("todo", f"no {p.rows_name}",
                f"python3 tools/merge_lanes.py --raw search_raw --out {p.rows_name}")
    rep = p.json("merge_report.json") or {}
    anteced = p.count(lambda r: str(r.get("source", "")).startswith("anteced"))
    note = f"{p.n} rows"
    if rep.get("lanes"):
        note += f" from {len(rep['lanes'])} lanes"
    note += f", {anteced} antecedents" if anteced else ", NO antecedents (contract rule 4)"
    return ("done" if anteced else "part", note,
            None if anteced else "run the antecedents pass (Phase 2b): it is required at every scale")


def s_verify(p):
    if not p.rows:
        return ("todo", "no table to verify", None)
    ok = p.count(common.verified_ok)
    return _part(ok, p.n, "rows verified",
                 f"python3 tools/verify.py --rows {p.rows_name} --out verify_report.json")


def s_handcheck(p):
    # common.ids_of returns a (doi, arxiv) PAIR, so the tuple itself is always
    # truthy; a row with neither id is ("", ""). Asking the tuple rather than
    # its contents reported a corpus of DOI-less rows as fully identified.
    noid = [r for r in p.rows if not any(common.ids_of(r))]
    if not noid:
        return ("done", "every row has a DOI or arXiv id", None)
    checked = {h.get("ref") for h in (p.json("handcheck_result.json") or [])}
    done = sum(1 for r in noid if r.get(p.keyf) in checked)
    return _part(done, len(noid), "DOI-less rows hand-checked",
                 f"python3 tools/handcheck.py --rows {p.rows_name} --prepare handcheck_input.json")


def s_canon(p):
    """Canonical, or one of contract rule 2's two recorded exceptions.

    A DOI-less row's hand-checked `apa` stands, and a row whose source had no
    usable record keeps its `apa` under an acknowledged `kept-existing-apa`.
    Neither ever gets a `canonical_at`, so counting only that stamp leaves a
    finished build three rows short forever and keeps proposing a canon re-run.
    """
    if not p.rows:
        return ("todo", "no table", None)
    acks = p.json("audit_acks.json") or {}

    def settled(r):
        if r.get("canonical_at") or not any(common.ids_of(r)):
            return True
        return any(w.startswith("kept-existing-apa")
                   for w in (acks.get(str(r.get(p.keyf))) or {}))

    done = p.count(settled)
    return _part(done, p.n, "references canonical (or an acknowledged exception)",
                 f"python3 tools/references.py --rows {p.rows_name} --out {p.rows_name}")


def s_counts(p):
    done = p.count(lambda r: r.get("cite_asof"))
    return _part(done, p.n, "rows with citation counts",
                 f"python3 tools/citations.py --rows {p.rows_name}")


def s_abstracts(p):
    done = p.count(lambda r: str(r.get("summary") or "").strip())
    return _part(done, p.n, "rows with a summary",
                 f"python3 tools/abstracts.py --rows {p.rows_name} --out abstracts.json")


def s_summary_check(p):
    with_sum = p.count(lambda r: str(r.get("summary") or "").strip())
    done = p.count(lambda r: (r.get("summary_check") or {}).get("verdict"))
    bad = p.count(lambda r: (r.get("summary_check") or {}).get("verdict")
                  in ("unsupported", "wrong-abstract"))
    state, detail, cmd = _part(done, with_sum, "summaries checked",
                               f"python3 tools/summary_audit.py --rows {p.rows_name} --prepare summary_audit")
    if bad:
        return ("part", detail + f", {bad} flagged", "fix the flagged rows and re-run summary_audit.py")
    return (state, detail, cmd)


def s_candidates(p):
    ledger = p.json("candidates.json")
    if ledger is None:
        return ("todo", "no candidate ledger",
                f"python3 tools/xref.py --rows {p.rows_name} --out xref.json "
                "--internal-out internal_citations.json  (then forward.py, then candidates.py --add)")
    cands = [(k, v) for k, v in ledger.items() if not k.startswith("_") and isinstance(v, dict)]
    pending = [k for k, v in cands if not v.get("decision")]
    runs = ledger.get("_runs") or {}
    short = [s for s, r in runs.items()
             if not r.get("complete", True) or (r.get("n_papers") or 0) < p.n]
    if pending:
        return ("part", f"{len(pending)} of {len(cands)} candidates undecided",
                "python3 tools/candidates.py --rows %s --prepare candidate_batches "
                "--scope lanes.json" % p.rows_name)
    missing = [s for s in ("xref", "forward") if s not in runs]
    if missing:
        return ("part", f"{len(cands)} candidates decided; no {'/'.join(missing)} run recorded",
                f"python3 tools/{missing[0]}.py --rows {p.rows_name}")
    if short:
        return ("part", f"{len(cands)} candidates decided; {', '.join(short)} ran short "
                        "(acknowledge it or re-run)", None)
    return ("done", f"{len(cands)} candidates, all decided", None)


def s_families(p):
    fam = p.json("families.json")
    if not fam:
        return ("n/a", "no families.json (offer the timeline: Phase 6b)",
                f"python3 tools/families.py --rows {p.rows_name} --digest")
    assigned = len(fam.get("assignments") or {})
    names = [f["name"] for f in fam.get("families", [])]
    state, detail, cmd = _part(assigned, p.n, f"rows assigned to {len(names)} families",
                               f"python3 tools/families.py --rows {p.rows_name} "
                               "--assign families_input.json --out families.json")
    return (state, detail, cmd)


def s_figure(p):
    if not p.json("families.json"):
        return ("n/a", "no families to draw", None)
    figs = p.glob("*_families.html")
    return ("done", os.path.basename(figs[0]), None) if figs else (
        "todo", "no timeline page",
        "python3 tools/families_figure.py --rows %s --families families.json "
        "--out <topic>_families.html" % p.rows_name)


def s_audit(p):
    acks = p.json("audit_acks.json")
    return ("todo", "the audit is a gate, and this tool does not run it",
            f"python3 tools/references.py --rows {p.rows_name} --audit"
            + ("" if acks else "   (then --list-acks for any warning)"))


def s_spreadsheet(p):
    books = p.glob("*.xlsx", exclude=("_DRAFT", "~$"))
    if books:
        return ("done", os.path.basename(books[0]), None)
    drafts = p.glob("*_DRAFT.xlsx")
    return ("part" if drafts else "todo",
            "only a draft workbook" if drafts else "no workbook",
            f"python3 tools/spreadsheet.py --rows {p.rows_name} --out <topic>_bibliography.xlsx")


def s_review(p):
    pages = p.glob("*_review.html") + p.glob("*review*.docx", exclude=("~$",))
    if not pages:
        return ("n/a", "no written review (Phase 7 is optional)", None)
    return ("done", ", ".join(sorted(os.path.basename(x) for x in pages)),
            "gates: cite_check.py, priority_check.py, prose_audit.py --baseline")


def s_handoff(p):
    return ("todo", "the report is assembled from the files",
            "python3 tools/handoff.py --project .")


STEPS = [
    ("0",  "Preflight",            s_preflight),
    ("1",  "Lanes briefed, run",   s_lanes),
    ("2c", "Merged into a table",  s_merge),
    ("3",  "Verified",             s_verify),
    ("3e", "DOI-less rows",        s_handcheck),
    ("3f", "Canonical references", s_canon),
    ("5b", "Citation counts",      s_counts),
    ("5c", "Abstracts/summaries",  s_abstracts),
    ("5c", "Summary check",        s_summary_check),
    ("6",  "Candidates",           s_candidates),
    ("6b", "Families",             s_families),
    ("6b", "Timeline",             s_figure),
    ("3f", "Reference audit",      s_audit),
    ("5",  "Spreadsheet",          s_spreadsheet),
    ("7",  "Written review",       s_review),
    ("8",  "Hand-off",             s_handoff),
]

MARK = {"done": "✓", "part": "–", "todo": "○", "n/a": " "}


def run(p):
    return [(phase, name) + fn(p) for phase, name, fn in STEPS]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".", help="the project directory (default: .)")
    ap.add_argument("--rows", default="rows.json", help="table file name inside --project")
    ap.add_argument("--next", action="store_true", help="print only the next command")
    ap.add_argument("--writers", action="store_true",
                    help="which tools write the table, and what may run beside them")
    args = ap.parse_args()

    if args.writers:
        writers = table_writers()
        print("Write rows.json (one at a time):\n  " + "\n  ".join(writers))
        print("\nAnything not in that list only reads the table, and may run beside a "
              "writer.\nSemantic Scholar is paced in code (common.s2_wait_turn), so "
              "citations.py,\nabstracts.py and xref.py may run side by side.")
        return

    if not os.path.isdir(args.project):
        sys.exit(f"no such directory: {args.project}")
    p = Project(args.project, args.rows)
    rows_in_lab = p.has("lab_papers.json")
    steps = run(p)
    nxt = next((cmd for _ph, _n, st, _d, cmd in steps if st in ("todo", "part") and cmd), None)

    if args.next:
        print(nxt or "nothing outstanding that this tool can see")
        return

    print(f"{os.path.basename(os.path.abspath(args.project))}: {p.n} rows"
          + (" (lab mode)" if rows_in_lab else ""))
    print()
    for phase, name, state, detail, _cmd in steps:
        print(f"  {MARK[state]} {phase:>3}  {name:<21} {detail}")
    print()
    print("next: " + (nxt or "nothing outstanding that this tool can see"))
    print("\nThis reads the files; it runs no gate. 'part' means a pass ran over "
          "fewer rows\nthan the table now holds — usually a pass from before "
          "candidates were appended.")


if __name__ == "__main__":
    main()
