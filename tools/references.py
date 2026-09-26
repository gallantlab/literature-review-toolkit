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

arXiv ids are fetched in batches of 50 (one request per 50 rows, 3 s apart, as
arXiv asks), never one per row. A row whose fetch fails gets a second try at the
end of the run after --retry-wait; a row that still fails is named and the run
exits 1, because its `apa` is not canonical. `--only A-01,B-02` rebuilds just
those rows and leaves every other row exactly as it is (the targeted re-canon).
"""
import argparse
import datetime
import difflib
import os
import re
import sys
import time

import common
from common import ARXIV_DOI, build_apa, clean_venue, doi_of, person, split_name

PHASE = "3f"   # pipeline phase, read by tools/gen_docs.py for the tool index


# ---- authoritative sources ------------------------------------------------
# Both readers live in common (crossref_record / arxiv_entries) and are shared
# with verify.py and xref.py; this file only turns a record into an APA string.
def crossref_apa(r):
    """APA string for one crossref_record(): a chapter names its book, not its series."""
    if r.get("book"):
        return common.build_chapter_apa(r["people"], r["year"], r["title"], r["book"],
                                        r["pages"], r.get("publisher"))
    return build_apa(r["people"], r["year"], r["title"], r["journal"],
                     r["volume"], r["issue"], r["pages"])


def crossref(doi, fallback_venue=""):
    r = common.crossref_work(doi, fallback_venue)
    if not r or not r["people"]:
        return None
    return {"apa": crossref_apa(r), "venue": r["book"] or r["journal"], "source": "crossref"}


def arxiv(aid, fallback_venue="", entries=None):
    """APA from the arXiv record; `entries` is a common.arxiv_batch() prefetch
    (else this one id is fetched on its own)."""
    na = common.norm_arxiv(aid)
    e = (entries if entries is not None else common.arxiv_fetch([aid])).get(na)
    if not e:
        return None
    people = [person(*split_name(name)) for name in e["authors"]]
    # a published paper often records its venue in arXiv's journal_ref
    journal = e["journal_ref"] or clean_venue(fallback_venue) or "arXiv"
    apa = build_apa(people, e["year"], e["title"], journal)
    return {"apa": apa, "venue": journal, "source": "arxiv"}


def route(row):
    """(journal_doi, arxiv_id) the row is canonicalized from; at most one is set.

    A real (non-arXiv) DOI is the version of record: prefer CrossRef over the
    arXiv preprint even when the row carries both, so a published paper is cited
    by its journal version rather than its preprint. arXiv is used only when
    there is no journal DOI (preprint-only rows) or the DOI is itself an arXiv DOI."""
    doi = doi_of(row)
    aid = (row.get("arxiv") or "").strip()
    am = ARXIV_DOI.match(doi or "")
    if am:
        aid = aid or am.group(1)
    journal_doi = doi if (doi and not am) else ""
    return journal_doi, ("" if journal_doi else aid)


def canonical(row, arxiv_cache=None):
    """Return {apa, link, source, ...} rebuilt from the authoritative source, or
    None if there is no DOI/arxiv to rebuild from (or the source has no usable
    record). `arxiv_cache` is an (entries, errored) common.arxiv_batch() result;
    an id in `errored` is reported as a fetch error, never as a miss."""
    doi = doi_of(row)
    journal_doi, aid = route(row)
    fv = row.get("venue", "")
    try:
        if journal_doi:
            r = crossref(journal_doi, fv)
        elif aid:
            if arxiv_cache is not None:
                entries, errored = arxiv_cache
                if common.norm_arxiv(aid) in errored:
                    return {"error": "arXiv batch could not complete (rate-limit/network)",
                            "source": "error"}
                r = arxiv(aid, fv, entries)
            else:
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


def stamp_canonical(row, asof):
    """Mark a row as canonical (rebuilt or repaired on `asof`). common.write_rows
    reads this stamp to refuse an upstream emitter's overwrite of the live table."""
    row["canonical_at"] = asof


# ---- quality gate ---------------------------------------------------------
def doi_year(doi):
    """A 4-digit year embedded in a DOI suffix, else None.

    Publishers that digitized a back catalog often deposit the DIGITIZATION
    year as the issued date while leaving the true year in the DOI string
    (Wiley's `10.1111/j.1439-0310.1943.tb00655.x` is a 1943 paper deposited as
    2010). Only years in a plausible publishing range are returned."""
    # Deliberately NARROW: only the Wiley legacy back-file shape `.<year>.tb<n>`,
    # which is where this error class actually comes from. A looser scan matches
    # page numbers (`science.167.3926.1745`), article ids (`nrn1606`, `nmeth.1694`)
    # and ISSN fragments (`s1874-6055`) and is pure noise.
    m = re.search(r"\.(1[89]\d\d|20[0-4]\d)\.tb\d", str(doi or ""), re.I)
    return int(m.group(1)) if m else None


def deposit_year_conflict(doi, apa):
    """Warn when the DOI's embedded year disagrees with the reference's year.

    Returns a message or None. Three real cases in one corpus: Seyfarth 1991
    deposited as 2008, Lorenz 1943 and Schleidt 1962 both deposited as 2010."""
    dy = doi_year(doi)
    ay = common.year_of(apa)
    if dy and ay and abs(dy - ay) > 1:
        return (f"deposit-year: DOI encodes {dy} but the reference says {ay} — "
                "likely a publisher back-file/digitization date; verify by hand")
    return None


def cached_year_conflict(row):
    """Pre-canon emitters often cache a `year` field next to the apa. Canon
    rewrites the apa but nothing re-checked the cache, and a page that prefers
    the cache (`r.get("year") or year_of(apa)`) then trusts a stale copy —
    five corpora had already diverged when this warning was added. Reported as
    a warning, not a defect: only a human can say which value is right."""
    cached = row.get("year")
    apa_year = common.year_of(row.get("apa", ""))
    if cached in (None, "") or apa_year is None:
        return None
    try:
        cached_int = int(str(cached).strip())
    except ValueError:
        return f"cached year {cached!r} is not a year (apa says {apa_year})"
    if cached_int != apa_year:
        return (f"cached year {cached_int} != apa year {apa_year} — "
                "fix whichever is wrong, or delete the stale cache field")
    return None


def audit(apa, has_source):
    """Return (defects, notes). `defects` are real formatting errors that must
    fail the build; `notes` are non-fatal (a well-formed book/report with no DOI
    can't be auto-rebuilt, but is still a valid reference)."""
    defects, notes = [], []
    if not has_source:
        notes.append("no DOI/arxiv — manual ref (verify by hand)")
    # One grammar for the whole toolkit (common.parse_apa): it accepts APA-7's
    # 2025a/2025b year suffix, so same-author/same-year works can be expressed.
    parts = common.parse_apa(apa)
    if not parts:
        defects.append("no-year")
    if apa.startswith("Anon.") or (parts and not parts["authors"]):
        defects.append("no-authors")
    # "et al." is a defect in an AUTHOR LIST and an ordinary word in a TITLE:
    # Nature titles its Matters Arising replies "<Author> et al. reply". So look
    # only at the author segment, falling back to the whole string when the APA
    # grammar cannot parse the reference (no author segment to narrow to, and a
    # malformed reference is exactly where an abbreviated list hides).
    if " et al" in (parts["authors"] if parts else apa):
        defects.append("et-al (should list all authors)")
    if "&amp;" in apa or "&#x" in apa or "&lt;" in apa or "&gt;" in apa:
        defects.append("html-entity")
    if common.MARKUP.search(apa):
        # CrossRef deposits JATS markup inside titles (<scp>SMALL CAPS</scp>, <i>);
        # the entity check above cannot see a literal tag.
        defects.append("markup-tag (JATS/HTML left in the reference)")
    if re.search(r"[?!]\.", apa):
        defects.append("double-terminal-punctuation (a title ending in ? or ! takes no period)")
    if parts:
        t = parts["title"]
        if re.search(r"[,;](?=[A-Za-z])", t):
            # a comma or semicolon with no space after it: CrossRef's JATS markup
            # was stripped without a separator ("marine mollusc,Tritonia")
            defects.append("missing-space (punctuation glued to the next word)")
        elif re.search(r"[a-z](" + "|".join(sorted(common.GENERA)) + r")\b", t):
            # same bug where the tag wrapped a genus ("cockroachPeriplaneta")
            defects.append("missing-space (a genus is glued to the preceding word)")
    if re.search(r"\?[A-Za-z]", apa) or re.search(r"\s\?\s", apa):
        # A '?' glued to a letter, or floating alone, is a smart quote / dash the
        # source could not encode (Wehner 1987 came back as "?Matched filters? ?
        # neural models"). A real question mark is followed by a space or a
        # closing bracket, so "What is (was?) the fixed action pattern?" is fine.
        defects.append("mangled-punct (a '?' where a quote or dash belongs — fix by hand)")
    if "‐" in apa or "‑" in apa:
        defects.append("unicode-hyphen (U+2010/U+2011 in a name — normalize to ASCII '-')")
    if re.search(r"\(\.|\[\.", apa):
        # a used name in parentheses initialized literally: 'L. (Renzo)' -> 'L. (.'
        defects.append("malformed-initial (a bracket was initialized as a name)")
    if re.search(r"\b[A-Z]\. -\.", apa):
        # a hyphenated given name deposited with its second part missing:
        # CrossRef's "Jean-" for Jean-Baptiste Poline initializes to 'J. -.'
        defects.append("malformed-initial (hyphenated given name missing its second part)")
    if "�" in apa:
        # U+FFFD replacement char = mojibake the source (often CrossRef) stored with
        # broken encoding; the original glyph is unrecoverable, so flag for a hand fix.
        defects.append("replacement-char (U+FFFD mojibake — fix by hand)")
    if re.search(r"\.\s+[A-Z]\.\s*$", apa):
        defects.append("single-letter venue (truncated)")
    # A footnote marker digit glued to the last title word ("psychological
    # science1", "BOLD fMRI1"): CrossRef keeps the superscript as plain text. Only
    # a lowercase letter followed by a single digit at the END of the title is
    # flagged, so area names (V1, S1, M1) and "area 3b" pass. A warning, because a
    # real title can end that way ("...of H1").
    _p = common.parse_apa(apa)
    if _p and re.search(r"[a-z][1-9]$", _p["title"]):
        notes.append("glued-footnote (a footnote digit stuck to the last title word — check the source)")
    # Catch an uppercase TITLE (norm_title misses titles that are only MOSTLY
    # caps). Scan the title sentence ONLY — author initials ("R. B. H.") and
    # venue acronyms ("PLOS ONE") legitimately have caps and must be excluded.
    title = parts["title"] if parts else ""
    run = mx = 0
    for t in re.findall(r"[A-Za-z][A-Za-z'/-]*", title):   # no '.', so initials aren't tokens
        run = run + 1 if (t.isupper() and len(t) >= 2) else 0
        mx = max(mx, run)
    if mx >= 3:
        defects.append(f"uppercase-title run ({mx} consecutive caps words)")
    for fam in common.suspect_surnames(apa):
        # Cannot be decided automatically: 'Lambon Ralph' is a real compound surname,
        # 'Thomas Yeo' is CrossRef folding given names into the family field. Both
        # need a human verdict, and re-running the formatter reintroduces the error.
        notes.append(f"multi-word surname '{fam}' — confirm it is not a mis-split given name")
    # a DOI-backed ref should name a venue: real text after the title sentence
    # (parse_apa already knows the title ends at ". ", "? " or "! ").
    venue_part = parts["rest"].strip(" .") if parts else ""
    if has_source and not venue_part:
        defects.append("empty venue")
    return defects, notes


def repair(apa):
    """Deterministic, offline repair of the defect classes that are pure string
    damage. Returns (fixed_apa, [what changed]).

    This exists to retrofit the gate onto an OLD corpus. Re-running the full
    canon would fix these too, but canon re-fetches from CrossRef and so wipes
    every post-canon hand fix the corpus depends on — the reviewed sentence
    casing, the mojibake repairs, the corrected compound surnames. Those are the
    fixes the PLAYBOOK says must come LAST, and a blanket re-canon undoes all of
    them. This touches only the damage, and never the network.
    """
    out, changed = apa, []
    if common.MARKUP.search(out):
        out = common.MARKUP.sub("", out)
        changed.append("stripped markup tag")
    if "‐" in out or "‑" in out:
        out = out.translate(common.UNI_HYPHEN)
        changed.append("normalized Unicode hyphen")
    if re.search(r"[?!]\.", out):
        out = re.sub(r"([?!])\.(\s|$)", r"\1\2", out)
        changed.append("removed period after ? or !")
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out, changed


def duplicate_scan(rows, keyf, threshold=0.88):
    """Corpus-level near-duplicate check -> [(keyA, keyB, ratio, why)].

    The per-row audit cannot see this: the same paper can enter a review TWICE as
    two legitimate-looking rows — typically an arXiv preprint found by one search
    agent and the published version found by another (different DOIs, so the
    one-row-per-DOI rule does not catch it, and each row canonicalizes perfectly).
    Compare normalized title sentences and report close pairs as WARNINGS, not
    defects: distinct papers do share near-identical titles (a 2014 toolbox paper
    and its 2026 successor; successive years of the same challenge), so this needs
    a human verdict — keep the version of record, drop the preprint.
    """
    def title_of(apa):
        p = common.parse_apa(apa)
        return re.sub(r"[^a-z0-9 ]", "", p["title"].lower()).strip() if p else ""

    items = [(r.get(keyf, "?"), title_of(r.get("apa", "")), (r.get("link") or "").lower())
             for r in rows]
    pairs = []
    sm = difflib.SequenceMatcher()          # same defaults as before (autojunk on)
    for i, (ka, ta, la) in enumerate(items):
        for kb, tb, lb in items[i + 1:]:
            if la and la == lb:
                pairs.append((ka, kb, 1.0, "same DOI"))
                continue
            if not ta or not tb:
                continue
            if abs(len(ta) - len(tb)) > 0.35 * max(len(ta), len(tb)):
                continue                                      # cheap length prefilter
            # real_quick_ratio() and quick_ratio() are upper bounds on ratio(), so
            # a pair that fails either can never pass: same pairs, ~8x faster.
            sm.set_seqs(ta, tb)
            if sm.real_quick_ratio() < threshold or sm.quick_ratio() < threshold:
                continue
            ratio = sm.ratio()
            if ratio >= threshold:
                preprint_pair = ("10.48550" in la) != ("10.48550" in lb)
                why = "preprint vs published?" if preprint_pair else "near-identical title"
                pairs.append((ka, kb, ratio, why))
    return pairs


def warning_id(note):
    """Stable id for an audit warning, so an acknowledgment survives reruns.

    deposit-year and cached-year encode the two years in conflict, so
    acknowledging one mismatch never silently covers a later, different
    mismatch on the same row. glued-footnote has no year (or any other value)
    in its note text to key on; this returns the bare category for it, and
    audit_rows refines it further from the row's own title."""
    m = re.match(r"multi-word surname '(.+?)'", note)
    if m:
        return f"multi-word-surname:{m.group(1)}"
    m = re.match(r"deposit-year: DOI encodes (\d+) but the reference says (\d+)", note)
    if m:
        return f"deposit-year:{m.group(1)}/{m.group(2)}"
    m = re.match(r"cached year '(.+?)' is not a year \(apa says (\d+)\)", note)
    if m:
        return f"cached-year:{m.group(1)}/{m.group(2)}"
    m = re.match(r"cached year (\S+) != apa year (\d+)", note)
    if m:
        return f"cached-year:{m.group(1)}/{m.group(2)}"
    if note.startswith("glued-footnote"):
        return "glued-footnote"
    return note


def row_gate_defects(r, warn):
    """Defects the reference gates add for one row of a GATED table; `warn(wid,
    text)` records a warning that must be acknowledged."""
    d = []
    if doi_of(r) or r.get("arxiv"):
        if not common.verified_ok(r):
            st = r.get("verified")
            why = ("never verified" if not isinstance(st, dict)
                   else "verified under a different DOI/arXiv id" if common.stamp_ids(st) != common.ids_of(r)
                   else f"verdict {st.get('verdict')} not resolved")
            d.append(f"unverified ({why})")
        elif not r.get("canonical_at"):
            warn("kept-existing-apa", "verified but not rebuilt by canon (the source had no usable "
                 "record); confirm the apa by hand")
    else:
        hv = r.get("hand_verified")
        if not (isinstance(hv, dict) and hv.get("verdict") in ("confirmed", "corrected")
                and str(hv.get("source_checked") or "").strip()):
            d.append("hand-check-missing (a DOI-less row needs handcheck.py --ingest)")
    s = (r.get("summary") or "").strip()
    if s:
        sc = r.get("summary_check")
        if not isinstance(sc, dict) or sc.get("summary_sha") != common.summary_sha(s):
            d.append("summary-unchecked (run summary_audit.py)")
        elif sc.get("verdict") == "unsupported":
            d.append(f"summary-flagged: {sc.get('note') or 'claims something its abstract does not'}")
        elif sc.get("verdict") == "no-abstract":
            warn("no-abstract", "the summary has no abstract to be checked against")
        elif sc.get("verdict") != "supported":
            d.append(f"summary-unchecked (unknown verdict {sc.get('verdict')!r})")
    return d


def load_acks(path):
    """audit_acks.json -> {ref: {warning_id: reason}} ({} when absent)."""
    acks = common.load_optional_json(path, {})
    if not isinstance(acks, dict) or not all(isinstance(v, dict) for v in acks.values()):
        raise ValueError(f"{path} must map ref -> {{warning_id: reason}}")
    for ref, ws in acks.items():
        for wid, reason in ws.items():
            if not isinstance(reason, str):
                raise ValueError(f"{path}: {ref} [{wid}] must be a string reason, not {reason!r}")
    return acks


def audit_rows(rows, keyf, acks=None):
    """The whole audit, for references.py --audit and spreadsheet.py alike."""
    gated = common.is_gated(rows)
    acks = acks or {}
    defects, warnings, manual = {}, {}, {}

    def warn(k, wid, text):
        warnings.setdefault(k, []).append((wid, text))

    for r in rows:
        k = r.get(keyf, "?")
        d, n = audit(r.get("apa", ""), bool(doi_of(r) or r.get("arxiv")))
        d = list(d)
        extra = [x for x in (deposit_year_conflict(doi_of(r), r.get("apa", "")), cached_year_conflict(r))
                 if x]
        for note in list(n) + extra:
            if note.startswith("no DOI"):
                manual[k] = note
            else:
                wid = warning_id(note)
                if wid == "glued-footnote":
                    # warning_id has no title to key on; the row does. Two different
                    # rows glued-footnoted on different words must not share one ack.
                    title = (common.parse_apa(r.get("apa", "")) or {}).get("title", "")
                    last_word = title.split()[-1] if title.split() else ""
                    wid = f"glued-footnote:{last_word}"
                warn(k, wid, note)
        if gated:
            d += row_gate_defects(r, lambda wid, text, k=k: warn(k, wid, text))
        if d:
            defects[k] = d
    dups = duplicate_scan(rows, keyf)
    for ka, kb, ratio, why in dups:
        warn(ka, f"possible-duplicate:{kb}", f"possible duplicate of {kb} ({ratio:.2f}, {why})")
    corpus = []
    unacked = {}
    for k, ws in warnings.items():
        for wid, text in ws:
            if not str((acks.get(k) or {}).get(wid) or "").strip():
                unacked.setdefault(k, []).append((wid, text))
    live = {(k, wid) for k, ws in warnings.items() for wid, _ in ws}
    stale = [(k, wid) for k, m in acks.items() for wid in m if (k, wid) not in live]
    failed = bool(defects or corpus or (gated and unacked))
    return {"gated": gated, "defects": defects, "corpus": corpus, "warnings": warnings,
            "unacked": unacked, "stale_acks": stale, "manual": manual, "dups": dups, "failed": failed}


def print_report(report, n_rows):
    """Human-readable audit, in the order a reader acts on it."""
    nw = sum(len(v) for v in report["warnings"].values())
    nu = sum(len(v) for v in report["unacked"].values())
    print(f"{n_rows} refs | {len(report['defects'])} defects | {len(report['manual'])} manual (no-DOI) | "
          f"{nw} warnings ({nu} unacknowledged) | {len(report['dups'])} possible duplicates")
    if not report["gated"]:
        print("  note: this corpus predates the reference gates, so they are not enforced here.")
        print("  Rerunning a search on it switches them on for the whole table; see PLAYBOOK "
              "'Upgrading an old corpus'.")
    for k, n in report["manual"].items():
        print(f"  · {k}: {n}")
    unacked_set = {(k2, w) for k2, v in report["unacked"].items() for w, _ in v}
    for k, ws in report["warnings"].items():
        for wid, text in ws:
            mark = "⚠" if (k, wid) in unacked_set else "✓"
            print(f"  {mark} {k} [{wid}]: {text}")
    for k, wid in report["stale_acks"]:
        print(f"  · stale acknowledgment {k} [{wid}]: no such warning any more; delete it")
    for c in report["corpus"]:
        print(f"  ✗ corpus: {c}")
    for k, d in report["defects"].items():
        print(f"  ✗ {k}: {'; '.join(d)}")


def canon_rows(rows, keyf, asof, sleep=0.25, retry_wait=60.0, only=None):
    """Rebuild every sourced row (or just the keys in `only`) in place.

    arXiv-routed rows are prefetched in batches first, so they cost no request
    and no pause of their own; a row that fetch-fails gets one more try after
    `retry_wait`. Returns {"rebuilt": n, "failed": [keys still failing],
    "kept": [keys whose source had no usable record, so the old apa stayed],
    "unverified": [keys not verified for their current DOI/arxiv id, so left
    un-rebuilt]}."""
    targets = [r for r in rows if (doi_of(r) or r.get("arxiv"))
               and (only is None or r.get(keyf) in only)]
    # The gate: a row is rebuilt only from ids verify.py confirmed. A MISMATCH
    # nobody resolved, or a DOI edited after verification, stays un-rebuilt, and
    # the audit then fails it — canon never prints a wrong paper beautifully.
    unverified = [r.get(keyf, "?") for r in targets if not common.verified_ok(r)]
    targets = [r for r in targets if common.verified_ok(r)]
    rebuilt, failed, kept = 0, [], []

    def one_pass(batch, chunk):
        nonlocal rebuilt
        aids = [route(r)[1] for r in batch if route(r)[1]]
        cache = common.arxiv_batch(aids, chunk=chunk) if aids else ({}, set())
        bad = []
        for r in batch:
            k = r.get(keyf, "?")
            before = common.request_count()
            res = canonical(r, cache)
            if res and res.get("apa"):
                r["apa"] = res["apa"]
                if res.get("link"):
                    r["link"] = res["link"]
                stamp_canonical(r, asof)
                rebuilt += 1
            elif res and res.get("error"):
                print(f"  [fetch-fail] {k}: {res['error']}", file=sys.stderr)
                bad.append(r)
            else:
                kept.append(k)
            if common.request_count() != before:
                time.sleep(sleep)      # courtesy pause only after a row that hit the network
        return bad

    bad = one_pass(targets, 50)
    if bad:
        print(f"  [retry] {len(bad)} fetch-fail row(s); cooling down {retry_wait:.0f}s, "
              "then one more try…", file=sys.stderr)
        time.sleep(retry_wait)
        bad = one_pass(bad, 25)
    failed = [r.get(keyf, "?") for r in bad]
    return {"rebuilt": rebuilt, "failed": failed, "kept": kept, "unverified": unverified}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", help="write rebuilt rows here (default: in place unless --audit)")
    ap.add_argument("--key", default=None, help="row key field (default: ref, else label)")
    ap.add_argument("--audit", action="store_true", help="report only; exit 1 if any ref is imperfect")
    ap.add_argument("--repair", action="store_true",
                    help="offline: fix markup / Unicode-hyphen / '?.' damage in place "
                         "WITHOUT re-fetching, so post-canon hand fixes survive. Use to "
                         "retrofit the gate onto an existing corpus.")
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"))
    ap.add_argument("--sleep", type=float, default=0.25,
                    help="pause after each row that made a request (default 0.25 s)")
    ap.add_argument("--retry-wait", type=float, default=60.0,
                    help="cool-down before fetch-fail rows get their second try (default 60 s)")
    ap.add_argument("--only", help="comma-separated keys: rebuild just these rows, leave the rest "
                    "untouched (targeted re-canon)")
    ap.add_argument("--asof", default=datetime.date.today().isoformat(),
                    help="date written to each rebuilt/repaired row's canonical_at (default: today)")
    ap.add_argument("--acks", help="acknowledged warnings (default: audit_acks.json beside --rows)")
    ap.add_argument("--list-acks", action="store_true",
                    help="list every unacknowledged warning as REF<TAB>WARNING_ID<TAB>TEXT and exit")
    args = ap.parse_args()
    if args.repair and args.audit:
        ap.error("--repair writes; --audit reports. Run --repair, then --audit to confirm.")
    if args.repair and args.list_acks:
        ap.error("--repair writes; --list-acks reports. Run --repair, then --list-acks to confirm.")
    if not args.email:
        ap.error("--email or LITREVIEW_EMAIL required (CrossRef/arXiv polite pool)")
    common.set_user_agent(args.email)

    rows = common.load_json(args.rows)
    keyf = common.key_field(rows, args.key)
    only = {x.strip() for x in args.only.split(",") if x.strip()} if args.only else None
    if only is not None:
        missing = only - {r.get(keyf) for r in rows}
        if missing:
            ap.error(f"--only names keys not in {args.rows}: {', '.join(sorted(missing))}")
    repaired, rebuilt = {}, 0
    result = {"rebuilt": 0, "failed": [], "kept": [], "unverified": []}
    if not args.repair and not args.audit and not args.list_acks:
        result = canon_rows(rows, keyf, args.asof, sleep=args.sleep,
                            retry_wait=args.retry_wait, only=only)
        rebuilt = result["rebuilt"]
    if args.repair:
        for r in rows:
            fixed, what = repair(r.get("apa", ""))
            if what:
                r["apa"] = fixed
                repaired[r.get(keyf, "?")] = what
            r.setdefault("canonical_at", args.asof)   # keep an existing date: repair is not canon
    if not args.audit and not args.list_acks:
        common.dump_json(rows, args.out or args.rows)

    acks_path = args.acks or os.path.join(os.path.dirname(os.path.abspath(args.rows)), "audit_acks.json")
    report = audit_rows(rows, keyf, load_acks(acks_path))
    if args.list_acks:
        for k, ws in report["unacked"].items():
            for wid, text in ws:
                print(f"{k}\t{wid}\t{text}")
        sys.exit(1 if report["unacked"] else 0)
    if rebuilt or args.repair:
        print(f"rebuilt {rebuilt}" + (f" | repaired {len(repaired)}" if args.repair else ""))
    for k, what in repaired.items():
        print(f"  ✎ {k}: {'; '.join(what)}")
    for k in result["kept"]:
        print(f"  ⚠ {k}: the source returned no usable record (no authors, or an id "
              "missing from the feed) — kept the existing apa; confirm it by hand")
    for k in result["failed"]:
        print(f"  ✗ {k}: fetch failed twice — NOT rebuilt, its apa is not canonical; "
              f"re-run with --only {k}")
    for k in result["unverified"]:
        print(f"  ✗ {k}: not verified for its current DOI/arXiv id — NOT rebuilt. Run "
              "verify.py --rows first, or clear a false alarm with verify.py --override")
    print_report(report, len(rows))
    if report["failed"] or result["failed"] or result["unverified"]:
        sys.exit(1)
    print("✓ all references pass the audit")


if __name__ == "__main__":
    main()
