# Tools reference

Every script lives in
[`tools/`](https://github.com/gallantlab/literature-review-toolkit/tree/main/tools).
Each is small, standalone, and meant to be **read and adapted** — scaffolding,
not a framework. They share one helper module (`common.py`: HTTP with backoff,
JSON I/O, DOI/arXiv parsing, the APA builder **and the APA parser** every tool
reads references back with, the CrossRef/arXiv record readers). Run any with
`--help`.

## Index

The table below is **generated** from the modules themselves — each script's
docstring, its `PHASE` constant, and the flags its own `--help` reports — by
`python3 tools/gen_docs.py`, and CI fails if it is stale. The same block appears
in `tools/README.md` and `PLAYBOOK.md`, so the three cannot disagree.

<!-- BEGIN GENERATED TOOL INDEX (python3 tools/gen_docs.py — do not edit by hand) -->
| Script | Phase | Purpose | Flags |
|---|---|---|---|
| `verify.py` | 3 | Verify a list of citations against PMC / PubMed / CrossRef / arXiv. | `--citations` `--email` `--key` `--out` `--rows` `--sleep` |
| `references.py` | 3f | Canonical reference builder — make EVERY reference perfect, in both modes. | `--asof` `--audit` `--email` `--key` `--out` `--repair` `--rows` `--sleep` |
| `sentence_case.py` | 3f | Post-canon pass — propose strict APA-7 sentence case for reference titles. | `--apply` `--out` `--proper` `--rows` `--vocab` |
| `download.py` | 4 (opt-in) | Multi-source PDF downloader (Phase 4 — OPT-IN, not run by default). | `--email` `--manual-list` `--out-dir` `--papers` `--sleep` |
| `reconcile_downloads.py` | 4 (opt-in) | Reconcile manually-downloaded PDFs against a slug+title+doi manifest. | `--downloads-dir` `--dry-run` `--manifest` `--out-dir` `--since-hours` |
| `spreadsheet.py` | 5 | Build/rebuild the bibliography xlsx from a JSON of accumulated rows. | `--out` `--rows` `--sheet-name` |
| `citations.py` | 5b | Fetch citation counts for a bibliography from OpenAlex + Semantic Scholar. | `--asof` `--email` `--key` `--out` `--rows` `--sources` |
| `xref.py` | 6 | Build a cross-citation index from a list of papers. | `--email` `--exclude` `--internal-out` `--key` `--min-cites` `--out` `--papers` `--resolve-unknown` `--rows` `--sleep` |
| `families.py` | 6b | Phase 6b — validate an LLM-proposed family taxonomy against the bibliography, stamp `family` onto rows.json, and emit families.json (the reproducible cache) + families.md (grouped tables + a family x topic cross-tab). | `--asof` `--assign` `--digest` `--md` `--out` `--rows` |
| `families_figure.py` | 6b | Phase 6b — render the interactive HTML lineage figure of the theoretical families. | `--emphasize-source` `--families` `--internal` `--lab-author` `--max-labels` `--min-year` `--motif-min` `--no-auto-landmarks` `--no-raster` `--out-prefix` `--per-family` `--rows` `--spec` `--time-warp` `--title` `--xlsx` |
| `cite_check.py` | 7 | Phase 7 gate — every in-text citation must name a paper in rows.json. | `--content` `--key` `--quiet` `--rows` |
| `review_paper.py` | 7 | Phase 7 — build a review ARTICLE (.docx) from a finished review corpus. | `--content` `--figure` `--out` `--rows` |
| `lab_corpus.py` | L1 | Lab mode — Phase L1: ingest a lab's full publication corpus from OpenAlex. | `--author` `--email` `--from-year` `--out` `--search` `--to-year` |
| `common.py` | — | Shared helpers for the literature-review toolkit. | — |
<!-- END GENERATED TOOL INDEX -->

## What each tool decides — the part that is judgment

The index says what a tool *is*; these notes say what it *refuses to guess*.

- **`verify.py`** returns `OK` / `MISMATCH` / `NOT-FOUND` / `ERROR`, and the
  last two are different verdicts: `ERROR` means a lookup could not complete
  (re-run it), `NOT-FOUND` means every lookup completed and nothing matched
  (chase it — likely fabricated). arXiv ids are prefetched in batches so the
  API's rate limit cannot turn real papers into false NOT-FOUNDs. It accepts a
  hand-built citations list **or `rows.json` directly (`--rows`)**.
- **`references.py`** rebuilds every `apa` from its verified DOI/arXiv id;
  `--audit` is a **hard gate** (exit 1 on any defect) that also *warns* on
  near-duplicate rows and on multi-word surnames that may be a mis-split given
  name — both need a human verdict. `--repair` fixes pure string damage
  (markup, Unicode hyphens, `?.`) **offline**, so a retrofit never re-fetches and
  never wipes post-canon hand fixes. Canon and repair stamp each row with
  `canonical_at`, which the write guard in `common.write_rows` honors.
- **`sentence_case.py`** proposes strict APA-7 sentence case and a human
  reviews; per-project proper nouns go in `--proper`, and `--vocab` reviews a
  large corpus by distinct token change rather than by title.
- **`spreadsheet.py`** auto-adds the `Cite` and `Family` columns when rows carry
  them; an unknown `source` value renders white with a warning rather than
  aborting the build.
- **`citations.py`** uses OpenAlex (primary) + Semantic Scholar (secondary),
  reconciles OpenAlex undercounts against S2, and never touches Google Scholar
  (no API, CAPTCHA).
- **`xref.py`** builds the cross-citation table from the corpus's own CrossRef
  reference lists; `--internal-out` emits within-corpus in-degree for the
  figure's landmark selection. Accepts `rows.json` directly (`--rows`).
- **`families.py`** validates an agent-proposed, human-approved family
  taxonomy (exhaustive / exclusive; hard limit 2–9 families, 3–8 recommended)
  and stamps `family` onto rows. Do not cluster embeddings to make families.
- **`families_figure.py`** selects and labels landmark dots **automatically**
  (most-cited per family, within-corpus in-degree, home-lab papers when opted
  in) and prints how many the label cap dropped. Arrows and notes stay editorial
  (`--spec`).
- **`cite_check.py`** is the Phase-7 gate: every in-text citation must name a
  row (exit 1 otherwise); an author-year matching two rows is warned, and APA-7
  §8.19 (name more authors) is the fix.
- **`review_paper.py`** renders the `.docx` mechanics only; its reference list
  is `reference_list(rows)` — the one implementation any HTML page should reuse.
- **`lab_corpus.py`** ingests a lab's corpus from OpenAlex; author-id
  disambiguation is the #1 correctness risk and cuts both ways (merged and
  split ids). Enrich abstracts before classifying.
- **`download.py` / `reconcile_downloads.py`** are opt-in (Phase 4). The
  reconciler's primary strategy is filename ↔ DOI substring, then author + year
  + title overlap on the first page; it refuses to move when uncertain.
- **`gen_docs.py`** regenerates the index above; `--check` is what CI runs.

!!! tip "Read the PLAYBOOK alongside the tools"
    The
    [`PLAYBOOK.md`](https://github.com/gallantlab/literature-review-toolkit/blob/main/PLAYBOOK.md)
    is the operating manual the agent follows — it documents the order, the
    guardrails, and the hard-won lessons (mojibake handling, compound-surname
    fixes, OpenAlex undercount tells, and more) that the scripts encode.
