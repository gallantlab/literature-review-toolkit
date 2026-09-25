# literature-review-toolkit

Scripts that let an LLM agent (Claude or another) run a literature review without
fabricating references. The agent decides what to search, how to group the
papers, and how to write them up. The scripts do the API calls, verification and
bookkeeping.

Version 1.15.0 · MIT license

📖 **Documentation: <https://gallantlab.org/literature-review-toolkit/>**, with the
[operator manual](https://gallantlab.org/literature-review-toolkit/manual/),
[tools reference](https://gallantlab.org/literature-review-toolkit/tools/) and
[worked examples](https://gallantlab.org/literature-review-toolkit/examples/).

## What it does

A review has two modes. **Topic mode** starts from a question and searches
outward. **Lab mode** starts from a lab's publications, derives its research
themes, and places them in the field. Both then run the same pipeline:

1. **Search**, plus a required **antecedents** pass for the field's roots.
2. **Verify** every citation against PubMed, PMC, CrossRef and arXiv. Search
   agents fabricate roughly 1 in 4.
3. **Canonicalize** every reference from its verified DOI into APA-7, behind a
   hard audit gate.
4. **Build the spreadsheet**, add **citation counts** (OpenAlex, checked against
   Semantic Scholar), and mine the corpus's reference lists for papers it missed.
5. **Offer the lineage timeline** on every review: the agent proposes
   **theoretical families**, and you use them, change them, or skip the timeline.
   If kept, it renders an interactive timeline of the families.
6. Optionally, write an AI-authored **review article**.

Each topic gets an annotated `.xlsx` bibliography and, unless you skip it, the
lineage timeline. PDF download is opt-in.

## Install

```bash
git clone https://github.com/gallantlab/literature-review-toolkit.git
cd literature-review-toolkit
pip install -r requirements.txt
export LITREVIEW_EMAIL=you@institution.edu   # NCBI and CrossRef require a contact email
```

`brew install poppler` (or `apt-get install poppler-utils`) is needed only for
the opt-in PDF step.

## Use

Open Claude Code in the directory that holds your reviews, with this repo cloned
inside it, and describe the review:

```text
i want a literature review on the anatomical connections between the visual
system and the cerebellum. any anatomy papers from primate or human, using any
tractography method. go back as far as the 1970s.
```

The agent follows [`PLAYBOOK.md`](./PLAYBOOK.md), creates one subdirectory per
topic, and delivers the spreadsheet there. To run the phases by hand, see
[§5 of the manual](https://gallantlab.org/literature-review-toolkit/manual/#5-the-shared-backbone);
every phase is one script in [`tools/`](./tools).

## Repository layout

| Path | Contents |
|---|---|
| [`PLAYBOOK.md`](./PLAYBOOK.md) | the procedure the agent follows, with its accumulated lessons |
| [`tools/`](./tools) | one script per phase, plus the shared `common.py` |
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
DOI; summaries and interpretation cannot be machine-checked. See the
[full disclosure](https://gallantlab.org/literature-review-toolkit/#ai-disclosure).

## License

MIT; see [`LICENSE`](./LICENSE).
