# Literature search subagent prompt — TEMPLATE

Fill in the `{PLACEHOLDERS}` and pass the result as the `prompt` field of an
Agent call (subagent_type: `general-purpose`). The agent has WebSearch +
WebFetch and will return a curated list. Do NOT trust its citations — verify
them all in Phase 3.

**Antecedents variant (Phase 2b).** This same template is reused for the required
antecedents pass. For that pass, FLIP the tier emphasis: the target is
foundational / classic / highly-cited work that PRE-DATES the modern literature
(methodology origins, foundational empirical results, or theory), not recent
papers. Run one agent per axis, set `{TIER_BOUNDARY_YEAR}` so "classic" dominates,
and expect some no-DOI books/chapters (handle per Phase 2b).

---

You are doing a literature search for an academic neuroscience review on the
**{REVIEW_TITLE}** by {LAB_NAME}. I need you to identify papers relevant to
ONE specific topic: **{TOPIC_NAME}**.

## What "{TOPIC_NAME}" means in this review

{TOPIC_DEFINITION}
<!-- 3-5 sentences. Include: brain regions, methods, theoretical positions,
     contested claims, what's IN scope and what's OUT of scope (adjacent
     topics covered separately). -->

## What I already have (DO NOT re-include these)

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

## Aim for ~{TARGET_COUNT} papers, balanced across

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
(`pubmed.ncbi.nlm.nih.gov`). Verify each paper actually exists by fetching
its abstract page before including it.

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
    "apa": "", "summary": "3-5 sentences from the actual abstract; do not invert findings.",
    "tag": "classic", "topic": "{TOPIC_NAME}", "source": "search", "note": "", "lane_fit": ""}],
 "deferred": [{"title": "...", "doi": "", "reason": "fits lane X better", "to_lane": "X"}],
 "could_not_confirm": [{"title": "...", "reason": "no such paper under any similar title"}]}
```

- Every paper needs a DOI or an arXiv id. arXiv-only: set `arxiv` to the bare id and
  `doi` to `10.48550/arXiv.<id>`. A book, chapter, report or essay with neither: leave
  `doi` empty, give its URL in `link` if any, and write the full APA-7 reference in
  `apa` from the title page or publisher record, with every author.
- `first_author`, `year` and `title` are read off the landing page. They are what
  the next phase verifies the DOI against.
- **Never drop an on-topic paper because another search might own it.** Include it
  and set `lane_fit` to the better-fitting area; duplicates are removed later.
- List in `deferred` every paper you found and left out on purpose, with the reason.
- Set `status.returned` to the number of papers, and `websearch_exhausted` to true if
  your web search stopped working; say in `notes` how you continued.

Balance `tag` across: `classic` | `recent-review` | `recent-empirical` |
`recent-method` | `recent-LLM` | `recent-theory` | `recent-clinical`.

Quality over quantity for pre-{TIER_BOUNDARY_YEAR}, err toward inclusion for recent work.

**Important:** Many published papers have similar titles. Always confirm
the first author and year by visiting the actual landing page (PubMed,
journal, or arxiv). Do not invent author names or invert findings — the
review needs accurate citations.
