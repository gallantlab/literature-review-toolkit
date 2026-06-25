# Getting started

## Install

```bash
git clone https://github.com/gallantlab/literature-review-toolkit.git
cd literature-review-toolkit

# Python deps (spreadsheet writer)
pip install xlsxwriter

# Only needed for the opt-in PDF reconciliation in Phase 4:
brew install poppler          # macOS
# or: sudo apt-get install poppler-utils
```

The tools are plain, standalone Python 3 scripts with a tiny dependency
footprint. They are meant to be **read and adapted** — scaffolding, not a
framework.

## Configure your contact email

NCBI and CrossRef ask API callers to identify themselves with a contact email
(it buys you politeness limits instead of throttling). Set it once:

```bash
export LITREVIEW_EMAIL=you@institution.edu
```

…or pass `--email you@institution.edu` to each tool invocation.

??? tip "Optional: a Semantic Scholar API key"
    Citation counts (Phase 5b) query OpenAlex first and Semantic Scholar as a
    cross-check. S2 will rate-limit (HTTP 429) anonymous callers on large
    corpora. If you have a key, export it to avoid the throttle:

    ```bash
    export S2_API_KEY=your-key-here
    ```

## How you'll run it

There are two ways to drive the toolkit. The intended one is to let a Claude Code
agent orchestrate the whole pipeline; the manual path exists for when you don't
have an agent or want to run a single step by hand.

=== "With Claude Code (recommended)"

    Open Claude Code in the directory where you keep your reviews (the
    *bibliography root*) and just describe the review in plain English. The agent
    reads [`PLAYBOOK.md`](https://github.com/gallantlab/literature-review-toolkit/blob/main/PLAYBOOK.md),
    picks a slug, creates a subdirectory, runs the phases, and drops the `.xlsx`
    inside.

    Prompts that work:

    ```text
    i want a literature review on the anatomical connections between the visual
    system and the cerebellum. any anatomy papers from primate or human, using
    any tractography method. go back as far as the 1970s.

    do a fresh lit review on language learning in adults — both L1 and L2,
    behavioral and neuroimaging, last 15 years.

    extend the existing visual_cerebellum review with another 20 papers focused
    on cerebello-thalamic projections.

    now group the world_models bibliography into a few theoretical families,
    and let's iterate on a lineage figure.

    turn the world_models bibliography into a written review article — author it,
    run the priority audit, and render the .docx.
    ```

    The agent confirms scope only when something is genuinely ambiguous, and
    reports when it's done.

    !!! info "Rough cost"
        For ~40 search-added + ~30 cross-citation papers, the no-PDF workflow
        takes roughly **1–2M tokens** and **5–10 minutes** wall-clock. The
        cross-citation pass (Phase 6) is the slowest step.

=== "Manually (no agent)"

    Every phase is a single script you can run yourself. You supply the search
    results (as `rows.json`); the toolkit does the verification and bookkeeping.

    ```bash
    # Pick a topic slug and make a subdir.
    mkdir my_topic && cd my_topic

    # Phase 2 / 2b: run the search agent with tools/search_prompt_template.md
    #   filled in (forward search + a REQUIRED antecedents pass). Save the
    #   returned papers as rows.json — links MUST be DOI URLs.

    # Phase 3: verify everything before trusting any of it.
    python3 ../tools/verify.py --citations rows.json --out verify_report.json

    # Phase 3f: rebuild every reference into canonical APA-7, then gate.
    python3 ../tools/references.py --rows rows.json --out rows.json
    python3 ../tools/references.py --rows rows.json --audit

    # Phase 5: build the xlsx.
    python3 ../tools/spreadsheet.py --rows rows.json --out my_topic_bibliography.xlsx

    # Phase 5b: citation counts (attach to rows, rerun spreadsheet.py).
    python3 ../tools/citations.py --rows rows.json --out citation_counts.json

    # Phase 6: cross-citation pass; pick additions; repeat 3 + 5 for the batch.
    python3 ../tools/xref.py --papers verified.json --exclude existing_dois.json \
                             --out xref_my_topic.json --min-cites 4 --resolve-unknown
    ```

    The optional Phases 6b (families + figure) and 7 (review article) are on the
    [Phases in detail](phases.md) page. PDF download (Phase 4) is opt-in.

## Where things land

Each review lives in **its own subdirectory** under your bibliography root. The
JSON files are the source of truth; the `.xlsx` is rendered from them.

```text
<bibliography_root>/
├── literature-review-toolkit/         <- this repo, cloned once
├── visual_cerebellum/                 <- one review topic, one subdir
│   ├── visual_cerebellum_bibliography.xlsx   <-- THE DELIVERABLE
│   ├── topic_definition.md            (scope you & the agent agreed on)
│   ├── rows.json                      (the LIVE table — everything renders from it)
│   ├── verify_report.json             (Phase 3: OK / MISMATCH / NOT-FOUND per cite)
│   ├── citation_counts.json           (Phase 5b: OpenAlex + S2 counts, cached)
│   ├── xref_visual_cerebellum.json    (Phase 6: cross-citation frequency table)
│   ├── families.json / families.md    (Phase 6b: grouping, if run)
│   ├── visual_cerebellum_families.html (Phase 6b: interactive figure; +svg/png/pdf)
│   ├── content.json                   (Phase 7: authored prose, if run)
│   └── Visual_Cerebellum_review.docx  (Phase 7: AI-authored review, if run)
└── attention/                         <- a different topic, separate subdir
    └── attention_bibliography.xlsx
```

!!! warning "After Phase 3f, `rows.json` is the live table"
    Edit `rows.json` directly for any later change. Re-running an upstream
    row-emitter is **destructive** — it wipes the canonical references and the
    citation counts. To share results, send the `.xlsx` (or the `.docx`). To
    extend or re-run later, the JSON files are what the toolkit reads from.
