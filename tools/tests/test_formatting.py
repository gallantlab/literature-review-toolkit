#!/usr/bin/env python3
"""Regression tests for the reference formatter, audit gate and Phase-7 checks.

Every case here is a real defect that reached a delivered bibliography before the
check existed. Run with no arguments; no pytest required.

    python3 tools/tests/test_formatting.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cite_check  # noqa: E402
import common  # noqa: E402
import families  # noqa: E402
import families_figure  # noqa: E402
import gen_docs  # noqa: E402
import references  # noqa: E402
import review_paper  # noqa: E402
import sentence_case as sc  # noqa: E402
import spreadsheet  # noqa: E402
import verify  # noqa: E402
import xref  # noqa: E402

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}\n     got:  {got!r}\n     want: {want!r}")


def check_true(name, cond, detail=""):
    if not cond:
        FAILURES.append(f"{name}{(' — ' + detail) if detail else ''}")


# ---- build_apa / norm_title ----------------------------------------------
# CrossRef deposits JATS markup inside titles; the &amp; check cannot see a tag.
check("markup stripped from title",
      common.build_apa(["Buckner, R. L."], 2008, "<i>The Brain's Default Network</i>",
                       "Annals"),
      "Buckner, R. L. (2008). The Brain's Default Network. Annals.")
check("small-caps markup stripped",
      common.norm_title("An intensively sampled 7 Tesla <scp>MRI</scp> case study"),
      "An intensively sampled 7 Tesla MRI case study")

# A title ending in ? or ! takes no additional period (APA-7).
check("question-mark title takes no period",
      common.build_apa(["Friston, K."], 2010, "The free-energy principle: A unified brain theory?",
                       "Nat Rev Neurosci"),
      "Friston, K. (2010). The free-energy principle: A unified brain theory? Nat Rev Neurosci.")
check("ordinary title still takes a period",
      common.build_apa(["Biswal, B."], 1995, "Functional connectivity", "MRM"),
      "Biswal, B. (1995). Functional connectivity. MRM.")

# U+2010/U+2011 look like a hyphen but break matching; U+2013 must survive.
check("unicode hyphen normalized",
      common.build_apa([common.person("Andrews‐Hanna", "J. R.")], 2014, "T", "V"),
      "Andrews-Hanna, J. R. (2014). T. V.")
check_true("en dash preserved in page range",
           "1–38" in common.build_apa(["A, B."], 2008, "T", "V", 1124, 1, "1–38"))

# CrossRef folds a familiar name into the family field for some authors.
check("parenthetical nickname dropped from surname",
      common.person("(Bud) Craig", "A. D."), "Craig, A. D.")
check("real parentheses-free surname untouched",
      common.person("Lambon Ralph", "M. A."), "Lambon Ralph, M. A.")
check("uppercase surname still fixed", common.person("ANDERSON", "J."), "Anderson, J.")
# A used name in parentheses must not be initialized literally: 'L. (Renzo)'
# produced the nonsense initial '(.' and shipped as 'Huber, L. (.'
check("parenthetical used-name in given field",
      common.person("Huber", "L. (Renzo)"), "Huber, L. R.")
check("hyphenated given name still initialized",
      common.person("King", "Jean-Rémi"), "King, J.-R.")
# CrossRef folds a middle initial into the family field; a surname never starts
# with an initial, so this one is safe to repair automatically.
check("leading initial moved out of surname",
      common.person("A. Moffat", "Bradford"), "Moffat, B. A.")
check("particle surname not mistaken for an initial",
      common.person("van den Heuvel", "M. P."), "van den Heuvel, M. P.")

# ---- parse_apa: ONE grammar for the canonical string ------------------------
# Every tool that reads an `apa` back (audit, figure, digest, cite_check,
# sentence_case, duplicate scan) must agree on where the year, title and venue
# are — in particular all must accept APA-7's 2025a/2025b year suffix, which the
# gate accepts and the docs recommend. Three of them used to require a bare year.
_P = common.parse_apa("Yang, W., & Li, X. (2025a). A title: With subtitle? Venue, 1(1), 1-2.")
check("parse_apa authors", _P["authors"], "Yang, W., & Li, X.")
check("parse_apa year is an int", _P["year"], 2025)
check("parse_apa suffix", _P["suffix"], "a")
check("parse_apa title excludes its terminal mark", _P["title"], "A title: With subtitle")
check("parse_apa terminal mark", _P["terminal"], "?")
check("parse_apa rest keeps its leading space (for exact reassembly)", _P["rest"], " Venue, 1(1), 1-2.")
check("parse_apa reassembles the original",
      _P["head"] + _P["title"] + _P["terminal"] + _P["rest"],
      "Yang, W., & Li, X. (2025a). A title: With subtitle? Venue, 1(1), 1-2.")
check("parse_apa without a year is None", common.parse_apa("Yang, W. Title. Venue."), None)
_Q = common.parse_apa("Biswal, B. (1995). Functional connectivity")
check("parse_apa tolerates a bare title with no venue", (_Q["title"], _Q["terminal"], _Q["rest"]),
      ("Functional connectivity", "", ""))
check("lead_surname keeps a particle surname", common.lead_surname("van den Heuvel, M. P. (2010). T. V."),
      "van den Heuvel")
check("year_of accepts a suffix", common.year_of("Yang, W. (2025a). T. V."), 2025)
check("year_of on garbage is None", common.year_of("no year"), None)
# the consumers agree with the gate
check("families.lead_year accepts a suffix", families.lead_year("Yang, W. (2025a). T. V."), ("Yang", 2025))
check("families_figure.year_of accepts a suffix", families_figure.year_of("Yang, W. (2025a). T. V."), 2025)
check("families_figure.lead is the first surname", families_figure.lead("Yang, W., & Li, X. (2025a). T. V."), "Yang")
check("sentence_case.split_apa accepts a suffix",
      sc.split_apa("Yang, W. (2025a). A Title. Venue, 1."), ("Yang, W. (2025a). ", "A Title.", " Venue, 1."))
check("cite_check keys carry the suffix", cite_check.keys_for("Yang, W. (2025a). T. V."), ["Yang, 2025a"])


# ---- source records: ONE reading of a CrossRef work / arXiv entry ------------
# references.py, verify.py and xref.py each used to extract title / year /
# first author / journal from the raw CrossRef message with their own copy of
# the date-field loop; the copies had already drifted (int vs str year).
_MSG = {"title": ["A <i>Title</i>"], "author": [{"family": "Tang", "given": "Jerry"},
                                                {"family": "Huth", "given": "Alexander G."}],
        "published-online": {"date-parts": [[2023, 5, 1]]}, "issued": {"date-parts": [[2022]]},
        "container-title": ["Nature Neuroscience"], "volume": "26", "issue": "5", "page": "858-866"}
_R = common.crossref_record(_MSG)
check("crossref_record title is markup-free", _R["title"], "A Title")
check("crossref_record prefers print, then online, then issued", _R["year"], "2023")
check("crossref_record first_author is 'Family I'", _R["first_author"], "Tang J")
check("crossref_record journal", _R["journal"], "Nature Neuroscience")
check("crossref_record people are APA-formatted", _R["people"], ["Tang, J.", "Huth, A. G."])
check("crossref_record biblio", (_R["volume"], _R["issue"], _R["pages"]), ("26", "5", "858-866"))
check("crossref_record names a preprint server when container-title is empty",
      common.crossref_record({"title": ["T"], "author": [{"family": "A", "given": "B"}],
                              "issued": {"date-parts": [[2024]]},
                              "institution": [{"name": "bioRxiv"}]})["journal"], "bioRxiv")
check("crossref_record falls back to the caller's venue",
      common.crossref_record({"title": ["T"], "author": [{"family": "A", "given": "B"}]},
                             fallback_venue="PsyArXiv (OSF)")["journal"], "PsyArXiv")
# An author-less work (some editorials, datasets) is still a real record for the
# existence check; only canon (which must print authors) refuses it.
check("crossref_record with no authors keeps the title", common.crossref_record({"title": ["T"]})["people"], [])
# CrossRef deposits a series/subtitle in a separate `subtitle` field; dropping it
# made "Part I" and "Part II" papers render as the same title (Creutzfeldt 1989).
check("crossref_record appends the CrossRef subtitle APA-style",
      common.crossref_record({"title": ["Neuronal activity in the human lateral temporal lobe"],
                              "subtitle": ["I. Responses to speech"]})["title"],
      "Neuronal activity in the human lateral temporal lobe: I. Responses to speech")
check("crossref_record skips a subtitle the title already contains",
      common.crossref_record({"title": ["Sleep: a review"], "subtitle": ["A review"]})["title"],
      "Sleep: a review")
check("crossref_record does not double a colon before the subtitle",
      common.crossref_record({"title": ["Sleep:"], "subtitle": ["a review"]})["title"], "Sleep: A review")
check("crossref_record ignores an empty subtitle list",
      common.crossref_record({"title": ["T"], "subtitle": []})["title"], "T")

_ATOM = ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">'
         '<entry><id>http://arxiv.org/abs/2305.18274v2</id><title>Semantic  reconstruction\n of language</title>'
         '<published>2023-05-29T00:00:00Z</published><author><name>Jerry Tang</name></author>'
         '<author><name>Alexander G. Huth</name></author><arxiv:journal_ref>Nat Neurosci 26</arxiv:journal_ref>'
         '</entry><entry><title>Error</title></entry></feed>')
_ES = common.arxiv_entries(_ATOM)
check("arxiv_entries skips the API's synthetic Error entry", len(_ES), 1)
check("arxiv_entries id is normalized (no version)", _ES[0]["id"], "2305.18274")
check("arxiv_entries title is whitespace-collapsed", _ES[0]["title"], "Semantic reconstruction of language")
check("arxiv_entries year", _ES[0]["year"], "2023")
check("arxiv_entries authors are display names", _ES[0]["authors"], ["Jerry Tang", "Alexander G. Huth"])
check("arxiv_entries first_author", _ES[0]["first_author"], "Jerry Tang")
check("arxiv_entries journal_ref", _ES[0]["journal_ref"], "Nat Neurosci 26")

check("key_field prefers ref", common.key_field([{"ref": "A1"}]), "ref")
check("key_field falls back to label", common.key_field([{"label": "x"}]), "label")
check("key_field honors an override", common.key_field([{"ref": "A1"}], "slug"), "slug")
check("key_field on an empty list", common.key_field([]), "label")

# One transient-error policy: a 502 from CrossRef is retried by http() AND
# reported as ERROR (not NOT-FOUND) by verify — the two sets used to differ.
import urllib.error  # noqa: E402

check_true("502 is transient for verify", verify._is_transient(urllib.error.HTTPError("u", 502, "bad", {}, None)))
check_true("404 is a clean miss for verify", not verify._is_transient(urllib.error.HTTPError("u", 404, "no", {}, None)))
check("verify and http share the transient set", verify._TRANSIENT_HTTP, common.TRANSIENT_HTTP)
check_true("http() retries on every transient code", {500, 502, 504} <= common.TRANSIENT_HTTP)
# A dropped connection is transient too. On a 588-row verify run CrossRef closed
# ~30 connections mid-response (RemoteDisconnected / IncompleteRead); neither is a
# URLError, so is_transient() called them clean misses, the DOI lookup returned
# None, and the title-search fallback filed unrelated PubMed hits as MISMATCH.
import http.client  # noqa: E402

check_true("RemoteDisconnected is transient",
           common.is_transient(http.client.RemoteDisconnected("closed")))
check_true("IncompleteRead is transient",
           common.is_transient(http.client.IncompleteRead(b"x")))
check_true("ConnectionResetError is transient", common.is_transient(ConnectionResetError()))
check_true("ValueError is still not transient", not common.is_transient(ValueError("bad json")))



# ---- audit gate -----------------------------------------------------------
def defects(apa, has_source=True):
    return references.audit(apa, has_source)[0]


def notes(apa, has_source=True):
    return references.audit(apa, has_source)[1]


check_true("clean reference passes",
           defects("Biswal, B. (1995). Functional connectivity. MRM, 34(4), 537-541.") == [],
           str(defects("Biswal, B. (1995). Functional connectivity. MRM, 34(4), 537-541.")))
# APA-7 disambiguates same-author/same-year works with a letter suffix; the gate
# used to reject that as "no-year", making correct APA impossible to express.
check_true("year suffix accepted",
           "no-year" not in defects("Yang, W. (2025a). Title. Venue, 1(1), 1-2."))
check_true("missing year still caught", "no-year" in defects("Yang, W. Title. Venue."))
check_true("uppercase title caught behind a year suffix",
           any("uppercase" in d for d in
               defects("Yang, W. (2025a). THE FULLY UPPERCASE TITLE HERE. Venue, 1(1), 1-2.")))
check_true("markup caught",
           any("markup" in d for d in defects("A, B. (2008). <i>T</i>. V, 1(1), 1-2.")))
check_true("double terminal punctuation caught",
           any("double-terminal" in d for d in defects("F, K. (2010). A theory?. V, 1(1), 1-2.")))
check_true("unicode hyphen caught",
           any("unicode-hyphen" in d for d in defects("Kabat‐Zinn, J. (1982). T. V, 1(1), 1-2.")))
check_true("malformed initial caught",
           any("malformed-initial" in d for d in defects("Huber, L. (., Ehses, P. (2025). T. V, 1(1), 1-2.")))
check_true("multi-word surname warns, does not fail",
           any("multi-word surname" in n for n in notes("Thomas Yeo, B. T. T. (2011). T. V, 1(1), 1-2."))
           and defects("Thomas Yeo, B. T. T. (2011). T. V, 1(1), 1-2.") == [])
check_true("particle surname does not warn",
           not any("multi-word surname" in n for n in notes("de Heer, W. A. (2017). T. V, 1(1), 1-2.")))

# ---- offline repair -------------------------------------------------------
# Retrofitting the gate onto an old corpus must not require re-canonicalizing it,
# because canon re-fetches and wipes every post-canon hand fix.
check("repair strips markup",
      references.repair("A, B. (2008). <i>T</i>. V, 1(1), 1-2.")[0],
      "A, B. (2008). T. V, 1(1), 1-2.")
check("repair normalizes unicode hyphen",
      references.repair("Kabat‐Zinn, J. (1982). T. V, 1(1), 1-2.")[0],
      "Kabat-Zinn, J. (1982). T. V, 1(1), 1-2.")
check("repair removes period after question mark",
      references.repair("F, K. (2010). A unified theory?. V, 1(1), 1-2.")[0],
      "F, K. (2010). A unified theory? V, 1(1), 1-2.")
check("repair is a no-op on a clean reference",
      references.repair("Biswal, B. (1995). T. MRM, 34(4), 537-541.")[0],
      "Biswal, B. (1995). T. MRM, 34(4), 537-541.")
check_true("clean reference reports no changes",
           references.repair("Biswal, B. (1995). T. MRM, 34(4), 537-541.")[1] == [])
# The repaired string must then pass the gate it was failing.
_r = references.repair("A, B. (2008). <i>T</i>? V, 1(1), 1-2.")[0]
check_true("repaired reference passes the audit", defects(_r) == [], str(defects(_r)))
# En dashes in page ranges must survive the hyphen normalization.
check_true("repair preserves en dash",
           "1124–1138" in references.repair("A, B. (2008). T. V, 1, 1124–1138.")[0])

# ---- cite_check -----------------------------------------------------------
ROWS = [
    {"ref": "A1", "apa": "Farb, N. A. S., Segal, Z. V., & Mayberg, H. (2007). Attending to the present. SCAN, 2(4), 313-322."},
    {"ref": "A2", "apa": "Kral, T. R. A., Davis, K., & Korponay, C. (2022). Absence of structural change. Sci Adv, 8(20), 1-9."},
    {"ref": "A3", "apa": "Kral, T. R. A., Lapate, R. C., & Imhoff-Smith, T. (2022). Long-term meditation training. Brain Imaging, 1(1), 1-9."},
    {"ref": "A4", "apa": "Millière, R. (2018). Psychedelics, meditation, and self-consciousness. Front Psychol, 9, 1475."},
]
idx = {}
for _r in ROWS:
    for _k in cite_check.keys_for(_r["apa"]):
        idx.setdefault(cite_check.norm(_k), []).append(_r["ref"])

check_true("parenthetical citation resolves", idx.get(cite_check.norm("Farb et al., 2007")) == ["A1"])
check_true("single-author citation resolves", idx.get(cite_check.norm("Millière, 2018")) == ["A4"])
check_true("accent-folded citation resolves", idx.get(cite_check.norm("Milliere, 2018")) == ["A4"])
check_true("same author-year is ambiguous",
           sorted(set(idx.get(cite_check.norm("Kral et al., 2022") or "", []))) == ["A2", "A3"])
check_true("APA 8.19 extra author disambiguates",
           idx.get(cite_check.norm("Kral, Davis, et al., 2022")) == ["A2"])
found = cite_check.citations_in(
    "As shown (Farb et al., 2007; Kral, Davis, et al., 2022). Millière (2018) argued otherwise.")
check_true("parenthetical and narrative both parsed",
           {"Farb et al., 2007", "Kral, Davis, et al., 2022", "Millière, 2018"} <= found,
           str(sorted(found)))

# ---- sentence_case --------------------------------------------------------
def sent(t, words=(), phrases=()):
    return sc.sentence_case(t, set(sc.PROPER) | set(words), list(phrases))


check("title case lowered", sent("Effects Of Meditation Experience On Brain Networks"),
      "Effects of meditation experience on brain networks")
check("subtitle after colon capitalized", sent("Defining meditation: foundations for a system"),
      "Defining meditation: Foundations for a system")
check("acronyms protected", sent("EEG And fMRI Evidence For DMN Change"),
      "EEG and fMRI evidence for DMN change")
check("hyphen parts judged separately", sent("Resting-State Functional Connectivity"),
      "Resting-state functional connectivity")
check("lone capital in a compound is an acronym part",
      sent("A Study Of ACAM-J And S-ART"), "A study of ACAM-J and S-ART")
check("digits protected", sent("Evidence From 7T And COVID-19 Cohorts"),
      "Evidence from 7T and COVID-19 cohorts")
check("eponym protected", sent("A Bayesian Account Of Alzheimer's Disease"),
      "A Bayesian account of Alzheimer's disease")
check("project phrase protected, generic word not",
      sent("Yoga And Sahaja Yoga Meditation", phrases=["Sahaja Yoga"]),
      "Yoga and Sahaja Yoga meditation")
# A hyphenated allowlist entry must be matched whole; checking only its parts
# lowercased 'Age-Well' and would have lowercased the built-in 'Lempel-Ziv'.
check("hyphenated allowlist entry protected",
      sent("Secondary Analyses From The Age-Well Trial", words=["Age-Well"]),
      "Secondary analyses from the Age-Well trial")
check("built-in hyphenated eponym protected",
      sent("Estimating Lempel-Ziv Complexity"), "Estimating Lempel-Ziv complexity")

# ---- renderers agree with the gate ------------------------------------------
# The reference list is built in ONE place (review_paper.reference_list) so the
# .docx and any HTML page cannot disagree, and it never re-creates a defect the
# gate forbids (a period after a title's ? or !).
_RL = review_paper.reference_list([
    {"apa": "Zeidan, F. (2015). Does it work?", "link": "L"},
    {"apa": "Millière, R. (2018). T. V.", "link": ""},
    {"apa": "Miller, A. (2000). T. V.", "link": ""},
    {"apa": "Miller, A. (2000). T. V.", "link": "dup"},
])
check("reference_list dedupes on the apa text", len(_RL), 3)
check("reference_list sorts with accents folded (Miller before Millière)",
      [a[:7] for a, _ in _RL], ["Miller,", "Millièr", "Zeidan,"])
check("reference_list adds no period after ?", _RL[2][0], "Zeidan, F. (2015). Does it work?")
check("reference_list keeps the first row's link", _RL[0][1], "")

# spreadsheet.py must not crash on a `source` value it has never seen — corpora
# already disagree on the tag vocabulary (anteced vs search for the same pass).
import tempfile  # noqa: E402

_tmp = os.path.join(tempfile.mkdtemp(), "t.xlsx")
spreadsheet.build([{"ref": "A1", "apa": "A, B. (2020). T. V.", "link": "", "summary": "s",
                    "source": "never-seen-before"}], _tmp)
check_true("spreadsheet.build tolerates an unknown source", os.path.exists(_tmp))
check_true("spreadsheet knows an unknown source when it sees one",
           spreadsheet.unknown_sources([{"source": "never-seen-before"}, {"source": "xref"}])
           == ["never-seen-before"])

# verify_note is the "this row still needs / got a human decision" field; 11 corpora
# stamp it (102 rows in neuroethology alone) and the xlsx used to hide it entirely.
import zipfile  # noqa: E402

_tmpv = os.path.join(tempfile.mkdtemp(), "v.xlsx")
spreadsheet.build([{"ref": "A1", "apa": "A, B. (2020). T. V.", "source": "search",
                    "verify_note": "DOI-less item; needs catalog check"}], _tmpv)
with zipfile.ZipFile(_tmpv) as _z:
    _ss = _z.read("xl/sharedStrings.xml").decode("utf-8")
check_true("verify_note reaches the spreadsheet",
           "Verify note" in _ss and "needs catalog check" in _ss)
spreadsheet.build([{"ref": "A1", "apa": "A, B. (2020). T. V.", "source": "search"}], _tmpv)
with zipfile.ZipFile(_tmpv) as _z:
    _ss = _z.read("xl/sharedStrings.xml").decode("utf-8")
check_true("no verify_note anywhere -> no empty column", "Verify note" not in _ss)


# ---- generated tool index -------------------------------------------------
# The tool table in docs/tools.md, tools/README.md and PLAYBOOK.md is generated
# from the modules themselves (docstring first sentence, PHASE constant, argparse
# flags), so four hand-written descriptions can no longer drift apart.
_ENT = {e["name"]: e for e in gen_docs.tool_entries()}
# --- lessons from the neuroethology history corpus (2026-08-29) -------------
# 1. Mangled punctuation INSIDE a title. CrossRef could not encode the quotes and
#    dash in Wehner 1987 and returned literal '?' characters. The existing check
#    only catches a '?.' double terminal, so this shipped silently.
check_true("stray ? before a letter is a defect", any(
    "mangled-punct" in d for d in defects(
        'Wehner, R. (1987). ?Matched filters? ? neural models of the world. JCP A, 161(4), 511-531.')))
check_true("a legitimate question mark is not a defect", not any(
    "mangled-punct" in d for d in defects(
        "Dewsbury, D. (1978). What is (was?) the fixed action pattern? Animal Behaviour, 26, 310-311.")))

# 2. A publisher back-file/digitization deposit re-dates an old paper. Seen three
#    times in one corpus: Seyfarth 1991->2008, Lorenz 1943->2010, Schleidt 1962->2010.
#    The DOI suffix usually still carries the true year.
check("doi year is read out of the suffix",
      references.doi_year("10.1111/j.1439-0310.1943.tb00655.x"), 1943)
check("doi with no year gives None", references.doi_year("10.1038/nn.4244"), None)
# A loose scan matched page numbers, article ids and ISSN fragments: 15 false
# positives and no true ones on a 493-ref corpus. These must all read None.
check("a page number is not a year", references.doi_year("10.1126/science.167.3926.1745"), None)
check("an article id is not a year", references.doi_year("10.1038/nrn1606"), None)
check("an issn fragment is not a year", references.doi_year("10.1016/s1874-6055(98)80006-6"), None)
check("a method id is not a year", references.doi_year("10.1038/nmeth.1694"), None)

# Stripping JATS <i> tags removes the tag but leaves no separator, so the words
# either side are glued ("marine mollusc,Tritonia", "cockroachPeriplaneta").
check_true("comma glued to a word is a defect", any("missing-space" in d for d in defects(
    "Getting, P. A. (1976). Escape swimming of the marine mollusc,Tritonia. JCP, 110(3), 271-286.")))
check_true("genus glued to a word is a defect", any("missing-space" in d for d in defects(
    "Camhi, J. M. (1978). The escape behavior of the cockroachPeriplaneta americana. JCP, 128, 203-212.")))
check_true("a normal title has no missing-space defect", not any("missing-space" in d for d in defects(
    "Getting, P. A. (1976). Escape swimming of the marine mollusc, Tritonia. JCP, 110(3), 271-286.")))
check_true("deposit-year conflict is reported", references.deposit_year_conflict(
    "10.1111/j.1439-0310.1943.tb00655.x",
    "Lorenz, K. (2010). Die angeborenen Formen. Z. Tierpsychol., 5(2), 235-409.") is not None)
check_true("matching years are not reported", references.deposit_year_conflict(
    "10.1111/j.1439-0310.1943.tb00655.x",
    "Lorenz, K. (1943). Die angeborenen Formen. Z. Tierpsychol., 5(2), 235-409.") is None)

# 3. A non-English title must not be sentence-cased: the pass lowercases German
#    nouns. The language test must not fire on 'von'/'de' inside a personal name
#    ("Karl von Frisch", "fin-de-siecle") or on the English word 'man'.
check_true("German title detected", sc.is_foreign_title("Der Kumpan in der Umwelt des Vogels"))
check_true("French title detected", sc.is_foreign_title("La machine animale: Locomotion terrestre"))
check_true("English title with 'von' in a name is not foreign",
           not sc.is_foreign_title("Karl von Frisch and the discipline of ethology"))
check_true("English title with 'de' in a name is not foreign",
           not sc.is_foreign_title("Neuroanatomist in fin-de-siecle Vienna"))
check_true("'animals and man' is not foreign",
           not sc.is_foreign_title("The nervous system of vertebrates, including man"))

# 4. A partly ALL-CAPS title is shouting, not an acronym. references.norm_title
#    only fixes a title that is ENTIRELY caps, and sentence_case protects all-caps
#    tokens as possible acronyms, so 'BEHAVIORAL MUTANTS OF Drosophila ISOLATED BY
#    COUNTERCURRENT DISTRIBUTION' passed through both untouched.
check("all-caps run is lowered", sent("BEHAVIORAL MUTANTS OF Drosophila ISOLATED BY DISTRIBUTION"),
      "Behavioral mutants of Drosophila isolated by distribution")
check("a short acronym is still protected", sent("Encoding and decoding in fMRI and MEG studies"),
      "Encoding and decoding in fMRI and MEG studies")

# 5. Model-organism genera must keep their capital when canon sentence-cases an
#    ALL-CAPS title (Brenner 1974 came back as 'caenorhabditis elegans').
check("genus survives an all-caps title",
      common.norm_title("THE GENETICS OF CAENORHABDITIS ELEGANS"),
      "The genetics of Caenorhabditis elegans")

# --- families_figure: the timeline walk-through (added 2026-08-29) -----------
# The figure has hundreds of small dots; clicking each one to read it is
# impractical, so the panel carries Prev/Next plus arrow-key bindings that step
# through papers in year order. These assert the shell actually ships that code.
_SHELL = families_figure.HTML_SHELL
check_true("figure panel has Prev/Next buttons", 'id="prev"' in _SHELL and 'id="next"' in _SHELL)
check_true("figure binds the arrow keys", "ArrowRight" in _SHELL and "ArrowLeft" in _SHELL)
check_true("figure orders the walk by year", "DATA[a].year-DATA[b].year" in _SHELL)
check_true("figure can leave the family scope", "LANEONLY" in _SHELL and 'id="lanechk"' in _SHELL)
check_true("figure shows the walk position", 'id="pos"' in _SHELL)
# The controls sit ABOVE the reference text: a summary can run several hundred
# characters, and a nav row placed under it would move on every step.
check_true("nav row precedes the reference text",
           _SHELL.find("navHTML(k,doi)") < _SHELL.find('<div id="apa">'))
# Hover must NOT re-pin the panel: the reader moves the mouse across other dots
# on the way to the Next button, which would silently change the selection.
# Positive-form guard: a byte-exact negative match only forbids one spelling of
# the bug — any reformatted `mouseenter ... show(...)` handler must also fail.
check_true("hover does not re-pin the panel",
           not re.search(r"mouseenter[^\n]*\bshow\(", _SHELL))
# The node tooltip is the per-dot `<title>{esc(p["apa"])}</title>` (drawn twice:
# node + label group) — a bare "<title>" grep is satisfied forever by the page's
# own <title> tag in HTML_SHELL.
with open(os.path.join(os.path.dirname(families_figure.__file__), "families_figure.py"),
          encoding="utf-8") as _ffsrc:
    check_true("nodes still carry a hover tooltip",
               _ffsrc.read().count('<title>{esc(p["apa"])}</title>') >= 2)

check_true("every tool module is indexed", {"verify.py", "references.py", "families_figure.py"} <= set(_ENT))
check("phase comes from the module's PHASE constant", _ENT["references.py"]["phase"], "3f")
check_true("flags come from argparse", "--audit" in _ENT["references.py"]["flags"])
check_true("purpose is the docstring's first sentence",
           _ENT["verify.py"]["purpose"].startswith("Verify a list of citations"))
_BLK = gen_docs.render_block(list(_ENT.values()))
check_true("generated block is fenced by markers",
           _BLK.startswith(gen_docs.BEGIN) and _BLK.rstrip().endswith(gen_docs.END))
check("splice replaces only what is between the markers",
      gen_docs.splice("a\n" + gen_docs.BEGIN + "\nold\n" + gen_docs.END + "\nz\n", "NEW"),
      "a\n" + gen_docs.BEGIN + "\nNEW\n" + gen_docs.END + "\nz\n")


# ---- rows.json in, no converters ------------------------------------------
# verify.py and xref.py take the live table directly; 14 per-project scripts
# existed only to rename ref -> label/slug and re-derive the first author with
# their own regex.
_ROW = {"ref": "A1", "apa": "Tang, J., & Huth, A. G. (2023). Semantic reconstruction. Nat Neurosci, 26, 1.",
        "link": "https://doi.org/10.1038/x", "arxiv": "2305.1"}
check("rows_to_citations derives the verify input from rows.json",
      verify.rows_to_citations([_ROW]),
      [{"label": "A1", "doi": "10.1038/x", "arxiv": "2305.1", "title": "Semantic reconstruction",
        "expect_first_author": "Tang", "expect_year": "2023"}])
check("rows_to_citations keeps a row with no DOI (title search still runs)",
      verify.rows_to_citations([{"ref": "B", "apa": "K, J. (1982). Old book. Pub."}])[0]["doi"], None)
check("rows_to_papers derives the xref input", xref.rows_to_papers([_ROW]), [{"slug": "A1", "doi": "10.1038/x"}])
check("rows_to_papers skips a row with neither DOI nor pdf",
      xref.rows_to_papers([{"ref": "B", "apa": "K, J. (1982). Old book. Pub."}]), [])

# ---- attach_counts / write_rows: the glue every project re-implemented ------
_R2 = [{"ref": "A1"}, {"ref": "A2", "cite_openalex": 3}]
check("attach_counts stamps cite_openalex / cite_s2 and returns how many",
      common.attach_counts(_R2, {"A1": {"openalex": 5, "s2": 7, "s2_influential": 1, "asof": "d"}}), 1)
check("attach_counts wrote the exact keys spreadsheet.py reads", (_R2[0]["cite_openalex"], _R2[0]["cite_s2"]), (5, 7))
# citations.py fetches influentialCitationCount; attach_counts used to drop it on
# the floor (world_models' rows carried the key only via a retired private script).
check("attach_counts keeps the influential count it paid to fetch",
      _R2[0].get("cite_s2_influential"), 1)
check("attach_counts leaves an unlisted row alone", _R2[1]["cite_openalex"], 3)
try:
    common.attach_counts([{"ref": "A1"}], {"A1": {"oa": 5}})
    check_true("attach_counts rejects a counts file with the wrong schema", False)
except KeyError:
    pass

_dir = tempfile.mkdtemp()
_rp = os.path.join(_dir, "rows.json")
common.write_rows(_rp, [{"ref": "A1", "apa": "x"}])
check_true("write_rows creates a fresh table", os.path.exists(_rp))
common.write_rows(_rp, [{"ref": "A1", "apa": "y"}])
check("write_rows overwrites a non-canonical table", common.load_json(_rp)[0]["apa"], "y")
common.write_rows(_rp, [{"ref": "A1", "apa": "canon", "canonical_at": "2026-08-18"}])
try:
    common.write_rows(_rp, [{"ref": "A1", "apa": "emitter output"}])
    check_true("write_rows refuses to overwrite a canonical table", False)
except common.CanonicalTableError:
    pass
check("the canonical table survived", common.load_json(_rp)[0]["apa"], "canon")
common.write_rows(_rp, [{"ref": "A1", "apa": "forced"}], force=True)
check("write_rows(force=True) overrides the guard", common.load_json(_rp)[0]["apa"], "forced")
# An unreadable table must DISARM nothing: a half-written rows.json (truncated dump,
# bad permissions) is exactly when the canonical stamps can't be seen — refuse blind.
with open(_rp, "w", encoding="utf-8") as _f:
    _f.write('[{"ref": "A1", "apa": "canon", "canonical_at": "2026-08-1')  # truncated write
try:
    common.write_rows(_rp, [{"ref": "A1", "apa": "emitter output"}])
    check_true("write_rows refuses to overwrite an unreadable table", False)
except common.CanonicalTableError:
    pass
check("the unreadable table was left untouched",
      open(_rp, encoding="utf-8").read().endswith('2026-08-1'), True)
common.write_rows(_rp, [{"ref": "A1", "apa": "rebuilt"}], force=True)
check("write_rows(force=True) still overrides on an unreadable table",
      common.load_json(_rp)[0]["apa"], "rebuilt")
_row = {"ref": "A1"}
references.stamp_canonical(_row, "2026-08-18")
check("references stamps canonical_at", _row["canonical_at"], "2026-08-18")

# ---- stale cached year: canon rewrites apa, nothing re-checked the cache ----
# complexity 2b3 cached 2005 vs apa 2004; human_brain_decoding T03 1961 vs 2012.
check("cached year that diverged from the apa is warned",
      bool(references.cached_year_conflict(
          {"year": 2005, "apa": "Kemp, C. (2004). A theory. Science."})), True)
check("matching cached year is quiet",
      references.cached_year_conflict(
          {"year": "2004", "apa": "Kemp, C. (2004). A theory. Science."}), None)
check("APA year suffix does not false-positive the cache check",
      references.cached_year_conflict(
          {"year": 2025, "apa": "Kral, T. (2025a). Paper. J."}), None)
check("a row with no cached year is quiet",
      references.cached_year_conflict({"apa": "Kemp, C. (2004). T. S."}), None)

# ---- xref: an incomplete fetch is not "this paper cites nothing" ------------
# A throttle that exhausted the backoff used to collapse into an empty reference
# list, silently deflating the frequency table and the --internal-out in-degrees.
import urllib.error  # noqa: E402


def _http_raising(code):
    def _f(url, **kw):
        raise urllib.error.HTTPError(url, code, "x", {}, None)
    return _f


_orig_http_json = xref.http_json
xref.http_json = _http_raising(404)
check("xref: DOI absent from CrossRef = complete, no reference list", xref.crossref_refs("10.1/x"), [])
xref.http_json = _http_raising(503)
check("xref: exhausted throttle = INCOMPLETE (None), never an empty list",
      xref.crossref_refs("10.1/x"), None)
xref.http_json = _orig_http_json

# ---- a throttled DOI lookup must not be masked by the title-search fallback ---
# On a 588-row run CrossRef throttled ~30 DOI lookups; verify_one then fell through
# to lookup_pubmed_title, which returned an unrelated paper, and the row was
# reported MISMATCH ("Adelson 1985" -> "Wang 2026, MSF: Multi-Level Spatiotemporal
# Filtering") instead of ERROR. A MISMATCH reads as "the agent got it wrong"; an
# ERROR reads as "re-run". The two must stay distinct when the real lookup errored.
_orig_cr, _orig_pt = verify.lookup_crossref, verify.lookup_pubmed_title
def _throttled(doi):
    raise urllib.error.HTTPError("u", 429, "rate limited", {}, None)
verify.lookup_crossref = _throttled
verify.lookup_pubmed_title = lambda t: {"title": "MSF: Multi-Level Spatiotemporal Filtering",
                                        "year": "2026", "first_author": "Wang J", "journal": "X"}
_r = verify.verify_one({"label": "E15", "doi": "10.1364/josaa.2.000284",
                        "title": "Spatiotemporal energy models for the perception of motion",
                        "expect_first_author": "Adelson", "expect_year": "1985"})
check("throttled DOI lookup + unrelated title hit -> ERROR, not MISMATCH", _r["verdict"], "ERROR")
# ...but a title-search hit that DOES match the claim is still accepted as OK.
verify.lookup_pubmed_title = lambda t: {"title": "Spatiotemporal energy models for the perception of motion",
                                        "year": "1985", "first_author": "Adelson EH", "journal": "JOSA A"}
_r = verify.verify_one({"label": "E15", "doi": "10.1364/josaa.2.000284",
                        "title": "Spatiotemporal energy models for the perception of motion",
                        "expect_first_author": "Adelson", "expect_year": "1985"})
check("throttled DOI lookup + matching title hit -> OK", _r["verdict"], "OK")
verify.lookup_crossref, verify.lookup_pubmed_title = _orig_cr, _orig_pt

# ---- two deposit defects that shipped through the gate on a 588-row corpus ------
# CrossRef stores a hyphenated given name with the second part missing ("Poline,
# J. -." for Jean-Baptiste Poline) and glues a footnote digit to the last title
# word ("psychological science1"). Neither was caught; both were found by eye.
_d, _n = references.audit("Friston, K. J., & Poline, J. -. (1994). Statistical parametric maps. Human Brain Mapping, 2(4), 189-210.", True)
check_true("hyphenated initial with a missing part is a defect", any(x.startswith("malformed-initial") for x in _d), str(_d))
_d, _n = references.audit("Allport, G. W. (1962). The general and the unique in psychological science1. Journal of Personality, 30(3), 405-422.", True)
check_true("footnote digit glued to the title is flagged", any("glued-footnote" in x for x in _d + _n), str(_d + _n))
_d, _n = references.audit("Boynton, G. M. (1996). Linear systems analysis of fMRI in human V1. Journal of Neuroscience, 16(13), 4207-4221.", True)
check_true("a title ending in an area name (V1) is not a glued footnote", not any("glued-footnote" in x for x in _d + _n), str(_d + _n))
_d, _n = references.audit("Kay, K. N. (2013). Compressive spatial summation in area 3b. Journal of Vision, 13(2), 1-10.", True)
check_true("a title ending in 3b is not a glued footnote", not any("glued-footnote" in x for x in _d + _n), str(_d + _n))

# ---- verify is a gate: exit 0 only when every verdict is OK -----------------
# It used to always exit 0, so `verify.py && references.py ...` sailed past a
# run full of NOT-FOUNDs; the other two gates already failed loud.
check("verify gate passes an all-OK run", verify.gate_code([{"verdict": "OK"}] * 3), 0)
for _v in ("MISMATCH", "NOT-FOUND", "ERROR"):
    check(f"verify gate fails a run with a {_v}",
          verify.gate_code([{"verdict": "OK"}, {"verdict": _v}]), 1)


# ---- report ---------------------------------------------------------------
if FAILURES:
    print(f"FAILED {len(FAILURES)} check(s):\n")
    for f in FAILURES:
        print("  ✗ " + f)
    sys.exit(1)
print("✓ all formatting/audit/citation regression checks pass")
