// node worker.js <jobs.json> <workerIndex> <nWorkers> <outDir> <seedStart> <nSeeds>
const T = require('./t1sim.js'); const fs = require('fs');
const [jf, wi, nw, outDir, s0, ns] = process.argv.slice(2);
const jobs = JSON.parse(fs.readFileSync(jf)); fs.mkdirSync(outDir, {recursive: true});
const seeds = Array.from({length: +ns}, (_, k) => require('./seedmix.js')(+s0 + k));
for (let i = +wi; i < jobs.length; i += +nw) {
  const j = jobs[i]; const out = `${outDir}/${i}.json`; if (fs.existsSync(out)) continue;
  const t0 = Date.now(); const B = T.build(j.arch, j.k, j.lead, j.back);
  if (j.rows) { B.myActs = B.myActs.filter(a => j.rows.includes(a.label)); }
  const r = T.run(B, seeds); r.ms = Date.now() - t0; r.job = i;
  fs.writeFileSync(out, JSON.stringify(r));
  console.log(new Date().toISOString().slice(11, 19), i, j.arch, '|', j.pair, '|', j.lead.join('+'), r.myActs.length + 'x' + r.thActs.length, (r.ms / 1000).toFixed(0) + 's bad ' + r.bad);
}
console.log('DONE');
