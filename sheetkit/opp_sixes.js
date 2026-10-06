// The opposing sixes for "both sides pick their four": per archetype a list of {label, weight, six: [sets]}.
//   An archetype the replay model gives exactly six Pokemon is one six (weight 1). Any other is a mix of teams, so each of its six common
//   lead pairs becomes one six: the pair plus the four Pokemon most often brought behind it in replays, weighted by the pair's share.
//   Sets are the replay model's (t1sim.oppSet: modal set per species, spreads from foes.json; fallback sets for the rarer ones).
// usage (from pssim/): node ../sheetkit/opp_sixes.js > sixes.json
const path = require('path');
const T = require(path.resolve('t1sim.js'));
const set = (arch, sp) => { const s = T.oppSet(arch, sp, []); return {species: s.species, item: s.item, ability: s.ability, nature: s.nature, evs: s.evs, moves: s.moves}; };
const out = {};
for (const [arch, d] of Object.entries(T.OPP)) {
  const names = Object.keys(d.sets);
  if (names.length === 6) { out[arch] = [{label: names.join(', '), weight: 1, six: names.map(sp => set(arch, sp))}]; continue; }
  out[arch] = d.pairs.map(p => {
    const lead = p.pair.split(' + ');
    const back = p.back.split(', ').map(x => x.split(':')[0]).filter(x => !lead.includes(x)).slice(0, 4);
    const six = [];
    for (const sp of [...lead, ...back]) { try { six.push(set(arch, sp)); } catch (e) {} }
    return {label: p.pair + ' (+ ' + back.join(', ') + ')', weight: p.share, six};
  });
}
console.log(JSON.stringify(out));
