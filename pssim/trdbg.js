const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const S = (species, item, ability, nature, evs, moves) => T.toSet({species, item, ability, nature, evs, moves: ['splash', ...moves]});
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
const BL = S('Blastoise', 'blastoisinite', 'torrent', 'Quiet', [32, 0, 0, 32, 2, 0], ['fakeout', 'waterspout', 'aurasphere', 'darkpulse']);
const R = S('Rillaboom', 'miracleseed', 'grassysurge', 'Adamant', [32, 32, 0, 0, 0, 2], ['woodhammer']);
for (let seed = 1; seed <= 4; seed++) {
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed, 4, 8, 15]}); b.debugMode = false;
  b.setPlayer('p1', {name: 'Me', team: [BL, FILL, FILL, FILL]}); b.setPlayer('p2', {name: 'Them', team: [R, FILL, FILL, FILL]});
  b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234'); b.choose('p1', 'move waterspout mega, move splash'); b.choose('p2', 'move splash, move splash');
  const i = b.log.findIndex(x => x.includes('|move|p1a: Blastoise|Water Spout')); console.log(b.log.slice(i, i + 14).join('\n')); console.log('---');
}
