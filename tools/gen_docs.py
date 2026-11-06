#!/usr/bin/env python3
"""Generate the tool index that docs/tools.md, tools/README.md and PLAYBOOK.md share.

It also stamps the toolkit's version, computed from git history by version.py
(uncommitted changes count as the next commit), into every file that states it.
Run it just before committing, with everything you intend to commit, and pass
the bump the commit will declare:

  python3 tools/gen_docs.py --bump minor   # then commit with "Version-Bump: minor"
  python3 tools/gen_docs.py                # rewrite the block and the version in every target file
  python3 tools/gen_docs.py --check        # exit 1 if anything is stale (CI runs this)

The index gives each script's phase, one-line purpose and flags. Four documents
once described every tool by hand, and they drifted apart: one said the gate did
not catch mojibake while another said it did, and two disagreed on the
family-count limit. So the index is generated from the modules themselves: the
docstring's first sentence, the module's PHASE constant, and the options that
`--help` reports. The narrative around it stays hand-written.

tools/README.md also gets a second generated block: every tool's whole module
docstring, one section per tool in phase order. So a tool's details are written
once, at the top of the script, and the README cannot drift from them.

Each target carries a block between two marker comments; everything outside
them is left alone. A tool without a PHASE constant is listed with "—".
gen_docs.py and version.py are maintainer tools, so they are not listed.
"""
import argparse
import ast
import functools
import glob
import os
import re
import subprocess
import sys

import version

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGETS = ["docs/tools.md", "tools/README.md", "PLAYBOOK.md"]
BEGIN = "<!-- BEGIN GENERATED TOOL INDEX (python3 tools/gen_docs.py — do not edit by hand) -->"
END = "<!-- END GENERATED TOOL INDEX -->"
SKIP = {"gen_docs.py", "version.py", "__init__.py"}   # maintainer tools, not review tools
# tools/README.md also carries each tool's full docstring, generated: the README used to
# restate every tool by hand and drifted from the code it described.
DETAILS_TARGET = "tools/README.md"
DETAILS_BEGIN = "<!-- BEGIN GENERATED TOOL DETAILS (python3 tools/gen_docs.py — do not edit by hand) -->"
DETAILS_END = "<!-- END GENERATED TOOL DETAILS -->"
# (file, regex whose one group is the stated version)
VERSION_TARGETS = [
    (".claude-plugin/plugin.json", r'"version": "(\d+\.\d+\.\d+)"'),
    (".claude-plugin/marketplace.json", r'"version": "(\d+\.\d+\.\d+)"'),
    ("skills/literature-review/SKILL.md", r"^  version: (\d+\.\d+\.\d+)$"),
    ("mkdocs.yml", r"Version (\d+\.\d+\.\d+)"),
    ("docs/index.md", r"Version (\d+\.\d+\.\d+)"),
    ("README.md", r"Version (\d+\.\d+\.\d+)"),
]


def _first_sentence(doc):
    para = (doc or "").strip().split("\n\n")[0]
    para = " ".join(para.split())
    m = re.match(r"(.+?[.!?])(?:\s|$)", para)
    return (m.group(1) if m else para).strip()


def _flags(path):
    """Options as argparse reports them — the tool's own `--help`, so the index
    can never list a flag that does not exist."""
    try:
        out = subprocess.run([sys.executable, path, "--help"], capture_output=True,
                             text=True, timeout=60).stdout
    except Exception:
        return []
    return sorted(set(re.findall(r"^\s+(?:-\w, )?(--[\w-]+)", out, re.M)) - {"--help"})


def tool_entries():
    """[{name, phase, purpose, flags}] for every script in tools/, sorted by phase."""
    entries = []
    for path in sorted(glob.glob(os.path.join(HERE, "*.py"))):
        name = os.path.basename(path)
        if name in SKIP:
            continue
        with open(path, encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        m = re.search(r'^PHASE = "([^"]*)"', src, re.M)
        entries.append({"name": name, "phase": m.group(1) if m else "—",
                        "purpose": _first_sentence(ast.get_docstring(tree)),
                        "doc": (ast.get_docstring(tree) or "").strip(),
                        "flags": _flags(path) if "argparse" in src else []})

    def order(e):     # numeric phases first, then lab (L*), then helpers (—)
        p = e["phase"]
        m = re.match(r"(\d+)([a-z]?)", p)
        return (0, int(m.group(1)), m.group(2)) if m else (1, p, "")
    return sorted(entries, key=lambda e: (order(e), e["name"]))


def render_table(entries):
    rows = ["| Script | Phase | Purpose | Flags |", "|---|---|---|---|"]
    for e in entries:
        flags = " ".join(f"`{f}`" for f in e["flags"]) or "—"
        rows.append(f"| `{e['name']}` | {e['phase']} | {e['purpose']} | {flags} |")
    return "\n".join(rows)


def render_block(entries):
    return "\n".join([BEGIN, render_table(entries), END])


def render_details(entries):
    """One section per tool: its whole module docstring, verbatim, in phase order."""
    out = []
    for e in entries:
        p = e["phase"]
        label = "Shared helpers" if p == "—" else f"Lab mode {p}" if p.startswith("L") else f"Phase {p}"
        out.append(f"### {label}: `{e['name']}`\n\n```text\n{e['doc']}\n```")
    return "\n\n".join(out)


# ---------------------------------------------------------------------------
# Tables generated from the registries that own them. Four tables in PLAYBOOK.md
# restated values that live in the code, and two had already drifted: the row
# colors listed eight sources where spreadsheet.py had nine, and the warning table
# was missing an id added the same morning. Each renderer below reads its module,
# so the prose cannot say something the code does not.


def marker(name, kind):
    """The block markers, in the same shape as the tool index's: the BEGIN marker
    carries the command that regenerates it, the END marker is bare."""
    note = " (python3 tools/gen_docs.py — do not edit by hand)" if kind == "BEGIN" else ""
    return f"<!-- {kind} GENERATED {name}{note} -->"


def _row(*cells):
    return "| " + " | ".join(str(c) for c in cells) + " |"


def render_scales():
    """Phase 1d's scale table, from common.SEARCH_SCALES."""
    import common
    out = [_row("Scale", "The user says", "Per lane", "Capped", "Lanes"),
           _row("---", "---", "---", "---", "---")]
    for name, p in common.SEARCH_SCALES.items():
        target = f"{p['lane_target']}" + ("" if p["capped"] else ", a floor")
        out.append(_row(f"`{name}`", p["says"], target,
                        "yes" if p["capped"] else "no", "%d-%d" % p["lanes"]))
    out.append(_row("a number", '"about 300 papers"', "the total spread over the lanes",
                    "yes", "1-50"))
    return "\n".join(out)


def render_sources():
    """Phase 5's row colors, from spreadsheet.SOURCES."""
    import spreadsheet
    out = [_row("`source`", "Fill", "What the row is"), _row("---", "---", "---")]
    for name, (fill, why) in spreadsheet.SOURCES.items():
        out.append(_row(f"`{name}`", f"`{fill}`" if fill else "white (none)", why))
    return "\n".join(out)


def render_defects():
    """Phase 3f's defect list, from references.DEFECTS. Each one fails the audit."""
    import references
    out = [_row("Defect", "What it means"), _row("---", "---")]
    for name, why in references.DEFECTS.items():
        out.append(_row(f"`{name}`", why))
    return "\n".join(out)


def render_warnings():
    """Phase 3f's warning table, from references.WARNINGS."""
    import references
    out = [_row("Warning id", "What it flags", "Verdict needed"), _row("---", "---", "---")]
    for name, (flags, verdict) in references.WARNINGS.items():
        out.append(_row(f"`{name}`", flags, verdict))
    return "\n".join(out)


# (block name, renderer, the files that carry its markers)
BLOCKS = [
    ("SEARCH SCALES", render_scales, ["PLAYBOOK.md", "docs/search.md"]),
    ("ROW COLORS", render_sources, ["PLAYBOOK.md"]),
    ("AUDIT DEFECTS", render_defects, ["PLAYBOOK.md"]),
    ("AUDIT WARNINGS", render_warnings, ["PLAYBOOK.md", "docs/checks.md"]),
]


def splice(text, inner, begin=BEGIN, end=END):
    """Replace what lies between the markers with `inner`; the markers and
    everything outside them are kept. Raises if a target has no markers."""
    i, j = text.find(begin), text.find(end)
    if i < 0 or j < 0:
        raise ValueError("target has no generated-block markers")
    return text[:i + len(begin)] + "\n" + inner + "\n" + text[j:]


PENDING_BUMP = None   # set from --bump: what the commit being prepared will declare


@functools.lru_cache(maxsize=None)
def current_version():
    return version.current(include_pending=True, pending_bump=PENDING_BUMP)


def sync_version(text, pattern, version):
    """Rewrite every version string `pattern` matches to `version`. Raises if the
    pattern matches nothing, so a target that lost its version string is caught
    rather than silently skipped."""
    rx = re.compile(pattern, re.M)
    if not rx.search(text):
        raise ValueError("no version string matching %r" % pattern)
    return rx.sub(lambda m: m.group(0).replace(m.group(1), version), text)


def version_status(write=False):
    """[(file, was_stale)] for every version target; rewrites stale ones if `write`."""
    ver, out = current_version(), []
    for rel, pattern in VERSION_TARGETS:
        path = os.path.join(ROOT, rel)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        new = sync_version(text, pattern, ver)
        out.append((rel, new != text))
        if write and new != text:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report stale targets and exit 1; write nothing")
    ap.add_argument("--bump", choices=version.BUMPS,
                    help="the Version-Bump the commit being prepared will declare (judged from the work)")
    args = ap.parse_args()
    global PENDING_BUMP
    PENDING_BUMP = args.bump
    entries = tool_entries()
    table, details = render_table(entries), render_details(entries)
    stale = []
    for rel in TARGETS:
        path = os.path.join(ROOT, rel)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        new = splice(text, table)
        if rel == DETAILS_TARGET and DETAILS_BEGIN in new:
            new = splice(new, details, DETAILS_BEGIN, DETAILS_END)
        if new != text:
            stale.append(rel)
            if not args.check:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new)
    for name, render, targets in BLOCKS:
        inner = render()
        for rel in targets:
            path = os.path.join(ROOT, rel)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            new = splice(text, inner, marker(name, "BEGIN"), marker(name, "END"))
            if new != text:
                if rel not in stale:
                    stale.append(rel)
                if not args.check:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new)
    vstale = [rel for rel, was in version_status(write=not args.check) if was]
    if args.check:
        if stale:
            print("stale generated tool index in: " + ", ".join(stale)
                  + "  — run `python3 tools/gen_docs.py`")
        if vstale:
            print("version differs from the computed %s in: %s  — run `python3 tools/gen_docs.py`"
                  % (current_version(), ", ".join(vstale)))
        if stale or vstale:
            sys.exit(1)
        print("✓ generated tool index is fresh in " + ", ".join(TARGETS))
        print("✓ version %s is stamped in all %d files" % (current_version(), len(VERSION_TARGETS)))
    else:
        print(f"updated {len(stale)} of {len(TARGETS)} targets" if stale else "all targets already fresh")
        if vstale:
            print("set version %s in: %s" % (current_version(), ", ".join(vstale)))


if __name__ == "__main__":
    main()
