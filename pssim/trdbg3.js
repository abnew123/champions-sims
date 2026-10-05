const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const S = (species, item, ability, nature, evs, moves) => T.toSet({species, item, ability, nature, evs, moves: ['splash', ...moves]});
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
const BL = S('Blastoise', 'blastoisinite', 'torrent', 'Quiet', [32, 0, 0, 32, 2, 0], ['waterspout']);
function run(label, tset, partner = FILL, mega = ' mega') {
  const v = [];
  for (let seed = 1; seed <= 40; seed++) {
    const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed * 7 + 3, seed * 13 + 1, seed * 5 + 2, seed + 11]}); b.debugMode = false;
    b.setPlayer('p1', {name: 'Me', team: [BL, FILL, FILL, FILL]}); b.setPlayer('p2', {name: 'Them', team: [tset, partner, FILL, FILL]});
    b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234'); b.choose('p1', `move waterspout${mega}, move splash`); b.choose('p2', 'move splash, move splash');
    if (b.log.some(x => x.startsWith('|-crit|p2a'))) continue;
    const line = b.log.find(x => x.startsWith('|-damage|p2a') && x.split('|')[3].includes('/' + b.sides[1].active[0].maxhp)); v.push(b.sides[1].active[0].maxhp - +line.split('|')[3].split('/')[0]);
  }
  console.log(label.padEnd(50), [...new Set(v)].sort((a, b) => a - b).join(','));
}
run('Rillaboom Grassy Surge + Miracle Seed', S('Rillaboom', 'miracleseed', 'grassysurge', 'Adamant', [32, 32, 0, 0, 0, 2], []));
run('Rillaboom Grassy Surge, no item', S('Rillaboom', '', 'grassysurge', 'Adamant', [32, 32, 0, 0, 0, 2], []));
run('Rillaboom Overgrow + Miracle Seed', S('Rillaboom', 'miracleseed', 'overgrow', 'Adamant', [32, 32, 0, 0, 0, 2], []));
run('Rillaboom Overgrow, partner Rillaboom sets terrain', S('Rillaboom', '', 'overgrow', 'Adamant', [32, 32, 0, 0, 0, 2], []), S('Rillaboom', '', 'grassysurge', 'Adamant', [32, 32, 0, 0, 0, 2], []));
run('Mega Salamence (Intimidate)', S('Salamence', 'salamencite', 'intimidate', 'Timid', [2, 0, 0, 32, 0, 32], []));
run('Salamence Moxie no item', S('Salamence', '', 'moxie', 'Timid', [2, 0, 0, 32, 0, 32], []));
run('Basculegion', S('Basculegion', 'lifeorb', 'adaptability', 'Adamant', [2, 32, 0, 0, 0, 32], []));
