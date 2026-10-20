# Reruns and upgrades

This page covers changing a finished review: adding papers, re-rendering its
outputs, and bringing an old review up to the current gates. Commands run in the
project folder and reach the scripts as `../tools/`
([Where files live](pipeline.md#where-files-live)).

## Add papers

Write the new papers as a lane file and append it:

```bash
python3 ../tools/merge_lanes.py --append <lane_file>.json --into rows.json
```

Then run verification (and hand checks), canon, citation counts and summary
checks on the new rows ([Checking](checks.md)). Rerun the missed-paper step and
`candidates.py --add`, so the recorded runs cover the new rows; otherwise the
audit warns `partial-xref-run` and `partial-forward-run`. Never rerun the script
that first wrote the rows ([rule 6](pipeline.md#the-rules)).

## Re-render the outputs

**A timeline.** After a toolkit change, rerun the command in
`figure_render_args.txt`, then compare the label set with the previous `.svg`. A
re-render should change the drawing, not the landmarks; if labels moved, find
out why before shipping.

**A written review.** After a toolkit or corpus change, render to a scratch path
first and compare the prose with the delivered `.docx`. If only the reference
list differs, replace the file. If the prose differs too, the delivered file
holds edits or is an older draft, and re-rendering would overwrite them.

!!! tip "Confirm the renderer is deterministic first"
    Render twice with unchanged code and data. Any difference is a renderer bug,
    and it would make every later comparison meaningless.

## Upgrade an old corpus

Rerunning a search on an existing review brings the whole project up to the
current standard, or redoes it if that is easier. It is never a lighter pass over
only the new rows.

### What switches the gates on

A table is **gated** once any row carries a verify stamp, or was built or
canonicalized on or after 2026-09-25 (a `built_at` or `canonical_at` date). Every
current tool that writes rows stamps `built_at`. Once a table is gated, the audit
and the spreadsheet fail every old row that lacks the new records, not only the
new batch. An older table is **legacy**: the audit only warns.

### Upgrade in place

1. **Verify the whole table**, not only the new rows: `verify.py --rows
   rows.json`. A canonical row that kept its search claim (`search_*`) is checked
   against both the claim and its `apa`, and fails if either disagrees with the
   record. A canonical row with no claim is checked against its own `apa` only.
   Canon built that `apa` from the same DOI, so the check cannot show that the DOI
   is the intended paper. Its stamp records `claim_basis: "canonical-apa"`, and
   the audit warns `identity-not-reestablished` until you confirm the DOI by hand
   and acknowledge it.
2. **Turn existing hand checks into records.** Write any `verify_note` text or
   informal check results as `handcheck.py --ingest` result files, and recheck
   any whose source is not recorded. A `hand_verified` record with no `apa_sha`
   predates binding hand checks to their `apa`, so it counts as missing:
   re-ingest it.
3. **Check the summaries**: `abstracts.py`, then `summary_audit.py --prepare`,
   the checking agents, and `--ingest`
   ([Check every summary](checks.md#check-every-summary-phase-5c)). Older
   `abstracts.json` entries and `summary_check` stamps record no ids, so they
   count as unbound. `abstracts.py` refetches the fetched entries. A hand-added
   landing-page entry needs the row's `doi` and `arxiv`, and is reported stale
   until it has them. Every summary is rechecked.
4. **Bring the candidate ledger up to date.** Run `candidates.py --rows rows.json
   --add xref.json --source xref`, and `--add forward_candidates.json --source
   forward` if there is one. Then decide each pending entry (`--list pending`,
   then `--decide DOI --decision include|exclude --reason "..."`). A gated table
   with no `candidates.json` warns `no-candidate-ledger` under `*`; acknowledge it
   if the corpus never ran the missed-paper step.
5. **Acknowledge each remaining warning**
   ([Acknowledge warnings](checks.md#acknowledge-warnings)).
6. **Run the gates**: `references.py --audit`, then `spreadsheet.py`.

### When a fresh review is easier

Redo the review instead when few old rows carry a DOI, or when the rows lack the
search lanes' claims (`search_*` fields), so `verify.py` has nothing independent
to check against. A redo is also easier when the lanes are stale enough that a
fresh search is simpler than reconciling one row at a time. Say which you chose,
and why.

### Measure a redo against the old review

Build the redo in its own project folder, then compare:

```bash
python3 ../tools/recall.py --rows rows.json --old ../<old>/rows.json --where source=search
```

`recall.py` matches every old row against the new table, by DOI, then arXiv id,
then title, and prints the recall. It writes the misses to
`recovery_input.json`, the input for one recovery lane. That lane's agent decides
each miss again from the landing page, since the old reference is a pointer, not
a claim. `--where source=search` limits the comparison to the old review's
search results.
