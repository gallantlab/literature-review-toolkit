#!/usr/bin/env python3
"""Canonical reference builder — make EVERY reference perfect, in both modes.

A reference's bibliographic text must never be trusted from a search agent's
memory (topic mode) or OpenAlex's light metadata (lab mode). This rebuilds each
`apa` from the *verified* DOI against the authoritative source — CrossRef for
DOIs, the arXiv API for arXiv ids — through ONE formatter, then audits the result
against a hard quality gate.

Pipeline position:
  topic mode:  search -> verify.py (catch fabrications) -> references.py (canonicalize)
  lab  mode:   lab_corpus.py (OpenAlex) -> references.py (canonicalize)

INPUT: a JSON list of rows. Each row needs a stable key (default "ref" else
"label") and a DOI (from a `doi` field or a `https://doi.org/...` link) and/or an
`arxiv` id. An optional `venue` is used only as a last-resort fallback (lab mode
passes the OpenAlex venue). Rows with no DOI/arxiv keep their existing `apa` and
are flagged `no-source` for manual attention.

  python3 tools/references.py --rows rows.json --out rows.json --email you@x.edu
  python3 tools/references.py --rows rows.json --audit          # report only, exit 1 on any defect

OUTPUT (default): rewrites each row's `apa` (and `link` to the DOI URL), prints a
per-defect audit. `--audit` reports without writing and exits nonzero if any row
is imperfect — wire it into the build so a bad ref can never ship.
"""
import argparse, json, os, re, sys, time, urllib.parse
import xml.etree.ElementTree as ET

import common
from common import (ARXIV_DOI, ATOM, ARXIV_NS, build_apa, clean_venue, doi_of,
                    http, person, split_name)

set_email = common.set_user_agent


# ---- authoritative sources ------------------------------------------------
def crossref(doi, fallback_venue=""):
    m = json.loads(http(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"))["message"]
    people = [person(a.get("family", ""), a.get("given", ""))
              for a in (m.get("author") or []) if a.get("family")]
    if not people:
        return None
    year = ""
    for k in ("published-print", "published-online", "issued"):
        dp = (m.get(k) or {}).get("date-parts", [[None]])[0]
        if dp and dp[0]:
            year = dp[0]
            break
    journal = (m.get("container-title") or [""])[0]
    if not journal:                          # preprints (posted-content): name the server
        inst = m.get("institution")
        if isinstance(inst, dict):
            inst = [inst]
        if isinstance(inst, list) and inst:
            journal = inst[0].get("name", "") if isinstance(inst[0], dict) else str(inst[0])
        if not journal:
            gt = m.get("group-title")
            journal = gt[0] if isinstance(gt, list) and gt else gt if isinstance(gt, str) else ""
        journal = (journal or "").strip() or clean_venue(fallback_venue)
    apa = build_apa(people, year, (m.get("title") or [""])[0], journal,
                    m.get("volume"), m.get("issue"), m.get("page"))
    return {"apa": apa, "venue": journal, "source": "crossref"}


def arxiv(aid, fallback_venue=""):
    root = ET.fromstring(http(f"http://export.arxiv.org/api/query?id_list={urllib.parse.quote(aid)}"))
    e = root.find(f"{ATOM}entry")
    if e is None or e.find(f"{ATOM}title") is None:
        return None
    people = [person(*split_name(a.find(f"{ATOM}name").text)) for a in e.findall(f"{ATOM}author")]
    year = (e.findtext(f"{ATOM}published") or "")[:4]
    # a published paper often records its venue in arXiv's journal_ref
    jref = e.findtext(f"{ARXIV_NS}journal_ref")
    journal = (jref or "").strip() or clean_venue(fallback_venue) or "arXiv"
    apa = build_apa(people, year, e.findtext(f"{ATOM}title"), journal)
    return {"apa": apa, "venue": journal, "source": "arxiv"}


def canonical(row):
    """Return {apa, link, source, ...} rebuilt from the authoritative source, or
    None if there is no DOI/arxiv to rebuild from."""
    doi = doi_of(row)
    aid = (row.get("arxiv") or "").strip()
    am = ARXIV_DOI.match(doi or "")
    if am:
        aid = aid or am.group(1)
    # A real (non-arXiv) DOI is the version of record: prefer CrossRef over the
    # arXiv preprint even when the row carries both, so a published paper is cited
    # by its journal version rather than its preprint. arXiv is used only when
    # there is no journal DOI (preprint-only rows) or the DOI is itself an arXiv DOI.
    journal_doi = doi if (doi and not am) else ""
    fv = row.get("venue", "")
    try:
        if journal_doi:
            r = crossref(journal_doi, fv)
        elif aid:
            r = arxiv(aid, fv)
        elif doi:
            r = crossref(doi, fv)
        else:
            return None
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "source": "error"}
    if r and doi:
        r["link"] = f"https://doi.org/{doi}"
    return r


# ---- quality gate ---------------------------------------------------------
def audit(apa, has_source):
    """Return (defects, notes). `defects` are real formatting errors that must
    fail the build; `notes` are non-fatal (a well-formed book/report with no DOI
    can't be auto-rebuilt, but is still a valid reference)."""
    defects, notes = [], []
    if not has_source:
        notes.append("no DOI/arxiv — manual ref (verify by hand)")
    if not re.search(r"\(\d{4}\)", apa):
        defects.append("no-year")
    if apa.startswith("Anon.") or re.match(r"^\(\d{4}\)", apa):
        defects.append("no-authors")
    if " et al" in apa:
        defects.append("et-al (should list all authors)")
    if "&amp;" in apa or "&#x" in apa or "&lt;" in apa or "&gt;" in apa:
        defects.append("html-entity")
    if "�" in apa:
        # U+FFFD replacement char = mojibake the source (often CrossRef) stored with
        # broken encoding; the original glyph is unrecoverable, so flag for a hand fix.
        defects.append("replacement-char (U+FFFD mojibake — fix by hand)")
    if re.search(r"\.\s+[A-Z]\.\s*$", apa):
        defects.append("single-letter venue (truncated)")
    # Catch an uppercase TITLE (norm_title misses titles that are only MOSTLY
    # caps). Scan the title sentence ONLY — author initials ("R. B. H.") and
    # venue acronyms ("PLOS ONE") legitimately have caps and must be excluded.
    m = re.search(r"\(\d{4}\)\.\s+(.+)", apa)
    title = m.group(1).split(". ", 1)[0] if m else ""
    run = mx = 0
    for t in re.findall(r"[A-Za-z][A-Za-z'/-]*", title):   # no '.', so initials aren't tokens
        run = run + 1 if (t.isupper() and len(t) >= 2) else 0
        mx = max(mx, run)
    if mx >= 3:
        defects.append(f"uppercase-title run ({mx} consecutive caps words)")
    # a DOI-backed ref should name a venue: real text after the title sentence.
    # Structure is "Authors (YEAR). Title. Venue...."; drop the year-paren and the
    # title sentence (its trailing ". ") and require something non-empty to remain.
    after_year = apa.split(").", 1)[1] if ")." in apa else ""
    venue_part = after_year.split(". ", 1)[1].strip(" .") if ". " in after_year else ""
    if has_source and not venue_part:
        defects.append("empty venue")
    return defects, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", help="write rebuilt rows here (default: in place unless --audit)")
    ap.add_argument("--key", default=None, help="row key field (default: ref, else label)")
    ap.add_argument("--audit", action="store_true", help="report only; exit 1 if any ref is imperfect")
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"))
    ap.add_argument("--sleep", type=float, default=0.25)
    args = ap.parse_args()
    if not args.email:
        ap.error("--email or LITREVIEW_EMAIL required (CrossRef/arXiv polite pool)")
    set_email(args.email)

    rows = common.load_json(args.rows)
    keyf = args.key or ("ref" if rows and "ref" in rows[0] else "label")
    defects, notes, rebuilt = {}, {}, 0
    for r in rows:
        k = r.get(keyf, "?")
        if not args.audit:
            res = canonical(r)
            if res and res.get("apa"):
                r["apa"] = res["apa"]
                if res.get("link"):
                    r["link"] = res["link"]
                rebuilt += 1
            elif res and res.get("error"):
                print(f"  [fetch-fail] {k}: {res['error']}", file=sys.stderr)
            time.sleep(args.sleep)
        d, n = audit(r.get("apa", ""), bool(doi_of(r) or r.get("arxiv")))
        if d:
            defects[k] = d
        if n:
            notes[k] = n

    if not args.audit:
        common.dump_json(rows, args.out or args.rows)

    print(f"{len(rows)} refs | rebuilt {rebuilt} | {len(defects)} defects | {len(notes)} manual (no-DOI)")
    for k, n in notes.items():
        print(f"  · {k}: {'; '.join(n)}")
    for k, d in defects.items():
        print(f"  ✗ {k}: {'; '.join(d)}")
    if defects:
        sys.exit(1)
    print("✓ all references perfect (no formatting defects)")


if __name__ == "__main__":
    main()
