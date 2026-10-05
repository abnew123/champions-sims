const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const opp = ['Gengar', 'Vivillon', 'Incineroar', 'Rillaboom'].map(sp => T.toSet(T.oppSet('Perish trap', sp)));
const mine = ['Salamence', 'Kingambit', 'Incineroar', 'Gholdengo'].map(n => T.toSet(T.MY[n]));
const out = {}; let spd = null; let dmg = [];
for (let seed = 1; seed <= 60; seed++) {
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed, 17, 29, 43]}); b.debugMode = false;
  b.setPlayer('p1', {name: 'Me', team: mine}); b.setPlayer('p2', {name: 'Them', team: opp}); b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
  b.choose('p1', 'move doubleedge 1 mega, move suckerpunch 1'); b.choose('p2', 'move perishsong mega, move sleeppowder 2');
  const L = b.log.join('\n'); const g = b.sides[1].pokemon.find(p => p.species.baseSpecies === 'Gengar');
  if (!spd) spd = {salamence: b.sides[0].active[0].getStat('spe'), gengar: g.getStat('spe'), vivillon: b.sides[1].active[1].getStat('spe'), kingambit: b.sides[0].active[1].getStat('spe')};
  const sang = L.includes('|move|p2a: Gengar|Perish Song'); const key = `${g.fainted ? 'Gengar KO' : 'Gengar alive ' + g.hp}${sang ? ', Perish Song went up' : ', no Perish Song'}${L.includes('|-crit|') ? ' (crit)' : ''}`;
  out[key] = (out[key] || 0) + 1;
  if (seed === 1) console.log(b.log.filter(x => /^\|(move|-damage|faint|-fail|cant|-status)\|/.test(x) && !/\/100/.test(x)).join('\n'));
}
console.log(spd); console.log(out);
