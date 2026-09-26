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
import forward  # noqa: E402
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
        "expect_surname": "Tang", "expect_year": "2023"}])
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
# ...and a title-search hit that DOES match the claim is not OK either: only the DOI's
# own record can verify the DOI (final fixes I1), so a throttled DOI lookup is re-run.
verify.lookup_pubmed_title = lambda t: {"title": "Spatiotemporal energy models for the perception of motion",
                                        "year": "1985", "first_author": "Adelson EH", "journal": "JOSA A"}
_r = verify.verify_one({"label": "E15", "doi": "10.1364/josaa.2.000284",
                        "title": "Spatiotemporal energy models for the perception of motion",
                        "expect_first_author": "Adelson", "expect_year": "1985"})
check("throttled DOI lookup + matching title hit -> ERROR (the DOI itself is unchecked)",
      _r["verdict"], "ERROR")
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

# ---- xref via Semantic Scholar (2026-09-26) --------------------------------
check("S2 ids for a journal and an arXiv DOI",
      (xref.s2_id_for("10.1/a"), xref.s2_id_for("10.48550/arXiv.2301.00001")), ("DOI:10.1/a", "ARXIV:2301.00001"))
check("a cited arXiv paper maps to its corpus DOI form",
      (xref._ref_doi({"ArXiv": "1706.03762"}), xref._ref_doi({"DOI": "10.1/ABC"}), xref._ref_doi({})),
      ("10.48550/arxiv.1706.03762", "10.1/abc", ""))


def _s2_batch_stub(responses):
    seq = list(responses)

    def f(path, body=None):
        r = seq.pop(0)
        if isinstance(r, Exception):
            raise r
        return r(body) if callable(r) else r
    return f


with _patched(common, s2_request=_s2_batch_stub([[{"referenceCount": 1, "references": [
        {"externalIds": {"ArXiv": "2301.00002"}, "title": "B"}]}, None]])):
    _got = xref.s2_refs(["10.48550/arXiv.2301.00001", "10.1/notins2"])
check("s2_refs maps references; a paper S2 lacks is complete and empty",
      ([r["doi"] for r in _got["10.48550/arXiv.2301.00001"]], _got["10.1/notins2"]),
      (["10.48550/arxiv.2301.00002"], []))
with _patched(common, s2_request=_s2_batch_stub([urllib.error.HTTPError("u", 500, "x", {}, None)])):
    check("s2_refs marks a failed batch incomplete", xref.s2_refs(["10.1/a"]), {"10.1/a": None})
with _patched(common, s2_request=_s2_batch_stub([
        [{"paperId": "P1", "referenceCount": 3, "references": [{"externalIds": {"DOI": "10.1/r1"}}]}],
        {"data": [{"citedPaper": {"externalIds": {"DOI": "10.1/r1"}}},
                  {"citedPaper": {"externalIds": {"DOI": "10.1/r2"}}}], "next": 2},
        {"data": [{"citedPaper": {"externalIds": {"DOI": "10.1/r3"}}}]}])):
    _got = xref.s2_refs(["10.1/long"])
check("s2_refs pages a list longer than the batch returned",
      [r["doi"] for r in _got["10.1/long"]], ["10.1/r1", "10.1/r2", "10.1/r3"])
_asked = []
with _patched(xref, http_json=_no_network, s2_refs=lambda dois: (_asked.extend(dois), {d: [] for d in dois})[1]), \
        _sleeps() as _sl:
    _refs, _inc = xref.fetch_all([{"slug": "A", "doi": "10.48550/arXiv.2301.00001"}], sleep=0.4, retry_wait=0)
check("xref sends an arXiv DOI to S2, never CrossRef, with no per-paper sleep",
      (_asked, _refs["A"], _inc, _sl), (["10.48550/arXiv.2301.00001"], [], [], []))
with _patched(xref, crossref_refs=lambda d: [],
              s2_refs=lambda dois: {d: [{"doi": "10.1/z"}] for d in dois}), _sleeps():
    _refs, _inc = xref.fetch_all([{"slug": "J", "doi": "10.1/j"}], sleep=0, retry_wait=0)
check("an empty CrossRef list falls back to S2", _refs["J"], [{"doi": "10.1/z"}])
with _patched(xref, s2_refs=lambda dois: {d: None for d in dois}), _sleeps():
    _refs, _inc = xref.fetch_all([{"slug": "A", "doi": "10.48550/arXiv.2301.00001"}], sleep=0, retry_wait=0)
check("an S2 failure is incomplete, not 'cites nothing'", _inc, ["A"])

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


def _s2_ok(url, retries=5, timeout=30, data=None, headers=None):
    ids = json.loads(data)["ids"]
    _bodies.append(len(ids))
    return [{"citationCount": 1, "influentialCitationCount": 0} for _ in ids]


_items = [(f"k{n}", f"10.1/{n}") for n in range(1200)]
common._S2_LAST[0] = 0.0
with _patched(common, http_json=_s2_ok), _sleeps():
    _got = citations.fetch_s2(_items)
check("s2: 1200 ids go out in chunks of <=500", _bodies, [500, 500, 200])
check("s2: every chunk's results are mapped back", len(_got), 1200)
_n400 = []


def _s2_400(url, retries=5, timeout=30, data=None, headers=None):
    _n400.append(1)
    raise urllib.error.HTTPError("u", 400, "bad", {}, None)


common._S2_LAST[0] = 0.0
with _patched(common, http_json=_s2_400), _sleeps() as _sl:
    citations.fetch_s2(_items[:10])
# final fixes I5: a 400 is bisected to find the rejected ids (10 ids -> 19 requests),
# but never retried as if transient: no 20 s / 40 s backoff sleep.
check("s2: a 400 is bisected, never backed off", (len(_n400), [x for x in _sl if x >= 20]), (19, []))

# ---- Semantic Scholar pacer (2026-09-26) -----------------------------------
_s2calls = []


def _s2_seq(*codes):
    seq = list(codes)

    def f(url, retries=5, timeout=30, data=None, headers=None):
        _s2calls.append((url, retries, dict(headers or {})))
        c = seq.pop(0) if seq else 200
        if isinstance(c, Exception):
            raise c
        if c != 200:
            raise urllib.error.HTTPError(url, c, "x", {}, None)
        return {"ok": True}
    return f


common._S2_LAST[0] = 0.0
with _patched(common, http_json=_s2_seq()), _sleeps() as _sl:
    common.s2_request("paper/batch?fields=title", {"ids": ["DOI:10.1/a"]})
    common.s2_request("paper/batch?fields=title", {"ids": ["DOI:10.1/b"]})
check_true("s2_request paces consecutive requests >= ~1.1 s", len(_sl) == 1 and 1.0 < _sl[0] <= 1.1, str(_sl))
check("s2_request lets common.http make exactly one attempt", _s2calls[-1][1], 1)
common._S2_LAST[0] = 0.0
with _patched(common, http_json=_s2_seq(429, 429)), _sleeps() as _sl:
    common.s2_request("paper/batch", {"ids": []})
check_true("s2_request backs off 20 s then 40 s after 429s", 20 in _sl and 40 in _sl, str(_sl))
common._S2_LAST[0] = 0.0
with _patched(common, http_json=_s2_seq(429, 429, 429)), _sleeps():
    check_true("s2_request gives up after the backoff", _raises(lambda: common.s2_request("paper/batch", {"ids": []})))
with _patched(os, environ=dict(os.environ, S2_API_KEY="k-test")), _patched(common, http_json=_s2_seq()), _sleeps():
    common._S2_LAST[0] = 0.0
    common.s2_request("paper/x")
check("s2_request sends the key when set", _s2calls[-1][2].get("x-api-key"), "k-test")
common._S2_LAST[0] = 0.0
with _patched(common, http_json=_s2_seq(503, 200)), _sleeps() as _sl:
    _got = common.s2_request("paper/x")
check_true("s2_request retries a 503 and returns", _got == {"ok": True} and 20 in _sl, str(_sl))
common._S2_LAST[0] = 0.0
with _patched(common, http_json=_s2_seq(urllib.error.URLError("reset"), 200)), _sleeps():
    _got = common.s2_request("paper/x")
check("s2_request retries a network error (URLError) and returns", _got, {"ok": True})
common._S2_LAST[0] = 0.0
with _patched(common, http_json=_s2_seq(400)), _sleeps() as _sl:
    _raised = _raises(lambda: common.s2_request("paper/x"))
check_true("s2_request raises a 400 at once with no backoff sleep",
           _raised and 20 not in _sl and 40 not in _sl, str(_sl))

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
      ("Amodei, D.", "2016", "Concrete problems in AI safety"))
check("rows_to_citations: 'D. Amodei' shape yields the surname (parsed once, by the author check)",
      verify.claim_surname(verify.rows_to_citations([dict(_pre, search_author="D. Amodei")])[0]
                           ["expect_first_author"]), "Amodei")
_canon = dict(_pre, apa="Amodei, D., & Olah, C. (2016). Concrete problems in AI safety. arXiv.",
              canonical_at="2026-09-25", search_author="Wrong, X.")
check("rows_to_citations: a canonical row is checked against its apa too",
      verify.rows_to_citations([_canon])[0]["alt_expect"]["expect_surname"], "Amodei")
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
check_true("verify uses the common title_agrees", verify.title_agrees is common.title_agrees)
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

# Entrance test: --no-stamp with --rows reports only -- rows.json is not written at all.
_d4 = _tmpf.mkdtemp()
_rp4 = os.path.join(_d4, "rows.json")
_rep4 = os.path.join(_d4, "report.json")
_before4 = [{"ref": "N1", "doi": "10.1/n1", "search_title": "T"}]
common.dump_json(_before4, _rp4)
_argv = sys.argv
sys.argv = ["verify.py", "--rows", _rp4, "--no-stamp", "--out", _rep4, "--email", "t@example.org"]
try:
    with _patched(verify, verify_all=_fake_verify_all):
        verify.main()
except SystemExit:
    pass
finally:
    sys.argv = _argv
check("verify --no-stamp leaves rows.json untouched", common.load_json(_rp4), _before4)
check("verify --no-stamp still writes the report", common.load_json(_rep4)[0]["verdict"], "OK")


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
    d, a = common.ids_of(r)
    r["summary_check"] = {"verdict": "supported", "summary_sha": common.summary_sha(summary), "doi": d, "arxiv": a}
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
check("a DOI edited after verify fails the audit (verify and summary check both lapse; the stale link is named)",
      _codes(_rep, "G2"), ["link-doi-mismatch", "unverified", "summary-unchecked"])
_nd = {"ref": "B1", "apa": "Kuhn, T. S. (1962). The structure of scientific revolutions. U Chicago Press.",
       "summary": "", "canonical_at": common.GATES_SINCE}
check("a DOI-less row without a hand check fails", _codes(references.audit_rows([_grow(), _nd], "ref"), "B1"),
      ["hand-check-missing"])
_nd_ok = dict(_nd, hand_verified={"verdict": "confirmed", "source_checked": "LoC catalog record",
                                  "apa_sha": common.apa_sha(_nd["apa"])})
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
           any(w.startswith("kept-existing-apa") for w, _ in references.audit_rows([_kept], "ref")["warnings"]["G1"]))
_legacy = [{"ref": "L1", "doi": "10.1/l1", "canonical_at": "2026-08-18",
            "apa": "Lambon Ralph, M. A. (2017). The neural basis. Nat Rev Neurosci, 1, 1."}]
_rep = references.audit_rows(_legacy, "ref")
check("a legacy table is audited as before: warnings do not fail", (_rep["gated"], _rep["failed"]), (False, False))

# Entrance test (controller ruling, Task 10 addendum): the legacy note must say WHY the
# gates are off and point at the upgrade procedure, not just assert "not enforced".
import io  # noqa: E402

_buf = io.StringIO()
with _ctx.redirect_stdout(_buf):
    references.print_report(_rep, len(_legacy))
_note = _buf.getvalue()
check_true("the legacy note explains why the gates are off and names the upgrade procedure",
           "predates the reference gates, so they are not enforced here" in _note
           and "Upgrading an old corpus" in _note, _note)

# Entrance test: --audit exits 1 on an unacknowledged warning in a gated table, 0 once acknowledged.
_d = _tmpf.mkdtemp()
_rp, _ap = os.path.join(_d, "rows.json"), os.path.join(_d, "audit_acks.json")
common.dump_json([_na], _rp)
# a gated table's ledger records that xref and forward ran (final fixes I8)
_RUNS_LEDGER = {"_runs": {"xref": {"at": "2026-09-25", "n": 0, "complete": True},
                          "forward": {"at": "2026-09-25", "n": 0, "complete": True}}}
common.dump_json(_RUNS_LEDGER, os.path.join(_d, "candidates.json"))


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
_d2 = _tmpf.mkdtemp()
_rp2, _ap2 = os.path.join(_d2, "rows.json"), os.path.join(_d2, "audit_acks.json")
common.dump_json([_na], _rp2)
common.dump_json(_RUNS_LEDGER, os.path.join(_d2, "candidates.json"))


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


# ---- reference gates: the spreadsheet runs the audit (2026-09-26) ----------
import zipfile as _zip  # noqa: E402


def _sheet_main(rows, *extra, candidates={}):
    d = _tmpf.mkdtemp()
    rp, out = os.path.join(d, "rows.json"), os.path.join(d, "bib.xlsx")
    common.dump_json(rows, rp)
    if candidates is not None:
        common.dump_json({**_RUNS_LEDGER, **candidates}, os.path.join(d, "candidates.json"))
    argv = sys.argv
    sys.argv = ["spreadsheet.py", "--rows", rp, "--out", out, *extra]
    code = 0
    try:
        spreadsheet.main()
    except SystemExit as e:
        code = e.code or 0
    finally:
        sys.argv = argv
    return code, d


def _xlsx_text(path):
    with _zip.ZipFile(path) as z:
        return "".join(z.read(n).decode("utf-8") for n in z.namelist()
                       if n.endswith(("sharedStrings.xml", "workbook.xml")))


_code, _dd = _sheet_main([dict(_grow(), doi="10.1/changed")])
check("spreadsheet refuses a failing gated table",
      (_code, os.path.exists(os.path.join(_dd, "bib.xlsx"))), (1, False))
_code, _dd = _sheet_main([dict(_grow(), doi="10.1/changed")], "--draft")
check_true("--draft writes a file named as a draft", _code == 0 and os.path.exists(os.path.join(_dd, "bib_DRAFT.xlsx")))
check("--draft does not write the deliverable name", os.path.exists(os.path.join(_dd, "bib.xlsx")), False)
check_true("the draft carries a banner", "DRAFT" in _xlsx_text(os.path.join(_dd, "bib_DRAFT.xlsx")))
_code, _dd = _sheet_main([_grow()])
check("a passing table is written", (_code, os.path.exists(os.path.join(_dd, "bib.xlsx"))), (0, True))
_undated = [{"ref": "N1", "apa": "Doe, J. Undated manuscript. Private papers.", "canonical_at": "2026-08-18"}]
_code, _dd = _sheet_main(_undated)
check("a legacy corpus with an accepted defect is still written",
      (_code, os.path.exists(os.path.join(_dd, "bib.xlsx"))), (0, True))
_code, _dd = _sheet_main([_grow()], candidates={"10.1/x": {"title": "Excluded paper", "year": "2019",
                                                           "first_author": "Roe", "sources": {"xref": 4},
                                                           "decision": "exclude", "reason": "off topic"}})
check_true("excluded candidates get their own sheet",
           "Considered and excluded" in _xlsx_text(os.path.join(_dd, "bib.xlsx")))
check("draft_path inserts _DRAFT", spreadsheet.draft_path("/a/b/bib.xlsx"), "/a/b/bib_DRAFT.xlsx")

# ---- fix round 1: spreadsheet.py is a third candidates.json loader (2026-09-26) ----
# references.audit_rows only validates the ledger when the table is gated, and
# --draft continues past a failed (gated) audit -- so a corrupted ledger still
# reached candidates.entries()/v.get("decision") unvalidated on a legacy table,
# or on a gated table with --draft. Both must exit 1 and write nothing.
_code, _dd = _sheet_main(_undated, candidates={"10.1/bad": "not-a-dict"})
check("spreadsheet refuses a corrupted ledger on a legacy table (no file written)",
      (_code, os.path.exists(os.path.join(_dd, "bib.xlsx"))), (1, False))
_code, _dd = _sheet_main([_grow()], "--draft", candidates={"10.1/bad": "not-a-dict"})
check("spreadsheet refuses a corrupted ledger on a gated table with --draft (no draft written)",
      (_code, os.path.exists(os.path.join(_dd, "bib_DRAFT.xlsx"))), (1, False))

_sd = _tmpf.mkdtemp()
_sdrp = os.path.join(_sd, "rows.json")
common.dump_json([_grow()], _sdrp)
common.dump_json({"10.1/bad": "not-a-dict"}, os.path.join(_sd, "candidates.json"))
_argv = sys.argv
sys.argv = ["spreadsheet.py", "--rows", _sdrp, "--out", os.path.join(_sd, "bib.xlsx")]
_serr = io.StringIO()
_scode = 0
try:
    with _ctx.redirect_stderr(_serr):
        spreadsheet.main()
except SystemExit as e:
    _scode = e.code or 0
finally:
    sys.argv = _argv
check("spreadsheet's corrupted-ledger message names the bad entry and exits 1",
      ("10.1/bad" in _serr.getvalue(), _scode), (True, 1))


# ---- reference gates: handcheck.py (2026-09-26) ----------------------------
import handcheck  # noqa: E402

_book = {"ref": "B1", "apa": "Kuhn, T. S. (1962). The structure of scientific revolutions. U Chicago Press.",
         "summary": "s"}
_hit = lambda t: [{"doi": "10.7208/x", "title": "The Structure of Scientific Revolutions", "year": "1962",  # noqa: E731
                   "source": "crossref"}]
_wrong_year = lambda t: [{"doi": "10.7208/y", "title": "The structure of scientific revolutions",  # noqa: E731
                          "year": "1996", "source": "openalex"}]
_far = lambda t: [{"doi": "10.1/z", "title": "Paradigms in physics", "year": "1962", "source": "crossref"}]  # noqa: E731
check("find_doi: title and year match", [h["doi"] for h in handcheck.find_doi(_book, (_hit,))], ["10.7208/x"])
check("find_doi: a different year is not a match", handcheck.find_doi(_book, (_wrong_year,)), [])
check("find_doi: a different title is not a match", handcheck.find_doi(_book, (_far,)), [])
_cands, _todo = handcheck.prepare([_book, {"ref": "B2", "apa": "Doe, J. (1970). Memo. Lab.", "summary": ""},
                                   {"ref": "D1", "doi": "10.1/d"}], "ref", (_far,))
check("prepare: DOI-less rows with no DOI match go to the hand check",
      (sorted(_cands), [t["ref"] for t in _todo]), ([], ["B1", "B2"]))
_rows = [dict(_book)]
_ad, _amb = handcheck.adopt(_rows, "ref", {"B1": [{"doi": "10.7208/x"}]})
check("adopt moves a row with one found DOI into the verify path",
      (_ad, _rows[0]["doi"], _rows[0]["link"]), (["B1"], "10.7208/x", "https://doi.org/10.7208/x"))
check("adopt skips an ambiguous row", handcheck.adopt([dict(_book)], "ref",
                                                      {"B1": [{"doi": "a"}, {"doi": "b"}]}), ([], ["B1"]))
_adopt_err = io.StringIO()
with _ctx.redirect_stderr(_adopt_err):
    _ad9, _amb9 = handcheck.adopt([dict(_book)], "ref", {"ZZ": [{"doi": "10.1/z"}]})
check("adopt does not adopt a candidate ref that is not in the table", (_ad9, _amb9), ([], []))
check_true("adopt prints a note for a candidate ref not in the table",
           "ZZ" in _adopt_err.getvalue() and "not in this table" in _adopt_err.getvalue(),
           _adopt_err.getvalue())
_rows = [dict(_book), {"ref": "B2", "apa": "Doe, J. (1970). Memo. Lab."}, {"ref": "D1", "doi": "10.1/d"}]
_hc_in = [{"ref": "B1", "apa_sha": common.apa_sha(_book["apa"])},
          {"ref": "B2", "apa_sha": common.apa_sha("Doe, J. (1970). Memo. Lab.")}]
_n, _err = handcheck.ingest(_rows, "ref", [
    {"ref": "B1", "verdict": "confirmed", "source_checked": "LoC record 62019621", "apa_sha": _hc_in[0]["apa_sha"]},
    {"ref": "B2", "verdict": "corrected", "apa": "Doe, J. (1971). Memo. Lab.", "source_checked": "scan",
     "apa_sha": _hc_in[1]["apa_sha"]},
    {"ref": "D1", "verdict": "confirmed", "source_checked": "x"},
    {"ref": "B9", "verdict": "confirmed", "source_checked": "x"}], _hc_in, "2026-09-26")
check("ingest records valid results", (_n, _rows[0]["hand_verified"]["verdict"], _rows[1]["apa"]),
      (2, "confirmed", "Doe, J. (1971). Memo. Lab."))
check("ingest refuses a DOI'd row and an unknown ref", len(_err), 2)
_n, _err = handcheck.ingest([dict(_book)], "ref", [{"ref": "B1", "verdict": "confirmed", "source_checked": "",
                                              "apa_sha": common.apa_sha(_book["apa"])}],
                            [{"ref": "B1", "apa_sha": common.apa_sha(_book["apa"])}], "2026-09-26")
check("ingest refuses a confirmation that names no source", (_n, len(_err)), (0, 1))
_n, _err = handcheck.ingest([dict(_book)], "ref",
                           [{"ref": "B1", "verdict": "maybe", "source_checked": "x", "apa_sha": common.apa_sha(_book["apa"])}],
                           [{"ref": "B1", "apa_sha": common.apa_sha(_book["apa"])}], "2026-09-26")
check("ingest refuses a verdict that is not confirmed/corrected/not-found", (_n, _err),
      (0, ["B1: verdict 'maybe' is not one of confirmed, corrected, not-found"]))
_n, _err = handcheck.ingest([dict(_book)], "ref",
                           [{"ref": "B1", "verdict": "corrected", "source_checked": "x", "apa_sha": common.apa_sha(_book["apa"])}],
                           [{"ref": "B1", "apa_sha": common.apa_sha(_book["apa"])}], "2026-09-26")
check("ingest refuses 'corrected' without the corrected apa", (_n, _err),
      (0, ["B1: corrected without the corrected apa"]))
check_true("a handcheck-ingested row passes the audit's hand-check gate",
           "hand-check-missing" not in " ".join(references.audit_rows(
               [_grow(), dict(_rows[0], canonical_at=common.GATES_SINCE, summary="")], "ref")["defects"].get("B1", [])))


# ---- abstracts.py (2026-09-26) ---------------------------------------------
import abstracts  # noqa: E402

_feed = (b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2301.00001v1</id>'
         b'<title>T</title><summary>  We show\n that it works. </summary>'
         b'<published>2023-01-01T00:00:00Z</published><author><name>A B</name></author></entry></feed>')
check("arxiv_entries returns the abstract", common.arxiv_entries(_feed)[0]["summary"], "We show that it works.")
check("reconstruct rebuilds an OpenAlex inverted index",
      abstracts.reconstruct({"works": [1], "It": [0], "well.": [2]}), "It works well.")
_R = [{"ref": "X", "arxiv": "2301.00001", "summary": "s"}, {"ref": "J", "doi": "10.1/J", "summary": "s"},
      {"ref": "K", "doi": "10.1/k", "summary": "s"}, {"ref": "P", "pmid": "123", "summary": "s"},
      {"ref": "H", "doi": "10.1/h", "summary": "s"}, {"ref": "N", "summary": "s"},
      {"ref": "F", "arxiv": "2301.00002", "summary": "s"}, {"ref": "U", "doi": "10.1/U", "summary": "s"}]
_asked = {}
# 2301.00002 (row F) never resolves at any source, so its arXiv batch failure must
# survive to `failed`. 10.1/U (row U) has an uppercase DOI that only S2 answers,
# keyed lowercase -- proves both the OpenAlex and S2 lookup keys are lowercased.
answer_keys = {"arxiv": {"2301.00001"}, "openalex": {"10.1/j"}, "s2": {"DOI:10.1/k", "DOI:10.1/u"},
               "pubmed": {"123"}}
fail_keys = {"arxiv": {"2301.00002"}}


def _fx(name, answer):
    def f(ids):
        _asked[name] = list(ids)
        got = {i: answer for i in ids if i in answer_keys[name]}
        failed = set(ids) & fail_keys.get(name, set())
        return got, failed
    return f


_ab, _missing, _failed, _ = abstracts.collect(
    _R, "ref", {"H": {"text": "hand-added", "source": "landing-page", "url": "u"}},
    {n: _fx(n, "text-" + n) for n in answer_keys})
check("collect takes each source in order", {k: v["source"] for k, v in _ab.items()},
      {"X": "arxiv", "J": "openalex", "K": "s2", "P": "pubmed", "H": "landing-page", "U": "s2"})
check("collect never re-fetches an existing entry", "10.1/h" in _asked["openalex"], False)
check("collect reports rows with a summary and no abstract", _missing, ["N"])
check("a fetch failure is reported separately from a clean no-abstract", list(_failed), ["F"])
check("a failed ref is not silently counted as having no abstract", "F" in _missing, False)
check("a failed ref never gets an abstract entry", "F" in _ab, False)
check("openalex looks up a DOI lowercased", "10.1/u" in _asked["openalex"], True)
check("s2 looks up a DOI lowercased", "DOI:10.1/u" in _asked["s2"], True)
check("an uppercase-DOI row resolved only by S2 gets its abstract", _ab.get("U", {}).get("source"), "s2")


# ---- summary_audit.py (2026-09-26) -----------------------------------------
import summary_audit  # noqa: E402

_S = [{"ref": "A", "summary": "It found X."}, {"ref": "B", "summary": "It found Y."},
      {"ref": "C", "summary": ""}, {"ref": "D", "summary": "No abstract here."},
      dict(_grow("E", "10.1/e"), summary="Tests whether a thing happens.")]
_AB = {"A": {"text": "We found X.", "source": "openalex"}, "B": {"text": "We found Y.", "source": "arxiv"},
       "E": {"text": "abs", "source": "s2"}}
_b, _na, _man = summary_audit.prepare(_S, "ref", _AB, batch=1)
check("prepare batches rows with a summary and an abstract, skipping checked ones",
      ([[x["ref"] for x in b] for b in _b], _na), ([["A"], ["B"]], ["D"]))
_n, _err = summary_audit.ingest(_S, "ref", [{"ref": "A", "verdict": "supported", "summary_sha": _man["sha"]["A"]},
                                            {"ref": "B", "verdict": "unsupported", "unsupported_clause": "Y",
                                             "summary_sha": _man["sha"]["B"]}],
                                _AB, _man, "2026-09-26")
check("ingest records both verdicts and the no-abstract row", (_n, _err, _S[0]["summary_check"]["verdict"],
                                                              _S[1]["summary_check"]["verdict"],
                                                              _S[3]["summary_check"]["verdict"]),
      (3, [], "supported", "unsupported", "no-abstract"))
check("the check carries the summary hash", _S[0]["summary_check"]["summary_sha"], common.summary_sha("It found X."))
_S2 = [{"ref": "A", "summary": "It found X."}, {"ref": "B", "summary": "It found Y."}]
_b, _na, _man = summary_audit.prepare(_S2, "ref", _AB)
_S2[0]["summary"] = "It found Z."        # edited between prepare and ingest
_n, _err = summary_audit.ingest(_S2, "ref", [{"ref": "A", "verdict": "supported"}], _AB, _man, "2026-09-26")
check_true("ingest refuses a summary edited since prepare, and names a missing result",
           "summary_check" not in _S2[0] and any("changed" in e for e in _err) and any("B" in e for e in _err),
           str(_err))
_n, _err = summary_audit.ingest([{"ref": "A", "summary": "It found X."}], "ref",
                                [{"ref": "A", "verdict": "unsupported",
                                  "summary_sha": common.summary_sha("It found X.")}], _AB,
                                {"refs": ["A"], "sha": {"A": common.summary_sha("It found X.")}, "no_abstract": [],
                                 "ids": {"A": list(common.ids_of({"ref": "A", "summary": "It found X."}))},
                                 "abstract_sha": {"A": common.summary_sha("We found X.")}},
                                "2026-09-26")
check("an unsupported verdict must quote the clause", (_n, len(_err)), (0, 1))
_tmpx = os.path.join(_tmpf.mkdtemp(), "s.xlsx")
spreadsheet.build([{"ref": "A", "apa": "A, B. (2020). T. V.", "source": "search", "summary": "s",
                    "summary_check": {"verdict": "no-abstract"}},
                   {"ref": "B", "apa": "A, B. (2021). T. V.", "source": "search", "summary": "s",
                    "summary_check": {"verdict": "supported", "abstract_source": "openalex"}}], _tmpx)
check_true("the spreadsheet marks a summary with no abstract",
           "Summary checked against" in _xlsx_text(_tmpx) and "no abstract" in _xlsx_text(_tmpx))

# fix round 1: an abstract that arrives between --prepare and --ingest must block the
# no-abstract stamp, not be silently overridden by it.
_S3 = [{"ref": "D", "summary": "No abstract here."}]
_b3, _na3, _man3 = summary_audit.prepare(_S3, "ref", {})
_n3, _err3 = summary_audit.ingest(_S3, "ref", [], {"D": {"text": "Backfilled abstract.", "source": "openalex"}},
                                  _man3, "2026-09-26")
check("an abstract that appeared since --prepare blocks the no-abstract stamp",
      ("summary_check" in _S3[0], _err3), (False, ["D: an abstract is now available; re-run --prepare"]))

# fix round 1: two results for the same ref must stamp neither, and be reported once.
_S4 = [{"ref": "A", "summary": "It found X."}]
_b4, _na4, _man4 = summary_audit.prepare(_S4, "ref", {"A": {"text": "We found X.", "source": "openalex"}})
_n4, _err4 = summary_audit.ingest(_S4, "ref", [{"ref": "A", "verdict": "supported"},
                                               {"ref": "A", "verdict": "unsupported", "unsupported_clause": "X"}],
                                  {"A": {"text": "We found X.", "source": "openalex"}}, _man4, "2026-09-26")
check("a duplicate result for the same ref stamps neither and is reported once",
      (_n4, "summary_check" in _S4[0], _err4), (0, False, ["A: more than one result; keep one"]))

# a ref that is BOTH a duplicate and outside the manifest reports "not in this
# summary audit" -- not "more than one result", which would say the ref was
# recognized when it was not.
_man5 = {"refs": [], "sha": {}, "no_abstract": [], "ids": {}, "abstract_sha": {}}
_n5, _err5 = summary_audit.ingest([], "ref", [{"ref": "Z", "verdict": "supported"},
                                              {"ref": "Z", "verdict": "supported"}],
                                  {}, _man5, "2026-09-26")
check("a duplicate ref outside the manifest reports 'not in this summary audit' first",
      _err5, ["Z: not in this summary audit"])

# ---- lane schema 2 in the search template (2026-09-26) ---------------------
with open(os.path.join(os.path.dirname(common.__file__), "search_prompt_template.md"), encoding="utf-8") as _fh:
    _TPL = _fh.read()
for _needle in ('"schema": 2', '"deferred"', '"could_not_confirm"', '"lane_fit"', '"websearch_exhausted"'):
    check_true(f"search template defines {_needle}", _needle in _TPL)
check_true("search template no longer abbreviates author lists", "et al." not in _TPL)
check_true("search template no longer caps DOI-less items", "at most 4" not in _TPL)

# ---- merge_lanes.py (2026-09-26) -------------------------------------------
import merge_lanes  # noqa: E402


def _lane(key, papers, deferred=(), target=None, exhausted=False):
    return {"schema": 2, "lane": key, "status": {"target": target or len(papers), "returned": len(papers),
                                                  "websearch_exhausted": exhausted},
            "papers": list(papers), "deferred": list(deferred), "could_not_confirm": []}


def _p(ref, doi="", arxiv="", title=None, au="Smith, J.", year=2020, apa=""):
    return {"ref": ref, "doi": doi, "arxiv": arxiv, "first_author": au, "year": year, "title": title or f"Paper {ref}",
            "apa": apa, "summary": "s", "tag": "classic", "topic": "T"}


_rows, _rep = merge_lanes.merge([
    _lane("A", [_p("A-01", doi="10.1/X"), _p("A-02", arxiv="2301.00001", title="Deep nets"),
                _p("A-03", title="Old book", au="Kuhn, T.", year=1962, apa="Kuhn, T. (1962). Old book. Pub.")]),
    _lane("B", [_p("B-01", doi="https://doi.org/10.1/x"),
                _p("B-02", doi="10.1/deepnets", title="Deep Nets", au="Smith, J.", year=2020),
                _p("B-03", doi="10.1/y", au="Doe, A."), _p("B-04")],
          deferred=[{"title": "Deep nets", "first_author": "Smith, J.", "reason": "A owns it"},
                    {"title": "Lost classic", "doi": "10.1/lost"}],
          target=20)])
check("merge dedups by DOI (any form) and by title+year", [r["ref"] for r in _rows], ["A-01", "A-02", "A-03", "B-03"])
check("merge records the other lanes", _rows[0].get("also_lanes"), ["B"])
check("merge keeps the agent's claim", (_rows[3]["search_author"], _rows[3]["search_year"]), ("Doe, A.", 2020))
check("a DOI-less paper keeps its APA; a DOI'd one does not", (_rows[2]["apa"] != "", _rows[0]["apa"]), (True, ""))
check("merge rejects a paper with no DOI, arXiv id or APA", [x["ref"] for x in _rep["rejected"]], ["B-04"])
check("merge matches a deferral by title and loses one no lane kept",
      ([d["title"] for d in _rep["deferrals_matched"]], [d["title"] for d in _rep["lost"]]),
      (["Deep nets"], ["Lost classic"]))
check("merge flags a thin lane", [t["lane"] for t in _rep["thin"]], ["B"])
_rows2, _rep2 = merge_lanes.merge([_lane("A", [_p("A-01", doi="10.1/x", au="Smith, J.")]),
                                   _lane("B", [_p("B-01", doi="10.1/x", au="Jones, K.")])])
check("merge reports a conflicting claim between duplicates", len(_rep2["conflicts"]), 1)
check_true("merge refuses a repeated ref", _raises(lambda: merge_lanes.merge(
    [_lane("A", [_p("A-01", doi="10.1/a")]), _lane("B", [_p("A-01", doi="10.1/b")])])))
_d = _tmpf.mkdtemp()
common.dump_json([_p("A-01", doi="10.1/a")], os.path.join(_d, "A.json"))
check_true("a schema-1 lane file is refused", _raises(lambda: merge_lanes.load_lane(os.path.join(_d, "A.json"))))
check("with --allow-v1 it loads without a deferral list",
      merge_lanes.load_lane(os.path.join(_d, "A.json"), allow_v1=True)["deferred"], None)


def _merge_exit(raw, out):
    argv = sys.argv
    sys.argv = ["merge_lanes.py", "--raw", raw, "--out", out]
    try:
        merge_lanes.main()
        return 0
    except SystemExit as e:
        return e.code or 0
    finally:
        sys.argv = argv


_d = _tmpf.mkdtemp()
_raw = os.path.join(_d, "search_raw")
os.makedirs(_raw)
common.dump_json(_lane("A", [_p("A-01", doi="10.1/a")], deferred=[{"title": "Lost classic"}]),
                 os.path.join(_raw, "A.json"))
check("merge_lanes exits 1 on a lost deferral", _merge_exit(_raw, os.path.join(_d, "rows.json")), 1)
# final fixes I7: a failed merge writes the report but NOT rows.json
check("and writes the report but not the rows",
      (os.path.exists(os.path.join(_d, "rows.json")), os.path.exists(os.path.join(_d, "merge_report.json"))),
      (False, True))

# ---- merge_lanes.py fix round 1: title-only dedup guard (2026-09-26) -------
# Same title+year but two different journal DOIs: NOT the same paper.
_rows3, _rep3 = merge_lanes.merge([
    _lane("C", [_p("C-01", doi="10.1/aaa", title="Same title", year=2021, au="Smith, J.")]),
    _lane("D", [_p("D-01", doi="10.1/bbb", title="Same title", year=2021, au="Smith, J.")])])
check("title+year dedup does not merge two different journal DOIs",
      [r["ref"] for r in _rows3], ["C-01", "D-01"])
check_true("...and flags a possible pair with the DOI reason",
           any(p.get("why", "").startswith("same title and year") and "different DOIs" in p["why"]
               for p in _rep3["possible_pairs"]))

# An arXiv DOI + a journal DOI of the same title+year IS the same paper.
_rows4, _rep4 = merge_lanes.merge([
    _lane("E", [_p("E-01", doi="10.48550/arXiv.2401.00001", title="Preprint title", year=2022, au="Smith, J.")]),
    _lane("F", [_p("F-01", doi="10.1/journal-f", title="Preprint title", year=2022, au="Smith, J.")])])
check("an arXiv DOI + a journal DOI of the same title+year still merges",
      [r["ref"] for r in _rows4], ["E-01"])
check("...also_lanes records the journal lane", _rows4[0].get("also_lanes"), ["F"])

# A DOI-less row (APA only) + a journal-DOI row of the same title+year still merges.
_rows5, _rep5 = merge_lanes.merge([
    _lane("G", [_p("G-01", title="No-DOI title", year=2022, au="Smith, J.",
                    apa="Smith, J. (2022). No-DOI title. Pub.")]),
    _lane("H", [_p("H-01", doi="10.1/journal-h", title="No-DOI title", year=2022, au="Smith, J.")])])
check("a DOI-less row and a journal-DOI row with the same title+year still merge",
      [r["ref"] for r in _rows5], ["G-01"])

# Same title+year but a conflicting claimed author: NOT the same paper either.
_rows6, _rep6 = merge_lanes.merge([
    _lane("I", [_p("I-01", doi="10.1/kim", title="Disputed title", year=2023, au="Kim, S.")]),
    _lane("J", [_p("J-01", doi="10.1/zhao", title="Disputed title", year=2023, au="Zhao, L.")])])
check("title+year dedup does not merge a conflicting author claim",
      [r["ref"] for r in _rows6], ["I-01", "J-01"])
check_true("...and flags the conflict as a possible pair",
           any(p.get("why", "").startswith("same title and year") and "Kim" in p["why"] and "Zhao" in p["why"]
               for p in _rep6["possible_pairs"]))

# ---- merge_lanes.py fix round 1: deferral title-only match needs corroboration ----
# A title similarity below the new 0.9 bar is still lost, even though it cleared the
# old 0.85 bar.
_rep7 = merge_lanes.merge([_lane("K", [_p("K-01", doi="10.1/deepcnn",
                                          title="Deep convolutional neural networks for vision")],
                                 deferred=[{"title": "Deep convolutional neural networks for language"}])])[1]
check("a title match below 0.9 is still lost, not accepted as a match",
      [d["title"] for d in _rep7["lost"]], ["Deep convolutional neural networks for language"])

# An exact title match with a disagreeing claimed first author is lost, not accepted.
_rep8 = merge_lanes.merge([_lane("L", [_p("L-01", doi="10.1/kim", title="Exact Title Match", au="Kim, S.")],
                                 deferred=[{"title": "Exact Title Match", "first_author": "Zhao, L."}])])[1]
check("a title match with a disagreeing claimed author is lost, not accepted",
      [d["title"] for d in _rep8["lost"]], ["Exact Title Match"])
check("...and is not counted as matched by title", _rep8["matched_by_title"], [])

# An exact title match with an agreeing claimed author (and year) IS matched, and
# is recorded separately so a human can double-check a title-only match.
_rep9 = merge_lanes.merge([_lane("M", [_p("M-01", doi="10.1/hinton", title="Perfectly Matched Title",
                                          au="Hinton, G.", year=2021)],
                                 deferred=[{"title": "Perfectly Matched Title", "first_author": "Hinton, G.",
                                           "year": 2021}])])[1]
check("an exact title match with an agreeing claimed author is matched",
      [d["title"] for d in _rep9["deferrals_matched"]], ["Perfectly Matched Title"])
check("...and is recorded in matched_by_title",
      [(m["found_as"], m["from_lane"]) for m in _rep9["matched_by_title"]], [("M-01", "M")])

# ---- merge_lanes --append (2026-09-26) -------------------------------------
_canon = [_grow("G1", "10.1/g1"), _grow("G2", "10.1/g2")]
_before = json.dumps(_canon, sort_keys=True)
_added, _skipped, _pairs = merge_lanes.append(
    _canon, "ref", _lane("X", [_p("X-01", doi="10.1/G1"), _p("X-02", doi="10.1/n")]))
check("append adds only papers not already in the table", (_added, [s["ref"] for s in _skipped]), (["X-02"], ["X-01"]))
check("append never changes an existing row", json.dumps(_canon[:2], sort_keys=True), _before)
check_true("append refuses a ref already in the table",
           _raises(lambda: merge_lanes.append(_canon, "ref", _lane("X", [_p("G1", doi="10.1/q")]))))

# R7: a title-only hit that fails the same gate merge() uses (here, two
# different non-arXiv DOIs) is a distinct paper sharing a title+year, not a
# duplicate — append it and report the pair for a human verdict, don't skip it.
_canon2 = [_grow("N1", "10.1/n1")]
_added2, _skipped2, _pairs2 = merge_lanes.append(
    _canon2, "ref",
    _lane("Y", [_p("Y-01", doi="10.1/other-journal", title="A real paper", year=2020, au="Jones, K.")]))
check("a title-only hit with a conflicting/differing DOI is appended, not skipped", _added2, ["Y-01"])
check("...and skipped stays empty", _skipped2, [])
check("...and reported as a possible pair for a human verdict",
      [(p["a"], p["b"]) for p in _pairs2], [("N1", "Y-01")])

# ---- forward.py (2026-09-26) -----------------------------------------------
_FR = [{"ref": "A", "doi": "10.1/a", "cite_openalex": 10}, {"ref": "B", "doi": "10.1/b", "cite_openalex": 500},
       {"ref": "C", "doi": "10.1/c", "cite_openalex": 50}, {"ref": "N"}]
check("landmarks: in-corpus in-degree first, then citations",
      [r["ref"] for r in forward.pick_landmarks(_FR, "ref", {"A": 9, "C": 9}, 2)], ["C", "A"])


def _w(wid, doi, refs, cites=5, title="T"):
    return {"id": f"https://openalex.org/{wid}", "doi": f"https://doi.org/{doi}" if doi else None,
            "display_name": title, "publication_year": 2024, "cited_by_count": cites,
            "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
            "referenced_works": [f"https://openalex.org/{x}" for x in refs]}


_corpus_w = {"W1", "W2", "W3"}
_cands, _nodoi = forward.score({"A": [_w("W9", "10.9/new", ["W1", "W2", "W3"], 40), _w("W2", "10.1/b", ["W1"]),
                                      _w("W8", "10.9/weak", ["W1"]), _w("W7", None, ["W1", "W2", "W3"])],
                                "C": [_w("W9", "10.9/new", ["W1", "W2", "W3"], 40)]},
                               _corpus_w, {"10.1/a", "10.1/b", "10.1/c"}, 3)
check("score keeps papers citing >= 3 corpus papers, outside the corpus, with a DOI",
      [(c["doi"], c["shared"], sorted(c["cites_landmarks"])) for c in _cands], [("10.9/new", 3, ["A", "C"])])
check("score counts candidates dropped for lacking a DOI", _nodoi, 1)
# A citing work can carry a DOI that is already in the corpus even though OpenAlex
# assigned it a *different* work id than any corpus row resolved to (a merged/
# duplicate OpenAlex record, or a corpus row whose id lookup failed) -- exclude by
# DOI too, not only by OpenAlex id.
_cands_doi_excl, _ = forward.score({"A": [_w("W99", "10.1/b", ["W1", "W2", "W3"])]},
                                   _corpus_w, {"10.1/a", "10.1/b", "10.1/c"}, 3)
check("score excludes a citing work whose DOI (not OpenAlex id) is already in the corpus",
      _cands_doi_excl, [])
# OpenAlex DOIs are lowercase, but a corpus DOI is not guaranteed to already be
# lowercased before it reaches score() -- the match must not be case-sensitive.
_cands_case, _ = forward.score({"A": [_w("W99", "10.1/B", ["W1", "W2", "W3"])]},
                               _corpus_w, {"10.1/a", "10.1/b", "10.1/c"}, 3)
check("score matches a corpus DOI case-insensitively", _cands_case, [])
with _patched(common, http_json=lambda url, **k: {"results": [{"id": "https://openalex.org/W1",
                                                               "doi": "https://doi.org/10.1/A"}]}), _sleeps():
    check("openalex_ids maps DOIs to short work ids", forward.openalex_ids(["10.1/a"], "t@example.org"),
          {"10.1/a": "W1"})

# ---- candidates.py and the audit's candidate check (2026-09-26) ------------
import candidates  # noqa: E402

_L = {}
_a, _s = candidates.add(_L, [{"doi": "10.9/NEW", "n_citations": 5, "title": "New"},
                             {"doi": "10.1/g1", "n_citations": 9}], "xref", {"10.1/g1"})
check("add records new candidates as pending and skips corpus papers",
      (_a, _s, _L["10.9/new"]["decision"]), (1, 1, "pending"))
candidates.add(_L, [{"doi": "https://doi.org/10.9/new", "shared": 4}], "forward", set())
check("add merges sources for the same DOI", _L["10.9/new"]["sources"], {"xref": 5, "forward": 4})
check_true("decide needs a reason", _raises(lambda: candidates.decide(_L, "10.9/new", "exclude", "", "d")))
check_true("decide needs include or exclude", _raises(lambda: candidates.decide(_L, "10.9/new", "maybe", "r", "d")))
check("pending candidates are a corpus defect", len(candidates.candidate_defects(_L, set())), 1)
candidates.decide(_L, "10.9/new", "include", "cited by 5 corpus papers; on topic", "2026-09-26")
check_true("an included candidate missing from the table is a defect",
           "not in the table" in " ".join(candidates.candidate_defects(_L, set())))
_lane_x = candidates.export_included(_L, set(), "X")
check("export_included writes a schema-2 lane of included papers",
      (_lane_x["schema"], [p["doi"] for p in _lane_x["papers"]], _lane_x["papers"][0]["ref"]), (2, ["10.9/new"], "X-01"))
check("no defects once the included paper is in the table", candidates.candidate_defects(_L, {"10.9/new"}), [])
_rep = references.audit_rows([_grow()], "ref", ledger=references.LEDGER_MISSING)
check("a gated table with no ledger must acknowledge that",
      [w for w, _ in _rep["unacked"].get("*", [])], ["no-candidate-ledger"])
_rep = references.audit_rows([_grow()], "ref", ledger={"10.9/p": {"decision": "pending"}})
check_true("pending candidates fail the audit", _rep["failed"] and _rep["corpus"])
_rep = references.audit_rows(_legacy, "ref", ledger=references.LEDGER_MISSING)
check("a legacy table is not asked for a ledger", "*" in _rep["warnings"], False)

# ---- validate_ledger: a corrupted candidates.json is named, not crashed on (2026-09-26) ----
candidates.validate_ledger({"10.1/a": {"decision": "pending"}, "_runs": {"xref": {"complete": True}}})
check_true("validate_ledger accepts a well-formed ledger", True)   # no exception raised above
check_true("validate_ledger refuses a non-object ledger",
           _raises(lambda: candidates.validate_ledger(["not", "a", "dict"])))
check_true("validate_ledger refuses an entry that is not an object",
           _raises(lambda: candidates.validate_ledger({"10.1/a": "pending"})))
check_true("validate_ledger refuses an entry with a bad decision",
           _raises(lambda: candidates.validate_ledger({"10.1/a": {"decision": "maybe"}})))
try:
    candidates.validate_ledger({"10.1/a": {"decision": "maybe"}})
    _vl_msg = ""
except ValueError as e:
    _vl_msg = str(e)
check_true("validate_ledger names the bad entry", "10.1/a" in _vl_msg, _vl_msg)
check_true("validate_ledger refuses a non-dict _runs",
           _raises(lambda: candidates.validate_ledger({"_runs": ["xref"]})))

# references.audit_rows: a corrupted ledger is reported as a corpus defect, not a crash.
_bad_ledger = {"10.1/bad": "not-a-dict"}
_rep = references.audit_rows([_grow()], "ref", ledger=_bad_ledger)
check_true("a corrupted ledger fails the audit as a named corpus defect, not a crash",
           _rep["failed"] and any("10.1/bad" in c for c in _rep["corpus"]), _rep["corpus"])

# Entrance test: candidates.py itself refuses a corrupted candidates.json cleanly
# (an argparse error), instead of an unhandled AttributeError from --list.
_cvd = _tmpf.mkdtemp()
_cvrp, _cvlp = os.path.join(_cvd, "rows.json"), os.path.join(_cvd, "candidates.json")
common.dump_json([_grow()], _cvrp)
common.dump_json({"10.1/bad": "not-a-dict"}, _cvlp)
_argv = sys.argv
sys.argv = ["candidates.py", "--rows", _cvrp, "--list", "pending"]
_exit = None
try:
    candidates.main()
except SystemExit as e:
    _exit = e
finally:
    sys.argv = _argv
check_true("candidates.py refuses a corrupted ledger with SystemExit(2), naming the bad entry",
           _exit is not None and _exit.code == 2, repr(_exit))

# ---- final fixes C1: every row emitter stamps built_at (2026-09-25) ---------
import importlib.util as _ilu  # noqa: E402

import lab_corpus  # noqa: E402

check("GATES_SINCE is the day the gates shipped", common.GATES_SINCE, "2026-09-25")
check_true("a row built since the gates makes the table gated",
           common.is_gated([{"ref": "B", "built_at": common.GATES_SINCE}]))
check_true("an old build date stays legacy", not common.is_gated([{"ref": "B", "built_at": "2026-08-01"}]))
check_true("a table with no built_at/canonical_at/verified stays legacy",
           not common.is_gated([{"ref": "C1", "apa": "Doe, J. (2001). T. V."}]))
_c1rows, _c1rep = merge_lanes.merge([_lane("A", [_p("A-01", doi="10.1/c1")])])
check_true("merge_lanes stamps built_at on every row", all(r.get("built_at") for r in _c1rows))
check_true("a merge_lanes table where verify never ran is gated", common.is_gated(_c1rows))
_c1code, _c1d = _sheet_main([dict(_c1rows[0], apa="Smith, J. (2020). Paper A-01. J Neurosci, 1, 1-2.")])
check("spreadsheet refuses an unverified merge_lanes table",
      (_c1code, os.path.exists(os.path.join(_c1d, "bib.xlsx"))), (1, False))
_c1canon = [_grow("G1", "10.1/g1")]
_c1added, _, _ = merge_lanes.append(_c1canon, "ref", _lane("X", [_p("X-01", doi="10.1/c1x")]))
check_true("merge_lanes --append stamps built_at", bool(_c1canon[-1].get("built_at")))
_c1spec = _ilu.spec_from_file_location(
    "_brt", os.path.join(os.path.dirname(common.__file__), "..", "templates", "build_rows_template.py"))
_brt = _ilu.module_from_spec(_c1spec)
_c1spec.loader.exec_module(_brt)
_brt.PAPERS = [("T", "M1", "10.1/m1", "Huth, A. G.", 2016, "Title", "Sum.", "classic", "search")]
check_true("the rows template stamps built_at", common.is_gated(_brt.rows()))
_c1out = os.path.join(_tmpf.mkdtemp(), "lab_papers.json")
_c1w = {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/lab", "title": "Lab paper",
        "publication_year": 2020, "authorships": [{"author": {"display_name": "Ada Lovelace"}}]}
_c1argv = sys.argv
sys.argv = ["lab_corpus.py", "--author", "A1", "--out", _c1out, "--email", "t@example.org"]
try:
    with _patched(lab_corpus, fetch_works=lambda *a, **k: [_c1w]):
        lab_corpus.main()
finally:
    sys.argv = _c1argv
check_true("lab_corpus stamps built_at", common.is_gated(common.load_json(_c1out)))

# ---- final fixes C2: strict symmetric title_match for deferrals (2026-09-25) -----
check_true("title_match: a case/punctuation variant matches",
           common.title_match("Sparse coding in visual cortex", "Sparse Coding in Visual Cortex."))
check_true("title_match: containment in one direction only is not a match",
           not common.title_match("Attention is not all you need: pure attention loses rank",
                                  "Attention is all you need"))
check_true("title_match: a missing title never matches", not common.title_match("", "Deep learning"))


def _c2(kept_title, deferred):
    return merge_lanes.merge([_lane("A", [_p("A-01", doi="10.1/c2", title=kept_title, au="Vaswani, A.",
                                             year=2017)], deferred=[deferred])])[1]


_c2r = _c2("Attention is all you need",
           {"title": "Attention is not all you need: pure attention loses rank", "first_author": "Dong, Y.",
            "year": 2021})
check("a deferral containing the kept title plus more words is lost",
      [d["title"] for d in _c2r["lost"]], ["Attention is not all you need: pure attention loses rank"])
_c2r = _c2("Deep learning", {"title": "Deep learning in neural networks: An overview",
                             "first_author": "Vaswani, A.", "year": 2017})
check("a short kept title contained in a longer deferral is lost",
      [d["title"] for d in _c2r["lost"]], ["Deep learning in neural networks: An overview"])
_c2r = _c2("Attention is all you need", {"title": "Attention is all you need", "first_author": "Vaswani, A."})
check("an exact title with an agreeing first author is matched",
      ([d["title"] for d in _c2r["deferrals_matched"]], _c2r["unconfirmed"]), (["Attention is all you need"], []))
_c2r = _c2("Attention is all you need", {"title": "Attention is all you need", "reason": "lane B"})
check("an exact title with no first_author or year is unconfirmed, not matched",
      ([d["title"] for d in _c2r["unconfirmed"]], _c2r["deferrals_matched"], _c2r["lost"]),
      (["Attention is all you need"], [], []))
_c2d = _tmpf.mkdtemp()
os.makedirs(os.path.join(_c2d, "raw"))
common.dump_json(_lane("A", [_p("A-01", doi="10.1/c2", title="Attention is all you need")],
                       deferred=[{"title": "Attention is all you need"}]), os.path.join(_c2d, "raw", "A.json"))
check("merge_lanes exits 1 on an unconfirmed deferral",
      _merge_exit(os.path.join(_c2d, "raw"), os.path.join(_c2d, "rows.json")), 1)
_c2dl = lambda t: [{"doi": "10.1/dl", "title": "Deep learning in neural networks: An overview",  # noqa: E731
                    "year": "2015", "source": "crossref"}]
check("find_doi rejects a containment-only title match",
      handcheck.find_doi({"ref": "B", "search_title": "Deep learning", "search_year": 2015}, (_c2dl,)), [])
check_true("the search template requires first_author and year on deferrals",
           "first_author` and `year` are required" in _TPL)

# ---- final fixes I1: a fabricated DOI with a real title is not OK (2026-09-25) -----
_i1rec = {"title": "Spatiotemporal energy models for the perception of motion", "year": "1985",
          "first_author": "Adelson EH", "journal": "JOSA A"}
_i1c = {"label": "F", "doi": "10.9/fabricated", "title": _i1rec["title"],
        "expect_first_author": "Adelson", "expect_year": "1985"}
with _patched(verify, lookup_crossref=lambda d: None, lookup_pubmed_title=lambda t: dict(_i1rec)):
    _r = verify.verify_one(dict(_i1c))
check("a DOI that does not resolve + a title-search hit is MISMATCH, not OK", _r["verdict"], "MISMATCH")
check_true("...naming the DOI that does not resolve",
           any("DOI 10.9/fabricated does not resolve; title-search found" in i for i in _r["issues"]), str(_r))
with _patched(verify, lookup_crossref=lambda d: None, lookup_pubmed_id=lambda i: dict(_i1rec),
              lookup_pubmed_title=lambda t: None):
    _r = verify.verify_one(dict(_i1c, pmid="123"))
check("a DOI that does not resolve + a PMID hit is MISMATCH", _r["verdict"], "MISMATCH")
check_true("...naming the PMID source", any("does not resolve; pmid found" in i for i in _r["issues"]), str(_r))
_i1other = dict(_i1rec, first_author="Zhou Q", title="An unrelated paper on retinal circuits")
with _patched(verify, lookup_crossref=lambda d: dict(_i1other), lookup_pubmed_id=lambda i: dict(_i1rec)):
    _r = verify.verify_one(dict(_i1c, pmid="123"))
check("with a PMID and a DOI, the claim is checked against the DOI record",
      (_r["verdict"], _r["source"]), ("MISMATCH", "doi"))
with _patched(verify, lookup_crossref=lambda d: dict(_i1rec), lookup_pubmed_id=lambda i: dict(_i1other)):
    _r = verify.verify_one(dict(_i1c, pmid="123"))
check("a PMID row whose DOI resolves and matches is OK from the DOI", (_r["verdict"], _r["source"]),
      ("OK", "doi"))


def _i1_404(doi, fv=""):
    raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)


with _patched(common, crossref_work=_i1_404, datacite_work=_i1_404):
    check("canonical: a CrossRef 404 (and DataCite 404 too) is a missing DOI, not a fetch error",
          references.canonical({"ref": "Z", "doi": "10.9/fabricated"}),
          {"error": "DOI does not exist (404)", "source": "missing"})
_i1d = _tmpf.mkdtemp()
_i1rp = os.path.join(_i1d, "rows.json")
common.dump_json([_stamp({"ref": "Z1", "doi": "10.9/fabricated", "search_title": "T"})], _i1rp)
_i1out = io.StringIO()
_argv = sys.argv
sys.argv = ["references.py", "--rows", _i1rp, "--email", "t@example.org", "--retry-wait", "0"]
try:
    with _patched(common, crossref_work=_i1_404, datacite_work=_i1_404), _sleeps(), _ctx.redirect_stdout(_i1out), \
            _ctx.redirect_stderr(io.StringIO()):
        references.main()
except SystemExit:
    pass
finally:
    sys.argv = _argv
check_true("references prints 'DOI does not exist' for a 404", "✗ Z1: DOI does not exist" in _i1out.getvalue(),
           _i1out.getvalue())
check_true("...not 'fetch failed'", "fetch failed" not in _i1out.getvalue())

# ---- Task 1: DataCite DOIs verify and canonicalize (2026-09-26) ------------
# CrossRef does not hold Zenodo/figshare/OSF/Dryad software/data-set/preprint
# DOIs; they are registered with DataCite instead. Shape below is from a live
# probe of api.datacite.org/dois/10.5281/zenodo.3509134.
def _dc_attrs(**over):
    base = {"types": {"resourceTypeGeneral": "Software"}, "publicationYear": 2020,
            "publisher": "Zenodo", "version": "v1.0.0",
            "creators": [{"name": "The pandas development team", "nameType": "Personal",
                         "familyName": "The pandas development team"}],
            "titles": [{"title": "pandas-dev/pandas: Pandas"}]}
    base.update(over)
    return base


_dcr = common.datacite_record(_dc_attrs())
check("datacite_record: a group creator with no givenName is kept whole, no initials",
      _dcr["people"], ["The pandas development team"])
check("datacite_record: title/year/version/resource_type/journal/publisher",
      (_dcr["title"], _dcr["year"], _dcr["version"], _dcr["resource_type"],
       _dcr["journal"], _dcr["publisher"]),
      ("pandas-dev/pandas: Pandas", "2020", "v1.0.0", "Software", "Zenodo", "Zenodo"))
check("datacite_record: publisher as a dict is normalized to its name",
      common.datacite_record(_dc_attrs(publisher={"name": "Zenodo"}))["journal"], "Zenodo")
check("datacite_record: a personal creator with a given name formats with initials",
      common.datacite_record(_dc_attrs(creators=[{"familyName": "Smith", "givenName": "Jane"}]))["people"],
      ["Smith, J."])
check("datacite_record: never a chapter (book is always empty)",
      common.datacite_record(_dc_attrs())["book"], "")

check("build_datacite_apa: group creator, software descriptor, version",
      common.build_datacite_apa(["The pandas development team"], "2020", "pandas-dev/pandas: Pandas",
                                "v1.0.0", "Software", "Zenodo"),
      "The pandas development team (2020). pandas-dev/pandas: Pandas (Version v1.0.0) "
      "[Computer software]. Zenodo.")
check("build_datacite_apa: no version omits the parenthetical; Dataset -> Data set",
      common.build_datacite_apa(["Smith, J."], "2021", "A dataset", None, "Dataset", "Dryad"),
      "Smith, J. (2021). A dataset [Data set]. Dryad.")
check("build_datacite_apa: Preprint descriptor",
      common.build_datacite_apa(["Smith, J."], "2021", "A preprint", None, "Preprint", "OSF"),
      "Smith, J. (2021). A preprint [Preprint]. OSF.")
check("build_datacite_apa: an unrecognized resource type omits the bracket",
      common.build_datacite_apa(["Smith, J."], "2021", "A thing", None, "Other", "Figshare"),
      "Smith, J. (2021). A thing. Figshare.")
_dc_apa_ok = common.build_datacite_apa(["The pandas development team"], "2020",
                                       "pandas-dev/pandas: Pandas", "v1.0.0", "Software", "Zenodo")
check("build_datacite_apa passes the audit (no empty venue, no defects)",
      references.audit(_dc_apa_ok, True)[0], [])


def _dc_json_body(url, **k):
    return json.dumps({"data": {"attributes": _dc_attrs()}}).encode()


# (M1 review: datacite_work fetches through its own _datacite_get, not http_json)
with _patched(common, _datacite_get=_dc_json_body):
    _dw = common.datacite_work("10.5281/zenodo.3509134")
check("datacite_work: fetched through _datacite_get and normalized like crossref_work",
      (_dw["title"], _dw["resource_type"]), ("pandas-dev/pandas: Pandas", "Software"))


def _dc_404(*a, **k):
    raise urllib.error.HTTPError("u", 404, "Not Found", {}, None)


with _patched(common, _datacite_get=_dc_404):
    check_true("datacite_work: a 404 propagates like crossref_work",
               _raises(lambda: common.datacite_work("10.5281/zenodo.nonexistent")))


def _cr_404(doi, fallback_venue=""):
    raise urllib.error.HTTPError("u", 404, "no", {}, None)


_dc_rec = dict(common.datacite_record(_dc_attrs()))
with _patched(common, crossref_work=_cr_404, datacite_work=lambda d, fv="": dict(_dc_rec)):
    _lc = verify.lookup_crossref("10.5281/zenodo.3509134")
check("verify.lookup_crossref: falls back to DataCite on a clean CrossRef 404",
      (_lc["title"], _lc["source"]), ("pandas-dev/pandas: Pandas", "datacite"))

with _patched(common, crossref_work=_cr_404, datacite_work=_cr_404):
    check("verify.lookup_crossref: a DOI missing from BOTH CrossRef and DataCite is still a clean miss",
          verify.lookup_crossref("10.5281/zenodo.nonexistent"), None)

_dc_c = {"label": "DC1", "doi": "10.5281/zenodo.3509134",
         "expect_first_author": "The pandas development team", "expect_year": "2020",
         "title": "pandas-dev/pandas: Pandas"}
with _patched(common, crossref_work=_cr_404, datacite_work=lambda d, fv="": dict(_dc_rec)):
    _dcv = verify.verify_one(dict(_dc_c))
check("verify_one: a DataCite-only DOI verifies OK with source datacite",
      (_dcv["verdict"], _dcv["source"]), ("OK", "datacite"))

_dc_i1c = {"label": "DCF", "doi": "10.5281/zenodo.fabricated", "title": _i1rec["title"],
           "expect_first_author": "Adelson", "expect_year": "1985"}
with _patched(common, crossref_work=_cr_404, datacite_work=_cr_404), \
        _patched(verify, lookup_pubmed_title=lambda t: dict(_i1rec)):
    _dcm = verify.verify_one(dict(_dc_i1c))
check("verify_one (I1 unchanged): a DOI missing from BOTH registries + a title-search hit is MISMATCH",
      _dcm["verdict"], "MISMATCH")
check_true("...naming the DOI that does not resolve",
           any("does not resolve" in i for i in _dcm["issues"]), str(_dcm))


# references.canonical(): CrossRef 404 -> DataCite; both 404 -> unchanged "DOI does not exist"
def _dc_row(ref="DC1", doi="10.5281/zenodo.3509134"):
    return _stamp({"ref": ref, "doi": doi, "apa": ""})


with _patched(common, crossref_work=_cr_404, datacite_work=lambda d, fv="": dict(_dc_rec)):
    _dcres = references.canonical(_dc_row())
check("canonical: CrossRef 404 falls back to DataCite",
      _dcres["apa"],
      "The pandas development team (2020). pandas-dev/pandas: Pandas (Version v1.0.0) "
      "[Computer software]. Zenodo.")
check("canonical: source is datacite", _dcres["source"], "datacite")

with _patched(common, crossref_work=_cr_404, datacite_work=_cr_404):
    check("canonical: a DOI missing from BOTH is still 'DOI does not exist' (unchanged)",
          references.canonical(_dc_row()),
          {"error": "DOI does not exist (404)", "source": "missing"})

_dc_row2 = _dc_row("DC2")
with _patched(common, crossref_work=_cr_404, datacite_work=lambda d, fv="": dict(_dc_rec)), _sleeps():
    _dcrows_res = references.canon_rows([_dc_row2], "ref", "2026-09-26", sleep=0, retry_wait=0)
check("canon_rows: a DataCite-only DOI is rebuilt", _dcrows_res["rebuilt"], 1)
# (C1 review: the group creator now raises an ack-able datacite-unsplit-author warning)
_dc_audit = references.audit_rows([_dc_row2], "ref", acks={"DC2": {
    "datacite-unsplit-author:The pandas development team": "a development team"}})
check("canon_rows: the rebuilt apa passes references.audit_rows (no defects, gate passes once acked)",
      (_dc_audit["defects"], _dc_audit["failed"]), ({}, False))

# ---- Task 5 addendum (Task 1 review): DataCite regression tests (2026-09-26) ----
# A DataCite record that RESOLVES but disagrees with the claim must MISMATCH, not
# be waved through just because the DOI exists somewhere.
_dc_mismatch_c = {"label": "DCM", "doi": "10.5281/zenodo.3509134",
                  "expect_first_author": "Someone Else", "expect_year": "1999",
                  "title": "A completely different paper"}
with _patched(common, crossref_work=_cr_404, datacite_work=lambda d, fv="": dict(_dc_rec)):
    _dcmis = verify.verify_one(dict(_dc_mismatch_c))
check("verify_one: a DataCite record that resolves but disagrees with the claim is MISMATCH",
      _dcmis["verdict"], "MISMATCH")


def _dc_502(*a, **k):
    raise urllib.error.HTTPError("u", 502, "bad gateway", {}, None)


def _dc_reset(*a, **k):
    raise ConnectionResetError("connection reset by peer")


for _dc_fail, _dc_why in [(_dc_502, "HTTPError 502"), (_dc_reset, "ConnectionResetError")]:
    with _patched(common, crossref_work=_cr_404, datacite_work=_dc_fail):
        check_true(f"verify.lookup_crossref: a transient DataCite failure ({_dc_why}) after a "
                   "clean CrossRef 404 propagates (ERROR, not a miss)",
                   _raises(lambda: verify.lookup_crossref("10.5281/zenodo.3509134")))
        _dcv_err = verify.verify_one(dict(_dc_c))
    check(f"verify_one: a transient DataCite failure ({_dc_why}) after a clean CrossRef 404 is ERROR",
          _dcv_err["verdict"], "ERROR")
    with _patched(common, crossref_work=_cr_404, datacite_work=_dc_fail):
        _dc_canon_err = references.canonical(_dc_row("DCE"))
    check(f"canonical: a transient DataCite failure ({_dc_why}) after a clean CrossRef 404 is "
          f"source 'error', never 'missing'", _dc_canon_err["source"], "error")

# references.audit passes on a personal-creator apa and on a Dataset descriptor apa
# (not just the group-creator/Software case already covered above).
_dc_personal_apa = common.build_datacite_apa(["Smith, J."], "2021", "A dataset", None, "Dataset", "Dryad")
check("build_datacite_apa (personal creator, Dataset) passes the audit (no defects)",
      references.audit(_dc_personal_apa, True)[0], [])

# ---- final fixes I2: upgrade verify re-establishes identity (2026-09-25) ------
_i2rec = {"title": "Concrete problems in AI safety", "year": "2016", "first_author": "Amodei D", "journal": "arXiv"}
_i2row = {"ref": "U1", "doi": "10.1/u1", "search_author": "Amodei, D.", "search_year": 2016,
          "search_title": "Concrete problems in AI safety", "canonical_at": "2026-08-18",
          "apa": "Amodei, D., & Olah, C. (2016). Concrete problems in AI safety. arXiv."}
_i2c = verify.rows_to_citations([_i2row])[0]
check("a canonical row with a search claim is checked against the claim",
      (_i2c["expect_first_author"], _i2c["title"]), ("Amodei, D.", "Concrete problems in AI safety"))
check("...and against its canonical apa as alt_expect",
      (_i2c["alt_expect"]["expect_surname"], _i2c["alt_expect"]["expect_year"]), ("Amodei", "2016"))
with _patched(verify, lookup_crossref=lambda d: dict(_i2rec)):
    check("both claims agree with the record -> OK", verify.verify_one(dict(_i2c))["verdict"], "OK")
    _r = verify.verify_one(verify.rows_to_citations([dict(_i2row, apa="Zhou, Q. (2001). Retinal circuits. J.")])[0])
    check("an apa that disagrees with the record -> MISMATCH, even when the claim agrees", _r["verdict"], "MISMATCH")
    check_true("...the issue is labeled as the canonical apa's",
               any(i.startswith("canonical apa: ") for i in _r["issues"]), str(_r))
    _r = verify.verify_one(verify.rows_to_citations([dict(_i2row, search_author="Zhou, Q.")])[0])
    check("a claim that disagrees with the record -> MISMATCH, even when the apa agrees", _r["verdict"], "MISMATCH")
_i2bare = {k: v for k, v in _i2row.items() if not k.startswith("search_")}
_i2c = verify.rows_to_citations([_i2bare])[0]
check("a canonical row with no search claim has claim_basis canonical-apa",
      (_i2c.get("claim_basis"), "alt_expect" in _i2c), ("canonical-apa", False))
with _patched(verify, lookup_crossref=lambda d: dict(_i2rec)), _sleeps():
    _i2res = verify._verify_pass([_i2c], 0)
_i2rows = [dict(_i2bare)]
verify.stamp_rows(_i2rows, _i2res, "ref", "2026-09-25")
check("stamp_rows copies claim_basis into verified", _i2rows[0]["verified"].get("claim_basis"), "canonical-apa")
_i2g = dict(_grow("U2", "10.1/u2"))
_i2g["verified"]["claim_basis"] = "canonical-apa"
_rep = references.audit_rows([_i2g], "ref")
check("the audit warns identity-not-reestablished for a canonical-apa basis",
      [w for w, _ in _rep["unacked"].get("U2", [])], ["identity-not-reestablished"])
check("...and an acknowledgment clears it",
      references.audit_rows([_i2g], "ref", {"U2": {"identity-not-reestablished": "DOI checked by hand"}})["failed"],
      False)

# ---- final fixes I3: abstracts and summary checks bound to the paper (2026-09-25) ----
_i3R = [{"ref": "J", "doi": "10.1/J", "summary": "s"}, {"ref": "O", "doi": "10.1/new-o", "summary": "s"},
        {"ref": "L", "doi": "10.1/new-l", "summary": "s"}]
_i3old = {"O": {"text": "old paper's abstract", "source": "openalex", "url": "", "doi": "10.1/old-o", "arxiv": ""},
          "L": {"text": "hand-added", "source": "landing-page", "url": "u", "doi": "10.1/old-l", "arxiv": ""}}
answer_keys = {"arxiv": set(), "openalex": {"10.1/j", "10.1/new-o", "10.1/new-l"}, "s2": set(), "pubmed": set()}
fail_keys = {}
_asked.clear()
_i3ab, _i3miss, _i3fail, _i3stale = abstracts.collect(_i3R, "ref", dict(_i3old),
                                                      {n: _fx(n, "text-" + n) for n in answer_keys})
check("a fetched abstract records the ids it was fetched for", (_i3ab["J"]["doi"], _i3ab["J"]["arxiv"]),
      ("10.1/j", ""))
check("an entry fetched for other ids is refetched", (_i3ab["O"]["text"], _i3ab["O"]["doi"]),
      ("text-openalex", "10.1/new-o"))
check("a landing-page entry for other ids is reported stale", _i3stale, ["L"])
check("...and neither overwritten nor refetched", (_i3ab["L"], "10.1/new-l" in _asked["openalex"]),
      (_i3old["L"], False))
_i3S = [dict(_grow("S1", "10.1/s1"), summary="It found X.")]
_i3S[0].pop("summary_check")
_i3AB = {"S1": {"text": "We found X.", "source": "openalex", "doi": "10.1/s1", "arxiv": ""}}
_b, _na, _man = summary_audit.prepare(_i3S, "ref", _i3AB)
summary_audit.ingest(_i3S, "ref", [{"ref": "S1", "verdict": "supported", "summary_sha": _man["sha"]["S1"]}],
                     _i3AB, _man, "2026-09-25")
_i3sc = _i3S[0]["summary_check"]
check("summary_check records the ids and the abstract's hash",
      (_i3sc.get("doi"), _i3sc.get("arxiv"), _i3sc.get("abstract_sha")),
      ("10.1/s1", "", common.summary_sha("We found X.")))
check("a summary check passes the audit for the same ids", _codes(references.audit_rows(_i3S, "ref"), "S1"), [])
_i3moved = dict(_i3S[0], summary_check=dict(_i3sc, doi="10.1/other"))
check("a summary check for other ids is summary-unchecked",
      _codes(references.audit_rows([_i3moved], "ref"), "S1"), ["summary-unchecked"])
_b, _na, _man = summary_audit.prepare([_i3moved], "ref", _i3AB)
check("prepare re-queues a summary checked under other ids", _man["refs"], ["S1"])

_b, _na, _man = summary_audit.prepare([_i3moved], "ref", {"S1": dict(_i3AB["S1"], doi="10.1/elsewhere")})
check("prepare refuses an abstract recorded for other ids (not batched, not no-abstract)",
      (_man["refs"], _na, list(_man["refused"])), ([], [], ["S1"]))

# ---- final fixes I4: a failed abstract fetch is not "no-abstract" (2026-09-25) -----
def _i4_abstracts_main(rows, arxiv_fails):
    d = _tmpf.mkdtemp()
    rp = os.path.join(d, "rows.json")
    common.dump_json(rows, rp)
    none = lambda ids: ({}, set())  # noqa: E731
    argv = sys.argv
    sys.argv = ["abstracts.py", "--rows", rp, "--email", "t@example.org"]
    try:
        with _patched(abstracts, fetch_arxiv=lambda ids: ({}, set(ids) & arxiv_fails), fetch_s2=none,
                      fetch_pubmed=none, make_fetch_openalex=lambda e: none), \
                _ctx.redirect_stdout(io.StringIO()), _ctx.redirect_stderr(io.StringIO()):
            abstracts.main()
    except SystemExit:
        pass
    finally:
        sys.argv = argv
    return d


_i4d = _i4_abstracts_main([{"ref": "F", "arxiv": "2301.00002", "summary": "s"}], {"2301.00002"})
_i4f = common.load_optional_json(os.path.join(_i4d, "abstracts_failed.json"), None)
check_true("abstracts.py writes abstracts_failed.json naming the failed ref with a reason",
           isinstance(_i4f, dict) and list(_i4f) == ["F"] and bool(_i4f["F"]), str(_i4f))
_i4d0 = _i4_abstracts_main([{"ref": "N", "arxiv": "2301.00003", "summary": "s"}], set())
check("...and an empty one when nothing failed",
      common.load_optional_json(os.path.join(_i4d0, "abstracts_failed.json"), None), {})
_b, _na, _man = summary_audit.prepare([{"ref": "F", "summary": "s"}, {"ref": "N", "summary": "t"}], "ref", {},
                                      failed={"F": "arxiv batch failed"})
check("prepare refuses a failed-fetch ref instead of filing it as no-abstract",
      (_na, list(_man["refused"])), (["N"], ["F"]))
check_true("...telling you to re-run abstracts.py or add a landing-page entry",
           "re-run abstracts.py or add a landing-page entry" in _man["refused"]["F"])
_b, _na, _man = summary_audit.prepare([{"ref": "F", "summary": "s"}], "ref",
                                      {"F": {"text": "hand abstract", "source": "landing-page"}},
                                      failed={"F": "arxiv batch failed"})
check("a landing-page entry added since the failure clears the refusal", (_man["refs"], _man["refused"]),
      (["F"], {}))
common.dump_json([{"ref": "F", "arxiv": "2301.00002", "summary": "s"}], os.path.join(_i4d, "rows.json"))
_argv = sys.argv
sys.argv = ["summary_audit.py", "--rows", os.path.join(_i4d, "rows.json"), "--prepare"]
_i4code = 0
try:
    with _ctx.redirect_stdout(io.StringIO()):
        summary_audit.main()
except SystemExit as e:
    _i4code = e.code or 0
finally:
    sys.argv = _argv
check("summary_audit --prepare exits 1 on a ref whose abstract fetch failed", _i4code, 1)

# ---- final fixes I5: one S2 400 does not fail a whole batch (2026-09-25) ------
def _i5_stub(bad, make, transient_on=()):
    calls = []

    def f(path, body=None):
        ids = body["ids"]
        calls.append(list(ids))
        if any(i in transient_on for i in ids):
            raise urllib.error.HTTPError("u", 429, "slow down", {}, None)
        if any(i in bad for i in ids):
            raise urllib.error.HTTPError("u", 400, "bad id", {}, None)
        return [make(i) for i in ids]
    return f, calls


_i5f, _i5calls = _i5_stub({"DOI:bad"}, lambda i: {"n": i})
with _patched(common, s2_request=_i5f):
    _i5res, _i5failed, _i5rej = common.s2_batch("paper/batch?fields=x", ["DOI:a", "DOI:b", "DOI:bad", "DOI:c"], 4)
check("s2_batch bisects a 400 down to the one rejected id",
      (sorted(_i5res), _i5failed, _i5rej), (["DOI:a", "DOI:b", "DOI:c"], set(), {"DOI:bad"}))
check("...and keeps each id's own record", _i5res["DOI:c"], {"n": "DOI:c"})
_i5f, _ = _i5_stub(set(), lambda i: {"n": i}, transient_on={"DOI:t"})
with _patched(common, s2_request=_i5f):
    _i5res, _i5failed, _i5rej = common.s2_batch("p", ["DOI:a", "DOI:t", "DOI:c", "DOI:d"], 2)
check("s2_batch marks a transiently failed chunk failed, not rejected, and continues",
      (sorted(_i5res), _i5failed, _i5rej), (["DOI:c", "DOI:d"], {"DOI:a", "DOI:t"}, set()))
_i5f, _ = _i5_stub({"DOI:10.1/bad"}, lambda i: {"citationCount": 7, "influentialCitationCount": 1})
with _patched(common, s2_request=_i5f), _ctx.redirect_stderr(io.StringIO()) as _i5err:
    _i5got = citations.fetch_s2([("A", "10.1/a"), ("B", "10.1/bad"), ("C", "10.1/c")])
check("citations.fetch_s2 counts every paper but the rejected one", sorted(_i5got), ["A", "C"])
check_true("...and names the rejected one", "10.1/bad" in _i5err.getvalue(), _i5err.getvalue())
_i5f, _ = _i5_stub(set(), lambda i: {"citationCount": 7, "influentialCitationCount": 1},
                   transient_on={"DOI:10.1/a"})
with _patched(common, s2_request=_i5f), _patched(citations, S2_BATCH=1), _ctx.redirect_stderr(io.StringIO()):
    _i5got = citations.fetch_s2([("A", "10.1/a"), ("C", "10.1/c")])
check("citations.fetch_s2 continues past a failed chunk", sorted(_i5got), ["C"])
_i5f, _ = _i5_stub({"DOI:10.1/bad"}, lambda i: {"abstract": "abs " + i})
with _patched(common, s2_request=_i5f), _ctx.redirect_stderr(io.StringIO()):
    _i5out, _i5fail = abstracts.fetch_s2(["DOI:10.1/a", "DOI:10.1/bad"])
check("abstracts.fetch_s2: a rejected id is 'not in S2', complete, not failed",
      (sorted(_i5out), _i5fail), (["DOI:10.1/a"], set()))
_i5f, _ = _i5_stub({"DOI:10.1/bad"}, lambda i: {"paperId": "P", "referenceCount": 1,
                                                "references": [{"externalIds": {"DOI": "10.1/r"}}]})
with _patched(common, s2_request=_i5f), _ctx.redirect_stderr(io.StringIO()) as _i5err:
    _i5x = xref.s2_refs(["10.1/a", "10.1/bad"])
check("xref.s2_refs: a rejected id is complete and empty; the rest keep their lists",
      ([r["doi"] for r in _i5x["10.1/a"]], _i5x["10.1/bad"]), (["10.1/r"], []))
check_true("...and the rejected id is reported by name", "10.1/bad" in _i5err.getvalue(), _i5err.getvalue())

# ---- final fixes I6: arXiv over https; curl follows redirects (2026-09-25) ------
check_true("the arXiv API is called over https", common.ARXIV_API.startswith("https://export.arxiv.org/"))
_i6cmds = []


def _i6run(out):
    def run(cmd, capture_output=True, timeout=None):
        _i6cmds.append(cmd)
        return _sp.CompletedProcess(cmd, 0, stdout=out, stderr=b"")
    return run


with _patched(common.shutil, which=lambda n: "/usr/bin/curl"), \
        _patched(common.subprocess, run=_i6run(b'{"ok": 1}\n200')):
    check("curl_get strips the status line from a 2xx body",
          common.curl_get("https://example.org/x", {}, 10), b'{"ok": 1}')
check_true("curl_get follows redirects, https only, and captures the status",
           {"-L", "--proto-redir", "=https", "-w"} <= set(_i6cmds[-1]), str(_i6cmds[-1]))
with _patched(common.shutil, which=lambda n: "/usr/bin/curl"), \
        _patched(common.subprocess, run=_i6run(b"<html>Moved Permanently</html>\n301")):
    check_true("curl_get raises OSError on a non-2xx final status",
               _raises(lambda: common.curl_get("https://example.org/x", {}, 10)))
_i6html = b"<html><body>Moved Permanently</body></html>"
check_true("arxiv_entries refuses a body that is not an Atom feed", _raises(lambda: common.arxiv_entries(_i6html)))
with _patched(common, http=lambda url, **k: _i6html), _sleeps():
    _i6e, _i6err = common.arxiv_batch(["2301.00001", "2301.00002"])
check("arxiv_batch marks a non-feed chunk errored, not missing", (_i6e, sorted(_i6err)),
      ({}, ["2301.00001", "2301.00002"]))

# ---- final fixes I7: a failed merge does not write rows.json (2026-09-25) -----
_i7d = _tmpf.mkdtemp()
os.makedirs(os.path.join(_i7d, "raw"))
common.dump_json(_lane("A", [_p("A-01", doi="10.1/a"), _p("A-02")]), os.path.join(_i7d, "raw", "A.json"))
check("merge_lanes exits 1 on a rejected paper", _merge_exit(os.path.join(_i7d, "raw"),
                                                             os.path.join(_i7d, "rows.json")), 1)
check("...writing the report but not rows.json",
      (os.path.exists(os.path.join(_i7d, "rows.json")), os.path.exists(os.path.join(_i7d, "merge_report.json"))),
      (False, True))
common.dump_json([{"ref": "OLD", "doi": "10.1/old"}], os.path.join(_i7d, "rows.json"))
_merge_exit(os.path.join(_i7d, "raw"), os.path.join(_i7d, "rows.json"))
check("...and leaves an existing rows.json untouched",
      [r["ref"] for r in common.load_json(os.path.join(_i7d, "rows.json"))], ["OLD"])
common.dump_json(_lane("A", [_p("A-01", doi="10.1/a")]), os.path.join(_i7d, "raw", "A.json"))
os.remove(os.path.join(_i7d, "rows.json"))
check("a clean merge writes rows.json", (_merge_exit(os.path.join(_i7d, "raw"), os.path.join(_i7d, "rows.json")),
                                         os.path.exists(os.path.join(_i7d, "rows.json"))), (0, True))

# ---- final fixes I8: the ledger records that xref/forward ran (2026-09-25) -----
_i8L = {}
candidates.add(_i8L, [{"doi": "10.9/a", "n_citations": 4}, {"doi": "10.1/in", "n_citations": 3}], "xref",
               {"10.1/in"}, asof="2026-09-25")
check("candidates.add records the run", _i8L.get("_runs"),
      {"xref": {"at": "2026-09-25", "n": 2, "complete": True}})
check("candidate_defects ignores the _runs record", candidates.candidate_defects({"_runs": _i8L["_runs"]}, set()),
      [])
candidates.decide(_i8L, "10.9/a", "include", "on topic", "2026-09-25")
check("export_included ignores the _runs record",
      [p["doi"] for p in candidates.export_included(_i8L, set(), "X")["papers"]], ["10.9/a"])
_rep = references.audit_rows([_grow()], "ref", ledger={})
check("a gated ledger with no xref/forward run warns under *",
      sorted(w for w, _ in _rep["unacked"].get("*", [])), ["no-forward-run", "no-xref-run"])
check("...and fails the audit until acknowledged", _rep["failed"], True)
_rep = references.audit_rows([_grow()], "ref", ledger={"_runs": {"xref": {"at": "d", "n": 1, "complete": True}}})
check("a ledger with an xref run still warns about forward",
      [w for w, _ in _rep["unacked"].get("*", [])], ["no-forward-run"])
_rep = references.audit_rows([_grow()], "ref", ledger=dict(_RUNS_LEDGER))
check("a ledger recording both runs passes", (_rep["failed"], "*" in _rep["warnings"]), (False, False))
check("a legacy table is not asked for runs", "*" in references.audit_rows(_legacy, "ref", ledger={})["warnings"],
      False)
_i8d = _tmpf.mkdtemp()
_i8rp = os.path.join(_i8d, "rows.json")
common.dump_json([{"ref": "A", "doi": "10.1/a", "cite_openalex": 5}], _i8rp)


def _i8_forward(*extra):
    def boom(wid, per, email):
        raise urllib.error.URLError("down")
    argv = sys.argv
    sys.argv = ["forward.py", "--rows", _i8rp, "--email", "t@example.org", *extra]
    try:
        with _patched(forward, openalex_ids=lambda dois, email: {"10.1/a": "W1"}, citing=boom), _sleeps(), \
                _ctx.redirect_stdout(io.StringIO()), _ctx.redirect_stderr(io.StringIO()):
            forward.main()
        return 0
    except SystemExit as e:
        return e.code or 0
    finally:
        sys.argv = argv


check("forward.py exits 1 when a landmark pull failed", _i8_forward(), 1)
check("...unless --allow-incomplete", _i8_forward("--allow-incomplete"), 0)
common.dump_json(_i8L, os.path.join(_i8d, "candidates.json"))
_argv = sys.argv
sys.argv = ["candidates.py", "--rows", _i8rp, "--list", "all"]
_i8out = io.StringIO()
try:
    with _ctx.redirect_stdout(_i8out), _ctx.redirect_stderr(io.StringIO()):
        candidates.main()
finally:
    sys.argv = _argv
check_true("candidates --list skips the _runs record", "_runs" not in _i8out.getvalue(), _i8out.getvalue())

# ---- final fixes I9: a hand check is bound to the apa it confirmed (2026-09-25) ----
check("apa_sha ignores case and whitespace", common.apa_sha(" Kuhn,  T. (1962). The Structure. "),
      common.apa_sha("kuhn, t. (1962). the structure."))
_i9rows = [{"ref": "B1", "apa": "Kuhn, T. S. (1962). The structure of scientific revolutions. U Chicago Press.",
            "summary": "", "canonical_at": common.GATES_SINCE}]
handcheck.ingest(_i9rows, "ref", [{"ref": "B1", "verdict": "confirmed", "source_checked": "LoC record",
                                   "apa_sha": common.apa_sha(_i9rows[0]["apa"])}],
                 [{"ref": "B1", "apa_sha": common.apa_sha(_i9rows[0]["apa"])}], "2026-09-25")
check("handcheck records the apa_sha it confirmed", _i9rows[0]["hand_verified"].get("apa_sha"),
      common.apa_sha(_i9rows[0]["apa"]))
check("a hand-checked row passes", _codes(references.audit_rows([_grow(), _i9rows[0]], "ref"), "B1"), [])
_i9ed = dict(_i9rows[0], apa=_i9rows[0]["apa"].replace("1962", "1970"))
_i9d = references.audit_rows([_grow(), _i9ed], "ref")["defects"].get("B1", [])
check_true("an apa edited since the hand check is hand-check-missing",
           any(x.startswith("hand-check-missing") and "apa changed since the hand check" in x for x in _i9d),
           str(_i9d))
_i9k = _grow("K1", "10.1/k1")
del _i9k["canonical_at"]
check("the kept-existing-apa warning id is bound to the apa",
      [w for w, _ in references.audit_rows([_i9k], "ref")["warnings"]["K1"]],
      [f"kept-existing-apa:{common.apa_sha(_i9k['apa'])[:8]}"])
_i9rp = os.path.join(_tmpf.mkdtemp(), "rows.json")
common.dump_json([dict(_i9k, apa=_i9k["apa"] + "?.")], _i9rp)
_argv = sys.argv
sys.argv = ["references.py", "--rows", _i9rp, "--repair", "--email", "t@example.org"]
try:
    with _ctx.redirect_stdout(io.StringIO()):
        references.main()
except SystemExit:
    pass
finally:
    sys.argv = _argv
check("--repair on a gated table does not stamp canonical_at", "canonical_at" in common.load_json(_i9rp)[0], False)

# ---- final fixes I10: concurrent rows.json writers (2026-09-25) --------------
def _i10_touch(path):
    st = os.stat(path)
    os.utime(path, (st.st_atime, st.st_mtime + 5))


_i10d = _tmpf.mkdtemp()
_i10rp = os.path.join(_i10d, "rows.json")
common.dump_json([{"ref": "A"}], _i10rp)
_i10m = os.path.getmtime(_i10rp)
common.save_rows(_i10rp, [{"ref": "A", "x": 1}], _i10m)
check("save_rows writes when the file is unchanged since load", common.load_json(_i10rp), [{"ref": "A", "x": 1}])
_i10m = os.path.getmtime(_i10rp)
_i10_touch(_i10rp)
check_true("save_rows refuses a file that changed since load",
           _raises(lambda: common.save_rows(_i10rp, [{"ref": "A", "x": 2}], _i10m)))
check("...and leaves it as the other writer left it", common.load_json(_i10rp), [{"ref": "A", "x": 1}])


def _i10_run(mod, argv, **patches):
    """Run mod.main() with `patches`; returns the exception it raised (None if it exited or returned)."""
    old = sys.argv
    sys.argv = argv
    try:
        with _patched(mod, **patches), _sleeps(), _ctx.redirect_stdout(io.StringIO()), \
                _ctx.redirect_stderr(io.StringIO()):
            mod.main()
    except SystemExit:
        return None
    except RuntimeError as e:
        return e
    finally:
        sys.argv = old
    return None


def _i10_rows(rows):
    common.dump_json(rows, _i10rp)
    return _i10rp


_i10row = {"ref": "V1", "doi": "10.1/v1", "search_title": "T", "search_author": "Smith", "search_year": 2020}


def _i10_verify_all(cits, sleep=0.4, retry_wait=60.0):
    _i10_touch(_i10rp)          # another writer lands while verify runs
    return [{"label": c["label"], "verdict": "OK", "found": None, "source": "doi", "issues": []} for c in cits]


_e = _i10_run(verify, ["verify.py", "--rows", _i10_rows([_i10row]), "--email", "t@example.org"],
              verify_all=_i10_verify_all)
check_true("verify refuses to stamp a rows.json that changed while it ran",
           isinstance(_e, RuntimeError) and "changed since it was loaded" in str(_e), repr(_e))
_i10res = os.path.join(_i10d, "hc.json")
common.dump_json([{"ref": "B1", "verdict": "confirmed", "source_checked": "LoC"}], _i10res)
_e = _i10_run(handcheck, ["handcheck.py", "--rows", _i10_rows([{"ref": "B1", "apa": "Doe, J. (1970). M. L."}]),
                          "--ingest", _i10res],
              ingest=lambda rows, keyf, results, hc_input, asof: (_i10_touch(_i10rp), (0, []))[1])
check_true("handcheck --ingest refuses a rows.json that changed", isinstance(_e, RuntimeError), repr(_e))
common.dump_json({"refs": [], "sha": {}, "no_abstract": [], "ids": {}, "abstract_sha": {}},
                 os.path.join(_i10d, "manifest.json"))
_e = _i10_run(summary_audit, ["summary_audit.py", "--rows", _i10_rows([{"ref": "S", "summary": "s"}]),
                              "--ingest", "--dir", _i10d],
              ingest=lambda *a: (_i10_touch(_i10rp), (0, []))[1])
check_true("summary_audit --ingest refuses a rows.json that changed", isinstance(_e, RuntimeError), repr(_e))
_e = _i10_run(references, ["references.py", "--rows", _i10_rows([{"ref": "R", "apa": "A, B. (2001). T?. V."}]),
                           "--repair", "--email", "t@example.org"],
              repair=lambda apa: (_i10_touch(_i10rp), (apa, []))[1])
check_true("references --repair refuses a rows.json that changed", isinstance(_e, RuntimeError), repr(_e))
_i10lane = os.path.join(_i10d, "lane.json")
common.dump_json(_lane("X", [_p("X-01", doi="10.1/x")]), _i10lane)
_e = _i10_run(merge_lanes, ["merge_lanes.py", "--append", _i10lane, "--into", _i10_rows([_grow()])],
              append=lambda rows, keyf, lane: (_i10_touch(_i10rp), ([], [], []))[1])
check_true("merge_lanes --append refuses a rows.json that changed", isinstance(_e, RuntimeError), repr(_e))

# Entrance test: --append --into an empty table ([]) is refused -- common.key_field
# would key the appended rows by "label" (its fallback for a table with no "ref"
# row to look at), silently diverging from every fresh-merge table's "ref" key.
_d5 = _tmpf.mkdtemp()
_emptyrp = os.path.join(_d5, "rows.json")
common.dump_json([], _emptyrp)
_emptylane = os.path.join(_d5, "lane.json")
common.dump_json(_lane("X", [_p("X-01", doi="10.1/x")]), _emptylane)
_argv = sys.argv
sys.argv = ["merge_lanes.py", "--append", _emptylane, "--into", _emptyrp]
_exit = None
try:
    merge_lanes.main()
except SystemExit as e:
    _exit = e
finally:
    sys.argv = _argv
check_true("merge_lanes --append --into an empty table is refused",
           _exit is not None and _exit.code == 2, repr(_exit))
check("merge_lanes --append --into an empty table leaves it untouched",
      common.load_json(_emptyrp), [])

# ---- final fixes I11: arXiv-only rows are visible to coverage (2026-09-25) -----
_i11 = merge_lanes.to_row(_p("A-01", arxiv="2301.00001v2"), "A")
check("to_row gives an arXiv-only paper its arXiv DOI and doi.org link", (_i11["doi"], _i11["link"], _i11["arxiv"]),
      ("10.48550/arXiv.2301.00001", "https://doi.org/10.48550/arXiv.2301.00001", "2301.00001"))
check("xref.rows_to_papers falls back to the arXiv DOI form",
      xref.rows_to_papers([{"ref": "X", "arxiv": "2301.00001"}]), [{"slug": "X", "doi": "10.48550/arXiv.2301.00001"}])
check("candidates.corpus_dois falls back to the arXiv DOI form",
      candidates.corpus_dois([{"ref": "X", "arxiv": "2301.00001v2"}, {"ref": "D", "doi": "10.1/D"}]),
      {"10.48550/arxiv.2301.00001", "10.1/d"})

# ---- final fixes: minors (2026-09-25) --------------------------------------
_code, _dd = _sheet_main([_grow()], candidates={"10.9/p": {"title": "P", "sources": {"xref": 4},
                                                           "decision": "pending"}})
check("spreadsheet refuses a gated table with a pending candidate",
      (_code, os.path.exists(os.path.join(_dd, "bib.xlsx"))), (1, False))
_code, _dd = _sheet_main([_grow()], candidates={"10.9/inc": {"title": "Inc", "sources": {"xref": 4},
                                                             "decision": "include", "reason": "on topic"}})
check("spreadsheet refuses a gated table with an included candidate missing from it",
      (_code, os.path.exists(os.path.join(_dd, "bib.xlsx"))), (1, False))
_mn = dict(_grow(), link="https://doi.org/10.1/other")
check("a doi.org link that disagrees with the DOI is a defect",
      _codes(references.audit_rows([_mn], "ref"), "G1"), ["link-doi-mismatch"])
check("a doi.org link in another case is not a mismatch",
      _codes(references.audit_rows([dict(_grow(), link="https://doi.org/10.1/G1")], "ref"), "G1"), [])
check("_ref_doi strips an arXiv version", xref._ref_doi({"ArXiv": "1706.03762v5"}), "10.48550/arxiv.1706.03762")
with open(xref.__file__, encoding="utf-8") as _fh:
    _XDOC = _fh.read().split('"""')[1]
check_true("xref's docstring names Semantic Scholar as a reference-list source",
           "Semantic Scholar" in " ".join(_XDOC.splitlines()[2:4]), _XDOC.splitlines()[2])
_mL = {"10.9/f": {"title": "F", "sources": {"forward": 5}, "decision": "include", "reason": "r"}}
_mx = candidates.export_included(_mL, set(), "X")["papers"][0]
check("export_included takes tag/source from the ledger's sources", (_mx["source"], _mx["tag"]),
      ("forward", "forward"))
check_true("a forward-sourced row has a spreadsheet color", "forward" in spreadsheet.COLORS)
_mrp = os.path.join(_tmpf.mkdtemp(), "rows.json")
common.dump_json([{"ref": "Z1", "doi": "10.1/z1"}, {"ref": "Z2", "doi": "10.1/z2"}], _mrp)
_argv = sys.argv
sys.argv = ["xref.py", "--rows", _mrp, "--out", os.path.join(os.path.dirname(_mrp), "x.json"),
            "--email", "t@example.org"]
_merr = io.StringIO()
try:
    with _patched(xref, fetch_all=lambda papers, sleep=0.4, retry_wait=60.0: (
            {"Z1": [{"doi": "10.1/c"}], "Z2": []}, [])), _ctx.redirect_stderr(_merr):
        xref.main()
except SystemExit:
    pass
finally:
    sys.argv = _argv
check_true("xref names the papers that contributed zero references",
           "1 paper(s) contributed zero references: Z2" in _merr.getvalue(), _merr.getvalue()[-300:])

# ---- post-review fix: s2_batch must not read an auth/request 4xx as "not in S2" (2026-09-25) ----
def _i6_stub(code, bad=frozenset()):
    """Every call raises HTTPError(code); if `bad` is given, only a batch that
    contains one of those ids raises (the rest succeed) -- used for the
    400-bisection cases. Calls are recorded so a test can assert no
    bisection happened."""
    calls = []

    def f(path, body=None):
        ids = body["ids"]
        calls.append(list(ids))
        if bad:
            if any(i in bad for i in ids):
                raise urllib.error.HTTPError("u", code, "err", {}, None)
            return [{"n": i} for i in ids]
        raise urllib.error.HTTPError("u", code, "err", {}, None)
    return f, calls


_i6f, _i6calls = _i6_stub(403)
with _patched(common, s2_request=_i6f), _ctx.redirect_stderr(io.StringIO()) as _i6err:
    _i6res, _i6failed, _i6rej = common.s2_batch("p", ["DOI:a", "DOI:b", "DOI:c", "DOI:d"], 4)
check("s2_batch: an always-403 chunk fails whole, rejects none",
      (_i6res, _i6failed, _i6rej), ({}, {"DOI:a", "DOI:b", "DOI:c", "DOI:d"}, set()))
check("...and makes exactly one request (no bisection)", len(_i6calls), 1)
check_true("...and names the HTTP code and S2_API_KEY on stderr",
           "403" in _i6err.getvalue() and "S2_API_KEY" in _i6err.getvalue(), _i6err.getvalue())

_i6f, _i6calls = _i6_stub(401)
with _patched(common, s2_request=_i6f), _ctx.redirect_stderr(io.StringIO()):
    _i6res, _i6failed, _i6rej = common.s2_batch("p", ["DOI:a", "DOI:b", "DOI:c", "DOI:d"], 4)
check("s2_batch: an always-401 chunk fails whole, rejects none, no bisection",
      (_i6res, _i6failed, _i6rej, len(_i6calls)), ({}, {"DOI:a", "DOI:b", "DOI:c", "DOI:d"}, set(), 1))

_i6f, _i6calls = _i6_stub(400, bad={"DOI:10.1/bad"})
with _patched(common, s2_request=_i6f), _ctx.redirect_stderr(io.StringIO()):
    _i6res, _i6failed, _i6rej = common.s2_batch("p", ["DOI:a", "DOI:b", "DOI:10.1/bad", "DOI:c"], 4)
check("s2_batch: a single bad id in a batch of 4 is bisected out and rejected alone",
      (sorted(_i6res), _i6failed, _i6rej),
      (["DOI:a", "DOI:b", "DOI:c"], set(), {"DOI:10.1/bad"}))

_i6f, _i6calls = _i6_stub(400)
with _patched(common, s2_request=_i6f), _ctx.redirect_stderr(io.StringIO()):
    _i6res, _i6failed, _i6rej = common.s2_batch("p", ["DOI:a", "DOI:b", "DOI:c", "DOI:d"], 4)
check("s2_batch: a chunk still 400-ing after full bisection is failed, not rejected",
      (_i6res, _i6failed, _i6rej), ({}, {"DOI:a", "DOI:b", "DOI:c", "DOI:d"}, set()))

_i6f, _ = _i6_stub(403)
with _patched(common, s2_request=_i6f), _ctx.redirect_stderr(io.StringIO()):
    _i6x = xref.s2_refs(["10.1/a", "10.1/b"])
check("xref.s2_refs: an always-403 stub leaves every doi incomplete (None), not empty",
      _i6x, {"10.1/a": None, "10.1/b": None})

_i6f, _ = _i6_stub(403)
_i6fetchers = {"arxiv": lambda ids: ({}, set()), "openalex": lambda ids: ({}, set()),
              "s2": abstracts.fetch_s2, "pubmed": lambda ids: ({}, set())}
with _patched(common, s2_request=_i6f), _ctx.redirect_stderr(io.StringIO()):
    _i6ab, _i6missing, _i6failedrefs, _i6stale = abstracts.collect(
        [{"ref": "P", "doi": "10.1/p", "summary": "s"}], "ref", {}, _i6fetchers)
check("abstracts.collect: an always-403 S2 fetch leaves the ref failed, not missing",
      (_i6missing, list(_i6failedrefs)), ([], ["P"]))

# ---- Task 2: bind summary and hand checks at --prepare (2026-09-26) --------
# summary_audit: the manifest binds a check to the paper's ids and its abstract's
# text, not just to the summary -- so a DOI arriving, or the abstract being
# refetched to different text, between --prepare and --ingest is caught instead
# of being silently stamped as if the checking agent had seen it.
_t2S = [{"ref": "T1", "summary": "It found X."}]
_t2AB = {"T1": {"text": "We found X.", "source": "openalex"}}
_b, _na, _t2man = summary_audit.prepare(_t2S, "ref", _t2AB)
check("summary_audit prepare records ids and abstract_sha in the manifest",
      (_t2man["ids"].get("T1"), _t2man["abstract_sha"].get("T1")),
      (list(common.ids_of(_t2S[0])), common.summary_sha("We found X.")))

_t2S_doi = [dict(_t2S[0], doi="10.1/t1")]        # the paper gained a DOI since --prepare
_n, _err = summary_audit.ingest(_t2S_doi, "ref", [{"ref": "T1", "verdict": "supported"}], _t2AB, _t2man,
                                "2026-09-26")
check("ingest refuses a ref whose ids changed since --prepare, and stamps nothing",
      (_n, _err, "summary_check" in _t2S_doi[0]),
      (0, ["T1: the paper or its abstract changed since --prepare; re-run --prepare"], False))

_t2S2 = [dict(_t2S[0])]                          # the abstract was refetched to different text
_t2AB2 = {"T1": {"text": "We found Z, not X.", "source": "openalex"}}
_n, _err = summary_audit.ingest(_t2S2, "ref", [{"ref": "T1", "verdict": "supported"}], _t2AB2, _t2man,
                                "2026-09-26")
check("ingest refuses a ref whose abstract text changed since --prepare, and stamps nothing",
      (_n, _err, "summary_check" in _t2S2[0]),
      (0, ["T1: the paper or its abstract changed since --prepare; re-run --prepare"], False))

_t2S3 = [dict(_t2S[0])]                          # unchanged: the happy path
_n, _err = summary_audit.ingest(_t2S3, "ref", [{"ref": "T1", "verdict": "supported",
                                                "summary_sha": _t2man["sha"]["T1"]}], _t2AB, _t2man,
                                "2026-09-26")
check("ingest stamps the unchanged happy path with the manifest's ids/abstract_sha",
      (_n, _err, _t2S3[0]["summary_check"]["doi"], _t2S3[0]["summary_check"]["abstract_sha"]),
      (1, [], "", common.summary_sha("We found X.")))

# the same drift check guards the no-abstract path: a DOI arriving must block
# the no-abstract stamp too, not just an abstract arriving.
_t2N = [{"ref": "T2", "summary": "No abstract for this one."}]
_b, _na, _t2manN = summary_audit.prepare(_t2N, "ref", {})
_t2N_doi = [dict(_t2N[0], doi="10.1/t2")]
_n, _err = summary_audit.ingest(_t2N_doi, "ref", [], {}, _t2manN, "2026-09-26")
check("ingest refuses a no-abstract ref whose ids changed since --prepare",
      (_n, _err, "summary_check" in _t2N_doi[0]),
      (0, ["T2: the paper or its abstract changed since --prepare; re-run --prepare"], False))

# handcheck: the hand-check input recorded at --prepare binds a result to the apa
# it was checked against, so an edit landing between --prepare and --ingest is
# caught -- rather than silently accepted, or (for "corrected") silently overwritten.
_t2book = {"ref": "H1", "apa": "Kuhn, T. S. (1962). The structure of scientific revolutions. U Chicago Press.",
           "summary": ""}
_t2cands, _t2todo = handcheck.prepare([_t2book], "ref", (_far,))
check("handcheck prepare records apa_sha in the hand-check input",
      _t2todo[0].get("apa_sha"), common.apa_sha(_t2book["apa"]))

_t2rows_edited = [dict(_t2book, apa=_t2book["apa"] + " (2nd printing)")]   # apa edited since --prepare
_n, _err = handcheck.ingest(_t2rows_edited, "ref",
                            [{"ref": "H1", "verdict": "confirmed", "source_checked": "LoC record"}],
                            _t2todo, "2026-09-26")
check("ingest refuses a result whose apa changed since --prepare, and stamps nothing",
      (_n, _err, "hand_verified" in _t2rows_edited[0]),
      (0, ["H1: the reference changed since --prepare; re-check it"], False))

_n, _err = handcheck.ingest(_t2rows_edited, "ref",
                            [{"ref": "H1", "verdict": "corrected", "apa": "Something else entirely.",
                              "source_checked": "LoC record"}],
                            _t2todo, "2026-09-26")
check("a corrected verdict is refused the same way, checked against the pre-correction apa",
      (_n, _err, _t2rows_edited[0]["apa"]),
      (0, ["H1: the reference changed since --prepare; re-check it"], _t2book["apa"] + " (2nd printing)"))

_t2rows_unlisted = [dict(_t2book, ref="H2")]     # never went through --prepare
_n, _err = handcheck.ingest(_t2rows_unlisted, "ref",
                            [{"ref": "H2", "verdict": "confirmed", "source_checked": "LoC record"}],
                            _t2todo, "2026-09-26")
check("a result for a ref absent from the hand-check input is refused",
      (_n, _err), (0, ["H2: not in this hand check"]))

_t2rows_ok = [dict(_t2book)]                     # unchanged: the happy path
_n, _err = handcheck.ingest(_t2rows_ok, "ref",
                            [{"ref": "H1", "verdict": "confirmed", "source_checked": "LoC record",
                              "apa_sha": _t2todo[0]["apa_sha"]}],
                            _t2todo, "2026-09-26")
check("ingest records the unchanged happy path", (_n, _err), (1, []))

# --input defaults to handcheck_input.json beside --rows
_hcd = _tmpf.mkdtemp()
_hcrp = os.path.join(_hcd, "rows.json")
common.dump_json([dict(_t2book)], _hcrp)
common.dump_json(_t2todo, os.path.join(_hcd, "handcheck_input.json"))
common.dump_json([{"ref": "H1", "verdict": "confirmed", "source_checked": "LoC record",
                   "apa_sha": _t2todo[0]["apa_sha"]}],
                 os.path.join(_hcd, "handcheck_result.json"))
_argv = sys.argv
sys.argv = ["handcheck.py", "--rows", _hcrp, "--ingest", os.path.join(_hcd, "handcheck_result.json")]
try:
    with _ctx.redirect_stdout(io.StringIO()):
        handcheck.main()
except SystemExit:
    pass
finally:
    sys.argv = _argv
check("handcheck --ingest reads handcheck_input.json beside --rows by default",
      common.load_json(_hcrp)[0]["hand_verified"]["verdict"], "confirmed")

# ---- Task 2 fix round 1: an old-format manifest/input must fail closed, not
# silently treat a genuinely drifted row as unchanged (2026-09-26) -----------
# summary_audit: a manifest written before ids/abstract_sha existed cannot prove
# what the checking agents saw. The reviewer's repro: a row that gained a DOI
# and a different abstract after an old-format --prepare must not be stamped.
_t2oldman = {"refs": ["T3"], "sha": {"T3": common.summary_sha("It found X.")}, "no_abstract": []}
_t2S_old = [{"ref": "T3", "summary": "It found X.", "doi": "10.1/t3"}]   # gained a DOI since the old --prepare
_n, _err = summary_audit.ingest(_t2S_old, "ref", [{"ref": "T3", "verdict": "supported"}],
                                {"T3": {"text": "A completely different abstract.", "source": "openalex"}},
                                _t2oldman, "2026-09-26")
check("an old-format manifest (no ids/abstract_sha) refuses a genuinely drifted ref, stamps nothing",
      (_n, _err, "summary_check" in _t2S_old[0]),
      (0, ["T3: manifest predates --prepare binding; re-run --prepare"], False))

# ...and refuses every OTHER ref in the same old-format manifest too, not just the drifted one
_t2oldman2 = {"refs": ["T4"], "sha": {"T4": common.summary_sha("Unrelated summary.")}, "no_abstract": ["T5"]}
_n, _err = summary_audit.ingest(
    [{"ref": "T4", "summary": "Unrelated summary."}, {"ref": "T5", "summary": "Another one."}], "ref",
    [{"ref": "T4", "verdict": "supported"}], {}, _t2oldman2, "2026-09-26")
check("an old-format manifest refuses every ref it lists, unchanged or not",
      (_n, sorted(_err)),
      (0, ["T4: manifest predates --prepare binding; re-run --prepare",
           "T5: manifest predates --prepare binding; re-run --prepare"]))

# handcheck: a hand-check-input entry written before apa_sha existed cannot prove
# what the hand-check agent saw; the apa was also genuinely edited since.
_t2oldhc = [{"ref": "H3", "apa": "Old apa text."}]                # no apa_sha: pre-binding input
_t2rows_h3 = [{"ref": "H3", "apa": "Old apa text. (edited since the old --prepare)"}]
_n, _err = handcheck.ingest(_t2rows_h3, "ref",
                            [{"ref": "H3", "verdict": "confirmed", "source_checked": "LoC record"}],
                            _t2oldhc, "2026-09-26")
check("an old-format hand-check-input entry (no apa_sha) is refused explicitly, stamps nothing",
      (_n, _err, "hand_verified" in _t2rows_h3[0]),
      (0, ["H3: hand-check input predates --prepare binding; re-run --prepare"], False))

# ---- Task 3: verify's title check without one-way containment (2026-09-26) -
# title_score's one-way containment let a short claim ("Deep learning") match a
# longer, unrelated record title ("Deep learning in neural networks: An
# overview") because it only checked the short title's words against the long
# one. title_agrees requires two-way agreement instead, except when one title
# is exactly the other's main title (a dropped subtitle).
check_true("title_agrees: a short claim contained in an unrelated longer title is NOT an agreement",
           common.title_agrees("Deep learning",
                                "Deep learning in neural networks: An overview") < 0.5)
check_true("title_agrees: a dropped subtitle still agrees",
           common.title_agrees("The free-energy principle",
                                "The free-energy principle: A unified brain theory?") == 1.0)
check_true("title_agrees: dropping a subtitle agrees in the other direction too",
           common.title_agrees("The free-energy principle: A unified brain theory?",
                                "The free-energy principle") == 1.0)
check_true("title_agrees: case/punctuation differences agree",
           common.title_agrees("Sparse coding in visual cortex",
                                "Sparse Coding in Visual Cortex.") == 1.0)
check("title_agrees: a missing title returns None", common.title_agrees("", "Deep learning"), None)
check("verify._title_issue: the containment case is now a title mismatch",
      len(verify._title_issue({"title": "Deep learning"},
                               {"title": "Deep learning in neural networks: An overview"})), 1)
check("verify._title_issue: a dropped subtitle raises no issue",
      verify._title_issue({"title": "The free-energy principle"},
                           {"title": "The free-energy principle: A unified brain theory?"}), [])

# ---- Task 3 fix round 1: the main-title shortcut needs >=3 content words
# (2026-09-25) ------------------------------------------------------------
# Review found: the shortcut returned 1.0 for a short claim against an
# UNRELATED record whose title starts with the same words before a subtitle
# break -- "Deep learning" wholly matches the main title of "Deep learning -
# a survey of unrelated gardening techniques" even though the two papers have
# nothing to do with each other. A main title of only 1-2 content words is too
# easily coincidental, so the shortcut now requires >= 3 content words
# (_TITLE_STOP words excluded) in the main title that triggers it; anything
# shorter falls back to the two-way score.
check_true("title_agrees: a short main title before ' - ' does not shortcut an unrelated record",
           common.title_agrees("Deep learning",
                                "Deep learning - a survey of unrelated gardening techniques") < 0.5)
check_true("title_agrees: a short main title before ':' does not shortcut an unrelated record",
           common.title_agrees("Neural networks",
                                "Neural networks: a completely unrelated history of jazz music") < 0.5)
check_true("title_agrees: a short main title before a standalone '?' does not shortcut either",
           common.title_agrees("Deep learning",
                                "Deep learning? A completely unrelated survey of gardening "
                                "techniques") < 0.5)
check_true("title_agrees: a long-enough main title before a standalone '?' still shortcuts "
           "(a dropped subtitle, not a coincidence)",
           common.title_agrees("Is deep learning working",
                                "Is deep learning working? A survey of failure modes in "
                                "modern AI") == 1.0)
check_true("title_agrees: a long-enough main title before ' - ' still shortcuts",
           common.title_agrees("Attention is all you need",
                                "Attention is all you need - a walkthrough of the "
                                "transformer architecture") == 1.0)
# "free-energy" tokenizes as two content words ("free", "energy"), not one --
# _title_words turns the hyphen into a space like any other non-alnum
# character -- so "The free-energy principle" still has 3 content words
# (free, energy, principle) after "the" is dropped as a stop word, and the
# dropped-subtitle case from the first Task 3 section keeps agreeing.
check_true("title_agrees: a hyphenated main title still counts each half as its own content word",
           common.title_agrees("The free-energy principle",
                                "The free-energy principle: A unified brain theory?") == 1.0)

# ---- Task 4 item 1: sentence_case.py and families.py write through save_rows
# (2026-09-26) -----------------------------------------------------------
# Both tools load rows.json, do their work, then write it straight back with
# common.dump_json -- bypassing the concurrent-write guard every other
# load-then-write tool goes through (common.save_rows). A handcheck --ingest
# or verify run landing in between would silently lose one of the two writes.
_t4d = _tmpf.mkdtemp()
_t4rp = os.path.join(_t4d, "rows.json")
common.dump_json([{"ref": "A", "apa": "Doe, J. (2020). A TITLE HERE and more words. Journal."}], _t4rp)
_e = _i10_run(sc, ["sentence_case.py", "--rows", _t4rp, "--apply"],
              split_apa=lambda apa: (_i10_touch(_t4rp), None)[1])
check_true("sentence_case --apply refuses a rows.json that changed since load",
           isinstance(_e, RuntimeError) and "changed since it was loaded" in str(_e), repr(_e))

# Task 5 addendum (Task 4 review): --apply --out <other file> writes THAT file
# and leaves --rows untouched (no concurrent-write guard needed on it either --
# nothing else is writing to a file this run never touches).
_t4od = _tmpf.mkdtemp()
_t4orp = os.path.join(_t4od, "rows.json")
_t4oout = os.path.join(_t4od, "other.json")
_t4orows = [{"ref": "A", "apa": "Doe, J. (2020). A Study Of Cognitive Behavior. Journal."}]
common.dump_json(_t4orows, _t4orp)
_argv = sys.argv
sys.argv = ["sentence_case.py", "--rows", _t4orp, "--apply", "--out", _t4oout]
try:
    with _sleeps(), _ctx.redirect_stdout(io.StringIO()), _ctx.redirect_stderr(io.StringIO()):
        sc.main()
except SystemExit:
    pass
finally:
    sys.argv = _argv
check("sentence_case --apply --out leaves --rows untouched", common.load_json(_t4orp), _t4orows)
check("sentence_case --apply --out writes the changed title to the other file",
      common.load_json(_t4oout)[0]["apa"], "Doe, J. (2020). A study of cognitive behavior. Journal.")

_t4frp = os.path.join(_t4d, "families_rows.json")
common.dump_json([{"ref": "F1", "apa": "Doe, J. (2020). Title. J."}], _t4frp)
_t4assign = os.path.join(_t4d, "assign.json")
common.dump_json({"principle": "p", "families": [{"key": "a", "name": "A"}, {"key": "b", "name": "B"}],
                  "assignments": {"F1": "a"}}, _t4assign)
_t4_orig_load_json = common.load_json


def _t4_load_json(path):
    if path == _t4assign:
        _i10_touch(_t4frp)          # another writer lands while families.py runs
    return _t4_orig_load_json(path)


_argv = sys.argv
sys.argv = ["families.py", "--rows", _t4frp, "--assign", _t4assign,
            "--out", os.path.join(_t4d, "families.json"), "--md", os.path.join(_t4d, "families.md")]
_t4err = None
try:
    with _patched(common, load_json=_t4_load_json), _ctx.redirect_stdout(io.StringIO()), \
            _ctx.redirect_stderr(io.StringIO()):
        families.main()
except RuntimeError as e:
    _t4err = e
except SystemExit:
    pass
finally:
    sys.argv = _argv
check_true("families.py refuses a rows.json that changed since load",
           isinstance(_t4err, RuntimeError) and "changed since it was loaded" in str(_t4err), repr(_t4err))
check("...and leaves it as the other writer left it",
      common.load_json(_t4frp), [{"ref": "F1", "apa": "Doe, J. (2020). Title. J."}])

# common.write_run_sidecar: the <out>.run.json snippet shared by xref.py and
# forward.py (Task 5 addendum, Task 4 review), so the two copies cannot drift.
_wrs_d = _tmpf.mkdtemp()
_wrs_out = os.path.join(_wrs_d, "x.json")
common.write_run_sidecar(_wrs_out, ["A", "B"], "2026-09-26")
check("write_run_sidecar records the incomplete refs, complete=False, and the date",
      common.load_json(f"{_wrs_out}.run.json"),
      {"complete": False, "incomplete": ["A", "B"], "at": "2026-09-26"})
common.write_run_sidecar(_wrs_out, [], "2026-09-26")
check("write_run_sidecar records complete=True when nothing is incomplete",
      common.load_json(f"{_wrs_out}.run.json")["complete"], True)

# fix round 1: xref.py used indent=1 for its sidecar before the shared function
# existed; the refactor must not silently change it to the default indent=2.
common.write_run_sidecar(_wrs_out, ["A"], "2026-09-26", indent=1)
with open(f"{_wrs_out}.run.json", encoding="utf-8") as _wrs_fh:
    _wrs_text = _wrs_fh.read()
check("write_run_sidecar honors an indent parameter (xref.py's original indent=1)",
      _wrs_text, json.dumps({"complete": False, "incomplete": ["A"], "at": "2026-09-26"},
                            indent=1, ensure_ascii=False))

# ---- Task 4 item 2: an incomplete xref/forward run is not recorded as complete
# (2026-09-26) -------------------------------------------------------------
# xref.py and forward.py write a <out>.run.json sidecar recording whether the
# run finished; candidates.py --add reads it and stamps _runs[source].complete
# so the ledger, and the audit, can tell a partial run from a full one.
_t4xd = _tmpf.mkdtemp()
_t4xrp = os.path.join(_t4xd, "rows.json")
common.dump_json([{"ref": "Z1", "doi": "10.1/z1"}, {"ref": "Z2", "doi": "10.1/z2"}], _t4xrp)
_t4xout = os.path.join(_t4xd, "x.json")


def _t4x_run(incomplete, *extra):
    argv = sys.argv
    sys.argv = ["xref.py", "--rows", _t4xrp, "--out", _t4xout, "--email", "t@example.org", *extra]
    try:
        with _patched(xref, fetch_all=lambda papers, sleep=0.4, retry_wait=60.0:
                       ({"Z1": [], "Z2": []}, incomplete)), \
                _ctx.redirect_stdout(io.StringIO()), _ctx.redirect_stderr(io.StringIO()):
            xref.main()
    except SystemExit:
        pass
    finally:
        sys.argv = argv


_t4x_run(["Z2"], "--allow-incomplete")
_t4xrun = common.load_json(f"{_t4xout}.run.json")
check("xref.py records an incomplete run in <out>.run.json",
      (_t4xrun["complete"], _t4xrun["incomplete"]), (False, ["Z2"]))
check_true("...and stamps a date", bool(_t4xrun.get("at")), _t4xrun)

_t4x_run([])
_t4xrun = common.load_json(f"{_t4xout}.run.json")
check("xref.py records a complete run", (_t4xrun["complete"], _t4xrun["incomplete"]), (True, []))

_t4fd = _tmpf.mkdtemp()
_t4frp3 = os.path.join(_t4fd, "rows.json")
common.dump_json([{"ref": "A", "doi": "10.1/a", "cite_openalex": 5}], _t4frp3)


def _t4f_run(citing_fn, *extra):
    argv = sys.argv
    sys.argv = ["forward.py", "--rows", _t4frp3, "--email", "t@example.org", *extra]
    try:
        with _patched(forward, openalex_ids=lambda dois, email: {"10.1/a": "W1"}, citing=citing_fn), \
                _sleeps(), _ctx.redirect_stdout(io.StringIO()), _ctx.redirect_stderr(io.StringIO()):
            forward.main()
    except SystemExit:
        pass
    finally:
        sys.argv = argv


def _t4f_boom(wid, per, email):
    raise urllib.error.URLError("down")


_t4f_run(_t4f_boom, "--allow-incomplete")
_t4frun = common.load_json(os.path.join(_t4fd, "forward_candidates.json.run.json"))
check("forward.py records an incomplete run in <out>.run.json",
      (_t4frun["complete"], _t4frun["incomplete"]), (False, ["A"]))

_t4f_run(lambda wid, per, email: [])
_t4frun = common.load_json(os.path.join(_t4fd, "forward_candidates.json.run.json"))
check("forward.py records a complete run", (_t4frun["complete"], _t4frun["incomplete"]), (True, []))

# candidates.py --add reads FILE.run.json beside the file it's adding
_t4ed = _tmpf.mkdtemp()
_t4erp = os.path.join(_t4ed, "rows.json")
common.dump_json([{"ref": "R1", "doi": "10.1/r1"}], _t4erp)
_t4eadd = os.path.join(_t4ed, "xref.json")
common.dump_json([{"doi": "10.9/e", "n_citations": 4}], _t4eadd)
common.dump_json({"complete": False, "incomplete": ["R2"], "at": "2026-09-26"}, f"{_t4eadd}.run.json")


def _t4e_add(rp, add_path, source):
    argv = sys.argv
    sys.argv = ["candidates.py", "--rows", rp, "--add", add_path, "--source", source]
    try:
        with _ctx.redirect_stdout(io.StringIO()), _ctx.redirect_stderr(io.StringIO()):
            candidates.main()
    except SystemExit:
        pass
    finally:
        sys.argv = argv


_t4e_add(_t4erp, _t4eadd, "xref")
check("candidates --add reads the FILE.run.json sidecar and records complete=False",
      common.load_json(os.path.join(_t4ed, "candidates.json"))["_runs"]["xref"]["complete"], False)

# no sidecar at all -> also complete False (a missing sidecar is not proof the run finished)
_t4gd = _tmpf.mkdtemp()
_t4grp = os.path.join(_t4gd, "rows.json")
common.dump_json([{"ref": "R1", "doi": "10.1/r1"}], _t4grp)
_t4gadd = os.path.join(_t4gd, "forward_candidates.json")
common.dump_json([], _t4gadd)
_t4e_add(_t4grp, _t4gadd, "forward")
check("candidates --add with no sidecar records complete=False",
      common.load_json(os.path.join(_t4gd, "candidates.json"))["_runs"]["forward"]["complete"], False)

common.dump_json({"complete": True, "incomplete": [], "at": "2026-09-26"}, f"{_t4gadd}.run.json")
_t4e_add(_t4grp, _t4gadd, "forward")
check("candidates --add with a complete sidecar records complete=True",
      common.load_json(os.path.join(_t4gd, "candidates.json"))["_runs"]["forward"]["complete"], True)

# the audit distinguishes an incomplete run from no run at all, and it's ack-able
# like the rest of the ledger warnings
_t4rledger = {"_runs": {"xref": {"at": "d", "n": 1, "complete": False},
                        "forward": {"at": "d", "n": 1, "complete": True}}}
_rep = references.audit_rows([_grow()], "ref", ledger=_t4rledger)
check("an incomplete xref run warns incomplete-xref-run, not no-xref-run",
      [w for w, _ in _rep["unacked"].get("*", [])], ["incomplete-xref-run"])
check("...and fails the audit until acknowledged", _rep["failed"], True)
_rep = references.audit_rows([_grow()], "ref", ledger=_t4rledger,
                             acks={"*": {"incomplete-xref-run": "small corpus, ran once by hand"}})
check("incomplete-xref-run is ack-able like the other ledger warnings", _rep["failed"], False)

# ---- Task 4 item 3: re-verifying a canonical row keeps an independent OK stamp
# (2026-09-26) -------------------------------------------------------------
# A lab-style row's `apa` predates canon (e.g. built from an OpenAlex record by
# hand, not by references.py from this same DOI); its first verify pass checks
# that apa against the DOI's real record with no claim_basis -- an independent
# check. If the row is later canonicalized (apa rebuilt from THIS SAME DOI) and
# re-verified, rows_to_citations now reports claim_basis "canonical-apa" for it
# (nothing left to check the DOI against but itself), which would otherwise
# silently downgrade the earlier independent OK into a circular one and start
# nagging "identity-not-reestablished" on lab corpora that were already confirmed.
_i3row = {"ref": "U3", "doi": "10.1/u3",
         "apa": "Amodei, D., & Olah, C. (2016). Concrete problems in AI safety. arXiv."}
verify.stamp_rows([_i3row], [{"label": "U3", "verdict": "OK", "source": "doi", "issues": []}],
                  "ref", "2026-08-01")
check("first pass: independently verified, no claim_basis",
      (_i3row["verified"]["verdict"], "claim_basis" in _i3row["verified"]), ("OK", False))

_i3row["canonical_at"] = "2026-09-26"           # canonicalized afterward; apa unchanged
_i3c = verify.rows_to_citations([_i3row])[0]
check("re-verifying after canon now has claim_basis canonical-apa",
      _i3c.get("claim_basis"), "canonical-apa")
verify.stamp_rows([_i3row], [{"label": "U3", "verdict": "OK", "source": "doi", "issues": [],
                              "claim_basis": "canonical-apa"}], "ref", "2026-09-26")
check("re-verify keeps the earlier independent stamp (no claim_basis) and records reverified_at",
      (_i3row["verified"].get("claim_basis"), _i3row["verified"].get("at"),
       _i3row["verified"].get("reverified_at")),
      (None, "2026-08-01", "2026-09-26"))
check("the audit does not warn identity-not-reestablished for the kept stamp",
      references.audit_rows([_i3row], "ref")["unacked"].get("U3", []), [])

# ...but the kept-stamp rule lapses when the row's ids changed since the earlier stamp
_i3row2 = {"ref": "U4", "doi": "10.1/u4",
          "apa": "Smith, J. (2018). Some other paper. arXiv.", "canonical_at": "2026-08-01",
          "verified": {"verdict": "OK", "doi": "10.1/u4-old", "arxiv": "", "source": "doi",
                       "issues": [], "at": "2026-08-01"}}
verify.stamp_rows([_i3row2], [{"label": "U4", "verdict": "OK", "source": "doi", "issues": [],
                               "claim_basis": "canonical-apa"}], "ref", "2026-09-26")
check("a changed DOI since the earlier stamp is not kept: it is overwritten with the new claim_basis",
      (_i3row2["verified"]["doi"], _i3row2["verified"].get("claim_basis"), "reverified_at" in _i3row2["verified"]),
      ("10.1/u4", "canonical-apa", False))

# ---- final review C1: DataCite creators with no givenName (2026-09-26) -----
# DataCite often deposits a person as a bare display name ("Jagroop Singh Doad",
# nameType Personal, no givenName); kept whole it shipped given-name-first.
def _c1_people(creators):
    rec = common.datacite_record(_dc_attrs(creators=creators))
    return rec["people"], rec["unsplit"]


check("C1: a Personal display name with no givenName is split on its last token",
      _c1_people([{"name": "Jagroop Singh Doad", "nameType": "Personal"}]), (["Doad, J. S."], []))
check("C1: a 'Family, Given' name with no givenName is split on the first ', '",
      _c1_people([{"name": "Doe, John"}]), (["Doe, J."], []))
check("C1: 'Family, Given' also splits for a Personal name",
      _c1_people([{"name": "Doe, John", "nameType": "Personal"}]), (["Doe, J."], []))
check("C1: a Personal display name keeps its nobiliary particle with the surname",
      _c1_people([{"name": "Ludwig van Beethoven", "nameType": "Personal"}]),
      (["van Beethoven, L."], []))
check("C1: a Personal name starting with 'The' is a group: kept whole and recorded unsplit",
      _c1_people([{"name": "The pandas development team", "nameType": "Personal",
                   "familyName": "The pandas development team"}]),
      (["The pandas development team"], ["The pandas development team"]))
check("C1: an Organizational name is kept whole (it is declared a group, so not flagged)",
      _c1_people([{"name": "Allen Institute for Brain Science, Seattle", "nameType": "Organizational"}]),
      (["Allen Institute for Brain Science, Seattle"], []))
check("C1: a multi-token name with no nameType is kept whole and recorded unsplit",
      _c1_people([{"name": "Jagroop Singh Doad"}]), (["Jagroop Singh Doad"], ["Jagroop Singh Doad"]))
check("C1: a givenName still wins (unchanged)",
      _c1_people([{"name": "Doad, Jagroop Singh", "familyName": "Doad", "givenName": "Jagroop Singh",
                   "nameType": "Personal"}]), (["Doad, J. S."], []))

_c1_doad = dict(common.datacite_record(_dc_attrs(creators=[{"name": "Jagroop Singh Doad",
                                                              "nameType": "Personal"}])))
with _patched(common, crossref_work=_cr_404, datacite_work=lambda d, fv="": dict(_c1_doad)):
    _c1_res = references.canonical(_dc_row("C1D"))
check("C1: canonical apa of a split display name",
      _c1_res["apa"], "Doad, J. S. (2020). pandas-dev/pandas: Pandas (Version v1.0.0) "
      "[Computer software]. Zenodo.")
check("C1: the split name's canonical apa passes references.audit", references.audit(_c1_res["apa"], True)[0], [])
check_true("C1: a fully split record carries no warn list", not _c1_res.get("warn"), str(_c1_res))

with _patched(common, crossref_work=_cr_404, datacite_work=lambda d, fv="": dict(_dc_rec)):
    _c1_dc = references.datacite("10.5281/zenodo.3509134")
    _c1_grp = references.canonical(_dc_row("C1G"))
check("C1: references.datacite still returns the apa of an unsplit group",
      _c1_dc["apa"], "The pandas development team (2020). pandas-dev/pandas: Pandas (Version v1.0.0) "
      "[Computer software]. Zenodo.")
check("C1: ...and marks it warn datacite-unsplit-author:<name>",
      _c1_dc["warn"], ["datacite-unsplit-author:The pandas development team"])
check("C1: canonical passes the warn list through", _c1_grp.get("warn"), _c1_dc["warn"])
check("C1: the group's canonical apa passes references.audit", references.audit(_c1_grp["apa"], True)[0], [])

_c1_row = _dc_row("C1R")
with _patched(common, crossref_work=_cr_404, datacite_work=lambda d, fv="": dict(_dc_rec)), _sleeps():
    references.canon_rows([_c1_row], "ref", "2026-09-26", sleep=0, retry_wait=0)
check("C1: canon_rows stores the warning on the row as canon_warnings",
      [w["id"] for w in _c1_row.get("canon_warnings", [])],
      ["datacite-unsplit-author:The pandas development team"])
_c1_aud = references.audit_rows([_c1_row], "ref")
check("C1: the audit emits it as an unacknowledged warning that fails the gate",
      ([w for w, _ in _c1_aud["unacked"].get("C1R", [])], _c1_aud["failed"], _c1_aud["defects"]),
      (["datacite-unsplit-author:The pandas development team"], True, {}))
_c1_ack = references.audit_rows([_c1_row], "ref", acks={"C1R": {
    "datacite-unsplit-author:The pandas development team": "a development team, not a person"}})
check("C1: an acknowledgment clears it", (_c1_ack["unacked"], _c1_ack["failed"]), ({}, False))
_c1_ungated = {k: v for k, v in _c1_row.items() if k not in ("verified", "canonical_at")}
check_true("C1: an ungated table does not emit canon warnings",
           not any(w.startswith("datacite-") for w, _ in
                   references.audit_rows([_c1_ungated], "ref")["warnings"].get("C1R", [])))
with _patched(common, crossref_work=_cr_404, datacite_work=lambda d, fv="": dict(_c1_doad)), _sleeps():
    references.canon_rows([_c1_row], "ref", "2026-09-27", sleep=0, retry_wait=0)
check_true("C1: a later rebuild with no warnings clears canon_warnings", "canon_warnings" not in _c1_row,
           str(_c1_row))

# ---- final review I1: "(Version ...) [Descriptor]" is not part of the title (2026-09-26) ----
_i1s_apa = "Smith, A. (2021). Spike sorter (Version v2.1) [Computer software]. Zenodo."
_i1s_p = common.parse_apa(_i1s_apa)
check("I1: parse_apa leaves '(Version ...) [Descriptor]' out of the title",
      (_i1s_p["title"], _i1s_p["descriptor"], _i1s_p["rest"]),
      ("Spike sorter", " (Version v2.1) [Computer software]",
       " (Version v2.1) [Computer software]. Zenodo."))
check("I1: parse_apa still reassembles the original",
      _i1s_p["head"] + _i1s_p["title"] + _i1s_p["terminal"] + _i1s_p["rest"], _i1s_apa)
check("I1: a bracket descriptor alone is split off too",
      common.parse_apa("Smith, J. (2021). A dataset [Data set]. Dryad.")["title"], "A dataset")
check("I1: a version alone is split off too",
      common.parse_apa("Smith, J. (2021). A tool (Version 3). Zenodo.")["title"], "A tool")
check("I1: an ordinary title has an empty descriptor",
      common.parse_apa("Yang, W. (2025a). A Title. Venue, 1.")["descriptor"], "")
check("I1: a descriptor with no publisher after it is still an empty venue",
      "empty venue" in references.audit("Smith, J. (2021). A dataset [Data set].", True)[0], True)
check("I1: sentence_case.split_apa returns the title without the descriptor",
      sc.split_apa(_i1s_apa), ("Smith, A. (2021). ", "Spike sorter",
                               " (Version v2.1) [Computer software]. Zenodo."))

# Round trip: DataCite software row -> verify (claim) OK -> canon -> re-verify
# (canonical-apa path) OK -> sentence_case leaves the descriptor untouched.
_i1s_rec = dict(common.datacite_record(_dc_attrs(
    creators=[{"familyName": "Smith", "givenName": "Alice", "nameType": "Personal"}],
    titles=[{"title": "Spike sorter"}], version="v2.1", publicationYear=2021)))
_i1s_row = {"ref": "I1S", "doi": "10.5281/zenodo.555", "search_author": "Smith",
            "search_year": "2021", "search_title": "Spike sorter", "built_at": "2026-09-26"}
with _patched(common, crossref_work=_cr_404, datacite_work=lambda d, fv="": dict(_i1s_rec)), _sleeps():
    _i1s_v1 = verify.verify_one(verify.rows_to_citations([_i1s_row], "ref")[0])
    verify.stamp_rows([_i1s_row], [dict(_i1s_v1, label="I1S")], "ref", "2026-09-26")
    references.canon_rows([_i1s_row], "ref", "2026-09-26", sleep=0, retry_wait=0)
    _i1s_bare = {k: v for k, v in _i1s_row.items() if not k.startswith("search_")}
    _i1s_c2 = verify.rows_to_citations([_i1s_bare], "ref")[0]
    _i1s_v2 = verify.verify_one(dict(_i1s_c2))
check("I1 round trip: the claim verifies OK", _i1s_v1["verdict"], "OK")
check("I1 round trip: canon builds the software apa", _i1s_row["apa"], _i1s_apa)
check("I1 round trip: re-verify on the canonical-apa path is OK",
      (_i1s_c2.get("claim_basis"), _i1s_c2["title"], _i1s_v2["verdict"]),
      ("canonical-apa", "Spike sorter", "OK"))
_i1s_h, _i1s_t, _i1s_r = sc.split_apa(_i1s_row["apa"])
check("I1 round trip: sentence_case leaves '(Version v2.1) [Computer software]' untouched",
      _i1s_h + sc.sentence_case(_i1s_t, set(sc.PROPER), []) + _i1s_r, _i1s_apa)

# ---- final review I2: a stale hand-check result cannot be ingested after a re-prepare (2026-09-26) ----
# The reviewer's repro: --prepare, edit the apa, --prepare again, then --ingest
# the SAME old result. The row now matches the NEW input's apa_sha, so only the
# result's own echo of the apa_sha it was checked against can catch it.
_i2book = {"ref": "HS", "apa": "Kuhn, T. S. (1962). The structure of scientific revolutions. U Chicago Press.",
           "summary": ""}
_i2_old_in = handcheck.prepare([dict(_i2book)], "ref", (_far,))[1]
_i2_old_res = [{"ref": "HS", "verdict": "confirmed", "source_checked": "LoC record",
                "apa_sha": _i2_old_in[0]["apa_sha"]}]
_i2_rows = [dict(_i2book, apa=_i2book["apa"].replace("1962", "1970"))]   # edited, then re-prepared
_i2_new_in = handcheck.prepare(_i2_rows, "ref", (_far,))[1]
_n, _err = handcheck.ingest(_i2_rows, "ref", _i2_old_res, _i2_new_in, "2026-09-26")
check("I2: an old result ingested after a re-prepare is refused, stamps nothing",
      (_n, _err, "hand_verified" in _i2_rows[0]),
      (0, ["HS: result was for a different version of the reference; re-check it"], False))
_n, _err = handcheck.ingest(_i2_rows, "ref", [{k: v for k, v in _i2_old_res[0].items() if k != "apa_sha"}],
                            _i2_new_in, "2026-09-26")
check("I2: a result that does not echo apa_sha is refused",
      (_n, _err, "hand_verified" in _i2_rows[0]),
      (0, ["HS: result does not echo the prepared apa_sha; re-check it"], False))
_n, _err = handcheck.ingest(_i2_rows, "ref", [dict(_i2_old_res[0], apa_sha=_i2_new_in[0]["apa_sha"])],
                            _i2_new_in, "2026-09-26")
check("I2: a result echoing the current apa_sha is stamped",
      (_n, _err, _i2_rows[0].get("hand_verified", {}).get("verdict")), (1, [], "confirmed"))
check_true("I2: the brief tells the agent to copy apa_sha into its result", "apa_sha" in handcheck.BRIEF)

# --prepare moves an existing handcheck_result.json aside (never deletes it)
_i2d = _tmpf.mkdtemp()
_i2rp = os.path.join(_i2d, "rows.json")
common.dump_json([dict(_i2book)], _i2rp)
common.dump_json(_i2_old_res, os.path.join(_i2d, "handcheck_result.json"))
_argv = sys.argv
sys.argv = ["handcheck.py", "--rows", _i2rp, "--prepare", "--email", "t@example.org"]
_i2out = io.StringIO()
try:
    with _patched(handcheck, prepare=lambda rows, keyf: ({}, [])), _ctx.redirect_stdout(_i2out):
        handcheck.main()
finally:
    sys.argv = _argv
_i2stale = [f for f in os.listdir(_i2d) if f.startswith("handcheck_result.stale-") and f.endswith(".json")]
check("I2: --prepare renames the old handcheck_result.json to a stale-<timestamp> copy",
      (os.path.exists(os.path.join(_i2d, "handcheck_result.json")), len(_i2stale)), (False, 1))
check("I2: ...keeping its content", common.load_json(os.path.join(_i2d, _i2stale[0])) if _i2stale else None,
      _i2_old_res)
check_true("I2: ...and says so", "stale" in _i2out.getvalue(), _i2out.getvalue())

# ---- final review I3: a repository copy is flagged, not silently canonical (2026-09-26) ----
# A journal article re-deposited on Zenodo (DataCite type Text/JournalArticle)
# verifies and canonicalizes like any DOI; it should cite the version of record.
def _i3_dc(**over):
    rec = dict(common.datacite_record(_dc_attrs(
        creators=[{"familyName": "Smith", "givenName": "Alice", "nameType": "Personal"}], **over)))
    with _patched(common, crossref_work=_cr_404, datacite_work=lambda d, fv="": dict(rec)):
        return references.datacite("10.5281/zenodo.777")


_i3_text = _i3_dc(types={"resourceTypeGeneral": "Text"})
check("I3: a DataCite Text deposit carries a datacite-deposit warning",
      (_i3_text.get("warn"), _i3_text.get("warn_text", {}).get("datacite-deposit")),
      (["datacite-deposit"], "a repository copy (DataCite Text, Zenodo); cite the version of record's "
                             "DOI if one exists"))
check("I3: a JournalArticle deposit is flagged too",
      _i3_dc(types={"resourceTypeGeneral": "JournalArticle"}).get("warn"), ["datacite-deposit"])
check("I3: a Preprint deposit is flagged too",
      _i3_dc(types={"resourceTypeGeneral": "Preprint"}).get("warn"), ["datacite-deposit"])
check("I3: software is not flagged", _i3_dc().get("warn"), None)
check("I3: a data set is not flagged", _i3_dc(types={"resourceTypeGeneral": "Dataset"}).get("warn"), None)
check("I3: software with publisher 'Unpublished' is flagged",
      _i3_dc(publisher="Unpublished").get("warn"), ["datacite-deposit"])

_i3_rec = dict(common.datacite_record(_dc_attrs(
    creators=[{"familyName": "Smith", "givenName": "Alice", "nameType": "Personal"}],
    types={"resourceTypeGeneral": "Text"})))
_i3_row = _dc_row("I3R")
with _patched(common, crossref_work=_cr_404, datacite_work=lambda d, fv="": dict(_i3_rec)), _sleeps():
    references.canon_rows([_i3_row], "ref", "2026-09-26", sleep=0, retry_wait=0)
_i3_aud = references.audit_rows([_i3_row], "ref")
check("I3: canon stores it and the gated audit fails on it unacknowledged",
      ([w for w, _ in _i3_aud["unacked"].get("I3R", [])], _i3_aud["failed"]), (["datacite-deposit"], True))
_i3_ack = references.audit_rows([_i3_row], "ref", acks={"I3R": {"datacite-deposit": "no version of record"}})
check("I3: acknowledging it passes the gate", (_i3_ack["unacked"], _i3_ack["failed"]), ({}, False))

# ---- final review M1: datacite_work's own fetch keeps a curl 404 a 404 (2026-09-26) ----
# The vendored curl_get uses --fail, so through http() a DataCite 404 fetched by
# curl became "curl exit 22" -- an ERROR -- instead of "DOI does not exist".
class _M1Resp:
    def __init__(self, body):
        self.body, self.headers = body, {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


_m1_body = json.dumps({"data": {"attributes": _dc_attrs()}}).encode()


def _m1_urlopen_ok(req, timeout=None):
    return _M1Resp(_m1_body)


def _m1_urlopen_drop(req, timeout=None):
    raise ConnectionResetError("connection reset by peer")


def _m1_urlopen_404(req, timeout=None):
    raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)


_m1_cmds = []


def _m1_curl(code, body=b"{}"):
    def run(cmd, capture_output=True, timeout=None):
        _m1_cmds.append(cmd)
        return _sp.CompletedProcess(cmd, 0, stdout=body + b"\n" + code.encode(), stderr=b"")
    return run


def _m1_fetch(urlopen, run=None):
    pats = {"urlopen": urlopen}
    with _patched(common.urllib.request, **pats), \
            _patched(common.subprocess, run=run or _m1_curl("500")), \
            _patched(common.shutil, which=lambda n: "/usr/bin/curl"), _sleeps():
        try:
            return common.datacite_work("10.5281/zenodo.3509134")
        except Exception as e:
            return e


check("M1: urllib success is parsed (no curl)",
      (_m1_fetch(_m1_urlopen_ok)["title"], len(_m1_cmds)), ("pandas-dev/pandas: Pandas", 0))
_m1_e = _m1_fetch(_m1_urlopen_404)
check("M1: a urllib 404 propagates as HTTPError 404",
      (type(_m1_e).__name__, getattr(_m1_e, "code", None)), ("HTTPError", 404))
_m1_cmds.clear()
_m1_e = _m1_fetch(_m1_urlopen_drop, _m1_curl("404", b'{"errors":[{"status":"404"}]}'))
check("M1: a network failure then a curl 404 raises HTTPError 404 (a clean miss, not ERROR)",
      (type(_m1_e).__name__, getattr(_m1_e, "code", None)), ("HTTPError", 404))
check_true("M1: curl ran WITHOUT --fail and captured the status",
           _m1_cmds and "--fail" not in _m1_cmds[0] and "\n%{http_code}" in _m1_cmds[0], str(_m1_cmds))
check("M1: a network failure then a curl 200 is parsed",
      _m1_fetch(_m1_urlopen_drop, _m1_curl("200", _m1_body))["title"], "pandas-dev/pandas: Pandas")
check_true("M1: a network failure then a curl 503 is still an error, never a 404",
           not (isinstance(_m1_fetch(_m1_urlopen_drop, _m1_curl("503")), urllib.error.HTTPError)
                and _m1_fetch(_m1_urlopen_drop, _m1_curl("503")).code == 404))
check_true("M1: ...and is transient (ERROR)",
           common.is_transient(_m1_fetch(_m1_urlopen_drop, _m1_curl("503"))))
_m1_c = {"label": "M1", "doi": "10.5281/zenodo.nonexistent", "title": "A title nobody has",
         "expect_first_author": "Nobody", "expect_year": "2020"}
with _patched(common, crossref_work=_cr_404), _patched(common.urllib.request, urlopen=_m1_urlopen_drop), \
        _patched(common.subprocess, run=_m1_curl("404")), _patched(common.shutil, which=lambda n: "/x/curl"), \
        _patched(verify, lookup_pubmed_title=lambda t: None), _sleeps():
    _m1_v = verify.verify_one(dict(_m1_c))
    _m1_cn = references.canonical(_dc_row("M1C", "10.5281/zenodo.nonexistent"))
check_true("M1: verify of a DOI missing from both registries (DataCite via curl) is not ERROR",
           _m1_v["verdict"] != "ERROR", str(_m1_v))
check("M1: canonical says 'DOI does not exist'", _m1_cn, {"error": "DOI does not exist (404)", "source": "missing"})

# ---- final review M2: the run sidecar names its tool and paper count (2026-09-26) ----
# A forward sidecar added as --source xref (or an xref run over an older, smaller
# table) was recorded as a full run of the other pass.
_m2d = _tmpf.mkdtemp()
_m2out = os.path.join(_m2d, "x.json")
common.write_run_sidecar(_m2out, [], "2026-09-26", tool="xref", n_papers=3)
check("M2: write_run_sidecar records tool and n_papers",
      common.load_json(f"{_m2out}.run.json"),
      {"complete": True, "incomplete": [], "at": "2026-09-26", "tool": "xref", "n_papers": 3})
_t4x_run([])
check("M2: xref.py's sidecar names the tool and the papers it read",
      {k: common.load_json(f"{_t4xout}.run.json").get(k) for k in ("tool", "n_papers")},
      {"tool": "xref", "n_papers": 2})
_t4f_run(lambda wid, per, email: [])
check("M2: forward.py's sidecar names the tool and the papers it read",
      {k: common.load_json(os.path.join(_t4fd, "forward_candidates.json.run.json")).get(k)
       for k in ("tool", "n_papers")}, {"tool": "forward", "n_papers": 1})

check_true("M2: run_record refuses a sidecar from the other tool",
           _raises(lambda: candidates.run_record({"complete": True, "tool": "forward", "n_papers": 1}, "xref")))
check("M2: run_record reads complete and n_papers",
      candidates.run_record({"complete": True, "tool": "xref", "n_papers": 4}, "xref"), (True, 4))
check("M2: a missing sidecar is an incomplete run of unknown size", candidates.run_record(None, "xref"),
      (False, None))

_m2rp = os.path.join(_m2d, "rows.json")
common.dump_json([{"ref": "R1", "doi": "10.1/r1"}, {"ref": "R2", "doi": "10.1/r2"}], _m2rp)
_m2add = os.path.join(_m2d, "forward_candidates.json")
common.dump_json([{"doi": "10.9/f", "shared": 3}], _m2add)
common.dump_json({"complete": True, "incomplete": [], "at": "2026-09-26", "tool": "forward", "n_papers": 1},
                 f"{_m2add}.run.json")
_t4e_add(_m2rp, _m2add, "xref")
check("M2: candidates --add refuses --source xref for a forward sidecar (nothing written)",
      os.path.exists(os.path.join(_m2d, "candidates.json")), False)
_t4e_add(_m2rp, _m2add, "forward")
check("M2: candidates --add records n_papers under _runs[source]",
      common.load_json(os.path.join(_m2d, "candidates.json"))["_runs"]["forward"].get("n_papers"), 1)

_m2rows = [_grow("P1", "10.1/p1"), dict(_grow("P2", "10.1/p2"),
                                         apa="Jones, K. (2019). Another study entirely. Neuron, 2, 3-4.")]
_m2L = {"_runs": {"xref": {"at": "d", "n": 1, "complete": True, "n_papers": 2},
                  "forward": {"at": "d", "n": 1, "complete": True, "n_papers": 1}}}
_rep = references.audit_rows(_m2rows, "ref", ledger=_m2L)
check("M2: a run over fewer papers than the table's sourced rows warns partial-<source>-run",
      [w for w, _ in _rep["unacked"].get("*", [])], ["partial-forward-run"])
check("M2: ...and fails the audit until acknowledged", _rep["failed"], True)
_rep = references.audit_rows(_m2rows, "ref", ledger=_m2L,
                             acks={"*": {"partial-forward-run": "the added row is a data set"}})
check("M2: partial-forward-run is ack-able", _rep["failed"], False)
_m2L["_runs"]["forward"]["n_papers"] = 2
check("M2: a run over every sourced row does not warn",
      references.audit_rows(_m2rows, "ref", ledger=_m2L)["unacked"].get("*", []), [])

# ---- final review M3: a non-object candidates.json is refused by spreadsheet (2026-09-26) ----
# Only a dict ledger was validated; a `[]` ledger skipped validation, reached the
# audit as "not LEDGER_MISSING", and a legacy table (or --draft) was written.
for _m3extra in ((), ("--draft",)):
    _m3d = _tmpf.mkdtemp()
    _m3rp = os.path.join(_m3d, "rows.json")
    common.dump_json(_undated, _m3rp)
    common.dump_json([], os.path.join(_m3d, "candidates.json"))
    _argv = sys.argv
    sys.argv = ["spreadsheet.py", "--rows", _m3rp, "--out", os.path.join(_m3d, "bib.xlsx"), *_m3extra]
    _m3err, _m3code = io.StringIO(), 0
    try:
        with _ctx.redirect_stderr(_m3err), _ctx.redirect_stdout(io.StringIO()):
            spreadsheet.main()
    except SystemExit as e:
        _m3code = e.code or 0
    finally:
        sys.argv = _argv
    check(f"M3: spreadsheet {' '.join(_m3extra)} refuses a [] ledger: exit 1, nothing written",
          (_m3code, sorted(f for f in os.listdir(_m3d) if f.endswith(".xlsx"))), (1, []))
    check_true("M3: ...naming the ledger's shape", "not a JSON object" in _m3err.getvalue(), _m3err.getvalue())

# ---- final review M4: _runs values and sidecars must be objects (2026-09-26) ----
check_true("M4: validate_ledger refuses a non-dict _runs value",
           _raises(lambda: candidates.validate_ledger({"_runs": {"xref": True}})))
try:
    candidates.validate_ledger({"_runs": {"xref": ["complete"]}})
    _m4msg = ""
except ValueError as e:
    _m4msg = str(e)
check_true("M4: ...naming the source", "_runs" in _m4msg and "xref" in _m4msg, _m4msg)
candidates.validate_ledger({"_runs": {"xref": {"complete": True}}})    # a dict value still passes
check_true("M4: run_record refuses a non-dict sidecar", _raises(lambda: candidates.run_record([True], "xref")))
_m4d = _tmpf.mkdtemp()
_m4rp = os.path.join(_m4d, "rows.json")
common.dump_json([{"ref": "R1", "doi": "10.1/r1"}], _m4rp)
_m4add = os.path.join(_m4d, "xref.json")
common.dump_json([{"doi": "10.9/e", "n_citations": 4}], _m4add)
common.dump_json(["complete"], f"{_m4add}.run.json")
_argv = sys.argv
sys.argv = ["candidates.py", "--rows", _m4rp, "--add", _m4add, "--source", "xref"]
_m4err = io.StringIO()
try:
    with _ctx.redirect_stdout(io.StringIO()), _ctx.redirect_stderr(_m4err):
        candidates.main()
except SystemExit:
    pass
finally:
    sys.argv = _argv
check("M4: candidates --add refuses a non-dict sidecar (no ledger written)",
      os.path.exists(os.path.join(_m4d, "candidates.json")), False)
check_true("M4: ...with a clear message naming the sidecar",
           "run.json" in _m4err.getvalue() and "not a JSON object" in _m4err.getvalue(), _m4err.getvalue())

# ---- final review M5: DataCite main title + Subtitle (2026-09-26) ----------
# titles[0] may be a TranslatedTitle or AlternativeTitle; the main title is the
# one with no titleType, and a Subtitle entry joins it after ": " (as CrossRef's does).
def _m5_title(titles):
    return common.datacite_record(_dc_attrs(titles=titles))["title"]


check("M5: the first title with no titleType is the main title",
      _m5_title([{"title": "Ein Titel", "titleType": "TranslatedTitle"}, {"title": "Spike sorter"}]),
      "Spike sorter")
check("M5: a Subtitle entry is appended after ': '",
      _m5_title([{"title": "Spike sorter"}, {"title": "fast and exact", "titleType": "Subtitle"}]),
      "Spike sorter: Fast and exact")
check("M5: a subtitle already inside the title is not repeated",
      _m5_title([{"title": "Spike sorter: fast and exact"}, {"title": "fast and exact", "titleType": "Subtitle"}]),
      "Spike sorter: fast and exact")
check("M5: with every title typed, titles[0] is used",
      _m5_title([{"title": "Alt one", "titleType": "AlternativeTitle"}, {"title": "Alt two", "titleType": "Other"}]),
      "Alt one")
check("M5: no titles at all is an empty title", _m5_title([]), "")

# ---- final review M6: DataCite is consulted on a CrossRef 404 only (2026-09-26) ----
# verify fell back on ANY non-transient CrossRef error (a 400, a bad body) while
# canon fell back on a 404 only; the two must agree, and anything but a 404
# propagates (verify_all turns it into ERROR; canonical into source "error").
_m6_calls = []


def _m6_dc(d, fv=""):
    _m6_calls.append(d)
    return dict(_dc_rec)


def _m6_cr400(doi, fallback_venue=""):
    raise urllib.error.HTTPError("u", 400, "Bad Request", {}, None)


def _m6_crbad(doi, fallback_venue=""):
    raise ValueError("Expecting value: line 1 column 1 (char 0)")


for _m6_fn, _m6_why in [(_m6_cr400, "HTTPError 400"), (_m6_crbad, "ValueError")]:
    _m6_calls.clear()
    with _patched(common, crossref_work=_m6_fn, datacite_work=_m6_dc):
        _m6_lr = _raises(lambda: verify.lookup_crossref("10.5281/zenodo.3509134"))
        _m6_cn = references.canonical(_dc_row("M6"))
        _m6_v = verify._verify_pass([dict(_dc_c)], 0)[0]
    check(f"M6: a CrossRef {_m6_why} propagates from verify.lookup_crossref without consulting DataCite",
          (_m6_lr, _m6_calls), (True, []))
    check(f"M6: ...verify reports the {_m6_why} as ERROR", _m6_v["verdict"], "ERROR")
    check(f"M6: ...and canonical reports the {_m6_why} as source 'error' without consulting DataCite",
          (_m6_cn["source"], _m6_calls), ("error", []))


def _m6_dcbad(d, fv=""):
    raise ValueError("bad DataCite body")


with _patched(common, crossref_work=_cr_404, datacite_work=_m6_dcbad):
    check_true("M6: a non-404 DataCite failure after a CrossRef 404 propagates (not a clean miss)",
               _raises(lambda: verify.lookup_crossref("10.5281/zenodo.3509134")))

# ---- final review M7: a summary result echoes its batch entry's summary_sha (2026-09-26) ----
# Like handcheck's apa_sha (I2): a result must prove which version of the summary
# it judged, so a result for an older batch cannot stamp the current summary.
_m7S = [{"ref": "M7", "summary": "It found X."}]
_m7AB = {"M7": {"text": "We found X.", "source": "openalex"}}
_m7b, _m7na, _m7man = summary_audit.prepare(_m7S, "ref", _m7AB)
check("M7: prepare writes summary_sha into each batch entry",
      _m7b[0][0].get("summary_sha"), common.summary_sha("It found X."))
check_true("M7: the brief tells the agent to echo summary_sha", "summary_sha" in summary_audit.BRIEF)
_n, _err = summary_audit.ingest([dict(_m7S[0])], "ref", [{"ref": "M7", "verdict": "supported"}], _m7AB, _m7man,
                                "2026-09-26")
check("M7: a result with no summary_sha echo is refused",
      (_n, _err), (0, ["M7: result does not echo the batch's summary_sha; re-check it"]))
_n, _err = summary_audit.ingest([dict(_m7S[0])], "ref",
                                [{"ref": "M7", "verdict": "supported", "summary_sha": common.summary_sha("Old.")}],
                                _m7AB, _m7man, "2026-09-26")
check("M7: a result echoing another summary_sha is refused",
      (_n, _err), (0, ["M7: result was for a different version of the summary; re-check it"]))
_m7ok = [dict(_m7S[0])]
_n, _err = summary_audit.ingest(_m7ok, "ref", [{"ref": "M7", "verdict": "supported",
                                                "summary_sha": _m7b[0][0]["summary_sha"]}],
                                _m7AB, _m7man, "2026-09-26")
check("M7: a result echoing the batch's summary_sha is stamped",
      (_n, _err, _m7ok[0].get("summary_check", {}).get("verdict")), (1, [], "supported"))

# ---- final review M8: first-author check on whole tokens, ignoring an article (2026-09-26) ----
# "the" is a substring of "Matthews", so a group creator "The pandas development
# team" matched any first author containing "the".
def _m8(expect, actual):
    return verify._author_issue({"expect_first_author": expect}, {"first_author": actual})


check_true("M8: a group 'The pandas development team' does not match 'Matthews'",
           _m8("The pandas development team", "Matthews J") != [])
check_true("M8: ...nor the other way round", _m8("Matthews", "The pandas development team") != [])
check("M8: 'Tang' still matches 'Tang J'", _m8("Tang", "Tang J"), [])
check("M8: the group matches itself", _m8("The pandas development team", "The pandas development team"), [])
check("M8: a leading article is ignored on either side", _m8("pandas development team", "The pandas development team"),
      [])
check("M8: a surname token matches inside a particle surname", _m8("Heuvel", "van den Heuvel M"), [])
check("M8: the first part matches a hyphenated surname", _m8("Andrews", "Andrews-Hanna J"), [])
check_true("M8: a short surname no longer matches a longer one containing it", _m8("Lee", "Leeson K") != [])
check_true("M8: an unrelated surname still mismatches", _m8("Smith", "Jones A") != [])

# ---- final review M9: handcheck hashes the text it shows the agent (2026-09-26) ----
# A row with no apa yet is shown its search_apa, but apa_sha hashed the empty
# apa, so an edit to the search_apa between --prepare and --ingest went unseen.
_m9row = {"ref": "M9", "apa": "", "search_apa": "Doe, J. (1970). A memo. Lab.", "summary": ""}
_m9in = handcheck.prepare([dict(_m9row)], "ref", (_far,))[1]
check("M9: --prepare's apa_sha is the hash of the text it shows (search_apa here)",
      (_m9in[0]["apa"], _m9in[0]["apa_sha"]), (_m9row["search_apa"], common.apa_sha(_m9row["search_apa"])))
_m9res = [{"ref": "M9", "verdict": "confirmed", "source_checked": "LoC", "apa_sha": _m9in[0]["apa_sha"]}]
_m9edit = [dict(_m9row, search_apa="Doe, J. (1971). A different memo. Lab.")]
_n, _err = handcheck.ingest(_m9edit, "ref", _m9res, _m9in, "2026-09-26")
check("M9: --ingest refuses a row whose shown search_apa changed since --prepare",
      (_n, _err), (0, ["M9: the reference changed since --prepare; re-check it"]))
_n, _err = handcheck.ingest([dict(_m9row)], "ref", _m9res, _m9in, "2026-09-26")
check("M9: ...and accepts the unchanged row", (_n, _err), (1, []))

# ---- final review C1 (self-review): a comma-split group is still caught (2026-09-26) ----
# "Family, Given" splitting a group name with no nameType ("Allen Institute for
# Brain Science, Seattle") yields a multi-word family name; the audit's
# multi-word-surname warning is the net that asks a human about it.
_c1b = common.datacite_record(_dc_attrs(creators=[{"name": "Allen Institute for Brain Science, Seattle"}]))
_c1b_apa = common.build_datacite_apa(_c1b["people"], "2020", "Atlas", None, "Dataset", "Zenodo")
check_true("C1: a comma-split multi-word family name raises the audit's multi-word-surname warning",
           any("multi-word surname 'Allen Institute for Brain Science'" in n
               for n in references.audit(_c1b_apa, True)[1]), _c1b_apa)

# ---- author fix 3: DataCite never invents a one-letter surname (2026-09-26) ----
# A Personal name deposited family-first with trailing initials ("Doad J S") was
# split on its last token into "S, D. J." and shipped unflagged.
for _a3name in ("Doad J S", "Doad JS", "Doad J. S."):
    check(f"A3: a family-first name with trailing initials ({_a3name!r}) keeps its surname",
          _c1_people([{"name": _a3name, "nameType": "Personal"}]), (["Doad, J. S."], []))
check("A3: a familyName is used as the family, the given name taken from the rest of `name`",
      _c1_people([{"name": "Jagroop Singh Doad", "familyName": "Doad"}]), (["Doad, J. S."], []))
check("A3: ...also when `name` is family-first with a comma",
      _c1_people([{"name": "Doad, Jagroop Singh", "familyName": "Doad", "nameType": "Personal"}]),
      (["Doad, J. S."], []))
check("A3: ...and initials run together in the rest are all kept ('Doad JS')",
      _c1_people([{"name": "Doad JS", "familyName": "Doad"}]), (["Doad, J. S."], []))
check("A3: a last-token split that would leave a one-letter surname keeps the name whole, unsplit",
      _c1_people([{"name": "Jagroop Singh d", "nameType": "Personal"}]),
      (["Jagroop Singh d"], ["Jagroop Singh d"]))
check("A3 (round 1, C): a capital last initial splits words-then-initials, for suspect_surnames to warn",
      _c1_people([{"name": "Jagroop Singh D", "nameType": "Personal"}]), (["Jagroop Singh, D."], []))
_a3notes = references.audit("S, D. J. (2020). T. V.", True)[1]
check("A3: the audit flags a one-letter surname from any source, ack-able by id",
      [references.warning_id(n) for n in _a3notes if "single-letter" in n], ["single-letter-surname:S"])
check("A3: ...for a later author too, and not for initials",
      [references.warning_id(n) for n in references.audit(
          "Smith, J. A., & O, K. (2020). T. V.", True)[1] if "single-letter" in n],
      ["single-letter-surname:O"])
_a3row = {"ref": "A3", "apa": "S, D. J. (2020). T. V.", "doi": "10.1/a3"}
check("A3: audit_rows lists it as an unacknowledged warning...",
      [w for w, _ in references.audit_rows([_a3row], "ref")["unacked"]["A3"]], ["single-letter-surname:S"])
check("A3: ...which an acknowledgment clears",
      references.audit_rows([_a3row], "ref", acks={"A3": {"single-letter-surname:S": "a real surname"}})
      ["unacked"], {})
check("A3: an ordinary author list raises no one-letter-surname note",
      [n for n in references.audit("Doad, J. S., & Smith, J. (2020). T. V.", True)[1]
       if "single-letter" in n], [])

# ---- author fix 4: a family-first claim is checked on its surname (2026-09-26) ----
# claim_surname("Smith J") returned "J", and the author check then matched any
# record whose first author had the initial J.
for _a4in, _a4out in (("Smith J", "Smith"), ("Smith JL", "Smith"), ("Smith J.", "Smith"),
                      ("Smith J. L.", "Smith"), ("J. Smith", "Smith"), ("J Smith", "Smith"),
                      ("Smith, J.", "Smith"), ("Smith", "Smith")):
    check(f"A4: claim_surname({_a4in!r})", verify.claim_surname(_a4in), _a4out)
check_true("A4: 'J. Smith' no longer matches 'Jones J' on the initial", _m8("J. Smith", "Jones J") != [])
check_true("A4: ...nor the other way round", _m8("Jones J", "J. Smith") != [])
check("A4: 'Smith J' matches the record 'Smith J'", _m8("Smith J", "Smith J"), [])
check("A4: 'J. Smith' matches the record 'Smith J'", _m8("J. Smith", "Smith J"), [])
check("A4: a one-letter surname still compares (nothing else is left on that side)", _m8("O", "O K"), [])
check_true("A4: ...and still mismatches another one-letter surname", _m8("O", "Q K") != [])

# ---- author fix 1: the surname "An" is not an article (2026-09-26) ----
# _name_tokens dropped a leading "a"/"an" as an article, so the record "An J"
# lost its surname and mismatched a correct claim "An".
check("A1: 'An' matches 'An J'", _m8("An", "An J"), [])
check("A1: 'A' matches 'A J'", _m8("A", "A J"), [])
check("A1: 'An' matches the record 'An JH'", _m8("An", "An JH"), [])
check_true("A1: 'The pandas development team' still does not match 'Matthews'",
           _m8("The pandas development team", "Matthews") != [])
check("A1: 'Tang' still matches 'Tang J'", _m8("Tang", "Tang J"), [])

# ---- author fix 2: a hyphenated surname matches on either part (2026-09-26) ----
# Only a >= 4-char prefix matched, so a claim naming the second part of a
# hyphenated surname ("Hanna" for Andrews-Hanna) was a false alarm.
check("A2: 'Hanna' matches 'Andrews-Hanna J'", _m8("Hanna", "Andrews-Hanna J"), [])
check("A2: 'Andrews' matches 'Andrews-Hanna J'", _m8("Andrews", "Andrews-Hanna J"), [])
check("A2: 'Lopez' matches 'Garcia-Lopez J'", _m8("Lopez", "Garcia-Lopez J"), [])
check_true("A2: 'Han' still mismatches 'Andrews-Hanna J' (no partial-word match)",
           _m8("Han", "Andrews-Hanna J") != [])
check_true("A2: a one-letter hyphen part does not count ('A' vs 'B-A J')", _m8("A", "B-A J") != [])

# ---- author fix 4b: a multi-word surname before trailing initials (2026-09-26) ----
# "Van Essen D" returned "D"; once initials stopped matching (fix 4), a correct
# claim then mismatched its record "Van Essen D".
check("A4b: claim_surname('Van Essen D')", verify.claim_surname("Van Essen D"), "Van Essen")
check("A4b: claim_surname('Thomas Yeo BT')", verify.claim_surname("Thomas Yeo BT"), "Thomas Yeo")
check("A4b: claim_surname('Van Essen DC') matches the record 'Van Essen D'",
      _m8(verify.claim_surname("Van Essen DC"), "Van Essen D"), [])
check("A4b: 'Thomas Yeo B' matches the record 'Yeo B'", _m8(verify.claim_surname("Thomas Yeo B"), "Yeo B"), [])
check("A4b: a given-first name is unchanged ('Jane Smith')", verify.claim_surname("Jane Smith"), "Smith")

# ---- author fix round 1, B: claim_surname reads every PubMed shape (2026-09-26) ----
for _bin, _bout in (("LI J", "LI"), ("AN J", "AN"), ("O K", "O"), ("LEE JH", "LEE"),
                    ("Smith J.-L.", "Smith"), ("King J-R", "King"), ("Smith JLK", "Smith"),
                    ("SCHLEIDT W", "SCHLEIDT"), ("Van Essen DC", "Van Essen"),
                    ("van den Heuvel MP", "van den Heuvel"), ("Thomas Yeo BT", "Thomas Yeo"),
                    ("Quoc V. Le", "Le"), ("Hae-Jeong Park", "Park")):
    check(f"B: claim_surname({_bin!r})", verify.claim_surname(_bin), _bout)

# ---- author fix round 1, A: compare surname to surname (2026-09-26) ----
# The token patchwork let given names and initials take part ("Van Essen DC"
# matched "Van Dijk K" on "van"; "Min" matched "Seung-Min Park"). Now both sides
# go through claim_surname, arXiv display names are split first, and only the
# claim's first non-particle surname token is looked up in the record surname.
def _mA(expect, actual, arxiv=False):
    rec = (verify._found_record({"title": "", "year": "", "first_author": actual}) if arxiv
           else {"first_author": actual})
    return verify._author_issue({"expect_first_author": expect}, rec)


for _ae, _aa, _ax in (("Van Essen DC", "Van Dijk K", False), ("Van Essen DC", "van den Heuvel M", False),
                      ("Van Essen DC", "Aaron van den Oord", True), ("Le Bihan D", "Quoc V. Le", True),
                      ("Le Bihan D", "Le Cun Y", False), ("den Ouden HE", "van den Heuvel M", False),
                      ("de Heer WA", "de Lange FP", False), ("Thomas Yeo BT", "Thomas Serre", True),
                      ("Min", "Seung-Min Park", True), ("Jeong", "Hae-Jeong Park", False),
                      ("Hyun", "Jae-Hyun Kim", False), ("Jing", "Xiao-Jing Wang", False),
                      ("An", "An Nguyen", True), ("Ma", "Smith MA", False), ("An", "Smith AN", False),
                      ("Ho", "Chan HO", False), ("Smith J", "Jones J", False), ("O K", "Kim K", False),
                      ("The pandas development team", "The NumPy team", False)):
    check_true(f"A: {_ae!r} mismatches {'arXiv ' if _ax else ''}{_aa!r}", _mA(_ae, _aa, _ax) != [])
for _ae, _aa, _ax in (("Heuvel", "van den Heuvel M", False), ("van den Heuvel MP", "van den Heuvel M", False),
                      ("Dupré la Tour", "Dupré la Tour T", False), ("Hanna", "Andrews-Hanna JR", False),
                      ("Lambon Ralph MA", "Lambon Ralph M", False), ("O'Reilly RC", "O'Reilly R", False),
                      ("Li XJ", "Li X", False), ("An", "An J", False), ("Tang", "Tang J", False),
                      ("Van Essen DC", "Van Essen D", False), ("Oord", "Aaron van den Oord", True),
                      ("Park", "Seung-Min Park", True), ("Le", "Quoc V. Le", True),
                      ("The pandas development team", "The pandas development team", False)):
    check(f"A: {_ae!r} matches {'arXiv ' if _ax else ''}{_aa!r}", _mA(_ae, _aa, _ax), [])
check("A: an arXiv found-record carries the 'Family G' shape",
      verify._found_record({"title": "T", "year": "2016", "first_author": "Aaron van den Oord"})["first_author"],
      "van den Oord A")
check("A: claim_surname keeps a 'The ...' group name whole",
      verify.claim_surname("The pandas development team"), "The pandas development team")

# (A calibration: PubMed suffixes and all-caps particle surnames, 2026-09-26)
for _bin, _bout in (("Hagler DJ Jr", "Hagler"), ("Smith EL 3rd", "Smith"), ("SCHADE OH Sr", "SCHADE"),
                    ("Smith J II", "Smith"), ("VAN DER TWEEL LH", "VAN DER TWEEL"),
                    ("DE LANGE DZN H", "DE LANGE"), ("de Lange Dzn", "de Lange Dzn"),
                    ("van der Tweel", "van der Tweel")):
    check(f"A: claim_surname({_bin!r})", verify.claim_surname(_bin), _bout)
for _ae, _aa in (("Hagler", "Hagler DJ Jr"), ("Smith", "Smith EL 3rd"), ("Schade", "SCHADE OH Sr"),
                 ("de Lange Dzn", "DE LANGE DZN H"), ("van der Tweel", "VAN DER TWEEL LH")):
    check(f"A: {_ae!r} matches {_aa!r}", _mA(_ae, _aa), [])
check_true("A: 'van der Tweel' still mismatches 'VAN DER BERG LH'", _mA("van der Tweel", "VAN DER BERG LH") != [])

# ---- author fix round 1, C: DataCite never takes trailing initials as the family (2026-09-26) ----
for _cn, _cp in (("Van Essen DC", "Van Essen, D. C."), ("Thomas Yeo BT", "Thomas Yeo, B. T."),
                 ("Kim J-H", "Kim, J.-H."), ("Doad JLK", "Doad, J. L. K."), ("VAN DER TWEEL LH", None)):
    if _cp:
        check(f"C: Personal {_cn!r} splits words-then-initials", _c1_people([{"name": _cn, "nameType": "Personal"}]),
              ([_cp], []))
check("C: an all-caps particle surname splits words-then-initials too",
      _c1_people([{"name": "VAN DER TWEEL LH", "nameType": "Personal"}])[1], [])
check_true("C: 'Thomas Yeo, B. T.' is left for suspect_surnames to warn about",
           "Thomas Yeo" in common.suspect_surnames("Thomas Yeo, B. T. (2020). T. V."))
check("C: initials with no words before them are kept whole, unsplit",
      _c1_people([{"name": "J S", "nameType": "Personal"}]), (["J S"], ["J S"]))
check("C: a familyName that is only part of a hyphenated word is not found: kept whole, unsplit",
      _c1_people([{"name": "Anna Doad-Smith", "familyName": "Doad"}]), (["Anna Doad-Smith"], ["Anna Doad-Smith"]))
check("C: a familyName absent from `name` keeps the name whole, unsplit",
      _c1_people([{"name": "Jane Roe", "familyName": "Doad"}]), (["Jane Roe"], ["Jane Roe"]))
check("C: a hyphenated familyName is still found whole",
      _c1_people([{"name": "Anna Doad-Smith", "familyName": "Doad-Smith"}]), (["Doad-Smith, A."], []))

# ---- author fix round 1, D: one initials regex, one family extractor (2026-09-26) ----
check("D: apa_families lists every initialed family, in order",
      common.apa_families("Smith, J. A., O, K., & van den Heuvel, M. P. (2020). T. V."),
      ["Smith", "O", "van den Heuvel"])
check_true("D: verify uses common's initials regex", not hasattr(verify, "_INITIALS"))
check("C: a Personal 'An Nguyen' is a person, not a group", _c1_people([{"name": "An Nguyen", "nameType": "Personal"}]),
      (["Nguyen, A."], []))

# ---- author fix round 2, item 1: initials of any script (2026-09-26) ----
# INITIALS knew only [A-ZÀ-Ý]; "Ł" was no initial, so both "Nowak Ł" and
# "Kowalski Ł" reduced to "Ł" and matched.
for _ae, _aa in (("Nowak Ł", "Kowalski Ł"), ("Novák Š", "Svoboda Š"), ("Yılmaz Ş", "Kaya Ş"),
                 ("Иванов И", "Петров И")):
    check_true(f"R2.1: {_ae!r} mismatches {_aa!r}", _mA(_ae, _aa) != [])
check("R2.1: 'Kowalski' matches 'Kowalski Ł'", _mA("Kowalski", "Kowalski Ł"), [])
check("R2.1: claim_surname('Nguyen ĐT')", verify.claim_surname("Nguyen ĐT"), "Nguyen")
check("R2.1: claim_surname never returns one letter when a longer token exists",
      verify.claim_surname("Kowalski ł"), "Kowalski")
check("R2.1: DataCite 'Kowalski ŁS' -> family Kowalski",
      _c1_people([{"name": "Kowalski ŁS", "nameType": "Personal"}]), (["Kowalski, Ł. S."], []))
check("R2.1: DataCite 'Nguyen ĐT' -> family Nguyen",
      _c1_people([{"name": "Nguyen ĐT", "nameType": "Personal"}]), (["Nguyen, Đ. T."], []))
check_true("R2.1: is_initials takes any uppercase script, 1-4 letters",
           all(common.is_initials(t) for t in ("Ł", "ŁS", "Đ.T.", "И", "J-H", "J.-L.", "JLKM"))
           and not any(common.is_initials(t) for t in ("Jr", "Li", "JLKMN", "ł", "1A", "-", "")))

# ---- author fix round 2, item 2: an unreadable record author fails closed (2026-09-26) ----
check_true("R2.2: 'Smith' vs a CrossRef 'Craig (' is a mismatch", _mA("Smith", "Craig (") != [])
check("R2.2: ...while 'Craig' matches it", _mA("Craig", "Craig ("), [])
check("R2.2: a record author with no readable word is reported, not skipped",
      _mA("Smith", "( — )"), ["first-author mismatch: could not read the record's first author '( — )' "
                              "(expected 'Smith')"])
check("R2.2: a record with no first author at all is still not checked", _mA("Smith", ""), [])

# ---- author fix round 2, item 3: the claim is parsed once (2026-09-26) ----
# rows_to_citations applied claim_surname and _author_issue parsed it again, so
# "Dupré la Tour" keyed on "Tour" and "Lambon Ralph" on "Ralph".
def _r3(search_author, apa, record):
    """(claim-path issues, apa-path issues) for a canonical row with a claim."""
    c = verify.rows_to_citations([{"ref": "R3", "doi": "10.1/r3", "search_author": search_author,
                                   "apa": apa, "canonical_at": "2026-09-26"}], "ref")[0]
    rec = {"first_author": record}
    return verify._author_issue(c, rec), verify._author_issue(dict(c, **c["alt_expect"]), rec)


_r3c = verify.rows_to_citations([{"ref": "R3", "doi": "10.1/r3", "search_author": "Dupré la Tour T",
                                  "apa": "Dupré la Tour, T. (2020). T. V.", "canonical_at": "x"}], "ref")[0]
check("R2.3: a claim carries the raw search_author; the apa path an expect_surname used as-is",
      (_r3c["expect_first_author"], _r3c["alt_expect"].get("expect_surname"),
       "expect_first_author" in _r3c["alt_expect"]), ("Dupré la Tour T", "Dupré la Tour", False))
for _sa, _apa, _rec in (("Dupré la Tour T", "Dupré la Tour, T. (2020). T. V.", "Tour X"),
                        ("Lambon Ralph MA", "Lambon Ralph, M. A. (2020). T. V.", "Ralph J"),
                        ("Thomas Yeo BT", "Thomas Yeo, B. T. (2020). T. V.", "Thomas R")):
    _i = _r3(_sa, _apa, _rec)
    check_true(f"R2.3: {_sa!r} vs {_rec!r} mismatches on the claim path and the apa path",
               _i[0] != [] and _i[1] != [], str(_i))
check("R2.3: ...and the right record matches on both", _r3("Dupré la Tour T", "Dupré la Tour, T. (2020). T. V.",
                                                          "Dupré la Tour T"), ([], []))
check("R2.3: a --citations input's expect_first_author is raw and parsed once",
      verify._author_issue({"expect_first_author": "Lambon Ralph MA"}, {"first_author": "Lambon Ralph M"}), [])
check_true("R2.3: ...so 'Lambon Ralph MA' does not match 'Ralph J'",
           verify._author_issue({"expect_first_author": "Lambon Ralph MA"}, {"first_author": "Ralph J"}) != [])

# ---- report ---------------------------------------------------------------
if FAILURES:
    print(f"FAILED {len(FAILURES)} check(s):\n")
    for f in FAILURES:
        print("  ✗ " + f)
    sys.exit(1)
print("✓ all formatting/audit/citation regression checks pass")
