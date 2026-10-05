// Two-turn spot check: does planning one turn ahead (what the 2v2 batches do) pick worse mixes than looking two turns ahead?
// For sampled positions: solve the one-turn game; keep each side's top K options; re-score those K x K cells by playing the turn
// and solving the NEXT turn in full (its game value); solve that deeper K x K game and compare.
//   usage: MYTEAM=... EG_SEEDS=2 node eg_depth2.js <jobs.json> <workerIndex> <nWorkers> <outDir> [K=6]
const E = require('./endgame2.js'); const fs = require('fs');
const [jf, wi, nw, outDir, Karg = '6'] = process.argv.slice(2); const K = +Karg; const NS = +(process.env.EG_SEEDS || 2);
const jobs = JSON.parse(fs.readFileSync(jf)); fs.mkdirSync(outDir, {recursive: true});
const dot = (x, M, y) => M.reduce((t, r, a) => t + x[a] * r.reduce((u, v, c) => u + v * y[c], 0), 0);
const top = (p, score, k) => p.map((v, i) => [v, score[i], i]).sort((a, b) => b[0] - a[0] || b[1] - a[1]).slice(0, k).map(z => z[2]).sort((a, b) => a - b);
for (let n = +wi; n < jobs.length; n += +nw) {
  const out = `${outDir}/${n}.json`; if (fs.existsSync(out)) continue;
  const j = jobs[n]; const [ms, ts] = E.sets(j.arch, j.mine, j.theirs); const t0 = Date.now();
  const lg = []; lg.snaps = []; E.playGame(ms, ts, 0, j.K, lg);       // one game; positions at the start of turns 1-3
  let res = null;
  for (const [t, s] of lg.snaps.slice(0, 3).entries()) {
    const b = E.Battle.fromJSON(s); const seeds = Array.from({length: NS}, (_, k) => E.seedmix(9e6 + n * 10 + t + 1e5 * k));
    const s1 = E.solveTurn(b, seeds); if (!s1.x || s1.R.length < 4 || s1.C.length < 4) continue;
    const rv = s1.M.map(r => r.reduce((u, v, c) => u + v * s1.y[c], 0)), cv = s1.C.map((_, c) => -s1.M.reduce((u, r, a) => u + r[c] * s1.x[a], 0));
    const ri = top(s1.x, rv, K), ci = top(s1.y, cv, K);
    const M2 = ri.map(i => ci.map(jj => {
      let tot = 0;
      for (const sd of seeds) {
        const c = E.Battle.fromJSON(s1.snap); c.prng = new E.PRNG(sd);
        c.choose('p1', s1.R[i]); c.choose('p2', s1.C[jj]);
        if (c.ended) { tot += E.value(c); continue; }
        const s2 = E.solveTurn(c, seeds.map(z => z.map((w, q) => (w + 7919 * (q + 1)) % 65536)));
        tot += s2.v == null ? E.value(c) : s2.v;
      }
      return tot / seeds.length;
    }));
    const M1 = ri.map(i => ci.map(jj => s1.M[i][jj]));
    const [x2, y2] = E.nash(M2), [x1k, y1k] = E.nash(M1);         // deep and one-turn equilibria on the same K x K options
    const v2 = dot(x2, M2, y2);
    res = {arch: j.arch, mine: j.mine, theirs: j.theirs, K: j.K, turn: t + 1, size: [s1.R.length, s1.C.length],
      v1: +dot(x1k, M1, y1k).toFixed(4), v2: +v2.toFixed(4),
      myLoss: +(v2 - dot(x1k, M2, y2)).toFixed(4),            // my one-turn mix vs their deep mix, scored two turns deep
      theirLoss: +(dot(x2, M2, y1k) - v2).toFixed(4),         // their one-turn mix vs my deep mix
      sameTopMine: x1k.indexOf(Math.max(...x1k)) === x2.indexOf(Math.max(...x2)), sameTopTheirs: y1k.indexOf(Math.max(...y1k)) === y2.indexOf(Math.max(...y2)),
      my1: ri.map((i, k) => [E.label(b, b.sides[0], s1.R[i]), +x1k[k].toFixed(2), +x2[k].toFixed(2)]),
      th1: ci.map((i, k) => [E.label(b, b.sides[1], s1.C[i]), +y1k[k].toFixed(2), +y2[k].toFixed(2)]), ms: Date.now() - t0};
    break;
  }
  fs.writeFileSync(out, JSON.stringify(res || {skip: true, arch: j.arch}));
  console.log(new Date().toISOString().slice(11, 19), n, j.arch, j.mine.join('+'), 'vs', j.theirs.join('+'), res ? `turn ${res.turn} myLoss ${res.myLoss} theirLoss ${res.theirLoss} ${(res.ms / 1000).toFixed(0)}s` : 'skip');
}
console.log('DONE');
