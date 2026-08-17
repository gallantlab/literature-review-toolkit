#!/usr/bin/env python3
"""Phase 7 gate — every in-text citation must name a paper in rows.json.

A review's reference list is built from rows.json, so an in-text citation that
names no row is a reference the reader cannot follow, and an author-year that
matches TWO rows is a citation the reader cannot resolve. Both are invisible to
the renderer, which simply prints whatever prose it is given.

  python3 tools/cite_check.py --rows rows.json --content content.json

Reads the `abstract` and every `sections[].paragraphs[]` of the content JSON,
parses APA author-date citations in both parenthetical and narrative form, and
checks each against author-year keys derived from the canonical `apa` strings.

Exit 1 on an UNRESOLVED citation (a hard gate: the reference list cannot back it).
AMBIGUOUS citations are reported as warnings, because the fix is editorial —
APA-7 8.19 says to name enough subsequent authors to tell the two apart
("(Kral, Davis, et al., 2022)"), which this tool cannot write for you.

Note on year suffixes: APA-7's other disambiguator is 2025a/2025b. references.py
accepts those, and so does this tool, but adding them means editing rows.json's
canonical `apa` strings; the extra-author form usually costs less.
"""
import argparse
import re
import sys
import unicodedata

import common

# "Family, I. N." — the unit the APA formatter emits. Family may be a compound
# ('Lambon Ralph') or carry a particle ('de Heer', 'van den Heuvel').
SURNAME = re.compile(
    r"([A-ZÀ-ÝÄÖÜ][\wÀ-ÿ'’\-]*(?:\s(?:[a-zà-ÿ]+\s)*[A-ZÀ-ÝÄÖÜ][\wÀ-ÿ'’\-]*)?)"
    r",\s+(?:[A-ZÀ-Ý]\.(?:\s*[-A-ZÀ-Ý]\.)*)")


def norm(s):
    """Fold accents and curly apostrophes so 'Millière' matches 'Milliere'."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().replace("’", "'").replace("‐", "-").replace("‑", "-").strip()


def keys_for(apa):
    """Every in-text form that should legitimately resolve to this reference."""
    m = re.match(r"^(.*?)\s\((\d{4}[a-z]?)\)", apa or "")
    if not m:
        return []
    fams, yr = SURNAME.findall(m.group(1)), m.group(2)
    if not fams:
        return []
    if len(fams) == 1:
        return [f"{fams[0]}, {yr}"]
    if len(fams) == 2:
        return [f"{fams[0]} & {fams[1]}, {yr}", f"{fams[0]} et al., {yr}"]
    # 3+ authors: the plain form, plus APA-7 8.19's extra-author disambiguation
    out = [f"{fams[0]} et al., {yr}", f"{fams[0]}, {fams[1]}, et al., {yr}"]
    if len(fams) > 2:
        out.append(f"{fams[0]}, {fams[1]}, {fams[2]}, et al., {yr}")
    return out


def citations_in(text):
    """Both APA forms: parenthetical '(Farb et al., 2007)' and narrative
    'Farb and colleagues (2007)'."""
    found = set()
    for grp in re.findall(r"\(([^()]*\d{4}[a-z]?[^()]*)\)", text):
        for part in grp.split(";"):
            part = part.strip().rstrip(",")
            # trim a locator: "(Smith, 2020, p. 4)" -> "Smith, 2020"
            part = re.sub(r",\s*(?:p{1,2}\.|para\.|Ch\.)\s*[\d\-–]+$", "", part)
            if re.search(r",\s*\d{4}[a-z]?$", part):
                found.add(part)
    for m in re.finditer(
            r"([A-ZÀ-ÝÄÖÜ][\wÀ-ÿ'’\-]+(?:\s(?:&|and)\s[A-ZÀ-ÝÄÖÜ][\wÀ-ÿ'’\-]+|"
            r"\s+et\s+al\.)?)\s+\((\d{4}[a-z]?)\)", text):
        who = m.group(1).replace(" and ", " & ")
        found.add(f"{who}, {m.group(2)}")
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--content", required=True)
    ap.add_argument("--key", default=None, help="row key field (default: ref, else label)")
    ap.add_argument("--quiet", action="store_true", help="only report problems")
    args = ap.parse_args()

    rows = common.load_json(args.rows)
    content = common.load_json(args.content)
    keyf = args.key or ("ref" if rows and "ref" in rows[0] else "label")

    index = {}
    for r in rows:
        for k in keys_for(r.get("apa", "")):
            index.setdefault(norm(k), []).append(r.get(keyf, "?"))

    text = content.get("abstract", "")
    for s in content.get("sections", []):
        text += "\n" + "\n".join(s.get("paragraphs", []))

    cites = citations_in(text)
    unresolved, ambiguous, ok = [], [], []
    for c in sorted(cites):
        hits = sorted(set(index.get(norm(c), [])))
        if not hits:
            unresolved.append(c)
        elif len(hits) > 1:
            ambiguous.append((c, hits))
        else:
            ok.append((c, hits[0]))

    print(f"{len(cites)} distinct in-text citations | {len(ok)} resolve | "
          f"{len(ambiguous)} ambiguous | {len(unresolved)} unresolved")
    for c, hits in ambiguous:
        print(f"  ⚠ ambiguous: ({c}) matches {hits} — APA-7 8.19: name more authors")
        for ref in hits:
            row = next((r for r in rows if r.get(keyf) == ref), {})
            print(f"       {ref}: {(row.get('title') or row.get('apa', ''))[:88]}")
    for c in unresolved:
        print(f"  ✗ unresolved: ({c}) names no reference in {args.rows}")
    if not args.quiet and not unresolved and not ambiguous:
        print("✓ every in-text citation resolves to exactly one reference")
    if unresolved:
        sys.exit(1)


if __name__ == "__main__":
    main()
