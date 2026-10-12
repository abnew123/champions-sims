// The reachability check (reach.py): each turn's position rebuilt as positions.js does, the choices the log shows played in Showdown over
// many seeds, the replacements the log shows sent in, and a summary of where each seed leaves the battle at the next turn's start.
// usage (from the main folder's pssim/): node <this file> <cases.json> <out.json>
// case: {spec, choose: {p1: '<choose string>', p2: ...}, replace: {p1: [species], p2: [...]}, seeds: n}
// out: [{states: [summary per seed], error}] in the same order; summary: {field: {weather, terrain, tr}, sides: {p1: {tailwind, screens,
// mons: [{sp, active, hp, maxhp, fnt, status, boosts}]}, ...}, turnDone}
const path = require('path'), fs = require('fs');
const {rebuild, dex, toID} = require(path.join(__dirname, 'positions.js'));
const {PRNG} = require(path.resolve('node_modules/pokemon-showdown/dist/sim/prng'));
const [cf, outf] = process.argv.slice(2);
const base = sp => dex.species.get(sp).baseSpecies;
function summary(b) {
  const sides = {};
  for (const [si, side] of b.sides.entries()) {
    const sc = side.sideConditions;
    sides['p' + (si + 1)] = {tailwind: !!sc.tailwind, screens: ['reflect', 'lightscreen', 'auroraveil'].filter(c => sc[c]).sort(),
      mons: side.pokemon.map(p => ({sp: base(p.species.name), active: p.isActive && !p.fainted, hp: p.hp, maxhp: p.maxhp, fnt: !!p.fainted || p.hp <= 0,
                                    status: p.fainted ? '' : p.status || '', boosts: Object.fromEntries(Object.entries(p.boosts).filter(([, v]) => v))}))};
  }
  return {field: {weather: b.field.weather || '', terrain: b.field.terrain || '', tr: !!b.field.pseudoWeather.trickroom}, sides};
}
function play(c, seed, mode) {
  const {b} = rebuild(c.spec, false);
  b.prng = new PRNG(seed);
  // besides the seeds: every chance roll succeeding (crits, secondaries, accuracy) with the highest damage ('hi') and none with the lowest
  // ('lo'); and the typical turn, the likely chances happening and the unlikely not (hits land, no crit, no 10% secondary), at the highest
  // and the lowest damage ('typ+', 'typ-')
  // and 'sec+' / 'sec-': every added effect happening (a move's secondaries, a 30% contact ability) but nothing else unlikely (no crit,
  // no full paralysis), at the highest and the lowest damage: a 10% effect on a target that lives is otherwise rare in the seeds
  if (mode) {
    const top = mode === 'hi' || mode === 'typ+' || mode === 'sec+', sec = mode.startsWith('sec');
    b.randomChance = mode === 'hi' ? () => true : mode === 'lo' ? (num, den) => num >= den : sec ? (num, den) => num / den >= 0.5 || den === 10 : (num, den) => num / den >= 0.5;
    b.random = (m, n) => { if (n === undefined) { n = m; m = 0; } if (n === 100 && !m) return sec ? 0 : mode.startsWith('typ') ? 99 : top ? 0 : 99; return top ? (m || 0) : Math.max(m || 0, (n || 1) - 1); };
  }
  const t0 = b.turn, sides = ['p1', 'p2'], left = {p1: [...(c.replace.p1 || [])], p2: [...(c.replace.p2 || [])]};
  for (const sd of sides) if (!b.choose(sd, c.choose[sd] || 'default')) b.choose(sd, 'default');
  for (let guard = 0; b.turn === t0 && !b.ended && guard < 8; guard++) {                // switch requests mid-turn and at its end
    for (const [si, side] of b.sides.entries()) {
      if (side.requestState !== 'switch') continue;
      const sd = sides[si], req = side.activeRequest, need = (req && req.forceSwitch) || [];
      const used = new Set(), parts = need.map(f => {
        if (!f) return 'pass';
        const want = left[sd].shift(); let k = -1;
        if (want) k = side.pokemon.findIndex((p, i) => !used.has(i) && !p.isActive && !p.fainted && base(p.species.name) === base(want));
        if (k < 0) k = side.pokemon.findIndex((p, i) => !used.has(i) && !p.isActive && !p.fainted);
        if (k < 0) return 'pass';
        used.add(k); return 'switch ' + (k + 1);
      });
      if (!b.choose(sd, parts.join(', '))) b.choose(sd, 'default');
    }
  }
  return {...summary(b), turnDone: b.turn > t0 || b.ended, ...(c.debug ? {log: b.log.slice(-60).filter(l => !l.startsWith('|t:|') && !l.startsWith('|split'))} : {})};
}
const out = JSON.parse(fs.readFileSync(cf)).map(c => {
  try { const states = ['hi', 'lo', 'typ+', 'typ-', 'sec+', 'sec-'].map(m => play(c, [1, 2, 3, 4], m)); for (let s = 0; s < (c.seeds || 32); s++) states.push(play(c, [s + 1, 7, 11, 13])); return {states}; }
  catch (e) { return {error: String(e.message).slice(0, 160)}; }
});
fs.writeFileSync(outf, JSON.stringify(out));
