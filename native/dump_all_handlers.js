// Source of every function on every in-scope effect (moves, their conditions/secondaries, items, abilities, conditions) for porting.
// usage (from pssim/): node ../native/dump_all_handlers.js ../native/engine_data.json ../native/handlers_all.js
const {Dex} = require(require('path').resolve('node_modules/pokemon-showdown')); const dex = Dex.mod('champions'); const fs = require('fs');
const d = JSON.parse(fs.readFileSync(process.argv[2])); const out = [];
const dump = (label, o) => { if (!o) return; for (const k of Object.keys(o)) if (typeof o[k] === 'function') out.push(`// ${label}.${k}\n${o[k].toString()}\n`); };
for (const id of Object.keys(d.moves)) { const m = dex.moves.get(id); dump(`move:${id}`, m); (m.secondaries || []).forEach((s, i) => dump(`move:${id}.secondaries.${i}`, s)); if (m.self) dump(`move:${id}.self`, m.self); }
for (const id of Object.keys(d.items)) dump(`item:${id}`, dex.items.get(id));
for (const id of Object.keys(d.abilities)) dump(`ability:${id}`, dex.abilities.get(id));
for (const id of Object.keys(d.conditions)) dump(`cond:${id}`, dex.conditions.getByID(id));
fs.writeFileSync(process.argv[3], out.join('\n')); console.log(out.length, 'functions');
