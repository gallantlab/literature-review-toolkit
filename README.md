# literature-review-toolkit

Scaffolding to drive a Claude (or other LLM) agent through a structured
literature review for an academic topic — search, verify, download,
xref, and assemble a single annotated `.xlsx` bibliography.

The agent does the judgment work; these scripts handle the API calls,
verification, and bookkeeping that keep the agent honest.

See [`PLAYBOOK.md`](./PLAYBOOK.md) for the procedure. Scripts live in
[`tools/`](./tools).

## What it produces

For each topic batch:
- Rows appended to a single `<your-bibliography>.xlsx` with columns
  `Topic | Ref# | APA reference | Link | Summary | Tag | PDF (local) | Xref`,
  color-coded by origin (white = source-doc, cream = initial search,
  green = cross-citation pass).
- PDFs in `papers/<topic_slug>/<paper_slug>.pdf` for everything the
  auto-downloader could fetch.
- A browser-helper page `papers/<topic_slug>/_download_helper.html` listing
  what's left for the user to grab manually (paywalled / bot-blocked); a
  reconcile script then moves those PDFs into place from `~/Downloads`.
- A cross-citation index `xref_<topic_slug>.json` after Phase 6.

## Setup

```bash
git clone <this-repo>
cd literature-review-toolkit

# Python deps
pip install xlsxwriter
# pdftotext (for tools/reconcile_downloads.py and PDF DOI extraction)
brew install poppler        # macOS; or: apt-get install poppler-utils

# Contact email for NCBI/CrossRef User-Agent (required by verify/xref).
# Either export once:
export LITREVIEW_EMAIL=you@inst.edu
# ...or pass --email to each tool invocation.
```

## Quick start (running it yourself)

```bash
# Phase 2: spawn a literature-search subagent with the prompt at
#          tools/search_prompt_template.md filled in for your topic.
#          The agent returns a list of papers; save as agent_out.json.

# Phase 3: verify everything before trusting any of it.
python3 tools/verify.py --citations agent_out.json --out verify_report.json

# Phase 4: try to auto-download PDFs.
python3 tools/download.py --papers verified.json \
                          --out-dir papers/<topic>/ \
                          --email "$LITREVIEW_EMAIL"

# Phase 4b: for what failed, generate a browser-helper page (see PLAYBOOK
#           for the URL conventions) and reconcile after the user clicks
#           through.
python3 tools/reconcile_downloads.py --manifest papers/<topic>/_manifest.json \
                                     --out-dir papers/<topic>/

# Phase 5: build the xlsx from your accumulated rows JSON.
python3 tools/spreadsheet.py --rows rows.json --out bibliography.xlsx

# Phase 6: cross-citation pass.
python3 tools/xref.py --papers verified.json \
                      --exclude existing_dois.json \
                      --out xref_<topic>.json \
                      --min-cites 4 --resolve-unknown

# Pick green-tier additions from the xref output, repeat Phases 3-5
# for that batch.
```

## Quick start (driving it via Claude Code)

Open Claude Code in a fresh project directory and tell the agent:

```
Read PLAYBOOK.md. We're going to build a bibliography on <topic>.
The source document is at <path>. The spreadsheet should live at
<path>.xlsx. My contact email is <email>.
```

The agent will work through the 7 phases described in the playbook.

## Tools index

| Script | Purpose |
|---|---|
| [`tools/verify.py`](./tools/verify.py) | Verify citations via PMC/PubMed/CrossRef; catches ~25% search-agent fabrications. |
| [`tools/download.py`](./tools/download.py) | Multi-source PDF downloader (arxiv → Unpaywall → EuropePMC). |
| [`tools/xref.py`](./tools/xref.py) | Cross-citation frequency table from CrossRef reference lists. |
| [`tools/spreadsheet.py`](./tools/spreadsheet.py) | Build/rebuild the `.xlsx` from accumulated JSON rows. |
| [`tools/reconcile_downloads.py`](./tools/reconcile_downloads.py) | Move user-downloaded PDFs from `~/Downloads` into the per-topic dir with the right slug. |
| [`tools/search_prompt_template.md`](./tools/search_prompt_template.md) | Prompt template for the literature-search subagent. |

Each is small, standalone, and meant to be read and adapted. They're
scaffolding, not a framework.

## License

MIT — see [`LICENSE`](./LICENSE).
