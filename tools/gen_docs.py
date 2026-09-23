#!/usr/bin/env python3
"""Generate the tool index that docs/tools.md, tools/README.md and PLAYBOOK.md share.

It also stamps the toolkit's version, computed from git history by version.py
(uncommitted changes count as the next commit), into every file that states it.
Run it just before committing, with everything you intend to commit, passing
the bump the commit will declare:

  python3 tools/gen_docs.py --bump minor   # then commit with "Version-Bump: minor"

Four documents used to hand-describe every tool, and they drifted (one said
the gate did not catch mojibake while another said it did; two disagreed on
the family-count limit). The index — script, phase, one-line purpose, flags —
is mechanical, so it is generated from the modules themselves: the docstring's
first sentence, the module's PHASE constant, and the argparse options reported
by `--help`. The narrative around it stays hand-written.

  python3 tools/gen_docs.py            # rewrite the block and the version in every target file
  python3 tools/gen_docs.py --check    # exit 1 if anything is stale (CI runs this)

Targets carry the block between two marker comments; everything outside them is
left alone. A tool without a PHASE constant is listed with "—".
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
    table = render_table(tool_entries())
    stale = []
    for rel in TARGETS:
        path = os.path.join(ROOT, rel)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        new = splice(text, table)
        if new != text:
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
