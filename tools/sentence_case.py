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
import os
import re

import common

PHASE = "3f"   # pipeline phase, read by tools/gen_docs.py for the tool index

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
} | set(common.GENERA)   # model-organism genera are proper nouns in any corpus

SEPS = r"[-–—/]"
# punctuation that can wrap a token without being part of the word
WRAP = "()[]{}'’\"“”,;:.!?"


def protect_part(p, words):
    core = p.strip(WRAP)
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
    if tok.strip(WRAP) in words:
        return tok
    parts = re.split(f"({SEPS})", tok)
    compound = len([p for p in parts if p and not re.fullmatch(SEPS, p)]) > 1
    out, seen_alpha = [], False
    for p in parts:
        if not p or re.fullmatch(SEPS, p):
            out.append(p)
            continue
        core = p.strip(WRAP)
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


# Foreign-language titles must not be sentence-cased: the pass lowercases German
# nouns ("Der Kumpan in der Umwelt des Vogels" -> "der kumpan in der umwelt ...").
# 'von' and 'de' are NOT markers - they occur inside personal names in English
# titles (Karl von Frisch, fin-de-siecle) - and neither is 'man', which is the
# English word in "animals and man". Learned on a corpus with 16 German/French
# titles among 493.
FOREIGN = re.compile(
    r"\b(der|die|das|und|über|ueber|zur|zum|den|des|dem|ein|eine|einen|im|bei|mit|auf|aus|"
    r"nach|zwischen|namentlich|durch|wenn|ihm|einzelnen|la|le|les|du|et|sur)\b", re.I)


def is_foreign_title(title):
    """True when a title looks German/French and must be left exactly as published."""
    return bool(FOREIGN.search(title or ""))


# A run of ALL-CAPS words is a shouted title, not an acronym. references.norm_title
# only fixes a title that is ENTIRELY caps, and case_token protects all-caps tokens
# as possible acronyms, so a MIXED title ("BEHAVIORAL MUTANTS OF Drosophila ISOLATED
# BY COUNTERCURRENT DISTRIBUTION") slipped through both.
CAPS_RUN_MIN = 3


def _lower_caps_runs(title, words):
    toks = title.split(" ")
    def is_shout(t):
        c = t.strip(WRAP)
        return len(c) >= 2 and c.isalpha() and c.isupper() and c not in words
    i, n = 0, len(toks)
    while i < n:
        j = i
        while j < n and is_shout(toks[j]):
            j += 1
        if j - i >= CAPS_RUN_MIN:
            for k in range(i, j):
                toks[k] = toks[k].lower()
        i = j + 1 if j == i else j
    return " ".join(toks)


def sentence_case(title, words, phrases):
    title = _lower_caps_runs(title, words)
    toks = title.split(" ")
    protected = set()
    low = [t.strip(WRAP).lower() for t in toks]
    for phrase in phrases:
        pt = phrase.lower().split(" ")
        for i in range(len(low) - len(pt) + 1):
            if low[i:i + len(pt)] == pt:
                for j, want in enumerate(pt):
                    protected.add(i + j)
                    bare = toks[i + j].strip(WRAP)
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
    """-> (head_through_year, title_with_terminal_punct, rest) or None.
    Thin wrapper over the shared APA grammar; None when there is no year or the
    title never terminates (nothing after it to protect the split)."""
    p = common.parse_apa(apa)
    if not p or not p["terminal"] or not p["rest"]:
        return None
    return p["head"], p["title"] + p["terminal"], p["rest"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", help="write here (default: in place, with --apply)")
    ap.add_argument("--proper", help='JSON {"words": [...], "phrases": [...]}')
    ap.add_argument("--apply", action="store_true", help="write the changes")
    ap.add_argument("--vocab", action="store_true",
                    help="report distinct token changes instead of full titles")
    ap.add_argument("--include-foreign", action="store_true",
                    help="also case non-English titles (default: leave them exactly as "
                         "published — the pass lowercases German nouns)")
    args = ap.parse_args()

    words, phrases = set(PROPER), []
    if args.proper:
        extra = common.load_json(args.proper)
        words |= set(extra.get("words", []))
        phrases += list(extra.get("phrases", []))

    rows = common.load_json(args.rows)
    loaded = os.path.getmtime(args.rows)         # --apply refuses a file changed since
    keyf = common.key_field(rows)
    changes, vocab, unparsed, foreign = [], {}, [], []
    for r in rows:
        parts = split_apa(r.get("apa", ""))
        if not parts:
            unparsed.append(r.get(keyf, "?"))
            continue
        head, title, rest = parts
        if not args.include_foreign and is_foreign_title(title):
            # German and French titles are correct as published; casing them
            # lowercases every noun. Report them so the skip is visible.
            foreign.append(r.get(keyf, "?"))
            continue
        new = sentence_case(title[:-1], words, phrases) + title[-1]
        if new != title:
            changes.append((r.get(keyf, "?"), title, new))
            for a, b in zip(title[:-1].split(" "), new[:-1].split(" ")):
                if a != b:
                    vocab[f"{a} -> {b}"] = vocab.get(f"{a} -> {b}", 0) + 1
            if args.apply:
                r["apa"] = head + new + rest

    if foreign:
        print(f"skipped {len(foreign)} non-English title(s), left exactly as published: "
              f"{', '.join(map(str, foreign[:12]))}"
              f"{' ...' if len(foreign) > 12 else ''}\n"
              f"  (pass --include-foreign to case them anyway)")
    if args.apply:
        out = args.out or args.rows
        same = os.path.abspath(out) == os.path.abspath(args.rows)
        common.save_rows(out, rows, loaded if same else None)
        print(f"applied {len(changes)} title changes to {out}")
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
