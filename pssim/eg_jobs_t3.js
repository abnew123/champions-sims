// Jobs for the final 2v2: every pair of my six vs N opposing pairs per archetype, drawn (without replacement) in proportion to how
// often each pair is on the field at the start of turn 3 in public replays (endpairs.json); weights = those frequencies.
//   usage: MYTEAM=... node eg_jobs_t3.js <out.json> [N=8] [K=3]
const T = require('./t1sim.js'); const fs = require('fs');
const [outf, N = '8', K = '3'] = process.argv.slice(2);
const MAP = {'Tailwind': 'Tailwind goodstuffs', 'Indeedee TR': 'Indeedee TR / Psychic Terrain', 'Balance': 'Balance, no speed control',
  'Trick Room': 'Trick Room without Indeedee', 'Rain + Sun': 'Rain + sun', 'Perish': 'Perish trap', 'Sun': 'Sun', 'Rain': 'Rain', 'Sand': 'Sand', 'Snow': 'Snow'};
const rows = JSON.parse(fs.readFileSync('endpairs.json')).rows;
let rs = 12345; const rnd = () => (rs = (rs * 1103515245 + 12345) % 2147483648) / 2147483648;
const SIX = Object.keys(T.MY); const jobs = []; const info = {};
for (const [tab, arch] of Object.entries(MAP)) {
  const cnt = {};
  for (const r of rows) if (r.arch === tab && r.t3 && r.t3.length === 2) { const k = r.t3.join(','); cnt[k] = (cnt[k] || 0) + 1; }
  const ok = k => { try { k.split(',').forEach(s => T.oppSet(arch, s, [])); return true; } catch (e) { return false; } };
  let pool = Object.entries(cnt).filter(([k]) => ok(k)); const tot = pool.reduce((t, [, n]) => t + n, 0); const pick = [];
  while (pick.length < +N && pool.length) {
    let x = rnd() * pool.reduce((t, [, n]) => t + n, 0), i = 0;
    for (; i < pool.length - 1; i++) { x -= pool[i][1]; if (x <= 0) break; }
    pick.push(pool[i]); pool.splice(i, 1);
  }
  info[arch] = pick.map(([k, n]) => `${k} ${(100 * n / tot).toFixed(1)}%`);
  for (const [k, n] of pick) for (let a = 0; a < 6; a++) for (let c = a + 1; c < 6; c++) for (const k2 of [+K, 0])
    jobs.push({arch, mine: [SIX[a], SIX[c]], theirs: k.split(","), w: +(1 / pick.length).toFixed(4), freq: +(n / tot).toFixed(4), K: k2});   // drawn by frequency, so weighted equally
}
fs.writeFileSync(outf, JSON.stringify(jobs)); console.log(jobs.length, 'jobs');
for (const a in info) console.log(a.slice(0, 28).padEnd(28), '|', info[a].join('; '));
