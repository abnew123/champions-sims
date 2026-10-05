// Mean Speed of each side's brought four (lead + back, Mega forme where it Mega Evolves) for every job.
// Used to credit a turn-one Trick Room to the slower team instead of to whoever clicked it.
const T = require('./t1sim.js'); const {Dex} = require('pokemon-showdown'); const dex = Dex.mod('champions'); const fs = require('fs');
const NAT = n => { const x = dex.natures.get(n); return x.plus === 'spe' ? 1.1 : x.minus === 'spe' ? 0.9 : 1.0; };
function spe(set, megaOK) {
  let sp = dex.species.get(set.species); const it = dex.items.get(set.item);
  if (megaOK && it.megaStone) { const f = typeof it.megaStone === 'string' ? it.megaStone : (it.megaStone[sp.name] || Object.values(it.megaStone)[0]); if (f) sp = dex.species.get(f); }
  const ev = Array.isArray(set.evs) ? set.evs[5] : set.evs.spe;
  return Math.floor((sp.baseStats.spe + 20 + ev) * NAT(set.nature));
}
const jobs = JSON.parse(fs.readFileSync(process.argv[2] || 'jobs_tr1.json')); const out = {};
for (const j of jobs) {
  const B = T.build(j.arch, j.k, j.lead, j.back);
  const mine = [...j.lead, ...j.back].map(n => spe(T.MY[n], true));
  const theirs = [...B.sets, ...B.bsets].map((s, i) => spe(s, i < 2 ? B.megaOK[i] : true));
  out[`${j.arch}|${[...j.lead].join('+')}|${j.pair}`] = {mine, theirs, m: mine.reduce((a, b) => a + b, 0) / mine.length, t: theirs.reduce((a, b) => a + b, 0) / theirs.length};
}
fs.writeFileSync(process.argv[3] || 'tr_speeds.json', JSON.stringify(out));
const d = Object.values(out).map(v => v.t - v.m); d.sort((a, b) => a - b);
console.log(Object.keys(out).length, 'jobs; their mean minus mine: min', d[0].toFixed(1), 'median', d[d.length >> 1].toFixed(1), 'max', d[d.length - 1].toFixed(1), '| jobs where theirs is slower:', d.filter(x => x < 0).length);
const worst = Object.entries(out).sort((a, b) => (a[1].t - a[1].m) - (b[1].t - b[1].m)).slice(0, 8);
for (const [k, v] of worst) console.log('  ', k, 'mine', v.mine.join('/'), 'theirs', v.theirs.join('/'));
