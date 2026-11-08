// Full battle-state export (v2) shared by the native engine's tools: everything native/champ reads.
// Pokemon references are {$p: [side, index in side.pokemon]}; effects are {$e: effectType, id}.
const enc = (v, depth = 0) => {
  if (v === null || v === undefined || typeof v !== 'object') return typeof v === 'function' ? undefined : v;
  if (v.constructor && v.constructor.name === 'Pokemon') return {$p: [v.side.n, v.side.pokemon.indexOf(v)]};
  if (v.constructor && v.constructor.name === 'Side') return {$s: v.n};
  if (v.constructor && v.constructor.name === 'Field') return {$f: 1};
  if (v.effectType && v.id !== undefined && typeof v.exists === 'boolean') return {$e: v.effectType, id: v.id};
  if (depth > 3) return undefined;
  if (Array.isArray(v)) return v.map(x => enc(x, depth + 1));
  const o = {}; for (const [k, x] of Object.entries(v)) { if (k === 'target' && depth === 0) continue; const e = enc(x, depth + 1); if (e !== undefined) o[k] = e; } return o;
};
const st = s => enc(s);
const mon = (p, o = {}) => ({...(o.v43 ? {gender: p.gender || ''} : {}), species: p.species.id, baseSpecies: p.baseSpecies.id, set: {species: p.set.species, nature: p.set.nature, evs: p.set.evs, ability: p.set.ability, item: p.set.item, level: p.set.level},
  types: p.types, addedType: p.addedType || '', storedStats: {...p.storedStats}, baseStoredStats: {...p.baseStoredStats}, hp: p.hp, maxhp: p.maxhp, baseMaxhp: p.baseMaxhp,
  boosts: {...p.boosts}, status: p.status || '', statusState: st(p.statusState), volatiles: Object.fromEntries(Object.entries(p.volatiles).map(([k, v]) => [k, st(v)])),
  ability: p.ability, baseAbility: p.baseAbility, abilityState: st(p.abilityState), item: p.item, itemState: st(p.itemState), lastItem: p.lastItem || '',
  usedItemThisTurn: !!p.usedItemThisTurn, ateBerry: !!p.ateBerry, itemKnockedOff: !!p.itemKnockedOff,
  moveSlots: p.moveSlots.map(m => ({id: m.id, pp: m.pp, maxpp: m.maxpp, disabled: m.disabled || false, used: !!m.used})),
  // a transformed Pokemon's own moves, restored when it leaves the field (2026-10-12)
  baseMoveSlots: p.transformed ? p.baseMoveSlots.map(m => ({id: m.id, pp: m.pp, maxpp: m.maxpp, disabled: m.disabled || false, used: !!m.used})) : undefined,
  position: p.position, isActive: !!p.isActive, fainted: !!p.fainted, faintQueued: !!p.faintQueued, level: p.level,
  activeTurns: p.activeTurns, activeMoveActions: p.activeMoveActions, weighthg: p.weighthg, speed: p.speed,
  lastMove: p.lastMove ? p.lastMove.id : '', lastMoveTargetLoc: p.lastMoveTargetLoc ?? null, moveThisTurn: p.moveThisTurn || '',
  moveThisTurnResult: p.moveThisTurnResult === undefined ? 'undef' : p.moveThisTurnResult, moveLastTurnResult: p.moveLastTurnResult === undefined ? 'undef' : p.moveLastTurnResult,
  lastDamage: p.lastDamage || 0, hurtThisTurn: p.hurtThisTurn ?? null, timesAttacked: p.timesAttacked || 0,
  attackedBy: p.attackedBy.map(a => ({source: enc(a.source), damage: a.damage, move: a.move, thisTurn: a.thisTurn, slot: a.slot,
                                      ...(o.v43 ? {numeric: typeof a.damageValue === 'number'} : {})})),   // getLastDamagedBy's filter (v43)
  statsRaisedThisTurn: !!p.statsRaisedThisTurn, statsLoweredThisTurn: !!p.statsLoweredThisTurn, switchFlag: p.switchFlag || false, forceSwitchFlag: !!p.forceSwitchFlag,
  newlySwitched: !!p.newlySwitched, syrupTriggered: !!p.syrupTriggered, beingCalledBack: !!p.beingCalledBack, canMegaEvo: p.canMegaEvo || null, transformed: !!p.transformed,
  trapped: p.trapped || false, maybeTrapped: !!p.maybeTrapped, maybeDisabled: !!p.maybeDisabled, maybeLocked: !!p.maybeLocked});
// opts.v43 (2026-11-07, champ-battle-v43): also each Pokemon's gender (Cute Charm, Attract, Rivalry), battle.lastMove's id (Copycat) and
// whether each attackedBy entry's damage was a number (Comeuppance: getLastDamagedBy skips status moves).
// Off by default, so the states other tools build (the eval bar's and the bot's positions) are unchanged; older engines ignore both.
function exportState(b, opts = {}) {
  return {...(opts.v43 ? {lastMove: b.lastMove ? b.lastMove.id : ''} : {}), turn: b.turn, effectOrder: b.effectOrder, ended: b.ended, winner: b.winner || '', prng: b.prng.rng && b.prng.rng.seed ? [...b.prng.rng.seed] : null,
    lastSuccessfulMoveThisTurn: b.lastSuccessfulMoveThisTurn || null, quickClawRoll: !!b.quickClawRoll,
    field: {weather: b.field.weather || '', weatherState: st(b.field.weatherState), terrain: b.field.terrain || '', terrainState: st(b.field.terrainState),
            pseudoWeather: Object.fromEntries(Object.entries(b.field.pseudoWeather).map(([k, v]) => [k, st(v)]))},
    sides: b.sides.map(s => ({pokemonLeft: s.pokemonLeft, totalFainted: s.totalFainted, faintedThisTurn: enc(s.faintedThisTurn), faintedLastTurn: enc(s.faintedLastTurn),
      sideConditions: Object.fromEntries(Object.entries(s.sideConditions).map(([k, v]) => [k, st(v)])),
      slotConditions: s.slotConditions.map(sc => Object.fromEntries(Object.entries(sc).map(([k, v]) => [k, st(v)]))),
      active: s.active.map(p => p ? s.pokemon.indexOf(p) : null), pokemon: s.pokemon.map(p => mon(p, opts))}))};
}
module.exports = {exportState};
