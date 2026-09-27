#!/usr/bin/env python3
"""Preflight: before any search, check for a newer toolkit, the API keys and the OpenAlex budget.

Run it FIRST, before writing a single lane brief. A build runs for hours, and two
of its services ration keyless use: OpenAlex (citation counts, abstracts, forward
citations, the hand-check DOI search, lab_corpus.py) and Semantic Scholar (xref,
the second citation count, abstracts). Finding that out halfway through a build
costs hours; finding it out here costs one request to each.

It checks:
  the toolkit        the version on GitHub (main) against this copy. The toolkit
                     changes often, so a newer version is offered with the
                     command that installs it (git pull for a clone, the plugin
                     menu otherwise). A build already under way keeps the version
                     it started with, so pass it --no-update-check.
  LITREVIEW_EMAIL    required by NCBI and CrossRef (or pass --email to every tool)
  OPENALEX_API_KEY   without it, every client on the same IP address shares ONE
                     free budget of 1,000 credits a day, and a campus network may
                     have spent it before you start; a free key has its own
                     10,000. A probe reads the budget left right now.
  S2_API_KEY         without it, Semantic Scholar throttles hard: xref and the S2
                     counts take hours and leave gaps.
It also estimates what a corpus of --papers N costs in OpenAlex credits.

Exit 0 when the build can run as planned. Exit 2 when the user must decide
first: a newer toolkit is available (offer to install it), LITREVIEW_EMAIL is not
set, a key is missing or rejected, or the budget is short. For a missing key or a
short budget, give the user the three choices it prints: get the keys, cap the
search, or be prepared to wait. Ask before any lane is launched.

    python3 tools/preflight.py --papers 600
    python3 tools/preflight.py --papers 600 --offline      # environment only: no probes, no GitHub check
"""
import argparse
import datetime
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

import common

PHASE = "0"   # pipeline phase, read by tools/gen_docs.py for the tool index

OPENALEX_PROBE = "https://api.openalex.org/works?filter=doi:10.1038/nature06713&select=id"
S2_PROBE = "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/nature06713?fields=title"
# realpath: projects reach tools/ through a symlink, and the manifest lives in the real checkout
ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
MANIFEST = os.path.join(".claude-plugin", "plugin.json")      # stamped with the version every commit
REMOTE_MANIFEST = ("https://raw.githubusercontent.com/gallantlab/literature-review-toolkit/main/"
                   ".claude-plugin/plugin.json")
OPENALEX_KEY_URL = "https://help.openalex.org/api/authentication"
S2_KEY_URL = "https://www.semanticscholar.org/product/api#api-key-form"

# OpenAlex credits, read off its X-RateLimit headers on 2026-09-27: a filter
# (batch) request costs 1, a title search 10, a single-work lookup 0. Keyless
# clients share 1000 a day per IP; a free key has its own 10000.
FILTER_COST = 1
SEARCH_COST = 10
DOILESS_SHARE = 0.03      # share of rows with no DOI (books, reports): one search each
FORWARD_LANDMARKS = 30    # forward.py --landmarks default: one filter request each
SAFETY = 2.0              # reruns, retries, recovery lanes, a second forward pass


def openalex_need(papers):
    """Credits a corpus of `papers` rows is expected to spend in OpenAlex, with
    SAFETY headroom: citations, abstracts and forward's id lookup each batch 50
    DOIs per filter request; forward pulls each landmark's citing works; handcheck
    runs one title search per DOI-less row."""
    batches = math.ceil(papers / 50)
    base = 3 * batches * FILTER_COST + FORWARD_LANDMARKS * FILTER_COST \
        + math.ceil(DOILESS_SHARE * papers) * SEARCH_COST
    return math.ceil(base * SAFETY)


def openalex_fits(credits):
    """Largest corpus whose expected need fits in `credits` (0 if none does)."""
    lo, hi = 0, 100000
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if openalex_need(mid) <= credits:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _get(url, headers, timeout=20):
    """(status, headers) for one GET; never raises on an HTTP status."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {})


def probe_openalex():
    """{"status", "remaining", "limit", "reset_s"} from one 1-credit request, or {"error"}."""
    try:
        status, h = _get(OPENALEX_PROBE, common._openalex_headers(OPENALEX_PROBE, dict(common.HDRS)))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    h = {k.lower(): v for k, v in h.items()}

    def num(k):
        try:
            return int(float(h[k]))
        except (KeyError, ValueError):
            return None
    return {"status": status, "remaining": num("x-ratelimit-remaining"),
            "limit": num("x-ratelimit-limit"), "reset_s": num("x-ratelimit-reset")}


def probe_s2():
    """{"status"} for one Semantic Scholar request (with S2_API_KEY if set), or {"error"}."""
    hdrs = dict(common.HDRS)
    key = os.environ.get("S2_API_KEY", "").strip()
    if key:
        hdrs["x-api-key"] = key
    try:
        return {"status": _get(S2_PROBE, hdrs)[0]}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _reset_text(seconds):
    if seconds is None:
        return "at midnight UTC"
    when = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
    return f"in {seconds / 3600:.1f} h (about {when:%H:%M} local time; it resets at midnight UTC)"


def parse_version(text):
    """(major, minor, patch) from '1.22.0', else None."""
    m = re.fullmatch(r"\s*v?(\d+)\.(\d+)\.(\d+)\s*", text or "")
    return tuple(int(x) for x in m.groups()) if m else None


def local_version(root=ROOT):
    try:
        with open(os.path.join(root, MANIFEST), encoding="utf-8") as f:
            return json.load(f).get("version")
    except (OSError, ValueError):
        return None


def remote_version(timeout=10):
    """The version stamped on GitHub's main branch, or None if it cannot be read."""
    try:
        req = urllib.request.Request(REMOTE_MANIFEST, headers=dict(common.HDRS))
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = common.decompress(r.read(), r.headers.get("Content-Encoding", ""))
        return json.loads(body).get("version")
    except Exception:
        return None


def install_kind(root=ROOT):
    """How this copy was installed, for the update command: 'git' with its state, else 'copy'."""
    if not os.path.isdir(os.path.join(root, ".git")):
        return {"kind": "copy"}

    def git(*a):
        p = subprocess.run(["git", "-C", root, *a], capture_output=True, text=True, timeout=20)
        return p.stdout.strip() if p.returncode == 0 else None
    return {"kind": "git", "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(git("status", "--porcelain"))}


def update_offer(local, remote, inst, root=ROOT):
    """Lines offering the newer version, or [] when this copy is current (or either
    version is unreadable). A local copy AHEAD of GitHub (unpushed work) is current."""
    lv, rv = parse_version(local), parse_version(remote)
    if not lv or not rv or rv <= lv:
        return []
    out = ["", f"A newer toolkit is available: {remote} on GitHub (this copy is {local}).",
           "Offer to install it before the search starts (a build already under way keeps its version):"]
    if inst.get("kind") == "git":
        out.append(f"    git -C {root} pull --ff-only")
        if inst.get("dirty"):
            out.append("    (this checkout has uncommitted changes: commit or stash them first, or the pull "
                       "may refuse)")
        if inst.get("branch") not in (None, "main"):
            out.append(f"    (this checkout is on branch {inst['branch']!r}, not main: switch first)")
    else:
        out.append("    update the plugin from Claude Code's /plugin menu, or download the new release from")
        out.append("    https://github.com/gallantlab/literature-review-toolkit")
    out.append("  Then rerun this preflight. See what changed: "
               "https://github.com/gallantlab/literature-review-toolkit/commits/main")
    return out


def assess(env, papers, oa=None, s2=None):
    """(ok, problems, lines): the report. env holds the three variables; oa and s2
    are probe results (None = not probed). Pure, so it is tested offline."""
    problems, lines = [], []
    email = (env.get("LITREVIEW_EMAIL") or "").strip()
    oa_key = bool((env.get("OPENALEX_API_KEY") or "").strip())
    s2_key = bool((env.get("S2_API_KEY") or "").strip())
    need = openalex_need(papers)

    lines.append(f"  LITREVIEW_EMAIL   {'set' if email else 'NOT SET'}")
    if not email:
        lines.append("                    NCBI/CrossRef require a contact email: export it, or pass "
                     "--email to every tool")
    lines.append(f"  OPENALEX_API_KEY  {'set' if oa_key else 'NOT SET'}")
    if not oa_key:
        problems.append("openalex-key")
    if oa is not None:
        if "error" in oa:
            lines.append(f"                    probe failed ({oa['error']}); budget unknown")
        elif oa["status"] == 401 or oa["status"] == 403:
            lines.append(f"                    OpenAlex rejected the key (HTTP {oa['status']}): check it")
            problems.append("openalex-key-rejected")
        else:
            rem, lim = oa.get("remaining"), oa.get("limit")
            who = "this key's own" if oa_key else "this IP address's SHARED keyless"
            left = f"{rem if rem is not None else '?'} of {lim if lim is not None else '?'}"
            lines.append(f"                    {who} daily budget: {left} credits left; "
                         f"resets {_reset_text(oa.get('reset_s'))}")
            lines.append(f"                    a {papers}-paper build needs about {need} credits "
                         f"(fits in what is left: up to ~{openalex_fits(rem or 0)} papers)")
            if oa["status"] == 429 or (rem is not None and rem < need):
                problems.append("openalex-budget")
    lines.append(f"  S2_API_KEY        {'set' if s2_key else 'NOT SET'}")
    if not s2_key:
        problems.append("s2-key")
    if s2 is not None:
        st = s2.get("status")
        if "error" in s2:
            lines.append(f"                    probe failed ({s2['error']})")
        elif st in (401, 403) and s2_key:
            lines.append(f"                    Semantic Scholar rejected the key (HTTP {st}): check it")
            problems.append("s2-key-rejected")
        elif st == 429:
            lines.append("                    throttled right now (HTTP 429)")
    return (not problems and bool(email)), problems, lines


def choices(problems, papers, oa):
    """The three options to put to the user, specific to what is missing."""
    rem = (oa or {}).get("remaining")
    fits = openalex_fits(rem) if rem is not None else None
    out = ["", "Before any search: this build is short of API access. Ask the user to choose:", ""]
    keys = []
    if "openalex-key" in problems or "openalex-key-rejected" in problems:
        keys.append(f"OpenAlex (free): {OPENALEX_KEY_URL}  ->  export OPENALEX_API_KEY=...")
    if "s2-key" in problems or "s2-key-rejected" in problems:
        keys.append(f"Semantic Scholar (free, approved by email): {S2_KEY_URL}  ->  export S2_API_KEY=...")
    out.append("  (1) Get the API keys. Each is free and has its own budget, not shared with the network:")
    out += [f"        {k}" for k in keys] or ["        (keys are set; the budget, not a key, is short)"]
    out.append("      Add the export lines to your shell profile, open a new shell, and rerun this check.")
    if fits == 0:
        full = openalex_fits((oa or {}).get("limit") or 1000)
        out.append(f"  (2) Cap the search: fewer lanes and a hard per-lane cap. Today's budget is already "
                   f"spent, so a cap helps only after the reset; a full day's budget then covers ~{full} "
                   "papers, less if others on the network use it too.")
    else:
        cap = f"~{fits}" if fits else "a few hundred"
        out.append(f"  (2) Cap the search: fewer lanes and a hard per-lane cap, so the whole build stays "
                   f"within {cap} papers.")
    out.append("      Tell the lanes the search is CAPPED (search_prompt_template.md): an on-topic paper "
               "over the cap goes in `excluded`, so it is listed, not lost.")
    if "s2-key" in problems:
        out.append("      Without S2_API_KEY, also expect xref to leave gaps; run it with --allow-incomplete "
                   "and say so in the hand-off.")
    out.append("  (3) Be prepared to wait. Nothing is skipped, but it takes longer:")
    if "openalex-key" in problems or "openalex-budget" in problems:
        out.append(f"        OpenAlex steps stop with OpenAlexBudgetError when the budget runs out; rerun "
                   f"them after the budget resets {_reset_text((oa or {}).get('reset_s'))}. A large build "
                   "can need more than one day.")
    if "s2-key" in problems:
        out.append("        Semantic Scholar steps (xref, citations' S2 column, abstracts) back off on every "
                   "429; on a large corpus that can take hours.")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--papers", type=int, default=500,
                    help="planned corpus size (lanes x target, plus lab papers); default 500")
    ap.add_argument("--offline", action="store_true", help="check the environment only; no probes")
    ap.add_argument("--email", help="contact email (else LITREVIEW_EMAIL)")
    ap.add_argument("--no-update-check", action="store_true",
                    help="skip the GitHub version check (a build already under way)")
    args = ap.parse_args()
    env = {k: os.environ.get(k, "") for k in ("LITREVIEW_EMAIL", "OPENALEX_API_KEY", "S2_API_KEY")}
    if args.email:
        env["LITREVIEW_EMAIL"] = args.email
    if env["LITREVIEW_EMAIL"]:
        common.set_user_agent(env["LITREVIEW_EMAIL"])
    oa = s2 = None
    if not args.offline:
        oa, s2 = probe_openalex(), probe_s2()
    ok, problems, lines = assess(env, args.papers, oa, s2)
    local = local_version()
    print(f"preflight for a ~{args.papers}-paper build (toolkit {local or '?'}):")
    offer = []
    if not (args.offline or args.no_update_check):
        remote = remote_version()
        if remote is None:
            print("  toolkit           could not read the version on GitHub; check by hand if it matters")
        else:
            offer = update_offer(local, remote, install_kind())
            print(f"  toolkit           {local or '?'} here, {remote} on GitHub"
                  + ("  -> NEWER VERSION AVAILABLE" if offer else "  (current)"))
    print("\n".join(lines))
    if offer:
        print("\n".join(offer))
    if problems:
        print("\n".join(choices(problems, args.papers, oa)))
    if not env["LITREVIEW_EMAIL"]:
        print("\nStop: set a contact email first (NCBI and CrossRef require one):\n"
              "    export LITREVIEW_EMAIL=you@institution.edu      (or pass --email to every tool)\n"
              "then rerun this preflight.")
    if ok and not offer:
        print("\nOK: toolkit current, keys set, and the OpenAlex budget covers the build.")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
