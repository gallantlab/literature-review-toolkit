#!/usr/bin/env python3
"""Verify a list of citations against PMC / PubMed / CrossRef / arXiv.

Reports: confirmed-OK, author-mismatch, year-mismatch, not-found.

arXiv/conference papers are a verification BLIND SPOT for PMC/PubMed/CrossRef:
an arXiv DOI (10.48550/arXiv.<id>) is not in CrossRef, and a PubMed title-search
returns a plausible-but-wrong paper — so they come back NOT-FOUND or a garbage
MISMATCH, which reads as "skip" and lets a whole class of papers (AI/ML venues,
preprints) dodge the check. So this tool resolves arXiv DOIs and bare `arxiv`
ids directly against the arXiv API. Never treat NOT-FOUND as "fine to add."

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
import argparse, json, os, sys, time, urllib.parse
import xml.etree.ElementTree as ET

import common
from common import ATOM, arxiv_id_of, http, http_json, set_user_agent

# NCBI/CrossRef expect a contact email in the User-Agent; backoff on 429/503.
http_get_json = http_json


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
    try:
        d = http_get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")
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
    except Exception:
        return None


def lookup_arxiv(aid):
    """Resolve a bare arXiv id (e.g. '2305.18274') via the arXiv Atom API."""
    aid = aid.strip()
    url = f"http://export.arxiv.org/api/query?id_list={urllib.parse.quote(aid)}"
    root = ET.fromstring(http(url))
    e = root.find(f"{ATOM}entry")
    if e is None or e.find(f"{ATOM}title") is None:
        return None
    authors = [a.find(f"{ATOM}name").text for a in e.findall(f"{ATOM}author")]
    return {
        "title": " ".join((e.find(f"{ATOM}title").text or "").split()),
        # arXiv 'published' is the submission date, which can precede the venue
        # publication year by a year or two — the ±1 year tolerance below absorbs
        # the common case; a larger gap is surfaced as a (reviewable) MISMATCH.
        "year": (e.find(f"{ATOM}published").text or "")[:4],
        "first_author": authors[0] if authors else "",
        "journal": "arXiv",
    }


def verify_one(c):
    """Try lookups in priority order and return result + verdict.

    arXiv papers route to the arXiv API FIRST (CrossRef has no arXiv DOIs and a
    PubMed title-search mis-resolves them), so they get a real verdict instead of
    a misleading NOT-FOUND/MISMATCH."""
    found = None
    src = None
    aid = arxiv_id_of(c)
    if aid:
        try:
            r = lookup_arxiv(aid)
            if r:
                found, src = r, "arxiv"
        except Exception:
            pass
    if not found:
        for fn, key in [(lookup_pmc, "pmcid"), (lookup_pubmed_id, "pmid"), (lookup_crossref, "doi")]:
            if c.get(key):
                try:
                    r = fn(c[key])
                    if r:
                        found = r
                        src = key
                        break
                except Exception:
                    pass
    if not found and c.get("title"):
        try:
            found = lookup_pubmed_title(c["title"])
            src = "title-search"
        except Exception:
            pass

    if not found:
        return {"verdict": "NOT-FOUND", "found": None, "source": None}

    issues = []
    expect_au = (c.get("expect_first_author") or "").lower().strip()
    actual_au = (found.get("first_author") or "").lower().strip()
    # Fuzzy surname containment (handles "Tang" vs "Tang J"). It can over-accept
    # a short surname that is a substring of another ("Lee" in "Leeson") — a
    # deliberate trade to avoid false MISMATCH spam; verdicts are human-reviewed.
    if expect_au and actual_au and expect_au.split()[0] not in actual_au and actual_au.split()[0] not in expect_au:
        issues.append(f"first-author mismatch: expected '{c.get('expect_first_author')}', got '{found['first_author']}'")
    expect_year = (c.get("expect_year") or "").strip()
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
    out = []
    for c in cits:
        r = verify_one(c)
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
    print(f"\n=== {n_ok} OK / {n_mm} MISMATCH / {n_nf} NOT-FOUND ===", file=sys.stderr)


if __name__ == "__main__":
    main()
