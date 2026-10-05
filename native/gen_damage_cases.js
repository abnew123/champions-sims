// Differential-test cases for the native damage calc: random attacker/defender/move/field from real sets (regional team lists, ladder model,
// your team), and Showdown's damage for all 16 random rolls, without and with a critical hit. One JSON object per line.
// usage (from pssim/): node ../native/gen_damage_cases.js <n> <out.jsonl> [seed]
const path = require('path'), fs = require('fs');
const {Battle, Dex, PRNG} = require(path.resolve('node_modules/pokemon-showdown')); const dex = Dex.mod('champions');
const T = require(path.resolve('t1sim.js'));
const [N, outf, seed0 = '1'] = process.argv.slice(2);
const toID = s => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
let rs = (+seed0 * 2654435761) >>> 0;   // mulberry32
const rnd = () => { rs = (rs + 0x6D2B79F5) >>> 0; let t = rs; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; const pick = a => a[Math.floor(rnd() * a.length)];
// set pool
const pool = [];
const sd = n => ({'Female Indeedee': 'Indeedee-F', 'Eternal Flower Floette': 'Floette-Eternal', 'Female Meowstic': 'Meowstic-F'}[n] ||
  n.replace(/^(Alolan|Galarian|Hisuian|Paldean) (.+)$/, (m, r, b) => `${b}-${{Alolan: 'Alola', Galarian: 'Galar', Hisuian: 'Hisui', Paldean: 'Paldea'}[r]}`));
for (const S of Object.values(JSON.parse(fs.readFileSync('../regionals/regional_sets.json')))) for (const s of S) pool.push({...s, species: sd(s.species)});
for (const f of ['opp_model_a.json', 'opp_model_b.json']) for (const d of Object.values(JSON.parse(fs.readFileSync(f)))) for (const [sp, v] of Object.entries(d.sets)) {
  const [item, ability, nature, mv] = v.replace(/ \(.*\)$/, '').split('|'); pool.push({species: sp, item, ability, nature, moves: mv.split('/')}); }
for (const s of Object.values(JSON.parse(fs.readFileSync('myteam_7.json')))) pool.push(s);
const okSet = s => dex.species.get(s.species).exists && s.moves.every(m => dex.moves.get(m).exists) && dex.natures.get(s.nature).exists;
const P = pool.filter(okSet);
const dEV = n => ['Adamant', 'Jolly', 'Naughty', 'Lonely'].includes(n) ? [2, 32, 0, 0, 0, 32] : ['Modest', 'Timid', 'Mild', 'Rash', 'Hasty', 'Naive'].includes(n) ? [2, 0, 0, 32, 0, 32]
  : n === 'Brave' ? [32, 32, 2, 0, 0, 0] : n === 'Quiet' ? [32, 0, 2, 32, 0, 0] : ['Calm', 'Careful', 'Sassy'].includes(n) ? [32, 0, 14, 0, 20, 0] : [32, 0, 20, 0, 14, 0];
const STATS = ['hp', 'atk', 'def', 'spa', 'spd', 'spe'];
const out = fs.createWriteStream(outf); let n = 0, tries = 0;
while (n < +N && tries < +N * 20) {
  tries++;
  const A = pick(P), D = pick(P); const dmgMoves = A.moves.filter(m => dex.moves.get(m).category !== 'Status'); if (!dmgMoves.length) continue;
  const mid = toID(pick(dmgMoves)); const mv = dex.moves.get(mid);
  const evA = A.evs || dEV(A.nature), evD = D.evs || dEV(D.nature);
  const mk = (s, ev) => T.toSet({species: s.species, item: s.item, ability: s.ability || dex.species.get(s.species).abilities['0'], moves: s.moves, nature: s.nature, evs: ev});
  const filler = mk(P[0], dEV(P[0].nature));
  let b;
  try {
    b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [1, 2, 3, 4]}); b.debugMode = false;
    b.setPlayer('p1', {name: 'A', team: [mk(A, evA), filler]}); b.setPlayer('p2', {name: 'B', team: [mk(D, evD), filler]});
    b.choose('p1', 'team 12'); b.choose('p2', 'team 12');
  } catch (e) { continue; }
  const att = b.sides[0].active[0], def = b.sides[1].active[0];
  // Mega Evolve if holding its stone
  for (const p of [att, def]) { const it = dex.items.get(p.item); if (it.megaStone) { const f = it.megaStone[p.species.baseSpecies] || it.megaStone[p.species.name]; if (f) p.formeChange(f, it, true); } }
  // field
  const weather = pick(['', '', '', 'sunnyday', 'raindance', 'sandstorm', 'snowscape']); const terrain = pick(['', '', '', 'psychicterrain', 'grassyterrain', 'electricterrain', 'mistyterrain']);
  b.field.clearWeather(); b.field.clearTerrain(); if (weather) b.field.setWeather(weather, att); if (terrain) b.field.setTerrain(terrain, att);
  const screens = []; for (const sc of ['reflect', 'lightscreen', 'auroraveil']) if (rnd() < 0.12) { b.sides[1].addSideCondition(sc, def); screens.push(sc); }
  for (const p of [att, def]) for (const k of ['atk', 'def', 'spa', 'spd', 'spe']) p.boosts[k] = rnd() < 0.25 ? Math.floor(rnd() * 5) - 2 : 0;
  const hpA = rnd() < 0.5 ? 1 : 0.2 + 0.8 * rnd(), hpD = rnd() < 0.5 ? 1 : 0.2 + 0.8 * rnd();
  att.hp = Math.max(1, Math.floor(att.maxhp * hpA)); def.hp = Math.max(1, Math.floor(def.maxhp * hpD));
  const burned = rnd() < 0.1; if (burned) att.setStatus('brn', null, null, true);
  const helping = rnd() < 0.15; if (helping) att.addVolatile('helpinghand');
  const spread = ['allAdjacentFoes', 'allAdjacent'].includes(mv.target) && rnd() < 0.7; const itemD = def.item;
  const rolls = (crit) => { const r = []; for (let k = 0; k < 16; k++) {
    let m = dex.getActiveMove(mid);
    if (def.item !== itemD) { def.item = itemD; def.itemState = {id: itemD, target: def}; }      // a resist berry is eaten on the first roll: put it back
    b.random = () => k; b.randomChance = () => false;
    let d; try {
      // as in a real turn (useMoveInner): the move's own type/move hooks, then everyone's (Pixilate, Sheer Force, Weather Ball, ...)
      b.singleEvent('ModifyType', m, null, att, def, m, m); b.singleEvent('ModifyMove', m, null, att, def, m, m);
      m = b.runEvent('ModifyType', att, def, m, m); m = b.runEvent('ModifyMove', att, def, m, m);
      if (spread) m.spreadHit = true; m.willCrit = crit; m.hit = 1;   // per-hit power (Triple Axel) uses the hit number
      d = b.actions.getDamage(att, def, m, true);
    } catch (e) { d = 'ERR'; }
    r.push(d === false ? null : d === undefined ? null : d); } return r; };
  const r0 = rolls(false), r1 = rolls(true);
  if (r0.includes('ERR')) continue;
  const mon = p => ({species: p.species.id, item: p === def ? toID(itemD) : toID(p.item), ability: toID(p.ability), nature: p.set.nature, sp: Object.fromEntries(STATS.map((s, i) => [s, p.set.evs[s]])),
                     boosts: {...p.boosts}, hp: p.hp, maxhp: p.maxhp, status: p.status || '', stats: {...p.storedStats}});
  out.write(JSON.stringify({id: n, attacker: mon(att), defender: mon(def), move: mid, field: {weather, terrain, screens, spread, helping}, rolls: r0, critRolls: r1}) + '\n');
  n++;
}
out.end(); console.log(`${n} cases (${tries} tries) -> ${outf}`);
