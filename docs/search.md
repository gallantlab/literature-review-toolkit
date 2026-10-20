# Searching

This page covers the steps that build the first table: the preflight, the scope,
the search lanes, and the merge. Lab mode replaces the search with the lab's own
record; see [Build a lab corpus](#build-a-lab-corpus-lab-mode). From
verification on, both modes run the same steps ([Checking](checks.md)).

Commands run in the project folder and reach the scripts as `../tools/`
([Where files live](pipeline.md#where-files-live)).

| | Topic mode | Lab mode |
|---|---|---|
| Starts from | a question | a lab's publications |
| Direction | searches outward | derives themes, then places them in the field |
| Front-end phases | 1 scope, 2 search, 2b antecedents, 2c merge | L1 ingest, L2 prune, L3 themes, L4c contextualize |
| Answers | "What is known about X?" | "What has this lab done, and where does it sit?" |

---

## Run the preflight (Phase 0)

A review runs for hours, and two of its services ration keyless use. The
preflight finds out, before the review starts, whether it can finish. Create the
project folder and run it from the bibliography root:

```bash
mkdir -p <topic>
python3 tools/preflight.py --project <topic>/ --scale focused
```

`--scale` is the size of the search (`scan`, `focused`, `standard`, `exhaustive`
or a number of papers; see [Set the scope and size](#set-the-scope-and-size-phase-1)).
Add `--lanes N` if you know the lane count. `--papers` gives the planned corpus
size directly instead (default 500).

**What it does.** The preflight:

1. **Checks for a newer toolkit.** It compares this copy's version with the one
   on GitHub. When GitHub is newer, it prints the update command:
   `git -C <toolkit> pull --ff-only` for a clone, or the Claude Code `/plugin`
   menu or a fresh download otherwise. It never installs anything.
2. **Checks the variables** `LITREVIEW_EMAIL`, `OPENALEX_API_KEY` and
   `S2_API_KEY`.
3. **Probes OpenAlex and Semantic Scholar** with one request each, and reads how
   much of today's OpenAlex budget is left.
4. **Estimates the OpenAlex credits** the review needs, and the largest review
   today's budget can cover.

A review already under way keeps the version it started with: pass
`--no-update-check`. `--offline` checks the variables only, with no probes and no
version check.

**When it stops.** Exit 0 means the review can run as planned. Exit 2 means the
user decides first:

- **A newer toolkit** is offered to install or decline. After an install, rerun
  the preflight.
- **A missing `LITREVIEW_EMAIL`** must be set; then rerun.
- **A missing key or a short budget** offers three choices:
    - **Get the API keys.** Both are free, and each has its own budget. Add the
      exports to the shell profile, open a new shell, and rerun.
    - **Cap the search.** Use fewer lanes and a hard per-lane cap, with a capped
      scale (`scan`, `focused` or a number). Every brief then says the search is
      capped. Each lane lists its on-topic papers over the cap in `excluded`,
      with the reason `over the capped-search limit`, so they appear on the
      spreadsheet's "Considered and excluded" sheet. Without `S2_API_KEY`, also
      run `xref.py --allow-incomplete`, and say so at hand-off.
    - **Wait.** Nothing is skipped, but it takes longer. An OpenAlex step that
      runs out of budget stops with `OpenAlexBudgetError`; rerun it after the
      budget resets at midnight UTC. A large review can need more than one day.
      Semantic Scholar steps back off on every 429, and can take hours on a large
      corpus.

**The record is a gate.** Every run writes `preflight.json` into the project
folder; if the folder does not exist, nothing is recorded. `merge_lanes.py`
refuses to run without a record that is at most 14 days old and cleared. A record
is cleared when everything passed, or when the user's choice is recorded: rerun
with `--accept cap` or `--accept wait` after a key or budget stop, or
`--accept current-version` to keep this toolkit. A run whose every stop is
accepted exits 0. A missing email can never be accepted. After a cap choice,
`lane_briefs.py` refuses an uncapped scale. To merge with no record, pass
`merge_lanes.py --no-preflight "reason"`; the reason is kept in
`merge_report.json`.

!!! note "Why the OpenAlex budget matters"
    Without a key, OpenAlex gives each IP address 1,000 credits a day, shared by
    every client behind it; a key has its own 10,000. OpenAlex serves the
    citation counts, abstracts, forward citations, the hand-check DOI search and
    `lab_corpus.py`. On a campus network, others can spend the shared budget
    before the day's review starts. A spent budget shows as a 429 asking for a
    wait of more than 10 minutes. Backing off cannot help, so the tools stop at
    once with `OpenAlexBudgetError`.

## Set the scope and size (Phase 1)

**Scope.** The agent and the user agree on the question and its span: field,
species or method restrictions, and how far back. The agent writes it to
`topic_definition.md`, which anchors every later search. It asks only about what
the request leaves open.

**Size.** The user says it in their own words. The agent maps it to a scale,
passes the scale to the preflight, and writes it into the lane spec:

| Scale | The user says | Papers per lane | Capped | Lanes |
|---|---|---|---|---|
| `scan` | "a quick look", "the key papers" | 15 | yes | 2–4 |
| `focused` | "the core literature" | 30 | yes | 3–8 |
| `standard` | nothing about size (the default) | 40, as a floor | no | 4–12 |
| `exhaustive` | "everything", "comprehensive" | 60, as a floor | no | 6–20 |
| a number | "about 300 papers" | the total, spread over the lanes | yes | up to 50 |

A lane may set its own target. A smaller scale means fewer papers, never fewer
checks: every gate runs at every scale, and every scale needs an antecedent lane.

## Write the lane spec (Phase 2)

Each search lane is an agent with its own generated brief; never write a brief by
hand. Describe the lanes in a spec, `lanes.json`, in the project folder:

```json
{"title": "Anatomical connections between the visual system and the cerebellum",
 "for": "<who the review is for>",
 "description": "What the bibliography covers, and what is out of scope for every lane.",
 "scale": "focused",
 "lanes": [{"key": "A", "name": "Cerebello-thalamic projections",
            "short": "one line for the lane table", "kind": "forward",
            "definition": "...", "exclusions": ["..."], "queries": ["..."],
            "seeds": ["a landmark title, no author"]},
           {"key": "R", "name": "Roots: tract-tracing methods", "kind": "antecedent", "...": "..."}]}
```

The example shows two lanes; a `focused` spec needs three to eight. Then render
the briefs:

```bash
python3 ../tools/lane_briefs.py --spec lanes.json
```

**What it does.** `lane_briefs.py` fills
[`tools/search_prompt_template.md`](https://github.com/gallantlab/literature-review-toolkit/blob/main/tools/search_prompt_template.md)
for each lane, keeping only the blocks that apply: forward or antecedent, capped
or uncapped, lab mode, seeds. It writes `briefs/brief_<KEY>.md`,
`lane_manifest.json` and an empty `search_raw/`. It prints the prompt to give
each search agent, and a preflight command sized to the plan. Lab mode adds
`"lab": {"pi": ..., "lane": "L"}` ([Build a lab corpus](#build-a-lab-corpus-lab-mode)).

**When it fails.** It refuses a spec, naming each problem, when it has:

- a missing field, a repeated lane key, or a seed that names an author;
- a lane count outside the scale's range, or no antecedent lane;
- an uncapped scale after the user chose, at the preflight, to cap the search;
- a brief with anything left unfilled.

So every brief carries the verification duty and the other rules.

### The lane file

Each lane agent writes one JSON lane file (schema 2) into `search_raw/`. Links
must be DOI URLs. Papers older than the tier boundary (the spec's `tier`, by
default five years before today) must be highly cited or foundational. Newer
papers have no citation threshold, because they have not had time to collect
citations.

| List | What goes in it |
|---|---|
| `papers` | every on-topic paper the lane keeps; each needs a DOI or an arXiv id, and a book or report with neither needs its full APA reference |
| `deferred` | a hand-off: a paper for another, named lane (`to_lane`), with its `first_author` and `year` |
| `excluded` | a decision: a paper outside the scope, or an older paper below the bar for classics, with its `reason`, `first_author` and `year` |
| `could_not_confirm` | a paper the lane could not confirm exists |

**In an uncapped search, the target is a floor.** A lane never drops an on-topic
paper to stay near its target; "trimmed to target" is not a reason. Uncapped
lanes typically return about three times their target.

**In a capped search, the target is a hard cap.** Each lane keeps its most
important papers and lists every other on-topic paper in `excluded`, with the
reason `over the capped-search limit`. The merge fails a capped lane that returns
more than its cap.

!!! warning "Expect a third of remembered seed titles not to exist"
    About 30–40% of landmark titles recalled from memory are not real papers. The
    brief labels seeds as unverified titles, and `lane_briefs.py` refuses a seed
    that names an author. An agent told the seeds may be wrong substitutes real
    work; an agent not told invents a paper to match.

!!! note "Why every brief carries a verification duty"
    The brief tells each lane to read the author list off the landing page,
    confirm that the DOI resolves to the right paper, and read the abstract
    before summarizing. Without that duty, about 1 in 4 citations came back
    wrong. A 555-paper corpus built with it returned 535 OK, 2 MISMATCH and 0
    NOT-FOUND at verification.

## Search for the field's roots (Phase 2b)

The forward search favors recent papers and the topic's current framing, so it
misses the field's roots. Antecedent lanes search for three kinds:

1. **Methods**: where the measurement tools came from.
2. **Foundational results**: older physiology, psychophysics and behavior.
3. **Theory**: the ideas the field is built on.

Give these lanes `"kind": "antecedent"` in the spec; their briefs favor classics.
Launch them with the forward lanes, into the same `search_raw/`. Classics from
before 2000, and books and chapters, often have no DOI. Those keep a hand-written
APA reference, get a hand check
([Hand-check references with no DOI](checks.md#hand-check-references-with-no-doi-phase-3e)),
and get no citation count.

## Merge the lanes (Phase 2c)

Once every lane has finished, merge the lane files into `rows.json`:

```bash
python3 ../tools/merge_lanes.py --raw search_raw --out rows.json
```

The merge first reads `preflight.json`, and stops if there is no cleared record
under 14 days old ([Run the preflight](#run-the-preflight-phase-0)).

**What it does.** `merge_lanes.py` removes duplicates by DOI, then arXiv id, then
normalized title plus year. It keeps each lane's claim as `search_author`,
`search_year` and `search_title`, which verification checks the DOI against.

- **A title and year match alone is a hint, not a merge.** Two rows count as one
  paper only when the lanes' claimed authors and years agree and the rows do not
  carry two different journal DOIs. A preprint DOI and its own journal DOI are
  not a conflict. Otherwise both rows are kept and reported as a possible pair.
- **Every pair of kept rows is compared by title.** A pair with a similarity of
  0.9 or more, whatever the year or DOI, is listed as a possible duplicate. A
  title of fewer than four content words must match exactly, so "The human
  visual cortex" does not pair with every longer title that contains its words.
- **Exclusions never need to match a row.** The merge records them in
  `merge_report.json`, and the spreadsheet lists every exclusion that no lane
  kept on its "Considered and excluded" sheet. A paper missing from the table is
  then visibly one that a lane decided against.

**When it fails.** In each of these cases the merge writes `merge_report.json`
but not `rows.json`, and exits 1:

| Failure | What it is | Fix |
|---|---|---|
| Lost deferral | a deferred paper that no lane's `papers` matched by DOI, arXiv id or title (a title match needs a similarity of 0.9, or each title's words 90% contained in the other, confirmed by `first_author` or `year`) | send the lost papers to one recovery lane, add its file to `search_raw/`, and re-merge |
| Deferral to no other lane | an empty, "none" or own-lane `to_lane`: an exclusion or trimmed paper in the wrong list | put it back in `papers` if on topic, or move it to `excluded` |
| Unconfirmed deferral | a title-only match whose deferral gives neither `first_author` nor `year`, or an unreadable `first_author` such as "?" | add the missing fields, or send it to a recovery lane |
| Rejected paper | no DOI, no arXiv id and no APA string, so it can be neither verified nor hand-checked | give it a DOI or arXiv id, or have the lane write its full APA reference |
| Capped lane over its cap | read from `lane_manifest.json` | resume the lane; it keeps its most important papers and moves the rest to `excluded` |

The merge also prints each **thin lane**: one that returned under 60% of its
target, or ran out of search budget. Resume that lane; do not start a new one.

**Adding rows later.** A recovery lane, or the papers found in
[Find missed papers](checks.md#find-missed-papers-phase-6), go in with
`--append FILE --into rows.json`. It never changes an existing row. It refuses an
empty `rows.json`, because a first merge uses `--raw` and `--out`.

## Build a lab corpus (lab mode)

Lab mode starts from a lab's publications instead of a question.

```bash
python3 ../tools/lab_corpus.py --search "Jack Gallant"           # find the OpenAlex id
python3 ../tools/lab_corpus.py --author A5056348548 --out lab_papers.json
python3 ../tools/abstracts.py --rows lab_papers.json --out lab_abstracts.json
```

**L1: ingest.** `lab_corpus.py` pulls a PI's works from OpenAlex. Pass several
`--author` ids to add key lab members, or because one person's record is split
across ids. Every row carries `source: "lab"` and a `built_at` date, so the
reference gates apply from the start. OpenAlex topic tags are too coarse to
classify papers by, so fetch the abstracts too.

**L2: prune (user decision).** Author disambiguation is the main risk in lab mode,
and it fails both ways. OpenAlex merges people with the same name into one id,
which leaves false positives to remove. It also splits one person across ids,
which leaves papers to add, and nothing fails when a record is missing. `--search`
prints each id's year span and ORCID to tell them apart.

**L3: derive themes (user decision).** The agent derives the lab's research themes
from the abstracts, and how their emphasis changed over time. The user approves
them. They are written to `themes.json` as `[{"key", "name", "claim"}]`, and
become the lanes for the rest of the review.

**Check the record by content.** Database tags mislabel papers, so checking agents
read every item. `lab_lane.py` handles the mechanics around them; it needs the
approved themes, because each item is assigned to one:

```bash
python3 ../tools/lab_lane.py --prepare --papers lab_papers.json --abstracts lab_abstracts.json \
        --themes themes.json --pi "Jack L. Gallant"
# dispatch one checking agent per lab_check/input_NN.json, with the brief lab_check/brief.md
python3 ../tools/lab_lane.py --build --papers lab_papers.json --themes themes.json
```

Each agent decides authorship, kind, species, duplicates and theme. A meeting
abstract, erratum or peer-review report is excluded, and of two versions of one
work, the version of record is kept. `--build` writes lane L, the lab's own
papers, to `search_raw/0_L.json`. It refuses an unchecked item, an included
duplicate, an item not by the PI, or a theme not in `themes.json`.

**L4c: place the lab in its field.** This runs the topic-mode search once per
theme, with the same guardrails. The lane spec has a lane per theme, the
antecedent lanes, and `"lab": {"pi": "Jack L. Gallant", "lane": "L"}`. Field lanes
then defer the lab's papers to lane L, so the merge fails on any lab paper the
record lacks: the completeness check that a split author id needs. Lane L's file
sorts first, so a lab paper that a field lane also found keeps its lab row.

The lab's own early work counts as an antecedent. A filter such as "human fMRI
only" must not drop, for example, macaque physiology that predates the lab's
human work; re-enter those papers as lab-sourced. See the
[lab review example](examples.md#a-lab-review).
