# Literature Review Agent Playbook

**Purpose.** Build or extend a bibliography for an academic review topic, offer
its lineage timeline on every review, and optionally write it up as a review.
This is ONE tool with two front-ends, **topic mode** (start from a query) and
**lab mode** (start from a lab's corpus), that share the entire downstream
pipeline. How big a search to run is the user's call (Phase 1d).

**How to read this file.** The operating contract and Phase 0 are the rules; read
them first. The phases give each step's procedure once. "Quick start for a fresh
Claude" at the end lists the steps in order. Many rules are enforced by the tools
themselves; where so, this file names the tool and what it refuses, and the fix is
whatever its message says. Every command below that touches the network needs a
contact email: export `LITREVIEW_EMAIL` (or pass `--email` to each tool); the
commands assume it is set.

## Operating contract — the rules that don't bend

These ten rules are the invariants. Everything below elaborates them; when in
doubt, obey this list. Bold elsewhere in this file is ordinary emphasis, not an
eleventh rule.

0. **Run the preflight before any new search, and stop on exit 2** (Phase 0).
   `preflight.py --project <dir> --scale <scale>` writes `preflight.json`, and
   `merge_lanes.py` refuses to build a table without a cleared record under 14 days
   old. On exit 2, put its choices to the user, wait for their pick before launching
   any lane, and record it with `--accept`.
1. **Verify EVERY citation before it enters a deliverable** (Phase 3), preprints
   included. `verify.py --rows` stamps each row; canon refuses, and the audit
   fails, a row without an OK stamp (or a reasoned override) for its current
   DOI/arXiv id. A row with neither id needs a recorded hand check instead
   (Phase 3e). Why: from briefs without a verification duty, about 1 in 4
   agent-returned refs had a fabricated author list, a wrong year, a reversed
   conclusion, or a bad DOI.
2. **Every reference is canonical** (Phase 3f). `references.py` rebuilds each
   `apa` from the verified DOI/arXiv id; never ship an agent-typed or
   OpenAlex-typed string. The exceptions are a DOI-less item, whose hand-checked
   `apa` stands, and a verified row whose source had no usable record, whose kept
   `apa` is confirmed by hand and acknowledged (`kept-existing-apa`).
3. **One row per paper.** `merge_lanes.py` dedups on DOI, arXiv id and title+year;
   the merge and the audit report possible preprint/published pairs, and each pair
   needs a verdict. This is row-level dedup, distinct from the one-family-per-paper
   rule that `families.py` enforces (Phase 6b).
4. **Run the antecedents pass on every review, both modes** (Phase 2b).
   `lane_briefs.py` refuses a lane spec with no antecedent lane, at every scale.
   Why: the forward search misses the topic's methodological, empirical and
   theoretical roots, and without them the field looks ~10 years old.
5. **Audit the temporal order of ideas before delivering any written review**
   (Phase 7). An origin claim cites the EARLIEST deserving paper, and multiple
   citations go oldest-first, not whichever ref fits the sentence.
6. **`rows.json` is the live table from the first successful merge (Phase 2c).**
   From then on, add rows only with `merge_lanes.py --append`, and change them
   only by tool writes or recorded hand fixes (Phase 3f). Never regenerate it: a
   fresh `merge_lanes.py --raw --out` (or a project row emitter) drops every stamp,
   hand check, canonical `apa`, count and family written since. `common.write_rows` refuses to overwrite a
   canonical table; do not pass `--force` to get past it.
7. **Don't ask before fetching** from PubMed/PMC/CrossRef/DataCite/OpenAlex/
   Semantic Scholar/Unpaywall/arXiv/publishers: these are read-only academic
   GETs. Do confirm destructive or shared-state actions. Every link is a bare
   `https://doi.org/<doi>`, never a libproxy URL.
8. **PDFs are opt-in** (Phase 4): the default is no, and never ask whether to
   fetch them.
9. **The spreadsheet is the release gate** (Phase 5). `spreadsheet.py` runs the
   full audit (`references.py --audit`) and refuses to write a failing gated table;
   `--draft` writes `<out>_DRAFT.xlsx` with a red banner, which is never the
   deliverable. Run `references.py --rows rows.json --audit` before every other
   deliverable too.

**Default tier criteria.** The tier boundary is today minus ~5 years;
`lane_briefs.py` sets it to today's year minus 5 unless the spec gives `tier`.
Before it: only highly cited or foundational work. From it on: promiscuous, with no
citation-count gate, since recent papers have not had time to accrue cites.

---

## Documentation site — keep it in sync

The public site at **https://gallantlab.org/literature-review-toolkit/** is built
from `docs/` (MkDocs + Material). It is a superset of this PLAYBOOK and the README,
not a fork. **When you change the toolkit (a tool, a phase, a command or flag, a
guardrail or lesson), update the matching page under `docs/` in the same change.**
`docs/manual.md` drifts fastest, since it carries every phase command, guardrail
and flag. The tool index in `docs/tools.md`, `tools/README.md` and this file is
generated: run `python3 tools/gen_docs.py` after adding a tool or a flag. CI
(`.github/workflows/tests.yml`) runs `ruff check .`,
`tools/tests/test_formatting.py` and `gen_docs.py --check`, and fails on a stale
index. The site deploys from `.github/workflows/docs.yml` on a push to `main` that
touches `docs/` or `mkdocs.yml` (`mkdocs build --strict`). Editing, figure and
snippet details are in `docs/maintaining.md`.

---

## Phase 0 — check the toolkit and API access, then choose the mode (do this first)

**Step 0: preflight (contract rule 0).** Read the scale from the user's request
first (Phase 1d), then run

```bash
python3 tools/preflight.py --project <dir> --scale <scale>
```

`<dir>` is the folder `rows.json` will live in, and must already exist (otherwise
nothing is recorded). `--scale` sizes the OpenAlex estimate (`--lanes N` if you
know the lane count; `--papers N` overrides; without either it assumes 500).
`--offline` checks only the environment variables.

**What the record gates.** `<dir>/preflight.json` must be under 14 days old and
cleared for `merge_lanes.py --raw` to run: everything passed, or the user's choice
is recorded for each stop (`--accept cap` or `--accept wait` for a key or budget,
`--accept current-version` for a newer toolkit; a missing email cannot be
accepted). `--no-preflight "reason"` merges anyway and keeps the reason in
`merge_report.json`. After `--accept cap`, `lane_briefs.py` refuses an uncapped
scale.

**The version.** When GitHub's `main` is newer than this copy, the preflight prints
the install command (`git -C <toolkit> pull --ff-only` for a clone, else the
`/plugin` menu or a fresh download). Offer it, install only on a yes, and rerun the
preflight. A build already under way keeps its version: rerun the preflight
mid-build with `--no-update-check`.

**Keys and budget.** It checks `LITREVIEW_EMAIL`, `OPENALEX_API_KEY` and
`S2_API_KEY`, probes both services (one OpenAlex credit), reads the OpenAlex budget
left today, and estimates what the planned corpus needs. It exits 2 when a newer
version exists, when the email is unset (export it and rerun), or when a key is
missing or rejected or the budget is short. In the last case it prints three
choices, with the key URLs and the budget arithmetic. Give them to the user in its
words and wait for their pick:

1. **Get the API keys** (free; each has its own budget). Export them in the shell
   profile, open a new shell, and rerun the preflight.
2. **Cap the search** (`--accept cap`): a capped scale (`scan`, `focused` or a
   number, Phase 1d) sized to the budget it reports. The code carries the cap from
   there (Phase 1d, 2c). Without `S2_API_KEY`, also run `xref.py
   --allow-incomplete` and say so at hand-off.
3. **Be prepared to wait** (`--accept wait`). Nothing is skipped. An OpenAlex step
   that runs out of budget stops at once with `OpenAlexBudgetError` (citations,
   abstracts, forward and the hand-check DOI search all re-raise it); rerun it
   after the reset at midnight UTC. Semantic Scholar steps back off on every 429
   and can take hours on a large corpus.

**Why the budget matters.** Keyless OpenAlex gives 1,000 credits a day per IP
address, shared by everyone behind it; a key has its own 10,000. A filter (batch)
request costs 1 credit, a title search 10, a single-work lookup 0 (OpenAlex's
rate-limit headers, 2026-09-27). That day a campus network's keyless budget was
already spent at 06:30 UTC. `common.http` sends `OPENALEX_API_KEY` to
api.openalex.org only, and treats a 429 whose Retry-After exceeds 10 minutes as a
spent budget rather than a throttle.

**Then choose the mode.** Everything after the front-end (verify, canon, counts,
families, figure, spreadsheet) is the same machinery, run the same way; there are
no mode-specific shortcuts.

| Mode | Start from | User says… | Front-end | Then gather |
|------|-----------|-----------|-----------|-------------|
| **Topic** | a query/topic | "lit review on X", "extend the bibliography for Y" | Phase 1 (scope) → 2 (search) + **2b (antecedents)** → 2c (merge) | topic name + 1-paragraph definition, the scale, source doc if any, target spreadsheet path, tier criteria |
| **Lab** | a lab's publications | "review lab Z's work", "how has Z's research evolved" | Phases L1–L3 (ingest, check and theme the lab's record) → **L4c** (field lanes + **2b antecedents**) | the lab/author ids, the inclusion filter (e.g. human-only), the scale, target paths |

Both converge on the shared pipeline: **3 verify → 3e hand checks → 3f canon →
5b counts → 5c summary checks → 6 cross-citation → 6b families + timeline
(offered every time; the user may decline) → 5 spreadsheet → 7 review article
(optional) → 8 hand-off.** Lab mode's L4c is not a lighter pass: it runs the
topic-mode front-end (Phases 2–6) with a lane per theme, with the same guardrails.

---

## Output artifacts (per topic batch)

Deliverables:

1. `<topic>_bibliography.xlsx`, built by `spreadsheet.py` from `rows.json`
   (columns in Phase 5), plus its "Considered and excluded" sheet.
2. `families.json` + `families.md` and `<topic>_families.{html,svg,png,pdf}`: the
   theoretical grouping and its interactive timeline (Phase 6b; absent only if
   the user declined it).
3. **Only if Phase 7 was opted into:** `<Topic>_review.docx` (prose authored into
   `content.json`, rendered by `tools/review_paper.py`, reference list from
   `rows.json`).
4. **Only if Phase 4 was opted into:** PDFs at
   `papers/<topic_slug>/<paper_slug>.pdf`, and the helper page
   `papers/<topic_slug>/_download_helper.html` for paywalled or bot-blocked papers.

Working files, all beside `rows.json` (keep them; the gates read several):

| File | Written by | Phase |
|---|---|---|
| `preflight.json` | `preflight.py --project` | 0 |
| `lanes.json` (the lane spec), `briefs/brief_<KEY>.md`, `lane_manifest.json`, `scratch/<KEY>/` | you; `lane_briefs.py` | 2 |
| `search_raw/<KEY>.json` | each search agent (lab mode: `search_raw/0_L.json` from `lab_lane.py --build`) | 2, 2b, L2 |
| `rows.json` | `merge_lanes.py`, then every stamping tool | 2c on |
| `merge_report.json` | `merge_lanes.py` (its `excluded` list feeds the spreadsheet) | 2c |
| `verify_report.json` | `verify.py --out` | 3 |
| `handcheck_doi_candidates.json`, `handcheck_input.json`, `handcheck_brief.md`, `handcheck_result.json` | `handcheck.py --prepare`; the hand-check agent writes the result | 3e |
| `hand_fixes.json`, `audit_acks.json` | you | 3f |
| `citation_counts.json` | `citations.py` | 5b |
| `abstracts.json`, `abstracts_failed.json` | `abstracts.py` | 5c |
| `summary_audit/` (`batch_NN.json`, `brief.md`, `manifest.json`, `result_NN.json`) | `summary_audit.py --prepare`; checking agents write the results | 5c |
| `xref_<topic>.json` (+ its `.refs.json` cache), `internal_citations.json`, `forward_candidates.json`, each output with a `<out>.run.json` sidecar | `xref.py`, `forward.py` | 6 |
| `candidates.json` | `candidates.py` | 6 |

---

## Running steps at the same time — two rules

A build runs for hours, so overlap the waits. Two rules decide what may overlap:

1. **One writer of `rows.json` at a time.** The tools that write it (`verify.py`,
   `handcheck.py --adopt-dois` / `--reject` / `--ingest`, `references.py`,
   `sentence_case.py --apply`, `citations.py --attach` / `--attach-only`,
   `summary_audit.py --ingest`, `merge_lanes.py --append`, `families.py --assign`)
   refuse to save over a file that changed since they loaded it ("rows.json changed
   since it was loaded; re-run"): the second writer fails rather than silently
   dropping the first one's stamps, so rerun it. Tools that only read it
   (`citations.py` without `--attach`, `abstracts.py`, `xref.py`, `forward.py`,
   `handcheck.py --prepare`, `summary_audit.py --prepare`, `spreadsheet.py`) may
   run alongside a writer.
2. **Semantic Scholar is paced in code.** `citations.py`, `abstracts.py` and
   `xref.py` share one `S2_API_KEY`, and every S2 request waits its turn through a
   lock file shared by all processes (`common.s2_wait_turn`), so they may run side
   by side.

**What that allows.** Once verify's DOI corrections are in (Phase 3), start
`citations.py`, `abstracts.py` and `xref.py` in the background while canon runs;
none of them needs canonical `apa` strings. Pitch the families at the same point
(Phase 6b), since the user's reply is the one human wait in the run. `forward.py`
reads `internal_citations.json` from xref and the attached counts, so it follows
both.

**Measured timings** (2026-09-27, 1,158 rows, both keys set): the nine search lanes
took ~1.5 h of agent web search; verify ~8 min; canon ~11 min; citation counts
~3 min; xref 35+ min (Semantic Scholar rate limits). xref is the long pole, which
is why it starts as early as it can. Phase 4 downloads, if requested, add 10–20 min.

---

## Topic mode — the 8-phase workflow

(The query-driven front-end. Lab mode reuses Phases 2–7; see "Lab mode" below.)

### Phase 1 — Scope the topic

**1a. Read the source document, if the user gave one.** For a `.docx`:

```bash
python3 -c "import re,sys,zipfile; x=zipfile.ZipFile(sys.argv[1]).read('word/document.xml').decode(); print(re.sub(r'<[^>]+>','',re.sub(r'</w:p>','\n',x)))" X.docx
```

For a `.pdf`, `pdftotext` (poppler). Only the references the **main text** cites
are the baseline; a bibliography can hold hundreds of refs the document never
discusses.

**1b. Define the topic precisely.** Write 3-5 sentences on what counts as
relevant: the contested theoretical positions, the methods / sub-areas /
populations involved, and the boundary with adjacent topics. It becomes the lane
spec's `description` and each lane's `definition` (Phase 2), which the search
agents use verbatim.

**1c. List the "already-known" papers** from the existing spreadsheet (filter by
`Topic`) into the spec's `already_have`, so the search agents do not re-find them.
Without one, an agent re-found 3 of 44 papers already in the spreadsheet.

**1d. Set the scale from the user's description.** How big a search the user asked
for is the one sizing decision, and it is theirs. Read it from how they describe the
review, before the preflight; if they said nothing about size, use `standard`; if
the words are ambiguous, ask once.

| Scale | The user says | Per lane | Capped | Lanes |
|---|---|---|---|---|
| `scan` | "a quick look", "the key papers", "get me oriented" | 15 | yes | 2-4 |
| `focused` | "the core literature", "a manageable list" | 30 | yes | 3-8 |
| `standard` | nothing about size (the default) | 40, a floor | no | 4-12 |
| `exhaustive` | "everything", "comprehensive", "leave nothing out" | 60, a floor | no | 6-20 |
| a number | "about 300 papers" | the total spread over the lanes | yes | 1-50 |

Pass it to the preflight (`--scale`) and put it in the lane spec (`"scale"`). The
code carries the rest (`common.SEARCH_SCALES`): `lane_briefs.py` sets each lane's
target (a lane may set its own) and the cap, and refuses a lane count outside the
scale's range or numeric targets that add up past the number; `merge_lanes.py`
fails a capped lane that returned more than its cap. Every gate runs at every
scale: a `scan` is smaller, never less checked. Say the scale at hand-off.

### Phase 2 — Brief and launch the search lanes

Write the lane spec as `lanes.json` in the project folder: its outputs go beside
it, and the merge reads `lane_manifest.json` and `preflight.json` from beside
`rows.json`. The schema is in `lane_briefs.py --help`: `title`, `for`,
`description` (Phase 1b, with what is out of scope for every lane), `scale`,
optional `already_have` (Phase 1c), `tier`, `today`, and in lab mode `lab`; per
lane `key` (1-4 capitals/digits, the ref prefix), `name`, `short`, `kind`
(`forward` or `antecedent`), `definition`, `exclusions`, `queries`, and optional
`seeds` (TITLES only) and `target`. Leave out `capped`: it follows from the scale.

```bash
python3 tools/lane_briefs.py --spec lanes.json
```

Never fill `tools/search_prompt_template.md` by hand. `lane_briefs.py` renders
`briefs/brief_<KEY>.md` per lane and writes `lane_manifest.json`, `search_raw/` and
`scratch/<KEY>/`. It refuses a missing field, a bad or repeated key, a seed that
names an author, a scale violation (Phase 1d), no antecedent lane, an uncapped
scale after `--accept cap`, and any placeholder left. Every brief carries the
verification duty, the abstract-only summary rule, the floor-or-cap rule, the
lane-seam rules, the lab deferral rule and the output contract. The tool prints
the plan and a preflight command sized to it; if that is far above the preflight's
estimate, rerun the preflight with it (plus `--no-update-check` and any `--accept`
already given). Launch one `general-purpose` agent per lane, forward and
antecedent lanes in one message, with the prompt it prints.

**What a lane returns.** One schema-2 JSON object (`"schema": 2`, `lane`,
`status`, `papers`, `deferred`, `excluded`, `could_not_confirm`) at
`search_raw/<KEY>.json`. Each paper's `first_author`, `year` and `title` become the
row's claim (`search_author` / `search_year` / `search_title`), which Phase 3
verifies the DOI against.

**No paper may fall between lanes.** The brief tells each agent to include an
on-topic paper another lane might own (naming that lane in `lane_fit`), to use
`deferred` only for a hand-off to a named lane (with `first_author` and `year`),
to use `excluded` only for a paper out of scope or below the tier bar (with a
reason), and that the target is a floor unless the search is capped. The merge
enforces it (Phase 2c). Why: three builds lost 14, 6 and 4 papers at their seams,
and each loss cost a recovery lane; on the first reference-gated build (2026-09-26)
eleven lanes deferred 138 papers no lane kept, most "trimmed to target".

**Do not act on the lanes' output yet.** It will contain errors. Go to Phase 2c,
then Phase 3.

### Phase 2b — Antecedents (the foundations pass) — REQUIRED

The Phase-2 search is biased toward recent work and the topic's current framing,
so it misses the literature the topic was built on (contract rule 4). Put the
antecedent lanes in the same spec as the Phase-2 lanes (`"kind": "antecedent"`), so
they run in the same fan-out: the merge dedups on DOI and arXiv id, so overlap costs
nothing, while waiting costs a full search round. One lane per axis:

1. **Measurement / methodology origins**: the instrument, signal or technique the
   work depends on, and the papers that established and validated it (for
   human-fMRI work: the BOLD mechanism, the first functional studies, what the
   signal measures).
2. **Foundational empirical results**: the classic findings the topic builds on,
   including older work in adjacent methods, species or eras (single-unit
   physiology, psychophysics, the first description of an effect or region).
3. **Theory / computational framework**: the conceptual claims that motivate the
   work (efficient coding, a normative principle, a levels-of-analysis framing).

An antecedent brief flips the tier emphasis to classic work that PRE-DATES the
modern literature and tags its papers `"source": "anteced"` (the spreadsheet's
lilac band). An old classic with no DOI comes back as `anteced-nosrc` with a full
APA string from the title page or a library record; it gets a hand check (Phase 3e)
instead of a verify stamp, and `citations.py` leaves its counts blank. The brief
also says to cite an old book's original edition, never a reissue DOI, which
re-dates the work to the reprint year.

**Lab mode:** the antecedents include the lab's OWN pre-paradigm work that the
inclusion filter drops; it stays in lane L (Phase L2), not excluded.

**Effect on the figure:** antecedents stretch the time axis back decades; render
with `--min-year` and `--time-warp` (Phase 6b).

### Phase 2c — Merge the lanes (`tools/merge_lanes.py`) — a gate

Once every lane has written its file into `search_raw/`:

```bash
python3 tools/merge_lanes.py --raw search_raw --out rows.json
```

It refuses to run without a cleared `preflight.json` beside `--out` (Phase 0).

**How it dedups.** By DOI, then arXiv id, then normalized title + year, recording
the other lanes that returned a paper (`also_lanes`). An arXiv-only paper gets its
arXiv DOI (`10.48550/arXiv.<id>`), so the DOI-keyed checks see it. A title+year
match alone merges only when the claimed author and year agree (the verify
comparison) and the rows do not carry two different journal DOIs; otherwise both
rows are kept and reported as a **possible pair**. It also lists every pair of kept
rows whose titles score ≥ 0.9 (a title under 4 content words must match on
characters: word containment alone paired "The human visual cortex" with 60 longer
titles). DOI/arXiv hits whose claims disagree are printed ("the claims differ")
for you to look at.

**When the merge fails.** It exits 1 and writes `merge_report.json` but **not**
`rows.json`, so nothing downstream runs on a table with a hole in it:

| Failure | What it means | Fix |
|---|---|---|
| `LOST` | a `deferred` entry matched no merged row, by DOI or by title (`common.title_match`: similarity ≥ 0.9, or each title's words ≥ 90% in the other; a short title inside a longer one is not a match) confirmed by its `first_author`/`year` | if its `to_lane` names another lane: send it to one recovery lane, add that file to `search_raw/`, re-merge. If it names no other lane: put it back in the lane's `papers`, or move it to `excluded` with its reason |
| `UNCONFIRMED` | matched by title only, with neither `first_author` nor `year`, or an unreadable `first_author` ("?") | add the fields to the deferral and re-merge, or send it to a recovery lane |
| rejected | a paper with no DOI, arXiv id or APA string, which can be neither verified nor hand-checked | give it a DOI or arXiv id, or have the lane write its full APA string, then re-merge |
| `OVER CAP` | a lane of a capped search (`lane_manifest.json`) returned more papers than its cap | resume the lane to keep its most important papers and move the rest to `excluded` with reason `over the capped-search limit`, then re-merge |

An `excluded` entry never has to match a row; the merge records it for the
spreadsheet. Every title-only deferral match is printed (`matched_by_title`) for
you to check. A lane that returned under 60% of its target, or reported
`websearch_exhausted`, is printed as thin: resume it through SendMessage (its
transcript intact) rather than re-spawning it, which discards everything it
verified, and `--append` what it adds.

**Later additions** (a recovery lane after the first successful merge, the Phase-6
candidates) use `--append`, which never touches an existing row (contract rule 6):

```bash
python3 tools/merge_lanes.py --append recovery.json --into rows.json
```

It skips (and reports) a paper already in the table or one with no DOI, arXiv id
or APA string, flags a title+year clash that fails the check above as a possible
duplicate, refuses a ref already used ("renumber the lane"), and prints the
`verify.py --only` list for the new rows. It checks no deferrals or caps, and
refuses an empty `--into`: use `--raw`/`--out` for the first merge. A schema-1 lane
file (a bare array) is refused unless `--allow-v1`, which leaves its deferrals
unchecked.

### Phase 3 — Verify EVERY citation (CRITICAL)

Why: in an early run the search agent fabricated 5 author lists, reversed one
paper's conclusion, and invented a bioRxiv DOI; about 1 in 4 citations had errors.
Lane briefs with a verification duty bring that close to zero (Lessons), but this
phase is still the gate that proves it.

#### 3a. Run verify on the live table

```bash
python3 tools/verify.py --rows rows.json --out verify_report.json
```

Start it as soon as the merge passes, with `handcheck.py --prepare` (Phase 3e)
alongside. `--rows` derives each row's expectations from its claim (`search_*`),
and after canon from its `apa` too, so never write a converter for verify's input
(fourteen projects once did, each with its own first-author regex). It exits **0
only when every verdict is OK**, so a chained run stops on a table that needs
attention.

#### 3b. Act on each verdict

| Verdict | Meaning | What to do |
|---|---|---|
| **OK** | the record matches the claim | nothing |
| **MISMATCH** | first author, year or title disagrees, or the DOI does not resolve in CrossRef or DataCite | read the `issues`; open the landing page. Wrong DOI: fix `doi` and `link`, then `--only REF`. Fabricated: drop the row. A false alarm (a preprint retitled on publication; a "confirm by hand" first author you confirmed): `--override` (3d) |
| **NOT-FOUND** | every lookup completed and none matched | chase it: likely fabricated. Find the real paper and its DOI, or drop the row. Never wave it through as "an arXiv paper" |
| **ERROR** | a lookup could not complete (rate limit, network) | rerun it; it is NOT the same as NOT-FOUND |
| **UNCHECKED** | the row carries no claim, so a resolving DOI proves nothing | give it `search_*` fields from the landing page, then `--only REF` |

To rerun the rows that were not OK, or name rows explicitly (never build a rerun
input file by hand):

```bash
python3 tools/verify.py --rows rows.json --retry-from verify_report.json --out verify_report.json
python3 tools/verify.py --rows rows.json --only A-01,B-02 --out verify_report_fix.json
```

`--retry-from` re-verifies only the report's non-OK rows and splices the new
verdicts into it. Every run already gives its ERROR rows a second try at the end,
after a 60 s cool-down (`--retry-wait`) with smaller arXiv batches.

**Fabrication patterns to look for** when you open a landing page: an author who
is not among the paper's authors; a conclusion that is the OPPOSITE of the finding;
a DOI that does not resolve, or resolves to an unrelated paper (agents invent
plausible DOIs and mis-copy real ones, so confirm the *target*, not just that it
resolves); an arXiv id that does not resolve.

**Do not judge a DOI by its shape; resolve it.** Prefixes and suffix formats drift.
bioRxiv now issues `10.64898/...` DOIs alongside `10.1101/...`, and Imaging
Neuroscience uses `10.1162/imag.a.NNNN` (dots; the underscore shape you might guess
404s).

As soon as the rows are verified, pitch the families to the user (Phase 6b, step
2) and start `citations.py`, `abstracts.py` and `xref.py` ("Running steps at the
same time").

#### 3c. What the checks compare

The rules live in `verify.py` (its docstrings hold the full name grammar); an issue
line says which one fired.

- **Which record.** arXiv ids go to the arXiv API, 50 per request 3 s apart (a
  per-paper loop gets the IP banned, and real preprints then read as NOT-FOUND). A
  row with both an arXiv id and a journal DOI has both checked, because canon cites
  the journal DOI. **A journal DOI is verified only by its own record**: CrossRef, or
  DataCite on a clean CrossRef 404 (Zenodo, figshare, OSF, Dryad). A PMID, PMCID or
  title search never stands in for it: a real title with a fabricated DOI once
  verified OK that way. Any other CrossRef error, or a non-matching title-search hit
  after a lookup errored, is ERROR, not MISMATCH (on a 588-row run ~30 throttled
  calls each surfaced an unrelated PubMed paper).
- **First author: surname against surname; initials never decide a match.** "J.
  Smith" cannot match "Jones J"; every word of a compound surname must be in the
  record ("Lambon Ralph" does not match "Ralph J"); an unknown name on either side
  fails. The record's first author is trusted only when the registry deposited it
  as family + given name, and an ambiguous claim ("Hao CHEN") is reported; both
  read "confirm by hand". `merge_lanes.py` uses the same comparison.
- **Year** within ±1 (a preprint and its version of record differ). **Title**
  agreement ≥ 0.5, two-way: a short claim merely contained in a longer record fails,
  a dropped subtitle passes when the main title has at least 3 content words. On
  2,473 past OK verdicts this flags 2 (a preprint retitled on publication, a dropped
  subtitle under a 2-word main title), cleared with `--override`.

#### 3d. Stamps, overrides and re-verification

**`--rows` stamps each row**, not just the report: a `verified` field with the
verdict, the DOI/arXiv id checked, source, issues and date. Canon and the audit
read it, and it lapses the moment the row's DOI or arXiv id changes. `--no-stamp`
reports without writing.

**Clearing a false alarm** is recorded on the row:

```bash
python3 tools/verify.py --rows rows.json --override REF --reason "retitled on publication; checked the landing page"
```

It is refused without an existing stamp, without a reason, or if the row's
DOI/arXiv id changed since it was verified.

**Re-verifying a canonical row keeps an earlier independent stamp.** After canon,
a row's `apa` is built from the same DOI verify checks, so a re-run with no search
claim yields only a circular `claim_basis: "canonical-apa"` OK. When the row already
carries an independent OK for the SAME ids, that stamp is kept and `reverified_at`
records the re-run. A canonical row verified only against its own `apa` gets the
audit warning `identity-not-reestablished` (confirm the DOI by hand, then
acknowledge it).

#### 3e. Hand-check rows with no DOI or arXiv id (`tools/handcheck.py`)

A book, report, thesis or web essay cannot be machine-verified, so a gated table
needs a recorded hand check instead; the audit fails a DOI-less row without one
(`hand-check-missing`).

```bash
python3 tools/handcheck.py --rows rows.json --prepare
python3 tools/handcheck.py --rows rows.json --adopt-dois handcheck_doi_candidates.json
# dispatch one hand-check agent: handcheck_input.json + handcheck_brief.md -> handcheck_result.json
python3 tools/handcheck.py --rows rows.json --ingest handcheck_result.json
```

1. **`--prepare`** (reads only; run it alongside verify) searches CrossRef and
   OpenAlex for a DOI the row turns out to have (same title by `common.title_match`,
   same year). Rows with a candidate go to `handcheck_doi_candidates.json`; the rest
   go to `handcheck_input.json` plus `handcheck_brief.md`. A previous
   `handcheck_result.json` is renamed `.stale-<timestamp>`.
2. **`--adopt-dois`** (a writer; after verify finishes) gives each row with exactly
   one candidate that DOI, for `verify.py --only`. A row with several is named: keep
   the right one in the file and rerun. If none is right, `--reject REF --reason
   "..."` records them as `doi_rejected`, and the next `--prepare` sends the row to
   the hand check.
3. **The hand-check agent** checks every author, the year, title, edition,
   publisher and pages or report number against a real source (a library catalog,
   the publisher's page, the post itself; never another paper's citation of it),
   and echoes each entry's `apa_sha`.
4. **`--ingest`** (a writer; after verify finishes) records `hand_verified`
   (`confirmed`, `corrected` with the new APA, or `not-found`). It refuses a result
   whose reference changed since `--prepare` or that does not echo its `apa_sha`,
   and exits 1 on a `not-found` row: remove it or re-check it.

Editing a hand-checked `apa` afterward lapses the check (`hand-check-missing`).

### Phase 3f — Canonicalize EVERY reference (`tools/references.py`)

Verification (Phase 3) confirms a citation is *real*; canon makes its `apa` string
*correct* (contract rule 2). `references.py` is the single formatter and a hard
gate, used identically in both modes:

```bash
python3 tools/references.py --rows rows.json --out rows.json   # rebuild, then print the audit
python3 tools/references.py --rows rows.json --audit           # gate: report only, exit 1 on any failure
python3 tools/references.py --rows rows.json --only A-01,B-02  # targeted re-canon; every other row untouched
```

**Canon rebuilds only verified rows, on every table.** A row whose verify stamp (or
reasoned override) is not OK for its current DOI/arXiv id keeps its `apa`, is
named, and makes the run exit 1: re-verify it (`verify.py --rows rows.json --only
REF`), then re-canon. A legacy table goes through "Upgrading an old corpus".

**Sources.** CrossRef for a journal DOI (preferred over arXiv when a row has both:
it is the version of record); DataCite on a CrossRef 404; the arXiv API for an
arXiv id or `10.48550/arXiv.*` DOI, 50 ids per request, 3 s apart (until
2026-09-25 it sent one request per row, and a 475-ref build spent most of 53
minutes asleep in 429 backoff). The output is full APA-7: every author (past 20:
19, an ellipsis and the last), name particles and casing repairs, joined subtitles, book chapters, preprint
venues and DataCite `(Version v) [Data set]` deposits.

**How a canon run ends.** It prints the full audit and exits 1 when the audit
fails, or when any row was not rebuilt:

| Printed | Meaning | Fix |
|---|---|---|
| `not verified for its current DOI/arXiv id` | the gate above | `verify.py --only`, or `--override` a false alarm, then re-canon |
| `fetch failed twice` | the row got a second try after `--retry-wait` (60 s) and still failed; its `apa` is not canonical | `--only REF` later |
| `DOI does not exist` | 404 from CrossRef and DataCite | fix or drop the DOI, re-verify |
| `the source returned no usable record` (a warning) | an author-less editorial, an id missing from the feed; the old `apa` is kept | confirm it by hand; acknowledge `kept-existing-apa:<hash>` if the audit raises it |

**The audit's defects** each fail `--audit` and the spreadsheet, and each prints
its fix. Formatting: `no-year`, `no-authors`, `et-al`, `html-entity`, `markup-tag`,
`double-terminal-punctuation`, `missing-space`, `mangled-punct`, `unicode-hyphen`,
`malformed-initial`, `replacement-char`, a truncated or empty venue, an
`uppercase-title run`, and `hand-fix-lost` (below). On a gated table the reference
gates add `unverified`, `link-doi-mismatch`, `hand-check-missing` (Phase 3e),
`summary-unchecked` / `summary-flagged` / `abstract-wrong` / `no-summary`
(Phase 5c), and the candidate-ledger defects (Phase 6). A DOI-less item is not a
defect; it is listed as a manual ref and needs its hand check.

**Acknowledge warnings.** Some findings need a human verdict, not a fix. On a gated
table an unacknowledged warning fails the audit like a defect; on a legacy table it
is only printed. Record each verdict in `audit_acks.json` beside `rows.json`:
`{ref: {warning_id: "why this is fine"}}` (`*` for corpus-wide ones).
`references.py --list-acks` prints every unacknowledged warning as
`REF<TAB>WARNING_ID<TAB>TEXT` to build the file from; it exits 1 while any is
unacknowledged, never on a defect, so `--audit` stays the gate. A stale
acknowledgment (its warning no longer fires) is reported, not failed: delete it.

| Warning id | What it flags | Verdict needed |
|---|---|---|
| `possible-duplicate:<ref>` | near-identical titles (often a preprint and its journal version) | two distinct papers, or keep the version of record and drop the other |
| `multi-word-surname:<name>` | `Lambon Ralph` (real) and `Thomas Yeo` (CrossRef folding given names into the family) look alike | fix the split (`hand_fixes.json`), or acknowledge a real compound surname |
| `single-letter-surname:<name>` | `S, D. J.`: almost always an initial split off as the surname | fix it (`hand_fixes.json`), or acknowledge a real one (`O`) |
| `deposit-year:<doi-year>/<apa-year>` | the DOI encodes another year (publisher back-file digitization re-dates old papers) | which year is right |
| `cached-year:<cached>/<apa>` | a cached `year` field disagrees with the `apa` | fix whichever is wrong, or delete the stale cache |
| `glued-footnote:<word>` | a footnote digit stuck to the last title word (`psychological science1`) | check the source |
| `datacite-unsplit-author:<name>` | a DataCite creator with no given name that could not be split safely (`The pandas development team`, `Hao CHEN`) | a group (acknowledge), or a person (fix the `apa`) |
| `datacite-deposit` | a DataCite record that is not software or a data set (or whose publisher is "Unpublished"): a repository copy of a paper | cite the version of record's DOI if one exists |
| `kept-existing-apa:<hash>` | verified, but canon could not rebuild it; keyed to the `apa`, so an edit lapses it | confirm the `apa` by hand |
| `identity-not-reestablished` | a canonical row verified only against its own `apa` (Phase 3d) | confirm the DOI is the intended paper |
| `no-abstract` | a summary with no abstract to check it against (Phase 5c) | acknowledge, or add a landing-page abstract |
| `*`: `no-candidate-ledger`, `no-xref-run` / `no-forward-run`, `incomplete-xref-run` / `incomplete-forward-run`, `partial-xref-run` / `partial-forward-run` | Phase 6 was not run, did not finish, or read fewer papers than the table now has | run the pass (Phase 6), or acknowledge why this review goes without it |

**Record every hand fix in `hand_fixes.json`**, never by editing `apa` alone:
`{"<ref>": [{"old": "<damaged text canon produces>", "new": "<final text, in sentence
case>", "why": "<source>"}]}` (`old` is `""` for an empty apa). Canon re-fetches on
every run, so `references.py` and `sentence_case.py --apply` re-apply every fix
after they write; the audit fails a row whose fix is gone (`hand-fix-lost`), and
canon exits 1 on a fix that matches neither its `old` nor its `new` text. A fix can
therefore be made at any point in the build. Typical fixes: U+FFFD mojibake
(`Bürgel`), compound-surname splits, two authors packed into one, a missing
subtitle or year (Lessons, "Reference records"). `references.py --repair` fixes
markup, Unicode-hyphen and `?.` damage offline without re-fetching.

**Sentence-case titles after canon (`tools/sentence_case.py`).** Strict APA-7 wants
sentence case, and canon does not impose it, because correct casing needs
proper-noun judgment (Lessons, "Casing and foreign-language titles"). The tool
proposes, you review, then `--apply`. Keep the corpus's proper nouns in a
per-project `--proper` file (`{"words": [...], "phrases": [...]}`) so a generic word
lowercases while a named entity does not (`yoga practitioners` but `Sahaja Yoga`).
On a large corpus review with `--vocab` (the distinct token changes): a mis-cased
proper noun is obvious there and invisible in a long diff. Non-English titles are
skipped by default (`--include-foreign` overrides).

```bash
python3 tools/sentence_case.py --rows rows.json --proper proper.json --vocab
python3 tools/sentence_case.py --rows rows.json --proper proper.json --apply
```

### Phase 4 (OPTIONAL) — Download PDFs

**Skip this phase by default.** Run it only if the user explicitly asks for PDFs;
it is legacy machinery that still works on demand.

```bash
python3 tools/download.py --papers pdf_list.json --out-dir papers/<topic_slug>/ \
        --email you@inst.edu --manual-list papers/<topic_slug>/_needs_manual.txt
```

`pdf_list.json` is a list of `{slug, doi, arxiv, pmcid}`. The tool tries arXiv
direct, then every Unpaywall OA location (`best_oa_location` first, non-PMC URLs
before PMC), then Europe PMC (`?pdf=render`); it skips hosts that block bots
(`BLOCKED_HOSTS`: PMC PDF URLs, bioRxiv/medRxiv, PNAS, OUP, MIT Press,
ScienceDirect, Wiley, Cell), and keeps a download only if its first 4 bytes are
`%PDF` (a 200 can be an HTML challenge page). Failures are appended to
`--manual-list`.

**Route the failures to a browser-helper page**, not to retries: those hosts work
in a real browser. Write `papers/<topic_slug>/_download_helper.html`, one row per
failed paper (author, year, slug, title) with an Open link: plain
`https://doi.org/<doi>` for paywalled papers (the user has institutional access;
never a libproxy URL), `https://pmc.ncbi.nlm.nih.gov/articles/<PMCID>/` for
OA-on-PMC, `https://www.biorxiv.org/content/<doi>v1` for bioRxiv. The user opens
it, downloads each PDF with the publisher's button into `~/Downloads`, and then:

```bash
python3 tools/reconcile_downloads.py --manifest papers/<topic_slug>/_manifest.json \
        --out-dir papers/<topic_slug>/
```

It matches each PDF (filename ↔ DOI substring, else first-author + year + title
words on the first page), files it under its slug, and leaves any PDF it is unsure
of. The manifest is a list of `{slug, title, first_author, year, doi}`; `--dry-run`
previews.

### Phase 5 — Build the spreadsheet (the release gate)

```bash
python3 tools/spreadsheet.py --rows rows.json --out <topic>_bibliography.xlsx
```

Build it last, once Phases 3–6b are done: it is the release gate (contract rule 9).
A legacy (ungated) table is written despite its findings. It rebuilds the whole
file from `rows.json` each time (xlsxwriter is write-only).

Columns: `Topic | Ref # | APA reference | Link | Summary | Tag` then, when any row
carries them, `Family` (Phase 6b), `Cite (OpenAlex) | Cite (S2)` (Phase 5b),
`Verify note` (hand-check notes), `Summary checked against` (Phase 5c: the abstract
source, or "no abstract"), then `PDF (local) | Xref`. The "Considered and
excluded" sheet lists the ledger's `exclude` decisions (Phase 6) and the lanes'
`excluded` papers from `merge_report.json`, minus any another lane kept.

What each row field should hold:

- `topic`: one of the project's topic categories (e.g. "Multimodal networks").
- `ref`: the lane ref (`<LANE_KEY>-NN`). Refs must stay unique across batches:
  give each later batch a new lane key, since `--append` refuses a used ref.
- `apa`: the canonical `apa` from Phase 3f.
- `link`: `https://doi.org/<doi>`, never a PubMed/PMC URL. A paper with only a
  PMID/PMCID gets its DOI looked up first.
- `summary`: two to four sentences written only from the abstract (what the paper
  did and found; no priority or impact claim the abstract does not make), the same
  rule the lane briefs carry. The summary check (Phase 5c) flags anything else. Rows
  exported from the candidate ledger and lane-L rows arrive with none, and on a
  gated table the audit fails an empty summary (`no-summary`).
- `tag`: the template's tag vocabulary (`classic`, `recent-review`, …).
- `pdf`: a relative path if downloaded, else empty. `xref`: shown in the `Xref`
  column, but no tool fills it.

**Row colors** come from `source` (rules in `spreadsheet.py`'s `COLORS`; an
unknown value renders white with a warning): white `source-doc` (refs from the
source document); cream `#FFF7E0` `search`; green `#E2F0D9` `xref`, `forward`,
`survey` (Phase 6); blue `#DDEBF7` `lab`; lilac `#F3E6F5` `anteced` and
`anteced-nosrc` (Phase 2b).

### Phase 5b — Citation counts (standard; do this on every review)

Google Scholar cannot be queried (Lessons, "Citation counts"), so
`tools/citations.py` queries two databases by DOI:

- **OpenAlex**, the primary source: near-complete by DOI, 50 DOIs per filter
  request (1 credit each against the daily budget, Phase 0), with a single-work
  lookup (0 credits) for any DOI the batch missed or whose count is under half a
  Semantic Scholar count of 50 or more.
- **Semantic Scholar**, secondary: often higher for CS/AI venues, and gives
  `influentialCitationCount`. 500 ids per request; an arXiv DOI is looked up by its
  arXiv id. An id S2 rejects is isolated and named (treated as not in S2) and a
  chunk that fails is named; either way the OpenAlex counts stand. Without
  `S2_API_KEY` expect gaps.

```bash
python3 tools/citations.py --rows rows.json --out citation_counts.json                 # fetch; reads rows.json only
python3 tools/citations.py --rows rows.json --out citation_counts.json --attach-only   # write the counts onto the rows
```

The fetch may run during canon. `--attach-only` writes `rows.json`
(`cite_openalex` / `cite_s2` / `cite_s2_influential` / `cite_asof`, which
`spreadsheet.py`, the figure and `forward.py` read), so run it when no other writer
is running; `--attach` fetches and attaches in one run. A re-run keeps an earlier
count wherever this run's lookup came back empty (a throttled S2 batch is not "no
citations"), so re-running to fill S2 gaps never loses coverage. Counts are a
snapshot (`--asof`, default today); rows with no DOI stay blank. They are keyed by
ref, so attach only after the refs are final.

### Phase 5c — Abstracts and the summary check

A summary can drift from what a paper found, the same way a citation can be
fabricated, so it is checked the same way: against an authoritative record, by an
agent that sees nothing but that record.

```bash
python3 tools/abstracts.py --rows rows.json
python3 tools/summary_audit.py --rows rows.json --prepare
# dispatch one checking agent (no web access) per summary_audit/batch_NN.json; brief: summary_audit/brief.md
python3 tools/summary_audit.py --rows rows.json --ingest
```

**`abstracts.py`** fetches each row's abstract once, from the most authoritative
source that has it (the arXiv API for arXiv papers, then OpenAlex, then Semantic
Scholar, PubMed by PMID, then PubMed and Europe PMC by DOI), into `abstracts.json`. Each entry
records the `doi` and `arxiv` it was fetched for, so when a row's ids change its
entry is fetched again. A fetch that could not complete goes to
`abstracts_failed.json` and makes the run exit 1: that is not "no abstract", so
re-run it. A source text that is boilerplate, a citation line or an author list
is refused (`abstracts.not_an_abstract`) and the next source is tried. For a paper
no source has, add a hand entry from the landing page: `{"text": "...", "source":
"landing-page", "url": "...", "doi": "<row's doi>", "arxiv": "<row's arxiv>"}` (an
empty `text` records that none exists). A landing-page entry is never overwritten;
if its ids stop matching the row it is reported as stale.

**`summary_audit.py --prepare`** writes the rows needing a check into batches of 40
(`--batch`), each entry with its summary, abstract and `summary_sha`, plus the brief
and a `manifest.json`. It refuses (exit 1) any row whose abstract fetch failed or
whose abstract entry records other ids. It **deletes old `batch_*.json` and
`result_*.json`**, so ingest every finished result before re-preparing. Each
checking agent judges only whether the abstract supports the summary, echoing each
entry's `summary_sha`: "supported", "unsupported" (the unsupported clause quoted
exactly), or "wrong-abstract" (the abstract on file is not this paper's).

**`--ingest`** binds every result to the manifest, not to whatever `rows.json` or
`abstracts.json` now say. It refuses a result if the summary was edited, the row's
ids changed, or the abstract text changed since `--prepare`, or if the result does
not echo the batch's `summary_sha`; each refusal names its fix (re-run
`--prepare`, or re-check the entry). A manifest from before this binding existed
refuses every ref in it. A row with no abstract is recorded as `no-abstract`, a
warning to acknowledge (Phase 3f). An "unsupported" summary is a defect
(`summary-flagged`): fix it, then `--prepare` and `--ingest` again. A
"wrong-abstract" verdict is a defect too (`abstract-wrong`): add the real abstract
as a landing-page entry, rewrite the summary from it, and re-check.

### Phase 6 — Cross-citation analysis (second pass)

Finds high-impact papers the search missed, two ways: what the corpus papers cite
repeatedly (backward, `xref.py`) and what cites the corpus's landmarks (forward,
`forward.py`). Every paper either pass suggests gets a recorded decision in the
candidate ledger (`candidates.py`); the audit fails while any is pending.

**Order and prerequisites.** Start `xref.py` once verify's DOI corrections are
applied (both passes read only DOIs/arXiv ids); it may run beside citations and
abstracts. `forward.py` follows xref (it reads `internal_citations.json` to pick
landmarks) and the attached counts (`cite_openalex` breaks ties; Phase 5b). See
"Running steps at the same time".

**Backward: `xref.py`.** For each paper it reads the CrossRef reference list; for an
arXiv DOI, or a paper CrossRef holds no list for, it asks Semantic Scholar (10
papers per request, one half-size retry of a failed chunk: 100-paper chunks drew a
429 or a truncated body and failed 400 papers of a 677-row build). On a 2026-09-25
probe S2 had lists for 16 of 20 sampled arXiv papers (OpenAlex had 4 of 39). An
incomplete CrossRef fetch is retried once at the end (`--retry-wait`, default
60 s). Every completed list is cached in `<out>.refs.json`, so a re-run fetches
only the lists that are missing or incomplete (`--no-cache` refetches everything).

```bash
python3 tools/xref.py --rows rows.json --out xref_<topic>.json --min-cites 4 \
        --resolve-unknown --internal-out internal_citations.json
```

- The output ranks every DOI cited by at least `--min-cites` corpus papers (default
  3). On a ~40-paper topic, 4 is a strong signal and 3 borderline (take a 3 only if
  clearly foundational); raise it for a large corpus, since every entry becomes a
  pending candidate.
- `--resolve-unknown` looks up titles for ranked DOIs CrossRef returned bare.
- `--internal-out` writes each corpus paper's within-corpus in-degree. Always emit
  it: `forward.py` and the figure's landmark criterion (2) read it from beside
  `rows.json`.
- CrossRef coverage varies by publisher (Nature, Cell, OUP, JNeurosci deposit
  reference lists; some small journals deposit none).
- A reference list that could not be fetched makes the run **incomplete**: xref
  names the papers, says the table is undercounted, and exits 1. Re-run (the cache
  makes that cheap), or pass `--allow-incomplete` to accept it (say so at hand-off).

**Forward: `forward.py`.** Picks the landmarks (top `--landmarks` 30 by
within-corpus in-degree, then `cite_openalex`), asks OpenAlex for the most-cited
papers citing each (up to `--per-landmark` 200), and keeps a citing paper that cites
at least `--min-shared` 3 corpus papers.

```bash
python3 tools/forward.py --rows rows.json --out forward_candidates.json
```

- Pulls are ordered by citation count, so very recent papers are under-represented;
  the output says so.
- A corpus row is recognized by its OpenAlex id or DOI. A row with no DOI (or whose
  id lookup failed) cannot be excluded, so it may come back as its own candidate:
  exclude it by hand.
- A failed landmark pull exits 1 (its citing papers are missing); re-run, or pass
  `--allow-incomplete`. A spent OpenAlex budget raises `OpenAlexBudgetError` at once
  (Phase 0).

Both tools write a run sidecar `<out>.run.json`, which `candidates.py --add` reads
to record whether the run finished and how many papers it read.

**Decide every candidate: `candidates.py`.** One ledger (`candidates.json` beside
`rows.json`) holds both passes:

```bash
python3 tools/candidates.py --rows rows.json --add xref_<topic>.json --source xref
python3 tools/candidates.py --rows rows.json --add forward_candidates.json --source forward
python3 tools/candidates.py --rows rows.json --list pending
python3 tools/candidates.py --rows rows.json --decide 10.1038/xxxxx \
        --decision exclude --reason "methods paper, not on topic"
python3 tools/candidates.py --rows rows.json --export-included xref_lane.json --lane X
```

- `--add` skips DOIs already in the corpus and records the run under `_runs`; a
  missing sidecar records `complete: false`, and another tool's sidecar is refused.
- `--reason` is required for every decision. Excluded candidates stay in the ledger
  and are listed on the spreadsheet's "Considered and excluded" sheet, so a missing
  paper is visibly one that was considered.
- Expect ~25–35 included additions per topic pass (almost half as many again as the
  search found). Many more makes the spreadsheet unwieldy; far fewer usually means
  under-mining.
- A hand-edited or truncated `candidates.json` is refused by name by
  `candidates.py`, the audit and the spreadsheet.

The audit fails while any candidate is pending, or while an `include`d candidate is
not in the table. On a gated table it also warns (the `*` row of the Phase 3f
table) when a pass was never added, its last run did not finish, or its last run
read fewer papers with a DOI or arXiv id than the table now has. That count leaves
out the rows the passes themselves brought in, so `partial-*` means rows added some
other way (a recovery lane after the pass ran): re-run the pass and `--add` it
again. Acknowledge any of these only when the review genuinely skipped that pass or
proceeds without full coverage.

**Bring the included papers in.** Exported rows are refs `<lane>-01…`, `source`
`xref` or `forward` (green in the spreadsheet), with the candidate's author, year
and title as the claim. Then:

1. `python3 tools/merge_lanes.py --append xref_lane.json --into rows.json` (never
   touches an existing row). A second export needs a new `--lane` key: `--append`
   refuses a ref already in the table.
2. `verify.py --rows rows.json --only <new refs>` (the append prints the list), then
   `references.py --rows rows.json --only <new refs>`.
3. Re-run `citations.py --attach` (when no other writer runs) and `abstracts.py`
   (it fetches only what is missing or stale).
4. Write each new row's `summary` (from its abstract) and `topic`: the export leaves
   both empty, and the audit fails an empty summary (`no-summary`).
5. Assign the new rows a family if Phase 6b is already under way (`families.py`
   fails on an unassigned row).

### Phase 6b — Families and the timeline (offered on EVERY review)

The lineage timeline is the deliverable users find most useful, so **always offer
it; do not wait to be asked.** It groups the papers into a few **theoretical
families**, an axis *orthogonal to the Topic column* (Topic is method/sub-area; a
family is what a paper is fundamentally *for*). It adds a `Family` column,
`families.md` (grouped tables plus a family × topic cross-tab), and the figure.

**Pitch as soon as the rows are verified (after Phase 3), not after xref.** The
proposal needs only titles and summaries, and the user's reply is the one human wait
in the run: let canon, counts and xref run while they decide. On a 475-ref build the
pitch came last, and 56 minutes passed between the pitch and the finished figure.

1. **Propose.** Read the corpus with `python3 tools/families.py --rows rows.json
   --digest` and use `tools/family_prompt_template.md`. Propose ~3–8 families (the
   tool accepts 2–9), each `{key, name, claim, lineage}`, and one organizing
   principle. Families must cut *across* the Topic lanes: a good family unites
   textually dissimilar papers and splits similar ones. **Do not cluster
   embeddings**; that yields surface-similarity groups, not theoretical ones.
   The `claim` and `lineage` are shown to readers on hover, so they need citation
   discipline: **compose each lineage from rows already in the corpus** (grep
   `rows.json` for the canonical lead surname and year) rather than from memory. On
   the cortical-layers build a remembered lineage put Senzai et al. 2019 in
   `contingency` when its contribution (laminar landmarks from spike power and
   sink-source distributions) belongs in `boundary`.
2. **Pitch.** Offer the timeline and show *just the family definitions* (name +
   one-line claim). The user picks: **use these**, **change them** (iterate until they
   approve), or **skip the timeline** (then no `Family` column and no figure; say so
   at hand-off). Iterating on six definitions is cheap; redoing an assignment is not.
3. **Assign** every paper to one family (its dominant commitment) against the frozen
   spec, in batches for a large corpus, never one rushed 250-paper pass. Write
   `families_input.json` (`{principle, families, assignments: {ref: key},
   hard_calls}`; the template's Step 2 asks the agents for `hard_calls`, the papers
   that fit the spec badly). `families.py` prints every hard call and warns when the
   file records none; read them before rendering. The agents are told not to argue
   with the spec, so a hard call is the only place a wrong family definition shows
   up. (In the Senzai case an agent flagged the conflict, deferred to the spec, and
   the error propagated until the flag was read.)
4. **Validate and stamp.**
   ```bash
   python3 tools/families.py --rows rows.json --assign families_input.json \
           --results 'families_batches/result_*.json' --out families.json
   ```
   `--results` merges the assignment agents' files (and their hard calls) into the spec;
   in lab mode `--default-from-lanes` gives every row no agent assigned its lane's theme
   (or its `lane_fit`); a family with no `lineage` gets one mechanically (its six most
   cited rows within the corpus, oldest first, marked `lineage_source`). No project script.
   It fails on an unassigned ref, an unknown ref or an unknown family key, and warns
   (stderr only, so read it) on a family holding >60% of papers or a single paper.
   It stamps `family` (the display name) onto `rows.json`, writes `families.json`
   (the reproducible cache) and `families.md` (to the current directory unless
   `--md`), and `spreadsheet.py` adds the `Family` column on the next build. Re-run
   only when the taxonomy or the row set changes (it is a `rows.json` writer).
5. **Render.**
   ```bash
   python3 tools/families_figure.py --rows rows.json --families families.json \
           --out-prefix <topic>_families --title "<Topic> — theoretical families"
   ```
   Add `--time-warp 0.85` when the corpus spans many decades (usual after the
   antecedents pass). The defaults are the standard settings: dots sized by citation
   count (`--size-by-citations sqrt`), `internal_citations.json` read from beside
   `rows.json`, and the exact arguments written to `figure_render_args.txt` when that
   file is missing (an existing one holds tuning notes and is never overwritten; the
   tool says when a render is not recorded in it).

The output is a self-contained `<prefix>.html` (family lanes, every paper as a dot
by year, labeled landmarks, a click panel with the reference and Prev/Next, a hover
on each family name for its claim and lineage) plus a standalone `.svg`, and `.png`
+ `.pdf` when `rsvg-convert` or `inkscape` is present (`--no-raster` skips them).
`--xlsx` embeds the spreadsheet with a download button.

**Dot size.** Keep the default `sqrt` (area-proportional; `log` reads flat, `none`
says nothing about how cited a paper is), normalized at the 95th percentile. Papers
with no count draw **hollow**. When presenting, say that citation count is partly an
age variable, so the right edge of any timeline runs small.

**Landmark labels are automatic; do not hand-build a labels overlay.** A paper is
labeled if ANY of:

1. it is among the top `--per-family` (default 4) most-cited in its family, by
   max(OpenAlex, S2);
2. it is cited by ≥ `--motif-min` (default 3) corpus papers (needs
   `internal_citations.json`; skipped without it);
3. it is a home-lab paper: `source == "lab"`, or an author surname given by
   `--lab-author` (repeatable) or `LITREVIEW_LAB_AUTHOR` (comma-separated; the flag
   wins). Surname matching is **off by default** (the toolkit is lab-neutral).
   Home-lab papers are starred (★) and ringed in `--lab-color` (default gold,
   moved automatically if it matches a lane color; quote the hex in the shell).

Labels are capped at `--max-labels` (default 28). When the cap binds, the home-lab
papers and each family's top 2 survive, the rest of the budget goes by in-degree, and
the tool prints `N papers qualified, M labeled (K dropped …)`. Read that line.

- **`--motif-min` does not scale with corpus size.** On a 396-paper corpus 175
  papers cleared the default 3 and the cap silently discarded 147, so the figure read
  "here are the landmarks" when it meant "28 of 175". Raise `--motif-min` (25 was
  right there) instead of letting the cap choose.
- **Raising a threshold must never remove a label already shown.** A higher
  `--motif-min` shrinks the qualified pool, not just the cap. On
  structure_representation, `--motif-min 10` lost Smolensky 1990, Schuck 2016 and
  Liu 2019 (in-degree 8–9), which the old cap had picked from a larger pool. Tune by
  diffing the before/after label sets: take the highest `--motif-min` with **zero
  removals**, then set `--max-labels` above the resulting qualified count. Six figures
  were retuned this way on 2026-09-19 (+72 landmarks, 0 lost).
- **In-degree undercounts papers whose reference lists were not fetched.** On a
  475-paper AI-alignment corpus built before xref read arXiv lists from Semantic
  Scholar, the auto-landmarks favored old journal classics (Simon, Jensen, Arrow)
  over the field's own arXiv canon. If xref ran incomplete or without `S2_API_KEY`,
  raise `--per-family`/`--max-labels` (checking zero removals) or add each family's
  lineage papers through a `--spec` labels map.
- `--emphasize-source lab` draws every row of one source as a big dot (lab mode);
  `--no-auto-landmarks` turns labeling off.

**Time axis.** `--min-year` clamps the start (older papers pin to the left edge).
`--time-warp <0–1>` blends the linear axis with the empirical CDF of all paper years,
globally: `0` linear, `1` fully density-equalizing, **~0.85** keeps old foundations
legible while decluttering the modern clump. Faint gridlines mark the labeled years,
and the axis labels single years wherever they fit. Always note a nonlinear axis in
the figure caption.

**Editorial overlay (the remaining human checkpoint).** Cross-family arrows and notes
are judgment; curate them with the user via `--spec figure_spec.json`
(`{labels, arrows: [{from, to, color, label}], notes: [{at, text, color}], order,
subtitle}`, all optional). A `labels` map overrides auto-selection entirely. Do not
expect a good arrow set to be generated.

**Write the `claim` as prose for the hover reader.** The figure clamps the drawn copy
under the lane name to the room the lane has and ellipsizes it (`claim_lines()`);
before that clamp, a long claim ran through the next family's title.

**If you change `families_figure.py`**, these bugs each shipped once:

- *Unknown is not zero.* The first size encoding drew a paper with no count as
  uncited; on reverse_polish_notation (67% coverage) a third of the corpus claimed
  zero citations. Before mapping a column onto a visual channel, count how many rows
  have it and decide what a blank looks like.
- *Order follows the drawn geometry.* Next/Prev sorted on `(year, reference)`, but
  the beeswarm fans a year's papers out from the lane center, so the walk hopped (137
  backward steps on a 555-paper corpus). It now tie-breaks on the dot's drawn y. The
  sort looked right through two code reviews.
- *Run interactive code; do not read it.* That bug was caught by executing the
  figure's own `ORDER` expression against its embedded data. After any change to the
  interactive code, run `node tools/checks/verify_nav_order.mjs <figure>.html` and
  `node tools/checks/verify_hover.mjs <figure>.html` (no browser needed).
- *Renders must be deterministic.* Landmarks picked into a Python `set` moved 5 of 57
  labels between two renders of identical input, so the re-render diff was reading
  noise. Sort keys are now `(year, ref)` and `(x, ref)`. Before trusting a
  "re-rendering changes nothing" check, render twice with unchanged code.
- *A marker must not share the palette of what it marks.* The home-lab ring was also
  `PALETTE[4]`, so a lab paper in family 5 got a gold ring on a gold dot.
  `--lab-color` is now resolved against the lane colors in use. Check whether a
  parameter exists before adding one: which lab gets starred was `--lab-author` all
  along.
- *An SVG `<g>` is not hoverable*, and `<text>` takes pointer events only on glyph
  strokes, so the lane-label hover fired only on a letter. Give any SVG-text
  affordance a transparent hit target.
- *The hover panel sits on the lane legend.* Anchored to the label's right edge it
  covered the earliest papers, where a warped axis puts the foundations; it is now
  anchored to the left edge and its width is set before `offsetHeight` is read.

### Phase 7 — Write the review article (OPTIONAL)

Run only when the user asks for a written review. Prerequisites: Phase 3f (canonical
`apa`) and 5b (counts). The Phase 6b families are the natural section structure and
the timeline is the review's figure.

**Authorship and honesty (non-negotiable when a model writes it).** Put the model's
name in `authors`, an `author_note` saying it is an AI, and a `disclosure` stating
that the bibliography was machine-assembled and machine-verified and that the author
read only abstracts and metadata, not full texts. State it once, in the masthead.

**Prose.** Write with the `scientific-writing` skill (one idea per sentence, forward
flow, "represent" reserved for brain representations). Organize sections by the
families, not the topic lanes. The title gives the question, the answer, and why it
matters. Every in-text citation is APA author–date (`(Huth et al., 2016)`) and must
name a row in `rows.json`. Keep the prose in a per-project emitter (`write_review.py`
→ `content.json`, or `build_review_page.py` for the web page) and **edit the
emitter, never the rendered `.docx` or HTML**: a fix applied to the output is lost at
the next render and leaves the output disagreeing with its script.

**Priority: cite the earliest deserving paper (contract rule 5).** The most common
failure of a model-written review is crediting whichever paper fits the sentence
rather than the one that established the idea. A sentence making an **origin claim**
(*emerges, first, established, identified, introduced, was mapped, showed that, had
been, early work, foundational, began, demonstrated, discovery*) cites the earliest
paper that deserves priority, with multiple citations oldest-first. Four inversions
seen in real drafts (2026-06-13):

- a later **review** credited for an earlier **primary** finding (Tanaka 1996 vs.
  Desimone et al. 1984 for object/face selectivity in IT);
- a later **model** credited for an earlier **empirical** result (Reynolds & Heeger
  2009 vs. McAdams & Maunsell 1999 for attention changing gain/tuning);
- a later, narrower paper preferred over an earlier, **more general** one of the same
  year (Dumoulin & Wandell 2008 pRF vs. Kay et al. 2008's per-voxel model);
- in **lab mode**, the lab's own foundational paper relegated while another group's
  follow-up takes the priority slot (Hegdé & Van Essen 2000 vs. Gallant et al. 1993
  for complex-form selectivity in V4). The lab's antecedents (Phase 2b / L4c) exist so
  priority can be assigned correctly.

**Priority audit (required before delivering).** After drafting, dispatch one
independent agent with the draft prose and `rows.json` (every paper with its year).
It scans every origin-claim sentence, checks whether an earlier paper in `rows.json`
(or an undisputed classic) deserves priority, and reports each inversion as
`claim → currently cites (year) → earlier source (year) → fix`. Apply the confirmed
fixes: reorder oldest-first, add the originating paper, demote the later work to
"later", and reword as history. Self-review misses these because the drafting model is
biased toward its own story.

**Concision pass (required; `tools/prose_audit.py`).** A model-written draft is
accurate and unreadable, and the defect is compression, not vocabulary: four or five
findings chained through semicolons into one 60–120 word sentence, each with its own
citation. A filler-word scan of one 10,800-word draft found nothing to cut while 54
sentences ran past 50 words. `cite_check.py` cannot see this.

```bash
cp build_review_page.py /tmp/before.py         # or: cp content.json /tmp/before.json
python3 tools/prose_audit.py --page build_review_page.py             # diagnose
#   ... revise ...
python3 tools/prose_audit.py --page build_review_page.py --baseline /tmp/before.py   # GATE
```

(`--content content.json` for the `.docx` route.) It reports words, mean sentence
length and sentences of ≥ `--long` words (default 45) per block. Aim for a mean near
24 words with almost nothing over 50; first drafts land near 31. Give each finding its
own sentence and cut the semicolon chains. On a 555-reference review this moved the
mean 31 → 24 and 50+-word sentences 54 → 8 for a 3.8% word saving: the gain is
followability, not length. Long sentences are reported, never gated.

- **`--baseline` is the gate.** Splitting sentences is exactly how a reference falls
  out of the works cited, and nothing downstream notices. It compares the cited set
  before and after and exits 1 on any loss. Keep the pre-revision copy outside the
  project.
- **Two blocks sharing many references tell the same story twice.** It reports block
  pairs sharing ≥ `--overlap` (default 8) citations. On the cortical-layers review
  the humans/species section and the laminar-fMRI comparison shared 35; folding one
  into the other cut 372 words and lost nothing, because each of its 27 references was
  cited elsewhere. Check that before cutting.

**Render the `.docx` (`tools/review_paper.py`).** It writes no prose. It lays out the
title/author/disclosure block, abstract, sections and the figure with its caption,
and builds the reference list from **every row's** canonical `apa` (deduped, APA-7
order: authors, then year, then title; hanging indent; DOI links). The schema is in
the module docstring.

```bash
python3 write_review.py            # project file: authors prose -> content.json
python3 tools/cite_check.py --rows rows.json --content content.json   # GATE: exits 1
python3 tools/review_paper.py --rows rows.json --content content.json \
        --figure <topic>_families.png --out <Topic>_review.docx
```

**`cite_check.py` is a gate.** It exits 1 on a citation that names no row. It warns
when one author-year matches two rows (five times on a 396-row corpus). Fix with
APA-7 §8.19, naming enough further authors to tell them apart: `(Kral, Davis, et al.,
2022)`. A `2025a`/`2025b` suffix is also accepted but means editing the canonical
`apa` strings (as hand fixes), which usually costs more.

Open the `.docx` and confirm the figure renders and the structure reads. Worked
example: `distributed_conceptual_network/` (`write_review.py` + `content.json`, 370
references).

**The review web page.** The readable deliverable is a self-contained HTML page from
a project-local `build_review_page.py`: the prose, the interactive timeline
(`<topic>_families.html`) in an iframe, and a numbered works-cited list, built with
`review_paper.reference_list(rows)` so it cannot disagree with the `.docx`. Nothing
else: the timeline's side panel already shows every paper's reference, family,
topic, DOI, summary and counts, and a second reference browser was cut from the first
review that shipped with both. `tools/bib_viewer.py` is for a corpus with **no**
timeline (standalone: `--rows --families --out --title --author --author-note`; or
embedded via `bib_viewer.render()` with `provenance=False` under a masthead that
already carries the disclosure). After a change to the viewer's filter code, run
`node tools/checks/verify_bib_filter.mjs <page>.html` on a page that carries it.

**A toolkit fix reaches a delivered review only when you re-render it.**
`reference_list` once sorted each author's works by title instead of year (67
inversions across 7 delivered reviews, fixed 2026-09-23). Before overwriting a
delivered file, render to scratch and diff the prose: if it differs, the delivered
file holds edits or is an older draft, and re-rendering would destroy them.

### Phase 8 — Hand off

Tell the user:
- Total rows, broken down by source (search / antecedents / xref / forward / lab),
  and how many candidates were considered and excluded.
- The spreadsheet path (never a `_DRAFT` file) and the timeline
  (`<topic>_families.html`, open in a browser) with its families, or that the
  timeline was offered and declined.
- The scale (Phase 1d), any choice recorded at the preflight (`--accept`) or a
  `--no-preflight` reason, and any pass that ran capped or incomplete
  (`--allow-incomplete`, acknowledged `incomplete-*`/`partial-*` warnings), and why.
- For a redo of an old build: the recall against it ("Upgrading an old corpus").
- Verification corrections you made (fabricated ids, wrong first authors, DOIs that
  resolved to another paper).
- **Only if Phase 4 ran:** PDFs downloaded vs. failed, and the path to the
  browser-helper page or `_needs_manual.txt`.

---

## Lab mode — review a lab's corpus in the context of the field

Topic mode starts from a query and searches outward. **Lab mode** starts from a
known body of work (a lab's publications), derives the lab's research themes and how
they shifted, then searches outward to place that work in the field. Everything
downstream (verify, canon, counts, families, figure, gates) is the same machinery.
The three human checkpoints mirror topic mode: **(1) the corpus** (not a topic),
**(2) the themes**, **(3) the figure**. Phase 0 (the preflight) comes first here too.

**Phase L1 — ingest the record.** `tools/lab_corpus.py --search "<name>"` lists
candidate OpenAlex author ids with works count, year span, ORCID and institutions,
and warns on the shapes visible from the listing (see L2). Then
`--author <id> --out lab_papers.json`, repeating `--author` for key lab members **or
for one person whose record is split across ids** (works are deduplicated). Rows are
refs `L1…` with an OpenAlex-built `apa`, `cite_openalex`, `topics`, the OpenAlex
abstract (or the title) in `summary`, and `source: "lab"` (the blue spreadsheet color
and the starred figure landmarks key on it). Then fetch the abstracts, which the
content check reads (OpenAlex abstracts are missing for a sizable minority of papers,
and its `topics` tags are too coarse to classify from):

```bash
python3 tools/abstracts.py --rows lab_papers.json --out lab_abstracts.json
```

**Phase L2 — define the lab (HUMAN CHECKPOINT #1).** Author-id disambiguation is
the #1 correctness risk (OpenAlex ids split, merge and collide; trainees move
between labs).

*Resolving the author id: five real bootstraps, four failure shapes.* The institution
label misled in three of the five; do not pick by it.

| Shape | What it looked like | What decided it |
|---|---|---|
| **Wrong-university** | The id labeled with the right university had 3 works; the correct one showed an unrelated institution and had 130 | Works count, then reading titles |
| **Moved lab** | *Two* candidates carried the searched university and neither was the person (one was a glaciologist); the correct id still showed the PI's previous university | **Distinct ORCIDs** settle it; otherwise the raw affiliation strings on the newest works |
| **Merged** | A *single* candidate spanning 1976–2026, holding at least five people | The **year span**: `--search` warns above 45 years |
| **Split** | *Three* candidates, all the same person, one holding a single high-profile paper | Same ORCID / institutions / adjacent years; pass every id to `--author` |

1. **A single candidate is the dangerous case.** OpenAlex often merges colliding
   namesakes into one id, so "only one match" can mean "all the contamination is in
   here".
2. **ORCID confirms authorship; it does not refute it.** One PI's 18 papers of
   psychiatric neuroimaging looked like a collision and were her own pre-PhD work;
   pruning on topic would have deleted a third of a real record. Profiles go stale
   (another PI's ORCID listed 18 works against OpenAlex's 39), so absence from ORCID
   is not evidence a paper is someone else's.

**Check the record by content (`tools/lab_lane.py`).**

```bash
python3 tools/lab_lane.py --prepare --papers lab_papers.json --abstracts lab_abstracts.json \
        --pi "<PI as printed on papers>"
# one checking agent per lab_check/input_NN.json, brief lab_check/brief.md -> result_NN.json
python3 tools/lab_lane.py --build --papers lab_papers.json
```

The brief has each agent decide, from content and not database tags, authorship,
kind (a meeting abstract, erratum or peer-review report is excluded), species and
duplicates (keep the version of record), web-verifying every item without an
abstract. It keeps the lab's earlier-method and other-species work (the lab's own
antecedents) and real authorship off the lab's program (`off_program`), so an
inclusion filter such as "human work only" never silently drops the lab's
foundational papers: flag those to the user rather than dropping them. Review the
judgment calls the agents flag, then `--build`: it writes lane L
(`search_raw/0_L.json`, `source: "lab"`, excluded items listed with their kind) and
refuses an item with no check, an included duplicate or an item not by the PI.
`--themes` is optional: the themes are approved after this check (L3), so without
it lane L rows carry no theme and `families.py` assigns them at Phase 6b. (Given
approved themes, the agents also assign one per item, and `--build` refuses a theme
outside the file.)

*The record can be incomplete as well as impure.* The merge catches a lab paper that
a field lane found and lane L lacks (L4c); nothing catches one that no lane found.
So check explicitly for a split id, and say in writing how many records were added
as well as pruned. Off-program authorship (a PhD in another field, a postdoc
elsewhere) is real but skews any step that reads titles: in one corpus such papers
were 35% of the total and the keyword derivation proposed *schizophrenia* for a
speech lab.

**Phase L3 — derive themes (HUMAN CHECKPOINT #2).** Propose the lab's research
programs from the papers lane L kept, with Step 1 of `family_prompt_template.md`,
ignoring the off-program vocabulary, and have the user approve them. They define
the per-theme lanes of L4c and are the family spec for Phase 6b on the merged
table.

**Phase L4 — the lab's trajectory.** `families_figure.py` gives themes × year with the
lab's papers as the spine: this *is* "the lab's topics and how they changed over
time". `spreadsheet.py` gives the bibliography.

**Phase L4c — contextualize: a FULL topic-mode review per theme.** Not optional and
not lighter: run Phases 2–6 with the same guardrails. Treating it as a quick
"context" add-on is how a sloppy, half-fabricated field set gets into an otherwise
careful review.

1. **Spec and search (Phases 1d, 2, 2b).** One forward lane per theme (a precise
   definition, the lab's papers in that theme as its `already_have`), plus the
   antecedent lanes, with `"lab": {"pi": "<PI as printed on papers>", "lane": "L"}`
   in the spec. Every brief then tells its agent to defer a paper with the PI as an
   author to lane L instead of keeping it.
2. **Merge with lane L (Phase 2c).** `merge_lanes.py --raw search_raw --out
   rows.json` with `0_L.json` in `search_raw/`. It fails `LOST` on any lab paper a
   field lane deferred that the record lacks: that is the completeness check a split
   author id needs. `0_L.json` sorts first, so a lab paper a field lane also found
   keeps its lab row. Use `--raw`, not `--append`: `--append` checks no deferrals.
3. **The shared pipeline (Phases 3–6)** on the merged table. Lane L rows arrive with
   no summary (write them from the abstracts), and its DOI-less items get hand checks
   (Phase 3e).
4. **Families and the figure (Phase 6b)** on the merged table, with the L3 themes as
   the family spec and `--emphasize-source lab` to keep the lab's papers as the
   labeled spine over the field dots.

In a Phase 7 review, the lab's foundational papers (lane L and Phase 2b) let the
priority audit credit the lab's earlier work over later follow-ups (contract rule 5).

---

## Lessons learned (don't repeat these mistakes)

Each entry is a rule plus the incident that established it. Rules that a phase
already states are kept there; the incidents behind them are here.

### Lane briefs and search agents

Most of these rules now live in `search_prompt_template.md`, which `lane_briefs.py`
renders into every brief; the incidents stay here.

- **The verification duty** (landing page, first author and year read off it, the
  DOI's target confirmed, abstract read before summarizing, unconfirmable papers to
  `could_not_confirm`) drives the ~25% error rate of contract rule 1 to about zero:
  on the 541-ref cortical-layers build Phase 3 returned 535 OK, 2 MISMATCH and 0
  NOT-FOUND, both exceptions being diacritics the agent dropped (`Hertag` for
  `Hertäg`), which canon restored. Phase 3 still runs: it is the gate that proves
  this happened. The `could_not_confirm` lists are where the useful findings come
  from (a misattributed classic, a wrong stored DOI, a title that does not exist;
  the DOI in circulation for Nandy et al. 2017 resolves to a different Neuron paper).
- **Seeds are titles only** (`lane_briefs.py` refuses one that names an author).
  Author-name seeding injected fabricated attributions into three builds.
  Remembered titles fail too: on the cortical-layers build about 40 of ~170 seeded
  titles did not exist ("Cortical microcircuitry of attention", "The draining vein
  problem in laminar fMRI"). It cost little because the briefs labeled them as
  unreliable, and every agent substituted the real nearest work. Better still, seed
  from a real source (a sibling corpus, a review's reference list).
- **The session's WebSearch quota (200 calls) is shared by all subagents.** With 14
  lanes it ran out after about two; the other twelve used the Europe PMC, PubMed
  E-utilities, CrossRef, bioRxiv and arXiv REST APIs, which is not a degradation
  (dated, field-restricted sweeps are more systematic; the weak spot is work that
  does not use the topic's vocabulary in its title). The brief names that route as
  first-class. Resume a thin lane through SendMessage (Phase 2c).
- **A concrete target, never "as many as possible".** Asking for 40 gave 40–44;
  "as many as possible" gave sprawl with more fabrications. The scale sets it
  (Phase 1d).
- **Agents invert findings.** One described "X > Y" for a paper that found the
  opposite. That is why every summary is checked against its abstract (Phase 5c).
- **NOT-FOUND is a real failure; ERROR is not NOT-FOUND** (rules in Phase 3). Before
  verify.py queried arXiv directly, preprints came back NOT-FOUND and were waved
  through: a "Vo et al." attention paper was really Foster et al., and two Jain & Huth
  arXiv ids pointed at unrelated papers. On a ~90-paper world_models run, 8 real
  preprints came back NOT-FOUND only because a per-paper arXiv loop drew a 429 ban;
  verify now batches arXiv ids and reports ERROR when a lookup cannot complete.

### Casing and foreign-language titles

From a 493-ref history corpus (2026-08-29); all now handled by the tools and covered
by `tools/tests/test_formatting.py`. Keep them in mind when changing a formatter.

- **Never sentence-case a non-English title.** The pass lowercased German nouns ("der
  kumpan in der umwelt des vogels"), so `sentence_case.py` skips German/French titles
  (`--include-foreign` forces casing). `von`, `de` and `man` are not usable language
  markers ("Karl von Frisch", "fin-de-siècle", "including man").
- **A partly ALL-CAPS title is shouting, not an acronym** ("BEHAVIORAL MUTANTS OF
  *Drosophila* ISOLATED BY …" passed both casers). `sentence_case.py` lowercases runs
  of ≥3 all-caps words and keeps isolated acronyms (`fMRI`, `MEG`).
- **Model-organism genera are proper nouns** (canon once emitted "the genetics of
  caenorhabditis elegans"); `common.GENERA` restores them.
- **A `?` inside a title or venue is mangled punctuation** (`?Matched filters? ?
  neural models…`, `Journal of Comparative Physiology ? A`): the audit fails
  `mangled-punct`. **Stripped JATS markup glues words** (`the cockroachPeriplaneta
  americana`): `missing-space`. Both hit the same rows; a deposit broken one way is
  usually broken in several.
- **Why canon does not sentence-case Title Case.** Correct casing needs proper-noun
  judgment (`Bayesian`, `Atari`, `Tolman-Eichenbaum` stay capitalized; `Active`,
  `World`, `Model` do not), and a mechanical caser's errors are invisible to the
  audit. So `sentence_case.py` proposes and a person reviews (Phase 3f).

### Reference records: what CrossRef gets wrong

- **Back-file deposits re-date old papers.** Digitized back catalogs carry the
  digitization year: Seyfarth & Zottoli 1991 deposited as 2008, Lorenz 1943 and
  Schleidt 1962 as 2010 (`10.1111/j.1439-0310.1943.tb00655.x`: the year is in the
  suffix). The audit warns `deposit_year_conflict()`; only a human can say which year
  is right. `doi_year()` matches only the Wiley `.<year>.tb<n>` shape on purpose: a
  broad 4-digit scan gave 15 false positives and no true ones on 493 refs (page
  numbers, article ids, ISSN fragments). Seyfarth's `10.1159/000114363` carries no
  year; verify's year check is what catches that one.
- **Deposited names can be plain wrong.** `family="A. Moffat"` (now auto-repaired: no
  surname starts with an initial), `family="(Bud) Craig"` (nickname now stripped), and
  `Sprby` for Terje Sparby, a misspelling caught only by finding the name spelled
  correctly on a sibling paper. The last kind is caught only by reading.
- **Compound and particle surnames get mis-split** (`Lambon Ralph` → `Ralph, M. A.
  L.`; `de Heer` → `Heer, W. A. D.`; the reverse, `J. Adam Noah` → family `Adam
  Noah`). The audit warns on every multi-word surname; expect some legitimate ones
  (Spanish, Vietnamese, Italian double surnames). Fix a real mis-split in
  `hand_fixes.json` (Phase 3f).
- **`U+FFFD` mojibake is unrecoverable at the source** (`Bürgel`, `Zeitschrift für
  Anatomie`), and every re-canon pulls it back in; that is why hand fixes live in
  `hand_fixes.json`, which canon re-applies (Phase 3f).
- **Subtitles.** CrossRef keeps a series part or subtitle in a separate field; until
  2026-08-22 canon dropped it, so Creutzfeldt 1989 parts I and II rendered as one
  identical title, and a `possible duplicate (1.00)` warning was the only tell. Canon
  now joins them (`common.crossref_record`). Corpora canonicalized before that date
  need subtitles restored by hand. Their older hand fixes were typed into `rows.json`
  and are lost on a re-canon unless first recorded in `hand_fixes.json`.
- **Book chapters.** CrossRef deposits `container-title` as `[series, book]`; canon
  builds `In Book (pp. x-y). Publisher.` from the last entry
  (`common.build_chapter_apa`). Most chapters have no deposited editors, and Springer
  sometimes deposits the WRONG book (Biggio 2013 carried another volume's title and
  ISBN), so spot-check chapter rows; book titles still need hand sentence case.
- **Formatter defects sit in finished work.** JATS markup in titles, `?.` double
  terminals and U+2010/U+2011 hyphens in surnames (`Fischer‐Baum`) shipped in five
  delivered bibliographies before the gate caught them. After a formatter change,
  re-run `--audit` over old projects (`references.py --repair` fixes these classes
  offline; see "Upgrading an old corpus").
- **A whole-string check condemns legitimate titles** (for anyone adding an audit
  check). Forbidding `et al.` anywhere failed Nature's "<Author> et al. reply"
  titles; the check now reads only `parse_apa`'s author segment, falling back to the
  whole string when the reference will not parse. Ask which APA segment a defect lives
  in before checking.

### Versions, duplicates and the version of record

- **Keep both ids on a row that has them**; canon prefers the journal DOI (Phase 3f).
- **Not every "published" DOI is the version of record.** Curran/Proceedings.com
  `10.52202/*` DOIs for printed NeurIPS volumes resolve and match title searches, but
  moving 6 gallant_lab rows to them would have cut OpenAlex counts ~3–4× (MindEye 40 →
  11) for nothing. ACL Anthology (`10.18653/*`), IEEE/CVF (`10.1109/*`) and journal
  DOIs are real upgrades (MindBridge 2 → 41). Before promoting a preprint row, compare
  the candidate DOI's OpenAlex count with the arXiv record's; if it is much lower, keep
  arXiv and name the venue in prose.
- **The same paper can enter twice under two DOIs** (preprint from one lane, journal
  version from another); three such pairs sat in a 362-row corpus for six weeks. The
  merge (Phase 2c) and the audit's duplicate scan both flag possible pairs as
  warnings; real distinct papers also collide (a 2014 toolbox and its 2026 successor),
  so each pair needs a verdict. Keep the version of record, drop the preprint, and
  re-check any in-text citation whose year moves (2025 → 2026).

### Network failures that look alike and are not

A run that will not finish is almost always one of these. All three arrive as
`http.client.HTTPException` and are correctly classed transient; they differ in
timing and determinism.

| Symptom | What it is | Fix (in `common.http`) |
|---|---|---|
| Random requests fail, succeed on retry | genuine rate limiting | backoff; raise `--sleep` |
| The **same** large records fail at the **same byte count**, small ones fine | truncation of a large uncompressed body (`IncompleteRead(1782210 bytes read, 399724 more expected)`) | `Accept-Encoding: gzip, deflate` + `common.decompress` |
| The **same** records fail **instantly** (~0.3 s), curl fetches them fine | HTTP-stack / proxy incompatibility | `common.curl_get` at the first network failure |

Only the first is fixed by waiting; against the other two a retry loop runs forever
and reports as slowness. On the cortical-layers build, uncompressed: 117 of 537 rows
failed canon and xref managed ~19 papers per 7 minutes; compressed, the same records
fetch in 0.3 s. Then 71 of 536 xref fetches failed on the stack issue; curl-first
takes 0.7 s instead of 32 s of backoff. urllib does not decompress, so requesting gzip
and decoding it must land together; `decompress()` passes an unknown encoding through
rather than raising.

**First diagnostic:** re-fetch one failing URL with `curl -sS --compressed`. If curl
succeeds where the tool failed, it is not the server, and `--sleep` will not help.

### Citation counts (Phase 5b)

- **Google Scholar cannot be automated** (no API; CAPTCHA after ~10–20 requests).
- **OpenAlex is the workhorse** (~95%+ coverage by DOI) but undercounts arXiv-only
  preprints, which it files separately from the published version; lean on S2 for
  those rows.
- **OpenAlex's batch filter can return a low-count duplicate** (Whittington 2020 TEM:
  6 from the batch, 667 from `/works/doi:`; Tolman 1948: 1 vs 6,656). `citations.py`
  keeps the max per DOI in a batch and re-queries the single-work endpoint when
  OpenAlex < half of S2 (S2 ≥ 50). Still spot-check landmark counts against the S2
  column: a famous old paper with single-digit OpenAlex is the tell.
- **Semantic Scholar without a key** 429s, 400s a whole batch on one malformed id
  (`common.s2_batch` bisects to isolate and name it) and 404s valid papers under load.
  Set `S2_API_KEY`; without it, accept partial S2 coverage.
- The two columns will not match each other, and GS-style totals run higher than
  both.

### On the spreadsheet

- **Ref ids must be unique across merges, and counts must not be keyed by a reused
  ref.** A one-character lane prefix plus a counter is ambiguous (lane `4`, ref `410`
  vs lane `41`, ref `0`): a naive merge re-emitted an xref batch as `410…` over the
  existing `410…`, `families.py` assigned one paper twice, and two rows sharing `415`
  shared one count, so Carvalho 2024 inherited Elman 1990's 10,838 citations. The
  tools now use separator ids (`<KEY>-01` in every brief and `candidates.py` export)
  and `merge_lanes.py` refuses a repeated ref; still attach counts only after ids are
  final, and assert `len(refs) == len(set(refs))` after any hand merge.
- `rows.json` is the table; the `.xlsx` is only a rendering of it (xlsxwriter is
  write-only). A project row emitter (from `templates/build_rows_template.py`) runs
  once, guards its writing block under `if __name__ == "__main__":`, and writes through
  `common.write_rows`, which refuses to overwrite a canonical table (contract rule 6).

---

## API endpoint reference

| Service | URL pattern | Returns |
|---------|-------------|---------|
| PubMed esearch | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=<q>&retmode=json` | List of PMIDs |
| PubMed esummary | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=<id>&retmode=json` | Title/authors/year |
| PMC esummary | `...?db=pmc&id=<numeric_pmc>` | Same, for PMC |
| Unpaywall | `https://api.unpaywall.org/v2/<doi>?email=<email>` | OA PDF URLs |
| CrossRef metadata | `https://api.crossref.org/works/<doi>` | Title, authors, references |
| DataCite | `https://api.datacite.org/dois/<doi>` | Zenodo/figshare/OSF/Dryad records (verify and canon fall back to it on a CrossRef 404) |
| OpenAlex (counts) | `https://api.openalex.org/works?filter=doi:<d1>\|<d2>...&mailto=<email>` | `cited_by_count`, 50 DOIs/request; budget and credit costs in Phase 0 |
| Semantic Scholar (counts) | `POST https://api.semanticscholar.org/graph/v1/paper/batch?fields=citationCount,influentialCitationCount` body `{"ids":["DOI:..","ARXIV:.."]}` | citation + influential counts, ≤500 ids/request; `S2_API_KEY` as `x-api-key` |
| EuropePMC search | `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=<q>&format=json` | Full search |
| EuropePMC PDF | `https://europepmc.org/articles/<PMCID>?pdf=render` | PDF (often) |
| arXiv API | `https://export.arxiv.org/api/query?search_query=all:<q>` (the tools use `id_list=`) | Atom XML |
| arXiv PDF | `https://arxiv.org/pdf/<id>.pdf` | PDF |
| Nature direct | `https://www.nature.com/articles/<id>.pdf` | PDF (if OA) |

Rate limits worth knowing:
- arXiv API: ~1 request/3 s; bursts trigger 429 (`common.arxiv_batch` sends 50 ids per
  request, 3 s apart).
- NCBI eutils: 3 requests/s without an API key, 10/s with one. Use a 0.4 s sleep.
- CrossRef: polite pool with `mailto:` in the User-Agent gives unlimited; without,
  ~50/s.
- Unpaywall: 100k requests/day per email.

Every tool sends a User-Agent carrying your contact email (`LITREVIEW_EMAIL` or
`--email`).

---

## Reusable helper scripts

All in `tools/`. Each is standalone, reads JSON/CLI input and writes JSON/files; run
`python3 tools/<script>.py --help` for flags. The index below is generated from the
modules by `python3 tools/gen_docs.py` (CI fails if it is stale); per-tool detail is
in `tools/README.md` and `docs/tools.md`.

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

Notes the index cannot carry:
- `references.py --repair` retrofits an old corpus offline (no re-fetch). It stamps
  `canonical_at` only on a legacy table: on a gated table `canonical_at` means
  "rebuilt from a verified source", which an offline repair is not.
- `tools/checks/*.mjs` (Node.js, no browser) execute the figure's and the viewer's
  own scripts: `verify_hover.mjs`, `verify_nav_order.mjs` (Phase 6b) and
  `verify_bib_filter.mjs` (Phase 7).
- Project scripts `import common` (see tools/README.md, "Using the toolkit from a
  project script") and write `rows.json` through `common.write_rows`.

The helpers are small and meant to be read and adapted: scaffolding to keep the
judgment work fast, not a framework.

---

## Upgrading an old corpus

Rerunning a search on an existing bibliography brings the WHOLE project up to the
current standard, or redoes it if that is easier; it is never a lighter pass over
just the new rows. The first verified row (or any row a current tool built, which
carries `built_at`) switches the reference gates on for the whole table
(`common.is_gated`), and from then on the audit and the spreadsheet fail every OLD row
that lacks the new records.

Procedure, in order:

1. `verify.py --rows rows.json` over the WHOLE table. A canonical row that kept its
   search claim (`search_*`) is checked against both the claim and its `apa`; one
   with no claim can only be checked against its own `apa`, and the audit warns
   `identity-not-reestablished` until you confirm the DOI by hand (Phase 3d).
2. Turn existing hand checks (`verify_note` text, informal results) into `handcheck.py
   --ingest` result files; re-check any whose source is not recorded. A
   `hand_verified` record without `apa_sha` (written before hand checks were bound to
   the `apa`) counts as missing: re-ingest it.
3. `abstracts.py`, then `summary_audit.py --prepare` / checking agents / `--ingest`
   (Phase 5c). Older `abstracts.json` entries and `summary_check` stamps record no
   ids, so they count as unbound: `abstracts.py` refetches fetched entries, a
   hand-added landing-page entry needs the row's `doi`/`arxiv` added (it is reported
   stale until then), and every summary is re-checked.
4. Before any re-canon, record the table's old hand fixes (corrections typed into
   `apa` after an earlier canon) in `hand_fixes.json`; canon re-applies only those
   (Phase 3f). If the audit shows formatter defects (markup, Unicode hyphens, `?.`),
   `references.py --rows rows.json --repair` fixes them offline instead.
5. Bring the candidate ledger up to date over the existing xref/forward output:
   `candidates.py --rows rows.json --add xref_<topic>.json --source xref` (and `--add
   forward_candidates.json --source forward` if there is one), then decide each
   pending entry (`--list pending`; `--decide DOI --decision include|exclude --reason
   "..."`). An old output with no `.run.json` sidecar is recorded as an incomplete
   run (`incomplete-*-run`): re-run the pass, or acknowledge it. A gated table with no
   `candidates.json` at all warns `no-candidate-ledger` under `*`; acknowledge it only
   if the corpus genuinely never ran xref/forward.
6. Acknowledge each remaining warning (`references.py --list-acks`, then
   `audit_acks.json`; Phase 3f).
7. `references.py --audit`, then `spreadsheet.py`.

**When a full redo is easier:** few old rows carry a DOI, the rows lack the search
agents' claims (`search_*`, so verify has nothing independent to check against), or
the lanes are stale enough that a fresh search is simpler than reconciling row by row.
Say which you chose, and why.

**A redo is measured against the old build.** A redo is a new search, so it starts
at Phase 0. Build it in its own folder (the old one stays as the baseline), then,
after the first merge:

```bash
python3 tools/recall.py --rows rows.json --old ../<old>/rows.json --where source=search \
        --out manual_check/recovery_input.json
```

It reports how many of the old build's papers the rerun found (by DOI, arXiv id or
title) and writes the misses for ONE recovery lane, whose agent decides each again
(include with a claim read off the landing page, or exclude with a reason; the old
reference is a pointer, not a claim); append its file with `merge_lanes.py
--append`. Report the recall at hand-off.

---

## Quick start for a fresh Claude

Read this playbook, then any existing `rows.json` (after Phase 3f it is the live
table; the `.xlsx` is only a rendering). Confirm topic and criteria with the user. Do
NOT ask whether to download PDFs: the default is no (Phase 4 is opt-in). Extending or
rerunning an EXISTING corpus follows "Upgrading an old corpus"; lab mode builds lane L
first ("Lab mode", L1–L3). Then, in order:

```
 0. Read the scale from the user's description (Phase 1d; standard if they
    said nothing), then
    python3 tools/preflight.py --project <dir> --scale <scale>        (Phase 0)
    Exit 2: stop. Offer the newer toolkit if it found one (install only on a
    yes); if access is short, give its three choices: get the keys, cap the
    search, or be prepared to wait. Record the pick by rerunning with
    --accept cap|wait|current-version. Mid-build reruns: --no-update-check.

 1. Scope the topic (Phase 1a-c). Write <dir>/lanes.json with the forward
    AND antecedent lanes (Phases 2 + 2b), then
    python3 tools/lane_briefs.py --spec <dir>/lanes.json
    Launch one general-purpose agent per lane, all in one message, with the
    prompt it prints; each writes search_raw/<KEY>.json.

 2. python3 tools/merge_lanes.py --raw search_raw --out rows.json       (Phase 2c)
    A lost, unconfirmed, rejected or over-cap paper fails the merge and writes
    no rows.json: fix the lane or send the papers to one recovery lane, and
    re-merge. Resume a lane flagged thin.

 3. python3 tools/verify.py --rows rows.json --out verify_report.json   (Phase 3)
    Fix or drop each MISMATCH / NOT-FOUND / UNCHECKED; re-run ERRORs
    (--retry-from verify_report.json --out verify_report.json); clear a false
    alarm with --override REF --reason "...". Meanwhile handcheck.py
    --prepare; after verify finishes, --adopt-dois (or --reject), the
    hand-check agent, and --ingest (Phase 3e).

 4. Pitch the families (Phase 6b steps 1-2): families.py --digest, propose,
    and let the user use, change, or skip them. Steps 5-6 run meanwhile.

 5. Once rows are verified, two tracks at once:
    a. canon: references.py --rows rows.json --out rows.json      (Phase 3f)
    b. citations.py (5b), abstracts.py (5c) and
       xref.py --internal-out internal_citations.json (6), side by side
    After canon has finished (both write rows.json): citations.py
    --attach-only (5b), then forward.py (6).

 6. candidates.py --add both outputs; decide every pending one with a
    reason; --export-included; merge_lanes.py --append; then verify --only,
    references.py --only, citations --attach, abstracts, and a summary and
    topic for each new row (Phase 6).

 7. sentence_case.py (review with --vocab and a --proper file, then --apply)
    (Phase 3f). Record any hand fix in hand_fixes.json whenever you find it;
    canon and --apply re-apply them.

 8. summary_audit.py --prepare; one checking agent per batch, no web access;
    --ingest. Fix each flagged or wrong-abstract row and re-run (Phase 5c).

 9. Unless skipped at step 4: assign families (families.py --assign
    families_input.json --out families.json; read the hard calls it prints)
    and render the timeline (families_figure.py) (Phase 6b).

10. references.py --list-acks -> audit_acks.json for every remaining
    warning; references.py --audit must exit 0 (Phase 3f).

11. python3 tools/spreadsheet.py --rows rows.json --out <topic>_bibliography.xlsx
    It runs the full audit and writes only a passing table; --draft writes a
    marked <out>_DRAFT.xlsx, never the deliverable (Phase 5).
```

Then Phase 7 (review, only if asked) and Phase 8 (hand-off). Plan on hours: the
measured timings are under "Running steps at the same time". If you change any tool,
phase or command, update the matching `docs/` page (see "Documentation site — keep it
in sync").
