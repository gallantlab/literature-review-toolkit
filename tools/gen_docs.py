#!/usr/bin/env python3
"""Generate the tool index that docs/tools.md, tools/README.md and PLAYBOOK.md share.

Four documents used to hand-describe every tool, and they drifted (one said
the gate did not catch mojibake while another said it did; two disagreed on
the family-count limit). The index — script, phase, one-line purpose, flags —
is mechanical, so it is generated from the modules themselves: the docstring's
first sentence, the module's PHASE constant, and the argparse options reported
by `--help`. The narrative around it stays hand-written.

  python3 tools/gen_docs.py            # rewrite the block in every target file
  python3 tools/gen_docs.py --check    # exit 1 if any target is stale (CI runs this)

Targets carry the block between two marker comments; everything outside them is
left alone. A tool without a PHASE constant is listed with "—".
"""
import argparse
import ast
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGETS = ["docs/tools.md", "tools/README.md", "PLAYBOOK.md"]
BEGIN = "<!-- BEGIN GENERATED TOOL INDEX (python3 tools/gen_docs.py — do not edit by hand) -->"
END = "<!-- END GENERATED TOOL INDEX -->"
SKIP = {"gen_docs.py", "__init__.py"}


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
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        m = re.search(r'^PHASE = "([^"]*)"', src, re.M)
        entries.append({"name": name, "phase": m.group(1) if m else "—",
                        "purpose": _first_sentence(ast.get_docstring(tree)),
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


def splice(text, inner):
    """Replace what lies between the markers with `inner`; the markers and
    everything outside them are kept. Raises if a target has no markers."""
    i, j = text.find(BEGIN), text.find(END)
    if i < 0 or j < 0:
        raise ValueError("target has no generated-block markers")
    return text[:i + len(BEGIN)] + "\n" + inner + "\n" + text[j:]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report stale targets and exit 1; write nothing")
    args = ap.parse_args()
    table = render_table(tool_entries())
    stale = []
    for rel in TARGETS:
        path = os.path.join(ROOT, rel)
        text = open(path, encoding="utf-8").read()
        new = splice(text, table)
        if new != text:
            stale.append(rel)
            if not args.check:
                open(path, "w", encoding="utf-8").write(new)
    if args.check:
        if stale:
            print("stale generated tool index in: " + ", ".join(stale)
                  + "  — run `python3 tools/gen_docs.py`")
            sys.exit(1)
        print("✓ generated tool index is fresh in " + ", ".join(TARGETS))
    else:
        print(f"updated {len(stale)} of {len(TARGETS)} targets" if stale else "all targets already fresh")


if __name__ == "__main__":
    main()
