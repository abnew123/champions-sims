// Differential-test cases for the native turn engine: random doubles positions from real sets, random legal choices, one turn played by
// Showdown with its random generator forced to a deterministic mode ("lo": every draw returns its lowest value, so max damage rolls and every
// crit / secondary / accuracy check / speed-tie draw takes the first option; "hi": every draw returns its highest value), plus normal RNG.
// Exports the state before and after the turn in a plain JSON form the native engine reads.
// usage (from pssim/): node ../native/gen_turn_cases.js <n> <out.jsonl> [seed] [supported.json]
const path = require('path'), fs = require('fs');
const {Battle, Dex} = require(path.resolve('node_modules/pokemon-showdown')); const dex = Dex.mod('champions');
const T = require(path.resolve('t1sim.js'));
const [N, outf, seed0 = '1', suppf] = process.argv.slice(2);
const toID = s => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
let rs = (+seed0 * 2654435761) >>> 0;
const rnd = () => { rs = (rs + 0x6D2B79F5) >>> 0; let t = rs; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const pick = a => a[Math.floor(rnd() * a.length)];
// supported subset (moves / abilities / items the native engine implements); sets outside it are skipped
const SUP = suppf ? JSON.parse(fs.readFileSync(suppf)) : null;
const supported = s => !SUP || (SUP.items.includes(toID(s.item)) && SUP.abilities.includes(toID(s.ability || dex.species.get(s.species).abilities['0'])) && s.moves.some(m => SUP.moves.includes(toID(m))));
// set pool (same sources as the damage cases)
const pool = [];
const sd = n => ({'Female Indeedee': 'Indeedee-F', 'Eternal Flower Floette': 'Floette-Eternal', 'Female Meowstic': 'Meowstic-F'}[n] ||
  n.replace(/^(Alolan|Galarian|Hisuian|Paldean) (.+)$/, (m, r, b) => `${b}-${{Alolan: 'Alola', Galarian: 'Galar', Hisuian: 'Hisui', Paldean: 'Paldea'}[r]}`));
for (const S of Object.values(JSON.parse(fs.readFileSync('../regionals/regional_sets.json')))) for (const s of S) pool.push({...s, species: sd(s.species)});
for (const f of ['opp_model_a.json', 'opp_model_b.json']) for (const d of Object.values(JSON.parse(fs.readFileSync(f)))) for (const [sp, v] of Object.entries(d.sets)) {
  const [item, ability, nature, mv] = v.replace(/ \(.*\)$/, '').split('|'); pool.push({species: sp, item, ability, nature, moves: mv.split('/')}); }
for (const s of Object.values(JSON.parse(fs.readFileSync('myteam_7.json')))) pool.push(s);
// FOCUS_POOL=<json: [sets]> adds sets to the pool (e.g. ladder sets with a mechanic under test); FOCUS=<comma list of species / ability / item /
// move ids> makes every team include at least one set matching one of them (2026-10-09, for porting checks of rarer mechanics)
if (process.env.FOCUS_POOL) for (const s of JSON.parse(fs.readFileSync(process.env.FOCUS_POOL))) pool.push(s);
const P = pool.filter(s => dex.species.get(s.species).exists && s.moves.every(m => dex.moves.get(m).exists) && dex.natures.get(s.nature).exists).filter(supported);
const FOCUS = process.env.FOCUS ? process.env.FOCUS.split(',').map(toID) : null;
const isFocus = s => FOCUS && (FOCUS.includes(toID(s.species)) || FOCUS.includes(toID(s.ability || dex.species.get(s.species).abilities['0'])) || FOCUS.includes(toID(s.item)) || s.moves.some(m => FOCUS.includes(toID(m))));
const PF = FOCUS ? P.filter(isFocus) : [];
if (FOCUS) console.log(`${PF.length} focus sets of ${P.length}`);
const dEV = n => ['Adamant', 'Jolly', 'Naughty', 'Lonely'].includes(n) ? [2, 32, 0, 0, 0, 32] : ['Modest', 'Timid', 'Mild', 'Rash', 'Hasty', 'Naive'].includes(n) ? [2, 0, 0, 32, 0, 32]
  : n === 'Brave' ? [32, 32, 2, 0, 0, 0] : n === 'Quiet' ? [32, 0, 2, 32, 0, 0] : ['Calm', 'Careful', 'Sassy'].includes(n) ? [32, 0, 14, 0, 20, 0] : [32, 0, 20, 0, 14, 0];
const mk = s => T.toSet({species: s.species, item: s.item, ability: s.ability || dex.species.get(s.species).abilities['0'], moves: s.moves, nature: s.nature, evs: s.evs || dEV(s.nature)});
// deterministic random generators
function fakePRNG(mode) {
  const r = (from, to) => from === undefined ? {lo: 0, hi: 0.999999, mid: 0.5}[mode] : to === undefined ? {lo: 0, hi: from - 1, mid: Math.floor(from / 2)}[mode] : {lo: from, hi: to - 1, mid: from + Math.floor((to - from) / 2)}[mode];
  const p = {random: r, randomChance: (n, d) => r(d) < n, sample: items => items[r(items.length)],
    shuffle(items, start = 0, end = items.length) { while (start < end - 1) { const ni = r(start, end); if (start !== ni) [items[start], items[ni]] = [items[ni], items[start]]; start++; } },
    getSeed: () => 'fake', startingSeed: 'fake', clone() { return fakePRNG(mode); }};
  return p;
}
const {exportState} = require(path.resolve(__dirname, 'export_state.js'));
function choicesFor(b, side) {
  const out = [];
  for (let i = 0; i < 2; i++) {
    const p = side.active[i], req = side.activeRequest && side.activeRequest.active && side.activeRequest.active[i];
    if (!p || p.fainted || !req) { out.push('pass'); continue; }
    const opts = [];
    req.moves.forEach((m, k) => { if (m.disabled) return; const mv = dex.moves.get(m.id); if (SUP && !SUP.moves.includes(mv.id)) return;
      if (['normal', 'any', 'adjacentFoe'].includes(mv.target)) { for (const t of [1, 2]) if (side.foe.active[t - 1] && !side.foe.active[t - 1].fainted) opts.push(`move ${k + 1} ${t}`); }
      else if (mv.target === 'adjacentAlly') { if (side.active[1 - i] && !side.active[1 - i].fainted) opts.push(`move ${k + 1} ${i === 0 ? -2 : -1}`); }
      else opts.push(`move ${k + 1}`); });
    // switching (only when a bench exists): about 15% of the time when legal
    const bench = side.pokemon.map((q, k) => k).filter(k => k >= 2 && !side.pokemon[k].fainted && !out.includes(`switch ${k + 1}`));
    if (bench.length && !req.trapped && !req.maybeTrapped && rnd() < 0.15) { out.push(`switch ${pick(bench) + 1}`); continue; }
    if (!opts.length) return null;
    let c = pick(opts);
    if (req.canMegaEvo && !out.some(x => x.includes('mega')) && rnd() < 0.7) c += ' mega';
    out.push(c);
  }
  return out.join(', ');
}
const out = fs.createWriteStream(outf); let n = 0, tries = 0;
while (n < +N && tries < +N * 30) {
  tries++;
  const NT = +(process.env.TEAM || 2);  // 2 = no bench (the 2v2 endgame setting; no switch requests)
  const team = side => { const t = []; let g = 0;   // species clause, as in real teams
    while (t.length < NT && g++ < 100) { const x = (FOCUS && t.length === 0 && PF.length) ? pick(PF) : pick(P); const bs = dex.species.get(x.species).baseSpecies; if (!t.some(y => dex.species.get(y.species).baseSpecies === bs)) t.push(x); }
    return t.map(mk); };
  const t1 = team(), t2 = team();
  const modes = ['lo', 'hi', 'mid', 'real'];
  let base;
  try {
    base = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [1, 2, 3, Math.floor(rnd() * 60000)]}); base.debugMode = false;
    base.setPlayer('p1', {name: 'A', team: t1}); base.setPlayer('p2', {name: 'B', team: t2}); base.choose('p1', 'team ' + '1234'.slice(0, NT)); base.choose('p2', 'team ' + '1234'.slice(0, NT));
  } catch (e) { continue; }
  if (base.ended || base.sides.some(s => s.activeRequest && s.activeRequest.forceSwitch)) continue;
  // random mid-battle field and state
  for (const s of base.sides) for (const p of s.active) { if (!p) continue;
    if (rnd() < 0.4) p.hp = Math.max(1, Math.floor(p.maxhp * (0.15 + 0.85 * rnd())));
    for (const k of ['atk', 'def', 'spa', 'spd', 'spe']) if (rnd() < 0.15) p.boosts[k] = Math.floor(rnd() * 5) - 2; }
  if (rnd() < 0.3) { base.field.addPseudoWeather('trickroom', base.sides[0].active[0]); base.field.pseudoWeather.trickroom.duration = 1 + Math.floor(rnd() * 4); }
  if (rnd() < 0.2) { const s = pick(base.sides); s.addSideCondition('tailwind', s.active[0]); s.sideConditions.tailwind.duration = 1 + Math.floor(rnd() * 4); }
  const c1 = choicesFor(base, base.sides[0]), c2 = choicesFor(base, base.sides[1]);
  if (!c1 || !c2) continue;
  const pre = exportState(base); const snap = JSON.stringify(base.toJSON());
  const res = {};
  let ok = true;
  for (const mode of modes) {
    const b = Battle.fromJSON(snap); b.debugMode = false;
    if (mode !== 'real') b.prng = fakePRNG(mode);
    const logStart = b.log.length;
    let r1, r2; try { r1 = b.choose('p1', c1); r2 = b.choose('p2', c2); } catch (e) { ok = false; break; }
    if (!r1 || !r2) { ok = false; break; }
    // mid-turn / end-of-turn switch requests (U-turn, faints with a bench): answered with random legal switches, recorded for the replay
    const switches = []; let guard = 0;
    while (!b.ended && b.requestState === 'switch' && guard++ < 10) {
      for (const s of b.sides) {
        const req = s.activeRequest; if (!req || !req.forceSwitch) continue;
        let avail = s.pokemon.map((q, k) => k).filter(k => k >= 2 && !s.pokemon[k].fainted); const parts = [];
        for (let i = 0; i < 2; i++) {
          if (!req.forceSwitch[i] || !avail.length) { parts.push('pass'); continue; }
          const k = pick(avail); avail = avail.filter(x => x !== k); parts.push(`switch ${k + 1}`);
        }
        const c = parts.join(', '); switches.push([s.n, c]);
        try { if (!b.choose(s.id, c)) { ok = false; } } catch (e) { ok = false; }
        if (!ok) break;
      }
      if (!ok) break;
    }
    if (!ok || b.requestState === 'switch') { ok = false; break; }
    res[mode] = {switches, post: exportState(b), log: b.log.slice(logStart).filter(l => /^\|(move|-damage|-heal|faint|cant|-fail|-miss|-immune|-activate|-boost|-unboost|-status|-crit|-start|-end|-sidestart|-sideend|-fieldstart|-fieldend|-weather|-mega|-enditem|-item|switch|turn|upkeep)\|/.test(l))};
  }
  if (!ok) continue;
  out.write(JSON.stringify({id: n, choices: [c1, c2], pre, ...res}) + '\n'); n++;
}
out.end(); console.log(`${n} turn cases (${tries} tries) -> ${outf}`);
