#!/usr/bin/env python3
"""Screenshot a built page in light, dark and phone widths, so a human can look at it.

A page that builds is not a page that reads: a passing build says nothing about raw
shortcodes, unreadable dark-mode colors or a layout that breaks at phone width. The
only way to know is to look, so this renders the page and writes the images.

    python3 tools/screenshot.py --page <topic>_review.html

It drives a headless browser, and no headless browser runs inside Claude Code's
sandbox. The sandbox denies the mach bootstrap every modern browser needs to spawn
its child processes, so Chrome and Firefox both abort at startup with the identical
`bootstrap_check_in ... Error:1100`, whatever flags they are given. Firefox was
tested on 2026-11-05 specifically to see whether it escaped the problem; it does not,
and neither would Playwright or Puppeteer, which drive those same browsers. Rendering
therefore needs a sandbox exemption, which is why this is one narrow script with one
stable command line rather than an ad-hoc browser invocation each time:

    "sandbox": {"excludedCommands": ["Bash(python3 /abs/path/to/tools/screenshot.py *)"]}

**It refuses any page or output directory outside --root (the working directory by
default), and refuses a --root outside the workspace that holds this toolkit.** Both
bounds matter. --root alone is an ordinary argument, and the exemption pattern ends
in `*`, so a caller could once pass `--root /` and photograph anything on the disk
with the sandbox off; the ceiling is what makes the bound real rather than advisory.
Chrome is likewise located from a fixed list, not from an argument, so the exemption
cannot be turned into "run this binary outside the sandbox". Symbolic links are
resolved before both checks, so a link inside the tree pointing out of it is refused.

Each capture is the top of the page at the mode's window size, not the whole page:
Chrome's --screenshot photographs the viewport. The run says how tall each capture
was, because a reviewer who is told "wrote 3 images" and sees only the first screenful
believes a long page was checked when it was not.

Exits 1 when Chrome is missing, when a path escapes the root or the root escapes the
workspace, or when a mode produces no image, so a silent failure cannot pass for a
clean render.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

PHASE = "7"

# width, height, extra Chrome flags
MODES = {
    "light": (1280, 1600, []),
    "dark": (1280, 1600, ["--blink-settings=preferredColorScheme=0"]),
    "phone": (500, 1400, []),
}

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


# The workspace that contains this toolkit: tools/ -> repo -> workspace. No --root
# above this is accepted, so the sandbox exemption cannot reach the rest of the disk.
WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_chrome():
    """The Chrome binary, or None, from the fixed list above and the PATH.

    Deliberately takes no argument and reads no environment variable. An
    exemption that runs this script outside the sandbox would otherwise be an
    exemption to run any binary outside the sandbox. Add a path to CHROME_PATHS
    to support another install location."""
    for cand in CHROME_PATHS:
        if os.path.exists(cand):
            return cand
    return shutil.which("google-chrome") or shutil.which("chromium")


def inside(path, root):
    """True when `path` is `root` or sits under it, with links resolved first.

    os.path.realpath is what stops a symlink planted inside the tree from pointing
    the exemption at somewhere else on disk."""
    path = os.path.realpath(path)
    root = os.path.realpath(root)
    return path == root or path.startswith(root + os.sep)


def shoot(chrome, page, out_dir, modes, stem, quiet=False):
    """Render `page` once per mode. Returns the files written; raises on a mode
    that produced nothing, so a failed render is never mistaken for a clean one."""
    written = []
    for mode in modes:
        width, height, extra = MODES[mode]
        out = os.path.join(out_dir, f"{stem}_{mode}.png")
        if os.path.exists(out):
            os.remove(out)
        # Chrome needs a writable profile; a fresh one per run keeps concurrent
        # renders from fighting over the same ProcessSingleton socket.
        with tempfile.TemporaryDirectory(prefix="shot-") as profile:
            cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox",
                   "--hide-scrollbars", "--no-first-run", "--disable-breakpad",
                   f"--user-data-dir={profile}", f"--window-size={width},{height}",
                   "--virtual-time-budget=6000", f"--screenshot={out}",
                   "file://" + os.path.abspath(page)] + extra
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if not os.path.exists(out):
            # Chrome's own stderr says whether this is the sandbox (mach port and
            # socket denials) or something about the page. Guessing wasted a round.
            why = "\n".join(ln for ln in (r.stderr or "").splitlines()
                            if "ERROR" in ln or "FATAL" in ln)[:600]
            raise RuntimeError(f"{mode}: chrome wrote no image to {out}\n{why}")
        written.append(out)
        if not quiet:
            print(f"  {mode:<6} {width}x{height}  {os.path.getsize(out) // 1024:>5} KB  {out}")
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--page", required=True, help="the .html file to photograph")
    ap.add_argument("--out", help="directory for the images (default: beside the page)")
    ap.add_argument("--root", default=os.getcwd(),
                    help="the tree the page and images must stay inside "
                         "(default: the working directory)")
    ap.add_argument("--modes", default="light,dark,phone",
                    help="comma-separated: " + ", ".join(MODES))
    ap.add_argument("--quiet", action="store_true", help="print only the failures")
    args = ap.parse_args()

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    unknown = [m for m in modes if m not in MODES]
    if unknown:
        sys.exit(f"unknown mode(s): {', '.join(unknown)} (known: {', '.join(MODES)})")

    page = os.path.abspath(args.page)
    if not os.path.exists(page):
        sys.exit(f"no such page: {page}")
    out_dir = os.path.abspath(args.out or os.path.dirname(page))

    # The exemption is bounded here, not by the caller: the root may be narrowed
    # but never widened past the workspace that holds this toolkit.
    if not inside(args.root, WORKSPACE):
        sys.exit(f"refusing: --root {os.path.realpath(args.root)} is outside {WORKSPACE}")
    for label, path in (("--page", page), ("--out", out_dir)):
        if not inside(path, args.root):
            sys.exit(f"refusing: {label} {path} is outside {os.path.realpath(args.root)}")

    chrome = find_chrome()
    if not chrome:
        sys.exit("no Chrome found; set CHROME_PATH or pass --chrome")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(page))[0]
    try:
        written = shoot(chrome, page, out_dir, modes, stem, quiet=args.quiet)
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        sys.exit(f"screenshot failed: {e}")
    if not args.quiet:
        print(f"wrote {len(written)} image(s): the TOP of the page at each size, not the whole "
              "page. Scroll-depth problems do not appear here; read them, then check the rest "
              "of the page another way before calling it done.")


if __name__ == "__main__":
    main()
