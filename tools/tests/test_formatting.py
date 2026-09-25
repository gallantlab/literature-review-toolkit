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

import bib_viewer  # noqa: E402
import cite_check  # noqa: E402
import common  # noqa: E402
import families  # noqa: E402
import families_figure  # noqa: E402
import gen_docs  # noqa: E402
import prose_audit  # noqa: E402
import references  # noqa: E402
import review_paper  # noqa: E402
import sentence_case as sc  # noqa: E402
import spreadsheet  # noqa: E402
import verify  # noqa: E402
import version  # noqa: E402
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
# APA-7 dates web posts, reports and magazine issues more finely: (2022, June 5)
_W = common.parse_apa("Yudkowsky, E. (2022, June 5). AGI ruin: A list of lethalities. LessWrong. https://x.org")
check("parse_apa accepts a (YYYY, Month D) date", (_W["year"], _W["title"]), (2022, "AGI ruin: A list of lethalities"))
check("year_of accepts a (YYYY, Month) date", common.year_of("Asimov, I. (1942, March). Runaround. V."), 1942)
check("year_of accepts a day range", common.year_of("Doe, J. (2021, June 10-12). T. V."), 2021)
check("year_of rejects a lowercase non-date", common.year_of("Doe, J. (2021, draft). T. V."), None)
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
# A book chapter deposits [series, book] as container-title. Reading only the
# first printed "Title. The Frontiers Collection." -- no book, pages or publisher.
_CH = common.crossref_record({
    "type": "book-chapter", "title": ["The Singularity and Machine Ethics"],
    "author": [{"family": "Muehlhauser", "given": "Luke"}, {"family": "Helm", "given": "Louie"}],
    "issued": {"date-parts": [[2012]]}, "page": "101-126",
    "container-title": ["The Frontiers Collection", "Singularity Hypotheses"],
    "publisher": "Springer Berlin Heidelberg"})
check("crossref_record: a chapter's book is the last container-title", _CH["book"], "Singularity Hypotheses")
check("crossref_record: a chapter keeps its publisher", _CH["publisher"], "Springer Berlin Heidelberg")
check("crossref_record: a journal article has no book", _R["book"], "")
check("references.crossref_apa builds an APA-7 chapter",
      references.crossref_apa(_CH),
      "Muehlhauser, L., & Helm, L. (2012). The Singularity and Machine Ethics. "
      "In Singularity Hypotheses (pp. 101-126). Springer Berlin Heidelberg.")
check("references.crossref_apa leaves an article unchanged", references.crossref_apa(_R),
      "Tang, J., & Huth, A. G. (2023). A Title. Nature Neuroscience, 26(5), 858-866.")
check("a chapter reference parses with the book as venue",
      common.parse_apa(references.crossref_apa(_CH))["rest"], " In Singularity Hypotheses (pp. 101-126). Springer Berlin Heidelberg.")
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



# ---- common.http: compressed transfers (added 2026-09-18) ------------------
# CrossRef reference lists are large (a single work record can exceed 1 MB), and
# an uncompressed chunked response is the shape that gets truncated in transit:
# `IncompleteRead(1782210 bytes read, 399724 more expected)`. That surfaces as
# http.client.HTTPException, so it is correctly classed transient and retried —
# but it retries forever on the big records, which is what a large truncation
# looks like from the outside. Asking for gzip cuts the payload ~5x and the
# failures with it. Measured on the cortical-layers build: 117 of 537 rows failed
# canon uncompressed, and an xref pass was running at ~19 papers per 7 minutes.
import gzip as _gzip  # noqa: E402
import zlib as _zlib  # noqa: E402

check_true("http requests a compressed body",
           "gzip" in common.HDRS.get("Accept-Encoding", ""))
check("gzip body is decompressed",
      common.decompress(_gzip.compress(b'{"ok":1}'), "gzip"), b'{"ok":1}')
check("deflate body is decompressed",
      common.decompress(_zlib.compress(b'{"ok":1}'), "deflate"), b'{"ok":1}')
# An uncompressed response must pass through untouched — servers ignore the
# header freely, and most of the toolkit's endpoints do.
check("identity body is passed through",
      common.decompress(b'{"ok":1}', ""), b'{"ok":1}')
check("unknown encoding is passed through, not corrupted",
      common.decompress(b'{"ok":1}', "br-unsupported"), b'{"ok":1}')
# A server that lies about the encoding must not take the whole run down: better
# to hand back the raw bytes and let the JSON parser complain than to raise here.
check("a mislabeled body degrades to raw bytes",
      common.decompress(b"not actually gzipped", "gzip"), b"not actually gzipped")

def _raises(fn):
    try:
        fn()
    except Exception:
        return True
    return False


# ---- common.http: curl fallback (added 2026-09-18) -------------------------
# Some CrossRef records fail INSTANTLY and deterministically under urllib
# (`RemoteDisconnected`, 0.3s, same DOIs every time) while curl fetches the exact
# same URL without trouble — an HTTP-stack/proxy interaction, not rate limiting
# and not truncation. 71 of 536 reference-list fetches died this way on the
# cortical-layers xref pass. When urllib has exhausted its retries, one curl
# attempt recovers them. Exercised offline here through file://, which curl
# supports, so the suite still needs no network.
import subprocess as _sp  # noqa: E402
import tempfile as _tf  # noqa: E402

if _sp.run(["which", "curl"], capture_output=True).returncode == 0:
    with _tf.NamedTemporaryFile("wb", suffix=".json", delete=False) as _fh:
        _fh.write(b'{"message":"curl-fallback-ok"}')
        _curlpath = _fh.name
    check("curl_get fetches a body", common.curl_get("file://" + _curlpath, {}, 10),
          b'{"message":"curl-fallback-ok"}')
    check_true("curl_get raises, not returns, on a missing target",
               _raises(lambda: common.curl_get("file:///nonexistent-litreview-test", {}, 10)))
    os.unlink(_curlpath)
# The fallback must be wired into http(), not merely defined beside it.
with open(os.path.join(os.path.dirname(common.__file__), "common.py"), encoding="utf-8") as _csrc:
    _CSRC = _csrc.read()
check_true("http() falls back to curl after exhausting retries",
           "curl_get" in _CSRC.split("def http(")[1].split("def http_json")[0])

# ---- audit gate -----------------------------------------------------------
def defects(apa, has_source=True):
    return references.audit(apa, has_source)[0]


def notes(apa, has_source=True):
    return references.audit(apa, has_source)[1]


# "et al." is a DEFECT in an author list and a legitimate word in a TITLE. Nature
# journals title their Matters Arising replies "<Author> et al. reply", so the
# whole-string check condemned a correctly canonicalized reference and no edit
# could satisfy the gate without falsifying the published title. Found on
# Nat Neurosci 29(2), 284-286 in the cortical-layers corpus, 2026-09-18.
_ETAL_TITLE = ("Major, A. J., Abdaltawab, A., & Mendoza-Halliday, D. (2026). "
               "A. J. Major et al. reply. Nature Neuroscience, 29(2), 284-286.")
check_true("et al. inside a TITLE is not a defect",
           "et-al (should list all authors)" not in defects(_ETAL_TITLE),
           str(defects(_ETAL_TITLE)))
# ...but an abbreviated AUTHOR list is still the defect it always was.
_ETAL_AUTHORS = "Hubel, D. H., et al. (1977). Functional architecture. Phil Trans, 198, 1-59."
check_true("et al. in the AUTHOR list is still a defect",
           "et-al (should list all authors)" in defects(_ETAL_AUTHORS))
# A reference the APA grammar cannot parse has no author segment to inspect, so
# the check must fall back to the whole string rather than silently passing.
check_true("et al. still caught when the reference will not parse",
           "et-al (should list all authors)" in defects("Hubel et al. Functional architecture."))

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
# APA-7 §9.44-9.46: the same authors sort by year, and a sole author precedes
# that author's multi-author works. Sorting on the whole string letters-only
# ignored the year and let titles decide (Anobile 2016 printed before 2014).
_RL2 = review_paper.reference_list([
    {"apa": "Anobile, G., & Burr, D. C. (2016). Number as a primary attribute.", "link": ""},
    {"apa": "Anobile, G., & Burr, D. C. (2014). Separate mechanisms.", "link": ""},
    {"apa": "Attneave, F. (1959). Applications of information theory.", "link": ""},
    {"apa": "Attneave, F., & Arnoult, M. D. (1956). The quantitative study.", "link": ""},
    {"apa": "Attneave, F. (1954). Some informational aspects.", "link": ""},
    {"apa": "Attneave, F. (1957). Physical determinants.", "link": ""},
])
check("reference_list orders same authors by year, sole author first",
      [re.search(r"\((\d{4})\)", a).group(1) for a, _ in _RL2],
      ["2014", "2016", "1954", "1957", "1959", "1956"])

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

with open(os.path.join(os.path.dirname(families_figure.__file__), "families_figure.py"),
          encoding="utf-8") as _ffe:
    _FFSRC_EARLY = _ffe.read()
# --- families_figure: family definitions on hover (added 2026-09-18) ---------
# The families carry a `claim` and a `lineage` in families.json, and the figure
# drew only a truncated claim beside the lane name — the lineage, which is the
# whole point of a lineage figure, was carried in the data and never shown. A
# reader could not find out what a family MEANT without opening families.md.
# Hovering (or focusing) the lane title now reveals both.
check_true("figure ships a family hover tooltip", 'id="famtip"' in _SHELL)
check_true("figure hover carries claim AND lineage",
           "FAMINFO" in _SHELL and ".claim" in _SHELL and ".lineage" in _SHELL)
check_true("family tooltip is injected with the rest of the data", "__FAMINFO__" in _SHELL)
# Keyboard parity: a hover-only affordance is unreachable without a mouse, and
# the lane titles are the figure's primary legend.
check_true("lane titles are focusable",
           'class="lanelabel" tabindex="0"' in _FFSRC_EARLY)
# The family tooltip must not overwrite a PINNED reference in the side panel —
# the reader passes the lane titles on the way to anything else, and losing the
# pinned entry is the same defect the node-hover guard above forbids.
check_true("family hover does not clobber the pinned panel",
           not re.search(r"lanelabel[\s\S]{0,400}?panel\.innerHTML", _SHELL))
with open(os.path.join(os.path.dirname(families_figure.__file__), "families_figure.py"),
          encoding="utf-8") as _ffsrc:
    _FFSRC = _ffsrc.read()
# The standalone .svg/.png/.pdf have no JavaScript, so the lane group carries a
# native <title> too: the exported figure must describe its own families.
check_true("lane label carries a native SVG title", "lanetitle" in _FFSRC)
check_true("figure reads lineage out of the family spec", '.get("lineage"' in _FFSRC)

# --- families_figure: the drawn claim must stay inside its lane (2026-09-18) --
# The lane label draws the family's claim under its name at 12px line pitch, with
# no bound on how many lines that is. A long claim (this toolkit's own family
# specs run 300-500 characters) overflowed into the NEXT family's title and drew
# on top of it. Now that the full claim is one hover away, the drawn copy is
# clamped to the space the lane actually has and ellipsized.
check_true("the drawn claim is clamped to the lane height", "claim_lines" in _FFSRC_EARLY)
check("claim_lines keeps a short claim whole",
      families_figure.claim_lines("Short enough to fit.", 42, 10),
      ["Short enough to fit."])
_long = ("Before any laminar difference can be measured the layer has to be made into a "
         "well-defined measurable object, and these papers are about knowing which layer "
         "you are in across every method the corpus uses.")
_cl = families_figure.claim_lines(_long, 42, 3)
check_true("claim_lines never exceeds the line budget", len(_cl) <= 3, str(len(_cl)))
check_true("a truncated claim says so", _cl[-1].endswith("\u2026"), repr(_cl[-1]))
# A budget of zero must yield nothing rather than raising or drawing one line.
check("a zero budget draws no claim", families_figure.claim_lines(_long, 42, 0), [])
# Year ticks: a density-warped axis stretches each recent year to hundreds of
# pixels, and 5-year candidates alone left 2021-2024 unlabeled on the widest,
# densest part of the plot. Single years fill in wherever they fit.
_xf = lambda y: {2000: 0, 2005: 20, 2010: 40, 2015: 60, 2020: 100}.get(y, 100 + (y - 2020) * 150) if y >= 2020 \
    else (y - 2000) * 4  # noqa: E731
_tk = families_figure.year_ticks(2000, 2026, _xf, warp=0.85)
check("year ticks keep the 5-year grid", {2000, 2010, 2020} <= set(_tk), True)
check("year ticks fill single years where the axis is stretched", {2021, 2022, 2023, 2024, 2026} <= set(_tk), True)
check("year ticks never crowd (>= 34px apart)", all(_xf(b) - _xf(a) >= 34 for a, b in zip(_tk, _tk[1:])), True)
check("year ticks skip single years in a compressed span", 2003 in _tk, False)
check("an unwarped axis keeps the plain 5-year grid (no single-year fill)",
      families_figure.year_ticks(1960, 2000, lambda y: (y - 1960) * 20, warp=0), list(range(1960, 2001, 5)))

# The timeline is a standard deliverable (offered on every review), so its standard
# settings are the defaults: dots sized by citations, internal citations picked up
# from beside rows.json, and the exact arguments recorded without clobbering notes.
_ffa = families_figure.build_parser().parse_args(
    ["--rows", "r.json", "--families", "f.json", "--out-prefix", "x"])
check("figure: dots are sized by citations by default", _ffa.size_by_citations, "sqrt")
check("figure: --size-by-citations none restores binary dots",
      families_figure.build_parser().parse_args(
          ["--rows", "r", "--families", "f", "--out-prefix", "x", "--size-by-citations", "none"]
      ).size_by_citations, "none")
_ffd = tempfile.mkdtemp()
check("figure: no internal_citations.json beside rows means none",
      families_figure.resolve_internal(None, os.path.join(_ffd, "rows.json")), None)
open(os.path.join(_ffd, "internal_citations.json"), "w").write("{}")
check("figure: internal_citations.json beside rows is picked up",
      families_figure.resolve_internal(None, os.path.join(_ffd, "rows.json")),
      os.path.join(_ffd, "internal_citations.json"))
check("figure: an explicit --internal wins", families_figure.resolve_internal("mine.json", "rows.json"),
      "mine.json")
_argv = ["--rows", "rows.json", "--families", "families.json", "--out-prefix", "t_families",
         "--title", "My topic — families", "--time-warp", "0.85"]
check("figure: recorded args parse from both file formats",
      families_figure.recorded_argvs(
          "# note\nfamilies_figure.py --rows rows.json --families families.json "
          "--out-prefix t_families --title 'My topic — families' --time-warp 0.85\n"
          "python3 ../literature-review-toolkit/tools/families_figure.py \\\n"
          "  --rows rows.json --families families.json \\\n  --out-prefix other\n"),
      [_argv, ["--rows", "rows.json", "--families", "families.json", "--out-prefix", "other"]])
_ffr = os.path.join(_ffd, "figure_render_args.txt")
check("figure: args file written when absent", families_figure.record_args(_argv, _ffd), "written")
check("figure: the written file round-trips", families_figure.recorded_argvs(open(_ffr).read()), [_argv])
open(_ffr, "w").write("# hand-written tuning notes\nfamilies_figure.py --rows rows.json --out-prefix old\n")
check("figure: a different render is reported, never overwritten",
      (families_figure.record_args(_argv, _ffd), open(_ffr).read().startswith("# hand-written")),
      ("unrecorded", True))

# --- families_figure: label placement never gives up blindly (2026-09-19) -----
# Placement tries 12 vertical tiers and, if every one is taken, used to fall back
# to TIERS[-1] unconditionally — registering a box that overlaps a label already
# placed. On cognitive_map_representation that put "Tolman 1948" on top of
# "O'Keefe 1971": two early, heavily-cited papers crowded at the compressed left
# end of a warped axis. The fallback now picks the LEAST-overlapping tier, so a
# crowded lane degrades to the best available slot instead of an arbitrary one.
check("no overlap between disjoint boxes",
      families_figure._overlap_area((0, 10, 0, 10), (20, 30, 0, 10)), 0.0)
check("touching edges do not count as overlap",
      families_figure._overlap_area((0, 10, 0, 10), (10, 20, 0, 10)), 0.0)
check("overlap area is width times height",
      families_figure._overlap_area((0, 10, 0, 10), (5, 25, 5, 8)), 15.0)
check("full containment is the inner area",
      families_figure._overlap_area((0, 10, 0, 10), (2, 4, 2, 7)), 10.0)
check_true("placement falls back to the least-overlapping tier, not the last one",
           "TIERS[-1]" not in _FFSRC_EARLY and "best_pen" in _FFSRC_EARLY)

# --- families_figure: the lane title needs a HIT TARGET (2026-09-19) ---------
# The hover panel was wired to the .lanelabel <g>, but an SVG <g> has no geometry
# of its own and <text> only receives pointer events on the rendered glyph
# strokes. So the panel fired only when the cursor landed exactly on a letter,
# and not in the gaps between words or lines — which reads as "the hover does not
# work". The node groups already solve this with an invisible
# `<circle class="hit" fill="none" pointer-events="all">`; the lane label needs
# the same treatment, a transparent rect over the whole left-margin band.
# Slice the whole lane-label emit block rather than a fixed character window, so
# adding a comment to the renderer cannot silently disarm the check.
_LANEBLOCK = _FFSRC_EARLY.split('class="lanelabel"')[1].split("s.append('</g>')")[0]
check_true("lane label carries an invisible hit rect", 'class="hit"' in _LANEBLOCK)
check_true("the lane hit target accepts pointer events",
           'pointer-events="all"' in _LANEBLOCK)
check_true("the lane hit target is invisible", 'fill="none"' in _LANEBLOCK)

# --- families_figure: the hover panel sits ON the legend (2026-09-19) --------
# The panel was anchored to the lane label's RIGHT edge (r.right + 14), which put
# it exactly over the start of the plot and hid the earliest papers — the whole
# left end of the timeline, which on a time-warped axis is where the foundational
# work lives. It is now anchored to the label's LEFT edge and sized to the legend
# band, so it covers the legend it belongs to instead of the data.
check_true("hover panel is not anchored to the label's right edge",
           "r.right+14" not in _SHELL and "r.right + 14" not in _SHELL)
check_true("hover panel anchors to the label's left edge", "r.left" in _SHELL)
check_true("hover panel is sized to the legend band",
           "r.right-r.left" in _SHELL or "r.right - r.left" in _SHELL)
# Width must be applied BEFORE offsetHeight is read, or the vertical clamp uses a
# height measured at the old width and can push the panel off-screen.
check_true("panel width is set before its height is measured",
           _SHELL.index("famtip.style.width") < _SHELL.index("famtip.offsetHeight"))

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
# The version is computed from git history (tools/version.py) and gen_docs stamps
# it into the manifests, skill, README and docs, so no copy can drift.
check("sync_version rewrites the stated version",
      gen_docs.sync_version("footer: Version 0.1.0 · MIT", r"Version (\d+\.\d+\.\d+)", "0.2.0"),
      "footer: Version 0.2.0 · MIT")
try:
    gen_docs.sync_version("no version here", r"Version (\d+\.\d+\.\d+)", "0.2.0")
    _raised = False
except ValueError:
    _raised = True
check("sync_version raises when a target lost its version string", _raised, True)
# version.py: a large commit bumps MINOR and resets PATCH; small ones bump PATCH;
# a commit that only restates the version changes nothing.
check("version: first large commit gives 0.1.0, small ones count up",
      version.version_from_sizes([(1588, False), (178, False), (18, False)], major=0), (0, 1, 2))
check("version: a large commit resets the patch count",
      version.version_from_sizes([(900, False), (5, False), (400, False), (3, False)], major=0), (0, 2, 1))
check("version: binary-only is a patch, version-only is nothing",
      version.version_from_sizes([(900, False), (0, True), (0, False)], major=0), (0, 1, 1))
# A declared Version-Bump (judged from the work) overrides size in either direction,
# and only a declaration can bump MAJOR.
check("version: a declared bump overrides size",
      version.version_from_sizes([(900, False), (3000, False, "patch"), (5, False, "minor")], major=1),
      (1, 2, 0))
check("version: a declared major resets minor and patch",
      version.version_from_sizes([(900, False), (5, False), (10, False, "major"), (5, False)], major=1),
      (2, 0, 1))
check("version: trailer parsed from a commit message",
      version.declared_bump("Add a flag\n\nBody.\n\nVersion-Bump: Minor\nCo-Authored-By: X"), "minor")
check("version: no trailer means no declaration", version.declared_bump("Fix a typo"), None)
_PATCH = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,2 +1,2 @@
-Version 0.1.0 · MIT license
+Version 0.2.0 · MIT license
-old line
+new line
+--flag documented
diff --git a/x.png b/x.png
Binary files a/x.png and b/x.png differ
"""
check("version: diff lines counted, headers and version-only lines skipped",
      version.count_lines(_PATCH), (3, True))
# Only a clean tree can be checked here: uncommitted work has no Version-Bump
# trailer yet (gen_docs.py --check --bump <level> covers it). CI is always clean.
if version._pending() == (0, False):
    check("every version target agrees with the version computed from history",
          [rel for rel, stale in gen_docs.version_status() if stale], [])


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

# ---- PMC ids: case-insensitive prefix, percent-encoded in the URL -----------
# A lower-case "pmc123" never matched the "PMC" strip, so the whole string went
# to esummary as the id; NCBI returned nothing and a real, correctly-cited paper
# was reported unverifiable. Caught by mvdoc in review of the
# gallantlab-claude-skills port (2026-05-08) and never ported back here.
_seen_urls = []
_orig_vj = verify.http_json


def _capture(payload):
    def _f(url, **kw):
        _seen_urls.append(url)
        return payload
    return _f


_PMC_REC = {"result": {"11304553": {"uid": "11304553", "title": "Semantic reconstruction",
                                    "pubdate": "2023", "authors": [{"name": "Tang J"}],
                                    "source": "Nat Neurosci"}}}
verify.http_json = _capture(_PMC_REC)
_hi = verify.lookup_pmc("PMC11304553")
_seen_urls.clear()
_lo = verify.lookup_pmc("pmc11304553")
check("a lower-case pmc prefix resolves like the upper-case form", _lo, _hi)
check_true("the pmc prefix is stripped whatever its case", "id=11304553&" in _seen_urls[0], _seen_urls[0])
check_true("a real record is still returned (the result key is not quoted)", _lo is not None)

# The id is interpolated into a URL, so it is percent-encoded there — but the
# `result` dict is keyed by the id as sent, so the key must stay unquoted.
verify.http_json = _capture({"result": {}})
_seen_urls.clear()
verify.lookup_pubmed_id("37127759 x")
check_true("a stray character in an id is percent-encoded in the URL",
           "id=37127759%20x&" in _seen_urls[0], _seen_urls[0])
verify.http_json = _orig_vj

# ---- verify is a gate: exit 0 only when every verdict is OK -----------------
# It used to always exit 0, so `verify.py && references.py ...` sailed past a
# run full of NOT-FOUNDs; the other two gates already failed loud.
check("verify gate passes an all-OK run", verify.gate_code([{"verdict": "OK"}] * 3), 0)
for _v in ("MISMATCH", "NOT-FOUND", "ERROR"):
    check(f"verify gate fails a run with a {_v}",
          verify.gate_code([{"verdict": "OK"}, {"verdict": _v}]), 1)


# --- families_figure: dot size proportional to citation count (2026-09-19) ----
# Size used to be binary — a big dot meant "labeled landmark", a small dot meant
# everything else — so the figure said nothing about how much a paper was
# actually cited. --size-by-citations maps the count onto the radius. Citation
# counts run over four orders of magnitude (0 to ~24k in a real corpus), so a
# raw-radius mapping is unusable; log compresses the tail, sqrt is
# area-proportional (the perceptually honest one) against a high-percentile
# reference so a single outlier cannot flatten everything else.
_cites = [0, 1, 10, 100, 1000, 10000]

for _mode in ("log", "sqrt"):
    _f = families_figure.radius_scale(_mode, _cites, 2.0, 11.0)
    check(f"{_mode}: an uncited paper sits at the floor", round(_f(0), 3), 2.0)
    check(f"{_mode}: a missing count sits at the floor", round(_f(-1), 3), 2.0)
    check_true(f"{_mode}: the radius never exceeds the ceiling",
               all(_f(c) <= 11.0 + 1e-9 for c in _cites + [10 ** 6]))
    check_true(f"{_mode}: the radius rises with the citation count",
               all(_f(a) <= _f(b) for a, b in zip(_cites, _cites[1:])))

# The scale has to SEPARATE the mid-range, which is the whole point. A log scale
# on this corpus must put 100 citations visibly above 10, not bunch both at the
# floor: the tell that a scale is mis-parameterized is a flat low end.
_flog = families_figure.radius_scale("log", _cites, 2.0, 11.0)
check_true("log separates 10 from 100 citations by >= 1px", _flog(100) - _flog(10) >= 1.0)
check_true("log separates 100 from 1000 citations by >= 1px", _flog(1000) - _flog(100) >= 1.0)

# sqrt against the MAX would flatten a heavy tail (sqrt(100/24178) = 6% of the
# range). The reference is a high percentile and everything above it clamps.
_fsq = families_figure.radius_scale("sqrt", [0] * 95 + [50] * 4 + [24178], 2.0, 11.0)
check("sqrt clamps everything above its reference", round(_fsq(24178), 3), 11.0)
check_true("sqrt does not flatten the bulk against a lone outlier", _fsq(50) > 6.0)

# Variable radii break the fixed-step beeswarm: it tests |off_i - off_j| against
# a CONSTANT 2r, so an 11px dot and a 2px dot packed 5.6px apart overlap. With a
# radius function the packer must test the two circles' OWN radii.
_items = [(100.0, "a"), (100.0, "b"), (100.0, "c"), (103.0, "d"), (106.0, "e")]
_rad = {"a": 11.0, "b": 11.0, "c": 2.0, "d": 9.0, "e": 4.0}
_packed = families_figure.beeswarm(_items, radius=lambda ref: _rad[ref])
_bad = [(p, q) for i, p in enumerate(_packed) for q in _packed[i + 1:]
        if ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5 < _rad[p[2]] + _rad[q[2]] - 0.01
        and abs(p[1]) < 52 and abs(q[1]) < 52]
check("variable-radius beeswarm packs without overlap", _bad, [])

# The default path must be byte-identical to the old fixed-radius packing, or
# every figure rendered without the flag shifts.
check("beeswarm without a radius function is unchanged",
      families_figure.beeswarm(_items),
      [(100.0, 0, "a"), (100.0, 11.2, "b"), (100.0, -11.2, "c"),
       (103.0, 22.4, "d"), (106.0, 0, "e")])

# A size encoding the reader cannot decode is decoration. The figure must carry
# a size legend whenever --size-by-citations is on.
check_true("the renderer emits a size legend", "sizelegend" in _FFSRC_EARLY)


# When no slot in the lane is clear the packer must take the LEAST-buried one.
# The first draft fell back to `off = 0.0`, which is dead center — the single
# worst slot available, right on top of the dot already there.
_crowd = families_figure.beeswarm([(50.0, "a"), (50.0, "b")], maxoff=5,
                                  radius=lambda ref: 9.0)
_boff = dict((ref, off) for _, off, ref in _crowd)
check("the first dot takes the center", _boff["a"], 0.0)
check_true("a buried dot moves as far from the center as the lane allows",
           abs(_boff["b"]) == 5 - 0.5, str(_boff))
# and nothing is ever placed outside the lane it belongs to
_packed_t = families_figure.beeswarm([(50.0, f"p{i}") for i in range(40)],
                                     maxoff=20, radius=lambda ref: 9.0)
check_true("no dot is placed outside the lane",
           all(abs(off) <= 20 for _, off, _ in _packed_t))



# --- families_figure: Next/Prev must follow the picture (2026-09-19) ---------
# The walk-through sorted on (year, reference string). The reference string bears
# no relation to where the dot was drawn, and the beeswarm fans a year's papers
# out from the lane center (0, +d, -d, +2d, -2d), so Next sent the highlight
# hopping up and down the column: 137 backward steps inside a year-column on the
# 555-paper cortical-layers corpus. Every paper of one year shares an x, so a
# year IS a vertical column; the tie-break has to be the dot's own drawn y.
check_true("the client data carries each dot's drawn y",
           _FFSRC_EARLY.count("ny=round(y, 1)") == 2)
_ORDER = _FFSRC_EARLY.split("const ORDER=")[1].split(";")[0]
check_true("the walk-through breaks year ties on the drawn y, not the ref string",
           "DATA[a].ny-DATA[b].ny" in _ORDER, _ORDER)
check_true("the drawn y is tried before the ref string",
           _ORDER.index("ny") < _ORDER.index("localeCompare"), _ORDER)


# --- families_figure: the home-lab ring must be visible, and settable (2026-09-20)
# WHICH lab gets starred has always been a parameter (--lab-author / the
# LITREVIEW_LAB_AUTHOR env var, off by default so the tool is lab-neutral). What
# was NOT settable was the ring's COLOR, hardcoded to the same #d4a017 that sits
# at PALETTE[4] — so a home-lab paper landing in the FIFTH family got a gold ring
# on a gold dot and the highlight vanished. Live in gallant_lab_in_context: two
# lab papers in family 5.
check_true("the gold default really is a palette color (the bug's root)",
           "#d4a017" in families_figure.PALETTE)

_lanes5 = families_figure.PALETTE[:5]          # a 5-family figure includes the gold
_lanes4 = families_figure.PALETTE[:4]          # a 4-family figure does not

_c, _note = families_figure.lab_ring_color("#d4a017", _lanes4)
check("no collision keeps the default gold", _c, "#d4a017")
check("no collision raises no note", _note, None)

_c, _note = families_figure.lab_ring_color("#d4a017", _lanes5)
check_true("a colliding default is replaced", _c.lower() != "#d4a017", _c)
check_true("the replacement is not itself a lane color",
           _c.lower() not in {x.lower() for x in _lanes5}, _c)
check_true("the substitution is reported", bool(_note), str(_note))

# An explicitly chosen color is HONORED even when it collides — the operator may
# know something the tool does not — but it must still say so.
_c, _note = families_figure.lab_ring_color("#2a9d8f", _lanes5, explicit=True)
check("an explicit color is honored", _c, "#2a9d8f")
check_true("an explicit collision is still warned about", bool(_note), str(_note))

# The label ink is derived from the ring color, not a second hardcoded constant,
# or setting --lab-color leaves the starred label in the old gold.
_ink = families_figure.darken("#d4a017", 0.55)
check_true("darken returns a hex color", re.fullmatch(r"#[0-9a-f]{6}", _ink) is not None, _ink)
check_true("darken actually darkens",
           int(_ink[1:3], 16) < 0xd4 and int(_ink[3:5], 16) < 0xa0, _ink)
check("darken is a no-op at factor 1.0", families_figure.darken("#d4a017", 1.0), "#d4a017")
check("darken clamps to black", families_figure.darken("#d4a017", 0.0), "#000000")


# ---- bib_viewer -----------------------------------------------------------
# The viewer is the reader's route from a claim in a review back to the summary
# that produced it, so its invariants are: every corpus row appears, exactly once;
# the cited chip is distinguishable from the OpenAlex count beside it; and the
# provenance note naming the author is present whenever an author is given.
_spec = {"families": [
    {"key": "a", "name": "Family A", "claim": "A's claim."},
    {"key": "b", "name": "Family B", "claim": "B's claim."},
]}
_rows = [
    {"ref": "A-01", "apa": "Alpha, A. (1999). First paper. J.", "doi": "10.1/a",
     "link": "https://doi.org/10.1/a", "summary": "First summary.", "tag": "classic",
     "topic": "Topic one", "lane": "A", "search_year": 1999, "cite_openalex": 12,
     "family": "Family A"},
    {"ref": "B-01", "apa": "Beta, B. (2020). Second paper. J.", "doi": "10.1/b",
     "summary": "Second summary.", "tag": "recent-empirical", "topic": "Topic two",
     "lane": "B", "search_year": 2020, "family": "Family B"},
    {"ref": "A-02", "apa": "Gamma, G. (1980). Third paper. J.", "summary": "Third summary.",
     "topic": "Topic one", "lane": "A", "search_year": 1980, "family": "Family A"},
]

_groups = bib_viewer.group_rows(_rows, _spec)
check("groups follow the spec's family order", [g[1] for g in _groups], ["Family A", "Family B"])
check("every row lands in exactly one group", sum(len(g[3]) for g in _groups), len(_rows))

# A family the spec does not know is a build error, not a silently dropped paper.
try:
    bib_viewer.group_rows(_rows + [dict(_rows[0], ref="C-01", family="Family C")], _spec)
    check_true("an unknown family raises", False, "no ValueError")
except ValueError as exc:
    check_true("an unknown family raises", "Family C" in str(exc), str(exc))

# With no spec, grouping falls back to the rows' own Topic column.
check("grouping falls back to topic", [g[1] for g in bib_viewer.group_rows(_rows)],
      ["Topic one", "Topic two"])

_block = bib_viewer.render(_rows, spec=_spec, cited={"A-01": 7},
                           author="Claude Opus 5",
                           author_note="An artificial intelligence developed by Anthropic")
check("every row is rendered once", _block.count('<li class="bref"'), len(_rows))
check("only cited rows are marked", _block.count('data-cited="1"'), 1)
check_true("the cited chip links to the works-cited entry", 'href="#ref-7"' in _block, _block[:0])
check_true("the chip says 'ref N', not 'cited N'",
           ">ref 7</a>" in _block and ">cited 7</a>" not in _block)
check_true("the OpenAlex count stays a separate field", "12 cites" in _block)
check_true("the provenance note names the author", "Claude Opus 5" in _block and
           "Where these summaries come from" in _block)
check_true("the provenance note disclaims full texts",
           "no figure, table or methods section was read" in _block)
check_true("a citation map enables the cited-only filter", 'id="bibcited"' in _block)
check_true("rows sort oldest first within a family",
           _block.index("Third paper") < _block.index("First paper"))
# A-01 carries a full link, B-01 only a bare `doi` (which still resolves to a
# link), A-02 neither — so exactly the two identifiable rows are linked.
check("a bare doi still links; a row with neither does not",
      _block.count('class="bref-doi"'), 2)
check_true("a bare doi is linked through doi.org",
           'href="https://doi.org/10.1/b"' in _block)

# No citation map: no chips and no cited-only filter, so a standalone corpus
# viewer does not offer a control that would hide everything.
_plain = bib_viewer.render(_rows, spec=_spec, author="Claude Opus 5", author_note="An AI")
check("no chips without a citation map", _plain.count('data-cited="1"'), 0)
check_true("no cited-only filter without a citation map", 'id="bibcited"' not in _plain)

# No author: no provenance note to make a claim the caller did not authorize.
check_true("no provenance note without an author",
           "Where these summaries come from" not in bib_viewer.render(_rows, spec=_spec))

check_true("the standalone page is a complete document",
           bib_viewer.standalone(_rows, _spec, title="T", author="X", author_note="An AI")
           .startswith("<!doctype html>"))
check_true("the standalone page declares a charset",
           '<meta charset="utf-8">' in bib_viewer.standalone(_rows, _spec, title="T"))


# ---- prose_audit: measuring a review's readability (2026-09-22) ------------
# Every case is a real miscount from the pass that cut a 555-reference review's
# mean sentence from 31 to 24 words.

# A sentence ending in a numeral is a sentence end. Guarding trailing digits (to
# protect decimals) glued two real sentences into one 54-word phantom; decimals
# need no guard because '0.1 mm' has no space after the period.
check("a numeral ends a sentence",
      len(prose_audit.sentences("Latencies are shortest in layers 4C and 6. CSD begins there.")), 2)
check("a decimal does not end a sentence",
      len(prose_audit.sentences("Localization is good to 0.1 mm at best.")), 1)

# 'et al.' is the abbreviation that matters: unguarded, it cuts almost every
# citation-bearing sentence of an APA-cited review in half.
check("et al. does not end a sentence",
      len(prose_audit.sentences("Nandy et al. found a laminar profile. It replicated.")), 2)
check("e.g. does not end a sentence",
      len(prose_audit.sentences("Some layers (e.g. 4C) are unoriented.")), 1)

# A flattened HTML table reads as one enormous sentence — a real one measured
# 153 words and swamped the section it was reported in.
_tbl = "<p>Short prose here.</p><table><tr><td>a</td><td>b</td></tr></table>"
check_true("tables are dropped before measuring", "a" not in prose_audit.detag(_tbl))
check_true("table cells kept when asked", "a" in prose_audit.detag(_tbl, drop_tables=False))

# Citation markers must not be counted as prose words, and entities must resolve.
check("markers are not words",
      prose_audit.detag("<p>Layer 4 is the input layer[[R-01|R-02]].</p>"),
      "Layer 4 is the input layer.")
check("entities are unescaped", prose_audit.detag("<p>1909&ndash;2026</p>"), "1909–2026")

# Blocks are read by static parse, never by importing the project's script, and
# a section keeps its slug so a finding can be mapped back to a section.
_page = os.path.join(os.path.dirname(__file__), "_tmp_review_page.py")
with open(_page, "w", encoding="utf-8") as fh:
    fh.write('BODY = [\n("A title", "sec-demo", """<p>' + ("word " * 40)
             + 'and so on[[R-01]]. A second sentence[[R-02]].</p>"""),\n]\n'
             'PAGE = """<!doctype html><style>p{color:red}</style>"""\n')
_blocks = prose_audit.page_blocks(_page)
check("section prose is named by its slug", sorted(_blocks), ["BODY:sec-demo"])
check_true("the page template is not counted as prose",
           not any("doctype" in v for v in _blocks.values()))
check("citations are read from the markers",
      prose_audit.cites_in(_blocks["BODY:sec-demo"], False), {"R-01", "R-02"})
os.remove(_page)


# ---- network efficiency + verify gaps (added 2026-09-25) ------------------
# A 475-ref arXiv-heavy build spent ~85 min in network tools, 53 of them in
# canon: one arXiv request per row, 0.25 s apart, against arXiv's ~3 s courtesy
# interval, so 39 rows each slept 45 s of 429 backoff and then failed. Everything
# here runs offline: urlopen / arxiv_fetch / crossref_work are stubbed and every
# sleep is recorded instead of taken.
def _stamp(row, verdict="OK"):
    d, a = common.ids_of(row)
    row["verified"] = {"verdict": verdict, "doi": d, "arxiv": a, "source": "doi", "issues": [],
                       "at": common.GATES_SINCE}
    return row


import contextlib as _ctx  # noqa: E402
import json  # noqa: E402
import time as _time  # noqa: E402

import citations  # noqa: E402


@_ctx.contextmanager
def _patched(obj, **attrs):
    old = {k: getattr(obj, k) for k in attrs}
    for k, v in attrs.items():
        setattr(obj, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(obj, k, v)


@_ctx.contextmanager
def _sleeps():
    got = []
    with _patched(_time, sleep=lambda s: got.append(s)):
        yield got


def _atom(ids):
    ents = "".join(
        f"<entry><id>http://arxiv.org/abs/{i}v1</id><title>Paper {i}</title>"
        f"<published>2023-01-01T00:00:00Z</published><author><name>Ada Lovelace</name></author>"
        f"</entry>" for i in ids)
    return f'<feed xmlns="http://www.w3.org/2005/Atom">{ents}</feed>'.encode()


class _FakeArxiv:
    """arxiv_fetch stand-in: counts calls; `fail_calls` lists call numbers that raise."""
    def __init__(self, fail_calls=()):
        self.calls, self.fail_calls = [], set(fail_calls)

    def __call__(self, ids):
        self.calls.append(list(ids))
        if len(self.calls) in self.fail_calls:
            raise urllib.error.HTTPError("u", 429, "slow down", {}, None)
        return {e["id"]: e for e in common.arxiv_entries(_atom(ids))}


# T1 — one batched prefetch, shared by verify and canon.
_ids = [f"2301.{n:05d}" for n in range(120)]
_fa = _FakeArxiv()
with _patched(common, arxiv_fetch=_fa), _sleeps() as _sl:
    _ent, _err = common.arxiv_batch(_ids)
check("arxiv_batch: 120 ids take 3 requests of <=50", [len(c) for c in _fa.calls], [50, 50, 20])
check("arxiv_batch: every id resolved", (len(_ent), _err), (120, set()))
check("arxiv_batch: 3 s courtesy pause between chunks only", _sl, [3.0, 3.0])
_fa = _FakeArxiv(fail_calls={2})
with _patched(common, arxiv_fetch=_fa), _sleeps():
    _ent, _err = common.arxiv_batch(_ids)
check("arxiv_batch: a failed chunk marks exactly its ids errored", len(_err), 50)
check_true("arxiv_batch: errored ids are not reported as misses", not (_err & set(_ent)))

_AROWS = [_stamp(r) for r in
          [{"ref": f"A{n}", "doi": f"10.48550/arXiv.2301.{n:05d}", "apa": ""} for n in range(60)]]
_fa = _FakeArxiv()
with _patched(common, arxiv_fetch=_fa), _sleeps():
    _res = references.canon_rows(_AROWS, "ref", "2026-09-25", sleep=0.25, retry_wait=0)
check("canon: 60 arXiv rows cost 2 batched requests, not 60", len(_fa.calls), 2)
check("canon: every arXiv row rebuilt from the batch", _res["rebuilt"], 60)
check_true("canon: arXiv-built apa names the paper",
           _AROWS[0]["apa"].startswith("Lovelace, A. (2023). Paper 2301.00000."), _AROWS[0]["apa"])

# T2 — a failed batch is retried inside the run, not by a hand-built rerun file.
_AROWS = [_stamp(r) for r in
          [{"ref": f"A{n}", "doi": f"10.48550/arXiv.2301.{n:05d}", "apa": ""} for n in range(3)]]
_fa = _FakeArxiv(fail_calls={1})
with _patched(common, arxiv_fetch=_fa), _sleeps():
    _res = references.canon_rows(_AROWS, "ref", "2026-09-25", sleep=0, retry_wait=0)
check("canon: an arXiv 429 batch is retried in-run", (_res["rebuilt"], _res["failed"]), (3, []))


def _cr_record(first="Smith", title="A real paper", year=2020):
    return {"title": title, "year": str(year), "authors": [(first, "J")],
            "people": [f"{first}, J."], "first_author": f"{first} J", "journal": "J Neurosci",
            "volume": "1", "issue": None, "pages": "1-2", "book": "", "publisher": ""}


class _FlakyCR:
    """crossref_work stand-in: the first call per DOI raises 503, later calls succeed."""
    def __init__(self, rec=None):
        self.seen, self.rec = {}, rec

    def __call__(self, doi, fallback_venue=""):
        self.seen[doi] = self.seen.get(doi, 0) + 1
        if self.seen[doi] == 1:
            raise urllib.error.HTTPError("u", 503, "busy", {}, None)
        return self.rec if self.rec is not None else _cr_record()


_JROWS = [_stamp(r) for r in
          [{"ref": "J1", "doi": "10.1523/x1", "apa": ""}, {"ref": "J2", "doi": "10.1523/x2", "apa": ""}]]
with _patched(common, crossref_work=_FlakyCR()), _sleeps():
    _res = references.canon_rows(_JROWS, "ref", "2026-09-25", sleep=0, retry_wait=0)
check("canon: a transient CrossRef failure is retried in-run", (_res["rebuilt"], _res["failed"]), (2, []))


def _always_503(doi, fallback_venue=""):
    raise urllib.error.HTTPError("u", 503, "busy", {}, None)


_JROWS = [_stamp(r) for r in
          [{"ref": "J1", "doi": "10.1523/x1", "apa": "Old, A. (2020). Agent typed. J."}]]
with _patched(common, crossref_work=_always_503), _sleeps():
    _res = references.canon_rows(_JROWS, "ref", "2026-09-25", sleep=0, retry_wait=0)
check("canon: a row that still fails after the retry is named", _res["failed"], ["J1"])
check_true("canon: a failed row is not stamped canonical", "canonical_at" not in _JROWS[0])

# C4 — a source that answers with no usable record must not pass silently.
_JROWS = [_stamp(r) for r in
          [{"ref": "E1", "doi": "10.1038/editorial", "apa": "Nature. (2020). Editorial. Nature."}]]
with _patched(common, crossref_work=lambda d, fallback_venue="": dict(_cr_record(), people=[])), _sleeps():
    _res = references.canon_rows(_JROWS, "ref", "2026-09-25", sleep=0, retry_wait=0)
check("canon: a row the source cannot rebuild is named, not skipped silently", _res["kept"], ["E1"])

# T2 — --only canonicalizes the named rows and leaves every other row untouched.
_JROWS = [_stamp(r) for r in
          [{"ref": "J1", "doi": "10.1523/x1", "apa": "keep me"},
           {"ref": "J2", "doi": "10.1523/x2", "apa": ""}]]
with _patched(common, crossref_work=lambda d, fallback_venue="": _cr_record()), _sleeps():
    _res = references.canon_rows(_JROWS, "ref", "2026-09-25", sleep=0, retry_wait=0, only={"J2"})
check("canon --only: other rows untouched", (_JROWS[0]["apa"], "canonical_at" in _JROWS[0]), ("keep me", False))
check("canon --only: named row rebuilt", _res["rebuilt"], 1)

# T4 — sleep only after a row that actually went to the network. Stubbing
# urlopen (not http) keeps common.http's real bookkeeping in the path.
class _Resp:
    def __init__(self, body):
        self.body, self.headers = body, {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


def _cr_body(first="Smith", title="A real paper", year=2020):
    return json.dumps({"message": {"author": [{"family": first, "given": "J"}],
                                   "title": [title], "issued": {"date-parts": [[year]]},
                                   "container-title": ["J Neurosci"]}}).encode()


_CITS = [{"label": "X1", "arxiv": "2301.00001", "expect_first_author": "Lovelace", "expect_year": "2023",
          "title": "Paper 2301.00001"},
         {"label": "X2", "arxiv": "2301.00002", "expect_first_author": "Lovelace", "expect_year": "2023",
          "title": "Paper 2301.00002"},
         {"label": "J1", "doi": "10.1523/x1", "expect_first_author": "Smith", "expect_year": "2020",
          "title": "A real paper"}]
with _patched(common, arxiv_fetch=_FakeArxiv()), \
        _patched(urllib.request, urlopen=lambda req, timeout=30: _Resp(_cr_body())), _sleeps() as _sl:
    _out = verify.verify_all(_CITS, sleep=0.4, retry_wait=0)
check("verify: all three verified", [r["verdict"] for r in _out], ["OK", "OK", "OK"])
check("verify: rows answered by the arXiv prefetch do not sleep", _sl, [0.4])

# T2 — verify retries ERROR rows itself after a cool-down.
with _patched(common, arxiv_fetch=_FakeArxiv(fail_calls={1})), _sleeps() as _sl:
    _out = verify.verify_all(_CITS[:2], sleep=0, retry_wait=60)
check("verify: an errored arXiv chunk is retried in-run", [r["verdict"] for r in _out], ["OK", "OK"])
check_true("verify: the retry waits out the cool-down first", 60 in _sl, str(_sl))

# T2 — --only / --retry-from select rows; merge_reports splices results by label.
check("verify: --only selects by label",
      [c["label"] for c in verify.select_citations(_CITS, only={"J1"})], ["J1"])
check("verify: --retry-from selects the non-OK rows of a report",
      [c["label"] for c in verify.select_citations(
          _CITS, retry_from=[{"label": "X1", "verdict": "OK"}, {"label": "X2", "verdict": "ERROR"}])],
      ["X2"])
check("verify: merge_reports replaces by label and keeps order",
      verify.merge_reports([{"label": "A", "verdict": "ERROR"}, {"label": "B", "verdict": "OK"}],
                           [{"label": "A", "verdict": "OK"}]),
      [{"label": "A", "verdict": "OK"}, {"label": "B", "verdict": "OK"}])

# T3 — CrossRef has no 10.48550 DOIs; asking costs a 404 per row.
def _no_network(*a, **k):
    raise AssertionError("network call for an arXiv DOI")


_asked = []
with _patched(verify, lookup_crossref=lambda d: _asked.append(("crossref", d)),
              lookup_pubmed_title=lambda t: _asked.append(("pubmed-title", t))):
    _r = verify.verify_one({"label": "A", "doi": "10.48550/arXiv.2301.00001", "arxiv": "2301.00001",
                            "title": "AI safety via debate"}, {}, {"2301.00001"})
check("verify: an errored arXiv row is ERROR", _r["verdict"], "ERROR")
# A PubMed title search mis-resolves arXiv papers (on one build it answered an
# AI-debate paper with a physiotherapy article), and CrossRef has no
# 10.48550 DOIs: both lookups are pure cost. The in-run retry re-asks arXiv.
check("verify: an errored arXiv row asks neither CrossRef nor PubMed", _asked, [])
with _patched(xref, http_json=_no_network), _sleeps() as _sl:
    _refs, _inc = xref.fetch_all([{"slug": "A", "doi": "10.48550/arXiv.2301.00001"}], sleep=0.4, retry_wait=0)
check("xref: an arXiv DOI is skipped, complete, and costs no sleep", (_refs["A"], _inc, _sl), ([], [], []))

_calls = []


def _xref_flaky(doi):
    _calls.append(doi)
    return None if len(_calls) == 1 else [{"doi": "10.1/y"}]


with _patched(xref, crossref_refs=_xref_flaky), _sleeps():
    _refs, _inc = xref.fetch_all([{"slug": "B", "doi": "10.1/b"}], sleep=0, retry_wait=0)
check("xref: an incomplete fetch is retried in-run", (_inc, len(_refs["B"])), ([], 1))

# T5 — honor Retry-After (seconds, capped), and fall back to backoff without it.
def _urlopen_seq(*errs):
    seq = list(errs)

    def f(req, timeout=30):
        if seq:
            raise seq.pop(0)
        return _Resp(b"{}")
    return f


with _patched(urllib.request, urlopen=_urlopen_seq(
        urllib.error.HTTPError("u", 429, "slow", {"Retry-After": "7"}, None))), _sleeps() as _sl:
    common.http("https://example.org/x")
check("http: Retry-After seconds are honored", _sl, [7.0])
with _patched(urllib.request, urlopen=_urlopen_seq(
        urllib.error.HTTPError("u", 429, "slow", {"Retry-After": "9999"}, None))), _sleeps() as _sl:
    common.http("https://example.org/x")
check("http: Retry-After is capped", _sl, [120.0])
with _patched(urllib.request, urlopen=_urlopen_seq(
        urllib.error.HTTPError("u", 503, "busy", {}, None))), _sleeps() as _sl:
    common.http("https://example.org/x")
check("http: no Retry-After falls back to exponential backoff", _sl, [3])

# T5 — S2: at most 500 ids per POST, and a 400 is not retried or slept on.
_bodies = []


def _s2_ok(url, data=None, headers=None, **k):
    ids = json.loads(data)["ids"]
    _bodies.append(len(ids))
    return [{"citationCount": 1, "influentialCitationCount": 0} for _ in ids]


_items = [(f"k{n}", f"10.1/{n}") for n in range(1200)]
with _patched(citations, http_json=_s2_ok), _sleeps():
    _got = citations.fetch_s2(_items)
check("s2: 1200 ids go out in chunks of <=500", _bodies, [500, 500, 200])
check("s2: every chunk's results are mapped back", len(_got), 1200)
_n400 = []


def _s2_400(url, data=None, headers=None, **k):
    _n400.append(1)
    raise urllib.error.HTTPError("u", 400, "bad", {}, None)


with _patched(citations, http_json=_s2_400), _sleeps() as _sl:
    citations.fetch_s2(_items[:10])
check("s2: a 400 is not retried or slept on", (len(_n400), _sl), (1, []))

# T6 — the duplicate-scan prefilter must not change a single pair.
import difflib as _dl  # noqa: E402
import random as _rnd  # noqa: E402

_rng = _rnd.Random(7)
_words = "cortex layer visual neuron model deep laminar feedback alpha gamma coding".split()
_titles = [" ".join(_rng.choice(_words) for _ in range(_rng.randint(3, 8))) for _ in range(150)]
_DROWS = [{"ref": f"D{i}", "apa": f"Doe, J. (2020). {t}. J."} for i, t in enumerate(_titles)]


def _brute(rows, thr=0.88):
    out = []
    items = [(r["ref"], re.sub(r"[^a-z0-9 ]", "", common.parse_apa(r["apa"])["title"].lower()).strip())
             for r in rows]
    for i, (ka, ta) in enumerate(items):
        for kb, tb in items[i + 1:]:
            if abs(len(ta) - len(tb)) > 0.35 * max(len(ta), len(tb)):
                continue
            q = _dl.SequenceMatcher(None, ta, tb).ratio()
            if q >= thr:
                out.append((ka, kb))
    return out


check("duplicate_scan: prefilter finds exactly the brute-force pairs",
      [(a, b) for a, b, _, _ in references.duplicate_scan(_DROWS, "ref")], _brute(_DROWS))

# C1 — pre-canon rows verify against the SEARCH AGENT's claim, not an empty apa.
_pre = {"ref": "P1", "doi": "10.1/p", "apa": "", "search_author": "Amodei, D.",
        "search_year": 2016, "search_title": "Concrete problems in AI safety"}
_c = verify.rows_to_citations([_pre])[0]
check("rows_to_citations: pre-canon expectations come from search_*",
      (_c["expect_first_author"], _c["expect_year"], _c["title"]),
      ("Amodei", "2016", "Concrete problems in AI safety"))
check("rows_to_citations: 'D. Amodei' shape yields the surname",
      verify.rows_to_citations([dict(_pre, search_author="D. Amodei")])[0]["expect_first_author"], "Amodei")
_canon = dict(_pre, apa="Amodei, D., & Olah, C. (2016). Concrete problems in AI safety. arXiv.",
              canonical_at="2026-09-25", search_author="Wrong, X.")
check("rows_to_citations: a canonical row is checked against its apa",
      verify.rows_to_citations([_canon])[0]["expect_first_author"], "Amodei")
with _patched(verify, lookup_crossref=lambda d: {"title": "T", "year": "2020",
                                                   "first_author": "Smith J", "journal": "J"}):
    _r = verify.verify_one({"label": "N", "doi": "10.1/n"})
check("verify: a row with nothing to check against is UNCHECKED, not OK", _r["verdict"], "UNCHECKED")
check("verify gate fails an UNCHECKED row", verify.gate_code([_r]), 1)

# C2 — a DOI that resolves to a different paper by the same first author.
_rec = {"title": "Sparse coding in visual cortex", "year": "2020", "first_author": "Smith J", "journal": "J"}
with _patched(verify, lookup_crossref=lambda d: _rec):
    _bad = verify.verify_one({"label": "T", "doi": "10.1/t", "expect_first_author": "Smith",
                              "expect_year": "2020", "title": "Attention modulates auditory thalamus"})
    _good = verify.verify_one({"label": "T", "doi": "10.1/t", "expect_first_author": "Smith",
                               "expect_year": "2020", "title": "Sparse Coding in Visual Cortex."})
check("verify: a different title under the same author/year is a MISMATCH", _bad["verdict"], "MISMATCH")
check_true("verify: the title mismatch is named", any("title" in i for i in _bad["issues"]), str(_bad))
check("verify: case and punctuation differences still pass", _good["verdict"], "OK")

# C3 — with both ids, the journal DOI canon will cite must be checked too.
_arx = {"2301.00009": {"title": "Emergent behavior in agents", "year": "2023",
                       "first_author": "Ada Lovelace", "journal": "arXiv"}}
_both = {"label": "B", "doi": "10.1038/s1", "arxiv": "2301.00009", "expect_first_author": "Lovelace",
         "expect_year": "2023", "title": "Emergent behavior in agents"}
with _patched(verify, lookup_crossref=lambda d: {"title": "Unrelated chemistry paper", "year": "2023",
                                                  "first_author": "Curie M", "journal": "Nature"}):
    _r = verify.verify_one(_both, _arx, set())
check("verify: a wrong journal DOI beside a right arXiv id is a MISMATCH", _r["verdict"], "MISMATCH")
with _patched(verify, lookup_crossref=lambda d: {"title": "Emergent behavior in agents", "year": "2024",
                                                  "first_author": "Lovelace A", "journal": "Nature"}):
    _r = verify.verify_one(_both, _arx, set())
check("verify: arXiv id and journal DOI of one paper pass", (_r["verdict"], _r["source"]), ("OK", "arxiv+doi"))


def _cr_throttled(d):
    raise urllib.error.HTTPError("u", 503, "busy", {}, None)


with _patched(verify, lookup_crossref=_cr_throttled):
    _r = verify.verify_one(_both, _arx, set())
check("verify: an unreachable journal DOI is ERROR, not OK", _r["verdict"], "ERROR")


# ---- reference gates: stamp primitives (added 2026-09-26) ------------------
_g = _stamp({"ref": "A", "doi": "https://doi.org/10.1/ABC"})
check("ids_of normalizes the DOI form", common.ids_of(_g), ("10.1/abc", ""))
check_true("a stamp matches the same DOI written differently",
           common.verified_ok(dict(_g, doi="10.1/abc")))
check_true("a stamp lapses when the DOI changes", not common.verified_ok(dict(_g, doi="10.1/other")))
check_true("an arXiv row is identified by its id",
           common.ids_of({"doi": "10.48550/arXiv.2301.00001v2"}) == ("10.48550/arxiv.2301.00001v2", "2301.00001"))
_m = _stamp({"ref": "M", "doi": "10.1/m"}, "MISMATCH")
check_true("a MISMATCH is not verified", not common.verified_ok(_m))
_m["verify_override"] = {"reason": "preprint retitled on publication", "doi": "10.1/m", "arxiv": ""}
check_true("an override with a reason clears it", common.verified_ok(_m))
check_true("an override without a reason does not",
           not common.verified_ok(dict(_m, verify_override={"reason": " ", "doi": "10.1/m", "arxiv": ""})))
check_true("an override for other ids does not",
           not common.verified_ok(dict(_m, verify_override={"reason": "x", "doi": "10.1/z", "arxiv": ""})))
check_true("a legacy table is not gated", not common.is_gated([{"ref": "L", "canonical_at": "2026-08-18"}]))
check_true("a stamped table is gated", common.is_gated([{"ref": "L"}, _g]))
check_true("a table canonicalized since the gates is gated",
           common.is_gated([{"ref": "L", "canonical_at": common.GATES_SINCE}]))
check("summary_sha ignores surrounding whitespace", common.summary_sha(" A b. "), common.summary_sha("A b."))
check_true("summary_sha sees an edit", common.summary_sha("A b.") != common.summary_sha("A c."))
check_true("title_score lives in common", common.title_score("Sparse coding in visual cortex",
                                                               "Sparse Coding in Visual Cortex.") > 0.99)
check_true("verify uses the common title_score", verify.title_score is common.title_score)
check("load_optional_json returns the default for a missing file",
      common.load_optional_json("/nonexistent/litreview.json", {}), {})


# ---- reference gates: verify stamps (added 2026-09-26) ---------------------
import tempfile as _tmpf  # noqa: E402

_rows = [{"ref": "V1", "doi": "10.1/v1"}, {"ref": "V2", "doi": "10.1/v2"}]
_n = verify.stamp_rows(_rows, [{"label": "V1", "verdict": "OK", "source": "doi", "issues": []}],
                       "ref", "2026-09-26")
check("stamp_rows stamps only rows it has a result for", (_n, "verified" in _rows[1]), (1, False))
check("the stamp records verdict, ids and date",
      {k: _rows[0]["verified"][k] for k in ("verdict", "doi", "arxiv", "at")},
      {"verdict": "OK", "doi": "10.1/v1", "arxiv": "", "at": "2026-09-26"})

_rows = [_stamp({"ref": "O1", "doi": "10.1/o1"}, "MISMATCH")]
verify.override(_rows, "ref", "O1", "preprint retitled on publication", "2026-09-26")
check_true("an override makes the row verified", common.verified_ok(_rows[0]))
check("the override records what it overrode", _rows[0]["verify_override"]["overrode"], "MISMATCH")
for _bad, _why in [([{"ref": "O2", "doi": "10.1/o2"}], "no stamp"),
                   ([dict(_stamp({"ref": "O2", "doi": "10.1/o2"}, "MISMATCH"), doi="10.1/new")], "ids changed")]:
    check_true(f"override refused: {_why}", _raises(lambda: verify.override(_bad, "ref", "O2", "r", "2026-09-26")))
check_true("override refused: empty reason",
           _raises(lambda: verify.override([_stamp({"ref": "O3", "doi": "10.1/o3"}, "MISMATCH")],
                                           "ref", "O3", "  ", "2026-09-26")))

# Entrance test: --retry-from splices OLD verdicts into the report; only the
# rows verified in THIS run may be stamped.
_d = _tmpf.mkdtemp()
_rp, _prior, _rep = (os.path.join(_d, f) for f in ("rows.json", "prior.json", "report.json"))
common.dump_json([{"ref": "R1", "doi": "10.1/r1", "search_title": "T"},
                  {"ref": "R2", "doi": "10.1/r2", "search_title": "T"}], _rp)
common.dump_json([{"label": "R1", "verdict": "OK"}, {"label": "R2", "verdict": "ERROR"}], _prior)


def _fake_verify_all(cits, **k):
    return [{"label": c["label"], "verdict": "OK", "found": None, "source": "doi", "issues": []} for c in cits]


_argv = sys.argv
sys.argv = ["verify.py", "--rows", _rp, "--retry-from", _prior, "--out", _rep, "--email", "t@example.org"]
try:
    with _patched(verify, verify_all=_fake_verify_all):
        verify.main()
except SystemExit:
    pass
finally:
    sys.argv = _argv
_after = {r["ref"]: r for r in common.load_json(_rp)}
check("verify --retry-from stamps the re-verified row", _after["R2"].get("verified", {}).get("verdict"), "OK")
check_true("verify --retry-from does not stamp a row it only copied from the old report",
           "verified" not in _after["R1"])

# Entrance test: --citations and --rows together must not reach the stamping
# block with `rows` unbound (main() took the --citations branch, so `rows` was
# never assigned) — they are mutually exclusive, refused by argparse.
_d2 = _tmpf.mkdtemp()
_cp, _rp2 = (os.path.join(_d2, f) for f in ("cits.json", "rows.json"))
common.dump_json([{"label": "C1", "doi": "10.1/c1"}], _cp)
common.dump_json([{"ref": "C1", "doi": "10.1/c1"}], _rp2)
_before2 = common.load_json(_rp2)
_argv = sys.argv
sys.argv = ["verify.py", "--citations", _cp, "--rows", _rp2, "--email", "t@example.org"]
_exit = None
try:
    verify.main()
except SystemExit as e:
    _exit = e
finally:
    sys.argv = _argv
check_true("verify: --citations + --rows is refused with a SystemExit(2)",
           _exit is not None and _exit.code == 2, repr(_exit))
check("verify: --citations + --rows leaves the rows file untouched",
      common.load_json(_rp2), _before2)

# Entrance test: --override does no network I/O, so it must not require
# --email / LITREVIEW_EMAIL.
_d3 = _tmpf.mkdtemp()
_rp3 = os.path.join(_d3, "rows.json")
common.dump_json([_stamp({"ref": "O1", "doi": "10.1/o1"}, "MISMATCH")], _rp3)
_env = {k: v for k, v in os.environ.items() if k != "LITREVIEW_EMAIL"}
_argv = sys.argv
sys.argv = ["verify.py", "--rows", _rp3, "--override", "O1", "--reason", "retitled"]
try:
    with _patched(os, environ=_env):
        verify.main()
except SystemExit:
    pass
finally:
    sys.argv = _argv
_after3 = {r["ref"]: r for r in common.load_json(_rp3)}
check_true("verify: --override needs no --email/LITREVIEW_EMAIL",
           "verify_override" in _after3["O1"], _after3["O1"])


# ---- reference gates: canon refuses unverified rows (added 2026-09-26) -----
_crok = lambda d, fallback_venue="": _cr_record()   # noqa: E731
for _label, _row in [("never verified", {"ref": "U1", "doi": "10.1/u1", "apa": ""}),
                     ("verdict MISMATCH", _stamp({"ref": "U2", "doi": "10.1/u2", "apa": ""}, "MISMATCH")),
                     ("DOI changed after verify", dict(_stamp({"ref": "U3", "doi": "10.1/u3", "apa": ""}),
                                                        doi="10.1/u3-new"))]:
    with _patched(common, crossref_work=_crok), _sleeps():
        _res = references.canon_rows([_row], "ref", "2026-09-26", sleep=0, retry_wait=0)
    check(f"canon refuses a row: {_label}", (_res["unverified"], _res["rebuilt"], _row["apa"]), ([_row["ref"]], 0, ""))
_ov = _stamp({"ref": "U4", "doi": "10.1/u4", "apa": ""}, "MISMATCH")
_ov["verify_override"] = {"reason": "retitled preprint", "doi": "10.1/u4", "arxiv": ""}
with _patched(common, crossref_work=_crok), _sleeps():
    _res = references.canon_rows([_ov], "ref", "2026-09-26", sleep=0, retry_wait=0)
check("canon rebuilds an overridden row", (_res["rebuilt"], _res["unverified"]), (1, []))

# Entrance test: --repair must not re-date a legacy corpus (that would gate it).
_d = _tmpf.mkdtemp()
_rp = os.path.join(_d, "rows.json")
common.dump_json([{"ref": "L1", "apa": "Andrews‐Hanna, J. (2012). The brain. Neuron, 1, 1.",
                   "doi": "10.1/l1", "canonical_at": "2026-08-18"}], _rp)
_argv = sys.argv
sys.argv = ["references.py", "--rows", _rp, "--repair", "--email", "t@example.org"]
try:
    references.main()
except SystemExit:
    pass
finally:
    sys.argv = _argv
_L = common.load_json(_rp)[0]
check("--repair fixes the string damage", "‐" in _L["apa"], False)
check("--repair keeps the original canon date", _L["canonical_at"], "2026-08-18")


# ---- reference gates: one audit, gate defects, acknowledgments (2026-09-26) -
def _grow(ref="G1", doi="10.1/g1", summary="Tests whether a thing happens."):
    r = {"ref": ref, "doi": doi, "link": f"https://doi.org/{doi}", "summary": summary,
         "apa": "Smith, J. (2020). A real paper. J Neurosci, 1, 1-2.", "canonical_at": common.GATES_SINCE}
    _stamp(r)
    r["summary_check"] = {"verdict": "supported", "summary_sha": common.summary_sha(summary)}
    return r


def _codes(report, ref):
    return [d.split(" ")[0].rstrip(":") for d in report["defects"].get(ref, [])]


check("warning ids are stable, and deposit-year/cached-year are instance-specific",
      [references.warning_id(n) for n in [
          "multi-word surname 'Lambon Ralph' — confirm it is not a mis-split given name",
          "glued-footnote (a footnote digit stuck to the last title word — check the source)",
          "deposit-year: DOI encodes 1943 but the reference says 2010 — likely a publisher "
          "back-file/digitization date; verify by hand",
          "cached year 2019 != apa year 2020 — fix whichever is wrong, or delete the stale cache field",
          "cached year 'x' is not a year (apa says 2020)"]],
      ["multi-word-surname:Lambon Ralph", "glued-footnote", "deposit-year:1943/2010",
       "cached-year:2019/2020", "cached-year:x/2020"])
_gf = dict(_grow(ref="GF1", doi="10.1/gf1"),
          apa="Allport, G. W. (1962). The general and the unique in psychological science1. "
              "Journal of Personality, 30(3), 405-422.")
check("glued-footnote gets an instance-specific id from the row's title (audit_rows, not warning_id)",
      [w for w, _ in references.audit_rows([_gf], "ref")["warnings"]["GF1"]], ["glued-footnote:science1"])
_cy = _grow(ref="CY1", doi="10.1/cy1")
_cy["year"] = 2018
_rep = references.audit_rows([_cy], "ref", acks={"CY1": {"cached-year:2019/2020": "old, no longer matches"}})
check("an ack tied to a stale year pair does not cover a new mismatch on the same row",
      (_rep["failed"], _rep["stale_acks"]), (True, [("CY1", "cached-year:2019/2020")]))
_rep = references.audit_rows([_grow()], "ref")
check("a fully checked gated row passes", (_rep["gated"], _rep["failed"], _rep["defects"]), (True, False, {}))
_rep = references.audit_rows([_grow(), dict(_grow("G2", "10.1/g2"), doi="10.1/changed")], "ref")
check("a DOI edited after verify fails the audit", _codes(_rep, "G2"), ["unverified"])
_nd = {"ref": "B1", "apa": "Kuhn, T. S. (1962). The structure of scientific revolutions. U Chicago Press.",
       "summary": "", "canonical_at": common.GATES_SINCE}
check("a DOI-less row without a hand check fails", _codes(references.audit_rows([_grow(), _nd], "ref"), "B1"),
      ["hand-check-missing"])
_nd_ok = dict(_nd, hand_verified={"verdict": "confirmed", "source_checked": "LoC catalog record"})
check("a hand-checked DOI-less row passes", references.audit_rows([_grow(), _nd_ok], "ref")["defects"], {})
_ed = _grow()
_ed["summary"] = "Tests whether a different thing happens."
check("an edited summary is unchecked", _codes(references.audit_rows([_ed], "ref"), "G1"), ["summary-unchecked"])
_fl = _grow()
_fl["summary_check"]["verdict"] = "unsupported"
check("a flagged summary fails", _codes(references.audit_rows([_fl], "ref"), "G1"), ["summary-flagged"])
_na = _grow()
_na["summary_check"]["verdict"] = "no-abstract"
_rep = references.audit_rows([_na], "ref")
check("no abstract is a warning, and unacknowledged it fails a gated table",
      (_rep["defects"], [w for w, _ in _rep["unacked"]["G1"]], _rep["failed"]), ({}, ["no-abstract"], True))
_rep = references.audit_rows([_na], "ref", acks={"G1": {"no-abstract": "editorial, no abstract exists"}})
check("an acknowledged warning passes", _rep["failed"], False)
_rep = references.audit_rows([_na], "ref", acks={"G1": {"no-abstract": " "}})
check("an acknowledgment needs a reason", _rep["failed"], True)
_ackp = os.path.join(_tmpf.mkdtemp(), "audit_acks.json")
for _bad_reason in (True, ["a reason"], 5):
    common.dump_json({"G1": {"no-abstract": _bad_reason}}, _ackp)
    try:
        references.load_acks(_ackp)
        check_true("load_acks rejects a non-string reason", False, f"accepted {_bad_reason!r}")
    except ValueError as exc:
        check_true("load_acks rejects a non-string reason, naming ref and warning id",
                   "G1" in str(exc) and "no-abstract" in str(exc), str(exc))
_rep = references.audit_rows([_grow()], "ref", acks={"G1": {"glued-footnote": "fine"}})
check("a stale acknowledgment is reported, not failed", (_rep["stale_acks"], _rep["failed"]),
      ([("G1", "glued-footnote")], False))
_kept = _grow()
del _kept["canonical_at"]
_kept["verified"]["at"] = common.GATES_SINCE
check_true("a verified row canon could not rebuild is a warning",
           "kept-existing-apa" in [w for w, _ in references.audit_rows([_kept], "ref")["warnings"]["G1"]])
_legacy = [{"ref": "L1", "doi": "10.1/l1", "canonical_at": "2026-08-18",
            "apa": "Lambon Ralph, M. A. (2017). The neural basis. Nat Rev Neurosci, 1, 1."}]
_rep = references.audit_rows(_legacy, "ref")
check("a legacy table is audited as before: warnings do not fail", (_rep["gated"], _rep["failed"]), (False, False))

# Entrance test: --audit exits 1 on an unacknowledged warning in a gated table, 0 once acknowledged.
_d = _tmpf.mkdtemp()
_rp, _ap = os.path.join(_d, "rows.json"), os.path.join(_d, "audit_acks.json")
common.dump_json([_na], _rp)


def _audit_exit():
    _argv = sys.argv
    sys.argv = ["references.py", "--rows", _rp, "--audit", "--email", "t@example.org"]
    try:
        references.main()
        return 0
    except SystemExit as e:
        return e.code or 0
    finally:
        sys.argv = _argv


check("references --audit fails on an unacknowledged warning", _audit_exit(), 1)
common.dump_json({"G1": {"no-abstract": "editorial, no abstract exists"}}, _ap)
check("references --audit passes once it is acknowledged", _audit_exit(), 0)

# Entrance test: --repair + --list-acks is refused, like --repair + --audit — otherwise
# --list-acks's early exit would silently discard the repair (no write ever happens).
_argv = sys.argv
sys.argv = ["references.py", "--rows", _rp, "--repair", "--list-acks", "--email", "t@example.org"]
_exit = None
try:
    references.main()
except SystemExit as e:
    _exit = e
finally:
    sys.argv = _argv
check_true("--repair + --list-acks is refused with SystemExit(2)",
           _exit is not None and _exit.code == 2, repr(_exit))

# Entrance test: --list-acks prints REF<TAB>WARNING_ID<TAB>TEXT for every unacknowledged
# warning and exits 1; once acknowledged it prints nothing and exits 0.
import io  # noqa: E402

_d2 = _tmpf.mkdtemp()
_rp2, _ap2 = os.path.join(_d2, "rows.json"), os.path.join(_d2, "audit_acks.json")
common.dump_json([_na], _rp2)


def _list_acks():
    _argv = sys.argv
    sys.argv = ["references.py", "--rows", _rp2, "--acks", _ap2, "--list-acks", "--email", "t@example.org"]
    buf = io.StringIO()
    try:
        with _ctx.redirect_stdout(buf):
            references.main()
        code = 0
    except SystemExit as e:
        code = e.code or 0
    finally:
        sys.argv = _argv
    return code, buf.getvalue()


_code, _out = _list_acks()
check("references --list-acks prints REF\\tWARNING_ID\\tTEXT and exits 1 when unacknowledged",
      (_code, _out.strip()), (1, "G1\tno-abstract\tthe summary has no abstract to be checked against"))
common.dump_json({"G1": {"no-abstract": "editorial, no abstract exists"}}, _ap2)
_code, _out = _list_acks()
check("references --list-acks exits 0 and prints nothing once acknowledged", (_code, _out), (0, ""))


# ---- report ---------------------------------------------------------------
if FAILURES:
    print(f"FAILED {len(FAILURES)} check(s):\n")
    for f in FAILURES:
        print("  ✗ " + f)
    sys.exit(1)
print("✓ all formatting/audit/citation regression checks pass")
