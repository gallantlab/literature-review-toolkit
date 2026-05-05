#!/usr/bin/env python3
"""Verify a list of citations against PMC / PubMed / CrossRef.

Reports: confirmed-OK, author-mismatch, year-mismatch, not-found.

Input format (JSON list of dicts):
[
  {"label": "Tang2023_decoder",
   "pmcid": "PMC11304553",        # optional
   "pmid":  "37127759",           # optional
   "doi":   "10.1038/s41593-...", # optional
   "title": "Semantic reconstruction ...",  # optional, used as fallback search
   "expect_first_author": "Tang J",  # optional; if given, will be checked
   "expect_year": "2023"             # optional; if given, will be checked
  },
  ...
]

Run:  python3 verify.py < input.json > report.json
Or:   python3 verify.py --citations input.json --out report.json
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request

# Set via --email flag or LITREVIEW_EMAIL env var. NCBI/CrossRef expect a
# contact email in the User-Agent for API politeness.
HDRS = {"User-Agent": "litreview-toolkit/1.0"}


def set_user_agent(email: str):
    HDRS["User-Agent"] = f"litreview-toolkit/1.0 (mailto:{email})"


def http_get_json(url, timeout=20):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


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


def verify_one(c):
    """Try lookups in priority order and return result + verdict."""
    found = None
    src = None
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
    if expect_au and actual_au and expect_au.split()[0] not in actual_au and actual_au.split()[0] not in expect_au:
        issues.append(f"first-author mismatch: expected '{c.get('expect_first_author')}', got '{found['first_author']}'")
    expect_year = (c.get("expect_year") or "").strip()
    if expect_year and found.get("year") and abs(int(expect_year) - int(found["year"])) > 1:
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

    raw = open(args.citations).read() if args.citations else sys.stdin.read()
    cits = json.loads(raw)
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

    js = json.dumps(out, indent=2)
    if args.out:
        open(args.out, "w").write(js)
    else:
        print(js)
    n_ok = sum(1 for r in out if r["verdict"] == "OK")
    n_mm = sum(1 for r in out if r["verdict"] == "MISMATCH")
    n_nf = sum(1 for r in out if r["verdict"] == "NOT-FOUND")
    print(f"\n=== {n_ok} OK / {n_mm} MISMATCH / {n_nf} NOT-FOUND ===", file=sys.stderr)


if __name__ == "__main__":
    main()
