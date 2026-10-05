// Export everything the native turn engine needs from Showdown's Champions mod: full move/item/ability/condition data (functions dropped) plus,
// for every effect, the list of event callbacks it defines with their order/priority/subOrder (the keys Showdown sorts event handlers by).
// usage (from pssim/): node ../native/export_engine.js <champions_data.json (for the species/move/item/ability scope)> <out.json>
const {Dex} = require(require('path').resolve('node_modules/pokemon-showdown')); const dex = Dex.mod('champions'); const fs = require('fs');
const toID = s => (s || '').toLowerCase().replace(/[^a-z0-9]/g, '');
const base = JSON.parse(fs.readFileSync(process.argv[2]));
const cbs = o => { const r = {};
  // every on<Event> name that has a callback or an Order/Priority/SubOrder (residual handlers can exist with only an order, via getKey "duration")
  // (a numeric onXPriority / onXOrder / onXSubOrder is a sort key for onX; anything else named on* is a callback, e.g. onModifyPriority)
  const keys = Object.keys(o).filter(k => /^on[A-Z]/.test(k));
  const names = new Set(keys.map(k => typeof o[k] === 'number' && /(SubOrder|Order|Priority)$/.test(k) ? k.replace(/(SubOrder|Order|Priority)$/, '') : k));
  for (const k of names) {
    const e = {}; if (o[k] === undefined) e.absent = true; else if (typeof o[k] !== 'function') e.val = o[k];
    for (const s of ['Order', 'Priority', 'SubOrder']) if (typeof o[k + s] === 'number') e[s[0].toLowerCase() + s.slice(1)] = o[k + s];
    if (e.absent && Object.keys(e).length === 1) continue;
    r[k] = e; }
  return r; };
// functions nested in data (secondary.onHit, self.onHit, ...) become the marker "__fn" so the engine knows to call its port
const plain = o => JSON.parse(JSON.stringify(o, function (k, v) { if (k === 'desc' || k === 'shortDesc' || k === 'condition') return undefined;
  if (typeof v === 'function') return this === o ? undefined : '__fn'; return v; }));
const fnKeys = o => Object.keys(o).filter(k => typeof o[k] === 'function' && !/^on[A-Z]/.test(k));
const moves = {}, items = {}, abilities = {}, conditions = {};
// plus moves the engine needs as effects even when nobody uses them (Stealth Rock damage on switch-in from Stone Axe)
// EXTRA_MOVES=a,b: moves outside the scope file (e.g. ones seen in recorded games), exported into a separate data file
for (const id of [...Object.keys(base.moves), 'stealthrock', 'struggle', 'recharge', ...(process.env.EXTRA_MOVES || '').split(',').filter(Boolean)]) { const m = dex.moves.get(id); moves[id] = {...plain(m), cbs: cbs(m), fns: fnKeys(m)}; }
// EXTRA_ITEMS=a,b / EXTRA_SPECIES=a,b: items and species outside the scope file (e.g. an opponent's Pokemon seen in a recorded game)
const extra = k => (process.env[k] || '').split(',').map(toID).filter(Boolean);
for (const id of [...Object.keys(base.items), ...extra('EXTRA_ITEMS')]) { const it = dex.items.get(id); items[id] = {...plain(it), cbs: cbs(it), fns: fnKeys(it)}; }
for (const id of Object.keys(base.abilities)) { const a = dex.abilities.get(id); abilities[id] = {...plain(a), cbs: cbs(a), fns: fnKeys(a)}; }
const cids = new Set(Object.keys(dex.data.Conditions));
for (const id of Object.keys(base.moves)) if (dex.data.Moves[id] && dex.data.Moves[id].condition) cids.add(id);
for (const id of Object.keys(base.items)) if (dex.data.Items[id] && dex.data.Items[id].condition) cids.add(id);
for (const id of Object.keys(base.abilities)) if (dex.data.Abilities[id] && dex.data.Abilities[id].condition) cids.add(id);
// conditions that in-scope moves/abilities/items put on the field (Psychic Noise -> healblock, Toxic Debris -> toxicspikes, ...)
const refs = o => o ? ['volatileStatus', 'sideCondition', 'slotCondition', 'pseudoWeather', 'weather', 'terrain', 'status'].map(k => o[k]).filter(x => typeof x === 'string') : [];
for (const id of Object.keys(base.moves)) { const m = dex.moves.get(id); for (const x of [...refs(m), ...refs(m.self), ...(m.secondaries || []).flatMap(s => [...refs(s), ...refs(s.self)])]) cids.add(toID(x)); }
for (const x of ['toxicspikes', 'stealthrock', 'spikes', 'gem', 'attract', 'torment', 'embargo', 'magnetrise', 'ingrain', 'smackdown', 'focusenergy', 'charge', 'nightmare']) cids.add(x);
for (const id of ['psychicterrain', 'grassyterrain', 'electricterrain', 'mistyterrain', 'trickroom', 'tailwind', 'reflect', 'lightscreen', 'auroraveil', 'wideguard', 'quickguard', 'gravity'])
  cids.add(id);
for (const id of cids) { const c = dex.conditions.getByID(id); if (!c || c.exists === false) continue;
  conditions[id] = {id, effectType: c.effectType, duration: c.duration || null, fns: fnKeys(c), cbs: cbs(c)}; }
const species = {};
const addSp = s => { if (!s.exists || species[s.id]) return;
  species[s.id] = {name: s.name, base: s.baseSpecies, types: s.types, stats: s.baseStats, abilities: s.abilities, weightkg: s.weightkg, isMega: !!s.isMega,
                   requiredItem: s.requiredItem || null, otherFormes: s.otherFormes || [], id: s.id, num: s.num, baseSpeciesId: dex.species.get(s.baseSpecies).id,
                   weighthg: s.weighthg, cbs: cbs(s)}; };
// every in-scope species plus all its formes (Megas, and battle formes like Aegislash-Blade, Mimikyu-Busted, Palafin-Hero)
for (const id of [...Object.keys(base.species), ...extra('EXTRA_SPECIES')]) { const s = dex.species.get(id); addSp(s); for (const f of [...(s.otherFormes || []), ...(s.formeOrder || [])]) addSp(dex.species.get(f)); }
fs.writeFileSync(process.argv[3], JSON.stringify({species, moves, items, abilities, conditions, natures: base.natures, types: base.types}));
const n = o => Object.values(o).reduce((a, e) => a + Object.keys(e.cbs).length, 0);
console.log(`moves ${Object.keys(moves).length} (${n(moves)} cbs) | items ${Object.keys(items).length} (${n(items)}) | abilities ${Object.keys(abilities).length} (${n(abilities)}) | conditions ${Object.keys(conditions).length} (${n(conditions)})`);
