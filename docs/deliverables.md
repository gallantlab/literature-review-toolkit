# Deliverables

This page covers what a review produces: the families and the timeline, the
spreadsheet, PDFs, the written review, and the hand-off. Commands run in the
project folder and reach the scripts as `../tools/`
([Where files live](pipeline.md#where-files-live)). For what the user sees, see
[Step 7 of the tutorial](tutorial.md#step-7-read-the-results).

---

## Families and the timeline (Phase 6b)

The timeline is usually the most useful thing a review produces, so the agent
offers it on every review without being asked. It is drawn from families. A
**family** groups papers by what they are for: the theoretical claim they
support. It is independent of the Topic column, which records method or
sub-area. A good family unites papers that read differently, and splits papers
that read alike.

```bash
# 1. propose: the agent reads the corpus and proposes a grouping
python3 ../tools/families.py --rows rows.json --digest

# 2. pitch: the agent offers the timeline and shows the family definitions;
#    the user accepts them, changes them, or skips the timeline

# 3. assign (agents briefed from tools/family_prompt_template.md), validate and stamp
python3 ../tools/families.py --rows rows.json --assign families_input.json \
        --results 'families_batches/result_*.json' --out families.json

# 4. render the timeline
python3 ../tools/families_figure.py --rows rows.json --families families.json \
        --out-prefix <topic>_families --title "<Topic> — theoretical families"
```

**Step 2 is the only stop.** Editing six definitions costs nothing; reassigning
300 papers does not. If the user skips the timeline, the phase ends there, with no
`Family` column and no timeline. Otherwise steps 3 and 4 run without stopping.

**What `families.py` checks.** Every paper belongs to exactly one family, and
there are 2–9 families (3–8 recommended). It stops on an unassigned paper, a row
not in `rows.json`, or an unknown or duplicate family key. It warns when one
family holds more than 60% of the papers, or has a single member.

**Read the hard calls before rendering.** The assignment agents do not argue with
the definitions. Instead, they record each **hard call**, a paper that fits its
family badly or fits two about equally, in the assignment's `hard_calls` field.
`families.py` prints them, and warns when the field is missing. A wrong family
definition shows up only there.

**Write each family's `claim` and `lineage` for a reader who sees nothing else.**
Readers open the timeline, not `families.md`. The timeline shows the full text
when the reader hovers a lane name, and truncates the copy drawn beside the lane.
Build lineages from papers already in `rows.json`, with the canonical surname and
year. A lineage recalled from memory can be wrong in the same ways a citation can.

!!! danger "Do not cluster embeddings to make families"
    Clustering finds surface similarity, not shared theory. An agent proposes the
    families from the corpus, the user approves the definitions, and
    `families.py` validates the assignment.

### How the timeline draws

**The render.** The defaults are the standard settings. Dots are sized by citation
count, and `internal_citations.json` is read from beside `rows.json`. The exact
arguments are written to `figure_render_args.txt` if that file does not exist. An
existing file holds tuning notes, so it is never overwritten, and the script says
when a render is not recorded there. The `.html` file is self-contained: no
network and no dependencies.

**Dot size.** By default (`--size-by-citations sqrt`), dot area is proportional to
citation count. Counts span four orders of magnitude, so the scale tops out at
the 95th percentile and clamps anything above it; otherwise one classic would
shrink every other dot. `log` makes most dots look alike, and `none` draws them
all the same size. A paper with no count is drawn hollow, not as zero. Citation
count also depends on age, so recent papers draw small. Say so when presenting the
timeline.

**Landmarks.** Selection is automatic; do not hand-build a label overlay. A paper
is a landmark if it is among its family's `--per-family` most cited, if at least
`--motif-min` corpus papers cite it (from `internal_citations.json`), or if it is
a home-lab paper. Landmarks are drawn solid and labeled; other dots are faded.
Solid is a yes-or-no flag, not a score, so a small solid dot is a lightly cited
paper that qualified another way. A key under the year axis names the rules this
render used. Each run prints how many labels the cap dropped. Only arrows and
notes are editorial (`--spec`); a `labels` map there replaces the automatic choice.

**Home-lab papers.** Starring is off by default, so the toolkit stays neutral.
Turn it on with `--lab-author Surname` (repeatable) or `LITREVIEW_LAB_AUTHOR`.
Rows with `source == "lab"`, which lab mode produces, are always starred.
`--lab-color` sets the ring color. The default gold matches the fifth family's
lane color, so when they would collide, the timeline picks another color and says
so.

**Shapes.** `--shape-by FIELD --square-if V1,V2` draws a paper as a square when its
field holds a listed value (case-insensitive), and `--triangle-if V3` adds a
third shape. `--shape-legend "circle text|square text|triangle text"` sets the
key, which sits under the subtitle.

### Tune the timeline for a large corpus

The label defaults (`--motif-min 3`, `--max-labels 28`) suit a 50-paper review.
For 110–650 papers, retune for each corpus, and read the list of dropped labels,
not only its length.

| Flag | Effect |
|---|---|
| `--time-warp 0.85` | a density-equalizing year axis: compresses sparse early decades and expands dense recent years |
| `--min-year 1909` | clamps the axis start; older papers pin to the left edge |
| `--motif-min N` | a paper cited by at least N corpus papers is a landmark |
| `--max-labels N` | caps the total labels; set it above the qualifying set so it never binds |
| `--per-family N` | labels the N most-cited papers in each family (default 4) |
| `--emphasize-source lab` | draws every row from one source as a large dot |
| `--lab-author Surname` | rings and stars the home lab's papers (repeatable; off by default) |
| `--lab-color '#c1121f'` | sets the ring color; quote it, or the shell reads `#` as a comment |
| `--spec figure_spec.json` | editorial overlay: manual labels, arrows, notes, lane order |
| `--shape-by`, `--square-if`, `--triangle-if`, `--shape-legend` | draws papers in up to three shapes by a field's value |
| `--xlsx <file>` | embeds the spreadsheet, with a download button |

!!! warning "Raising a threshold can remove a label already shown"
    A higher `--motif-min` shrinks the pool of qualifying papers, not only the
    cap. Compare the label sets before and after, and choose the highest
    threshold that removes nothing.

## Build the spreadsheet (Phase 5)

```bash
python3 ../tools/spreadsheet.py --rows rows.json --out <topic>_bibliography.xlsx
```

The spreadsheet is the core deliverable and the release gate
([rule 9](pipeline.md#the-rules)). `spreadsheet.py` runs the same audit as
`references.py --audit`: verify stamps, hand checks, summary checks, the candidate
ledger and acknowledged warnings. It refuses to write a failing gated table.

- **`--draft`** writes a failing table anyway, as `<out>_DRAFT.xlsx`, with a red
  banner naming the failure count. Never hand it off as the deliverable.
- **A legacy table** is written despite its findings, with the findings printed
  ([What switches the gates on](reruns.md#what-switches-the-gates-on)).
- **A malformed `candidates.json`** is refused on any table, draft or not.

**Columns.** `Topic · Ref # · APA reference · Link · Summary · Tag · Family ·
Cite (OpenAlex) · Cite (S2) · Verify note · Summary checked against · PDF (local) ·
Xref`. The `Family`, `Cite`, `Verify note` and `Summary checked against` columns
appear once any row carries them. `Link` is always the bare DOI URL. `Summary
checked against` names the abstract's source, or says "no abstract".
`--column FIELD=HEADER` (repeatable) adds a project field as a column after
`Family`, such as the field a timeline's `--shape-by` reads. A list value is
joined with `; `, and a field that already has its own column is refused.

**Row colors** record where each paper came from: white for a paper cited in a
source document, cream for the search, purple for the antecedent search, green
for the missed-paper step, and blue for the lab's own papers. An unknown source
renders white, with a warning.

**The "Considered and excluded" sheet** lists every paper that was looked at and
set aside, with its DOI, title, year, first author, who found it and the reason.
It holds the candidates excluded in the ledger and the lanes' exclusions that no
lane kept.

## Download PDFs (Phase 4)

PDFs are downloaded only when the user asks. `download.py` tries arXiv, then
Unpaywall, then Europe PMC, keeps a file only when its bytes are a PDF, and lists
the failures for manual download. `reconcile_downloads.py` files the PDFs
downloaded by hand. It matches a file name to a DOI first, then the author, year
and title on the first page. It leaves any file it is unsure of in place, and
never overwrites a PDF already filed.

## Write the review (Phase 7)

```bash
# write the prose into content.json, after the priority audit
python3 ../tools/cite_check.py --rows rows.json --content content.json   # the gate
python3 ../tools/review_paper.py --rows rows.json --content content.json \
        --figure <topic>_families.png --out <topic>_review.docx
```

The agent writes the prose; it is the user's decision whether to have one. Three
safeguards apply:

- **The priority audit.** Before rendering, an independent pass checks that every
  claim of origin cites the earliest paper that earned it, not whichever reference
  fits the sentence. On one 396-paper review it found five such inversions and
  four factual errors.
- **The citation gate.** `cite_check.py` exits 1 if any in-text citation does not
  match a row in `rows.json`. If one author and year match two rows, name more
  authors (APA-7 §8.19).
- **The reference list comes from the table.** `review_paper.py` builds it from
  `rows.json` with `reference_list(rows)`, in APA-7 order, so it cannot drift from
  the checked corpus. An HTML page should reuse that function.

A review written by an AI states its author and how it was checked, once, in the
masthead.

### Make the prose readable

First drafts are accurate but compressed: four or five findings chained through
semicolons into one sentence of 60–120 words. `cite_check.py` cannot see this,
because every citation resolves. `prose_audit.py` measures it.

```bash
cp build_review_page.py /tmp/before.py      # keep the pre-revision copy outside the project
python3 ../tools/prose_audit.py --page build_review_page.py
#   ... rewrite the sentences it lists ...
python3 ../tools/prose_audit.py --page build_review_page.py --baseline /tmp/before.py
```

The tool reads a review page script (`--page`, with `[[REF]]` markers) or a
`content.json` (`--content`, with APA author-date citations). It reports words,
mean sentence length and long sentences for each block (`--long`, default 45
words). Aim for a mean near 24 words, with almost nothing over 50; first drafts
typically average 31. To fix a listed sentence, give each finding its own
sentence.

- **`--baseline` is a gate.** Splitting sentences is how a reference silently
  drops out of the works cited. The flag compares the cited references before and
  after, and exits 1 on any loss.
- **It flags arguments made twice.** It reports pairs of blocks that share eight
  or more citations. Before merging two such sections, confirm that every
  reference in the removed one is cited elsewhere.

Long sentences are reported, not gated: a sentence that lists things can
legitimately run long.

### The review web page

The `.docx` is the manuscript. The readable deliverable is a self-contained HTML
page, built by a project script, `build_review_page.py`, from the same
`rows.json`. It carries:

1. the **numbered works cited**, which resolve the in-text citations;
2. the **interactive timeline** (`<topic>_families.html`) in an iframe. It doubles
   as the corpus browser: clicking a paper shows its reference, family, topic,
   DOI, summary and citation counts.

Do not add a second reference browser; the timeline's panel already shows
everything it would.

For a corpus with no timeline, `bib_viewer.py` renders a searchable bibliography
grouped by family, with a note on who wrote the summaries and that they come from
abstracts:

```bash
python3 ../tools/bib_viewer.py --rows rows.json --families families.json \
        --out corpus_viewer.html --title "<Topic>" \
        --author "<model>" --author-note "<what the model is>"
```

The viewer can also be embedded in a page (`bib_viewer.render()`, with
`bib_viewer.CSS` and `bib_viewer.JS`). Pass `provenance=False` where the masthead
already carries the disclosure. Without `--author`, the page carries no note, and
the tool warns.

!!! tip "Test interactive pages by running them"
    `node ../tools/checks/verify_bib_filter.mjs <page>.html` runs the viewer's
    filter against a stub page and checks what is visible. The same folder holds
    `verify_hover.mjs` (the timeline's lane hover) and `verify_nav_order.mjs` (its
    Next and Prev order). They need Node.js and no browser.

## Hand off (Phase 8)

Deliver the spreadsheet and the timeline (or note that the timeline was skipped),
plus the written review if there is one. Report the scale, the number of rows from
each source, the verification corrections made, and any step run with
`--allow-incomplete`. **Keep the JSON files with the deliverables.** They are the
audit trail and the input to any later rerun.
