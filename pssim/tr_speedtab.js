// Speeds of common opposing sets (modal set per archetype, usual spread) for the Trick Room order table.
const T = require('./t1sim.js'); const {Dex} = require('pokemon-showdown'); const dex = Dex.mod('champions'); const fs = require('fs');
const NAT = n => { const x = dex.natures.get(n); return x.plus === 'spe' ? 1.1 : x.minus === 'spe' ? 0.9 : 1.0; };
const foes = JSON.parse(fs.readFileSync('../foes.json'));
const rows = {};
for (const [arch, A] of Object.entries(T.OPP)) {
  const n = A.n;
  for (const [sp, raw] of Object.entries(A.sets)) {
    const cnt = +((raw.match(/\((\d+)\/(\d+)\)/) || [0, 0, 0])[2]);   // how many of that species on this archetype's teams
    let s; try { s = T.oppSet(arch, sp, []); } catch (e) { continue; }
    let spc = dex.species.get(sp); const it = dex.items.get(s.item);
    if (it.megaStone) { const f = typeof it.megaStone === 'string' ? it.megaStone : (it.megaStone[spc.name] || Object.values(it.megaStone)[0]); if (f) spc = dex.species.get(f); }
    const v = Math.floor((spc.baseStats.spe + 20 + s.evs[5]) * NAT(s.nature));
    const name = spc.name; (rows[name] = rows[name] || []).push({arch, spe: v, nature: s.nature, sp: s.evs[5], cnt, item: s.item});
  }
}
const out = Object.entries(rows).map(([name, L]) => { const tot = L.reduce((a, b) => a + b.cnt, 0); const bySpe = {};
  for (const x of L) bySpe[x.spe] = (bySpe[x.spe] || 0) + x.cnt; return {name, tot, speeds: Object.entries(bySpe).sort((a, b) => b[1] - a[1]).map(([s, c]) => [+s, c])}; })
  .sort((a, b) => b.tot - a.tot);
for (const r of out.slice(0, 40)) console.log(r.name.padEnd(22), String(r.tot).padStart(5), r.speeds.map(([s, c]) => `${s}(${c})`).join(' '));
fs.writeFileSync('tr_speedtab.json', JSON.stringify(out));
