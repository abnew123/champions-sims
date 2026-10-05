// Mega Lopunny (Jolly, Close Combat / Fake Out / Protect / Triple Axel, 2 HP / 32 Atk / 32 Spe) vs the player's six, turn one, Champions engine.
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const my = n => T.toSet(T.MY[n]);
const LOP = (ability = 'limber') => T.toSet({species: 'Lopunny', item: 'lopunnite', ability, moves: ['closecombat', 'fakeout', 'protect', 'tripleaxel'], nature: 'Jolly', evs: [2, 32, 0, 0, 0, 32]});
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
const NOINT = s => Object.assign({}, s, {ability: s.species === 'Salamence' ? 'moxie' : s.species === 'Incineroar' ? 'blaze' : s.ability});
function battle(p1, p2, c1, c2, seed) {
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed, 5, 9, 13]}); b.debugMode = false;
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

const IND = T.toSet(T.oppSet('Indeedee TR / Psychic Terrain', 'Indeedee-F'));
const noSurge = st => Object.assign({}, st, {ability: 'overgrow'});
console.log('Rillaboom into Mega Lopunny (142 HP):');
test('Wood Hammer, Grassy Terrain', [my('Rillaboom'), FILL], [LOP(), FILL], 'move woodhammer 1, move splash', 'move protect mega, move splash'.replace('protect', 'fakeout 2'), 'p1a: Rillaboom', 'Wood Hammer', 'Lopunny', 142);
test('Wood Hammer, Psychic Terrain (Indeedee)', [noSurge(my('Rillaboom')), FILL], [LOP(), IND], 'move woodhammer 1, move splash', 'move fakeout 2 mega, move psychic 2', 'p1a: Rillaboom', 'Wood Hammer', 'Lopunny', 142);
test('Wood Hammer, no terrain', [noSurge(my('Rillaboom')), FILL], [LOP(), FILL], 'move woodhammer 1, move splash', 'move fakeout 2 mega, move splash', 'p1a: Rillaboom', 'Wood Hammer', 'Lopunny', 142);
test('Grassy Glide, Grassy Terrain', [my('Rillaboom'), FILL], [LOP(), FILL], 'move grassyglide 1, move splash', 'move fakeout 2 mega, move splash', 'p1a: Rillaboom', 'Grassy Glide', 'Lopunny', 142);
test('Close Combat -> Rillaboom after Intimidate (-1)', [my('Rillaboom'), my('Salamence')], [LOP(), FILL], 'move woodhammer 2, move tailwind mega', 'move closecombat 1 mega, move splash', 'p2a: Lopunny', 'Close Combat', 'Rillaboom', 193);
test('Triple Axel -> Rillaboom after Intimidate (-1)', [my('Rillaboom'), my('Salamence')], [LOP(), FILL], 'move woodhammer 2, move tailwind mega', 'move tripleaxel 1 mega, move splash', 'p2a: Lopunny', 'Triple Axel', 'Rillaboom', 193);
// Milotic: Competitive. Modest attacker (Ice Beam / Icy Wind / Protect / Scald) and Calm Coil set (Coil / Hypnosis / Muddy Water / Protect)
const MILO_M = T.toSet({species: 'Milotic', item: 'sitrusberry', ability: 'competitive', moves: ['icebeam', 'icywind', 'protect', 'scald'], nature: 'Modest', evs: [32, 0, 2, 32, 0, 0]});
const MILO_C = T.toSet({species: 'Milotic', item: 'leftovers', ability: 'competitive', moves: ['coil', 'hypnosis', 'muddywater', 'protect'], nature: 'Calm', evs: [32, 0, 2, 0, 32, 0]});
const MILO_B = T.toSet({species: 'Milotic', item: 'sitrusberry', ability: 'competitive', moves: ['coil', 'hypnosis', 'muddywater', 'protect'], nature: 'Bold', evs: [32, 0, 32, 0, 2, 0]});
const MHP = (() => { const b = battle([FILL], [MILO_M], 'move splash, move splash', 'move protect, move splash', 1); return b.sides[1].active[0].maxhp; })();
console.log(`\nMilotic attacking (${MHP} HP). "+2" = led into your Salamence's Intimidate:`);
test('+2 Modest Ice Beam -> Mega Salamence', [my('Salamence'), FILL], [MILO_M, FILL], 'move tailwind mega, move splash', 'move icebeam 1, move splash', 'p2a: Milotic', 'Ice Beam', 'Salamence', 171);
test('+0 Modest Ice Beam -> Mega Salamence', [NOINT(my('Salamence')), FILL], [MILO_M, FILL], 'move tailwind mega, move splash', 'move icebeam 1, move splash', 'p2a: Milotic', 'Ice Beam', 'Salamence', 171);
test('+2 Modest Scald -> Kingambit', [my('Salamence'), my('Kingambit')], [MILO_M, FILL], 'move tailwind mega, move ironhead 2', 'move scald 2, move splash', 'p2a: Milotic', 'Scald', 'Kingambit', 207);
test('+0 Modest Scald -> Kingambit', [NOINT(my('Salamence')), my('Kingambit')], [MILO_M, FILL], 'move tailwind mega, move ironhead 2', 'move scald 2, move splash', 'p2a: Milotic', 'Scald', 'Kingambit', 207);
test('+2 Modest Scald -> Gholdengo', [my('Salamence'), my('Gholdengo')], [MILO_M, FILL], 'move tailwind mega, move powergem 2', 'move scald 2, move splash', 'p2a: Milotic', 'Scald', 'Gholdengo', 164);
test('+2 Calm Muddy Water -> Kingambit', [my('Salamence'), my('Kingambit')], [MILO_C, FILL], 'move tailwind mega, move ironhead 2', 'move muddywater, move splash', 'p2a: Milotic', 'Muddy Water', 'Kingambit', 207);
test('+2 Calm Muddy Water -> Mega Salamence', [my('Salamence'), my('Kingambit')], [MILO_C, FILL], 'move tailwind mega, move ironhead 2', 'move muddywater, move splash', 'p2a: Milotic', 'Muddy Water', 'Salamence', 171);
console.log('\nYour hits into Milotic (Calm 32 HP / 32 SpD, Sitrus) and Bold (32 HP / 32 Def):');
for (const [lab, M] of [['Calm', MILO_C], ['Bold', MILO_B]]) {
  const hp = MHP;
  test(`Rillaboom Wood Hammer -> ${lab}`, [my('Rillaboom'), FILL], [M, FILL], 'move woodhammer 1, move splash', 'move protect, move splash'.replace('move protect', 'move coil'), 'p1a: Rillaboom', 'Wood Hammer', 'Milotic', hp);
  test(`Rillaboom Grassy Glide -> ${lab}`, [my('Rillaboom'), FILL], [M, FILL], 'move grassyglide 1, move splash', 'move coil, move splash', 'p1a: Rillaboom', 'Grassy Glide', 'Milotic', hp);
  test(`Kingambit Low Kick -> ${lab}`, [my('Kingambit'), FILL], [M, FILL], 'move lowkick 1, move splash', 'move coil, move splash', 'p1a: Kingambit', 'Low Kick', 'Milotic', hp);
  test(`Kingambit Kowtow -> ${lab}`, [my('Kingambit'), FILL], [M, FILL], 'move kowtowcleave 1, move splash', 'move coil, move splash', 'p1a: Kingambit', 'Kowtow Cleave', 'Milotic', hp);
  test(`Salamence Double-Edge -> ${lab}`, [NOINT(my('Salamence')), FILL], [M, FILL], 'move doubleedge 1 mega, move splash', 'move coil, move splash', 'p1a: Salamence', 'Double-Edge', 'Milotic', hp);
  test(`Gholdengo Shadow Ball -> ${lab}`, [my('Gholdengo'), FILL], [M, FILL], 'move shadowball 1, move splash', 'move coil, move splash', 'p1a: Gholdengo', 'Shadow Ball', 'Milotic', hp);
}
test('Kingambit Low Kick at +2 (Defiant, after Icy Wind) -> Calm', [my('Kingambit'), FILL], [MILO_C, FILL], 'move lowkick 1, move splash', 'move coil, move splash', 'p1a: Kingambit', 'Low Kick', 'Milotic', MHP);
