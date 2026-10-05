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

function test2(label, p1, p2, c1, c2, who, move, tgtName, maxhp, N = 80) {
  const nc = [], cr = []; let ko = 0, n = 0;
  for (let s = 1; s <= N; s++) { const b = battle(p1, p2, c1, c2, s); const r = hpAfter(b, who, move, tgtName, maxhp); if (r.hp === null) continue;
    n++; const now = r.hp.includes('fnt') ? 0 : +r.hp.split('/')[0]; if (now === 0) ko++; (r.crit ? cr : nc).push(maxhp - now); }
  const f = a => a.length ? `${Math.min(...a)}-${Math.max(...a)} (${(100 * Math.min(...a) / maxhp).toFixed(0)}-${(100 * Math.max(...a) / maxhp).toFixed(0)}%)` : '-';
  console.log(`  ${label.padEnd(44)} no crit ${f(nc).padEnd(22)} crit ${f(cr).padEnd(22)} KO ${ko}/${n}`);
}
const HP = {Salamence: 171, Kingambit: 207, Incineroar: 202, Gholdengo: 164, Rillaboom: 193, Sneasler: 169};
const APE = (nature = 'Adamant') => T.toSet({species: 'Annihilape', item: 'choicescarf', ability: 'defiant', moves: ['closecombat', 'icepunch', 'rocktomb', 'shadowclaw'], nature, evs: [2, 32, 0, 0, 0, 32]});
const SIR = T.toSet({species: "Sirfetch'd", item: 'leek', ability: 'scrappy', moves: ['meteorassault', 'closecombat', 'feint', 'detect'], nature: 'Adamant', evs: [32, 32, 0, 0, 2, 0]});
const idle = t => ({Salamence: 'move tailwind mega', Kingambit: 'move ironhead 2', Incineroar: 'move flareblitz 2', Gholdengo: 'move powergem 2', Rillaboom: 'move grassyglide 2', Sneasler: 'move direclaw 2'}[t] + ', move splash');
if (0) { const b = battle([my('Salamence')], [APE('Adamant')], 'move tailwind mega, move splash', 'move icepunch 1, move splash', 1);
  const b2 = battle([my('Salamence')], [APE('Jolly')], 'move tailwind mega, move splash', 'move icepunch 1, move splash', 1);
  const b3 = battle([my('Salamence')], [SIR], 'move tailwind mega, move splash', 'move detect, move splash', 1);
  console.log('Speed: Scarf Annihilape Adamant', b.sides[1].active[0].getStat('spe'), '| Jolly', b2.sides[1].active[0].getStat('spe'), "| Sirfetch'd Adamant", b3.sides[1].active[0].getStat('spe'), '| your Mega Salamence 185');
  console.log('Turn order log:', b.log.filter(x => x.startsWith('|move|')).join(' || '));
}
if (0) {
console.log('\nScarf Annihilape (Defiant, Adamant) attacking:');
test2('Ice Punch -> Mega Salamence, no Intimidate', [NOINT(my('Salamence')), FILL], [APE(), FILL], idle('Salamence'), 'move icepunch 1, move splash', 'p2a: Annihilape', 'Ice Punch', 'Salamence', 171);
test2('Ice Punch -> Mega Salamence, after Intimidate', [my('Salamence'), FILL], [APE(), FILL], idle('Salamence'), 'move icepunch 1, move splash', 'p2a: Annihilape', 'Ice Punch', 'Salamence', 171);
test2('Rock Tomb -> Mega Salamence, no Intimidate', [NOINT(my('Salamence')), FILL], [APE(), FILL], idle('Salamence'), 'move rocktomb 1, move splash', 'p2a: Annihilape', 'Rock Tomb', 'Salamence', 171);
for (const t of ['Kingambit', 'Incineroar', 'Rillaboom', 'Sneasler']) test2(`Close Combat -> ${t}`, [NOINT(my(t)), FILL], [APE(), FILL], idle(t), 'move closecombat 1, move splash', 'p2a: Annihilape', 'Close Combat', t, HP[t]);
test2('Shadow Claw -> Gholdengo', [my('Gholdengo'), FILL], [APE(), FILL], idle('Gholdengo'), 'move shadowclaw 1, move splash', 'p2a: Annihilape', 'Shadow Claw', 'Gholdengo', 164);
const AHP = (() => { const b = battle([FILL], [APE()], 'move splash, move splash', 'move icepunch 1, move splash', 1); return b.sides[1].active[0].maxhp; })();
console.log(`\nYour hits into Annihilape (${AHP} HP, 0 bulk investment):`);
for (const [att, c1, mv] of [['Gholdengo', 'move shadowball 1, move splash', 'Shadow Ball'], ['Salamence', 'move doubleedge 1 mega, move splash', 'Double-Edge'], ['Salamence', 'move hypervoice mega, move splash', 'Hyper Voice'],
  ['Kingambit', 'move kowtowcleave 1, move splash', 'Kowtow Cleave'], ['Kingambit', 'move suckerpunch 1, move splash', 'Sucker Punch'], ['Rillaboom', 'move woodhammer 1, move splash', 'Wood Hammer'], ['Sneasler', 'move acrobatics 1, move splash', 'Acrobatics'], ['Incineroar', 'move flareblitz 1, move splash', 'Flare Blitz']])
  test2(`${att} ${mv}`, [NOINT(my(att)), FILL], [APE(), FILL], c1, 'move icepunch 2, move splash', `p1a: ${att}`, mv, 'Annihilape', AHP);
}
console.log("\nSirfetch'd (Scrappy, Leek = 1 in 2 crits, Adamant 32 Atk) attacking:");
for (const t of ['Rillaboom']) {
  test2(`Meteor Assault -> ${t}`, [NOINT(my(t)), FILL], [SIR, FILL], idle(t), 'move meteorassault 1, move splash', "p2a: Sirfetch’d", 'Meteor Assault', t, HP[t]);
}
test2('Close Combat -> Rillaboom', [NOINT(my('Rillaboom')), FILL], [SIR, FILL], idle('Rillaboom'), 'move closecombat 1, move splash', "p2a: Sirfetch’d", 'Close Combat', 'Rillaboom', 193);
if (0) {
const SHP = (() => { const b = battle([FILL], [SIR], 'move splash, move splash', 'move detect, move splash', 1); return b.sides[1].active[0].maxhp; })();
console.log(`\nYour hits into Sirfetch'd (${SHP} HP, 32 HP investment):`);
for (const [att, c1, mv] of [['Salamence', 'move doubleedge 1 mega, move splash', 'Double-Edge'], ['Salamence', 'move hypervoice mega, move splash', 'Hyper Voice'], ['Gholdengo', 'move makeitrain, move splash', 'Make It Rain'],
  ['Gholdengo', 'move shadowball 1, move splash', 'Shadow Ball'], ['Sneasler', 'move acrobatics 1, move splash', 'Acrobatics'], ['Rillaboom', 'move woodhammer 1, move splash', 'Wood Hammer'], ['Kingambit', 'move ironhead 1, move splash', 'Iron Head'], ['Incineroar', 'move flareblitz 1, move splash', 'Flare Blitz']])
  test2(`${att} ${mv}`, [NOINT(my(att)), FILL], [SIR, FILL], c1, 'move feint 2, move splash', `p1a: ${att}`, mv, "Sirfetch’d", SHP);

}