// Legality of the swaps + second-use damage (Draco at -2 vs Dragon Pulse) into Mega Salamence / Garchomp.
const {Dex, Battle} = require('pokemon-showdown'); const d = Dex.mod('champions'); const T = require('./t1sim.js');
for (const [sp, mv] of [['garchomp', 'dragonpulse'], ['garchomp', 'dracometeor'], ['sylveon', 'quickattack'], ['sylveon', 'yawn'], ['sneasler', 'direclaw'], ['sneasler', 'poisonjab']]) {
  let s = d.species.get(sp), ok = false; while (s && !ok) { const l = d.data.Learnsets[s.id]; ok = !!(l && l.learnset && l.learnset[mv]); s = s.prevo ? d.species.get(s.prevo) : null; }
  console.log(sp, mv, ok ? 'legal' : 'NOT in learnset');
}
console.log('Pixilate:', d.abilities.get('pixilate').desc || d.abilities.get('pixilate').shortDesc);
const S = (species, item, ability, nature, evs, moves) => T.toSet({species, item, ability, nature, evs, moves: ['splash', ...moves]});
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
const CHOMP = S('Garchomp', 'garchompitez', 'roughskin', 'Modest', [32, 0, 0, 32, 0, 2], ['dracometeor', 'dragonpulse', 'flamethrower', 'powergem']);
const TG = {'Mega Salamence': [S('Salamence', 'salamencite', 'intimidate', 'Timid', [2, 0, 0, 32, 0, 32], []), ' mega'], 'Garchomp (LO)': [S('Garchomp', 'lifeorb', 'roughskin', 'Jolly', [2, 32, 0, 0, 0, 32], []), ''],
  'Mega Garchomp Z': [S('Garchomp', 'garchompitez', 'roughskin', 'Modest', [2, 0, 0, 32, 0, 32], []), ' mega']};
for (const [tn, [ts, mg]] of Object.entries(TG)) {
  let ko = 0, n = 0, lo = 1e9, hi = 0, max = 0;
  for (let seed = 1; seed <= 64; seed++) {
    const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed, 1, 2, 3]}); b.debugMode = false;
    b.setPlayer('p1', {name: 'Me', team: [CHOMP, FILL, FILL, FILL]}); b.setPlayer('p2', {name: 'Them', team: [ts, FILL, FILL, FILL]});
    b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
    b.sides[0].active[0].boosts.spa = -2;  // a Draco Meteor already used
    b.choose('p1', 'move dracometeor 1 mega, move splash'); b.choose('p2', `move splash${mg}, move splash`);
    const t = b.sides[1].active[0]; max = t.maxhp; const L = b.log.join('\n');
    if (/\|-miss\|/.test(L) || /\|-crit\|p2a/.test(L)) continue; n++; const dmg = t.maxhp - t.hp; lo = Math.min(lo, dmg); hi = Math.max(hi, dmg); if (t.fainted || t.hp === 0) ko++;
  }
  console.log(`  -2 Draco Meteor -> ${tn.padEnd(16)} ${(100 * lo / max).toFixed(0)}-${(100 * Math.min(hi, max) / max).toFixed(0)}%  KO ${ko}/${n}`);
}
