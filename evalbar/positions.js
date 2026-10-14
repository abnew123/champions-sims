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
const SELF_VOL = new Set(['imprison', 'substitute', 'flashfire']);          // volatiles a Pokemon puts on itself (srcDue)
// volDue (battlestate.FLAGS; the bot's: botpos.BOT_FLAGS): a volatile with a countdown gets what Showdown would have left of it at the
// start of this turn: its full duration as set when it started (data/moves.js) less one for each end of turn since. x.volturn[v] = [the turn
// it started, what the Pokemon was doing then: 'waits' (its move that turn still to come: queue.willMove), 'moving' (its own move was
// running: Cursed Body), 'moved' (on the field since the turn started, its action done), 'new' (it came in that turn: activeTurns 0)]
const FULL = {
  taunt: how => 3 + (how === 'moved' || how === 'moving' ? 1 : 0),       // +1 if it had been on the field since the turn started and would not move again
  encore: how => 3 + (how === 'waits' ? 0 : 1),                          // +1 if it would not move again that turn
  disable: how => 5 - (how === 'waits' || how === 'moving' ? 1 : 0),     // -1 if it was still to move that turn, or moving (Cursed Body)
  throatchop: () => 2,
  healblock: (how, arg) => arg === 'psychicnoise' ? 2 : 5,               // Psychic Noise's 2, the move Heal Block's 5 (no Persistent in Champions)
};
function left(spec, x, id, arg, approx, v) {
  const t = (x.volturn || {})[v];
  if (!spec.volDue || !t || !FULL[id]) return null;
  const n = FULL[id](t[1], arg) - (spec.turn - t[0]);
  if (n < 1) approx.push(v);                                             // it should have ended: the log's -end was missed
  return Math.max(1, n);
}
// the engine's data: this Showdown package gives three Megas an older ability (Mega Golisopod Emergency Exit for Tough Claws, Mega
// Garchomp Z Sand Force for Levitate, Mega Absol Z Magic Bounce for Sharpness); real games and the engine agree with the engine data
const ENGINE = JSON.parse(fs.readFileSync(path.resolve('../native/engine_data_full.json')));
const SHOWN = (h, M) => h >= M ? 100 : Math.min(99, Math.max(1, Math.ceil(100 * h / M)));   // Showdown's percent for h of M HP
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
      // pctDue (battlestate.FLAGS; the bot's: botpos.BOT_FLAGS): a shown percent (Showdown rounds up, 99 until full) rebuilt as an HP that shows as it,
      // the middle of those; rounding made 1% into 2 HP (shown 2%) and the like, half an HP too much on average (reach.py, 2026-10-12)
      if (spec.pctDue && Number.isInteger(x.hpPct) && x.hpPct > 0 && x.hpPct < 100 && SHOWN(p.hp, p.maxhp) !== x.hpPct) {
        const c = []; for (let h = 1; h < p.maxhp; h++) if (SHOWN(h, p.maxhp) === x.hpPct) c.push(h);
        if (c.length) p.hp = c[Math.floor((c.length - 1) / 2)];
      }
      for (const s of STATS) p.boosts[s] = (x.boosts || {})[s] || 0;
      p.status = ''; p.statusState = b.initEffectState({});
      if (x.status) {
        p.status = x.status; p.statusState = b.initEffectState({id: x.status, target: p});
        // the sleep counter is hidden: the case live.py's sleep_cases gives (2 or 3), else the likelier 3, less the turns slept (Early Bird: twice)
        if (x.status === 'slp') { const n = x.sleepStart || 3; p.statusState.startTime = n; p.statusState.time = Math.max(1, n - (x.slept || 0) * (p.hasAbility('earlybird') ? 2 : 1)); }
        if (x.status === 'tox') p.statusState.stage = spec.chipDue ? (x.toxn || 0) : 1;   // chipDue: the ticks so far (it counts up each end of turn)
      }
      // syrupDue (battlestate.FLAGS; the bot's: botpos.BOT_FLAGS): Supersweet Syrup acts once a battle; the log showed it (champ-battle-v29 reads the field,
      // Battle sim, 2026-10-13). Left to the rebuild, a lead holder had it set at the rebuild's start and one that came in earlier did not
      if (spec.syrupDue) p.syrupTriggered = !!x.syrupDone;
      const item = toID(x.itemNow);
      if (p.item !== item) { if (!item) p.lastItem = p.item; p.item = item; p.itemState = b.initEffectState({id: item, target: p}); }
      for (const v of Object.keys(p.volatiles)) delete p.volatiles[v];
      if (!x.onField) return;
      if (x.last && p.moveSlots.some(m => m.id === toID(x.last))) p.lastMove = dex.getActiveMove(toID(x.last));
      if (x.moved) { p.activeMoveActions = Math.max(1, p.activeMoveActions); p.activeTurns = Math.max(1, p.activeTurns); }
      if (x.stall) p.addVolatile('stall');
      if (x.lock && p.moveSlots.some(m => m.id === toID(x.lock))) p.volatiles.choicelock = b.initEffectState({id: 'choicelock', target: p, move: toID(x.lock)});
      for (const v of x.vol || []) {
        const arg = toID((x.volarg || {})[v]), n = left(spec, x, VOL[v] || toID(v), arg, approx, v);
        if (VOL[v]) {
          // srcDue (battlestate.FLAGS; the bot's: botpos.BOT_FLAGS): a volatile's source as Showdown has it, not the foe in the first slot: the holder for the
          // ones it puts on itself (Imprison's handlers disable what the source knows), and for Leech Seed the slot it was seeded from, which
          // its drain heals (Battle sim, 2026-10-13)
          let src = side.foe.active[0];
          if (spec.srcDue && SELF_VOL.has(VOL[v])) src = p;
          else if (spec.srcDue && (v === 'Leech Seed' || v === 'Yawn') && /^[af][ab]$/.test(arg)) src = (arg[0] === 'a' ? side : side.foe).active[arg[1] === 'a' ? 0 : 1] || src;   // the Yawner: the sleep's source
          if (!p.addVolatile(VOL[v], src)) approx.push(v);
          else if (v === 'Yawn' && spec.yawnDue) p.volatiles.yawn.duration = 1;
          else if (n !== null) p.volatiles[VOL[v]].duration = n;
        }
        // yawnDue: a Yawn on the field at the start of a turn was used last turn, so it puts its target to sleep at the end of this one
        // (Showdown's duration 2 has already lost one end of turn). live.specs_for and botpos.bot_position (the bot, from 2026-10-12) set it
        // fallenDue (battlestate.FLAGS; the bot's: botpos.BOT_FLAGS): Supreme Overlord's count of fallen allies, taken when it came in (the log's
        // -start fallenN); a Kingambit already on the field otherwise hit with none of it (the engine reads the ability state's 'fallen')
        else if (spec.fallenDue && /^fallen[1-5]$/.test(v) && p.hasAbility('supremeoverlord')) p.abilityState.fallen = +v.slice(6);
        // rechargeDue (battlestate.FLAGS; the bot's: botpos.BOT_FLAGS): it used Hyper Beam or the like last turn, so this turn it can only recharge (one end of
        // turn left); before, it was offered every move and nothing was flagged (an outside review, 2026-10-14: 12 of 735 bot logs)
        else if (spec.rechargeDue && v === 'mustrecharge') { if (p.addVolatile('mustrecharge')) p.volatiles.mustrecharge.duration = 1; else approx.push(v); }
        else if ((v === 'Encore' || v === 'Disable') && arg && p.moveSlots.some(m => m.id === arg))
          p.volatiles[toID(v)] = b.initEffectState({id: toID(v), target: p, move: arg, duration: n !== null ? n : v === 'Encore' ? 2 : 3});
        else approx.push(v);
      }
      // fieldDue (battlestate.FLAGS; the bot's: botpos.BOT_FLAGS): Unburden doubles Speed once its item is gone while it is on the
      // field (Showdown keeps that as a volatile the log never shows), and Perish Song's count goes on (a fresh volatile would be 4)
      if (spec.fieldDue && x.unburden && p.hasAbility('unburden') && !toID(x.itemNow)) p.addVolatile('unburden');
      // chipDue (battlestate.FLAGS; the bot's: botpos.BOT_FLAGS): a binding move (Infestation, Whirlpool...) goes on from its user, 5 turns less those passed
      // (Showdown draws 5 or 6, 8 with Grip Claw), with its end-of-turn damage and its trap
      if (spec.chipDue && x.ptrap) {
        const src = side.foe.active.find(q => q && !q.fainted && toID(q.species.baseSpecies) === toID(dex.species.get(x.ptrap[2] || '').baseSpecies || ''));
        if (src && p.addVolatile('partiallytrapped', src, dex.getActiveMove(toID(x.ptrap[0])))) p.volatiles.partiallytrapped.duration = Math.max(1, (src.hasItem('gripclaw') ? 8 : 5) - (x.ptrap[1] || 0));
        else approx.push('bound');
      }
      // abilDue (battlestate.FLAGS; the bot's: botpos.BOT_FLAGS): an ability it gained in battle (Trace, Skill Swap, Role Play), set without its start
      if (spec.abilDue && x.abilityNow && dex.abilities.get(toID(x.abilityNow)).exists) { p.ability = toID(x.abilityNow); p.abilityState = b.initEffectState({id: p.ability, target: p}); }
      // typeDue (battlestate.FLAGS; the bot's: botpos.BOT_FLAGS): types changed in battle (Soak, Protean / Libero, Double Shock, Burn Up: the log's -start
      // typechange) and a type added (Forest's Curse); before, a Soaked Pokemon kept its own types. Protean / Libero used since it came in: once a stint
      if (spec.typeDue) {
        if (x.typesNow && x.typesNow.length) p.setType(x.typesNow, true);
        if (x.typeAdd) p.addedType = x.typeAdd;
        if (x.proteanUsed && (p.ability === 'protean' || p.ability === 'libero')) p.abilityState[p.ability] = true;
      }
      if (spec.fieldDue && x.perish > 0) { if (p.addVolatile('perishsong')) p.volatiles.perishsong.duration = x.perish; else approx.push('Perish Song'); }
      // fieldDue: the second turn of a two-turn move (Electro Shot outside rain, Solar Beam, Meteor Beam, Fly...): locked into it, aimed
      // where the log shows it fired (else the first foe), as Showdown's twoturnmove leaves it after the charging turn's end
      if (spec.fieldDue && (x.vol || []).includes('charging') && x.last && p.moveSlots.some(m => m.id === toID(x.last))) {
        const acts = (flip ? [spec.acts[1], spec.acts[0]] : spec.acts || [[], []])[si] || [], a = acts[k], letter = flip ? ['p2', 'p1'] : ['p1', 'p2'];
        let foe = a && a.target && letter.indexOf(a.target.slice(0, 2)) >= 0 ? b.sides[letter.indexOf(a.target.slice(0, 2))].active[a.target[2] === 'a' ? 0 : 1] : null;
        if (!foe || foe.fainted) foe = side.foe.active.find(q => q && !q.fainted) || null;
        if (foe) {
          p.lastMoveTargetLoc = p.getLocOf(foe); p.addVolatile('twoturnmove', foe, dex.getActiveMove(toID(x.last)));
          if (p.volatiles.twoturnmove) { p.volatiles.twoturnmove.duration = 1; const ci = approx.indexOf('charging'); if (ci >= 0) approx.splice(ci, 1); }
        }
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
  // trapping, as Showdown works it out at the end of each turn (Shadow Tag, Arena Trap, Magnet Pull): the engine reads it from the state
  for (const side of b.sides) for (const p of side.active) {
    if (!p || p.fainted) continue;
    p.trapped = p.maybeTrapped = false; b.runEvent('TrapPokemon', p);
    if (!p.knownType || b.dex.getImmunity('trapped', p)) b.runEvent('MaybeTrapPokemon', p);
    if (p.trapped) p.trapped = true;                                       // 'hidden' (a trap the request hides) is still a trap
    if (p.getLockedMove()) p.trapped = true;                               // as Showdown's request: a move it is locked into (a charged one)
  }
  return {b, sides, approx};
}
function build(spec, flip) {
  const {b, sides, approx} = rebuild(spec, flip);
  // what was actually chosen, in engine terms
  const acts = flip ? [spec.acts[1], spec.acts[0]] : spec.acts, letter = flip ? ['p2', 'p1'] : ['p1', 'p2'];
  const choice = (si, i) => {
    const a = acts[si][i], side = b.sides[si], p = side.active[i];
    if (!a || !p || p.fainted) return null;
    if (a.none) return {none: a.none, by: a.by ? dex.moves.get(a.by).priority : null, mega: a.mega};   // not shown: it fainted first (to a move of that priority) or could not move
    if (a.switch) {                                    // a Mega that went back comes in again as "Golisopod-Mega": match the base species (one per team)
      const base = s => dex.species.get(s).baseSpecies;
      const k = sides[si].mons.findIndex(x => x.species === a.switch || base(x.species) === base(a.switch)); return k < 0 ? null : ['switch', k]; }
    const k = p.moveSlots.findIndex(m => m.id === toID(a.move)); if (k < 0) return null;
    // it failed (or only charged): the log shows the move but no target. The engine reads the choice as unknown; move tells the eval bar
    // which move it was (its luck counts that move's targets, not the whole mix)
    // (a single-target move that spread, Expanding Force in Psychic Terrain: the target it was aimed at, spreadTarget)
    const needs = ['normal', 'any', 'adjacentFoe', 'adjacentAlly', 'adjacentAllyOrSelf'].includes(dex.moves.get(a.move).target), tgt = a.target || (needs && a.spreadTarget) || '';
    if (!tgt && needs) return {move: k, mega: !!a.mega};
    let t = 0;
    if (tgt) { const ts = tgt.slice(0, 2), ti = tgt[2] === 'a' ? 0 : 1; t = ts === letter[si] ? (ti === i ? 0 : -(ti + 1)) : ti + 1; }
    return {c: [k, t, !!a.mega], unsure: !!a.unsure};
  };
  const pack = si => [0, 1].map(i => { const c = choice(si, i); return c && c.c ? {choice: c.c, unsure: c.unsure} : c && c.move !== undefined ? {choice: null, move: c.move, mega: c.mega, unsure: false} : c && c.none ? {choice: null, none: c.none, by: c.by, mega: c.mega, unsure: false} : c ? {choice: c, unsure: false} : null; });
  return {name: `${spec.name} ${flip ? 'p2' : 'p1'}`, turn: spec.turn, side: flip ? 'p2' : 'p1', perish: !!spec.perish, standIns: spec.standIns || 0, dropped: spec.dropped || [], approx: [...new Set(approx)],
          actual: pack(0), their_actual: pack(1), state: exportState(b),
          // the luck pass (live.py): the Pokemon each side sent in during the turn, for evalpos's actual_cell
          ...(spec.replace ? {actual_replace: {0: spec.replace[flip ? 'p2' : 'p1'] || [], 1: spec.replace[flip ? 'p1' : 'p2'] || []}} : {})};
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
