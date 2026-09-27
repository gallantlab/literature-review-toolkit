// verify_nav_order.mjs <figure.html>
//
// Executes the figure's OWN ORDER expression against its OWN embedded DATA and
// checks that the Next/Prev walk sweeps each year's column monotonically instead
// of hopping around it. Written because "the highlight skips around within a
// year" survived reading the code — the sort looked fine until you noticed its
// tie-break (the reference string) had nothing to do with the beeswarm layout.
import { readFileSync } from "node:fs";

const file = process.argv[2];
if (!file) { console.error("usage: node verify_nav_order.mjs <figure.html>"); process.exit(2); }
const html = readFileSync(file, "utf8");

const m = html.match(/const DATA=(\{.*?\}), FAMCOLOR=/s);
if (!m) { console.error("could not find the embedded DATA object"); process.exit(2); }
const DATA = JSON.parse(m[1]);

const src = html.match(/const ORDER=Object\.keys\(DATA\)\.sort\((.*?)\);/s);
if (!src) { console.error("could not find the ORDER sort expression"); process.exit(2); }
const ORDER = Object.keys(DATA).sort(eval("(" + src[1] + ")"));

const n = ORDER.length;
const missingY = ORDER.filter(r => typeof DATA[r].ny !== "number");
if (missingY.length) {
  console.log(`✗ ${missingY.length} of ${n} papers carry no drawn y (ny) — the walk cannot follow the picture`);
  process.exit(1);
}

// Within one family lane (what "stay in this family" gives you) a year's papers
// must come out in a single monotone run of y — no revisiting a column.
let breaks = 0, cols = 0, worst = null;
for (const fam of new Set(ORDER.map(r => DATA[r].family))) {
  const lane = ORDER.filter(r => DATA[r].family === fam);
  for (let i = 0; i < lane.length; ) {
    const y0 = DATA[lane[i]].year;
    let j = i;
    while (j < lane.length && DATA[lane[j]].year === y0) j++;
    const col = lane.slice(i, j).map(r => DATA[r].ny);
    cols++;
    for (let k = 1; k < col.length; k++) {
      if (col[k] < col[k - 1]) {
        breaks++;
        if (!worst) worst = `${fam} ${y0}: ${col.map(v => v.toFixed(0)).join(" -> ")}`;
      }
    }
    i = j;
  }
}
console.log(`  ${n} papers, ${cols} year-columns in ${new Set(ORDER.map(r => DATA[r].family)).size} lanes`);
if (breaks) {
  console.log(`✗ ${breaks} backward step(s) inside a year-column — the walk still hops`);
  console.log(`  first: ${worst}`);
  process.exit(1);
}
console.log("✓ every year-column is walked top-to-bottom in one sweep");
