#!/usr/bin/env python3
"""Phase 7 — measure a review's prose and prove a revision pass lost no citation.

A model-written review is rarely wrong and often unreadable. The recurring defect
is not fancy words, it is compression: four or five findings chained through
semicolons into one 60-120 word sentence, each with its own citation. The prose
is accurate, and nobody can follow it. That is invisible to `cite_check.py`,
which asks only whether the citations resolve.

  python3 tools/prose_audit.py --page build_review_page.py
  python3 tools/prose_audit.py --content content.json

It reports, per prose block: words, sentence count, mean sentence length, and the
sentences long enough to be unreadable. Then it reports pairs of blocks that share
many citations, which is how the same argument gets told twice in two sections.

Rewriting for concision silently drops citations, so this is also the gate on that
pass. Keep a copy of the source before revising and compare against it:

  cp build_review_page.py /tmp/before.py      # then revise
  python3 tools/prose_audit.py --page build_review_page.py --baseline /tmp/before.py

Exit 1 if any citation present in the baseline is missing afterwards (a reference
silently cut from the works cited). Long sentences are reported, never gated — how
short a sentence should be is editorial, and a list-like sentence with parallel
clauses can legitimately run long.
"""
import argparse
import ast
import os
import re
import sys
from html import unescape

import common

PHASE = "7"   # pipeline phase, read by tools/gen_docs.py for the tool index

# Targets, from the 2026-09-22 pass over a 555-reference review: mean sentence
# length fell 31 -> 24 words and sentences of 50+ words fell 54 -> 8, which is
# what turned "wordy and hard to follow" into readable. They are guidance for
# the report, not thresholds anything fails on.
GOOD_MEAN = 25
LONG_SENTENCE = 45

# Tokens that end in a period without ending a sentence. "et al." is the one that
# matters — a naive split cuts almost every citation-bearing sentence in half.
ABBREV = {"al", "e.g", "i.e", "cf", "vs", "etc", "Fig", "Figs", "Eq", "Ref", "No",
          "Nos", "pp", "approx", "ca", "Dr", "Prof", "St", "Jr", "Sr", "Inc"}

CITE_MARKER = re.compile(r"\[\[([A-Za-z0-9|_-]+)\]\]")
SLUG = re.compile(r"[a-z][a-z0-9-]{2,}$")
# A page template, not prose: the HTML shell, its CSS, its placeholders.
TEMPLATE = re.compile(r"(?i)<!doctype|<style|</html>|\{\{\w+\}\}")


def detag(html, drop_tables=True):
    """HTML prose -> plain text.

    Tables are dropped by default. A flattened table reads as one enormous
    "sentence" (a real one measured 153 words) and swamps the statistics it
    would otherwise be reported in.
    """
    if drop_tables:
        html = re.sub(r"(?is)<table.*?</table>", " ", html)
    html = CITE_MARKER.sub("", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(html)).strip()


def _ends_abbrev(s):
    """True if s ends in an abbreviation rather than a full stop.

    Only the word list counts. A decimal ('0.1 mm') never has a space after its
    period, so the split cannot break one and it needs no guard — while a guard
    on trailing digits would swallow the very common real sentence end
    '...are in layers 4C and 6. CSD in alert monkeys...'.
    """
    m = re.search(r"(\S+)\.$", s)
    # Leading bracket/quote stripped too: '(e.g.' is the same abbreviation as 'e.g.'
    return bool(m) and m.group(1).lstrip("([{“\"'").rstrip(".") in ABBREV


def sentences(text):
    """Split on sentence punctuation, without splitting at 'et al.' or initials."""
    out = []
    for part in re.split(r"(?<=[.!?])\s+", text):
        if out and _ends_abbrev(out[-1]):
            out[-1] += " " + part
        else:
            out.append(part)
    return [p for p in out if p.strip()]


# --------------------------------------------------------------------------
# Reading the two shapes a review comes in
# --------------------------------------------------------------------------

def _is_prose(s):
    return len(s) >= 150 and bool(re.search(r"[.!?][\s\"']", s)) and not TEMPLATE.search(s)


def _collect(label, node, out):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if _is_prose(node.value):
            key, n = label, 2
            while key in out:                      # two prose strings in one tuple
                key, n = f"{label}~{n}", n + 1
            out[key] = node.value
    elif isinstance(node, (ast.List, ast.Tuple)):
        for i, el in enumerate(node.elts):
            sub = f"{label}[{i}]"
            if isinstance(el, (ast.List, ast.Tuple)):
                # ("Section title", "sec-slug", "<p>prose</p>") -> name it by the
                # slug, and let the prose inside take that name directly rather
                # than an index nobody can map back to a section.
                consts = [e.value for e in el.elts
                          if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                slug = next((c for c in consts if len(c) < 60 and SLUG.fullmatch(c)), None)
                sub = f"{label}:{slug}" if slug else sub
                for e in el.elts:
                    _collect(sub, e, out)
                continue
            _collect(sub, el, out)


def page_blocks(path):
    """Prose blocks from a project's build_review_page.py, by static parse.

    The module is never imported: a shared tool should not execute a project
    script to read its text.
    """
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    _collect(target.id, node.value, out)
                    break
    return out


def content_blocks(path):
    """Prose blocks from a content.json (the .docx route)."""
    doc = common.load_json(path)
    out = {}
    if doc.get("abstract"):
        out["abstract"] = doc["abstract"]
    for i, sec in enumerate(doc.get("sections", [])):
        label = sec.get("heading") or f"sections[{i}]"
        text = "\n\n".join(sec.get("paragraphs", []))
        if text.strip():
            out[label[:48]] = text
    return out


def cites_in(block, apa_mode):
    """Citation tokens in one block: [[REF]] markers, or APA author-date."""
    if apa_mode:
        import cite_check
        return set(cite_check.citations_in(block))
    found = set()
    for grp in CITE_MARKER.findall(block):
        found.update(grp.split("|"))
    return found


def read(path, apa_mode):
    blocks = content_blocks(path) if apa_mode else page_blocks(path)
    return {k: (v, cites_in(v, apa_mode)) for k, v in blocks.items()}


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--page", help="project build_review_page.py (prose + [[REF]] markers)")
    src.add_argument("--content", help="content.json for the .docx route (APA author-date)")
    ap.add_argument("--baseline", help="pre-revision copy of the same file; "
                                       "exit 1 if a citation was lost against it")
    ap.add_argument("--long", type=int, default=LONG_SENTENCE,
                    help=f"report sentences at least this many words (default {LONG_SENTENCE})")
    ap.add_argument("--overlap", type=int, default=8,
                    help="report block pairs sharing at least this many citations (default 8)")
    ap.add_argument("--exclude", help="regex: skip blocks whose label matches")
    ap.add_argument("--quiet", action="store_true", help="totals and failures only")
    args = ap.parse_args()

    path = args.content or args.page
    apa = bool(args.content)
    if not os.path.exists(path):
        sys.exit(f"no such file: {path}")
    blocks = read(path, apa)
    if args.exclude:
        skip = re.compile(args.exclude)
        blocks = {k: v for k, v in blocks.items() if not skip.search(k)}
    if not blocks:
        sys.exit(f"no prose blocks found in {path}")

    rows, all_lens, total_words, long_ones = [], [], 0, []
    for label, (raw, refs) in blocks.items():
        text = detag(raw) if not apa else re.sub(r"\s+", " ", raw).strip()
        sents = sentences(text)
        lens = [len(s.split()) for s in sents] or [0]
        total_words += sum(lens)
        all_lens += lens
        rows.append((label, sum(lens), len(sents), sum(lens) / len(lens), max(lens), len(refs)))
        for s in sents:
            if len(s.split()) >= args.long:
                long_ones.append((len(s.split()), label, s))

    mean = sum(all_lens) / len(all_lens)
    if not args.quiet:
        print(f"{'block':44}{'words':>7}{'sent':>6}{'mean':>7}{'max':>6}{'cites':>7}")
        for label, w, n, m, mx, nr in sorted(rows, key=lambda r: -r[1]):
            flag = "  <-" if m > GOOD_MEAN else ""
            print(f"{label[:44]:44}{w:7}{n:6}{m:7.1f}{mx:6}{nr:7}{flag}")
        print()

    over = sum(1 for x in all_lens if x >= args.long)
    print(f"{len(blocks)} blocks · {total_words} words · mean sentence {mean:.1f} words "
          f"(target <= {GOOD_MEAN}) · {over} sentences >= {args.long} words")

    if long_ones and not args.quiet:
        print(f"\nLongest sentences — break these first ({len(long_ones)} at or over {args.long} words):")
        for n, label, s in sorted(long_ones, reverse=True)[:12]:
            print(f"  [{n:3}w] {label}")
            print(f"        {s[:160]}{'...' if len(s) > 160 else ''}")

    # The same argument told twice: two sections resting on the same references.
    pairs = []
    labels = list(blocks)
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            shared = blocks[a][1] & blocks[b][1]
            if len(shared) >= args.overlap:
                pairs.append((len(shared), a, b))
    if pairs and not args.quiet:
        print(f"\nBlock pairs sharing {args.overlap}+ citations — check for a duplicated argument:")
        for n, a, b in sorted(pairs, reverse=True)[:8]:
            print(f"  {n:3} shared   {a}  <->  {b}")

    status = 0
    if args.baseline:
        if not os.path.exists(args.baseline):
            sys.exit(f"no such baseline: {args.baseline}")
        before = read(args.baseline, apa)
        was = set().union(*[r for _, r in before.values()]) if before else set()
        now = set().union(*[r for _, r in blocks.values()]) if blocks else set()
        lost, gained = sorted(was - now), sorted(now - was)
        bw = sum(len(detag(r).split()) if not apa else len(r.split()) for r, _ in before.values())
        print(f"\nvs baseline: {bw} -> {total_words} words ({(total_words - bw) / bw * 100:+.1f}%)"
              f" · {len(was)} -> {len(now)} distinct citations")
        if gained:
            print(f"  NEW citations ({len(gained)}): {' '.join(gained[:20])}")
        if lost:
            print(f"  LOST citations ({len(lost)}): {' '.join(lost[:20])}")
            print("  A revision pass must not drop a reference. Restore them, or "
                  "confirm each is cited elsewhere.")
            status = 1
        else:
            print("  no citation lost")
    sys.exit(status)


if __name__ == "__main__":
    main()
