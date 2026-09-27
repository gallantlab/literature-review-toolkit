# Literature review scripts

These are the scripts that run the phases of [`PLAYBOOK.md`](../PLAYBOOK.md),
plus the shared helper module `common.py`. Each script stands alone: it reads
JSON and writes JSON or a file. For the order of the phases, read the playbook
first. This page covers each script's inputs, outputs and gates, one section per
script in phase order; the two lab-mode scripts come last. For the commands in
the order you run them, see
[§5 of the manual](https://gallantlab.org/literature-review-toolkit/manual/#5-the-shared-backbone).

## Before you run anything: email and API keys

NCBI and CrossRef require a contact email. Export `LITREVIEW_EMAIL` once, or pass
`--email` to each script.

Two services ration keyless use. Without `OPENALEX_API_KEY`, everyone behind the
same IP address shares 1,000 OpenAlex credits a day; a free key has its own
10,000. Without `S2_API_KEY`, Semantic Scholar throttles hard. To check both
before a new search, run `preflight.py` (Phase 0). `xref.py`, `citations.py` and
`abstracts.py` share one `S2_API_KEY`. Their requests take turns through a pacer
shared by every process on the machine (a lock file, `common.s2_wait_turn`), so
the three may run at the same time.

## Index

`gen_docs.py` generates this table from each script's docstring, `PHASE` constant
and `--help` flags. The same table appears in `docs/tools.md` and `PLAYBOOK.md`,
and CI fails if any copy is stale.

<!-- BEGIN GENERATED TOOL INDEX (python3 tools/gen_docs.py — do not edit by hand) -->
| Script | Phase | Purpose | Flags |
|---|---|---|---|
| `preflight.py` | 0 | Preflight: before any search, check for a newer toolkit, the API keys and the OpenAlex budget. | `--accept` `--email` `--lanes` `--no-update-check` `--offline` `--papers` `--project` `--scale` |
| `lane_briefs.py` | 2 | Render every search lane's brief from one lane spec, so no brief goes out incomplete. | `--spec` |
| `merge_lanes.py` | 2c | Merge search-lane files into rows.json, and fail when a paper fell between lanes. | `--allow-v1` `--append` `--force` `--into` `--no-preflight` `--out` `--raw` `--report` |
| `recall.py` | 2c | Measure a rerun's recall against the old build, and list the papers it missed. | `--key` `--old` `--out` `--rows` `--where` |
| `verify.py` | 3 | Verify a list of citations against CrossRef, DataCite, arXiv, PMC and PubMed. | `--asof` `--citations` `--email` `--key` `--no-stamp` `--only` `--out` `--override` `--reason` `--retry-from` `--retry-wait` `--rows` `--sleep` |
| `handcheck.py` | 3e | Hand-check the references that have no DOI or arXiv id (books, reports, essays). | `--adopt-dois` `--asof` `--candidates` `--email` `--ingest` `--input` `--key` `--prepare` `--reason` `--reject` `--rows` |
| `references.py` | 3f | Canon: rebuild each verified row's reference as APA-7 from its DOI or arXiv id, and audit the table. | `--acks` `--asof` `--audit` `--candidates` `--email` `--hand-fixes` `--key` `--list-acks` `--only` `--out` `--repair` `--retry-wait` `--rows` `--sleep` |
| `sentence_case.py` | 3f | Post-canon pass: propose strict APA-7 sentence case for reference titles, for a human to review. | `--apply` `--include-foreign` `--out` `--proper` `--rows` `--vocab` |
| `download.py` | 4 (opt-in) | Download open-access PDFs for a list of papers, only when the user asks for them. | `--email` `--manual-list` `--out-dir` `--papers` `--sleep` |
| `reconcile_downloads.py` | 4 (opt-in) | Match PDFs the user downloaded by hand to a slug + title + DOI manifest, and file them. | `--downloads-dir` `--dry-run` `--manifest` `--out-dir` `--since-hours` |
| `spreadsheet.py` | 5 | Build the bibliography .xlsx from rows.json, and refuse a table that fails the audit. | `--acks` `--candidates` `--draft` `--key` `--out` `--rows` `--sheet-name` |
| `citations.py` | 5b | Fetch citation counts for every row from OpenAlex and Semantic Scholar. | `--asof` `--attach` `--attach-only` `--email` `--key` `--out` `--rows` `--sources` |
| `abstracts.py` | 5c | Fetch each row's abstract into abstracts.json, for the summary check. | `--email` `--key` `--out` `--rows` |
| `summary_audit.py` | 5c | Summary check: agents with no web access confirm each row's summary against its abstract. | `--abstracts` `--asof` `--batch` `--dir` `--ingest` `--key` `--prepare` `--recheck` `--rows` |
| `candidates.py` | 6 | The candidate ledger: record a decision on every paper that xref, forward citation or a survey suggests. | `--add` `--asof` `--decide` `--decision` `--export-included` `--lane` `--ledger` `--list` `--reason` `--rows` `--source` |
| `forward.py` | 6 | Find papers that cite the corpus's landmark papers but are not in the corpus. | `--allow-incomplete` `--email` `--internal` `--key` `--landmarks` `--min-shared` `--out` `--per-landmark` `--rows` |
| `xref.py` | 6 | Build a cross-citation index: the DOIs that at least --min-cites corpus papers cite. | `--allow-incomplete` `--cache` `--email` `--exclude` `--internal-out` `--key` `--min-cites` `--no-cache` `--out` `--papers` `--resolve-unknown` `--retry-wait` `--rows` `--sleep` |
| `families.py` | 6b | Validate a family taxonomy, stamp `family` onto rows.json, and write families.json and families.md. | `--asof` `--assign` `--default-from-lanes` `--digest` `--md` `--out` `--results` `--rows` |
| `families_figure.py` | 6b | Render the interactive lineage timeline of the theoretical families. | `--emphasize-source` `--families` `--internal` `--lab-author` `--lab-color` `--max-labels` `--min-year` `--motif-min` `--no-auto-landmarks` `--no-raster` `--out-prefix` `--per-family` `--rows` `--size-by-citations` `--size-range` `--spec` `--time-warp` `--title` `--xlsx` |
| `bib_viewer.py` | 7 | Render a searchable bibliography of the whole corpus, for a page that has no timeline. | `--author` `--author-note` `--families` `--out` `--rows` `--subtitle` `--title` |
| `cite_check.py` | 7 | Gate: every in-text citation in a review must name a paper in rows.json. | `--content` `--key` `--quiet` `--rows` |
| `prose_audit.py` | 7 | Measure a review's prose, and check that a revision pass lost no citation. | `--baseline` `--content` `--exclude` `--long` `--overlap` `--page` `--quiet` |
| `review_paper.py` | 7 | Build a review article (.docx) from a finished review corpus. | `--content` `--figure` `--out` `--rows` |
| `lab_corpus.py` | L1 | Lab mode: fetch a lab's full publication corpus from OpenAlex. | `--author` `--email` `--from-year` `--out` `--search` `--to-year` |
| `lab_lane.py` | L2 | Lab mode, Phase L2: check the lab's record by content, then turn it into lane L. | `--abstracts` `--batch` `--build` `--dir` `--lane` `--out` `--papers` `--pi` `--prepare` `--themes` |
| `common.py` | — | Shared helpers for the literature-review toolkit. | — |
<!-- END GENERATED TOOL INDEX -->

## Phase 0: `preflight.py`

The first step of every new search. It compares this copy with the version on
GitHub and offers the install command. It checks the three environment variables,
probes OpenAlex and Semantic Scholar, reads today's OpenAlex budget, and estimates
what the planned corpus costs.

```bash
python3 tools/preflight.py --project <topic>/ --scale focused
python3 tools/preflight.py --project <topic>/ --scale focused --accept wait   # record the user's choice
python3 tools/preflight.py --project <topic>/ --papers 600 --no-update-check  # a build under way
```

To size the estimate, pass the search scale the user asked for (`--scale`, see
Phase 2; add `--lanes N` when you know the lane count). Or give the corpus size
itself with `--papers N` (default 500). `--offline` checks the environment only,
with no probes and no GitHub check.

**Exit 2 means the user decides before any lane starts.** It stops on a newer
toolkit, a missing `LITREVIEW_EMAIL`, a missing or rejected key, or a short
budget. For a key or budget stop, it prints three choices: get the keys, cap the
search, or be prepared to wait.

**The record.** Every run writes `preflight.json` into `--project` (default: the
current directory); nothing is recorded when that folder does not exist yet.
`merge_lanes.py` refuses to build a table without a record that is under 14 days
old and cleared. A record is cleared when everything passed, or when a rerun with
`--accept` records the user's choice: `cap` or `wait` after a key or budget stop,
`current-version` to keep this toolkit. A missing email cannot be accepted.

## Phase 2: `lane_briefs.py`

Renders every search lane's brief from one spec, so no brief goes out missing the
verification duty, the summary rule or the output contract. Never fill
`search_prompt_template.md` by hand.

```bash
python3 tools/lane_briefs.py --spec <topic>/lanes.json
```

**The spec** gives the bibliography's `title`, who it is `for` and its
`description`, the search `scale`, and `lab` in lab mode (the PI and the lab
lane's key). Per lane it gives a `key`, `name`, `short` (one line for the lane
table), `kind` (`forward` or `antecedent`), `definition`, `exclusions` and
`queries`, and optionally `seeds` (titles only) and its own `target`. The module
docstring has the full format.

**The scale** is the size of search the user asked for (`common.SEARCH_SCALES`).
`scan` and `focused` cap each lane at 15 or 30 papers. `standard` (the default)
and `exhaustive` set floors of 40 and 60. A number of papers is a capped total
spread over the lanes. Each scale also bounds the number of lanes; the
[manual's table](https://gallantlab.org/literature-review-toolkit/manual/#41-topic-mode)
gives the ranges.

**Refusals.** It exits 1, naming every problem, on:

- a missing field, a repeated or malformed key, or a seed that names an author;
- a lane count outside the scale's range, or no antecedent lane (every scale
  needs one);
- lane targets that add up to more than a numeric scale;
- an uncapped scale when `preflight.json` records that the user chose to cap;
- a brief with anything left unfilled.

**Output**, beside the spec: `briefs/brief_<KEY>.md`, `lane_manifest.json`, an
empty `search_raw/`, and a `scratch/<KEY>/` per lane. It prints the plan, the
preflight command sized to it, and the one-line prompt for each search agent.
Keep the spec in the project folder, because the merge reads `lane_manifest.json`
beside `rows.json` to enforce a capped search's caps.

## Phase 2c: `merge_lanes.py`

Merges the search lanes' files into `rows.json`, and fails when a paper fell
between lanes.

```bash
python3 tools/merge_lanes.py --raw search_raw --out rows.json
python3 tools/merge_lanes.py --append recovery.json --into rows.json   # later rows
```

**Input.** One schema-2 lane file per lane, as `search_prompt_template.md`
defines it: `papers`, `deferred` (a hand-off to a named lane, with `first_author`
and `year`), `excluded` (with a reason) and `could_not_confirm`.

**Needs the preflight.** It refuses to run without a recent, cleared
`preflight.json` in the folder of `--out` (Phase 0). `--no-preflight "reason"`
merges anyway, and the reason is kept in `merge_report.json`.

**Dedup.** Papers are matched by DOI, then arXiv id, then title and year. A title
and year match whose claims conflict stays as two rows and is reported as a
possible pair. The merge also reports every other pair of similar titles. A short
title (under four content words) must match on characters there, not on shared
words alone. Each row keeps its lane's claim as `search_author`, `search_year` and
`search_title`, which `verify.py` checks the DOI against.

**Fails** (exit 1, no `rows.json` written) on a deferral that no lane kept, a
deferral matched by title alone with nothing to confirm it, or a paper with no
DOI, arXiv id or APA string. In a capped search, it also fails a lane that
returned more papers than its cap. `merge_report.json` is written either way.

**Also.** The merge flags thin lanes (under 60% of target, or out of search
budget) to resume. Lane exclusions are recorded for the spreadsheet's "Considered
and excluded" sheet. `--append` adds a later lane file to an existing table
without changing any existing row, and refuses an empty `--into`.

## Phase 2c, reruns: `recall.py`

Measures a rerun against the old build, and lists the papers it missed.

```bash
python3 tools/recall.py --rows rows.json --old ../<old>/rows.json --where source=search
```

It matches each old row by DOI, then arXiv id, then title, and prints the recall.
`--where KEY=VALUE` (repeatable) compares only the old rows whose field matches.
The misses go to `recovery_input.json` beside `--rows` (or to `--out`), as the
input for one recovery lane. That lane's agent decides each miss again, with a
claim read off the landing page, because the old reference is a pointer, not a
claim. Add its lane file with `merge_lanes.py --append`.

## Phase 3: `verify.py`

Checks every citation against the literature databases. Search agents have gotten
as many as a quarter of their citations wrong (authors, years, or the whole
paper), so nothing enters the spreadsheet unverified.

```bash
python3 tools/verify.py --rows rows.json --out report.json            # from the live table
python3 tools/verify.py --citations cits.json --out report.json       # from a citation list
python3 tools/verify.py --rows rows.json --retry-from report.json --out report.json   # re-check non-OK rows
python3 tools/verify.py --rows rows.json --override A-07 --reason "retitled on publication"
```

**Input.** With `--rows`, the citations are built from `rows.json`. The key comes
from `ref`, the DOI from `doi` or `link`, and the expected author, year and title
from the search agent's claim (`search_author`, `search_year`, `search_title`).
Once a row is canonical, its `apa` must agree with the record too. A `--citations`
list has one object per item: `{label, pmcid?, pmid?, doi?, arxiv?, title?,
expect_first_author?, expect_year?}`. `expect_first_author` is the author as
reported, in any shape ("Tang J", "J. Tang", "Tang, J.").

**Stamps.** With `--rows`, every verdict is written onto its row as `verified`,
bound to the row's DOI and arXiv id; `--no-stamp` skips this. Canon and the audit
read that stamp. To clear a false alarm, such as a preprint retitled on
publication, record the reason with `--override`.

**Lookup order.** arXiv papers (an `arxiv` id or a `10.48550/arXiv.<id>` DOI) go
to the arXiv API. They are fetched in batches, because per-paper calls trigger a
temporary ban. A journal DOI goes to CrossRef, and only its own record can verify
it. On a clean CrossRef 404, DataCite is tried next, since Zenodo, figshare, OSF
and Dryad register software and data-set deposits there. Resolving in DataCite
counts the same as resolving in CrossRef. PMC, PubMed and a PubMed title search
are fallbacks for a citation with no journal DOI. For a DOI that resolves in
neither registry, a fallback hit gives `MISMATCH` and no hit gives `NOT-FOUND`.

**First author.** The check compares surnames, not initials:

- A record is read by its source's "Family INITIALS" contract: "Collins AGE" is
  Collins, and an arXiv "John Smith" becomes "Smith J".
- A record's first author is trusted only when the registry deposited it
  structured. Any other form is flagged for a human to confirm:
  - a DataCite first creator without both `familyName` and `givenName`, unless it
    is "Family, Given" or an Organizational group;
  - a CrossRef first author with no given name, or a first entry with no family;
  - an arXiv name with a capitalized word ("CHEN Hao");
  - a bare "Hae-Jeong Park" or "Hao CHEN J".
- Accepted as they are: bare records with spaced initials or a comma list ("Kim J
  H", "Chen, Hao H"), and a CrossRef whole name deposited as the family.
- A claim is read once, in whatever shape it was reported. "Smith J", "J. Smith"
  and "Smith, J." all give Smith. Initials of any script ("Ł" or "И") count as
  initials, and a list ("Smith J; Jones K" or "Smith J and Jones K") gives its
  first name. An ambiguous claim, such as "Hao CHEN" or "Collins AGE", is an issue
  to confirm by hand.
- The claim's surname must match a whole word of the record's: "Tang" matches
  "Tang J", "Heuvel" matches "van den Heuvel M", and "Hanna" matches
  "Andrews-Hanna J". "Van Essen" does not match "Van Dijk", nor "Min" "Seung-Min
  Park", nor "Lambon Ralph" "Ralph J". A given-first claim ("John Smith") must
  start with one of the record's initials. A claim led by a capitalized particle
  ("DU Wei") matches only a record that carries the particle.
- A group author ("ATLAS Collaboration", "Stanford University", "Google Research")
  is compared whole. An unknown name on either side ("?", "anon", "unknown", or
  no readable word) is an author issue, never a match.

The year may differ by one from the record (a preprint and its version of record
often do), and the title must agree both ways. `merge_lanes.py` uses the same
author comparison to tell a duplicate from two papers that share a title. It never
merges on, or confirms a deferral by, an unknown author.

**Verdicts.** The exit status is 0 only when every verdict is `OK`.

| Verdict | Meaning | Action |
|---|---|---|
| `OK` | the record matches | none |
| `MISMATCH` | the record disagrees on author, year or title, or the DOI does not resolve | fix or drop the row, or `--override` a false alarm |
| `NOT-FOUND` | every lookup completed and none matched | chase it; likely fabricated |
| `ERROR` | a lookup could not complete (rate limit, network) | re-run (`--retry-from`) |
| `UNCHECKED` | the row carried no author, year or title to check | give it a claim or a canonical `apa` |

A malformed row becomes `ERROR` without aborting the batch. When a PMC or PubMed
lookup fails and the fallback title search returns a paper that does not match,
the verdict is also `ERROR`, not `MISMATCH`.

**Record cache.** verify and canon keep every CrossRef, DataCite and arXiv record they
fetch in `.record_cache/` beside `rows.json` for 14 days, so canon reuses what verify
fetched and a targeted re-run makes almost no requests. Only successful records are
cached, so a missing or failed lookup still reads as NOT-FOUND or ERROR.
`LITREVIEW_RECORD_CACHE=off` turns it off; any other value is used as its folder.

## Phase 3e: `handcheck.py`

No API can verify a row with no DOI or arXiv id (a book, report or essay). So on
a gated table the audit fails such a row until it has a hand-check record.

```bash
python3 tools/handcheck.py --rows rows.json --prepare --email you@inst.edu
python3 tools/handcheck.py --rows rows.json --adopt-dois handcheck_doi_candidates.json
python3 tools/handcheck.py --rows rows.json --reject Y-19 --reason "both candidates are reviews of it"
python3 tools/handcheck.py --rows rows.json --ingest handcheck_result.json
```

**`--prepare`** first searches CrossRef and OpenAlex for a DOI the row lacks (same
title, same year), and lists the rows it finds one for in
`handcheck_doi_candidates.json`. The other rows go to `handcheck_input.json`, with
`handcheck_brief.md` for a checking agent. The agent confirms or corrects each
reference against a library catalog, the publisher, or the work itself.

**`--adopt-dois`** gives each row with exactly one candidate that DOI, so it goes
through `verify.py` instead. When every candidate for a row is the wrong paper,
**`--reject REF --reason "..."`** records that on the row (`doi_rejected`), and
the next `--prepare` sends it to the hand check.

**`--ingest`** records each result on its row as `hand_verified`. Each input entry
carries `apa_sha`, a hash of the reference it shows, and each result must echo it.
So a result is refused when the reference changed after `--prepare`, or when it
answers an older `--prepare`.

## Phase 3f: `references.py`

Rebuilds each reference from its verified DOI or arXiv id, so no reference text
comes from an agent's memory or from a database's abbreviated metadata. Used in
both modes. It rebuilds only a row whose verify stamp is OK for its current ids,
and it names every row it did not rebuild.

```bash
python3 tools/references.py --rows rows.json --out rows.json
python3 tools/references.py --rows rows.json --audit        # exit 1 on any defect
python3 tools/references.py --rows rows.json --list-acks    # warnings still to acknowledge
python3 tools/references.py --rows rows.json --repair       # offline retrofit, in place
```

Canon needs `LITREVIEW_EMAIL` or `--email`. `--audit`, `--list-acks` and
`--repair` make no network request and need neither.

**Input.** Per row: a key (`ref` or `label`), a DOI (`doi` field or a
`https://doi.org/` link) and/or an `arxiv` id, and an optional `venue` fallback.
When a row has both a journal DOI and an arXiv id, the journal DOI wins: a
published paper is cited by its version of record.

**Output.** APA-7 from CrossRef, DataCite or the arXiv API:

- full author lists (more than 20 authors: first 19, ellipsis, last);
- correct initials and name particles (`de Heer`), fixed casing
  (`ANDERSON` → `Anderson`);
- unescaped HTML, with all-caps titles sentence-cased;
- a real venue, including preprint servers CrossRef leaves blank (`bioRxiv`,
  `PsyArXiv`, `arXiv`, or arXiv's `journal_ref` when present);
- for a DataCite-registered software, data-set or preprint DOI that CrossRef does
  not hold (Zenodo, figshare, OSF, Dryad): `Authors (Year). Title (Version v)
  [Data set|Computer software|Preprint]. Publisher.` The bracket and version are
  omitted when DataCite has none. A creator with no given name is split when safe:
  "Jagroop Singh Doad" or "Doad J S" → "Doad, J. S.", and "Kim J-H" → "Kim, J.-H.".
  A `familyName` is the surname when `name` contains it as a whole word. A name is
  never split on trailing initials, into a one-letter surname, or from a 3-4
  letter capitalized word ("Collins AGE", "Hao CHEN"). A creator kept whole is
  flagged `datacite-unsplit-author:<name>`, and a record that is not software or a
  data set is flagged `datacite-deposit`. Both are stored as the row's
  `canon_warnings` and must be acknowledged in the audit.

**`--audit` fails on formatting defects:**

- a missing author or year, or `et al.` in the author list;
- an HTML entity or markup tag, `?.` or `!.`, or a U+2010/U+2011 hyphen;
- a malformed initial (`L. (.`, `J. -.`);
- punctuation glued to the next word, or a `?` where a quote or dash belongs;
- `U+FFFD` mojibake;
- a truncated or empty venue;
- an uppercase title (three or more all-caps words in a row);
- a hand fix that is no longer in the row (`hand-fix-lost`, below).

A DOI-less book or report is not a formatting defect. It is listed for a check by
hand, which a gated table requires (`handcheck.py`).

**`--audit` warns on** the cases that need a human verdict:

- **near-duplicate titles**, usually a preprint and its published version with
  different DOIs. Keep the version of record, and re-check any in-text citation
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

On a legacy table, warnings are only reported. On a gated table, each warning
must be acknowledged, or the audit fails. Record the reason in `audit_acks.json`
(`{ref: {warning_id: reason}}`); `--list-acks` lists the warnings still open.

**Reference gates.** A table is gated once any row carries a verify stamp, or was
built or canonicalized on or after the gates date (`common.GATES_SINCE`). On a
gated table the audit also fails:

- a row with a DOI or arXiv id that is not verified OK for its current ids;
- a DOI-less row with no valid hand check, or whose `apa` changed since it;
- a row with no summary (`no-summary`);
- a summary with no summary check for its current text and ids, one judged
  unsupported, or one checked against an abstract judged not the paper's
  (`abstract-wrong`);
- a `link` that is not the row's DOI;
- a pending candidate in `candidates.json`, or an included candidate that is not
  in the table.

It also adds warnings to acknowledge:

- no candidate ledger;
- an xref or forward run that is missing or did not finish, or that read fewer
  papers than the table now has (not counting the candidates the passes added);
- a row verified only against its own canonical `apa`;
- a verified row that canon could not rebuild;
- each canon warning;
- a summary with no abstract to check it against.

**Hand fixes.** Some damage canon cannot repair, because the registry record
itself is wrong: a compound surname split in two, two authors packed into one, a
missing subtitle or year. Mojibake is flagged, not fixed, because the original
character is lost. Canon re-fetches on every run and would undo a fix typed into
`apa`. So record each fix in `hand_fixes.json` beside `rows.json` (or
`--hand-fixes`):
`{"<ref>": [{"old": "<damaged text>", "new": "<final text>", "why": "<source>"}]}`.
Write `new` in its final form, sentence case included. Canon, `--repair` and
`sentence_case.py --apply` re-apply every fix after they write. Canon exits 1 on a
fix that no longer matches its row, and the audit fails a row whose fix is gone.

**`--repair`** fixes pure string damage (markup, Unicode hyphens, `?.`) without
re-fetching, so earlier hand edits survive. Use it on an old corpus instead of a
full re-run. Canon stamps each rebuilt row with `canonical_at`, which
`common.write_rows` checks before overwriting. `--repair` adds that stamp only on
a legacy table. On a gated table the stamp means "rebuilt from a verified
source", which a string repair is not.

## Phase 3f: `sentence_case.py`

Proposes APA-7 sentence case for titles, for a human to review. `references.py`
does not impose sentence case, because doing it correctly requires knowing which
words are proper nouns, and a mis-cased proper noun passes the audit.

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
- **`--apply`** writes the changes with every fix in `hand_fixes.json`
  re-applied, so each hand fix keeps its exact text (see `references.py` above).
- **Non-English titles are skipped** and listed; `--include-foreign` overrides.

## Phase 4 (opt-in): `download.py`

PDF download runs only when the user asks for it.

```bash
python3 tools/download.py --papers list.json --out-dir papers/topic_X/ \
        --email you@inst.edu --manual-list papers/topic_X/_needs_manual.txt
```

It tries arXiv, then Unpaywall (non-PMC URLs first), then EuropePMC. It keeps a
file only if it starts with `%PDF`, and it skips hosts known to block scripts
(PMC, bioRxiv, medRxiv, PNAS, OUP, MIT Press, ScienceDirect, Wiley, Cell). With
`--manual-list`, it appends the papers it could not fetch to that file. Input:
`[{slug, doi?, arxiv?, pmcid?}]`.

## Phase 4 (opt-in): `reconcile_downloads.py`

Files the PDFs the user downloaded by hand.

```bash
python3 tools/reconcile_downloads.py --manifest papers/topic_X/_manifest.json \
        --out-dir papers/topic_X/
```

It scans `~/Downloads` (or `--downloads-dir`) for PDFs from the last 12 hours
(`--since-hours`). It matches the filename to a DOI, then the author, year and
title on the first page. Each match moves into `--out-dir` as `<slug>.pdf`; a file
it is unsure of stays where it is. `--dry-run` reports without moving anything.
Manifest: `[{slug, title, first_author, year, doi}]`. Requires `pdftotext`
(`brew install poppler`).

## Phase 5: `spreadsheet.py`

Builds the `.xlsx` from the full rows JSON, after running the same audit as
`references.py --audit`. Always rebuild from scratch; the writer cannot edit an
existing file.

```bash
python3 tools/spreadsheet.py --rows rows.json --out bibliography.xlsx
python3 tools/spreadsheet.py --rows rows.json --out bibliography.xlsx --draft   # a marked draft
```

**The audit gates it.** On a gated table, a failing audit writes nothing and
exits 1. `--draft` writes `<out>_DRAFT.xlsx` instead, with a banner saying it is
not a deliverable. A legacy table is written despite the findings.

**Input.** Per row: `{topic, ref, apa, link, summary, tag, pdf, xref, source}`.
`link` is always `https://doi.org/<doi>`; `pdf` is empty unless Phase 4 ran.

**Columns.** Some columns are added after `Tag` only when the rows carry their
data: `Family` (from `family`), two `Cite` columns (from `cite_openalex` and
`cite_s2`), `Verify note` (from `verify_note`), and `Summary checked against`
(from `summary_check`).

**Row color by `source`:** white = cited in the source document, cream = search,
green = cross-citation, forward citation or survey, blue = lab, lilac =
antecedents. An unknown source renders white, with a warning.

**"Considered and excluded" sheet.** It lists every candidate the ledger excluded
and every paper a lane excluded (from `merge_report.json`), each with its reason.

## Phase 5b: `citations.py`

Fetches citation counts by DOI from OpenAlex (primary) and Semantic Scholar
(secondary, best-effort without `S2_API_KEY`). Google Scholar has no API and
blocks scripts, so it is not used.

```bash
python3 tools/citations.py --rows rows.json --out citation_counts.json --attach
python3 tools/citations.py --rows rows.json --out citation_counts.json --attach-only   # attach an existing file
```

It reads the DOI from a `doi` field or a DOI link. An arXiv-only row is counted by
its arXiv DOI, which Semantic Scholar is asked for by arXiv id; a row with neither
id gets no count. OpenAlex's batch endpoint sometimes returns a low-count
duplicate record. So the script keeps the highest count per DOI, and re-queries
the single-work endpoint when OpenAlex is far below Semantic Scholar. Still, check
that no famous old paper shows a single-digit count.

**Attaching.** The spreadsheet and the figure read the counts from the rows.
`--attach` writes them onto `rows.json` as `cite_openalex`, `cite_s2`,
`cite_s2_influential` and `cite_asof`; `--attach-only` attaches an existing
`--out` without fetching. Both refuse a `rows.json` that another tool changed
meanwhile. Rebuild the spreadsheet afterward.

**Re-runs.** A re-run keeps an earlier count where its own lookup came back empty,
since a throttled batch is not "no citations". A spent OpenAlex budget stops the
run with `OpenAlexBudgetError`.

## Phase 5c: `abstracts.py`

Fetches each row's abstract into `abstracts.json` beside `rows.json`, for the
summary check.

```bash
python3 tools/abstracts.py --rows rows.json
```

It tries the arXiv API, then OpenAlex, then Semantic Scholar, then PubMed (by PMID, then by DOI), then Europe PMC. A text
that is boilerplate, a citation line, or an author list and venue is not an
abstract (`abstracts.not_an_abstract`). It is refused and reported, and the next
source is tried.

An entry added by hand (`"source": "landing-page"`) is never overwritten, and one
with an empty `text` records that the paper has no abstract. A fetch that could
not complete goes to `abstracts_failed.json`, and the script exits 1: a failed
fetch is not "no abstract".

## Phase 5c: `summary_audit.py`

Checks every summary against its paper's abstract, with agents that have no web
access, so a summary cannot claim what the abstract does not say.

```bash
python3 tools/summary_audit.py --rows rows.json --prepare
#   checking agents write summary_audit/result_NN.json
python3 tools/summary_audit.py --rows rows.json --ingest
```

**`--prepare`** writes batches of summary and abstract pairs, a brief and a
manifest to `summary_audit/`. It refuses a row whose abstract fetch failed.

**`--ingest`** records `summary_check` on each row, bound to the summary, the
paper's ids and the abstract the agent saw. A result is refused when any of them
changed after `--prepare`. A summary judged unsupported fails the audit until it
is fixed and checked again. So does a "wrong-abstract" verdict, which says the
abstract on file is not this paper's: add the real one as a landing-page entry,
rewrite the summary from it, and check it again. A row with no abstract is a
warning to acknowledge.

## Phase 6: `xref.py`

Finds papers the corpus cites often but does not contain. For each paper, it
fetches the reference list and counts the cited DOIs.

```bash
python3 tools/xref.py --rows rows.json --out xref.json --exclude existing_dois.json \
        --min-cites 4 --resolve-unknown --internal-out internal_citations.json
```

- **Input:** `--rows` (key from `ref`, DOI from `doi` or `link`) or `--papers`
  with `[{slug, doi?, pdf?}]`.
- **Sources:** CrossRef for a journal DOI. Semantic Scholar for an arXiv paper, or
  one CrossRef holds no list for. For a paper with no DOI, the DOIs in its PDF,
  read with `pdftotext`.
- **`--resolve-unknown`** looks up titles for unknown DOIs (slow).
- **`--internal-out`** writes how often each corpus paper is cited by the others.
  The figure and `forward.py` use it to pick landmarks.
- **Cache:** each completed reference list is kept in `<out>.refs.json` (or
  `--cache`), keyed by slug and DOI. A re-run after a throttled pass fetches only
  the lists that are missing, incomplete or for a changed DOI; `--no-cache`
  refetches all of them.
- **Completeness:** it writes `<out>.run.json` for `candidates.py`, and exits 1
  when a reference list could not be fetched, unless `--allow-incomplete`.

## Phase 6: `forward.py`

Looks forward where `xref.py` looks backward. It finds papers that cite the
corpus's landmark papers (by within-corpus in-degree, then citation count) and
cite at least `--min-shared` corpus papers, but are not in the corpus. The pulls
come from OpenAlex and are ordered by citation count, so very recent papers are
under-represented.

```bash
python3 tools/forward.py --rows rows.json --out forward_candidates.json
```

Like `xref.py`, it writes `<out>.run.json` and exits 1 on a failed pull unless
`--allow-incomplete`.

## Phase 6: `candidates.py`

The candidate ledger. Every paper `xref.py` or `forward.py` suggests gets a
recorded decision, so a paper left out of the review was visibly considered.

```bash
python3 tools/candidates.py --rows rows.json --add xref.json --source xref
python3 tools/candidates.py --rows rows.json --add forward_candidates.json --source forward
python3 tools/candidates.py --rows rows.json --list pending
python3 tools/candidates.py --rows rows.json --decide 10.1/x --decision exclude --reason "methods paper"
python3 tools/candidates.py --rows rows.json --export-included xref_lane.json --lane X
python3 tools/merge_lanes.py --append xref_lane.json --into rows.json
```

`--add` also records the run, from its `.run.json` sidecar, so the audit can tell
whether xref and forward citation ran and finished. The audit fails while any
candidate is pending. The spreadsheet lists the excluded ones with their reasons.
Verify the rows that `--export-included` and `--append` add.

## Phase 6b: `families.py`

Validates a theoretical grouping and stamps it onto the rows. On every review the
agent proposes families and pitches the timeline built from them (see
`family_prompt_template.md`); the user uses the families, changes them, or skips
the timeline. This script does the deterministic half.

```bash
python3 tools/families.py --rows rows.json --digest                  # corpus digest for the proposal
python3 tools/families.py --rows rows.json --assign families_input.json --out families.json
python3 tools/families.py --rows rows.json --assign spec.json --results 'batches/result_*.json' \
        --default-from-lanes --out families.json      # merge agent results; lab mode: lanes are themes
```

`--results` merges the assignment agents' result files (`{ref: key}`, or with
`hard_calls`) and refuses one that re-assigns a ref differently. `--default-from-lanes`
(lab mode, where each lane is a theme) assigns every row no result covered to its lane
key, else its `lane_fit`. A family whose `lineage` is empty gets one mechanically: its six
rows with the most within-corpus citations (`internal_citations.json`), oldest first,
marked `lineage_source`.

**Input** (`families_input.json`): `{principle, families: [{key, name, claim,
lineage}], assignments: {ref: key}, hard_calls: [{ref, assigned, also_fits,
why}]}`. Assignment values match case-insensitively, by `key` or by display
`name`, so you can re-run from the `family` field already stamped into
`rows.json`.

**Hard calls** are the papers the assignment agents found a poor fit, or a fit to
two families. They are the only place a wrong family definition shows, so the
script prints each one to read before rendering, and warns when the input has no
`hard_calls`.

**Fails** unless every paper is assigned, every assigned ref exists, every family
key is known and unique, and there are 2–9 families (3–8 recommended). **Warns**
on a single-paper family or one holding more than 60% of the corpus; empty
families are dropped.

**Output:** `family` on each row, `families.json` (the reproducible cache) and
`families.md` (tables by family plus a family × topic cross-tab). Do not build
families by clustering embeddings; theoretical families cut across textual
similarity.

## Phase 6b: `families_figure.py`

Renders the lineage timeline, which the agent offers on every review: a
self-contained interactive `.html`, a standalone `.svg`, and a `.png` and `.pdf`
if `rsvg-convert` or `inkscape` is installed.

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
title shows the family's claim and lineage. Prev/Next (or the arrow keys) step
through the papers in year order.

- **Landmarks are automatic:** the most cited per family (`--per-family`,
  default 4), papers cited by at least `--motif-min` corpus papers (from
  `internal_citations.json`, or `--internal`), and home-lab papers.
  `--max-labels` (default 28) caps the total. When the cap drops labels, the run
  says how many.
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

**Check it by running it.** Reading the code has missed interactive bugs, so two
Node.js checkers execute the page's own script:

```bash
node tools/checks/verify_hover.mjs mytopic_families.html       # what each lane's hover panel shows
node tools/checks/verify_nav_order.mjs mytopic_families.html   # Prev/Next walks each year in order
```

## Phase 7: `cite_check.py`

Gate: every in-text citation must name a row in `rows.json`. `review_paper.py`
prints whatever prose it is given, so without this check a citation to nothing
ships unnoticed.

```bash
python3 tools/cite_check.py --rows rows.json --content content.json
```

It parses parenthetical `(Farb et al., 2007)` and narrative `Farb et al. (2007)`
or `Farb and Segal (2007)` citations, folds accents (`Millière` = `Milliere`), and
matches author-year keys built from `apa`. **It exits 1 on an unresolved
citation.** It warns when one author-year matches two references; to fix one,
name more authors (APA-7 §8.19), as in `(Kral, Davis, et al., 2022)`. Year
suffixes (`2025a`) are also accepted.

## Phase 7: `prose_audit.py`

Measures how readable a review is, and checks that a rewrite lost no citation.

```bash
python3 tools/prose_audit.py --page build_review_page.py
python3 tools/prose_audit.py --page build_review_page.py --baseline /tmp/before.py
```

- **Input:** `--page`, a review page script with `[[REF]]` markers, or
  `--content`, a `content.json` with APA author-date citations. Blocks are read by
  parsing the file, not by importing it.
- **Report:** words, mean sentence length, and sentences of at least `--long`
  words (default 45) per block. Aim for a mean of 25 words or less.
- **`--baseline`** compares the set of cited references with a pre-revision copy,
  and exits 1 on any loss.
- **`--overlap`** (default 8) reports block pairs that share that many
  citations, a sign that one argument is made twice.
- `--exclude` skips blocks whose label matches a regex.

## Phase 7: `review_paper.py`

Renders an AI-authored review article as `.docx`. It handles only the mechanics:
the title, author and disclosure block, the abstract, the sections, an embedded
figure with its caption, and an APA-7 reference list. The list holds every row's
canonical `apa` from `rows.json` (deduplicated, hanging indent, each with its
link). References follow APA-7 order: authors letter by letter, then year, then
title, so a sole author precedes that author's co-authored works.

```bash
python3 tools/review_paper.py --rows rows.json --content content.json \
        --figure my_topic_families.png --out My_Topic_review.docx
```

**Input** (`content.json`, written separately): `{title, authors, author_note?,
affiliation_line?, disclosure?, abstract, sections: [{heading, level,
paragraphs}], figure: {path, caption}, references_heading?, references_note?}`.

When an LLM writes the prose, put the model in `authors`. State in the disclosure
that the bibliography was machine-verified and that the author read abstracts,
not full texts. Before rendering, run the priority audit (every origin claim cites
the earliest paper) and `cite_check.py`. HTML pages should reuse
`reference_list(rows)` for their reference lists.

## Phase 7: `bib_viewer.py`

Renders a searchable bibliography of the whole corpus, grouped by family, with a
search box, a "cited only" filter, and a link from each cited entry to its
works-cited number. It is for a page with no timeline. A review page embeds the
interactive timeline instead, which already carries every paper's reference and
summary, so it does not add this viewer.

```bash
python3 tools/bib_viewer.py --rows rows.json --families families.json \
        --out corpus_viewer.html --title "My topic" \
        --author "<model>" --author-note "<what the model is>"
```

Run from the command line, it writes a standalone page for a corpus with no
review attached. That page includes a note naming who wrote the summaries and
stating that they come from abstracts. To put the viewer inside another page, use
`bib_viewer.render()`, `bib_viewer.CSS` and `bib_viewer.JS`, and pass
`provenance=False` when that page already carries the disclosure. To check the
filter, run `node tools/checks/verify_bib_filter.mjs <page>.html`, which drives
the page's own script against its rendered entries.

## Lab mode L1: `lab_corpus.py`

Pulls a lab's full publication list from OpenAlex by author id. In lab mode, it
and `lab_lane.py` run before the search lanes.

```bash
python3 tools/lab_corpus.py --search "Jack Gallant"        # find the author id
python3 tools/lab_corpus.py --author A5056348548 --out lab_papers.json
```

Output: one row per paper, with its title, year, DOI, venue, APA reference,
OpenAlex citation count, topics, coauthors, abstract and `source: "lab"`. Author
disambiguation is the main risk, so the record is checked by content in Phase L2
before anything is built on it. OpenAlex abstracts are patchy and its topic tags
too coarse, so fetch abstracts from Semantic Scholar or PubMed before that check. The playbook's "Lab mode"
section covers the later steps.

## Lab mode L2: `lab_lane.py`

Checks the lab's record by content, and turns it into lane L.

```bash
python3 tools/lab_lane.py --prepare --papers lab_papers.json --abstracts lab_abstracts.json \
        --pi "Jack L. Gallant"
#   one checking agent per lab_check/input_NN.json writes lab_check/result_NN.json
python3 tools/lab_lane.py --build --papers lab_papers.json
```

An author record holds meeting abstracts, errata, peer-review reports, a preprint
and its published version as two works, and sometimes a namesake's papers.
Database tags mislabel them, so agents read each item and decide.

- **`--prepare`** writes batches of up to 90 items (`--batch`) and
  `lab_check/brief.md`. Each checking agent decides, per item, whether the PI is
  an author, its kind and species, whether it duplicates another item, and
  whether to include it. With `--themes themes.json` (`[{key, name, claim}]`, the
  lab's approved themes from Phase L3), it also gives each item a theme.
- **`--build`** writes `search_raw/0_L.json`, a schema-2 lane with
  `source: "lab"`, and lists each excluded item with its reason. It refuses an
  item with no check, a result checked twice or for an item not in the record, an
  included duplicate, an included item not by the PI, and, with `--themes`, a
  theme outside that file. An included item with no DOI keeps its OpenAlex reference and
  gets a hand check (Phase 3e).

Field lanes defer the lab's papers to lane L, so the merge fails on any lab paper
the record lacks. That is the record's completeness check.

## Other files

- **`search_prompt_template.md`**: the brief for a Phase 2 search agent, rendered
  by `lane_briefs.py` (never filled by hand). It defines the schema-2 lane file
  that `merge_lanes.py` reads.
- **`family_prompt_template.md`**: the two-step propose-then-assign prompt for
  Phase 6b, including the hard calls.
- **`checks/`**: the Node.js checkers that execute a page's own script, for the
  timeline (`verify_hover.mjs`, `verify_nav_order.mjs`) and the bibliography
  viewer (`verify_bib_filter.mjs`). Phase 6b and Phase 7 above say what each
  checks.
- **`gen_docs.py`**: regenerates the index above in all three files and stamps
  the version; `--check` exits 1 if anything is stale.

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
loaded = os.path.getmtime("rows.json")
# ... change the rows ...
common.save_rows("rows.json", rows, loaded)   # refuses if another tool wrote rows.json meanwhile

common.write_rows("rows.json", new_rows)      # an emitter: refuses to overwrite a canonical table unless force=True
```

Two guards protect the live table. `save_rows` refuses to write back a
`rows.json` that changed after it was loaded. `write_rows` enforces "after Phase
3f, `rows.json` is the live table": if the file on disk carries `canonical_at`
stamps, it refuses to let an upstream emitter replace it.
