# Tools reference

Every script lives in
[`tools/`](https://github.com/gallantlab/literature-review-toolkit/tree/main/tools).
Each is small, standalone, and meant to be **read and adapted** — scaffolding,
not a framework. They share one helper module (`common.py`: HTTP with backoff,
JSON I/O, DOI/arXiv parsing, APA building). Run any with `--help`.

## Core pipeline

| Script | Phase | Purpose |
|---|---|---|
| [`verify.py`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/verify.py) | 3 | Verify every citation via PMC/PubMed/CrossRef **+ the arXiv API** (preprints get a real verdict, not a misleading `NOT-FOUND`). Catches ~25% search-agent fabrications. |
| [`references.py`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/references.py) | 3f | Rebuild every reference from its verified DOI/arXiv id into canonical APA-7 (full authors, particles, casing, real venue incl. bioRxiv/PsyArXiv). `--audit` is a **hard gate**. Both modes. |
| [`spreadsheet.py`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/spreadsheet.py) | 5 | Build/rebuild the `.xlsx` from the accumulated JSON rows; auto-adds `Cite` / `Family` columns when present. |
| [`citations.py`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/citations.py) | 5b | Per-paper citation counts from OpenAlex (primary) + Semantic Scholar by DOI, with undercount reconciliation. |
| [`xref.py`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/xref.py) | 6 | Cross-citation frequency table from the corpus's own CrossRef reference lists. |

## Families, figure & review

| Script | Phase | Purpose |
|---|---|---|
| [`families.py`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/families.py) | 6b | Validate / stamp / render a theoretical-family grouping (agent proposes, you approve the definitions). |
| [`families_figure.py`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/families_figure.py) | 6b | Interactive HTML lineage figure (+ svg/png/pdf); landmark dots auto-selected by citation count, within-corpus in-degree, and lab authorship. |
| [`family_prompt_template.md`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/family_prompt_template.md) | 6b | Two-step *propose → assign* prompt for the families pass. |
| [`review_paper.py`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/review_paper.py) | 7 | Render an AI-authored narrative review `.docx` from `content.json` (prose) + `rows.json` (canonical references). Mechanics only — prose is authored separately, after the priority audit. |

## Lab mode

| Script | Phase | Purpose |
|---|---|---|
| [`lab_corpus.py`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/lab_corpus.py) | L1 | Ingest a lab's full publication corpus from OpenAlex by author id (`--search` to resolve the id). Enrich abstracts before classifying — OpenAlex metadata alone is insufficient. |

## Search prompt & PDFs (opt-in)

| Script | Phase | Purpose |
|---|---|---|
| [`search_prompt_template.md`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/search_prompt_template.md) | 2 / 2b | Prompt template for the literature-search subagent (forward search + antecedents). |
| [`download.py`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/download.py) | 4 *(opt-in)* | Multi-source PDF downloader (arXiv → Unpaywall → EuropePMC). |
| [`reconcile_downloads.py`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/reconcile_downloads.py) | 4 *(opt-in)* | File manually-downloaded PDFs from `~/Downloads` into the per-topic dir with the right slug. |

## Shared helper

| Script | Purpose |
|---|---|
| [`common.py`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/common.py) | HTTP with exponential backoff, JSON read/write, DOI/arXiv id parsing, author-name splitting, and the canonical APA builder shared by the other tools. |

!!! tip "Read the PLAYBOOK alongside the tools"
    The
    [`PLAYBOOK.md`](https://github.com/gallantlab/literature-review-toolkit/blob/main/PLAYBOOK.md)
    is the operating manual the agent follows — it documents the order, the
    guardrails, and the hard-won lessons (mojibake handling, compound-surname
    fixes, OpenAlex undercount tells, and more) that the scripts encode.
