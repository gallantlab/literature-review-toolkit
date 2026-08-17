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

import cite_check                       # noqa: E402
import common                           # noqa: E402
import references                       # noqa: E402
import sentence_case as sc              # noqa: E402

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

# ---- report ---------------------------------------------------------------
if FAILURES:
    print(f"FAILED {len(FAILURES)} check(s):\n")
    for f in FAILURES:
        print("  ✗ " + f)
    sys.exit(1)
print("✓ all formatting/audit/citation regression checks pass")
