# literature-review-toolkit

Scaffolding to drive a Claude (or other LLM) agent through a structured
literature review for an academic topic — search, verify, xref, and
assemble a single annotated `.xlsx` bibliography. PDF acquisition is
opt-in.

The agent does the judgment work; these scripts handle the API calls,
verification, and bookkeeping that keep the agent honest.

See [`PLAYBOOK.md`](./PLAYBOOK.md) for the procedure. Scripts live in
[`tools/`](./tools).

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
`Topic | Ref# | APA reference | Link | Summary | Tag | PDF (local) | Xref`,
color-coded by origin (white = cited in your source doc if any, cream =
initial agent search, green = cross-citation pass). The `Link` column is
always the DOI URL (`https://doi.org/<doi>`).

**PDF acquisition is opt-in.** By default the toolkit does not download
PDFs — the `PDF (local)` column stays empty. Phase 4 (`tools/download.py`
+ `tools/reconcile_downloads.py`) only runs if the user explicitly asks.
A dedicated PDF-fetch tool will replace this path eventually.

## Setup

```bash
git clone https://github.com/jackgallant/literature-review-toolkit.git
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

# Phase 5: build the xlsx from your accumulated rows JSON.
python3 ../tools/spreadsheet.py --rows rows.json --out my_topic_bibliography.xlsx

# Phase 6: cross-citation pass.
python3 ../tools/xref.py --papers verified.json \
                         --exclude existing_dois.json \
                         --out xref_my_topic.json \
                         --min-cites 4 --resolve-unknown

# Pick green-tier additions from xref_my_topic.json, repeat Phases 3+5
# for that batch (append to rows.json, rerun spreadsheet.py).

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

## Worked example: language-learning review

Earlier project, same workflow, different topic. Output dir is
`language.learning/`, deliverable is `bibliography.xlsx`. The audit
trail (`agent_out.json`, `rows.json`, `xref_language_learning.json`,
etc.) is preserved in case the review is extended later.

## Tools index

| Script | Purpose |
|---|---|
| [`tools/verify.py`](./tools/verify.py) | Verify citations via PMC/PubMed/CrossRef; catches ~25% search-agent fabrications. |
| [`tools/xref.py`](./tools/xref.py) | Cross-citation frequency table from CrossRef reference lists. |
| [`tools/spreadsheet.py`](./tools/spreadsheet.py) | Build/rebuild the `.xlsx` from accumulated JSON rows (links are DOI URLs). |
| [`tools/search_prompt_template.md`](./tools/search_prompt_template.md) | Prompt template for the literature-search subagent. |
| [`tools/download.py`](./tools/download.py) | **Opt-in (Phase 4).** Multi-source PDF downloader (arxiv → Unpaywall → EuropePMC). |
| [`tools/reconcile_downloads.py`](./tools/reconcile_downloads.py) | **Opt-in (Phase 4).** Move user-downloaded PDFs from `~/Downloads` into the per-topic dir with the right slug. |

Each is small, standalone, and meant to be read and adapted. They're
scaffolding, not a framework.

## License

MIT — see [`LICENSE`](./LICENSE).
