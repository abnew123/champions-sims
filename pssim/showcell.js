// print the battle log of one cell: node showcell.js arch pairIdx l1 l2 b1 b2 myChoice theirChoice seedk
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const [arch, idx, l1, l2, b1, b2, c1, c2, sk] = process.argv.slice(2);
const P = T.OPP[arch].pairs[+idx]; const lead = P.pair.split(' + ');
const backs = P.back.split(', ').map(x => x.split(':')[0]).filter(x => !lead.includes(x));
const dists = lead.map(sp => T.parseDist(P.t1[sp]));
const sets = lead.map((sp, i) => T.oppSet(arch, sp, dists[i].map(x => x[0]).filter(x => !x.startsWith('('))));
const bsets = []; for (const sp of backs) { try { bsets.push(T.oppSet(arch, sp, [])); } catch (e) {} if (bsets.length === 2) break; }
const opp = [...sets, ...bsets].map(T.toSet); const my = [l1, l2, b1, b2].map(n => T.toSet(T.MY[n]));
const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [+sk, 101, 211, 307]});
b.setPlayer('p1', {name: 'Me', team: my}); b.setPlayer('p2', {name: 'Them', team: opp});
b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
const s0 = b.log.length; console.log(b.choose('p1', c1), b.choose('p2', c2));
for (let g = 0; b.turn < 2 && g < 8; g++) { for (const side of b.sides) if (side.requestState === 'switch' && !side.isChoiceDone()) side.autoChoose(); if (b.allChoicesDone()) b.commitChoices(); else break; }
console.log(b.log.slice(s0 - 12).filter(l => !l.startsWith('|t:|') && !l.startsWith('|split')).join('\n'));
for (const side of b.sides) for (const p of side.pokemon) console.log(side.id, p.species.name, p.hp + '/' + p.maxhp, JSON.stringify(p.boosts), p.status);
