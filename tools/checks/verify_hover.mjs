// Verify that a lineage figure's lane-hover panel actually works.
//
// Written after three rounds of "the hover is missing" that inspection could not
// settle: the markup was present every time, so presence checks kept passing.
// This EXECUTES the page's own handler in a stub DOM and reports what the panel
// would really contain, per lane.
//
//     node verify_hover.mjs <figure.html>
//     for f in */*_families.html; do node verify_hover.mjs "$f"; done
//
// Two traps this file encodes, both of which produced false results first time:
//   - a browser DECODES entities when reading dataset.*, so the stub must too,
//     or any family name containing & or ' looks like a mismatch that is not real;
//   - checking that FAMINFO exists is not the same as checking that the handler
//     fills the panel for EVERY lane.
// Execute the figure's real hover handler in a minimal DOM and report what the
// panel would contain. No browser: we stub just enough DOM for the page's own
// script, then fire mouseenter on a lane label.
import fs from "node:fs";
const file = process.argv[2];
const html = fs.readFileSync(file, "utf8");

// A browser DECODES entities when reading dataset.*, so the stub must too —
// otherwise a family name containing & or ' looks like a mismatch that is not real.
const dec = s => s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
  .replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&#39;/g, "'");
const lanes = [...html.matchAll(/<g class="lanelabel"[^>]*data-fam="([^"]*)"/g)].map(m => dec(m[1]));
const js = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));

function mkEl(extra = {}) {
  return {
    innerHTML: "", hidden: true, style: {}, dataset: {}, classList: {
      add() {}, remove() {}, contains() { return false; } },
    offsetHeight: 120, offsetWidth: 330,
    getBoundingClientRect: () => ({ top: 100, right: 262, left: 0, bottom: 237 }),
    addEventListener(t, fn) { (this._h ||= {})[t] = fn; },
    blur() {}, ...extra,
  };
}
const famtip = mkEl(), panel = mkEl();
const laneEls = lanes.map(f => mkEl({ dataset: { fam: f } }));
const nodeEls = [];
globalThis.window = { innerWidth: 1600, innerHeight: 900 };
globalThis.CSS = { escape: s => s };
globalThis.document = {
  getElementById: id => (id === "famtip" ? famtip : id === "panel" ? panel : mkEl()),
  querySelectorAll: sel => (sel === ".lanelabel" ? laneEls : sel === ".node" ? nodeEls : []),
  querySelector: () => null,
  addEventListener() {},
};
try { new Function(js)(); } catch (e) { console.log("  SCRIPT ERROR:", e.message); process.exit(1); }

let ok = 0, geo = null;
for (const el of laneEls) {
  const h = el._h && el._h.mouseenter;
  if (!h) { console.log(`  ${el.dataset.fam}: NO mouseenter handler`); continue; }
  famtip.innerHTML = ""; famtip.hidden = true;
  h();
  const txt = famtip.innerHTML;
  const hasClaim = /ft-claim/.test(txt), hasLin = /ft-lin/.test(txt), hasN = /ft-n/.test(txt);
  // Geometry: the panel must sit ON the legend band, not over the plot. The stub
  // reports the lane label as spanning x 0..262, which is the legend width.
  const left = parseFloat(famtip.style.left), w = parseFloat(famtip.style.width);
  const right = left + w;
  const onLegend = Number.isFinite(right) && right <= 262 + 2;
  if (!famtip.hidden && hasClaim && hasLin && hasN && onLegend) ok++;
  else console.log(`  ${el.dataset.fam}: hidden=${famtip.hidden} claim=${hasClaim} `
    + `lineage=${hasLin} count=${hasN} left=${left} w=${w} right=${right} onLegend=${onLegend}`);
  geo = { left, w, right };
}
console.log(`  ${ok}/${laneEls.length} lanes show a full panel on the legend`
  + (geo ? `  [panel x ${geo.left}-${geo.right}, legend ends 262]` : ""));
