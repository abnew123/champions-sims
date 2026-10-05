// Non-Mega Tyranitar vs full-HP Helping Hand Eruption in Torkoal's sun (spread: both foes out), three spreads.
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown'); const mix = require('./seedmix.js'); const fs = require('fs');
const MY = JSON.parse(fs.readFileSync('myteam_tr.json')); const my = n => T.toSet(MY[n]);
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
for (const [nat, evs, item] of [['Careful', [32, 0, 0, 0, 32, 2], 'Leftovers'], ['Adamant', [32, 32, 0, 0, 2, 0], 'Leftovers'], ['Adamant', [2, 32, 0, 0, 0, 32], 'Focus Sash']]) {
  const set = T.toSet({species: 'Tyranitar', item, ability: 'Sand Stream', nature: nat, evs, moves: ['splash', 'protect']});
  const d = []; let ko = 0, n = 0, maxhp = 0, weather = '';
  for (let s = 1; s <= 32; s++) {
    const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: mix(s + 5200)}); b.debugMode = false;
    b.setPlayer('p1', {name: 'Me', team: [my('Torkoal'), my('Indeedee-F'), FILL, FILL]}); b.setPlayer('p2', {name: 'Them', team: [set, FILL, FILL, FILL]});
    b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234'); b.choose('p1', 'move eruption, move helpinghand -1'); b.choose('p2', 'move splash, move splash');
    weather = b.field.weather; const t = b.sides[1].active[0]; maxhp = t.maxhp;
    if (b.log.some(x => x.startsWith('|-crit|p2a'))) continue;
    const L = b.log.filter(x => x.startsWith('|-damage|p2a') && !x.includes('[from]')); if (!L.length) continue;
    const h = L[0].split('|')[3]; const hp = h.includes('fnt') ? 0 : +h.split('/')[0]; n++; if (hp === 0) ko++; d.push(maxhp - hp);
  }
  const pct = x => (100 * x / maxhp).toFixed(0);
  console.log(`${nat} ${evs.join('/')} ${item}: HP ${maxhp}, spread ${pct(Math.min(...d))}-${pct(Math.max(...d))}%, KO ${ko}/${n}, weather after: ${weather}`);
}
