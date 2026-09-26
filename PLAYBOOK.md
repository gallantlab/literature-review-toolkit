# Literature Review Agent Playbook

**Purpose.** Build or extend a bibliography for an academic review topic, offer
its lineage timeline on every review, and optionally write it up as a review.
This is ONE tool with two front-ends — **topic mode** (start from a query) and
**lab mode** (start from a lab's corpus) — that share the entire downstream
pipeline; only the front-end differs. Per topic, aim for ~50-70 high-impact and recent papers, classified and
summarized. Decide the mode first (Phase 0), then gather that mode's inputs.

## Operating contract — the rules that don't bend

These are the load-bearing invariants. Everything below the contract is reference
detail that elaborates them; when in doubt, obey this list. Section pointers are in
parentheses. Treat bold emphasis elsewhere in this file as ordinary guidance — the
genuinely inviolable rules are *only* the nine here.

1. **Verify EVERY citation before it enters a deliverable** (Phase 3); `verify.py --rows`
   stamps each row, canon refuses a row without an OK stamp for its current ids, and the
   audit fails it. About 1 in 4 agent-returned refs has a fabricated author list, wrong
   year, reversed conclusion, or bad DOI. No exceptions — preprints included.
2. **Every reference is canonical** (Phase 3f). Rebuild each `apa` from the verified
   DOI/arXiv with `references.py`; never ship an agent-typed or OpenAlex-typed
   string. Canon's refusal to rebuild an unverified row is unconditional — on every
   table, including one built before the gates existed. `references.py --audit` is a
   hard gate (exit 1) — run it before every deliverable.
3. **One row per DOI** — global dedup; a paper appears once in `rows.json`. Bites
   hardest at the lab-mode merge, where one paper surfaces under several
   theme-searches and a lab paper can resurface as "field" (Phase L4c). (Distinct
   from the *one-family-per-paper* rule, which `families.py` enforces automatically
   — Phase 6b. This contract item is only about row-level deduplication.)
4. **Run the antecedents pass on every review, both modes** (Phase 2b). The forward
   search misses the topic's methodological, empirical, and theoretical roots;
   without it the field looks ~10 years old.
5. **Audit the temporal order of ideas before delivering any written review**
   (Phase 7). Origin claims must cite the EARLIEST deserving paper, oldest-first —
   not whichever ref fits the sentence.
6. **`rows.json` is the live table after Phase 3f.** Edit it by hand for any later
   change; never re-run the row-emitter (it wipes canonical `apa` + citation counts).
7. **Don't ask before fetching** from PubMed/PMC/CrossRef/OpenAlex/Unpaywall/arXiv/
   publishers — these are read-only academic GETs; do confirm destructive or
   shared-state actions. Every link is a bare `https://doi.org/<doi>` (never a
   libproxy URL). Set a contact email (`LITREVIEW_EMAIL` or `--email`) for the API
   User-Agent.
8. **PDFs are opt-in** (Phase 4) — default no, and never ask whether to fetch them.
9. **The spreadsheet is the release gate.** `spreadsheet.py` runs the full audit and
   refuses a failing table (verify stamps, hand checks for DOI-less rows, summary
   checks, acknowledged warnings); `--draft` writes a file marked as a draft.

**Default tier criteria.** Pre-2021: only highly cited / foundational. 2022+:
promiscuous (no citation-count gate — too recent to have accrued cites). The
boundary is "today minus ~5 years"; advance it as the calendar moves.

---

## Documentation site — keep it in sync

There is a public documentation website built from `docs/` (MkDocs + Material),
live at **https://gallantlab.org/literature-review-toolkit/**. It is a *superset*
of this PLAYBOOK and the README, not a fork. **When you change the toolkit — a
tool, a phase, a command/flag, a guardrail or lesson — update the matching page
under `docs/` in the same change** (fastest to drift: `docs/manual.md`, which
carries every phase command, guardrail and flag). The tool index in `docs/tools.md`, `tools/README.md` and
this file is **generated** — run `python3 tools/gen_docs.py` after adding a tool
or a flag; `.github/workflows/tests.yml` fails on a stale copy, and also runs
`ruff check .` and `tools/tests/test_formatting.py`. The site auto-deploys via
`.github/workflows/docs.yml` on push to `main` (build runs `mkdocs build
--strict`). Full editing/figure/snippet details live in `docs/maintaining.md`.
The repo is **public** (that's what enables free Pages); `site_url` uses the org's
`gallantlab.org` custom domain, not `github.io`.

---

## Phase 0 — choose the mode (do this first)

One tool, two front-ends. Everything after the front-end — verify, citation
counts, families, figure, spreadsheet — is the SAME shared machinery, run the
same way. There are no mode-specific shortcuts.

| Mode | Start from | User says… | Front-end | Then gather |
|------|-----------|-----------|-----------|-------------|
| **Topic** | a query/topic | "lit review on X", "extend the bibliography for Y" | Phase 1 (scope) → 2 (search) → **2b (antecedents)** | topic name + 1-paragraph definition, source doc if any, target spreadsheet path, tier criteria |
| **Lab** | a lab's publications | "review lab Z's work", "how has Z's research evolved" | Phase L1–L3 (ingest corpus → derive themes) → **L4c** (+ **2b antecedents**) | the lab/author ids, the inclusion filter (e.g. human-only), target paths |

**Phase 2b (antecedents) is required in both modes** — the forward search misses a
topic's methodological, empirical, and theoretical roots; do not skip it.

Both then converge on the shared pipeline: **Phase 3 verify → 3f canonicalize refs → 5 spreadsheet →
5b citation counts → 6 cross-citation → 6b families + timeline (offered every time; the user may
decline) → 7 review article (optional) → 8 hand-off.** Lab mode's
outward/contextualize layer (**L4c**) is not a lighter pass — it *runs the
topic-mode front-end (Phases 2–6) once per theme*, with the identical
verify/count/dedup guardrails. Topic mode is the next section; lab mode is under
"Lab mode" below.

---

## Output artifacts (per topic batch)

1. New rows appended to `<spreadsheet>.xlsx` with columns:
   `Topic | Ref# | APA reference | Link | Summary | Tag | Family | Cite (OpenAlex) |
   Cite (S2) | Verify note | PDF (local) | Xref` (`Family` / `Cite` / `Verify note`
   appear automatically once any row carries them).
   `Link` is always the DOI URL (`https://doi.org/<doi>`). `Family` (Phase 6b)
   and the two `Cite` columns (Phase 5b) are auto-added by `spreadsheet.py`
   whenever rows carry them.
2. `citation_counts.json` — per-paper OpenAlex + Semantic Scholar counts (Phase 5b)
3. `families.json` + `families.md`, and `<topic>_families.{html,svg,png,pdf}` —
   the theoretical grouping and its interactive timeline (Phase 6b, offered on every
   review; absent only if the user declined it)
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
- `{ALREADY_HAVE_LIST}` — bullet list of existing papers (don't rediscover)
- `{REVIEW_TITLE}`, `{LAB_NAME}`, `{SEARCH_QUERIES}`, `{RELEVANT_METHODS}`,
  `{DOMAIN_SPECIFIC_CATEGORY}` — the template's remaining placeholders; fill or
  strip each one (grep for `{` before sending)
- `{TODAY}` — current date (gives the agent a recency anchor)
- `{TIER_BOUNDARY_YEAR}`
- `{TARGET_COUNT}` — usually 25-40 papers
- `{OUTPATH}` — the lane file path the agent writes its JSON object to; put it
  inside a `search_raw/` directory beside `rows.json` (`search_raw/<lane>.json`),
  since Phase 2c's `merge_lanes.py --raw search_raw` reads every file there
- `{LANE_KEY}` — this lane's short key, used in `"lane"` and each `ref` prefix

The agent writes one JSON object (schema 2: `status`, `papers`, `deferred`,
`could_not_confirm`) to `{OUTPATH}`, per `search_prompt_template.md`. Keep each
paper's claimed first author, year and title as `search_author` / `search_year` /
`search_title`: they are what Phase 3 verifies against.

**With several lanes, no paper may fall between them.** The template already tells
each agent never to drop an on-topic paper because another lane might own it —
include it and name the lane it fits better (`lane_fit`), since the merge dedups on
DOI and arXiv id. Anything left out on purpose goes in `deferred`, with its
`first_author` and `year` (required), so Phase 2c's merge can confirm a deferred
paper by title alone. Do not cap DOI-less items per lane. Three recent builds lost
14, 6 and 4 papers at their seams, and each loss cost a recovery lane after the fact
— Phase 2c now catches this in code instead of relying on a session to notice.

**Do not act on the agent's output yet.** It will contain errors. Proceed
to Phase 2b, then Phase 2c, then Phase 3.

### Phase 2b — Antecedents (the foundations pass) — REQUIRED

The Phase-2 search is biased toward recent work and the topic's *current*
framing, so it systematically misses the literature the topic was built on. A
review that omits its antecedents reads as if the field began ~10 years ago. Run a
dedicated antecedents pass in both modes (contract rule 4), after the main search
and before verifying.

Spawn a separate search agent **per axis** for the topic's intellectual roots:

1. **Measurement / methodology origins** — the instrument, signal, or technique
   the work depends on, and the papers that established and validated it (e.g.
   for human-fMRI work: the BOLD mechanism, the first functional studies, what
   the signal actually measures).
2. **Foundational empirical results** — the classic findings the topic builds on,
   including older work in adjacent methods, species, or eras that the forward
   search's recency bias skips (e.g. single-unit neurophysiology, psychophysics,
   the first description of an effect or region).
3. **Theory / computational framework** — the conceptual claims that motivate the
   work (e.g. efficient coding, a normative principle, a levels-of-analysis
   framing).

Reuse `tools/search_prompt_template.md`, but **flip the tier emphasis**: the
target here is foundational / highly-cited / classic work that PRE-DATES the
modern literature, not recent papers. **Launch the antecedent lanes in the same
fan-out as the Phase-2 lanes**, not after them: the merge dedups on DOI and arXiv
id, so overlap costs nothing, and waiting costs a full search round. Give each agent
the already-have list (the seed list; add Phase-2 results only if they already
exist) so it does not re-find them, and have it tag
each paper with the best-fit **existing** theme/family. Antecedents fold into the
existing lanes by default — do NOT spin up new lanes for them unless the user
asks. Feed every returned paper through Phase 3 → 3f → 5b like any other.

**Old classics often have no DOI** (pre-2000 papers, books, book chapters). Keep
them as hand-written canonical APA `no-source` rows (references.py flags them;
the audit gate allows them) and exclude them from `citations.json` — the same
pattern as any DOI-less item. Beware reissue DOIs for old books (they re-date the
work to the reprint year); prefer a hand APA citing the original edition. Verify
each by title/author against the publisher or a library record before trusting
the agent's APA.

**Lab mode:** the antecedents include the lab's OWN pre-paradigm work — the
earlier-method, other-species, or pre-tool publications that the inclusion filter
(Phase L2) drops. Reconsider that filter: a lab's foundational pre-paradigm papers
are usually the most direct antecedent of its current program, and belong in the
corpus as `source=lab` (starred) rather than excluded.

**Effect on the figure:** antecedents widen the time span (often back to the
mid-20th century) while most papers cluster in the last decade. Set the figure's
`--min-year` to the earliest antecedent and add `--time-warp` so the sparse early
decades compress and the dense recent years expand — otherwise the modern
literature collapses into an unreadable clump at the right. See Phase 6b.

### Phase 2c — Merge the lanes (`tools/merge_lanes.py`) — a gate

Once every Phase-2 and Phase-2b lane has written its file into `search_raw/`:

```bash
python3 tools/merge_lanes.py --raw search_raw --out rows.json
```

It dedups by DOI, then arXiv id, then normalized title + year, and records the
other lanes that returned a paper (`also_lanes`). A title+year match alone is
only a hint, not a merge: it is treated as the same paper only when the lanes'
claimed author/year agree and the rows do not carry two *different* journal DOIs
(an arXiv preprint's DOI and its own journal DOI are the same paper and still
merge). When the hint fails that check, both rows are kept and reported as a
**possible pair** for a person to look at — the same warning the audit's
duplicate scan raises. After the merge, it also title-scores every pair of kept
rows (similarity ≥ 0.9, regardless of year or DOI) and lists any close pair as a
possible duplicate too — a second, corpus-wide check independent of the dedup
above.

**Every `deferred` entry must match a merged row**, by DOI, arXiv id, or title
(`common.title_match`: similarity ≥ 0.9, or each title's words ≥ 90% contained
in the other — a short title inside a longer one is not a match), confirmed by
the deferral's `first_author`/`year`. Every title-only match is printed for you
to check (`matched_by_title`). **`merge_lanes.py` fails on a lost deferral** — an
entry no lane's papers matched — and on an **unconfirmed** one — a title-only
match whose deferral gives neither `first_author` nor `year` — and exits 1: add
the missing fields and re-merge, or send the papers to one recovery lane, add
its file to `search_raw/`, and re-merge. It also fails on a **rejected**
paper — one with no DOI, no arXiv id and no APA string, which can be neither
verified nor hand-checked — reported the same way: give it a DOI or arXiv id,
or have the lane write its full APA string as a DOI-less item, then re-merge.
A failed merge (lost, unconfirmed or rejected) writes `merge_report.json` but
**not** `rows.json`, so nothing downstream runs on a table with a hole in it.
A lane that returned under 60% of its target, or ran out of search budget, is
printed as thin — resume it through SendMessage rather than re-spawning it.

**Later additions** (xref/forward candidates via Phase 6, a recovery lane after
Phase 2c itself) use `--append` instead, which never touches an existing row:

```bash
python3 tools/merge_lanes.py --append recovery.json --into rows.json
```

A schema-1 lane file (a bare array, from an old prompt) is refused with the
schema it expects, unless `--allow-v1` — in which case that lane's deferrals
cannot be checked and the merge says so.

### Phase 3 — Verify EVERY citation (CRITICAL)

In a previous run, the search agent fabricated 5 author lists, reversed
one paper's conclusion, and invented a bioRxiv DOI that didn't exist.
About 1 in 4 citations had errors. **Always verify before adding.**

`verify.py` returns one verdict per citation: **OK**, **MISMATCH** (first author,
year, or title), **NOT-FOUND**, **ERROR**, or **UNCHECKED** (the row carried no
claim to check, so a resolving DOI proved nothing — give it one). NOT-FOUND and ERROR are NOT the same and must be
handled differently: NOT-FOUND means every lookup completed and none matched
(chase it down — likely fabricated); ERROR means a lookup could not complete
(rate-limit / network), so **re-run those** rather than treating them as missing.
On a big run this matters — arXiv rate-limits hard, so the tool prefetches all
arXiv ids in batches (many per `id_list` call); a genuinely real preprint that
would otherwise 429 into a false NOT-FOUND now comes back OK (or, if the batch
still fails, ERROR to re-run).
The same discipline applies to the title-search fallback: when the DOI/PMID lookup
errored and the fallback title search returns a record that does not match the
claim, the verdict is ERROR, not MISMATCH (on a 588-row run ~30 throttled CrossRef
calls each surfaced an unrelated PubMed paper and looked like agent fabrications).

`verify.py` exits **0 only when every verdict is OK** — the same fail-loud
contract as the audit gate and `cite_check.py` — so a chained Phase-3 run stops
on a table that still needs attention.

Feed it the live table directly — `python3 tools/verify.py --rows rows.json --out
verify_report.json`. **Keep each search agent's claim on its row** as
`search_author` / `search_year` / `search_title` (the row template does). Before
canon, `apa` is empty, so those fields ARE the expectations; after canon (a row
stamped `canonical_at`) they still are, and the canonical `apa` must agree with the
record as well. Do not write a per-project
converter script: fourteen projects did, each with its own first-author regex, and
five more wrote `make_verify_input.py` because the `apa`-only path verified nothing.

What a verdict checks: the first-author surname (fuzzy containment), the year
(±1, since a preprint and its version of record differ), and the **title**
(similarity ≥ 0.5, which on 2,473 past OK verdicts flagged exactly one: a preprint
retitled on publication). A row with **both** an arXiv id and a journal DOI has
both checked, because canon cites the journal DOI: a wrong DOI beside a right
arXiv id is a MISMATCH. The same holds for PubMed and PMC ids: **a journal DOI is
verified only by its own CrossRef record.** A row with a PMID/PMCID and a DOI is
checked against the DOI's record; a DOI that does not resolve is a MISMATCH ("DOI
... does not resolve; pmid found ...") even when a PubMed or title search finds the
claimed paper — a real title with a fabricated DOI once verified OK that way. Canon
reports a DOI CrossRef does not have (404) as "DOI does not exist", not as a fetch
failure to retry.

**Retries are built in.** An ERROR row gets a second try at the end of the run
after a 60 s cool-down (`--retry-wait`), with smaller arXiv batches. Anything still
ERROR is re-checked later with `--retry-from verify_report.json --out
verify_report.json`, which re-verifies only the non-OK rows and splices the new
verdicts into the report; `--only A-01,B-02` names rows explicitly. Never build a
rerun input file by hand.

**`--rows` stamps the row, not just the report.** Each checked row gets a `verified`
field (verdict, DOI/arXiv id, source, issues, date), so canon and the audit gate know
what was checked and against which ids without re-reading `verify_report.json`
(`--no-stamp` reports without writing). A false alarm a human clears — a preprint
retitled on publication, say — is recorded with `verify.py --rows rows.json --override
REF --reason "..."`; it is refused without an existing stamp, without a reason, or if
the row's DOI/arXiv id changed since it was verified.

**Start verifying before the last lane lands.** Lanes finish minutes apart; run
verify on each lane's rows as they arrive (`--only`), and dispatch the DOI-less
hand check (Phase 3e) as soon as those rows exist, instead of after the merge.

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

**Hand-checking references with no DOI or arXiv id.** A book, report, thesis or web
essay cannot be machine-verified, so a gated table needs a recorded hand check
instead — the audit fails a DOI-less row without one. `tools/handcheck.py --prepare`
searches CrossRef and OpenAlex for a DOI the row turns out to have (the same title
by `common.title_match`, not merely contained in a longer one, and the same year) and writes the rest as a hand-check input plus a brief;
`--adopt-dois` gives a row with exactly one candidate DOI that DOI, so it goes
through `verify.py` like any other reference (a row with several candidates is left
alone and named); `--ingest` records each checked row as `hand_verified` —
`confirmed`, `corrected` (with the corrected APA), or `not-found` — with the source
actually checked (a library catalog, the publisher's page, the post itself; never
another paper's citation of it). Dispatch this as soon as a lane's DOI-less rows
exist, alongside verify (see "Start verifying before the last lane lands" above).

Common fabrication patterns to flag:
- Author name that doesn't appear in any of the paper's actual authors.
- Conclusion that is the OPPOSITE of the paper's actual finding.
- A DOI that does not resolve, or that resolves to an unrelated paper (agents
  invent plausible DOIs and also mis-copy real ones — confirm the *target*, not
  just that it resolves).
- arxiv preprint IDs that don't resolve.

**Don't treat an unfamiliar DOI shape as fabrication evidence — resolve it.**
Prefixes and suffix formats drift, so a DOI not matching the shape you expect is
often just a newer pattern, not a fake. Seen in real builds: bioRxiv now issues
`10.64898/...` DOIs alongside the older `10.1101/...`; Imaging Neuroscience uses
`10.1162/imag.a.NNNN` (dots, not the `imag_a_NNNNN` underscores you might guess —
the wrong shape 404s). Always judge a DOI by what it resolves to, never by its
string.

### Phase 3f — Canonicalize EVERY reference (`tools/references.py`)

Verification (3a–3e) confirms a citation is *real*; this makes its `apa` string
*perfect* (contract rule 2). Never ship a reference typed from an agent's memory
(topic mode) or OpenAlex's light metadata (lab mode) — rebuild every `apa` from the
verified DOI against the authoritative source. `references.py` is the single
canonical formatter and a hard gate, used identically in both modes:

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
defect (missing author/year, `et al.` **in the author list**, HTML entity, `U+FFFD` replacement-char
mojibake, truncated/empty venue, uppercase title, **JATS/HTML markup left in a
title** (`<scp>`, `<i>`), **a `?.` or `!.` double terminal punctuation**, **a
U+2010/U+2011 Unicode hyphen in a name**, **a `?` standing in for a quote or dash
(`mangled-punct`)**, **words fused by stripped JATS tags (`missing-space`,
`cockroachPeriplaneta`)**, and **a hyphenated given name deposited with its second
part missing (`Poline, J. -.`, a second `malformed-initial` shape)**; it warns on a
**footnote digit glued to the last title word (`glued-footnote`, `psychological
science1`)**). The ONLY allowed non-fatal
case is a DOI-less item (book, report, old proceedings) — it keeps its
hand-written `apa` and is reported as a
manual ref; verify those by hand. **Run the gate before every deliverable.**

**Canon's refusal to rebuild an unverified row is unconditional.** It rebuilds only
rows verified for their current DOI/arXiv id — on EVERY table, including one built
before the reference gates existed. A row whose ids changed since verification, or
that was never verified, keeps its existing `apa`, is named, and the run exits 1;
re-verify those rows first (`verify.py --rows rows.json --only A-01,B-02`), then
re-canon. Re-canoning rows of an old corpus with `references.py --only ...` needs the
same `verify.py --rows ... --only ...` pass first — see "Upgrading an old corpus"
below for bringing a whole legacy table up to date at once.

**Acknowledging warnings.** Some audit findings need a human verdict, not a fix — a
possible duplicate that turns out to be two distinct papers, a summary with no
abstract to check it against, a multi-word surname that is genuinely compound. On a
gated table, an unacknowledged warning fails the audit just like a defect. Record the
verdict in `audit_acks.json` beside `rows.json` (`{ref: {warning_id: "why this is
fine"}}`); `references.py --list-acks` prints every unacknowledged warning as
`REF<TAB>WARNING_ID<TAB>TEXT` so you can build the file from it. `--list-acks` only
lists — it exits nonzero when a warning is unacknowledged, never on a defect;
`--audit` is the actual gate. A stale acknowledgment (the warning it named no longer
applies) is reported, not failed; delete it.

**arXiv is read in batches.** Canon prefetches every arXiv-routed id 50 per request,
3 s apart (`common.arxiv_batch`, shared with verify). Until 2026-09-25 it sent one
request per row, and a 475-ref arXiv-heavy build spent most of 53 minutes asleep in
429 backoff; the
same fetch is now about 30 s. A row whose fetch fails gets one more try at the end
of the run (`--retry-wait`, default 60 s); a row that still fails is **named, not
stamped, and the run exits 1**, because its `apa` is not canonical. A row whose
source answers with no usable record (an author-less editorial, an id missing from
the feed) keeps its existing `apa` and is named as a warning — confirm it by hand.
**Targeted re-canon is a flag:** `--only A-01,B-02` rebuilds those rows and leaves
every other row byte-for-byte as it was, so a splice script is never needed.

Four things the gate reports as **warnings**, because none can be decided
automatically: a near-duplicate row pair; a **multi-word surname** that may be
a mis-split given name; a **deposit-year conflict** (the DOI encodes a different
year than the reference — publisher back-file digitization re-dates old papers);
and a **cached `year` field that diverged from the apa** (fix whichever is wrong,
or delete the stale cache). `Lambon Ralph` is a real compound surname and `Thomas Yeo`
is CrossRef folding B. T. T. Yeo's given names into the family field; they are
indistinguishable to a machine, so each needs a human verdict. (A *leading initial*
in a family field — CrossRef's `family="A. Moffat"` — IS unambiguous and is now
repaired automatically, since no surname begins with an initial.)

**Sentence-case titles after canon with `tools/sentence_case.py`.** Strict APA-7
wants sentence case, and canon deliberately does not impose it (see Lessons). The
tool proposes, you review, then `--apply`. Keep the corpus's proper nouns in a
per-project `--proper` allowlist file so a generic word lowercases while a named
entity does not (`yoga practitioners` but `Sahaja Yoga`). On a large corpus use
`--vocab` to review the ~N distinct token changes rather than 150 title diffs — a
mis-cased proper noun is obvious there and invisible in a long diff.

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

| Topic | Ref # | APA reference | Link | Summary | Tag | Family | Cite (OpenAlex) | Cite (S2) | Verify note | PDF (local) | Xref |
|-------|-------|---------------|------|---------|-----|--------|-----------------|-----------|-------------|-------------|------|

(`Family` appears only after Phase 6b, and the two `Cite` columns only when
Phase 5b has populated them.)

- `Topic`: one of the project's topic categories (e.g. "Multimodal networks").
- `Ref #`: numeric for source-document refs; use `<topic-letter><n>` for
  added refs (e.g. `M1`-`M40` for first multimodal batch, `M41`-`M70` for xref
  batch). Keep numbering monotonically increasing across batches.
- `APA reference`: the canonical `apa` from Phase 3f — full author list (APA-7:
  up to 20; 19 + ellipsis + last beyond that). Never `et al.` in the author list;
  the audit gate
  fails on it.
- `Link`: DOI URL in `https://doi.org/<doi>` form — verified to resolve.
  PubMed/PMC URLs are NOT used as the primary link. If a paper has only a
  PMID/PMCID, look up its DOI before adding the row.
- `Summary`: 3-5 sentences. State what the paper did and why it matters for
  the topic. Don't just paraphrase the abstract.
- `Tag`: see Phase 2 list.
- `PDF (local)`: relative path if downloaded, else empty.
- `Xref`: citation count from cross-reference analysis (Phase 6), else empty.

**Color-code rows** so origin is visible (`source` field; the rules live in
`spreadsheet.py`'s `COLORS`, and an unknown value renders white with a warning):
- White: refs from the source paper (`source-doc`).
- Cream `#FFF7E0`: refs added in the search passes (`search`).
- Green `#E2F0D9`: refs added via cross-citation analysis, Phase 6 (`xref`).
- Blue `#DDEBF7`: the lab's own papers in lab mode (`lab`).
- Lilac `#F3E6F5`: Phase-2b antecedents (`anteced`; `anteced-nosrc` for
  hand-cited classics with no DOI).

`tools/spreadsheet.py` does the rebuild from a JSON of rows: it freezes the
header, sets the column widths and 110-pt row heights, and adds the `Family` and
`Cite` columns when the rows carry them.

**The spreadsheet is the release gate (contract rule 9).** `spreadsheet.py` runs the
same audit as `references.py --audit` (verify stamps, hand checks, summary checks,
acknowledged warnings) and refuses to write a failing gated table. Pass `--draft` to
write one anyway, as `<out>_DRAFT.xlsx` with a red banner naming the failure count —
never hand that file off as the deliverable. A candidate ledger entry marked
`"decision": "exclude"` gets its own "Considered and excluded" sheet. A row with a
checked summary carries a "Summary checked against" column, naming the abstract
source or "no abstract".

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

Citations and xref (Phase 6) read only DOIs, so start both in the background as soon
as verify's DOI corrections are applied, while canon runs; none of the three waits on
another. S2 is queried 500 ids per request; a 400 stops S2 for the run (it never
recovered on retry in any logged build) and OpenAlex counts stand.

Then attach the counts to each row (`cite_openalex` / `cite_s2` keys) in your
`build_data.py`/rows pipeline and rebuild — `spreadsheet.py` auto-adds the two
`Cite` columns when it sees them. Counts are a snapshot at run time; re-run to
refresh. Papers with no DOI (books, blog/tech-report releases) stay blank.

**Per-version data scripts:** if you split batch data across importing Python
files, guard the xlsx-writing block under `if __name__ == "__main__":` so an
import doesn't rewrite the spreadsheet as a side effect — or just keep all rows in
one JSON and rebuild via `tools/spreadsheet.py` (the simpler path; see Lessons →
On the spreadsheet).

### Phase 5c — Abstracts and the summary check

A summary can drift from what a paper actually found, the same way a citation can be
fabricated, so check it the same way: against an authoritative record, by an agent
that cannot see anything but that record.

```bash
python3 tools/abstracts.py --rows rows.json --email you@inst.edu
python3 tools/summary_audit.py --rows rows.json --prepare
# dispatch one checking agent per summary_audit/batch_NN.json; brief: summary_audit/brief.md
python3 tools/summary_audit.py --rows rows.json --ingest
```

`abstracts.py` fetches every row's abstract once, from the most authoritative source
that has it — the arXiv API for arXiv papers, then OpenAlex, then Semantic Scholar,
then PubMed — into `abstracts.json`. Each entry records the `doi` and `arxiv` it was
fetched for, so an abstract stays bound to its paper: when a row's ids change, its
fetched entry is fetched again, and `summary_audit.py --prepare` refuses any entry
recorded for other ids. A hand-added entry (`"source": "landing-page"`, which must
carry the row's `doi`/`arxiv`) is never overwritten; if its ids no longer match the
row it is reported as stale for you to fix. A fetch failure is reported separately
from a genuine no-abstract miss and written to `abstracts_failed.json`;
`summary_audit.py --prepare` refuses those rows (exit 1) instead of filing them as
"no abstract" — re-run `abstracts.py`, or add a landing-page entry.
`summary_audit.py --prepare` splits the rows needing a check into batches of 40 (`--batch`) with each summary and its abstract, plus a brief; dispatch
one checking agent per batch, with no web access — it judges only whether the
abstract supports the summary, "supported" or "unsupported" with the unsupported
clause quoted exactly. `--ingest` records the verdict as `summary_check`, with the
row's ids and a hash of the abstract it was checked against, keyed to a hash of the
summary text (a check recorded for other ids counts as unchecked), so a summary edited after `--prepare` is refused, and an
edited summary is re-flagged as unchecked rather than trusted on its old check. A row
with no abstract is recorded as `no-abstract` — a warning the audit makes you
acknowledge (see the acknowledgments note under Phase 3f). A flagged summary is a
defect: fix it and run `--prepare` again.

### Phase 6 — Cross-citation analysis (second pass)

Run after Phase 5 is committed. The point: find high-impact papers the
initial search missed, both by what the papers we DO have cite repeatedly
(backward, `xref.py`) and by what cites our own landmark papers (forward,
`forward.py`). Every paper either pass suggests gets a recorded decision
(`candidates.py`) — the audit gate fails while any candidate is still pending.

**6a. Backward: fetch reference lists (`tools/xref.py`).** For each paper with a
DOI, call CrossRef: `https://api.crossref.org/works/<doi>`. The
`message.reference[]` field has the cited refs. For an arXiv DOI, and for any
paper whose CrossRef record has no reference list, xref asks **Semantic
Scholar** instead (`paper/batch` with reference ids, chunked; `paper/{id}/references`
paged for long lists) — set `S2_API_KEY`. A cited arXiv id is normalized to
`10.48550/arxiv.<id>` so it matches a corpus DOI. A probe on 2026-09-25 found
reference lists for 16 of 20 sampled arXiv papers this way (OpenAlex had 4 of
39). A paper whose references could not be fetched makes the run **incomplete**
and xref exits 1, same as a genuine fetch failure — pass `--allow-incomplete`
to accept a partial table (it says so in its output) rather than re-running
immediately.

```bash
python3 tools/xref.py --rows rows.json --out xref_<topic>.json --min-cites 4 \
        --resolve-unknown --internal-out internal_citations.json
```

**6b. Build the frequency table.** For each cited DOI, count how many of your N
papers cite it — `xref.py` does this as part of the same run above, and retries
an incomplete CrossRef fetch once at the end of the run before it reports the
table as undercounted.

**6c. Resolve unknowns.** `--resolve-unknown` looks up titles for top-cited DOIs
that came back with no title/author (many cited refs have only a DOI in the
CrossRef response).

**6d. Forward: papers citing our landmarks (`tools/forward.py`).** Picks the
corpus's landmarks (top 30 by within-corpus in-degree — from
`--internal-out` above — then citation count), asks OpenAlex for the most-cited
papers citing each one (up to 200 per landmark), and scores each citing paper
by how many corpus papers it also cites. A citing paper that cites at least 3
corpus papers becomes a candidate. Because each pull is ordered by citation
count, very recent papers are under-represented — the output says so. A
corpus row with no DOI (or whose OpenAlex id lookup failed) cannot be excluded
from the candidates, so it may reappear as its own "candidate"; check by hand.
A landmark whose pull failed makes `forward.py` exit 1 (its citing papers are
missing from the candidates); re-run it, or pass `--allow-incomplete`.

```bash
python3 tools/forward.py --rows rows.json --out forward_candidates.json
```

**6e. Every candidate gets a recorded decision (`tools/candidates.py`).** Add
both passes' results to one ledger, decide each with a reason, and export the
included ones as a lane file:

```bash
python3 tools/candidates.py --rows rows.json --add xref_<topic>.json --source xref
python3 tools/candidates.py --rows rows.json --add forward_candidates.json --source forward
python3 tools/candidates.py --rows rows.json --list pending
python3 tools/candidates.py --rows rows.json --decide 10.1038/xxxxx \
        --decision exclude --reason "methods paper, not on topic"
python3 tools/candidates.py --rows rows.json --export-included xref_lane.json --lane X
```

Aim for ~25-35 *included* additions per pass. More than that and the spreadsheet
becomes unwieldy; less and you've under-mined. The excluded ones are not
discarded — they stay in `candidates.json` with their reason, and
`spreadsheet.py` lists them on a "Considered and excluded" sheet, so a paper
missing from the review is visibly one that was considered. The audit gate
fails while any candidate is pending, or while an `include`d candidate is not
actually in the table. Each `--add` also records the run in the ledger
(`_runs`: source, date, count), and on a gated table the audit warns
`no-xref-run` / `no-forward-run` under `*` until both passes have been added —
acknowledge one only if this review genuinely skipped that pass.

**6f. Repeat Phases 3, 3f and 5b** for the new batch: `merge_lanes.py --append
xref_lane.json --into rows.json` adds the exported rows without touching any
existing row, then `verify.py --rows --only <new refs>`, `references.py`, and
`citations.py` bring them up to the same standard as every other row (with the
green color and Xref column populated).

### Phase 6b — Families and the timeline (offered on EVERY review)

The lineage timeline is the deliverable users find most useful, so **always offer
it — do not wait to be asked.** It needs the papers grouped into a few **theoretical
families** — a conceptual axis *orthogonal to the Topic column* (Topic captures
method/sub-area; families capture what each paper is fundamentally *for*). Adds a
`Family` column, a `families.md` (grouped tables + a family×topic cross-tab), and the
timeline. **Pitch the families as soon as the rows are verified (after Phase 3),
not after xref.** The proposal needs only titles and summaries, and the user's reply
is the one human wait in the run: let canon, citations and xref run in the
background while they decide. Rows that xref adds later join the same assignment
batch (`families.py` fails loud on any unassigned row). On a 475-ref build the pitch
came last, and 56 minutes passed between the pitch and the finished figure.

The user's one decision is at step 2, and it covers the timeline too: **use the
proposed families, change them, or skip the timeline.** Everything after that runs
without stopping; the mechanical part is owned by `tools/families.py` and
`tools/families_figure.py`:

1. **Propose** (agent, reading the corpus via `tools/families.py --digest`):
   propose ~3-8 families, each `{key, name, claim, lineage}`, and state the one
   organizing principle. The hard constraint: families must cut *across* the
   Topic lanes — a good family unites textually-dissimilar papers and splits
   similar ones. **Do NOT cluster embeddings** to make families; that yields
   surface-similarity groups, not theoretical ones. Use the prompt in
   `tools/family_prompt_template.md`.
2. **Pitch** — offer the timeline and show *just the ~6 family definitions* it would
   be drawn from (name + one-line claim each). Ask the user to pick one of three:
   **use these**, **change them** (iterate on the definitions until they approve), or
   **skip the timeline** (then stop Phase 6b: no `Family` column, no figure, and say
   so at hand-off). This is the cheap, high-leverage checkpoint: iterating on six
   definitions is free; redoing the assignment is not.
3. **Assign** — against the frozen spec, assign every paper to one family
   (dominant commitment). Assign in batches for large corpora; never one rushed
   250-paper pass. Write `families_input.json`
   (`{principle, families, assignments:{ref:key}}`).
4. **Validate + render:**
   ```bash
   python3 tools/families.py --rows rows.json --assign families_input.json \
           --out families.json
   ```
   It enforces exhaustive / exclusive (fails loud otherwise; imbalance — one family
   holding >60%, or a singleton — is only a stderr warning, so read it), stamps
   `family` onto rows.json, writes `families.json` (the reproducible cache, like
   `citation_counts.json`) + `families.md`, and `spreadsheet.py` auto-adds the
   `Family` column on the next rebuild. Re-run only when the taxonomy changes.

5. **Render the timeline** — an interactive HTML (not a static png), produced by
   `tools/families_figure.py` from `rows.json` + `families.json`. The standard settings
   are its defaults: dots sized by citation count, `internal_citations.json` (from the
   Phase-6 `xref.py --internal-out`) read from beside `rows.json`, and the exact
   arguments written to `figure_render_args.txt` when that file is missing (an existing
   one holds tuning notes and is never overwritten; the tool says when a render is not
   recorded in it):

```bash
python3 tools/families_figure.py --rows rows.json --families families.json \
        --out-prefix <topic>_families --title "<Topic> — theoretical families"
```

   Add `--time-warp 0.85` when the corpus spans many decades (it usually does after the
   antecedents pass), and read the "qualified / labeled / dropped" line it prints.

It writes a self-contained `.html` (family lanes with their defining sentences,
every paper as a dot beeswarm-packed by year, landmark studies as big labeled dots;
hover any node for its full reference, click for citation + DOI, **hover or focus a
family's NAME for a panel giving that family's claim and its full lineage** while its
papers are spotlighted) plus a standalone `.svg` and — if `rsvg-convert`/`inkscape`
is present — `.png` + `.pdf` for slides/papers. This replaces the old static figure.

**Dots are sized by citation count (`--size-by-citations sqrt`) — standard since
2026-09-19 and the default since 1.14.0.** `--size-by-citations none` gives binary dots
(big = labeled landmark, small = the rest), which say nothing about how much a paper
is actually cited. `sqrt`
is area-proportional and is the one to use; `log` reads flat. Both normalize against
the 95th percentile and clamp above it, because counts span four orders of magnitude
and one runaway classic otherwise flattens the rest. Landmark status moves entirely
onto the ring, leader line and label. Papers with no citation count draw HOLLOW, not
at the floor — "unknown" is not "zero" (see Lessons). The figure gains a size legend
automatically.

**Next/Prev walks each year's column top to bottom.** All papers of one year share an
x, so a year is a vertical column; the walk-through tie-breaks on the dot's own drawn
y. Nothing to configure — but if you touch the ordering, re-run
`verify_nav_order.mjs` (project root), which executes the figure's own sort against
its own data.

**Write the family `claim` as prose and let the figure clamp it.** The lane label
draws the claim under the family name, and until 2026-09-18 nothing bounded how many
lines that was — a claim of a few hundred characters ran straight through the NEXT
family's title and drew on top of it. Since the full claim is now one hover away,
the drawn copy is clamped to the room the lane actually has and ellipsized
(`claim_lines()`). So write the claim for the reader who hovers, not for the
40-character column: the figure will show as much as fits and no more.

**The hover panel sits ON the lane legend, not beside it.** Anchored to the label's
right edge it landed over the start of the plot and hid the earliest papers — on a
density-warped axis, exactly where the foundational work sits. It is now anchored to
the label's LEFT edge and sized to the legend band (`r.right - r.left`), minus a
small inset, with a 240px readability floor for narrow windows. Width is applied
before `offsetHeight` is read, or the vertical clamp measures the old width.

**An SVG `<g>` is not hoverable — give it a hit target.** A `<g>` has no geometry of
its own and `<text>` only receives pointer events on the rendered glyph strokes, so a
handler bound to the lane-label group fires when the cursor is exactly on a letter and
nowhere else. That reads to a user as "the hover does not work", which is how it was
reported. Every node group already carried an invisible
`<circle class="hit" fill="none" pointer-events="all">` for this reason; the lane label
now carries an equivalent transparent rect over its whole left-margin band. The same
trap applies to any future affordance attached to SVG text.

**The family definitions must be readable FROM the figure.** `families.json` has always
carried each family's `claim` and `lineage`, but until 2026-09-18 the figure drew only a
truncated claim beside the lane name and never showed the lineage at all — so the one
artifact a reader actually opens could not tell them what a family *meant*, and they had to
go find `families.md`. Hovering or focusing a lane title now opens a panel with the claim,
the lineage and the family's paper count. The exported `.svg`/`.png`/`.pdf` carry the same
text in a native SVG `<title>`, because no JavaScript runs there. Nothing to configure —
write a good `claim` and `lineage` into the family spec and the figure surfaces them.

**Landmark labeling is AUTOMATIC — do not hand-build a labels overlay.** A paper is
labeled as a landmark (big dot) if ANY of: (1) it is among the **most-cited in its
family** (top `--per-family`, default 4, by max(OpenAlex, S2)); (2) it is **foundational
within this review** — cited by ≥ `--motif-min` (default 3) of the corpus's own papers
(this is criterion (2) and needs `internal_citations.json` from `xref.py --internal-out`,
read from beside `rows.json` automatically; skipped if absent — so emit it in Phase 6); or (3) it is a **home-lab
paper** — an author surname listed in `--lab-author` or the `LITREVIEW_LAB_AUTHOR` env
var, or a row with `source=="lab"` — these are **starred (★) and gold-ringed** so the
lab's own work stands out. Total labels are capped at `--max-labels` (default 28); what
survives the cap is the home-lab papers plus the top-2 most-cited per family, with the
rest of the budget filled by within-review in-degree.

**Raising a cap must never REMOVE a label that was already shown.** The obvious fix
for a capped figure — raise `--motif-min` until the qualified set is small enough to
label in full — can silently drop papers the capped figure was already showing,
because a higher threshold shrinks the *qualified pool*, not just the cap. On
structure_representation, going to `--motif-min 10` lost Smolensky 1990, Schuck 2016
and Liu 2019 (in-degree 8-9): the old cap had been selecting them by in-degree from a
much larger pool, and the new threshold put them outside it. Tune by measuring the
before/after label sets, not by reasoning about the numbers: pick the highest
`--motif-min` at which the diff shows **zero removals**, then set `--max-labels`
above the resulting qualified count so the cap never binds. Six figures were retuned
this way on 2026-09-19 (+72 landmarks, 0 lost).

**`--motif-min` does not scale with corpus size, so watch the drop count.** The default
of 3 is tuned for a ~50-paper review. On a 396-paper corpus whose papers cite each other
heavily, 175 papers cleared it and the cap silently discarded 147 of them — a figure
that reads as "here are the landmarks" when it is really "here are 28 of 175". The tool
now **prints how many qualified and how many were dropped** on every run. If that number
is large, raise `--motif-min` (25 was right for 396 papers) rather than letting the cap
choose for you.

> **Home-lab favoring is OFF by default** — this is a shared, lab-neutral toolkit, so
> criterion (3) does nothing until you opt in. Turn it on per project by passing
> `--lab-author Surname` (repeatable), or set it once for your environment with
> `export LITREVIEW_LAB_AUTHOR=Surname` (comma-separated for several surnames). The CLI
> flag overrides the env var. Rows tagged `source=="lab"` (from Lab mode) are always
> starred regardless of the switch.

**Time axis.** `--min-year` clamps the axis start (older papers pin to the left edge).
When the corpus spans many decades but is recency-heavy — the usual shape after a
**Phase-2b antecedents pass** — add `--time-warp <0–1>`. It blends the linear axis with
the empirical CDF of all paper years, GLOBALLY (not per-region): sparse early spans
compress, dense recent spans expand. `0` = linear, `1` = full density-equalizing; **~0.85**
keeps old foundations legible while decluttering the modern clump. Faint gridlines mark the
labeled years so the nonlinear scale stays readable. Always note the nonlinear axis in the
figure caption (independence principle).

**Only the editorial *arrows/notes* remain a human checkpoint** (cross-family convergence
arrows and annotations are judgment). Curate those via an optional `--spec figure_spec.json`
(`{arrows:[{from,to,color,label}], notes:[{at,text,color}], order, subtitle}`); a `labels`
map there still overrides auto-selection if you ever need to force a specific set. Don't
expect a good arrow set auto-generated.

### Phase 7 — Write the review article (OPTIONAL)

Turn the finished corpus into a narrative **review article** as a `.docx`. Run only when
the user asks for a written review (not for the bibliography itself). Prerequisites: Phase 3f
(canonical `apa`) and 5b (counts) are done. Phase 6b's families and timeline normally exist too
(they are offered on every review): the families are the natural section structure, and the
timeline is the review's figure.

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

**Concision pass (required before delivering; `tools/prose_audit.py`).** A model-written review
is rarely wrong and often unreadable, and the defect is always the same one: four or five findings
chained through semicolons into a single 60–120 word sentence, each clause carrying its own
citation. Every fact is right, the citations all resolve, and no reader can follow it. `cite_check.py`
cannot see this, because it only asks whether the citations resolve.

Measure before rewriting, because "wordy" is a number:

```bash
cp build_review_page.py /tmp/before.py         # or: cp content.json /tmp/before.json
python3 tools/prose_audit.py --page build_review_page.py            # diagnose
#   ... revise ...
python3 tools/prose_audit.py --page build_review_page.py --baseline /tmp/before.py   # GATE
```

Aim for a **mean sentence of ~24 words** with almost nothing over 50; a first draft typically
lands near 31 with dozens of 50-plus sentences. The rewrite is mechanical once the long sentences
are listed: give each finding its own sentence and cut the semicolon chains. On a 555-reference
review this moved the mean 31 → 24 and sentences of 50+ words 54 → 8, for a 3.8% word saving —
the gain is in followability, not length, and the two should not be confused.

**A concision pass silently drops citations, so it needs its own gate.** Rewriting a
five-clause sentence into three is exactly how a reference falls out of the works cited, and
nothing downstream notices: the renderer prints what it is given and the reference list is built
only from what remains cited. `prose_audit.py --baseline` compares the distinct-citation set
before and after and exits 1 if any reference was lost. Keep the pre-revision copy outside the
project (it is a temporary, not a deliverable).

**Two sections resting on the same references are telling the same story twice.** `prose_audit.py`
reports block pairs sharing 8+ citations. On the cortical-layers review the humans/species section
and the laminar-fMRI comparison shared **35** — the fMRI case was argued in full in both places.
Folding one into the other cut 372 words and, because every one of its 27 references was cited
elsewhere too, lost nothing from the works cited. Check that before cutting, not after.

**Respect the temporal order of ideas — distil the intellectual history, do not force refs into
the narrative (contract rule 5; confirmed by user 2026-06-13).** The single most common failure of an
AI-written review is crediting the wrong paper for an idea: it picks whichever citation fits the
sentence it wants to write, rather than the paper that actually established the idea first. When a
sentence makes an **origin claim** — signalled by *emerges, first, established, identified,
introduced, was mapped, showed that, had been, early work, foundational, began, demonstrated,
discovery* — it MUST cite the **earliest** paper that deserves priority, and order multiple
citations oldest-first. Four recurring inversions to watch for (each example is a real miss caught
2026-06-13):
- crediting a later **review** for a finding an earlier **primary paper** made (e.g. Tanaka 1996
  review vs. Desimone et al. 1984 for object/face selectivity in IT);
- crediting a later **model/normalization/synthesis** for a phenomenon earlier **empirical** work
  established (e.g. Reynolds & Heeger 2009 model vs. McAdams & Maunsell 1999 for attention changing
  gain/tuning);
- crediting a later, narrower paper while ignoring an earlier, **more general** one from the same
  year (e.g. Dumoulin & Wandell 2008 pRF vs. Kay et al. 2008's more general per-voxel model);
- in **lab mode**, relegating the lab's OWN foundational paper to a later section while a follow-up
  from another group gets the priority slot (e.g. Hegdé & Van Essen 2000 vs. Gallant et al. 1993
  for complex-form selectivity in V4). The lab's antecedents (Phase 2b / L4c) exist precisely so
  the review can assign priority correctly — use them.

**Priority audit (before delivering the review; contract rule 5).** After drafting `content.json`, run a
dedicated audit pass — analogous to the Phase-3 citation verify and the Phase-2b antecedents pass.
Dispatch one agent with the draft prose plus `rows.json` (which carries every candidate paper and
its `year`) and instruct it to: scan every origin-claim sentence; for each, check whether an
**earlier** paper in `rows.json` (or an undisputed classic) deserves priority for that specific
idea; and report each inversion as `claim → currently cites (year) → earlier source (year) → fix`.
Apply the confirmed fixes (reorder citations oldest-first, add the originating paper, demote the
later review/model to "later", and adjust wording so the sentence reads as history not narrative).
This pass catches what self-review misses because the drafting model is biased toward its own story.

**Mechanics — `tools/review_paper.py`.** The tool owns only the mechanical render; it does not
write prose. It reads `rows.json` and builds the **APA-7 reference list straight from the
canonical `apa` strings** (deduped, in APA-7 order — authors, then year, then title — hanging indent, with DOI links), embeds the
families figure with a standalone caption, and lays out the title/author/disclosure block + the
abstract + sections. Keep the prose in a small per-project emitter that dumps `content.json`
(see the schema in `review_paper.py`); render with the shared tool:

```bash
python3 write_review.py            # project file: authors prose -> content.json
python3 tools/cite_check.py --rows rows.json --content content.json   # GATE: exits 1
python3 tools/review_paper.py --rows rows.json --content content.json \
        --figure <topic>_families.png --out <Topic>_review.docx
```

**`cite_check.py` is a gate, not a nicety.** The renderer prints whatever prose it
is given, so a citation naming no row in `rows.json` ships silently and the reader
cannot follow it. The tool also warns when one author-year matches TWO references —
on a 396-row corpus that happened five times (two Hölzel 2011s, two Kral 2022s, two
Yang 2025s, two Haudry 2025s, two Gusnard 2001s). Fix those with **APA-7 §8.19**:
name enough subsequent authors to distinguish them, `(Kral, Davis, et al., 2022)`.
The other APA disambiguator, a `2025a`/`2025b` year suffix, is accepted by the audit
gate but means editing the canonical `apa` strings, so it usually costs more.

The reference list comes from `rows.json`, so it is automatically canonical and complete; verify
by opening the `.docx` and confirming the figure renders and the section/citation structure reads
correctly. Worked example: `distributed_conceptual_network/` (`write_review.py` + `content.json`
→ an AI-authored review with all 370 refs in APA-7). Output artifact:
`<Topic>_review.docx` (plus the project's `content.json`).

### Phase 8 — Hand off

Tell the user:
- Total rows in spreadsheet, broken down (source / search / xref).
- The timeline (`<topic>_families.html`, open it in a browser) and its families — or,
  if the user skipped it, that it was offered and declined.
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
several `--author` ids for PI + key lab members, **or for one person whose record
is split across ids**). Output `lab_papers.json`. `--search` prints each
candidate's ORCID and publication year span and warns on the failure shapes that
are visible from the listing alone — read those rather than picking by
institution, which is wrong more often than it is right (see L2).
Every row carries a `built_at` date, so the table is gated from the start: after
L2, run `tools/verify.py --rows lab_papers.json` before `tools/references.py`
(canon refuses unverified rows, and the audit and spreadsheet fail them).

**Phase L1b — enrich abstracts (REQUIRED).** OpenAlex metadata is not enough:
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
**But do not let the inclusion filter discard the lab's foundational pre-paradigm
work** (the macaque physiology, the pre-tool methods papers): those are the lab's
own antecedents and should re-enter as `source=lab` (starred) in the Phase-2b
pass even when the headline filter is, say, "human fMRI only." Flag them for the
user at this checkpoint rather than silently dropping them.

*Resolving the author id — five real bootstraps, four distinct failure shapes.*
The institution label is the obvious discriminator and it was misleading in three
of the five. Do not pick by it.

| Shape | What it looked like | What decided it |
|---|---|---|
| **Wrong-university** | The id labeled with the right university had 3 works; the correct one showed an unrelated institution and had 130 | Works count, then reading titles |
| **Moved lab** | *Two* candidates carried the university being searched for and neither was the person; one was a glaciologist. The correct id was still labeled with the PI's previous university | **Distinct ORCIDs** settle it instantly; otherwise the raw affiliation strings on the newest works |
| **Merged** | A *single* candidate, spanning 1976–2026, holding at least five different people | The **year span** — `--search` warns above 45 years |
| **Split** | *Three* candidates, all the same person, one holding a single high-profile paper | Same ORCID / same institutions / adjacent years; pass every id to `--author` |

Two rules follow, and they are easy to get backwards:

1. **A single candidate is the DANGEROUS case, not the safe one.** When namesakes
   collide OpenAlex frequently merges them into one id rather than splitting them,
   so "only one match" can mean "all the contamination is in here".
2. **ORCID confirms authorship; it does not refute it.** Use it to establish that
   a surprising paper *is* the PI's — one lab's 18 papers of psychiatric
   neuroimaging looked exactly like a collision and were her own pre-PhD work, and
   pruning on topic would have deleted a third of a real record. But profiles go
   stale: another PI's ORCID listed 18 works against OpenAlex's 39, so **absence
   from ORCID is not evidence a paper belongs to someone else.**

**L2 is therefore a completeness check as well as a purity check.** Every
bootstrap before the split case only ever needed records removed, and nothing
fails when a record is merely missing — so check explicitly for a split id, and
say in writing how many records were added as well as pruned.

*Keeping papers that are genuinely the PI's but not the lab's program.* Early
career work (a PhD in another field, a postdoc in another lab) is real authorship
and L2 has no basis to prune it — but its vocabulary will skew any downstream step
that reads titles. In one corpus such papers were 35% of the total and the keyword
derivation duly proposed *schizophrenia* for a speech lab. Keep them, and record
which groups are off-program in the notes so the next step knows to reject their
vocabulary rather than rediscovering the problem.

**Phase L3 — derive themes (HUMAN CHECKPOINT #2).** Run the families step
(`family_prompt_template.md` → user approves the ~N themes → assign every kept
paper). The "families" are now the lab's research programs; `tools/families.py`
validates/stamps and emits `families.json` + `families.md`.

**Phase L4 — render the lab's trajectory.**
- **Trajectory figure:** `tools/families_figure.py` — themes × year, the lab's
  papers as the spine (milestones labeled, the rest dots). This *is* "the lab's
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
2. **Verify EVERY citation (Phase 3)** with `tools/verify.py`.
   It resolves arXiv/conference papers against the arXiv API (batched) — so a
   NOT-FOUND is a real failure to investigate, never "an arXiv paper, skip it."
   Re-run any ERROR verdicts (transient rate-limit/network — distinct from
   NOT-FOUND). Expect ~1 in 4 to need a fix (fabricated author lists, wrong arXiv
   ids, garbage DOIs).
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
   keep the lab papers as the labeled spine over the field dots).

The three human checkpoints mirror topic mode: **(1) the corpus** (not a topic),
**(2) the themes**, **(3) the figure**.

The lab's foundational pre-paradigm papers (gathered in L2 + Phase 2b) exist so a Phase-7 review
can assign priority to the lab's own earlier work over later follow-ups from other groups — enforce
that with the priority audit (contract rule 5; Phase 7).

---

## Lessons learned (don't repeat these mistakes)


### Casing and foreign-language titles (learned on a 493-ref history corpus, 2026-08-29)

Four failure modes, all now handled by the tools and covered by regression tests
in `tools/tests/test_formatting.py`:

- **A non-English title must never be sentence-cased.** The pass lowercases German
  nouns, turning "Der Kumpan in der Umwelt des Vogels" into "der kumpan in der
  umwelt des vogels". `sentence_case.py` now detects German/French titles and
  **skips them by default**, printing which refs it skipped; `--include-foreign`
  forces the old behavior. Getting the language test right took three attempts:
  **`von` and `de` are not usable markers** (they sit inside personal names in
  English titles — "Karl von Frisch", "fin-de-siècle"), and neither is **`man`**
  ("the nervous system of vertebrates, including man"). Allowlisting German nouns
  one by one is the wrong fix; skip the title.
- **A partly ALL-CAPS title is shouting, not an acronym.** `references.norm_title`
  only sentence-cases a title that is *entirely* caps, and `case_token` protects
  all-caps tokens as possible acronyms — so "BEHAVIORAL MUTANTS OF *Drosophila*
  ISOLATED BY COUNTERCURRENT DISTRIBUTION" passed through both untouched and only
  showed up as an audit `uppercase-title run` that nothing fixed. `sentence_case.py`
  now lowercases a **run of ≥3 consecutive all-caps words** while still protecting
  isolated acronyms (`fMRI`, `MEG`).
- **Model-organism genera are proper nouns in any corpus.** Canon's ALL-CAPS
  sentence-caser emitted "the genetics of caenorhabditis elegans" from Brenner
  1974's uppercase deposit. `common.GENERA` is now shared: `common.norm_title`
  restores the capital, and `sentence_case.PROPER` includes the list, so no
  project has to allowlist *Drosophila* or *Aplysia* again.
- **A `?` inside a title or venue is mangled punctuation, not a question.** CrossRef
  could not encode the quotes and dash in Wehner 1987 and returned
  `?Matched filters? ? neural models of the external world`; the same deposit bug put
  `Journal of Comparative Physiology ? A` in the venue of five other rows while forty
  rows carried it correctly. The gate's existing check only caught a `?.` double
  terminal, so all six shipped silently. The audit now fails on a `?` glued to a
  letter or floating between spaces, while leaving a real question mark alone
  ("What is (was?) the fixed action pattern?").
- **Stripping JATS markup glues words together.** `common.MARKUP.sub("")` removes an
  `<i>` tag but leaves no separator, so a wrapped species name fuses with the word
  before it: `the cockroachPeriplaneta americana`, `desert ants, genusCataglyphis`,
  `the marine mollusc,Tritonia`. The audit now reports `missing-space` for
  punctuation glued to the next word, and for a `common.GENERA` name glued to a
  preceding lowercase letter. Found on the same rows as the venue bug — a deposit
  that is broken in one way is usually broken in several.

### A publisher back-file deposit re-dates an old paper (2026-08-29)

Digitized back catalogs are deposited with the **digitization year** as the issued
date while the true year survives in the DOI string. Three cases in one corpus:
Seyfarth & Zottoli 1991 deposited as 2008, Lorenz 1943 and Schleidt 1962 both
deposited as 2010 (`10.1111/j.1439-0310.1943.tb00655.x` — the year is right there in
the suffix). `references.py --audit` now warns via `deposit_year_conflict()` when a
DOI's embedded year disagrees with the reference's year by more than one. It is a
**warning, not a defect**: only a human can say which year is right.

`doi_year()` is deliberately **narrow** — it matches only the Wiley legacy
`.<year>.tb<n>` shape. The first version scanned for any plausible 4-digit year
anywhere in the DOI and produced **fifteen false positives and no true ones** on a
493-ref corpus, matching page numbers (`science.167.3926.1745`), article ids
(`nrn1606`, `nmeth.1694`) and ISSN fragments (`s1874-6055`). A narrow check that
fires rarely and correctly beats a broad one the reader learns to ignore. Note that
Seyfarth's `10.1159/000114363` carries no year at all, so no DOI-based check can
catch it — that one is caught by `verify.py` comparing the claimed year to CrossRef.

### Three network failures that look alike and are not (2026-09-18)

A run that will not finish is almost always one of these. They are distinguished by
*timing and determinism*, not by the exception type — all three arrive as
`http.client.HTTPException` and so are all correctly classed transient.

| Symptom | What it is | Fix |
|---|---|---|
| Random requests fail, succeed on retry | genuine rate limiting | backoff (already there); raise `--sleep` |
| The **same** records fail at the **same byte count**, small ones fine | response truncation of a large uncompressed body | `Accept-Encoding: gzip` + `common.decompress` |
| The **same** records fail **instantly** (~0.3s) every time, curl fetches them fine | HTTP-stack / proxy incompatibility | `common.curl_get` fallback |

Only the first is fixed by waiting. The other two are deterministic, and a retry
loop against them is an infinite loop that reports as slowness. On the
cortical-layers build all three appeared: 117 canon rows lost to truncation, then 71
of 536 xref reference-list fetches lost to the stack issue. `common.http` now tries
`curl` at the **first** network failure rather than after the full 2+4+8+16s backoff
— for the affected records that is 0.7s instead of 32s, and for genuine load nothing
changes because curl fails too and the backoff still runs.

**The diagnostic to reach for first:** re-fetch one failing URL with
`curl -sS --compressed`. If curl succeeds where the tool failed, it is not the
server and no amount of `--sleep` will help.

### An arXiv-heavy corpus breaks three silent assumptions (2026-09-24)

A 475-paper AI-alignment corpus, half of it arXiv-only plus blog and forum posts, exposed
three places where the toolkit assumed a journal-article literature:

- **Dated web sources failed the gate as `no-year`.** APA-7 dates a post `(2022, June 5)` and
  a magazine issue `(1942, March)`; `common.parse_apa` accepted only `(2022)`, so nine
  correctly cited posts and reports reported defects. It now accepts the month/day forms.
- **Book chapters printed the series as the venue.** CrossRef deposits a chapter's
  `container-title` as `[series, book]`, and canon read only the first entry, giving
  `Title. Lecture Notes in Computer Science.` with no book, pages or publisher. Canon now
  builds `In Book (pp. x-y). Publisher.` from the last entry (`common.build_chapter_apa`).
  CrossRef deposits no editors for most chapters, and Springer occasionally deposits the
  WRONG book (Biggio 2013 carried another volume's title and ISBN; the book-level DOI had
  the right one), so spot-check chapter rows. Book titles still need hand sentence case.
- **Within-corpus in-degree is blind to arXiv papers.** `xref.py` reads CrossRef reference
  lists, which arXiv DOIs do not have, so the auto-landmarks favored old journal classics
  (Simon, Jensen, Arrow) over the field's own canon. Raise `--per-family`/`--max-labels`
  (checking zero removals), then add each family's lineage papers through a `--spec`
  labels map. Also: on a warped axis the recent years are wide, and the x axis now labels
  single years wherever they fit (`families_figure.year_ticks`).

Two search-side notes from the same build: with 11 lanes, **seven papers were deferred by
one lane to another and kept by neither** (a 14-paper recovery lane found them all), and a
journal paper returned by one lane under its DOI and by another under its arXiv DOI is the
same paper, so dedup on the arXiv id as well as the DOI.

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
- **NOT-FOUND ≠ ERROR — a transient failure must never read as "missing."** On a
  ~90-paper world_models run, 8 real preprints came back NOT-FOUND purely because
  arXiv rate-limited (429) a per-paper loop into a temporary ban; trusting that
  verdict would have dropped real papers. `verify.py` now (a) prefetches arXiv ids
  in **batches** (many per `id_list` call, ~3s apart) so the ban doesn't happen,
  and (b) reports a distinct **ERROR** verdict when a lookup can't complete, kept
  separate from NOT-FOUND. Re-run ERRORs; only NOT-FOUND means "does not exist."
  Pass `expect_year` as a string OR int — either is accepted (a JSON int no longer
  crashes the run), and one malformed row degrades to ERROR instead of aborting.
- **Reference titles are strict APA-7 sentence case; DOIs are the ground truth
  for *location*, the APA string is just the bibliography display.** CrossRef and
  arXiv return titles in inconsistent casing (arXiv and many publishers use Title
  Case; Nature deposits sentence case), so `references.py` normalizes ALL-CAPS
  titles but deliberately does NOT auto-transform Title Case → sentence case:
  correct sentence-casing needs the proper-noun judgment APA bakes in (`Bayesian`,
  `Atari`, `Weber`, `Tolman-Eichenbaum` stay capitalized; `Active`, `World`,
  `Model` lowercase), and a mechanical caser silently mis-cases proper nouns —
  which the audit can't catch. So after canon, **sentence-case new preprint titles
  in a reviewed pass** (auto-protect all-caps acronyms, camelCase/digit model
  names, and hyphen parts; keep a small proper-noun allowlist; eyeball every
  changed title, e.g. a product name like `Matrix-Game`). This is a post-canon
  hand-fix like the mojibake and compound-surname fixes below.

### Make the agent verify its own citations — it drives fabrication to ~zero (2026-09-18)

The ~25% fabrication rate quoted throughout this playbook is what you get when the
brief asks for papers. Put an explicit **verification duty** section in every lane
brief and the rate collapses: on the 541-ref cortical-layers build, Phase 3 returned
**535 OK / 2 / 0 NOT-FOUND**, and both exceptions were missing diacritics in a name
the agent typed (`Hertag` for `Hertäg`), which canon then restored. Not one
fabricated reference in fourteen lanes.

The section that did it, in every brief, roughly:

1. Visit the actual landing page for every paper; read the author list **off the
   page**, never reconstruct it from memory.
2. Confirm first author and year on that page before writing the row.
3. Confirm the DOI **resolves to the paper you think it is** — not merely that it
   resolves. (This caught a real one: the DOI in circulation for Nandy et al. 2017
   resolves to a different Neuron paper.)
4. Read the abstract before writing the summary; do not invert the finding.
5. Do not judge a DOI by the shape of its string.
6. If you cannot confirm a paper, leave it out and list it under "Could not confirm".

Phase 3 still runs — it is the gate, not a formality, and it is what proves the
above happened. But it now confirms good work instead of finding a quarter of the
corpus rotten. Agents also report *what* they could not confirm, which is where the
useful findings come from (a misattributed classic, a wrong stored DOI, a title that
does not exist).

### Seed lane briefs with titles, and expect a third of them to be wrong (2026-09-18)

The standing rule is **seed with titles only, never remembered author names** —
author-name seeding injected fabricated attributions into three builds. That rule
holds. But titles recalled from memory are themselves unreliable: on the
cortical-layers build **roughly forty of ~170 seeded titles did not exist** under
that or any close wording ("Laminar analysis of ocular dominance plasticity",
"Cortical microcircuitry of attention", "The draining vein problem in laminar fMRI"
— all plausible, none real).

This cost little because the briefs labeled the seeds honestly ("These are paper
TITLES ONLY, from memory, and some may be slightly wrong... if one turns out not to
exist under any similar title, drop it and say so"), and every agent substituted the
real nearest work and reported the substitution. **Keep that framing** — a seed list
presented as fact would have sent fourteen agents hunting ghosts. Better still,
where a real source exists (a sibling corpus, a review's reference list), seed from
it instead of from memory.

### The shared WebSearch budget runs out early on a wide fan-out (2026-09-18)

The session's WebSearch quota (200 calls) is shared across all subagents. With 14
lanes it was exhausted after about two of them, and the remaining twelve completed
discovery through the Europe PMC, PubMed E-utilities, CrossRef, bioRxiv and arXiv
REST APIs instead. That was **not** a degradation — dated, field-restricted API
sweeps are more systematic than keyword search, and verification against those same
records is what the machine check uses anyway. The one real weakness is finding work
that does not put the topic's vocabulary in its title.

So: do not treat "WebSearch exhausted" as a reason to re-run a lane. Tell the briefs
up front that the API path is a first-class route, and if a lane comes back thin,
**resume it via SendMessage** (transcript intact) rather than re-spawning — a
re-spawn discards everything it had already verified.

### Family claims and lineages are content, and need the same discipline as citations (2026-09-18)

Since the figure now surfaces each family's `claim` and `lineage` on hover, those
strings are read by the reader, not just by the agent doing the assignment — and a
lineage composed from memory can be wrong in exactly the way a citation can. On the
cortical-layers build the `contingency` lineage named Senzai et al. 2019, whose
actual contribution (reproducible laminar landmarks from spike power and sink-source
distributions) puts it squarely in `boundary`. An assignment agent flagged the
conflict, correctly deferred to the frozen spec, and the error propagated until the
flag was read.

Two rules follow. **Compose lineages from rows that are already in the corpus** —
grep `rows.json` after canon and use the canonical lead surname and year, rather
than recalling a chain. And **read the assignment agents' `hard_calls`**: they are
the only place a wrong family definition shows up, because the agents are instructed
not to argue with the spec.

### A size encoding must not turn "unknown" into a number (2026-09-19)

`--size-by-citations` maps a paper's citation count onto its dot radius. The first
version sized a paper with NO count at the floor, which is exactly where a paper
with zero citations lands — so the figure asserted a count it did not have. On
`reverse_polish_notation` that is 67% coverage, i.e. a third of the corpus silently
claimed to be uncited. Missing counts now draw HOLLOW, keyed in the legend.

The general rule: before mapping a data column onto a visual channel, **count how
many rows actually have that column**, per corpus, and decide what the blanks look
like. Coverage across the 15 corpora here runs 67-100%, so the blanks are never
negligible and are worst exactly where the literature is oldest and most obscure.

Two scale notes, from rendering both: citation counts span four orders of magnitude
(0 to ~80k), so normalize against a high percentile and CLAMP above it, or one
runaway classic flattens everything else. `sqrt` (area-proportional) is the one to
use; `log` compresses so hard that a 100-citation paper sits at ~67% of the radius
range and the whole figure reads flat. And say it out loud when presenting: citation
count is partly an AGE variable, so the right-hand edge of any timeline goes small.

### A walk-through's order must follow the drawn geometry, not the data key (2026-09-19)

The figure's Next/Prev walk sorted on `(year, reference string)`. The reference
string has nothing to do with where the beeswarm put the dot, and the beeswarm fans
a year's papers out from the lane center as 0, +d, -d, +2d, -2d — so the highlight
hopped up and down the column and the walk read as random. 137 backward steps inside
a year-column on a 555-paper corpus. Every paper of one year shares an x, so a year
IS a vertical column: tie-break on the dot's own drawn y and the walk sweeps it.

This survived code review twice because the sort LOOKS right until you ask what its
tie-break has to do with the picture. The check that caught it executes the figure's
own `ORDER` expression against its own embedded data (`verify_nav_order.mjs`) — the
same tactic as `verify_hover.mjs`. **For anything interactive, run the figure's own
code; do not read it.**

### Set iteration makes a render nondeterministic, which defeats the diff (2026-09-19)

`families_figure.py` picked landmarks into a `set` of reference strings, and Python
randomizes string hashes per process. Same-year and same-x ties therefore came out
in a different order on every run: two renders of identical code against identical
data produced different bytes and moved 5 of 57 labels between tiers. Harmless on
screen — but `rerender_figures.py` verifies by DIFFING the re-render against the
delivered file, so the whole safety net was reading noise. Sort keys are now
`(year, ref)` and `(x, ref)`; three consecutive renders are byte-identical.

If a harness's guarantee is "re-rendering changes nothing", prove that by rendering
TWICE with unchanged code first. Any diff there is a bug in the renderer, not a
change in the data.

### A highlight ring must never be the color of the thing it rings (2026-09-20)

The home-lab ring marked a paper by outlining its dot in gold, `#d4a017`. That is
also `PALETTE[4]` — the FIFTH family's lane color. So on any figure with five or
more families, a home-lab paper in family 5 got a gold ring on a gold dot and the
highlight silently did nothing. Live in `gallant_lab_in_context` (6 families, 2
lab papers in family 5) and latent in four more corpora.

The ring color is now `--lab-color`, and it is resolved against the lane colors
actually in use: an unset default that collides moves itself out of the way and
says which color it took, an explicitly chosen one is honored but warned about.
The starred label's ink is *derived* from the ring color rather than being a
second hardcoded constant (`#9a7400`), so one parameter controls both.

Two general rules. **A marker drawn on top of colored data must be checked against
that data's palette, not chosen in isolation** — the collision is invisible in
every figure where no marked item happens to land in the clashing lane, which is
why this survived every visual review. And when asked to "make X a parameter",
**check whether it already is**: *which* lab gets starred had been
`--lab-author` / `LITREVIEW_LAB_AUTHOR` all along, off by default and lab-neutral.
The real gap was one layer down, in the appearance.

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

### On writing the review (Phase 7)
- **The draft will be accurate and unreadable; budget a concision pass.** The failure is
  compression, not vocabulary — a filler-word scan over one 10,800-word draft found essentially
  nothing to cut, while 54 sentences ran past 50 words. Run `prose_audit.py`, work down the
  long-sentence list it prints, and re-run it with `--baseline` so the pass cannot drop a reference.
- **Edit the emitter, never the rendered page.** The prose lives in `build_review_page.py` /
  `content.json`; a fix applied to the HTML or the `.docx` is gone at the next render and, worse,
  leaves the page disagreeing with the script that claims to produce it.
- **Order ideas by publication date, not by your narrative.** The drafting model reliably presents
  a later paper as an idea's origin because that ref fits the sentence it wants to write. The rule,
  the four inversion patterns, the real misses caught 2026-06-13, and the required pre-delivery
  **priority audit** are all in Phase 7 — run the audit. Self-review misses these because the
  author is biased toward its own story; an independent pass with the publication years catches them.

- **A toolkit fix does not reach a delivered .docx until you re-render it.** `reference_list`
  once sorted on the whole string with digits dropped, so one author's works came out in title
  order, not year order (67 inversions across 7 delivered reviews, fixed 2026-09-23). Before
  overwriting a delivered `.docx`, render to scratch and diff the prose against the old file: if
  the prose differs, the file holds edits or is an older draft, and re-rendering would destroy
  them.

### On PDF downloads
Phase 4 has the full source order and the bot-blocked list. Three things that recur:
institutional-repo URLs (`.edu`/`.ac.uk`) from Unpaywall almost always work;
PMC/Cell/Elsevier/Wiley/OUP/MIT Press/PNAS/bioRxiv all block bots (route to the
helper page, don't retry); always validate the first 4 bytes are `%PDF` (a 200 can
be an HTML challenge page).

### On the spreadsheet
- Use a "source" column or color code so a future you (or the user) knows
  where each ref came from and how confident to be.
- **Ref ids must be globally unique, and stay unique across merges.** A
  single-character lane prefix plus a multi-digit counter is ambiguous: lane `4`
  with refs `41…49` then `410…423` parses the same as lane `41`, and a naive
  merge re-emitted the xref batch as `410…` on top of the existing `410…`,
  silently duplicating ids. Two failures followed: `families.py` assigned the same
  paper twice, and — worse — `citation_counts.json` keyed by ref got
  cross-contaminated (two rows sharing id `415` shared one count, so Carvalho 2024
  inherited Elman 1990's 10,838 cites). After any merge, assert
  `len(refs)==len(set(refs))`; attach citation counts only AFTER ids are final (or
  key the counts by DOI, not by ref); and prefer zero-padded or separator'd ids
  (`4-01`, or two-char lanes) so the counter can't collide with the prefix.
- Keep summaries to 3-5 sentences. Long ones become unreadable in a row.
- Don't try to read existing xlsx with xlsxwriter — it's write-only. If
  appending, regenerate the whole file from a JSON of accumulated rows.
- **Keep all rows in `rows.json` and rebuild the xlsx via `tools/spreadsheet.py`.**
  A project's row emitter (start from `templates/build_rows_template.py`) runs
  ONCE, guards its writing block under `if __name__ == "__main__":`, imports the
  toolkit's `common`, and writes through `common.write_rows` — which refuses to
  overwrite a canonical table, so re-running it later cannot wipe Phase 3f.

### On canonicalization & the live table
- **When `--audit` flags `U+FFFD` mojibake, hand-fix it LAST.** CrossRef stores a
  few names/venues with broken encoding (the original glyph is unrecoverable), so
  `references.py` pulls the broken character back in on *every* run. Fix it
  directly in `rows.json` AFTER the final `references.py` pass and before building
  the spreadsheet/figure — fixing it earlier just gets it overwritten on the next
  canon, and you loop on the gate. Real cases: `Bürgel`, `Zeitschrift für
  Anatomie`.
- **A defect check that reads the whole reference string will condemn a legitimate
  title.** The gate forbade `et al.` anywhere in the `apa`, which is right for an
  author list and wrong for a title: Nature titles its Matters Arising replies
  "<Author> et al. reply", so a correctly canonicalized Nat Neurosci reply could not
  pass the gate without falsifying its own published title. The check now inspects
  only `parse_apa`'s author segment, falling back to the whole string when the
  reference will not parse (a malformed reference is exactly where an abbreviated
  author list hides). Generalize the rule, not the example: before adding a
  whole-string check, ask which APA segment the defect actually lives in.
- **CrossRef mis-splits compound / particle surnames** (`Lambon Ralph` →
  `Ralph, M. A. L.`; `de Heer` → `Heer, W. A. D.`). The shared formatter handles
  the common particles, but novel ones slip through and re-canon reintroduces the
  bad split — so correct these in `rows.json` after the last canon, same as
  mojibake. `--audit` now *warns* on every multi-word surname so they get looked at;
  expect a handful of legitimate ones (Spanish, Vietnamese and Italian double
  surnames) alongside the real errors. The reverse error also happens: a given
  name with two parts (`J. Adam Noah` → family `Adam Noah`) — the warning catches
  it, the fix is `Noah, J. A.` by hand.
- **CrossRef keeps a series part / subtitle in a separate `subtitle` field.** Until
  2026-08-22 canon dropped it, so Creutzfeldt 1989 "I. Responses to speech" and
  "II. Responses to the subjects own voice" rendered as one identical title — the
  `--audit` "possible duplicate (1.00)" warning was the only tell. `crossref_record`
  now joins them APA-style (`Title: Subtitle`). Corpora canonicalized before that
  date still lack subtitles; restore them by hand (a re-canon would wipe other
  post-canon fixes).
- **What CrossRef deposits is sometimes simply wrong, not just mis-parsed.** Seen in
  one 396-row corpus: `family="A. Moffat"` with `given="Bradford"` (a middle initial
  folded into the surname — now auto-repaired, since no surname starts with an
  initial); `family="(Bud) Craig"` for A. D. Craig (parenthetical nickname — now
  stripped); and `Sprby` for Terje Sparby, a plain misspelling of a living author's
  name, verifiable only by finding the same author spelled correctly on a sibling
  paper. The first two are handled; the third can only be caught by reading.
- **Four formatter defects that shipped in five delivered bibliographies before the
  gate caught them**, all now hard defects: JATS markup left inside a title
  (`<i>Generalization and Differentiation</i>`), a `?.` where a question-mark title
  got an extra period, and U+2010/U+2011 Unicode hyphens in surnames
  (`Fischer‐Baum`, `Kabat‐Zinn`, `low‐frequency`) that look identical to ASCII but
  break every string match. Re-run `--audit` over old projects after a formatter
  change; these had been sitting in finished work for months.
- **The audit's `no-year` check used to reject APA year suffixes.** `\(\d{4}\)`
  fails on `(2025a)`, so the standard way to disambiguate two same-author/same-year
  works could not be expressed. It now accepts `\(\d{4}[a-z]?\)`.
- **`rows.json` is the live table; the row-emitter script is destructive once you
  pass Phase 3f.** A per-project `build_data.py` (or equivalent) only knows the
  original search rows — re-running it after canon/xref/families drops the xref
  rows and wipes the canonical `apa` + citation counts. After the first build,
  edit `rows.json` directly (or splice via targeted canon); don't regenerate it
  from the emitter.
- **`references.py` prefers the journal DOI over arXiv when a row has both** (the
  version of record), and falls back to arXiv only for preprint-only rows (no
  journal DOI) or rows whose DOI is itself an arXiv DOI. So you no longer need to
  hand-clear an `arxiv` field to stop a published paper from being cited as its
  preprint — just keep both ids and let canon pick the journal version. (Agents
  routinely return a journal DOI *and* the preprint id for the same paper.)
- **BUT: not every "published" DOI is the version of record — check the count
  before you swap.** Curran/Proceedings.com registers DOIs (`10.52202/*`) for the
  *printed* NeurIPS volumes. They resolve, and a CrossRef title search happily
  returns them, but they are shadow records of the paper the community actually
  cites: on a 2026 gallant_lab pass, moving 6 rows to their `10.52202` DOIs would
  have cut OpenAlex counts by ~3-4× (MindEye 40 → 11, Toneva-style rows 34 → 10)
  while adding nothing. ACL Anthology (`10.18653/*`), IEEE/CVF (`10.1109/*`) and
  real journal DOIs are the opposite — genuine upgrades (MindBridge 2 → 41). Rule:
  before promoting a preprint row to a "published" DOI, query the candidate DOI's
  OpenAlex count; if it is much LOWER than the arXiv record's, keep arXiv and note
  the venue in prose. Preprint-heavy CS/AI reviews are where this bites.
- **The same paper can enter a review twice, and per-row canon will never notice.**
  One agent finds the arXiv preprint, another finds the journal version; two
  different DOIs, so the one-row-per-DOI rule passes and *both* rows canonicalize
  perfectly. Three such pairs sat undetected in a 362-row corpus for six weeks.
  `references.py --audit` now runs a corpus-level `duplicate_scan()` and prints
  `⚠ A ~ B: possible duplicate` for near-identical titles (labeling the
  preprint-vs-published case explicitly). It is a **warning, not a defect** — real
  distinct papers do collide (a 2014 toolbox paper and its 2026 successor;
  successive years of the same challenge), so every pair needs a human verdict.
  Keep the version of record, drop the preprint, and re-check any in-text citation
  whose YEAR moves as a result (a preprint→journal promotion can shift 2025 → 2026).

### Always ask for a compressed body (2026-09-18)

`common.HDRS` now sends `Accept-Encoding: gzip, deflate` and `common.http` decodes the
reply (`common.decompress`). urllib does **not** decompress for you, so the two must
land together — requesting gzip without decoding returns binary garbage.

Why it matters: a CrossRef work record carries its whole reference list and can exceed
a megabyte. Uncompressed, those large responses arrive truncated —
`IncompleteRead(1782210 bytes read, 399724 more expected)` — which is an
`http.client.HTTPException` and therefore correctly classed **transient**, so the tools
retry it. The failure mode is not an error message; it is a run that never finishes.
On the 541-row cortical-layers build, uncompressed: **117 of 537 rows failed canon**
and needed three splice passes, and `xref.py` was managing ~19 papers per 7 minutes
(a ~3-hour projection). Compressed, the same records fetch in 0.3 s each.

The tell is a burst of `RemoteDisconnected` / `IncompleteRead` against *particular*
DOIs that fail identically every time, at the same byte count, while small records
sail through. That is not throttling and no amount of `--sleep` fixes it — a retry
loop on a truncating transfer just truncates again. `decompress()` passes an unknown
or mislabeled encoding straight through rather than raising, so a server that lies
about Content-Encoding degrades to a JSON parse error instead of killing the run.

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
- **OpenAlex's BATCH filter can return a low-count duplicate record** for a DOI
  that has both a merged primary work and a stub (e.g. Whittington 2020 TEM came
  back as 6 from the batch but 667 from the canonical `/works/doi:` endpoint;
  Tolman 1948 as 1 vs 6656). `citations.py` now (a) keeps the MAX count when a DOI
  appears more than once in a batch, and (b) re-queries the single-work endpoint
  whenever the OpenAlex count is < half the S2 count (with S2 ≥ 50). Still
  **spot-check landmark/foundational counts against the S2 column** before
  delivering — a famous old paper showing single-digit OpenAlex is the tell.
- **Semantic Scholar's free endpoints are flaky**: the `/paper/batch` endpoint
  429s and sometimes 400s (one malformed id poisons the whole batch — the
  toolkit's `common.s2_batch` bisects such a batch until the rejected id stands
  alone, names it, and treats it as not in S2, so the other ids still resolve;
  `citations.py`, `abstracts.py` and `xref.py` all go through it); the
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
| arxiv API | `https://export.arxiv.org/api/query?search_query=all:<q>` | Atom XML |
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
outputs JSON/files. Run `python3 tools/<script>.py --help` for flags. The index
below is generated from the modules by `python3 tools/gen_docs.py` (CI fails if
it is stale); the per-tool detail is in `tools/README.md` and `docs/tools.md`.

<!-- BEGIN GENERATED TOOL INDEX (python3 tools/gen_docs.py — do not edit by hand) -->
| Script | Phase | Purpose | Flags |
|---|---|---|---|
| `merge_lanes.py` | 2c | Merge search-lane files into rows.json, and fail when a paper fell between lanes. | `--allow-v1` `--append` `--force` `--into` `--out` `--raw` `--report` |
| `verify.py` | 3 | Verify a list of citations against PMC / PubMed / CrossRef / arXiv. | `--asof` `--citations` `--email` `--key` `--no-stamp` `--only` `--out` `--override` `--reason` `--retry-from` `--retry-wait` `--rows` `--sleep` |
| `handcheck.py` | 3e | Hand-check the references that have no DOI or arXiv id (books, reports, essays). | `--adopt-dois` `--asof` `--email` `--ingest` `--key` `--prepare` `--rows` |
| `references.py` | 3f | Canonical reference builder — make EVERY reference perfect, in both modes. | `--acks` `--asof` `--audit` `--candidates` `--email` `--key` `--list-acks` `--only` `--out` `--repair` `--retry-wait` `--rows` `--sleep` |
| `sentence_case.py` | 3f | Post-canon pass — propose strict APA-7 sentence case for reference titles. | `--apply` `--include-foreign` `--out` `--proper` `--rows` `--vocab` |
| `download.py` | 4 (opt-in) | Multi-source PDF downloader (Phase 4 — OPT-IN, not run by default). | `--email` `--manual-list` `--out-dir` `--papers` `--sleep` |
| `reconcile_downloads.py` | 4 (opt-in) | Reconcile manually-downloaded PDFs against a slug+title+doi manifest. | `--downloads-dir` `--dry-run` `--manifest` `--out-dir` `--since-hours` |
| `spreadsheet.py` | 5 | Build/rebuild the bibliography xlsx from a JSON of accumulated rows. | `--acks` `--candidates` `--draft` `--key` `--out` `--rows` `--sheet-name` |
| `citations.py` | 5b | Fetch citation counts for a bibliography from OpenAlex + Semantic Scholar. | `--asof` `--email` `--key` `--out` `--rows` `--sources` |
| `abstracts.py` | 5c | Fetch the abstract of every row, in batches, into abstracts.json. | `--email` `--key` `--out` `--rows` |
| `summary_audit.py` | 5c | Check every row's summary against its abstract, by checking agents with no web access. | `--abstracts` `--asof` `--batch` `--dir` `--ingest` `--key` `--prepare` `--recheck` `--rows` |
| `candidates.py` | 6 | The candidate ledger: every paper xref or forward citations suggest gets a recorded decision. | `--add` `--asof` `--decide` `--decision` `--export-included` `--lane` `--ledger` `--list` `--reason` `--rows` `--source` |
| `forward.py` | 6 | Find papers that cite the corpus's landmark papers but are not in the corpus. | `--allow-incomplete` `--email` `--internal` `--key` `--landmarks` `--min-shared` `--out` `--per-landmark` `--rows` |
| `xref.py` | 6 | Build a cross-citation index from a list of papers. | `--allow-incomplete` `--email` `--exclude` `--internal-out` `--key` `--min-cites` `--out` `--papers` `--resolve-unknown` `--retry-wait` `--rows` `--sleep` |
| `families.py` | 6b | Phase 6b — validate an LLM-proposed family taxonomy against the bibliography, stamp `family` onto rows.json, and emit families.json (the reproducible cache) + families.md (grouped tables + a family x topic cross-tab). | `--asof` `--assign` `--digest` `--md` `--out` `--rows` |
| `families_figure.py` | 6b | Phase 6b — render the interactive HTML lineage figure of the theoretical families. | `--emphasize-source` `--families` `--internal` `--lab-author` `--lab-color` `--max-labels` `--min-year` `--motif-min` `--no-auto-landmarks` `--no-raster` `--out-prefix` `--per-family` `--rows` `--size-by-citations` `--size-range` `--spec` `--time-warp` `--title` `--xlsx` |
| `bib_viewer.py` | 7 | Render the searchable bibliography viewer every review page embeds. | `--author` `--author-note` `--families` `--out` `--rows` `--subtitle` `--title` |
| `cite_check.py` | 7 | Phase 7 gate — every in-text citation must name a paper in rows.json. | `--content` `--key` `--quiet` `--rows` |
| `prose_audit.py` | 7 | Phase 7 — measure a review's prose and prove a revision pass lost no citation. | `--baseline` `--content` `--exclude` `--long` `--overlap` `--page` `--quiet` |
| `review_paper.py` | 7 | Phase 7 — build a review ARTICLE (.docx) from a finished review corpus. | `--content` `--figure` `--out` `--rows` |
| `lab_corpus.py` | L1 | Lab mode — Phase L1: ingest a lab's full publication corpus from OpenAlex. | `--author` `--email` `--from-year` `--out` `--search` `--to-year` |
| `common.py` | — | Shared helpers for the literature-review toolkit. | — |
<!-- END GENERATED TOOL INDEX -->

Notes the index cannot carry:
- `verify.py` and `xref.py` accept `--rows rows.json` directly, so a project needs
  no converter script to feed them.
- `references.py --repair` retrofits an old corpus offline (no re-fetch, so
  post-canon hand fixes survive); canon and repair stamp rows `canonical_at`.
- `reconcile_downloads.py` matches by filename ↔ DOI substring first, then by
  first-author + year + title overlap on the first page (`pdftotext`), and refuses
  to move a PDF it is unsure about.
- Project scripts should `import common` (see tools/README.md, "Using the toolkit
  from a project script") and write `rows.json` through `common.write_rows`, which
  refuses to overwrite a canonical table.

Each helper is small and meant to be read + adapted. They are not a framework —
they're scaffolding to keep the LLM judgment work fast.

---

## Upgrading an old corpus

Rerunning a search on an existing bibliography brings the WHOLE project up to the
current standard, or redoes it if that is easier — it is never a lighter pass over
just the new rows. The first verified row (or any row a current emitter built, which
carries a `built_at` date) switches the reference gates on for the whole table
(`common.is_gated`); once that happens, the audit and the spreadsheet
gate fail every OLD row that lacks the new records, not just the new batch.

Procedure, in order:

1. `verify.py --rows rows.json` over the WHOLE table, not just the new rows.
   A canonical row that kept its search claim (`search_*`) is checked against
   BOTH the claim and its `apa`, and fails if either disagrees with the record.
   A canonical row with no claim is checked against its own `apa` only — which
   canon built from the same DOI, so it cannot re-establish that the DOI is the
   intended paper: its stamp records `claim_basis: "canonical-apa"` and the audit
   warns `identity-not-reestablished` until you confirm the DOI by hand and
   acknowledge it.
2. Turn any existing hand checks (`verify_note` text, informal manual-check results)
   into `handcheck.py --ingest` result files; re-check any whose source is not
   recorded.
3. `abstracts.py`, then `summary_audit.py --prepare` / dispatch checking agents /
   `--ingest` (Phase 5c).
4. Acknowledge each remaining warning (`references.py --list-acks`, then
   `audit_acks.json`; Phase 3f).
5. `candidates.py --rows rows.json --add xref_<topic>.json --source xref` (and
   `--add forward_candidates.json --source forward` if you have one) over the
   existing xref/forward output, then decide any still-pending entries
   (`--list pending`, `--decide DOI include|exclude --reason "..."`), to bring
   the candidate ledger up to date. A gated table with no `candidates.json` at
   all fails the audit with `no-candidate-ledger` under `*` — acknowledge that
   in `audit_acks.json` if the corpus genuinely never ran xref/forward.
6. `references.py --audit`, then `spreadsheet.py`.

**When a full redo is easier than upgrading in place:** few of the old rows carry a
DOI, the rows lack the search agents' claims (`search_*` fields, so `verify.py` has
nothing independent to check against), or the lanes are stale enough that a fresh
search is simpler than reconciling one row at a time. Say which you chose, and why.

---

## Quick start for a fresh Claude

Read this playbook, then read any existing `rows.json` — after Phase 3f it is the
live table and the xlsx is only a rendering of it (xlsxwriter is write-only).
Confirm topic + criteria with the user; do NOT ask whether to download PDFs, the
default is no (Phase 4 is opt-in only). Then the pipeline, in order:

```
 1. Scope the topic (Phase 1, your decision). Write the lane briefs with the
    schema-2 output format (tools/search_prompt_template.md); launch the
    forward-search and antecedent lanes in one fan-out (Phases 2 + 2b), each
    writing its file into search_raw/.

 2. python3 tools/merge_lanes.py --raw search_raw --out rows.json      (Phase 2c)
    Lost deferrals fail the merge: send them to one recovery lane, add its
    file to search_raw/, and re-merge. Resume any lane it flags as thin.

 3. python3 tools/verify.py --rows rows.json --out verify_report.json  (Phase 3)
    Fix or drop each MISMATCH and NOT-FOUND, or clear a false alarm with
    --override REF --reason "...". In parallel: tools/handcheck.py --prepare
    for the DOI-less rows, the hand-check agent, then --ingest (Phase 3e).

 4. Pitch the families to the user (Phase 6b step 2): propose ~3-8 families
    (tools/families.py --digest) and let them use, change, or skip them.

 5. In parallel, once rows are verified: canon (tools/references.py — refuses
    an unverified row; Phase 3f), citation counts (tools/citations.py; Phase
    5b), cross-citation via Semantic Scholar (tools/xref.py; Phase 6), forward
    citations of the landmarks (tools/forward.py; Phase 6), and abstracts
    (tools/abstracts.py; Phase 5c).

 6. tools/candidates.py --add for both the xref and forward results; decide
    each pending one with a reason; --export-included the decided-in papers,
    tools/merge_lanes.py --append them into rows.json, then verify, canon and
    citation counts for the new rows (Phase 6).

 7. Sentence-case titles in a reviewed pass (tools/sentence_case.py --proper)
    and any post-canon hand fixes (mojibake, compound surnames); acknowledge
    every remaining audit warning in audit_acks.json (references.py
    --list-acks) (Phase 3f).

 8. tools/summary_audit.py --prepare; dispatch checking agents with no web
    access; --ingest. Fix any flagged summary and re-run --prepare (Phase 5c).

 9. Assign families (tools/families.py --assign --out families.json) and
    render the timeline (tools/families_figure.py) — only if not skipped at
    step 4 (Phase 6b).

10. python3 tools/spreadsheet.py --rows rows.json --out <topic>_bibliography.xlsx
    It runs the full audit and writes the deliverable only if it passes;
    --draft writes a marked draft instead (Phase 5).
```

Then Phase 7 (review article, OPTIONAL) and Phase 8 (report to the user). Phase 4
(PDF download) is OPTIONAL — only run if the user explicitly asks. If you changed
any tool/phase/command, update the matching docs/ page (see "Documentation site —
keep it in sync" above). Extending or rerunning an EXISTING corpus is not a
lighter pass — see "Upgrading an old corpus" above: the first verified row gates
the whole table.

Plan on hours, not minutes. A 475-ref, 11-lane build took about
4 hours on 2026-09-24: ~20 min of web search, ~85 min in the network tools (53 of
them in canon's arXiv backoff), and the rest in reruns, hand steps and the families
decision. The 2026-09-25 fixes (batched arXiv canon, in-run retries, no arXiv DOIs
sent to CrossRef, pauses only after real requests) should cut the tool time to
roughly 15-20 min; that has not yet been measured on a full build. With Phase 4
turned on, add 10-20 more minutes for downloads.
