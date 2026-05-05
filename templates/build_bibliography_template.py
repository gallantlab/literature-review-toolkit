"""Template — copy this to your project as `build_bibliography.py` and edit.

This is the per-version-script pattern: each batch of papers gets its own
`build_bibliography_v<N>.py` that imports the previous version's data and
appends its own. Final script in the chain (the one you run) writes the
xlsx.

The simpler alternative is to keep all rows in a single JSON and call
`tools/spreadsheet.py`. Pick whichever fits how you work.

KEY CONVENTION (mandatory if you use this pattern): the xlsx-writing block
must live under `if __name__ == "__main__":`. Otherwise importing this
script for its data structures rewrites the spreadsheet as a side effect.
See PLAYBOOK.md, "Note on per-version data scripts".

Schema for each ROWS entry:
  (topic, ref_num, apa_string, link_url, summary)
"""
import xlsxwriter

# ============================================================
# DATA (importable, no side effects)
# ============================================================

ROWS = [
    # (topic, ref, apa, link, summary)
    # ("Topic name", 1,
    #  "Author, A. (YEAR). Title. Journal, vol(iss), pages.",
    #  "https://pubmed.ncbi.nlm.nih.gov/<pmid>/",
    #  "3-5 sentence summary of what the paper did and why it matters."),
]


# ============================================================
# WRITING BLOCK — guarded so imports don't rewrite the xlsx
# ============================================================

if __name__ == "__main__":
    WB = "bibliography.xlsx"
    wb = xlsxwriter.Workbook(WB)
    ws = wb.add_worksheet("References")

    header_fmt = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1, "valign": "top"})
    cell_fmt = wb.add_format({"valign": "top", "text_wrap": True, "border": 1})
    link_fmt = wb.add_format({"valign": "top", "text_wrap": True, "border": 1,
                              "font_color": "blue", "underline": 1})

    ws.set_column("A:A", 22)  # Topic
    ws.set_column("B:B", 8)   # Ref #
    ws.set_column("C:C", 60)  # APA
    ws.set_column("D:D", 50)  # Link
    ws.set_column("E:E", 90)  # Summary

    ws.write_row(0, 0, ["Topic", "Ref #", "APA reference", "Link", "Summary"], header_fmt)
    ws.freeze_panes(1, 0)

    for i, (topic, ref, apa, link, summary) in enumerate(ROWS, start=1):
        ws.write(i, 0, topic, cell_fmt)
        ws.write(i, 1, ref, cell_fmt)
        ws.write(i, 2, apa, cell_fmt)
        ws.write_url(i, 3, link, link_fmt, link)
        ws.write(i, 4, summary, cell_fmt)
        ws.set_row(i, 110)

    wb.close()
    print(f"Wrote {len(ROWS)} rows to {WB}")
