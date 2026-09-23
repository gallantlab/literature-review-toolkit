#!/usr/bin/env python3
"""Compute the toolkit's version from its git commits: how many, and how much work.

The version is MAJOR.MINOR.PATCH, starting from MAJOR.0.0 and folding in every
non-merge commit reachable from HEAD, oldest first. Each commit is one bump:

  - major: MAJOR + 1, MINOR and PATCH reset (breaks existing projects: a flag
    removed or renamed, a rows.json field changed, an output format changed);
  - minor: MINOR + 1, PATCH reset (new capability: a tool, flag or phase);
  - patch: PATCH + 1 (fixes, docs, refactors);
  - none:  no change.

A commit declares its bump, judged from the work it does, with a trailer in its
message:

  Version-Bump: minor

A commit without the trailer (all commits before 1.13.0) is judged by size: at
least MINOR_LINES added plus removed text lines is minor, anything smaller
(including a binary-only change) is patch. Size can never declare a major bump.

MAJOR below is the base the history starts from. It is 1, not 0, because by
1.13.0 the toolkit had been in development for six months, released publicly
many times, and used in production.
Merge commits are skipped, since their changes are already counted in the
commits they merge. Lines that only state the version are not counted, so
stamping the version into files never changes it.

Uncommitted changes count as one more commit, so `gen_docs.py` can stamp the
version a commit will have before it is made. Needs full history: a shallow
clone (CI's default) must fetch with `fetch-depth: 0`.

  python3 tools/version.py              # print the version
  python3 tools/version.py --explain    # one line per commit, with its effect
"""
import argparse
import os
import re
import subprocess
import sys

MAJOR = 1
MINOR_LINES = 400
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# a line that states the toolkit version, in any of the files gen_docs.py stamps
VERSION_LINE = re.compile(r'("version": "|version: |Version )\d+\.\d+\.\d+')
BUMPS = ("major", "minor", "patch", "none")
TRAILER = re.compile(r"^Version-Bump:\s*(\w+)\s*$", re.M | re.I)


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout


def count_lines(patch):
    """(changed lines, touched a binary file) for a unified diff, skipping lines
    that only state the version."""
    n, binary, in_hunk = 0, False, False
    for line in patch.splitlines():
        if line.startswith("diff --git"):
            in_hunk = False
        elif line.startswith("Binary files"):
            binary = True
        elif line.startswith("@@"):
            in_hunk = True
        elif in_hunk and line[:1] in "+-" and not VERSION_LINE.search(line):
            n += 1
    return n, binary


def declared_bump(message):
    """The bump a commit message declares with a Version-Bump trailer, or None."""
    m = TRAILER.search(message or "")
    if not m:
        return None
    bump = m.group(1).lower()
    if bump not in BUMPS:
        raise ValueError("Version-Bump must be one of %s, not %r" % ("/".join(BUMPS), bump))
    return bump


def bump_of(lines, binary, declared=None, minor_lines=MINOR_LINES):
    """A declared bump wins; otherwise size decides. A commit that changed nothing
    countable (only version lines) is 'none'."""
    if declared:
        return declared
    if lines >= minor_lines:
        return "minor"
    return "patch" if lines or binary else "none"


def version_from_bumps(bumps, major=MAJOR):
    """Fold a sequence of bumps into (major, minor, patch)."""
    minor = patch = 0
    for b in bumps:
        if b == "major":
            major, minor, patch = major + 1, 0, 0
        elif b == "minor":
            minor, patch = minor + 1, 0
        elif b == "patch":
            patch += 1
    return major, minor, patch


def version_from_sizes(sizes, major=MAJOR, minor_lines=MINOR_LINES):
    """Fold [(lines, binary)] or [(lines, binary, declared)] into (major, minor, patch)."""
    return version_from_bumps([bump_of(*s[:2], s[2] if len(s) > 2 else None, minor_lines)
                               for s in sizes], major)


def _pending():
    """Size of the uncommitted changes, counted as a commit would count them."""
    n, binary = count_lines(_git("diff", "HEAD", "--no-renames", "-U0", "--no-color"))
    for rel in _git("ls-files", "--others", "--exclude-standard").splitlines():
        with open(os.path.join(ROOT, rel), "rb") as f:
            data = f.read()
        if b"\0" in data:
            binary = True
            continue
        n += sum(1 for line in data.decode("utf-8", "replace").splitlines()
                 if not VERSION_LINE.search(line))
    return n, binary


def history(include_pending=True, pending_bump=None):
    """[(sha, subject, lines, binary, declared)] for every counted commit, oldest
    first. Uncommitted changes, if any, get `pending_bump` as their declaration."""
    if _git("rev-parse", "--is-shallow-repository").strip() == "true":
        sys.exit("version.py: shallow clone; fetch full history (actions/checkout fetch-depth: 0)")
    out = []
    for sha in _git("rev-list", "--no-merges", "--reverse", "HEAD").split():
        lines, binary = count_lines(_git("show", "--format=", "--no-renames", "-U0", "--no-color", sha))
        message = _git("log", "-1", "--format=%B", sha)
        out.append((sha[:7], message.strip().split("\n")[0], lines, binary, declared_bump(message)))
    if include_pending:
        lines, binary = _pending()
        if lines or binary:
            out.append(("working", "(uncommitted changes)", lines, binary, pending_bump))
    return out


def current(include_pending=True, pending_bump=None):
    """The version string for the working tree (or for HEAD alone)."""
    hist = history(include_pending, pending_bump)
    return "%d.%d.%d" % version_from_sizes([(n, b, d) for _, _, n, b, d in hist])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--explain", action="store_true",
                    help="list each commit, its size and the version after it")
    ap.add_argument("--committed", action="store_true", help="ignore uncommitted changes")
    ap.add_argument("--bump", choices=BUMPS, help="the bump the uncommitted changes will declare")
    args = ap.parse_args()
    hist = history(not args.committed, args.bump)
    if args.explain:
        sizes = []
        for sha, subject, n, b, d in hist:
            sizes.append((n, b, d))
            how = d + " (declared)" if d else bump_of(n, b) + " (size)"
            print("%-8s %5d%s  %-16s %-9s %s" % (sha, n, "b" if b else " ", how,
                                                "%d.%d.%d" % version_from_sizes(sizes), subject[:60]))
    print("%d.%d.%d" % version_from_sizes([(n, b, d) for _, _, n, b, d in hist]))


if __name__ == "__main__":
    main()
