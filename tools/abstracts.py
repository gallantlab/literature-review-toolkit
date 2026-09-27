#!/usr/bin/env python3
"""Fetch each row's abstract into abstracts.json, for the summary check.

The summary check (summary_audit.py) compares each summary with its abstract, so
each abstract comes from the most authoritative source that has it. The sources
are tried in order: the arXiv API for arXiv papers, then OpenAlex (50 DOIs per
request), then Semantic Scholar (500 ids per request), then PubMed for rows with
a `pmid`, then PubMed by DOI (50 per request), then Europe PMC by DOI (20 per
request). The last two found 150 of the 194 abstracts the others missed on one
1,215-row build, which a landing-page agent had to collect before. A source's
abstract field sometimes holds something else: a journal's
self-description, JSTOR's terms of use, a citation line, or an author list and
venue. not_an_abstract() refuses such a text, the next source is tried, and a
text no later source replaced is reported.

Each entry records the `doi` and `arxiv` it was fetched for. When a row's ids
change, its entry is fetched again. An entry added by hand ("source":
"landing-page") is never overwritten; one with an empty `text` records that the
paper has no abstract. When its ids no longer match the row, it is reported as
stale: check that it is still this paper's abstract, then set its ids to the
row's.

abstracts.json goes beside --rows unless --out names another file.
abstracts_failed.json, written beside abstracts.json, maps each ref whose fetch
could not complete to the reason ({} when none). A failed fetch is not "no
abstract", so summary_audit.py --prepare refuses those refs.

Exit 1 when any fetch failed or any hand-added entry is stale; re-run to fill
the gaps. A spent OpenAlex daily budget stops the run with OpenAlexBudgetError.
One S2_API_KEY serves xref, citations and abstracts; their requests take turns
through a pacer shared across processes, so they may run at the same time.

    python3 tools/abstracts.py --rows rows.json --email you@inst.edu
"""
import argparse
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

import common

PHASE = "5c"   # pipeline phase, read by tools/gen_docs.py for the tool index


def reconstruct(inv):
    """OpenAlex abstract_inverted_index -> text."""
    if not inv:
        return ""
    return " ".join(w for _, w in sorted((p, w) for w, ps in inv.items() for p in ps))


def fetch_arxiv(aids):
    """-> ({id: text}, {id that a batch could not complete for})."""
    entries, err = common.arxiv_batch(aids)
    return {a: e["summary"] for a, e in entries.items() if e.get("summary")}, set(err)


def make_fetch_openalex(email):
    def fetch(dois):
        out, failed = {}, set()
        for i in range(0, len(dois), 50):
            batch = dois[i:i + 50]
            filt = "doi:" + "|".join(batch)
            url = (f"https://api.openalex.org/works?filter={urllib.parse.quote(filt, safe=':|/.')}"
                   f"&per-page=100&select=doi,abstract_inverted_index&mailto={email}")
            try:
                for w in common.http_json(url).get("results", []):
                    d = (w.get("doi") or "").lower().replace("https://doi.org/", "")
                    t = reconstruct(w.get("abstract_inverted_index"))
                    if d and t:
                        out[d] = t
            except common.OpenAlexBudgetError:
                raise
            except Exception as e:
                print(f"  OpenAlex batch {i}: {type(e).__name__}: {e}", file=sys.stderr)
                failed.update(batch)
        return out, failed
    return fetch


def fetch_s2(ids):
    """-> ({id: abstract}, failed). An id S2 rejects (400) is 'not in S2' — a
    complete lookup — and is named; a chunk that fails transiently is failed."""
    res, failed, rejected = common.s2_batch("paper/batch?fields=abstract", ids, 500)
    if rejected:
        print(f"  S2 rejected {len(rejected)} id(s) as invalid (treated as not in S2): "
              f"{', '.join(sorted(rejected))}", file=sys.stderr)
    if failed:
        print(f"  S2 lookups failed for {len(failed)} id(s)", file=sys.stderr)
    return {sid: p["abstract"] for sid, p in res.items() if p and p.get("abstract")}, failed


def fetch_pubmed(pmids):
    out, failed = {}, set()
    for i in range(0, len(pmids), 200):
        part = pmids[i:i + 200]
        url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id="
               + ",".join(part))
        try:
            root = ET.fromstring(common.http(url))
        except Exception as e:
            print(f"  PubMed batch {i}: {type(e).__name__}: {e}", file=sys.stderr)
            failed.update(part)
            continue
        for art in root.findall(".//PubmedArticle"):
            pmid = art.findtext(".//PMID") or ""
            text = " ".join("".join(t.itertext()).strip() for t in art.findall(".//Abstract/AbstractText"))
            if pmid and text.strip():
                out[pmid] = " ".join(text.split())
    return out, failed


def _pubmed_articles(root):
    """(doi, pmid, abstract) for every PubmedArticle in an efetch reply."""
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//PMID") or ""
        doi = ""
        for aid in art.findall(".//ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi" and aid.text:
                doi = aid.text.strip().lower()
        text = " ".join("".join(t.itertext()).strip() for t in art.findall(".//Abstract/AbstractText"))
        yield doi, pmid, " ".join(text.split())


def fetch_pubmed_by_doi(dois, batch=50):
    """PubMed abstracts looked up by DOI, for rows with no PMID: one esearch per
    batch of DOIs (term "a[doi] OR b[doi]"), then one efetch for the PMIDs it
    returns, matched back to each DOI by the article's own DOI record. On
    gallant_lab_v2 the landing-page agents found most of 171 missing abstracts in
    PubMed and Europe PMC; this and fetch_europepmc do that step in the tool."""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    out, failed = {}, set()
    for i in range(0, len(dois), batch):
        part = dois[i:i + batch]
        term = " OR ".join(f"{d}[doi]" for d in part)
        try:
            ids = common.http_json(f"{base}esearch.fcgi?db=pubmed&retmode=json&retmax={2 * len(part)}&term="
                                   + urllib.parse.quote(term)).get("esearchresult", {}).get("idlist", [])
            if not ids:
                continue
            root = ET.fromstring(common.http(f"{base}efetch.fcgi?db=pubmed&retmode=xml&id="
                                             + ",".join(ids)))
        except Exception as e:
            print(f"  PubMed-by-DOI batch {i}: {type(e).__name__}: {e}", file=sys.stderr)
            failed.update(part)
            continue
        want = set(part)
        for doi, _pmid, text in _pubmed_articles(root):
            if doi in want and text:
                out[doi] = text
    return out, failed


EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def fetch_europepmc(dois, batch=20):
    """Europe PMC abstracts by DOI (query DOI:"a" OR DOI:"b", core results)."""
    out, failed = {}, set()
    for i in range(0, len(dois), batch):
        part = dois[i:i + batch]
        q = " OR ".join(f'DOI:"{d}"' for d in part)
        try:
            res = common.http_json(f"{EUROPEPMC}?format=json&resultType=core&pageSize={2 * len(part)}"
                                   "&query=" + urllib.parse.quote(q))
        except Exception as e:
            print(f"  Europe PMC batch {i}: {type(e).__name__}: {e}", file=sys.stderr)
            failed.update(part)
            continue
        want = set(part)
        for r in (res.get("resultList") or {}).get("result", []):
            d = (r.get("doi") or "").lower()
            text = re.sub(r"<[^>]+>", " ", r.get("abstractText") or "")
            if d in want and text.strip() and d not in out:
                out[d] = " ".join(text.split())
    return out, failed


def _s2_id(row):
    aid = common.arxiv_id_of(row)
    if aid:
        return f"ARXIV:{common.norm_arxiv(aid)}"
    d = common.doi_of(row, lower=True)
    return f"DOI:{d}" if d else ""


_BOILERPLATE = re.compile(
    r"\ba peer[- ]reviewed journal\b|JSTOR is a not-for-profit|terms (and conditions )?of use|"
    r"all rights reserved|this content downloaded from|use of the jstor archive|"
    r"content in the JSTOR archive|you may not download an entire issue|"
    r"\bVolume \d+,? Issue \d+\b", re.I)


def not_an_abstract(text):
    """Why `text` is not a paper's abstract, or "" if it may be one.

    Sources sometimes hold something else in the abstract field: a journal's
    self-description ("PNAS, a peer reviewed journal..."), JSTOR's terms of use,
    a citation line for another item ("...; Preface: ..., Volume 1, Issue 1"), or
    just the author list and venue. A summary written from one of these describes
    the text, not the paper, so it is refused here and the next source is tried."""
    t = " ".join((text or "").split())
    if not t:
        return "empty"
    m = _BOILERPLATE.search(t)
    if m:
        return f"boilerplate ({m.group(0)!r})"
    words = t.split()
    if len(words) < 60 and re.search(r"\b(Proceedings of|In Proceedings|Conference on)\b", t) and \
            re.match(r"^\W*(?:[A-Z][\w.'’\- ]{1,40}, ){2,}", t):
        return "an author list and venue, not an abstract"
    return ""


def collect(rows, keyf, existing, fetchers, rejected=None):
    """-> ({ref: {text, source, url, doi, arxiv}}, missing, failed {ref: reason}, stale).

    `missing` is every ref with a summary whose lookup completed at every
    source and found no abstract. `failed` is every ref whose lookup could not
    complete at some source (a batch that raised) and that no later source
    filled — reported separately because a failed fetch is not "no abstract"
    and must not be silently folded into `missing`. `stale` is every ref whose
    hand-added (landing-page) entry records other ids than the row now has: it
    is kept as it is, but it is not this paper's abstract any more; one recorded for
    the row's preprint_doi (the row moved to its published version) is refetched.
    `rejected`, if given, is filled with {ref: [why]} for every text a source
    returned that not_an_abstract() refused and no later source replaced.
    """
    ab, stale = dict(existing), []
    for r in rows:
        k, e = r.get(keyf), ab.get(r.get(keyf))
        if isinstance(e, dict) and common.stamp_ids(e) != common.ids_of(r):
            moved = r.get("preprint_doi") and (e.get("doi") or "").lower() == r["preprint_doi"].lower()
            if e.get("source") == "landing-page" and not moved:
                stale.append(k)
            else:
                del ab[k]            # fetched for other ids: fetch it again for these
        elif isinstance(e, dict) and e.get("source") != "landing-page" and not_an_abstract(e.get("text")):
            del ab[k]                # fetched before the screen existed and is not an abstract: refetch
    todo = [r for r in rows if r.get(keyf) not in ab]
    by = {r.get(keyf): r for r in rows}
    failed_refs = {}
    refused = {}           # ref -> [why], texts a source returned that are not abstracts

    def take(source, key_of, fetch):
        nonlocal todo
        want = {r.get(keyf): key_of(r) for r in todo if key_of(r)}
        if not want:
            return
        got, failed_keys = fetch(sorted(set(want.values())))
        for ref, k in want.items():
            why = not_an_abstract(got.get(k)) if got.get(k) else ""
            if why:
                refused.setdefault(ref, []).append(f"{source}: {why}")
                continue
            if got.get(k):
                d, a = common.ids_of(by[ref])
                ab[ref] = {"text": got[k], "source": source, "url": "", "doi": d, "arxiv": a}
            elif k in failed_keys:
                failed_refs.setdefault(ref, []).append(source)
        todo = [r for r in todo if r.get(keyf) not in ab]

    take("arxiv", lambda r: common.norm_arxiv(common.arxiv_id_of(r) or ""), fetchers["arxiv"])
    take("openalex", lambda r: common.doi_of(r, lower=True) or "", fetchers["openalex"])
    take("s2", _s2_id, fetchers["s2"])
    take("pubmed", lambda r: str(r.get("pmid") or ""), fetchers["pubmed"])
    def doi_key(r):                   # arXiv DOIs are not in PubMed or Europe PMC
        d = common.doi_of(r, lower=True) or ""
        return "" if common.ARXIV_DOI.match(d) else d
    if "pubmed-doi" in fetchers:
        take("pubmed", doi_key, fetchers["pubmed-doi"])
    if "europepmc" in fetchers:
        take("europepmc", doi_key, fetchers["europepmc"])
    # a later source may still have found it
    failed = {r.get(keyf): f"{'/'.join(failed_refs[r.get(keyf)])} lookup could not complete"
              for r in rows if r.get(keyf) in failed_refs and r.get(keyf) not in ab}
    missing = [r.get(keyf) for r in rows if (r.get("summary") or "").strip()
               and r.get(keyf) not in ab and r.get(keyf) not in failed_refs]
    if rejected is not None:
        rejected.update({k: v for k, v in refused.items() if k not in ab})
    return ab, missing, failed, stale


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", help="default: abstracts.json beside --rows")
    ap.add_argument("--key", default=None, help="row key field (default: ref, else label)")
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"))
    args = ap.parse_args()
    if not args.email:
        ap.error("--email or LITREVIEW_EMAIL required (arXiv/OpenAlex polite pool)")
    common.set_user_agent(args.email)
    rows = common.load_json(args.rows)
    keyf = common.key_field(rows, args.key)
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.rows)), "abstracts.json")
    existing = common.load_optional_json(out, {})
    fetchers = {"arxiv": fetch_arxiv, "openalex": make_fetch_openalex(re.sub(r"\s", "", args.email)),
                "s2": fetch_s2, "pubmed": fetch_pubmed, "pubmed-doi": fetch_pubmed_by_doi,
                "europepmc": fetch_europepmc}
    rejected = {}
    ab, missing, failed, stale = collect(rows, keyf, existing, fetchers, rejected)
    common.dump_json(ab, out)
    common.dump_json(failed, os.path.join(os.path.dirname(os.path.abspath(out)), "abstracts_failed.json"))
    by = {}
    for v in ab.values():
        by[v["source"]] = by.get(v["source"], 0) + 1
    print(f"{len(ab)} abstracts -> {out} ({', '.join(f'{k} {n}' for k, n in sorted(by.items()))})")
    if missing:
        print(f"  {len(missing)} row(s) with a summary and no abstract (add a landing-page entry, "
              f"or acknowledge no-abstract later): {', '.join(missing)}")
    for k, whys in rejected.items():
        print(f"  ⚠ {k}: refused a text that is not its abstract ({'; '.join(whys)}); add a "
              "landing-page entry if the paper has one", file=sys.stderr)
    for k in stale:
        print(f"  ✗ {k}: its landing-page abstract records other ids than the row now has; check it is "
              "this paper's, then set its doi/arxiv to the row's (or delete it and re-run)", file=sys.stderr)
    if failed:
        print(f"  {len(failed)} row(s) fetch failed — re-run abstracts.py; this is not 'no abstract': "
              f"{', '.join(failed)}", file=sys.stderr)
    if failed or stale:
        sys.exit(1)


if __name__ == "__main__":
    main()
