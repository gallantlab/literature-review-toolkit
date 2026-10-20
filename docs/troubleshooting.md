# Troubleshooting

This page lists failures and their fixes, for developers running the steps. For
the problems a user is likely to meet, see
[If something goes wrong](tutorial.md#if-something-goes-wrong) in the tutorial.

---

## Network failures that look alike

Four different failures all look like "the fetch broke". Backing off fixes only
the first.

| Symptom | Cause | Fix |
|---|---|---|
| HTTP 429 responses spread across many URLs, easing with delay | throttling | raise `--sleep`; set `S2_API_KEY` |
| Every OpenAlex request returns 429 with a wait of hours (`OpenAlexBudgetError`) | the free daily budget is spent | set `OPENALEX_API_KEY`, or wait for the reset ([Run the preflight](search.md#run-the-preflight-phase-0)) |
| `IncompleteRead` on particular large records, failing at the same byte count every time | a truncated uncompressed response | request gzip; `common.http` already does |
| One URL fails under `urllib` but works under `curl`, including a large Semantic Scholar batch read short (Semantic Scholar ignores gzip) | client incompatibility | `common.curl_get`, which the tools try automatically for GET and POST requests; Semantic Scholar batch requests go to curl directly |

If retries never converge, the diagnosis is wrong. To tell which case applies,
run `curl -sS --compressed` on one failing URL.

## The audit fails

`references.py --audit` names each defect. Fix the row in `rows.json` and rerun.
Do not relax the gate.

| Defect | Fix |
|---|---|
| a formatting defect: `empty venue`, `no-year`, `no-authors`, `et-al`, `malformed-initial`, `mangled-punct`, `missing-space`, `html-entity`, `markup-tag`, `uppercase-title run` (a `?` inside a URL is not `mangled-punct`) | fix the `apa` by hand, or run `--repair` for markup, hyphen and `?.` damage |
| `unverified (...)` | `verify.py --rows rows.json --only <refs>`, then re-canon those rows |
| `hand-check-missing` | `handcheck.py --prepare`, the hand-check agent, then `--ingest` ([Hand-check references with no DOI](checks.md#hand-check-references-with-no-doi-phase-3e)) |
| `summary-unchecked`, `summary-flagged` | `summary_audit.py`; fix a flagged summary and check it again ([Check every summary](checks.md#check-every-summary-phase-5c)) |
| `no-summary` | write a summary from the abstract, then check it |
| `abstract-wrong` | add the real abstract as a landing-page entry, rewrite the summary, and check it again |
| `hand-fix-lost` | run `references.py` to re-apply `hand_fixes.json`, or update the fix if the row changed ([Rebuild every reference](checks.md#rebuild-every-reference-phase-3f)) |
| `candidates-pending` | `candidates.py --prepare`, the agents, then `--ingest` ([Decide the candidates](checks.md#decide-the-candidates)) |
| `candidate ... is marked include but is not in the table` | `--export-included`, `merge_lanes.py --append`, then verify |
| `link-doi-mismatch` | make the row's `link` the DOI URL of its `doi` |
| an unacknowledged warning | fix the row, or acknowledge it ([Acknowledge warnings](checks.md#acknowledge-warnings)) |

## The source is wrong, not the corpus

- **CrossRef truncates some records**: an author list cut to one name, a subtitle
  dropped, a section heading deposited as the title. Compare with the publisher's
  landing page, and record the fix in `hand_fixes.json`.
- **A widely used DOI can be wrong.** PubMed and CrossRef confuse Felleman & Van
  Essen (1991) with that issue's preface, and 19 papers in one corpus cited the
  preface's DOI. A `MISMATCH` sometimes means the literature is wrong.

## Verification returns NOT-FOUND for real papers

The usual cause is arXiv rate limiting. `verify.py` batches arXiv lookups to
prevent it. If a cluster of preprints still comes back `NOT-FOUND`, rerun before
treating them as invented.

## The timeline hides landmarks or looks wrong

| Symptom | Cause | Fix |
|---|---|---|
| Labels missing | the label cap bound | read the run's "N qualified, M labeled, K dropped" line and its dropped list, then raise `--max-labels` ([Tune the timeline](deliverables.md#tune-the-timeline-for-a-large-corpus)) |
| Dots bunched at the left | a long, sparse early history | `--time-warp 0.85` and `--min-year` |
| A family's claim is cut off | the copy beside the lane is truncated to fit | none needed; the full text appears on hover |
| Many hollow dots | poor citation-count coverage, or counts never attached | check coverage, and run `citations.py --attach-only` ([Fetch citation counts](checks.md#fetch-citation-counts-phase-5b)) |

## Citation counts look wrong

A famous old paper with a single-digit OpenAlex count is an undercount; compare
the Semantic Scholar column, and see
[Fetch citation counts](checks.md#fetch-citation-counts-phase-5b). A count that
dropped sharply after a DOI change may point at a shadow record rather than the
version of record.
