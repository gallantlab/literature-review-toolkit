#!/usr/bin/env python3
"""Regression tests for the reference formatter, audit gate and Phase-7 checks.

Every case here is a real defect that reached a delivered bibliography before the
check existed. Run with no arguments; no pytest required.

    python3 tools/tests/test_formatting.py
"""
import os
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


# ---- generated tool index -------------------------------------------------
# The tool table in docs/tools.md, tools/README.md and PLAYBOOK.md is generated
# from the modules themselves (docstring first sentence, PHASE constant, argparse
# flags), so four hand-written descriptions can no longer drift apart.
_ENT = {e["name"]: e for e in gen_docs.tool_entries()}
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
_row = {"ref": "A1"}
references.stamp_canonical(_row, "2026-08-18")
check("references stamps canonical_at", _row["canonical_at"], "2026-08-18")


# ---- report ---------------------------------------------------------------
if FAILURES:
    print(f"FAILED {len(FAILURES)} check(s):\n")
    for f in FAILURES:
        print("  ✗ " + f)
    sys.exit(1)
print("✓ all formatting/audit/citation regression checks pass")
