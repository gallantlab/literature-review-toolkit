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
| `verify.py` | 3 | Verify a list of citations against CrossRef, DataCite, arXiv, PMC and PubMed. | `--asof` `--citations` `--email` `--key` `--no-stamp` `--only` `--out` `--override` `--reason` `--retry-from` `--retry-wait` `--rows` `--sleep` `--workers` |
| `handcheck.py` | 3e | Hand-check the references that have no DOI or arXiv id (books, reports, essays). | `--adopt-dois` `--asof` `--candidates` `--email` `--ingest` `--input` `--key` `--prepare` `--reason` `--reject` `--rows` |
| `references.py` | 3f | Canon: rebuild each verified row's reference as APA-7 from its DOI or arXiv id, and audit the table. | `--acks` `--asof` `--audit` `--candidates` `--email` `--hand-fixes` `--key` `--list-acks` `--only` `--out` `--repair` `--retry-wait` `--rows` `--sleep` `--workers` |
| `sentence_case.py` | 3f | Post-canon pass: propose strict APA-7 sentence case for reference titles, for a human to review. | `--apply` `--include-foreign` `--out` `--proper` `--rows` `--vocab` |
| `download.py` | 4 (opt-in) | Download open-access PDFs for a list of papers, only when the user asks for them. | `--email` `--manual-list` `--out-dir` `--papers` `--sleep` |
| `reconcile_downloads.py` | 4 (opt-in) | Match PDFs the user downloaded by hand to a slug + title + DOI manifest, and file them. | `--downloads-dir` `--dry-run` `--manifest` `--out-dir` `--since-hours` |
| `spreadsheet.py` | 5 | Build the bibliography .xlsx from rows.json, and refuse a table that fails the audit. | `--acks` `--candidates` `--draft` `--key` `--out` `--rows` `--sheet-name` |
| `citations.py` | 5b | Fetch citation counts for every row from OpenAlex and Semantic Scholar. | `--asof` `--attach` `--attach-only` `--email` `--key` `--out` `--rows` `--sources` |
| `abstracts.py` | 5c | Fetch each row's abstract into abstracts.json, for the summary check. | `--email` `--key` `--out` `--rows` |
| `summary_audit.py` | 5c | Summary check: agents with no web access confirm each row's summary against its abstract. | `--abstracts` `--asof` `--batch` `--dir` `--ingest` `--key` `--prepare` `--recheck` `--rows` |
| `candidates.py` | 6 | The candidate ledger: record a decision on every paper that xref, forward citation or a survey suggests. | `--add` `--asof` `--decide` `--decision` `--email` `--export-included` `--ingest` `--lane` `--ledger` `--list` `--no-fetch` `--per` `--prepare` `--reason` `--rows` `--scope` `--source` |
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

## Each tool in detail

Each section below is the tool's own module docstring, generated by
`tools/gen_docs.py`. To change one, edit the docstring at the top of the script,
then run `python3 tools/gen_docs.py`.

<!-- BEGIN GENERATED TOOL DETAILS (python3 tools/gen_docs.py — do not edit by hand) -->
### Phase 0: `preflight.py`

```text
Preflight: before any search, check for a newer toolkit, the API keys and the OpenAlex budget.

Run it FIRST, before writing a single lane brief. A build runs for hours, and two
of its services ration keyless use: OpenAlex (citation counts, abstracts, forward
citations, the hand-check DOI search, lab_corpus.py) and Semantic Scholar (xref,
the second citation count, abstracts). Finding that out halfway through a build
costs hours; finding it out here costs one request to each.

It checks:
  the toolkit        the version on GitHub (main) against this copy. The toolkit
                     changes often, so a newer version is offered with the
                     command that installs it (git pull for a clone, the plugin
                     menu otherwise). A build already under way keeps the version
                     it started with, so pass it --no-update-check.
  LITREVIEW_EMAIL    required by NCBI and CrossRef (or pass --email to every tool)
  OPENALEX_API_KEY   without it, every client on the same IP address shares ONE
                     free budget of 1,000 credits a day, and a campus network may
                     have spent it before you start; a free key has its own
                     10,000. A probe reads the budget left right now.
  S2_API_KEY         without it, Semantic Scholar throttles hard: xref and the S2
                     counts take hours and leave gaps. A probe checks that
                     Semantic Scholar accepts the key.
It also estimates what the planned corpus costs in OpenAlex credits. Size it with
--scale, the search scale the user asked for (scan, focused, standard, exhaustive
or a number of papers; common.scale_plan, with --lanes N if the lane count is
known), or give the size directly with --papers N (default 500). --offline
checks the environment only, with no probes and no GitHub check.

Exit 0 when the build can run as planned. Exit 2 when the user must decide
first: a newer toolkit is available (offer to install it), LITREVIEW_EMAIL is not
set, a key is missing or rejected, or the budget is short. For a missing key or a
short budget, give the user the three choices it prints: get the keys, cap the
search, or be prepared to wait. Ask before any lane is launched.

Every run writes preflight.json into --project (default: the current directory;
nothing is written when it is not a directory yet). merge_lanes.py refuses to
build a table without a record under 14 days old that is cleared: everything
passed, or the user's choice is recorded by rerunning with --accept (cap or wait
after a key or budget stop, current-version to keep this toolkit). A missing
email cannot be accepted. A cleared run exits 0.

    python3 tools/preflight.py --project <topic>/ --scale focused
    python3 tools/preflight.py --project <topic>/ --scale focused --accept wait   # the user's choice
    python3 tools/preflight.py --project <topic>/ --papers 600 --offline   # environment only, no probes
    python3 tools/preflight.py --project <topic>/ --papers 600 --no-update-check  # a build under way
```

### Phase 2: `lane_briefs.py`

```text
Render every search lane's brief from one lane spec, so no brief goes out incomplete.

The search agents are only as good as their briefs, and a hand-filled brief drifts:
a lane missing the verification duty, a leftover {PLACEHOLDER}, a capped-search rule
left in an uncapped build. This tool fills tools/search_prompt_template.md for each
lane, builds the shared lane table, keeps or drops the template's conditional blocks
(forward/antecedent, capped/uncapped, lab, seeds), and refuses to write any brief
with a placeholder or block marker left in it. Never fill the template by hand.

    python3 tools/lane_briefs.py --spec lanes.json

It writes briefs/brief_<KEY>.md, lane_manifest.json (key, name, brief, out, target,
kind, capped, scale) and an empty search_raw/ and scratch/<KEY>/ per lane, all
beside the spec, and prints the one-line prompt to give each search agent. Keep the
spec in the project folder: merge_lanes.py reads lane_manifest.json beside its
--out to fail a capped lane over its cap.

The spec (JSON):
  {"title": "The Gallant lab in the context of its field",
   "for": "Jack Gallant at UC Berkeley",
   "description": "What the bibliography covers, what is out of scope for all lanes.",
   "today": "2026-09-27",            # optional, default today
   "tier": 2021,                     # optional, default today's year minus 5
   "scale": "standard",              # scan | focused | standard | exhaustive | a number of papers
   "capped": false,                  # optional; follows from the scale
   "lab": {"pi": "Jack L. Gallant", "lane": "L"},      # optional: lab mode
   "already_have": ["Author Year - title", ...],        # optional, every lane
   "lanes": [{"key": "V", "name": "...", "short": "one line for the lane table",
              "kind": "forward" | "antecedent", "target": 40,     # target optional: from the scale
              "definition": "...", "exclusions": ["...", ...] or "...",
              "queries": ["...", ...], "seeds": ["title", ...],   # seeds optional
              "already_have": [...]}]}                            # optional, this lane

The scale is how big a search the user asked for (common.SEARCH_SCALES): it sets
each lane's target (a lane may set its own), whether lanes are capped, and the
number of lanes allowed. `scan` and `focused` cap each lane at 15 or 30 papers.
`standard` (the default) and `exhaustive` set floors of 40 and 60. A numeric
scale is a capped total spread over the lanes, and the lane targets may not add
up to more than it. Every scale still needs at least one antecedent lane
(contract rule 4). When the project's preflight.json
records that the user chose to cap the search, an uncapped scale is refused. The
tool prints the plan and the preflight command sized to it.

Lane keys are 1-4 capital letters or digits, since they prefix every ref. Seeds
are TITLES only: a seed that carries an author name is refused, because
remembered author names have injected fabricated attributions into past builds.

It exits 1, naming every problem, on:
  - a missing field, a repeated or malformed key, or a seed that names an author;
  - a lane count outside the scale's range, or no antecedent lane;
  - lane targets that add up to more than a numeric scale;
  - an uncapped scale when preflight.json records that the user chose to cap;
  - a brief with anything left unfilled.
```

### Phase 2c: `merge_lanes.py`

```text
Merge search-lane files into rows.json, and fail when a paper fell between lanes.

It reads every schema-2 lane file (see tools/search_prompt_template.md) in --raw.
A lane file holds `papers`, `deferred` (a hand-off to a named lane, with
`first_author` and `year`), `excluded` (each with a reason) and
`could_not_confirm`. The merge:
  - dedups by DOI, then arXiv id, then normalized title + year, and records the
    other lanes that returned a paper (`also_lanes`). A title + year match with
    a conflicting author or year, or with two different journal DOIs, stays as
    two rows and is reported as a possible pair. Every other pair of similar
    titles is reported too; a title of under four content words must match on
    characters, since word containment alone paired one short title with 60
    longer ones. Authors are compared the way verify.py compares them, and an
    unknown author never merges a pair or confirms a deferral;
  - keeps each lane's claim as search_author / search_year / search_title,
    which verify.py checks the DOI against;
  - rejects a paper with no DOI, arXiv id or APA string, since it can be neither
    verified nor hand-checked;
  - matches every `deferred` entry against the merged table. A deferral that no
    lane kept is LOST. One matched by title alone, with neither first_author nor
    year (or with an unreadable first_author), is UNCONFIRMED. Send those to a
    recovery lane, or complete the deferral, and re-merge;
  - records each lane's `excluded` papers (out of scope, or pre-tier and not
    classic) with their reasons, for the spreadsheet's "Considered and excluded"
    sheet. An exclusion is a decision, not a hand-off, so it never has to match
    a row. The lane target is a floor, so an on-topic paper trimmed to meet it
    belongs back in `papers` (except in a capped search);
  - flags thin lanes (under 60% of target, or out of search budget), to resume;
  - in a capped search (lane_manifest.json from lane_briefs.py, beside --out),
    fails a lane that returned more papers than its cap. Resume it to move the
    rest to `excluded` with reason "over the capped-search limit".
A merge with a lost, unconfirmed or rejected paper, or a lane over its cap,
writes merge_report.json but not rows.json, and exits 1. It refuses to overwrite a
canonical rows.json unless --force, and refuses a schema-1 lane file (a bare
list) unless --allow-v1.

Phase 0 is enforced here, at the first step that builds the table: the merge
refuses to run without a recent, cleared preflight.json (preflight.py) in the
folder of --out. --no-preflight "reason" merges anyway, and the reason is kept in
merge_report.json.

    python3 tools/merge_lanes.py --raw search_raw --out rows.json
    python3 tools/merge_lanes.py --append recovery.json --into rows.json   # late rows

--append adds a lane file's papers to an existing table and never changes an
existing row. It skips a paper the table already holds, and it refuses an empty
--into (run --raw/--out for a first merge). Verify the appended rows next.
```

### Phase 2c: `recall.py`

```text
Measure a rerun's recall against the old build, and list the papers it missed.

A redo of an old bibliography should find what the old build had. This tool
matches every old row against the new table (by DOI, then arXiv id, then title
via common.title_match) and writes the misses as the input for ONE recovery lane,
whose agent decides each miss again (include, with a claim read off the landing
page, or exclude, with a reason). The old reference is a pointer, not a claim.

    python3 tools/recall.py --rows rows.json --old ../old_build/rows.json \
            --where source=search --out manual_check/recovery_input.json

--where KEY=VALUE keeps only the old rows whose field matches (repeatable), e.g.
source=search to compare field papers only. Prints the recall and writes
[{"old_ref", "doi", "reference_in_old_build", "old_family"}] for the misses, to
recovery_input.json beside --rows unless --out names another file. Add the
recovery lane's file to the table with `merge_lanes.py --append`.
```

### Phase 3: `verify.py`

```text
Verify a list of citations against CrossRef, DataCite, arXiv, PMC and PubMed.

Search agents have gotten as many as a quarter of their citations wrong (authors,
years, or the whole paper), so nothing enters the spreadsheet unverified.

Reports one verdict per citation:
  OK          the record agrees with the claim
  MISMATCH    the record disagrees on first author, year or title, or the DOI
              does not resolve: fix or drop the row, or --override a false alarm
  NOT-FOUND   every lookup completed and none matched: chase it down, since it
              is likely fabricated
  ERROR       a lookup could not complete (rate limit, network): re-run it
  UNCHECKED   the row carried no author, year or title to check, so a resolving
              DOI shows only that the DOI exists: give it a claim or a canonical apa
NOT-FOUND and ERROR are kept strictly apart. An earlier version swallowed
exceptions into NOT-FOUND, which can drop a real paper on a transient throttle.
Never drop a NOT-FOUND without chasing it, and always re-run an ERROR. A
malformed row becomes ERROR without aborting the batch. When a PMC or PubMed
lookup fails and the fallback title search returns a paper that does not match,
the verdict is also ERROR, not MISMATCH.

Exit status: 0 only when every verdict is OK; 1 otherwise. references.py --audit
and cite_check.py fail the same way, so a chained Phase 3 run stops at the first
table that needs attention.

Lookups. arXiv papers (an `arxiv` id, or a 10.48550/arXiv.<id> DOI) are a blind
spot for the other sources: CrossRef has no arXiv DOIs, and a PubMed title search
returns a plausible but wrong paper. So they go to the arXiv API, prefetched in
BATCHES, because the API takes many ids per call and bans a per-paper loop. A
journal DOI is verified only by its own record, and a row with both ids is
checked against both. A DOI missing from CrossRef is not necessarily fake:
Zenodo, figshare, OSF and Dryad register software, data-set and some preprint
deposits with DataCite. So a clean CrossRef 404 is followed by a DataCite lookup,
and resolving there counts the same as resolving in CrossRef. PMC, PubMed and a
PubMed title search are fallbacks. They can verify a citation with no journal
DOI, but they never stand in for a DOI: when a DOI resolves in neither registry,
a fallback hit makes the verdict MISMATCH ("DOI does not resolve"), and no hit
makes it NOT-FOUND.

First author. Surnames are compared, not initials.
  - A record is read by its source's "Family INITIALS" contract: "Collins AGE" is
    Collins, and an arXiv "John Smith" becomes "Smith J".
  - A record's first author is trusted only when the registry deposited it
    structured (family + given name). These forms give MISMATCH with "confirm by
    hand":
      a DataCite first creator without both familyName and givenName, unless it
        is "Family, Given" or an Organizational group;
      a CrossRef first author with no given name, or a first entry with no family;
      an arXiv name with a capitalized word ("CHEN Hao");
      a bare "Hae-Jeong Park" or "Hao CHEN J".
  - Accepted as they are: bare records with spaced initials or a comma list
    ("Kim J H", "Chen, Hao H"), and a CrossRef whole name deposited as the family.
  - A claim is read once, in whatever shape it was reported. "Smith J", "J. Smith"
    and "Smith, J." all give Smith. Initials of any script ("Ł" or "И") count as
    initials. A list ("Smith J; Jones K" or "Smith J and Jones K") gives its first
    name. An ambiguous claim, such as "Hao CHEN" or "Collins AGE", is also an
    issue to confirm by hand.
  - The claim's surname must match a whole word of the record's: "Tang" matches
    "Tang J", "Heuvel" matches "van den Heuvel M", and "Hanna" matches
    "Andrews-Hanna J". "Van Essen" does not match "Van Dijk", nor "Min"
    "Seung-Min Park", nor "Lambon Ralph" "Ralph J". In a given-first claim ("John
    Smith"), each given name must start with one of the record's initials (or be
    a word of its surname). A claim led by a capitalized particle ("DU Wei")
    matches only a record that carries the particle.
  - A group author ("ATLAS Collaboration", "Stanford University", "Google
    Research") is compared whole. An unknown name on either side ("?", "anon",
    "unknown", or no readable word) is an author issue, never a match.
The year may differ by one from any record, and the title must agree both ways
(common.title_agrees). merge_lanes.py uses the same author comparison to tell a
duplicate from two papers that share a title. It never merges on, or confirms a
deferral by, an unknown author.

Input format (JSON list of dicts):
[
  {"label": "Tang2023_decoder",
   "pmcid": "PMC11304553",        # optional
   "pmid":  "37127759",           # optional
   "doi":   "10.1038/s41593-...", # optional (incl. arXiv DOIs 10.48550/arXiv.X)
   "arxiv": "2305.18274",         # optional; bare arXiv id (else parsed from doi)
   "title": "Semantic reconstruction ...",  # optional; checked, and the title-search fallback
   "expect_first_author": "Tang J",  # optional; as reported (any shape), checked by surname
   "expect_year": "2023"             # optional; if given, will be checked
  },
  ...
]
expect_first_author is the author as reported, in any shape ("Tang J", "J. Tang",
"Tang, J.").

  python3 tools/verify.py < input.json > report.json
  python3 tools/verify.py --citations input.json --out report.json
  python3 tools/verify.py --rows rows.json --out report.json    # straight from the live table

With --rows, the citation list is built from rows.json (rows_to_citations):
label = the row key, the DOI from `doi` or `link`, and the expected first author,
year and title from the SEARCH AGENT's claim (`search_author` / `search_year` /
`search_title`). Once a row is canonical, its `apa` must agree with the record as
well. So a project needs no converter script, and a pre-canon table is not
verified against its own empty `apa`. A canonical row with no claim is checked
against its apa alone, and the audit then asks a human to confirm it
(identity-not-reestablished).

--rows also writes each verdict onto its row as `verified` (every verdict, not
only OK, bound to the row's DOI and arXiv id), unless --no-stamp. references.py
rebuilds only rows with an OK stamp for their current ids, and its audit reads the
stamp too. To clear a false alarm
(e.g. a preprint retitled on publication), record why; this needs no network:
  python3 tools/verify.py --rows rows.json --override A-07 --reason "retitled on publication"

A lookup that fails transiently is retried once more at the end of the run,
after a cool-down (--retry-wait). To re-check a few rows later:
  python3 tools/verify.py --rows rows.json --retry-from report.json --out report.json
This re-verifies only the rows that were not OK and splices them back into the
report (--only A-01,B-02 names rows explicitly).

Record cache. verify and canon (references.py) keep every CrossRef, DataCite and
arXiv record they fetch in .record_cache/ beside --rows (or --citations) for 14
days. So canon reuses what verify fetched, and a targeted re-run makes almost no
requests. Only successful records are cached, so a missing or failed lookup still
reads as NOT-FOUND or ERROR. LITREVIEW_RECORD_CACHE=off turns the cache off; any
other value is used as its folder.
```

### Phase 3e: `handcheck.py`

```text
Hand-check the references that have no DOI or arXiv id (books, reports, essays).

No API can verify a DOI-less row, so on a gated table the audit fails any such
row without a hand-check record. A checking agent confirms or corrects each
reference against a library catalog, the publisher, or the work itself. This
tool does the work around the hand check:

  --prepare           search CrossRef and OpenAlex for a DOI the row lacks (the
                      same title, by common.title_match, and the same year).
                      Rows with a candidate go to handcheck_doi_candidates.json;
                      the rest go to handcheck_input.json, with
                      handcheck_brief.md for the checking agent. Each input entry
                      carries `apa_sha`, the hash of the reference it shows (the
                      apa, else search_apa). An existing handcheck_result.json
                      answers the previous --prepare, so it is renamed (never
                      deleted) to handcheck_result.stale-<timestamp>.json.
  --adopt-dois FILE   give each row with exactly one candidate DOI that DOI, so it
                      goes through verify.py instead. For a row with several, keep
                      one in the file and re-run.
  --ingest FILE       record each result on its row as `hand_verified`. A result
                      is refused when the row's shown reference changed since
                      --prepare, when its --input entry has no `apa_sha` (an
                      input written before that binding existed), or when the
                      result's own `apa_sha` echo is missing or differs from the
                      input's (a result for an older --prepare).
  --reject REF        the row's candidate DOIs (in --candidates, default
                      handcheck_doi_candidates.json beside --rows) are all the
                      wrong paper: record them on the row as `doi_rejected`, with
                      the required --reason, so the next --prepare skips them and
                      sends the row to the hand check. Repeat for several rows;
                      exit 1 when a ref is not in the table or has no candidates.
  --input FILE        the hand-check input that --ingest checks against
                      (default: handcheck_input.json beside --rows)

    python3 tools/handcheck.py --rows rows.json --prepare --email you@inst.edu
    python3 tools/handcheck.py --rows rows.json --adopt-dois handcheck_doi_candidates.json
    python3 tools/handcheck.py --rows rows.json --reject Y-19 --reason "both candidates are reviews of it"
    python3 tools/handcheck.py --rows rows.json --ingest handcheck_result.json

Result file: a JSON list of {"ref", "apa_sha" (copied from the input entry),
"verdict": "confirmed"|"corrected"|"not-found", "apa" (corrected only),
"source_checked", "changes"}. A "corrected" result replaces the row's apa.

--ingest exits 1 when it refused any result or any row is recorded not-found;
remove a not-found row, or check it again.
```

### Phase 3f: `references.py`

```text
Canon: rebuild each verified row's reference as APA-7 from its DOI or arXiv id, and audit the table.

A reference's text must never be trusted from a search agent's memory (topic
mode) or from OpenAlex's light metadata (lab mode). So each `apa` is rebuilt
through ONE formatter from the authoritative record: CrossRef for a DOI, the
arXiv API for an arXiv id. When CrossRef has no such DOI, DataCite is tried,
because Zenodo, figshare, OSF and Dryad register software, data-set and some
preprint deposits there. When a row has both a journal DOI and an arXiv id, the
journal DOI wins, because a published paper is cited by its version of record.

Canon rebuilds only a row whose verify stamp is OK (or overridden with a reason)
for its current ids, so it never prints a wrong paper in a correct format. It
names every row it did not rebuild: not verified, a DOI no registry has, a source
with no usable record (the old apa is kept), or a fetch that failed twice.

Pipeline position:
  topic mode:  merge_lanes.py -> verify.py --rows -> references.py
  lab  mode:   lab_corpus.py -> verify.py --rows -> references.py

INPUT: a JSON list of rows. Each row needs a key (default "ref", else "label")
and a DOI (a `doi` field or a `https://doi.org/...` link) and/or an `arxiv` id.
An optional `venue` is used only as a last-resort fallback (lab mode passes the
OpenAlex venue). A row with neither id keeps its `apa` and is listed for a check
by hand (handcheck.py).

  python3 tools/references.py --rows rows.json --email you@inst.edu   # canon, in place
  python3 tools/references.py --rows rows.json --audit                # report only
  python3 tools/references.py --rows rows.json --list-acks            # unacknowledged warnings
  python3 tools/references.py --rows rows.json --repair               # offline string repair

Canon rewrites each rebuilt row's `apa` (and its `link` to the DOI URL), stamps
`canonical_at`, and prints the audit. --audit prints the audit and writes
nothing, and exits 1 on any defect. On a gated table (see the reference gates
below), the audit also applies the reference gates: the verify stamp, the hand
check, the summary check, the candidate ledger, and an acknowledgment in
audit_acks.json for every warning. spreadsheet.py runs this same audit. Canon
needs --email or LITREVIEW_EMAIL; --audit, --list-acks and --repair make no
network request and do not.

OUTPUT. Each rebuilt `apa` is APA-7 from CrossRef, DataCite or the arXiv API, with:
  - the full author list (more than 20 authors: the first 19, an ellipsis, the last);
  - correct initials and name particles (de Heer), and fixed casing
    (ANDERSON -> Anderson);
  - HTML unescaped, and all-caps titles sentence-cased;
  - a real venue, including the preprint servers CrossRef leaves blank (bioRxiv,
    PsyArXiv, arXiv, or arXiv's journal_ref when present).
A DataCite-registered software, data-set or preprint DOI that CrossRef does not
hold (Zenodo, figshare, OSF, Dryad) is written as
    Authors (Year). Title (Version v) [Data set|Computer software|Preprint]. Publisher.
The bracket and version are left out when DataCite has none. A creator with no
given name is split when that is safe: "Jagroop Singh Doad" or "Doad J S" gives
"Doad, J. S.", and "Kim J-H" gives "Kim, J.-H.". A `familyName` is the surname
when `name` contains it as a whole word. A name is never split on trailing
initials, into a one-letter surname, or from a 3-4 letter capitalized word
("Collins AGE", "Hao CHEN"). A creator kept whole is flagged
datacite-unsplit-author:<name>. A record that is not software or a data set, or
whose publisher is "Unpublished", is flagged datacite-deposit. Both are stored as
the row's `canon_warnings`, and each must be acknowledged in the audit.

--audit fails on formatting defects:
  - a missing author or year, or `et al.` in the author list;
  - an HTML entity or markup tag, `?.` or `!.`, or a U+2010/U+2011 hyphen;
  - a malformed initial (`L. (.`, `J. -.`);
  - punctuation glued to the next word, or a `?` where a quote or dash belongs;
  - U+FFFD mojibake;
  - a truncated or empty venue;
  - an uppercase title (three or more all-caps words in a row);
  - a hand fix that is no longer in the row (hand-fix-lost, below).
A DOI-less book or report is not a formatting defect. It is listed for a check by
hand, which a gated table requires (handcheck.py).

--audit warns on the cases that need a human verdict:
  - near-duplicate titles, usually a preprint and its published version with
    different DOIs. Keep the version of record, and re-check any in-text citation
    whose year changes;
  - multi-word surnames, which may be real (Lambon Ralph) or given names CrossRef
    folded into the surname (Thomas Yeo). A leading initial in the surname
    (A. Moffat) is unambiguous and repaired automatically;
  - one-letter surnames (S, D. J.), almost always an initial split off as the
    surname. Acknowledge a real one (O) as single-letter-surname:<name>;
  - a footnote digit glued to the title;
  - a deposit-year conflict, where the DOI encodes a different year (back-file
    digitization re-dates old papers);
  - a cached `year` field that disagrees with `apa`.
On a legacy table, warnings are only reported. On a gated table, each warning
must be acknowledged, or the audit fails. Record the reason in audit_acks.json
({ref: {warning_id: reason}}); --list-acks lists the warnings still open.

Reference gates. A table is gated once any row carries a verify stamp, or was
built or canonicalized on or after the gates date (common.GATES_SINCE). On a
gated table the audit also fails:
  - a row with a DOI or arXiv id that is not verified OK for its current ids;
  - a DOI-less row with no valid hand check, or whose `apa` changed since it;
  - a row with no summary (no-summary);
  - a summary with no summary check for its current text and ids, one judged
    unsupported, or one checked against an abstract judged not the paper's
    (abstract-wrong);
  - a `link` that is not the row's DOI;
  - a pending candidate in candidates.json, or an included candidate that is not
    in the table.
It also adds warnings to acknowledge:
  - no candidate ledger;
  - an xref or forward run that is missing or did not finish, or that read fewer
    papers than the table now has (not counting the candidates the passes added);
  - a row verified only against its own canonical `apa`;
  - a verified row that canon could not rebuild;
  - each canon warning;
  - a summary with no abstract to check it against.

Hand fixes. Some registry records are wrong in ways canon cannot fix (a split
compound surname, two authors packed into one, a missing subtitle or year).
Mojibake is flagged, not fixed, because the original character is lost. Because
canon re-fetches on every run, it would undo a fix typed into `apa`. So such a
fix lives in hand_fixes.json beside --rows (--hand-fixes), with "old" the damaged
text, "new" the final text and "why" its source: {ref: [{"old", "new", "why"}]}
(common.load_hand_fixes). Write "new" in its final form, sentence case included.
Canon, --repair and `sentence_case.py --apply` re-apply every fix after they
write. Canon and --repair exit 1 on a fix that no longer matches its row. The
audit fails a row whose fix is gone (hand-fix-lost).

--repair fixes pure string damage (markup, Unicode hyphens, `?.` and `!.`)
without re-fetching, so earlier hand edits survive. Use it on an old corpus
instead of a full re-run. Canon stamps each rebuilt row with `canonical_at`,
which common.write_rows checks before overwriting. --repair adds that stamp only
on a legacy table: on a gated table the stamp means "rebuilt from a verified
source", which a string repair is not.

arXiv ids are fetched in batches of 50 (one request per 50 rows, 3 s apart, as
arXiv asks), never one per row. A row whose fetch fails gets a second try at the
end of the run, after --retry-wait. `--only A-01,B-02` rebuilds just those rows
and leaves every other row as it is (the targeted re-canon).

Exit 1 when the audit fails, any row was not rebuilt (not verified, a DOI no
registry has, or a failed fetch), or a hand fix is stale, so a bad reference
cannot ship.
```

### Phase 3f: `sentence_case.py`

```text
Post-canon pass: propose strict APA-7 sentence case for reference titles, for a human to review.

The DOI is ground truth for where a paper is; the `apa` string is display, and
APA-7 wants sentence case. CrossRef and arXiv return titles in mixed casing
(arXiv and many publishers use Title Case; Nature deposits sentence case).
references.py fixes ALL-CAPS titles but deliberately does NOT turn Title Case
into sentence case. Doing that correctly needs the proper-noun judgment APA
assumes, and a mechanical caser mis-cases proper nouns without leaving anything
the audit could catch.

So this tool PROPOSES and a human REVIEWS. Run it, read the diff, add the
corpus's own proper nouns to a --proper file, then apply.

  python3 tools/sentence_case.py --rows rows.json                    # print the diff
  python3 tools/sentence_case.py --rows rows.json --vocab            # review by token
  python3 tools/sentence_case.py --rows rows.json --proper mine.json # project allowlist
  python3 tools/sentence_case.py --rows rows.json --proper mine.json --apply

`--vocab` is the fast way to review a large corpus: instead of reading 150 title
diffs, read the ~400 distinct token changes they amount to. A mis-cased proper
noun shows up there at once.

Protected automatically, with no allowlist needed:
  - ALL-CAPS acronyms (EEG, DMN, MBSR, LORETA)
  - any token containing a digit (7T, COVID-19, 5-MeO-DMT)
  - camelCase and internal capitals (fMRI, pRF, LEiDA)
  - a lone capital letter inside a compound (ACAM-J, S-ART, 7-T)
  - each hyphen/slash/dash part judged separately, so 'Resting-State' is not
    mistaken for camelCase
  - the first word of the title and of any subtitle after a colon
A DataCite deposit's `(Version …)` and bracket descriptor (`[Data set]`,
`[Computer software]`, `[Preprint]`) are not part of the title, so they are never
cased and need no --proper entry. Titles that look German or French are skipped and
listed, because casing them lowercases every noun; --include-foreign cases them
anyway.

The built-in allowlist (PROPER, below) holds only nouns that are proper in ANY
corpus. Domain proper nouns (a practice, a cohort, a trial, an instrument, a
language) belong in a per-project `--proper` file: {"words": [...], "phrases":
[...]}. Phrases match case-insensitively and are restored to the capitalization
written there, so a generic word can lowercase while a named entity containing
it does not (yoga practitioners, but Sahaja Yoga).

--apply writes in place (or to --out), and refuses a rows.json that changed since
it was read. Before it writes, it re-applies every fix in hand_fixes.json beside
--rows, so a recorded hand fix keeps its exact final text (see references.py).
```

### Phase 4 (opt-in): `download.py`

```text
Download open-access PDFs for a list of papers, only when the user asks for them.

Phase 4 is opt-in: the default workflow does not download PDFs (see PLAYBOOK.md). Run this tool only
when the user has asked for PDF acquisition. A dedicated replacement is planned;
until then, this legacy tool still works.

For each paper it tries arXiv, then Unpaywall (non-PMC URLs first), then
EuropePMC. It keeps a file only if its bytes start with %PDF, and it skips hosts
that block scripts (PMC, bioRxiv, medRxiv, PNAS, OUP, MIT Press, ScienceDirect,
Wiley, Cell). A PDF already in --out-dir is kept. With --manual-list, the papers
it could not fetch are appended to that file with their DOI, PMC and arXiv links,
for download by hand.

Input format (JSON list):
[
  {"slug": "Tang2023_decoder",
   "doi": "10.1038/s41593-023-01304-9",  # optional
   "arxiv": "1809.10193",                 # optional
   "pmcid": "PMC11304553"},               # optional
  ...
]

  python3 tools/download.py --papers list.json --out-dir papers/topic_X/ \
          --email you@inst.edu --manual-list papers/topic_X/_needs_manual.txt
```

### Phase 4 (opt-in): `reconcile_downloads.py`

```text
Match PDFs the user downloaded by hand to a slug + title + DOI manifest, and file them.

Companion to download.py (Phase 4, opt-in): run it only when the user has asked
for PDF acquisition. It scans --downloads-dir (default ~/Downloads) for PDFs
modified in the last --since-hours (default 12), and moves each match into
--out-dir as <slug>.pdf. --dry-run reports without moving anything. It needs
pdftotext (brew install poppler).

Matching, most reliable first:
  1. **Filename ↔ DOI substring.** Many publishers encode the DOI suffix in the
     filename: `nrn755.pdf` → `10.1038/nrn755`, `science.1138071.pdf` →
     `10.1126/science.1138071`, `s41467-019-13761-7.pdf` → `10.1038/s41467-...`.
     A filename that matches exactly one manifest DOI is a confident match.
  2. **Author surname + year + title words** on the PDF's first page (read with
     pdftotext). All three must agree, and the best entry must lead the runner-up
     by a clear margin.
  3. **Refuse to move** when uncertain. The PDF stays in Downloads for the user
     to confirm, rather than being misfiled; a slug already filled is never
     overwritten.

Manifest format (JSON list):
[
  {"slug": "Treue1996_xref",
   "title": "Attentional modulation of visual motion processing in cortical areas MT and MST",
   "first_author": "Treue", "year": "1996",
   "doi": "10.1038/382539a0"},
  ...
]

  python3 tools/reconcile_downloads.py --manifest list.json --out-dir papers/attention/
```

### Phase 5: `spreadsheet.py`

```text
Build the bibliography .xlsx from rows.json, and refuse a table that fails the audit.

It runs the same audit as references.py --audit. On a gated table, a failing
audit writes nothing and exits 1; --draft writes <out>_DRAFT.xlsx instead, with a
banner saying it is not a deliverable. A legacy table (one that predates the
reference gates) is written despite the findings. A candidates.json that is not a
valid ledger is refused on any table. Always rebuild from scratch: the writer
cannot edit an existing file.

Base schema (sheet "References", or --sheet-name):
  Topic | Ref # | APA reference | Link | Summary | Tag | PDF (local) | Xref

Columns added after Tag when the data carries them, in this order:
  - Family, when any row has `family` (families.py);
  - Cite (OpenAlex) | Cite (S2), when any row has `cite_openalex` or `cite_s2`.
    The counts come from citations.py (Phase 5b); attach them to the rows with
    its --attach or --attach-only. Google Scholar cannot be queried at scale (no API,
    CAPTCHA), so these databases are the proxy. See PLAYBOOK.md;
  - Verify note, when any row has a `verify_note` (handcheck.py writes one);
  - Summary checked against, when any row has a `summary_check`
    (summary_audit.py): the abstract's source, or "no abstract".

A second sheet, "Considered and excluded", lists each candidate the ledger
excluded and each paper a lane excluded (merge_report.json beside --rows), with
its reason. So a paper that is not in the review was visibly considered.

`Link` should always be a DOI URL (`https://doi.org/<doi>`); PubMed/PMC URLs are
not used as the primary link. `PDF (local)` is empty unless Phase 4 was opted
into.

Row color by `source` (see COLORS; an unknown value renders white, with a warning):
  source-doc -> white | search -> cream (#FFF7E0) | xref / forward / survey -> green (#E2F0D9)
  lab -> blue (#DDEBF7) | anteced / anteced-nosrc -> lilac (#F3E6F5)

Input format (JSON list):
[
  {"topic": "Multimodal networks", "ref": "M41",
   "apa": "Author, A. (2024). Title. Journal, 1(1), 1-2.",
   "link": "https://doi.org/10.1234/abcd", "summary": "...", "tag": "classic",
   "pdf": "", "xref": 10, "source": "xref",
   "cite_openalex": 123, "cite_s2": 140},      # optional; omit if not fetched
  ...
]

  python3 tools/spreadsheet.py --rows rows.json --out bibliography.xlsx
  python3 tools/spreadsheet.py --rows rows.json --out bibliography.xlsx --draft   # a marked draft
```

### Phase 5b: `citations.py`

```text
Fetch citation counts for every row from OpenAlex and Semantic Scholar.

Google Scholar has no public API and blocks automated queries after a few
requests, so it cannot be queried for a whole bibliography. OpenAlex and Semantic
Scholar are the queryable proxies.

OpenAlex is the primary source, with near-complete coverage by DOI. Without
OPENALEX_API_KEY, every client on the same IP address shares one daily budget,
and a spent budget stops the run with OpenAlexBudgetError (run preflight.py
first). Semantic Scholar is the secondary source. It often counts higher for
CS/AI venues and adds an "influential citations" count, but it throttles hard
without S2_API_KEY, so treat its column as best-effort. One S2_API_KEY serves
xref, citations and abstracts; their requests take turns through a pacer shared
across processes, so they may run at the same time.

INPUT: a JSON list of rows. Each row needs a key (default: "ref", else "label")
and a DOI, from a "doi" field or a https://doi.org/... "link". An arXiv-only row
is counted by its arXiv DOI (10.48550/arXiv.<id>), which Semantic Scholar is
asked for by arXiv id. A row with neither id gets empty counts.

OUTPUT: {key: {"openalex": int|None, "s2": int|None, "s2_influential": int|None,
               "asof": "YYYY-MM-DD"}}
The spreadsheet and the figure read the counts from the rows, not from this
file. Pass --attach to write them onto --rows as cite_openalex, cite_s2,
cite_s2_influential and cite_asof (through the guarded save, so it refuses to
overwrite a rows.json another tool changed meanwhile), or --attach-only to attach
an existing --out without fetching (through the same guard). Rebuild the
spreadsheet afterward.

A re-run keeps what an earlier run found: when a lookup returns nothing but the
existing --out has a count for that row, the earlier count stays (a throttled
Semantic Scholar batch is not "no citations").

  python3 tools/citations.py --rows rows.json --out citation_counts.json --attach \
          --email you@inst.edu
  python3 tools/citations.py --rows rows.json --out citation_counts.json --attach-only

OpenAlex's batch filter sometimes returns a low-count duplicate record. So the
tool keeps the highest count per DOI, retries each miss by single-work lookup,
and re-queries a count far below Semantic Scholar's. Still, check that no famous
old paper shows a single-digit count. Counts are a snapshot at run time; re-run
to refresh. See PLAYBOOK Phase 5b.
```

### Phase 5c: `abstracts.py`

```text
Fetch each row's abstract into abstracts.json, for the summary check.

The summary check (summary_audit.py) compares each summary with its abstract, so
each abstract comes from the most authoritative source that has it. The sources
are tried in order: the arXiv API for arXiv papers, then OpenAlex (50 DOIs per
request), then Semantic Scholar (500 ids per request), then PubMed for rows with
a `pmid`, then PubMed by DOI (50 per request), then Europe PMC by DOI (20 per
request). The last two found 150 of the 194 abstracts the others missed on one
1,215-row build, which a landing-page agent had to collect before. A source's
abstract field sometimes holds something else: a journal's
self-description, JSTOR's terms of use, a citation line, or an author list and
venue. not_an_abstract() refuses such a text, the next source is tried, and a
text no later source replaced is reported.

Each entry records the `doi` and `arxiv` it was fetched for. When a row's ids
change, its entry is fetched again. An entry added by hand ("source":
"landing-page") is never overwritten; one with an empty `text` records that the
paper has no abstract. When its ids no longer match the row, it is reported as
stale: check that it is still this paper's abstract, then set its ids to the
row's.

abstracts.json goes beside --rows unless --out names another file.
abstracts_failed.json, written beside abstracts.json, maps each ref whose fetch
could not complete to the reason ({} when none). A failed fetch is not "no
abstract", so summary_audit.py --prepare refuses those refs.

Exit 1 when any fetch failed or any hand-added entry is stale; re-run to fill
the gaps. A spent OpenAlex daily budget stops the run with OpenAlexBudgetError.
One S2_API_KEY serves xref, citations and abstracts; their requests take turns
through a pacer shared across processes, so they may run at the same time.

    python3 tools/abstracts.py --rows rows.json --email you@inst.edu
```

### Phase 5c: `summary_audit.py`

```text
Summary check: agents with no web access confirm each row's summary against its abstract.

The checking agents see only the abstract, so a summary cannot claim what the
abstract does not say.

  --prepare   write summary_audit/batch_NN.json (summary + abstract pairs, up to
              --batch rows each, default 40), brief.md for the checking agents,
              and manifest.json. Old batch and result files are deleted first.
  --ingest    read summary_audit/result_NN.json and record `summary_check` on
              each row, bound to the summary, paper ids and abstract it checked

Rows already checked for their current summary are skipped unless --recheck. A
row with no abstract is recorded as `no-abstract`, a warning the audit makes you
acknowledge. --prepare refuses, and exits 1 on, a row whose abstract fetch FAILED
(abstracts_failed.json) or whose abstract entry was recorded for other ids.

--ingest checks each result against exactly what the checking agents saw. The
manifest records each ref's summary, paper (DOI/arXiv id) and abstract text, and
a ref whose summary, paper or abstract changed since --prepare is refused. Each
batch entry carries its `summary_sha`, and a result that does not echo it (or
echoes another) is refused. A manifest written before that binding existed (no
`ids`/`abstract_sha` maps at all) refuses every ref in it, rather than treating
each one as unchanged. --ingest exits 1 on any refused result, any ref with no
result, or any summary judged "unsupported"; fix those summaries and --prepare
again. It also exits 1 on a "wrong-abstract" verdict, which says the abstract on
file is not this paper's: add the real one as a landing-page entry in
abstracts.json (an empty text if it has none), rewrite the summary from it, and
--prepare again. The audit fails both verdicts (summary-flagged, abstract-wrong).

    python3 tools/summary_audit.py --rows rows.json --prepare
    #   checking agents write summary_audit/result_NN.json
    python3 tools/summary_audit.py --rows rows.json --ingest
```

### Phase 6: `candidates.py`

```text
The candidate ledger: record a decision on every paper that xref, forward citation or a survey suggests.

candidates.json maps each DOI to {title, year, first_author, sources, decision,
reason, at}. Keys that start with "_" are records, not candidates. `_runs` holds
{source: {at, n, complete, n_papers}}, written by each --add. From it the audit
can tell whether xref and forward citation were run, whether each run finished,
and whether it read every row with a DOI or arXiv id (not counting the included
candidates, which the run that proposed them cannot have read). `complete` and `n_papers`
come from the <FILE>.run.json sidecar that xref.py and forward.py write beside
their --out; a missing sidecar records complete=False. --add refuses a sidecar
written by a different tool than --source names, and skips candidates the corpus
already holds. A candidate whose title matches a table row (common.title_match),
with years no more than DUP_YEARS apart, is the same paper under another DOI,
usually a preprint of a published paper: --add excludes it at once, naming the row.

Deciding the rest is agent work, and the tool frames it:

  --prepare DIR --scope FILE   writes the pending candidates as DIR/input_NN.json
                               (--per per file, default 60) and DIR/BRIEF.md, from
                               tools/candidate_prompt_template.md. FILE defines the
                               bibliography (a lane brief or topic definition); the
                               lanes come from lane_manifest.json beside --rows.
                               Each candidate carries its CrossRef/DataCite record
                               and its abstract (abstracts.py's sources), fetched
                               here, so agents decide and summarize from them
                               instead of browsing for every paper.
  --ingest 'DIR/result_*.json' records the agents' decisions. It refuses the whole
                               batch if any entry lacks a reason, names a DOI not in
                               the ledger, or includes a paper without the claim
                               read off its landing page (first_author, year,
                               title, lane, summary).

The audit fails while any candidate is pending, or while an included candidate is
not in the table. A missing ledger, or a missing, incomplete or partial xref or
forward run, is a warning the audit makes you acknowledge. The spreadsheet lists
every excluded candidate with its reason on its "Considered and excluded" sheet,
so a paper left out of the review was visibly considered and set aside.

    python3 tools/candidates.py --rows rows.json --add xref.json --source xref
    python3 tools/candidates.py --rows rows.json --add forward_candidates.json --source forward
    python3 tools/candidates.py --rows rows.json --prepare manual_check/cand --scope briefs/brief_V.md
    #   one agent per manual_check/cand/input_NN.json writes result_NN.json
    python3 tools/candidates.py --rows rows.json --ingest 'manual_check/cand/result_*.json'
    python3 tools/candidates.py --rows rows.json --list pending
    python3 tools/candidates.py --rows rows.json --decide 10.1/x --decision exclude --reason "methods paper"
    python3 tools/candidates.py --rows rows.json --export-included cand_lane.json --lane C

--decide needs --decision and a --reason. --export-included writes the included
candidates that are not yet in the table as a schema-2 lane file, carrying each
include's landing-page claim and summary. Its --lane (default C) must be a key no
table row uses. Add it with
`merge_lanes.py --append xref_lane.json --into rows.json`, then verify the new
rows.
```

### Phase 6: `forward.py`

```text
Find papers that cite the corpus's landmark papers but are not in the corpus.

xref.py looks backward, at what corpus papers cite; this tool looks forward. It
takes the landmarks: the top --landmarks rows with a DOI (default 30), ranked by
within-corpus in-degree (internal_citations.json, from xref.py --internal-out),
then by citation count. For each landmark it asks OpenAlex for the most-cited
papers that cite it (up to --per-landmark, default and maximum 200). Each citing
paper is scored by how many corpus papers it cites. Those that cite at least
--min-shared corpus papers (default: the corpus size / 80, at least 3;
common.candidate_floor) and have a DOI become candidates for
candidates.py.

A citing paper is recognized as already in the corpus by its OpenAlex id or its
DOI. A corpus row with no DOI cannot be recognized, so it may come back as a
candidate. Because each pull is ordered by citation count, very recent papers are
under-represented.

    python3 tools/forward.py --rows rows.json --out forward_candidates.json --email you@inst.edu

It also writes `<out>.run.json` beside --out: {"complete", "incomplete": [refs
whose landmark pull failed], "at", "tool": "forward", "n_papers": rows with a DOI
or arXiv id}. candidates.py --add reads it to tell a partial run from a full one.

Exit 1 when any landmark pull failed (re-run), unless --allow-incomplete. A spent
OpenAlex daily budget stops the run with OpenAlexBudgetError.
```

### Phase 6: `xref.py`

```text
Build a cross-citation index: the DOIs that at least --min-cites corpus papers cite.

It finds papers the corpus cites often but does not contain. For each paper,
fetch its reference list from CrossRef, or from Semantic Scholar for an arXiv
paper or one CrossRef holds no list for. A paper with no DOI but a
`pdf` has the DOIs in its PDF read with pdftotext instead. Then count, for each
cited DOI, how many input papers cite it, and rank those cited by at least
--min-cites (default: the corpus size / 80, at least 3; common.candidate_floor).
--exclude drops DOIs the table already has, and
--resolve-unknown looks up missing titles in CrossRef (slow).

Input format (JSON list):
[
  {"slug": "Tang2023_decoder",
   "doi":  "10.1038/s41593-023-01304-9"},   # optional but strongly preferred
  {"slug": "JainHuth_arxiv",
   "doi":  null,
   "pdf":  "papers/topic_X/JainHuth_arxiv.pdf"},  # used as fallback
  ...
]

  python3 tools/xref.py --papers list.json --out xref.json --min-cites 3
  python3 tools/xref.py --rows rows.json --out xref.json     # slug = row key, DOI from doi/link
  python3 tools/xref.py --rows rows.json --out xref.json --exclude existing_dois.json \
          --resolve-unknown --internal-out internal_citations.json

With --rows, an arXiv-only row is looked up by its arXiv DOI, and a row with
neither a DOI nor a pdf is skipped. --internal-out also writes {slug:
internal_indegree}, how many OTHER corpus papers cite each corpus paper, which
families_figure.py and forward.py use to pick landmarks.

Every completed reference list is cached, by slug and DOI (or PDF), in
<out>.refs.json or --cache. So a re-run after a throttled or interrupted pass
fetches only the lists that are missing, incomplete or for an edited DOI;
--no-cache refetches everything.

Semantic Scholar needs S2_API_KEY to be reliable. xref, citations and abstracts
share one key, and their requests take turns through a pacer shared across
processes, so they may run at the same time. Semantic Scholar reference lists are
fetched in chunks of 10, and a failed chunk gets one more try in half-size
chunks. A CrossRef fetch that fails transiently gets a second try at the end of
the run, after --retry-wait.

Output: a JSON list of {doi, n_citations, cited_by: [slugs], title, year,
author, journal, raw}, most cited first. It also writes `<out>.run.json` beside
--out: {"complete", "incomplete": [slugs still unfetched], "at", "tool": "xref",
"n_papers": papers with a DOI, arXiv DOIs included}. candidates.py --add reads it
to tell a partial run from a full one.

Exit 1 when any reference list could not be fetched, because those papers
contributed no references and every count is low; re-run, or pass
--allow-incomplete to accept the gap and say so.
```

### Phase 6b: `families.py`

```text
Validate a family taxonomy, stamp `family` onto rows.json, and write families.json and families.md.

The carving is judgment: the agent proposes a few families and assigns every
paper, with a human checkpoint on the family definitions (see
family_prompt_template.md and PLAYBOOK Phase 6b). On every review the agent
proposes families and pitches the timeline built from them. The user uses the
families, changes them, or skips the timeline. This tool does the mechanical
half. It checks that the assignment is exhaustive and exclusive, warns when it is
unbalanced, stamps the rows, and renders families.md (tables by family plus a
family x topic cross-tab). families.json is the reproducible cache, like
citation_counts.json, so re-run only when the taxonomy changes.

Do not cluster embeddings to make families. Good theoretical families cut across
textual similarity: they unite dissimilar papers and split similar ones. So the
proposal must be an LLM synthesis, not a distance metric. See PLAYBOOK.

INPUT (--assign FILE): the JSON the agent produced and the user approved:
  { "principle": "one line naming the organizing axis (orthogonal to Topic)",
    "families": [ {"key":"compress", "name":"Compress",
                   "claim":"one-line claim", "lineage":"A -> B -> C"}, ... ],
    "assignments": { "<ref>": "<family key>", ... },    # every rows.json ref, once
    "hard_calls": [ {"ref", "assigned", "also_fits", "why"}, ... ] }

The hard calls are the papers the assignment agents found a poor fit, or a fit
to two families. The agents do not argue with the spec, so these are the only
place a wrong family definition shows. The tool prints each one to read before
rendering, and warns when the input records no `hard_calls` at all.

It stops with an error on a duplicate family key, fewer than 2 or more than 9
families (3-8 recommended), an unassigned paper, a ref not in rows.json, or an
unknown family key. An assignment may name a family by key or by display name,
in any case, so it can be rebuilt from the `family` already stamped on the rows.
It warns on a one-paper family or one holding more than 60% of the papers, and
drops empty families.

--results GLOB (repeatable) merges the assignment agents' result files into the
spec's assignments. Each file is {ref: key}, or {"assignments": {...},
"hard_calls": [...]}, and a file that re-assigns a ref differently is refused.
--default-from-lanes is for lab mode, where each lane is a theme. It assigns each
row that no result covered to its `lane_fit` when that is a family key, else to
its lane key when that is one.

A family whose `lineage` is empty gets one mechanically: its six rows with the
most within-corpus citations (internal_citations.json beside --rows, with the
OpenAlex count breaking ties), oldest first, marked `lineage_source`.

  python3 tools/families.py --rows rows.json --digest     # compact corpus for the proposal
  python3 tools/families.py --rows rows.json --assign families_input.json \
          --out families.json
  python3 tools/families.py --rows rows.json --assign spec.json --results 'batches/result_*.json' \
          --default-from-lanes --out families.json      # merge agent results; lab mode
```

### Phase 6b: `families_figure.py`

```text
Render the interactive lineage timeline of the theoretical families.

It writes one self-contained .html (inline SVG, CSS and JS; no dependencies, no
network), a standalone .svg, and a .png and .pdf when rsvg-convert or inkscape is
installed. Because the timeline is offered on every review, the standard settings
are the defaults: dots sized by citation count, internal_citations.json read from
beside rows.json, and the exact arguments recorded in figure_render_args.txt.
That file holds hand-written tuning notes, so it is created when missing and
never overwritten; the tool says when a render is not recorded in it.

Open the .html in a browser and present it fullscreen. Hover a dot to see its
full reference; click it for a side panel with the citation, summary and a live
DOI link. Hover or focus a family's name for a panel with the family's claim, its
lineage in full and its paper count, while its papers are spotlighted. The
exported .svg, .png and .pdf carry the same family text in a native SVG <title>,
since no script runs there. The side panel's Prev/Next buttons (and the
left/right arrow keys) step through the papers in year order, so a reader can
walk the timeline instead of hunting for dots. A checkbox switches between
stepping within the selected family and across the whole corpus.

Family lanes come from families.json and dots from rows.json: one dot per paper,
packed by year within its lane.

LANDMARKS are selected and labeled automatically (big dots). A paper is a
landmark if ANY of:
  (1) it is among the most-cited in its family (top --per-family, default 4, by
      max(OpenAlex, S2));
  (2) it is foundational within this review: cited by >= --motif-min (default 3)
      of the corpus's own papers (needs internal_citations.json from
      `xref.py --internal-out`, read from beside rows.json unless --internal
      names another; skipped if there is none);
  (3) it is a home-lab paper: a row with source == "lab", or one with an author
      surname given by --lab-author Surname (repeatable) or the
      LITREVIEW_LAB_AUTHOR env var (comma-separated; both off by default).
      Home-lab papers are starred (★) and ringed in --lab-color (default gold,
      moved automatically if it clashes with a family lane; quote the #).
--max-labels (default 28) caps the total for legibility. When the cap bites, the home-lab
papers and the top 2 most-cited per family always survive, and within-review
in-degree fills the rest. On a large corpus that cites itself densely, hundreds
of papers can clear --motif-min, so the cap is what keeps the figure readable.
When the cap drops labels, the run says how many; raise --max-labels or
--motif-min if that number is large. A "labels" map in --spec replaces the
automatic selection (manual curation wins); --no-auto-landmarks turns labeling
off.

DOT SIZE encodes citation count by default (--size-by-citations sqrt), with a
size legend; landmark status rides on the ring, leader and label. A paper with no
count is drawn hollow, not as a zero. `--size-by-citations none` gives the older
binary dots (big = labeled landmark, small = everything else), which say nothing
about how often a paper is cited. Counts span four orders of magnitude in a real
corpus (0 to ~24k), so both scales normalize against the 95th percentile and
clamp above it. `sqrt` is area-proportional and separates the heavy tail; `log`
compresses harder and reads flatter. Citation count is partly an AGE variable,
so the right-hand edge of any timeline is small. --size-range MIN,MAX sets the
dot radius range in pixels (default 2.0,11.0).

OTHER OPTIONS. For a long time span, --time-warp (0 to 1) compresses sparse early
decades, and --min-year clamps the axis start. --xlsx embeds the spreadsheet with
a download button. --emphasize-source lab draws one source's rows large.
--no-raster skips the PNG and PDF.

  python3 tools/families_figure.py --rows rows.json --families families.json \
          --out-prefix mytopic_families --title "My topic — theoretical families"

OPTIONAL editorial overlay (--spec figure_spec.json), all keys optional:
  { "labels":  {"<ref>": "short label", ...},     # which papers to label (overrides auto-selection)
    "arrows":  [{"from":"<ref>","to":"<ref>","color":"#b00020","label":"..."}],
    "notes":   [{"at":"<ref>","text":"...","color":"#333"}],
    "order":   ["FamilyName", ...],                # lane order (default: families.json order)
    "subtitle":"..." }
The arrows and notes are editorial: curate them with the user, and do not expect
a good automatic set. See PLAYBOOK Phase 6b.

Check the interactive layer by running it, never by reading it (Node.js):
`node tools/checks/verify_hover.mjs <figure>.html` runs the page's own lane-hover
handler for every lane, and `node tools/checks/verify_nav_order.mjs <figure>.html`
checks that Prev/Next walks each year's column in order.
```

### Phase 7: `bib_viewer.py`

```text
Render a searchable bibliography of the whole corpus, for a page that has no timeline.

A review page does not use it: the review embeds the interactive timeline, which
already carries every paper's reference, summary and counts, so a second browser
beside it would be duplication. Use this viewer for a corpus with no review
attached, or wherever the references are wanted as text rather than as a plot.
It lets a reader get from a claim to the summary behind it. It lists the WHOLE corpus, grouped by theoretical
family, including the references the review never cites: which papers went
uncited is itself evidence about the review's scope. It has a live search box, a
"cited in this review only" filter, and a chip on each cited entry that links to
its numbered works-cited entry.

The viewer can carry a provenance note that names who wrote the summaries and
says they come from abstracts, not full texts. A model-written review states its
authorship once. So pass provenance=False from a review page whose masthead
already carries that disclosure, and leave it on for a standalone viewer.

To embed it, call it from a project's `build_review_page.py`:

    import bib_viewer
    block = bib_viewer.render(rows, spec=common.load_json("families.json"),
                              cited={"C-01": 12, ...},          # ref -> citation number
                              author="Claude Opus 5",
                              author_note="An artificial intelligence developed by Anthropic")
    ... page CSS += bib_viewer.CSS ... page body += block ... page JS += bib_viewer.JS

`render` returns only the block, so the host page owns its <section>, heading and
design tokens. The CSS uses the token names every page in this toolkit defines
(--panel, --sunk, --band, --ink, --ink-2, --muted, --rule, --rule-2, --accent,
--accent-ink, --accent-soft, --f1..--f6, --display, --body, --data).

For a corpus with no review attached, it writes a complete viewer page:

    python3 tools/bib_viewer.py --rows rows.json --families families.json \
            --out corpus_viewer.html --title "Cortical layers" \
            --author "<model>" --author-note "<what the model is>"

Without --author the page carries no provenance note, and the tool warns.

Check the filter by running it, never by reading it:
`node tools/checks/verify_bib_filter.mjs <page>.html` runs this module's JS
against a stub DOM built from the rendered entries.
```

### Phase 7: `cite_check.py`

```text
Gate: every in-text citation in a review must name a paper in rows.json.

A review's reference list is built from rows.json. An in-text citation that names
no row is a reference the reader cannot follow. An author-year that matches TWO
rows is a citation the reader cannot resolve. The renderer cannot see either
problem, because it prints whatever prose it is given.

  python3 tools/cite_check.py --rows rows.json --content content.json

It reads the `abstract` and every `sections[].paragraphs[]` of the content JSON.
It parses APA author-date citations in parenthetical form ("(Farb et al., 2007)")
and narrative form ("Farb et al. (2007)", "Farb and Segal (2007)"). It folds
accents ("Millière" matches "Milliere") and checks each citation against
author-year keys built from the canonical `apa` strings.

Exit 1 on an UNRESOLVED citation, because the reference list cannot back it.
AMBIGUOUS citations are warnings, because the fix is editorial. APA-7 8.19 names
enough further authors to tell the two apart ("(Kral, Davis, et al., 2022)"),
which this tool cannot write for you.

APA-7's other disambiguator is a year suffix (2025a, 2025b). references.py and
this tool both accept one. Adding it means editing the canonical `apa` strings in
rows.json, so the extra-author form is usually the cheaper fix.
```

### Phase 7: `prose_audit.py`

```text
Measure a review's prose, and check that a revision pass lost no citation.

A model-written review is rarely wrong and often unreadable. The recurring defect
is compression, not fancy words: four or five findings chained through
semicolons into one 60-120 word sentence, each with its own citation. The prose
is accurate, and nobody can follow it. cite_check.py cannot see this, because it
asks only whether the citations resolve.

  python3 tools/prose_audit.py --page build_review_page.py    # [[REF]] markers
  python3 tools/prose_audit.py --content content.json         # APA author-date

For each prose block it reports words, sentence count, mean and longest sentence
length, and citation count, and it lists the longest sentences (at least --long
words, default 45). Aim for a mean of 25 words or less. It then reports pairs
of blocks that share at least --overlap citations (default 8), which is how one
argument gets told twice in two sections. --exclude REGEX skips blocks whose label matches. A page script is
read by parsing it, never by importing it.

Rewriting for concision can drop citations unnoticed, so this tool is also the
gate on that pass. Keep a copy of the source before revising, and compare
against it:

  cp build_review_page.py /tmp/before.py      # then revise
  python3 tools/prose_audit.py --page build_review_page.py --baseline /tmp/before.py

Exit 1 if any citation in the baseline is missing afterward (a reference cut
from the works cited). Long sentences are reported, never gated: how short a
sentence should be is editorial, and a list-like sentence with parallel clauses
can run long.
```

### Phase 7: `review_paper.py`

```text
Build a review article (.docx) from a finished review corpus.

This tool owns only the mechanics: the title, author and disclosure block, the
abstract, the section headings and paragraphs, an embedded figure with its
caption, and an APA-7 reference list. The reference list holds every row's
canonical `apa` from rows.json (deduplicated, hanging indent, each with its
link). It follows APA-7 order: authors letter by letter, then year, then title,
so a sole author precedes that author's co-authored works. reference_list()
builds it, and HTML pages should reuse it.

It does NOT write prose. Write the prose separately with the scientific-writing
skill, and supply it as a content JSON (--content). In-text citations are APA
author-date, e.g. "(Huth et al., 2016)". Every in-text citation must name a paper
in rows.json. This tool prints whatever prose it is given, so before rendering
run the priority audit (every origin claim cites the earliest paper) and
cite_check.py.

If the review is AI-authored, say so: put the model's name in `authors`, an
`author_note` identifying it as an AI, and a `disclosure` paragraph (the
fabricate-then-verify caveat; see PLAYBOOK Phase 7). State in the disclosure
that the bibliography was machine-verified and that the author read abstracts,
not full texts.

content.json schema:
{
  "title": "single string (\n allowed for a two-line title)",
  "authors": ["Claude Fable 5"],
  "author_note": "An artificial intelligence developed by Anthropic",
  "affiliation_line": "Prepared for ... · DD Month YYYY",
  "disclosure": "Author's disclosure: ...",          # optional
  "abstract": "one paragraph",
  "sections": [ {"heading": "1. Introduction", "level": 1,
                 "paragraphs": ["para one", "para two"]}, ... ],
  "figure": {"path": "<topic>_families.png", "caption": "Figure 1. ..."},  # optional; --figure overrides
  "references_heading": "References",                 # optional (default "References")
  "references_note": "..."                            # optional; "{n}" is replaced by the count
}
A relative figure path is read from the folder of --out.

  python3 tools/review_paper.py --rows rows.json --content content.json \
          --out <Topic>_review.docx [--figure <topic>_families.png]
```

### Lab mode L1: `lab_corpus.py`

```text
Lab mode: fetch a lab's full publication corpus from OpenAlex.

Topic mode starts from a query and searches outward. LAB MODE starts from a known
set of papers (a lab's output), derives its themes, tracks them over time, and
only then searches outward to place them in the field. This tool fetches that
corpus, the seed everything else hangs off. In lab mode, it and lab_lane.py run
before the search lanes.

Give it an OpenAlex author id; find one with --search first. "All papers from a
lab" is approximated by the PI's authored works. Pass several ids with repeated
--author for either of two reasons: to widen coverage to key lab members, or
because ONE PERSON's record is split across ids, which is common and easy to
miss. Works are deduplicated by OpenAlex id. --from-year and --to-year limit the
publication years.

  python3 tools/lab_corpus.py --search "Jack Gallant"          # find the id
  python3 tools/lab_corpus.py --author A5056348548 --out lab_papers.json
  python3 tools/lab_corpus.py --author A50… --author A51… --out lab_papers.json

Output: lab_papers.json, one row per paper, sorted by year and keyed L1, L2, …,
with ref / openalex / doi / link / title / year / venue / apa / cite_openalex /
topic / topics / summary (the abstract, else the title) / coauthors / type /
source ("lab") / built_at.

Disambiguation is the main correctness risk, and it cuts both ways. An id can be
MERGED (holding several namesakes, so Phase L2 must prune it) or SPLIT (one
person across several ids, so Phase L2 must ADD the others, and nothing fails
when a record is missing). This is why --search prints each id's year span and
ORCID; read its warnings. OpenAlex abstracts are patchy and its topic tags too
coarse, so fetch abstracts from Semantic Scholar or PubMed before the Phase L2
check. See PLAYBOOK "Lab mode" for the later steps.
```

### Lab mode L2: `lab_lane.py`

```text
Lab mode, Phase L2: check the lab's record by content, then turn it into lane L.

An author id's record (lab_corpus.py) holds meeting abstracts, errata, peer-review
reports, a preprint and its published version as two works, and sometimes a
namesake's papers. Classifying it from database tags mislabels papers, so agents
read each item and decide; this tool does the mechanics around them.

  --prepare   split lab_papers.json into lab_check/input_NN.json batches of
              --batch items (default 90), with any abstracts fetched by
              abstracts.py, and write lab_check/brief.md for the checking
              agents. One agent per input file writes
              lab_check/result_NN.json: per item by_pi (authorship), kind,
              species, duplicate_of, include, theme and reason.
  --build     join the record with every result into search_raw/0_L.json, a
              schema-2 lane (source "lab", the record's OpenAlex claim as the row's
              claim). It refuses an item with no check, a result for an item not in
              the record or checked twice, an included duplicate, an included item
              not by the PI, and (with --themes) a theme not in that file. The file
              sorts first, so a lab paper a field lane also found keeps its lab row.
              Each excluded item is listed in the lane's `excluded` with its
              reason. An included item with no DOI keeps its OpenAlex reference
              and gets a hand check (Phase 3e).

    python3 tools/lab_lane.py --prepare --papers lab_papers.json --abstracts lab_abstracts.json \
            --pi "Jack L. Gallant"
    #   one checking agent per lab_check/input_NN.json writes lab_check/result_NN.json
    python3 tools/lab_lane.py --build --papers lab_papers.json

--themes themes.json (optional): [{"key": "V", "name": "...", "claim": "..."}],
the lab's approved themes (Phase L3). Field lanes defer the lab's papers to lane L, so the merge
then fails on any lab paper the record lacks: that is the completeness check.
```

### Shared helpers: `common.py`

```text
Shared helpers for the literature-review toolkit.

Every tool imports this one module, so each guarantee lives in one place:

  - HTTP: a polite User-Agent, gzip decoding, and a GET/POST with backoff on
    rate limits and timeouts. An OpenAlex request carries OPENALEX_API_KEY when it
    is set, and a spent OpenAlex daily budget raises OpenAlexBudgetError at once.
    Semantic Scholar requests carry S2_API_KEY when it is set, and are paced
    across every process on the machine (s2_wait_turn), so the tools that share
    the key may run at the same time.
  - Sources: the CrossRef, DataCite and arXiv record readers, and batched arXiv
    and Semantic Scholar lookups.
  - References: DOI and arXiv-id parsing, the APA-7 name and reference formatter
    (so the canonical-reference guarantee lives in exactly one place), the one
    APA parser every tool reads a reference back with, and title matching.
  - The live table: JSON load/dump that always reads and writes UTF-8
    (ensure_ascii=False), write guards that refuse to overwrite a canonical or
    changed rows.json, the stamps and hashes the reference gates check, and the
    hand fixes (hand_fixes.json) that every tool rewriting `apa` re-applies.
  - Search scale: SEARCH_SCALES and scale_plan, which turn the size of search
    the user asked for into lane targets, a cap and a lane-count range.

Tools are run as `python3 tools/<tool>.py`, so `tools/` is on sys.path[0] and a
plain `import common` resolves.

The hot-papers repo imports this module too (it has no copy), through HDRS,
http, http_json, load_json, dump_json, doi_of, arxiv_id_of, ARXIV_NS and ATOM.
Run its tests before changing any of them.
```
<!-- END GENERATED TOOL DETAILS -->

## Other files

- **`search_prompt_template.md`**: the brief for a Phase 2 search agent, rendered
  by `lane_briefs.py` (never filled by hand). It defines the schema-2 lane file
  that `merge_lanes.py` reads.
- **`candidate_prompt_template.md`**: the brief for the agents that decide the
  candidate ledger, rendered by `candidates.py --prepare` (never filled by hand).
- **`family_prompt_template.md`**: the two-step propose-then-assign prompt for
  Phase 6b, including the hard calls.
- **`checks/`**: the Node.js checkers that execute a page's own script, for the
  timeline (`verify_hover.mjs`, `verify_nav_order.mjs`) and the bibliography
  viewer (`verify_bib_filter.mjs`). The `families_figure.py` and `bib_viewer.py` sections above say what each
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
