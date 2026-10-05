// The data blocks of a sheet page as JSON: node sheetkit/blocks.js <page.html>  ->  {L, T, C, N, X, R} (a block the page lacks is null).
// Used to compare a built page with a published one value by value (page.py compare) and to import an existing page into a team folder.
const fs = require('fs');
const s = fs.readFileSync(process.argv[2], 'utf8');
const RX = {
  L: /^const L=(\[\n[\s\S]*?\n\]);$/m,          // leads: one tab per line
  T: /^const T=(\[\n[\s\S]*?\n\]);$/m,          // team cards
  C: /^const C=(\[.*\]);$/m,                    // coverage rows
  N: /^const N=(\[.*\]);$/m,                    // matchup columns
  X: /^const X=(\[.*\]);$/m,                    // matchup rows
  R: /^const R=(\[[\s\S]*?\]);$/m,              // speed rows
};
const out = {};
for (const [k, rx] of Object.entries(RX)) { const m = s.match(rx); out[k] = m ? (0, eval)('(' + m[1] + ')') : null; }
process.stdout.write(JSON.stringify(out));
