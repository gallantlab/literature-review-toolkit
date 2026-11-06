# Lessons learned

Each entry is a rule and the incident that established it. **The rules themselves
live in [`PLAYBOOK.md`](PLAYBOOK.md) and in the tools that enforce them.** This file
holds only the evidence behind them, and phase numbers refer to the playbook.

Read it when you change the toolkit, not when you run a review. No review needs it:
every rule it explains is already a gate that refuses, a case in
`tools/tests/test_formatting.py`, or a line that `lane_briefs.py` renders into every
brief. It was moved out of the playbook on 2026-11-05, where roughly 4,100 tokens of
incident history was being read into context on every run.

The incidents stay dated and specific on purpose. A rule whose reason is written down
survives the next person who decides it looks unnecessary.

## Lane briefs and search agents

Most of these rules now live in `search_prompt_template.md`, which `lane_briefs.py`
renders into every brief; the incidents stay here.

- **The verification duty** (landing page, first author and year read off it, the
  DOI's target confirmed, abstract read before summarizing, unconfirmable papers to
  `could_not_confirm`) drives the ~25% error rate of contract rule 1 to about zero:
  on the 541-ref cortical-layers build Phase 3 returned 535 OK, 2 MISMATCH and 0
  NOT-FOUND, both exceptions being diacritics the agent dropped (`Hertag` for
  `Hertäg`), which canon restored. Phase 3 still runs: it is the gate that proves
  this happened. The `could_not_confirm` lists are where the useful findings come
  from (a misattributed classic, a wrong stored DOI, a title that does not exist;
  the DOI in circulation for Nandy et al. 2017 resolves to a different Neuron paper).
- **Seeds are titles only** (`lane_briefs.py` refuses one that names an author).
  Author-name seeding injected fabricated attributions into three builds.
  Remembered titles fail too: on the cortical-layers build about 40 of ~170 seeded
  titles did not exist ("Cortical microcircuitry of attention", "The draining vein
  problem in laminar fMRI"). It cost little because the briefs labeled them as
  unreliable, and every agent substituted the real nearest work. Better still, seed
  from a real source (a sibling corpus, a review's reference list).
- **The session's WebSearch quota (200 calls) is shared by all subagents.** With 14
  lanes it ran out after about two; the other twelve used the Europe PMC, PubMed
  E-utilities, CrossRef, bioRxiv and arXiv REST APIs, which is not a degradation
  (dated, field-restricted sweeps are more systematic; the weak spot is work that
  does not use the topic's vocabulary in its title). The brief names that route as
  first-class. Resume a thin lane through SendMessage (Phase 2c).
- **A concrete target, never "as many as possible".** Asking for 40 gave 40–44;
  "as many as possible" gave sprawl with more fabrications. The scale sets it
  (Phase 1d).
- **Agents invert findings.** One described "X > Y" for a paper that found the
  opposite. That is why every summary is checked against its abstract (Phase 5c).
- **NOT-FOUND is a real failure; ERROR is not NOT-FOUND** (rules in Phase 3). Before
  verify.py queried arXiv directly, preprints came back NOT-FOUND and were waved
  through: a "Vo et al." attention paper was really Foster et al., and two Jain & Huth
  arXiv ids pointed at unrelated papers. On a ~90-paper world_models run, 8 real
  preprints came back NOT-FOUND only because a per-paper arXiv loop drew a 429 ban;
  verify now batches arXiv ids and reports ERROR when a lookup cannot complete.

## Casing and foreign-language titles

From a 493-ref history corpus (2026-08-29); all now handled by the tools and covered
by `tools/tests/test_formatting.py`. Keep them in mind when changing a formatter.

- **Never sentence-case a non-English title.** The pass lowercased German nouns ("der
  kumpan in der umwelt des vogels"), so `sentence_case.py` skips German/French titles
  (`--include-foreign` forces casing). `von`, `de` and `man` are not usable language
  markers ("Karl von Frisch", "fin-de-siècle", "including man").
- **A partly ALL-CAPS title is shouting, not an acronym** ("BEHAVIORAL MUTANTS OF
  *Drosophila* ISOLATED BY …" passed both casers). `sentence_case.py` lowercases runs
  of ≥3 all-caps words and keeps isolated acronyms (`fMRI`, `MEG`).
- **Model-organism genera are proper nouns** (canon once emitted "the genetics of
  caenorhabditis elegans"); `common.GENERA` restores them.
- **A `?` inside a title or venue is mangled punctuation** (`?Matched filters? ?
  neural models…`, `Journal of Comparative Physiology ? A`): the audit fails
  `mangled-punct`. Text inside a URL is ignored, so an OpenReview `forum?id=` link
  passes. **Stripped JATS markup glues words** (`the cockroachPeriplaneta
  americana`): `missing-space`. Both hit the same rows; a deposit broken one way is
  usually broken in several.
- **Why canon does not sentence-case Title Case.** Correct casing needs proper-noun
  judgment (`Bayesian`, `Atari`, `Tolman-Eichenbaum` stay capitalized; `Active`,
  `World`, `Model` do not), and a mechanical caser's errors are invisible to the
  audit. So `sentence_case.py` proposes and a person reviews (Phase 3f).

## Reference records: what CrossRef gets wrong

- **Back-file deposits re-date old papers.** Digitized back catalogs carry the
  digitization year: Seyfarth & Zottoli 1991 deposited as 2008, Lorenz 1943 and
  Schleidt 1962 as 2010 (`10.1111/j.1439-0310.1943.tb00655.x`: the year is in the
  suffix). The audit warns `deposit_year_conflict()`; only a human can say which year
  is right. `doi_year()` matches only the Wiley `.<year>.tb<n>` shape on purpose: a
  broad 4-digit scan gave 15 false positives and no true ones on 493 refs (page
  numbers, article ids, ISSN fragments). Seyfarth's `10.1159/000114363` carries no
  year; verify's year check is what catches that one.
- **Deposited names can be plain wrong.** `family="A. Moffat"` (now auto-repaired: no
  surname starts with an initial), `family="(Bud) Craig"` (nickname now stripped), and
  `Sprby` for Terje Sparby, a misspelling caught only by finding the name spelled
  correctly on a sibling paper. The last kind is caught only by reading.
- **Compound and particle surnames get mis-split** (`Lambon Ralph` → `Ralph, M. A.
  L.`; `de Heer` → `Heer, W. A. D.`; the reverse, `J. Adam Noah` → family `Adam
  Noah`). The audit warns on every multi-word surname; expect some legitimate ones
  (Spanish, Vietnamese, Italian double surnames). Fix a real mis-split in
  `hand_fixes.json` (Phase 3f).
- **Whole author lists can be wrong in other ways:** given and family names swapped
  for every author, a generational suffix inside the surname (`Náñez Sr, J. E.`), or a
  preprint server listing the corresponding author first (Research Square). Check the
  author order against PubMed or the landing page and fix it in `hand_fixes.json`.
- **`U+FFFD` mojibake is unrecoverable at the source** (`Bürgel`, `Zeitschrift für
  Anatomie`), and every re-canon pulls it back in; that is why hand fixes live in
  `hand_fixes.json`, which canon re-applies (Phase 3f).
- **Subtitles.** CrossRef keeps a series part or subtitle in a separate field; until
  2026-08-22 canon dropped it, so Creutzfeldt 1989 parts I and II rendered as one
  identical title, and a `possible duplicate (1.00)` warning was the only tell. Canon
  now joins them (`common.crossref_record`). Corpora canonicalized before that date
  need subtitles restored by hand. Their older hand fixes were typed into `rows.json`
  and are lost on a re-canon unless first recorded in `hand_fixes.json`.
- **Book chapters.** CrossRef deposits `container-title` as `[series, book]`; canon
  builds `In Book (pp. x-y). Publisher.` from the last entry
  (`common.build_chapter_apa`). Most chapters have no deposited editors, and Springer
  sometimes deposits the WRONG book (Biggio 2013 carried another volume's title and
  ISBN), so spot-check chapter rows; book titles still need hand sentence case.
- **Formatter defects sit in finished work.** JATS markup in titles, `?.` double
  terminals and U+2010/U+2011 hyphens in surnames (`Fischer‐Baum`) shipped in five
  delivered bibliographies before the gate caught them. After a formatter change,
  re-run `--audit` over old projects (`references.py --repair` fixes these classes
  offline; see "Upgrading an old corpus").
- **A whole-string check condemns legitimate titles** (for anyone adding an audit
  check). Forbidding `et al.` anywhere failed Nature's "<Author> et al. reply"
  titles; the check now reads only `parse_apa`'s author segment, falling back to the
  whole string when the reference will not parse. Ask which APA segment a defect lives
  in before checking.

## Versions, duplicates and the version of record

- **Keep both ids on a row that has them**; canon prefers the journal DOI (Phase 3f).
- **Not every "published" DOI is the version of record.** Curran/Proceedings.com
  `10.52202/*` DOIs for printed NeurIPS volumes resolve and match title searches, but
  moving 6 gallant_lab rows to them would have cut OpenAlex counts ~3–4× (MindEye 40 →
  11) for nothing. ACL Anthology (`10.18653/*`), IEEE/CVF (`10.1109/*`) and journal
  DOIs are real upgrades (MindBridge 2 → 41). Before promoting a preprint row, compare
  the candidate DOI's OpenAlex count with the arXiv record's; if it is much lower, keep
  arXiv and name the venue in prose.
- **The same paper can enter twice under two DOIs** (preprint from one lane, journal
  version from another); three such pairs sat in a 362-row corpus for six weeks. The
  merge (Phase 2c) and the audit's duplicate scan both flag possible pairs as
  warnings; real distinct papers also collide (a 2014 toolbox and its 2026 successor),
  so each pair needs a verdict. Keep the version of record, drop the preprint, and
  re-check any in-text citation whose year moves (2025 → 2026).

## Network failures that look alike and are not

A run that will not finish is almost always one of these. All three arrive as
`http.client.HTTPException` and are correctly classed transient; they differ in
timing and determinism.

| Symptom | What it is | Fix (in `common.http`) |
|---|---|---|
| Random requests fail, succeed on retry | genuine rate limiting | backoff; raise `--sleep` |
| The **same** large records fail at the **same byte count**, small ones fine | truncation of a large uncompressed body (`IncompleteRead(1782210 bytes read, 399724 more expected)`) | `Accept-Encoding: gzip, deflate` + `common.decompress` |
| The **same** records fail **instantly** (~0.3 s), or a large body comes back short even with gzip requested; curl fetches them fine | HTTP-stack / proxy incompatibility (Semantic Scholar ignores `Accept-Encoding`: every 300-paper batch POST read short, so S2 counted 0 of 315 papers on 2026-10-07) | `common.curl_get` at the first network failure, for GETs and POSTs; S2 batch POSTs go to curl directly. Headers (the API keys) reach curl through a private file, never its command line |

Only the first is fixed by waiting; against the other two a retry loop runs forever
and reports as slowness. On the cortical-layers build, uncompressed: 117 of 537 rows
failed canon and xref managed ~19 papers per 7 minutes; compressed, the same records
fetch in 0.3 s. Then 71 of 536 xref fetches failed on the stack issue; curl-first
takes 0.7 s instead of 32 s of backoff. urllib does not decompress, so requesting gzip
and decoding it must land together; `decompress()` passes an unknown encoding through
rather than raising.

**First diagnostic:** re-fetch one failing URL with `curl -sS --compressed`. If curl
succeeds where the tool failed, it is not the server, and `--sleep` will not help.

## Citation counts (Phase 5b)

- **Google Scholar cannot be automated** (no API; CAPTCHA after ~10–20 requests).
- **OpenAlex is the workhorse** (~95%+ coverage by DOI) but undercounts arXiv-only
  preprints, which it files separately from the published version; lean on S2 for
  those rows.
- **OpenAlex's batch filter can return a low-count duplicate** (Whittington 2020 TEM:
  6 from the batch, 667 from `/works/doi:`; Tolman 1948: 1 vs 6,656). `citations.py`
  keeps the max per DOI in a batch and re-queries the single-work endpoint when
  OpenAlex < half of S2 (S2 ≥ 50). Still spot-check landmark counts against the S2
  column: a famous old paper with single-digit OpenAlex is the tell.
- **Semantic Scholar without a key** 429s, 400s a whole batch on one malformed id
  (`common.s2_batch` bisects to isolate and name it) and 404s valid papers under load.
  Set `S2_API_KEY`; without it, accept partial S2 coverage.
- The two columns will not match each other, and GS-style totals run higher than
  both.

## On the spreadsheet

- **Ref ids must be unique across merges, and counts must not be keyed by a reused
  ref.** A one-character lane prefix plus a counter is ambiguous (lane `4`, ref `410`
  vs lane `41`, ref `0`): a naive merge re-emitted an xref batch as `410…` over the
  existing `410…`, `families.py` assigned one paper twice, and two rows sharing `415`
  shared one count, so Carvalho 2024 inherited Elman 1990's 10,838 citations. The
  tools now use separator ids (`<KEY>-01` in every brief and `candidates.py` export)
  and `merge_lanes.py` refuses a repeated ref; still attach counts only after ids are
  final, and assert `len(refs) == len(set(refs))` after any hand merge.
- `rows.json` is the table; the `.xlsx` is only a rendering of it (xlsxwriter is
  write-only). A project row emitter (from `templates/build_rows_template.py`) runs
  once, guards its writing block under `if __name__ == "__main__":`, and writes through
  `common.write_rows`, which refuses to overwrite a canonical table (contract rule 6).

## If you change families_figure.py

Each of these shipped once.

- *Unknown is not zero.* The first size encoding drew a paper with no count as
  uncited; on reverse_polish_notation (67% coverage) a third of the corpus claimed
  zero citations. Before mapping a column onto a visual channel, count how many rows
  have it and decide what a blank looks like.
- *Order follows the drawn geometry.* Next/Prev sorted on `(year, reference)`, but
  the beeswarm fans a year's papers out from the lane center, so the walk hopped (137
  backward steps on a 555-paper corpus). It now tie-breaks on the dot's drawn y. The
  sort looked right through two code reviews.
- *Run interactive code; do not read it.* That bug was caught by executing the
  figure's own `ORDER` expression against its embedded data. After any change to the
  interactive code, run `node tools/checks/verify_nav_order.mjs <figure>.html` and
  `node tools/checks/verify_hover.mjs <figure>.html` (no browser needed).
- *Renders must be deterministic.* Landmarks picked into a Python `set` moved 5 of 57
  labels between two renders of identical input, so the re-render diff was reading
  noise. Sort keys are now `(year, ref)` and `(x, ref)`. Before trusting a
  "re-rendering changes nothing" check, render twice with unchanged code.
- *A marker must not share the palette of what it marks.* The home-lab ring was also
  `PALETTE[4]`, so a lab paper in family 5 got a gold ring on a gold dot.
  `--lab-color` is now resolved against the lane colors in use. Check whether a
  parameter exists before adding one: which lab gets starred was `--lab-author` all
  along.
- *An SVG `<g>` is not hoverable*, and `<text>` takes pointer events only on glyph
  strokes, so the lane-label hover fired only on a letter. Give any SVG-text
  affordance a transparent hit target.
- *The hover panel sits on the lane legend.* Anchored to the label's right edge it
  covered the earliest papers, where a warped axis puts the foundations; it is now
  anchored to the left edge and its width is set before `offsetHeight` is read.
