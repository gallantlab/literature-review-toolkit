#!/usr/bin/env python3
"""Lab mode — Phase L1: ingest a lab's full publication corpus from OpenAlex.

Topic mode starts from a query and searches outward; LAB MODE starts from a
known set of papers (a lab's output), derives the themes, tracks them over time,
and only then searches outward to place them in the field. This tool fetches the
corpus — the seed everything else hangs off.

Give it an OpenAlex author id (recommended — use --search first to find it).
"All papers from a lab" is approximated by a PI's authored works; pass several
ids (PI + key members) with repeated --author if you want broader coverage.

  python3 tools/lab_corpus.py --search "Jack Gallant"          # find the id
  python3 tools/lab_corpus.py --author A5056348548 --out lab_papers.json

Output: lab_papers.json — one row per paper with ref / title / year / doi / link
/ apa / venue / cite_openalex / topics / abstract(summary) / coauthors / type.
Disambiguation is the #1 correctness risk: review the list (Phase L2) and prune
false-positives before theming.  See PLAYBOOK "Lab mode".
"""
import argparse, os, time, urllib.parse

import common
from common import build_apa, http_json, person, split_name

API = "https://api.openalex.org"


def get(url):
    """OpenAlex GET with backoff (the cursor loop can run for many pages)."""
    return http_json(url, timeout=60)


def search_authors(name, email):
    url = f"{API}/authors?search={urllib.parse.quote(name)}&per-page=10&mailto={email}"
    for a in get(url).get("results", []):
        insts = a.get("last_known_institutions") or []
        inst = insts[0]["display_name"] if insts else "?"
        print(f"  {a['id'].split('/')[-1]}  {a['display_name']:28s}  "
              f"{a.get('works_count'):>4} works  {a.get('cited_by_count'):>7} cites  {inst}")


def unabstract(inv):
    """Reconstruct an abstract from OpenAlex's inverted index."""
    if not inv:
        return ""
    words = sorted(((pos, w) for w, ps in inv.items() for pos in ps))
    return " ".join(w for _, w in words)


def apa(authorships, year, title, venue, biblio=None):
    """A full APA-7 reference whose first comma separates the lead surname (the
    figure parses that). Uses the shared formatter so OpenAlex names get the same
    canonical treatment as CrossRef/arXiv — including nobiliary particles
    ('de Heer' stays the surname, not 'Heer' with a stray 'D.' initial)."""
    people = []
    for a in authorships:
        disp = (a.get("author", {}).get("display_name") or "").strip()
        if disp:
            people.append(person(*split_name(disp)))
    b = biblio or {}
    pages = "-".join(p for p in (b.get("first_page"), b.get("last_page")) if p)
    return build_apa(people, year, title, venue, b.get("volume"), b.get("issue"), pages)


def fetch_works(author_id, email, from_year, to_year):
    select = ("id,doi,title,publication_year,cited_by_count,type,topics,"
              "primary_location,abstract_inverted_index,authorships,biblio")
    filt = f"authorships.author.id:{author_id}"
    if from_year:
        filt += f",from_publication_date:{from_year}-01-01"
    if to_year:
        filt += f",to_publication_date:{to_year}-12-31"
    out, cursor = [], "*"
    while cursor:
        url = (f"{API}/works?filter={filt}&select={select}&per-page=200"
               f"&cursor={urllib.parse.quote(cursor)}&mailto={email}")
        d = get(url)
        out.extend(d["results"])
        cursor = d["meta"].get("next_cursor")
        time.sleep(0.3)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--author", action="append", help="OpenAlex author id (repeatable)")
    ap.add_argument("--search", help="resolve an author id by name, then stop")
    ap.add_argument("--out", default="lab_papers.json")
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"))
    ap.add_argument("--from-year", type=int)
    ap.add_argument("--to-year", type=int)
    args = ap.parse_args()
    if not args.email:
        ap.error("--email or LITREVIEW_EMAIL required (OpenAlex polite pool)")
    common.set_user_agent(args.email)
    if args.search:
        print(f"author candidates for {args.search!r} (pass the id to --author):")
        search_authors(args.search, args.email)
        return
    if not args.author:
        ap.error("--author <OpenAlex id> required (use --search to find it)")

    seen, papers = set(), []
    for aid in args.author:
        for w in fetch_works(aid, args.email, args.from_year, args.to_year):
            if w["id"] in seen:
                continue
            seen.add(w["id"])
            doi = (w.get("doi") or "").replace("https://doi.org/", "")
            loc = w.get("primary_location") or {}
            venue = ((loc.get("source") or {}).get("display_name")) or ""
            title = w.get("title") or "(untitled)"
            yr = w.get("publication_year")
            papers.append({
                "openalex": w["id"].split("/")[-1], "doi": doi,
                "link": f"https://doi.org/{doi}" if doi else w["id"],
                "title": title, "year": yr, "venue": venue,
                "apa": apa(w.get("authorships") or [], yr, title, venue, w.get("biblio")),
                "cite_openalex": w.get("cited_by_count"),
                "topic": (w.get("topics") or [{}])[0].get("display_name", ""),
                "topics": [t.get("display_name", "") for t in (w.get("topics") or [])],
                "summary": unabstract(w.get("abstract_inverted_index")) or title,
                "coauthors": [a.get("author", {}).get("display_name", "")
                              for a in (w.get("authorships") or [])],
                "type": w.get("type", ""),
            })

    papers.sort(key=lambda p: (p["year"] or 0))
    for i, p in enumerate(papers, 1):
        p["ref"] = f"L{i}"

    common.dump_json(papers, args.out)

    yrs = [p["year"] for p in papers if p["year"]]
    abs_n = sum(1 for p in papers if p["summary"] and p["summary"] != p["title"])
    print(f"wrote {len(papers)} papers -> {args.out}  "
          f"({min(yrs) if yrs else '?'}-{max(yrs) if yrs else '?'}; abstracts for {abs_n})")


if __name__ == "__main__":
    main()
