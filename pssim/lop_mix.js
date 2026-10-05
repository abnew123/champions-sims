// Mega Lopunny (Jolly, Close Combat / Fake Out / Protect / Triple Axel, 2 HP / 32 Atk / 32 Spe) vs the player's six, turn one, Champions engine.
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const my = n => T.toSet(T.MY[n]);
const LOP = (ability = 'limber') => T.toSet({species: 'Lopunny', item: 'lopunnite', ability, moves: ['closecombat', 'fakeout', 'protect', 'tripleaxel'], nature: 'Jolly', evs: [2, 32, 0, 0, 0, 32]});
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
const NOINT = s => Object.assign({}, s, {ability: s.species === 'Salamence' ? 'moxie' : s.species === 'Incineroar' ? 'blaze' : s.ability});
function battle(p1, p2, c1, c2, seed) {
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: require('./seedmix.js')(seed)}); b.debugMode = false;
  b.setPlayer('p1', {name: 'Me', team: [...p1, FILL, FILL].slice(0, 4)}); b.setPlayer('p2', {name: 'Them', team: [...p2, FILL, FILL].slice(0, 4)});
  b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
  if (!b.choose('p1', c1)) throw new Error('p1 ' + c1 + ' ' + b.sides[0].choice.error);
  if (!b.choose('p2', c2)) throw new Error('p2 ' + c2 + ' ' + b.sides[1].choice.error);
  return b;
}
// HP of `tgt` right after `who` used `move` (last damage line inside that move's block), crit-free samples only
function hpAfter(b, who, move, tgt, maxhp) {
  let inMove = false, hp = null, crit = false, sash = false;
  for (const x of b.log) {
    if (x.startsWith('|move|')) inMove = x.startsWith(`|move|${who}|${move}|`);
    else if (!inMove) continue;
    else if (x.startsWith('|-crit|') && x.includes(tgt)) crit = true;
    else if (x.startsWith('|-enditem|') && x.includes(tgt) && x.includes('Focus Sash')) sash = true;
    else if (x.startsWith('|-damage|') && x.split('|')[2].endsWith(': ' + tgt) && !x.includes('[from]')) {
      const h = x.split('|')[3]; if (h.includes('fnt')) hp = '0 fnt'; else if (+h.split('/')[1].split(' ')[0] === maxhp) hp = h; }
  }
  return {hp, crit, sash};
}
function test(label, p1, p2, c1, c2, who, move, tgtName, maxhp, N = 60) {
  const d = []; let ko = 0, n = 0, sash = 0;
  for (let s = 1; s <= N; s++) { const b = battle(p1, p2, c1, c2, s); const r = hpAfter(b, who, move, tgtName, maxhp); if (r.hp === null || r.crit) continue;
    n++; const now = r.hp.includes('fnt') ? 0 : +r.hp.split('/')[0]; if (now === 0) ko++; if (r.sash) sash++; d.push(maxhp - now); }
  const lo = Math.min(...d), hi = Math.max(...d);
  console.log(`  ${label.padEnd(46)} ${String(lo).padStart(3)}-${String(hi).padStart(3)} of ${maxhp} (${(100 * lo / maxhp).toFixed(0)}-${(100 * hi / maxhp).toFixed(0)}%)  KO ${ko}/${n}${sash ? `  sash ${sash}` : ''}`);
}
const HP = {Salamence: 171, Kingambit: 207, Incineroar: 202, Gholdengo: 164, Rillaboom: 193, Sneasler: 169};
console.log('Mega Lopunny attacking (no Intimidate on it):');
for (const [tgt, mv, c2] of [['Kingambit', 'Close Combat', 'move closecombat 1 mega, move splash'], ['Incineroar', 'Close Combat', 'move closecombat 1 mega, move splash'],
  ['Gholdengo', 'Close Combat', 'move closecombat 1 mega, move splash'], ['Rillaboom', 'Close Combat', 'move closecombat 1 mega, move splash'], ['Rillaboom', 'Triple Axel', 'move tripleaxel 1 mega, move splash'],
  ['Salamence', 'Triple Axel', 'move tripleaxel 1 mega, move splash'], ['Sneasler', 'Close Combat', 'move closecombat 1 mega, move splash'], ['Sneasler', 'Triple Axel', 'move tripleaxel 1 mega, move splash']]) {
  const tset = NOINT(my(tgt)); const c1 = tgt === 'Salamence' ? 'move protect mega, move splash' : 'move ' + ({Kingambit: 'suckerpunch 1', Incineroar: 'fakeout 1', Gholdengo: 'protect', Rillaboom: 'fakeout 1', Sneasler: 'protect'}[tgt]) + ', move splash';
  // target does nothing that matters: use a harmless first move where possible
  const c1b = tgt === 'Salamence' ? 'move tailwind mega, move splash' : tgt === 'Kingambit' ? 'move ironhead 2, move splash' : tgt === 'Incineroar' ? 'move flareblitz 2, move splash' : tgt === 'Gholdengo' ? 'move powergem 2, move splash' : tgt === 'Rillaboom' ? 'move woodhammer 2, move splash' : 'move direclaw 2, move splash';
  test(`${mv} -> ${tgt}`, [tset, FILL], [LOP(), FILL], c1b, c2, 'p2a: Lopunny', mv, tgt, HP[tgt]);
}
console.log('Same, after Salamence/Incineroar lead Intimidate (-1, before it Mega Evolves):');
test('Triple Axel -> Salamence (-1)', [my('Salamence'), FILL], [LOP(), FILL], 'move tailwind mega, move splash', 'move tripleaxel 1 mega, move splash', 'p2a: Lopunny', 'Triple Axel', 'Salamence', 171);
test('Close Combat -> Kingambit (-1)', [my('Kingambit'), my('Incineroar')], [LOP(), FILL], 'move ironhead 2, move flareblitz 2', 'move closecombat 1 mega, move splash', 'p2a: Lopunny', 'Close Combat', 'Kingambit', 207);
console.log('Your hits into Mega Lopunny (it Protects nothing; it uses Fake Out on the filler):');
const LOPHP = (() => { const b = battle([FILL], [LOP()], 'move splash, move splash', 'move protect mega, move splash', 1); return b.sides[1].active[0].maxhp; })();
for (const [att, c1, mv] of [['Salamence', 'move doubleedge 1 mega, move splash', 'Double-Edge'], ['Salamence', 'move hypervoice mega, move splash', 'Hyper Voice'],
  ['Sneasler', 'move closecombat 1, move splash', 'Close Combat'], ['Sneasler', 'move acrobatics 1, move splash', 'Acrobatics'], ['Rillaboom', 'move woodhammer 1, move splash', 'Wood Hammer'],
  ['Kingambit', 'move ironhead 1, move splash', 'Iron Head'], ['Gholdengo', 'move makeitrain, move splash', 'Make It Rain'], ['Incineroar', 'move flareblitz 1, move splash', 'Flare Blitz']]) {
  test(`${att} ${mv} -> Mega Lopunny`, [NOINT(my(att)), FILL], [LOP(), FILL], c1, 'move fakeout 2 mega, move splash', `p1a: ${att}`, mv, 'Lopunny', LOPHP);
}
const b = battle([my('Salamence'), my('Sneasler')], [LOP(), FILL], 'move tailwind mega, move protect', 'move protect mega, move splash', 1);
console.log('speeds:', 'Mega Lopunny', b.sides[1].active[0].getStat('spe'), '| Mega Salamence', b.sides[0].active[0].getStat('spe'), '| Sneasler', b.sides[0].active[1].getStat('spe'), '(x2 with Unburden) | HP', LOPHP);
