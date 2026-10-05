// Starting positions for full 4v4 battles (champ battle): team preview resolved by t1sim.build (my lead + back two from the job; their
// lead pair k and back two from the replay model of the archetype), turn 1 not yet played. One line per job and game.
// usage (from pssim/): MYTEAM=... node ../native/battle_starts.js <jobs.json> <out.jsonl> <games> [first game index G0=0]
//   jobs: [{arch, k (their lead pair index), lead: [a, b], back: [c, d]}]  -> both sides from t1sim.build (archetype replay model)
//     or  [{mine: [4 sets], theirs: [4 sets], meta: {...}}]                 -> explicit teams, in order lead, lead, back, back;
//         sets in MYTEAM format {species, item, ability, nature, evs: [6], moves: [4]}
//   game g (G0 .. G0+games-1) uses battle seed seedmix(1e6 + g) and sampling seed seedmix(7e6 + g); champ battle derives the planning
//   seeds from (job index, g), so two runs with the same job order and G0 play paired games (same RNG streams).
const path = require('path'), fs = require('fs');
const {Battle} = require(path.resolve('node_modules/pokemon-showdown'));
const T = require(path.resolve('t1sim.js')); const seedmix = require(path.resolve('seedmix.js'));
const {exportState} = require(path.resolve(__dirname, 'export_state.js'));
const [jf, outf, games = '8', g0 = '0'] = process.argv.slice(2);
const jobs = JSON.parse(fs.readFileSync(jf)); const out = fs.createWriteStream(outf); let n = 0;
jobs.forEach((j, i) => {
  const mk = s => T.toSet({species: s.species, item: s.item, ability: s.ability, moves: s.moves, nature: s.nature, evs: s.evs});
  const B = j.mine ? {myTeam: j.mine.map(mk), oppTeam: j.theirs.map(mk), P: {pair: j.theirs.slice(0, 2).map(s => s.species).join(' + '), share: 1}}
                   : T.build(j.arch, j.k, j.lead, j.back);
  for (let g = +g0; g < +g0 + +games; g++) {
    const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: seedmix(1e6 + g)}); b.debugMode = false;
    b.setPlayer('p1', {name: 'Me', team: B.myTeam}); b.setPlayer('p2', {name: 'Them', team: B.oppTeam});
    b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
    const r = seedmix(7e6 + g);
    const meta = j.mine ? {...(j.meta || {}), lead: j.mine.slice(0, 2).map(s => s.species), back: j.mine.slice(2).map(s => s.species), pair: B.P.pair, share: 1,
                           theirs: j.theirs.map(s => s.species)}
                        : {arch: j.arch, lead: j.lead, back: j.back, pair: B.P.pair, share: B.P.share, theirs: B.oppTeam.map(s => s.species)};
    // seedKey: what champ-battle-v3 derives its turn/planning seeds from (with g), so every team or bring facing the same opponent shares
    // them (common random numbers): archetype mode keys on (arch, their lead pair k); explicit mode on their four in order
    const seedKey = j.mine ? 'x|' + j.theirs.map(s => s.species).join(',') : `a|${j.arch}|${j.k}`;
    out.write(JSON.stringify({job: i, g, seedKey, meta, rng: r[0] * 65536 + r[1], state: exportState(b)}) + '\n'); n++;
  }
});
out.end(); console.log(`${n} starting positions (${jobs.length} jobs) -> ${outf}`);
