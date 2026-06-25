# Maintaining this site

Notes for whoever edits the docs next — human or agent.

!!! warning "Keep the docs in sync with the toolkit"
    This site is a **superset of `README.md` + `PLAYBOOK.md`**, not a fork. When
    you change the toolkit — add/rename a tool, change a phase, alter a command or
    flag, add a guardrail/lesson — **update the affected page under `docs/` in the
    same change.** The pages that drift fastest:

    - `docs/phases.md` — phase commands and guardrails
    - `docs/tools.md` — the tool tables (one row per script in `tools/`)
    - `docs/pipeline.md` — the Mermaid flow and the phases-at-a-glance line

## How it's built and deployed

- **Engine:** MkDocs + Material. Config: [`mkdocs.yml`](https://github.com/gallantlab/literature-review-toolkit/blob/main/mkdocs.yml). Content: `docs/`.
- **Deploy:** [`.github/workflows/docs.yml`](https://github.com/gallantlab/literature-review-toolkit/blob/main/.github/workflows/docs.yml)
  runs on every push to `main` that touches `docs/**`, `mkdocs.yml`, or the
  workflow. It runs `mkdocs build --strict` (a broken link or missing file
  **fails the build**) and publishes to GitHub Pages.
- **Live URL:** <https://gallantlab.org/literature-review-toolkit/> — the
  `gallantlab` org serves project Pages under its **custom domain**, so
  `site_url` in `mkdocs.yml` is `gallantlab.org`, **not** `github.io`. Don't
  "correct" it back.
- **Repo is public** — that's what lets free GitHub Pages serve it.

## Preview locally

```bash
pip install -r docs/requirements.txt
mkdocs serve            # http://127.0.0.1:8000, live-reload
mkdocs build --strict   # what CI runs; fix anything it flags before pushing
```

## Where the figures come from

All example figures are **real outputs from actual reviews**, copied into
`docs/assets/`:

- `assets/figures/lineage_*.png` — families figures (`families_figure.py` output)
  from various review subdirectories.
- `assets/figures/lab_*.png` — the `gallant_lab` lab-mode trajectory + in-context
  figures.
- `assets/examples/example_review_*.png` — pages of a review `.docx`, rendered via
  LibreOffice → PDF → `pdftoppm`, then trimmed with ImageMagick.

To refresh them, re-copy the source PNG (or re-render the `.docx`/`.xlsx`) and
overwrite the file in `docs/assets/` — the filenames are referenced from the
Markdown, so keep them stable.

## The spreadsheet preview table

The colour-coded bibliography table on the [Phases](phases.md#phase-5-build-the-spreadsheet)
page is **not** a screenshot — it's HTML generated from a real `rows.json` and
pulled in as a snippet (`--8<-- "docs/_includes/bib_table.html"`). To regenerate
it from a different review, build an HTML `<table class="bib-preview">` with rows
classed `row-search` / `row-xref` / `row-source` (the colour classes live in
`docs/stylesheets/extra.css`) and overwrite `docs/_includes/bib_table.html`. That
partial is excluded from the published site via `exclude_docs` in `mkdocs.yml`.
