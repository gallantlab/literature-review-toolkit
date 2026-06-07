# Thematic-families prompt — TEMPLATE (Phase 6b)

Two steps with a human checkpoint between them. The orchestrator can do this
directly, or dispatch a sub-agent with structured output. `tools/families.py`
then validates + renders. Feed the corpus via `tools/families.py --digest`
(compact) or the raw `rows.json`.

---

## Step 1 — Propose families  (then STOP for the human checkpoint)

You are organizing a literature review on **{TOPIC_NAME}** into a few
**theoretical families** — groups defined by *what each paper fundamentally
commits to / is for*, NOT by method or sub-area.

Here is the corpus (one line each: `ref / topic / cites / author year / summary`):

{CORPUS_DIGEST}

Propose **{N_MIN}-{N_MAX} families** that satisfy ALL of:
- **Orthogonal to the Topic column.** Topic already captures method/sub-area; a
  family that mirrors it is useless. Find a *conceptual* axis that cuts across
  topics — a good family routinely unites textually-dissimilar papers and splits
  textually-similar ones. (This is why you must reason, not cluster by similarity.)
- **One clear organizing principle**, stated in a sentence (e.g. "grouped by what
  the model is *for*: compress / infer / control / map / simulate").
- **Roughly MECE** — every paper has one dominant home; few or no orphans.
- **Balanced enough to be useful** — no family swallowing >60% or left a singleton.

Return ONLY this JSON and then WAIT for the user to approve or revise the
definitions before assigning anything:
```json
{ "principle": "one sentence naming the axis",
  "families": [
    {"key": "short_slug", "name": "Display Name",
     "claim": "one-line statement of the family's core commitment",
     "lineage": "Author Year -> Author Year -> ... (the spine; optional)"} 
  ] }
```

## Step 2 — Assign every paper  (after the definitions are approved)

Using the **frozen** family list below, assign EVERY paper to exactly one family
(its dominant commitment). Work through the corpus in order; do not skip any ref.
For large corpora, assign in batches and concatenate — never one rushed pass.

Approved families:
{APPROVED_FAMILIES_JSON}

Corpus:
{CORPUS_DIGEST}

Return ONLY:
```json
{ "principle": "...copied from approved spec...",
  "families": [ ...copied from approved spec... ],
  "assignments": { "<ref>": "<family key>", ...one entry per paper... } }
```

Save that as `families_input.json`, then run:
```
python3 tools/families.py --rows rows.json --assign families_input.json --out families.json
```
It validates (exhaustive / exclusive / balanced — fails loud otherwise), stamps
`family` onto rows.json, writes `families.json` (the reproducible cache) and
`families.md`, and `tools/spreadsheet.py` will auto-add the Family column on the
next rebuild.

**Note.** The optional lineage/taxonomy *figure* is a separate, bespoke step —
hand-curate node selection and the cross-family arrows; don't expect a good one
auto-generated. Treat it as a collaboration with the user (the third checkpoint).
