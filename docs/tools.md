# Tools reference

Every script lives in
[`tools/`](https://github.com/gallantlab/literature-review-toolkit/tree/main/tools),
is standalone, and is meant to be read and adapted. They share one helper module,
`common.py`, which provides HTTP with backoff, JSON I/O, DOI and arXiv parsing,
the APA builder and parser, and the CrossRef and arXiv record readers. Run any
script with `--help`.

## Index

`tools/gen_docs.py` generates this table from each script's docstring, `PHASE`
constant and `--help` flags, and CI fails if it is stale. The same table appears
in `tools/README.md` and `PLAYBOOK.md`.

<!-- BEGIN GENERATED TOOL INDEX (python3 tools/gen_docs.py — do not edit by hand) -->
| Script | Phase | Purpose | Flags |
|---|---|---|---|
| `verify.py` | 3 | Verify a list of citations against PMC / PubMed / CrossRef / arXiv. | `--citations` `--email` `--key` `--out` `--rows` `--sleep` |
| `references.py` | 3f | Canonical reference builder — make EVERY reference perfect, in both modes. | `--asof` `--audit` `--email` `--key` `--out` `--repair` `--rows` `--sleep` |
| `sentence_case.py` | 3f | Post-canon pass — propose strict APA-7 sentence case for reference titles. | `--apply` `--include-foreign` `--out` `--proper` `--rows` `--vocab` |
| `download.py` | 4 (opt-in) | Multi-source PDF downloader (Phase 4 — OPT-IN, not run by default). | `--email` `--manual-list` `--out-dir` `--papers` `--sleep` |
| `reconcile_downloads.py` | 4 (opt-in) | Reconcile manually-downloaded PDFs against a slug+title+doi manifest. | `--downloads-dir` `--dry-run` `--manifest` `--out-dir` `--since-hours` |
| `spreadsheet.py` | 5 | Build/rebuild the bibliography xlsx from a JSON of accumulated rows. | `--out` `--rows` `--sheet-name` |
| `citations.py` | 5b | Fetch citation counts for a bibliography from OpenAlex + Semantic Scholar. | `--asof` `--email` `--key` `--out` `--rows` `--sources` |
| `xref.py` | 6 | Build a cross-citation index from a list of papers. | `--email` `--exclude` `--internal-out` `--key` `--min-cites` `--out` `--papers` `--resolve-unknown` `--rows` `--sleep` |
| `families.py` | 6b | Phase 6b — validate an LLM-proposed family taxonomy against the bibliography, stamp `family` onto rows.json, and emit families.json (the reproducible cache) + families.md (grouped tables + a family x topic cross-tab). | `--asof` `--assign` `--digest` `--md` `--out` `--rows` |
| `families_figure.py` | 6b | Phase 6b — render the interactive HTML lineage figure of the theoretical families. | `--emphasize-source` `--families` `--internal` `--lab-author` `--lab-color` `--max-labels` `--min-year` `--motif-min` `--no-auto-landmarks` `--no-raster` `--out-prefix` `--per-family` `--rows` `--size-by-citations` `--size-range` `--spec` `--time-warp` `--title` `--xlsx` |
| `bib_viewer.py` | 7 | Render the searchable bibliography viewer every review page embeds. | `--author` `--author-note` `--families` `--out` `--rows` `--subtitle` `--title` |
| `cite_check.py` | 7 | Phase 7 gate — every in-text citation must name a paper in rows.json. | `--content` `--key` `--quiet` `--rows` |
| `prose_audit.py` | 7 | Phase 7 — measure a review's prose and prove a revision pass lost no citation. | `--baseline` `--content` `--exclude` `--long` `--overlap` `--page` `--quiet` |
| `review_paper.py` | 7 | Phase 7 — build a review ARTICLE (.docx) from a finished review corpus. | `--content` `--figure` `--out` `--rows` |
| `lab_corpus.py` | L1 | Lab mode — Phase L1: ingest a lab's full publication corpus from OpenAlex. | `--author` `--email` `--from-year` `--out` `--search` `--to-year` |
| `common.py` | — | Shared helpers for the literature-review toolkit. | — |
<!-- END GENERATED TOOL INDEX -->

## What each tool refuses to guess

- **`verify.py`** returns `OK`, `MISMATCH`, `NOT-FOUND` or `ERROR`. `ERROR` means
  a lookup could not complete (re-run it); `NOT-FOUND` means every lookup
  completed and nothing matched (likely fabricated). arXiv ids are fetched in
  batches so rate limits cannot produce false NOT-FOUNDs. Accepts a citation list
  or `rows.json` (`--rows`).
- **`references.py`** rebuilds every reference from its verified DOI or arXiv id.
  `--audit` exits 1 on any defect and warns on near-duplicate rows and possibly
  mis-split surnames, which need a human verdict. `--repair` fixes string damage
  (markup, Unicode hyphens, `?.`) offline, without re-fetching or undoing hand
  fixes. Both stamp rows with `canonical_at`, which `common.write_rows` refuses
  to overwrite.
- **`sentence_case.py`** proposes APA-7 sentence case for a human to review.
  Project proper nouns go in `--proper`; `--vocab` reviews a large corpus by
  distinct word change rather than title by title.
- **`spreadsheet.py`** adds the `Cite` and `Family` columns when rows carry them.
  An unknown `source` renders white with a warning instead of failing.
- **`citations.py`** uses OpenAlex, corrects its undercounts against Semantic
  Scholar, and never queries Google Scholar (no API).
- **`xref.py`** builds the cross-citation table from the corpus's CrossRef
  reference lists. `--internal-out` writes within-corpus citation counts for
  the figure's landmark selection. Accepts `rows.json` (`--rows`).
- **`families.py`** validates an agent-proposed, human-approved grouping: every
  paper in exactly one family, 2–9 families (3–8 recommended). Never build
  families by clustering embeddings.
- **`families_figure.py`** draws the timeline offered on every review. Its
  defaults are the standard settings: dots sized by citation count, internal
  citations read from beside `rows.json`, and the arguments recorded in
  `figure_render_args.txt` when that file is missing (never overwritten).
  Landmarks are chosen automatically (most cited per family, most cited within
  the corpus, home-lab papers when opted in), and each run prints how many
  labels the cap dropped. Arrows and notes stay editorial (`--spec`).
- **`bib_viewer.py`** renders a searchable, family-grouped bibliography for a
  corpus with no lineage figure, with a note on who wrote the summaries.
- **`cite_check.py`** exits 1 if an in-text citation matches no row, and warns
  when one author-year matches two (name more authors, APA-7 §8.19).
- **`prose_audit.py`** reports sentence length per block; `--baseline` exits 1 if
  a revision lost a citation.
- **`review_paper.py`** renders the `.docx` only. Its reference list comes from
  `reference_list(rows)`, in APA-7 order (authors, then year, then title); any
  HTML page should reuse it.
- **`lab_corpus.py`** ingests a lab's corpus from OpenAlex. Author-id
  disambiguation is the main risk: ids can merge different people or split one
  person. Fetch abstracts before classifying.
- **`download.py` / `reconcile_downloads.py`** are opt-in (Phase 4). The
  reconciler matches filename to DOI, then author, year and title on the first
  page, and refuses to move a file when unsure.
- **`gen_docs.py`** regenerates the index above; `--check` is what CI runs.

!!! tip "Read the PLAYBOOK alongside the tools"
    [`PLAYBOOK.md`](https://github.com/gallantlab/literature-review-toolkit/blob/main/PLAYBOOK.md)
    is the procedure the agent follows: phase order, guardrails, and the lessons
    the scripts encode.
