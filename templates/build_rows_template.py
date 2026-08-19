#!/usr/bin/env python3
"""Template — copy this into a new review directory as `build_rows.py` and edit.

It emits the project's `rows.json` ONCE, from the papers a search agent
returned, and then hands everything to the shared tools:

    python3 build_rows.py                                   # -> rows.json (guarded)
    python3 tools/verify.py     --rows rows.json --out verify_report.json
    python3 tools/references.py --rows rows.json --out rows.json      # canon + canonical_at stamp
    python3 tools/references.py --rows rows.json --audit              # hard gate
    python3 tools/citations.py  --rows rows.json --out citation_counts.json
    python3 tools/spreadsheet.py --rows rows.json --out <topic>_bibliography.xlsx

Two conventions this template enforces, both learned the hard way:

  * It imports the toolkit's `common` instead of re-implementing JSON I/O or DOI
    parsing, so a fix in the toolkit reaches this project (the UTF-8 / ensure_ascii
    fix and the APA year-suffix fix once did not reach any project script).
  * It writes rows.json through `common.write_rows`, which REFUSES to overwrite a
    canonical table (rows stamped `canonical_at` by references.py). After Phase 3f
    rows.json is the live table — edit it directly; re-running this script would
    wipe the canonical references, the reviewed casing, and every hand fix.

The `apa` field is left empty here on purpose: references.py rebuilds it from the
DOI, and the audit gate refuses anything typed from memory.
"""
import os
import sys

# --- toolkit on the path: sibling checkout, or point LITREVIEW_TOOLS at tools/ ---
sys.path.insert(0, os.environ.get("LITREVIEW_TOOLS", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "literature-review-toolkit", "tools")))
import common  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# DATA (importable, no side effects)
# ============================================================
# One tuple per paper: (topic, ref, doi, summary, tag, source)
#   topic   one of the project's topic lanes (the spreadsheet's Topic column)
#   ref     stable row key, e.g. "M1" — never reuse one across batches
#   doi     bare DOI ("10.1038/…"); "" for a book/report (kept as a manual ref)
#   summary 3-5 sentences: what the paper did and why it matters for the topic
#   tag     see PLAYBOOK Phase 2 (classic / method / review / …)
#   source  "search" | "xref" | "anteced" | "source-doc" | "lab" (row color)
PAPERS = [
    # ("Multimodal networks", "M1", "10.1038/nn.4244",
    #  "Mapped semantic selectivity across cortex with natural narrative speech …",
    #  "classic", "search"),
]


def rows():
    out = []
    for topic, ref, doi, summary, tag, source in PAPERS:
        out.append({"topic": topic, "ref": ref, "doi": doi,
                    "link": f"https://doi.org/{doi}" if doi else "",
                    "apa": "",                     # filled by references.py
                    "summary": summary, "tag": tag, "source": source})
    refs = [r["ref"] for r in out]
    assert len(refs) == len(set(refs)), "duplicate ref ids"
    return out


# ============================================================
# WRITING BLOCK — guarded so an import never rewrites rows.json
# ============================================================
if __name__ == "__main__":
    path = os.path.join(HERE, "rows.json")
    force = "--force" in sys.argv
    try:
        common.write_rows(path, rows(), force=force)
    except common.CanonicalTableError as e:
        sys.exit(f"{e}\n(run with --force only if you really mean to rebuild the table)")
    print(f"wrote {len(PAPERS)} rows -> {path}")
