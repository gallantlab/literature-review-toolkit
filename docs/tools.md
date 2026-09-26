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
| `merge_lanes.py` | 2c | Merge search-lane files into rows.json, and fail when a paper fell between lanes. | `--allow-v1` `--append` `--force` `--into` `--out` `--raw` `--report` |
| `verify.py` | 3 | Verify a list of citations against PMC / PubMed / CrossRef / arXiv. | `--asof` `--citations` `--email` `--key` `--no-stamp` `--only` `--out` `--override` `--reason` `--retry-from` `--retry-wait` `--rows` `--sleep` |
| `handcheck.py` | 3e | Hand-check the references that have no DOI or arXiv id (books, reports, essays). | `--adopt-dois` `--asof` `--email` `--ingest` `--key` `--prepare` `--rows` |
| `references.py` | 3f | Canonical reference builder — make EVERY reference perfect, in both modes. | `--acks` `--asof` `--audit` `--candidates` `--email` `--key` `--list-acks` `--only` `--out` `--repair` `--retry-wait` `--rows` `--sleep` |
| `sentence_case.py` | 3f | Post-canon pass — propose strict APA-7 sentence case for reference titles. | `--apply` `--include-foreign` `--out` `--proper` `--rows` `--vocab` |
| `download.py` | 4 (opt-in) | Multi-source PDF downloader (Phase 4 — OPT-IN, not run by default). | `--email` `--manual-list` `--out-dir` `--papers` `--sleep` |
| `reconcile_downloads.py` | 4 (opt-in) | Reconcile manually-downloaded PDFs against a slug+title+doi manifest. | `--downloads-dir` `--dry-run` `--manifest` `--out-dir` `--since-hours` |
| `spreadsheet.py` | 5 | Build/rebuild the bibliography xlsx from a JSON of accumulated rows. | `--acks` `--candidates` `--draft` `--key` `--out` `--rows` `--sheet-name` |
| `citations.py` | 5b | Fetch citation counts for a bibliography from OpenAlex + Semantic Scholar. | `--asof` `--email` `--key` `--out` `--rows` `--sources` |
| `abstracts.py` | 5c | Fetch the abstract of every row, in batches, into abstracts.json. | `--email` `--key` `--out` `--rows` |
| `summary_audit.py` | 5c | Check every row's summary against its abstract, by checking agents with no web access. | `--abstracts` `--asof` `--batch` `--dir` `--ingest` `--key` `--prepare` `--recheck` `--rows` |
| `candidates.py` | 6 | The candidate ledger: every paper xref or forward citations suggest gets a recorded decision. | `--add` `--asof` `--decide` `--decision` `--export-included` `--lane` `--ledger` `--list` `--reason` `--rows` `--source` |
| `forward.py` | 6 | Find papers that cite the corpus's landmark papers but are not in the corpus. | `--email` `--internal` `--key` `--landmarks` `--min-shared` `--out` `--per-landmark` `--rows` |
| `xref.py` | 6 | Build a cross-citation index from a list of papers. | `--allow-incomplete` `--email` `--exclude` `--internal-out` `--key` `--min-cites` `--out` `--papers` `--resolve-unknown` `--retry-wait` `--rows` `--sleep` |
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

- **`merge_lanes.py`** dedups schema-2 lane files by DOI, then arXiv id, then
  normalized title + year; a title+year match alone is treated as the same
  paper only when the lanes' claims agree and the rows do not carry two
  different journal DOIs, otherwise both rows are kept as a possible pair. It
  also title-scores every pair of kept rows after the merge (similarity ≥ 0.9,
  regardless of year or DOI) and lists any close pair as a possible duplicate
  too. Every `deferred` entry must match a merged row (DOI, arXiv id, or a
  symmetric title match confirmed by `first_author`/`year`); a lost deferral
  exits 1, and so does an unconfirmed one (a title-only match whose deferral
  gives neither field). So does a **rejected** paper — no DOI, arXiv id or APA string, so it
  can be neither verified nor hand-checked — give it a DOI/arXiv id or have the
  lane write its full APA string, then re-merge. A lane under 60% of its
  target, or out of search budget, is flagged thin. `--append FILE --into
  ROWS` adds a lane's papers to a table that may already be canonical, never
  touching an existing row.
- **`verify.py`** returns `OK`, `MISMATCH`, `NOT-FOUND`, `ERROR` or `UNCHECKED`.
  `ERROR` means a lookup could not complete (it is retried once in the run, then
  re-checked with `--retry-from`); `NOT-FOUND` means every lookup completed and
  nothing matched (likely fabricated); `UNCHECKED` means the row carried no claim,
  so a resolving DOI proved nothing. A match needs the first author, the year
  (±1) and the title to agree; a journal DOI is verified only by its own CrossRef
  record, so one that does not resolve is a MISMATCH even when a PubMed or title
  search finds the claimed paper. arXiv ids are fetched in batches so rate limits
  cannot produce false NOT-FOUNDs. Accepts a citation list or `rows.json`
  (`--rows`). `--rows` stamps each row as `verified` (verdict, ids, source, date);
  `--override REF --reason "..."` records a cleared false alarm, refused without an
  existing stamp, without a reason, or if the row's ids changed since verification.
- **`references.py`** rebuilds every reference from its verified DOI or arXiv id.
  Its refusal to rebuild an unverified row is unconditional, on every table
  including one predating the gates: an id that changed since verification, or a
  row never verified, keeps its existing `apa` and the run exits 1. `--audit`
  exits 1 on any defect and warns on near-duplicate rows, possibly mis-split
  surnames, a deposit-year conflict, and a cached `year` that disagrees with the
  `apa` — all need a human verdict. `--repair` fixes string damage (markup,
  Unicode hyphens, `?.`) offline, without re-fetching or undoing hand fixes. Both
  stamp rows with `canonical_at`, which `common.write_rows` refuses to overwrite.
  A row whose fetch fails twice is named and the run exits 1; `--only` rebuilds
  just the named rows. `--list-acks` prints every unacknowledged warning as
  `REF<TAB>WARNING_ID<TAB>TEXT` and exits nonzero only on those — never on a
  defect; `--audit` is the actual gate.
- **`sentence_case.py`** proposes APA-7 sentence case for a human to review.
  Project proper nouns go in `--proper`; `--vocab` reviews a large corpus by
  distinct word change rather than title by title.
- **`handcheck.py`** finds and records the hand check a DOI-less row needs, since
  no API can verify it. `--prepare` searches CrossRef/OpenAlex for a DOI the row
  turns out to have; `--adopt-dois` gives a row with exactly one candidate that
  DOI, so it verifies normally; `--ingest` records `confirmed` / `corrected` /
  `not-found` as `hand_verified`, with the source actually checked. A
  `not-found` result exits nonzero.
- **`spreadsheet.py`** adds the `Cite` and `Family` columns when rows carry them.
  An unknown `source` renders white with a warning instead of failing. It also
  runs the same audit as `references.py --audit` and refuses to write a failing
  gated table; `--draft` writes `<out>_DRAFT.xlsx` with a banner instead. A
  candidate marked `"decision": "exclude"` gets its own "Considered and excluded"
  sheet.
- **`citations.py`** uses OpenAlex, corrects its undercounts against Semantic
  Scholar, and never queries Google Scholar (no API).
- **`abstracts.py`** fetches each row's abstract once, from the most authoritative
  source that has it (arXiv, then OpenAlex, then Semantic Scholar, then PubMed),
  recording the ids it was fetched for; an entry for other ids is fetched again,
  except a hand-added entry, which is never overwritten and is reported stale. A
  fetch failure is reported separately from a genuine no-abstract miss, in
  `abstracts_failed.json`, and `summary_audit.py --prepare` refuses those rows.
- **`summary_audit.py`** checks every summary against its abstract, by an agent with
  no web access. `--ingest` records `summary_check` with the row's ids and the
  abstract's hash, keyed to a hash of the summary (a check for other ids lapses),
  so an edited summary is refused (or re-flagged unchecked) rather than trusted on
  its old verdict. A row with no abstract is `no-abstract`, a warning to
  acknowledge; a flagged (`unsupported`) summary is a defect.
- **`xref.py`** builds the cross-citation table from the corpus's CrossRef
  reference lists. For an arXiv DOI, or any paper whose CrossRef record has no
  reference list, it asks Semantic Scholar instead (`S2_API_KEY`), normalizing
  a cited arXiv id to `10.48550/arxiv.<id>`. A paper whose references could not
  be fetched makes the run incomplete and it exits 1 unless
  `--allow-incomplete`. `--internal-out` writes within-corpus citation counts
  for the figure's landmark selection. Accepts `rows.json` (`--rows`).
- **`forward.py`** picks the corpus's landmarks (top in-degree, then citation
  count), pulls the most-cited papers citing each from OpenAlex, and keeps
  those citing at least `--min-shared` corpus papers as candidates. Because
  each pull is citation-ordered, recent papers are under-represented; a corpus
  row with no DOI cannot be excluded from the candidates.
- **`candidates.py`** is the shared ledger for `xref.py` and `forward.py`
  output: `--add` merges candidates in by DOI, keeping every source and score;
  `--decide DOI include|exclude --reason "..."` is required before the audit
  will pass; `--export-included` writes a schema-2 lane file for
  `merge_lanes.py --append`. The audit fails while any candidate is pending, or
  while an `include`d one is missing from the table, and a gated table with no
  `candidates.json` at all needs the `no-candidate-ledger` warning acknowledged.
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
