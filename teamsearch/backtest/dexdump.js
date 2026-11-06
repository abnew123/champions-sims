// M-B backtest: Showdown's Champions data (pssim's copy predates M-C, so its legality is M-B's) for the blind-set generator
// (build_mb.py): per species, its types, base stats, abilities with Showdown's generic ratings, and its learnable moves that are legal
// (not 'Past') with what the generator needs. Megas learn their base species' moves. An optional third file maps species names to
// move ids that replace their learnset, all legal (M-C's new species: Showdown's current Champions learnsets, part of an announcement)
//   node backtest/dexdump.js <species json list> <out json> [learnset overrides json]
const fs = require('fs');
const {Dex} = require(require('path').join(__dirname, '..', '..', 'pssim', 'node_modules', 'pokemon-showdown'));
const d = Dex.mod('champions');
const [inp, out, over] = process.argv.slice(2);
const OVER = over ? JSON.parse(fs.readFileSync(over, 'utf8')) : {};
const res = {};
for (const name of JSON.parse(fs.readFileSync(inp, 'utf8'))) {
  const sp = d.species.get(name);
  if (!sp.exists) { res[name] = null; continue; }
  const learn = new Set(OVER[name] || []);
  if (!OVER[name]) for (const id of [sp.id, d.toID(sp.baseSpecies), d.toID(sp.changesFrom || '')]) {
    const ls = id && d.data.Learnsets[id];
    if (ls && ls.learnset) Object.keys(ls.learnset).forEach(m => learn.add(m));
  }
  const moves = {};
  for (const id of learn) {
    const m = d.moves.get(id);
    if (!m.exists || (m.isNonstandard === 'Past' && !OVER[name]) || m.isZ || m.isMax) continue;
    moves[m.name] = {type: m.type, cat: m.category, bp: m.basePower, acc: m.accuracy === true ? 100 : m.accuracy, pri: m.priority,
                     target: m.target, multihit: m.multihit || null, recharge: !!(m.self && m.self.volatileStatus === 'mustrecharge'),
                     charge: !!(m.flags && m.flags.charge), selfdestruct: !!m.selfdestruct, recoil: !!m.recoil};
  }
  const abilities = {};
  for (const a of Object.values(sp.abilities)) { const x = d.abilities.get(a); abilities[a] = x.exists ? x.rating : null; }
  res[name] = {name: sp.name, types: sp.types, stats: sp.baseStats, abilities, requiredItem: sp.requiredItem || null,
               legalMB: sp.isNonstandard !== 'Past' && sp.isNonstandard !== 'Future', moves};
}
fs.writeFileSync(out, JSON.stringify(res));
console.log(Object.keys(res).length, 'species dumped');
