#!/usr/bin/env python3
"""Post-canon pass — propose strict APA-7 sentence case for reference titles.

The DOI is ground truth for a paper's *location*; the `apa` string is display,
and APA-7 wants sentence case. CrossRef and arXiv return titles in inconsistent
casing (arXiv and many publishers use Title Case, Nature deposits sentence case),
so references.py normalizes ALL-CAPS titles but deliberately does NOT transform
Title Case into sentence case: doing that correctly needs the proper-noun
judgment APA bakes in, and a mechanical caser mis-cases proper nouns silently —
which the audit gate cannot catch.

So this tool PROPOSES and a human REVIEWS. Run it, read the diff, extend the
allowlist for the corpus's own proper nouns, then apply.

  python3 tools/sentence_case.py --rows rows.json                    # print the diff
  python3 tools/sentence_case.py --rows rows.json --vocab            # review by token
  python3 tools/sentence_case.py --rows rows.json --proper mine.json # project allowlist
  python3 tools/sentence_case.py --rows rows.json --apply

`--vocab` is the fast way to review a large corpus: instead of reading 150 title
diffs, read the ~400 distinct token changes they amount to. A mis-cased proper
noun shows up there immediately.

Protected automatically, with no allowlist needed:
  - ALL-CAPS acronyms (EEG, DMN, MBSR, LORETA)
  - any token containing a digit (7T, COVID-19, 5-MeO-DMT)
  - camelCase and internal capitals (fMRI, pRF, LEiDA)
  - a lone capital letter inside a compound (ACAM-J, S-ART, 7-T)
  - each hyphen/slash/dash part judged separately, so 'Resting-State' is not
    mistaken for camelCase
  - the first word of the title and of any subtitle after a colon

The allowlist below holds only nouns that are proper in ANY corpus. Domain proper
nouns (a practice, a cohort, a trial, an instrument, a language) belong in a
per-project `--proper` file: {"words": [...], "phrases": [...]}. Phrases are
matched case-insensitively and restored to the capitalization written there,
which is what lets a generic word lowercase while a named entity containing it
does not.
"""
import argparse
import json
import re

import common

# Proper in any corpus: eponyms, peoples/places, calendar terms.
PROPER = {
    "Bayesian", "Markov", "Gaussian", "Fourier", "Laplacian", "Hilbert",
    "Granger", "Hebbian", "Bonferroni", "Poisson", "Boltzmann", "Euclidean",
    "Riemannian", "Kolmogorov", "Shannon", "Lempel-Ziv", "Monte", "Carlo",
    "Alzheimer", "Alzheimer's", "Parkinson", "Parkinson's", "Huntington",
    "Huntington's", "Broca", "Wernicke", "Brodmann",
    "English", "German", "French", "Japanese", "Chinese", "Indian", "American",
    "European", "African", "Western", "Eastern", "Latin", "Greek",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "June", "July", "August",
    "September", "October", "November", "December",
}

SEPS = r"[-–—/]"


def protect_part(p, words):
    core = p.strip("()[]{}'’\"“”,;:.!?")
    if not core:
        return True
    if any(c.isdigit() for c in core):          # 7T, COVID-19, 5-MeO
        return True
    if core.isupper() and len(core) >= 2:       # EEG, DMN, MBSR
        return True
    if core[1:] != core[1:].lower():            # camelCase: fMRI, LEiDA, pRF
        return True
    return core in words


def case_token(tok, clause_initial, words):
    # Check the WHOLE token against the allowlist before splitting it: a hyphenated
    # entry ('Age-Well', 'Lempel-Ziv', 'Medit-Ageing') has parts that are not
    # themselves allowlisted, so a parts-only check silently lowercases it.
    if tok.strip("()[]{}'’\"“”,;:.!?") in words:
        return tok
    parts = re.split(f"({SEPS})", tok)
    compound = len([p for p in parts if p and not re.fullmatch(SEPS, p)]) > 1
    out, seen_alpha = [], False
    for p in parts:
        if not p or re.fullmatch(SEPS, p):
            out.append(p)
            continue
        core = p.strip("()[]{}'’\"“”,;:.!?")
        # a lone capital inside a compound is an acronym part (ACAM-J), not a word
        if protect_part(p, words) or (compound and len(core) == 1 and core.isupper()):
            out.append(p)
            seen_alpha = True
            continue
        lead = re.match(r"^\W*", p).group(0)
        body = p[len(lead):]
        body = body[:1].lower() + body[1:]
        if clause_initial and not seen_alpha:
            body = body[:1].upper() + body[1:]
        out.append(lead + body)
        seen_alpha = True
    return "".join(out)


def sentence_case(title, words, phrases):
    toks = title.split(" ")
    protected = set()
    low = [t.strip("()[]{}'’\"“”,;:.!?").lower() for t in toks]
    for phrase in phrases:
        pt = phrase.lower().split(" ")
        for i in range(len(low) - len(pt) + 1):
            if low[i:i + len(pt)] == pt:
                for j, want in enumerate(pt):
                    protected.add(i + j)
                    bare = toks[i + j].strip("()[]{}'’\"“”,;:.!?")
                    if bare:
                        toks[i + j] = toks[i + j].replace(bare, phrase.split(" ")[j])
    out = []
    for i, tok in enumerate(toks):
        if i in protected:
            out.append(tok)
            continue
        prev = toks[i - 1] if i else ""
        out.append(case_token(tok, (i == 0) or prev.endswith((":", "?", "!", ".", ";")), words))
    return " ".join(out)


def split_apa(apa):
    """-> (head_through_year, title_with_terminal_punct, rest) or None."""
    m = re.search(r"\(\d{4}[a-z]?\)\.\s+", apa or "")
    if not m:
        return None
    head, tail = apa[:m.end()], apa[m.end():]
    m2 = re.search(r"[.?!]\s", tail)
    if not m2:
        return None
    return head, tail[:m2.start() + 1], tail[m2.start() + 1:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", help="write here (default: in place, with --apply)")
    ap.add_argument("--proper", help='JSON {"words": [...], "phrases": [...]}')
    ap.add_argument("--apply", action="store_true", help="write the changes")
    ap.add_argument("--vocab", action="store_true",
                    help="report distinct token changes instead of full titles")
    args = ap.parse_args()

    words, phrases = set(PROPER), []
    if args.proper:
        extra = common.load_json(args.proper)
        words |= set(extra.get("words", []))
        phrases += list(extra.get("phrases", []))

    rows = common.load_json(args.rows)
    changes, vocab, unparsed = [], {}, []
    for r in rows:
        parts = split_apa(r.get("apa", ""))
        if not parts:
            unparsed.append(r.get("ref") or r.get("label", "?"))
            continue
        head, title, rest = parts
        new = sentence_case(title[:-1], words, phrases) + title[-1]
        if new != title:
            changes.append((r.get("ref") or r.get("label", "?"), title, new))
            for a, b in zip(title[:-1].split(" "), new[:-1].split(" ")):
                if a != b:
                    vocab[f"{a} -> {b}"] = vocab.get(f"{a} -> {b}", 0) + 1
            if args.apply:
                r["apa"] = head + new + rest

    if args.apply:
        common.dump_json(rows, args.out or args.rows)
        print(f"applied {len(changes)} title changes to {args.out or args.rows}")
    elif args.vocab:
        for k, v in sorted(vocab.items(), key=lambda x: -x[1]):
            print(f"{v:4d}  {k}")
        print(f"\n{len(vocab)} distinct token changes across {len(changes)} titles. "
              f"Scan for proper nouns that should NOT be lowercased, add them to "
              f"--proper, then re-run.")
    else:
        for ref, old, new in changes:
            print(f"{ref}\n  - {old}\n  + {new}")
        print(f"\n{len(changes)} of {len(rows)} titles would change. "
              f"Review with --vocab, then --apply.")
    if unparsed:
        print(f"  [unparsed, left alone] {len(unparsed)}: {unparsed[:12]}")


if __name__ == "__main__":
    main()
