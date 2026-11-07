#!/usr/bin/env python3
"""Gate: an origin claim cites its sources oldest-first (contract rule 5).

The most common failure of a model-written review is crediting whichever paper
fits the sentence rather than the one that established the idea. The rule has
two halves, and only one of them is mechanical.

  python3 tools/priority_check.py --rows rows.json --content content.json
  python3 tools/priority_check.py --rows rows.json --page build_review_page.py

**The gate (mechanical).** A sentence that makes an origin claim — it says a
finding *emerged*, was *first* shown, *established*, *identified*, *introduced*,
*discovered* — and cites several papers in one group must cite them oldest
first. A group is one parenthesis, `(Desimone et al., 1984; Tanaka, 1996)`, or
one `[[REF|REF]]` marker on the page route. Years come from each row's canonical
`apa`, so a reordering that the prose claims and the corpus denies cannot pass.
Exit 1 on any inversion.

Only within-group order is gated. Two separate citations in one sentence often
belong to two different claims ("X showed A (Smith, 2000) while Y showed B
(Jones, 1990)"), and gating those would fail correct prose.

**The worklist (judgment).** Order is the symptom; the real failure is citing a
1996 review for a 1984 primary finding when both are in the corpus. For every
origin claim the tool lists corpus rows published BEFORE the earliest paper the
sentence cites whose titles overlap the sentence, scored by `common.title_score`
at `--relevance` or better. That is a worklist for a reader, not a verdict: a
listed row may be off-topic, and an absent one may still deserve priority. Work
it before delivering, and keep the independent priority audit (PLAYBOOK Phase 7)
for what no word overlap can see — a later model credited for an earlier
empirical result, a narrower paper preferred over a more general one of the
same year, the lab's own foundational work relegated in lab mode.

Run it beside `cite_check.py`, before the review renders. It reads the review
only; it never writes.
"""
import argparse
import re
import sys
from html import unescape

import cite_check
import common
import prose_audit

PHASE = "7"   # pipeline phase, read by tools/gen_docs.py for the tool index

# The vocabulary of an origin claim. PLAYBOOK Phase 7 points here rather than
# repeating the list: this registry is the only copy, so prose and gate cannot
# drift. Each pattern is matched case-insensitively on word boundaries.
TRIGGERS = (
    r"emerg(?:e|es|ed|ing|ence)",
    r"first (?:show|shown|showed|report|reported|describ\w+|demonstrat\w+|propos\w+|"
    r"identif\w+|observ\w+|measur\w+|us\w+|appl\w+)",
    r"the first\b",
    r"establish(?:ed|es|ing)",
    r"identif(?:ied|ies)",
    r"introduc(?:ed|es|ing)",
    r"origin(?:ated|ate|s)?\b",
    r"discover(?:ed|y|ies)",
    r"was (?:mapped|described|coined|named|developed)",
    r"were (?:mapped|described|coined|named|developed)",
    r"had been\b",
    r"early work",
    r"earliest\b",
    r"foundational",
    r"seminal",
    r"pioneer(?:ed|ing)",
    r"began\b",
    r"dates? back",
    r"gave rise to",
    r"gives? rise to",
    r"led to the\b",
    r"laid the (?:ground|found)\w*",
    r"since\s+\d{4}",
)
TRIGGER_RE = re.compile(r"\b(?:" + "|".join(TRIGGERS) + r")\b", re.I)

# Default floor for the worklist. A row's title must reach this share of
# overlap with the sentence (common.title_score) to be worth a reader's time.
# It is a reporting knob, never a gate: raising it hides candidates, lowering
# it buries the real ones in noise.
RELEVANCE = 0.45

PAREN = re.compile(r"\(([^()]*\d{4}[a-z]?[^()]*)\)")
MARKER = re.compile(r"\[\[([A-Za-z0-9|_-]+)\]\]")


def detag(html):
    """HTML prose -> plain text, KEEPING any [[REF]] markers.

    prose_audit.detag drops the markers, which are the citations on the page
    route; tables go, for the reason given there.
    """
    html = re.sub(r"(?is)<table.*?</table>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(html)).strip()


def year_index(rows, keyf):
    """Two lookups: in-text author-year key -> years, and row key -> year."""
    by_key, by_ref = {}, {}
    for r in rows:
        yr = common.year_of(r.get("apa", ""))
        by_ref[str(r.get(keyf, ""))] = yr
        for k in cite_check.keys_for(r.get("apa", "")):
            by_key.setdefault(cite_check.norm(k), set()).add(yr)
    return by_key, by_ref


def corpus_titles(rows, keyf):
    """[(ref, year, title)] for every row that has both.

    A canonical row carries no `title` field — the title is inside its `apa`,
    which is what `parse_apa` is for. The agent-supplied `search_title` is the
    fallback for a row whose `apa` will not parse, never the first choice.
    """
    out = []
    for r in rows:
        p = common.parse_apa(r.get("apa", ""))
        title = (p["title"] if p else "") or r.get("title") or r.get("search_title") or ""
        year = p["year"] if p else r.get("search_year")
        if title and isinstance(year, int):
            out.append((str(r.get(keyf, "?")), year, title))
    return out


def groups_in(sentence, apa_mode, by_key, by_ref):
    """Citation groups in one sentence, as [[(label, year), ...], ...].

    A group of one is kept: it cannot be out of order, but its year is still
    the floor the worklist searches below. A year of None (an unresolved
    citation, or two rows of different years behind one author-year) is kept
    in place so the caller sees it instead of comparing against nothing.
    """
    out = []
    if apa_mode:
        for grp in PAREN.findall(sentence):
            cited = []
            for part in grp.split(";"):
                part = part.strip().rstrip(",")
                part = re.sub(r",\s*(?:p{1,2}\.|para\.|Ch\.)\s*[\d\-–]+$", "", part)
                if not re.search(r",\s*\d{4}[a-z]?$", part):
                    continue
                yrs = by_key.get(cite_check.norm(part), set())
                cited.append((part, next(iter(yrs)) if len(yrs) == 1 else None))
            if cited:
                out.append(cited)
        # narrative form, 'Desimone et al. (1984) showed': one citation each,
        # so it never reaches the order gate, but it does set the floor.
        for who, yr in re.findall(
                r"([A-ZÀ-Ý][\wÀ-ÿ'’\-]+(?:\s(?:&|and)\s[A-ZÀ-Ý][\wÀ-ÿ'’\-]+|"
                r"\s+et\s+al\.)?)\s+\((\d{4}[a-z]?)\)", sentence):
            key = f"{who.replace(' and ', ' & ')}, {yr}"
            yrs = by_key.get(cite_check.norm(key), set())
            out.append([(key, next(iter(yrs)) if len(yrs) == 1 else None)])
    else:
        for grp in MARKER.findall(sentence):
            out.append([(ref, by_ref.get(ref)) for ref in grp.split("|")])
    return out


def inversions(cited):
    """Pairs in a group that run newest-before-oldest, in citation order."""
    bad = []
    for i in range(len(cited) - 1):
        for j in range(i + 1, len(cited)):
            (an, ay), (bn, by) = cited[i], cited[j]
            if ay is not None and by is not None and ay > by:
                bad.append((an, ay, bn, by))
    return bad


def content_words(text):
    """Lowercase content words of a title or a sentence, stop words dropped."""
    words = common._title_words(text).split()
    return [w for w in words if w not in common._TITLE_STOP]


def overlap(sentence_words, title):
    """Share of a title's content words that the sentence uses, or None.

    None when the title is too short to mean anything: a two-word title like
    "The sialic acids" matches every sentence in a review about sialic acid,
    so it would head the worklist of every claim. common.MIN_MAIN_TITLE_WORDS
    is the same floor title_agrees uses, for the same reason — this is not
    title_score, whose one-way containment has no floor at all.
    """
    tw = content_words(title)
    if len(tw) < common.MIN_MAIN_TITLE_WORDS:
        return None
    return sum(w in sentence_words for w in tw) / len(tw)


def earlier_rows(sentence, floor, corpus, cited, relevance, top):
    """Corpus rows older than `floor` whose titles overlap the sentence."""
    if floor is None:
        return []
    words, scored = set(content_words(sentence)), []
    for ref, yr, title in corpus:
        if yr >= floor or ref in cited:
            continue
        score = overlap(words, title)
        if score is not None and score >= relevance:
            scored.append((score, yr, ref, title))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return scored[:top]


def claims(blocks, apa_mode, by_key, by_ref):
    """[(label, sentence, groups)] for every origin-claim sentence with a group."""
    found = []
    for label, text in blocks.items():
        for sent in prose_audit.sentences(detag(text) if not apa_mode else text):
            if not TRIGGER_RE.search(sent):
                continue
            found.append((label, sent, groups_in(sent, apa_mode, by_key, by_ref)))
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--page", help="project build_review_page.py ([[REF]] markers)")
    src.add_argument("--content", help="content.json for the .docx route (APA author-date)")
    ap.add_argument("--key", default=None, help="row key field (default: ref, else label)")
    ap.add_argument("--relevance", type=float, default=RELEVANCE,
                    help=f"worklist: title overlap floor, 0-1 (default {RELEVANCE})")
    ap.add_argument("--top", type=int, default=5,
                    help="worklist: earlier rows listed per claim (default 5)")
    ap.add_argument("--no-worklist", action="store_true",
                    help="run the gate only, and skip the judgment half")
    ap.add_argument("--quiet", action="store_true", help="totals and failures only")
    args = ap.parse_args()

    rows = common.load_json(args.rows)
    keyf = common.key_field(rows, args.key)
    apa = bool(args.content)
    path = args.content or args.page
    blocks = prose_audit.content_blocks(path) if apa else prose_audit.page_blocks(path)

    by_key, by_ref = year_index(rows, keyf)
    found = claims(blocks, apa, by_key, by_ref)
    grouped = [c for c in found if any(len(g) > 1 for g in c[2])]

    bad = [(label, sent, inv)
           for label, sent, groups in grouped
           for g in groups
           for inv in [inversions(g)] if inv]

    print(f"{len(found)} origin-claim sentence(s) | {len(grouped)} cite a group | "
          f"{len(bad)} out of order")
    for label, sent, inv in bad:
        print(f"  ✗ {label}: cites newer before older")
        print(f"       {sent.strip()[:200]}")
        for an, ay, bn, by in inv:
            print(f"       {an} ({ay}) precedes {bn} ({by}) — reorder oldest-first")

    if not args.no_worklist:
        listed = 0
        corpus = corpus_titles(rows, keyf)
        for label, sent, groups in found:
            years = [y for g in groups for _, y in g if y is not None]
            here = {name for g in groups for name, _ in g}
            cands = earlier_rows(sent, min(years) if years else None,
                                 corpus, here, args.relevance, args.top)
            if not cands:
                continue
            listed += 1
            print(f"  ? {label}: {len(cands)} corpus row(s) older than {min(years)}")
            print(f"       {sent.strip()[:200]}")
            for score, yr, ref, title in cands:
                print(f"       {yr}  {ref}  {title[:76]}  (overlap {score:.2f})")
        if listed and not args.quiet:
            print(f"  — {listed} claim(s) have an older candidate: judgment, not a verdict")

    if bad:
        sys.exit(1)
    if not args.quiet:
        print("✓ every origin claim that cites a group cites it oldest-first")


if __name__ == "__main__":
    main()
