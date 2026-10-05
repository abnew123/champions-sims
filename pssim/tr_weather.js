// Water Spout (Mega Blastoise) and Eruption (Torkoal) from full HP, spread, in no weather / rain / sun, into common targets.
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown'); const mix = require('./seedmix.js');
const MY = JSON.parse(require('fs').readFileSync('myteam_tr.json')); const my = n => T.toSet(MY[n]);
const S = (species, item, ability, nature, evs) => T.toSet({species, item, ability, nature, evs, moves: ['splash', 'protect']});
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
const TGT = {
  Incineroar: S('Incineroar', 'sitrusberry', 'intimidate', 'Careful', [32, 0, 14, 0, 20, 0]), Kingambit: S('Kingambit', 'chopleberry', 'defiant', 'Adamant', [32, 32, 0, 0, 2, 0]),
  Sneasler: S('Sneasler', 'whiteherb', 'unburden', 'Adamant', [2, 32, 0, 0, 0, 32]), Rillaboom: S('Rillaboom', 'miracleseed', 'overgrow', 'Adamant', [32, 32, 0, 0, 0, 2]),
  'Mega Salamence': S('Salamence', 'salamencite', 'intimidate', 'Timid', [2, 0, 0, 32, 0, 32]), Gholdengo: S('Gholdengo', 'lifeorb', 'goodasgold', 'Timid', [2, 0, 0, 32, 0, 32]),
  Archaludon: S('Archaludon', 'leftovers', 'stamina', 'Modest', [32, 0, 20, 0, 14, 0]), Pelipper: S('Pelipper', 'focussash', 'keeneye', 'Modest', [32, 0, 20, 0, 14, 0]),
};
const MEGA = {'Mega Salamence': true};
function run(att, move, tname, weather, N = 40) {
  const d = []; let ko = 0, n = 0, maxhp = 0;
  for (let s = 1; s <= N; s++) {
    const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: mix(s + 700)}); b.debugMode = false;
    const a = my(att); if (att === 'Torkoal') a.ability = 'whitesmoke';            // no Drought: weather is set by hand below
    b.setPlayer('p1', {name: 'Me', team: [a, FILL, FILL, FILL]}); b.setPlayer('p2', {name: 'Them', team: [TGT[tname], FILL, FILL, FILL]});
    b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
    if (weather) b.field.setWeather(weather, b.sides[1].active[1]);
    b.choose('p1', `move ${move}${att === 'Blastoise' ? ' mega' : ''}, move splash`); b.choose('p2', `move splash${MEGA[tname] ? ' mega' : ''}, move splash`);
    const t = b.sides[1].active[0]; maxhp = t.maxhp; if (b.log.some(x => x.startsWith('|-crit|p2a'))) continue;
    const L = b.log.filter(x => x.startsWith('|-damage|p2a') && !x.includes('[from]') && (x.split('|')[3].includes('/' + maxhp) || x.split('|')[3].includes('fnt')));
    if (!L.length) continue; const h = L[0].split('|')[3]; const hp = h.includes('fnt') ? 0 : +h.split('/')[0]; n++; if (hp === 0) ko++; d.push(maxhp - hp);
  }
  const pct = x => Math.round(100 * Math.min(x, maxhp) / maxhp);
  return n ? `${pct(Math.min(...d))}-${pct(Math.max(...d))}%${ko ? ` KO ${Math.round(100 * ko / n)}%` : ''}` : 'n/a';
}
const out = {};
for (const [att, move] of [['Blastoise', 'waterspout'], ['Torkoal', 'eruption']]) {
  console.log(`${att} ${move} (spread, full HP):`.padEnd(40), 'none'.padEnd(18), 'rain'.padEnd(18), 'sun');
  for (const t of ['Incineroar', 'Kingambit', 'Sneasler', 'Rillaboom', 'Mega Salamence', 'Gholdengo', 'Archaludon', 'Pelipper']) {
    const r = [run(att, move, t, ''), run(att, move, t, 'raindance'), run(att, move, t, 'sunnyday')]; out[`${att}|${t}`] = r;
    console.log('   ' + t.padEnd(36), r[0].padEnd(18), r[1].padEnd(18), r[2]);
  }
}
require('fs').writeFileSync('tr_weather.json', JSON.stringify(out));
