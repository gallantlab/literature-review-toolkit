# Literature review helper scripts

Topic-agnostic helpers used by `PLAYBOOK.md`. Each is standalone, takes
JSON input, outputs JSON / files. Read the playbook first for workflow
context; these are scaffolding, not a framework.

NCBI and CrossRef expect a contact email in the User-Agent. Pass
`--email you@inst.edu` to each tool, or export `LITREVIEW_EMAIL` once.

## Index

Generated from the modules (docstring, `PHASE` constant, `--help`) by
`python3 tools/gen_docs.py`; the same block is in `docs/tools.md` and
`PLAYBOOK.md`, and CI fails if any copy is stale. Details per tool follow.

<!-- BEGIN GENERATED TOOL INDEX (python3 tools/gen_docs.py — do not edit by hand) -->
| Script | Phase | Purpose | Flags |
|---|---|---|---|
| `verify.py` | 3 | Verify a list of citations against PMC / PubMed / CrossRef / arXiv. | `--citations` `--email` `--key` `--out` `--rows` `--sleep` |
| `references.py` | 3f | Canonical reference builder — make EVERY reference perfect, in both modes. | `--asof` `--audit` `--email` `--key` `--out` `--repair` `--rows` `--sleep` |
| `sentence_case.py` | 3f | Post-canon pass — propose strict APA-7 sentence case for reference titles. | `--apply` `--out` `--proper` `--rows` `--vocab` |
| `download.py` | 4 (opt-in) | Multi-source PDF downloader (Phase 4 — OPT-IN, not run by default). | `--email` `--manual-list` `--out-dir` `--papers` `--sleep` |
| `reconcile_downloads.py` | 4 (opt-in) | Reconcile manually-downloaded PDFs against a slug+title+doi manifest. | `--downloads-dir` `--dry-run` `--manifest` `--out-dir` `--since-hours` |
| `spreadsheet.py` | 5 | Build/rebuild the bibliography xlsx from a JSON of accumulated rows. | `--out` `--rows` `--sheet-name` |
| `citations.py` | 5b | Fetch citation counts for a bibliography from OpenAlex + Semantic Scholar. | `--asof` `--email` `--key` `--out` `--rows` `--sources` |
| `xref.py` | 6 | Build a cross-citation index from a list of papers. | `--email` `--exclude` `--internal-out` `--key` `--min-cites` `--out` `--papers` `--resolve-unknown` `--rows` `--sleep` |
| `families.py` | 6b | Phase 6b — validate an LLM-proposed family taxonomy against the bibliography, stamp `family` onto rows.json, and emit families.json (the reproducible cache) + families.md (grouped tables + a family x topic cross-tab). | `--asof` `--assign` `--digest` `--md` `--out` `--rows` |
| `families_figure.py` | 6b | Phase 6b — render the interactive HTML lineage figure of the theoretical families. | `--emphasize-source` `--families` `--internal` `--lab-author` `--max-labels` `--min-year` `--motif-min` `--no-auto-landmarks` `--no-raster` `--out-prefix` `--per-family` `--rows` `--spec` `--time-warp` `--title` `--xlsx` |
| `cite_check.py` | 7 | Phase 7 gate — every in-text citation must name a paper in rows.json. | `--content` `--key` `--quiet` `--rows` |
| `review_paper.py` | 7 | Phase 7 — build a review ARTICLE (.docx) from a finished review corpus. | `--content` `--figure` `--out` `--rows` |
| `lab_corpus.py` | L1 | Lab mode — Phase L1: ingest a lab's full publication corpus from OpenAlex. | `--author` `--email` `--from-year` `--out` `--search` `--to-year` |
| `common.py` | — | Shared helpers for the literature-review toolkit. | — |
<!-- END GENERATED TOOL INDEX -->

## `verify.py` — verify citations

Catches the ~25% of search-agent citations that have wrong authors, wrong
years, or are fabricated. Run before adding anything to the spreadsheet.

```
python3 tools/verify.py --citations cits.json --out report.json --email you@inst.edu
python3 tools/verify.py --rows rows.json --out report.json      # straight from the live table
```

`cits.json` per item: `{label, pmcid?, pmid?, doi?, arxiv?, title?,
expect_first_author?, expect_year?}` (`expect_year` may be a string or int).
With `--rows` the same fields are derived from `rows.json` itself — the key
(`ref`), the DOI from `link`, and the expected first author / year / title from
the canonical `apa` — so a project needs no converter script.
arXiv papers (an `arxiv` id or a `10.48550/arXiv.<id>` DOI) route to the arXiv
API first; otherwise looks up via PMC, then PubMed, then CrossRef, then
title-search. arXiv ids are **prefetched in batches** (`id_list`, many per call)
because the API rate-limits a per-paper loop into a temporary ban. Verdict per
item: `OK`, `MISMATCH`, `NOT-FOUND`, or `ERROR`. **`NOT-FOUND` and `ERROR` are
different and must be handled differently:** NOT-FOUND = every lookup completed,
none matched (chase it down — likely fabricated); ERROR = a lookup could not
complete (rate-limit / network), so **re-run those** — never treat a throttled
fetch as "does not exist." One malformed row degrades to ERROR rather than
aborting the whole batch.

## `references.py` — canonical reference builder (Phase 3f)

Makes every `apa` perfect, in **both** modes. Verification proves a citation is
real; this rebuilds its text from the verified DOI/arXiv id so it's never trusted
from an agent's memory (topic mode) or OpenAlex's light metadata (lab mode).

```
python3 tools/references.py --rows rows.json --out rows.json --email you@inst.edu
python3 tools/references.py --rows rows.json --audit        # gate: exit 1 on any defect
```

Per row it reads a key (`ref`/`label`), a DOI (`doi` field or `https://doi.org/`
link) and/or an `arxiv` id, with an optional `venue` fallback. When a row carries
**both** a journal DOI and an arXiv id, the journal DOI wins — a published paper
is cited by its version of record, not its preprint; arXiv is used only for
preprint-only rows or rows whose DOI is itself an arXiv DOI (so you needn't
hand-clear an `arxiv` field). It fetches CrossRef or the arXiv API and emits
APA-7: full author list (>20 → 19 + ellipsis + last), correct initials +
nobiliary particles (`de Heer`), fixed casing (`ANDERSON`→`Anderson`),
HTML-unescaped + sentence-cased all-caps titles, and a real venue — including
preprint servers CrossRef leaves bare (`bioRxiv`, `PsyArXiv`, `arXiv`; arXiv's
`journal_ref` is used when present). `--audit` fails on any defect — no
author/year, `et al.`, HTML entity, JATS/HTML markup tag, `?.`/`!.` double
terminal punctuation, a U+2010/U+2011 Unicode hyphen, a malformed initial
(`L. (.`), `U+FFFD` mojibake, a truncated or empty venue, an uppercase title;
a DOI-less item (book/report) is the only non-fatal case — reported as a manual
ref to check by hand. Mojibake is flagged, not fixed: the glyph is
unrecoverable, so hand-fix it LAST (re-canon reintroduces it).

`--repair` is the **offline retrofit**: it fixes the pure string-damage classes
(markup, Unicode hyphens, `?.`) in place without re-fetching, so a corpus's
post-canon hand fixes (reviewed sentence casing, mojibake repairs, compound
surnames) survive. Use it on an old corpus; never a blanket re-canon. Both canon
and repair stamp each row with `canonical_at`, which `common.write_rows` uses to
refuse to overwrite a live table from an upstream emitter.

`--audit` also runs a corpus-level **near-duplicate scan** and prints
`⚠ A ~ B: possible duplicate` for rows whose titles nearly match. This catches the
one defect per-row canon structurally cannot see: the same paper entering the
review twice — usually an arXiv preprint found by one search agent and the
published version found by another, which have different DOIs and so both pass
the one-row-per-DOI rule and both canonicalize perfectly. It is a **warning, not
a defect** (exit status is unaffected): genuinely distinct papers do share
near-identical titles, so each pair needs a human verdict. Keep the version of
record, drop the preprint — and re-check any in-text citation whose year moves.

The gate's second warning is a **multi-word surname**, which may be a real compound
name (`Lambon Ralph`, `Sanz Perl`) or CrossRef folding given names into the family
field (`Thomas Yeo` for B. T. T. Yeo). A machine cannot tell them apart, so each
needs a human verdict; a *leading initial* in the family field (`A. Moffat`) is
unambiguous and gets repaired automatically.

## `sentence_case.py` — strict APA-7 sentence case (Phase 3f, after canon)

APA-7 wants sentence-case titles, and `references.py` deliberately does not impose
it: correct sentence-casing needs proper-noun judgment, and a mechanical caser
mis-cases proper nouns silently — which the audit gate cannot catch. So this tool
**proposes and you review**.

```
python3 tools/sentence_case.py --rows rows.json --proper proper_nouns.json --vocab
python3 tools/sentence_case.py --rows rows.json --proper proper_nouns.json --apply
```

Protected with no configuration: ALL-CAPS acronyms, any token with a digit,
camelCase, a lone capital inside a compound (`ACAM-J`), each hyphen part judged
separately (so `Resting-State` is not read as camelCase), and the first word of the
title and of any subtitle. Everything domain-specific goes in `--proper`
(`{"words": [...], "phrases": [...]}`); phrases are what let a generic word
lowercase while a named entity containing it does not (`yoga practitioners`, but
`Sahaja Yoga`). On a large corpus review with `--vocab`, which collapses ~150 title
diffs into the ~400 distinct token changes they amount to — a mis-cased proper noun
is obvious there and easy to miss in a long diff.

## `cite_check.py` — in-text citations must resolve (Phase 7 gate)

```
python3 tools/cite_check.py --rows rows.json --content content.json
```

`review_paper.py` prints whatever prose it is given, so a citation naming no row in
`rows.json` ships silently and the reader cannot follow it. This parses both APA
forms — parenthetical `(Farb et al., 2007)` and narrative `Farb et al. (2007)` /
`Farb and Segal (2007)` —
folds accents so `Millière` matches `Milliere`, and checks each against author-year
keys built from the canonical `apa` strings. **Exits 1 on an unresolved citation.**

It also warns when one author-year matches **two** references, which is invisible to
every other check and common on a large corpus. Fix with APA-7 §8.19 by naming more
authors, `(Kral, Davis, et al., 2022)` — the tool accepts that form, and the
`2025a`/`2025b` year-suffix form too.

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
python3 tools/xref.py --rows rows.json --out xref.json ...     # straight from the live table
```

`list.json` per item: `{slug, doi?, pdf?}`; with `--rows` the slug is the row
key and the DOI comes from `link`. PDF fallback uses `pdftotext`
to extract DOIs from the references section — install poppler if missing.

## `citations.py` — per-paper citation counts (Phase 5b)

Fetches citation counts by DOI from **OpenAlex** (primary; free, reliable,
batchable) and **Semantic Scholar** (secondary; best-effort, rate-limits
without `S2_API_KEY`). Google Scholar is deliberately not used — it has no API
and CAPTCHA-blocks bots, so it can't be queried for a whole bibliography.
Reads any rows JSON (DOI from a `doi` field or a `https://doi.org/...` link);
arXiv DOIs are auto-mapped to the arXiv id for S2. OpenAlex's batch filter can
return a low-count duplicate record for a DOI, so the tool keeps the highest
count per DOI and, when an OpenAlex count is far below the S2 count, re-queries
the canonical single-work endpoint — still, spot-check that a famous old paper
isn't showing a single-digit OpenAlex count before shipping.

```
python3 tools/citations.py --rows rows.json --out citation_counts.json \
                           --email you@inst.edu --asof 2026-06-07
```

Attach the counts to rows as `cite_openalex` / `cite_s2`, then rebuild — the
spreadsheet auto-adds the two `Cite` columns.

## `families.py` — thematic families (Phase 6b)

Groups the finished bibliography into a few theoretical families (a conceptual
axis orthogonal to the Topic column). The *carving* is judgment: an agent
proposes ~3-8 families and assigns every paper, with a **human checkpoint on the
family definitions** (see `family_prompt_template.md`). This tool owns only the
deterministic half — it validates the assignment and stamps `family` onto rows,
writing `families.json` (reproducible cache) + `families.md` (grouped tables +
family×topic cross-tab). Validation is **hard** on exhaustiveness (every paper
assigned), exclusivity (no unknown/extra refs), and the family count (hard limit
2–9; 3–8 recommended) — any of these exits non-zero. Imbalance is only a **warning**: empty families are
dropped, a single-paper family is flagged, and a family holding >60% of the
corpus prints a "consider splitting" warning but does not fail. `spreadsheet.py`
then auto-adds the `Family` column. Don't cluster embeddings to make families —
good theoretical families cut across textual similarity.

```
python3 tools/families.py --digest --rows rows.json          # corpus digest for the proposal
python3 tools/families.py --rows rows.json --assign families_input.json --out families.json
```

`families_input.json`: `{principle, families:[{key,name,claim,lineage}],
assignments:{ref:key}}`. Assignment values are accepted case-insensitively and
by display **name** as well as `key`, so you can re-run straight off the `family`
field this tool stamped into `rows.json` (which holds the display name,
e.g. `"Infer"`) without first lowercasing it back to the key.

## `families_figure.py` — interactive HTML lineage figure (Phase 6b)

Turns `rows.json` + `families.json` into a self-contained interactive `.html`
figure (family lanes with their defining sentences; every paper a dot,
beeswarm-packed by year; milestones labeled; hover for the full reference, click
for citation + DOI, hover a family name to spotlight its lineage) plus a
standalone `.svg` and — if `rsvg-convert`/`inkscape` is present — `.png` + `.pdf`
for slides/papers. Replaces the old static matplotlib figure.

```
python3 tools/families_figure.py --rows rows.json --families families.json \
        --out-prefix mytopic_families --title "My topic — theoretical families"
```

Landmark dots (the big labeled studies) are selected **automatically** — most-cited
within a family, foundational within this review (high within-corpus in-degree, via
`xref.py --internal-out`), or a home-lab paper (starred). Home-lab favoring is **off by
default** (lab-neutral); opt in with `--lab-author Surname` (repeatable) or the
`LITREVIEW_LAB_AUTHOR` env var (comma-separated), the flag winning over the env var. Pass
`--min-year` and
`--time-warp 0–1` for recency-heavy corpora that span many decades (an antecedents
pass usually makes one), so old foundations stay legible. The editorial layer (which
papers to *force*-label, cross-family convergence arrows, notes) is judgment — pass
an optional `--spec figure_spec.json` (`{labels, arrows, notes, order, subtitle}`)
and curate it with the user.

## `review_paper.py` — render the narrative review .docx (Phase 7, opt-in)

Turns the finished, verified bibliography into an AI-authored **review article**
`.docx`. This tool owns only the *mechanics* — the title/author/disclosure block,
the abstract, section headings + body paragraphs, an embedded figure with a
standalone caption, and an **APA-7 reference list pulled straight from the
canonical `apa` strings in `rows.json`** (deduped, alphabetized, hanging indent,
DOI links). Because the references come from the verified corpus, they cannot
drift from the in-text citations.

```
python3 tools/review_paper.py --rows rows.json --content content.json \
        --out My_Topic_review.docx --figure my_topic_families.png
```

The prose is authored *separately* (not by this tool) into `content.json`:
`{title, authors, author_note?, affiliation_line?, disclosure?, abstract,
sections:[{heading, level, paragraphs:[...]}], figure:{path,caption},
references_heading?, references_note?}`. Two non-negotiables when an LLM writes
it: (1) **disclose** the AI authorship — put the model in `authors`, add a
disclosure paragraph stating the bibliography was machine-assembled and
machine-verified and that the author read abstracts, not full texts; (2) run the
**priority audit** before rendering — an independent pass that checks every
origin claim cites the *earliest* paper that earned priority, oldest-first. Every
in-text citation must name a paper that exists in `rows.json`.

## `lab_corpus.py` — ingest a lab's corpus (Lab mode, L1)

Entry point for **lab mode** (start from a lab's papers instead of a query).
Pulls a lab's full publication list from OpenAlex by author id.

```
python3 tools/lab_corpus.py --search "Jack Gallant"        # find the author id
python3 tools/lab_corpus.py --author A5056348548 --out lab_papers.json
```

Output `lab_papers.json` (title / year / doi / venue / citations / coauthors /
abstract). **Then enrich abstracts (Semantic Scholar / PubMed) before
classifying — OpenAlex abstracts are spotty and its topic tags are coarse, so
classifying from them alone mislabels papers.** Disambiguation is the #1
correctness risk: review and prune the list before theming. See PLAYBOOK
"Lab mode" for L1b–L4 (enrich → verify/classify → themes → trajectory figure).

## `spreadsheet.py` — build the xlsx

Reads a JSON of accumulated rows and writes the xlsx with the standard
schema and color coding (white = source-doc, cream = search, green = xref,
blue = lab, lilac = anteced / anteced-nosrc; an unknown `source` renders white
with a warning). If any row carries `cite_openalex`/`cite_s2`, two `Cite`
columns are added automatically after `Tag`; `family` adds a `Family` column.
Always rebuild from the full JSON; xlsxwriter is write-only.

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

## `gen_docs.py` — regenerate the tool index

```
python3 tools/gen_docs.py            # rewrite the generated block in docs/tools.md, tools/README.md, PLAYBOOK.md
python3 tools/gen_docs.py --check    # exit 1 if any copy is stale (CI runs this)
```

## Using the toolkit from a project script

Per-topic scripts (row emitters, family assigners, page builders) should import
`common` rather than re-implement JSON I/O, DOI parsing, or the APA parser —
that is how the `ensure_ascii` fix and the year-suffix fix once failed to reach
them. Put the toolkit on the path and use `common.write_rows` for `rows.json`:

```python
import os, sys
sys.path.insert(0, os.environ.get("LITREVIEW_TOOLS",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                             "literature-review-toolkit", "tools")))
import common

rows = common.load_json("rows.json")
common.attach_counts(rows, common.load_json("citation_counts.json"))
common.write_rows("rows.json", rows)      # refuses to overwrite a canonical table unless force=True
```

`write_rows` is the guard behind the rule "after Phase 3f, `rows.json` is the
live table": if the file on disk carries `canonical_at` stamps, an upstream
emitter cannot silently replace it.

---

## Idiomatic usage

```bash
# Phase 2: spawn agent (fill in search_prompt_template.md). Agent returns
#          a list of papers with DOI links (https://doi.org/<doi>).

export LITREVIEW_EMAIL=you@inst.edu     # set once for verify.py + xref.py

# Phase 3: verify what the agent gave you (a citation list, or rows.json directly)
python3 tools/verify.py --rows accumulated_rows.json --out verify_report.json

# Phase 5: build the spreadsheet
python3 tools/spreadsheet.py --rows accumulated_rows.json --out bibliography.xlsx

# Phase 5b: citation counts (attach to rows as cite_openalex/cite_s2, rerun spreadsheet)
python3 tools/citations.py --rows accumulated_rows.json --out citation_counts.json

# Phase 6: cross-citation analysis (rows.json directly; slug = ref, DOI from link)
python3 tools/xref.py --rows accumulated_rows.json \
                      --exclude existing_spreadsheet_dois.json \
                      --out xref_$TOPIC.json \
                      --min-cites 4 --resolve-unknown

# ... pick from xref_$TOPIC.json, write summaries, repeat 3+5 ...

# Phase 6b (optional): theoretical families (agent proposes, user approves) + figure
python3 tools/families.py --rows accumulated_rows.json --assign families_input.json --out families.json
python3 tools/families_figure.py --rows accumulated_rows.json --families families.json \
                                 --out-prefix ${TOPIC}_families --title "$TOPIC — families"

# Phase 7 (optional): AI-authored narrative review .docx (author content.json first,
#   run the priority audit, gate the citations, then render — refs come from rows.json)
python3 tools/cite_check.py --rows accumulated_rows.json --content content.json
python3 tools/review_paper.py --rows accumulated_rows.json --content content.json \
                              --figure ${TOPIC}_families.png --out ${TOPIC}_review.docx

# --- OPTIONAL: Phase 4 (PDF download), only if user has asked for PDFs ---
# python3 tools/download.py --papers verified_papers.json \
#                           --out-dir papers/$TOPIC/ \
#                           --email $LITREVIEW_EMAIL
# python3 tools/reconcile_downloads.py --manifest papers/$TOPIC/_manifest.json \
#                                      --out-dir papers/$TOPIC/
```
