#!/usr/bin/env python3
"""Verify a list of citations against PMC / PubMed / CrossRef / DataCite / arXiv.

Reports one verdict per citation: OK, MISMATCH (author/year/title), NOT-FOUND,
ERROR, or UNCHECKED (the row carried no claim to check, so a resolving DOI proves
nothing). NOT-FOUND and ERROR are kept strictly separate: NOT-FOUND means every
lookup completed and none matched (chase it down — likely fabricated); ERROR
means a lookup could not complete (rate-limit / network) and must be re-run.
Collapsing the two — as an earlier version did by swallowing exceptions into
NOT-FOUND — can drop a real paper on a transient throttle. Never add a NOT-FOUND
without chasing it, and always re-run an ERROR.

Exit status: 0 only when every verdict is OK; 1 otherwise — the same fail-loud
contract as references.py --audit and cite_check.py, so a chained Phase-3 run
stops on the first table that needs attention.

arXiv/conference papers are a verification BLIND SPOT for PMC/PubMed/CrossRef:
an arXiv DOI (10.48550/arXiv.<id>) is not in CrossRef, and a PubMed title-search
returns a plausible-but-wrong paper — so they come back NOT-FOUND or a garbage
MISMATCH, which reads as "skip" and lets a whole class of papers (AI/ML venues,
preprints) dodge the check. So this tool resolves arXiv DOIs and bare `arxiv`
ids directly against the arXiv API, prefetched in BATCHES (the API takes many
ids per `id_list` call and rate-limits a per-paper loop into a ban).

A DOI missing from CrossRef is not necessarily fake: Zenodo, figshare, OSF and
Dryad software/data-set (and some preprint) deposits are registered with
DataCite instead, so a clean CrossRef 404 is followed by a DataCite lookup
before the DOI is called MISMATCH. A DOI missing from BOTH registries is still
the existing "DOI does not resolve" — DataCite resolving it counts the same as
CrossRef resolving it.

Input format (JSON list of dicts):
[
  {"label": "Tang2023_decoder",
   "pmcid": "PMC11304553",        # optional
   "pmid":  "37127759",           # optional
   "doi":   "10.1038/s41593-...", # optional (incl. arXiv DOIs 10.48550/arXiv.X)
   "arxiv": "2305.18274",         # optional; bare arXiv id (else parsed from doi)
   "title": "Semantic reconstruction ...",  # optional, used as fallback search
   "expect_first_author": "Tang J",  # optional; as reported (any shape), checked by surname
   "expect_year": "2023"             # optional; if given, will be checked
  },
  ...
]

Run:  python3 verify.py < input.json > report.json
Or:   python3 verify.py --citations input.json --out report.json
Or:   python3 verify.py --rows rows.json --out report.json    # straight from the live table

With --rows the citation list is derived from rows.json (rows_to_citations):
label = the row key, doi from `doi`/`link`, and the expected first author, year
and title from the SEARCH AGENT's claim (`search_author` / `search_year` /
`search_title`), and once the row is canonical from its `apa` as well (both must
agree with the record) — so a project needs no converter script, and a
pre-canon table is not verified against its own empty `apa`.

A lookup that fails transiently is retried once more at the end of the run,
after a cool-down (--retry-wait). To re-check a few rows later:
      python3 verify.py --rows rows.json --retry-from report.json --out report.json
re-verifies only the rows that were not OK and splices them back into the report
(--only A-01,B-02 names rows explicitly).
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse

import common
from common import arxiv_id_of, http_json, set_user_agent

PHASE = "3"   # pipeline phase, read by tools/gen_docs.py for the tool index

# The transient-vs-miss split is shared with common.http()'s backoff, so an
# exhausted-backoff failure is reported as ERROR, never mistaken for a NOT-FOUND
# (which the workflow treats as 'chase down / likely fake').
_TRANSIENT_HTTP = common.TRANSIENT_HTTP
_is_transient = common.is_transient
_norm_arxiv = common.norm_arxiv

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _esummary(db, uid):
    """One NCBI esummary record (PMC or PubMed) as a found-record, or None.

    The id is percent-encoded for the URL but NOT for the result lookup: NCBI
    keys `result` by the id as sent, so quoting the key too would miss on any
    id that actually needed encoding.
    """
    uid = str(uid)
    d = http_json(f"{_EUTILS}/esummary.fcgi?db={db}&id={urllib.parse.quote(uid)}&retmode=json")
    r = (d.get("result") or {}).get(uid)
    if not r or "uid" not in r:
        return None
    return {
        "title": r.get("title", ""),
        "year": (r.get("pubdate", "") or "")[:4],
        "first_author": (r.get("authors") or [{"name": ""}])[0].get("name", ""),
        "journal": r.get("source", ""),
    }


def lookup_pmc(pmcid):
    # Upper-case before stripping: a lower-case "pmc123" does not match "PMC",
    # so the prefix survived, esummary got a malformed id, and a real paper came
    # back unverifiable.
    return _esummary("pmc", pmcid.upper().replace("PMC", ""))


def lookup_pubmed_id(pmid):
    return _esummary("pubmed", pmid)


def lookup_pubmed_title(title):
    q = urllib.parse.quote_plus(title)
    d = http_json(f"{_EUTILS}/esearch.fcgi?db=pubmed&term={q}&retmode=json&retmax=2")
    ids = d.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return None
    return lookup_pubmed_id(ids[0])


def lookup_crossref(doi):
    """CrossRef's record for `doi`, or DataCite's on a clean CrossRef miss —
    Zenodo/figshare/OSF/Dryad software and data-set (and some preprint) DOIs are
    registered with DataCite, not CrossRef, so a CrossRef 404 there is "wrong
    registry", not "does not exist". The found record's `source` is "datacite"
    in that case (verify_one reads it to label the verdict); a record found
    directly in CrossRef carries no `source` key.

    Let a transient failure from EITHER registry propagate (verify_one reports
    it as ERROR); a clean miss from BOTH returns None — the existing "DOI does
    not resolve" MISMATCH (I1) is unchanged: a DOI row is OK only if the DOI
    itself resolved and matched, and DataCite resolving it counts the same as
    CrossRef resolving it. Swallowing everything to None — as this once did —
    hides rate-limiting as a false "not in CrossRef".

    Only a CrossRef HTTPError 404 falls back to DataCite, and only a DataCite
    404 is a clean miss — the same condition references._crossref_or_datacite
    uses; any other error (a 400, an unreadable body) propagates, and
    verify_all records it as ERROR rather than a verdict.
    """
    try:
        r = common.crossref_work(doi)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        r = None
    if r:
        return _registry_found(r)
    try:
        r = common.datacite_work(doi)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        return None
    if not r:
        return None
    rec = _registry_found(r)
    rec["source"] = "datacite"
    return rec


def _registry_found(r):
    """A CrossRef/DataCite record -> the found-record shape, carrying
    `first_author_unsplit` (the registry did not deposit the first author as a
    family name and a given name, so first_author is not a trusted "Family I":
    a whole name, a guessed split, or not the first author) for _author_issue."""
    rec = {k: r[k] for k in ("title", "year", "first_author", "journal")}
    if r.get("first_author_unsplit"):
        rec["first_author_unsplit"] = True
    return rec


def _found_record(entry):
    """arXiv entry (from common.arxiv_entries) -> the found-record shape. arXiv
    gives a display name ("Aaron van den Oord"); it is split (particles kept with
    the surname) into the "Family G" shape every other source uses. A display name
    with a capitalized word that is not initials ("CHEN Hao") may be family-first,
    so its split is not trusted: the record is flagged first_author_unsplit."""
    raw = name = entry["first_author"] or ""
    if not common.is_group(name):
        fam, giv = common.split_name(" ".join(common.strip_suffixes(name.split())))
        name = f"{fam} {giv[:1]}".strip()
    rec = {"title": entry["title"], "year": entry["year"], "first_author": name, "journal": "arXiv"}
    if any(len(w) >= 2 and w.isalpha() and w.isupper() and not common.is_initials(w)
           for w in (t.replace(".", "").replace("-", "") for t in raw.split())):
        rec["first_author_unsplit"] = True
    return rec


def lookup_arxiv_batch(aids, chunk=50, sleep=3.0):
    """Resolve many arXiv ids in a handful of requests (common.arxiv_batch).
    arXiv asks for a ~3s courtesy interval and rate-limits hard, so
    one-request-per-paper gets the IP temporarily banned on a big run — the
    whole reason a batch of real papers can come back as false NOT-FOUNDs.

    Returns (results, errored): `results[norm_id]` is the found-record or None
    (a genuine miss), and `errored` is the set of ids whose chunk failed
    (reported as ERROR, not NOT-FOUND, so they get re-run)."""
    entries, errored = common.arxiv_batch(aids, chunk=chunk, sleep=sleep)
    uniq = dict.fromkeys(_norm_arxiv(a) for a in aids if a)
    results = {a: (_found_record(entries[a]) if a in entries else None)
               for a in uniq if a not in errored}
    return results, errored


# A generational suffix PubMed puts after the initials ("Hagler DJ Jr", "Smith EL 3rd").


class Ambiguous(str):
    """claim_surname's answer for a form that cannot be read safely: a mixed-case
    word followed by a 3-4 letter capitalized WORD ("Hao CHEN" is given name +
    surname, "Collins AGE" is surname + initials; nothing tells them apart). The
    author check fails closed on it: a human confirms by hand."""


def _has_lower(tok):
    return any(ch.islower() for ch in tok)


def _caps_word(tok):
    """A 3-4 letter capitalized token that is a word, not initials ("CHEN", "AGE")."""
    letters = tok.replace(".", "").replace("-", "")
    return 3 <= len(letters) <= 4 and letters.isalpha() and letters.isupper() and not common.is_initials(tok)


def _full_name(toks):
    """A whole name rather than a bare family: words then initials ("Smith JL")
    or initials then a word ("K. Jones")."""
    if len(toks) < 2:
        return False
    if common.words_then_initials(toks):
        return True
    k = 0
    while k < len(toks) and common.is_initials(toks[k]):
        k += 1
    return 0 < k < len(toks) and all(len(t) >= 2 and not common.is_initials(t) for t in toks[k:])


def _claim_shape(name):
    """A CLAIMED first author -> (family, given words, ambiguous). See claim_surname."""
    name = re.sub(r"\s*(?:,?\s*et al\.?|&.*)$", "", str(name or "").split(";")[0].strip())
    if not common.is_group(name):
        name = re.split(r"(?i)\s+and\s+", name)[0].strip()   # a list: "Smith J and Jones K"
    if not name:
        return "", [], False
    if "," in name:
        first = name.split(",", 1)[0].strip()
        ft = first.split()
        if _full_name(ft):
            return _claim_shape(first)   # a list: "Smith JL, Jones K" -> its first name
        # family-first: "Smith, J. L.", "Lambon Ralph, Matthew A."
        return first, [], len(ft) > 1 and _caps_word(ft[-1]) and any(_has_lower(t) for t in ft[:-1])
    toks = name.split()
    if len(toks) > 1 and common.is_group(name):
        return name, [], False   # a group ("ATLAS Collaboration"): its last word is no surname
    toks = common.strip_suffixes(toks)
    split = common.words_then_initials(toks)   # particles are words even in capitals
    if split:
        return split[0], [], False
    if len(toks) > 1 and all(common.is_initials(t) for t in toks):
        return toks[0], [], False   # all-caps PubMed: "LI J", "O K"
    first = toks[0].replace("-", "")
    if (len(toks) > 1 and first.isalpha() and first.isupper() and not common.is_initials(toks[0])
            and toks[0].lower() not in common.PARTICLES and all(_has_lower(t) for t in toks[1:])):
        return toks[0], [], False   # a surname in capitals, then given names: "CHEN Hao" (never "VAN")
    if len(toks) > 1 and _caps_word(toks[-1]) and any(_has_lower(t) for t in toks[:-1]):
        return name, [], True       # "Hao CHEN" or "Collins AGE": which is the surname?
    if len(toks) > 1 and toks[0].lower() in common.PARTICLES:
        return " ".join(toks), [], False   # opens with a particle: already a surname ("de Lange Dzn")
    if len(toks) > 1 and not any(common.is_initials(t) or sum(ch.isalpha() for ch in t) < 2 for t in toks):
        return toks[-1], toks[:-1], False   # given-first words: "John Smith", "Lambon Ralph"
    # the last token that is not an initial, and never a single letter while a
    # longer word exists ("Kowalski ł" -> Kowalski)
    parts = [p for p in toks if not (len(p.rstrip(".")) == 1 and p.endswith("."))] or toks
    longer = [p for p in parts if sum(ch.isalpha() for ch in p) >= 2]
    return (longer or parts)[-1], [], False


def claim_surname(name):
    """Surname out of whatever shape a search agent reported a first author in:
    'Gilbert, C. D.' / 'C. D. Gilbert' / 'Gilbert CD' / 'Gilbert' -> 'Gilbert'.
    A list gives its first name ("Smith J; Jones K", "Smith J and Jones K",
    "Smith JL, Jones K"). A comma
    otherwise means family-first ("Lambon Ralph, Matthew A." -> Lambon Ralph); so
    do words followed only by unambiguous initials ('Smith J', 'Smith JLK',
    'Smith J.-L.', 'Van Essen DC', PubMed style), which give all the words, and an
    all-caps form made only of initials-shaped tokens ('LI J', 'O K'), which gives
    its first token; a capitalized word before given names ('CHEN Hao') is the
    surname. A trailing 'Jr'/'Sr'/'3rd' is dropped; a name opening with a particle
    ('de Lange Dzn') or a group name (common.is_group) is returned whole. Words
    with no initials ('John Smith') give the last word, the rest being given names
    (see surname_agrees). A mixed-case word before a 3-4 letter capitalized word
    ('Hao CHEN', 'Collins AGE') is ambiguous: an Ambiguous marker is returned.
    Otherwise the last token that is not an initial."""
    fam, _, ambiguous = _claim_shape(name)
    return Ambiguous(str(name).strip()) if ambiguous else fam


def rows_to_citations(rows, keyf=None):
    """rows.json -> the citation list this tool verifies.

    The expectations must be an INDEPENDENT claim. Before canon a row's `apa` is
    empty (references.py fills it from the very DOI being checked), so a row is
    checked against what the search agent reported (`search_author` /
    `search_year` / `search_title`). A canonical row (`canonical_at`) with that
    claim is checked against BOTH the claim and its canonical `apa`
    (`alt_expect`): the apa alone was built from the very DOI being checked, so
    it cannot re-establish that the DOI is the intended paper. A canonical row
    with no claim is checked against its apa only, and the stamp records
    `claim_basis: "canonical-apa"` so the audit asks a human to confirm it.
    Rows with neither yield no expectations and verify as UNCHECKED."""
    keyf = keyf or common.key_field(rows)
    out = []
    for r in rows:
        apa = r.get("apa", "") or ""
        claim = any(r.get(k) for k in ("search_author", "search_year", "search_title"))
        p = common.parse_apa(apa)
        from_apa = {"title": p["title"] if p else "",
                    "expect_surname": common.lead_surname(apa) if apa else "",
                    "expect_year": str(p["year"]) if p else ""}
        if claim:
            c = {"title": r.get("search_title") or "",
                 "expect_first_author": (r.get("search_author") or "").strip(),
                 "expect_year": str(r.get("search_year") or "")}
            if r.get("canonical_at") and any(from_apa.values()):
                c["alt_expect"] = from_apa
                c["claim_basis"] = "search+canonical-apa"
        else:
            c = dict(from_apa)
            if r.get("canonical_at") and apa:
                c["claim_basis"] = "canonical-apa"
        c = {"label": r.get(keyf, "?"), "doi": common.doi_of(r), "arxiv": r.get("arxiv"), **c}
        for k in ("pmid", "pmcid"):
            if r.get(k):
                c[k] = str(r[k])
        out.append(c)
    return out


def select_citations(cits, only=None, retry_from=None):
    """The citations to (re-)verify: those labeled in `only`, and/or those whose
    verdict in a previous report (`retry_from`) was anything but OK."""
    keep = set(only or ())
    if retry_from is not None:
        keep |= {r.get("label") for r in retry_from if r.get("verdict") != "OK"}
    if only is None and retry_from is None:
        return list(cits)
    return [c for c in cits if c.get("label") in keep]


def merge_reports(old, new):
    """Splice re-verified results into an earlier report: same order, each label
    replaced by its newer verdict, unseen labels appended."""
    by = {r.get("label"): r for r in new}
    out = [by.pop(r.get("label"), r) for r in old]
    return out + list(by.values())


def stamp_rows(rows, results, keyf, asof):
    """Write each result onto its row as `verified` (every verdict, not only OK,
    so the audit can name an unresolved MISMATCH). Returns the number stamped.
    Pass only results verified in THIS run: a verdict copied from an older
    report may be for ids the row no longer has.

    Exception: when the row already carries an OK stamp for its CURRENT ids
    that was NOT based on claim_basis "canonical-apa" (an independent check —
    a search claim, or an apa that predates canon), and the new result is OK
    but only re-establishes claim_basis "canonical-apa" (the row was
    canonicalized since, so its apa is now built from this same DOI), the
    earlier independent stamp is kept rather than overwritten -- re-verifying
    a canonical row must not downgrade an independent verification into a
    circular one. `reverified_at` records that the re-run happened."""
    by = {r.get("label"): r for r in results}
    n = 0
    for row in rows:
        res = by.get(row.get(keyf))
        if res is None:
            continue
        doi, aid = common.ids_of(row)
        existing = row.get("verified")
        if (isinstance(existing, dict) and existing.get("verdict") == "OK"
                and existing.get("claim_basis") != "canonical-apa"
                and common.stamp_ids(existing) == (doi, aid)
                and res.get("verdict") == "OK" and res.get("claim_basis") == "canonical-apa"):
            existing["reverified_at"] = asof
            n += 1
            continue
        row["verified"] = {"verdict": res.get("verdict"), "doi": doi, "arxiv": aid,
                           "source": res.get("source"), "issues": list(res.get("issues") or []), "at": asof}
        if res.get("claim_basis"):
            row["verified"]["claim_basis"] = res["claim_basis"]
        n += 1
    return n


def override(rows, keyf, ref, reason, asof):
    """Clear a false alarm (e.g. a preprint retitled on publication) on the record.
    Refused without a stamp, when the ids changed since verification, or without a reason."""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("--override needs a non-empty --reason")
    row = next((r for r in rows if r.get(keyf) == ref), None)
    if row is None:
        raise ValueError(f"no row {ref!r}")
    st = row.get("verified")
    if not isinstance(st, dict):
        raise ValueError(f"{ref} has no verify stamp; run verify.py --rows first")
    if common.stamp_ids(st) != common.ids_of(row):
        raise ValueError(f"{ref}'s DOI/arXiv id changed since it was verified; re-verify it")
    doi, aid = common.ids_of(row)
    row["verify_override"] = {"reason": reason, "overrode": st.get("verdict"),
                              "doi": doi, "arxiv": aid, "at": asof}


# Title agreement lives in common (title_agrees requires two-way agreement,
# unlike title_score's one-way containment, which merge_lanes and handcheck
# still use for their own deferral/candidate matching). Calibrated on 2,473 OK
# verdicts from five corpora: at 0.5, 2 past OK verdicts fall below it. See
# common.title_agrees for the full calibration note.
title_agrees = common.title_agrees


TITLE_MIN = 0.5


def _name_tokens(name):
    """Lowercased, accent-folded word tokens of a name, a leading "the" dropped
    ("The pandas development team" -> pandas, development, team). Only "the":
    "An" and "A" are real surnames ("An J"), and a group name opens with "The"."""
    toks = re.findall(r"[\w'-]+", common.fold(str(name or "")))
    return toks[1:] if len(toks) > 1 and toks[0] == "the" else toks


def _hyphen_parts(tok):
    """The 2+ letter parts of a hyphenated token ("andrews-hanna" -> andrews, hanna)."""
    return {p for p in tok.split("-") if len(p) >= 2} if "-" in tok else set()


def _core(surname):
    """A surname's tokens without nobiliary particles ("van den Heuvel" -> heuvel);
    one made only of particles ("Le") keeps them."""
    toks = _name_tokens(surname)
    return [t for t in toks if t not in common.PARTICLES] or toks


def _tok_agrees(a, t):
    """Whole-word agreement, or a 2+ letter part of a hyphenated t ("hanna" / "andrews-hanna")."""
    return a == t or a in _hyphen_parts(t)


def _caps_short(tok):
    """1-4 capitals, dotted or hyphenated: in a mixed-case record ("Collins AGE")
    such a trailing token can only be initials."""
    letters = tok.replace(".", "").replace("-", "")
    return 1 <= len(letters) <= 4 and all(ch.isalpha() and ch.isupper() for ch in letters)


def _record_parts(first_author):
    """A RECORD's first_author -> (family, trailing initials tokens), by the source
    contract rather than the claim heuristics: every record is "Family INITIALS"
    (CrossRef and DataCite build f"{fam} {giv[:1]}", PubMed esummary gives
    "Collins AGE", arXiv is normalized by _found_record). After suffixes, exactly
    one trailing token is stripped if it is initials or, in a mixed-case record,
    any all-caps token of <= 4 letters ("Van DAM J" -> Van DAM); the rest is the
    family. A group is whole."""
    name = str(first_author or "").strip()
    toks = name.split()
    if len(toks) > 1 and common.is_group(name):
        return name, []
    toks = common.strip_suffixes(toks)
    mixed = any(ch.islower() for t in toks for ch in t)
    # exactly ONE trailing token is the initials: "Van DAM J" is Van DAM, not Van
    if len(toks) > 1 and (common.is_initials(toks[-1]) or (mixed and _caps_short(toks[-1]))):
        return " ".join(toks[:-1]), toks[-1:]
    return " ".join(toks), []


def record_surname(first_author):
    """The family of a record's first_author ("Collins AGE" -> Collins, "VAN DER
    MEER J" -> VAN DER MEER); see _record_parts."""
    return _record_parts(first_author)[0]


def _parsed_record(first_author):
    """A record's family tokens (_core); [] for none; None when unknown."""
    if not str(first_author or "").strip():
        return []
    fam = record_surname(first_author)
    if common.is_unknown_name(first_author) or common.is_unknown_name(fam):
        return None
    return _core(fam) or None


def _claim_parts(name, is_surname=False):
    """A claim -> (family tokens, given-name tokens); ([], []) for no claim; None
    when unknown ("?", "anon", no readable surname); "ambiguous" for an Ambiguous
    form. An apa-derived lead surname (`is_surname`) is used as-is."""
    if not str(name or "").strip():
        return [], []
    if common.is_unknown_name(name):
        return None
    fam, given, ambiguous = (str(name).strip(), [], False) if is_surname else _claim_shape(name)
    if ambiguous:
        return "ambiguous"
    if common.is_unknown_name(fam):
        return None   # a placeholder once parsed: "Anonymous, A.", "Unknown, U."
    core = _core(fam)
    if not core:
        return None
    return core, [t for w in given for t in _name_tokens(w) if t not in common.PARTICLES]


def is_unknown(name):
    """True for a given name that cannot be read as a surname: unknown or ambiguous."""
    return bool(str(name or "").strip()) and _claim_parts(name) in (None, "ambiguous")


def _caps_particle(claim):
    """For a claim led by a particle in capitals ("DU Wei", "LE Minh", "VAN Essen",
    "VAN DAM"), (the particle, the family-first reading: family = the particle,
    given names = the rest); else None. Read family-first the surname is the
    particle itself ("Du", given Wei), otherwise a particle surname ("Du Wei");
    either way the record must carry the particle."""
    name = re.sub(r"\s*(?:,?\s*et al\.?|&.*)$", "", str(claim or "").split(";")[0].strip())
    toks = name.split()
    if "," in name or len(toks) < 2:
        return None
    first = toks[0].replace(".", "")
    if not (len(first) >= 2 and first.isalpha() and first.isupper() and first.lower() in common.PARTICLES):
        return None
    given = [t for w in toks[1:] for t in _name_tokens(w) if t not in common.PARTICLES]
    return first.lower(), ([first.lower()], given)


def _agrees(claim, pc, record, r):
    """surname_agrees on a parsed claim `pc` and parsed record family `r`."""
    c, given = pc
    if not c or not r:
        return True
    if common.is_group(claim) or common.is_group(record):
        return set(c) == set(r)   # a group compares whole: "CMS Collaboration" is not "ATLAS Collaboration"
    fam, tail = _record_parts(record)
    full = _name_tokens(fam) + _name_tokens(" ".join(tail))
    letters = {common.fold(ch).lower() for t in tail for ch in t if ch.isalpha()}
    return (any(_tok_agrees(c[0], t) for t in r)
            and all(any(_tok_agrees(x, t) for t in full) for x in c[1:])
            and all(any(_tok_agrees(w, t) for t in r) or w[:1] in letters for w in given))


def surname_agrees(claim, record, claim_is_surname=False):
    """True when the claimed first author agrees with the record's (a first_author
    in the source contract's "Family INITIALS" shape, see _record_parts); None when
    either is unknown or the claim is ambiguous: those never agree. The claim is
    parsed once by _claim_shape -- unless `claim_is_surname` (an apa-derived lead
    surname, used as-is) -- so initials never take part. The claim's first
    non-particle family word must agree with a word of the record's family; any
    further claim family word ("Lambon Ralph", "de Lange Dzn") must appear in the
    record's name; and a claim's given names ("John Smith") must each be a word
    of the record's family or start with one of its initials. A group author
    (common.is_group) compares whole: all its words must match. A claim led by a
    capitalized particle ("DU Wei") matches only a record carrying that particle,
    read either as the particle surname or family-first ("DU, Wei")."""
    pc, r = _claim_parts(claim, claim_is_surname), _parsed_record(record)
    if pc is None or pc == "ambiguous" or r is None:
        return None
    cp = None if claim_is_surname else _caps_particle(claim)
    if cp:
        if cp[0] not in _name_tokens(record):
            return False
        # the family-first reading keeps its given names, so they must agree with the
        # record's initials ("DU Wei" / "Du W" yes; "VAN Essen" / "Van J" no)
        return _agrees(claim, pc, record, r) or _agrees(claim, cp[1], record, r)
    return _agrees(claim, pc, record, r)


def _claims_key_agree(a, pa, b, pb):
    ca, cb = pa[0], pb[0]
    if not ca or not cb:
        return True
    if common.is_group(a) or common.is_group(b):
        return set(ca) == set(cb)
    return any(_tok_agrees(ca[0], t) for t in cb) or any(_tok_agrees(cb[0], t) for t in ca)


def claims_agree(a, b):
    """Two CLAIMED first authors (neither is a record) name the same surname: the
    first family word of either agrees with a family word of the other (a group
    compares whole); None when either is unknown or ambiguous. A claim led by a
    capitalized particle ("DU Wei") agrees only with one carrying that particle.
    merge_lanes uses it to tell a duplicate from two papers sharing a title ("An,
    J." is not "Chan, H.")."""
    pa, pb = _claim_parts(a), _claim_parts(b)
    if pa in (None, "ambiguous") or pb in (None, "ambiguous"):
        return None
    readings_a, readings_b = [(a, pa)], [(b, pb)]
    for x, y, readings in ((a, b, readings_a), (b, a, readings_b)):
        cp = _caps_particle(x)
        if cp:
            if cp[0] not in _name_tokens(y):
                return False
            readings.append((x, cp[1]))
    return any(_claims_key_agree(xa, qa, xb, qb) for xa, qa in readings_a for xb, qb in readings_b)


def _no_given_name(first_author, flagged=False):
    """True for a record first author the "Family INITIALS" contract cannot be
    trusted to read: flagged by the registry (`first_author_unsplit`: not
    deposited as family + given name), a bare name of two or more words that ends in no
    initial ("Hae-Jeong Park", "Richard Ngo"), or one that ends in "JR"/"SR" after
    two or more words ("John Smith JR"). A one-word name or a group
    has no given name to mistake for the surname, so it is compared as usual."""
    name = str(first_author or "").strip()
    if common.is_group(name):
        return False
    toks = common.strip_suffixes(name.split())
    if len([t for t in toks if re.search(r"[^\W\d_]", t) and t.lower() not in common.PARTICLES]) < 2:
        return False
    if toks[-1] in ("JR", "SR") and len([t for t in toks[:-1] if t.lower() not in common.PARTICLES]) >= 2:
        return True   # "John Smith JR": a given-first name + suffix, or a compound family + initials?
    return bool(flagged) or not _record_parts(name)[1]


def _author_issue(c, rec, where=""):
    # Surname against surname (surname_agrees): "J. Smith" cannot match "Jones J"
    # on the J, "Min" cannot match "Seung-Min Park", "Lee" cannot match "Leeson".
    # A claim is either `expect_first_author` (what a search agent or a
    # --citations file reported, parsed here once) or `expect_surname` (the lead
    # surname of the row's apa, used as-is); the record is parsed by its source
    # contract (_record_parts). An unknown name on either side ("?", "anon", no
    # readable word), or an ambiguous claim ("Hao CHEN"), is an issue: it can
    # confirm nothing.
    # Calibrated on the same OK verdicts as the title check, with each claim
    # rebuilt as rows_to_citations now builds it: 9 of 2,471 are flagged (5 were
    # already, a group author against a person or a mangled name; 4 are a compound
    # surname the record shortened, "Quian Quiroga" / "Quiroga R", which a human
    # confirms). Of 103,760 random claim x record pairs, and of 353,564 probe
    # pairs and claim agreements, none that an earlier version rejected passes,
    # except where a ruling requires the match (see the round-5 fix report).
    is_surname = bool(str(c.get("expect_surname") or "").strip())
    claim = c.get("expect_surname") if is_surname else c.get("expect_first_author")
    got = str(rec.get("first_author") or "")
    if not str(claim or "").strip() or not got.strip():
        return []
    pc = _claim_parts(claim, is_surname)
    if pc is None:
        return [f"{where}first-author mismatch: could not read the claimed first author "
                f"'{claim}' (got '{got}')"]
    if pc == "ambiguous":
        return [f"{where}first-author mismatch: ambiguous first-author form ('{claim}'); confirm by hand"]
    if _parsed_record(got) is None:
        return [f"{where}first-author mismatch: could not read the record's first author "
                f"'{got}' (expected '{claim}')"]
    if _no_given_name(got, rec.get("first_author_unsplit")):
        return [f"{where}first-author mismatch: the record's first author was not deposited as a family "
                f"name and a given name ('{got}'); confirm by hand"]
    if not surname_agrees(claim, got, is_surname):
        return [f"{where}first-author mismatch: expected '{claim}', got '{got}'"]
    return []


def _title_issue(c, rec, where=""):
    s = title_agrees(c.get("title"), rec.get("title"))
    if s is not None and s < TITLE_MIN:
        return [f"{where}title mismatch ({s:.2f}): expected '{c['title'][:80]}', "
                f"got '{rec['title'][:80]}'"]
    return []


def _year_issue(c, recs):
    """Year within ±1 of ANY of the records (a preprint and its version of record
    legitimately differ, and the agent may have reported either)."""
    expect_year = str(c.get("expect_year") or "").strip()
    years = [(r.get("year") or "").strip() for r in recs]
    # Guard the int() — a human-typed "in press"/"2023a" must not crash the run;
    # compare numerically only when both years are clean 4-digit values.
    clean = [int(y) for y in years if y.isdigit()]
    if expect_year.isdigit() and clean and all(abs(int(expect_year) - y) > 1 for y in clean):
        return [f"year mismatch: expected {expect_year}, got {'/'.join(years)}"]
    return []


def _claim_issues(c, found, journal=None):
    """Every way the record(s) disagree with the expectations in `c`."""
    if journal is not None:
        # Both ids: the journal record is what canon prints, so it gets the full
        # check; the preprint gets the author check (preprints are often retitled
        # on publication, so its title is not held against the claim).
        return (_author_issue(c, journal, "journal DOI: ") + _title_issue(c, journal, "journal DOI: ")
                + _author_issue(c, found, "arXiv: ") + _year_issue(c, [journal, found]))
    return _author_issue(c, found) + _year_issue(c, [found]) + _title_issue(c, found)


def verify_one(c, arxiv_results=None, arxiv_errored=None):
    """Try lookups in priority order and return result + verdict.

    arXiv papers route to the arXiv API FIRST (CrossRef has no arXiv DOIs and a
    PubMed title-search mis-resolves them), so they get a real verdict instead of
    a misleading NOT-FOUND/MISMATCH. arXiv ids are resolved from `arxiv_results`
    (prefetched in batch by main); `arxiv_errored` holds ids whose batch failed.

    A lookup that fails transiently (rate-limit / network) yields verdict ERROR,
    kept strictly distinct from NOT-FOUND — a throttled fetch must never read as
    'this paper does not exist' and get dropped."""
    arxiv_results = arxiv_results or {}
    arxiv_errored = arxiv_errored or set()
    found = None
    src = None
    errored = False          # a lookup could not complete (not a clean miss)

    aid = arxiv_id_of(c)
    if aid:
        na = _norm_arxiv(aid)
        if na in arxiv_errored:
            # arXiv is the only authority for this id. CrossRef has no 10.48550
            # DOIs and a PubMed title search mis-resolves arXiv papers, so asking
            # them is pure cost; the retry pass re-asks arXiv instead.
            return {"verdict": "ERROR", "found": None, "source": None,
                    "issues": ["arXiv lookup failed (rate-limit/network) — re-run to verify"]}
        elif na in arxiv_results:
            if arxiv_results[na]:
                found, src = arxiv_results[na], "arxiv"
        else:                # standalone/uncached call: resolve just this id
            res, err = lookup_arxiv_batch([aid])
            if na in err:
                return {"verdict": "ERROR", "found": None, "source": None,
                        "issues": ["arXiv lookup failed (rate-limit/network) — re-run to verify"]}
            elif res.get(na):
                found, src = res[na], "arxiv"
    doi = c.get("doi") or ""
    is_arxiv_doi = bool(common.ARXIV_DOI.match(doi))
    journal = None           # the journal record, when a row carries both ids
    if found and doi and not is_arxiv_doi:
        # references.py cites the JOURNAL DOI over the preprint, so an arXiv hit
        # alone does not verify what will be printed: check the DOI as well.
        try:
            journal = lookup_crossref(doi)
        except Exception as e:
            if _is_transient(e):
                return {"verdict": "ERROR", "found": found, "source": "arxiv",
                        "issues": ["journal DOI lookup failed (rate-limit/network) — re-run to verify"]}
            raise
        if journal is None:
            return {"verdict": "MISMATCH", "found": found, "source": "arxiv",
                    "issues": [f"journal DOI {doi} not found in CrossRef (the arXiv id resolves)"]}
    doi_missing = False      # the row's journal DOI is a clean miss in CrossRef
    if not found and doi and not is_arxiv_doi:
        # A journal DOI is what canon prints, so only its OWN record can verify
        # it. Checked first, and a PMC/PMID/title hit never stands in for it: a
        # fabricated DOI attached to a real title once verified OK that way.
        try:
            found = lookup_crossref(doi)
        except Exception as e:
            if not _is_transient(e):
                raise
            return {"verdict": "ERROR", "found": None, "source": None,
                    "issues": ["DOI lookup failed (rate-limit/network) — re-run to verify"]}
        if found:
            src = found.get("source") or "doi"      # "datacite" when CrossRef missed
        else:
            doi_missing = True
    if not found:
        for fn, key in [(lookup_pmc, "pmcid"), (lookup_pubmed_id, "pmid")]:
            if c.get(key):
                try:
                    r = fn(c[key])
                except Exception as e:
                    if _is_transient(e):
                        errored = True
                    continue
                if r:
                    found, src = r, key
                    break
    if not found and c.get("title"):
        try:
            found = lookup_pubmed_title(c["title"])
            src = "title-search"
        except Exception as e:
            if _is_transient(e):
                errored = True

    if not found:
        # ERROR (a lookup could not complete) vs NOT-FOUND (every lookup completed
        # and none matched) — surfaced separately so transient failures are re-run,
        # not waved through as nonexistent.
        if errored:
            return {"verdict": "ERROR", "found": None, "source": None,
                    "issues": ["lookup failed (rate-limit/network) — re-run to verify"]}
        return {"verdict": "NOT-FOUND", "found": None, "source": None}

    if doi_missing:
        return {"verdict": "MISMATCH", "found": found, "source": src,
                "issues": [f"DOI {doi} does not resolve; {src} found '{(found.get('title') or '')[:80]}'"]}

    if not any(str(c.get(k) or "").strip()
               for k in ("expect_first_author", "expect_surname", "expect_year", "title")):
        # Nothing to compare: the DOI resolves, which proves only that it exists.
        # Reporting that as OK is how a pre-canon table once passed with every
        # expectation blank (see rows_to_citations).
        return {"verdict": "UNCHECKED", "found": found, "source": src,
                "issues": ["no expected author/year/title to check the record against"]}

    issues = _claim_issues(c, found, journal)
    if c.get("alt_expect"):
        # a canonical row: its apa must agree with the record as well as the claim
        issues += ["canonical apa: " + i for i in _claim_issues(dict(c, **c["alt_expect"]), found, journal)]
    if journal is not None:
        return {"verdict": "OK" if not issues else "MISMATCH", "issues": issues,
                "found": journal, "source": "arxiv+" + (journal.get("source") or "doi")}

    if issues and errored and src == "title-search":
        # The authoritative lookup (DOI/PMID) could not complete and the fallback
        # title search returned something that does not match the claim. That is
        # almost always an unrelated PubMed hit standing in for a throttled
        # CrossRef call, so report ERROR (re-run), not MISMATCH (agent was wrong).
        # A fallback hit that DOES match the claim is still accepted above.
        return {"verdict": "ERROR", "found": found, "source": src,
                "issues": ["lookup failed (rate-limit/network); title-search fallback did not "
                           "match the claim — re-run to verify"] + issues}
    return {
        "verdict": "OK" if not issues else "MISMATCH",
        "issues": issues,
        "found": found,
        "source": src,
    }


def gate_code(results):
    """Exit status for a verify run: 0 only when every verdict is OK.

    verify is the Phase-3 fabrication gate; like references.py --audit and
    cite_check.py it must fail loud, or a chained run (`verify.py && ...`)
    sails past a table full of MISMATCH/NOT-FOUND/ERROR verdicts."""
    return 0 if all(r.get("verdict") == "OK" for r in results) else 1


def _print_result(c, r):
    v = r["verdict"]
    au = r["found"]["first_author"] if r["found"] else "?"
    yr = r["found"]["year"] if r["found"] else "?"
    ti = (r["found"]["title"] if r["found"] else "")[:60]
    print(f"  [{v:9s}] {c.get('label','?')}  →  {au} ({yr})  {ti}", file=sys.stderr)
    for i in r.get("issues") or []:
        print(f"             ↳ {i}", file=sys.stderr)


def _verify_pass(cits, sleep, chunk=50):
    # Prefetch every arXiv id in a few batched requests. arXiv rate-limits a
    # per-paper loop into a temporary ban (its retries exhaust and the paper
    # falls through to a false NOT-FOUND), so batching is both faster and the fix
    # for that failure mode; ids whose chunk failed come back as ERROR, not miss.
    aids = [a for a in (arxiv_id_of(c) for c in cits) if a]
    arxiv_results, arxiv_errored = ({}, set())
    if aids:
        print(f"  [arxiv] batch-resolving {len(set(_norm_arxiv(a) for a in aids))} ids…", file=sys.stderr)
        arxiv_results, arxiv_errored = lookup_arxiv_batch(aids, chunk=chunk)
    out = []
    for c in cits:
        before = common.request_count()
        try:
            r = verify_one(c, arxiv_results, arxiv_errored)
        except Exception as e:
            # One malformed row must not abort a long batch — record and move on.
            r = {"verdict": "ERROR", "found": None, "source": None,
                 "issues": [f"{type(e).__name__}: {e}"]}
        r["label"] = c.get("label", "?")
        if c.get("claim_basis"):
            r["claim_basis"] = c["claim_basis"]      # stamp_rows records what the verdict rests on
        out.append(r)
        _print_result(c, r)
        if common.request_count() != before:
            time.sleep(sleep)      # courtesy pause only after a row that hit the network
    return out


def verify_all(cits, sleep=0.4, retry_wait=60.0):
    """Verify every citation, then give each ERROR one more try after a
    cool-down (smaller arXiv chunks). Returns results in input order."""
    out = _verify_pass(cits, sleep)
    again = [c for c, r in zip(cits, out) if r["verdict"] == "ERROR"]
    if again:
        print(f"\n  [retry] {len(again)} ERROR row(s); cooling down {retry_wait:.0f}s, then one more try…",
              file=sys.stderr)
        time.sleep(retry_wait)
        out = merge_reports(out, _verify_pass(again, sleep, chunk=25))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--citations", help="JSON citation list (else --rows, else stdin)")
    ap.add_argument("--rows", help="verify a rows.json directly (label = row key; expectations "
                    "from the search agent's claim, plus the canonical apa after canon)")
    ap.add_argument("--key", default=None, help="row key field for --rows (default: ref, else label)")
    ap.add_argument("--out", help="JSON output file (else stdout)")
    ap.add_argument("--only", help="comma-separated labels: verify just these rows")
    ap.add_argument("--retry-from", help="an earlier report: re-verify only its non-OK rows and "
                    "splice the new verdicts into it (write with --out)")
    ap.add_argument("--sleep", type=float, default=0.4,
                    help="pause after each row that made a request (default 0.4 s)")
    ap.add_argument("--retry-wait", type=float, default=60.0,
                    help="cool-down before ERROR rows get their second try (default 60 s)")
    ap.add_argument("--no-stamp", action="store_true",
                    help="with --rows: report only, do not write `verified` onto the rows")
    ap.add_argument("--override", metavar="REF",
                    help="with --rows: record that REF's non-OK verdict is a false alarm (needs --reason)")
    ap.add_argument("--reason", help="why the --override verdict is a false alarm")
    ap.add_argument("--asof", default=datetime.date.today().isoformat(),
                    help="date written into stamps (default: today)")
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"),
                    help="Contact email for NCBI/CrossRef User-Agent (required; "
                         "or set LITREVIEW_EMAIL env var)")
    args = ap.parse_args()

    if args.citations and args.rows:
        ap.error("give --citations or --rows, not both")

    if args.override:
        # No network I/O, so it must not demand a contact email — check this
        # before the --email requirement below.
        if not args.rows:
            ap.error("--override needs --rows")
        rows = common.load_json(args.rows)
        try:
            override(rows, common.key_field(rows, args.key), args.override, args.reason, args.asof)
        except ValueError as e:
            ap.error(str(e))
        common.dump_json(rows, args.rows)
        print(f"recorded an override for {args.override}", file=sys.stderr)
        return

    if not args.email:
        ap.error("--email or LITREVIEW_EMAIL required "
                 "(NCBI/CrossRef expect a contact email in the User-Agent)")
    set_user_agent(args.email)

    if args.citations:
        cits = common.load_json(args.citations)
    elif args.rows:
        rows = common.load_json(args.rows)
        loaded = os.path.getmtime(args.rows)     # stamping refuses a file changed since
        cits = rows_to_citations(rows, common.key_field(rows, args.key))
    else:
        cits = json.loads(sys.stdin.read())

    prior = common.load_json(args.retry_from) if args.retry_from else None
    only = {x.strip() for x in args.only.split(",") if x.strip()} if args.only else None
    cits = select_citations(cits, only=only, retry_from=prior)
    fresh = verify_all(cits, sleep=args.sleep, retry_wait=args.retry_wait)
    out = merge_reports(prior, fresh) if prior is not None else fresh
    if args.rows and not args.no_stamp:
        n = stamp_rows(rows, fresh, common.key_field(rows, args.key), args.asof)
        common.save_rows(args.rows, rows, loaded)
        print(f"  stamped {n} row(s) in {args.rows}", file=sys.stderr)

    if args.out:
        common.dump_json(out, args.out)
    else:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    n = {v: sum(1 for r in out if r["verdict"] == v)
         for v in ("OK", "MISMATCH", "NOT-FOUND", "ERROR", "UNCHECKED")}
    tail = "".join(f" / {n[v]} {v}" for v in ("ERROR", "UNCHECKED") if n[v])
    print(f"\n=== {n['OK']} OK / {n['MISMATCH']} MISMATCH / {n['NOT-FOUND']} NOT-FOUND{tail} ===",
          file=sys.stderr)
    if n["ERROR"]:
        print("    ERROR = lookup could not complete (rate-limit/network) even after the retry; "
              "re-run with --retry-from — NOT the same as NOT-FOUND.", file=sys.stderr)
    if n["UNCHECKED"]:
        print("    UNCHECKED = the row carried no author/year/title claim, so nothing was "
              "verified; give it search_* fields or a canonical apa.", file=sys.stderr)
    sys.exit(gate_code(out))


if __name__ == "__main__":
    main()
