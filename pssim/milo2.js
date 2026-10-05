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


const MILO_C = T.toSet({species: 'Milotic', item: 'leftovers', ability: 'competitive', moves: ['coil', 'hypnosis', 'muddywater', 'protect'], nature: 'Calm', evs: [32, 0, 2, 0, 32, 0]});
const MILO_B = T.toSet({species: 'Milotic', item: 'sitrusberry', ability: 'competitive', moves: ['coil', 'hypnosis', 'muddywater', 'protect'], nature: 'Bold', evs: [32, 0, 32, 0, 2, 0]});
function boosted(label, M, c1, move) {  // Milotic already at +1 Def from a Coil
  const d = []; let ko = 0;
  for (let s = 1; s <= 60; s++) {
    const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [s, 5, 9, 13]}); b.debugMode = false;
    b.setPlayer('p1', {name: 'Me', team: [my('Rillaboom'), FILL, FILL, FILL]}); b.setPlayer('p2', {name: 'Them', team: [M, FILL, FILL, FILL]});
    b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234'); b.sides[1].active[0].boosts.def = 1;
    b.choose('p1', c1); b.choose('p2', 'move protect'.replace('protect', 'hypnosis 2') + ', move splash');
    const r = hpAfter(b, 'p1a: Rillaboom', move, 'Milotic', 202); if (r.hp === null || r.crit) continue;
    const now = r.hp.includes('fnt') ? 0 : +r.hp.split('/')[0]; if (!now) ko++; d.push(202 - now);
  }
  console.log(`  ${label.padEnd(40)} ${Math.min(...d)}-${Math.max(...d)} of 202 (${(100 * Math.min(...d) / 202).toFixed(0)}-${(100 * Math.max(...d) / 202).toFixed(0)}%)  KO ${ko}/${d.length}`);
}
console.log('Into Milotic that already used Coil (+1 Def), Grassy Terrain:');
boosted('Wood Hammer -> Calm +1', MILO_C, 'move woodhammer 1, move splash', 'Wood Hammer');
boosted('Wood Hammer -> Bold +1', MILO_B, 'move woodhammer 1, move splash', 'Wood Hammer');
boosted('Grassy Glide -> Calm +1', MILO_C, 'move grassyglide 1, move splash', 'Grassy Glide');
