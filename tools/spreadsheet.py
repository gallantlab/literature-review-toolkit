#!/usr/bin/env python3
"""Build the bibliography .xlsx from rows.json, and refuse a table that fails the audit.

It runs the same audit as references.py --audit. On a gated table, a failing
audit writes nothing and exits 1; --draft writes <out>_DRAFT.xlsx instead, with a
banner saying it is not a deliverable. A legacy table (one that predates the
reference gates) is written despite the findings. A candidates.json that is not a
valid ledger is refused on any table.

Base schema (sheet "References", or --sheet-name):
  Topic | Ref # | APA reference | Link | Summary | Tag | PDF (local) | Xref

Columns added after Tag when the data carries them, in this order:
  - Family, when any row has `family` (families.py);
  - Cite (OpenAlex) | Cite (S2), when any row has `cite_openalex` or `cite_s2`.
    The counts come from citations.py (Phase 5b); attach them to the rows with
    its --attach or --attach-only. Google Scholar cannot be queried at scale (no API,
    CAPTCHA), so these databases are the proxy. See PLAYBOOK.md;
  - Verify note, when any row has a `verify_note` (handcheck.py writes one);
  - Summary checked against, when any row has a `summary_check`
    (summary_audit.py): the abstract's source, or "no abstract".

A second sheet, "Considered and excluded", lists each candidate the ledger
excluded and each paper a lane excluded (merge_report.json beside --rows), with
its reason. So a paper that is not in the review was visibly considered.

`Link` should always be a DOI URL (`https://doi.org/<doi>`); PubMed/PMC URLs are
not used as the primary link. `PDF (local)` is empty unless Phase 4 was opted
into.

Row color by `source` (see COLORS; an unknown value renders white, with a warning):
  source-doc -> white | search -> cream (#FFF7E0) | xref / forward / survey -> green (#E2F0D9)
  lab -> blue (#DDEBF7) | anteced / anteced-nosrc -> lilac (#F3E6F5)

Input format (JSON list):
[
  {"topic": "Multimodal networks", "ref": "M41",
   "apa": "Author, A. (2024). Title. Journal, 1(1), 1-2.",
   "link": "https://doi.org/10.1234/abcd", "summary": "...", "tag": "classic",
   "pdf": "", "xref": 10, "source": "xref",
   "cite_openalex": 123, "cite_s2": 140},      # optional; omit if not fetched
  ...
]

  python3 tools/spreadsheet.py --rows rows.json --out bibliography.xlsx
"""
import argparse
import os
import sys

import xlsxwriter

import candidates
import common
import references

PHASE = "5"   # pipeline phase, read by tools/gen_docs.py for the tool index

COLORS = {"source-doc": None, "search": "#FFF7E0", "xref": "#E2F0D9", "lab": "#DDEBF7",
          # Phase 6 candidates found by forward citation or a survey share xref's green
          "forward": "#E2F0D9", "survey": "#E2F0D9",
          # Phase 2b antecedents (foundations pass): a distinct band. DOI'd classics
          # get the fill; no-DOI hand-cited classics ("anteced-nosrc") share it.
          "anteced": "#F3E6F5", "anteced-nosrc": "#F3E6F5",
          # a forward lane's DOI-less item (a book, a report) keeps the search fill
          "search-nosrc": "#FFF7E0"}


def cite_val(row, key):
    """Citation count for a column, or None. `0` is a real count, so test type
    (not truthiness); a bool is never a valid count."""
    v = row.get(key)
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def unknown_sources(rows):
    """`source` values with no color rule — a warning, not a crash: corpora
    already disagree on the tag vocabulary, and a new value must never abort a
    build. They render with the default (white) format."""
    return sorted({r.get("source", "source-doc") for r in rows} - set(COLORS))


def draft_path(out):
    """bib.xlsx -> bib_DRAFT.xlsx: a draft can never pass for the deliverable."""
    stem, ext = os.path.splitext(out)
    return f"{stem}_DRAFT{ext or '.xlsx'}"


def lane_exclusions(report_path, rows, seen_dois=()):
    """The papers search lanes excluded on purpose (merge_lanes.py `excluded`), as
    "Considered and excluded" entries — minus any another lane kept, any the table
    now holds, and any the candidate ledger already lists."""
    if not os.path.exists(report_path):
        return []
    rep = common.load_json(report_path)
    have = {common.doi_of(r, lower=True) for r in rows} - {None, ""}
    seen = {(d or "").lower() for d in seen_dois}
    out = []
    for e in (rep.get("excluded") or []) if isinstance(rep, dict) else []:
        doi = common.doi_of(e, lower=True) or ""
        if e.get("kept_as") or (doi and (doi in have or doi in seen)):
            continue
        out.append({"doi": doi, "title": e.get("title", ""), "year": e.get("year", ""),
                    "first_author": e.get("first_author", ""), "sources": f"lane {e.get('from_lane', '')}",
                    "reason": e.get("reason", "")})
    return out


def build(rows, out, sheet_name="References", banner=None, excluded=None):
    """Write the xlsx. Returns (n_rows, has_cite)."""
    # Auto-detect citation counts on any row -> add the two columns.
    has_cite = any(
        cite_val(r, "cite_openalex") is not None or cite_val(r, "cite_s2") is not None
        for r in rows
    )

    wb = xlsxwriter.Workbook(out)
    ws = wb.add_worksheet(sheet_name)

    header_fmt = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1,
                                "valign": "top", "text_wrap": True})
    base_fmt = {"valign": "top", "text_wrap": True, "border": 1}
    base_link = {**base_fmt, "font_color": "blue", "underline": 1}
    base_num = {**base_fmt, "align": "center"}

    fmts = {None: wb.add_format(base_fmt), "link": wb.add_format(base_link),
            "num": wb.add_format(base_num)}
    for src, color in COLORS.items():
        if color:
            fmts[src] = wb.add_format({**base_fmt, "bg_color": color})
            fmts[("link", src)] = wb.add_format({**base_link, "bg_color": color})
            fmts[("num", src)] = wb.add_format({**base_num, "bg_color": color})
        else:
            fmts[src] = fmts[None]
            fmts[("link", src)] = fmts["link"]
            fmts[("num", src)] = fmts["num"]

    # Optional thematic grouping column, auto-added when rows carry `family`.
    has_family = any(r.get("family") for r in rows)
    # verify_note marks a reference needing (or explaining) human attention —
    # a hand-check-pending row must not ship indistinguishable from a verified one.
    has_vnote = any(r.get("verify_note") for r in rows)
    # summary_audit.py stamps summary_check on every checked row -- surface what
    # each summary was checked against, so a "no abstract" row is not indistinguishable
    # from one the audit actually confirmed.
    has_scheck = any(isinstance(r.get("summary_check"), dict) for r in rows)

    # Column plan: (header, key, width, kind). kind in {text, link, num}.
    cols = [
        ("Topic",         "topic",   22, "text"),
        ("Ref #",         "ref",      8, "text"),
        ("APA reference", "apa",     60, "text"),
        ("Link",          "link",    48, "link"),
        ("Summary",       "summary", 88, "text"),
        ("Tag",           "tag",     18, "text"),
    ]
    if has_family:
        cols.append(("Family", "family", 14, "text"))
    if has_cite:
        cols += [("Cite (OpenAlex)", "cite_openalex", 13, "num"),
                 ("Cite (S2)",       "cite_s2",       12, "num")]
    if has_vnote:
        cols.append(("Verify note", "verify_note", 32, "text"))
    if has_scheck:
        cols.append(("Summary checked against", "summary_basis", 18, "text"))
    cols += [("PDF (local)", "pdf", 14, "text"), ("Xref", "xref", 8, "text")]

    top = 0
    if banner:
        banner_fmt = wb.add_format({"bold": True, "font_color": "#9C0006", "bg_color": "#FFC7CE",
                                    "text_wrap": True, "valign": "top"})
        ws.merge_range(0, 0, 0, len(cols) - 1, banner, banner_fmt)
        ws.set_row(0, 36)
        top = 1
    for c, (header, _, width, _kind) in enumerate(cols):
        ws.set_column(c, c, width)
        ws.write(top, c, header, header_fmt)
    ws.freeze_panes(top + 1, 0)

    for i, r in enumerate(rows, start=top + 1):
        src = r.get("source", "source-doc")
        if src not in COLORS:
            src = "source-doc"           # unknown tag -> default format (see unknown_sources)
        cf, lf, nf = fmts[src], fmts[("link", src)], fmts[("num", src)]
        for c, (_h, key, _w, kind) in enumerate(cols):
            if kind == "link":
                link = r.get("link", "")
                ws.write_url(i, c, link, lf, link) if link else ws.write(i, c, "", cf)
            elif kind == "num":
                v = cite_val(r, key)
                ws.write_number(i, c, v, nf) if v is not None else ws.write(i, c, "", nf)
            elif key == "xref":
                x = r.get("xref")
                ws.write(i, c, "" if x in (None, "") else str(x), cf)
            elif key == "summary_basis":
                sc = r.get("summary_check") or {}
                verdict = sc.get("verdict")
                basis = ("no abstract" if verdict == "no-abstract"
                         else f"abstract ({sc.get('abstract_source')})" if verdict == "supported" else "")
                ws.write(i, c, basis, cf)
            else:
                ws.write(i, c, r.get(key, ""), cf)
        ws.set_row(i, 110)

    if excluded:
        xs = wb.add_worksheet("Considered and excluded")
        xcols = [("DOI", "doi", 30), ("Title", "title", 70), ("Year", "year", 8),
                 ("First author", "first_author", 22), ("Found by", "sources", 20), ("Reason", "reason", 60)]
        for c, (h, _k, w) in enumerate(xcols):
            xs.set_column(c, c, w)
            xs.write(0, c, h, header_fmt)
        for i, e in enumerate(excluded, start=1):
            for c, (_h, k, _w) in enumerate(xcols):
                v = e.get(k, "")
                xs.write(i, c, ", ".join(sorted(v)) if isinstance(v, dict) else str(v), fmts[None])

    wb.close()
    return len(rows), has_cite


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sheet-name", default="References")
    ap.add_argument("--key", default=None, help="row key field (default: ref, else label)")
    ap.add_argument("--acks", help="acknowledged warnings (default: audit_acks.json beside --rows)")
    ap.add_argument("--candidates", help="candidate ledger (default: candidates.json beside --rows)")
    ap.add_argument("--draft", action="store_true",
                    help="write even if the audit fails, as <out>_DRAFT.xlsx with a banner")
    args = ap.parse_args()

    rows = common.load_json(args.rows)
    here = os.path.dirname(os.path.abspath(args.rows))
    keyf = common.key_field(rows, args.key)
    acks = references.load_acks(args.acks or os.path.join(here, "audit_acks.json"))
    ledger = common.load_optional_json(args.candidates or os.path.join(here, "candidates.json"),
                                       references.LEDGER_MISSING)
    if ledger is not references.LEDGER_MISSING:
        # references.audit_rows only validates the ledger's shape when the table
        # is gated, and --draft continues past a failed (gated) audit -- so a
        # corrupted ledger must be caught here too, on EVERY table (gated or
        # legacy, --draft or not), before anything is written. Any file that
        # exists is validated: a `[]` ledger is refused, not skipped.
        try:
            candidates.validate_ledger(ledger)
        except ValueError as e:
            print(f"✗ {e}", file=sys.stderr)
            sys.exit(1)
    report = references.audit_rows(rows, keyf, acks, ledger=ledger,
                                   hand_fixes=common.load_hand_fixes(os.path.join(here, common.HAND_FIXES)))
    out, banner = args.out, None
    if report["failed"]:
        references.print_report(report, len(rows))
        n = len(report["defects"]) + len(report["corpus"]) + sum(len(v) for v in report["unacked"].values())
        if args.draft:
            out = draft_path(args.out)
            banner = f"DRAFT, NOT A DELIVERABLE: {n} audit failure(s). Run references.py --audit."
        elif report["gated"]:
            print(f"✗ not written: {n} audit failure(s). Fix them, or pass --draft for a marked draft.",
                  file=sys.stderr)
            sys.exit(1)
        else:
            print("  (legacy corpus: written despite the audit findings above)", file=sys.stderr)
    ledger_dict = ledger if isinstance(ledger, dict) else {}
    excluded = [dict(v, doi=d) for d, v in candidates.entries(ledger_dict) if v.get("decision") == "exclude"]
    excluded += lane_exclusions(os.path.join(here, "merge_report.json"), rows, {e["doi"] for e in excluded})
    for src in unknown_sources(rows):
        print(f"  ⚠ source={src!r} has no color rule (known: {', '.join(COLORS)}); "
              "rendered white", file=sys.stderr)
    n, has_cite = build(rows, out, args.sheet_name, banner=banner, excluded=excluded)
    n_pdf = sum(1 for r in rows if r.get("pdf"))
    extra = " + citation columns" if has_cite else ""
    print(f"Wrote {n} rows ({n_pdf} with PDFs){extra} to {out}")


if __name__ == "__main__":
    main()
