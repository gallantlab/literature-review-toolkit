#!/usr/bin/env python3
"""Phase 6b figure — an INTERACTIVE HTML lineage figure of the theoretical
families (replaces the old static matplotlib png/pdf/svg).

Self-contained single .html (inline SVG + CSS + JS, no deps, no network): open
in a browser, present fullscreen. Hover any node -> full reference (tooltip);
click -> side panel with citation + a live DOI link; hover a family's name ->
spotlight its lineage. Also writes a standalone .svg of the panel and, if
rsvg-convert/inkscape is present, .png + .pdf for slides/papers.

Data-driven: family lanes come from families.json, dots from rows.json (one per
paper, beeswarm-packed by year within its lane).

LANDMARKS are auto-selected and labelled (big dots) — no hand-made overlay needed.
A paper is a landmark if ANY of:
  (1) it is among the most-cited in its family (top --per-family by max(OpenAlex, S2)),
  (2) it is foundational *within this review* — cited by >= --motif-min of the corpus's
      own papers (needs --internal internal_citations.json from `xref.py --internal-out`;
      silently skipped if not supplied),
  (3) it is a home-lab paper (an author surname in --lab-author, default "Gallant", or a
      row with source == "lab") — these are starred (★) and gold-ringed.
Total labels are capped at --max-labels (lab + internal-motif papers are always kept).
Pass --spec with a "labels" map to override auto-selection entirely (manual curation wins);
--no-auto-landmarks turns labelling off.

  python3 tools/families_figure.py --rows rows.json --families families.json \
          --out-prefix mytopic_families --title "My topic — theoretical families" \
          --internal internal_citations.json   # optional, from xref.py --internal-out

OPTIONAL editorial overlay (--spec figure_spec.json), all keys optional:
  { "labels":  {"<ref>": "short label", ...},     # which papers to label (overrides milestones)
    "arrows":  [{"from":"<ref>","to":"<ref>","color":"#b00020","label":"..."}],
    "notes":   [{"at":"<ref>","text":"...","color":"#333"}],
    "order":   ["FamilyName", ...],                # lane order (default: families.json order)
    "subtitle":"..." }
The lineage arrows/notes are editorial — curate them with the user; don't expect
a good auto-generated set. See PLAYBOOK Phase 6b.
"""
import argparse, base64, bisect, html, json, os, re, shutil, subprocess, sys

PALETTE = ["#1b6ca8", "#2a9d8f", "#e76f51", "#8338ec", "#d4a017", "#6c757d",
           "#c1121f", "#177e89", "#7209b7", "#bc6c25"]


def esc(s): return html.escape(str(s), quote=True)
def year_of(apa):
    m = re.search(r"\((\d{4})\)", apa or "")
    return int(m.group(1)) if m else None
def lead(apa): return (apa or "").split(",")[0]


def wrap(text, n=40):
    out, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > n:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


def beeswarm(items, r=2.7, step=5.6, maxoff=52):
    placed, out = [], []
    for x, payload in sorted(items, key=lambda t: t[0]):
        off, k = 0, 1
        while any(abs(x - px) < 2 * r + 0.6 and abs(off - po) < 2 * r + 0.6 for px, po in placed):
            off = step * ((k + 1) // 2) * (1 if k % 2 else -1)
            if abs(off) > maxoff:
                break
            k += 1
        placed.append((x, off)); out.append((x, off, payload))
    return out


def _boxes_overlap(a, b):
    """a, b = (x0, x1, y0, y1). True if the two rectangles intersect."""
    return not (a[1] < b[0] or a[0] > b[1] or a[3] < b[2] or a[2] > b[3])


def _box_hits_dot(box, dx, dy, margin=11):
    """True if a dot at (dx, dy) falls within `margin` of the label box."""
    return box[0] - margin <= dx <= box[1] + margin and box[2] - margin <= dy <= box[3] + margin


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--families", required=True, help="families.json from tools/families.py")
    ap.add_argument("--out-prefix", required=True)
    ap.add_argument("--title", default="Theoretical families")
    ap.add_argument("--spec", help="optional editorial overlay JSON (labels/arrows/notes)")
    ap.add_argument("--no-raster", action="store_true", help="skip png/pdf even if a converter exists")
    ap.add_argument("--min-year", type=int, help="clamp the x-axis start; older papers pin to the left edge")
    ap.add_argument("--time-warp", type=float, default=0.0,
                    help="nonlinear time axis in [0,1]: blend the linear axis with the empirical CDF "
                         "of paper years, so sparse (early) spans compress and dense (recent) spans "
                         "expand. 0 = linear (default), 1 = full density-equalizing.")
    ap.add_argument("--xlsx", help="embed this .xlsx and add a download button to the figure")
    ap.add_argument("--emphasize-source", help="render rows with this source as big circles "
                    "(e.g. 'lab' so a lab's own papers stand out from the field)")
    ap.add_argument("--no-auto-landmarks", action="store_true",
                    help="disable automatic landmark labelling (default: on when --spec has no labels)")
    ap.add_argument("--per-family", type=int, default=4,
                    help="auto-landmarks: label the top-N most-cited papers per family (default 4)")
    ap.add_argument("--max-labels", type=int, default=28,
                    help="auto-landmarks: cap total labels for legibility (default 28); each lane is "
                         "guaranteed its top-2 most-cited + all home-lab papers, rest filled by centrality")
    ap.add_argument("--motif-min", type=int, default=3,
                    help="auto-landmarks: a paper cited by >= this many corpus siblings is a landmark "
                         "(needs --internal)")
    ap.add_argument("--internal", help="auto-landmarks: {ref: internal_indegree} JSON from "
                    "`xref.py --internal-out` — enables criterion (2), within-review centrality")
    ap.add_argument("--lab-author", action="append", default=[],
                    help="auto-landmarks: home-lab author surname(s) to star as landmarks "
                         "(repeatable; default 'Gallant'). Rows with source=='lab' are also starred.")
    args = ap.parse_args()

    def load(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    rows = load(args.rows)
    fam_spec = load(args.families)
    spec = load(args.spec) if args.spec else {}

    fams = fam_spec["families"]
    order = spec.get("order") or [f["name"] for f in fams]
    claim = {f["name"]: f.get("claim", "") for f in fams}
    COLOR = {name: PALETTE[i % len(PALETTE)] for i, name in enumerate(order)}
    LANE = {name: i for i, name in enumerate(order)}
    subtitle = spec.get("subtitle") or fam_spec.get("principle", "")

    # papers with a usable year, grouped per lane
    papers = {}
    for r in rows:
        y = year_of(r.get("apa"))
        fam = r.get("family")
        if y and fam in LANE:
            papers[r["ref"]] = {"ref": r["ref"], "family": fam, "year": y,
                                "apa": r.get("apa", ""), "doi": r.get("link", ""),
                                "topic": r.get("topic", ""), "source": r.get("source", ""),
                                "summary": r.get("summary", ""),
                                "oa": r.get("cite_openalex"), "s2": r.get("cite_s2")}

    if not papers:
        sys.exit("families_figure: no papers with a parseable year and a known family — "
                 "nothing to plot (check rows.json has `family` + a (YYYY) in each apa).")

    # ---- landmark (big, labelled) selection --------------------------------
    # Home-lab detection (criterion 3): author surname match or source=="lab".
    lab_surnames = [s for s in args.lab_author if s.strip()] or ["Gallant"]

    def _is_lab(p):
        if p.get("source") == "lab":
            return True
        authors = p.get("apa", "").split("(")[0]        # author list, before the (year)
        return any(re.search(r"\b" + re.escape(sn) + r"\b", authors, re.I) for sn in lab_surnames)

    def _cites(p):
        vals = [v for v in (p.get("oa"), p.get("s2")) if isinstance(v, int)]
        return max(vals) if vals else -1

    internal = load(args.internal) if (args.internal and os.path.exists(args.internal)) else {}
    lab = {ref for ref, p in papers.items() if _is_lab(p)}

    # which papers get labels: spec.labels (manual, overrides) > legacy ★-in-ref > auto-landmarks
    if spec.get("labels"):
        labelled = {ref: lab for ref, lab in spec["labels"].items() if ref in papers}
    elif any("★" in ref for ref in papers):
        labelled = {ref: lead(p["apa"]) for ref, p in papers.items() if "★" in ref}
    elif args.no_auto_landmarks:
        labelled = {}
    else:
        def _fam_by_cites(name):
            return sorted((ref for ref, p in papers.items() if p["family"] == name),
                          key=lambda r: -_cites(papers[r]))
        cite_top = set()                                                   # (1) top-cited per family
        for name in order:
            cite_top |= set(_fam_by_cites(name)[:max(0, args.per_family)])
        motif = {ref for ref in papers if internal.get(ref, 0) >= args.motif_min}  # (2) within-review centrality
        chosen = set(lab) | motif | cite_top                               # (3) home-lab papers
        if len(chosen) > args.max_labels:
            # Cap for legibility. Guarantee each lane is represented (lab + top-2 most-cited
            # per family), then fill the budget by within-review in-degree — the "motivates
            # other work" signal — breaking ties by citation count.
            keep = set(lab)
            for name in order:
                keep |= set(_fam_by_cites(name)[:2])
            pool = sorted(chosen - keep,
                          key=lambda r: (internal.get(r, 0), _cites(papers[r])), reverse=True)
            chosen = keep | set(pool[:max(0, args.max_labels - len(keep))])
        labelled = {ref: f'{lead(papers[ref]["apa"]).strip()} {papers[ref]["year"]}' for ref in chosen}

    # star home-lab papers in their label (auto or manual), so they read as the lab's own
    labelled = {ref: (("★ " + t) if (ref in lab and not t.startswith("★")) else t)
                for ref, t in labelled.items()}

    # ---- geometry -----------------------------------------------------------
    W, H = 1560, max(660, 150 + 140 * len(order))
    PADL, PADR, PADT, PADB = 270, 60, 112, 56
    plotW, laneH = W - PADL - PADR, (H - PADT - PADB) / len(order)
    yrs = [p["year"] for p in papers.values()]
    YMIN = args.min_year if args.min_year else min(yrs) - 3
    YMAX = max(yrs) + 2
    n_pre = sum(1 for y in yrs if y < YMIN)   # older papers pinned to the axis (y-axis)

    # Density-equalizing time axis (optional): blend the linear position with the
    # empirical CDF of paper years so sparse early spans compress and dense recent
    # spans expand. warp=0 -> linear; warp=1 -> equal #papers per unit width.
    warp = max(0.0, min(1.0, args.time_warp))
    yrs_sorted = sorted(yrs)
    N = len(yrs_sorted) or 1

    def _cdf(y):  # midpoint rank of year y in the paper-year distribution
        return (bisect.bisect_left(yrs_sorted, y) + bisect.bisect_right(yrs_sorted, y)) / 2 / N
    _c0, _cspan = _cdf(YMIN), (_cdf(YMAX) - _cdf(YMIN)) or 1

    def _frac(y):
        y = max(YMIN, min(y, YMAX))
        lin = (y - YMIN) / (YMAX - YMIN)
        if warp <= 0:
            return lin
        return (1 - warp) * lin + warp * (_cdf(y) - _c0) / _cspan

    def xf(y): return PADL + _frac(y) * plotW
    def yf(f): return PADT + (LANE[f] + 0.5) * laneH

    # "big" = labelled milestones plus (optionally) every paper of an emphasized
    # source — those render as big circles; everything else is a small dot.
    emph = args.emphasize_source
    big = set(labelled)
    if emph:
        big |= {ref for ref, p in papers.items() if p.get("source") == emph}

    pos, bg = {}, []
    # small (non-big) -> beeswarm background
    for name in order:
        items = [(xf(p["year"]), ref) for ref, p in papers.items()
                 if p["family"] == name and ref not in big]
        for x, off, ref in beeswarm(items):
            pos[ref] = (x, yf(name) + off); bg.append(ref)
    # big -> lane centre (default spine) or a wider beeswarm when emphasizing a source
    for name in order:
        bigs = [ref for ref, p in papers.items() if p["family"] == name and ref in big]
        if emph:
            for x, off, ref in beeswarm([(xf(papers[r]["year"]), r) for r in bigs],
                                        r=7, step=12, maxoff=42):
                pos[ref] = (x, yf(name) + off)
        else:
            for r in bigs:
                pos[r] = (xf(papers[r]["year"]), yf(name))

    # Greedy multi-tier label placement. A label must clear BOTH other labels and
    # every big dot (with --emphasize-source the lane is full of big dots at
    # beeswarm offsets, so a label placed only by x-spacing can land on a dot —
    # e.g. "Gao 2015" under the Huth 2015 circle). Offsets are measured from each
    # label's own dot; tiers fan outward so labels migrate clear of the dot band.
    TIERS = [-18, 19, -33, 34, -49, 50, -66, 67, -84, 85, -103, 104]
    big_dots = [pos[r] for r in big]              # (x, y) of every big circle
    loff, placed_lbl = {}, []                     # placed_lbl: label bounding boxes
    for name in order:
        lane = sorted(((ref, pos[ref]) for ref in labelled if papers[ref]["family"] == name),
                      key=lambda t: t[1][0])
        for ref, (x, dy) in lane:
            w = len(labelled[ref]) * 6.2 + 8
            pick = TIERS[-1]
            for o in TIERS:
                ly = dy + o
                box = (x - w / 2, x + w / 2, ly - 8, ly + 6)
                if any(_boxes_overlap(box, b) for b in placed_lbl):
                    continue
                if any(not (abs(bx - x) < 0.5 and abs(by - dy) < 0.5)  # ignore own dot
                       and _box_hits_dot(box, bx, by) for bx, by in big_dots):
                    continue
                pick = o
                break
            loff[ref] = pick
            ly = dy + pick
            placed_lbl.append((x - w / 2, x + w / 2, ly - 8, ly + 6))

    # ---- SVG ----------------------------------------------------------------
    s = [f'<svg id="fig" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
         'font-family="Helvetica,Arial,sans-serif">',
         '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" '
         'orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="#444"/></marker></defs>',
         f'<rect width="{W}" height="{H}" fill="white"/>',
         f'<text x="10" y="34" font-size="22" font-weight="bold" fill="#222">{esc(args.title)}</text>']
    for j, ln in enumerate(wrap(subtitle, 150)[:2]):
        s.append(f'<text x="10" y="{56+j*18}" font-size="12.5" fill="#555">{esc(ln)}</text>')

    for name in order:
        y, top, c = yf(name), yf(name) - laneH / 2, COLOR[name]
        s.append(f'<rect x="{PADL}" y="{top:.0f}" width="{plotW}" height="{laneH:.0f}" '
                 f'fill="{c}" opacity="0.05"/>')
        s.append(f'<line x1="{PADL}" y1="{y:.0f}" x2="{W-PADR}" y2="{y:.0f}" stroke="{c}" opacity="0.25"/>')
        s.append(f'<g class="lanelabel" data-fam="{esc(name)}">')
        ly = top + 20
        for ln in wrap(name, 24):                       # wrap long theme names onto multiple lines
            s.append(f'<text x="10" y="{ly:.0f}" font-size="14" font-weight="bold" fill="{c}">{esc(ln)}</text>')
            ly += 15
        ly += 4
        for ln in wrap(claim[name], 42):
            s.append(f'<text x="10" y="{ly:.0f}" font-size="9.5" fill="{c}" opacity="0.85">{esc(ln)}</text>')
            ly += 12
        s.append('</g>')

    # x axis. A warped axis bunches early decades, so consider 5-year candidates and
    # greedily drop any label that would collide with the previous one (kept >=34px
    # apart). A faint gridline marks each drawn tick so the nonlinear scale is legible.
    span = YMAX - YMIN
    step = 5 if (warp > 0 or span <= 40) else 10
    cand = list(range(((YMIN + step - 1) // step) * step, YMAX + 1, step))
    drawn_x = -1e9
    for t in cand:
        x = xf(t)
        if x - drawn_x < 34:
            continue
        drawn_x = x
        if warp > 0:
            s.append(f'<line x1="{x:.0f}" y1="{PADT:.0f}" x2="{x:.0f}" y2="{H-PADB:.0f}" '
                     f'stroke="#000" stroke-opacity="0.04"/>')
        s.append(f'<text x="{x:.0f}" y="{H-PADB+22:.0f}" text-anchor="middle" font-size="12" fill="#555">{t}</text>')
    if n_pre:   # note the older papers pinned to the left edge (the y-axis)
        s.append(f'<text x="{PADL:.0f}" y="{H-PADB+34:.0f}" text-anchor="middle" font-size="9.5" '
                 f'fill="#999">{n_pre} pre-{YMIN}</text>')

    data = {}
    # background dots
    for ref in bg:
        p = papers[ref]; x, y = pos[ref]; data[ref] = p
        s.append(f'<g class="node bg" data-key="{ref}" tabindex="0"><title>{esc(p["apa"])}</title>'
                 f'<circle class="hit" cx="{x:.0f}" cy="{y:.0f}" r="9" fill="none" pointer-events="all"/>'
                 f'<circle cx="{x:.0f}" cy="{y:.0f}" r="2.4" fill="{COLOR[p["family"]]}"/></g>')
    # editorial arrows + notes (optional)
    for a in spec.get("arrows", []):
        if a.get("from") in pos and a.get("to") in pos:
            (x1, y1), (x2, y2) = pos[a["from"]], pos[a["to"]]
            col = a.get("color", "#444")
            s.append(f'<path d="M{x1:.0f},{y1:.0f} Q{(x1+x2)/2:.0f},{(y1+y2)/2-40:.0f} {x2:.0f},{y2:.0f}" '
                     f'fill="none" stroke="{col}" stroke-width="1.4" marker-end="url(#arrow)" opacity="0.9"/>')
            if a.get("label"):
                s.append(f'<text x="{(x1+x2)/2:.0f}" y="{(y1+y2)/2-44:.0f}" text-anchor="middle" '
                         f'font-size="10.5" fill="{col}">{esc(a["label"])}</text>')
    for nt in spec.get("notes", []):
        if nt.get("at") in pos:
            x, y = pos[nt["at"]]
            s.append(f'<text x="{x:.0f}" y="{y-12:.0f}" text-anchor="middle" font-size="10.5" '
                     f'fill="{nt.get("color","#333")}">{esc(nt["text"])}</text>')
    # big nodes (labelled milestones + any emphasized source) on top; labelled
    # ones also get a leader line + text label
    for ref in sorted(big, key=lambda r: papers[r]["year"]):
        p = papers[ref]; x, y = pos[ref]; data[ref] = p
        is_lab = ref in lab
        rr = (9.5 if is_lab else 8.5) if ref in labelled else 7
        stroke, sw = ("#d4a017", 2.6) if is_lab else ("#fff", 1.2)   # home-lab -> gold ring
        leader = label = ""
        if ref in labelled:
            off = loff[ref]
            ly1, ly2 = (y - 7, y + off + 1) if off < 0 else (y + 7, y + off - 9)
            leader = (f'<line x1="{x:.0f}" y1="{ly1:.0f}" x2="{x:.0f}" y2="{ly2:.0f}" '
                      f'stroke="{COLOR[p["family"]]}" stroke-width="1" opacity="0.65"/>')
            label = (f'<text class="lbl" x="{x:.0f}" y="{y+off:.0f}" text-anchor="middle" '
                     f'font-size="11" font-weight="bold" fill="{"#9a7400" if is_lab else "#222"}">'
                     f'{esc(labelled[ref])}</text>')
        s.append(f'{leader}<g class="node spine" data-key="{ref}" tabindex="0">'
                 f'<title>{esc(p["apa"])}</title>'
                 f'<circle class="hit" cx="{x:.0f}" cy="{y:.0f}" r="12" fill="none" pointer-events="all"/>'
                 f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rr}" fill="{COLOR[p["family"]]}" '
                 f'stroke="{stroke}" stroke-width="{sw}"/>{label}</g>')
    s.append('</svg>')
    svg = "".join(s)

    # optional embedded xlsx download button (base64 data URI -> works offline)
    xlsx_btn = ""
    if args.xlsx and os.path.exists(args.xlsx):
        b64 = base64.b64encode(open(args.xlsx, "rb").read()).decode()
        xlsx_btn = (f'<a class="dl" download="{esc(os.path.basename(args.xlsx))}" '
                    f'href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;'
                    f'base64,{b64}">⬇ Download table (.xlsx)</a>')

    # `<\/` so a "</script>" inside any apa can't terminate the inline <script>
    def js_json(o): return json.dumps(o).replace("</", "<\\/")
    doc = HTML_SHELL.replace("__TITLE__", esc(args.title)).replace("__SVG__", svg)\
        .replace("__XLSXBTN__", xlsx_btn)\
        .replace("__DATA__", js_json(data)).replace("__COLOR__", js_json(COLOR))

    base = args.out_prefix
    with open(base + ".html", "w", encoding="utf-8") as f:
        f.write(doc)
    with open(base + ".svg", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n' + svg)
    made = ["html", "svg"]
    conv = None if args.no_raster else (shutil.which("rsvg-convert") or shutil.which("inkscape"))
    if conv and conv.endswith("rsvg-convert"):
        for fmt, extra in (("png", ["-z", "2"]), ("pdf", [])):
            subprocess.run([conv, "-f", fmt, *extra, "-o", f"{base}.{fmt}", base + ".svg"], check=True)
            made.append(fmt)
    elif conv:  # inkscape — different CLI
        for fmt in ("png", "pdf"):
            subprocess.run([conv, base + ".svg", "--export-type=" + fmt,
                            f"--export-filename={base}.{fmt}"], check=True)
            made.append(fmt)
    print(f"wrote {base}.{{{','.join(made)}}}  "
          f"({len(bg)} dots + {len(big)} big ({len(labelled)} labelled) across {len(order)} families)")


HTML_SHELL = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
 *{box-sizing:border-box;} body{margin:0;font-family:Helvetica,Arial,sans-serif;color:#222;
   display:flex;flex-direction:column;height:100vh;}
 header{padding:8px 16px;} .sub{color:#666;font-size:12.5px;}
 main{flex:1;display:flex;min-height:0;}
 #figwrap{flex:1;min-width:0;overflow:auto;padding:6px 10px;}
 #fig{width:100%;height:auto;display:block;}
 .node{cursor:pointer;} .node.bg circle:not(.hit){opacity:.38;}
 .node.bg:hover circle:not(.hit),.node.bg:focus circle:not(.hit){r:6;opacity:1;}
 .node.spine:hover circle:not(.hit),.node.spine:focus circle:not(.hit){r:11;}
 .node:hover .lbl{fill:#000;} .node.sel circle:not(.hit){stroke:#000;stroke-width:2.6px;opacity:1;}
 .dim{opacity:.1;transition:opacity .15s;}
 aside{width:340px;border-left:1px solid #e5e5e5;padding:16px 18px;overflow:auto;font-size:13.5px;line-height:1.45;}
 #fam{display:inline-block;padding:2px 9px;border-radius:11px;color:#fff;font-size:12px;font-weight:bold;}
 #apa{margin:12px 0;} #meta{color:#666;font-size:12.5px;}
 #summary{margin:10px 0;color:#333;font-size:12.5px;line-height:1.5;}
 a.doi{display:inline-block;margin-top:12px;padding:7px 13px;background:#1b6ca8;color:#fff;border-radius:6px;text-decoration:none;font-size:13px;}
 a.doi.off{background:#bbb;pointer-events:none;} .hint{color:#999;}
 #close{float:right;border:none;background:#eee;border-radius:50%;width:24px;height:24px;font-size:16px;cursor:pointer;color:#444;}
 a.dl{float:right;margin-left:12px;padding:5px 11px;background:#217346;color:#fff;border-radius:6px;text-decoration:none;font-size:12.5px;}
</style></head><body>
<header>__XLSXBTN__<div class="sub">Hover a node for its citation + summary; click it to pin the citation + DOI.
 Hover a family's name at left to spotlight its lineage.</div></header>
<main><div id="figwrap">__SVG__</div>
<aside id="panel"><div class="hint">Click any node to see its full reference here.</div></aside></main>
<script>
const DATA=__DATA__, FAMCOLOR=__COLOR__, panel=document.getElementById('panel');
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>(
 {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function resetPanel(){document.querySelectorAll('.node.sel').forEach(n=>n.classList.remove('sel'));
 panel.innerHTML='<div class="hint">Click any node to see its full reference here.</div>';}
function show(k){const d=DATA[k];if(!d)return;
 document.querySelectorAll('.node.sel').forEach(n=>n.classList.remove('sel'));
 const g=document.querySelector('.node[data-key="'+CSS.escape(k)+'"]');if(g)g.classList.add('sel');
 const url=(d.doi||'').startsWith('http')?d.doi:'';
 const doi=url?'<a class="doi" href="'+esc(url)+'" target="_blank" rel="noopener">Open paper \\u2197</a>':'<a class="doi off">no DOI</a>';
 const c=[];if(Number.isInteger(d.oa))c.push(d.oa+' (OpenAlex)');if(Number.isInteger(d.s2))c.push(d.s2+' (S2)');
 panel.innerHTML='<button id="close" onclick="resetPanel()">\\u00d7</button>'
  +'<div id="fam" style="background:'+esc(FAMCOLOR[d.family]||'#666')+'">'+esc(d.family)+'</div> <span id="meta">'+esc(d.ref)+' \\u00b7 '+esc(d.topic)+'</span>'
  +'<div id="apa">'+esc(d.apa)+'</div>'+(d.summary?'<div id="summary">'+esc(d.summary)+'</div>':'')+(c.length?'<div id="meta">Cited by: '+esc(c.join(' \\u00b7 '))+'</div>':'')+doi;}
document.querySelectorAll('.node').forEach(g=>{g.addEventListener('click',()=>show(g.dataset.key));
 g.addEventListener('mouseenter',()=>show(g.dataset.key));
 g.addEventListener('focus',()=>show(g.dataset.key));
 g.addEventListener('keydown',e=>{if(e.key==='Enter')show(g.dataset.key);});});
document.querySelectorAll('.lanelabel').forEach(g=>{const f=g.dataset.fam;
 g.addEventListener('mouseenter',()=>document.querySelectorAll('.node').forEach(n=>{if(DATA[n.dataset.key].family!==f)n.classList.add('dim');}));
 g.addEventListener('mouseleave',()=>document.querySelectorAll('.node').forEach(n=>n.classList.remove('dim')));});
</script></body></html>"""


if __name__ == "__main__":
    main()
