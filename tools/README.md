# Literature review scripts

One script per phase of [`PLAYBOOK.md`](../PLAYBOOK.md), plus the shared helper
module `common.py`. Each script is standalone: it reads JSON and writes JSON or a
file. Read the playbook first for the order of phases; this page covers each
script's inputs and behavior. For the commands in pipeline order, see
[§5 of the manual](https://gallantlab.org/literature-review-toolkit/manual/#5-the-shared-backbone).

NCBI and CrossRef require a contact email. Export `LITREVIEW_EMAIL` once, or pass
`--email` to each script.

## Index

`gen_docs.py` generates this table from each script's docstring, `PHASE` constant
and `--help` flags. The same table appears in `docs/tools.md` and `PLAYBOOK.md`,
and CI fails if any copy is stale.

<!-- BEGIN GENERATED TOOL INDEX (python3 tools/gen_docs.py — do not edit by hand) -->
| Script | Phase | Purpose | Flags |
|---|---|---|---|
| `merge_lanes.py` | 2c | Merge search-lane files into rows.json, and fail when a paper fell between lanes. | `--allow-v1` `--append` `--force` `--into` `--out` `--raw` `--report` |
| `verify.py` | 3 | Verify a list of citations against PMC / PubMed / CrossRef / DataCite / arXiv. | `--asof` `--citations` `--email` `--key` `--no-stamp` `--only` `--out` `--override` `--reason` `--retry-from` `--retry-wait` `--rows` `--sleep` |
| `handcheck.py` | 3e | Hand-check the references that have no DOI or arXiv id (books, reports, essays). | `--adopt-dois` `--asof` `--email` `--ingest` `--input` `--key` `--prepare` `--rows` |
| `references.py` | 3f | Canonical reference builder — make EVERY reference perfect, in both modes. | `--acks` `--asof` `--audit` `--candidates` `--email` `--key` `--list-acks` `--only` `--out` `--repair` `--retry-wait` `--rows` `--sleep` |
| `sentence_case.py` | 3f | Post-canon pass — propose strict APA-7 sentence case for reference titles. | `--apply` `--include-foreign` `--out` `--proper` `--rows` `--vocab` |
| `download.py` | 4 (opt-in) | Multi-source PDF downloader (Phase 4 — OPT-IN, not run by default). | `--email` `--manual-list` `--out-dir` `--papers` `--sleep` |
| `reconcile_downloads.py` | 4 (opt-in) | Reconcile manually-downloaded PDFs against a slug+title+doi manifest. | `--downloads-dir` `--dry-run` `--manifest` `--out-dir` `--since-hours` |
| `spreadsheet.py` | 5 | Build/rebuild the bibliography xlsx from a JSON of accumulated rows. | `--acks` `--candidates` `--draft` `--key` `--out` `--rows` `--sheet-name` |
| `citations.py` | 5b | Fetch citation counts for a bibliography from OpenAlex + Semantic Scholar. | `--asof` `--email` `--key` `--out` `--rows` `--sources` |
| `abstracts.py` | 5c | Fetch the abstract of every row, in batches, into abstracts.json. | `--email` `--key` `--out` `--rows` |
| `summary_audit.py` | 5c | Check every row's summary against its abstract, by checking agents with no web access. | `--abstracts` `--asof` `--batch` `--dir` `--ingest` `--key` `--prepare` `--recheck` `--rows` |
| `candidates.py` | 6 | The candidate ledger: every paper xref or forward citations suggest gets a recorded decision. | `--add` `--asof` `--decide` `--decision` `--export-included` `--lane` `--ledger` `--list` `--reason` `--rows` `--source` |
| `forward.py` | 6 | Find papers that cite the corpus's landmark papers but are not in the corpus. | `--allow-incomplete` `--email` `--internal` `--key` `--landmarks` `--min-shared` `--out` `--per-landmark` `--rows` |
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

## Phase 3: `verify.py`

Checks every citation against the literature databases. Search agents get about
25% of citations wrong (authors, years, or the whole paper), so nothing enters
the spreadsheet unverified.

```bash
python3 tools/verify.py --rows rows.json --out report.json            # from the live table
python3 tools/verify.py --citations cits.json --out report.json       # from a citation list
```

**Input.** With `--rows`, every field is derived from `rows.json`: the key from
`ref`, the DOI from `link`, and the expected author, year and title from `apa`.
A `--citations` list has one object per item: `{label, pmcid?, pmid?, doi?,
arxiv?, title?, expect_first_author?, expect_year?}`.

**Lookup order.** arXiv papers (an `arxiv` id or a `10.48550/arXiv.<id>` DOI) go
to the arXiv API, fetched in batches because per-paper calls trigger a temporary
ban. Everything else tries PMC, PubMed, CrossRef, then a title search. A journal
DOI CrossRef does not hold (Zenodo, figshare, OSF, Dryad software/data-set
deposits) is checked against DataCite next, on a CrossRef 404 only; resolving
there counts the same as resolving in CrossRef, and a 404 from both registries is
"does not resolve" even when the DataCite fetch fell back to curl. The
first-author check compares whole words ("Tang" matches "Tang J"), either way
round, ignoring initials and a leading "The"; one part of a hyphenated surname is
enough ("Hanna" matches "Andrews-Hanna J"). A claim written "Smith J" is read as
the surname Smith.

**Verdicts.**

| Verdict | Meaning | Action |
|---|---|---|
| `OK` | the record matches | none |
| `MISMATCH` | the record disagrees on author, year or title | fix or drop the row |
| `NOT-FOUND` | every lookup completed and none matched | chase it; likely fabricated |
| `ERROR` | a lookup could not complete (rate limit, network) | re-run |

A malformed row becomes `ERROR` without aborting the batch. When the DOI lookup
errors, a non-matching title-search hit also yields `ERROR`, never `MISMATCH`.

## Phase 3f: `references.py`

Rebuilds every reference from its verified DOI or arXiv id, so no reference text
comes from an agent's memory or from a database's abbreviated metadata. Used in
both modes.

```bash
python3 tools/references.py --rows rows.json --out rows.json
python3 tools/references.py --rows rows.json --audit        # exit 1 on any defect
python3 tools/references.py --rows rows.json --repair       # offline retrofit, in place
```

**Input.** Per row: a key (`ref` or `label`), a DOI (`doi` field or a
`https://doi.org/` link) and/or an `arxiv` id, and an optional `venue` fallback.
When a row has both a journal DOI and an arXiv id, the journal DOI wins: a
published paper is cited by its version of record.

**Output.** APA-7 from CrossRef or the arXiv API:

- full author lists (more than 20 authors: first 19, ellipsis, last);
- correct initials and name particles (`de Heer`), fixed casing
  (`ANDERSON` → `Anderson`);
- unescaped HTML, with all-caps titles sentence-cased;
- a real venue, including preprint servers CrossRef leaves blank (`bioRxiv`,
  `PsyArXiv`, `arXiv`, or arXiv's `journal_ref` when present);
- a DataCite-registered software/data-set/preprint DOI CrossRef does not hold
  (Zenodo, figshare, OSF, Dryad): `Authors (Year). Title (Version v)
  [Data set|Computer software|Preprint]. Publisher.`, with the bracket and
  version omitted when DataCite has none. A creator with no given name is split
  when safe ("Jagroop Singh Doad" or "Doad J S" → "Doad, J. S."; a `familyName`
  is always kept as the surname), never into a one-letter surname; one kept whole is flagged
  `datacite-unsplit-author:<name>`, and a record that is not software or a data
  set is flagged `datacite-deposit`. Both are stored as the row's
  `canon_warnings` and must be acknowledged in the audit.

**`--audit` fails on** a missing author or year, `et al.`, an HTML entity or
markup tag, `?.` or `!.`, a U+2010/U+2011 hyphen, a malformed initial (`L. (.`,
`J. -.`), `U+FFFD` mojibake, a truncated or empty venue, or an uppercase title. A
DOI-less book or report is the one non-fatal case; it is listed for checking by
hand.

**`--audit` warns on** (exit status unaffected; each needs a human verdict):

- **near-duplicate titles**, usually a preprint and its published version with
  different DOIs. Keep the version of record and re-check any in-text citation
  whose year changes;
- **multi-word surnames**, which may be real (`Lambon Ralph`) or given names
  CrossRef folded into the surname (`Thomas Yeo`). A leading initial in the
  surname (`A. Moffat`) is unambiguous and repaired automatically;
- **one-letter surnames** (`S, D. J.`), almost always an initial split off as the
  surname; acknowledge a real one (`O`) as `single-letter-surname:<name>`;
- **a footnote digit glued to the title**;
- **a deposit-year conflict**, where the DOI encodes a different year (back-file
  digitization re-dates old papers);
- **a cached `year` field that disagrees with `apa`**.

**Mojibake is flagged, not fixed**, because the original character is lost. Fix
it by hand, last: re-canonicalizing reintroduces it.

**`--repair`** fixes pure string damage (markup, Unicode hyphens, `?.`) without
re-fetching, so hand fixes (sentence casing, mojibake, compound surnames) survive.
Use it on an old corpus instead of a full re-run. Both modes stamp each row with
`canonical_at`, which `common.write_rows` checks before overwriting.

## Phase 3f: `sentence_case.py`

Proposes APA-7 sentence case for titles; a human reviews. `references.py` does
not impose sentence case, because doing it correctly requires knowing which words
are proper nouns, and a mis-cased proper noun passes the audit.

```bash
python3 tools/sentence_case.py --rows rows.json --proper proper_nouns.json --vocab
python3 tools/sentence_case.py --rows rows.json --proper proper_nouns.json --apply
```

- **Protected automatically:** all-caps acronyms, tokens with digits, camelCase,
  a lone capital inside a compound (`ACAM-J`), and the first word of the title and
  of any subtitle. Each part of a hyphenated word is judged separately.
- **`--proper`** takes `{"words": [...], "phrases": [...]}`. Phrases let a generic
  word lowercase while a named entity keeps it (`yoga practitioners`, but
  `Sahaja Yoga`). A DataCite deposit's `(Version …)` and bracket descriptor
  (`[Data set]`, `[Computer software]`, `[Preprint]`) are not part of the title
  and are never cased, so they need no entry here.
- **`--vocab`** groups the proposed changes by distinct word instead of by title.
  On a large corpus, hundreds of title diffs collapse into a short list where a
  mis-cased proper noun stands out.
- **Non-English titles are skipped** and listed; `--include-foreign` overrides.

## Phase 4 (opt-in): `download.py` and `reconcile_downloads.py`

PDF download runs only when the user asks.

```bash
python3 tools/download.py --papers list.json --out-dir papers/topic_X/ \
        --manual-list papers/topic_X/_needs_manual.txt
python3 tools/reconcile_downloads.py --manifest papers/topic_X/_manifest.json \
        --out-dir papers/topic_X/
```

**`download.py`** tries arXiv, then Unpaywall (non-PMC URLs first), then
EuropePMC. It checks each file starts with `%PDF`, skips hosts known to block
scripts (PMC direct, bioRxiv, PNAS, OUP, MIT Press, Wiley, Cell), and writes
failures to the manual list. Input: `[{slug, doi?, arxiv?, pmcid?}]`.

**`reconcile_downloads.py`** files PDFs the user downloaded by hand from
`~/Downloads` (or `--downloads-dir`). It matches filename to DOI, then author,
year and title on the first page, renames each file to its slug, and refuses to
move any file it is unsure of. Manifest: `[{slug, title, first_author, year,
doi}]`. Requires `pdftotext` (`brew install poppler`).

## Phase 5: `spreadsheet.py`

Builds the `.xlsx` from the full rows JSON. Always rebuild from scratch; the
writer cannot edit an existing file.

```bash
python3 tools/spreadsheet.py --rows rows.json --out bibliography.xlsx
```

**Input.** Per row: `{topic, ref, apa, link, summary, tag, pdf, xref, source}`.
`link` is always `https://doi.org/<doi>`; `pdf` is empty unless Phase 4 ran.

**Row color by `source`:** white = cited in the source document, cream = search,
green = cross-citation, blue = lab, lilac = antecedents. An unknown source
renders white with a warning. Rows carrying `cite_openalex`/`cite_s2` add two
`Cite` columns after `Tag`; rows carrying `family` add a `Family` column.

## Phase 5b: `citations.py`

Fetches citation counts by DOI from OpenAlex (primary) and Semantic Scholar
(secondary; set `S2_API_KEY` to avoid rate limits). Google Scholar has no API and
blocks scripts, so it is not used.

```bash
python3 tools/citations.py --rows rows.json --out citation_counts.json --asof 2026-06-07
```

Reads the DOI from a `doi` field or a DOI link; arXiv DOIs are mapped to arXiv
ids for S2. OpenAlex's batch endpoint sometimes returns a low-count duplicate
record, so the script keeps the highest count per DOI and re-queries the
single-work endpoint when OpenAlex is far below S2. Still, check that no famous
old paper shows a single-digit count. Attach the counts to rows as
`cite_openalex` and `cite_s2` (`common.attach_counts`), then rebuild the
spreadsheet.

## Phase 6: `xref.py`

Finds papers the corpus cites often but does not contain. For each paper with a
DOI, it fetches the reference list from CrossRef and counts cited DOIs.

```bash
python3 tools/xref.py --rows rows.json --out xref.json --exclude existing_dois.json \
        --min-cites 4 --resolve-unknown --internal-out internal_citations.json
```

- **Input:** `--rows` (key from `ref`, DOI from `link`) or `--papers` with
  `[{slug, doi?, pdf?}]`. For papers without CrossRef references, it extracts
  DOIs from the PDF with `pdftotext`.
- **`--resolve-unknown`** looks up titles for unknown DOIs (slow).
- **`--internal-out`** writes how often each corpus paper is cited by the others,
  which the figure uses to pick landmarks.

## Phase 6b: `families.py`

Validates a theoretical grouping and stamps it onto the rows. On every review the
agent proposes families and pitches the timeline built from them (see
`family_prompt_template.md`); the user uses the families, changes them, or skips
the timeline. This script does the deterministic half.

```bash
python3 tools/families.py --rows rows.json --digest                  # corpus digest for the proposal
python3 tools/families.py --rows rows.json --assign families_input.json --out families.json
```

**Input** (`families_input.json`): `{principle, families: [{key, name, claim,
lineage}], assignments: {ref: key}}`. Assignment values match case-insensitively,
by `key` or by display `name`, so you can re-run from the `family` field already
stamped into `rows.json`.

**Fails** unless every paper is assigned, every assigned ref exists, and there are
2–9 families (3–8 recommended). **Warns** on a single-paper family or one holding
more than 60% of the corpus; empty families are dropped.

**Output:** `family` on each row, `families.json` (the reproducible cache) and
`families.md` (tables by family plus a family × topic cross-tab). Do not build
families by clustering embeddings; theoretical families cut across textual
similarity.

## Phase 6b: `families_figure.py`

Renders the lineage timeline, which the agent offers on every review: a
self-contained interactive `.html`, a standalone `.svg`, and `.png` and `.pdf` if
`rsvg-convert` or `inkscape` is installed.

```bash
python3 tools/families_figure.py --rows rows.json --families families.json \
        --out-prefix mytopic_families --title "My topic — theoretical families"
```

The defaults are the standard settings, so this short command is the standard
render: dots sized by citation count, `internal_citations.json` read from beside
`rows.json`, and the exact arguments written to `figure_render_args.txt` when that
file is missing. An existing file holds hand-written tuning notes and is never
overwritten; the script warns when a render is not recorded in it.

Each family is a lane; each paper is a dot placed by year. Hovering a dot shows
its reference, clicking shows its summary, counts and DOI, and hovering a lane
title shows the family's claim and lineage.

- **Landmarks are automatic:** the most cited per family (`--per-family`,
  default 4), papers cited by at least `--motif-min` corpus papers (from
  `internal_citations.json`, or `--internal`), and home-lab papers. `--max-labels` (default 28) caps the total.
  Each run prints how many labels the cap dropped.
- **Dot size:** area is proportional to citation count by default
  (`--size-by-citations sqrt`), normalized at the 95th percentile; papers with no
  count draw hollow. `log` compresses harder; `none` gives binary dots.
  `--size-range` sets the radius range in pixels.
- **Long time spans:** `--time-warp 0–1` compresses sparse early decades;
  `--min-year` clamps the axis start.
- **Home lab:** off by default. `--lab-author Surname` (repeatable) or
  `LITREVIEW_LAB_AUTHOR` (comma-separated) stars that lab's papers; rows with
  `source == "lab"` are always starred. `--lab-color` sets the ring color (quote
  the `#`).
- **Editorial layer:** `--spec figure_spec.json` (`{labels, arrows, notes, order,
  subtitle}`) adds forced labels, arrows and notes, curated with the user.
- **Other:** `--xlsx` embeds the spreadsheet with a download button;
  `--emphasize-source lab` draws one source's rows large; `--no-raster` skips PNG
  and PDF.

## Phase 7: `cite_check.py`

Gate: every in-text citation must name a row in `rows.json`. `review_paper.py`
prints whatever prose it is given, so without this check a citation to nothing
ships silently.

```bash
python3 tools/cite_check.py --rows rows.json --content content.json
```

Parses parenthetical `(Farb et al., 2007)` and narrative `Farb et al. (2007)` or
`Farb and Segal (2007)` citations, folds accents (`Millière` = `Milliere`), and
matches author-year keys built from `apa`. **Exits 1 on an unresolved citation.**
It warns when one author-year matches two references; fix by naming more authors
(APA-7 §8.19), `(Kral, Davis, et al., 2022)`. Year suffixes (`2025a`) are also
accepted.

## Phase 7: `prose_audit.py`

Measures how readable a review is and proves a rewrite lost no citation.

```bash
python3 tools/prose_audit.py --page build_review_page.py
python3 tools/prose_audit.py --page build_review_page.py --baseline /tmp/before.py
```

- **Input:** `--page`, a review page script with `[[REF]]` markers, or
  `--content`, a `content.json` with APA author-date citations. Blocks are read by
  parsing the file, not by importing it.
- **Report:** words, mean sentence length, and sentences of at least `--long`
  words (default 45) per block. Aim for a mean near 24.
- **`--baseline`** compares the set of cited references with a pre-revision copy
  and exits 1 on any loss.
- **`--overlap`** (default 8) reports block pairs that share that many
  citations, a sign that one argument is made twice.
- `--exclude` skips blocks whose label matches a regex.

## Phase 7: `review_paper.py`

Renders an AI-authored review article as `.docx`. It handles only the mechanics:
title, author and disclosure block, abstract, sections, an embedded figure with
its caption, and an APA-7 reference list built from `rows.json` (deduplicated, hanging
indent, DOI links). References follow APA-7 order: authors letter by letter,
then year, then title, so a sole author precedes that author's co-authored works. Because the references come from the
verified corpus, they cannot drift from the citations.

```bash
python3 tools/review_paper.py --rows rows.json --content content.json \
        --figure my_topic_families.png --out My_Topic_review.docx
```

**Input** (`content.json`, written separately): `{title, authors, author_note?,
affiliation_line?, disclosure?, abstract, sections: [{heading, level,
paragraphs}], figure: {path, caption}, references_heading?, references_note?}`.

When an LLM writes the prose: put the model in `authors` and state in the
disclosure that the bibliography was machine-verified and that the author read
abstracts, not full texts. Run the priority audit (every origin claim cites the
earliest paper) and `cite_check.py` before rendering. HTML pages should reuse
`reference_list(rows)` for their reference lists.

## Phase 7: `bib_viewer.py`

Renders a searchable bibliography grouped by family, for a corpus with no lineage
figure. A review page with the figure does not need it.

```bash
python3 tools/bib_viewer.py --rows rows.json --families families.json \
        --out corpus_viewer.html --title "My topic" \
        --author "<model>" --author-note "<what the model is>"
```

The page includes a note naming who wrote the summaries and stating that they
come from abstracts. `bib_viewer.render()`, `bib_viewer.CSS` and `bib_viewer.JS`
embed the viewer in another page; pass `provenance=False` when the page already
carries the disclosure.

## Lab mode L1: `lab_corpus.py`

Pulls a lab's full publication list from OpenAlex by author id.

```bash
python3 tools/lab_corpus.py --search "Jack Gallant"        # find the author id
python3 tools/lab_corpus.py --author A5056348548 --out lab_papers.json
```

Output: title, year, DOI, venue, citations, coauthors and abstract per paper.
Author disambiguation is the main risk: prune the list before theming. Fetch
abstracts from Semantic Scholar or PubMed before classifying; OpenAlex abstracts
are patchy and its topic tags too coarse. The playbook's "Lab mode" section
covers the later steps.

## Other files

- **`search_prompt_template.md`**: the prompt for the Phase 2 search agent. The
  playbook explains each `{PLACEHOLDER}`.
- **`family_prompt_template.md`**: the two-step propose-then-assign prompt for
  Phase 6b.
- **`gen_docs.py`**: regenerates the index above in all three files; `--check`
  exits 1 if a copy is stale.

## Using the toolkit from a project script

Project scripts (row emitters, family assigners, page builders) should import
`common` instead of reimplementing JSON I/O, DOI parsing or the APA parser.
Copies drift: two fixes to `common` once failed to reach project scripts that had
their own versions.

```python
import os, sys
sys.path.insert(0, os.environ.get("LITREVIEW_TOOLS",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                             "literature-review-toolkit", "tools")))
import common

rows = common.load_json("rows.json")
common.attach_counts(rows, common.load_json("citation_counts.json"))
common.write_rows("rows.json", rows)      # refuses to overwrite a canonical table unless force=True
```

`write_rows` enforces "after Phase 3f, `rows.json` is the live table": if the
file on disk carries `canonical_at` stamps, it refuses to let an upstream emitter
replace it.
