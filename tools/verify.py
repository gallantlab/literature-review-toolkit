#!/usr/bin/env python3
"""Verify a list of citations against PMC / PubMed / CrossRef / arXiv.

Reports one verdict per citation: OK, MISMATCH (author/year), NOT-FOUND, or
ERROR. NOT-FOUND and ERROR are kept strictly separate: NOT-FOUND means every
lookup completed and none matched (chase it down — likely fabricated); ERROR
means a lookup could not complete (rate-limit / network) and must be re-run.
Collapsing the two — as an earlier version did by swallowing exceptions into
NOT-FOUND — can drop a real paper on a transient throttle. Never add a NOT-FOUND
without chasing it, and always re-run an ERROR.

arXiv/conference papers are a verification BLIND SPOT for PMC/PubMed/CrossRef:
an arXiv DOI (10.48550/arXiv.<id>) is not in CrossRef, and a PubMed title-search
returns a plausible-but-wrong paper — so they come back NOT-FOUND or a garbage
MISMATCH, which reads as "skip" and lets a whole class of papers (AI/ML venues,
preprints) dodge the check. So this tool resolves arXiv DOIs and bare `arxiv`
ids directly against the arXiv API, prefetched in BATCHES (the API takes many
ids per `id_list` call and rate-limits a per-paper loop into a ban).

Input format (JSON list of dicts):
[
  {"label": "Tang2023_decoder",
   "pmcid": "PMC11304553",        # optional
   "pmid":  "37127759",           # optional
   "doi":   "10.1038/s41593-...", # optional (incl. arXiv DOIs 10.48550/arXiv.X)
   "arxiv": "2305.18274",         # optional; bare arXiv id (else parsed from doi)
   "title": "Semantic reconstruction ...",  # optional, used as fallback search
   "expect_first_author": "Tang J",  # optional; if given, will be checked
   "expect_year": "2023"             # optional; if given, will be checked
  },
  ...
]

Run:  python3 verify.py < input.json > report.json
Or:   python3 verify.py --citations input.json --out report.json
"""
import argparse, json, os, re, socket, sys, time, urllib.error, urllib.parse
import xml.etree.ElementTree as ET

import common
from common import ATOM, arxiv_id_of, http, http_json, set_user_agent

# NCBI/CrossRef expect a contact email in the User-Agent; backoff on 429/503.
http_get_json = http_json

# HTTP status codes that mean "try again later" rather than "does not exist".
_TRANSIENT_HTTP = {429, 500, 502, 503, 504}


def _is_transient(exc):
    """True if `exc` is a rate-limit / server / network failure (the lookup
    could not complete), as opposed to a clean 'no such record' (e.g. 404).
    Used so an exhausted-backoff failure is reported as ERROR, never mistaken
    for a NOT-FOUND (which the workflow treats as 'chase down / likely fake')."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _TRANSIENT_HTTP
    return isinstance(exc, (urllib.error.URLError, TimeoutError, socket.timeout))


def _norm_arxiv(aid):
    """Normalize an arXiv id for matching: strip whitespace and a version suffix."""
    return re.sub(r"v\d+$", "", (aid or "").strip())


def lookup_pmc(pmcid):
    n = pmcid.replace("PMC", "")
    d = http_get_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pmc&id={n}&retmode=json")
    if "result" in d and n in d["result"] and "uid" in d["result"][n]:
        r = d["result"][n]
        return {
            "title": r.get("title", ""),
            "year": (r.get("pubdate", "") or "")[:4],
            "first_author": (r.get("authors") or [{"name": ""}])[0].get("name", ""),
            "journal": r.get("source", ""),
        }
    return None


def lookup_pubmed_id(pmid):
    d = http_get_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json")
    if "result" in d and pmid in d["result"]:
        r = d["result"][pmid]
        return {
            "title": r.get("title", ""),
            "year": (r.get("pubdate", "") or "")[:4],
            "first_author": (r.get("authors") or [{"name": ""}])[0].get("name", ""),
            "journal": r.get("source", ""),
        }
    return None


def lookup_pubmed_title(title):
    q = urllib.parse.quote_plus(title)
    d = http_get_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={q}&retmode=json&retmax=2")
    ids = d.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return None
    return lookup_pubmed_id(ids[0])


def lookup_crossref(doi):
    # Let a transient failure propagate (verify_one reports it as ERROR); a clean
    # miss (404 / unknown DOI) returns None. Swallowing everything to None — as
    # this once did — hides rate-limiting as a false "not in CrossRef".
    try:
        d = http_get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")
    except Exception as e:
        if _is_transient(e):
            raise
        return None
    m = d["message"]
    au = (m.get("author") or [{}])[0]
    first = f"{au.get('family','')} {au.get('given','')[:1]}".strip()
    year = ""
    for k in ("published-print", "published-online", "issued"):
        if k in m and m[k].get("date-parts", [[]])[0]:
            year = str(m[k]["date-parts"][0][0])
            break
    return {
        "title": (m.get("title") or [""])[0],
        "year": year,
        "first_author": first,
        "journal": (m.get("container-title") or [""])[0],
    }


def _parse_arxiv_entry(e):
    """Build a found-record from one arXiv Atom <entry>, or None if it is the
    API's synthetic 'Error' entry (an unknown id) or has no title."""
    title = (e.findtext(f"{ATOM}title") or "").strip()
    if not title or title == "Error":
        return None
    authors = [a.findtext(f"{ATOM}name") for a in e.findall(f"{ATOM}author")]
    return {
        "title": " ".join(title.split()),
        # arXiv 'published' is the submission date, which can precede the venue
        # publication year by a year or two — the ±1 year tolerance below absorbs
        # the common case; a larger gap is surfaced as a (reviewable) MISMATCH.
        "year": (e.findtext(f"{ATOM}published") or "")[:4],
        "first_author": authors[0] if authors else "",
        "journal": "arXiv",
    }


def lookup_arxiv_batch(aids, chunk=50, sleep=3.0):
    """Resolve many arXiv ids in a handful of requests via the API's `id_list`
    (comma-separated). arXiv asks for a ~3s courtesy interval and rate-limits
    hard, so one-request-per-paper gets the IP temporarily banned on a big run —
    the whole reason a batch of real papers can come back as false NOT-FOUNDs.

    Returns (results, errored): `results[norm_id]` is the found-record or None
    (a genuine miss), and `errored` is the set of ids whose chunk failed
    transiently (reported as ERROR, not NOT-FOUND, so they get re-run)."""
    results, errored = {}, set()
    uniq = list(dict.fromkeys(_norm_arxiv(a) for a in aids if a))
    for i in range(0, len(uniq), chunk):
        batch = uniq[i:i + chunk]
        url = ("http://export.arxiv.org/api/query?max_results="
               f"{len(batch)}&id_list={urllib.parse.quote(','.join(batch))}")
        try:
            root = ET.fromstring(http(url))
        except Exception:
            errored.update(batch)          # transient: don't mistake for missing
            continue
        got = {}
        for e in root.findall(f"{ATOM}entry"):
            idtext = e.findtext(f"{ATOM}id") or ""
            m = re.search(r"abs/(.+?)(?:v\d+)?$", idtext)
            rec = _parse_arxiv_entry(e)
            if m and rec:
                got[_norm_arxiv(m.group(1))] = rec
        for a in batch:
            results[a] = got.get(a)          # None = arXiv returned no entry = miss
        if i + chunk < len(uniq):
            time.sleep(sleep)
    return results, errored


def verify_one(c, arxiv_results=None, arxiv_errored=None):
    """Try lookups in priority order and return result + verdict.

    arXiv papers route to the arXiv API FIRST (CrossRef has no arXiv DOIs and a
    PubMed title-search mis-resolves them), so they get a real verdict instead of
    a misleading NOT-FOUND/MISMATCH. arXiv ids are resolved from `arxiv_results`
    (prefetched in batch by main); `arxiv_errored` holds ids whose batch failed.

    A lookup that fails transiently (rate-limit / network) yields verdict ERROR,
    kept strictly distinct from NOT-FOUND — a throttled fetch must never read as
    'this paper does not exist' and get dropped."""
    arxiv_results = arxiv_results or {}
    arxiv_errored = arxiv_errored or set()
    found = None
    src = None
    errored = False          # a lookup could not complete (not a clean miss)

    aid = arxiv_id_of(c)
    if aid:
        na = _norm_arxiv(aid)
        if na in arxiv_errored:
            errored = True
        elif na in arxiv_results:
            if arxiv_results[na]:
                found, src = arxiv_results[na], "arxiv"
        else:                # standalone/uncached call: resolve just this id
            res, err = lookup_arxiv_batch([aid])
            if na in err:
                errored = True
            elif res.get(na):
                found, src = res[na], "arxiv"
    if not found:
        for fn, key in [(lookup_pmc, "pmcid"), (lookup_pubmed_id, "pmid"), (lookup_crossref, "doi")]:
            if c.get(key):
                try:
                    r = fn(c[key])
                except Exception as e:
                    if _is_transient(e):
                        errored = True
                    continue
                if r:
                    found, src = r, key
                    break
    if not found and c.get("title"):
        try:
            found = lookup_pubmed_title(c["title"])
            src = "title-search"
        except Exception as e:
            if _is_transient(e):
                errored = True

    if not found:
        # ERROR (a lookup could not complete) vs NOT-FOUND (every lookup completed
        # and none matched) — surfaced separately so transient failures are re-run,
        # not waved through as nonexistent.
        if errored:
            return {"verdict": "ERROR", "found": None, "source": None,
                    "issues": ["lookup failed (rate-limit/network) — re-run to verify"]}
        return {"verdict": "NOT-FOUND", "found": None, "source": None}

    issues = []
    # str() so a JSON integer year or non-string author can't crash the whole run.
    expect_au = str(c.get("expect_first_author") or "").lower().strip()
    actual_au = (found.get("first_author") or "").lower().strip()
    # Fuzzy surname containment (handles "Tang" vs "Tang J"). It can over-accept
    # a short surname that is a substring of another ("Lee" in "Leeson") — a
    # deliberate trade to avoid false MISMATCH spam; verdicts are human-reviewed.
    if expect_au and actual_au and expect_au.split()[0] not in actual_au and actual_au.split()[0] not in expect_au:
        issues.append(f"first-author mismatch: expected '{c.get('expect_first_author')}', got '{found['first_author']}'")
    expect_year = str(c.get("expect_year") or "").strip()
    actual_year = (found.get("year") or "").strip()
    # Guard the int() — a human-typed "in press"/"2023a" must not crash the run;
    # compare numerically only when both years are clean 4-digit values.
    if expect_year.isdigit() and actual_year.isdigit() and abs(int(expect_year) - int(actual_year)) > 1:
        issues.append(f"year mismatch: expected {expect_year}, got {found['year']}")

    return {
        "verdict": "OK" if not issues else "MISMATCH",
        "issues": issues,
        "found": found,
        "source": src,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--citations", help="JSON file (else read stdin)")
    ap.add_argument("--out", help="JSON output file (else stdout)")
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"),
                    help="Contact email for NCBI/CrossRef User-Agent (required; "
                         "or set LITREVIEW_EMAIL env var)")
    args = ap.parse_args()

    if not args.email:
        sys.exit("error: provide --email or set LITREVIEW_EMAIL "
                 "(NCBI/CrossRef expect a contact email in the User-Agent)")
    set_user_agent(args.email)

    if args.citations:
        cits = common.load_json(args.citations)
    else:
        cits = json.loads(sys.stdin.read())

    # Prefetch every arXiv id in a few batched requests. arXiv rate-limits a
    # per-paper loop into a temporary ban (its retries exhaust and the paper
    # falls through to a false NOT-FOUND), so batching is both faster and the fix
    # for that failure mode; ids whose chunk failed come back as ERROR, not miss.
    aids = [a for a in (arxiv_id_of(c) for c in cits) if a]
    arxiv_results, arxiv_errored = ({}, set())
    if aids:
        print(f"  [arxiv] batch-resolving {len(set(_norm_arxiv(a) for a in aids))} ids…", file=sys.stderr)
        arxiv_results, arxiv_errored = lookup_arxiv_batch(aids)

    out = []
    for c in cits:
        try:
            r = verify_one(c, arxiv_results, arxiv_errored)
        except Exception as e:
            # One malformed row must not abort a long batch — record and move on.
            r = {"verdict": "ERROR", "found": None, "source": None,
                 "issues": [f"{type(e).__name__}: {e}"]}
        r["label"] = c.get("label", "?")
        out.append(r)
        v = r["verdict"]
        au = r["found"]["first_author"] if r["found"] else "?"
        yr = r["found"]["year"] if r["found"] else "?"
        ti = (r["found"]["title"] if r["found"] else "")[:60]
        print(f"  [{v:9s}] {c.get('label','?')}  →  {au} ({yr})  {ti}", file=sys.stderr)
        if r.get("issues"):
            for i in r["issues"]:
                print(f"             ↳ {i}", file=sys.stderr)
        time.sleep(args.sleep)

    if args.out:
        common.dump_json(out, args.out)
    else:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    n_ok = sum(1 for r in out if r["verdict"] == "OK")
    n_mm = sum(1 for r in out if r["verdict"] == "MISMATCH")
    n_nf = sum(1 for r in out if r["verdict"] == "NOT-FOUND")
    n_er = sum(1 for r in out if r["verdict"] == "ERROR")
    tail = f" / {n_er} ERROR" if n_er else ""
    print(f"\n=== {n_ok} OK / {n_mm} MISMATCH / {n_nf} NOT-FOUND{tail} ===", file=sys.stderr)
    if n_er:
        print("    ERROR = lookup could not complete (rate-limit/network); re-run "
              "those — NOT the same as NOT-FOUND.", file=sys.stderr)


if __name__ == "__main__":
    main()
