# Candidate decision brief — TEMPLATE

Do not fill this by hand. `tools/candidates.py --prepare DIR --scope FILE` renders
it into DIR/BRIEF.md, fills every `{PLACEHOLDER}`, and writes the input files it
names. Everything above the `BRIEF STARTS` marker is these notes and is never sent.
`candidates.py --ingest 'DIR/result_*.json'` reads the agents' answers back and
refuses a file with a missing reason or an include without its landing-page claim.

<!-- BRIEF STARTS -->
# Decide cross-citation candidates for the bibliography

**The bibliography.** Read `{SCOPE_FILE}` first. It defines the bibliography, its
lanes, what is out of scope, and the tier rule for older papers. If it is one
search lane's brief, use its description of the bibliography, its lane table and
its selection criteria, and ignore the instructions meant for that lane's
searcher. A paper may go to any lane, not only the one that brief was for. The
lanes are:

{LANE_TABLE}

**The candidates.** Each candidate in your input file is a paper the bibliography
does not yet hold. Either at least {XREF_FLOOR} papers in the bibliography cite it
(source `xref`), or it cites at least {FORWARD_FLOOR} of them (source `forward`).
The counts are in `sources`.

**Your input:** `{INPUT_DIR}/input_NN.json` (the NN you were given). **Your output:**
`{INPUT_DIR}/result_NN.json`, with the same NN.

For EACH candidate, decide `include` or `exclude`, with a one-line reason.

- **include**: the paper is squarely inside one lane of the bibliography, and it
  clears the tier rule in the scope file.
- **exclude**: out of scope per the scope file; OR a second copy of a paper the
  bibliography holds (a preprint of a published paper, a reprint, a repository
  copy, a book review); OR not identifiable. Name the reason.

Many titles are clear on their own. When a title is ambiguous or missing, open
`https://doi.org/<doi>` and read the landing page. Do not guess.

**For every included paper, read its landing page** and record, OFF THE PAGE:
`first_author` ("Family, I."), `year`, `title` exactly as on the page, `arxiv` (the
id, if any), `lane` (the letter it fits best), and `summary`: two to four sentences
written ONLY from the abstract. No priority, impact or lineage claims ("the first",
"classic", "seminal") that the abstract does not make. Every include is verified
against CrossRef later; a claim not read off the page will fail there.

Write `result_NN.json` as a JSON list with one entry per candidate:

```json
[{"doi": "10.xxxx/yyyy", "decision": "include", "reason": "one line",
  "first_author": "Family, I.", "year": 2019, "title": "As on the page",
  "arxiv": "", "lane": "V", "summary": "Two to four sentences from the abstract."},
 {"doi": "10.xxxx/zzzz", "decision": "exclude", "reason": "one line"}]
```

Write it incrementally and parse it back with
`python3 -c "import json;print(len(json.load(open('{INPUT_DIR}/result_NN.json'))))"`.
If you need a helper script, give it a unique name inside `{INPUT_DIR}`; other
agents work in parallel. Never read or write outside `{PROJECT_DIR}` except web
fetches. Do NOT delegate to subagents.

Reply with only: included N, excluded N.
