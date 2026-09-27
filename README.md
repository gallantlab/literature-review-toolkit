# literature-review-toolkit

Scripts that let an LLM agent (Claude or another) run a literature review without
fabricating references. The agent decides what to search, how to group the
papers, and how to write them up. The scripts do the API calls, verification and
bookkeeping.

Version 1.34.0 · MIT license

📖 **Documentation: <https://gallantlab.org/literature-review-toolkit/>**, with the
[operator manual](https://gallantlab.org/literature-review-toolkit/manual/),
[tools reference](https://gallantlab.org/literature-review-toolkit/tools/) and
[worked examples](https://gallantlab.org/literature-review-toolkit/examples/).

## What it does

A review has two modes. **Topic mode** starts from a question and searches
outward. **Lab mode** starts from a lab's publications, derives its research
themes, and places them in the field. Both then run the same pipeline:

1. **Search** in parallel lanes, plus a required **antecedents** lane for the
   field's roots.
2. **Verify** every citation against PubMed, PMC, CrossRef, DataCite and arXiv.
   Without a duty to verify, search agents got about 1 in 4 citations wrong.
3. **Canonicalize** every reference from its verified DOI into APA-7.
   References with no DOI get a hand check.
4. **Count citations** (OpenAlex, checked against Semantic Scholar), and check
   every summary against its paper's abstract.
5. **Mine the corpus** for papers the search missed: its reference lists, and
   the papers that cite its landmarks.
6. **Offer the lineage timeline** on every review. The agent proposes
   **theoretical families**, and you use them, change them, or skip the
   timeline. If you keep it, the toolkit renders an interactive timeline of the
   families.
7. **Build the spreadsheet.** It runs the full audit and refuses a table that
   fails it.
8. Optionally, write an AI-authored **review article**.

Each topic gets an annotated `.xlsx` bibliography and, unless you skip it, the
lineage timeline. PDF download is opt-in. Plan on hours, not minutes: in one
1,158-paper build the search lanes alone took about 1.5 hours.

## What it needs

- **Python 3** with `xlsxwriter` and `python-docx` (`requirements.txt`).
- **A contact email** in `LITREVIEW_EMAIL`. NCBI and CrossRef require one.
- **Two free API keys.** `OPENALEX_API_KEY`
  ([get one](https://help.openalex.org/api/authentication)) gives you your own
  daily budget. Without it, every client on one IP address shares a single
  budget, and a campus network can spend it before you start. `S2_API_KEY`
  ([request one](https://www.semanticscholar.org/product/api#api-key-form))
  avoids Semantic Scholar's heavy throttling of keyless use.
- **Optional:** poppler (`brew install poppler` or
  `apt-get install poppler-utils`) for the opt-in PDF step, and `rsvg-convert`
  or Inkscape for PNG and PDF copies of the timeline.

## Install

In the directory that will hold your reviews:

```bash
git clone https://github.com/gallantlab/literature-review-toolkit.git
cd literature-review-toolkit
pip install -r requirements.txt
export LITREVIEW_EMAIL=you@institution.edu
export OPENALEX_API_KEY=...
export S2_API_KEY=...
```

To keep the variables across sessions, add the `export` lines to your shell
profile.

## Start a review

Open Claude Code in the directory that holds your reviews and describe the
review:

```text
i want a literature review on the anatomical connections between the visual
system and the cerebellum. any anatomy papers from primate or human, using any
tractography method. go back as far as the 1970s.
```

You can also say how big a search you want, in your own words:

| You say | You get |
|---|---|
| "a quick look at the key papers" | a scan, capped at about 15 papers per lane |
| "the core literature" | a focused search, capped at about 30 per lane |
| "about 300 papers" | a search capped at that total |
| "everything" | an exhaustive search, uncapped |
| nothing about size | the standard search: each lane's target is a floor, not a cap |

Every check runs at every size, so a smaller search is only smaller. The full
table is in [§4.1 of the manual](https://gallantlab.org/literature-review-toolkit/manual/#41-topic-mode).

Before it searches, the agent runs `tools/preflight.py`. If GitHub has a newer
version of the toolkit, the agent offers to install it. If a key is missing or
the OpenAlex budget is short, it stops and asks you to choose: get the API keys,
cap the search, or be prepared to wait. To run the same check yourself, see
[§2.3 of the manual](https://gallantlab.org/literature-review-toolkit/manual/#23-phase-0-run-the-preflight-before-every-new-search).

The agent then follows [`PLAYBOOK.md`](./PLAYBOOK.md). It creates one
subdirectory per topic and delivers the spreadsheet there. When the repo is
installed as a Claude Code plugin, its skill points the agent at the playbook.
Without the plugin, name the playbook in your request.

To run the phases by hand, see
[§5 of the manual](https://gallantlab.org/literature-review-toolkit/manual/#5-the-shared-backbone).
Every phase is one script in [`tools/`](./tools).

## Repository layout

| Path | Contents |
|---|---|
| [`PLAYBOOK.md`](./PLAYBOOK.md) | the procedure the agent follows, with its accumulated lessons |
| [`tools/`](./tools) | one script per phase, the shared `common.py`, the search-lane and family prompt templates, and Node.js checkers for the figure and the review page (`tools/checks/`) |
| [`templates/`](./templates) | a starter script for building `rows.json` |
| [`skills/`](./skills) | the Claude skill that points an agent at the playbook |
| [`.claude-plugin/`](./.claude-plugin) | manifests that make the repo installable as a Claude Code plugin |
| [`docs/`](./docs) | the documentation site (MkDocs) |

## AI disclosure

Most of this toolkit's code and documentation were written by Claude, Anthropic's
AI model, under the direction of Jack Gallant (Gallant Lab, UC Berkeley). What
the toolkit produces is also AI-generated: the search, the paper summaries
(written from abstracts, not full texts), the family groupings and the review
articles. The scripts verify every citation and rebuild every reference from its
DOI. Summaries and interpretation cannot be machine-checked. See the
[full disclosure](https://gallantlab.org/literature-review-toolkit/#ai-disclosure).

## License

MIT; see [`LICENSE`](./LICENSE).
