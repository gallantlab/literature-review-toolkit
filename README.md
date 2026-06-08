# literature-review-toolkit

Scaffolding to drive a Claude (or other LLM) agent through a structured
literature review — search, verify, rebuild every reference into canonical form,
count citations, cross-reference, and assemble a single annotated `.xlsx`
bibliography, then (optionally) group it into theoretical families with an
interactive lineage figure. PDF acquisition is opt-in.

The agent does the judgment work; these scripts handle the API calls,
verification, and bookkeeping that keep the agent honest.

**Two modes.** *Topic mode* starts from a query and searches outward (the default
described below). *Lab mode* inverts it: start from a lab's full publication
corpus, derive its research themes and how they changed over time, then search
outward to place that work in the field — see "Lab mode" in
[`PLAYBOOK.md`](./PLAYBOOK.md). Both share the same verify / count / families /
figure machinery.

See [`PLAYBOOK.md`](./PLAYBOOK.md) for the full procedure. Scripts live in
[`tools/`](./tools).

## How it works — judgment vs. mechanics

A review has **three points where a human decides**; everything between them
runs automatically — but with a guardrail, not your attention, because those
steps have a ground truth.

| # | You decide… | Phase |
|---|---|---|
| 1 | **Scope** — the topic and span of the search | 1 |
| 2 | **Families** *(optional)* — you approve/edit the agent's proposed grouping *before* it labels every paper | 6b |
| 3 | **Figure** *(optional)* — you iterate on a lineage/taxonomy figure with the agent (bespoke, not auto-generated) | — |

In between, the mechanical steps are guarded, not reviewed: **every citation is
verified** against PMC/PubMed/CrossRef/arXiv (search agents fabricate roughly 1
in 4 — wrong first authors, inverted findings, invented DOIs), **every reference
is rebuilt** from its verified DOI into canonical APA-7 with a hard audit gate
(no agent-typed or OpenAlex-typed reference text is trusted), **citation counts**
are fetched and schema-checked, dedup and cross-citation mining run, and the
spreadsheet is rebuilt from JSON each time.

**Phases at a glance:** 1 scope · 2 search · 3 verify *(critical)* · 3f
canonicalize refs · 4 PDFs *(opt-in)* · 5 spreadsheet · 5b citation counts · 6
cross-citation · 6b families *(opt)* · 7 hand-off. **Lab mode** swaps phases 1–2
for ingest-corpus → derive-themes, then converges on this same pipeline. Full
detail in [`PLAYBOOK.md`](./PLAYBOOK.md).

## What you get out

**The deliverable is one `.xlsx` file.** Everything else is scaffolding
and an audit trail you can ignore.

For each review you run, results land in **a named subdirectory** — one
per topic — under whatever bibliography root you keep. The subdirectory
holds the spreadsheet plus all the JSON files used to build it. The
agent rebuilds the spreadsheet from the JSON each time, so the JSON is
the source of truth and the `.xlsx` is the rendered output.

```
<bibliography_root>/
├── literature-review-toolkit/         <- this repo, cloned once
├── visual_cerebellum/                 <- one review topic, one subdir
│   ├── visual_cerebellum_bibliography.xlsx   <-- THE DELIVERABLE
│   ├── topic_definition.md            (scope you & the agent agreed on)
│   ├── agent_out.json                 (raw search-agent output)
│   ├── verified.json                  (after Phase 3 corrections)
│   ├── verify_report.json             (per-citation OK / MISMATCH / NOT-FOUND)
│   ├── rows.json                      (everything the spreadsheet renders from)
│   ├── citation_counts.json           (Phase 5b: OpenAlex + S2 counts, cached)
│   ├── families.json / families.md    (Phase 6b: theoretical grouping, if run)
│   ├── visual_cerebellum_families.html (Phase 6b: interactive figure; + .svg/.png/.pdf)
│   ├── xref_visual_cerebellum.json    (cross-citation frequency table)
│   ├── xref_picks.json                (the green-tier picks from xref)
│   └── xref_meta.json                 (CrossRef metadata for xref picks)
├── attention/                         <- a different topic, separate subdir
│   └── attention_bibliography.xlsx
└── language_learning/
    └── bibliography.xlsx
```

If you want to share the result with someone, send the `.xlsx`. If you
want to extend or re-run the review later, the JSON files in the
subdirectory are what the toolkit reads from.

The spreadsheet has columns
`Topic | Ref# | APA reference | Link | Summary | Tag | Family | Cite (OpenAlex) | Cite (S2) | PDF (local) | Xref`,
color-coded by origin (white = cited in your source doc if any, cream =
initial agent search, green = cross-citation pass). The `Link` column is
always the DOI URL (`https://doi.org/<doi>`). Two columns appear only once their
pass has run: the **`Cite`** columns are per-paper citation counts from
`tools/citations.py` (Phase 5b) — Google Scholar has no API, so OpenAlex +
Semantic Scholar are the source — and **`Family`** is the theoretical grouping
from `tools/families.py` (Phase 6b). Both auto-add to the sheet when present.

**PDF acquisition is opt-in.** By default the toolkit does not download
PDFs — the `PDF (local)` column stays empty. Phase 4 (`tools/download.py`
+ `tools/reconcile_downloads.py`) only runs if the user explicitly asks.
A dedicated PDF-fetch tool will replace this path eventually.

## Setup

```bash
git clone https://github.com/gallantlab/literature-review-toolkit.git
cd literature-review-toolkit

# Python deps
pip install xlsxwriter
# pdftotext (only needed for the opt-in PDF reconciliation in Phase 4)
brew install poppler        # macOS; or: apt-get install poppler-utils

# Contact email for NCBI/CrossRef User-Agent (required by verify/xref).
# Either export once:
export LITREVIEW_EMAIL=you@inst.edu
# ...or pass --email to each tool invocation.
```

## Driving it via Claude Code (the intended workflow)

Open Claude Code in your bibliography root and just tell it the topic
in plain English. The agent reads `PLAYBOOK.md`, creates the named
subdirectory, runs Phases 1-7, and drops the `.xlsx` inside. Examples
of prompts that work:

```
> i want to do a literature review on the anatomical connections
  between the visual system and the cerebellum. any anatomy papers from
  primate or human, using any tractography method. go back as far as
  the 1970s.

> do a fresh lit review on language learning in adults — both L1 and L2,
  behavioral and neuroimaging studies, last 15 years.

> extend the existing visual_cerebellum review with another 20 papers
  focused on cerebello-thalamic projections.

> now group the world_models bibliography into a few theoretical families,
  and let's iterate on a lineage figure.
```

The agent will pick a slug for the subdirectory (`visual_cerebellum/`,
`language_learning/`, etc.), confirm scope only when something is
genuinely ambiguous, and report when done.

For ~40 search-added + ~30 xref-added papers, the no-PDF workflow takes
roughly 1-2M tokens and 5-10 minutes wall-clock; Phase 6 (xref) is the
slowest step.

## Driving it manually (if you don't have Claude Code)

```bash
# Pick a topic slug and make a subdir.
mkdir my_topic && cd my_topic

# Phase 2: spawn a literature-search agent (or do the search yourself)
#          with the prompt at ../tools/search_prompt_template.md filled in.
#          Save the returned list as agent_out.json. Links MUST be DOI URLs.

# Phase 3: verify everything before trusting any of it.
python3 ../tools/verify.py --citations agent_out.json --out verify_report.json

# Phase 3f: rebuild every reference into canonical APA-7 from the verified DOI,
#           then gate (exit 1 on any imperfect ref). Both modes.
python3 ../tools/references.py --rows rows.json --out rows.json
python3 ../tools/references.py --rows rows.json --audit

# Phase 5: build the xlsx from your accumulated rows JSON.
python3 ../tools/spreadsheet.py --rows rows.json --out my_topic_bibliography.xlsx

# Phase 5b: citation counts; attach to rows (cite_openalex/cite_s2), rerun spreadsheet.py.
python3 ../tools/citations.py --rows rows.json --out citation_counts.json

# Phase 6: cross-citation pass.
python3 ../tools/xref.py --papers verified.json \
                         --exclude existing_dois.json \
                         --out xref_my_topic.json \
                         --min-cites 4 --resolve-unknown

# Pick green-tier additions from xref_my_topic.json, repeat Phases 3+5
# for that batch (append to rows.json, rerun spreadsheet.py).

# Phase 6b (optional): theoretical families + interactive HTML figure.
python3 ../tools/families.py --rows rows.json --assign families_input.json --out families.json
python3 ../tools/families_figure.py --rows rows.json --families families.json \
                                    --out-prefix my_topic_families --title "My topic — families"

# --- OPTIONAL: Phase 4 (PDF download) ---
# Only run if you've decided to grab PDFs. Default workflow skips this.
# python3 ../tools/download.py --papers verified.json \
#                              --out-dir papers/ \
#                              --email "$LITREVIEW_EMAIL"
# python3 ../tools/reconcile_downloads.py --manifest papers/_manifest.json \
#                                         --out-dir papers/
```

## Worked example: visual–cerebellar anatomy review

Run from this conversation, fully reproducible from the JSON files in
the subdirectory:

| | |
|---|---|
| **Prompt** | "anatomical connections between visual system and cerebellum, primate or human, any tractography method, back to the 1970s" |
| **Output dir** | `visual_cerebellum/` |
| **Final spreadsheet** | `visual_cerebellum/visual_cerebellum_bibliography.xlsx` (72 rows) |
| **Agent search batch** | 42 papers spanning 1980-2025 (cream rows) |
| **Cross-citation batch** | 30 papers spanning 1944-2010 (green rows) |
| **Verifier corrections** | 3 fabrications caught: one paper had hallucinated authors (Schmahmann et al. 2025 was returned as "Olson et al."), one DOI was off by a digit, one PMCID was invented |
| **Wall-clock** | ~7 min, no PDF acquisition |

The `visual_cerebellum/` directory in the parent bibliography root has
the full audit trail: `agent_out.json` is the raw agent return,
`verify_report.json` shows what was caught, `xref_visual_cerebellum.json`
is the full cross-citation frequency table, `xref_picks.json` is the
30 picked from it, and `rows.json` is what the spreadsheet renders from.

## Worked example: social/observational learning fMRI review

Earlier project, same workflow:

| | |
|---|---|
| **Prompt** | "build a bibliography on social and observational learning, restricted to fMRI studies in humans" |
| **Output dir** | `language.learning/` (legacy name from when the topic was being scoped — kept as-is) |
| **Final spreadsheet** | `language.learning/bibliography.xlsx` (68 rows) |
| **Agent search batch** | 39 papers spanning 1999-2025 (cream rows) |
| **Cross-citation batch** | 29 papers (green rows) |
| **Verifier corrections** | 4 first-author fabrications caught (e.g. agent returned "Atlas" as first author of a paper actually first-authored by Tang; "Wittmann" for a Li paper). All fixed before the rows were written to the xlsx. |

## Tools index

| Script | Purpose |
|---|---|
| [`tools/verify.py`](./tools/verify.py) | Verify citations via PMC/PubMed/CrossRef + the arXiv API (preprints/conference papers get a real verdict, not a misleading NOT-FOUND); catches ~25% search-agent fabrications. |
| [`tools/references.py`](./tools/references.py) | **Phase 3f.** Rebuild every reference from its verified DOI/arXiv id into canonical APA-7 (full authors, particles, casing, real venue incl. bioRxiv/PsyArXiv); `--audit` is a hard gate. Used in **both** topic and lab mode so refs are never imperfect. |
| [`tools/citations.py`](./tools/citations.py) | **Phase 5b.** Per-paper citation counts from OpenAlex (primary) + Semantic Scholar by DOI. Google Scholar isn't queryable (no API / CAPTCHA). |
| [`tools/xref.py`](./tools/xref.py) | Cross-citation frequency table from CrossRef reference lists. |
| [`tools/lab_corpus.py`](./tools/lab_corpus.py) | **Lab mode (L1).** Ingest a lab's full publication corpus from OpenAlex by author id. Enrich abstracts before classifying — OpenAlex metadata alone is insufficient. |
| [`tools/families.py`](./tools/families.py) | **Phase 6b.** Validate/stamp/render a theoretical-family grouping (agent proposes, you approve the definitions). |
| [`tools/families_figure.py`](./tools/families_figure.py) | **Phase 6b.** Interactive HTML lineage figure (+ svg/png/pdf) from rows + families. Replaces the old static figure. |
| [`tools/family_prompt_template.md`](./tools/family_prompt_template.md) | Two-step propose → assign prompt for the families pass. |
| [`tools/spreadsheet.py`](./tools/spreadsheet.py) | Build/rebuild the `.xlsx` from accumulated JSON rows; auto-adds `Cite` / `Family` columns when present. |
| [`tools/search_prompt_template.md`](./tools/search_prompt_template.md) | Prompt template for the literature-search subagent. |
| [`tools/download.py`](./tools/download.py) | **Opt-in (Phase 4).** Multi-source PDF downloader (arxiv → Unpaywall → EuropePMC). |
| [`tools/reconcile_downloads.py`](./tools/reconcile_downloads.py) | **Opt-in (Phase 4).** Move user-downloaded PDFs from `~/Downloads` into the per-topic dir with the right slug. |

Each is small, standalone, and meant to be read and adapted. They're
scaffolding, not a framework.

## License

MIT — see [`LICENSE`](./LICENSE).
