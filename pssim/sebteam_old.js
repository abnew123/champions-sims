// The Frankfurt regional's second-place sun + Trick Room team: does Dragon Pulse (over Draco Meteor) on Mega Garchomp Z
// and Quick Attack (over Yawn) on Sylveon hold up? Turn-one damage in Showdown's engine with the Champions data.
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown');
const S = (species, item, ability, nature, evs, moves) => T.toSet({species, item, ability, nature, evs, moves: ['splash', ...moves]});
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
const TORK = T.toSet({species: 'Torkoal', item: 'charcoal', ability: 'drought', moves: ['splash', 'protect'], nature: 'Quiet', evs: [32, 0, 0, 32, 2, 0]});
// Seb's sets (Garchomp's "32 Atk" read as 32 HP: it has no physical moves, and HP does not change its damage)
const CHOMP = S('Garchomp', 'garchompitez', 'roughskin', 'Modest', [32, 0, 0, 32, 0, 2], ['dracometeor', 'dragonpulse', 'flamethrower', 'powergem']);
const SYLV = (item = 'fairyfeather') => S('Sylveon', item, 'pixilate', 'Modest', [9, 0, 22, 20, 0, 15], ['quickattack', 'hypervoice', 'hyperbeam', 'yawn']);
const SNEAS = S('Sneasler', 'whiteherb', 'unburden', 'Adamant', [0, 32, 2, 0, 0, 32], ['gunkshot', 'poisonjab', 'direclaw', 'closecombat']);
// common opposing sets (modal items / natures / spreads from the ladder + tournament data used for the lead sheet)
const TGT = {
  'Mega Salamence': [S('Salamence', 'salamencite', 'intimidate', 'Timid', [2, 0, 0, 32, 0, 32], []), true],
  'Garchomp (Life Orb)': [S('Garchomp', 'lifeorb', 'roughskin', 'Jolly', [2, 32, 0, 0, 0, 32], []), false],
  'Mega Garchomp Z': [S('Garchomp', 'garchompitez', 'roughskin', 'Modest', [2, 0, 0, 32, 0, 32], []), true],
  'Mega Baxcalibur': [S('Baxcalibur', 'baxcalibrite', 'thermalexchange', 'Adamant', [2, 32, 0, 0, 0, 32], []), true],
  'Mega Dragonite': [S('Dragonite', 'dragoninite', 'multiscale', 'Modest', [2, 0, 0, 32, 0, 32], []), true],
  'Archaludon': [S('Archaludon', 'leftovers', 'stamina', 'Modest', [32, 0, 20, 0, 14, 0], []), false],
  'Basculegion': [S('Basculegion', 'lifeorb', 'adaptability', 'Adamant', [2, 32, 0, 0, 0, 32], []), false],
  'Milotic': [S('Milotic', 'leftovers', 'competitive', 'Bold', [32, 0, 32, 0, 2, 0], []), false],
  'Incineroar': [S('Incineroar', 'sitrusberry', 'intimidate', 'Careful', [32, 0, 14, 0, 20, 0], []), false],
  'Rillaboom': [S('Rillaboom', 'miracleseed', 'grassysurge', 'Adamant', [32, 32, 0, 0, 0, 2], []), false],
  'Sneasler': [S('Sneasler', 'grassyseed', 'unburden', 'Adamant', [2, 32, 0, 0, 0, 32], []), false],
  'Farigiraf': [S('Farigiraf', 'sitrusberry', 'armortail', 'Bold', [27, 0, 20, 0, 19, 0], []), false],
  'Mega Lopunny': [S('Lopunny', 'lopunnite', 'limber', 'Jolly', [2, 32, 0, 0, 0, 32], []), true],
  'Annihilape': [S('Annihilape', 'choicescarf', 'defiant', 'Adamant', [2, 32, 0, 0, 0, 32], []), false],
  "Sirfetch’d": [S("Sirfetch’d", 'leek', 'scrappy', 'Adamant', [2, 32, 0, 0, 0, 32], []), false],
  'Kingambit': [S('Kingambit', 'chopleberry', 'defiant', 'Adamant', [32, 32, 0, 0, 2, 0], []), false],
  'Mega Tyranitar': [S('Tyranitar', 'tyranitarite', 'sandstream', 'Adamant', [25, 16, 0, 0, 0, 25], []), true],
  'Mega Floette': [S('Floette-Eternal', 'floettite', 'flowerveil', 'Modest', [2, 0, 0, 32, 0, 32], []), true],
  'Sylveon': [S('Sylveon', 'fairyfeather', 'pixilate', 'Modest', [32, 0, 32, 0, 2, 0], []), false],
  'Whimsicott (no Sash)': [S('Whimsicott', 'lightclay', 'prankster', 'Timid', [2, 0, 0, 32, 0, 32], []), false],
};
const noInt = s => Object.assign({}, s, {ability: s.species === 'Salamence' ? 'moxie' : s.species === 'Incineroar' ? 'blaze' : s.ability});
function battle(p1, p2, c1, c2, seed) {
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed, 3, 7, 19]}); b.debugMode = false;
  b.setPlayer('p1', {name: 'Me', team: [...p1, FILL, FILL].slice(0, 4)}); b.setPlayer('p2', {name: 'Them', team: [...p2, FILL, FILL].slice(0, 4)});
  b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
  if (!b.choose('p1', c1)) throw new Error('p1 ' + c1 + ' ' + b.sides[0].choice.error);
  if (!b.choose('p2', c2)) throw new Error('p2 ' + c2 + ' ' + b.sides[1].choice.error);
  return b;
}
function result(b, who, move, maxhp) {  // exact HP of p2a after `who` used `move`; null if it missed / did nothing
  let inMove = false, hp = null, crit = false, miss = false;
  for (const x of b.log) {
    if (x.startsWith('|move|')) { inMove = x.startsWith(`|move|${who}|${move}|`); if (inMove && x.includes('[miss]')) miss = true; }
    else if (!inMove) continue;
    else if (x.startsWith('|-miss|')) miss = true;
    else if (x.startsWith('|-crit|') && x.includes('p2a')) crit = true;
    else if (x.startsWith('|-damage|p2a') && !x.includes('[from]')) { const h = x.split('|')[3]; if (h.includes('fnt')) hp = 0; else if (+h.split('/')[1].split(' ')[0] === maxhp) hp = +h.split('/')[0]; }
  }
  return {hp, crit, miss};
}
function calc(label, att, partner, c1, who, move, tname, opts = {}) {
  let [tset, mega] = TGT[tname]; if (opts.noInt) tset = noInt(tset);
  const c2 = `move splash${mega ? ' mega' : ''}, move splash`;
  const maxhp = battle([att, partner], [tset, FILL], c1, c2, 1).sides[1].active[0].maxhp;
  const d = []; let ko = 0, miss = 0, n = 0, N = opts.N || 64;
  for (let s = 1; s <= N; s++) { const r = result(battle([att, partner], [tset, FILL], c1, c2, s), who, move, maxhp);
    if (r.miss) { miss++; continue; } if (r.hp === null || r.crit) continue; n++; if (r.hp === 0) ko++; d.push(maxhp - r.hp); }
  const lo = Math.min(...d), hi = Math.max(...d); const pct = x => (100 * x / maxhp).toFixed(0);
  const row = {label, tname, lo: +pct(lo), hi: +pct(Math.min(hi, maxhp)), ko: ko / n, miss: miss / N};
  console.log(`  ${label.padEnd(26)} -> ${tname.padEnd(20)} ${pct(lo).padStart(3)}-${pct(Math.min(hi, maxhp)).padStart(3)}%  KO ${String(ko).padStart(2)}/${n}${miss ? `  (missed ${miss}/${N})` : ''}`);
  return row;
}
const out = {};
const part = process.argv[2] || 'all';
if (part === 'all' || part === 'chomp') {
  console.log('Mega Garchomp Z (Modest, 32 SpA), partner idle, no weather:');
  out.chomp = [];
  for (const t of ['Mega Salamence', 'Garchomp (Life Orb)', 'Mega Garchomp Z', 'Mega Baxcalibur', 'Mega Dragonite', 'Archaludon', 'Basculegion', 'Milotic', 'Incineroar', 'Rillaboom', 'Sneasler', 'Farigiraf'])
    for (const [mv, id] of [['Draco Meteor', 'dracometeor'], ['Dragon Pulse', 'dragonpulse']]) out.chomp.push(calc(mv, CHOMP, FILL, `move ${id} 1 mega, move splash`, 'p1a: Garchomp', mv, t));
  console.log('Flamethrower with Torkoal\'s sun up (for scale on neutral targets):');
  for (const t of ['Incineroar', 'Rillaboom', 'Sneasler', 'Farigiraf', 'Basculegion']) out.chomp.push(calc('Flamethrower (sun)', CHOMP, TORK, 'move flamethrower 1 mega, move splash', 'p1a: Garchomp', 'Flamethrower', t));
  const b = battle([CHOMP, FILL], [FILL, FILL], 'move splash mega, move splash', 'move splash, move splash', 1); const g = b.sides[0].active[0];
  console.log('  Mega Garchomp Z stats', JSON.stringify(g.storedStats), 'ability', g.ability);
}
if (part === 'all' || part === 'sylv') {
  console.log('Sylveon Quick Attack (Modest, 0 Atk, Fairy Feather, Pixilate):');
  out.sylv = [];
  for (const t of ['Mega Salamence', 'Garchomp (Life Orb)', 'Mega Garchomp Z', 'Mega Baxcalibur', 'Mega Dragonite', 'Mega Lopunny', 'Annihilape', "Sirfetch’d", 'Sneasler', 'Kingambit', 'Mega Tyranitar', 'Rillaboom', 'Incineroar', 'Basculegion'])
    out.sylv.push(calc('Quick Attack', SYLV(), FILL, 'move quickattack 1, move splash', 'p1a: Sylveon', 'Quick Attack', t, {noInt: true}));
  console.log('  ...after an Intimidate (lead Salamence / Incineroar):');
  for (const t of ['Mega Salamence', 'Incineroar']) out.sylv.push(calc('Quick Attack (-1)', SYLV(), FILL, 'move quickattack 1, move splash', 'p1a: Sylveon', 'Quick Attack', t));
  console.log('  Hyper Voice for scale (spread, one target shown):');
  for (const t of ['Mega Salamence', 'Garchomp (Life Orb)', 'Mega Lopunny', 'Rillaboom', 'Incineroar']) out.sylv.push(calc('Hyper Voice', SYLV(), FILL, 'move hypervoice, move splash', 'p1a: Sylveon', 'Hyper Voice', t, {noInt: true}));
  const b = battle([SYLV(), FILL], [FILL, FILL], 'move splash, move splash', 'move splash, move splash', 1); const s = b.sides[0].active[0];
  console.log('  Sylveon stats', JSON.stringify(s.storedStats));
}
if (part === 'all' || part === 'sneas') {
  console.log('Sneasler (Adamant, 32 Atk) poison options into Fairies:');
  out.sneas = [];
  for (const t of ['Mega Floette', 'Sylveon', 'Whimsicott (no Sash)'])
    for (const [mv, id] of [['Gunk Shot', 'gunkshot'], ['Poison Jab', 'poisonjab'], ['Dire Claw', 'direclaw']]) out.sneas.push(calc(mv, SNEAS, FILL, `move ${id} 1, move splash`, 'p1a: Sneasler', mv, t));
}
require('fs').writeFileSync(__dirname + `/sebteam_${part}.json`, JSON.stringify(out));
