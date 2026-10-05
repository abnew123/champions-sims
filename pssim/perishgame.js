// Turn-3 guessing game inside the Perish loop. After T1 (their Fake Out Kingambit + Perish Song) and T2 (their double Protect),
// does Gengar survive on the field to trap me at my turn-4 choice? Trapped at T4 => both my perished leads faint at end of T4.
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const OPPSETS = {Gengar: 'gengarite|cursedbody|Modest|perishsong/protect/shadowball/sludgebomb', Incineroar: 'passhoberry|intimidate|Sassy|fakeout/flareblitz/partingshot/protect',
  Rillaboom: process.env.RILLA_ITEM === 'sitrus' ? 'sitrusberry|grassysurge|Sassy|fakeout/grassyglide/protect/uturn' : 'ejectbutton|grassysurge|Sassy|fakeout/grassyglide/protect/uturn',
  Politoed: 'sitrusberry|drizzle|Calm|encore/perishsong/protect/weatherball'};
const EV = {Gengar: [2, 0, 0, 32, 0, 32], Incineroar: [32, 0, 14, 0, 20, 0], Rillaboom: [32, 0, 14, 0, 20, 0], Politoed: [32, 0, 14, 0, 20, 0]};
const opp = ['Gengar', 'Incineroar', 'Rillaboom', 'Politoed'].map(sp => { const [item, ability, nature, mv] = OPPSETS[sp].split('|'); return T.toSet({species: sp, item, ability, nature, moves: mv.split('/'), evs: EV[sp]}); });
const mine = ['Salamence', 'Kingambit', 'Incineroar', 'Gholdengo'].map(n => T.toSet(T.MY[n]));
const T1 = process.argv[2] === 'DE' ? 'move 2 1 mega, move 1 1' : 'move 1 mega, move 1 1';
// their turn-3 options: [label, choice, forced-switch choices in order]
const THEM = [
  ['A: Gengar out, Parting Shot Salamence -> Gengar back', 'switch 3, move 3 1', ['switch 3', 'switch 4']],
  ['A2: Gengar out, Parting Shot Kingambit -> Gengar back', 'switch 3, move 3 2', ['switch 3', 'switch 4']],
  ['B: Gengar Protect again, Parting Shot Salamence', 'move 2, move 3 1', ['switch 3', 'switch 4']],
  ['B2: Gengar Protect again, Incineroar Protect again', 'move 2, move 4', []],
  ['C: Gengar Shadow Ball Salamence, Parting Shot Salamence', 'move 3 1, move 3 1', ['switch 3', 'switch 4']],
];
const ME = [];
for (const [sl, sc] of [['Sala Double-Edge Gengar-slot', 'move 2 1'], ['Sala Double-Edge Incin-slot', 'move 2 2'], ['Sala Hyper Voice', 'move 1'], ['Sala Protect', 'move 4']])
  for (const [kl, kc] of [['Kowtow Gengar-slot', 'move 1 1'], ['Kowtow Incin-slot', 'move 1 2'], ['Sucker Gengar-slot', 'move 2 1']]) ME.push([sl + ' + ' + kl, sc + ', ' + kc]);
function run(myC, th, seed) {
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed, 101, 211, 307]}); b.debugMode = false;
  b.setPlayer('p1', {name: 'Me', team: mine}); b.setPlayer('p2', {name: 'Them', team: opp}); b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
  const turn = (c1, c2, forced2) => { if (!b.choose('p1', c1) || !b.choose('p2', c2)) return false; const f = [...(forced2 || [])];
    for (let g = 0; g < 6 && !b.ended; g++) { let pend = false; for (const s of b.sides) if (s.requestState === 'switch' && !s.isChoiceDone()) { const x = s.id === 'p2' ? f.shift() : null; if (!(x && s.choose(x))) s.autoChoose(); pend = true; } if (b.allChoicesDone() && pend) b.commitChoices(); else break; }
    return true; };
  if (!turn(T1, 'move 1 mega, move 1 2')) return null;          // T1: Perish + Fake Out Kingambit
  if (b.sides[1].active[0].species.baseSpecies !== 'Gengar' || b.sides[1].active[0].fainted) return 1;  // Gengar already gone
  if (!turn('move 1, move 1 1', 'move 2, move 4')) return null;  // T2: they double Protect
  if (!turn(myC, th[1], th[2])) return null;                     // T3: the guess
  const req = b.sides[0].activeRequest; if (!req || !req.active) return 1;
  const trapped = req.active.some(a => a.trapped); const leadsAlive = b.sides[0].active.every(p => p && !p.fainted && ['Salamence', 'Kingambit'].includes(p.species.baseSpecies));
  return trapped ? 0 : 1;   // 1 = I can switch my perished leads out on turn 4
}
const N = +(process.argv[3] || 24); const M = [];
for (const [ml, mc] of ME) { const row = []; for (const th of THEM) { let s = 0, n = 0; for (let k = 1; k <= N; k++) { const r = run(mc, th, k); if (r === null) continue; s += r; n++; } row.push(n ? s / n : null); } M.push(row); }
console.log(JSON.stringify({T1: process.argv[2], them: THEM.map(t => t[0]), me: ME.map(m => m[0]), M}));
