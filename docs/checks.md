# Checking

This page covers every check between the merge and the deliverables. Both modes
run these steps. Commands run in the project folder and reach the scripts as
`../tools/` ([Where files live](pipeline.md#where-files-live)). For the order and
which steps run at the same time, see
[The order the agent runs](pipeline.md#the-order-the-agent-runs).

---

## Verify every citation (Phase 3)

Verification checks every row against the registries before anything else
trusts it.

```bash
python3 ../tools/verify.py --rows rows.json --out verify_report.json
```

**What it does.** `verify.py` checks every citation against PubMed, PMC,
CrossRef, DataCite and arXiv, and exits 0 only when every verdict is `OK`.

- **The claim.** Before canon, a row is checked against what its search lane
  reported, kept as `search_author`, `search_year` and `search_title`. After
  canon, the canonical `apa` must agree as well. A row with both an arXiv id and a
  journal DOI has both checked. The year may differ by one, since a preprint and
  its version of record often do.
- **Where a DOI must resolve.** A journal DOI is verified only by its own CrossRef
  record. When CrossRef has no such DOI (a 404), `verify.py` looks in DataCite,
  where Zenodo, figshare, OSF and Dryad register software, data sets and some
  preprints. Resolving there counts the same. Any other CrossRef error is an
  `ERROR` to rerun. A DOI that resolves in neither registry is a `MISMATCH`, even
  when a PubMed or title search finds the claimed paper.
- **First authors.** A record's first author is trusted only when the registry
  deposited it structured, as a family name and a given name. Anything else makes
  the verdict `MISMATCH`, with the note "confirm by hand". The full rules are
  below.

| Verdict | Meaning | Action |
|---|---|---|
| `OK` | the record matches the claim | none |
| `MISMATCH` | the record resolves but disagrees on author, year or title, or its first author needs a human | fix or drop the row, or confirm it by hand and override |
| `NOT-FOUND` | every lookup completed and nothing matched | chase it; it is likely invented |
| `ERROR` | a lookup could not complete (rate limit, network) | rerun |
| `UNCHECKED` | the row carried no author, year or title to check against | add the claim, rerun |

**The verify stamp.** With `--rows`, verification stamps each row with
`verified`: the verdict, DOI and arXiv id, source, issues and date. Canon and the
audit read this stamp to know what was checked and against which ids. The stamp
lapses as soon as the row's DOI or arXiv id changes. `--no-stamp` reports
without writing. To recheck a few rows, name them with `--only A-01,B-02`.

**Clearing a false alarm.** When a person confirms that a non-OK verdict is wrong
(a preprint retitled on publication, say), record an override:

```bash
python3 ../tools/verify.py --rows rows.json --override A-07 --reason "retitled on publication; same paper"
```

The override is refused without an existing stamp, without a reason, or when the
row's DOI or arXiv id changed since it was verified.

**Re-verifying a canonical row.** Once a row is canonical, its `apa` comes from
the same DOI that verification checks. A rerun with nothing else to check against
is a circular self-check, so it does not downgrade the row. If the row already
carried an independent OK for the same ids, that stamp is kept, and
`reverified_at` records the rerun. A canonical row with no claim at all is
covered in [Upgrade an old corpus](reruns.md#upgrade-an-old-corpus).

??? note "The first-author rules in full"
    The check compares surnames, never initials.

    - **Structured records** are read by their source's "Family INITIALS"
      contract: "Collins AGE" is Collins, "Van DAM J" is Van DAM, and an arXiv
      "Aaron van den Oord" becomes "van den Oord A".
    - **Records flagged for a human:** a DataCite first creator without both
      `familyName` and `givenName`, unless it reads "Family, Given" or is a
      declared organization; a CrossRef first author with no given name, or a first
      entry with no family name; an arXiv name with a capitalized word ("CHEN
      Hao"); a bare name the contract cannot read ("Hae-Jeong Park", "Hao CHEN J").
    - **Records accepted as they are:** bare records with spaced initials or a
      comma list ("Kim J H", "Chen, Hao H"), and a CrossRef whole name deposited
      as the family name.
    - **Claims** are read once, in whatever shape they were reported. "Smith J",
      "J. Smith" and "Smith, J." all give Smith; "Lambon Ralph, Matthew A." gives
      Lambon Ralph. A list such as "Smith J; Jones K" gives its first name. A claim
      of given-first words ("John Smith") needs each given name to start with one
      of the record's initials.
    - **Ambiguous claims.** In "Hao CHEN" or "Collins AGE", a capitalized word may
      be the surname or initials, so the claim is reported as ambiguous, to
      confirm by hand. A claim led by a capitalized particle ("DU Wei") matches
      only a record that carries the particle.
    - **Whole-word surnames.** The claim's surname must be a whole word of the
      record's, or one part of a hyphenated one. "Heuvel" matches "van den
      Heuvel" and "Hanna" matches "Andrews-Hanna", but "Han" matches neither. A
      particle alone is not enough, so "Van Essen" does not match "Van Dijk".
      Every word of a compound claim must appear, so "Lambon Ralph" does not
      match "Ralph J".
    - **Initials never decide a match.** "J. Smith" cannot match "Jones J", nor
      "Min" match "Seung-Min Park". Initials in any script count as initials, so
      "Nowak Ł" does not match "Kowalski Ł".
    - **Group authors** ("ATLAS Collaboration", "Stanford University", "The
      pandas development team") are compared whole, and "An" stays a surname.
    - **Unknown names fail the check** on either side: "?", "anon", "Anonymous,
      A.", "[No authors listed]", or no readable word.

    `merge_lanes.py` uses the same comparison for its duplicate and deferral
    checks. It never merges rows, or confirms a deferral, on an unknown author.

!!! warning "Rerun every non-OK verdict before acting on it"
    Network failures can look like bad citations. `ERROR` rows get one automatic
    retry at the end of the run, but check the rest anyway: a second run often
    clears them. `--retry-from verify_report.json --out verify_report.json`
    rechecks only the non-OK rows and keeps the others.

## Hand-check references with no DOI (Phase 3e)

A book, report, thesis or web essay has no DOI or arXiv id, so no script can
verify it. On a gated table ([What switches the gates on](reruns.md#what-switches-the-gates-on)),
the audit fails each such row until it has a recorded hand check.

```bash
python3 ../tools/handcheck.py --rows rows.json --prepare
python3 ../tools/handcheck.py --rows rows.json --adopt-dois handcheck_doi_candidates.json
# dispatch a hand-check agent with handcheck_brief.md and handcheck_input.json
python3 ../tools/handcheck.py --rows rows.json --ingest handcheck_result.json
```

**`--prepare`** first looks for a DOI the row turns out to have. It searches
CrossRef and OpenAlex for the same title (not one merely contained in a longer
title) and the same year, and writes what it finds to
`handcheck_doi_candidates.json`. Every other row with no DOI goes into
`handcheck_input.json`, with a brief for the checking agent,
`handcheck_brief.md`. Each input entry carries `apa_sha`, a hash of the reference
text it shows (the row's `apa`, else its `search_apa`). An existing
`handcheck_result.json` answers the previous `--prepare`, so it is renamed to
`handcheck_result.stale-<timestamp>.json`, never deleted.

**`--adopt-dois`** gives each row with exactly one candidate that DOI, so the row
goes through `verify.py` like any other. A row with several candidates is left
alone and named. A row no longer in the table is reported. When every candidate
is the wrong paper, record that, and the next `--prepare` skips those DOIs and
sends the row to the hand check:

```bash
python3 ../tools/handcheck.py --rows rows.json --reject Y-19 --reason "both candidates are reviews of it"
```

**The hand-check agent** checks each work against its own source: a library
catalog, the publisher's page, or the work itself, never another paper's citation
of it. It writes `handcheck_result.json`, one entry per row: the verdict
(`confirmed`, `corrected` with the corrected APA, or `not-found`), the source it
checked, and the `apa_sha` copied from the input entry.

**`--ingest`** records each result on its row as `hand_verified`, with a hash of
the `apa` it confirmed, so a later edit to that `apa` lapses the check. It
refuses a result, and you rerun `--prepare`, when:

- the row's `apa` changed since `--prepare`;
- the row never went through `--prepare`, or the input file (`--input`, default
  `handcheck_input.json`) predates `apa_sha`;
- the result's `apa_sha` is missing, or differs from its input entry's.

A `not-found` result exits nonzero: remove the row, or check it again.

Hand checks can run while `verify.py` runs. Both tools write `rows.json`, so run
`--ingest` after verification finishes. A tool that finds `rows.json` changed
since it loaded the file refuses to write, rather than lose the other tool's
work.

## Rebuild every reference (Phase 3f)

Canon rebuilds every reference from its verified DOI, so no reference is typed
by an agent or copied from a database.

```bash
python3 ../tools/references.py --rows rows.json --out rows.json
python3 ../tools/references.py --rows rows.json --audit    # exits 1 on any defect
```

**What it does.** `references.py` rebuilds every reference into APA-7 from its
verified DOI or arXiv id: full author lists, name particles, real venue names
(including bioRxiv and PsyArXiv), and unescaped HTML. A journal DOI replaces an
arXiv preprint as the version of record. Only a book or report with no DOI keeps
a hand-written reference.

**Canon rebuilds only verified rows.** It rebuilds a row only when the row's verify
stamp is OK, or overridden, for its current DOI or arXiv id. This refusal holds on
every table, including one built before the reference gates existed. Any other
row keeps its existing `apa`, is named, and the run exits 1. Re-verify those rows
first (`verify.py --rows rows.json --only A-01,B-02`), then rerun canon. A
targeted re-canon (`references.py --only ...`) likewise needs its rows verified
first.

**DataCite records.** A DOI that CrossRef does not hold is rebuilt from DataCite
as `Authors (Year). Title (Version v) [Data set|Computer software|Preprint].
Publisher.` The bracket and `(Version …)` are left out when DataCite has none. The
title is DataCite's main title plus its subtitle. A creator with no given name is
split only when that is safe:

- "Doe, John" splits, and so does a personal name such as "Jagroop Singh Doad"
  or "Doad J S", which becomes "Doad, J. S.".
- A `familyName`, when given, is the surname if `name` contains it as a whole
  word.
- A name is never split on trailing initials, or into a one-letter surname.

**Flags for a human.** Canon stores these on the row as `canon_warnings`, and the
audit makes you acknowledge each ([Acknowledge warnings](#acknowledge-warnings)):

| Flag | Raised when | What to do |
|---|---|---|
| `datacite-unsplit-author:<name>` | a creator that cannot be split safely ("The pandas development team", "Collins AGE") | confirm the name is right as a whole |
| `datacite-deposit` | a DataCite record that is neither software nor a data set: a repository copy | cite the version of record's DOI, if one exists |
| `published-version` | a CrossRef preprint whose server records its published version | `references.py --adopt-published` moves the row to that DOI, keeps the old one as `preprint_doi`, and verify then allows the later year |

**The audit.** `references.py --audit` is a hard gate: it exits 1 on any defect.
It also warns about near-duplicate rows and about multi-word surnames that may be
given names folded in. Registries also swap given and family names for a whole
author list, put a suffix inside the surname (`Náñez Sr, J. E.`), or (Research
Square) list the corresponding author first. Check the order against PubMed or
the landing page, and fix it in `hand_fixes.json`. Read the warnings even when
the gate passes. On a gated table, an unacknowledged warning fails the audit too.
`--repair` fixes string damage (markup, Unicode hyphens, `?.`) offline, without
re-fetching or undoing hand fixes. It stamps `canonical_at` only on a legacy
table, never on a gated one.

**Hand fixes survive every re-canon.** Some records are wrong at the registry: a
compound surname split in two, two authors packed into one, a missing subtitle
or year. Canon re-fetches on every run, so a fix typed into `rows.json` alone
would be undone. Record each fix in `hand_fixes.json`, beside `rows.json`:

```json
{"<ref>": [{"old": "<the damaged text>", "new": "<the final text>", "why": "<the source>"}]}
```

Write `new` in its final form, sentence case included. Canon and
`sentence_case.py --apply` re-apply every fix after they write. The audit fails a
row whose fix is gone (`hand-fix-lost`). Canon exits 1 on a fix whose damaged and
final text are both missing from the row, because the row changed underneath it.

From here on, `rows.json` holds the canonical references, and regenerating it
would wipe them ([rule 6](pipeline.md#the-rules)).

### Sentence-case the titles

APA titles use sentence case. Run it as a reviewed pass, after canon:

```bash
python3 ../tools/sentence_case.py --rows rows.json --proper proper_nouns.json --vocab
python3 ../tools/sentence_case.py --rows rows.json --proper proper_nouns.json --apply
```

`--vocab` lists each distinct word change for review, and `--apply` writes the
changes. `proper_nouns.json` lists the words and phrases that keep their capitals,
as `{"words": [...], "phrases": [...]}`. A DataCite deposit's `(Version …)` and
bracket descriptor follow the title, so they are never cased, and `verify.py`
compares only the title itself.

!!! warning "Non-English titles are skipped by default"
    Sentence case would lowercase German nouns, so `sentence_case.py` detects and
    skips titles that look German or French, and lists them.
    `--include-foreign` overrides.

## Fetch citation counts (Phase 5b)

```bash
python3 ../tools/citations.py --rows rows.json --out citation_counts.json               # fetch
python3 ../tools/citations.py --rows rows.json --out citation_counts.json --attach-only # attach
```

**What it does.** OpenAlex is the primary source (about 95% coverage by DOI), and
Semantic Scholar is the cross-check. Google Scholar has no API and blocks scripts,
so it is not used. Counts are a snapshot: record the `--asof` date, and do not
expect the two sources to agree. An arXiv-only row is looked up by its arXiv DOI.
A row with neither a DOI nor an arXiv id stays blank.

- **Fetching and attaching are separate steps.** The fetch writes
  `citation_counts.json` and leaves `rows.json` alone, so it can run while canon
  does. The spreadsheet's count columns and the timeline's dot sizes read the
  counts from the rows (`cite_openalex`, `cite_s2`). So once canon has finished,
  attach them with `--attach-only`. `--attach` fetches and attaches in one run,
  when no other tool is writing `rows.json`.
- **A rerun keeps what an earlier run found.** Where a lookup comes back empty
  but `citation_counts.json` already has a count, the earlier count stays. So a
  rerun to fill Semantic Scholar gaps never loses coverage.
- **A low OpenAlex count is re-queried.** OpenAlex's batch endpoint sometimes
  returns a stub record: Tolman (1948) came back as 1 from the batch and 6,656
  from the single-work endpoint. When the OpenAlex count is far below Semantic
  Scholar's, `citations.py` re-queries the single-work endpoint and keeps the
  higher count. Spot-check the landmarks anyway.

!!! warning "Not every journal DOI is the version of record"
    Before replacing a preprint's DOI, check the candidate's OpenAlex count.
    Proceedings.com DOIs for printed NeurIPS volumes (`10.52202/*`) resolve but
    are shadow records; switching to them cut counts three- to fourfold on a real
    corpus. ACL Anthology (`10.18653/*`), IEEE/CVF (`10.1109/*`) and journal DOIs
    are genuine upgrades.

## Check every summary (Phase 5c)

A summary can drift from what its paper found, the same way a citation can be
invented. So it is checked the same way: against an authoritative record, by an
agent that sees nothing else.

```bash
python3 ../tools/abstracts.py --rows rows.json
python3 ../tools/summary_audit.py --rows rows.json --prepare
# dispatch one checking agent per summary_audit/batch_NN.json, with the brief summary_audit/brief.md
python3 ../tools/summary_audit.py --rows rows.json --ingest
```

**Fetch the abstracts.** `abstracts.py` fetches every row's abstract once, into
`abstracts.json`, from the most authoritative source that has one: the arXiv API
for arXiv papers, then OpenAlex, Semantic Scholar, PubMed (by PMID, then by DOI),
and Europe PMC.

- Each entry records the `doi` and `arxiv` it was fetched for, and is fetched
  again when the row's ids change.
- A hand-added entry (`"source": "landing-page"`, with the row's `doi` and
  `arxiv`) is never overwritten. One whose ids no longer match is reported as
  stale. An entry with an empty `text` records that the paper has no abstract.
- A fetch that fails is reported separately from a paper with no abstract, and
  written to `abstracts_failed.json`.
- **Text that is not an abstract is refused**: a journal's self-description,
  JSTOR's terms of use, a citation line for another item, an author list and
  venue, or an abstract with text lost around a `<` or `>` sign ("RESULTS: =
  0.8"). A summary written from one of these describes the text, not the paper,
  so `abstracts.py` reports it and tries the next source.

**Every row needs a summary.** On a gated table, a row with an empty summary is a
defect (`no-summary`). Rows exported from the candidate ledger arrive without one,
so write theirs from the abstract before `--prepare`.

**Prepare the batches.** `summary_audit.py --prepare` splits the rows that need a
check into batches (`--batch`, default 40), each with its summaries and abstracts,
and writes a brief and a manifest. It exits 1 on a row whose abstract fetch failed
or whose abstract was recorded for other ids: rerun `abstracts.py`, or add a
landing-page entry. `--prepare` clears the previous batch and result files.
`--recheck` also rechecks rows that already passed.

**The checking agents.** Dispatch one agent per batch, with no web access. It
judges only whether the abstract supports the summary. Its verdict is
`supported`, `unsupported` with the unsupported clause quoted exactly, or
`wrong-abstract` when the abstract on file is not this paper's. It writes
`summary_audit/result_NN.json`, echoing each entry's `summary_sha`.

**Ingest the results.** `--ingest` records each verdict on its row as
`summary_check`. It binds every result to the manifest, which records exactly what
the agent saw. It refuses a result, and you rerun `--prepare`, when:

- the summary was edited after `--prepare`;
- the row's ids, or its abstract text, changed since `--prepare`;
- the result's `summary_sha` is missing or differs from its batch entry's;
- the manifest predates this binding, in which case every row in it is refused.

| Outcome | Kind | Fix |
|---|---|---|
| `no-abstract` | warning | acknowledge it ([Acknowledge warnings](#acknowledge-warnings)) |
| `summary-flagged` | defect | fix the summary and run `--prepare` again |
| `abstract-wrong` | defect | add the real abstract as a landing-page entry (or an empty `text` if it has none), rewrite the summary, and run `--prepare` again |

**Numbers taken from abstracts (optional).** When a review reports statistics
taken from the papers, `extract_check.py` batches only rows whose summary check is
current, and refuses any number not quoted word for word from the abstract. See
its `--help`.

## Find missed papers (Phase 6)

The search misses papers. This step looks for them in two directions, and every
paper it suggests gets a recorded decision.

```bash
python3 ../tools/xref.py --rows rows.json --out xref_<topic>.json \
        --resolve-unknown --internal-out internal_citations.json
python3 ../tools/forward.py --rows rows.json --out forward_candidates.json
```

**Backward: `xref.py`.** It tallies the corpus's own reference lists, from
CrossRef, to find papers the corpus cites often but does not contain. It usually
finds 25–35 candidates per topic.

- **Semantic Scholar fills the gaps.** For an arXiv paper, and any paper whose
  CrossRef record has no reference list, xref asks Semantic Scholar (set
  `S2_API_KEY`). It asks in chunks of 10 papers, and retries a failed chunk once in
  half-size chunks. It rewrites a cited arXiv id as `10.48550/arxiv.<id>` so it
  matches a corpus DOI.
- **An incomplete run fails.** When a paper's references could not be fetched,
  xref exits 1, unless you pass `--allow-incomplete`.
- **A rerun fetches only what is missing.** Every completed reference list is
  cached in `<out>.refs.json` (`--cache`), keyed by paper and DOI. A rerun
  fetches only the papers missing from the cache or whose DOI changed. An
  incomplete fetch is never cached. `--no-cache` refetches everything. CrossRef
  records that `verify.py` already fetched are read from `.record_cache/`.
- **Four or more citations across about 40 papers is a strong signal**; three is
  borderline. In a densely cited literature, raise `--min-cites` and record why.
- **CrossRef coverage varies by publisher.** Nature, Cell, OUP and J Neurosci
  deposit complete reference lists; some smaller journals deposit none.
- **`--internal-out`** records how often each paper is cited within the corpus.
  The timeline uses it to choose landmarks, and `forward.py` uses it to choose
  its starting papers.

**Forward: `forward.py`.** It picks the corpus's landmarks: the top `--landmarks`
(default 30) by citations within the corpus, then by citation count. So run it
after `xref.py` and after the counts are attached
([Fetch citation counts](#fetch-citation-counts-phase-5b)); it warns when either is
missing. For each landmark, it asks OpenAlex for the most-cited papers citing it,
up to `--per-landmark` (default 200), and scores each by how many corpus papers it
cites. A paper citing at least `--min-shared` corpus papers becomes a candidate.
The default grows with the corpus: one per 80 papers, never below 3, the same rule
that sets xref's `--min-cites`.

- Each pull is ordered by citation count, so very recent papers are
  under-represented, and the output says so.
- A citing paper is recognized as already in the corpus by its OpenAlex id or
  DOI, so a corpus row with no DOI can come back as a candidate.
- A failed landmark pull exits 1 unless you pass `--allow-incomplete`.

**The run record.** Each tool writes `<out>.run.json` beside its output:
`{complete, incomplete, at, tool, n_papers}`. The ledger reads it to tell a
partial run from a full one, and how many papers the run read.

### Decide the candidates

```bash
python3 ../tools/candidates.py --rows rows.json --add xref_<topic>.json --source xref
python3 ../tools/candidates.py --rows rows.json --add forward_candidates.json --source forward
python3 ../tools/candidates.py --rows rows.json --prepare manual_check/cand --scope briefs/brief_A.md
python3 ../tools/candidates.py --rows rows.json --ingest 'manual_check/cand/result_*.json'
python3 ../tools/candidates.py --rows rows.json --export-included cand_lane.json
python3 ../tools/merge_lanes.py --append cand_lane.json --into rows.json
```

**What it does.** `candidates.py` merges both directions into one ledger,
`candidates.json`, by DOI, keeping every source and score. A candidate with the
same title as a row is that row under another DOI, usually its preprint, and is
excluded at once. The audit fails while any candidate is pending.

- **Agents decide the rest.** `--prepare` splits the pending candidates into
  input files and writes the agents' brief. `--scope` names the file that defines
  the review, such as one lane's brief. Each agent decides include or exclude,
  with a reason. For an include, it also reads the landing page and records the
  first author, year, title, lane and a summary from the abstract. `--ingest`
  refuses the whole batch if any entry lacks a reason, or an include lacks those
  fields. `--decide` records one decision by hand.
- **Included papers rejoin the table.** `--export-included` writes the included
  papers not yet in the corpus as a schema-2 lane file, ready for
  `merge_lanes.py --append`. Its lane key (default `C`) must be one no row uses.
  Send the appended rows back through verification, canon, counts and summary
  checks. An included candidate that never reaches the table is a defect.
- **Excluded papers stay visible.** The spreadsheet lists them, with their
  reasons, on its "Considered and excluded" sheet.
- **Each `--add` records the run** in the ledger (`_runs`), reading `complete` and
  `n_papers` from the run record. It refuses a run record that the other tool
  wrote. On a gated table, the audit warns about a run that is missing, did not
  finish, or read fewer papers than the table now has. A hand-edited or truncated
  `candidates.json` is refused by name.
- **`candidates.py --add` warns when hundreds are pending.** In a densely cited
  literature, raise `--min-cites` and `--min-shared`, and record why.

!!! warning "Keep ids unique across merges"
    Check `len(refs) == len(set(refs))` after merging, and attach citation counts
    only after the ids are final. Otherwise counts attach to the wrong papers.

## Acknowledge warnings

Some audit findings need a human verdict, not a fix: a possible duplicate may be
two distinct papers, or a multi-word surname may be genuinely compound. On a
gated table, an unacknowledged warning fails the audit, as a defect does.

Record each verdict in `audit_acks.json`, beside `rows.json`. It maps each row to
`{warning_id: "why this is fine"}`; warnings about the whole table go under `*`:

```json
{
  "B-12": {"possible-duplicate:B-31": "two distinct papers: a 2014 toolbox and its 2026 successor"},
  "*": {"no-forward-run": "a 12-paper historical corpus; nothing cites it forward"}
}
```

To build the file, run `references.py --rows rows.json --list-acks`. It prints
every unacknowledged warning as `REF<TAB>WARNING_ID<TAB>TEXT`. It only lists: it
exits nonzero while a warning is unacknowledged, never on a defect, since
`--audit` is the gate. A stale acknowledgment, whose warning no longer applies,
is reported but does not fail; delete it.

| Warning id | Raised when |
|---|---|
| `possible-duplicate:<ref>` | two rows share a DOI or have near-identical titles, often a preprint and its published version |
| `multi-word-surname:<name>` | a surname of several words may be given names folded into the family name |
| `single-letter-surname:<name>` | a one-letter surname, almost always an initial split off ("S, D. J.") |
| `deposit-year:<a>/<b>`, `cached-year:<a>/<b>` | the DOI, or the row's cached year, gives a different year from the reference |
| `glued-footnote:<word>` | a footnote digit may be stuck to the title's last word |
| `no-abstract` | the summary has no abstract to be checked against |
| `kept-existing-apa:<hash>` | a verified row that canon could not rebuild; keyed to its `apa`, so editing the `apa` lapses the acknowledgment |
| `identity-not-reestablished` | a canonical row verified only against its own `apa` ([Upgrade an old corpus](reruns.md#upgrade-an-old-corpus)) |
| `datacite-unsplit-author:<name>`, `datacite-deposit`, `published-version` | canon's flags on a registry record ([Rebuild every reference](#rebuild-every-reference-phase-3f)) |
| `no-candidate-ledger` (under `*`) | there is no `candidates.json` |
| `no-xref-run`, `no-forward-run` (under `*`) | the ledger records no run of that direction |
| `incomplete-xref-run`, `incomplete-forward-run` (under `*`) | the last recorded run of that direction did not finish |
| `partial-xref-run`, `partial-forward-run` (under `*`) | the last run read fewer papers than the table now has with a DOI or arXiv id, not counting the candidates the passes added |
