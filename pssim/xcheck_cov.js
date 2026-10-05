// Cross-check three Coverage numbers in Showdown's engine (Champions mod): damage range and KO share over 96 seeds, no crits.
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown'); const mix = require('./seedmix.js');
const MY = JSON.parse(require('fs').readFileSync('myteam_tr.json')); const my = n => T.toSet(MY[n]);
const S = (species, item, ability, nature, evs) => T.toSet({species, item, ability, nature, evs, moves: ['splash', 'protect']});
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
function run(att, cmd, tgt, mega, N = 96) {
  const d = []; let ko = 0, n = 0, maxhp = 0;
  for (let s = 1; s <= N; s++) {
    const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: mix(s + 900)}); b.debugMode = false;
    b.setPlayer('p1', {name: 'Me', team: [my(att), FILL, FILL, FILL]}); b.setPlayer('p2', {name: 'Them', team: [tgt, FILL, FILL, FILL]});
    b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234');
    b.choose('p1', cmd); b.choose('p2', `move splash${mega ? ' mega' : ''}, move splash`);
    const t = b.sides[1].active[0]; maxhp = t.maxhp; if (b.log.some(x => x.startsWith('|-crit|p2a'))) continue;
    const L = b.log.filter(x => x.startsWith('|-damage|p2a') && !x.includes('[from]'));
    if (!L.length) continue; const h = L[0].split('|')[3]; const hp = h.includes('fnt') ? 0 : +h.split('/')[0]; n++; if (hp === 0) ko++; d.push(maxhp - hp);
  }
  const pct = x => (100 * x / maxhp).toFixed(1);
  return `${pct(Math.min(...d))}-${pct(Math.max(...d))}% (capped at 100) KO ${ko}/${n}`;
}
console.log('Mega Blastoise Aura Sphere -> Archaludon (Modest 32/20/14, Leftovers):', run('Blastoise', 'move aurasphere 1 mega, move splash', S('Archaludon', 'leftovers', 'stamina', 'Modest', [32, 0, 20, 0, 14, 0]), false), '| calc: max 112.7%, KO 11/16');
console.log('Hatterene Dazzling Gleam (spread) -> Mega Salamence (Timid 2/0/0/32/0/32):', run('Hatterene', 'move dazzlinggleam, move splash', S('Salamence', 'salamencite', 'intimidate', 'Timid', [2, 0, 0, 32, 0, 32]), true), '| calc: max 114%, KO 13/16');
console.log('Torkoal Eruption (spread, own sun) -> Rillaboom (Adamant 32/32/../2 Spe):', run('Torkoal', 'move eruption, move splash', S('Rillaboom', 'miracleseed', 'grassysurge', 'Adamant', [32, 32, 0, 0, 0, 2]), false), '| calc: max 209%, KO 16/16');
