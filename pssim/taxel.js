// Mega Lopunny Triple Axel into Mega Salamence: KO rate with well-mixed seeds, conditional and unconditional.
const T = require('./t1sim.js'); const {Battle} = require('pokemon-showdown'); const mix = require('./seedmix.js');
const my = n => T.toSet(T.MY[n]);
const LOP = T.toSet({species: 'Lopunny', item: 'lopunnite', ability: 'limber', moves: ['closecombat', 'fakeout', 'protect', 'tripleaxel'], nature: 'Jolly', evs: [2, 32, 0, 0, 0, 32]});
const FILL = T.toSet({species: 'Blissey', item: '', ability: 'naturalcure', moves: ['splash'], nature: 'Bold', evs: [0, 0, 0, 0, 0, 0]});
const NOINT = s => Object.assign({}, s, {ability: 'moxie'});
for (const [label, sal] of [['no Intimidate', NOINT(my('Salamence'))], ['after Intimidate (-1)', my('Salamence')]]) {
  let n = 0, ko = 0, firstMiss = 0, crit = 0, koNoCrit = 0, nNoCrit = 0; const N = 800;
  for (let s = 1; s <= N; s++) {
    const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed: mix(s + 5000)}); b.debugMode = false;
    b.setPlayer('p1', {name: 'Me', team: [sal, FILL, FILL, FILL]}); b.setPlayer('p2', {name: 'Them', team: [LOP, FILL, FILL, FILL]});
    b.choose('p1', 'team 1234'); b.choose('p2', 'team 1234'); b.choose('p1', 'move tailwind mega, move splash'); b.choose('p2', 'move tripleaxel 1 mega, move splash');
    const L = b.log; const i = L.findIndex(x => x.startsWith('|move|p2a: Lopunny|Triple Axel')); const blk = L.slice(i, L.findIndex((x, k) => k > i && x.startsWith('|move|')) >>> 0);
    const died = b.sides[0].active[0].fainted || b.sides[0].active[0].hp === 0; const c = blk.some(x => x.startsWith('|-crit|p1a'));
    n++; if (died) ko++; if (blk.some(x => x.startsWith('|-miss|')) && !blk.some(x => x.startsWith('|-damage|p1a'))) firstMiss++;
    if (c) crit++; else { nNoCrit++; if (died) koNoCrit++; }
  }
  console.log(`${label.padEnd(22)} KO overall ${(100 * ko / n).toFixed(1)}%  | no-crit KO ${(100 * koNoCrit / nNoCrit).toFixed(1)}%  | first hit missed ${(100 * firstMiss / n).toFixed(1)}%  crit seen ${(100 * crit / n).toFixed(1)}%  (N=${n})`);
}
