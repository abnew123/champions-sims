// node eg_worker.js <jobs.json> <workerIndex> <nWorkers> <outDir> <games>   (skips finished jobs)
const E = require(process.env.EG_ENGINE || './endgame.js'); const T = require('./t1sim.js'); const fs = require('fs');
const [jf, wi, nw, outDir, games] = process.argv.slice(2);
const jobs = JSON.parse(fs.readFileSync(jf)); fs.mkdirSync(outDir, {recursive: true});
// split the jobs that are still unfinished (not the full list) round-robin, so a resumed run keeps every worker busy
const pending = jobs.map((_, i) => i).filter(i => !fs.existsSync(`${outDir}/${i}.json`)).filter((_, k) => k % +nw === +wi);
for (const i of pending) {
  const j = jobs[i]; const out = `${outDir}/${i}.json`; if (fs.existsSync(out)) continue;
  const t0 = Date.now(); let r;
  if (j.theirSets) {                                            // explicit opposing sets (autopilot test): Showdown sets built here
    const {Dex} = require('./node_modules/pokemon-showdown'); const dex = Dex.mod('champions');
    const dEV = n => ['Adamant', 'Jolly', 'Naughty', 'Lonely'].includes(n) ? [2, 32, 0, 0, 0, 32] : ['Modest', 'Timid', 'Mild', 'Rash', 'Hasty', 'Naive'].includes(n) ? [2, 0, 0, 32, 0, 32]
      : n === 'Brave' ? [32, 32, 2, 0, 0, 0] : n === 'Quiet' ? [32, 0, 2, 32, 0, 0] : ['Calm', 'Careful', 'Sassy'].includes(n) ? [32, 0, 14, 0, 20, 0] : [32, 0, 20, 0, 14, 0];
    const ts = j.theirSets.map(x => T.toSet({species: x.species, item: x.item, ability: x.ability || dex.species.get(x.species).abilities['0'], moves: x.moves, nature: x.nature, evs: x.evs || dEV(x.nature)}));
    const ms = j.mine.map(n => T.toSet({...T.MY[n], species: T.MY[n].species}));
    r = E.matchupSets(ms, ts, +games, j.K, {arch: j.half, mine: j.mine, theirs: j.theirs});
  } else r = E.matchup(j.arch, j.mine, j.theirs, +games, j.K); r.w = j.w; r.ms = Date.now() - t0; r.job = i;
  fs.writeFileSync(out, JSON.stringify(r));
  console.log(new Date().toISOString().slice(11, 19), i, j.arch, j.mine.join('+'), 'vs', j.theirs.join('+'), 'K' + j.K, (r.v == null ? 'n/a' : r.v.toFixed(3)), (r.ms / 1000).toFixed(0) + 's');
}
console.log('DONE');
