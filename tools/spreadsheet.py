#!/usr/bin/env python3
"""Build/rebuild the bibliography xlsx from a JSON of accumulated rows.

Base schema:
  Topic | Ref# | APA reference | Link | Summary | Tag | PDF (local) | Xref

Optional columns, auto-added when the data carries them:
  - `family` on any row -> a "Family" column after Tag (thematic grouping).
  - citation counts -> "Cite (OpenAlex)" | "Cite (S2)" (see below).

Citation columns (auto-added): if any row carries citation counts, two columns
  Cite (OpenAlex) | Cite (S2)
are inserted after Tag. Counts come from tools/citations.py (Phase 5b); attach
them to each row as `cite_openalex` / `cite_s2` — the exact key names
citations.py emits (`openalex` / `s2`), prefixed `cite_`. Google Scholar can't
be queried at scale (no API, CAPTCHA) — these databases are the proxy. See
PLAYBOOK.md.

`Link` should always be a DOI URL (`https://doi.org/<doi>`). PubMed/PMC URLs
are not used as the primary link. `PDF (local)` is empty unless Phase 4 was
opted into.

Color codes by `source`:
  source-doc -> white | search -> cream (#FFF7E0) | xref -> green (#E2F0D9)

Input format (JSON list):
[
  {"topic": "Multimodal networks", "ref": "M41",
   "apa": "Author, A. (2024). Title. Journal, 1(1), 1-2.",
   "link": "https://doi.org/10.1234/abcd", "summary": "...", "tag": "classic",
   "pdf": "", "xref": 10, "source": "xref",
   "cite_openalex": 123, "cite_s2": 140},      # optional; omit if not fetched
  ...
]

Run:  python3 spreadsheet.py --rows rows.json --out bibliography.xlsx
"""
import argparse, json
import xlsxwriter

COLORS = {"source-doc": None, "search": "#FFF7E0", "xref": "#E2F0D9"}


def cite_val(row, key):
    """Citation count for a column, or None. `0` is a real count, so test type
    (not truthiness); a bool is never a valid count."""
    v = row.get(key)
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sheet-name", default="References")
    args = ap.parse_args()

    rows = json.load(open(args.rows))

    # Auto-detect citation counts on any row -> add the two columns.
    has_cite = any(
        cite_val(r, "cite_openalex") is not None or cite_val(r, "cite_s2") is not None
        for r in rows
    )

    wb = xlsxwriter.Workbook(args.out)
    ws = wb.add_worksheet(args.sheet_name)

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
    cols += [("PDF (local)", "pdf", 14, "text"), ("Xref", "xref", 8, "text")]

    for c, (header, _, width, _kind) in enumerate(cols):
        ws.set_column(c, c, width)
        ws.write(0, c, header, header_fmt)
    ws.freeze_panes(1, 0)

    for i, r in enumerate(rows, start=1):
        src = r.get("source", "source-doc")
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
            else:
                ws.write(i, c, r.get(key, ""), cf)
        ws.set_row(i, 110)

    wb.close()
    n_pdf = sum(1 for r in rows if r.get("pdf"))
    extra = " + citation columns" if has_cite else ""
    print(f"Wrote {len(rows)} rows ({n_pdf} with PDFs){extra} to {args.out}")


if __name__ == "__main__":
    main()
