// Starting positions + seeds for the native 2v2 planner (champ plan): for each job and game, the battle endgame2.js's start() builds
// (both sides' two Pokemon out, Trick Room with K turns left), exported with export_state.js, plus every seed playGame would use:
// the sampling RNG seed and the planning seeds per turn. Team building matches eg_worker_v2.js (MYTEAM, EG_KMIX as there).
// usage (from pssim/): MYTEAM=... EG_KMIX=1 node ../native/eg_starts.js <jobs.json> <out.jsonl> <games> [planning seeds per cell=EG_SEEDS]
const path = require('path'), fs = require('fs');
const {Battle, Dex} = require(path.resolve('node_modules/pokemon-showdown')); const dex = Dex.mod('champions');
const T = require(path.resolve('t1sim.js')); const seedmix = require(path.resolve('seedmix.js'));
const {exportState} = require(path.resolve(__dirname, 'export_state.js'));
const [jf, outf, games = '4', nsArg] = process.argv.slice(2); const NS = +(nsArg || process.env.EG_SEEDS || 1); const MAXTURN = 15;
const jobs = JSON.parse(fs.readFileSync(jf)); const out = fs.createWriteStream(outf);
const dEV = n => ['Adamant', 'Jolly', 'Naughty', 'Lonely'].includes(n) ? [2, 32, 0, 0, 0, 32] : ['Modest', 'Timid', 'Mild', 'Rash', 'Hasty', 'Naive'].includes(n) ? [2, 0, 0, 32, 0, 32]
  : n === 'Brave' ? [32, 32, 2, 0, 0, 0] : n === 'Quiet' ? [32, 0, 2, 32, 0, 0] : ['Calm', 'Careful', 'Sassy'].includes(n) ? [32, 0, 14, 0, 20, 0] : [32, 0, 20, 0, 14, 0];
const only = process.env.JOBS ? new Set(process.env.JOBS.split(',').map(Number)) : null;
let n = 0;
jobs.forEach((j, i) => {
  if (only && !only.has(i)) return;
  const ms = j.mine.map(m => T.toSet({...T.MY[m], species: T.MY[m].species}));
  const ts = j.theirSets ? j.theirSets.map(x => T.toSet({species: x.species, item: x.item, ability: x.ability || dex.species.get(x.species).abilities['0'], moves: x.moves, nature: x.nature, evs: x.evs || dEV(x.nature)}))
                         : j.theirs.map(sp => T.toSet(T.oppSet(j.arch, sp, [])));
  for (let g = 0; g < +games; g++) {
    const K = process.env.EG_KMIX && j.K > 0 ? [2, 3, 3, 4][g % 4] : j.K;
    const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: seedmix(1e6 + g)}); b.debugMode = false;
    b.setPlayer('p1', {name: 'Me', team: ms}); b.setPlayer('p2', {name: 'Them', team: ts});
    b.choose('p1', 'team 12'); b.choose('p2', 'team 12');
    if (K > 0) { b.field.addPseudoWeather('trickroom', b.sides[0].active[0]); b.field.pseudoWeather.trickroom.duration = K; }
    const r = seedmix(7e6 + g);
    const cseeds = Array.from({length: MAXTURN}, (_, t) => Array.from({length: NS}, (_, k) => seedmix(3e6 + g * 50 + (t + 1) + 1e5 * k)));
    out.write(JSON.stringify({job: i, g, K, meta: {arch: j.half || j.arch, mine: j.mine, theirs: j.theirs, w: j.w}, rng: r[0] * 65536 + r[1], cseeds, state: exportState(b)}) + '\n'); n++;
  }
});
out.end(); console.log(`${n} starting positions -> ${outf}`);
