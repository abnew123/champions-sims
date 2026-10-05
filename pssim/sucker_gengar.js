// Kingambit Sucker Punch / Kowtow Cleave into Mega Gengar (Gengar attacking), plus turn order vs Vivillon's Sleep Powder
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const my = n => T.toSet(T.MY[n]);
const gen = T.toSet(T.oppSet('Perish trap', 'Gengar')); const viv = T.toSet(T.oppSet('Perish trap', 'Vivillon'));
const fill = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0,0,0,0,0,0]});
const res = {}; const order = {};
for (let seed = 1; seed <= 80; seed++) for (const [lab, c1] of [['Sucker', 'move 1, move 2 1'], ['Kowtow', 'move 1, move 1 1']]) {
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed, 3, 5, 7]}); b.debugMode = false;
  b.setPlayer('p1', {name: 'Me', team: [my('Salamence'), my('Kingambit'), my('Gholdengo'), my('Incineroar')]});
  b.setPlayer('p2', {name: 'Them', team: [gen, viv, fill, fill]});
  b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
  // Salamence Protects; Gengar Shadow Balls Salamence (mega); Vivillon Sleep Powders Kingambit
  const gm = gen.moves.map(m => m.toLowerCase().replace(/ /g, '')); const vm = viv.moves.map(m => m.toLowerCase().replace(/ /g, ''));
  b.choose('p1', `move 4, ${c1.split(', ')[1]}`);
  b.choose('p2', `move ${gm.indexOf('shadowball') + 1} 1 mega, move ${vm.indexOf('sleeppowder') + 1} 2`);
  const L = b.log.join('\n'); const g = b.sides[1].pokemon.find(p => p.name === 'Gengar' || p.species.baseSpecies === 'Gengar');
  const key = lab + (L.includes('|-crit|p2a: Gengar') ? ' (crit)' : '');
  (res[key] = res[key] || []).push(g.fainted ? 'KO' : g.maxhp - g.hp);
  const seq = [...L.matchAll(/\|move\|(p\da: \w+)\|([^|]+)\|/g)].map(m => m[1].split(': ')[1] + ':' + m[2]).join(' > ');
  order[lab + ' | ' + seq] = (order[lab + ' | ' + seq] || 0) + 1;
}
for (const [k, v] of Object.entries(res)) { const ko = v.filter(x => x === 'KO').length; const d = v.filter(x => x !== 'KO'); console.log(k.padEnd(16), `KO ${ko}/${v.length}`, d.length ? `non-KO damage ${Math.min(...d)}-${Math.max(...d)} of ${137}` : ''); }
for (const [k, v] of Object.entries(order).sort((a, b) => b[1] - a[1]).slice(0, 6)) console.log(String(v).padStart(3), k);
