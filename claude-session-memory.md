# Session memory — literature-review-toolkit

Current status and recent sessions. Newest first. Dated archives
(`claude-session-memory-YYYY-MM-DD.md`) hold anything rotated out of here.

## Carry-forward (read this first)

**Where the toolkit stands.** Version 2.10.0. Every numbered rule in the
PLAYBOOK contract now has code behind it; rule 5 (temporal order of ideas) was
the last one, closed 2026-11-06. 1,569 regression checks in
`tools/tests/test_formatting.py` (script-style, no pytest), ruff clean, CI on
Python 3.10 / 3.12 / 3.14, `mkdocs build --strict` clean.

**Working rules that keep biting if forgotten.**

- Versions are computed from git history. Every commit carries a
  `Version-Bump:` trailer; stamp LAST with
  `python3 tools/gen_docs.py --bump <level>`, then commit everything the stamp
  saw. `gen_docs.py --check` is the CI gate for generated doc blocks.
- A registry in the owning module is the single source of truth; prose points
  at it (`priority_check.TRIGGERS`, `spreadsheet.SOURCES`) instead of copying
  it, and a test gates the drift.
- Anything checkable becomes a tool that refuses. Prose is only for judgment
  and agent briefs.

**Open gaps, stated but not assigned.**

- No end-to-end run of `status.py` / `handoff.py` / `priority_check.py` driven
  by an agent. They have been run by hand against two finished corpora and
  eight rewound stages of one of them.
- Lab mode is detected by `status.py` but its phases are not modeled.
- `handoff.py` cannot tell a declined timeline from one never offered. Stated
  in the tool and in the playbook; the agent has to say which.
- A third corpus would likely find more. The two we have (544 rows,
  biochemistry; 67 rows, MRI physics) sit at opposite ends of one axis that
  already broke a tool — see below.

## 2026-11-07 — validating the new tools against a second real corpus

The session before this one built `priority_check.py` (Phase 7),
`handoff.py` (Phase 8) and `status.py`, all tuned and tested against the GNE
corpus. The question that drove today: **how do we know this works?** Tokens
were explicitly deprioritized in favor of correctness.

**First test: eight rewound stages of the GNE build** (lanes only → merged →
verified → canon → counts → no families → no workbook → complete), rebuilt
from the real artifacts rather than fixtures. Two `status.py` defects:

- A permanently outstanding step swallows the next command for everything
  behind it. The reference audit was always `todo`, so a *finished* build
  answered "run the audit" instead of "hand off", forever. Fixed by
  inference: `spreadsheet.py` refuses to write a non-draft workbook unless
  the audit passed, so a workbook newer than `rows.json` is proof it passed,
  and an older one is evidence that has lapsed.
- A build with no families file proposed nothing. The timeline is *offered*
  on every review (Phase 6b) — the user may decline, the agent may not skip
  the offer. It is outstanding work.

Pushed as `68fd7f1`.

**Second test: `mri_brain_stimulation_2026-11-02`** — the review built three
days before GNE. 67 rows, four lanes, another session, another subject.
`handoff.py` was clean on a corpus it had never seen. The other two were not,
and all three findings were in the *judgment* half that no gate watches.
Fixed and committed as `ee9876a` (v2.10.0):

1. **`status.py` verify step counted rows `verify.py` cannot reach.** The
   13 unverified rows were exactly the 13 DOI-less ones — `verify.py` works
   from a DOI or arXiv id, and those rows are settled by the hand check,
   which has its own line. A delivered build read "54 of 67 verified" forever
   and `--next` proposed a re-run that could not move the number. Same shape
   as the earlier `s_canon` fix: counting a stamp that one legitimate path
   never produces.
2. **`status.py` and `handoff.py` disagreed off the same `_runs` record.**
   status called the short xref/forward passes outstanding work; handoff
   called the same fact normal. A pass that *read* fewer papers than the table
   now holds is the normal shape after candidates are appended. Only a pass
   that did not *finish* is work.
3. **`priority_check.py`'s overlap floor was not portable.** Measured over
   every (claim, row) pair: GNE's best is **1.00** with 99 pairs over 0.45;
   the MRI corpus's best *anywhere* is **0.33**, so the fixed 0.45 could never
   list anything, and Barker 1985 — the priority paper for human magnetic
   stimulation, under a sentence claiming the first human stimulation — sat at
   0.29 and was never shown. The number measures how much a review's prose
   repeats its own titles' vocabulary, which is a property of the subject.
   `calibrate()` now measures the floor per run as a share of the corpus
   high-water mark: GNE lands on 0.45 and reproduces its old output exactly
   (8 claims / 14 lines), MRI on 0.15 and its real candidate.
   **Rejected on evidence:** scaling to each *claim's* own best over-lists
   badly — it promotes the top of a weak pool, where candidates are generic
   papers on the subject rather than antecedents (82 lines on GNE where 14 is
   right). Don't retry it.
4. **An origin claim citing NOTHING escaped both halves** — no group to gate,
   no year to be older than. *"That letter is the origin of transcranial
   magnetic stimulation"* shipped in a delivered review uncited and
   unremarked. Now listed against the whole corpus and labeled.

**The lesson worth carrying:** a tool validated only on the corpus it was
tuned against cannot tell you what you overfitted to. One untuned corpus found
three defects that 1,558 regression checks and a finished-build run did not.

## Earlier in 2026-11 — the playbook-to-code work

PLAYBOOK.md went 113,316 → 103,052 → ~105,115 chars across the stage; net
~2,050 tokens/run saved, all of it from the first two stages. The Phase 7 and
Phase 8 stage *adds* about 500 tokens/run and was kept for correctness, not
economy. Also closed in that stretch: the Python floor (CI matrix 3.10 / 3.12
/ 3.14; the claimed 3.9 floor was stale and unverifiable — 3.9 reached EOL in
October 2025 and no longer installs on the runner image), and a real citation
inversion in the delivered GNE review, fixed at the emitter rather than in the
output.

**Environment gotchas that cost time.** Pushing needs
`allowed_domains: ["github.com"]` in the sandbox; the credential-storage-lock
message on push is benign. `gh` fails TLS verification in the sandbox — use
`curl` against api.github.com. zsh eats `$rev:PLAYBOOK.md` as a history
modifier; quote it as `"${rev}:PLAYBOOK.md"`. An exit code read through a pipe
is the pipe's, not the command's.
