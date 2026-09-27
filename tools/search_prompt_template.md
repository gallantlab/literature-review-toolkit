# Literature search subagent prompt — TEMPLATE

Fill in the `{PLACEHOLDERS}` and pass the result as the `prompt` field of an
Agent call (subagent_type: `general-purpose`). The agent has WebSearch +
WebFetch and writes one lane file (schema 2) that `tools/merge_lanes.py` reads.
Do NOT trust its citations — verify them all in Phase 3.

**Capped search.** Only if the user chose to cap the search at the Phase-0
preflight, keep the "*Exception — a CAPPED search*" sentence under "What to
return"; otherwise delete it before sending.

**Seed titles.** `{SEED_TITLES}` is an optional bullet list of landmark TITLES the lane
should cover, never author names (remembered author names have injected fabricated
attributions; about a third of remembered titles turn out not to exist as typed).
Delete the "Landmark titles" section if you have none.

**Lab mode.** Add to the topic definition: "A paper with {LAB_PI} as an author is the
lab's own; do not put it in `papers`. List it in `deferred` with `to_lane: "L"`" when
the lab's record is merged as lane `L`, so a deferral the record lacks exposes a gap
in the lab's record.

**Antecedents variant (Phase 2b).** This same template is reused for the required
antecedents pass. For that pass, FLIP the tier emphasis: the target is
foundational / classic / highly-cited work that PRE-DATES the modern literature
(methodology origins, foundational empirical results, or theory), not recent
papers. Run one agent per axis, set `{TIER_BOUNDARY_YEAR}` so "classic" dominates,
and expect some no-DOI books/chapters (handle per Phase 2b). In the JSON example,
change `"source": "search"` to `"source": "anteced"` (`"anteced-nosrc"` for a paper
with no DOI), so the spreadsheet colors antecedents lilac.

---

You are doing a literature search for an academic neuroscience review on the
**{REVIEW_TITLE}** by {LAB_NAME}. I need you to identify papers relevant to
ONE specific topic: **{TOPIC_NAME}**.

## What "{TOPIC_NAME}" means in this review

{TOPIC_DEFINITION}
<!-- 3-5 sentences. Include: brain regions, methods, theoretical positions,
     contested claims, what's IN scope and what's OUT of scope (adjacent
     topics covered separately). -->

## What the corpus already has (DO NOT re-include these)

{ALREADY_HAVE_LIST}
<!-- Bullet list of existing papers, each one line: First Author Year — title -->

## Selection criteria — TWO TIERS

- **Pre-{TIER_BOUNDARY_YEAR}**: ONLY include if highly impactful / well-cited
  / foundational. Think classic, canonical work.
- **{TIER_BOUNDARY_YEAR}–present**: Be promiscuous. Include even if not yet
  highly cited — they haven't had time. Anything methodologically interesting,
  addressing an open question, or extending a major framework is worth
  including.

The current date is {TODAY}. Search for papers up through today.

## Aim for ~{TARGET_COUNT} papers (a floor, not a cap: see "What to return"), balanced across

1. Classic / foundational (pre-{TIER_BOUNDARY_YEAR}, high impact)
2. Recent reviews and updates ({TIER_BOUNDARY_YEAR}-present)
3. Recent empirical work using {RELEVANT_METHODS}
4. Recent theoretical / computational advances
5. Recent {DOMAIN_SPECIFIC_CATEGORY} (e.g. clinical, lesion, intracranial)

## How to search

Use WebSearch and WebFetch. Try multiple query variants for each angle:

{SEARCH_QUERIES}
<!-- One bulleted line per query. Mix broad and narrow. Include some with
     explicit recent years (2024, 2025, etc.) -->

Search both Google Scholar (via `scholar.google.com` URLs) and PubMed
(`pubmed.ncbi.nlm.nih.gov`). Google Scholar often blocks automated fetches; if
it does, use PubMed, arXiv and publisher pages instead. Follow the reference lists
and "cited by" lists of the landmark papers you find; that is usually more
productive than more query variants.

If WebSearch stops working (the budget is shared by every agent running at once),
continue through PubMed E-utilities (`eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi`),
Semantic Scholar (`api.semanticscholar.org/graph/v1/paper/search`), OpenAlex
(`api.openalex.org/works?search=`), CrossRef (`api.crossref.org/works?query=`) and the
arXiv API with WebFetch. That is a first-class route, not a degradation.

## Landmark titles this lane should cover

These are paper TITLES ONLY, from memory, and some may be wrong or not exist. Find
each one, read its real title, authors and year off the landing page, and include it
if it fits. Do not trust an author name you have not read off a landing page. If a
title does not exist under any similar wording, list it in `could_not_confirm`.

{SEED_TITLES}

## What to return

Write ONE JSON object to `{OUTPATH}` with the Write tool, then parse it back with
`python3 -c "import json;json.load(open('{OUTPATH}'))"` and fix it if that fails.
Write it incrementally if you are worried about time, so no work is lost.

```json
{"schema": 2,
 "lane": "{LANE_KEY}",
 "status": {"target": {TARGET_COUNT}, "returned": 0, "websearch_exhausted": false, "notes": ""},
 "papers": [
   {"ref": "{LANE_KEY}-01", "doi": "10.xxxx/yyyy", "arxiv": "", "link": "https://doi.org/10.xxxx/yyyy",
    "first_author": "Family, I. I.", "year": 2022, "title": "Title as on the landing page",
    "apa": "", "summary": "2-4 sentences written ONLY from the abstract.",
    "tag": "classic", "topic": "{TOPIC_NAME}", "source": "search", "note": "", "lane_fit": ""}],
 "deferred": [{"title": "...", "doi": "", "first_author": "", "year": "", "reason": "fits lane X better",
              "to_lane": "X"}],
 "excluded": [{"title": "...", "doi": "", "first_author": "", "year": "", "reason": "governance as such"}],
 "could_not_confirm": [{"title": "...", "reason": "no such paper under any similar title"}]}
```

- Every paper needs a DOI or an arXiv id. arXiv-only: set `arxiv` to the bare id and
  `doi` to `10.48550/arXiv.<id>`. A book, chapter, report or essay with neither: leave
  `doi` empty, give its URL in `link` if any, and write the full APA-7 reference in
  `apa` from the title page or publisher record, with every author.
- `first_author`, `year` and `title` are read off the landing page. They are what
  the next phase verifies the DOI against.
- `summary`: 2-4 sentences written ONLY from the paper's abstract: what it did and what
  it found. No priority, impact or lineage claims ("the first", "classic", "seminal")
  unless the abstract makes them, and no details the abstract does not state. Every
  summary is checked against the abstract later (Phase 5c); on one build this rule cut
  unsupported summaries from 41% to 5%.
- **Never drop an on-topic paper because another search might own it.** Include it
  and set `lane_fit` to the better-fitting area; duplicates are removed later.
- **The target is a floor, not a cap.** Never leave out an on-topic paper to stay near
  it — "lower priority" or "trimmed to target" is not a reason to drop a paper.
  *Exception — a CAPPED search*: the target is a hard cap of {TARGET_COUNT}; keep the
  most important papers, and list every on-topic paper over the cap in `excluded` with
  reason `over the capped-search limit`, so it is shown, not lost.
- `deferred` is ONLY for a paper you handed to a different, named lane (`to_lane`) that
  you believe will include it; when in doubt, include it yourself with `lane_fit`.
  `first_author` and `year` are required on every deferred entry: the merge step needs
  them to confirm a deferred paper by title alone, and fails the merge on any deferred
  paper no lane kept.
- `excluded` is ONLY for a paper outside the review's scope, a pre-{TIER_BOUNDARY_YEAR}
  paper that does not clear the classic bar, or (in a capped search only) an on-topic
  paper over the cap — each with its `title`, `reason`, `first_author` and `year`.
  Excluded papers are listed on the spreadsheet's "Considered and excluded" sheet.
- Set `status.returned` to the number of papers, and `websearch_exhausted` to true if
  your web search stopped working; say in `notes` how you continued.

Balance `tag` across: `classic` | `recent-review` | `recent-empirical` |
`recent-method` | `recent-LLM` | `recent-theory` | `recent-clinical`.

Quality over quantity for pre-{TIER_BOUNDARY_YEAR}, err toward inclusion for recent work.

## Verification duty — read this twice

Every citation you return is machine-verified against CrossRef, DataCite, PubMed and
the arXiv API in the next phase. In past runs about one in four agent-returned
citations had a fabricated author list, a wrong year, a mis-copied DOI or arXiv id, or
a reversed conclusion. With this section in the brief, a 1,050-paper build had none.

1. **Visit the actual landing page** for every paper (PubMed, the journal, bioRxiv, the
   arXiv abstract page) and read the author list off it. Many papers have similar
   titles; do not reconstruct authors from memory or a search snippet.
2. **Confirm the first author and the year** on that page. Long author lists are where
   first authors get mis-ordered.
3. **Confirm the DOI or arXiv id resolves to the paper you mean**, not just that it
   resolves: invented DOIs often resolve to an unrelated real paper.
4. **Read the abstract before writing the summary.** Do not invert the finding.
5. Judge a DOI by what it resolves to, never by the shape of its string.
6. If you cannot confirm a paper, leave it out and list it in `could_not_confirm`.

## Output

Write the file incrementally (write what you have, then extend it), so a stall loses
nothing. If you need a helper script, put it only in `{SCRATCH_DIR}` (other lanes run
at the same time and share the project folder). Do NOT delegate to subagents. Then
reply with only: the count of papers written, the year range, and the numbers
deferred, excluded and could not confirm.
