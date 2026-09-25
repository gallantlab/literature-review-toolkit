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
import gzip
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import zlib

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

# Ask for a compressed body. CrossRef work records carry full reference lists
# and run to megabytes; an uncompressed chunked response of that size is the
# one that arrives truncated (`IncompleteRead(... more expected)`), which is
# transient-by-class and so retries until the run stalls. gzip cuts the
# payload several-fold and the truncations with it.
HDRS = {"User-Agent": "litreview-toolkit/1.0", "Accept-Encoding": "gzip, deflate"}

# HTTP statuses that mean "try again later", not "does not exist". ONE set, used
# by http()'s backoff and by verify.py's ERROR-vs-NOT-FOUND split, so a 502 from
# CrossRef is never retried in one tool and reported as a clean miss in another.
TRANSIENT_HTTP = {429, 500, 502, 503, 504}
# Connection-level failures that mean "try again", not "no such record": a
# server closing the socket mid-response (RemoteDisconnected, IncompleteRead —
# both http.client.HTTPException, NOT URLError) or resetting it (ConnectionError).
TRANSIENT_NETWORK = (urllib.error.URLError, TimeoutError, socket.timeout,
                     http.client.HTTPException, ConnectionError)


def set_user_agent(email):
    """NCBI/CrossRef/OpenAlex ask for a contact email in the User-Agent."""
    HDRS["User-Agent"] = f"litreview-toolkit/1.0 (mailto:{email})"


# ---- network --------------------------------------------------------------
def decompress(body, encoding):
    """Undo Content-Encoding. urllib does NOT do this for you — asking for gzip
    without decoding the reply yields binary garbage, so the two belong together.

    An unknown encoding, or a body that does not actually match the encoding the
    server declared, is passed through unchanged rather than raised on: the
    caller's json.loads gives a far more useful error than a decompression
    traceback five frames down, and a lying server should not take a 500-row run
    with it."""
    enc = (encoding or "").strip().lower()
    try:
        if enc == "gzip":
            return gzip.decompress(body)
        if enc == "deflate":
            try:
                return zlib.decompress(body)
            except zlib.error:            # raw deflate, no zlib wrapper
                return zlib.decompress(body, -zlib.MAX_WBITS)
    except (OSError, zlib.error, EOFError):
        return body
    return body


def curl_get(url, headers, timeout):
    """GET via the curl binary. Bytes on success; raises on any failure.

    A fallback, not a preference. Some hosts close the connection on urllib
    instantly and deterministically for particular URLs while curl fetches the
    same URL without trouble — an HTTP-stack/proxy interaction, distinct from
    rate limiting (random) and from truncation (same byte count each time). On
    one xref pass 71 of 536 reference-list fetches failed this way and every one
    of them succeeded through curl. `--compressed` matters here for the same
    reason the Accept-Encoding header does above."""
    exe = shutil.which("curl")
    if not exe:
        raise RuntimeError("curl not available for fallback")
    cmd = [exe, "-sS", "--compressed", "--fail", "--max-time", str(int(timeout))]
    for k, v in (headers or {}).items():
        if k.lower() == "accept-encoding":
            continue                      # --compressed sets and decodes it
        cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)
    p = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    if p.returncode != 0:
        raise OSError(f"curl exit {p.returncode}: {p.stderr.decode('utf-8', 'replace')[:120]}")
    return p.stdout


def retry_after(err, cap=120.0):
    """Seconds a 429/503 asks us to wait (its Retry-After header), capped, else
    None. The header is either delay-seconds or an HTTP-date; honoring it beats
    a fixed backoff that is either too short (and burns every retry inside the
    throttle window) or too long."""
    import email.utils
    val = ((getattr(err, "headers", None) or {}).get("Retry-After") or "").strip()
    if not val:
        return None
    try:
        secs = float(val)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(val)
        except (TypeError, ValueError):
            return None
        secs = when.timestamp() - time.time()
    return min(max(secs, 0.0), cap)


# Requests actually sent by http(). Loops compare it before/after a row so they
# pause only after a row that went to the network -- a row answered by a batch
# prefetch needs no courtesy delay.
_REQUESTS = 0


def request_count():
    """How many HTTP attempts http() has made in this process."""
    return _REQUESTS


def http(url, retries=5, timeout=30, data=None, headers=None):
    """GET (or POST if `data` given) with backoff on rate-limits (429/503) and
    timeouts, so a throttled fetch retries instead of failing hard. A server's
    Retry-After is honored; otherwise the wait doubles from 3 s. Requests a
    gzip/deflate body and decodes it. Returns raw bytes; raises on exhaustion."""
    global _REQUESTS
    hdrs = headers or HDRS
    tried_curl = False
    for attempt in range(retries):
        try:
            _REQUESTS += 1
            req = urllib.request.Request(url, data=data, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return decompress(r.read(), r.headers.get("Content-Encoding", ""))
        except urllib.error.HTTPError as e:
            if e.code in TRANSIENT_HTTP and attempt < retries - 1:
                wait = retry_after(e)
                time.sleep(wait if wait is not None else 3 * 2 ** attempt)   # 3, 6, 12, 24s
                continue
            raise
        except TRANSIENT_NETWORK:
            # Try curl at the FIRST network failure, before any backoff. A
            # connection the host closes on us is usually a stack/proxy
            # incompatibility rather than load, and urllib will reproduce it
            # exactly however long we wait — so sleeping 2+4+8+16s first only
            # makes a recoverable fetch slow. curl gets these on the first try.
            # GETs only: a POST body is not worth re-sending through a second
            # stack. If curl fails too, fall into the normal backoff, which is
            # the right response to genuine load.
            if data is None and not tried_curl:
                tried_curl = True
                try:
                    return curl_get(url, hdrs, timeout)
                except Exception:
                    pass
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
    return isinstance(exc, TRANSIENT_NETWORK)


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
    if not force and os.path.exists(path):
        try:
            old = load_json(path)
        except Exception as e:
            # An unreadable table must not disarm the guard: a half-written or
            # permission-broken rows.json is exactly when the canonical stamps
            # can't be seen, and overwriting destroys whatever is recoverable.
            raise CanonicalTableError(
                f"{path} exists but could not be read ({e}); refusing to overwrite it "
                "blind. Inspect/restore the file, or pass force=True to rebuild it.")
        if isinstance(old, list) and any(isinstance(r, dict) and r.get("canonical_at") for r in old):
            raise CanonicalTableError(
                f"{path} is a canonical table (rows stamped canonical_at by references.py); "
                "refusing to overwrite it from an upstream emitter. Edit rows.json directly, "
                "or pass force=True if you really mean to rebuild it.")
    dump_json(rows, path)


# ---- reference gates: stamps a check writes onto the row it checked ----------
# A table is GATED (the gates can fail it) once any row carries a verify stamp or
# was canonicalized on/after this date; older corpora are legacy and only warned.
GATES_SINCE = "2026-09-26"


def _bare_doi(d):
    return re.sub(r"(?i)^https?://(dx\.)?doi\.org/", "", (d or "").strip()).lower()


def ids_of(row):
    """(doi, arxiv) a row is identified by, normalized for comparing with a stamp."""
    return _bare_doi(doi_of(row) or ""), norm_arxiv(arxiv_id_of(row) or "").lower()


def stamp_ids(stamp):
    """(doi, arxiv) recorded in a verify stamp or override, normalized the same way."""
    return _bare_doi(stamp.get("doi") or ""), norm_arxiv(stamp.get("arxiv") or "").lower()


def verified_ok(row):
    """True when the row's verify stamp is for its CURRENT ids and is OK, or a
    non-OK verdict was overridden with a reason for those same ids."""
    st = row.get("verified")
    if not isinstance(st, dict) or stamp_ids(st) != ids_of(row):
        return False
    if st.get("verdict") == "OK":
        return True
    ov = row.get("verify_override")
    return (isinstance(ov, dict) and bool(str(ov.get("reason") or "").strip())
            and stamp_ids(ov) == ids_of(row))


def is_gated(rows):
    """True for a table built since the reference gates (see GATES_SINCE)."""
    return any(isinstance(r, dict) and (r.get("verified") or str(r.get("canonical_at") or "") >= GATES_SINCE)
               for r in rows)


def summary_sha(text):
    """Short hash of a summary, so a check recorded for one text lapses on an edit."""
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()[:16]


def load_optional_json(path, default):
    """load_json, or `default` when the file does not exist."""
    return load_json(path) if path and os.path.exists(path) else default


def _title_words(t):
    t = MARKUP.sub(" ", t or "").lower()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", t).split())


_TITLE_STOP = frozenset("a an the of in on and for to with by from at as is are be its via into".split())


def title_score(a, b):
    """Similarity of two titles in [0, 1], or None if either is missing: the
    better of character similarity and the share of the shorter title's content
    words found in the longer (so a dropped subtitle still scores high)."""
    import difflib
    a, b = _title_words(a), _title_words(b)
    if not a or not b:
        return None
    ta = [w for w in a.split() if w not in _TITLE_STOP]
    tb = [w for w in b.split() if w not in _TITLE_STOP]
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    contained = sum(w in set(long_) for w in short) / len(short) if short else 0.0
    return max(difflib.SequenceMatcher(None, a, b).ratio(), contained)


def attach_counts(rows, counts, keyf=None):
    """Attach citations.py output to rows in place: counts[key]['openalex'/'s2'/
    's2_influential'] -> row['cite_openalex'/'cite_s2'/'cite_s2_influential'] —
    the first two are the exact keys spreadsheet.py reads; the influential count
    rides along for pages/figures that want it.
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
        if c.get("s2_influential") is not None:
            r["cite_s2_influential"] = c["s2_influential"]
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
# APA-7 also dates web posts, reports and magazine issues more finely --
# "(2022, June 5)", "(1942, March)", "(2021, June 10-12)" -- and those must
# parse too, or a correctly cited blog post fails the gate as "no-year".
_APA_HEAD = re.compile(r"^(?P<authors>.*?)\s?\((?P<year>\d{4})(?P<suffix>[a-z]?)"
                       r"(?:, [A-Z][a-z]+(?: \d{1,2}(?:[-–]\d{1,2})?)?)?\)\.?\s*")


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


# Model-organism genera. These are proper nouns in ANY corpus, and canon's
# ALL-CAPS sentence-caser would otherwise emit "caenorhabditis elegans" (seen on
# Brenner 1974, whose Genetics deposit is entirely uppercase).
GENERA = frozenset("""Aplysia Apis Acheta Anas Apteronotus Bombyx Bufo Caenorhabditis Calliphora
Cataglyphis Chlorocebus Columba Danio Dixippus Drosophila Eigenmannia Gallus Gryllus Gymnotus
Helisoma Hirundo Hyla Limulus Locusta Lymnaea Macaca Manduca Melospiza Musca Myotis Nasonia
Ormia Pan Periplaneta Physalaemus Pteronotus Rana Rhinolophus Saimiri Schistocerca Serinus
Sternopygus Sturnus Taeniopygia Teleogryllus Tritonia Tyto Xenopus Zonotrichia""".split())


def restore_genera(text):
    """Re-capitalize a genus name that a lowercasing pass flattened."""
    if not text:
        return text
    return re.sub(r"\b([a-z][a-z]+)\b",
                  lambda m: m.group(1).capitalize()
                  if m.group(1).capitalize() in GENERA else m.group(1), text)


def norm_title(title):
    """HTML-unescape, strip JATS/HTML markup, and sentence-case a title only if it
    is ENTIRELY uppercase (acronyms inside a mixed-case title are left alone)."""
    import html
    t = MARKUP.sub("", html.unescape((title or "").strip()))
    alpha = [c for c in t if c.isalpha()]
    if alpha and all(c.isupper() for c in alpha):
        t = re.sub(r"(^|[.:]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t.lower())
        t = restore_genera(t)
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


def build_chapter_apa(people, year, title, book, pages=None, publisher=None):
    """APA-7 chapter in an edited book: `... Title. In Book (pp. x-y). Publisher.`
    CrossRef deposits no editors for most chapters, so none are printed."""
    import html
    t = norm_title(title).rstrip(".")
    s = f"{join_authors(people)} ({year}). {t}" + ("" if t.endswith(("?", "!")) else ".")
    s += f" In {clean_venue(book)}" + (f" (pp. {pages})" if pages else "") + "."
    if publisher:
        s += f" {publisher.strip().rstrip('.')}."
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
        first_author ('Family I'), journal, volume, issue, pages, book, publisher}.
    `book` is set only for a book chapter (see build_chapter_apa). `journal`
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
    containers = msg.get("container-title") or [""]
    journal = containers[0]
    # A chapter deposits [series, book] (or just [book]): the book is the LAST
    # entry, and it -- not the series -- is what APA-7 prints after "In".
    book = containers[-1] if msg.get("type") == "book-chapter" else ""
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
    title = norm_title((msg.get("title") or [""])[0])
    # CrossRef deposits a series part / subtitle separately ("I. Responses to
    # speech"); dropping it made Part I and Part II papers identical. APA joins
    # them with a colon. Some publishers repeat the subtitle inside the title
    # field itself — skip it then rather than print it twice.
    sub = norm_title((msg.get("subtitle") or [""])[0])
    if sub and sub.lower() not in title.lower():
        sub = sub[:1].upper() + sub[1:]
        title = f"{title.rstrip(':')}: {sub}"
    return {"title": title, "year": year,
            "authors": authors, "people": [person(f, g) for f, g in authors],
            "first_author": f"{fam} {giv[:1]}".strip(), "journal": journal,
            "volume": msg.get("volume"), "issue": msg.get("issue"), "pages": msg.get("page"),
            "book": book, "publisher": msg.get("publisher") or ""}


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


def arxiv_batch(ids, chunk=50, sleep=3.0):
    """Resolve many arXiv ids in a few `id_list` calls -> (entries, errored).

    `entries[norm_id]` is the arxiv_entries() record; an id absent from a batch
    that COMPLETED is a genuine miss; `errored` holds the ids whose batch could
    not complete (rate-limit / network), which callers must report as ERROR or
    fetch-fail and retry, never as "no such paper". arXiv asks for ~3 s between
    requests and bans a per-paper loop, so this is the only way the toolkit
    reads arXiv in bulk (verify.py and references.py both call it)."""
    entries, errored = {}, set()
    uniq = list(dict.fromkeys(norm_arxiv(a) for a in ids if a))
    for i in range(0, len(uniq), chunk):
        batch = uniq[i:i + chunk]
        try:
            got = arxiv_fetch(batch)
        except Exception:
            errored.update(batch)
        else:
            entries.update({a: got[a] for a in batch if a in got})
        if i + chunk < len(uniq):
            time.sleep(sleep)
    return entries, errored
