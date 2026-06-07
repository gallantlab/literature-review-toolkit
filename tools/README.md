# Literature review helper scripts

Topic-agnostic helpers used by `PLAYBOOK.md`. Each is standalone, takes
JSON input, outputs JSON / files. Read the playbook first for workflow
context; these are scaffolding, not a framework.

NCBI and CrossRef expect a contact email in the User-Agent. Pass
`--email you@inst.edu` to each tool, or export `LITREVIEW_EMAIL` once.

## `verify.py` — verify citations

Catches the ~25% of search-agent citations that have wrong authors, wrong
years, or are fabricated. Run before adding anything to the spreadsheet.

```
python3 tools/verify.py --citations cits.json --out report.json --email you@inst.edu
```

`cits.json` per item: `{label, pmcid?, pmid?, doi?, title?,
expect_first_author?, expect_year?}`. Looks up via PMC, then PubMed, then
CrossRef, then title-search. Verdict per item: `OK`, `MISMATCH`, `NOT-FOUND`.

## `download.py` — multi-source PDF downloader **(opt-in, Phase 4)**

PDF acquisition is **not** part of the default workflow. Run only when the
user explicitly asks. A dedicated replacement is planned.

Tries arxiv → Unpaywall (non-PMC URLs first) → EuropePMC. Validates `%PDF`
magic bytes. Skips known-blocked hosts (PMC direct, biorxiv, PNAS, OUP,
MIT Press, Wiley, Cell). Routes failures to a manual-followup file.

```
python3 tools/download.py --papers list.json --out-dir papers/topic_X/ \
                          --email you@example.edu \
                          --manual-list papers/topic_X/_needs_manual.txt
```

`list.json` per item: `{slug, doi?, arxiv?, pmcid?}`.

## `xref.py` — cross-citation analysis

For each input paper with a DOI, fetches the reference list via CrossRef.
Builds a frequency table of cited DOIs. Resolves unknown DOIs to titles
(slow, opt in with `--resolve-unknown`). Use to find high-impact papers
the initial search missed.

```
python3 tools/xref.py --papers list.json --out xref.json \
                      --exclude existing_dois.json \
                      --min-cites 4 --resolve-unknown \
                      --email you@inst.edu
```

`list.json` per item: `{slug, doi?, pdf?}`. PDF fallback uses `pdftotext`
to extract DOIs from the references section — install poppler if missing.

## `citations.py` — per-paper citation counts (Phase 5b)

Fetches citation counts by DOI from **OpenAlex** (primary; free, reliable,
batchable) and **Semantic Scholar** (secondary; best-effort, rate-limits
without `S2_API_KEY`). Google Scholar is deliberately not used — it has no API
and CAPTCHA-blocks bots, so it can't be queried for a whole bibliography.
Reads any rows JSON (DOI from a `doi` field or a `https://doi.org/...` link);
arXiv DOIs are auto-mapped to the arXiv id for S2.

```
python3 tools/citations.py --rows rows.json --out citation_counts.json \
                           --email you@inst.edu --asof 2026-06-07
```

Attach the counts to rows as `cite_openalex` / `cite_s2`, then rebuild — the
spreadsheet auto-adds the two `Cite` columns.

## `spreadsheet.py` — build the xlsx

Reads a JSON of accumulated rows and writes the xlsx with the standard
schema and color coding (white = source-doc, cream = search, green = xref).
If any row carries `cite_openalex`/`cite_s2`, two `Cite` columns are added
automatically after `Tag`. Always rebuild from the full JSON; xlsxwriter is
write-only.

```
python3 tools/spreadsheet.py --rows rows.json --out bibliography.xlsx
```

`rows.json` per item: `{topic, ref, apa, link, summary, tag, pdf, xref,
source}`. `link` is always a DOI URL (`https://doi.org/<doi>`); `pdf` is
empty unless Phase 4 was opted into.

## `reconcile_downloads.py` — match manually-downloaded PDFs **(opt-in, Phase 4)**

Companion to `download.py`. PDF acquisition is not run by default.

After the user clicks through the browser-helper page to grab paywalled
or bot-blocked papers, this script reads each PDF in `~/Downloads` (or
`--downloads-dir`), matches by filename↔DOI substring + author/year/title
overlap from a manifest, and moves the PDF into the topic dir with the
correct slug filename. Refuses to move when uncertain — better to skip
than misfile.

```
python3 tools/reconcile_downloads.py --manifest papers/topic/_manifest.json \
                                     --out-dir papers/topic/
```

Manifest format: list of `{slug, title, first_author, year, doi}`.
Requires `pdftotext` (`brew install poppler` on macOS).

## `search_prompt_template.md`

Prompt template to fill in and pass to the search subagent (Phase 2).
See the playbook for what to put in each `{PLACEHOLDER}`.

---

## Idiomatic usage

```bash
# Phase 2: spawn agent (fill in search_prompt_template.md). Agent returns
#          a list of papers with DOI links (https://doi.org/<doi>).

export LITREVIEW_EMAIL=you@inst.edu     # set once for verify.py + xref.py

# Phase 3: verify what the agent gave you
python3 tools/verify.py --citations agent_output_to_verify.json --out verify_report.json

# Phase 5: build the spreadsheet
python3 tools/spreadsheet.py --rows accumulated_rows.json --out bibliography.xlsx

# Phase 6: cross-citation analysis
python3 tools/xref.py --papers all_papers_with_dois.json \
                      --exclude existing_spreadsheet_dois.json \
                      --out xref_$TOPIC.json \
                      --min-cites 4 --resolve-unknown

# ... pick from xref_$TOPIC.json, write summaries, repeat 3+5 ...

# --- OPTIONAL: Phase 4 (PDF download), only if user has asked for PDFs ---
# python3 tools/download.py --papers verified_papers.json \
#                           --out-dir papers/$TOPIC/ \
#                           --email $LITREVIEW_EMAIL
# python3 tools/reconcile_downloads.py --manifest papers/$TOPIC/_manifest.json \
#                                      --out-dir papers/$TOPIC/
```
