# Maintaining the docs

This page is for whoever edits the toolkit or this site next, person or agent.
It covers the site's structure, the style every page follows, the checks, and
how the site is built.

!!! warning "Change the docs in the same commit as the code"
    When you add or rename a tool, change a phase, a command or a flag, or add a
    guardrail, update the affected page in the same commit. The pages under
    **How it works** drift fastest, because they hold every command and gate.

## Two audiences, two parts

The site serves two groups of readers, and each page belongs to one of them.

| Part | Pages | Reader | What the pages contain |
|---|---|---|---|
| **Using the toolkit** | Home, Tutorial, Example requests, Example results | Someone who wants a literature review and may never open a terminal again | What to ask, what the agent asks back, the decisions that are theirs, how to read the results |
| **How it works** | Overview, Searching, Checking, Deliverables, Reruns and upgrades, Troubleshooting, Tools reference, Maintaining the docs | A developer who runs phases by hand, changes a tool, or writes a new one | Every procedure, command, gate and file |

Keep the parts separate:

- **User pages carry no internals.** No flags, field names, file formats or
  phase numbers, beyond the setup commands in the tutorial. Say what the agent
  does and what the user decides.
- **User pages link to developer pages for detail; they never copy it.** A fact
  lives on one page.
- **Developer pages describe the procedure the agent follows.** They mirror
  [`PLAYBOOK.md`](https://github.com/gallantlab/literature-review-toolkit/blob/main/PLAYBOOK.md)
  and add the reasons behind each gate.

## Style guide

### Writing

- **Write US English.** Judgment, behavior, catalog, labeled, analyze.
- **Use the present tense and the active voice.** "Canon rebuilds the
  reference", not "the reference will be rebuilt".
- **Keep sentences short.** Aim for under 25 words, one idea per sentence. Do not
  chain clauses with semicolons.
- **Inform; do not sell.** This is documentation for a research tool. No
  promotional stat strips, slogans or marketing claims. State what the toolkit
  does and what it checks, plainly.
- **Keep one review's numbers with that review.** Describe what the toolkit
  produces in general terms ("one row per paper"). A count from an example
  ("587 papers") appears only where the text says which review it describes, so
  no reader takes it for what every review returns.
- **Describe current behavior only.** History, dated incidents and old versions
  belong in commit messages. A measured number may stay when it is the reason
  for a rule ("without the duty, about 1 in 4 citations were wrong").
- **Address the reader as "you".** On user pages, "you" is the person who wants
  the review. On developer pages, it is whoever runs the procedure, agent or
  person. The model that runs a review is always "the agent".

### Terms

Use one word for each thing, everywhere.

| Use | For | Not |
|---|---|---|
| review | the whole project, from request to hand-off | build, run, search (except for the search step) |
| corpus | the set of papers a review collects | bibliography, table (except `rows.json`) |
| request | what the user asks for | prompt, query |
| lane | on the timeline, one family's horizontal band; on developer pages, also one search agent's slice of the topic ("search lane" where both could be meant) | |
| family | a group of papers that share a theoretical claim | category, cluster |
| timeline | the interactive figure of families over time | lineage figure, chart, graph |
| spreadsheet | the `.xlsx` deliverable | workbook, bibliography |
| written review | the optional prose review | review article, review paper |
| project folder | one review's folder | subdirectory, review directory |
| canon | rebuilding a reference from its DOI | canonicalization (after first use) |
| gate | a check that stops the review on failure | |

### Formatting

- **Headings use sentence case.** The page title is the only `#` heading.
- **Tutorial steps are numbered** ("Step 3. Describe the review"). Nothing else
  is numbered in a heading.
- **A developer section that covers one phase ends with the phase in
  parentheses**: "Verify every citation (Phase 3)". Phase numbers come from
  `PLAYBOOK.md` and the tools' `PHASE` constants; never renumber them in the docs.
- **Every procedure section has the same order.** One sentence on its purpose,
  the commands, what the step does, what makes it fail, then at most one
  admonition.
- **Bold lead-ins end with a period**: "**The verify stamp.** With `--rows`, ..."
- **Commands** go in `bash` blocks. Commands run from the project folder and call
  `python3 ../tools/<tool>.py`. Placeholders look like `<topic>`. File names,
  flags, fields and values go in backticks.
- **Tables** always have a header row. Cells hold phrases, with no final period.
- **Admonitions** always have a title. Use `note` for background, `tip` for
  optional advice, `warning` for a mistake that fails silently, and `danger` for
  one that loses data.
- **Figures** use `<figure class="fig">`. The caption starts with a bold sentence
  that says what the figure shows, followed by at most two sentences. The alt
  text describes the image.
- **Links** name their target by its title, never by a section number:
  "[Verify every citation](checks.md#verify-every-citation-phase-3)".
- **Icons** use Material shortcodes such as `:material-table-large:`, which the
  `pymdownx.emoji` extension in `mkdocs.yml` turns into SVG icons. Use them only
  in card headings (the home page and the tutorial's "What you'll get"), as
  the heading's first item.
- **No `---` rules between sections.** Every `##` heading already draws a
  divider above it (`docs/stylesheets/extra.css`), so a rule doubles it.
- **Check the look, not only the build.** After a change to the home page or the
  stylesheet, screenshot the built site in light mode, dark mode and at phone
  width.
- **Numbers** are numerals. Ranges take an en dash (1970–2026). Write "about",
  not "~".

## The generated tool index and version

`python3 tools/gen_docs.py` generates the tool index in `docs/tools.md`,
`tools/README.md` and `PLAYBOOK.md` from the modules: each one's docstring,
`PHASE` constant and `--help` flags. Only the text around the index is written
by hand. The same run writes the current version number into the files that state
it: `README.md`, `docs/index.md`, `mkdocs.yml`, the skill and the two plugin
manifests. Run it last, after every other edit, with everything you intend to
commit.

## The AI disclosure

The home page's "AI disclosure" section states that the toolkit and these docs
were written largely by Claude, and that what the toolkit produces is
AI-generated. The site footer (`copyright` in `mkdocs.yml`) links to it, and the
README carries a short version. Keep all three.

## Checks

`.github/workflows/tests.yml` runs three checks on every push to `main` and every
pull request. Run them locally before pushing (`pip install ruff` first):

```bash
ruff check .                              # config in pyproject.toml
python3 tools/tests/test_formatting.py    # each case is a defect that once shipped
python3 tools/gen_docs.py --check         # fails if the tool index or a version stamp is stale
```

CI does not test the interactive pages. After a change to the timeline
(`families_figure.py`) or the bibliography viewer (`bib_viewer.py`), run the
Node.js checkers in `tools/checks/` on a rendered page. Each one runs the page's
own code, because these bugs have survived reading the source:

```bash
node tools/checks/verify_hover.mjs <figure>.html        # the family hover panels
node tools/checks/verify_nav_order.mjs <figure>.html    # the Prev/Next order
node tools/checks/verify_bib_filter.mjs <page>.html     # the viewer's filter
```

## Build and deploy

- **Engine.** MkDocs with the Material theme. The config is
  [`mkdocs.yml`](https://github.com/gallantlab/literature-review-toolkit/blob/main/mkdocs.yml),
  and the content is `docs/`.
- **Deploy.**
  [`.github/workflows/docs.yml`](https://github.com/gallantlab/literature-review-toolkit/blob/main/.github/workflows/docs.yml)
  runs on every push to `main` that touches `docs/**`, `mkdocs.yml` or the
  workflow. It runs `mkdocs build --strict`, which fails on a broken link, a
  missing anchor or a missing file, and publishes to GitHub Pages. The repo must
  stay public for free Pages hosting.
- **URL.** <https://gallantlab.org/literature-review-toolkit/>. The `gallantlab`
  organization serves Pages under its custom domain, so `site_url` is
  `gallantlab.org`, not `github.io`. Do not change it.
- **Old links.** `manual.md` is a stub, kept out of the navigation, that sends
  readers of the old single-page manual to the new pages. Keep it.

**Confirm the deploy after every push.** A local build reads files that git may
never send: `.gitignore` excludes `*.xlsx`, for example, except under
`docs/assets/examples/`. Check that the run succeeded, and that the live page
shows the change:

```bash
gh run list --workflow docs.yml --limit 3
```

Preview locally:

```bash
pip install -r docs/requirements.txt
mkdocs serve            # http://127.0.0.1:8000, live reload
mkdocs build --strict   # what CI runs
```

## Figures

Every figure is real output from a finished review, copied into `docs/assets/`:

| File | Source |
|---|---|
| `assets/figures/lineage_*.png` | `families_figure.py` output from each project folder |
| `assets/figures/lineage_microtesla.png` | a docs-only re-render of the microtesla timeline, with the label that named the company shortened to "Canori 2026"; the project's own figure is unchanged |
| `assets/figures/plot_diagnostic_accuracy.png` | a screenshot of the top of the diagnostic-accuracy review's `accuracy_by_disorder.html` |
| `assets/figures/lab_*.png` | the `gallant_lab` trajectory and in-context timelines |
| `assets/examples/creatine/` | the creatine review's real spreadsheet, timeline and written review, copied unchanged from its project folder, plus a preview screenshot of each. The home page shows the previews, labeled as examples, with general captions and no links; the Example results page links the three files under the creatine timeline |
| `assets/examples/example_review_*.png` | pages of a written review `.docx`, rendered with LibreOffice, then `pdftoppm`, and trimmed with ImageMagick |

To refresh the written-review pages, render the `.docx` with `review_paper.py`,
then:

```bash
/Applications/LibreOffice.app/Contents/MacOS/soffice --headless --convert-to pdf review.docx
pdftoppm -r 150 -png -f 1 -l 1 -singlefile review.pdf page   # page.png; repeat for the "References" page
magick page.png -trim -bordercolor white -border 20 -resize 1000x example_review_title.png
```

On macOS, `soffice` is not on `PATH`, and it hangs inside a sandbox that blocks
macOS system services. To refresh a figure, overwrite the file in place, because
the pages refer to the file names. When a figure changes, check its caption:
captions state paper counts, dates and findings read off the figure.

Before adding a figure, read its labels. A timeline labels landmark papers by
author and sometimes adds notes, which can name a company or a person the page
should not.

## The spreadsheet preview

The spreadsheet preview in the [tutorial](tutorial.md#step-7-read-the-results) is
HTML, not a screenshot. It lives in `docs/_includes/bib_table.html` and is pulled
in with `--8<-- "docs/_includes/bib_table.html"`. The `exclude_docs` setting in
`mkdocs.yml` keeps the partial from being published on its own. To regenerate it,
write a `<table class="bib-preview">` from a real `rows.json`, with rows classed
`row-search`, `row-xref` or `row-source` (colors in
`docs/stylesheets/extra.css`).
