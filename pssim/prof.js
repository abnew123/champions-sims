const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const my = ['Gholdengo','Kingambit','Salamence','Incineroar'].map(n => T.toSet(T.MY[n]));
const opp = ['Gholdengo','Raichu','Rillaboom','Arcanine-Hisui'].map(sp => T.toSet(T.oppSet('Tailwind goodstuffs', sp, [])));
let t0 = Date.now(), N = 1500;
for (let i = 0; i < N; i++) { const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [i+1,101,211,307]}); b.debugMode = false; b.setPlayer('p1', {name: 'Me', team: my}); b.setPlayer('p2', {name: 'Them', team: opp}); b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234'); b.choose('p1', 'move 2 1, move 1 2'); b.choose('p2', 'move 4 2, move 1 2 mega'); }
console.log('ms', (Date.now() - t0) / N);
