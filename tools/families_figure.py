#!/usr/bin/env python3
"""Phase 6b — render the interactive HTML lineage figure of the theoretical families.

Self-contained single .html (inline SVG + CSS + JS, no deps, no network) plus a
standalone .svg and, if rsvg-convert/inkscape is present, .png + .pdf. Replaces
the old static matplotlib figure.

Open in a browser, present fullscreen. Hover any node -> full reference
(tooltip); click -> side panel with citation + a live DOI link; hover or focus a
family's NAME -> a panel giving that family's claim and its lineage in full, plus
its paper count, while its papers are spotlighted. (families.json has always
carried `claim` and `lineage`; until 2026-09-18 the figure drew only a truncated
claim beside the lane and the lineage was invisible, so a reader had to open
families.md to learn what a family meant. The exported .svg/.png/.pdf carry the
same text in a native SVG <title>, since no script runs out there.)
The panel also carries Prev/Next buttons (and
binds the left/right arrow keys) that step through the papers in year order, so a
reader can walk the timeline instead of hunting for individual dots; a checkbox
switches between stepping within the selected family and across the whole corpus.

Data-driven: family lanes come from families.json, dots from rows.json (one per
paper, beeswarm-packed by year within its lane).

LANDMARKS are auto-selected and labeled (big dots) — no hand-made overlay needed.
A paper is a landmark if ANY of:
  (1) it is among the most-cited in its family (top --per-family by max(OpenAlex, S2)),
  (2) it is foundational *within this review* — cited by >= --motif-min of the corpus's
      own papers (needs --internal internal_citations.json from `xref.py --internal-out`;
      silently skipped if not supplied),
  (3) it is a home-lab paper — an author surname listed in --lab-author or the
      LITREVIEW_LAB_AUTHOR env var (home-lab favoring is OFF by default), or a row
      with source == "lab" — these are starred (★) and ringed in --lab-color
      (default gold, moved automatically if it clashes with a family lane).
Total labels are capped at --max-labels for legibility. When the cap bites, what is
guaranteed to survive is the home-lab papers plus the top-2 most-cited per family;
the rest of the budget is filled by within-review in-degree. Internal-motif papers
are NOT all kept — on a large, densely inter-citing corpus hundreds of papers can
clear --motif-min, so the cap is what keeps the figure readable. The number dropped
is reported on every run; raise --max-labels or --motif-min if it is large.
Pass --spec with a "labels" map to override auto-selection entirely (manual curation wins);
--no-auto-landmarks turns labeling off.

DOT SIZE is binary by default — big = labeled landmark, small = everything else —
so the figure says nothing about how much a paper is actually cited.
--size-by-citations {log,sqrt} replaces that with a continuous scale and adds a
size legend; landmark status then rides entirely on the ring, leader and label.
Counts span four orders of magnitude in a real corpus (0 to ~24k), so both modes
normalize against the 95th percentile and clamp above it; `sqrt` is
area-proportional and separates the heavy tail, `log` compresses harder and
reads flatter. Read the result with the obvious caveat in mind: citation count
is partly an AGE variable, so the right-hand edge of any timeline will be small.

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
import argparse
import base64
import bisect
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import Counter

import common

PHASE = "6b"   # pipeline phase, read by tools/gen_docs.py for the tool index

PALETTE = ["#1b6ca8", "#2a9d8f", "#e76f51", "#8338ec", "#d4a017", "#6c757d",
           "#c1121f", "#177e89", "#7209b7", "#bc6c25"]


def esc(s): return html.escape(str(s), quote=True)
# The year and lead surname come from the shared APA grammar (common.parse_apa),
# so the figure agrees with the audit gate about what a parseable year is — a
# private regex here once required a bare (YYYY) and silently dropped every
# 2025a-suffixed paper from the plot.
year_of = common.year_of
lead = common.lead_surname


def wrap(text, n=40):
    out, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > n:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


# Ring colors to fall back to when the requested one is already a family lane's
# color. Ordered by how loudly they read against the palette; none is in PALETTE.
LAB_RING_FALLBACKS = ["#111111", "#00a5cf", "#ff006e", "#7f4f24", "#006400"]


def darken(color, factor):
    """Scale a #rrggbb toward black. Used for the starred label's ink.

    The label ink was a second hardcoded constant (#9a7400, a darker gold), so
    setting the ring color left the label in the old color. Deriving it means one
    parameter controls both.
    """
    factor = max(0.0, min(1.0, factor))
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(int(round(v * factor)) for v in (r, g, b))


def lab_ring_color(requested, lane_colors, explicit=False):
    """Pick the home-lab ring color; return (color, note-or-None).

    The ring marks a home-lab paper by outlining its dot. If the ring color is
    the SAME as the color that dot is filled with — which is exactly what
    happened, because the default gold #d4a017 is also PALETTE[4] — the ring is
    invisible and the whole highlight silently does nothing for every lab paper
    in the fifth family.

    An explicitly requested color is honored (the operator may be matching a
    brand) but still reported. An un-asked-for default is moved out of the way.
    """
    used = {c.lower() for c in lane_colors}
    if requested.lower() not in used:
        return requested, None
    if explicit:
        return requested, (f"--lab-color {requested} is also a family lane color — "
                           f"home-lab rings will be invisible on that lane's dots")
    for alt in LAB_RING_FALLBACKS:
        if alt.lower() not in used:
            return alt, (f"the default home-lab ring {requested} is also a family lane "
                         f"color, so it would be invisible there; using {alt} instead "
                         f"(set --lab-color to choose your own)")
    return requested, f"every fallback ring color is in use; keeping {requested}"


def radius_scale(mode, cites, r_min, r_max, ref_pct=95):
    """Build value -> radius for --size-by-citations.

    Citation counts in a real corpus span four orders of magnitude (0 to ~24k),
    so the naive mappings both fail: radius-proportional makes the top paper 100x
    the width of the median, and area-proportional against the MAXIMUM squashes
    the whole bulk into the bottom sixth of the range. Both modes here therefore
    normalize against a high percentile (`ref_pct`) and clamp above it, so one
    runaway classic cannot flatten the rest of the figure.

      "log"  — r rises with log1p(c). Compresses the tail hardest; separates the
               10-vs-100-vs-1000 band a reader actually needs to tell apart.
      "sqrt" — area-proportional, the perceptually honest encoding: a dot with
               4x the area has 4x the citations, up to the clamp.

    A missing count (< 0) draws at the floor, same as an uncited paper — the
    figure must not imply a count it does not have.
    """
    vals = sorted(c for c in cites if isinstance(c, int) and c >= 0)
    ref = vals[min(len(vals) - 1, int(len(vals) * ref_pct / 100))] if vals else 1
    ref = max(ref, 1)
    span = r_max - r_min
    if mode == "sqrt":
        def t(c): return math.sqrt(max(0, c) / ref)
    else:
        denom = math.log1p(ref)
        def t(c): return math.log1p(max(0, c)) / denom

    def radius(c):
        if not isinstance(c, (int, float)) or c < 0:
            return r_min
        return r_min + span * min(1.0, t(c))
    return radius


def beeswarm(items, r=2.7, step=5.6, maxoff=52, radius=None):
    """Pack (x, payload) into vertical offsets within a lane.

    With `radius=None` every dot is the same size and the fixed-lattice packing
    below is exact. `radius` (payload -> r) turns on variable-size packing: the
    fixed lattice is then WRONG, because it tests every pair against a constant
    2r, so an 11px dot and a 2px dot sitting 5.6px apart on the lattice overlap.
    In that mode each dot is tried against the real circle geometry of the dots
    already placed, scanning outward in fine increments for the first clear slot.
    """
    placed, out = [], []
    if radius is not None:
        crowded = 0
        for x, payload in sorted(items, key=lambda t: t[0]):
            rr = radius(payload)
            off, best = None, None
            for cand in _offsets(maxoff):
                # How deep does this slot bury the dot in its neighbors? 0 = clear.
                pen = sum(max(0.0, (rr + pr + 0.7) - math.hypot(x - px, cand - po))
                          for px, po, pr in placed)
                if pen == 0:
                    off = cand
                    break
                if best is None or pen < best[0]:
                    best = (pen, cand)
            if off is None:
                # Every slot in the lane is taken. Falling back to 0 would drop the
                # dot dead center, on top of everything — the worst slot, not the
                # best. Take the least-buried one, the same way label placement
                # degrades to the least-overlapping tier.
                off, crowded = best[1], crowded + 1
            placed.append((x, off, rr))
            out.append((x, off, payload))
        if crowded:
            print(f"  beeswarm: {crowded} dot(s) had no clear slot in the lane and took "
                  f"the least-overlapping one (lane is full at +/-{maxoff}px)", file=sys.stderr)
        return out
    for x, payload in sorted(items, key=lambda t: t[0]):
        off, k = 0, 1
        while any(abs(x - px) < 2 * r + 0.6 and abs(off - po) < 2 * r + 0.6 for px, po in placed):
            off = step * ((k + 1) // 2) * (1 if k % 2 else -1)
            if abs(off) > maxoff:
                break
            k += 1
        placed.append((x, off))
        out.append((x, off, payload))
    return out


def _offsets(maxoff, inc=1.5):
    """0, +inc, -inc, +2inc, ... out to maxoff — the candidate slots a dot tries."""
    yield 0.0
    n = 1
    while n * inc <= maxoff:
        yield n * inc
        yield -n * inc
        n += 1


def _boxes_overlap(a, b):
    """a, b = (x0, x1, y0, y1). True if the two rectangles intersect."""
    return not (a[1] < b[0] or a[0] > b[1] or a[3] < b[2] or a[2] > b[3])


def _overlap_area(a, b):
    """Intersection area of two (x0, x1, y0, y1) boxes; 0.0 if they miss.

    Used to rank tiers when EVERY candidate slot for a label is already taken:
    the placement then degrades to the least-bad slot rather than an arbitrary
    one. Touching edges count as no overlap, matching _boxes_overlap."""
    dx = min(a[1], b[1]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[2], b[2])
    return float(dx * dy) if dx > 0 and dy > 0 else 0.0


def num(v):
    """Shortest exact-looking form of a coordinate: 9.0 -> "9", 2.40 -> "2.4".

    Radii became floats when --size-by-citations landed; without this every
    figure rendered WITHOUT the flag would churn (r="9" -> r="9.0") and the
    re-render harness's byte-comparison against the delivered SVG would go red
    on a change that moves nothing.
    """
    return f"{float(v):.2f}".rstrip("0").rstrip(".") or "0"


def size_legend(rad, cites, x_right, y_base, r_max, n_unknown=0):
    """A row of circles keying dot size to citation count.

    A size encoding with no key is decoration: the reader can see that one dot
    is bigger without being able to say how much more cited it is. Ticks are
    round numbers, kept only when they are at least 1.3px apart in radius (on a
    log scale 1 and 3 citations draw the same dot, and two identical circles
    labeled differently is worse than one), and the largest is marked "+"
    because the scale clamps above its reference percentile.
    """
    top = max([c for c in cites if isinstance(c, int) and c >= 0] or [0])
    cand = [0, 1, 3, 10, 30, 100, 300, 1000, 3000, 10000, 30000, 100000]
    cand = [c for c in cand if c <= top] or [0]
    ticks, last = [], None
    for c in cand:
        r = rad(c)
        if last is None or r - last >= 1.3:
            ticks.append(c)
            last = r
    ticks = ticks[-5:]
    # "+" on the top tick whenever papers sit ABOVE it — either because the
    # scale clamps there or because the tick is simply the largest round number
    # below the top of the data. Keying it to the radius alone let the log scale
    # print a bare "1,000" on a corpus whose most-cited paper had 13,923.
    clamped = bool(ticks) and (top > ticks[-1] or rad(ticks[-1]) >= r_max - 1e-9)

    out, pitch = [], 2 * r_max + 16
    x = x_right - pitch * (len(ticks) - 1)
    out.append(f'<text x="{x - r_max - 8:.0f}" y="{y_base - 2 * r_max - 8:.0f}" '
               f'font-size="10.5" fill="#777">dot size = times cited</text>')
    for i, c in enumerate(ticks):
        r = rad(c)
        cx = x + i * pitch
        out.append(f'<circle cx="{cx:.0f}" cy="{y_base - r:.1f}" r="{num(r)}" fill="none" '
                   f'stroke="#9a9a9a" stroke-width="1.1"/>')
        lab = f"{c:,}" + ("+" if (i == len(ticks) - 1 and clamped) else "")
        out.append(f'<text x="{cx:.0f}" y="{y_base + 13:.0f}" text-anchor="middle" '
                   f'font-size="9.5" fill="#777">{lab}</text>')
    if n_unknown:
        cy = y_base + 26
        hx = x_right - pitch * (len(ticks) - 1)
        out.append(f'<circle cx="{hx:.0f}" cy="{cy - 3:.0f}" r="3" fill="none" '
                   f'stroke="#9a9a9a" stroke-width="1.1"/>')
        out.append(f'<text x="{hx + 7:.0f}" y="{cy:.0f}" font-size="9.5" fill="#777">'
                   f'hollow = no count ({n_unknown})</text>')
    return "".join(out)


def _box_hits_dot(box, dx, dy, margin=11):
    """True if a dot at (dx, dy) falls within `margin` of the label box."""
    return box[0] - margin <= dx <= box[1] + margin and box[2] - margin <= dy <= box[3] + margin


def claim_lines(claim, width, max_lines):
    """Wrap `claim` to `width`, clamped to `max_lines` and ellipsized if it did
    not fit.

    The lane label draws the family's claim under its name. Nothing used to bound
    how many lines that was, so a long claim ran straight through the next
    family's title — a real collision on any spec whose claims are written as
    prose. The full text is one hover away (the #famtip panel, and the lane's
    native <title> in the exported SVG), so the drawn copy only has to say enough
    to identify the family."""
    if max_lines <= 0:
        return []
    lines = wrap(claim or "", width)
    if len(lines) <= max_lines:
        return lines
    lines = lines[:max_lines]
    lines[-1] = lines[-1].rstrip(" ,;:.") + "\u2026"
    return lines


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
                    help="disable automatic landmark labeling (default: on when --spec has no labels)")
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
                         "(repeatable). OFF by default; also settable via the "
                         "LITREVIEW_LAB_AUTHOR env var (comma-separated), which this flag "
                         "overrides. Rows with source=='lab' are always starred.")
    ap.add_argument("--lab-color", default=None, metavar="HEX",
                    help="color of the home-lab ring and its starred label "
                         "(default #d4a017, gold). Set it to your group's own color. "
                         "If the color is also one of the family lane colors the ring "
                         "would be invisible on that lane, so an unset default is moved "
                         "out of the way automatically and an explicit one is warned about.")
    ap.add_argument("--size-by-citations", choices=("log", "sqrt"), default=None,
                    metavar="SCALE",
                    help="size every dot by its citation count instead of by landmark "
                         "status: 'log' compresses the heavy tail (best for a corpus "
                         "spanning 0-20k citations), 'sqrt' is area-proportional. Both "
                         "normalize against the 95th percentile and clamp above it, and "
                         "the figure gains a size legend. Landmarks stay distinguished "
                         "by their ring and label. Default: off (binary big/small dots).")
    ap.add_argument("--size-range", default="2.0,11.0", metavar="MIN,MAX",
                    help="dot radius range in px for --size-by-citations (default 2.0,11.0)")
    args = ap.parse_args()

    load = common.load_json
    rows = load(args.rows)
    fam_spec = load(args.families)
    spec = load(args.spec) if args.spec else {}

    fams = fam_spec["families"]
    order = spec.get("order") or [f["name"] for f in fams]
    claim = {f["name"]: f.get("claim", "") for f in fams}
    lineage = {f["name"]: f.get("lineage", "") for f in fams}
    famkey = {f["name"]: f.get("key", "") for f in fams}
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

    # ---- landmark (big, labeled) selection --------------------------------
    # Home-lab detection (criterion 3): author surname match or source=="lab".
    # OFF by default so this shared tool is lab-neutral. Opt in per project with
    # --lab-author SURNAME (repeatable) or the LITREVIEW_LAB_AUTHOR env var
    # (comma-separated surnames); the CLI flag wins over the env var.
    lab_surnames = ([s for s in args.lab_author if s.strip()]
                    or [s.strip() for s in os.environ.get("LITREVIEW_LAB_AUTHOR", "").split(",")
                        if s.strip()])

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
        labeled = {ref: lab for ref, lab in spec["labels"].items() if ref in papers}
    elif any("★" in ref for ref in papers):
        labeled = {ref: lead(p["apa"]) for ref, p in papers.items() if "★" in ref}
    elif args.no_auto_landmarks:
        labeled = {}
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
            qualified = len(chosen)
            chosen = keep | set(pool[:max(0, args.max_labels - len(keep))])
            # Never truncate silently: a capped figure otherwise reads as "these are
            # all the landmarks" when it is really "these are the first N of many".
            print(f"  landmarks: {qualified} papers qualified, {len(chosen)} labeled "
                  f"({qualified - len(chosen)} dropped by --max-labels {args.max_labels}). "
                  f"Raise --max-labels or --motif-min (currently {args.motif_min}) to change this.",
                  file=sys.stderr)
        labeled = {ref: f'{lead(papers[ref]["apa"]).strip()} {papers[ref]["year"]}' for ref in chosen}

    # Home-lab ring color. Resolved against the lane colors actually in use, so a
    # lab paper's ring can never be the same color as the dot it outlines.
    _req = args.lab_color or "#d4a017"
    LAB_RING, _ring_note = lab_ring_color(_req, [COLOR[n] for n in order],
                                          explicit=bool(args.lab_color))
    LAB_INK = darken(LAB_RING, 0.72)
    if _ring_note and lab:
        print(f"  home-lab ring: {_ring_note}", file=sys.stderr)

    # star home-lab papers in their label (auto or manual), so they read as the lab's own
    labeled = {ref: (("★ " + t) if (ref in lab and not t.startswith("★")) else t)
                for ref, t in labeled.items()}

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

    # "big" = labeled milestones plus (optionally) every paper of an emphasized
    # source — those render as big circles; everything else is a small dot.
    emph = args.emphasize_source
    big = set(labeled)
    if emph:
        big |= {ref for ref, p in papers.items() if p.get("source") == emph}

    # ---- dot size -----------------------------------------------------------
    # Default: size is BINARY — a big dot is a labeled landmark, a small dot is
    # everything else, so the figure says nothing about how much a paper is
    # actually cited. --size-by-citations replaces that with a continuous scale.
    # Landmark status does not disappear; it moves entirely onto the ring, the
    # leader line and the label, which is where it already half lived.
    LANDMARK_FLOOR = 4.5      # a 2px dot cannot carry a 2.6px gold ring legibly
    size_mode = args.size_by_citations
    try:
        R_MIN, R_MAX = (float(v) for v in args.size_range.split(","))
    except ValueError:
        sys.exit("families_figure: --size-range wants MIN,MAX (e.g. 2.0,11.0)")
    if size_mode:
        _scale = radius_scale(size_mode, [_cites(p) for p in papers.values()], R_MIN, R_MAX)
        def rad_of(ref, landmark=False):
            r = _scale(_cites(papers[ref]))
            return max(r, LANDMARK_FLOOR) if landmark else r
        n_clamped = sum(1 for p in papers.values() if _scale(_cites(p)) >= R_MAX - 1e-9)
        print(f"  dot size: {size_mode} scale on citation counts, r {R_MIN}-{R_MAX}px "
              f"({n_clamped} paper(s) at the ceiling)", file=sys.stderr)
    else:
        def rad_of(ref, landmark=False):
            return 2.4

    pos, bg = {}, []
    # small (non-big) -> beeswarm background
    for name in order:
        items = [(xf(p["year"]), ref) for ref, p in papers.items()
                 if p["family"] == name and ref not in big]
        # Variable radii need the packer to know each dot's own size, or an 11px
        # dot and a 2px dot land on the same fixed lattice and overlap.
        swarm = beeswarm(items, radius=rad_of) if size_mode else beeswarm(items)
        for x, off, ref in swarm:
            pos[ref] = (x, yf(name) + off)
            bg.append(ref)
    # big -> lane center (default spine) or a wider beeswarm when emphasizing a source
    for name in order:
        bigs = [ref for ref, p in papers.items() if p["family"] == name and ref in big]
        if emph:
            for x, off, ref in beeswarm([(xf(papers[r]["year"]), r) for r in bigs],
                                        r=7, step=12, maxoff=42,
                                        radius=(lambda r: rad_of(r, True)) if size_mode else None):
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
    # (x, y, r) of every big circle — a label has to clear the dot's real edge,
    # which under --size-by-citations is anywhere from 4.5px to 11px.
    big_dots = [(pos[r][0], pos[r][1], rad_of(r, True)) for r in big]
    loff, placed_lbl = {}, []                     # placed_lbl: label bounding boxes
    for name in order:
        # (x, ref) again: `labeled` is keyed off a set, so sorting on x alone let
        # two labels at the same x swap places between runs, and greedy tier
        # placement is order-dependent — the same figure came out with different
        # label offsets each render.
        lane = sorted(((ref, pos[ref]) for ref in labeled if papers[ref]["family"] == name),
                      key=lambda t: (t[1][0], t[0]))
        for ref, (x, dy) in lane:
            w = len(labeled[ref]) * 6.2 + 8
            # Track the least-bad tier as we go: in a crowded lane every slot can
            # be taken, and falling back to a fixed tier drops the label on top of
            # one already placed. Rank the misses by overlap area instead.
            pick, best_pen = None, None
            for o in TIERS:
                ly = dy + o
                box = (x - w / 2, x + w / 2, ly - 8, ly + 6)
                pen = sum(_overlap_area(box, b) for b in placed_lbl)
                pen += sum(60.0 for bx, by, br in big_dots
                           if not (abs(bx - x) < 0.5 and abs(by - dy) < 0.5)
                           and _box_hits_dot(box, bx, by, margin=max(11.0, br + 3)))
                if pen == 0:
                    pick = o
                    break
                if best_pen is None or pen < best_pen:
                    pick, best_pen = o, pen
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
    if size_mode:
        s.append(f'<g id="sizelegend">'
                 + size_legend(lambda c: _scale(c), [_cites(p) for p in papers.values()],
                               W - PADR, PADT - 30, R_MAX,
                               sum(1 for p in papers.values() if _cites(p) < 0))
                 + '</g>')

    for name in order:
        y, top, c = yf(name), yf(name) - laneH / 2, COLOR[name]
        s.append(f'<rect x="{PADL}" y="{top:.0f}" width="{plotW}" height="{laneH:.0f}" '
                 f'fill="{c}" opacity="0.05"/>')
        s.append(f'<line x1="{PADL}" y1="{y:.0f}" x2="{W-PADR}" y2="{y:.0f}" stroke="{c}" opacity="0.25"/>')
        s.append(f'<g class="lanelabel" tabindex="0" data-fam="{esc(name)}">')
        # Native SVG tooltip: the exported .svg/.png/.pdf carry no script, so the
        # family's claim and lineage have to travel inside the graphic itself.
        # Stripped out of the HTML build below, where the styled #famtip replaces it.
        tip = name + (" — " + claim[name] if claim[name] else "")
        if lineage[name]:
            tip += "\n\nLineage: " + lineage[name]
        s.append(f'<title class="lanetitle">{esc(tip)}</title>')
        # Invisible hit target. A <g> has no geometry and <text> is only hit on its
        # glyph strokes, so without this the hover fires exactly on a letter and
        # nowhere else — the same reason every node group carries a `hit` circle.
        # Covers the whole left-margin band for this lane, stopping short of the
        # plot area so it cannot steal events from the dots.
        s.append(f'<rect class="hit" x="0" y="{top:.0f}" width="{PADL - 8}" '
                 f'height="{laneH:.0f}" fill="none" pointer-events="all"/>')
        ly = top + 20
        for ln in wrap(name, 24):                       # wrap long theme names onto multiple lines
            s.append(f'<text x="10" y="{ly:.0f}" font-size="14" font-weight="bold" fill="{c}">{esc(ln)}</text>')
            ly += 15
        ly += 4
        # Stay inside this lane: whatever vertical room is left below the name,
        # at the 12px line pitch, minus one line of breathing space.
        budget = max(0, int((top + laneH - ly) / 12) - 1)
        for ln in claim_lines(claim[name], 42, budget):
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
    # background dots. Under --size-by-citations these vary from 2px to 11px, so
    # draw the largest FIRST (they go to the back) and give every dot a thin
    # surface ring — without it two overlapping same-family dots read as one
    # blob and the size encoding is lost exactly where the swarm is densest.
    for ref in sorted(bg, key=lambda r: -rad_of(r)) if size_mode else bg:
        p = papers[ref]
        x, y = pos[ref]
        rr = rad_of(ref)
        # An unknown citation count is NOT a count of zero. Sized at the floor it
        # would be indistinguishable from a genuinely uncited paper, so the figure
        # would be asserting a number it does not have — on reverse_polish_notation
        # that is a third of the corpus. Draw those hollow instead.
        if size_mode and _cites(p) < 0:
            body = (f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{num(rr)}" fill="none" '
                    f'stroke="{COLOR[p["family"]]}" stroke-width="1.1" stroke-opacity="0.75"/>')
        else:
            ring = ' stroke="#fff" stroke-width="0.9" stroke-opacity="0.85"' if size_mode else ''
            body = (f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{num(rr)}" '
                    f'fill="{COLOR[p["family"]]}"{ring}/>')
        data[ref] = dict(p, ny=round(y, 1))
        s.append(f'<g class="node bg" data-key="{esc(ref)}" tabindex="0"><title>{esc(p["apa"])}</title>'
                 f'<circle class="hit" cx="{x:.0f}" cy="{y:.0f}" r="{num(max(9.0, rr + 2))}" '
                 f'fill="none" pointer-events="all"/>{body}</g>')
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
    # big nodes (labeled milestones + any emphasized source) on top; labeled
    # ones also get a leader line + text label
    # (year, ref): `big` is a SET of str, and Python randomizes string hashes per
    # process, so sorting on year alone left same-year ties in a different order
    # on every run — two renders of identical code and data produced different
    # bytes. Harmless on screen (it only changes which of two overlapping dots
    # paints on top) but it makes the re-render harness's byte-diff useless.
    for ref in sorted(big, key=lambda r: (papers[r]["year"], r)):
        p = papers[ref]
        x, y = pos[ref]
        data[ref] = dict(p, ny=round(y, 1))
        is_lab = ref in lab
        if size_mode:
            # Size now means citations for landmarks too; what marks a landmark
            # is its ring + leader + label. The floor only keeps a low-cited
            # landmark from being smaller than the ring it has to carry.
            rr = rad_of(ref, landmark=True)
        else:
            rr = (9.5 if is_lab else 8.5) if ref in labeled else 7
        stroke, sw = (LAB_RING, 2.6) if is_lab else ("#fff", 1.2)    # home-lab -> its own ring
        leader = label = ""
        if ref in labeled:
            off = loff[ref]
            # Under --size-by-citations the dot can be 11px wide, so start the
            # leader at its real edge; with fixed sizes keep the historical 7px
            # so unsized figures re-render byte-for-byte identical.
            edge = (rr + 1.5) if size_mode else 7
            ly1, ly2 = ((y - edge, y + off + 1) if off < 0
                        else (y + edge, y + off - 9))
            leader = (f'<line x1="{x:.0f}" y1="{ly1:.0f}" x2="{x:.0f}" y2="{ly2:.0f}" '
                      f'stroke="{COLOR[p["family"]]}" stroke-width="1" opacity="0.65"/>')
            label = (f'<text class="lbl" x="{x:.0f}" y="{y+off:.0f}" text-anchor="middle" '
                     f'font-size="11" font-weight="bold" fill="{LAB_INK if is_lab else "#222"}">'
                     f'{esc(labeled[ref])}</text>')
        s.append(f'{leader}<g class="node spine" data-key="{esc(ref)}" tabindex="0">'
                 f'<title>{esc(p["apa"])}</title>'
                 f'<circle class="hit" cx="{x:.0f}" cy="{y:.0f}" r="{num(max(12.0, rr + 3))}" '
                 f'fill="none" pointer-events="all"/>'
                 f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{num(rr)}" fill="{COLOR[p["family"]]}" '
                 f'stroke="{stroke}" stroke-width="{sw}"/>{label}</g>')
    s.append('</svg>')
    svg = "".join(s)

    # optional embedded xlsx download button (base64 data URI -> works offline)
    xlsx_btn = ""
    if args.xlsx and os.path.exists(args.xlsx):
        with open(args.xlsx, "rb") as xf:
            b64 = base64.b64encode(xf.read()).decode()
        xlsx_btn = (f'<a class="dl" download="{esc(os.path.basename(args.xlsx))}" '
                    f'href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;'
                    f'base64,{b64}">⬇ Download table (.xlsx)</a>')

    # Everything the hover panel needs about a family, including the lineage that
    # families.json has always carried and the figure never showed.
    fam_n = Counter(p["family"] for p in papers.values())
    faminfo = {name: {"key": famkey[name], "claim": claim[name],
                      "lineage": lineage[name], "n": fam_n.get(name, 0)}
               for name in order}

    # `<\/` so a "</script>" inside any apa can't terminate the inline <script>
    def js_json(o): return json.dumps(o).replace("</", "<\\/")
    # The HTML gets the styled #famtip instead of the browser's native title
    # tooltip; showing both would stack two descriptions on the same hover.
    svg_html = re.sub(r'<title class="lanetitle">.*?</title>', "", svg, flags=re.S)
    doc = HTML_SHELL.replace("__TITLE__", esc(args.title)).replace("__SVG__", svg_html)\
        .replace("__XLSXBTN__", xlsx_btn)\
        .replace("__DATA__", js_json(data)).replace("__COLOR__", js_json(COLOR))\
        .replace("__FAMINFO__", js_json(faminfo))

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
          f"({len(bg)} dots + {len(big)} big ({len(labeled)} labeled) across {len(order)} families)")


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
 #apa{margin:12px 0;} .meta{color:#666;font-size:12.5px;}
 #summary{margin:10px 0;color:#333;font-size:12.5px;line-height:1.5;}
 a.doi{display:inline-block;margin-top:12px;padding:7px 13px;background:#1b6ca8;color:#fff;border-radius:6px;text-decoration:none;font-size:13px;}
 a.doi.off{background:#bbb;pointer-events:none;} .hint{color:#999;}
 #close{float:right;border:none;background:#eee;border-radius:50%;width:24px;height:24px;font-size:16px;cursor:pointer;color:#444;}
 a.dl{float:right;margin-left:12px;padding:5px 11px;background:#217346;color:#fff;border-radius:6px;text-decoration:none;font-size:12.5px;}
 #nav{margin:10px 0 0;padding-bottom:10px;border-bottom:1px solid #e3e3e3;display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-height:32px;}
 #nav a.doi{margin:0;}
 #nav button{padding:6px 12px;font-size:12.5px;border:1px solid #bbb;border-radius:6px;background:#fafafa;cursor:pointer;}
 #nav button:hover{background:#eee;} #nav button:disabled{opacity:.4;cursor:default;}
 #pos{font-size:11.5px;color:#777;margin-left:auto;}
 #scope{font-size:11.5px;color:#555;margin:8px 0 12px;}
 #scope label{cursor:pointer;}
 .lanelabel{cursor:help;} .lanelabel:focus{outline:2px solid #1b6ca8;outline-offset:2px;}
 #famtip{position:fixed;z-index:20;width:330px;max-width:46vw;/*JS sets the real width*/background:#fff;color:#222;
   border:1px solid #d5d5d5;border-left-width:4px;border-radius:6px;padding:12px 14px;
   box-shadow:0 8px 28px rgba(0,0,0,.17);font-size:12.5px;line-height:1.45;pointer-events:none;}
 #famtip[hidden]{display:none;}
 #famtip .ft-name{font-weight:bold;font-size:14px;margin-bottom:1px;}
 #famtip .ft-n{color:#888;font-size:11px;margin-bottom:8px;}
 #famtip .ft-claim{color:#333;}
 #famtip .ft-lab{margin-top:10px;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:#999;}
 #famtip .ft-lin{color:#444;font-size:12px;margin-top:2px;}
</style></head><body>
<header>__XLSXBTN__<div class="sub">Hover a node for its reference; click it to pin the full entry here,
 then walk the timeline with Next/Prev or the \\u2190/\\u2192 arrow keys.
 Hover a family's name at left for its claim and lineage, and to spotlight its papers.</div></header>
<main><div id="figwrap">__SVG__</div>
<aside id="panel"><div class="hint">Click any node to see its full reference here.</div></aside></main>
<div id="famtip" hidden></div>
<script>
const DATA=__DATA__, FAMCOLOR=__COLOR__, FAMINFO=__FAMINFO__,
 panel=document.getElementById('panel'), famtip=document.getElementById('famtip');
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>(
 {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function resetPanel(){document.querySelectorAll('.node.sel').forEach(n=>n.classList.remove('sel'));
 panel.innerHTML='<div class="hint">Click any node to see its full reference here, '
  +'then step through the timeline with Next/Prev or the arrow keys.</div>';CUR=null;}
function show(k){const d=DATA[k];if(!d)return;
 document.querySelectorAll('.node.sel').forEach(n=>n.classList.remove('sel'));
 const g=document.querySelector('.node[data-key="'+CSS.escape(k)+'"]');if(g)g.classList.add('sel');
 const url=(d.doi||'').startsWith('http')?d.doi:'';
 const doi=url?'<a class="doi" href="'+esc(url)+'" target="_blank" rel="noopener">Open paper \\u2197</a>':'<a class="doi off">no DOI</a>';
 const c=[];if(Number.isInteger(d.oa))c.push(d.oa+' (OpenAlex)');if(Number.isInteger(d.s2))c.push(d.s2+' (S2)');
 panel.innerHTML='<button id="close" onclick="resetPanel()">\\u00d7</button>'
  +'<div id="fam" style="background:'+esc(FAMCOLOR[d.family]||'#666')+'">'+esc(d.family)+'</div> <span class="meta">'+esc(d.ref)+' \\u00b7 '+esc(d.topic)+'</span>'
  +navHTML(k,doi)
  +'<div id="apa">'+esc(d.apa)+'</div>'+(d.summary?'<div id="summary">'+esc(d.summary)+'</div>':'')+(c.length?'<div class="meta">Cited by: '+esc(c.join(' \\u00b7 '))+'</div>':'');
 CUR=k; wireNav();}

// ---- walking the timeline -------------------------------------------------
// ORDER is every paper sorted by year; WITHIN is the same restricted to one
// family lane. The figure has hundreds of small dots, so clicking each one is
// impractical; Next/Prev (and the arrow keys) step through them in time order.
//
// The tie-break inside a year is `ny`, the dot's own drawn y. Every paper of a
// given year shares one x, so a year IS a vertical column; ordering the walk by
// ny sweeps that column top to bottom. Sorting on the reference string instead
// (what this did until 2026-09-19) bore no relation to the beeswarm, which fans
// dots out from the lane center as 0, +d, -d, +2d, -2d - so Next jumped the
// highlight up and down the column and the walk read as random.
let CUR=null, LANEONLY=true;
const ORDER=Object.keys(DATA).sort((a,b)=>DATA[a].year-DATA[b].year
 ||DATA[a].ny-DATA[b].ny||a.localeCompare(b));
function seq(){return LANEONLY&&CUR?ORDER.filter(r=>DATA[r].family===DATA[CUR].family):ORDER;}
function navHTML(k,doi){const q=LANEONLY?ORDER.filter(r=>DATA[r].family===DATA[k].family):ORDER;
 const i=q.indexOf(k);
 return '<div id="nav"><button id="prev"'+(i<=0?' disabled':'')+'>\\u2190 Prev</button>'
  +'<button id="next"'+(i<0||i>=q.length-1?' disabled':'')+'>Next \\u2192</button>'
  +(doi||'')+'<span id="pos">'+(i+1)+' / '+q.length+'</span></div>'
  +'<div id="scope"><label><input type="checkbox" id="lanechk"'+(LANEONLY?' checked':'')+'> '
  +'stay in this family ('+esc(DATA[k].family)+')</label></div>';}
function step(n){const q=seq();const i=q.indexOf(CUR);const j=i+n;
 if(j<0||j>=q.length)return;show(q[j]);
 const g=document.querySelector('.node[data-key="'+CSS.escape(q[j])+'"]');
 if(g&&g.scrollIntoView)g.scrollIntoView({block:'nearest',inline:'center',behavior:'smooth'});}
function wireNav(){const p=document.getElementById('prev'),n=document.getElementById('next'),
  c=document.getElementById('lanechk');
 if(p)p.onclick=()=>step(-1); if(n)n.onclick=()=>step(1);
 if(c)c.onchange=()=>{LANEONLY=c.checked;show(CUR);};}
document.addEventListener('keydown',e=>{if(!CUR)return;
 if(e.target&&/^(INPUT|TEXTAREA)$/.test(e.target.tagName))return;
 if(e.key==='ArrowRight'){e.preventDefault();step(1);}
 else if(e.key==='ArrowLeft'){e.preventDefault();step(-1);}});
document.querySelectorAll('.node').forEach(g=>{g.addEventListener('click',()=>show(g.dataset.key));
 g.addEventListener('focus',()=>show(g.dataset.key));
 g.addEventListener('keydown',e=>{if(e.key==='Enter')show(g.dataset.key);});});
function showFam(f,el){const d=FAMINFO[f];if(!d)return;const c=FAMCOLOR[f]||'#222';
 famtip.innerHTML='<div class="ft-name" style="color:'+esc(c)+'">'+esc(f)+'</div>'
  +'<div class="ft-n">'+d.n+' paper'+(d.n===1?'':'s')+' in this family</div>'
  +(d.claim?'<div class="ft-claim">'+esc(d.claim)+'</div>':'')
  +(d.lineage?'<div class="ft-lab">Lineage</div><div class="ft-lin">'+esc(d.lineage)+'</div>':'');
 famtip.style.borderLeftColor=c;famtip.hidden=false;
 // Sit ON the lane legend, at the left edge. Anchored to the label's RIGHT edge
 // the panel landed over the start of the plot and hid the earliest papers —
 // which on a density-warped axis is exactly where the foundations sit. Size it
 // to the legend band so it covers the thing it describes, with a readable floor
 // and a viewport cap for narrow windows.
 const r=el.getBoundingClientRect();
 const INSET=6;                      // small gutter so it reads as a panel, not a block
 const band=Math.max(0,r.right-r.left);
 const w=Math.min(Math.max(band-2*INSET,240),Math.round(window.innerWidth*0.46));
 famtip.style.width=w+'px';
 const h=famtip.offsetHeight;        // measured AFTER the width is applied
 famtip.style.left=Math.max(4,Math.min(r.left+INSET,window.innerWidth-w-8))+'px';
 famtip.style.top=Math.max(8,Math.min(r.top,window.innerHeight-h-8))+'px';}
function hideFam(){famtip.hidden=true;}
document.querySelectorAll('.lanelabel').forEach(g=>{const f=g.dataset.fam;
 const on=()=>{showFam(f,g);
  document.querySelectorAll('.node').forEach(n=>{if(DATA[n.dataset.key].family!==f)n.classList.add('dim');});};
 const off=()=>{hideFam();document.querySelectorAll('.node').forEach(n=>n.classList.remove('dim'));};
 g.addEventListener('mouseenter',on);g.addEventListener('focus',on);
 g.addEventListener('mouseleave',off);g.addEventListener('blur',off);
 g.addEventListener('keydown',e=>{if(e.key==='Escape'){off();g.blur();}});});
</script></body></html>"""


if __name__ == "__main__":
    main()
