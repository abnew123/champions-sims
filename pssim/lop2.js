// Rillaboom + Sneasler lead vs Indeedee-F + Mega Lopunny: does Grassy Seed / Unburden fire, which terrain stays, who moves first?
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const my = n => T.toSet(T.MY[n]);
const LOP = T.toSet({species: 'Lopunny', item: 'lopunnite', ability: 'limber', moves: ['closecombat', 'fakeout', 'protect', 'tripleaxel'], nature: 'Jolly', evs: [2, 32, 0, 0, 0, 32]});
const IND = T.toSet(T.oppSet('Indeedee TR / Psychic Terrain', 'Indeedee-F'));
const res = {};
for (const [lab, c2] of [['Indeedee Helping Hand, Lopunny CC Sneasler', 'move helpinghand, move closecombat 2 mega'], ['Indeedee Follow Me, Lopunny CC Sneasler', 'move followme, move closecombat 2 mega'],
                         ['Indeedee Helping Hand, Lopunny Fake Out Sneasler', 'move helpinghand, move fakeout 2 mega']]) {
  for (let seed = 1; seed <= 40; seed++) {
    const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed, 5, 9, 13]}); b.debugMode = false;
    b.setPlayer('p1', {name: 'Me', team: [my('Rillaboom'), my('Sneasler'), my('Salamence'), my('Kingambit')]});
    b.setPlayer('p2', {name: 'Them', team: [IND, LOP, T.toSet(T.oppSet('Indeedee TR / Psychic Terrain', 'Sneasler')), T.toSet(T.oppSet('Indeedee TR / Psychic Terrain', 'Incineroar'))]});
    b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
    const terrain0 = b.field.terrain; const spe = b.sides[0].active[1].getStat('spe'); const seedUsed = !b.sides[0].active[1].item;
    b.choose('p1', 'move woodhammer 2, move closecombat 2'); b.choose('p2', c2);
    const L = b.log; const lop = b.sides[1].pokemon.find(p => p.species.baseSpecies === 'Lopunny'); const sn = b.sides[0].pokemon.find(p => p.species.name === 'Sneasler');
    const first = L.filter(x => x.startsWith('|move|')).map(x => x.split('|')[2].split(': ')[1] + ':' + x.split('|')[3]).join(' > ');
    const key = `${lab} | terrain at start: ${terrain0} | Sneasler spe ${spe}${seedUsed ? ' (seed used)' : ''} | order: ${first} | Lopunny ${lop.fainted ? 'KO' : lop.hp + '/' + lop.maxhp} | Sneasler ${sn.fainted ? 'KO' : sn.hp + '/' + sn.maxhp}`;
    res[key] = (res[key] || 0) + 1;
  }
}
for (const [k, v] of Object.entries(res).sort()) console.log(String(v).padStart(3), k);
