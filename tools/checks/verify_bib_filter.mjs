// verify_bib_filter.mjs — EXECUTE the review page's own bibliography filter.
//
//   node verify_bib_filter.mjs <topic>/<topic>_review.html
//
// Shared harness for the bibliography viewer that tools/bib_viewer.py renders into
// every review page.
//
// Written because filter logic survives code reading: a debounce that double-fires,
// a per-family count that drifts from the global one, or a details block left open
// after the query clears all look fine on the page source. This extracts the
// page's real <script>, runs it against a stub DOM built from the page's real
// entries, drives the controls, and checks the resulting visibility state.

import { readFileSync } from "node:fs";

const file = process.argv[2];
if (!file) {
  console.error("usage: node verify_bib_filter.mjs <review page>.html");
  process.exit(2);
}
const src = readFileSync(file, "utf8");

/* ---------- pull the real entries out of the real markup ---------- */

function decode(s) {
  return s
    .replace(/<[^>]+>/g, " ")
    .replace(/&middot;/g, "·").replace(/&mdash;/g, "—")
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'")
    .replace(/&[a-zA-Z]+;/g, " ")
    .replace(/\s+/g, " ").trim();
}

const blockRe = /<details([^>]*)class="refs (f\d)"[^>]*>([\s\S]*?)<\/details>/g;
const entryRe = /<li class="bref"([^>]*)>([\s\S]*?)<\/li>/g;

const blocksRaw = [];
let m;
while ((m = blockRe.exec(src)) !== null) {
  const inner = m[3];
  const openAtRest = /\sopen[\s>]/.test(m[0].slice(0, m[0].indexOf(">") + 1));
  const entries = [];
  let e;
  entryRe.lastIndex = 0;
  while ((e = entryRe.exec(inner)) !== null) {
    entries.push({ cited: /data-cited="1"/.test(e[1]), text: decode(e[2]) });
  }
  blocksRaw.push({ fam: m[2], openAtRest, entries });
}

const totalEntries = blocksRaw.reduce((n, b) => n + b.entries.length, 0);
if (!blocksRaw.length || !totalEntries) {
  console.error("FAIL: no bibliography entries found in", file);
  process.exit(1);
}

/* ---------- minimal DOM stub ---------- */

class El {
  constructor(tag, opts = {}) {
    this.tag = tag;
    this.hidden = false;
    this.open = false;
    this.textContent = opts.textContent ?? "";
    this.attrs = opts.attrs ?? {};
    this.children = opts.children ?? [];
    this.listeners = {};
    this.value = opts.value ?? "";
    this.checked = false;
  }
  hasAttribute(n) { return n in this.attrs; }
  querySelector(sel) { return this.query(sel)[0] ?? null; }
  querySelectorAll(sel) { return this.query(sel); }
  query(sel) {
    if (sel === "li.bref") return this.children.filter((c) => c.tag === "li");
    if (sel === ".shown") return this.children.filter((c) => c.tag === "shown");
    return [];
  }
  addEventListener(type, fn) { (this.listeners[type] ??= []).push(fn); }
  fire(type) { (this.listeners[type] ?? []).forEach((fn) => fn.call(this, {})); }
}

const shownEls = [];
const blockEls = blocksRaw.map((b) => {
  const shown = new El("shown", { textContent: String(b.entries.length) });
  shownEls.push(shown);
  const lis = b.entries.map(
    (en) =>
      new El("li", {
        textContent: en.text,
        attrs: en.cited ? { "data-cited": "1" } : {},
      })
  );
  const block = new El("details", { children: [shown, ...lis] });
  block.fam = b.fam;
  block.openAtRest = b.openAtRest;
  // a details element fires 'toggle' when .open changes
  let openState = b.openAtRest;
  Object.defineProperty(block, "open", {
    get: () => openState,
    set(v) {
      const changed = openState !== v;
      openState = v;
      if (changed) block.fire("toggle");
    },
  });
  return block;
});

const q = new El("input");
const cited = new El("input");
const expand = new El("button");
const count = new El("p");

const hasCitedToggle = /id="bibcited"/.test(src);
const byId = { bibq: q, bibexpand: expand, bibcount: count };
if (hasCitedToggle) byId.bibcited = cited;

let timerSeq = 1;
const timers = new Map();
globalThis.window = {
  setTimeout(fn) { const id = timerSeq++; timers.set(id, fn); return id; },
  clearTimeout(id) { timers.delete(id); },
};
function flush() {
  const pending = [...timers.values()];
  timers.clear();
  pending.forEach((fn) => fn());
}

globalThis.document = {
  getElementById: (id) => byId[id] ?? null,
  querySelectorAll: (sel) =>
    sel === ".bibblocks details.refs" ? blockEls : [],
};
globalThis.Array = Array;

/* ---------- run the page's own script ---------- */

const scripts = [...src.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((s) => s[1]);
const bibScript = scripts.find((s) => s.includes("bibq"));
if (!bibScript) {
  console.error("FAIL: no bibliography script found in", file);
  process.exit(1);
}
new Function(bibScript)();

/* ---------- drive it ---------- */

const fails = [];
const notes = [];
function check(name, cond, detail = "") {
  (cond ? notes : fails).push(`${cond ? "ok  " : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
}

const visible = () => blockEls.flatMap((b) => b.querySelectorAll("li.bref")).filter((li) => !li.hidden);
const famSum = () => shownEls.reduce((n, s) => n + Number(s.textContent), 0);
const countNum = () => Number((count.textContent.match(/^(\d+)/) ?? [0, 0])[1]);

// 1. at rest
check("at rest: every entry visible", visible().length === totalEntries,
  `${visible().length}/${totalEntries}`);
check("at rest: readout matches", countNum() === totalEntries, count.textContent);
check("at rest: per-family counts sum to total", famSum() === totalEntries, String(famSum()));
check("at rest: open state matches the markup",
  blockEls.every((b) => b.open === b.openAtRest),
  `${blockEls.filter((b) => b.openAtRest).length} open in markup`);
check("at rest: no family hidden", blockEls.every((b) => !b.hidden));
check("at rest: button offers expand", expand.textContent === "Expand all", expand.textContent);

// 2. text query
q.value = "neuropixels";
q.fire("input");
flush();
const hits = visible();
check("query: some but not all match", hits.length > 0 && hits.length < totalEntries,
  `${hits.length} hits`);
check("query: every visible entry matches",
  hits.every((li) => li.textContent.toLowerCase().includes("neuropixels")));
const hiddenWrong = blockEls
  .flatMap((b) => b.querySelectorAll("li.bref"))
  .filter((li) => li.hidden && li.textContent.toLowerCase().includes("neuropixels"));
check("query: no matching entry hidden", hiddenWrong.length === 0,
  `${hiddenWrong.length} wrongly hidden`);
check("query: readout matches visible", countNum() === hits.length,
  `${count.textContent} vs ${hits.length}`);
check("query: per-family counts sum to readout", famSum() === hits.length, String(famSum()));
check("query: families with matches are open",
  blockEls.every((b) => (Number(b.querySelector(".shown").textContent) > 0
    ? b.open && !b.hidden : b.hidden)));

// 3 + 4. cited-only, alone and combined with a query. The checkbox exists only
// when the page was built with a citation map, so a viewer with no review
// attached (bib_viewer.py standalone) skips these rather than failing them.
const citedTotal = blockEls
  .flatMap((b) => b.querySelectorAll("li.bref"))
  .filter((li) => li.hasAttribute("data-cited")).length;
q.value = "";
q.fire("input");
flush();
if (hasCitedToggle) {
  cited.checked = true;
  cited.fire("change");
  const citedVisible = visible();
  check("cited-only: exactly the cited entries", citedVisible.length === citedTotal,
    `${citedVisible.length}/${citedTotal}`);
  check("cited-only: every visible entry is cited",
    citedVisible.every((li) => li.hasAttribute("data-cited")));
  check("cited-only: readout matches", countNum() === citedTotal, count.textContent);

  q.value = "attention";
  q.fire("input");
  flush();
  const both = visible();
  check("combined: cited AND matching only",
    both.every((li) => li.hasAttribute("data-cited") &&
      li.textContent.toLowerCase().includes("attention")) && both.length > 0,
    `${both.length} hits`);
  check("combined: readout matches", countNum() === both.length, count.textContent);
} else {
  notes.push("skip  cited-only filter — page has no citation map");
}

// 5. clearing restores
q.value = "";
q.fire("input");
flush();
if (hasCitedToggle) {
  cited.checked = false;
  cited.fire("change");
}
check("cleared: every entry visible again", visible().length === totalEntries,
  `${visible().length}/${totalEntries}`);
check("cleared: readout restored", countNum() === totalEntries, count.textContent);
check("cleared: no family left hidden", blockEls.every((b) => !b.hidden));
check("cleared: open state restored to the at-rest state",
  blockEls.every((b) => b.open === b.openAtRest),
  `${blockEls.filter((b) => b.open).length} open`);

// 6. expand / collapse all
expand.fire("click");
check("expand all: every family open", blockEls.every((b) => b.open));
check("expand all: label flips to collapse", expand.textContent === "Collapse all",
  expand.textContent);
expand.fire("click");
check("collapse all: every family closed", blockEls.every((b) => !b.open));
check("collapse all: label flips back", expand.textContent === "Expand all",
  expand.textContent);

/* ---------- report ---------- */

console.log(`${file}: ${totalEntries} entries in ${blockEls.length} families, ` +
  `${citedTotal} cited\n`);
[...notes, ...fails].forEach((l) => console.log("  " + l));
console.log(`\n${fails.length ? "FAILED" : "PASSED"}  ` +
  `(${notes.length} ok, ${fails.length} failed)`);
process.exit(fails.length ? 1 : 0);
