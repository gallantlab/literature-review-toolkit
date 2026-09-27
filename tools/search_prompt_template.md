# Literature search lane brief — TEMPLATE

Do not fill this by hand. `tools/lane_briefs.py --spec lanes.json` renders one brief
per lane from it: it fills every `{PLACEHOLDER}`, keeps or drops each
`<!-- IF:name -->` … `<!-- ENDIF:name -->` block, builds the lane table, and refuses
to write a brief with anything left unfilled. Everything above the `BRIEF STARTS`
marker is these notes and is never sent.

Blocks: `forward` / `antecedent` (the lane's kind: the antecedents variant flips the
tier emphasis to classic, pre-modern work and tags papers `anteced`), `capped` /
`uncapped` (whether the spec's scale caps the lanes, `common.SEARCH_SCALES`; after a
"cap" choice at the preflight, `lane_briefs.py` refuses an uncapped scale), `lab`
(lab mode: the lab's own papers are deferred to the lab lane), `seeds` (the lane has
landmark titles). Seeds are TITLES only, never author names: remembered author names
have injected fabricated attributions, and about a third of remembered titles do not
exist as typed.

<!-- BRIEF STARTS -->
# Literature search brief — lane `{LANE_KEY}`: {TOPIC_NAME}

You are doing a literature search for an academic annotated bibliography titled
**"{REVIEW_TITLE}"**, assembled for {REVIEW_FOR}. You are responsible for ONE lane of
that bibliography.

## The bibliography as a whole

{BIBLIOGRAPHY_DESCRIPTION}
<!-- IF:lab -->

**The lab's own papers are out of scope for every search lane.** A lab paper is any
paper with {LAB_PI} as an author. Do NOT put one in `papers`. If you come across one,
list it in `deferred` with `"to_lane": "{LAB_LANE}"` and its first author, year and
title from the landing page: lane `{LAB_LANE}` is the lab's own record, and a deferral
that the record lacks shows the record is incomplete. Papers by the lab's former
trainees in their own labs are NOT lab papers unless {LAB_PI} is an author.
<!-- ENDIF:lab -->

## YOUR LANE — `{LANE_KEY}`: {TOPIC_NAME}

{TOPIC_DEFINITION}

### Explicitly OUT of your lane

{EXCLUSIONS}

Other agents are covering the rest of the bibliography in parallel. The full lane list
is below so you can tell what is yours; if a paper straddles two lanes, keep it if it
is squarely relevant to yours and note the overlap in a `note` field.

{LANE_TABLE}

## What the corpus already has (DO NOT re-include these)

{ALREADY_HAVE_LIST}

## Selection criteria
<!-- IF:forward -->

- **Pre-{TIER_BOUNDARY_YEAR}**: include ONLY if highly impactful, well cited, or
  genuinely foundational. Think canonical work.
- **{TIER_BOUNDARY_YEAR}–present**: be promiscuous. Include even if not yet highly
  cited — these papers have not had time to accrue citations. Anything methodologically
  interesting, addressing an open question, or extending a major framework is worth
  including.
<!-- ENDIF:forward -->
<!-- IF:antecedent -->

- This is an **ANTECEDENTS** lane: the target is foundational, highly cited, classic
  work that PRE-DATES and underpins the modern literature (methodology origins,
  foundational empirical results, or theory), much of it decades old. Include a later
  paper only if it is itself a canonical reference point for the idea.
- Recent work is covered by the other lanes; do not chase recent papers here.
- Old classics often have no DOI (books, chapters, pre-1990 articles): include them as
  DOI-less items (below). Cite an old book's ORIGINAL edition, never a reprint DOI
  (reissue DOIs re-date the work).
<!-- ENDIF:antecedent -->

The current date is {TODAY}. Search for papers up through today.
<!-- IF:forward -->
**Recent work matters**: sweep the last three years, including bioRxiv and arXiv
preprints, for this lane.
<!-- ENDIF:forward -->

## Target: ~{TARGET_COUNT} papers
<!-- IF:uncapped -->

**The target is a floor, not a cap.** Never leave out an on-topic paper to stay near
it: "lower priority" or "trimmed to target" is not a reason to drop a paper. Do not pad
with filler either.
<!-- ENDIF:uncapped -->
<!-- IF:capped -->

**This is a CAPPED search: the target is a hard cap of {TARGET_COUNT} papers.** Keep the
most important papers, and list every on-topic paper over the cap in `excluded` with
reason `over the capped-search limit`, so it is shown, not lost. The merge fails a lane
that returns more than {TARGET_COUNT} papers.
<!-- ENDIF:capped -->

## How to search

Use WebSearch and WebFetch. Try multiple query variants for each angle:

{SEARCH_QUERIES}

Search PubMed (`pubmed.ncbi.nlm.nih.gov`), Google Scholar, Semantic Scholar, bioRxiv,
arXiv, OpenReview and journal sites. Google Scholar often blocks automated fetches; if
it does, use the others. Follow the reference lists and "cited by" lists of the
landmark papers you find; that is usually more productive than more query variants.

If WebSearch stops working (the budget is shared by every agent running at once),
continue through PubMed E-utilities (`eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi`),
Semantic Scholar (`api.semanticscholar.org/graph/v1/paper/search`), OpenAlex
(`api.openalex.org/works?search=`), CrossRef (`api.crossref.org/works?query=`) and the
arXiv API with WebFetch. That is a first-class route, not a degradation.
<!-- IF:seeds -->

### Landmark titles this lane should cover

These are paper TITLES ONLY, from memory, and some may be wrong or not exist. Find each
one, read its real title, authors and year off the landing page, and include it if it
fits your lane. Do not trust an author name you have not read off a landing page. If a
title does not exist under any similar wording, list it in `could_not_confirm`.

{SEED_TITLES}
<!-- ENDIF:seeds -->

## What to return

Write ONE JSON object (schema 2) to:

    {OUTPATH}

```json
{"schema": 2,
 "lane": "{LANE_KEY}",
 "status": {"target": {TARGET_COUNT}, "returned": 0, "websearch_exhausted": false, "notes": ""},
 "papers": [
   {"ref": "{LANE_KEY}-01", "lane": "{LANE_KEY}", "doi": "10.xxxx/yyyy", "arxiv": "",
    "link": "https://doi.org/10.xxxx/yyyy",
    "first_author": "Family, I. I.", "year": 2022, "title": "Title exactly as on the landing page",
    "apa": "", "summary": "Two to four sentences written ONLY from the abstract.",
    "tag": "classic", "topic": "{TOPIC_NAME}", "source": "{SOURCE_TAG}", "note": "", "lane_fit": ""}],
 "deferred": [{"title": "...", "doi": "", "first_author": "Family, I.", "year": 2023,
               "reason": "fits lane X better", "to_lane": "X"}],
 "excluded": [{"title": "...", "doi": "", "first_author": "Family, I.", "year": 2010,
               "reason": "outside the bibliography's scope"}],
 "could_not_confirm": [{"title": "...", "reason": "no such paper under any similar title"}]}
```

- `ref`: `{LANE_KEY}-01`, `{LANE_KEY}-02`, … in the order you list them.
- **Every paper needs a DOI or an arXiv id**, except the DOI-less items below.
  - A journal paper → its DOI. For a preprint that was later published, give the
    PUBLISHED DOI (the version of record), and the arXiv id in `arxiv` if there is one.
  - An unpublished bioRxiv/PsyArXiv preprint → its preprint DOI, read off the page.
  - arXiv-only, or a conference paper with no DOI (NeurIPS, ICLR, ICML) → `arxiv` the bare
    id, `doi` `10.48550/arXiv.<id>`, `link` `https://doi.org/10.48550/arXiv.<id>`.
- **DOI-less and arXiv-less items** (a book, chapter, report, or software with neither):
  set `"source": "{SOURCE_TAG}-nosrc"`, leave `doi` and `arxiv` empty, put the canonical
  URL in `link`, and write the FULL APA-7 reference in `apa` from the title page,
  publisher record or library catalog, with every author (and the publisher for a book).
  Say in `note` where you confirmed it. There is no cap on these, but include only work
  widely cited in the literature.
- `first_author`, `year` and `title` are read OFF THE LANDING PAGE. They are what the
  next phase verifies the DOI against, so they must describe the paper the DOI resolves to.
- `summary`: two to four sentences written ONLY from the paper's abstract: what it did
  and what it found. No priority, impact or lineage claims ("the first", "classic",
  "seminal") unless the abstract makes them, and no details the abstract does not state.
  Every summary is checked against the abstract later, and unsupported ones are rewritten.
- `tag`: one of `classic`, `recent-review`, `recent-empirical`, `recent-method`,
  `recent-theory`, `recent-LLM`, `recent-clinical`.
- **Never drop an on-topic paper because another lane might own it.** Include it and set
  `lane_fit` to the lane letter it fits better; duplicates across lanes are removed
  automatically by DOI and arXiv id.
- `deferred` is ONLY for a paper you handed to a different, named lane (`to_lane`) that
  you believe will include it. When in doubt, include the paper yourself with `lane_fit`.
  `first_author` and `year` are required on every deferred entry: the merge confirms a
  deferred paper by title plus those fields, and fails on any deferred paper no lane kept.
- `excluded` is ONLY for a paper outside the bibliography's scope, a pre-{TIER_BOUNDARY_YEAR}
  paper that does not clear the classic bar, or (in a capped search) an on-topic paper
  over the cap — each with its `title`, `reason`, `first_author` and `year`. Excluded
  papers are listed on the spreadsheet's "Considered and excluded" sheet.
- Set `status.returned` to the number of papers, and `websearch_exhausted` to true if your
  web search stopped working; say in `notes` how you continued.

## Verification duty — read this twice

Every citation you return is machine-verified against CrossRef, DataCite, PubMed and the
arXiv API in the next phase. In past runs about one in four agent-returned citations had a
fabricated author list, a wrong year, a mis-copied DOI or arXiv id, or a reversed
conclusion. With this section in the brief, a 1,050-paper build had none.

1. **Visit the actual landing page** for every paper (PubMed, the journal, bioRxiv, the
   arXiv abstract page) and read the author list off it. Many papers have similar titles;
   do not reconstruct authors from memory or a search snippet.
2. **Confirm the first author and the year** on that page. Long author lists are where
   first authors get mis-ordered.
3. **Confirm the DOI or arXiv id resolves to the paper you mean**, not just that it
   resolves: invented DOIs often resolve to an unrelated real paper.
4. **Read the abstract before writing the summary.** Do not invert the finding.
5. Judge a DOI by what it resolves to, never by the shape of its string.
6. If you cannot confirm a paper, leave it out and list it in `could_not_confirm`.

## Output

Use the `Write` tool. The file must be valid JSON: parse it back with
`python3 -c "import json;d=json.load(open('{OUTPATH}'));print(len(d['papers']))"` and fix
it if that fails. Write it incrementally (write what you have, then extend it every ~10
papers), so a stall loses nothing. If you need a helper script, put it only in
`{SCRATCH_DIR}` (other lanes run at the same time and share the project folder). Never
read or write anywhere else except web fetches. Do NOT delegate to subagents.

Then reply with, and only with: the count of papers written, the year range, and the
numbers deferred, excluded and could not confirm.
