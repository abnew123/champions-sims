// Engine states for replay positions (the eval bar). Each spec from spots.py (both teams' sets and every Pokemon's state at the start of a
// turn) is rebuilt in Showdown and exported in the engine's state format, once from each player's side: line "<name> p1" has replay
// player 1 as the engine's side 0, line "<name> p2" has player 2 there. Team order: slot a, slot b, then the bench.
// Each line: {name, turn, side, perish, standIns, dropped, approx, state, actual, their_actual}. dropped: moves and items left out of the sets
// because the engine data lacks them. perish: Perish Song has been used (the planner cannot
// play the trap). standIns: brought Pokemon that never appeared and were filled in from the team sheet. actual / their_actual: what each slot of side 0 / side 1 chose, as the
// engine's choice ([move index, target, mega] or ['switch', team index]); null for a slot whose choice the log does not show (flinched,
// fainted first). approx: state details that were left out.
// usage (from the main folder's pssim/, where node_modules is): node <this file> <specs.json> <out.jsonl> [both|p1]   (engine.py does this)
const path = require('path'), fs = require('fs');
const {Battle, Dex} = require(path.resolve('node_modules/pokemon-showdown')); const dex = Dex.mod('champions');
const T = require(path.resolve('t1sim.js'));
const {exportState} = require(path.resolve('../native/export_state.js'));
const toID = s => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const [specf, outf, views = 'both'] = process.argv.slice(2);
const WEATHER = {Rain: 'raindance', Sun: 'sunnyday', Sandstorm: 'sandstorm', Snow: 'snowscape', Hail: 'hail', 'Harsh sun': 'desolateland', 'Heavy rain': 'primordialsea', 'Strong winds': 'deltastream'};
const VOL = {confusion: 'confusion', Taunt: 'taunt', 'Leech Seed': 'leechseed', 'Throat Chop': 'throatchop', Yawn: 'yawn', 'Heal Block': 'healblock', Substitute: 'substitute',
             Imprison: 'imprison', 'Flash Fire': 'flashfire'};
const STATS = ['atk', 'def', 'spa', 'spd', 'spe', 'accuracy', 'evasion'];
// the engine's data: this Showdown package gives three Megas an older ability (Mega Golisopod Emergency Exit for Tough Claws, Mega
// Garchomp Z Sand Force for Levitate, Mega Absol Z Magic Bounce for Sharpness); real games and the engine agree with the engine data
const ENGINE = JSON.parse(fs.readFileSync(path.resolve('../native/engine_data_full.json')));
function megaAbility(p) {
  const ab = ((ENGINE.species[toID(p.species.name)] || {}).abilities || {})['0'];
  if (ab && toID(ab) !== p.ability) { p.setAbility(ab, null, null, true); p.baseAbility = toID(ab); }
}

function rebuild(spec, flip) {
  const sides = flip ? [spec.sides[1], spec.sides[0]] : spec.sides, approx = [];
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [1, 2, 3, 4]}); b.debugMode = false;
  sides.forEach((sd, si) => b.setPlayer('p' + (si + 1), {name: 'Side ' + si, team: sd.mons.map(T.toSet)}));
  b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
  // Mega Evolution first (it can set weather), then wipe what the lead-off abilities did and lay the real position on top
  sides.forEach((sd, si) => {
    const side = b.sides[si];
    sd.mons.forEach((x, k) => { if (x.mega && !x.fainted && b.actions.runMegaEvo(side.pokemon[k])) megaAbility(side.pokemon[k]); });
    if (sd.mons.some(x => x.mega)) for (const q of side.pokemon) q.canMegaEvo = null;
  });
  b.field.clearWeather(); b.field.clearTerrain();
  for (const k of Object.keys(b.field.pseudoWeather)) b.field.removePseudoWeather(k);
  sides.forEach((sd, si) => {
    const side = b.sides[si];
    for (const k of Object.keys(side.sideConditions)) side.removeSideCondition(k);
    sd.mons.forEach((x, k) => {
      const p = side.pokemon[k];
      // forms other than Mega: Palafin's Hero and a busted Mimikyu last the game, Aegislash's Blade only until it leaves the field
      if (x.forme && !x.fainted) p.formeChange(x.forme, null, !x.forme.startsWith('Aegislash'));
      if (x.fainted) { p.hp = 0; p.fainted = true; p.status = 'fnt'; p.isActive = false; side.pokemonLeft--; side.totalFainted++; return; }
      p.hp = Math.max(1, Math.min(p.maxhp, Math.round(p.maxhp * x.hpPct / 100)));
      for (const s of STATS) p.boosts[s] = (x.boosts || {})[s] || 0;
      p.status = ''; p.statusState = b.initEffectState({});
      if (x.status) {
        p.status = x.status; p.statusState = b.initEffectState({id: x.status, target: p});
        if (x.status === 'slp') { p.statusState.startTime = 3; p.statusState.time = Math.max(1, 3 - (x.slept || 0)); }   // sleep length is hidden: assume the middle case
        if (x.status === 'tox') p.statusState.stage = 1;
      }
      const item = toID(x.itemNow);
      if (p.item !== item) { if (!item) p.lastItem = p.item; p.item = item; p.itemState = b.initEffectState({id: item, target: p}); }
      for (const v of Object.keys(p.volatiles)) delete p.volatiles[v];
      if (!x.onField) return;
      if (x.last && p.moveSlots.some(m => m.id === toID(x.last))) p.lastMove = dex.getActiveMove(toID(x.last));
      if (x.moved) { p.activeMoveActions = Math.max(1, p.activeMoveActions); p.activeTurns = Math.max(1, p.activeTurns); }
      if (x.stall) p.addVolatile('stall');
      if (x.lock && p.moveSlots.some(m => m.id === toID(x.lock))) p.volatiles.choicelock = b.initEffectState({id: 'choicelock', target: p, move: toID(x.lock)});
      for (const v of x.vol || []) {
        const arg = toID((x.volarg || {})[v]);
        if (VOL[v]) { if (!p.addVolatile(VOL[v], side.foe.active[0])) approx.push(v); }
        else if ((v === 'Encore' || v === 'Disable') && arg && p.moveSlots.some(m => m.id === arg)) p.volatiles[toID(v)] = b.initEffectState({id: toID(v), target: p, move: arg, duration: v === 'Encore' ? 2 : 3});
        else approx.push(v);
      }
    });
    const src = side.pokemon.find(p => !p.fainted), fsrc = side.foe.pokemon.find(p => !p.fainted);
    if (sd.tailwind) { side.addSideCondition('tailwind', src); side.sideConditions.tailwind.duration = sd.tailwind; }
    for (const [k, n] of Object.entries(sd.screens || {})) { side.addSideCondition(toID(k), src); if (side.sideConditions[toID(k)]) side.sideConditions[toID(k)].duration = n; else approx.push(k); }
    for (const h of sd.hazards || []) if (!side.addSideCondition(toID(h), fsrc)) approx.push(h);
  });
  const f = spec.field;
  if (f.terrain) { b.field.setTerrain(toID(f.terrain[0] + 'terrain'), b.sides[0].active[0]); b.field.terrainState.duration = f.terrain[1] || 5; }
  if (f.trickroom) { b.field.addPseudoWeather('trickroom', b.sides[0].active[0]); b.field.pseudoWeather.trickroom.duration = f.trickroom; }
  if (f.weather) { b.field.setWeather(WEATHER[f.weather[0]] || toID(f.weather[0]), b.sides[0].active[0]); b.field.weatherState.duration = f.weather[1] || 5; }
  // setting the field can trigger items and abilities again (seeds, weather forms): put items and boosts back
  sides.forEach((sd, si) => sd.mons.forEach((x, k) => {
    const p = b.sides[si].pokemon[k]; if (x.fainted) return;
    for (const s of STATS) p.boosts[s] = (x.boosts || {})[s] || 0;
    const item = toID(x.itemNow); if (p.item !== item) { p.item = item; p.itemState = b.initEffectState({id: item, target: p}); }
  }));
  return {b, sides, approx};
}
function build(spec, flip) {
  const {b, sides, approx} = rebuild(spec, flip);
  // what was actually chosen, in engine terms
  const acts = flip ? [spec.acts[1], spec.acts[0]] : spec.acts, letter = flip ? ['p2', 'p1'] : ['p1', 'p2'];
  const choice = (si, i) => {
    const a = acts[si][i], side = b.sides[si], p = side.active[i];
    if (!a || !p || p.fainted) return null;
    if (a.none) return {none: a.none, by: a.by ? dex.moves.get(a.by).priority : null};   // not shown: it fainted first (to a move of that priority) or could not move
    if (a.switch) {                                    // a Mega that went back comes in again as "Golisopod-Mega": match the base species (one per team)
      const base = s => dex.species.get(s).baseSpecies;
      const k = sides[si].mons.findIndex(x => x.species === a.switch || base(x.species) === base(a.switch)); return k < 0 ? null : ['switch', k]; }
    const k = p.moveSlots.findIndex(m => m.id === toID(a.move)); if (k < 0) return null;
    // it failed (or only charged): the log shows the move but no target. The engine reads the choice as unknown; move tells the eval bar
    // which move it was (its luck counts that move's targets, not the whole mix)
    if (!a.target && ['normal', 'any', 'adjacentFoe', 'adjacentAlly', 'adjacentAllyOrSelf'].includes(dex.moves.get(a.move).target)) return {move: k};
    let t = 0;
    if (a.target) { const ts = a.target.slice(0, 2), ti = a.target[2] === 'a' ? 0 : 1; t = ts === letter[si] ? (ti === i ? 0 : -(ti + 1)) : ti + 1; }
    return {c: [k, t, !!a.mega], unsure: !!a.unsure};
  };
  const pack = si => [0, 1].map(i => { const c = choice(si, i); return c && c.c ? {choice: c.c, unsure: c.unsure} : c && c.move !== undefined ? {choice: null, move: c.move, unsure: false} : c && c.none ? {choice: null, none: c.none, by: c.by, unsure: false} : c ? {choice: c, unsure: false} : null; });
  return {name: `${spec.name} ${flip ? 'p2' : 'p1'}`, turn: spec.turn, side: flip ? 'p2' : 'p1', perish: !!spec.perish, standIns: spec.standIns || 0, dropped: spec.dropped || [], approx: [...new Set(approx)],
          actual: pack(0), their_actual: pack(1), state: exportState(b)};
}
module.exports = {rebuild, build, dex, toID};                            // damage.js rebuilds positions the same way
if (require.main === module) {
  const out = fs.createWriteStream(outf); let n = 0, bad = 0;
  for (const spec of JSON.parse(fs.readFileSync(specf))) for (const flip of views === 'p1' ? [false] : [false, true]) {
    try { out.write(JSON.stringify(build(spec, flip)) + '\n'); n++; }
    catch (e) { bad++; console.log(`${spec.name}: could not rebuild (${String(e.message).slice(0, 120)})`); }
  }
  out.end(); console.log(`${n} engine positions written, ${bad} failed`);
}
