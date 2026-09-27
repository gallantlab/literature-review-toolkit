# Family assignment brief — TEMPLATE (Phase 6b, step 2)

Do not fill this by hand. `tools/families.py --assign SPEC --prepare DIR` renders
it into DIR/BRIEF.md from the approved spec and writes DIR/batch_NN.json with every
row no assignment covers yet. Everything above the `BRIEF STARTS` marker is these
notes and is never sent. Merge the answers with `families.py --results
'DIR/result_*.json'`.

<!-- BRIEF STARTS -->
# Assign papers to the bibliography's families

The bibliography groups every paper into ONE family. The organizing principle:

> {PRINCIPLE}

The approved families (do not argue with them or invent a new one):

{FAMILIES}

**Your input:** `{INPUT_DIR}/batch_NN.json` (the NN you were given): one entry per
paper, with its `ref`, `year`, `title`, `summary`, and `lane_hint` (the search lane
it came from, a hint only). **Your output:** `{INPUT_DIR}/result_NN.json`, with the
same NN.

Assign each paper to the family of its dominant commitment, using its title and
summary. An antecedent (a classic methods, empirical or theory paper) goes to the
family whose line of work it is most directly an antecedent OF. Record every **hard
call**: a paper that fits its family badly, or fits two about equally. The hard
calls are the only place a wrong family definition shows up.

Write `result_NN.json` as:

```json
{"assignments": {"<ref>": "<family key>"},
 "hard_calls": [{"ref": "<ref>", "assigned": "<key>", "also_fits": "<key or none>",
                 "why": "one sentence"}]}
```

One assignment per paper in your batch, none skipped. Parse the file back with
`python3 -c "import json;print(len(json.load(open('{INPUT_DIR}/result_NN.json'))['assignments']))"`.
Never read or write outside `{PROJECT_DIR}`. Do NOT delegate to subagents.

Reply with only: assigned N, hard calls N.
