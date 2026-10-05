const T = require('./t1sim.js'); const {Battle, State} = require('pokemon-showdown');
const my = ['Gholdengo','Kingambit','Salamence','Incineroar'].map(n => T.toSet(T.MY[n]));
const opp = ['Gholdengo','Raichu','Rillaboom','Arcanine-Hisui'].map(sp => T.toSet(T.oppSet('Tailwind goodstuffs', sp, [])));
let t0 = Date.now(), N = 300;
for (let i = 0; i < N; i++) { const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [i+1,101,211,307]}); b.setPlayer('p1', {name: 'Me', team: my}); b.setPlayer('p2', {name: 'Them', team: opp}); b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234'); }
console.log('create+preview ms', (Date.now() - t0) / N);
t0 = Date.now();
for (let i = 0; i < N; i++) { const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [i+1,101,211,307]}); b.setPlayer('p1', {name: 'Me', team: my}); b.setPlayer('p2', {name: 'Them', team: opp}); b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234'); b.choose('p1', 'move 2 1, move 1 2'); b.choose('p2', 'move 4 2, move 1 2 mega'); }
console.log('full ms', (Date.now() - t0) / N);
const b0 = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [1,101,211,307]}); b0.setPlayer('p1', {name: 'Me', team: my}); b0.setPlayer('p2', {name: 'Them', team: opp}); b0.choose('p1', 'team 1234'); b0.choose('p2', 'team 1234');
const js = JSON.stringify(b0.toJSON());
t0 = Date.now();
for (let i = 0; i < N; i++) { const b = Battle.fromJSON(js); b.choose('p1', 'move 2 1, move 1 2'); b.choose('p2', 'move 4 2, move 1 2 mega'); }
console.log('fromJSON+turn ms', (Date.now() - t0) / N);
