const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const S = (species, item, ability, nature, evs, moves) => T.toSet({species, item, ability, nature, evs, moves: ['splash', ...moves]});
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
const BL = S('Blastoise', 'blastoisinite', 'torrent', 'Quiet', [32, 0, 0, 32, 2, 0], ['fakeout', 'waterspout', 'aurasphere', 'darkpulse', 'surf', 'hydropump']);
function run(label, tset, mv, mega = '', seedTail = [4, 8, 15]) {
  const v = [];
  for (let seed = 1; seed <= 24; seed++) {
    const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed, ...seedTail]}); b.debugMode = false;
    b.setPlayer('p1', {name: 'Me', team: [BL, FILL, FILL, FILL]}); b.setPlayer('p2', {name: 'Them', team: [tset, FILL, FILL, FILL]});
    b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234'); b.choose('p1', `move ${mv}${mv === 'hydropump' || mv === 'aurasphere' ? ' 1' : ''}${mega}, move splash`); b.choose('p2', 'move splash, move splash');
    if (b.log.some(x => x.startsWith('|-crit|p2a') || x.startsWith('|-miss|'))) continue; const t = b.sides[1].active[0]; v.push(t.maxhp - t.hp);
  }
  console.log(label.padEnd(44), [...new Set(v)].sort((a, b) => a - b).join(','));
}
run('Water Spout -> Rillaboom (as before)', S('Rillaboom', 'miracleseed', 'grassysurge', 'Adamant', [32, 32, 0, 0, 0, 2], []), 'waterspout', ' mega');
run('Water Spout -> Rillaboom, other seed tail', S('Rillaboom', 'miracleseed', 'grassysurge', 'Adamant', [32, 32, 0, 0, 0, 2], []), 'waterspout', ' mega', [99, 123, 7]);
run('Water Spout -> Rillaboom, Overgrow no item', S('Rillaboom', '', 'overgrow', 'Adamant', [32, 32, 0, 0, 0, 2], []), 'waterspout', ' mega');
run('Surf -> Rillaboom (Grassy Surge)', S('Rillaboom', 'miracleseed', 'grassysurge', 'Adamant', [32, 32, 0, 0, 0, 2], []), 'surf', ' mega');
run('Hydro Pump -> Rillaboom (single)', S('Rillaboom', 'miracleseed', 'grassysurge', 'Adamant', [32, 32, 0, 0, 0, 2], []), 'hydropump', ' mega');
run('Water Spout -> Sneasler', S('Sneasler', 'grassyseed', 'unburden', 'Adamant', [2, 32, 0, 0, 0, 32], []), 'waterspout', ' mega');
run('Water Spout -> Garchomp', S('Garchomp', 'lifeorb', 'roughskin', 'Jolly', [2, 32, 0, 0, 0, 32], []), 'waterspout', ' mega');
run('Water Spout (no mega) -> Rillaboom', S('Rillaboom', 'miracleseed', 'grassysurge', 'Adamant', [32, 32, 0, 0, 0, 2], []), 'waterspout', '');
