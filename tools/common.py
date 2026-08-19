#!/usr/bin/env python3
"""Shared helpers for the literature-review toolkit.

One home for the things every tool needs: the arXiv/CrossRef constants, the
APA name+reference formatter (so the canonical-reference guarantee lives in
exactly one place), DOI parsing, a polite User-Agent, an HTTP GET/POST with
exponential backoff on rate-limits/timeouts, and JSON load/dump that always
reads+writes UTF-8 (ensure_ascii=False) through a context manager.

Tools are run as `python3 tools/<tool>.py`, so `tools/` is on sys.path[0] and a
plain `import common` resolves.
"""
import json
import re
import socket
import time
import urllib.error
import urllib.request

ARXIV_DOI = re.compile(r"10\.48550/arxiv\.(.+)$", re.I)
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
# lowercase nobiliary particles that belong to the surname, not the given name
PARTICLES = {"van", "von", "der", "den", "de", "del", "della", "di", "da", "du",
             "la", "le", "el", "al", "bin", "ibn", "dos", "das", "ten", "ter", "st"}

# JATS/HTML markup CrossRef deposits inside titles (<scp>, <i>, <sub>, <mml:*>).
# The audit's entity check (&amp;) does not see these, so strip them at the source.
MARKUP = re.compile(r"</?[A-Za-z][A-Za-z0-9:._-]*(?:\s[^>]*)?/?>")
# U+2010 HYPHEN and U+2011 NON-BREAKING HYPHEN look identical to an ASCII hyphen
# but break string matching in surnames (Andrews‐Hanna, Kabat‐Zinn). U+2013/U+2014
# are deliberately left alone: en/em dashes are legitimate in titles and page ranges.
UNI_HYPHEN = str.maketrans({"‐": "-", "‑": "-"})

HDRS = {"User-Agent": "litreview-toolkit/1.0"}

# HTTP statuses that mean "try again later", not "does not exist". ONE set, used
# by http()'s backoff and by verify.py's ERROR-vs-NOT-FOUND split, so a 502 from
# CrossRef is never retried in one tool and reported as a clean miss in another.
TRANSIENT_HTTP = {429, 500, 502, 503, 504}


def set_user_agent(email):
    """NCBI/CrossRef/OpenAlex ask for a contact email in the User-Agent."""
    HDRS["User-Agent"] = f"litreview-toolkit/1.0 (mailto:{email})"


# ---- network --------------------------------------------------------------
def http(url, retries=5, timeout=30, data=None, headers=None):
    """GET (or POST if `data` given) with exponential backoff on rate-limits
    (429/503) and timeouts, so a throttled fetch retries instead of failing
    hard. Returns raw bytes; raises on exhaustion."""
    hdrs = headers or HDRS
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in TRANSIENT_HTTP and attempt < retries - 1:
                time.sleep(3 * 2 ** attempt)          # 3, 6, 12, 24s
                continue
            raise
        except (urllib.error.URLError, TimeoutError, socket.timeout):
            if attempt < retries - 1:
                time.sleep(2 * 2 ** attempt)          # 2, 4, 8, 16s
                continue
            raise


def http_json(url, retries=5, timeout=30, data=None, headers=None):
    """http() + json.loads. Same backoff semantics."""
    return json.loads(http(url, retries=retries, timeout=timeout, data=data, headers=headers))


def is_transient(exc):
    """True if `exc` is a rate-limit / server / network failure (the lookup
    could not complete), as opposed to a clean 'no such record' (e.g. 404)."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in TRANSIENT_HTTP
    return isinstance(exc, (urllib.error.URLError, TimeoutError, socket.timeout))


# ---- JSON I/O (always UTF-8, human-readable) ------------------------------
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj, path, indent=2):
    """Write UTF-8 with ensure_ascii=False so canonical names (Graïc, Jürgens)
    stay legible on disk and a hand grep for U+FFFD mojibake still works."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False)


def fold(s):
    """Fold accents and curly apostrophes for matching/sorting: 'Millière' ->
    'milliere'. Used by cite_check (so a citation typed without the accent still
    resolves) and by the reference-list sort (so Millière sorts after Miller,
    not before it because the accented letter was dropped)."""
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().replace("’", "'").translate(UNI_HYPHEN).strip()


def key_field(rows, override=None):
    """The row-key field every tool reports by: an explicit --key, else `ref`
    if the first row has one, else `label`. One rule, so two tools never label
    the same row differently."""
    if override:
        return override
    return "ref" if rows and "ref" in rows[0] else "label"


# ---- the live table -------------------------------------------------------
class CanonicalTableError(RuntimeError):
    """Raised by write_rows() when the file on disk is a canonical rows.json
    (rows stamped `canonical_at` by references.py) and force=False."""


def write_rows(path, rows, force=False):
    """Write rows.json — refusing to overwrite a CANONICAL table.

    After Phase 3f the file carries canonical references, reviewed sentence
    casing and hand fixes; re-running an upstream row-emitter over it is
    destructive. That used to be a sentence in the README. Now it is a check:
    if the existing file has any row stamped `canonical_at`, raise unless the
    caller passes force=True. The canonical-preserving tools (references.py,
    families.py, sentence_case.py) write through dump_json and are unaffected.
    """
    import os
    if not force and os.path.exists(path):
        try:
            old = load_json(path)
        except Exception:
            old = []
        if isinstance(old, list) and any(isinstance(r, dict) and r.get("canonical_at") for r in old):
            raise CanonicalTableError(
                f"{path} is a canonical table (rows stamped canonical_at by references.py); "
                "refusing to overwrite it from an upstream emitter. Edit rows.json directly, "
                "or pass force=True if you really mean to rebuild it.")
    dump_json(rows, path)


def attach_counts(rows, counts, keyf=None):
    """Attach citations.py output to rows in place: counts[key]['openalex'/'s2']
    -> row['cite_openalex'/'cite_s2'] — the exact keys spreadsheet.py reads.
    Returns the number of rows updated. Raises KeyError if `counts` does not
    have citations.py's schema (every project once carried its own copy of this
    with a comment saying 'keep these in lockstep')."""
    keyf = keyf or key_field(rows)
    n = 0
    for r in rows:
        c = counts.get(r.get(keyf))
        if c is None:
            continue
        if "openalex" not in c and "s2" not in c:
            raise KeyError(f"counts for {r.get(keyf)!r} have keys {sorted(c)}; expected "
                           "citations.py's 'openalex' / 's2' — re-run tools/citations.py")
        if c.get("openalex") is not None:
            r["cite_openalex"] = c["openalex"]
        if c.get("s2") is not None:
            r["cite_s2"] = c["s2"]
        n += 1
    return n


# ---- DOI parsing ----------------------------------------------------------
def doi_of(row, lower=False):
    """Bare DOI from row['doi'] or a https://doi.org/... link, else None.
    Pass lower=True when matching against a source that returns lowercase DOIs
    (OpenAlex); leave it False to query CrossRef with the DOI as recorded."""
    d = (row.get("doi") or "").strip()
    if not d:
        m = re.match(r"https?://doi\.org/(10\..+)$", row.get("link") or "", re.I)
        if not m:
            return None
        d = m.group(1)
    d = re.sub(r"(?i)^https?://doi\.org/", "", d)
    return d.lower() if lower else d


def arxiv_id_of(row):
    """Bare arXiv id from an explicit `arxiv` field or an arXiv DOI, else None."""
    if row.get("arxiv"):
        return row["arxiv"].strip()
    m = ARXIV_DOI.match((row.get("doi") or "").strip())
    return m.group(1) if m else None


# ---- APA reference parsing (the ONE grammar for reading an `apa` back) ------
# "Authors (YEAR[a]). Title[.?!] Rest" — the shape build_apa() emits. Every tool
# that reads a reference back (the audit gate, the figure, the family digest,
# cite_check, sentence_case, the duplicate scan) must agree on where the year,
# title and venue are, or they diverge: three of them once required a bare
# (YYYY) while the gate had moved on to accept APA-7's 2025a/2025b suffix, so a
# suffixed row passed the gate and then silently vanished from the figure.
_APA_HEAD = re.compile(r"^(?P<authors>.*?)\s?\((?P<year>\d{4})(?P<suffix>[a-z]?)\)\.?\s*")


def parse_apa(apa):
    """Split a canonical reference into its parts, or None if it has no (YEAR).

    Returns {authors, year (int), suffix, head, title, terminal, rest} where
    `head` is the original text through the year sentence and its whitespace,
    `title` excludes its terminal mark (kept separately in `terminal`, one of
    '.', '?', '!' or ''), and `rest` is everything after — so that
    head + title + terminal + rest == apa. A title ending in ? or ! keeps that
    mark and takes no period (APA-7), which is why the terminal is not always '.'.
    """
    m = _APA_HEAD.match(apa or "")
    if not m:
        return None
    tail = apa[m.end():]
    t = re.search(r"([.?!])(?=\s|$)", tail)
    if t:
        title, terminal, rest = tail[:t.start()], t.group(1), tail[t.end():]
    else:
        title, terminal, rest = tail, "", ""
    return {"authors": m.group("authors"), "year": int(m.group("year")),
            "suffix": m.group("suffix"), "head": apa[:m.end()],
            "title": title, "terminal": terminal, "rest": rest}


def year_of(apa):
    """Publication year of a canonical reference as an int, else None."""
    p = parse_apa(apa)
    return p["year"] if p else None


def lead_surname(apa):
    """First author's family name — the text before the first comma of the
    author list ('van den Heuvel, M. P., & ...' -> 'van den Heuvel')."""
    p = parse_apa(apa)
    authors = p["authors"] if p else (apa or "")
    return authors.split(",")[0].strip()


# ---- APA name + reference formatting --------------------------------------
def initials(given):
    """'Jean-Rémi' -> 'J.-R.'; 'Jack L' -> 'J. L.'; 'L. (Renzo)' -> 'L. R.'

    Parentheses are dropped rather than initialized: sources record a used name
    that way ('L. (Renzo) Huber'), and taking the first character literally
    yields the nonsense initial '(.'
    """
    out = []
    for tok in re.sub(r"[()\[\]]", " ", given or "").replace(".", " ").split():
        out.append("-".join(s[0].upper() + "." for s in tok.split("-") if s))
    return " ".join(out)


def fix_fam(fam):
    """'ANDERSON' -> 'Anderson'; 'zhang' -> 'Zhang'; leave 'de Heer', 'McDermott'.

    Also drops a parenthetical nickname the source folded into the family name
    ('(Bud) Craig' -> 'Craig'), which CrossRef does for authors who publish under
    a familiar name; left in place it produces '(Bud) Craig, A. D.'
    """
    fam = re.sub(r"\s*\([^)]*\)\s*", " ", fam).strip()
    if fam.isupper():
        return " ".join(w.capitalize() for w in fam.split())
    if fam.islower() and " " not in fam:
        return fam.capitalize()
    return fam


def suspect_surnames(apa):
    """Family names in `apa` that may be a mis-split given name — a WARNING, not
    a defect, because it cannot be decided automatically.

    CrossRef routinely folds given-name tokens into the family field ('Thomas Yeo'
    for B. T. T. Yeo) and equally routinely records genuine compound surnames the
    same way ('Lambon Ralph'). Both look like 'Word Word'. Nobiliary particles are
    excluded because split_name already handles them. Everything returned needs a
    human verdict; re-running the formatter reintroduces whatever was wrong.
    """
    p = parse_apa(apa)
    if not p:
        return []
    out = []
    for fam in re.findall(r"(?:^|,\s|…\s)([^,]+?),\s+(?:[A-ZÀ-Ý]\.)", p["authors"]):
        # the last author is joined with "& ", which is not part of the surname
        fam = re.sub(r"^[&…]\s*", "", fam).strip()
        toks = fam.split()
        if len(toks) > 1 and not any(t.lower().strip(".") in PARTICLES for t in toks):
            out.append(fam)
    return sorted(set(out))


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
    """'Bradford' + 'A. Moffat' -> 'Moffat, B. A.'

    Sources sometimes fold a middle initial into the family field (CrossRef
    deposits given='Bradford', family='A. Moffat'). A surname never begins with
    an initial, so moving leading initials into the given name is unambiguous —
    unlike a mis-split full name ('Thomas Yeo'), which only suspect_surnames()
    can flag for a human.
    """
    family = family.strip()
    m = re.match(r"^((?:[A-ZÀ-Ý]\.\s*)+)(\S.*)$", family)
    if m:
        given = f"{given} {m.group(1)}".strip()
        family = m.group(2).strip()
    return f"{fix_fam(family)}, {initials(given)}".rstrip(", ").strip()


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
    """HTML-unescape, strip JATS/HTML markup, and sentence-case a title only if it
    is ENTIRELY uppercase (acronyms inside a mixed-case title are left alone)."""
    import html
    t = MARKUP.sub("", html.unescape((title or "").strip()))
    alpha = [c for c in t if c.isalpha()]
    if alpha and all(c.isupper() for c in alpha):
        t = re.sub(r"(^|[.:]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t.lower())
    return re.sub(r"\s+", " ", t).strip()


def build_apa(people, year, title, journal, vol=None, issue=None, pages=None):
    """Assemble one APA-7 reference from already-formatted `people` strings."""
    import html
    t = norm_title(title).rstrip(".")
    # APA-7: a title already ending in ? or ! keeps that mark and takes no period.
    # Appending one unconditionally produced "...a unified brain theory?."
    s = f"{join_authors(people)} ({year}). {t}" + ("" if t.endswith(("?", "!")) else ".")
    journal = clean_venue(journal)
    if journal:
        tail = journal
        if vol:
            tail += f", {vol}" + (f"({issue})" if issue else "") + (f", {pages}" if pages else "")
        s += f" {tail}."
    s = html.unescape(re.sub(r"\s+", " ", s).strip())
    return MARKUP.sub("", s).translate(UNI_HYPHEN)


# ---- authoritative-source records -------------------------------------------
# references.py (canon), verify.py (existence check) and xref.py (resolve a cited
# DOI) each read the same CrossRef message / arXiv Atom entry. One reading here,
# so the date-field preference and the author handling cannot drift again.
CROSSREF_API = "https://api.crossref.org/works/"
ARXIV_API = "http://export.arxiv.org/api/query"


def crossref_record(msg, fallback_venue=""):
    """Normalize a CrossRef `message` dict.

    -> {title, year (str), authors [(family, given)], people [APA-formatted],
        first_author ('Family I'), journal, volume, issue, pages}. `journal`
    falls back to the preprint server (institution / group-title) and then to
    the caller's venue, cleaned — CrossRef leaves posted-content bare. An
    author-less work still yields a record (people == []); canon rejects it,
    the existence check does not.
    """
    authors = [(a.get("family", ""), a.get("given", "") or "")
               for a in (msg.get("author") or []) if a.get("family")]
    year = ""
    for k in ("published-print", "published-online", "issued"):
        dp = (msg.get(k) or {}).get("date-parts", [[None]])[0]
        if dp and dp[0]:
            year = str(dp[0])
            break
    journal = (msg.get("container-title") or [""])[0]
    if not journal:                          # preprints (posted-content): name the server
        inst = msg.get("institution")
        if isinstance(inst, dict):
            inst = [inst]
        if isinstance(inst, list) and inst:
            journal = inst[0].get("name", "") if isinstance(inst[0], dict) else str(inst[0])
        if not journal:
            gt = msg.get("group-title")
            journal = gt[0] if isinstance(gt, list) and gt else gt if isinstance(gt, str) else ""
        journal = (journal or "").strip() or clean_venue(fallback_venue)
    fam, giv = authors[0] if authors else ("", "")
    return {"title": norm_title((msg.get("title") or [""])[0]), "year": year,
            "authors": authors, "people": [person(f, g) for f, g in authors],
            "first_author": f"{fam} {giv[:1]}".strip(), "journal": journal,
            "volume": msg.get("volume"), "issue": msg.get("issue"), "pages": msg.get("page")}


def crossref_work(doi, fallback_venue=""):
    """Fetch one DOI from CrossRef -> crossref_record(). Raises on a transient
    failure (so callers can tell ERROR from NOT-FOUND); a 404 propagates too —
    callers that want None on a clean miss check is_transient()."""
    import urllib.parse
    msg = http_json(f"{CROSSREF_API}{urllib.parse.quote(doi)}")["message"]
    return crossref_record(msg, fallback_venue)


def norm_arxiv(aid):
    """Normalize an arXiv id for matching: strip whitespace and a version suffix."""
    return re.sub(r"v\d+$", "", (aid or "").strip())


def arxiv_entries(xml_bytes):
    """Parse an arXiv API Atom feed -> [{id, title, year, authors, first_author,
    journal_ref}], skipping the API's synthetic 'Error' entry (an unknown id)."""
    import xml.etree.ElementTree as ET
    out = []
    for e in ET.fromstring(xml_bytes).findall(f"{ATOM}entry"):
        title = (e.findtext(f"{ATOM}title") or "").strip()
        if not title or title == "Error":
            continue
        idtext = e.findtext(f"{ATOM}id") or ""
        m = re.search(r"abs/(.+?)(?:v\d+)?$", idtext)
        authors = [(a.findtext(f"{ATOM}name") or "").strip() for a in e.findall(f"{ATOM}author")]
        out.append({"id": norm_arxiv(m.group(1)) if m else "",
                    "title": " ".join(title.split()),
                    # arXiv 'published' is the submission date, which can precede
                    # the venue year by a year or two — callers tolerate ±1.
                    "year": (e.findtext(f"{ATOM}published") or "")[:4],
                    "authors": authors, "first_author": authors[0] if authors else "",
                    "journal_ref": (e.findtext(f"{ARXIV_NS}journal_ref") or "").strip()})
    return out


def arxiv_fetch(ids):
    """One arXiv API call for many ids (`id_list`) -> {norm_id: entry}. Raises
    on failure; the caller decides whether that is transient."""
    import urllib.parse
    ids = list(dict.fromkeys(norm_arxiv(a) for a in ids if a))
    if not ids:
        return {}
    url = f"{ARXIV_API}?max_results={len(ids)}&id_list={urllib.parse.quote(','.join(ids))}"
    return {e["id"]: e for e in arxiv_entries(http(url))}
