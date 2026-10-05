// Scripted multi-turn Perish lines in the Showdown engine (Champions data).
// node perishline.js "<myLead1>,<myLead2>,<back1>,<back2>" "<turn choices JSON>" seed
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const OPPSETS = {
  Gengar: 'gengarite|cursedbody|Modest|perishsong/protect/shadowball/sludgebomb', Incineroar: 'passhoberry|intimidate|Sassy|fakeout/flareblitz/partingshot/protect',
  Rillaboom: process.env.RILLA_ITEM === 'sitrus' ? 'sitrusberry|grassysurge|Sassy|fakeout/grassyglide/protect/uturn' : 'ejectbutton|grassysurge|Sassy|fakeout/grassyglide/protect/uturn', Politoed: 'sitrusberry|drizzle|Calm|encore/perishsong/protect/weatherball',
};
const EV = {Gengar: [2, 0, 0, 32, 0, 32], Incineroar: [32, 0, 14, 0, 20, 0], Rillaboom: [32, 0, 14, 0, 20, 0], Politoed: [32, 0, 14, 0, 20, 0]};
const opp = ['Gengar', 'Incineroar', 'Rillaboom', 'Politoed'].map(sp => { const [item, ability, nature, mv] = OPPSETS[sp].split('|');
  return T.toSet({species: sp, item, ability, nature, moves: mv.split('/'), evs: EV[sp]}); });
const mine = process.argv[2].split(',').map(n => T.toSet(T.MY[n]));
const turns = JSON.parse(process.argv[3]); const seed = [+(process.argv[4] || 1), 101, 211, 307];
const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed}); b.debugMode = false;
b.setPlayer('p1', {name: 'Me', team: mine}); b.setPlayer('p2', {name: 'Them', team: opp});
b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
let from = b.log.length;
const show = () => { const out = b.log.slice(from).filter(l => /^\|(move|switch|faint|-damage|cant|-activate|-start|-fail|-immune|turn|-mega|-boost|-unboost|-singleturn|detailschange)\|/.test(l) && !l.includes('[silent]')); from = b.log.length; return out.map(l => '   ' + l).join('\n'); };
console.log(show());
for (const [i, [c1, c2, f1, f2]] of turns.entries()) {
  const req = b.sides[0].activeRequest; const trapped = req && req.active ? req.active.map(a => !!(a.trapped || a.maybeTrapped)) : null;
  console.log(`-- T${b.turn} my trapped: ${JSON.stringify(trapped)} | me: ${c1} | them: ${c2}`);
  const ok1 = b.choose('p1', c1), ok2 = b.choose('p2', c2);
  if (!ok1 || !ok2) { console.log('   INVALID', ok1, ok2, b.sides[0].choice.error, b.sides[1].choice.error); break; }
  const forced = {p1: (f1 || '').split(';').filter(Boolean), p2: (f2 || '').split(';').filter(Boolean)};
  for (let g = 0; g < 6 && !b.ended; g++) { let pend = false;
    for (const s of b.sides) if (s.requestState === 'switch' && !s.isChoiceDone()) { const f = forced[s.id].shift(); if (f) s.choose(f); else s.autoChoose(); pend = true; }
    if (b.allChoicesDone() && pend) b.commitChoices(); else break; }
  console.log(show());
  const st = side => side.pokemon.map(p => `${p.name}${p.isActive ? '*' : ''} ${p.hp}/${p.maxhp}${p.volatiles.perishsong ? ' perish' + p.volatiles.perishsong.duration : ''}`).join(', ');
  console.log(`   me: ${st(b.sides[0])}\n   them: ${st(b.sides[1])}`);
}
