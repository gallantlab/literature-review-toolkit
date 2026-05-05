#!/usr/bin/env python3
"""Build/rebuild the bibliography xlsx from a JSON of accumulated rows.

Schema:
  Topic | Ref# | APA reference | Link | Summary | Tag | PDF (local) | Xref

`Link` should always be a DOI URL (`https://doi.org/<doi>`). PubMed/PMC URLs
are not used as the primary link — see PLAYBOOK.md.

`PDF (local)` is empty by default since Phase 4 is opt-in. Populate only if
PDFs were actually downloaded.

Color codes by `source`:
  source-doc -> white
  search     -> cream  (#FFF7E0)
  xref       -> green  (#E2F0D9)

Input format (JSON list):
[
  {"topic": "Multimodal networks",
   "ref":   "M41",
   "apa":   "Author, A. (2024). Title. Journal, 1(1), 1-2.",
   "link":  "https://doi.org/10.1234/abcd",
   "summary": "...",
   "tag":   "classic",
   "pdf":   "",                           # empty unless Phase 4 was opted-in
   "xref":  10,                           # citation count, or null
   "source":"xref"                       # one of: source-doc | search | xref
  },
  ...
]

Run:  python3 spreadsheet.py --rows rows.json --out bibliography.xlsx
"""
import argparse, json
import xlsxwriter

COLORS = {
    "source-doc": None,
    "search":     "#FFF7E0",
    "xref":       "#E2F0D9",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sheet-name", default="References")
    args = ap.parse_args()

    rows = json.load(open(args.rows))

    wb = xlsxwriter.Workbook(args.out)
    ws = wb.add_worksheet(args.sheet_name)

    header_fmt = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1, "valign": "top"})
    base_fmt = {"valign": "top", "text_wrap": True, "border": 1}
    base_link = {**base_fmt, "font_color": "blue", "underline": 1}

    fmts = {None: wb.add_format(base_fmt), "link": wb.add_format(base_link)}
    for src, color in COLORS.items():
        if color:
            fmts[src] = wb.add_format({**base_fmt, "bg_color": color})
            fmts[("link", src)] = wb.add_format({**base_link, "bg_color": color})
        else:
            fmts[src] = fmts[None]
            fmts[("link", src)] = fmts["link"]

    ws.set_column("A:A", 22)
    ws.set_column("B:B", 8)
    ws.set_column("C:C", 60)
    ws.set_column("D:D", 50)
    ws.set_column("E:E", 90)
    ws.set_column("F:F", 14)
    ws.set_column("G:G", 50)
    ws.set_column("H:H", 8)

    headers = ["Topic", "Ref #", "APA reference", "Link", "Summary", "Tag", "PDF (local)", "Xref"]
    ws.write_row(0, 0, headers, header_fmt)
    ws.freeze_panes(1, 0)

    for i, r in enumerate(rows, start=1):
        src = r.get("source", "source-doc")
        cf = fmts[src]
        lf = fmts[("link", src)]
        ws.write(i, 0, r.get("topic", ""), cf)
        ws.write(i, 1, r.get("ref", ""), cf)
        ws.write(i, 2, r.get("apa", ""), cf)
        link = r.get("link", "")
        if link:
            ws.write_url(i, 3, link, lf, link)
        else:
            ws.write(i, 3, "", cf)
        ws.write(i, 4, r.get("summary", ""), cf)
        ws.write(i, 5, r.get("tag", ""), cf)
        ws.write(i, 6, r.get("pdf", ""), cf)
        x = r.get("xref")
        ws.write(i, 7, "" if x in (None, "") else str(x), cf)
        ws.set_row(i, 110)

    wb.close()
    n_pdf = sum(1 for r in rows if r.get("pdf"))
    print(f"Wrote {len(rows)} rows ({n_pdf} with PDFs) to {args.out}")


if __name__ == "__main__":
    main()
