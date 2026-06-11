# Literature Review Agent Playbook

**Purpose.** Build or extend a bibliography spreadsheet for an academic
review topic. Per topic, produce ~50-70 high-impact and recent papers,
classified and summarised. Each row's link is the paper's DOI URL
(`https://doi.org/<doi>`). PDFs are NOT downloaded by default — Phase 4 is
opt-in only.

**When to use.** This is ONE tool with two front-ends — **topic mode** (start
from a query) and **lab mode** (start from a lab's corpus). They share the entire
downstream pipeline; only the front-end differs. Decide the mode first (Phase 0),
then gather that mode's inputs. Do NOT ask whether to download PDFs — the default
is no; only run Phase 4 if the user explicitly requests it. Always need a contact
email for the NCBI/CrossRef/OpenAlex User-Agent (export `LITREVIEW_EMAIL` or pass
`--email` — required by `verify.py`, `citations.py`, `xref.py`).

**Default tier criteria.** Pre-2021: only highly cited / foundational. 2022+:
promiscuous (no citation-count gate, since they haven't had time). The
boundary year is "today minus ~5 years"; adjust as the calendar advances.

---

## Phase 0 — choose the mode (do this first)

One tool, two front-ends. Everything after the front-end — verify, citation
counts, families, figure, spreadsheet — is the SAME shared machinery, run the
same way. There are no mode-specific shortcuts.

| Mode | Start from | User says… | Front-end | Then gather |
|------|-----------|-----------|-----------|-------------|
| **Topic** | a query/topic | "lit review on X", "extend the bibliography for Y" | Phase 1 (scope) → 2 (search) | topic name + 1-paragraph definition, source doc if any, target spreadsheet path, tier criteria |
| **Lab** | a lab's publications | "review lab Z's work", "how has Z's research evolved" | Phase L1–L3 (ingest corpus → derive themes) → **L4c** | the lab/author ids, the inclusion filter (e.g. human-only), target paths |

Both then converge on the shared pipeline: **Phase 3 verify → 3f canonicalize refs → 5 spreadsheet →
5b citation counts → 6 cross-citation → 6b families → 7 review article (optional) → 8 hand-off.** Lab mode's
outward/contextualize layer (**L4c**) is not a lighter pass — it *runs the
topic-mode front-end (Phases 2–6) once per theme*, with the identical
verify/count/dedup guardrails. Topic mode is the next section; lab mode is under
"Lab mode" below.

---

## Output artifacts (per topic batch)

1. New rows appended to `<spreadsheet>.xlsx` with columns:
   `Topic | Ref# | APA reference | Link | Summary | Tag | Family | Cite (OpenAlex) |
   Cite (S2) | PDF (local) | Xref`.
   `Link` is always the DOI URL (`https://doi.org/<doi>`). `Family` (Phase 6b)
   and the two `Cite` columns (Phase 5b) are auto-added by `spreadsheet.py`
   whenever rows carry them.
2. `citation_counts.json` — per-paper OpenAlex + Semantic Scholar counts (Phase 5b)
3. `families.json` + `families.md`, and `<topic>_families.{html,svg,png,pdf}` —
   the theoretical grouping and its interactive figure (Phase 6b, optional)
4. Cross-reference index at `xref_<topic_slug>.json` (after Phase 6)
5. **Only if Phase 7 was opted into:** a narrative review article `<Topic>_review.docx`
   (prose authored into `content.json`, rendered with `tools/review_paper.py`; APA-7 reference
   list pulled from `rows.json`).
6. **Only if Phase 4 was opted into:**
   - PDFs at `papers/<topic_slug>/<paper_slug>.pdf`
   - Browser-helper page `papers/<topic_slug>/_download_helper.html` for
     paywalled / bot-blocked papers

---

## Topic mode — the 8-phase workflow

(The query-driven front-end. Lab mode reuses Phases 3–7 verbatim; see "Lab mode"
below.)

### Phase 1 — Scope the topic

**1a. Read source if provided.** If the user has a source doc (`.docx`/`.pdf`),
extract text. For docx: `unzip -p X.docx word/document.xml | python3 strip_xml.py`.
Identify which references are actually cited in the **main text** (not just in
the bibliography). The bibliography may have hundreds of refs the doc never
discusses; only main-text-cited ones are baseline.

**1b. Define the topic precisely.** Write 3-5 sentences of what counts as
relevant. Include the contested theoretical positions, the methods / sub-areas /
populations involved, and the boundary with adjacent topics. The
search agent will use this verbatim.

**1c. List "already-known" papers.** Pull from the existing spreadsheet
(filter by `Topic`). The search agent must not re-find these.

### Phase 2 — Spawn the literature search agent

Use the `general-purpose` Agent (or any web-enabled subagent). Give it a
self-contained prompt — it has no context from this conversation. Use the
template in `tools/search_prompt_template.md` and fill in:
- `{TOPIC_NAME}` and `{TOPIC_DEFINITION}`
- `{ALREADY_HAVE}` — bullet list of existing papers (don't rediscover)
- `{TODAY}` — current date (gives the agent a recency anchor)
- `{TIER_BOUNDARY_YEAR}`
- `{TARGET_COUNT}` — usually 25-40 papers

The agent should return a numbered list with: APA citation, **DOI link in
`https://doi.org/<doi>` form** (not PubMed/PMC URLs), PMCID if available,
3-5 sentence summary, tag (`classic`/`recent-review`/`recent-empirical`/
`recent-method`/`recent-LLM`/`recent-theory`/`recent-clinical`), and year.

**Do not act on the agent's output yet.** It will contain errors. Proceed
to Phase 3.

### Phase 3 — Verify EVERY citation (CRITICAL)

In a previous run, the search agent fabricated 5 author lists, reversed
one paper's conclusion, and invented a bioRxiv DOI that didn't exist.
About 1 in 4 citations had errors. **Always verify before adding.**

For each paper the agent returned:

**3a. If a PMCID was given:** call NCBI esummary
(`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pmc&id=<num>&retmode=json`).
Confirm first author, year, and title match. See `tools/verify.py`.

**3b. If no PMCID but a title is given:** call PubMed esearch
(`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=<title>&retmode=json`)
then esummary. Confirm match.

**3c. If only an arxiv ID:** WebFetch `https://arxiv.org/abs/<id>` and read
title/authors from the page.

**3d. If a publisher landing page (Nature, Springer, OUP):** WebFetch the
page and confirm author/year. Don't rely on the agent's claim.

**3e. Drop / fix:**
- Citation completely fabricated (URL doesn't resolve, no PubMed match) → drop.
- Wrong first author / wrong year → fix using the verified metadata.
- Title matches but agent's summary contradicts the abstract → fix summary.
- Suspicious DOI (e.g. unusual prefix, no resolution) → drop unless you can
  confirm via web search.

Common fabrication patterns to flag:
- Author name that doesn't appear in any of the paper's actual authors.
- Conclusion that is the OPPOSITE of the paper's actual finding.
- bioRxiv DOIs not matching the `10.1101/...` pattern.
- arxiv preprint IDs that don't resolve.

### Phase 3f — Canonicalize EVERY reference (`tools/references.py`)

Verification (3a–3e) confirms a citation is *real*; this makes its `apa` string
*perfect*. **Never ship a reference typed from an agent's memory (topic mode) or
OpenAlex's light metadata (lab mode)** — rebuild every `apa` from the verified
DOI against the authoritative source. `references.py` is the single canonical
formatter and a hard gate, used identically in BOTH modes:

```
python3 tools/references.py --rows rows.json --out rows.json   # rebuild + report
python3 tools/references.py --rows rows.json --audit           # gate: exit 1 on any defect
```

It pulls CrossRef (DOIs) or the arXiv API (arXiv ids / `10.48550/arXiv.*` DOIs),
then builds APA-7 with: full author list (>20 → 19 + ellipsis + last), correct
initials and nobiliary particles (`de Heer`, `Dupré la Tour`), fixed name casing
(`ANDERSON`→`Anderson`, `zhang`→`Zhang`), HTML-unescaped + sentence-cased
all-caps titles, and a real venue — including preprint servers CrossRef leaves
bare (`bioRxiv`, `PsyArXiv`, `arXiv`). The `--audit` gate fails the build on any
defect (missing author/year, `et al.`, HTML entity, `U+FFFD` replacement-char
mojibake, truncated/empty venue, uppercase title). The ONLY allowed non-fatal
case is a DOI-less item (book, report, old proceedings) — it keeps its
hand-written `apa` and is reported as a
manual ref; verify those by hand. **Run the gate before every deliverable.**

### Phase 4 (OPTIONAL) — Download PDFs

**Skip this phase by default.** Run only if the user explicitly asks for
PDFs. The default workflow is Phase 1 → 2 → 3 → 5 → 6 → 7. PDF acquisition
will eventually be replaced by a separate dedicated tool; treat the
machinery below as legacy that still works on demand.

If opted in, try sources in this order (`tools/download.py` does this
automatically):

1. **arxiv direct** — `https://arxiv.org/pdf/<id>.pdf`. Always works for
   arxiv preprints. Only one risk: rate-limit (429) if you hit too fast;
   use 2s sleeps between calls.

2. **Unpaywall API** — `https://api.unpaywall.org/v2/<doi>?email=<user_email>`.
   Returns `oa_locations` with PDF URLs. **Prefer non-PMC URLs first**, since
   PMC has aggressive bot blocking. Often gives author institutional repos
   (`.edu` / `.ac.uk` pages) that work with simple curl.

3. **Direct journal URL via Unpaywall's `best_oa_location.url_for_pdf`** —
   `https://www.nature.com/articles/<id>.pdf` typically works for OA Nature,
   Nat Commun, Nat Neuro, Nat Hum Behav, Sci Rep.

4. **Europe PMC** — `https://europepmc.org/articles/<PMCID>?pdf=render`
   works for many NIH-funded papers.

5. **Manual fallback via browser-helper page (preferred over `_needs_manual.txt`).**
   For papers that fail the auto-download, generate
   `papers/<topic>/_download_helper.html`: one row per failed paper with
   author/year/slug/title and an Open link to the journal landing page (use
   plain `https://doi.org/<doi>` for paywalled — the user has institutional
   access; do **not** wrap in libproxy URLs, those land on a generic library
   page). Use direct PMC `/articles/<PMCID>/` URLs for OA-on-PMC papers and
   `https://www.biorxiv.org/content/<doi>v1` for bioRxiv preprints.
   Open the helper with `open <path>` so it loads in the user's browser. The
   user clicks through, downloads each via the publisher's own PDF button,
   PDFs land in `~/Downloads` with publisher-chosen filenames. Then run
   `tools/reconcile_downloads.py --manifest <topic>/_manifest.json
   --out-dir papers/<topic>/` to read each PDF's first-page title via
   pdftotext, fuzzy-match to the manifest, and move into place with the
   right slug name.

**Verify each download is actually a PDF** (first 4 bytes == `%PDF`).
A 200 response can still return an HTML challenge page.

**Do NOT attempt** these sources — they all reliably fail to bots:
- PMC direct PDF URLs (`https://pmc.ncbi.nlm.nih.gov/articles/<PMCID>/pdf/`):
  Cloudflare Proof-of-Work challenge.
- bioRxiv / medRxiv direct: Cloudflare bot mitigation (403).
- PNAS direct PDF (`pnas.org/doi/pdf/...`): 403 via curl.
- OUP `academic.oup.com/.../article-pdf/...`: 403.
- MIT Press `direct.mit.edu/imag/article-pdf/...`: 403.
- Elsevier ScienceDirect `.../pdfft`: 403.
- Wiley `onlinelibrary.wiley.com/doi/pdfdirect/...`: 403.

These all work fine in a real browser, so route them to the helper page
described in step 5 — don't keep retrying programmatically.

### Phase 5 — Update the spreadsheet

Use `xlsxwriter` (no install if already present; if not, write CSV instead
and tell the user). Schema:

| Topic | Ref # | APA reference | Link | Summary | Tag | Cite (OpenAlex) | Cite (S2) | PDF (local) | Xref |
|-------|-------|---------------|------|---------|-----|-----------------|-----------|-------------|------|

(The two `Cite` columns appear only when Phase 5b has populated them.)

- `Topic`: one of the project's topic categories (e.g. "Multimodal networks").
- `Ref #`: numeric for source-document refs; use `<topic-letter><n>` for
  added refs (e.g. `M1`-`M40` for first multimodal batch, `M41`-`M70` for xref
  batch). Keep numbering monotonically increasing across batches.
- `APA reference`: full APA, list authors up to 6 then `et al.`.
- `Link`: DOI URL in `https://doi.org/<doi>` form — verified to resolve.
  PubMed/PMC URLs are NOT used as the primary link. If a paper has only a
  PMID/PMCID, look up its DOI before adding the row.
- `Summary`: 3-5 sentences. State what the paper did and why it matters for
  the topic. Don't just paraphrase the abstract.
- `Tag`: see Phase 2 list.
- `PDF (local)`: relative path if downloaded, else empty.
- `Xref`: citation count from cross-reference analysis (Phase 6), else empty.

**Color-code rows** so origin is visible:
- White: refs from the source paper.
- Cream `#FFF7E0`: refs added in initial search (Phase 2).
- Green `#E2F0D9`: refs added via cross-citation analysis (Phase 6).

Freeze the header row. Set column widths (~22, 8, 60, 50, 90, 14, 50, 8) and
row heights (~110pt) for readability with wrapped text.

`tools/spreadsheet.py` does the rebuild from a JSON of rows.

### Phase 5b — Citation counts (standard; do this on every review)

Add per-paper citation counts. **Google Scholar is not usable** — it has no
API and CAPTCHA-blocks automated queries after a handful of requests, so it
cannot be pulled for a whole bibliography. Use `tools/citations.py`, which
queries two databases by DOI:

- **OpenAlex** — primary source. Free, no key, reliable, near-complete by DOI,
  batchable. (Undercounts arXiv-only preprints, which it often files under a
  separate record from the published version — cross-check those with S2.)
- **Semantic Scholar** — secondary. Often higher for CS/AI venues and gives an
  `influentialCitationCount`. Its free endpoints rate-limit hard (HTTP 429/400)
  from shared IPs and silently drop papers; treat as best-effort. Set
  `S2_API_KEY` in the environment to make it reliable.

```bash
python3 tools/citations.py --rows rows.json --out citation_counts.json \
        --email you@inst.edu --asof <YYYY-MM-DD>
```

Then attach the counts to each row (`cite_openalex` / `cite_s2` keys) in your
`build_data.py`/rows pipeline and rebuild — `spreadsheet.py` auto-adds the two
`Cite` columns when it sees them. Counts are a snapshot at run time; re-run to
refresh. Papers with no DOI (books, blog/tech-report releases) stay blank.

**Note on per-version data scripts.** If you keep your batch data inside
numbered Python files (`build_bibliography.py`, `build_bibliography_v2.py`,
...) that import each other to inherit prior rows, then **the
xlsx-writing block in each one must live under `if __name__ == "__main__":`**.
Without the guard, a casual `from build_bibliography import ROWS` rewrites
the spreadsheet as a side effect of import. Module-level data and helpers
stay at top level so they're importable; only the xlsxwriter block is
guarded. The simpler alternative is to keep all rows in a single JSON and
rebuild via `tools/spreadsheet.py`.

### Phase 6 — Cross-citation analysis (second pass)

Run after Phase 5 is committed. The point: find high-impact papers the
initial search missed by looking at what the papers we DO have cite repeatedly.

**6a. Fetch reference lists.** For each paper with a DOI, call CrossRef:
`https://api.crossref.org/works/<doi>`. The `message.reference[]` field has
the cited refs. Most have a `DOI` field; some have only unstructured strings.
For papers without DOIs (arxiv-only), fall back to extracting DOIs from the
PDF text via `pdftotext -layout <pdf> - | grep -oE '10\.\d+/...'`. This is
crude but recovers some.

**6b. Build the frequency table.** For each cited DOI, count how many of
your N papers cite it. `tools/xref.py` does this.

**6c. Resolve unknowns.** Many cited refs have only a DOI in the CrossRef
response, no title/author. Look these up via CrossRef metadata
(`api.crossref.org/works/<doi>` again, but for the cited DOI).

**6d. Filter and select.** Take refs cited by `≥4` of your papers
(definite-include) plus selected `≥3`-cited foundational classics. Filter
out:
- Refs already in the spreadsheet (check by DOI normalized to lowercase).
- Methods/software citations (SciPy, NumPy, FreeSurfer, fMRIPrep, etc.)
  unless the topic is methods.
- Off-topic refs that just happened to be popular (e.g. a stats paper).

Aim for ~25-35 additions. More than that and the spreadsheet becomes
unwieldy; less and you've under-mined.

**6e. Repeat Phases 3-5** for the new batch. Verify every citation, attempt
PDF download, append to spreadsheet (with the green color and Xref column
populated).

### Phase 6b — Thematic families (OPTIONAL)

Group the finished bibliography into a few **theoretical families** — a
conceptual axis *orthogonal to the Topic column* (Topic captures method/sub-area;
families capture what each paper is fundamentally *for*). Adds a `Family` column
and a `families.md` (grouped tables + a family×topic cross-tab). Run after the
bibliography is assembled, verified, and counted.

This phase has **two judgment gates with a human checkpoint between them**; the
rest is mechanical, owned by `tools/families.py`:

1. **Propose** (agent, reading the corpus via `tools/families.py --digest`):
   propose ~3-8 families, each `{key, name, claim, lineage}`, and state the one
   organizing principle. The hard constraint: families must cut *across* the
   Topic lanes — a good family unites textually-dissimilar papers and splits
   similar ones. **Do NOT cluster embeddings** to make families; that yields
   surface-similarity groups, not theoretical ones. Use the prompt in
   `tools/family_prompt_template.md`.
2. **Confirm** — show the user *just the ~6 family definitions* for approval/edit.
   This is the cheap, high-leverage checkpoint: iterating on six definitions is
   free; redoing the assignment is not.
3. **Assign** — against the frozen spec, assign every paper to one family
   (dominant commitment). Assign in batches for large corpora; never one rushed
   250-paper pass. Write `families_input.json`
   (`{principle, families, assignments:{ref:key}}`).
4. **Validate + render:**
   ```bash
   python3 tools/families.py --rows rows.json --assign families_input.json \
           --out families.json
   ```
   It enforces exhaustive / exclusive / balanced (fails loud otherwise), stamps
   `family` onto rows.json, writes `families.json` (the reproducible cache, like
   `citation_counts.json`) + `families.md`, and `spreadsheet.py` auto-adds the
   `Family` column on the next rebuild. Re-run only when the taxonomy changes.

**The figure is an interactive HTML** (not a static png), produced by
`tools/families_figure.py` from `rows.json` + `families.json`:

```bash
# first emit the within-review citation graph (criterion 2 below); reuses the xref pass:
python3 tools/xref.py --papers xref_papers.json --out xref_<topic>.json \
        --exclude xref_exclude.json --internal-out internal_citations.json --email you@inst.edu
python3 tools/families_figure.py --rows rows.json --families families.json \
        --internal internal_citations.json \
        --out-prefix <topic>_families --title "<Topic> — theoretical families"
```

It writes a self-contained `.html` (family lanes with their defining sentences,
every paper as a dot beeswarm-packed by year, landmark studies as big labelled dots;
hover any node for its full reference, click for citation + DOI, hover a family name
to spotlight its lineage) plus a standalone `.svg` and — if `rsvg-convert`/`inkscape`
is present — `.png` + `.pdf` for slides/papers. This replaces the old static figure.

**Landmark labelling is AUTOMATIC — do not hand-build a labels overlay.** A paper is
labelled as a landmark (big dot) if ANY of: (1) it is among the **most-cited in its
family** (top `--per-family`, default 4, by max(OpenAlex, S2)); (2) it is **foundational
within this review** — cited by ≥ `--motif-min` (default 3) of the corpus's own papers
(this is criterion (2) and needs `internal_citations.json` from `xref.py --internal-out`;
silently skipped if absent — so always pass `--internal`); or (3) it is a **home-lab
paper** (an author surname in `--lab-author`, default `Gallant`, or a row with
`source=="lab"`) — these are **starred (★) and gold-ringed** so the lab's own work stands
out. Total labels are capped at `--max-labels` (lab + internal-motif papers always kept).

**Only the editorial *arrows/notes* remain a human checkpoint** (cross-family convergence
arrows and annotations are judgment). Curate those via an optional `--spec figure_spec.json`
(`{arrows:[{from,to,color,label}], notes:[{at,text,color}], order, subtitle}`); a `labels`
map there still overrides auto-selection if you ever need to force a specific set. Don't
expect a good arrow set auto-generated.

### Phase 7 — Write the review article (OPTIONAL)

Turn the finished corpus into a narrative **review article** as a `.docx`. Run only when
the user asks for a written review (not for the bibliography itself). Prerequisites: Phase 3f
(canonical `apa`) and 5b (counts) are done; ideally Phase 6b families + figure exist too, since
the families are the natural section structure.

**Authorship and honesty (non-negotiable when an LLM writes it).** If the article is
AI-authored, say so plainly. Put the model's name in `authors`, add an `author_note` that
identifies it as an AI, and include a `disclosure` paragraph stating that the bibliography was
machine-assembled and machine-verified and that the author has read only abstracts/metadata, not
full texts. Language models fabricate citations; the Phase-3/3f verification is what makes an
AI-written review trustworthy, and the disclosure must make that provenance explicit.

**Prose.** Author the prose with the `scientific-writing` skill (one idea per sentence, forward
flow, reserve "represent" for brain representations). Organize sections by the **Phase-6b
families** — the theoretical axis orthogonal to the topic lanes makes a better narrative than the
method/region lanes. The title should convey the question, the answer, and why it matters. Every
in-text citation is **APA author–date** (`(Huth et al., 2016)`) and MUST name a paper that exists
in `rows.json`, so the reference list backs it.

**Mechanics — `tools/review_paper.py`.** The tool owns only the mechanical render; it does not
write prose. It reads `rows.json` and builds the **APA-7 reference list straight from the
canonical `apa` strings** (deduped, alphabetised, hanging indent, with DOI links), embeds the
families figure with a standalone caption, and lays out the title/author/disclosure block + the
abstract + sections. Keep the prose in a small per-project emitter that dumps `content.json`
(see the schema in `review_paper.py`); render with the shared tool:

```bash
python3 write_review.py            # project file: authors prose -> content.json
python3 tools/review_paper.py --rows rows.json --content content.json \
        --figure <topic>_families.png --out <Topic>_review.docx
```

The reference list comes from `rows.json`, so it is automatically canonical and complete; verify
by opening the `.docx` and confirming the figure renders and the section/citation structure reads
correctly. Worked example: `distributed_conceptual_network/` (`write_review.py` + `content.json`
→ an AI-authored review with all 370 refs in APA-7). Output artifact:
`<Topic>_review.docx` (plus the project's `content.json`).

### Phase 8 — Hand off

Tell the user:
- Total rows in spreadsheet, broken down (source / search / xref).
- Any verification corrections you made (e.g. fabricated PMCIDs, wrong
  first authors).
- **Only if Phase 4 was run:** PDFs downloaded vs. failed, and the path to
  the browser-helper page or `_needs_manual.txt` for paywalled papers.

---

## Lab mode — review a lab's corpus in the context of the field

The workflow above is **topic mode**: it starts from a query and searches
outward. **Lab mode** inverts the front end — it starts from a known body of
work (a lab's publications), derives the lab's research themes and how they
shifted over time, then searches outward to place that work in the field.
Everything downstream (verify, count, families, figure) is the same machinery.

**Phase L1 — ingest the corpus.** `tools/lab_corpus.py` pulls the lab's full
publication list from OpenAlex by author id (use `--search` to find it; pass
several `--author` ids for PI + key lab members). Output `lab_papers.json`.

**Phase L1b — enrich abstracts (REQUIRED).** **OpenAlex metadata is not enough:**
its abstracts are missing for a sizable minority of papers and its `topics` tags
are coarse, so classifying from them alone mislabels papers. Fill missing
abstracts from Semantic Scholar (`/paper/batch`, by DOI) and/or PubMed first.

**Phase L2 — define the lab & verify the corpus (HUMAN CHECKPOINT #1).** The
load-bearing gate: author-id disambiguation is the #1 correctness risk (OpenAlex
ids split / merge / collide; trainees move between labs). Have an agent classify
every paper **from its actual content — not database topic tags** — into the
buckets the user wants (e.g. for "human work only": `human` / `primate` /
`other`), and **web-verify (PubMed / publisher) every paper without an abstract
and every ambiguous call**. Prune false-positives; keep what the user asked for.

**Phase L3 — derive themes (HUMAN CHECKPOINT #2).** Run the families step
(`family_prompt_template.md` → user approves the ~N themes → assign every kept
paper). The "families" are now the lab's research programs; `tools/families.py`
validates/stamps and emits `families.json` + `families.md`.

**Phase L4 — render the lab's trajectory.**
- **Trajectory figure:** `tools/families_figure.py` — themes × year, the lab's
  papers as the spine (milestones labelled, the rest dots). This *is* "the lab's
  topics and how they changed over time."
- **Bibliography:** `tools/spreadsheet.py` (lab papers get the `lab` row color).

**Phase L4c — contextualize: a FULL topic-mode review, once per theme.** This is
NOT an optional or "lighter" pass. Placing the lab in its field means running the
*entire* topic-mode workflow (Phases 2–6) for each theme — same rigor, same
guardrails, no shortcuts. The recurring failure mode is treating this as a quick
"context" add-on and skipping the machinery; that is exactly how a sloppy,
half-fabricated field set sneaks into an otherwise careful review. For each
theme:
1. **Search (Phase 2)** with `search_prompt_template.md` — precise theme
   definition, the lab's papers in that theme as the "already have"/exclude list,
   two-tier criteria (foundational vs recent), a capped target (~30–40), multiple
   query angles. One agent per theme.
2. **Verify EVERY citation (Phase 3, non-negotiable)** with `tools/verify.py`.
   It now resolves arXiv/conference papers against the arXiv API — so a NOT-FOUND
   is a real failure to investigate, never "an arXiv paper, skip it." Expect ~1
   in 4 to need a fix (fabricated author lists, wrong arXiv ids, garbage DOIs).
3. **Citation counts (Phase 5b)** with `tools/citations.py` for every field
   paper — bibliographies always carry counts.
4. **Consolidate with two guarded steps (fail loud):**
   (a) **cross-theme dedup** — a paper found by several themes must be assigned to
   exactly ONE (`families.py` checks ref-level exclusivity but NOT duplicate
   DOIs, so dedup by DOI yourself first); (b) **exclude the reviewed lab's own
   DOIs** — the agents only excluded each theme's seed list, so a lab paper from
   theme A can resurface as "field" in theme B. Assert zero field↔lab DOI
   collisions and zero cross-theme duplicate DOIs before merging.
5. **Merge** into the context corpus (lab rows `source=lab`, field rows
   `source=search`) and re-run families + figure (`--emphasize-source lab` to
   keep the lab papers as the labelled spine over the field dots).

The three human checkpoints mirror topic mode: **(1) the corpus** (not a topic),
**(2) the themes**, **(3) the figure**.

---

## Lessons learned (don't repeat these mistakes)

### On the search agent
- **Always verify.** ~25% of agent-returned citations have errors. Wrong
  first authors are the most common; the agent confuses similar-titled
  papers and mixes up author lists.
- **The conclusion can be reversed.** Read the abstract before trusting
  any summary — agents have been observed to invert a paper's headline
  finding (e.g., describing "X > Y" when the paper says the opposite).
- **Cap the request.** Asking for 40 papers gives 40-44; asking for "as many
  as possible" gives sprawl with more fabrications.
- **Give exhaustive "do not include" lists.** Without these, the agent
  re-finds papers already in the spreadsheet (3 of 44 in the first run).
- **NOT-FOUND ≠ unverifiable ≠ fine.** arXiv/conference papers used to slip
  through because CrossRef/PubMed can't see them, so they returned NOT-FOUND and
  got waved through. `verify.py` now hits the arXiv API directly; a NOT-FOUND is
  a real problem to chase, never a license to skip. (One run: a "Vo et al."
  attention paper was actually Foster et al.; two Jain & Huth arXiv ids pointed
  at unrelated papers — all caught only because every citation, preprint
  included, was verified.)

### On contextualizing a lab review (lab mode L4c)
- **The outward search is a FULL topic-mode review, not a "context" add-on.**
  Framing it as optional/lighter is precisely how a sloppy, half-fabricated field
  set sneaks into an otherwise careful review. Run Phases 2–6 per theme with the
  same verify/count/dedup guardrails — no shortcuts.
- **Dedup by DOI and exclude the lab's own papers before merging.** Multiple
  theme-agents find the same landmark (one paper turned up under three themes),
  and an agent only excludes its own theme's seeds — so a lab paper resurfaces as
  "field." `families.py` enforces ref-level exclusivity but not duplicate DOIs;
  assert zero cross-theme dup DOIs and zero field↔lab collisions yourself.

### On PDF downloads
- **PMC direct PDFs are hopeless via curl.** Cloudflare PoW challenge.
  Always go through Europe PMC or Unpaywall.
- **Cell, Elsevier, Wiley, OUP, MIT Press, PNAS, biorxiv all block bots.**
  Don't waste retries; route to manual list.
- **Author institutional repos work.** When Unpaywall returns a
  university-domain URL (`.edu`, `.ac.uk`, etc.), it almost always
  downloads cleanly.
- **Always validate the bytes.** A 200 response with `%PDF` magic = real PDF.
  A 200 response with HTML = challenge page or paywall preview.

### On the spreadsheet
- Use a "source" column or color code so a future you (or the user) knows
  where each ref came from and how confident to be.
- Keep summaries to 3-5 sentences. Long ones become unreadable in a row.
- Don't try to read existing xlsx with xlsxwriter — it's write-only. If
  appending, regenerate the whole file from a JSON of accumulated rows.
- **If you keep batch data inside per-version Python scripts that
  import each other, guard the xlsx-writing block under
  `if __name__ == "__main__":`.** Otherwise importing such a script
  for its data structures (e.g. `from build_bibliography import ROWS`)
  rewrites the spreadsheet as a side effect of import. The simpler
  alternative is to keep all rows in a single JSON and rebuild via
  `tools/spreadsheet.py`.

### On cross-citation analysis
- CrossRef coverage varies by publisher. Nature, Cell, OUP, JNeurosci have
  excellent coverage. Some smaller journals deposit no refs.
- ≥4 citations across 40 papers is a strong signal. ≥3 is borderline; only
  pick if the paper is clearly foundational.
- The xref pass typically finds 25-35 papers per topic that the initial
  search missed — almost half as many again.

### On citation counts (Phase 5b)
- **Google Scholar can't be automated.** No API; CAPTCHA after ~10-20 requests.
  Don't try to scrape it for a whole bibliography — use OpenAlex + S2.
- **OpenAlex is the reliable workhorse** (~95%+ coverage by DOI). It undercounts
  arXiv-only preprints (separate record from the published version), so for
  preprint-heavy reviews lean on the S2 number for those rows.
- **Semantic Scholar's free endpoints are flaky**: the `/paper/batch` endpoint
  429s and sometimes 400s (one malformed id poisons the whole batch); the
  single `/paper/{id}` endpoint 404s valid papers under load. Set `S2_API_KEY`
  to fix it. Without a key, accept partial S2 coverage — OpenAlex stands alone.
- Counts are a snapshot; record the `--asof` date. Don't expect the two columns
  to match — GS-style totals (which neither gives) run higher than both.

---

## API endpoint reference

| Service | URL pattern | Returns |
|---------|-------------|---------|
| PubMed esearch | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=<q>&retmode=json` | List of PMIDs |
| PubMed esummary | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=<id>&retmode=json` | Title/authors/year |
| PMC esummary | `...?db=pmc&id=<numeric_pmc>` | Same, for PMC |
| Unpaywall | `https://api.unpaywall.org/v2/<doi>?email=<email>` | OA PDF URLs |
| CrossRef metadata | `https://api.crossref.org/works/<doi>` | Title, authors, references |
| OpenAlex (counts) | `https://api.openalex.org/works?filter=doi:<d1>\|<d2>...&mailto=<email>` | `cited_by_count`, batchable 50/req |
| Semantic Scholar (counts) | `POST https://api.semanticscholar.org/graph/v1/paper/batch?fields=citationCount,influentialCitationCount` body `{"ids":["DOI:..","ARXIV:.."]}` | citation + influential counts; 429s without `S2_API_KEY` |
| EuropePMC search | `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=<q>&format=json` | Full search |
| EuropePMC PDF | `https://europepmc.org/articles/<PMCID>?pdf=render` | PDF (often) |
| arxiv API | `http://export.arxiv.org/api/query?search_query=all:<q>` | Atom XML |
| arxiv PDF | `https://arxiv.org/pdf/<id>.pdf` | PDF |
| Nature direct | `https://www.nature.com/articles/<id>.pdf` | PDF (if OA) |

Rate limits worth knowing:
- arxiv API: ~1 req/3s; bursts trigger 429.
- NCBI eutils: 3 req/s without API key, 10 req/s with key. Use 0.4s sleep.
- CrossRef: polite pool with `mailto:` in User-Agent gives unlimited; without, ~50/s.
- Unpaywall: 100k req/day per email.

Always include a `User-Agent` header with your email for these APIs.

---

## Reusable helper scripts

All in `<project>/tools/`. Each is standalone, takes input via JSON/CLI,
outputs JSON/files. Run `python3 tools/<script>.py --help` for flags.

| Script | Purpose |
|--------|---------|
| `tools/verify.py` | Verify a list of citations via PMC/PubMed/CrossRef + arXiv. Reports mismatches. |
| `tools/references.py` | Phase 3f. Rebuild every `apa` from the verified DOI (CrossRef) or arXiv id into canonical APA-7; `--audit` gates the build (exit 1 on any defect). Both modes. |
| `tools/citations.py` | Phase 5b. Fetch per-paper citation counts from OpenAlex (primary) + Semantic Scholar (secondary) by DOI. Google Scholar is not usable (no API / CAPTCHA). |
| `tools/families.py` | Phase 6b. Validate an (agent-proposed, human-approved) family taxonomy, stamp `family` onto rows, emit `families.json` + `families.md`. `--digest` prints a corpus digest for the proposal step. |
| `tools/families_figure.py` | Phase 6b. Interactive HTML lineage figure from `rows.json` + `families.json` (+ standalone svg/png/pdf). Optional `--spec` for editorial labels/arrows/notes. Replaces the old static figure. |
| `tools/lab_corpus.py` | **Lab mode** Phase L1. Ingest a lab's full publication corpus from OpenAlex by author id (`--search` to resolve). Enrich abstracts before classifying — OpenAlex alone is insufficient. |
| `tools/xref.py` | Build cross-citation index from a list of (slug, doi) tuples via CrossRef. |
| `tools/spreadsheet.py` | Build/rebuild xlsx from a JSON of accumulated rows (DOI URLs as Link). |
| `tools/review_paper.py` | **Phase 7 (optional).** Render a review-article `.docx` from `content.json` (prose) + `rows.json`. Builds the title/author/disclosure block, abstract, sections, embedded figure, and an APA-7 reference list pulled from the canonical `apa`. Prose is authored separately (scientific-writing skill); the tool owns only the mechanics. |
| `tools/search_prompt_template.md` | Prompt template for the literature-search subagent. |
| `tools/download.py` | **Opt-in (Phase 4).** Multi-source PDF downloader. Not run by default. |
| `tools/reconcile_downloads.py` | **Opt-in (Phase 4).** After the user manually downloads PDFs via the browser-helper page, this reads each PDF's first-page title via `pdftotext`, fuzzy-matches it against a manifest of slug+title pairs, and moves the PDF into the per-topic dir with the correct slug filename. |

Each helper is small (<200 lines) and meant to be read + adapted. They are
not a framework — they're scaffolding to keep the LLM judgment work fast.

---

## Quick start for a fresh Claude

```
1. Read this playbook.
2. Read the existing spreadsheet (xlsxwriter is write-only; convert to CSV
   first via `python3 -c "import openpyxl; ..."` or load via pandas if
   available, or just have the user paste the topic list).
3. Confirm topic + criteria with the user. Do NOT ask whether to download
   PDFs — the default is no (Phase 4 is opt-in only).
4. Phase 1: collect baseline (source-doc citations).
5. Phase 2: spawn search agent using tools/search_prompt_template.md.
6. Phase 3: verify EVERY citation (tools/verify.py).
7. Phase 5: update spreadsheet (tools/spreadsheet.py) with DOI URLs as Link.
8. Phase 5b: citation counts (tools/citations.py); attach to rows, rebuild.
9. Phase 6: cross-citation pass (tools/xref.py); verify and append xref
   batch via Phases 3 + 5 again.
9b. Phase 6b (OPTIONAL): thematic families — propose → confirm with user →
    assign → tools/families.py validates/stamps/renders. Figure is bespoke.
9c. Phase 7 (OPTIONAL): review article — author prose into content.json,
    render with tools/review_paper.py (APA-7 refs from rows.json). If
    AI-authored, state the AI author + a verification disclosure.
10. Phase 8: report to user.
11. Phase 4 (PDF download) is OPTIONAL. Only run if the user explicitly
    asks for PDFs.
```

For a topic with ~40 search-added + ~30 xref-added papers, the default
no-PDF workflow takes Claude roughly 1-2M tokens and 5-10 minutes
wall-clock — Phase 6 (xref) is the slowest step (~3-5 minutes for CrossRef
calls). With Phase 4 turned on, add 10-20 more minutes for downloads.
