// node eg_worker.js <jobs.json> <workerIndex> <nWorkers> <outDir> <games>   (skips finished jobs)
const E = require('./endgame.js'); const fs = require('fs');
const [jf, wi, nw, outDir, games] = process.argv.slice(2);
const jobs = JSON.parse(fs.readFileSync(jf)); fs.mkdirSync(outDir, {recursive: true});
for (let i = +wi; i < jobs.length; i += +nw) {
  const j = jobs[i]; const out = `${outDir}/${i}.json`; if (fs.existsSync(out)) continue;
  const t0 = Date.now(); const r = E.matchup(j.arch, j.mine, j.theirs, +games, j.K); r.w = j.w; r.ms = Date.now() - t0; r.job = i;
  fs.writeFileSync(out, JSON.stringify(r));
  console.log(new Date().toISOString().slice(11, 19), i, j.arch, j.mine.join('+'), 'vs', j.theirs.join('+'), 'K' + j.K, r.v.toFixed(3), (r.ms / 1000).toFixed(0) + 's');
}
console.log('DONE');
