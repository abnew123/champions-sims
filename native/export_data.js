// Export the Champions data the native engine needs from Showdown's own Champions mod: species (stats, types, abilities, weight, Mega formes),
// moves, and the item/ability lists in scope (top 99% of Reg M-C usage + everything our current sims use).
// usage (from pssim/): node ../native/export_data.js <scope_99.json> <out.json>
const {Dex} = require(require('path').resolve('node_modules/pokemon-showdown')); const dex = Dex.mod('champions'); const fs = require('fs');
const scope = JSON.parse(fs.readFileSync(process.argv[2])); const toID = s => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const want = {species: new Set(), moves: new Set(), items: new Set(), abilities: new Set()};
for (const n of scope.Pokemon) want.species.add(toID(n)); for (const n of scope.moves) want.moves.add(toID(n));
for (const n of scope.items) want.items.add(toID(n)); for (const n of scope.abilities) want.abilities.add(toID(n));
// everything in the sets our pipelines already simulate
const addSet = s => { if (!s) return; want.species.add(toID(s.species)); want.items.add(toID(s.item)); want.abilities.add(toID(s.ability)); (s.moves || []).forEach(m => want.moves.add(toID(m))); };
for (const f of ['opp_model_a.json', 'opp_model_b.json']) for (const d of Object.values(JSON.parse(fs.readFileSync(f)))) for (const [sp, v] of Object.entries(d.sets)) {
  const [it, ab, , mv] = v.replace(/ \(.*\)$/, '').split('|'); addSet({species: sp, item: it, ability: ab, moves: mv.split('/')}); }
for (const s of Object.values(JSON.parse(fs.readFileSync('myteam_7.json')))) addSet(s);
for (const S of Object.values(JSON.parse(fs.readFileSync('../regionals/regional_sets.json')))) S.forEach(addSet);
const species = {}, moves = {}, items = {}, abilities = {};
for (const id of want.species) {
  const s = dex.species.get(id); if (!s.exists) continue;
  for (const f of [s, ...(s.otherFormes || []).map(x => dex.species.get(x)).filter(x => x.isMega || x.forme === 'Mega')]) {
    species[f.id] = {name: f.name, base: f.baseSpecies, types: f.types, stats: f.baseStats, abilities: f.abilities, weightkg: f.weightkg,
                     isMega: !!f.isMega, requiredItem: f.requiredItem || null, otherFormes: f.otherFormes || []};
    for (const a of Object.values(f.abilities)) want.abilities.add(toID(a));
    if (f.requiredItem) want.items.add(toID(f.requiredItem));
  }
}
const keep = ['num', 'name', 'type', 'category', 'basePower', 'accuracy', 'pp', 'priority', 'target', 'flags', 'secondary', 'secondaries', 'self', 'boosts', 'status',
  'volatileStatus', 'sideCondition', 'pseudoWeather', 'weather', 'terrain', 'drain', 'recoil', 'multihit', 'critRatio', 'willCrit', 'selfSwitch', 'selfBoost',
  'ignoreDefensive', 'ignoreEvasion', 'ignoreImmunity', 'overrideOffensiveStat', 'overrideDefensiveStat', 'breaksProtect', 'stallingMove', 'forceSwitch', 'heal',
  'mindBlownRecoil', 'struggleRecoil', 'thawsTarget', 'hasCrashDamage', 'ohko', 'spreadModifier', 'tracksTarget', 'smartTarget', 'hasSheerForce'];
for (const id of want.moves) { const m = dex.moves.get(id); if (!m.exists) continue; const o = {id: m.id}; for (const k of keep) if (m[k] !== undefined && m[k] !== false) o[k] = m[k];
  o.custom = ['onBasePower', 'basePowerCallback', 'onModifyMove', 'onTry', 'onTryHit', 'onHit', 'onAfterHit', 'damageCallback', 'onModifyType', 'onEffectiveness', 'beforeMoveCallback', 'onPrepareHit', 'condition'].filter(h => m[h]); moves[m.id] = o; }
for (const id of want.items) { const it = dex.items.get(id); if (!it.exists) continue; items[it.id] = {name: it.name, megaStone: it.megaStone || null, isBerry: !!it.isBerry, fling: it.fling || null,
  hooks: Object.keys(it).filter(k => /^on[A-Z]/.test(k))}; }
for (const id of want.abilities) { const a = dex.abilities.get(id); if (!a.exists) continue; abilities[a.id] = {name: a.name, hooks: Object.keys(a).filter(k => /^on[A-Z]/.test(k))}; }
// handler priorities/orders (they decide the order modifiers chain in Showdown's events)
const prio = o => Object.fromEntries(Object.entries(o).filter(([k, v]) => /^on[A-Z].*(Priority|Order|SubOrder)$/.test(k) && typeof v === 'number'));
for (const [id, a] of Object.entries(abilities)) a.prio = prio(dex.abilities.get(id));
for (const [id, it] of Object.entries(items)) it.prio = prio(dex.items.get(id));
for (const [id, m] of Object.entries(moves)) { const mm = dex.moves.get(id); m.prio = prio(mm); if (mm.condition) { m.condition = {hooks: Object.keys(mm.condition).filter(k => /^on[A-Z]/.test(k)), prio: prio(mm.condition), duration: mm.condition.duration || null}; } }
const conditions = {};
for (const c of ['sunnyday', 'raindance', 'sandstorm', 'snowscape', 'psychicterrain', 'grassyterrain', 'electricterrain', 'mistyterrain', 'reflect', 'lightscreen', 'auroraveil', 'helpinghand', 'trickroom', 'tailwind', 'brn', 'par', 'slp', 'frz', 'psn', 'tox']) {
  const x = dex.conditions.get(c); if (x && x.exists !== false) conditions[c] = {hooks: Object.keys(x).filter(k => /^on[A-Z]/.test(k)), prio: prio(x)}; }
const natures = {}; for (const n of dex.natures.all()) natures[n.id] = {plus: n.plus || null, minus: n.minus || null};
const types = {}; for (const t of dex.types.all()) types[t.name] = t.damageTaken;
fs.writeFileSync(process.argv[3], JSON.stringify({species, moves, items, abilities, natures, types, conditions}, null, 0));
console.log(`species ${Object.keys(species).length} (incl. Megas) | moves ${Object.keys(moves).length} | items ${Object.keys(items).length} | abilities ${Object.keys(abilities).length}`);
const custom = Object.values(moves).filter(m => m.custom.length); console.log(`moves with custom code hooks: ${custom.length} -> e.g. ${custom.slice(0, 12).map(m => m.id).join(', ')}`);
