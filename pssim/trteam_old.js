// Mega Blastoise / Torkoal / Indeedee-F / Farigiraf / Kingambit / Hatterene Trick Room team (screenshot).
// Accuracy audit, Trick Room speeds, own-priority vs Psychic Terrain, and headline damage. Champions data.
const T = require('./t1sim.js'); const {Battle, Dex} = require('pokemon-showdown'); const d = Dex.mod('champions');
const S = (species, item, ability, nature, evs, moves) => T.toSet({species, item, ability, nature, evs, moves: ['splash', ...moves]});
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
const TEAM = {
  Blastoise: S('Blastoise', 'blastoisinite', 'torrent', 'Quiet', [2, 0, 0, 32, 0, 32], ['fakeout', 'waterspout', 'aurasphere', 'darkpulse']),
  'Blastoise (0 Spe)': S('Blastoise', 'blastoisinite', 'torrent', 'Quiet', [32, 0, 0, 32, 2, 0], ['fakeout', 'waterspout', 'aurasphere', 'darkpulse']),
  Torkoal: S('Torkoal', 'charcoal', 'drought', 'Quiet', [32, 0, 0, 32, 2, 0], ['eruption', 'weatherball', 'earthpower', 'protect']),
  'Indeedee-F': S('Indeedee-F', 'mentalherb', 'psychicsurge', 'Relaxed', [32, 0, 32, 0, 2, 0], ['followme', 'helpinghand', 'trickroom', 'healingwish']),
  Farigiraf: S('Farigiraf', 'sitrusberry', 'armortail', 'Relaxed', [31, 0, 24, 0, 11, 0], ['trickroom', 'protect', 'psychic', 'thunderbolt']),
  Kingambit: S('Kingambit', 'chopleberry', 'defiant', 'Brave', [32, 32, 0, 0, 2, 0], ['ironhead', 'kowtowcleave', 'lowkick', 'suckerpunch']),
  Hatterene: S('Hatterene', 'lifeorb', 'magicbounce', 'Quiet', [32, 2, 0, 32, 0, 0], ['trickroom', 'protect', 'expandingforce', 'dazzlinggleam']),
};
const part = process.argv[2] || 'audit';
function battle(p1, p2, c1, c2, seed) {
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [seed, 4, 8, 15]}); b.debugMode = false;
  b.setPlayer('p1', {name: 'Me', team: [...p1, FILL, FILL].slice(0, 4)}); b.setPlayer('p2', {name: 'Them', team: [...p2, FILL, FILL].slice(0, 4)});
  b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
  if (!b.choose('p1', c1)) throw new Error('p1 ' + c1 + ' ' + b.sides[0].choice.error);
  if (!b.choose('p2', c2)) throw new Error('p2 ' + c2 + ' ' + b.sides[1].choice.error);
  return b;
}
const TGT = {
  Rillaboom: [S('Rillaboom', 'miracleseed', 'grassysurge', 'Adamant', [32, 32, 0, 0, 0, 2], ['woodhammer']), false],
  Sneasler: [S('Sneasler', 'grassyseed', 'unburden', 'Adamant', [2, 32, 0, 0, 0, 32], ['closecombat']), false],
  'Mega Salamence': [S('Salamence', 'salamencite', 'intimidate', 'Timid', [2, 0, 0, 32, 0, 32], ['hypervoice']), true],
  Incineroar: [S('Incineroar', 'sitrusberry', 'intimidate', 'Careful', [32, 0, 14, 0, 20, 0], ['flareblitz']), false],
  Kingambit: [S('Kingambit', 'chopleberry', 'defiant', 'Adamant', [32, 32, 0, 0, 2, 0], ['ironhead']), false],
  Basculegion: [S('Basculegion', 'lifeorb', 'adaptability', 'Adamant', [2, 32, 0, 0, 0, 32], ['wavecrash']), false],
  'Mega Floette': [S('Floette-Eternal', 'floettite', 'flowerveil', 'Modest', [2, 0, 0, 32, 0, 32], ['moonblast']), true],
  Farigiraf: [S('Farigiraf', 'sitrusberry', 'armortail', 'Bold', [27, 0, 20, 0, 19, 0], ['psychic']), false],
  Gholdengo: [S('Gholdengo', 'lifeorb', 'goodasgold', 'Timid', [2, 0, 0, 32, 0, 32], ['shadowball']), false],
  'Garchomp (LO)': [S('Garchomp', 'lifeorb', 'roughskin', 'Jolly', [2, 32, 0, 0, 0, 32], ['dragonclaw']), false],
  'Mega Tyranitar': [S('Tyranitar', 'tyranitarite', 'sandstream', 'Adamant', [25, 16, 0, 0, 0, 25], ['rockslide']), true],
  'Mega Gengar': [S('Gengar', 'gengarite', 'cursedbody', 'Modest', [2, 0, 0, 32, 0, 32], ['shadowball']), true],
};
function hpAfter(b, who, move, maxhp) {
  let inMove = false, hp = null, crit = false, blocked = false;
  for (const x of b.log) {
    if (x.startsWith('|move|')) inMove = x.startsWith(`|move|${who}|${move}|`);
    else if (!inMove) continue;
    else if (x.startsWith('|-crit|p2a')) crit = true;
    else if (x.startsWith('|-activate|p2a') && x.includes('Psychic Terrain')) blocked = true;
    else if (x.startsWith('|-damage|p2a') && !x.includes('[from]')) { const h = x.split('|')[3]; if (h.includes('fnt')) hp = 0; else if (+h.split('/')[1].split(' ')[0] === maxhp) hp = +h.split('/')[0]; }
  }
  return {hp, crit, blocked};
}
function calc(label, att, partner, c1, who, move, tname, N = 48) {
  const [tset, mega] = TGT[tname]; const c2 = `move splash${mega ? ' mega' : ''}, move splash`;
  const maxhp = battle([att, partner], [tset, FILL], c1, c2, 1).sides[1].active[0].maxhp;
  const dd = []; let ko = 0, n = 0;
  for (let s = 1; s <= N; s++) { const r = hpAfter(battle([att, partner], [tset, FILL], c1, c2, s), who, move, maxhp); if (r.hp === null || r.crit) continue; n++; if (r.hp === 0) ko++; dd.push(maxhp - r.hp); }
  if (!n) { console.log(`  ${label.padEnd(30)} -> ${tname.padEnd(15)} no damage`); return; }
  const pct = x => (100 * Math.min(x, maxhp) / maxhp).toFixed(0);
  console.log(`  ${label.padEnd(30)} -> ${tname.padEnd(15)} ${pct(Math.min(...dd)).padStart(3)}-${pct(Math.max(...dd)).padStart(3)}%  KO ${String(ko).padStart(2)}/${n}`);
}
if (part === 'audit') {
  console.log('Every move on the sheet (Champions data):');
  for (const [mon, set] of Object.entries(TEAM)) { if (mon.includes('(')) continue;
    console.log(`  ${mon.padEnd(11)} ` + set.moves.filter(m => m !== 'splash').map(m => { const x = d.moves.get(m); return `${x.name} ${x.accuracy === true ? 'never misses' : x.accuracy + '%'}${x.priority ? ` (prio ${x.priority > 0 ? '+' : ''}${x.priority})` : ''}${x.isNonstandard ? ' [' + x.isNonstandard + ']' : ''}`; }).join(' | ')); }
  for (const i of ['blastoisinite', 'charcoal', 'mentalherb', 'sitrusberry', 'chopleberry', 'lifeorb', 'rockyhelmet', 'colburberry', 'psychicseed', 'blackglasses'])
    { const x = d.items.get(i); process.stdout.write(`${x.name}${x.isNonstandard ? ' [' + x.isNonstandard + ']' : ''}; `); } console.log();
  const bm = d.species.get('Blastoise-Mega'); console.log('Blastoise-Mega', bm.types.join('/'), JSON.stringify(bm.baseStats), Object.values(bm.abilities).join(','), bm.isNonstandard || '');
  console.log('Speeds after Mega Evolution (Trick Room: lowest moves first):');
  const out = [];
  for (const [mon, set] of Object.entries(TEAM)) { const b = battle([set, FILL], [FILL, FILL], `move splash${mon.startsWith('Blastoise') ? ' mega' : ''}, move splash`, 'move splash, move splash', 1);
    const p = b.sides[0].active[0]; out.push([p.getStat('spe'), mon, p.maxhp, p.ability]); }
  for (const [spe, mon, hp, ab] of out.sort((a, b) => a[0] - b[0])) console.log(`  ${String(spe).padStart(3)}  ${mon} (HP ${hp}, ${ab})`);
  for (const [n, s] of [['Rillaboom 2 Spe', TGT.Rillaboom[0]], ['Incineroar 0 Spe', TGT.Incineroar[0]], ['Farigiraf (Bold) ', TGT.Farigiraf[0]], ['Kingambit 0 Spe Adamant', TGT.Kingambit[0]]]) {
    const b = battle([FILL], [s, FILL], 'move splash, move splash', 'move splash, move splash', 1); console.log(`  (opp) ${n}: ${b.sides[1].active[0].getStat('spe')}`); }
  console.log('Own priority under Indeedee-F\'s Psychic Terrain (lead Indeedee-F + Mega Blastoise / Kingambit):');
  for (const [lab, mine, c1, who, mv, tname, c2] of [
    ['Fake Out -> Incineroar (grounded)', [TEAM['Indeedee-F'], TEAM['Blastoise (0 Spe)']], 'move splash, move fakeout 1 mega', 'p1b: Blastoise', 'Fake Out', 'Incineroar', 'move splash, move splash'],
    ['Fake Out -> Mega Salamence (flying)', [TEAM['Indeedee-F'], TEAM['Blastoise (0 Spe)']], 'move splash, move fakeout 1 mega', 'p1b: Blastoise', 'Fake Out', 'Mega Salamence', 'move splash mega, move splash'],
    ['Sucker Punch -> attacking Incineroar', [TEAM['Indeedee-F'], TEAM.Kingambit], 'move splash, move suckerpunch 1', 'p1b: Kingambit', 'Sucker Punch', 'Incineroar', 'move flareblitz 1, move splash'],
    ['Sucker Punch, no terrain (control)', [TEAM.Farigiraf, TEAM.Kingambit], 'move splash, move suckerpunch 1', 'p1b: Kingambit', 'Sucker Punch', 'Incineroar', 'move flareblitz 1, move splash']]) {
    const [ts] = TGT[tname]; const b = battle(mine, [ts, FILL], c1, c2, 3);
    const blk = b.log.some(x => x.startsWith('|-activate|p2a') && x.includes('Psychic Terrain')); const hit = b.log.some((x, i) => x.startsWith(`|move|${who}|${mv}|`) && b.log.slice(i + 1, i + 6).some(y => y.startsWith('|-damage|p2a')));
    console.log(`  ${lab.padEnd(38)} ${blk ? 'BLOCKED by Psychic Terrain' : hit ? 'hits' : 'no damage (other)'}`);
  }
}
if (part === 'dmg') {
  const BL = TEAM['Blastoise (0 Spe)'];
  console.log('Mega Blastoise Water Spout, full HP, spread, no weather:');
  for (const t of ['Rillaboom', 'Sneasler', 'Mega Salamence', 'Incineroar', 'Kingambit', 'Basculegion', 'Mega Floette', 'Farigiraf', 'Gholdengo', 'Garchomp (LO)']) calc('Water Spout', BL, FILL, 'move waterspout mega, move splash', 'p1a: Blastoise', 'Water Spout', t);
  console.log('Same in Torkoal\'s sun:'); for (const t of ['Incineroar', 'Kingambit']) calc('Water Spout (sun)', BL, TEAM.Torkoal, 'move waterspout mega, move protect', 'p1a: Blastoise', 'Water Spout', t);
  console.log('Mega Launcher pulses (single target):');
  for (const t of ['Kingambit', 'Incineroar', 'Mega Tyranitar', 'Rillaboom']) calc('Aura Sphere', BL, FILL, 'move aurasphere 1 mega, move splash', 'p1a: Blastoise', 'Aura Sphere', t);
  for (const t of ['Farigiraf', 'Gholdengo', 'Mega Gengar', 'Sneasler']) calc('Dark Pulse', BL, FILL, 'move darkpulse 1 mega, move splash', 'p1a: Blastoise', 'Dark Pulse', t);
  console.log('Torkoal Eruption, full HP, spread, sun, Charcoal:');
  for (const t of ['Rillaboom', 'Sneasler', 'Mega Salamence', 'Incineroar', 'Kingambit', 'Basculegion', 'Mega Floette', 'Farigiraf', 'Gholdengo', 'Garchomp (LO)']) calc('Eruption (sun)', TEAM.Torkoal, FILL, 'move eruption, move splash', 'p1a: Torkoal', 'Eruption', t);
  console.log('Hatterene Expanding Force in Psychic Terrain (spread), Life Orb:');
  for (const t of ['Rillaboom', 'Sneasler', 'Mega Salamence', 'Incineroar', 'Basculegion', 'Mega Floette', 'Farigiraf', 'Garchomp (LO)']) calc('Expanding Force (terrain)', TEAM.Hatterene, TEAM['Indeedee-F'], 'move expandingforce 1, move splash', 'p1a: Hatterene', 'Expanding Force', t);
  console.log('Kingambit (Brave 32 Atk) single target:');
  for (const [mv, id, ts] of [['Kowtow Cleave', 'kowtowcleave', ['Farigiraf', 'Mega Gengar', 'Gholdengo']], ['Iron Head', 'ironhead', ['Mega Floette']], ['Low Kick', 'lowkick', ['Kingambit', 'Mega Tyranitar', 'Incineroar']]])
    for (const t of ts) calc(mv, TEAM.Kingambit, FILL, `move ${id} 1, move splash`, 'p1a: Kingambit', mv, t);
}
