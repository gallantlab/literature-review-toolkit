# Tools reference

Every script lives in
[`tools/`](https://github.com/gallantlab/literature-review-toolkit/tree/main/tools),
runs on its own, and is meant to be read and adapted. All of them import one
helper module, `common.py`. It holds HTTP with backoff, the CrossRef, DataCite
and arXiv record readers, DOI and arXiv parsing, and the APA builder and parser.
It also holds the write guards that refuse to overwrite a canonical or changed
`rows.json`, and the Semantic Scholar pacer that lets the tools sharing one key
run at the same time. Run any script with `--help`.

## Index

`tools/gen_docs.py` generates this table from each script's docstring, `PHASE`
constant and `--help` flags, and CI fails if it is stale. The same table appears
in `tools/README.md` and `PLAYBOOK.md`.

<!-- BEGIN GENERATED TOOL INDEX (python3 tools/gen_docs.py — do not edit by hand) -->
| Script | Phase | Purpose | Flags |
|---|---|---|---|
| `preflight.py` | 0 | Preflight: before any search, check for a newer toolkit, the API keys and the OpenAlex budget. | `--accept` `--email` `--lanes` `--no-update-check` `--offline` `--papers` `--project` `--scale` |
| `lane_briefs.py` | 2 | Render every search lane's brief from one lane spec, so no brief goes out incomplete. | `--spec` |
| `merge_lanes.py` | 2c | Merge search-lane files into rows.json, and fail when a paper fell between lanes. | `--allow-v1` `--append` `--force` `--into` `--no-preflight` `--out` `--raw` `--report` |
| `recall.py` | 2c | Measure a rerun's recall against the old build, and list the papers it missed. | `--key` `--old` `--out` `--rows` `--where` |
| `verify.py` | 3 | Verify a list of citations against CrossRef, DataCite, arXiv, PMC and PubMed. | `--asof` `--citations` `--email` `--key` `--no-stamp` `--only` `--out` `--override` `--reason` `--retry-from` `--retry-wait` `--rows` `--sleep` `--workers` |
| `handcheck.py` | 3e | Hand-check the references that have no DOI or arXiv id (books, reports, essays). | `--adopt-dois` `--asof` `--candidates` `--email` `--ingest` `--input` `--key` `--prepare` `--reason` `--reject` `--rows` |
| `references.py` | 3f | Canon: rebuild each verified row's reference as APA-7 from its DOI or arXiv id, and audit the table. | `--ack` `--acks` `--adopt-published` `--asof` `--audit` `--candidates` `--email` `--hand-fixes` `--key` `--list-acks` `--only` `--out` `--reason` `--repair` `--retry-wait` `--rows` `--sleep` `--workers` |
| `sentence_case.py` | 3f | Post-canon pass: propose strict APA-7 sentence case for reference titles, for a human to review. | `--apply` `--include-foreign` `--out` `--proper` `--rows` `--vocab` |
| `download.py` | 4 (opt-in) | Download open-access PDFs for a list of papers, only when the user asks for them. | `--email` `--manual-list` `--out-dir` `--papers` `--sleep` |
| `reconcile_downloads.py` | 4 (opt-in) | Match PDFs the user downloaded by hand to a slug + title + DOI manifest, and file them. | `--downloads-dir` `--dry-run` `--manifest` `--out-dir` `--since-hours` |
| `spreadsheet.py` | 5 | Build the bibliography .xlsx from rows.json, and refuse a table that fails the audit. | `--acks` `--candidates` `--column` `--draft` `--key` `--out` `--rows` `--sheet-name` |
| `citations.py` | 5b | Fetch citation counts for every row from OpenAlex and Semantic Scholar. | `--asof` `--attach` `--attach-only` `--email` `--key` `--out` `--rows` `--sources` |
| `abstracts.py` | 5c | Fetch each row's abstract into abstracts.json, for the summary check. | `--acks` `--email` `--ingest-missing` `--key` `--out` `--per` `--prepare-missing` `--rows` |
| `summary_audit.py` | 5c | Summary check: agents with no web access confirm each row's summary against its abstract. | `--abstracts` `--asof` `--batch` `--dir` `--ingest` `--key` `--prepare` `--recheck` `--rows` |
| `extract_check.py` | 5d | Gate for numbers extracted from abstracts: batch only checked abstracts, refuse unquoted numbers. | `--abstracts` `--check` `--key` `--only` `--per` `--prepare` `--rows` `--skip-family` `--vocab` |
| `candidates.py` | 6 | The candidate ledger: record a decision on every paper that xref, forward citation or a survey suggests. | `--add` `--asof` `--decide` `--decision` `--email` `--export-included` `--ingest` `--lane` `--ledger` `--list` `--no-fetch` `--per` `--prepare` `--reason` `--rows` `--scope` `--source` |
| `forward.py` | 6 | Find papers that cite the corpus's landmark papers but are not in the corpus. | `--allow-incomplete` `--email` `--internal` `--key` `--landmarks` `--min-shared` `--out` `--per-landmark` `--rows` |
| `xref.py` | 6 | Build a cross-citation index: the DOIs that at least --min-cites corpus papers cite. | `--allow-incomplete` `--cache` `--email` `--exclude` `--internal-out` `--key` `--min-cites` `--no-cache` `--out` `--papers` `--resolve-unknown` `--retry-wait` `--rows` `--sleep` |
| `families.py` | 6b | Validate a family taxonomy, stamp `family` onto rows.json, and write families.json and families.md. | `--asof` `--assign` `--default-from-lanes` `--digest` `--md` `--out` `--per` `--prepare` `--results` `--rows` |
| `families_figure.py` | 6b | Render the interactive lineage timeline of the theoretical families. | `--emphasize-source` `--families` `--internal` `--lab-author` `--lab-color` `--max-labels` `--min-year` `--motif-min` `--no-auto-landmarks` `--no-raster` `--out-prefix` `--per-family` `--rows` `--shape-by` `--shape-legend` `--size-by-citations` `--size-range` `--spec` `--square-if` `--time-warp` `--title` `--triangle-if` `--xlsx` |
| `bib_viewer.py` | 7 | Render a searchable bibliography of the whole corpus, for a page that has no timeline. | `--author` `--author-note` `--families` `--out` `--rows` `--subtitle` `--title` |
| `cite_check.py` | 7 | Gate: every in-text citation in a review must name a paper in rows.json. | `--content` `--key` `--quiet` `--rows` |
| `prose_audit.py` | 7 | Measure a review's prose, and check that a revision pass lost no citation. | `--baseline` `--content` `--exclude` `--long` `--overlap` `--page` `--quiet` |
| `review_paper.py` | 7 | Build a review article (.docx) from a finished review corpus. | `--content` `--figure` `--out` `--rows` |
| `lab_corpus.py` | L1 | Lab mode: fetch a lab's full publication corpus from OpenAlex. | `--author` `--email` `--from-year` `--out` `--search` `--to-year` |
| `lab_lane.py` | L2 | Lab mode, Phase L2: check the lab's record by content, then turn it into lane L. | `--abstracts` `--batch` `--build` `--dir` `--lane` `--out` `--papers` `--pi` `--prepare` `--themes` |
| `common.py` | — | Shared helpers for the literature-review toolkit. | — |
<!-- END GENERATED TOOL INDEX -->

## What each tool refuses to guess

When a tool cannot establish something, it stops or says so; it does not guess.
This section lists, tool by tool, what each one will not decide for you and will
not do silently. [How it works](pipeline.md) gives the full procedure, and each
entry links to its section there.

### Before and during the search

- **`preflight.py`** (Phase 0) leaves the go or no-go decision to the user. It
  exits 2 when a newer toolkit is on GitHub, `LITREVIEW_EMAIL` is unset, a key is
  missing or rejected, or today's OpenAlex budget is short. For a key or budget
  problem, it prints three choices: get the API keys, cap the search, or be
  prepared to wait. It prints the update command but never installs anything. It
  records the outcome, and the user's choice (`--accept`), in the project's
  `preflight.json`. For a build already under way, pass `--no-update-check`.
  See [Run the preflight](search.md#run-the-preflight-phase-0).
- **`lane_briefs.py`** (Phase 2) does not let a brief go out incomplete, or out of
  step with the search scale. It refuses a spec with a missing field, a repeated
  key, a seed that names an author, no antecedent lane, or more or fewer lanes
  than the scale allows. After the user chose at the preflight to cap the search,
  it refuses an uncapped scale. It never writes a brief with anything left
  unfilled. See [Write the lane spec](search.md#write-the-lane-spec-phase-2).
- **`merge_lanes.py`** (Phase 2c) does not build a table before the preflight. It
  refuses to run without a recent, cleared `preflight.json`, unless
  `--no-preflight "reason"`, and it keeps the reason. It never merges two rows on
  title and year alone. They count as one paper only when the lanes' claimed
  authors and years agree and the rows carry no two different journal DOIs.
  Otherwise it keeps both rows and reports a possible pair.
    - It writes `merge_report.json` but no `rows.json`, and exits 1, on a lost or
      unconfirmed deferral, a paper with no DOI, arXiv id or APA string, or, in a
      capped search, a lane over its cap.
    - It flags a thin lane: one under 60% of its target, or out of search budget.
    - It refuses to overwrite a canonical `rows.json` without `--force`, and to
      read a schema-1 lane file without `--allow-v1`.
    - `--append` never changes an existing row, and refuses an empty `--into`.

    See [Write the lane spec](search.md#write-the-lane-spec-phase-2).
- **`recall.py`** (Phase 2c, reruns) does not decide a missed paper. It lists
  each old paper the rerun lacks as input for one recovery lane, whose agent
  decides it again from the landing page: the old reference is a pointer, not a
  claim. See [Upgrade an old corpus](reruns.md#upgrade-an-old-corpus).

### Verification and canon (Phase 3)

- **`verify.py`** does not treat a resolving DOI as proof of the paper.
    - A journal DOI must resolve in its own registry: CrossRef, or DataCite after
      a CrossRef 404. A DOI that resolves in neither is a `MISMATCH`, even when a
      title search finds the claimed paper.
    - The record must match the lane's claim on first author, year (±1) and title.
      A row with no claim to check is `UNCHECKED`, not `OK`.
    - A record's first author counts only when the registry deposited it
      structured, as family and given name. Otherwise the verdict is `MISMATCH`,
      with "confirm by hand".
    - `ERROR` means a lookup could not complete, not that the paper is fake. To
      re-check only the non-OK rows, pass `--retry-from`.
    - The run exits 0 only when every verdict is `OK`.
    - `--override REF --reason "..."` is refused without an existing stamp,
      without a reason, or when the row's ids changed since it was verified.

    See [Verify every citation](checks.md#verify-every-citation-phase-3).
- **`handcheck.py`** does not treat a reference with no DOI or arXiv id as
  verified. `--prepare` first searches CrossRef and OpenAlex for a DOI the row
  turns out to have. `--adopt-dois` applies a DOI only when exactly one candidate
  was found. `--reject REF --reason "..."` records that every candidate is the
  wrong paper, so the next `--prepare` sends the row to the hand check. `--ingest`
  refuses a result that does not answer the current `--prepare`: the row's `apa`
  changed since, the ref was never prepared, or the result's `apa_sha` echo is
  missing or differs. It exits 1 on any refused or `not-found` result. A later
  edit to the `apa` lapses the check.
  See [Hand-check references with no DOI](checks.md#hand-check-references-with-no-doi-phase-3e).
- **`references.py`** (canon) rebuilds a row only when its verify stamp is OK, or
  overridden, for its current ids. This refusal holds on every table, however old.
  A row it does not rebuild keeps its `apa`, is named, and makes the run exit 1.
  So does a DOI that no registry has, a fetch that fails twice, or a hand fix that
  no longer matches its row.
    - `--audit` is the gate: it exits 1 on any defect. On a gated table, an
      unacknowledged warning fails it too.
    - Its warnings (possible duplicates, suspect surnames, year conflicts,
      DataCite flags) need a human verdict, recorded in `audit_acks.json`.
    - `--list-acks` only lists the unacknowledged warnings. It exits nonzero on
      those, never on a defect.
    - A registry error that canon cannot fix is a hand fix in `hand_fixes.json`,
      re-applied after every write. The audit fails a row whose fix is gone
      (`hand-fix-lost`).
    - `--repair` fixes string damage offline, without re-fetching or undoing
      hand fixes.

    See [Rebuild every reference](checks.md#rebuild-every-reference-phase-3f) and
    [Acknowledge warnings](checks.md#acknowledge-warnings).
- **`sentence_case.py`** only proposes; it writes nothing until `--apply`, and
  `--apply` keeps each hand fix's exact text. It skips titles that look German or
  French unless `--include-foreign`. It never cases a DataCite deposit's
  `(Version …)` or `[Descriptor]`. Proper nouns specific to the corpus go in a
  `--proper` file.
  See [Rebuild every reference](checks.md#rebuild-every-reference-phase-3f).

### Counts, summaries and the spreadsheet (Phases 5 to 5c)

- **`citations.py`** never queries Google Scholar, which has no API. OpenAlex is
  the primary source and Semantic Scholar the cross-check. When the OpenAlex
  count is far below Semantic Scholar's, it re-queries OpenAlex's single-work
  endpoint and keeps the higher count. A re-run keeps an earlier count that its
  own lookup lost. A row with neither a DOI nor an arXiv id gets no count. It
  leaves `rows.json` alone unless you pass `--attach` or `--attach-only`.
  See [Fetch citation counts](checks.md#fetch-citation-counts-phase-5b).
- **`abstracts.py`** does not take a journal's boilerplate, a citation line or an
  author list for an abstract: it refuses the text and tries the next source. It
  does not count a failed fetch as a missing abstract. It lists failures in
  `abstracts_failed.json`, and `summary_audit.py --prepare` refuses those rows.
  An entry is fetched again when the row's ids change. A hand-added entry
  (`"source": "landing-page"`) is never overwritten; when its ids no longer match
  the row, it is reported as stale. The run exits 1 on any failed fetch or stale
  entry.
  See [Check every summary](checks.md#check-every-summary-phase-5c).
- **`summary_audit.py`** does not judge a summary itself. It writes batches for
  checking agents with no web access, and `--ingest` binds each verdict to what
  that agent saw. It refuses a result when the summary, the row's ids or the
  abstract changed since `--prepare`, or when it does not echo its batch entry's
  `summary_sha`. An `unsupported` summary is a defect, and so is a
  `wrong-abstract` verdict: the abstract on file is not the paper's. A row with no
  abstract is a `no-abstract` warning to acknowledge. On a gated table, a row with
  no summary at all fails the audit (`no-summary`).
  See [Check every summary](checks.md#check-every-summary-phase-5c).
- **`spreadsheet.py`** is the release gate. It runs the same audit as
  `references.py --audit`, and writes nothing for a failing gated table.
  `--draft` writes `<out>_DRAFT.xlsx` with a banner instead, which is never the
  deliverable. A legacy table is written with its findings printed. A malformed
  `candidates.json` is refused on any table, draft or not. An unknown `source`
  renders white, with a warning. The "Considered and excluded" sheet lists each
  excluded candidate and each lane exclusion, with its reason.
  See [Build the spreadsheet](deliverables.md#build-the-spreadsheet-phase-5).

### Finding missed papers (Phase 6)

- **`xref.py`** does not report a partial tally as complete. When any reference
  list could not be fetched, it exits 1 unless `--allow-incomplete`. Either way
  it writes `<out>.run.json` beside `--out`, which the candidate ledger reads.
  For an arXiv paper, or one whose CrossRef record has no reference list, it asks
  Semantic Scholar. Each completed list is cached in `<out>.refs.json`, so a
  re-run after a throttled pass fetches only the lists still missing.
  See [Find missed papers](checks.md#find-missed-papers-phase-6).
- **`forward.py`** exits 1 when any landmark pull failed, unless
  `--allow-incomplete`, and writes the same run record. Because each pull is
  ordered by citation count, recent papers are under-represented; the output says
  so. It cannot recognize a corpus row with no DOI, so that row may come back as a
  candidate. It ranks landmarks by within-corpus in-degree, then citation count.
  So run it after `xref.py --internal-out` and after the counts are attached; it
  warns when either is missing.
  See [Find missed papers](checks.md#find-missed-papers-phase-6).
- **`candidates.py`** does not let a suggested paper drop out unseen. Each
  candidate needs a decision:
  `--decide DOI --decision include|exclude --reason "..."`. The audit fails while
  any candidate is pending, or while an included one is missing from the table.
  `--add` refuses a run record written by the other tool, and records a missing
  one as incomplete. On a gated table, a missing ledger is a warning to
  acknowledge. So is a missing or incomplete xref or forward run, or a partial
  one that read fewer rows than the table has (not counting the candidates the
  passes added). A malformed ledger is refused by name rather than crashing the
  audit.
  See [Find missed papers](checks.md#find-missed-papers-phase-6).

### Families and the timeline (Phase 6b)

- **`families.py`** does not make the families. An agent proposes them, you
  approve the definitions, and the tool validates the result. Do not cluster
  embeddings to make them. It stops on an unassigned paper, a ref not in
  `rows.json`, an unknown or duplicate family key, or fewer than 2 or more than 9
  families (3–8 recommended). It warns on a one-paper family, or one holding more
  than 60% of the papers. It prints the assignment's hard calls to read before
  rendering, and warns when none are recorded.
  See [Families and the timeline](deliverables.md#families-and-the-timeline-phase-6b).
- **`families_figure.py`** does not cut labels silently. When `--max-labels`
  binds, it prints how many qualifying papers went unlabeled. It never
  overwrites an existing `figure_render_args.txt`, and says when a render is not
  recorded there. A paper with no citation count is drawn hollow, not as zero.
  Arrows and notes stay editorial, in `--spec`; a `labels` map there replaces the
  automatic choice.
  See [Families and the timeline](deliverables.md#families-and-the-timeline-phase-6b) and
  [The timeline looks wrong](troubleshooting.md#the-timeline-hides-landmarks-or-looks-wrong).

### The written review (Phase 7)

- **`bib_viewer.py`** is for a page with no timeline. A review page embeds the
  interactive timeline instead, whose panel already shows each paper's reference
  and summary, so it does not add the viewer. Without `--author`, the page
  carries no note on who wrote the summaries, and the tool warns.
  See [The review web page](deliverables.md#the-review-web-page).
- **`checks/*.mjs`** do not judge a page's interactive code by reading it. They
  run the page's own code against its own data, with Node.js and no browser:
  `verify_bib_filter.mjs` for the viewer's filter, `verify_hover.mjs` and
  `verify_nav_order.mjs` for the timeline's hover panels and Prev/Next order.
  See [The review web page](deliverables.md#the-review-web-page).
- **`cite_check.py`** exits 1 when an in-text citation in `content.json` names
  no row. When one author-year matches two rows, it warns rather than pick one;
  name more authors (APA-7 §8.19).
  See [Write the review](deliverables.md#write-the-review-phase-7).
- **`prose_audit.py`** reports long sentences but does not fail on them. The gate
  is `--baseline`, which exits 1 when a revision lost a citation.
  See [Make the prose readable](deliverables.md#make-the-prose-readable).
- **`review_paper.py`** does not write prose or check citations. It renders the
  `.docx` from `content.json`, so run `cite_check.py` first. Its reference list
  comes from `reference_list(rows)`, in APA-7 order; an HTML page should reuse
  that function. See [Write the review](deliverables.md#write-the-review-phase-7).

### Lab mode, PDFs and maintenance

- **`lab_corpus.py`** does not settle who the author is. An OpenAlex author id
  can merge several people, or one person can be split across ids, and nothing
  fails when a record is missing. To tell ids apart, `--search` prints each one's
  year span and ORCID. Its references come from OpenAlex metadata, so verify and
  canonicalize them as in topic mode. See [Build a lab corpus](search.md#build-a-lab-corpus-lab-mode).
- **`lab_lane.py`** does not classify the lab's record from database tags. Agents
  check each item by content, and `--build` refuses to write lane L while an item
  is unchecked, or an included item is a duplicate or not by the PI. See [Build a lab corpus](search.md#build-a-lab-corpus-lab-mode).
- **`download.py`** and **`reconcile_downloads.py`** run only when you ask for
  PDFs (Phase 4). `download.py` keeps a file only when its bytes are a PDF. The
  reconciler matches filename to DOI first, then author, year and title on the
  first page. When unsure, it leaves the PDF in place; it never overwrites a PDF
  already filed. See [Download PDFs](deliverables.md#download-pdfs-phase-4).
- **`gen_docs.py`** regenerates the index above, so no one edits it by hand.
  `--check` writes nothing and exits 1 when the index is stale; CI runs it. It is
  a maintainer tool, so the index does not list it.
  See [Maintaining this site](maintaining.md).

!!! tip "Read the PLAYBOOK alongside the tools"
    [`PLAYBOOK.md`](https://github.com/gallantlab/literature-review-toolkit/blob/main/PLAYBOOK.md)
    is the procedure the agent follows: phase order, guardrails, and the lessons
    the scripts encode.
