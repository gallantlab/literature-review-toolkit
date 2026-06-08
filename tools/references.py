#!/usr/bin/env python3
"""Canonical reference builder — make EVERY reference perfect, in both modes.

A reference's bibliographic text must never be trusted from a search agent's
memory (topic mode) or OpenAlex's light metadata (lab mode). This rebuilds each
`apa` from the *verified* DOI against the authoritative source — CrossRef for
DOIs, the arXiv API for arXiv ids — through ONE formatter, then audits the result
against a hard quality gate.

Pipeline position:
  topic mode:  search -> verify.py (catch fabrications) -> references.py (canonicalize)
  lab  mode:   lab_corpus.py (OpenAlex) -> references.py (canonicalize)

INPUT: a JSON list of rows. Each row needs a stable key (default "ref" else
"label") and a DOI (from a `doi` field or a `https://doi.org/...` link) and/or an
`arxiv` id. An optional `venue` is used only as a last-resort fallback (lab mode
passes the OpenAlex venue). Rows with no DOI/arxiv keep their existing `apa` and
are flagged `no-source` for manual attention.

  python3 tools/references.py --rows rows.json --out rows.json --email you@x.edu
  python3 tools/references.py --rows rows.json --audit          # report only, exit 1 on any defect

OUTPUT (default): rewrites each row's `apa` (and `link` to the DOI URL), prints a
per-defect audit. `--audit` reports without writing and exits nonzero if any row
is imperfect — wire it into the build so a bad ref can never ship.
"""
import argparse, html, json, os, re, socket, sys, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

ARXIV_DOI = re.compile(r"10\.48550/arxiv\.(.+)$", re.I)
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
HDRS = {"User-Agent": "litreview-toolkit/1.0"}
# lowercase nobiliary particles that belong to the surname, not the given name
PARTICLES = {"van", "von", "der", "den", "de", "del", "della", "di", "da", "du",
             "la", "le", "el", "al", "bin", "ibn", "dos", "das", "ten", "ter", "st"}


def set_email(email):
    HDRS["User-Agent"] = f"litreview-toolkit/1.0 (mailto:{email})"


def http(url, retries=5):
    """GET with exponential backoff on rate-limits (429/503) and timeouts, so a
    throttled fetch retries instead of silently keeping the old (imperfect) ref."""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDRS), timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < retries - 1:
                time.sleep(3 * 2 ** attempt)          # 3, 6, 12, 24s
                continue
            raise
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            if attempt < retries - 1:
                time.sleep(2 * 2 ** attempt)          # 2, 4, 8, 16s
                continue
            raise


# ---- formatting -----------------------------------------------------------
def initials(given):
    """'Jean-Rémi' -> 'J.-R.'; 'Jack L' -> 'J. L.'"""
    out = []
    for tok in (given or "").replace(".", " ").split():
        out.append("-".join(s[0].upper() + "." for s in tok.split("-") if s))
    return " ".join(out)


def fix_fam(fam):
    """'ANDERSON' -> 'Anderson'; 'zhang' -> 'Zhang'; leave 'de Heer', 'McDermott'."""
    if fam.isupper():
        return " ".join(w.capitalize() for w in fam.split())
    if fam.islower() and " " not in fam:
        return fam.capitalize()
    return fam


def split_name(display):
    """Split a 'First M. Last' display name into (family, given), keeping
    nobiliary particles ('van', 'de', ...) with the surname."""
    toks = display.split()
    if not toks:
        return "", ""
    i = len(toks) - 1
    while i - 1 >= 1 and toks[i - 1].lower().strip(".") in PARTICLES:
        i -= 1
    return " ".join(toks[i:]), " ".join(toks[:i])


def person(family, given):
    return f"{fix_fam(family.strip())}, {initials(given)}".rstrip(", ").strip()


def join_authors(people):
    people = [p for p in people if p and p != ","]
    n = len(people)
    if n == 0:
        return "Anon."
    if n == 1:
        return people[0]
    if n <= 20:
        return ", ".join(people[:-1]) + ", & " + people[-1]
    return ", ".join(people[:19]) + ", … " + people[-1]   # APA 7: 19 + ellipsis + last


def clean_venue(v):
    """'bioRxiv (Cold Spring Harbor Laboratory)' -> 'bioRxiv'."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", (v or "").strip())


def norm_title(title):
    """HTML-unescape; sentence-case a title only if it is ENTIRELY uppercase
    (acronyms inside a mixed-case title are left alone)."""
    t = html.unescape((title or "").strip())
    alpha = [c for c in t if c.isalpha()]
    if alpha and all(c.isupper() for c in alpha):
        t = re.sub(r"(^|[.:]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t.lower())
    return t


def build_apa(people, year, title, journal, vol=None, issue=None, pages=None):
    s = f"{join_authors(people)} ({year}). {norm_title(title).rstrip('.')}."
    journal = clean_venue(journal)
    if journal:
        tail = journal
        if vol:
            tail += f", {vol}" + (f"({issue})" if issue else "") + (f", {pages}" if pages else "")
        s += f" {tail}."
    return html.unescape(re.sub(r"\s+", " ", s).strip())


# ---- authoritative sources ------------------------------------------------
def crossref(doi, fallback_venue=""):
    m = json.loads(http(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"))["message"]
    people = [person(a.get("family", ""), a.get("given", ""))
              for a in (m.get("author") or []) if a.get("family")]
    if not people:
        return None
    year = ""
    for k in ("published-print", "published-online", "issued"):
        dp = (m.get(k) or {}).get("date-parts", [[None]])[0]
        if dp and dp[0]:
            year = dp[0]
            break
    journal = (m.get("container-title") or [""])[0]
    if not journal:                          # preprints (posted-content): name the server
        inst = m.get("institution")
        if isinstance(inst, dict):
            inst = [inst]
        if isinstance(inst, list) and inst:
            journal = inst[0].get("name", "") if isinstance(inst[0], dict) else str(inst[0])
        if not journal:
            gt = m.get("group-title")
            journal = gt[0] if isinstance(gt, list) and gt else gt if isinstance(gt, str) else ""
        journal = (journal or "").strip() or clean_venue(fallback_venue)
    apa = build_apa(people, year, (m.get("title") or [""])[0], journal,
                    m.get("volume"), m.get("issue"), m.get("page"))
    return {"apa": apa, "venue": journal, "source": "crossref"}


def arxiv(aid, fallback_venue=""):
    root = ET.fromstring(http(f"http://export.arxiv.org/api/query?id_list={urllib.parse.quote(aid)}"))
    e = root.find(f"{ATOM}entry")
    if e is None or e.find(f"{ATOM}title") is None:
        return None
    people = [person(*split_name(a.find(f"{ATOM}name").text)) for a in e.findall(f"{ATOM}author")]
    year = (e.findtext(f"{ATOM}published") or "")[:4]
    # a published paper often records its venue in arXiv's journal_ref
    jref = e.findtext(f"{ARXIV_NS}journal_ref")
    journal = (jref or "").strip() or clean_venue(fallback_venue) or "arXiv"
    apa = build_apa(people, year, e.findtext(f"{ATOM}title"), journal)
    return {"apa": apa, "venue": journal, "source": "arxiv"}


def doi_of(row):
    d = (row.get("doi") or "").strip()
    if d:
        return d.replace("https://doi.org/", "")
    m = re.match(r"https?://doi\.org/(10\..+)$", row.get("link", "") or "", re.I)
    return m.group(1) if m else None


def canonical(row):
    """Return {apa, link, source, ...} rebuilt from the authoritative source, or
    None if there is no DOI/arxiv to rebuild from."""
    doi = doi_of(row)
    aid = (row.get("arxiv") or "").strip()
    am = ARXIV_DOI.match(doi or "")
    if am:
        aid = aid or am.group(1)
    fv = row.get("venue", "")
    try:
        if aid:
            r = arxiv(aid, fv)
        elif doi:
            r = crossref(doi, fv)
        else:
            return None
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "source": "error"}
    if r and doi:
        r["link"] = f"https://doi.org/{doi}"
    return r


# ---- quality gate ---------------------------------------------------------
def audit(apa, has_source):
    """Return (defects, notes). `defects` are real formatting errors that must
    fail the build; `notes` are non-fatal (a well-formed book/report with no DOI
    can't be auto-rebuilt, but is still a valid reference)."""
    defects, notes = [], []
    if not has_source:
        notes.append("no DOI/arxiv — manual ref (verify by hand)")
    if not re.search(r"\(\d{4}\)", apa):
        defects.append("no-year")
    if apa.startswith("Anon.") or re.match(r"^\(\d{4}\)", apa):
        defects.append("no-authors")
    if " et al" in apa:
        defects.append("et-al (should list all authors)")
    if "&amp;" in apa or "&#x" in apa or "&lt;" in apa or "&gt;" in apa:
        defects.append("html-entity")
    if re.search(r"\.\s+[A-Z]\.\s*$", apa):
        defects.append("single-letter venue (truncated)")
    # Catch an uppercase TITLE (norm_title misses titles that are only MOSTLY
    # caps). Scan the title sentence ONLY — author initials ("R. B. H.") and
    # venue acronyms ("PLOS ONE") legitimately have caps and must be excluded.
    m = re.search(r"\(\d{4}\)\.\s+(.+)", apa)
    title = m.group(1).split(". ", 1)[0] if m else ""
    run = mx = 0
    for t in re.findall(r"[A-Za-z][A-Za-z'/-]*", title):   # no '.', so initials aren't tokens
        run = run + 1 if (t.isupper() and len(t) >= 2) else 0
        mx = max(mx, run)
    if mx >= 3:
        defects.append(f"uppercase-title run ({mx} consecutive caps words)")
    # a DOI-backed ref should name a venue (text after the title sentence)
    body = apa.split(").", 1)[1].strip() if ")." in apa else ""
    if has_source and body and "." in body and not body.rsplit(".", 2)[-2].strip():
        defects.append("empty venue")
    return defects, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", help="write rebuilt rows here (default: in place unless --audit)")
    ap.add_argument("--key", default=None, help="row key field (default: ref, else label)")
    ap.add_argument("--audit", action="store_true", help="report only; exit 1 if any ref is imperfect")
    ap.add_argument("--email", default=os.environ.get("LITREVIEW_EMAIL"))
    ap.add_argument("--sleep", type=float, default=0.25)
    args = ap.parse_args()
    if not args.email:
        ap.error("--email or LITREVIEW_EMAIL required (CrossRef/arXiv polite pool)")
    set_email(args.email)

    rows = json.load(open(args.rows))
    keyf = args.key or ("ref" if rows and "ref" in rows[0] else "label")
    defects, notes, rebuilt = {}, {}, 0
    for r in rows:
        k = r.get(keyf, "?")
        if not args.audit:
            res = canonical(r)
            if res and res.get("apa"):
                r["apa"] = res["apa"]
                if res.get("link"):
                    r["link"] = res["link"]
                rebuilt += 1
            elif res and res.get("error"):
                print(f"  [fetch-fail] {k}: {res['error']}", file=sys.stderr)
            time.sleep(args.sleep)
        d, n = audit(r.get("apa", ""), bool(doi_of(r) or r.get("arxiv")))
        if d:
            defects[k] = d
        if n:
            notes[k] = n

    if not args.audit:
        json.dump(rows, open(args.out or args.rows, "w"), indent=2, ensure_ascii=False)

    print(f"{len(rows)} refs | rebuilt {rebuilt} | {len(defects)} defects | {len(notes)} manual (no-DOI)")
    for k, n in notes.items():
        print(f"  · {k}: {'; '.join(n)}")
    for k, d in defects.items():
        print(f"  ✗ {k}: {'; '.join(d)}")
    if defects:
        sys.exit(1)
    print("✓ all references perfect (no formatting defects)")


if __name__ == "__main__":
    main()
