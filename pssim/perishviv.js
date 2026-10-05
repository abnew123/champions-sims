// Gengar + Vivillon Perish line from the player's game, turn by turn in Showdown's engine (Champions data).
// T1: they Perish Song + Sleep Powder Kingambit. T2: they double Protect. T3: the guess. Question: is Gengar on the field
// when I choose on turn 4 (then both my perished leads are trapped and faint at the end of turn 4)?
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const opp = ['Gengar', 'Vivillon', 'Incineroar', 'Rillaboom'].map(sp => T.toSet(T.oppSet('Perish trap', sp)));
const mine = ['Salamence', 'Kingambit', 'Incineroar', 'Gholdengo'].map(n => T.toSet(T.MY[n]));
const T1 = {HV: 'move hypervoice mega, move suckerpunch 1', DE: 'move doubleedge 1 mega, move suckerpunch 1'}[process.argv[2] || 'HV'];
const T2 = {TW: 'move tailwind, move kowtowcleave 1', HV: 'move hypervoice, move kowtowcleave 1'}[process.argv[3] || 'TW'];
const THEM = [
  ['Gengar out, Vivillon Rage Powder', 'switch 3, move ragepowder', ['switch 3']],
  ['Gengar out, Vivillon Protect again', 'switch 3, move protect', ['switch 3']],
  ['Gengar Protect again, Vivillon Rage Powder', 'move protect, move ragepowder', ['switch 3']],
  ['Gengar Protect again, Vivillon Protect again', 'move protect, move protect', ['switch 3']],
  ['Gengar Shadow Ball Salamence, Vivillon Rage Powder', 'move shadowball 1, move ragepowder', ['switch 3']],
  ['Gengar out, Vivillon Hurricane Salamence', 'switch 3, move hurricane 1', ['switch 3']],
];
const ME = [];
for (const [sl, sc] of [['Hyper Voice', 'move hypervoice'], ['Double-Edge Gengar slot', 'move doubleedge 1'], ['Protect', 'move protect']])
  for (const [kl, kc] of [['Kowtow Gengar slot', 'move kowtowcleave 1'], ['Sucker Punch Gengar slot', 'move suckerpunch 1']]) ME.push([sl + ' + ' + kl, sc + ', ' + kc]);
function run(myC, th, seed) {
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed, 17, 29, 43]}); b.debugMode = false;
  b.setPlayer('p1', {name: 'Me', team: mine}); b.setPlayer('p2', {name: 'Them', team: opp}); b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
  const turn = (c1, c2, forced2) => { if (!b.choose('p1', c1)) return 'p1 ' + b.sides[0].choice.error; if (!b.choose('p2', c2)) return 'p2 ' + b.sides[1].choice.error;
    const f = [...(forced2 || [])];
    for (let g = 0; g < 6 && !b.ended; g++) { let pend = false; for (const s of b.sides) if (s.requestState === 'switch' && !s.isChoiceDone()) { const x = s.id === 'p2' ? f.shift() : null; if (!(x && s.choose(x))) s.autoChoose(); pend = true; } if (b.allChoicesDone() && pend) b.commitChoices(); else break; }
    return null; };
  let e = turn(T1, 'move perishsong mega, move sleeppowder 2'); if (e) return {err: 'T1 ' + e};
  const g0 = b.sides[1].active[0]; if (g0.fainted || g0.species.baseSpecies !== 'Gengar') return {esc: 1, note: 'Gengar gone T1'};
  const kSleep = b.sides[0].active[1].status === 'slp';
  e = turn(T2, 'move protect, move protect'); if (e) return {err: 'T2 ' + e};
  e = turn(myC, th[1], th[2]); if (e) return {err: 'T3 ' + e};
  const req = b.sides[0].activeRequest; if (!req || !req.active) return {esc: 1, note: 'no request'};
  const trapped = req.active.some(a => a.trapped);
  const vivDead = b.sides[1].pokemon.find(p => p.species.name === 'Vivillon').fainted; const gen = b.sides[1].pokemon.find(p => p.species.baseSpecies === 'Gengar');
  return {esc: trapped ? 0 : 1, vivDead, genDead: gen.fainted, kSleep, kAwakeT3: b.sides[0].pokemon.find(p => p.species.name === 'Kingambit').status !== 'slp'};
}
const N = +(process.argv[4] || 24); const M = []; const extra = [];
for (const [ml, mc] of ME) {
  const row = [];
  for (const th of THEM) { let s = 0, n = 0, vd = 0, gd = 0, err = null;
    for (let k = 1; k <= N; k++) { const r = run(mc, th, k); if (r.err) { err = r.err; continue; } s += r.esc; n++; vd += r.vivDead ? 1 : 0; gd += r.genDead ? 1 : 0; }
    row.push(n ? {esc: s / n, vivDead: vd / n, genDead: gd / n, err} : {err}); }
  M.push([ml, row]);
}
console.log(JSON.stringify({T1: process.argv[2] || 'HV', T2: process.argv[3] || 'TW', them: THEM.map(t => t[0]), M}));
