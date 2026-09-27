#!/usr/bin/env python3
"""The candidate ledger: record a decision on every paper that xref, forward citation or a survey suggests.

candidates.json maps each DOI to {title, year, first_author, sources, decision,
reason, at}. Keys that start with "_" are records, not candidates. `_runs` holds
{source: {at, n, complete, n_papers}}, written by each --add. From it the audit
can tell whether xref and forward citation were run, whether each run finished,
and whether it read every row with a DOI or arXiv id (not counting the included
candidates, which the run that proposed them cannot have read). `complete` and `n_papers`
come from the <FILE>.run.json sidecar that xref.py and forward.py write beside
their --out; a missing sidecar records complete=False. --add refuses a sidecar
written by a different tool than --source names, and skips candidates the corpus
already holds. A candidate whose title matches a table row (common.title_match),
with years no more than DUP_YEARS apart, is the same paper under another DOI,
usually a preprint of a published paper: --add excludes it at once, naming the row.
When it is the other way round (the row cites the preprint and the candidate is
the published version), --add says so and marks the entry `upgrade_row`: move that
row to the published DOI, then re-verify it.

Deciding the rest is agent work, and the tool frames it:

  --prepare DIR --scope FILE   writes the pending candidates as DIR/input_NN.json
                               (--per per file, default 60) and DIR/BRIEF.md, from
                               tools/candidate_prompt_template.md. FILE defines the
                               bibliography (a lane brief or topic definition); the
                               lanes come from lane_manifest.json beside --rows.
                               Each candidate carries its CrossRef/DataCite record
                               and its abstract (abstracts.py's sources), fetched
                               here, so agents decide and summarize from them
                               instead of browsing for every paper.
  --ingest 'DIR/result_*.json' records the agents' decisions. It refuses the whole
                               batch if any entry lacks a reason, names a DOI not in
                               the ledger, or includes a paper without the claim
                               read off its landing page (first_author, year,
                               title, lane, summary).

The audit fails while any candidate is pending, or while an included candidate is
not in the table. A missing ledger, or a missing, incomplete or partial xref or
forward run, is a warning the audit makes you acknowledge. The spreadsheet lists
every excluded candidate with its reason on its "Considered and excluded" sheet,
so a paper left out of the review was visibly considered and set aside.

    python3 tools/candidates.py --rows rows.json --add xref.json --source xref
    python3 tools/candidates.py --rows rows.json --add forward_candidates.json --source forward
    python3 tools/candidates.py --rows rows.json --prepare manual_check/cand --scope briefs/brief_V.md
    #   one agent per manual_check/cand/input_NN.json writes result_NN.json
    python3 tools/candidates.py --rows rows.json --ingest 'manual_check/cand/result_*.json'
    python3 tools/candidates.py --rows rows.json --list pending
    python3 tools/candidates.py --rows rows.json --decide 10.1/x --decision exclude --reason "methods paper"
    python3 tools/candidates.py --rows rows.json --export-included cand_lane.json --lane C

--decide needs --decision and a --reason. --export-included writes the included
candidates that are not yet in the table as a schema-2 lane file, carrying each
include's landing-page claim and summary. Its --lane (default C) must be a key no
table row uses. Add it with
`merge_lanes.py --append xref_lane.json --into rows.json`, then verify the new
rows.
"""
import argparse
import datetime
import glob
import os
import re
import sys

import common

PHASE = "6"   # pipeline phase, read by tools/gen_docs.py for the tool index
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "candidate_prompt_template.md")
CLAIM = ("first_author", "year", "title", "lane", "summary")    # an include must carry these


def _doi(d):
    return re.sub(r"(?i)^https?://(dx\.)?doi\.org/", "", (d or "").strip()).lower()


def entries(ledger):
    """(doi, candidate) pairs, sorted; skips "_" record keys such as _runs."""
    return [(d, c) for d, c in sorted(ledger.items()) if not d.startswith("_")]


def validate_ledger(ledger):
    """Raise ValueError naming the bad entry when `ledger` is not a candidate
    ledger of the shape every reader assumes: a JSON object, each non-"_" key
    mapping to an object whose decision is pending/include/exclude, and
    `_runs` (when present) an object of objects. Every common.load_optional_json(...,
    default) caller for candidates.json calls this right after loading, so a
    hand-edited or truncated file is reported by name -- as a candidates.py
    argparse error, or a references.py audit corpus defect -- instead of an
    AttributeError deep inside entries()/candidate_defects()."""
    if not isinstance(ledger, dict):
        raise ValueError(f"candidate ledger is not a JSON object (got {type(ledger).__name__})")
    if "_runs" in ledger and not isinstance(ledger["_runs"], dict):
        raise ValueError(f"candidate ledger: _runs is not an object (got {type(ledger['_runs']).__name__})")
    for src, run in (ledger.get("_runs") or {}).items():
        if not isinstance(run, dict):
            raise ValueError(f"candidate ledger: _runs[{src!r}] is not an object (got {type(run).__name__})")
    for d, c in ledger.items():
        if d.startswith("_"):
            continue
        if not isinstance(c, dict):
            raise ValueError(f"candidate ledger: entry {d!r} is not an object")
        if c.get("decision") not in ("pending", "include", "exclude"):
            raise ValueError(f"candidate ledger: entry {d!r} has an invalid decision {c.get('decision')!r}")


def corpus_dois(rows):
    """Every row's DOI, lowercased; an arXiv-only row counts by its arXiv DOI."""
    out = set()
    for r in rows:
        aid = common.arxiv_id_of(r)
        d = common.doi_of(r) or (f"10.48550/arXiv.{common.norm_arxiv(aid)}" if aid else "")
        if d:
            out.add(_doi(d))
    return out


def run_record(sidecar, source):
    """(complete, n_papers) from a <FILE>.run.json sidecar (None when absent:
    an incomplete run of unknown size). Raises ValueError when the sidecar was
    written by the other tool than `source` names -- a forward run recorded as
    the xref pass would satisfy the audit's no-xref-run check without one."""
    if sidecar is None:
        return False, None
    if not isinstance(sidecar, dict):
        raise ValueError(f"the run sidecar is not a JSON object (got {type(sidecar).__name__}); "
                         "re-run the tool that wrote it")
    tool = sidecar.get("tool")
    if tool is not None and tool != source:
        raise ValueError(f"the run sidecar was written by {tool}, not {source}: "
                         f"use --source {tool}, or add the {source} output")
    n = sidecar.get("n_papers")
    return bool(sidecar.get("complete")), (n if isinstance(n, int) else None)


# A preprint and its published version are at most this many years apart. Past
# it, a matching title is a different paper: a 2025 "Python toolbox for RSA" is
# not the 2014 "toolbox for RSA".
DUP_YEARS = 3


# Preprint servers' DOI prefixes: bioRxiv/medRxiv, OSF and PsyArXiv, arXiv,
# Research Square, Preprints.org, TechRxiv, Authorea.
PREPRINT_DOI = re.compile(r"^10\.(1101|31234|31219|48550|21203|20944|36227|22541)/", re.I)


def _year(v):
    m = re.search(r"\d{4}", str(v or ""))
    return int(m.group(0)) if m else None


def row_titles(rows, keyf):
    """[(key, title, year, doi)] for every row with a title (the search claim, else the apa's)."""
    out = []
    for r in rows:
        apa = common.parse_apa(r.get("apa") or "") or {}
        t = r.get("search_title") or apa.get("title") or ""
        if t.strip():
            out.append((r.get(keyf, "?"), t, _year(r.get("search_year") or apa.get("year")),
                        common.doi_of(r, lower=True) or ""))
    return out


def same_paper(title, year, titles):
    """The key of the row in `titles` that is this candidate under another DOI:
    a matching title, and years (when both known) within DUP_YEARS. Else None."""
    y = _year(year)
    for k, rt, ry, *_ in titles:
        if title and common.title_match(title, rt) and (y is None or ry is None or abs(y - ry) <= DUP_YEARS):
            return k
    return None


def add(ledger, found, source, corpus, asof=None, complete=True, n_papers=None, titles=()):
    """Record `found` (xref / forward output) as candidates, and the run itself
    under ledger["_runs"][source]. `complete` records whether the run that
    produced `found` finished, and `n_papers` how many sourced papers it read
    (both from its <out>.run.json sidecar, via run_record); main() passes
    complete=False when the sidecar says so or is missing. A new candidate
    whose title matches one in `titles` ([(key, title)], row_titles) is
    excluded at once as that row under another DOI."""
    runs = ledger.setdefault("_runs", {})
    runs[source] = {"at": asof or datetime.date.today().isoformat(), "n": len(found),
                    "complete": bool(complete)}
    if n_papers is not None:
        runs[source]["n_papers"] = n_papers
    added = skipped = 0
    for e in found:
        d = _doi(e.get("doi"))
        if not d:
            continue
        if d in corpus:
            skipped += 1
            continue
        score = e.get("shared") if source == "forward" else e.get("n_citations")
        c = ledger.get(d)
        if c is None:
            ledger[d] = {"title": e.get("title") or "", "year": str(e.get("year") or ""),
                         "first_author": e.get("first_author") or e.get("author") or "",
                         "sources": {source: score}, "decision": "pending", "reason": "", "at": ""}
            same = same_paper(ledger[d]["title"], ledger[d]["year"], titles)
            if same:
                ledger[d].update(decision="exclude", at=asof or datetime.date.today().isoformat(),
                                 reason=f"already in the table as {same} under another DOI (same title)")
                row_doi = next((t[3] for t in titles if t[0] == same), "")
                if PREPRINT_DOI.match(row_doi) and not PREPRINT_DOI.match(d):
                    ledger[d]["upgrade_row"] = same
                    ledger[d]["reason"] = (f"the published version of {same}, which cites its preprint "
                                           f"{row_doi}: move {same} to this DOI")
            added += 1
        else:
            c["sources"][source] = score
            for f, v in (("title", e.get("title")), ("year", str(e.get("year") or "")),
                         ("first_author", e.get("first_author") or e.get("author"))):
                c[f] = c.get(f) or v or ""
    return added, skipped


def decide(ledger, doi, decision, reason, asof):
    d = _doi(doi)
    if d not in ledger or d.startswith("_"):
        raise ValueError(f"{doi} is not in the ledger")
    if decision not in ("include", "exclude"):
        raise ValueError("--decision must be include or exclude")
    if not (reason or "").strip():
        raise ValueError("--reason is required")
    ledger[d].update(decision=decision, reason=reason.strip(), at=asof)


def registry_record(doi):
    """{title, first_author, year, venue} from CrossRef, else DataCite; None when
    neither registry has the DOI; {"error": why} when a lookup could not complete."""
    import urllib.error
    for fetch in (common.crossref_work, common.datacite_work):
        try:
            r = fetch(doi)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            return {"error": f"HTTP {e.code}"}
        except Exception as e:
            return {"error": type(e).__name__}
        if r:
            return {"title": r.get("title") or "", "first_author": (r.get("people") or [""])[0],
                    "year": r.get("year") or "", "venue": r.get("journal") or r.get("publisher") or ""}
    return None


def enrich(pending, email):
    """Attach each candidate's registry `record` and `abstract` (in place)."""
    import abstracts
    common.set_user_agent(email)
    recs = common.pmap(lambda c: registry_record(c["doi"]), pending)
    for c, rec in zip(pending, recs):
        c["record"] = rec
    rows = [{"ref": c["doi"], "doi": c["doi"], "summary": "-"} for c in pending]
    fetchers = {"arxiv": abstracts.fetch_arxiv, "openalex": abstracts.make_fetch_openalex(email),
                "s2": abstracts.fetch_s2, "pubmed": abstracts.fetch_pubmed,
                "pubmed-doi": abstracts.fetch_pubmed_by_doi, "europepmc": abstracts.fetch_europepmc}
    ab, _missing, _failed, _stale = abstracts.collect(rows, "ref", {}, fetchers)
    for c in pending:
        c["abstract"] = (ab.get(c["doi"]) or {}).get("text", "")
    n_rec = sum(1 for c in pending if (c["record"] or {}).get("title"))
    return sum(1 for c in pending if c["abstract"]), n_rec


def prepare(ledger, outdir, scope, manifest, per=60, project=None, lab_lane=None, email=None):
    """Write the pending candidates as outdir/input_NN.json, `per` to a file, and
    outdir/BRIEF.md rendered from TEMPLATE. With `email`, each candidate also
    carries its registry record and abstract (enrich). Returns the input paths."""
    pending = [{"doi": d, "title": c.get("title", ""), "year": c.get("year", ""),
                "first_author": c.get("first_author", ""), "sources": c.get("sources", {})}
               for d, c in entries(ledger) if c.get("decision") == "pending"]
    if not pending:
        raise ValueError("no pending candidates to prepare")
    if not os.path.isfile(scope):
        raise ValueError(f"--scope {scope} does not exist")
    os.makedirs(outdir, exist_ok=True)
    stale = glob.glob(os.path.join(outdir, "input_*.json")) + glob.glob(os.path.join(outdir, "result_*.json"))
    if stale:
        raise ValueError(f"{outdir} already holds input or result files; ingest or move them first")
    if email:
        n_ab, n_rec = enrich(pending, email)
        print(f"  fetched {n_rec} registry record(s) and {n_ab} abstract(s) for {len(pending)} candidates",
              file=sys.stderr)
    paths = []
    for i in range(0, len(pending), per):
        p = os.path.join(outdir, f"input_{i // per + 1:02d}.json")
        common.dump_json(pending[i:i + per], p)
        paths.append(p)
    runs = ledger.get("_runs") or {}
    floor = {src: min((c["sources"][src] for _, c in entries(ledger) if src in (c.get("sources") or {})
                       and isinstance(c["sources"][src], int)), default="?") for src in ("xref", "forward")}
    lanes = "\n".join(f"- `{m['key']}`: {m.get('name', '')}" for m in manifest) or "(see the scope file)"
    if lab_lane:
        lanes += f"\n- `{lab_lane}`: the lab's own papers (lab mode)"
    with open(TEMPLATE, encoding="utf-8") as fh:
        text = fh.read().split("<!-- BRIEF STARTS -->", 1)[1].lstrip()
    fills = {"SCOPE_FILE": os.path.abspath(scope), "LANE_TABLE": lanes, "INPUT_DIR": os.path.abspath(outdir),
             "PROJECT_DIR": os.path.abspath(project or os.path.dirname(os.path.abspath(outdir))),
             "XREF_FLOOR": str(floor["xref"]) if "xref" in runs else "?",
             "FORWARD_FLOOR": str(floor["forward"]) if "forward" in runs else "?"}
    for k, v in fills.items():
        text = text.replace("{" + k + "}", v)
    left = re.findall(r"\{[A-Z_]+\}", text)
    if left:
        raise ValueError(f"template placeholders left unfilled: {sorted(set(left))}")
    with open(os.path.join(outdir, "BRIEF.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    return paths


def ingest(ledger, results, asof, lanes=None):
    """Apply agent decision lists to the ledger. Checks every entry first and
    raises ValueError listing each problem, so a bad file changes nothing.
    Returns (included, excluded)."""
    problems, todo = [], []
    for path, items in results:
        if not isinstance(items, list):
            problems.append(f"{path}: not a JSON list")
            continue
        for e in items:
            d = _doi((e or {}).get("doi"))
            where = f"{os.path.basename(path)} {d or '?'}"
            if d not in ledger or d.startswith("_"):
                problems.append(f"{where}: not in the ledger")
                continue
            if e.get("decision") not in ("include", "exclude"):
                problems.append(f"{where}: decision must be include or exclude")
            if not str(e.get("reason") or "").strip():
                problems.append(f"{where}: no reason")
            if e.get("decision") == "include":
                miss = [f for f in CLAIM if not str(e.get(f) or "").strip()]
                if miss:
                    problems.append(f"{where}: include without {', '.join(miss)} from the landing page")
                elif lanes and e["lane"] not in lanes:
                    problems.append(f"{where}: lane {e['lane']!r} is not a lane of this bibliography")
            todo.append((d, e))
    if problems:
        raise ValueError("refusing the whole batch:\n  " + "\n  ".join(problems))
    n_in = n_out = 0
    for d, e in todo:
        ledger[d].update(decision=e["decision"], reason=str(e["reason"]).strip(), at=asof)
        if e["decision"] == "include":
            ledger[d]["claim"] = {f: e.get(f) or "" for f in CLAIM + ("arxiv",)}
            n_in += 1
        else:
            ledger[d].pop("claim", None)
            n_out += 1
    return n_in, n_out


def export_included(ledger, corpus, lane):
    papers = []
    for d, c in entries(ledger):
        if c.get("decision") == "include" and d not in corpus:
            srcs = sorted(c.get("sources") or {}) or ["xref"]
            src = "xref" if "xref" in srcs else srcs[0]      # the pass that found it
            cl = c.get("claim") or {}
            papers.append({"ref": f"{lane}-{len(papers) + 1:02d}", "lane": lane, "doi": d,
                           "arxiv": cl.get("arxiv", ""), "link": f"https://doi.org/{d}",
                           "first_author": cl.get("first_author") or c.get("first_author", ""),
                           "year": cl.get("year") or c.get("year", ""),
                           "title": cl.get("title") or c.get("title", ""), "apa": "",
                           "summary": cl.get("summary", ""), "tag": src, "topic": "", "source": src,
                           "note": c.get("reason", ""), "lane_fit": cl.get("lane", "")})
    return {"schema": 2, "lane": lane, "status": {"target": len(papers), "returned": len(papers),
                                                  "websearch_exhausted": False, "notes": "candidate ledger"},
            "papers": papers, "deferred": [], "could_not_confirm": []}


def candidate_defects(ledger, corpus):
    out = []
    pending = [d for d, c in entries(ledger) if c.get("decision") not in ("include", "exclude")]
    if pending:
        out.append(f"candidates-pending: {len(pending)} undecided (candidates.py --list pending)")
    for d, c in entries(ledger):
        if c.get("decision") == "include" and d not in corpus:
            out.append(f"candidate {d} is marked include but is not in the table (export, append, verify)")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--ledger", help="default: candidates.json beside --rows")
    ap.add_argument("--add", metavar="FILE")
    ap.add_argument("--source", choices=("xref", "forward", "survey"))
    ap.add_argument("--list", choices=("pending", "include", "exclude", "all"))
    ap.add_argument("--decide", metavar="DOI")
    ap.add_argument("--decision", choices=("include", "exclude"))
    ap.add_argument("--reason")
    ap.add_argument("--export-included", metavar="OUT")
    ap.add_argument("--lane", default="C", help="lane key for --export-included refs (default C; "
                    "must be a key no row uses)")
    ap.add_argument("--prepare", metavar="DIR", help="write pending candidates and BRIEF.md for agents")
    ap.add_argument("--scope", metavar="FILE", help="with --prepare: the file that defines the bibliography")
    ap.add_argument("--per", type=int, default=60, help="with --prepare: candidates per input file")
    ap.add_argument("--ingest", metavar="GLOB", help="record the agents' result files")
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"),
                    help="with --prepare: contact email for fetching records and abstracts")
    ap.add_argument("--no-fetch", action="store_true",
                    help="with --prepare: do not fetch records and abstracts")
    ap.add_argument("--asof", default=datetime.date.today().isoformat())
    args = ap.parse_args()
    rows = common.load_json(args.rows)
    path = args.ledger or os.path.join(os.path.dirname(os.path.abspath(args.rows)), "candidates.json")
    ledger = common.load_optional_json(path, {})
    try:
        validate_ledger(ledger)
    except ValueError as e:
        ap.error(str(e))
    corpus = corpus_dois(rows)
    keyf = common.key_field(rows, None)
    here = os.path.dirname(os.path.abspath(args.rows))
    if args.add:
        if not args.source:
            ap.error("--add needs --source")
        try:
            complete, n_papers = run_record(common.load_optional_json(f"{args.add}.run.json", None),
                                            args.source)
        except ValueError as e:
            ap.error(f"{args.add}.run.json: {e}")
        before = sum(1 for _, c in entries(ledger) if c.get("decision") == "exclude")
        a, s = add(ledger, common.load_json(args.add), args.source, corpus, args.asof,
                   complete=complete, n_papers=n_papers, titles=row_titles(rows, keyf))
        common.dump_json(ledger, path)
        dup = sum(1 for _, c in entries(ledger) if c.get("decision") == "exclude") - before
        print(f"added {a} candidate(s) ({dup} excluded at once: same title as a row), "
              f"skipped {s} already in the corpus -> {path}")
        for d, c in entries(ledger):
            if c.get("upgrade_row") and c["upgrade_row"] in {r.get(keyf) for r in rows} and d not in corpus:
                print(f"  ✗ {c['upgrade_row']} cites a preprint; its published version is {d}. Set the row's "
                      "doi to it, then run verify.py and references.py with --only on it", file=sys.stderr)
    elif args.prepare:
        if not args.scope:
            ap.error("--prepare needs --scope FILE (the file that defines the bibliography)")
        manifest = common.load_optional_json(os.path.join(here, "lane_manifest.json"), [])
        try:
            lab = next((r.get("lane") or str(r.get(keyf, "")).split("-")[0] for r in rows
                        if r.get("source") == "lab"), None)
            if not args.email and not args.no_fetch:
                ap.error("--prepare fetches records and abstracts: give --email (or LITREVIEW_EMAIL), "
                         "or --no-fetch")
            common.enable_record_cache(args.rows)
            paths = prepare(ledger, args.prepare, args.scope, manifest, args.per, project=here, lab_lane=lab,
                            email=None if args.no_fetch else args.email)
        except ValueError as e:
            ap.error(str(e))
        print(f"{len(paths)} input file(s) + BRIEF.md -> {args.prepare}; one agent per input file, "
              f"then --ingest '{os.path.join(args.prepare, 'result_*.json')}'")
    elif args.ingest:
        files = sorted(glob.glob(args.ingest))
        if not files:
            ap.error(f"--ingest {args.ingest}: no files match")
        manifest = common.load_optional_json(os.path.join(here, "lane_manifest.json"), [])
        # the search lanes, plus every lane the table holds (a lab lane is not in the manifest)
        lanes = ({m["key"] for m in manifest if m.get("key")}
                 | {str(r.get(keyf, "")).split("-")[0] for r in rows})
        try:
            n_in, n_out = ingest(ledger, [(f, common.load_json(f)) for f in files], args.asof, lanes)
        except ValueError as e:
            sys.exit(f"✗ {e}")
        common.dump_json(ledger, path)
        left = sum(1 for _, c in entries(ledger) if c.get("decision") == "pending")
        print(f"recorded {n_in} include(s) and {n_out} exclude(s) from {len(files)} file(s); "
              f"{left} still pending")
    elif args.decide:
        try:
            decide(ledger, args.decide, args.decision, args.reason, args.asof)
        except ValueError as e:
            ap.error(str(e))
        common.dump_json(ledger, path)
        print(f"{args.decide}: {args.decision}")
    elif args.export_included:
        used = {str(r.get(keyf, "")).split("-")[0] for r in rows}
        if args.lane in used:
            ap.error(f"--lane {args.lane} is already a lane key in the table; pick another")
        lane = export_included(ledger, corpus, args.lane)
        common.dump_json(lane, args.export_included)
        print(f"{len(lane['papers'])} included paper(s) -> {args.export_included}; "
              f"next: merge_lanes.py --append {args.export_included} --into {args.rows}")
    elif args.list:
        for d, c in entries(ledger):
            if args.list == "all" or c.get("decision") == args.list:
                print(f"{d}\t{c.get('decision')}\t{c.get('year')}\t{c.get('first_author')}\t{c.get('title')}\t"
                      f"{c.get('sources')}\t{c.get('reason')}")
    else:
        ap.error("give one of --add, --prepare, --ingest, --decide, --export-included, --list")
    for x in candidate_defects(ledger, corpus):
        print(f"  · {x}", file=sys.stderr)


if __name__ == "__main__":
    main()
