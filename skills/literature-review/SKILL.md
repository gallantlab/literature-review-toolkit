---
name: literature-review
license: MIT
metadata:
  version: 1.31.1
  author: Jack L. Gallant
description: Structured academic literature review — search a topic and its antecedents, verify every citation against PMC/PubMed/CrossRef/arXiv, rebuild references into canonical APA form, count citations, cross-reference the set, and assemble an annotated xlsx bibliography, then offer an interactive lineage timeline of its theoretical families on every review. Use whenever the user asks for a lit review or literature review, wants to build or audit a bibliography, survey the literature on a topic, verify or canonicalize a list of citations, check which references cite which, gather citation counts, trace the intellectual lineage of a field, or review a lab's own corpus in the context of its field. PDF acquisition is opt-in and never runs by default.
---

# Literature review

Scaffolding that drives an agent through a structured literature review. The agent
does the judgment work; the scripts do the API calls, verification and bookkeeping
that keep it honest. Paths below are relative to the toolkit root.

## Start here: scale, preflight, then the playbook

1. **Read the scale from how the user describes the review.** "A quick look" is
   `scan`, "the core literature" is `focused`, "about N papers" is N, "everything"
   is `exhaustive`, and no word about size is `standard`. Ask once if it is
   ambiguous (PLAYBOOK Phase 1d). The code applies it: targets, caps and the
   preflight estimate.

2. **Run the preflight before any new search.**

   ```bash
   python3 tools/preflight.py --project <topic dir> --scale <scale>
   ```

   Exit 0: go on. Exit 2: stop, and ask the user before launching any lane.
   - If GitHub has a newer toolkit, the preflight prints the install command.
     Offer it, install only on a yes, and rerun the preflight.
   - If a key (`OPENALEX_API_KEY`, `S2_API_KEY`) is missing or rejected, or the
     OpenAlex budget is short, it prints three choices. Put them to the user and
     let them pick: (1) get the API keys (both free), (2) cap the search, or
     (3) be prepared to wait.
   - A missing `LITREVIEW_EMAIL` also exits 2, and no choice clears it.

   Record the user's pick with `--accept cap`, `--accept wait` or
   `--accept current-version`. The run writes `<topic dir>/preflight.json`, and
   `merge_lanes.py` refuses to build a table without a recent, cleared one. A
   build already under way keeps its version: pass `--no-update-check`.

3. **Then read `PLAYBOOK.md` and follow it.** It is the authoritative procedure;
   this file only points to it. The playbook holds the operating contract, every
   phase, and the lessons learned from mistakes already made once.

The rendered documentation is at <https://gallantlab.org/literature-review-toolkit/>.

## Layout

The repository is a plain Python toolkit that can also be installed as a Claude
plugin. Nothing in it requires Claude.

| Path | What it is |
|---|---|
| `PLAYBOOK.md` | The procedure. Start here. |
| `tools/` | The scripts, each standalone (JSON in, JSON or files out), plus the lane and family prompt templates (`search_prompt_template.md`, `family_prompt_template.md`). |
| `tools/README.md` | The tool index: purpose, phase and flags for every script. |
| `tools/checks/` | Node.js checkers that execute a rendered figure or viewer page. |
| `templates/` | `build_rows_template.py`, a starter script for building `rows.json`. |
| `docs/` | Source for the documentation site. |

The tool index is generated into `tools/README.md`, `docs/tools.md` and
`PLAYBOOK.md`. Read it there; it is not copied here, so this file cannot drift from
the scripts.

## Two modes

- **Topic mode** starts from a query and searches outward. It is the default.
- **Lab mode** starts from a lab's publications, derives its themes and how they
  changed, then searches outward to place that work in the field.

From verification on, both run the same pipeline.

## Contact email

NCBI and CrossRef expect a contact email. Export `LITREVIEW_EMAIL` once, or pass
`--email` to each tool. A network tool with neither stops with a usage error
(exit 2).

## Working rules

- **Three human decision points**: scope (including the scale), the families, and
  the optional write-up. Everything between them runs automatically behind gates.
  Do not pass one without asking.
- **Always offer the timeline.** Propose the families and pitch the timeline as soon
  as the rows are verified, without waiting to be asked. The user uses the families,
  changes them, or skips the timeline (PLAYBOOK Phase 6b).
- **Verification is not optional.** `verify.py` exits 1 unless every verdict is OK.
  Treat that as a stop: fix or drop each flagged row, or record a false alarm with
  `--override REF --reason`.
- **PDF download is opt-in.** Run `download.py` (Phase 4) only when the user asks
  for PDFs.
- **Do not hand-curate what a script generates.** Reference formatting, citation
  counts, lane briefs and the tool index each have a script that owns them. Fix the
  script, or record a reference correction in `hand_fixes.json`.
- **Only `spreadsheet.py` writes the deliverable, and only after the audit passes.**
  It runs the full audit (verify stamps, hand checks, summary checks, acknowledged
  warnings) and refuses a failing table. `--draft` writes a marked draft instead,
  never the deliverable.
