// Mega vs non-Mega Salamence, turn one, in Showdown's engine with the Champions data: damage dealt, damage taken, speed.
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const MYSET = n => T.toSet(T.MY[n]);
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
const opp = (arch, sp, moves) => { const s = T.toSet(T.oppSet(arch, sp)); if (moves) s.moves = moves; return s; };
function turn(p2sets, c1, c2, seed) {
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed, 7, 11, 13]}); b.debugMode = false;
  b.setPlayer('p1', {name: 'Me', team: [MYSET('Salamence'), MYSET('Gholdengo'), MYSET('Kingambit'), MYSET('Incineroar')]});
  b.setPlayer('p2', {name: 'Them', team: [...p2sets, FILL, FILL]});
  b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
  if (!b.choose('p1', c1) || !b.choose('p2', c2)) throw new Error('bad choice ' + c1 + ' / ' + c2 + ' ' + (b.sides.map(s => s.choice.error).join(' ')));
  return b;
}
// damage lines inside one attacker's move block; exact HP from the split (secret) copy
function hits(b, who, move) {
  const L = b.log; const out = []; let inMove = false; let crit = new Set();
  for (let i = 0; i < L.length; i++) {
    const x = L[i];
    if (x.startsWith('|move|')) inMove = x.startsWith(`|move|${who}|${move}|`);
    else if (inMove && x.startsWith('|-crit|')) crit.add(x.split('|')[2]);
    else if (inMove && x === '|split|p2' || inMove && x === '|split|p1') { const d = L[i + 1]; if (d.startsWith('|-damage|')) { const [, , tgt, hp] = d.split('|'); out.push([tgt, hp, crit.has(tgt)]); } i += 2; }
    else if (inMove && x.startsWith('|-damage|') && !/\[from\]/.test(x)) { const [, , tgt, hp] = x.split('|'); out.push([tgt, hp, crit.has(tgt)]); }
  }
  return out;
}
function range(label, p2sets, c1, c2, who, move, N = 64) {
  const dmg = {};
  for (let s = 1; s <= N; s++) {
    const b = turn(p2sets, c1, c2, s); const side = who.startsWith('p1') ? b.sides[1] : b.sides[0];
    for (const [tgt, hp, crit] of hits(b, who, move)) {
      if (crit) continue; const [now, max] = hp.split(' ')[0].split('/').map(Number);
      const mon = [...b.sides[0].pokemon, ...b.sides[1].pokemon].find(p => tgt.endsWith(': ' + p.name)); const full = mon ? mon.maxhp : max;
      (dmg[tgt] = dmg[tgt] || []).push(full - (hp.includes('fnt') ? 0 : now));
    }
  }
  for (const [tgt, v] of Object.entries(dmg)) {
    const mon = tgt.split(': ')[1]; const lo = Math.min(...v), hi = Math.max(...v);
    const b = turn(p2sets, c1, c2, 1); const p = [...b.sides[0].pokemon, ...b.sides[1].pokemon].find(q => q.name === mon);
    console.log(`  ${label.padEnd(34)} -> ${mon.padEnd(11)} ${String(lo).padStart(3)}-${String(hi).padStart(3)} of ${p.maxhp}  (${(100 * lo / p.maxhp).toFixed(0)}-${(100 * hi / p.maxhp).toFixed(0)}%)  n=${v.length}`);
  }
}
const W = ['splash'];
console.log('Hyper Voice (spread), Salamence Mega vs not:');
for (const [pair, sets, c2] of [
  ['Raichu-Mega-Y + Gholdengo', [opp('Tailwind goodstuffs', 'Raichu', ['splash']), opp('Tailwind goodstuffs', 'Gholdengo', W)], 'move 1 mega, move 1'],
  ['Incineroar + Gengar-Mega', [opp('Perish trap', 'Incineroar', W), opp('Perish trap', 'Gengar', W)], 'move 1, move 1 mega'],
  ['Archaludon + Tyranitar-Mega', [opp('Rain', 'Archaludon', W), opp('Sand', 'Tyranitar', W)], 'move 1, move 1 mega']]) {
  for (const mega of [true, false]) range(`${mega ? 'Mega' : 'non-Mega'} Hyper Voice vs ${pair}`, sets, `move 1${mega ? ' mega' : ''}, move 4`, c2, 'p1a: Salamence', 'Hyper Voice');
}
console.log('Double-Edge into Mega Raichu Y (resists Flying, neutral to Normal):');
for (const mega of [true, false]) range(`${mega ? 'Mega' : 'non-Mega'} Double-Edge`, [opp('Tailwind goodstuffs', 'Raichu', ['splash']), opp('Tailwind goodstuffs', 'Gholdengo', W)], `move 2 1${mega ? ' mega' : ''}, move 4`, 'move 1 mega, move 1', 'p1a: Salamence', 'Double-Edge');
console.log('Damage taken by Salamence (after its Intimidate), Mega vs not:');
for (const mega of [true, false]) {
  range(`${mega ? 'Mega' : 'non-Mega'}: Kingambit Iron Head`, [opp('Sun', 'Kingambit', ['ironhead']), opp('Perish trap', 'Incineroar', W)], `move 3${mega ? ' mega' : ''}, move 4`, 'move 1 1, move 1', 'p2a: Kingambit', 'Iron Head');
  range(`${mega ? 'Mega' : 'non-Mega'}: Mega Tyranitar Rock Slide`, [opp('Sand', 'Tyranitar', ['rockslide']), opp('Perish trap', 'Incineroar', W)], `move 3${mega ? ' mega' : ''}, move 4`, 'move 1 mega, move 1', 'p2a: Tyranitar', 'Rock Slide');
}
for (const mega of [true, false]) { const b = turn([opp('Perish trap', 'Incineroar', W), FILL], `move 3${mega ? ' mega' : ''}, move 4`, 'move 1, move 1', 1); const s = b.sides[0].active[0]; console.log(`  ${mega ? 'Mega' : 'non-Mega'} Salamence stats: ${JSON.stringify(s.storedStats)} hp ${s.maxhp} ability ${s.ability}`); }
