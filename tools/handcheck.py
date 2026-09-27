#!/usr/bin/env python3
"""Hand-check the references that have no DOI or arXiv id (books, reports, essays).

No API can verify a DOI-less row, so on a gated table the audit fails any such
row without a hand-check record. This tool does the work around the hand check:

  --prepare           search CrossRef and OpenAlex for a DOI the row lacks (the
                      same title, by common.title_match, and the same year).
                      Rows with a candidate go to handcheck_doi_candidates.json;
                      the rest go to handcheck_input.json, with
                      handcheck_brief.md for the checking agent. Each input entry
                      carries `apa_sha`, the hash of the reference it shows (the
                      apa, else search_apa). An existing handcheck_result.json
                      answers the previous --prepare, so it is renamed (never
                      deleted) to handcheck_result.stale-<timestamp>.json.
  --adopt-dois FILE   give each row with exactly one candidate DOI that DOI, so it
                      goes through verify.py instead. For a row with several, keep
                      one in the file and re-run.
  --ingest FILE       record each result on its row as `hand_verified`. A result
                      is refused when the row's shown reference changed since
                      --prepare, when its --input entry has no `apa_sha` (an
                      input written before that binding existed), or when the
                      result's own `apa_sha` echo is missing or differs from the
                      input's (a result for an older --prepare).
  --reject REF        the row's candidate DOIs (in --candidates, default
                      handcheck_doi_candidates.json beside --rows) are all the
                      wrong paper: record them on the row as `doi_rejected`, with
                      the required --reason, so the next --prepare skips them and
                      sends the row to the hand check. Repeat for several rows;
                      exit 1 when a ref is not in the table or has no candidates.
  --input FILE        the hand-check input that --ingest checks against
                      (default: handcheck_input.json beside --rows)

    python3 tools/handcheck.py --rows rows.json --prepare --email you@inst.edu
    python3 tools/handcheck.py --rows rows.json --adopt-dois handcheck_doi_candidates.json
    python3 tools/handcheck.py --rows rows.json --reject Y-19 --reason "both candidates are reviews of it"
    python3 tools/handcheck.py --rows rows.json --ingest handcheck_result.json

Result file: a JSON list of {"ref", "apa_sha" (copied from the input entry),
"verdict": "confirmed"|"corrected"|"not-found", "apa" (corrected only),
"source_checked", "changes"}. A "corrected" result replaces the row's apa.

--ingest exits 1 when it refused any result or any row is recorded not-found;
remove a not-found row, or check it again.
"""
import argparse
import datetime
import os
import sys
import urllib.parse

import common

PHASE = "3e"   # pipeline phase, read by tools/gen_docs.py for the tool index

VERDICTS = ("confirmed", "corrected", "not-found")

BRIEF = """# Hand check: references with no DOI or arXiv id

Each item in handcheck_input.json is a book, chapter, report, thesis, essay or other
work that no API can verify. Confirm or correct each one against an authoritative
source: a library catalog (LoC, WorldCat, BnF, CiNii), the publisher's page, a scan
of the title page, the post itself for a web essay, or an institutional repository.
Do NOT use another paper's citation of it: the most-repeated citation is often wrong.

For every item record, in handcheck_result.json (a JSON list):
  {"ref": "...", "apa_sha": "the item's apa_sha, copied exactly",
   "verdict": "confirmed" | "corrected" | "not-found",
   "apa": "the corrected APA-7 reference (corrected only)",
   "source_checked": "exactly what you checked, specific enough to re-check",
   "changes": "what you changed and why (corrected only)"}

Check authors (all of them, in order), year, title, edition, publisher, and pages or
report number. "not-found" means you could not establish that the work exists as cited.
Copy each item's apa_sha into its result unchanged: it proves which version of the
reference you checked, and a result without it (or with another's) is refused.
Write the result file incrementally, so no work is lost. Do not delegate to subagents.
"""


def _valid(hv):
    return (isinstance(hv, dict) and hv.get("verdict") in ("confirmed", "corrected")
            and bool(str(hv.get("source_checked") or "").strip()))


def needs_check(row):
    """A DOI-less, arXiv-less row with no valid hand-check record."""
    return not (common.doi_of(row) or row.get("arxiv")) and not _valid(row.get("hand_verified"))


def shown_apa(row):
    """The reference text the hand-check agent is shown: the apa, else (before
    canon or a hand edit fills it) the search agent's search_apa. apa_sha is
    taken over THIS text at --prepare and at --ingest, so an edit to whichever
    one the agent saw is caught."""
    return row.get("apa") or row.get("search_apa") or ""


def claim_of(row):
    """(title, year) the row claims: the search agent's, else its apa's."""
    p = common.parse_apa(row.get("apa") or row.get("search_apa") or "")
    title = row.get("search_title") or (p["title"] if p else "")
    year = str(row.get("search_year") or (p["year"] if p else ""))
    return title, year


def search_crossref(title):
    q = urllib.parse.quote(title)
    d = common.http_json(f"https://api.crossref.org/works?query.bibliographic={q}&rows=3&select=DOI,title,issued")
    out = []
    for it in d["message"]["items"]:
        yr = ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        out.append({"doi": it["DOI"], "title": (it.get("title") or [""])[0], "year": str(yr or ""),
                    "source": "crossref"})
    return out


def search_openalex(title):
    q = urllib.parse.quote(title)
    d = common.http_json(f"https://api.openalex.org/works?search={q}&per-page=3"
                         "&select=doi,display_name,publication_year")
    return [{"doi": w["doi"].replace("https://doi.org/", ""), "title": w.get("display_name") or "",
             "year": str(w.get("publication_year") or ""), "source": "openalex"}
            for w in d.get("results", []) if w.get("doi")]


def find_doi(row, searchers=(search_crossref, search_openalex)):
    """Candidate DOIs for a DOI-less row: the same title (common.title_match,
    which refuses a title merely contained in a longer one) and the same year."""
    title, year = claim_of(row)
    if not title:
        return []
    hits = {}
    for fn in searchers:
        try:
            cands = fn(title)
        except common.OpenAlexBudgetError:
            raise
        except Exception as e:
            print(f"  [search-fail] {fn.__name__}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        for c in cands:
            if common.title_match(title, c["title"]) and (not year or c["year"] == year):
                s = common.title_score(title, c["title"]) or 0
                hits.setdefault(c["doi"].lower(), dict(c, score=round(s, 3)))
    return list(hits.values())


def prepare(rows, keyf, searchers=(search_crossref, search_openalex)):
    doi_cands, todo = {}, []
    for r in rows:
        if not needs_check(r):
            continue
        rejected = {d.lower() for d in (r.get("doi_rejected") or {}).get("dois", [])}
        hits = [h for h in find_doi(r, searchers) if h["doi"].lower() not in rejected]
        if hits:
            doi_cands[r.get(keyf)] = hits
        else:
            todo.append({"ref": r.get(keyf), "apa": shown_apa(r),
                         "link": r.get("link", ""), "note": r.get("note", ""),
                         "summary": r.get("summary", ""), "apa_sha": common.apa_sha(shown_apa(r))})
    return doi_cands, todo


def adopt(rows, keyf, doi_cands):
    """Give each row with exactly one candidate that DOI; it then goes through verify.

    A candidate ref that is no longer in the table (renamed or removed since
    --prepare wrote handcheck_doi_candidates.json) is reported on stderr rather
    than silently dropped -- a stale candidates file once looked like it adopted
    nothing to worry about."""
    by = {r.get(keyf): r for r in rows}
    adopted, ambiguous = [], []
    for k, cands in doi_cands.items():
        if k not in by:
            print(f"  ⚠ {k}: candidate DOI(s) for a ref not in this table (renamed/removed "
                  "since --prepare); skipped", file=sys.stderr)
            continue
        if len(cands) != 1:
            ambiguous.append(k)
            continue
        doi = cands[0]["doi"]
        by[k]["doi"] = doi
        by[k]["link"] = f"https://doi.org/{doi}"
        by[k].pop("hand_verified", None)
        adopted.append(k)
    return adopted, ambiguous


def reject(rows, keyf, refs, doi_cands, reason, asof):
    """Record that every candidate DOI listed for each ref is the wrong paper.
    Returns (recorded refs, errors). The DOIs are appended to any rejected before."""
    by = {r.get(keyf): r for r in rows}
    done, errors = [], []
    for k in refs:
        if k not in by:
            errors.append(f"{k}: not in the table")
            continue
        dois = [c["doi"] for c in doi_cands.get(k, [])]
        if not dois:
            errors.append(f"{k}: no candidate DOIs recorded for it in the candidates file")
            continue
        prev = (by[k].get("doi_rejected") or {}).get("dois", [])
        by[k]["doi_rejected"] = {"dois": sorted(set(prev) | set(dois)), "reason": reason, "at": asof}
        done.append(k)
    return done, errors


def ingest(rows, keyf, results, hc_input, asof):
    """hc_input is the hand-check input recorded at --prepare (a JSON list of
    {"ref", "apa_sha", ...}): a result is refused if its row's current apa sha
    differs from what --prepare recorded (the reference changed while it was
    being checked), or if its ref never went through --prepare at all."""
    by = {r.get(keyf): r for r in rows}
    input_map = {e.get("ref"): e for e in hc_input}
    n, errors = 0, []
    for res in results:
        k, v = res.get("ref"), res.get("verdict")
        src = str(res.get("source_checked") or "").strip()
        row = by.get(k)
        if row is None:
            errors.append(f"{k}: no such row")
            continue
        if common.doi_of(row) or row.get("arxiv"):
            errors.append(f"{k}: has a DOI/arXiv id; it is verified by verify.py, not by hand")
            continue
        entry = input_map.get(k)
        if entry is None:
            errors.append(f"{k}: not in this hand check")
            continue
        if "apa_sha" not in entry:
            # an old-format hand-check-input entry (written before apa_sha existed)
            # cannot prove what the hand-check agent saw -- refuse explicitly, rather
            # than rely on None != a real sha to (accidentally) do the right thing
            errors.append(f"{k}: hand-check input predates --prepare binding; re-run --prepare")
            continue
        if common.apa_sha(shown_apa(row)) != entry["apa_sha"]:
            # checked against the PRE-correction apa: a "corrected" verdict has not
            # yet been applied to row["apa"] at this point in the function
            errors.append(f"{k}: the reference changed since --prepare; re-check it")
            continue
        if not res.get("apa_sha"):
            errors.append(f"{k}: result does not echo the prepared apa_sha; re-check it")
            continue
        if res["apa_sha"] != entry["apa_sha"]:
            # a result for an older --prepare: the apa was edited and re-prepared since,
            # so the row matches the NEW input and only the echo can tell them apart
            errors.append(f"{k}: result was for a different version of the reference; re-check it")
            continue
        if v not in VERDICTS:
            errors.append(f"{k}: verdict {v!r} is not one of {', '.join(VERDICTS)}")
            continue
        if v != "not-found" and not src:
            errors.append(f"{k}: {v} without source_checked")
            continue
        if v == "corrected":
            apa = str(res.get("apa") or "").strip()
            if not apa:
                errors.append(f"{k}: corrected without the corrected apa")
                continue
            row["apa"] = apa
        row["hand_verified"] = {"verdict": v, "source_checked": src, "changes": res.get("changes") or "",
                                "apa_sha": common.apa_sha(row.get("apa")), "at": asof}
        if v != "not-found":
            row["verify_note"] = f"Hand-verified ({v}) against {src}"
        n += 1
    return n, errors


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--key", default=None, help="row key field (default: ref, else label)")
    ap.add_argument("--prepare", action="store_true",
                    help="search for missing DOIs; write the hand-check input")
    ap.add_argument("--adopt-dois", metavar="FILE", help="apply handcheck_doi_candidates.json")
    ap.add_argument("--ingest", metavar="FILE", help="record hand-check results as hand_verified")
    ap.add_argument("--input", metavar="FILE",
                    help="hand-check input recorded at --prepare, used to detect an apa changed "
                         "since (default: handcheck_input.json beside --rows)")
    ap.add_argument("--reject", metavar="REF", action="append",
                    help="the row's candidate DOIs are all wrong: skip them and hand-check it (repeatable)")
    ap.add_argument("--reason", help="why the candidates are wrong (required with --reject)")
    ap.add_argument("--candidates", metavar="FILE",
                    help="candidates file for --reject "
                         "(default: handcheck_doi_candidates.json beside --rows)")
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"))
    ap.add_argument("--asof", default=datetime.date.today().isoformat())
    args = ap.parse_args()
    if sum(bool(x) for x in (args.prepare, args.adopt_dois, args.ingest, args.reject)) != 1:
        ap.error("give exactly one of --prepare, --adopt-dois, --reject, --ingest")
    if args.reject and not (args.reason or "").strip():
        ap.error("--reject needs --reason")
    rows = common.load_json(args.rows)
    loaded = os.path.getmtime(args.rows)         # writes refuse a file changed since
    keyf = common.key_field(rows, args.key)
    here = os.path.dirname(os.path.abspath(args.rows))
    if args.prepare:
        if not args.email:
            ap.error("--email or LITREVIEW_EMAIL required (CrossRef/OpenAlex polite pool)")
        common.set_user_agent(args.email)
        cands, todo = prepare(rows, keyf)
        old = os.path.join(here, "handcheck_result.json")
        if os.path.exists(old):
            stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
            stale = os.path.join(here, f"handcheck_result.stale-{stamp}.json")
            os.replace(old, stale)
            print(f"moved the previous handcheck_result.json to {os.path.basename(stale)}: it answers "
                  "the previous --prepare, so its results are stale")
        common.dump_json(cands, os.path.join(here, "handcheck_doi_candidates.json"))
        common.dump_json(todo, os.path.join(here, "handcheck_input.json"))
        with open(os.path.join(here, "handcheck_brief.md"), "w", encoding="utf-8") as f:
            f.write(BRIEF)
        print(f"{len(cands)} row(s) may have a DOI (handcheck_doi_candidates.json); "
              f"{len(todo)} row(s) need a hand check (handcheck_input.json + handcheck_brief.md)")
        return
    if args.adopt_dois:
        adopted, ambiguous = adopt(rows, keyf, common.load_json(args.adopt_dois))
        common.save_rows(args.rows, rows, loaded)
        print(f"adopted {len(adopted)} DOI(s); run verify.py --rows on them: {', '.join(adopted)}")
        for k in ambiguous:
            print(f"  ⚠ {k}: several candidate DOIs; keep one in the file and re-run")
        return
    if args.reject:
        cpath = args.candidates or os.path.join(here, "handcheck_doi_candidates.json")
        done, errors = reject(rows, keyf, args.reject, common.load_json(cpath),
                              args.reason.strip(), args.asof)
        if done:
            common.save_rows(args.rows, rows, loaded)
        print(f"rejected the candidate DOIs of {len(done)} row(s): {', '.join(done) or '-'}; "
              "re-run --prepare to send them to the hand check")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1 if errors else 0)
    input_path = args.input or os.path.join(here, "handcheck_input.json")
    n, errors = ingest(rows, keyf, common.load_json(args.ingest), common.load_optional_json(input_path, []),
                       args.asof)
    common.save_rows(args.rows, rows, loaded)
    not_found = [r.get(keyf) for r in rows if (r.get("hand_verified") or {}).get("verdict") == "not-found"]
    print(f"recorded {n} hand check(s)")
    for e in errors:
        print(f"  ✗ {e}")
    for k in not_found:
        print(f"  ✗ {k}: not found as cited; remove the row or re-check it")
    sys.exit(1 if errors or not_found else 0)


if __name__ == "__main__":
    main()
