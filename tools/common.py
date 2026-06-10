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
import json, re, socket, time, urllib.error, urllib.request

ARXIV_DOI = re.compile(r"10\.48550/arxiv\.(.+)$", re.I)
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
# lowercase nobiliary particles that belong to the surname, not the given name
PARTICLES = {"van", "von", "der", "den", "de", "del", "della", "di", "da", "du",
             "la", "le", "el", "al", "bin", "ibn", "dos", "das", "ten", "ter", "st"}

HDRS = {"User-Agent": "litreview-toolkit/1.0"}


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
            if e.code in (429, 503) and attempt < retries - 1:
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


# ---- JSON I/O (always UTF-8, human-readable) ------------------------------
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(obj, path, indent=2):
    """Write UTF-8 with ensure_ascii=False so canonical names (Graïc, Jürgens)
    stay legible on disk and a hand grep for U+FFFD mojibake still works."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False)


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


# ---- APA name + reference formatting --------------------------------------
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
    import html
    t = html.unescape((title or "").strip())
    alpha = [c for c in t if c.isalpha()]
    if alpha and all(c.isupper() for c in alpha):
        t = re.sub(r"(^|[.:]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t.lower())
    return t


def build_apa(people, year, title, journal, vol=None, issue=None, pages=None):
    """Assemble one APA-7 reference from already-formatted `people` strings."""
    import html
    s = f"{join_authors(people)} ({year}). {norm_title(title).rstrip('.')}."
    journal = clean_venue(journal)
    if journal:
        tail = journal
        if vol:
            tail += f", {vol}" + (f"({issue})" if issue else "") + (f", {pages}" if pages else "")
        s += f" {tail}."
    return html.unescape(re.sub(r"\s+", " ", s).strip())
