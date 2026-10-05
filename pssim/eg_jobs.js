// Jobs for the 2v2 endgame: every pair of my six vs each archetype's most likely back pairs, Trick Room up (K turns) and down.
// Their back pairs come from the replay back-row rates of each common lead pair: P(i,j) ~ share x r_i x r_j.
//   usage: MYTEAM=myteam_c_incin.json node eg_jobs.js <out.json> [topPairs=5] [K=3]
const T = require('./t1sim.js'); const fs = require('fs');
const [outf, top = '5', K = '3'] = process.argv.slice(2);
const SIX = Object.keys(T.MY); const jobs = []; const info = {};
for (const arch of Object.keys(T.OPP)) {
  const pp = {};
  for (const p of T.OPP[arch].pairs) {
    const lead = p.pair.split(' + ');
    const b = p.back.split(', ').map(x => { const i = x.lastIndexOf(':'); return [x.slice(0, i), +x.slice(i + 1)]; }).filter(([s]) => !lead.includes(s));
    let tot = 0; const loc = {};
    for (let i = 0; i < b.length; i++) for (let j = i + 1; j < b.length; j++) { const k = [b[i][0], b[j][0]].sort().join(','); loc[k] = b[i][1] * b[j][1]; tot += loc[k]; }
    for (const k in loc) pp[k] = (pp[k] || 0) + p.share * loc[k] / tot;
  }
  const list = Object.entries(pp).sort((a, b) => b[1] - a[1]); const tot = list.reduce((a, b) => a + b[1], 0);
  const keep = list.slice(0, +top).filter(([k]) => { try { k.split(',').forEach(s => T.oppSet(arch, s, [])); return true; } catch (e) { return false; } });
  info[arch] = keep.map(([k, v]) => [k, +(v / tot).toFixed(3)]);
  for (const [k, v] of keep) for (let a = 0; a < 6; a++) for (let c = a + 1; c < 6; c++) for (const k2 of [+K, 0])
    jobs.push({arch, mine: [SIX[a], SIX[c]], theirs: k.split(','), w: +(v / tot).toFixed(4), K: k2});
}
fs.writeFileSync(outf, JSON.stringify(jobs));
console.log(jobs.length, 'jobs'); for (const a in info) console.log(a, '|', info[a].map(([k, v]) => `${k} ${(100 * v).toFixed(0)}%`).join('; '));
