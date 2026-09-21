#!/usr/bin/env python3
"""Render the searchable bibliography viewer every review page embeds.

A written review is built from the corpus's abstract-derived summaries, so the
reader must be able to get from a claim in the prose to the summary that produced
it without leaving the page. That is what this block is for: the WHOLE corpus —
including the references the review never cites, because which papers went uncited
is itself evidence about the review's scope — grouped by theoretical family, with a
live search box, a "cited in this review only" filter, and a chip on each cited
entry linking back to its numbered works-cited entry.

It also carries its own provenance note. A review written by a model says so on its
own face AND inside its bibliography, because a reader who jumps straight to the
corpus never sees the masthead.

Use it from a project's `build_review_page.py`:

    import bib_viewer
    block = bib_viewer.render(rows, spec=common.load_json("families.json"),
                              cited={"C-01": 12, ...},          # ref -> citation number
                              author="Claude Opus 5",
                              author_note="An artificial intelligence developed by Anthropic")
    ... page CSS += bib_viewer.CSS ... page body += block ... page JS += bib_viewer.JS

`render` returns only the block, so the host page owns its own <section>, heading and
design tokens. The CSS is written against the token names every page in this toolkit
already defines (--panel, --sunk, --band, --ink, --ink-2, --muted, --rule, --rule-2,
--accent, --accent-ink, --accent-soft, --f1..--f6, --display, --body, --data).

Standalone, it writes a complete viewer page for a corpus with no review attached:

    python3 tools/bib_viewer.py --rows rows.json --families families.json \\
            --out corpus_viewer.html --title "Cortical layers"

Verify the filter by EXECUTING it, never by reading it: `verify_bib_filter.mjs`
runs this module's own JS against a stub DOM built from the rendered entries.
"""
import argparse
import html
import sys

import common

PHASE = "7"   # pipeline phase, read by tools/gen_docs.py for the tool index

# Family colour classes, in the order families.json lists them. Matches the
# report page's palette so a project's pages read as one system.
FAM_CLASSES = ["f1", "f2", "f3", "f4", "f5", "f6"]

PROVENANCE = (
    "<b>Where these summaries come from.</b> Each summary below was written by "
    "{author} &mdash; {author_note} &mdash; from that paper's <em>abstract</em>, "
    "retrieved during the literature search that built this bibliography. They are "
    "not the publishers' abstracts reproduced verbatim, and they are not written "
    "from the full papers: no figure, table or methods section was read. A summary "
    "states what its abstract supports plus the paper's role in the corpus. Where an "
    "abstract did not exist, the summary says so in its own text. The bibliographic "
    "data &mdash; authors, year, title, venue, DOI &mdash; is machine-built from "
    "CrossRef, PubMed or the arXiv API and is not the model's recollection. {tail}"
)
PROVENANCE_TAIL = (
    "The review above was written from exactly this material, so a claim in the text "
    "can be checked against the summary that produced it."
)


def E(s):
    return html.escape(str(s if s is not None else ""), quote=False)


def group_rows(rows, spec=None):
    """[(css_class, group_name, group_claim, rows)] — by family when a families.json
    spec is supplied, else by the rows' own Topic column, else one flat group.

    Families are emitted in the order the spec lists them, which is the order the
    report page and the lineage figure use. A row whose family is not in the spec is
    a build error, not something to silently drop."""
    if spec and spec.get("families"):
        fams = spec["families"]
        by_name = {f["name"]: f for f in fams}
        unknown = {r.get("family") for r in rows if r.get("family")} - set(by_name)
        if unknown:
            raise ValueError("rows carry families absent from the spec: %s"
                             % ", ".join(sorted(unknown)))
        out = []
        for i, fam in enumerate(fams):
            members = [r for r in rows if r.get("family") == fam["name"]]
            if members:
                out.append((FAM_CLASSES[i % len(FAM_CLASSES)], fam["name"],
                            fam.get("claim", ""), members))
        loose = [r for r in rows if not r.get("family")]
        if loose:
            out.append((FAM_CLASSES[len(out) % len(FAM_CLASSES)], "Unassigned", "", loose))
        return out

    topics = []
    for row in rows:
        topic = row.get("topic") or row.get("lane") or "References"
        if topic not in topics:
            topics.append(topic)
    if len(topics) <= 1:
        return [(FAM_CLASSES[0], topics[0] if topics else "References", "", list(rows))]
    return [(FAM_CLASSES[i % len(FAM_CLASSES)], t, "",
             [r for r in rows if (r.get("topic") or r.get("lane")) == t])
            for i, t in enumerate(topics)]


def _year(row):
    return row.get("search_year") or common.year_of(row.get("apa", "")) or 0


def entry(row, cited_n=None, anchor="#ref-{n}"):
    """One <li> for one reference: id, canonical APA, DOI, summary, meta line.

    The cited chip is labelled `ref N`, NOT `cited N`: the meta line beside it
    already carries an OpenAlex "N cites" count, and two senses of "cite" touching
    reads as one number."""
    apa = E(row.get("apa", ""))
    link = row.get("link") or common.doi_of(row)
    if link:
        href = link if link.startswith("http") else "https://doi.org/%s" % link
        label = common.doi_of(row) or link
        apa = '%s <a class="bref-doi" href="%s">%s</a>' % (apa, E(href), E(label))

    bits = [row.get("topic") or row.get("lane") or "", row.get("tag") or ""]
    if row.get("cite_openalex") is not None:
        bits.append("%s cites" % row["cite_openalex"])
    meta = " &middot; ".join(E(b) for b in bits if b)

    chip = ""
    if cited_n is not None:
        chip = ('<a class="bref-cited" href="%s" title="Cited in this review as '
                'reference %d">ref %d</a>'
                % (E(anchor.format(n=cited_n)), cited_n, cited_n))

    return ('<li class="bref"%s><span class="bref-id">%s</span>'
            '<div class="bref-body"><p class="bref-apa">%s</p>'
            '<p class="bref-sum">%s</p><p class="bref-meta">%s%s</p></div></li>'
            % (' data-cited="1"' if chip else "", E(row.get("ref") or row.get("label", "")),
               apa, E(row.get("summary", "")), meta, chip))


def render(rows, spec=None, cited=None, author="", author_note="",
           anchor="#ref-{n}", provenance=True, provenance_tail=PROVENANCE_TAIL,
           open_first=False):
    """The viewer block: provenance note, toolbar, and the grouped reference list.

    rows      — the corpus, every row of it (not only the cited ones)
    spec      — families.json, to group and colour by theoretical family
    cited     — {ref id: citation number}; enables the chips and the cited-only filter
    author/author_note — who wrote the summaries, named in the provenance note
    anchor    — format string for a cited chip's target, "{n}" is the citation number
    open_first — open the first group, so the page does not look empty at rest
    """
    cited = cited or {}
    groups = group_rows(rows, spec)
    total = sum(len(g[3]) for g in groups)

    blocks = []
    for i, (cls, name, claim, members) in enumerate(groups):
        members = sorted(members, key=lambda r: (_year(r), r.get("apa", "")))
        items = "".join(
            entry(r, cited.get(r.get("ref") or r.get("label")), anchor) for r in members)
        claim_html = '<p class="famclaim">%s</p>' % E(claim) if claim else ""
        blocks.append(
            '<details class="refs %s"%s><summary><span class="famname">%s</span>'
            '<span class="rn"><span class="shown">%d</span> of %d references</span>'
            '</summary>%s<ol class="rlist">%s</ol></details>'
            % (cls, " open" if (open_first and i == 0) else "", E(name),
               len(members), len(members), claim_html, items))

    note = ""
    if provenance and author:
        tail = (" " + provenance_tail) if provenance_tail else ""
        note = '<p class="provenance">%s</p>' % PROVENANCE.format(
            author=E(author),
            author_note=E(author_note[:1].lower() + author_note[1:]) if author_note else "",
            tail=tail.strip())

    cited_toggle = ""
    if cited:
        cited_toggle = ('<label class="chk"><input type="checkbox" id="bibcited" '
                        'name="bibcited"><span>Only papers cited in this review</span></label>')

    return """%s
<div class="bibtools">
  <div class="bibfield">
    <label for="bibq">Search the bibliography</label>
    <input type="search" id="bibq" name="bibq" autocomplete="off" spellcheck="false"
           placeholder="author, title, year, method, claim&hellip;">
  </div>
  <div class="bibopts">
    %s
    <button type="button" id="bibexpand" class="btn">Expand all</button>
  </div>
  <p class="bibcount" id="bibcount" aria-live="polite" role="status">%d of %d references shown</p>
</div>
<div class="bibblocks">
%s
</div>""" % (note, cited_toggle, total, total, "\n".join(blocks))


CSS = """
.bibtools{display:flex;flex-wrap:wrap;align-items:flex-end;gap:.9rem 1.6rem;
  background:var(--panel);border:1px solid var(--rule);border-radius:3px;
  padding:1rem 1.15rem;margin:1.6rem 0 1.4rem;position:sticky;top:0;z-index:5;}
.bibfield{display:flex;flex-direction:column;gap:.35rem;flex:1 1 300px;min-width:0;}
.bibfield label,.bibopts .chk span{font-family:var(--data);font-size:.63rem;
  letter-spacing:.11em;text-transform:uppercase;color:var(--muted);}
#bibq{font-family:var(--body);font-size:.95rem;color:var(--ink);
  background:var(--sunk);border:1px solid var(--rule-2);border-radius:3px;
  padding:.5rem .65rem;width:100%;min-width:0;}
#bibq::placeholder{color:var(--muted);opacity:.75;}
#bibq:focus-visible{outline:2px solid var(--accent);outline-offset:1px;}
.bibopts{display:flex;flex-wrap:wrap;align-items:center;gap:.7rem 1.2rem;}
.bibopts .chk{display:flex;align-items:center;gap:.45rem;cursor:pointer;}
.bibopts .chk input{accent-color:var(--accent);width:15px;height:15px;cursor:pointer;}
.btn{font-family:var(--data);font-size:.66rem;letter-spacing:.1em;text-transform:uppercase;
  color:var(--accent-ink);background:var(--accent-soft);border:1px solid var(--rule-2);
  border-radius:3px;padding:.45rem .7rem;cursor:pointer;}
.btn:hover{border-color:var(--accent);}
.bibcount{font-family:var(--data);font-size:.68rem;color:var(--muted);margin:0;
  flex:0 0 auto;font-variant-numeric:tabular-nums;}
.provenance{background:var(--band);border-left:3px solid var(--f5);
  border-radius:0 3px 3px 0;padding:1rem 1.2rem;font-size:.92rem;line-height:1.55;
  color:var(--ink-2);margin:1.4rem 0 0;max-width:78ch;}
.provenance b{color:var(--ink);}
.bibblocks{display:grid;gap:.7rem;}
details.refs{background:var(--panel);border:1px solid var(--rule);
  border-left:3px solid var(--fc);border-radius:2px;}
details.refs.f1{--fc:var(--f1);} details.refs.f2{--fc:var(--f2);}
details.refs.f3{--fc:var(--f3);} details.refs.f4{--fc:var(--f4);}
details.refs.f5{--fc:var(--f5);} details.refs.f6{--fc:var(--f6);}
details.refs summary{cursor:pointer;padding:.85rem 1.15rem;font-family:var(--display);
  font-weight:600;font-size:1.1rem;color:var(--fc);display:flex;flex-wrap:wrap;
  align-items:baseline;gap:.4rem .8rem;}
details.refs summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
details.refs .rn{font-family:var(--data);font-size:.68rem;color:var(--muted);
  font-weight:400;font-variant-numeric:tabular-nums;}
.famclaim{margin:0 1.15rem .4rem;font-size:.9rem;line-height:1.5;color:var(--ink-2);
  max-width:80ch;}
ol.rlist{margin:0;padding:0 1.15rem 1rem;list-style:none;}
ol.rlist li{display:grid;grid-template-columns:4.4rem 1fr;gap:.8rem;
  padding:.75rem 0;border-top:1px solid var(--rule);}
.bref-id{font-family:var(--data);font-size:.74rem;color:var(--muted);padding-top:.2rem;}
.bref-apa{margin:0 0 .3rem;font-size:.9rem;line-height:1.45;max-width:none;}
.bref-doi{font-family:var(--data);font-size:.72rem;color:var(--muted);word-break:break-word;}
.bref-sum{font-size:.85rem;line-height:1.5;color:var(--ink-2);margin:0 0 .35rem;max-width:82ch;}
.bref-meta{margin:0;font-family:var(--data);font-size:.66rem;color:var(--muted);
  display:flex;flex-wrap:wrap;gap:.3rem .7rem;align-items:center;max-width:none;}
.bref-cited{font-family:var(--data);font-size:.63rem;letter-spacing:.06em;
  text-transform:uppercase;color:var(--accent-ink);background:var(--accent-soft);
  border-radius:2px;padding:.15rem .4rem;text-decoration:none;}
.bref-cited:hover{text-decoration:underline;}
@media (max-width:560px){
  ol.rlist li{grid-template-columns:1fr;gap:.2rem;}
  .bibtools{position:static;}
}
"""

JS = """
(function () {
  var q = document.getElementById('bibq');
  var onlyCited = document.getElementById('bibcited');
  var expandBtn = document.getElementById('bibexpand');
  var countEl = document.getElementById('bibcount');
  var blocks = Array.prototype.slice.call(
    document.querySelectorAll('.bibblocks details.refs'));
  if (!q || !blocks.length) return;

  // The search index is built from the rendered text on first use, so the
  // summaries are not duplicated into the markup. On a 555-reference corpus
  // duplicating them into data- attributes cost 600KB.
  var index = null;
  function buildIndex() {
    index = blocks.map(function (block) {
      var entries = Array.prototype.slice.call(block.querySelectorAll('li.bref'))
        .map(function (li) {
          return {
            el: li,
            cited: li.hasAttribute('data-cited'),
            text: (li.textContent || '').toLowerCase()
          };
        });
      return {
        block: block,
        shownEl: block.querySelector('.shown'),
        total: entries.length,
        entries: entries,
        wasOpen: block.open
      };
    });
  }

  var total = 0;
  function apply() {
    if (!index) buildIndex();
    var needle = q.value.trim().toLowerCase();
    var citedOnly = !!(onlyCited && onlyCited.checked);
    var filtering = needle.length > 0 || citedOnly;
    var shown = 0;

    index.forEach(function (fam) {
      var famShown = 0;
      fam.entries.forEach(function (entry) {
        var hit = (!citedOnly || entry.cited) &&
                  (!needle || entry.text.indexOf(needle) !== -1);
        entry.el.hidden = !hit;
        if (hit) famShown++;
      });
      fam.shownEl.textContent = famShown;
      fam.block.hidden = filtering && famShown === 0;
      if (filtering) {
        if (!fam.block.hidden) fam.block.open = true;
      } else {
        fam.block.open = fam.wasOpen;
      }
      shown += famShown;
    });

    if (!total) total = index.reduce(function (n, f) { return n + f.total; }, 0);
    countEl.textContent = shown + ' of ' + total + ' references shown';
  }

  // A manual open/close is remembered only while no filter is running, so
  // clearing the query restores what the reader had open.
  blocks.forEach(function (block) {
    block.addEventListener('toggle', function () {
      if (!index) return;
      if (q.value.trim() !== '' || (onlyCited && onlyCited.checked)) return;
      index.forEach(function (fam) {
        if (fam.block === block) fam.wasOpen = block.open;
      });
      syncExpandLabel();
    });
  });

  function syncExpandLabel() {
    var allOpen = blocks.every(function (b) { return b.open || b.hidden; });
    expandBtn.textContent = allOpen ? 'Collapse all' : 'Expand all';
  }

  expandBtn.addEventListener('click', function () {
    if (!index) buildIndex();
    var allOpen = blocks.every(function (b) { return b.open || b.hidden; });
    blocks.forEach(function (b) { b.open = !allOpen; });
    index.forEach(function (fam) { fam.wasOpen = !allOpen; });
    syncExpandLabel();
  });

  var timer = null;
  q.addEventListener('input', function () {
    window.clearTimeout(timer);
    timer = window.setTimeout(apply, 90);
  });
  if (onlyCited) onlyCited.addEventListener('change', apply);
  apply();
  syncExpandLabel();
})();
"""

# Design tokens, for the standalone page only. A review page defines its own and
# must NOT include these.
TOKENS = """
:root{
  --ground:#EDF0F3; --panel:#FFFFFF; --sunk:#F5F7F9; --band:#E4E9ED;
  --ink:#101820; --ink-2:#3A4753; --muted:#6B7783;
  --rule:#D5DCE2; --rule-2:#B3BEC7;
  --accent:#1B6CA8; --accent-ink:#0F4B76; --accent-soft:#DEEAF3;
  --f1:#1b6ca8; --f2:#2a9d8f; --f3:#c25534; --f4:#7431d8; --f5:#96730f; --f6:#5c646b;
  --display:"Barlow Semi Condensed","Helvetica Neue",Arial,sans-serif;
  --body:"Source Serif 4",Georgia,"Times New Roman",serif;
  --data:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#0C1216; --panel:#131C22; --sunk:#101a20; --band:#18242B;
    --ink:#E6EDF2; --ink-2:#BCC9D2; --muted:#8494A0;
    --rule:#233038; --rule-2:#35454E;
    --accent:#57ADE0; --accent-ink:#8CCAEE; --accent-soft:#102A38;
    --f1:#5aa9dc; --f2:#3fbba9; --f3:#e58551; --f4:#a688ec; --f5:#d0a63a; --f6:#96a6b1;
  }
}
:root[data-theme="dark"]{
  --ground:#0C1216; --panel:#131C22; --sunk:#101a20; --band:#18242B;
  --ink:#E6EDF2; --ink-2:#BCC9D2; --muted:#8494A0;
  --rule:#233038; --rule-2:#35454E;
  --accent:#57ADE0; --accent-ink:#8CCAEE; --accent-soft:#102A38;
  --f1:#5aa9dc; --f2:#3fbba9; --f3:#e58551; --f4:#a688ec; --f5:#d0a63a; --f6:#96a6b1;
}
*{box-sizing:border-box;}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--body);
  font-size:17px;line-height:1.6;-webkit-font-smoothing:antialiased;}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px 4rem;}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:2px;}
h1{font-family:var(--display);font-weight:600;font-size:clamp(1.9rem,5vw,3rem);
  line-height:1.05;margin:2.6rem 0 .6rem;text-wrap:balance;}
.sub{color:var(--ink-2);max-width:70ch;margin:0;}
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@400;600&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>%(tokens)s%(css)s</style>
</head>
<body>
<div class="wrap">
<h1>%(heading)s</h1>
<p class="sub">%(sub)s</p>
%(block)s
</div>
<script>%(js)s</script>
</body>
</html>
"""


def standalone(rows, spec=None, title="Bibliography", author="", author_note="",
               subtitle=""):
    """A complete, self-contained viewer page for a corpus with no review attached."""
    sub = subtitle or ("%d references." % len(rows))
    return PAGE % dict(
        title=E(title), tokens=TOKENS, css=CSS, js=JS,
        heading=E(title), sub=E(sub),
        block=render(rows, spec=spec, author=author, author_note=author_note,
                     provenance_tail="", open_first=True))


def main():
    ap = argparse.ArgumentParser(
        description="Render the searchable bibliography viewer as a standalone page.")
    ap.add_argument("--rows", required=True, help="rows.json (the live table)")
    ap.add_argument("--families", help="families.json, to group by theoretical family")
    ap.add_argument("--out", required=True, help="HTML file to write")
    ap.add_argument("--title", default="Bibliography", help="page title and heading")
    ap.add_argument("--subtitle", default="", help="one line under the heading")
    ap.add_argument("--author", default="",
                    help="who wrote the summaries; named in the provenance note")
    ap.add_argument("--author-note", default="",
                    help='e.g. "An artificial intelligence developed by Anthropic"')
    a = ap.parse_args()

    rows = common.load_json(a.rows)
    spec = common.load_json(a.families) if a.families else None
    page = standalone(rows, spec, title=a.title, author=a.author,
                      author_note=a.author_note, subtitle=a.subtitle)
    with open(a.out, "w") as fh:
        fh.write(page)
    print("wrote %s  (%d references%s)"
          % (a.out, len(rows), ", grouped by family" if spec else ""))
    if not a.author:
        sys.stderr.write(
            "warning: no --author, so the page carries no provenance note. A viewer "
            "shipped with an AI-written review must say who wrote the summaries.\n")


if __name__ == "__main__":
    main()
