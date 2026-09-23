# Maintaining this site

Notes for whoever edits these docs next, human or agent.

!!! warning "Change the docs in the same commit as the toolkit"
    This site covers everything in `README.md` and `PLAYBOOK.md`. When you add or
    rename a tool, change a phase, a command or a flag, or add a guardrail,
    update the affected page under `docs/` in the same change. `docs/manual.md`
    drifts fastest: it holds the phase commands, the guardrails and the pipeline
    diagram.

## The generated tool index

The index in `docs/tools.md`, `tools/README.md` and `PLAYBOOK.md` is generated
from the modules (docstring, `PHASE` constant, `--help` flags) by
`python3 tools/gen_docs.py`. Run it after adding a tool or flag. Only the text
around the index is hand-written.

## Checks

`.github/workflows/tests.yml` runs three checks on every push and pull request.
Run them locally before pushing:

```bash
ruff check .                              # config in pyproject.toml
python3 tools/tests/test_formatting.py    # each case is a defect that once shipped
python3 tools/gen_docs.py --check         # fails if a tool index is stale
```

## Build and deploy

- **Engine:** MkDocs with the Material theme. Config:
  [`mkdocs.yml`](https://github.com/gallantlab/literature-review-toolkit/blob/main/mkdocs.yml).
  Content: `docs/`.
- **Deploy:**
  [`.github/workflows/docs.yml`](https://github.com/gallantlab/literature-review-toolkit/blob/main/.github/workflows/docs.yml)
  runs on every push to `main` that touches `docs/**`, `mkdocs.yml` or the
  workflow. It runs `mkdocs build --strict`, which fails on a broken link or
  missing file, and publishes to GitHub Pages. The repo must stay public for
  free Pages hosting.
- **URL:** <https://gallantlab.org/literature-review-toolkit/>. The `gallantlab`
  org serves Pages under its custom domain, so `site_url` is `gallantlab.org`,
  not `github.io`. Do not change it.

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
| `assets/figures/lineage_*.png` | `families_figure.py` output from each review directory |
| `assets/figures/lab_*.png` | the `gallant_lab` trajectory and in-context figures |
| `assets/examples/example_review_*.png` | pages of a review `.docx`, rendered with LibreOffice → PDF → `pdftoppm` and trimmed with ImageMagick |

To refresh the review pages, render the `.docx` with `review_paper.py`, then:

```bash
/Applications/LibreOffice.app/Contents/MacOS/soffice --headless --convert-to pdf review.docx
pdftoppm -r 150 -png -f 1 -l 1 review.pdf page       # and the "References" page
magick page-01.png -trim -bordercolor white -border 20 -resize 1000x example_review_title.png
```

On macOS, `soffice` is not on `PATH`, and it hangs inside a sandbox that blocks
macOS system services. To refresh any figure, overwrite the file in place; the
Markdown references the filenames. When a figure changes, check its caption:
captions state paper counts, dates and findings read off the figure.

## The spreadsheet preview

The bibliography table in the [manual](manual.md#71-the-spreadsheet) is HTML, not
a screenshot. It lives in `docs/_includes/bib_table.html` and is pulled in with
`--8<-- "docs/_includes/bib_table.html"`; `exclude_docs` in `mkdocs.yml` keeps
the partial from being published on its own. To regenerate it, write a
`<table class="bib-preview">` from a real `rows.json`, with rows classed
`row-search`, `row-xref` or `row-source` (colors in
`docs/stylesheets/extra.css`).
