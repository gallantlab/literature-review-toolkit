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
import sys
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
    reason the Accept-Encoding header does above.

    Redirects are followed (`-L`, to https only), and the final HTTP status is
    captured (`-w`): without them a 301 page came back as a "successful" body,
    and a whole arXiv batch read as garbage. A non-2xx final status raises."""
    exe = shutil.which("curl")
    if not exe:
        raise RuntimeError("curl not available for fallback")
    cmd = [exe, "-sS", "--compressed", "--fail", "-L", "--proto-redir", "=https",
           "--max-time", str(int(timeout)), "-w", "\n%{http_code}"]
    for k, v in (headers or {}).items():
        if k.lower() == "accept-encoding":
            continue                      # --compressed sets and decodes it
        cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)
    p = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    if p.returncode != 0:
        raise OSError(f"curl exit {p.returncode}: {p.stderr.decode('utf-8', 'replace')[:120]}")
    body, _, code = p.stdout.rpartition(b"\n")
    code = code.strip().decode("ascii", "replace")
    # file:// (used offline) has no HTTP status and reports 000; http(s) must be 2xx
    if url.lower().startswith(("http://", "https://")) and not code.startswith("2"):
        raise OSError(f"curl: final HTTP status {code or '?'} for {url}")
    return body


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


def write_run_sidecar(out, incomplete, asof, indent=2, tool=None, n_papers=None):
    """Write <out>.run.json = {"complete", "incomplete", "at", "tool",
    "n_papers"}, shared by xref.py and forward.py so their two copies of this
    snippet cannot drift. candidates.py --add reads it beside the file it is
    adding, to record whether the run that produced `out` finished
    (`complete`), refuse it under the wrong --source (`tool`: "xref" or
    "forward"), and record how many sourced papers the run read (`n_papers`),
    which the audit compares with the table's; `incomplete` is the refs/slugs
    still unresolved, and `asof` the date to stamp. `tool`/`n_papers` are
    written only when given. `indent` matches dump_json's own default; xref.py
    passes 1, matching its pre-refactor indentation for `out` itself."""
    rec = {"complete": not incomplete, "incomplete": list(incomplete), "at": asof}
    if tool is not None:
        rec["tool"] = tool
    if n_papers is not None:
        rec["n_papers"] = n_papers
    dump_json(rec, f"{out}.run.json", indent=indent)


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


def save_rows(path, rows, loaded_mtime):
    """Write rows back to the rows.json they were loaded from — refusing if the
    file changed since (another tool wrote it: a handcheck --ingest landing while
    verify was still running once lost one of the two writes). Pass the
    os.path.getmtime(path) taken right after loading; None skips the check (a
    different output path)."""
    if loaded_mtime is not None and os.path.exists(path) and os.path.getmtime(path) != loaded_mtime:
        raise RuntimeError(f"{path}: rows.json changed since it was loaded; re-run")
    dump_json(rows, path)


# ---- reference gates: stamps a check writes onto the row it checked ----------
# A table is GATED (the gates can fail it) once any row carries a verify stamp, or
# was built (`built_at`, stamped by every row emitter: merge_lanes.py, the rows
# template, lab_corpus.py) or canonicalized (`canonical_at`) on/after this date.
# The build stamp is what gates a new table whose verify step was skipped; a row
# with none of the three is from an older corpus, which is legacy and only warned.
GATES_SINCE = "2026-09-25"


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
    return any(isinstance(r, dict) and (r.get("verified")
                                        or str(r.get("built_at") or "") >= GATES_SINCE
                                        or str(r.get("canonical_at") or "") >= GATES_SINCE)
               for r in rows)


def summary_sha(text):
    """Short hash of a summary, so a check recorded for one text lapses on an edit."""
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()[:16]


def apa_sha(apa):
    """Short hash of a reference, casefolded and whitespace-collapsed, so a hand
    check or an acknowledgment recorded for one apa lapses when its text changes."""
    return summary_sha(" ".join((apa or "").casefold().split()))


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


TITLE_MATCH = 0.9


def title_match(a, b):
    """True when two titles name the same work: character similarity of the
    normalized titles >= TITLE_MATCH, OR each title's content words are >=
    TITLE_MATCH contained in the other. Symmetric on purpose, unlike
    title_score: "Deep learning" is wholly contained in "Deep learning in
    neural networks: An overview", and accepting that marks a lost paper as
    found. Used wherever a title alone decides identity (merge_lanes deferrals,
    handcheck DOI candidates)."""
    import difflib
    a, b = _title_words(a), _title_words(b)
    if not a or not b:
        return False
    if difflib.SequenceMatcher(None, a, b).ratio() >= TITLE_MATCH:
        return True
    ta = [w for w in a.split() if w not in _TITLE_STOP]
    tb = [w for w in b.split() if w not in _TITLE_STOP]
    if not ta or not tb:
        return False
    sa, sb = set(ta), set(tb)
    return (sum(w in sb for w in ta) / len(ta) >= TITLE_MATCH
            and sum(w in sa for w in tb) / len(tb) >= TITLE_MATCH)


def _main_title(t):
    """The text before the first ':' / ' - ' / '?' subtitle break, normalized
    (whichever break comes first) — the part of a title an agent keeps when
    it drops a subtitle."""
    t = t or ""
    idx = len(t)
    for sep in (":", " - ", "?"):
        i = t.find(sep)
        if i != -1 and i < idx:
            idx = i
    return _title_words(t[:idx])


MIN_MAIN_TITLE_WORDS = 3


def _content_words(words):
    """`words` (already space-joined and normalized) with _TITLE_STOP words dropped."""
    return [w for w in words.split() if w not in _TITLE_STOP]


def title_agrees(claim, record):
    """Similarity of a claimed title and a found record's title, in [0, 1], or
    None if either is missing.

    Unlike title_score, this refuses a short claim that merely happens to be
    CONTAINED in an unrelated longer record title — title_score's one-way
    containment let "Deep learning" match "Deep learning in neural networks:
    An overview" (a different paper), because it only checked the short
    title's words against the long one. title_agrees instead returns:
    - 1.0 when one title equals the other's main title (see _main_title) AND
      that main title has at least MIN_MAIN_TITLE_WORDS content words
      (_TITLE_STOP words excluded) — exactly the case of an agent dropping a
      subtitle, which is what the one-way check was built to tolerate. The
      word-count floor exists because a main title of only 1-2 content words
      is too easily a coincidence: "Deep learning" is wholly the main title of
      "Deep learning - a survey of unrelated gardening techniques", an
      unrelated paper, but "The free-energy principle" (3 content words:
      free, energy, principle — a hyphen splits into two words like any other
      non-alnum character, so "free-energy" counts as two) is specific enough
      to trust;
    - otherwise max(character-similarity ratio, two-way containment), where
      two-way containment is the MIN of each title's content words found in
      the other, so a short title inside a longer, unrelated one no longer
      passes on one direction alone.

    Calibrated on 2,473 OK verdicts from five corpora: at threshold 0.5, 2
    past OK verdicts fall below it (2026-09-26). One is a claim that
    paraphrased a title rather than quoting it (already below 0.5 before this
    function existed). The other is a genuinely dropped subtitle whose main
    title is only 2 content words -- collateral from the >=3-word floor added
    2026-09-25 to close the "Deep learning" vs. an unrelated "Deep learning -
    ..." false pass; the owner's ruling was to accept that false alarm rather
    than risk another false pass on a short, coincidental main title. See
    verify.TITLE_MIN.
    """
    import difflib
    a, b = _title_words(claim), _title_words(record)
    if not a or not b:
        return None
    ta, tb = _content_words(a), _content_words(b)
    ma, mb = _main_title(claim), _main_title(record)
    if ma and ma == b and len(_content_words(ma)) >= MIN_MAIN_TITLE_WORDS:
        return 1.0
    if mb and mb == a and len(_content_words(mb)) >= MIN_MAIN_TITLE_WORDS:
        return 1.0
    contained = (min(sum(w in set(tb) for w in ta) / len(ta),
                      sum(w in set(ta) for w in tb) / len(tb))
                 if ta and tb else 0.0)
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


# ` (Version v2.1)` and/or ` [Computer software]` ending the title sentence
_DESCRIPTOR = r"(?: \(Version [^()]*\))?(?: \[[^\[\]]+\])?"
_APA_DESCRIPTOR = re.compile(_DESCRIPTOR + "$")          # at the end of the title sentence
_APA_DESCRIPTOR_LEAD = re.compile(_DESCRIPTOR + r"(?=\.)")   # at the start of the tail


def parse_apa(apa):
    """Split a canonical reference into its parts, or None if it has no (YEAR).

    Returns {authors, year (int), suffix, head, title, terminal, rest} where
    `head` is the original text through the year sentence and its whitespace,
    `title` excludes its terminal mark (kept separately in `terminal`, one of
    '.', '?', '!' or ''), and `rest` is everything after — so that
    head + title + terminal + rest == apa. A title ending in ? or ! keeps that
    mark and takes no period (APA-7), which is why the terminal is not always '.'.

    A deposit's ` (Version …)` and/or ` […]` descriptor (build_datacite_apa:
    "Spike sorter (Version v2.1) [Computer software]. Zenodo.") belongs to the
    tail, not the title: `title` is then "Spike sorter", `terminal` is '' and
    `rest` starts with the descriptor, which is also returned alone as
    `descriptor` ('' when there is none) so a caller can find the venue after it.
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
    d = _APA_DESCRIPTOR.search(title) if terminal == "." else None
    if d and d.group(0) and d.start() > 0:
        title, terminal, rest = title[:d.start()], "", d.group(0) + terminal + rest
    d = _APA_DESCRIPTOR_LEAD.match(rest)
    descriptor = d.group(0) if d else ""
    return {"authors": m.group("authors"), "year": int(m.group("year")),
            "suffix": m.group("suffix"), "head": apa[:m.end()],
            "title": title, "terminal": terminal, "rest": rest, "descriptor": descriptor}


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


def apa_families(apa):
    """The family name of every author in `apa` that is followed by initials
    ('Smith, J. A., & O, K.' -> Smith, O), in order; [] if it does not parse."""
    p = parse_apa(apa)
    if not p:
        return []
    # the last author is joined with "& " (or "… " past 20), which is not part of the surname
    return [re.sub(r"^[&…]\s*", "", f).strip()
            for f in re.findall(r"(?:^|,\s|…\s)([^,]+?),\s+(?:[A-ZÀ-Ý]\.)", p["authors"])]


def suspect_surnames(apa):
    """Family names in `apa` that may be a mis-split given name — a WARNING, not
    a defect, because it cannot be decided automatically.

    CrossRef routinely folds given-name tokens into the family field ('Thomas Yeo'
    for B. T. T. Yeo) and equally routinely records genuine compound surnames the
    same way ('Lambon Ralph'). Both look like 'Word Word'. Nobiliary particles are
    excluded because split_name already handles them. Everything returned needs a
    human verdict; re-running the formatter reintroduces whatever was wrong.
    """
    out = []
    for fam in apa_families(apa):
        toks = fam.split()
        if len(toks) > 1 and not any(t.lower().strip(".") in PARTICLES for t in toks):
            out.append(fam)
    return sorted(set(out))


def single_letter_surnames(apa):
    """Family names in `apa` that are one letter ("S, D. J."): usually a name
    deposited family-first with trailing initials ("Doad J S") and split on its
    last token. A WARNING, not a defect: real one-letter surnames ("O") exist."""
    return sorted({f for f in apa_families(apa) if len(f.strip(".")) == 1})


GROUP_WORDS = {"collaboration", "consortium", "team", "group", "project", "institute", "initiative",
               "network", "committee", "society", "association", "council", "organization",
               "organisation", "laboratory", "center", "centre", "foundation"}


def is_group(name):
    """True for a group author: a name with a group word in it ("ATLAS
    Collaboration", "Allen Institute for Brain Science", "MICrONS Consortium") or
    opening with "The". A group has no surname to split off; it compares whole."""
    words = re.findall(r"[^\W\d_]+", name or "")
    return bool(words) and (words[0].lower() == "the" and len(words) > 1
                            or any(w.lower() in GROUP_WORDS for w in words))


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


# A resourceTypeGeneral that gets a bracket descriptor in the APA-7 reference;
# anything else (Text, Collection, ...) prints no bracket at all.
DATACITE_DESCRIPTORS = {"Dataset": "Data set", "Software": "Computer software", "Preprint": "Preprint"}


def build_datacite_apa(people, year, title, version=None, resource_type="", publisher=""):
    """APA-7 for a DataCite-registered deposit (Zenodo/figshare/OSF/Dryad software,
    data set or preprint): `Authors (Year). Title (Version v) [Descriptor].
    Publisher.` `(Version …)` is omitted when `version` is falsy; the bracket
    descriptor is 'Data set', 'Computer software' or 'Preprint' for those three
    resourceTypeGeneral values and omitted for any other."""
    import html
    t = norm_title(title).rstrip(".")
    s = f"{join_authors(people)} ({year}). {t}"
    if version:
        s += f" (Version {version})"
    descriptor = DATACITE_DESCRIPTORS.get(resource_type)
    if descriptor:
        s += f" [{descriptor}]"
    s += "."
    publisher = clean_venue(publisher)
    if publisher:
        s += f" {publisher}."
    s = html.unescape(re.sub(r"\s+", " ", s).strip())
    return MARKUP.sub("", s).translate(UNI_HYPHEN)


# ---- authoritative-source records -------------------------------------------
# references.py (canon), verify.py (existence check) and xref.py (resolve a cited
# DOI) each read the same CrossRef message / arXiv Atom entry. One reading here,
# so the date-field preference and the author handling cannot drift again.
CROSSREF_API = "https://api.crossref.org/works/"
ARXIV_API = "https://export.arxiv.org/api/query"   # http:// now answers with a 301
# Zenodo, figshare, OSF and Dryad software/data-set DOIs are registered with
# DataCite, not CrossRef, so a CrossRef 404 on one of those DOIs is not "does not
# exist" -- it is "wrong registry". DataCite is consulted as a fallback wherever
# CrossRef comes back with a clean 404.
DATACITE_API = "https://api.datacite.org/dois/"


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


def is_initials(tok):
    """True for an initials token: 1-4 uppercase letters of any script, dotted or
    not, hyphenated or not ("J", "JL", "JLKM", "J.L.", "J.-L.", "J-H", "Ł", "ĐT",
    "И"). Judged on the raw token, before any casing."""
    parts = (tok or "").replace(".", "").split("-")
    letters = "".join(parts)
    return (all(parts) and 1 <= len(letters) <= 4
            and all(ch.isalpha() and ch.isupper() for ch in letters))


_SUFFIX = re.compile(r"(?i)^(?:jr|sr|[2-9](?:nd|rd|th))\.?$")
_ROMAN_SUFFIX = {"II", "III", "IV"}


def strip_suffixes(toks):
    """Name tokens without a trailing generational suffix ("Smith J Jr",
    "John Smith Jr.", "Smith EL 3rd"). "II"/"III"/"IV" count only after two other
    tokens, since alone after a surname they may be initials ("Smith IV")."""
    toks = list(toks)
    while len(toks) > 1 and (_SUFFIX.match(toks[-1]) or (len(toks) > 2 and toks[-1] in _ROMAN_SUFFIX)):
        toks.pop()
    return toks


def _spaced_initials(toks):
    """Given-name tokens -> one string; initials-only tokens are spaced out
    ("JS" -> "J S", "J-H" -> "J-H") so initials() keeps every letter."""
    if toks and all(is_initials(t) for t in toks):
        return " ".join("-".join(" ".join(g) for g in t.replace(".", "").split("-")) for t in toks)
    return " ".join(toks)


def words_then_initials(toks):
    """'Van Essen DC' -> ('Van Essen', 'D C'): words (particles count as words,
    even in capitals) followed only by initials, the PubMed family-first shape.
    None when the tokens are not that shape. A trailing Jr/Sr/III is dropped."""
    toks = strip_suffixes(toks)
    k = len(toks)
    while k > 1 and is_initials(toks[k - 1]):
        k -= 1
    if k < len(toks) and all(len(t) >= 2 and (not is_initials(t) or t.lower() in PARTICLES)
                             for t in toks[:k]):
        return " ".join(toks[:k]), _spaced_initials(toks[k:])
    return None


def _datacite_creator(c):
    """One DataCite creator -> (family, given, kept_whole).

    With a `givenName`, the deposit already split the name. Without one, the bare
    `name` is often a PERSON's display name ("Jagroop Singh Doad", nameType
    Personal); kept whole it shipped given-name-first as if it were a surname. So:
    a `familyName` found in `name` as a whole word (a hyphen is part of a word:
    "Doad" is not found in "Anna Doad-Smith") is the family and the given name is
    the rest of `name`; one not found keeps the name whole. "Family, Given"
    splits on its first ", ". A Personal name whose last token is initials is
    never split there: words followed only by initials ("Doad J S", "Van Essen
    DC", "Kim J-H") are family + initials, and any other shape stays whole. Any
    other Personal name of 2+ tokens that does not open with "The" ("The pandas
    development team") splits on its last token (split_name, which keeps
    particles) -- unless that would leave a one-letter surname, which is never
    guessed. Anything else stays whole: `kept_whole` is True for it unless
    DataCite declares it Organizational -- the one case where a whole name is
    known to be a group rather than a guess.
    """
    given = (c.get("givenName") or "").strip()
    name = (c.get("name") or "").strip()
    if given:
        return (c.get("familyName") or name).strip(), given, False
    kind = (c.get("nameType") or "").strip()
    family = (c.get("familyName") or "").strip()
    whole = family or name
    if kind == "Organizational":
        return name or whole, "", False
    if family and name and family.lower() != name.lower():
        m = re.search(r"(?i)(?<![\w-])" + re.escape(family) + r"(?![\w-])", name)
        rest = (name[:m.start()] + " " + name[m.end():]).strip(" ,").split() if m else []
        return (family, _spaced_initials(rest), False) if rest else (name, "", True)
    name = name or whole
    if ", " in name:
        fam, given = name.split(", ", 1)
        return fam.strip(), given.strip(), False
    toks = strip_suffixes(name.split())
    if kind == "Personal" and len(toks) >= 2 and toks[0].lower() != "the":
        if is_initials(toks[-1]):
            split = words_then_initials(toks)
            return (split[0], split[1], False) if split else (name, "", True)
        fam, given = split_name(" ".join(toks))
        if len(fam.strip(".")) > 1:
            return fam, given, False
    return name, "", bool(name)


def datacite_record(attrs, fallback_venue=""):
    """Normalize a DataCite `data.attributes` dict to the SAME shape
    crossref_record() returns, plus `version` and `resource_type`
    (`types.resourceTypeGeneral`: Software, Dataset, Preprint, ...).

    DataCite is the registry behind Zenodo/figshare/OSF/Dryad DOIs — software and
    data-set deposits CrossRef does not hold. A creator's `familyName`/`givenName`
    are used when a given name is present. A creator with NO given name is split
    by _datacite_creator(); a name it cannot split safely is kept whole (formatted
    with no initials) and listed in the record's `unsplit`, for canon to flag.
    `publisher` may be a bare string or `{"name": ...}`; `journal` mirrors it,
    matching the field crossref_record() uses for the venue.
    """
    authors, unsplit = [], []
    for c in attrs.get("creators") or []:
        if not isinstance(c, dict):
            continue
        fam, given, whole = _datacite_creator(c)
        if fam:
            authors.append((fam, given))
            if whole:
                unsplit.append(fam)
    fam, giv = authors[0] if authors else ("", "")
    publisher = attrs.get("publisher")
    if isinstance(publisher, dict):
        publisher = publisher.get("name", "")
    publisher = (publisher or "").strip() or clean_venue(fallback_venue)
    # The main title is the first with no titleType (titles[0] may be a
    # TranslatedTitle or AlternativeTitle); a Subtitle entry joins it after ": ",
    # as crossref_record() joins CrossRef's subtitle.
    titles = [t for t in (attrs.get("titles") or []) if isinstance(t, dict)]
    main = next((t for t in titles if not t.get("titleType")), titles[0] if titles else {})
    title = norm_title(main.get("title", ""))
    sub = norm_title(next((t.get("title", "") for t in titles if t.get("titleType") == "Subtitle"), ""))
    if title and sub and sub.lower() not in title.lower():
        title = f"{title.rstrip(':')}: {sub[:1].upper() + sub[1:]}"
    year = attrs.get("publicationYear")
    return {"title": title, "year": str(year) if year else "",
            "authors": authors, "people": [person(f, g) for f, g in authors],
            "first_author": f"{fam} {giv[:1]}".strip(), "journal": publisher,
            "volume": attrs.get("volume"), "issue": attrs.get("issue"),
            "pages": attrs.get("page"), "book": "", "publisher": publisher,
            "version": attrs.get("version") or "",
            "resource_type": (attrs.get("types") or {}).get("resourceTypeGeneral", ""),
            "unsplit": unsplit}


def _curl_status(url, headers, timeout):
    """GET via curl WITHOUT --fail -> (HTTP status int, body bytes); raises when
    curl itself fails. Unlike curl_get (vendored, and --fail by design), a 404
    comes back as a status, so a caller can tell "no such record" from a failure."""
    exe = shutil.which("curl")
    if not exe:
        raise RuntimeError("curl not available for fallback")
    cmd = [exe, "-sS", "--compressed", "-L", "--proto-redir", "=https",
           "--max-time", str(int(timeout)), "-w", "\n%{http_code}"]
    for k, v in (headers or {}).items():
        if k.lower() != "accept-encoding":        # --compressed sets and decodes it
            cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)
    p = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    if p.returncode != 0:
        raise OSError(f"curl exit {p.returncode}: {p.stderr.decode('utf-8', 'replace')[:120]}")
    body, _, code = p.stdout.rpartition(b"\n")
    code = code.strip().decode("ascii", "replace")
    if not code.isdigit():
        raise OSError(f"curl: no HTTP status for {url}")
    return int(code), body


def _datacite_get(url, retries=5, timeout=30):
    """http() for DataCite: urllib first, curl on a network failure -- but a
    curl 404 is raised as urllib.error.HTTPError(404), so a DOI missing from both
    registries is still "does not exist", never ERROR. urllib's connection is
    dropped deterministically on some networks for api.datacite.org while curl
    fetches the same URL (the stack/proxy interaction http()'s fallback exists
    for); through http(), curl's --fail turned every such 404 into an error."""
    global _REQUESTS
    tried_curl = False
    for attempt in range(retries):
        try:
            _REQUESTS += 1
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return decompress(r.read(), r.headers.get("Content-Encoding", ""))
        except urllib.error.HTTPError as e:
            if e.code in TRANSIENT_HTTP and attempt < retries - 1:
                wait = retry_after(e)
                time.sleep(wait if wait is not None else 3 * 2 ** attempt)
                continue
            raise
        except TRANSIENT_NETWORK:
            if not tried_curl:
                tried_curl = True
                try:
                    code, body = _curl_status(url, HDRS, timeout)
                except Exception:
                    code, body = None, b""
                if code is not None and 200 <= code < 300:
                    return body
                if code is not None and code not in TRANSIENT_HTTP:
                    # a definite answer (404: no such DOI) -- not a failure to retry
                    raise urllib.error.HTTPError(url, code, f"HTTP {code} (via curl)", {}, None)
            if attempt < retries - 1:
                time.sleep(2 * 2 ** attempt)
                continue
            raise


def datacite_work(doi, fallback_venue=""):
    """Fetch one DOI from DataCite -> datacite_record(). Raises on a transient
    failure (so callers can tell ERROR from NOT-FOUND, same contract as
    crossref_work); a 404 propagates too, as urllib.error.HTTPError, whether
    urllib or the curl fallback got it (_datacite_get)."""
    import urllib.parse
    data = json.loads(_datacite_get(f"{DATACITE_API}{urllib.parse.quote(doi)}"))["data"]
    return datacite_record(data.get("attributes") or {}, fallback_venue)


def norm_arxiv(aid):
    """Normalize an arXiv id for matching: strip whitespace and a version suffix."""
    return re.sub(r"v\d+$", "", (aid or "").strip())


def arxiv_entries(xml_bytes):
    """Parse an arXiv API Atom feed -> [{id, title, year, authors, first_author,
    journal_ref, summary}], skipping the API's synthetic 'Error' entry (an
    unknown id). Raises ValueError on a body that is not an Atom feed (a
    redirect or error page), so a batch reads as errored, never as all-missing."""
    import xml.etree.ElementTree as ET
    out = []
    root = ET.fromstring(xml_bytes)
    if root.tag != f"{ATOM}feed":
        raise ValueError(f"arXiv API returned <{root.tag}>, not an Atom feed")
    for e in root.findall(f"{ATOM}entry"):
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
                    "journal_ref": (e.findtext(f"{ARXIV_NS}journal_ref") or "").strip(),
                    "summary": " ".join((e.findtext(f"{ATOM}summary") or "").split())})
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


# ---- Semantic Scholar ---------------------------------------------------------
# Every S2 call goes through s2_request. The per-key limit is strict and its 429s
# carry no Retry-After, so the toolkit paces itself: at least S2_MIN_INTERVAL
# between requests, then S2_BACKOFF after a 429 or other transient failure.
S2_API = "https://api.semanticscholar.org/graph/v1/"
S2_MIN_INTERVAL = 1.1
S2_BACKOFF = (20, 40)
_S2_LAST = [0.0]


def s2_request(path, body=None):
    """GET (or POST `body` as JSON) S2_API + path; returns parsed JSON.

    Backs off (S2_BACKOFF) and retries after a 429 or other transient failure
    (is_transient); a non-transient error (400, 404) raises immediately."""
    hdrs = dict(HDRS)
    if body is not None:
        hdrs["Content-Type"] = "application/json"
    key = os.environ.get("S2_API_KEY")
    if key:
        hdrs["x-api-key"] = key
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(len(S2_BACKOFF) + 1):
        wait = _S2_LAST[0] + S2_MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _S2_LAST[0] = time.monotonic()
        try:
            return http_json(S2_API + path, retries=1, data=data, headers=hdrs)
        except Exception as e:
            if is_transient(e) and attempt < len(S2_BACKOFF):
                time.sleep(S2_BACKOFF[attempt])
                continue
            raise


def s2_batch(path, ids, chunk):
    """POST `ids` to an S2 batch endpoint (`path`, e.g. "paper/batch?fields=...")
    in chunks -> (results {id: record or None}, failed set, rejected set).

    S2 answers a whole batch with a 400 (or 404) when ONE id is malformed,
    which used to fail up to 500 good ids with it. So a 400/404 on a chunk of
    more than one id is bisected until the offending ids stand alone: an id
    that still gets a 400/404 on its own is `rejected` (callers treat it as
    "not in S2" and name it).

    A 401/403 or any other non-transient 4xx is not "this id may be bad" --
    it is the request itself (a missing/expired S2_API_KEY, a malformed
    endpoint) -- so it marks the WHOLE chunk `failed` immediately, with no
    bisection, and is reported once so a bad key does not silently read as
    hundreds of "not in S2" misses. Likewise, if bisecting a 400/404 chunk
    still ends with EVERY id of that chunk rejected, the request -- not any
    one id -- was the problem, so those ids move from `rejected` to `failed`
    too.

    A chunk that fails transiently after s2_request's backoff marks its ids
    `failed` (re-run), and the other chunks still go out. A record of None
    means S2 has no such paper."""
    results, failed, rejected = {}, set(), set()
    warned = False

    def post(part):
        nonlocal warned
        try:
            res = s2_request(path, {"ids": part})
        except urllib.error.HTTPError as e:
            if e.code in (400, 404) and not is_transient(e):
                if len(part) > 1:
                    mid = len(part) // 2
                    post(part[:mid])
                    post(part[mid:])
                else:
                    rejected.update(part)
                return
            if 400 <= e.code < 500 and not is_transient(e):
                if not warned:
                    warned = True
                    print(f"Semantic Scholar refused the request (HTTP {e.code}); "
                          "check S2_API_KEY", file=sys.stderr)
            failed.update(part)
            return
        except Exception:
            failed.update(part)
            return
        for i, rec in zip(part, res or []):
            results[i] = rec

    uniq = list(dict.fromkeys(ids))
    for i in range(0, len(uniq), chunk):
        top = uniq[i:i + chunk]
        post(top)
        if len(top) > 1 and rejected.issuperset(top):
            rejected.difference_update(top)
            failed.update(top)
    return results, failed, rejected
