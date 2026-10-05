// Full-HP Torkoal Eruption in its own sun with Indeedee's Helping Hand, in Showdown's engine (Champions mod): damage to each target set.
// Spread (both foes out) and single target (their partner already gone). No crits counted.
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown'); const mix = require('./seedmix.js'); const fs = require('fs');
const MY = JSON.parse(fs.readFileSync('myteam_tr.json')); const my = n => T.toSet(MY[n]);
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
const TG = JSON.parse(fs.readFileSync('hh_targets.json')); const N = +(process.argv[2] || 32);
const out = [];
for (const tg of TG) {
  const set = T.toSet({species: tg.species, item: tg.item, ability: tg.ability, nature: tg.nature, evs: tg.evs, moves: ['splash', 'protect']});
  for (const mode of ['spread']) {
    const d = []; let ko = 0, n = 0, maxhp = 0, sash = 0;
    for (let s = 1; s <= N; s++) {
      const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: mix(s + 3100)}); b.debugMode = false;
      b.setPlayer('p1', {name: 'Me', team: [my('Torkoal'), my('Indeedee-F'), FILL, FILL]});
      b.setPlayer('p2', {name: 'Them', team: mode === 'spread' ? [set, FILL, FILL, FILL] : [set]});
      b.choose('p1', 'team 1234'); b.choose('p2', mode === 'spread' ? 'team 1234' : 'team 1');
      b.choose('p1', 'move eruption, move helpinghand -1');
      b.choose('p2', mode === 'spread' ? `move splash${tg.mega ? ' mega' : ''}, move splash` : `move splash${tg.mega ? ' mega' : ''}`);
      const t = b.sides[1].active[0]; maxhp = t.maxhp;
      if (b.log.some(x => x.startsWith('|-crit|p2a'))) continue;
      if (b.log.some(x => x.startsWith('|-immune|p2a'))) { d.push(0); n++; continue; }
      const L = b.log.filter(x => x.startsWith('|-damage|p2a') && !x.includes('[from]'));
      if (!L.length) continue;
      const h = L[0].split('|')[3]; const hp = h.includes('fnt') ? 0 : +h.split('/')[0]; n++;
      if (hp === 0) ko++; if (hp === 1 && b.log.some(x => x.includes('Focus Sash'))) sash++;
      d.push(maxhp - hp);
    }
    const pct = x => +(100 * x / maxhp).toFixed(1);
    out.push({key: tg.key, i: tg.i, mode, lo: pct(Math.min(...d)), hi: pct(Math.max(...d)), ko: ko / n, sash: sash / n, n, weather: null});
  }
}
fs.writeFileSync('hh_eruption.json', JSON.stringify(out)); console.log('done', out.length);
