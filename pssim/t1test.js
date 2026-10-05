const PS = require('pokemon-showdown');
const {Battle, Teams} = PS;
console.log(Object.keys(PS));
const MINE = [
  'Rillaboom||Miracle Seed|Grassy Surge|Fake Out,Grassy Glide,Wood Hammer,U-turn|Adamant|18,25,5,0,10,8||||50|',
  'Incineroar||Sitrus Berry|Intimidate|Fake Out,Throat Chop,Flare Blitz,Parting Shot|Careful|32,0,20,0,14,0||||50|',
  'Sneasler||Grassy Seed|Unburden|Close Combat,Dire Claw,Acrobatics,Protect|Adamant|14,20,0,0,0,32||||50|',
  'Gholdengo||Focus Sash|Good as Gold|Make It Rain,Shadow Ball,Power Gem,Protect|Modest|2,0,0,32,0,32||||50|',
  'Kingambit||Chople Berry|Defiant|Kowtow Cleave,Sucker Punch,Iron Head,Low Kick|Adamant|32,14,20,0,0,0||||50|',
  'Salamence||Salamencite|Intimidate|Hyper Voice,Double-Edge,Tailwind,Protect|Naive|1,21,0,15,0,29||||50|',
].join(']');
const THEM = [
  'Raichu||Raichunite Y|Lightning Rod|Fake Out,Zap Cannon,Focus Blast,Protect|Timid|2,0,0,32,0,32||||50|',
  'Gholdengo||Life Orb|Good as Gold|Make It Rain,Shadow Ball,Nasty Plot,Protect|Timid|2,0,0,32,0,32||||50|',
  'Rillaboom||Miracle Seed|Grassy Surge|Fake Out,Grassy Glide,Wood Hammer,High Horsepower|Adamant|32,32,0,0,2,0||||50|',
  'Salamence||Salamencite|Intimidate|Hyper Voice,Draco Meteor,Tailwind,Protect|Timid|2,0,0,32,0,32||||50|',
  'Arcanine-Hisui||Focus Sash|Rock Head|Flare Blitz,Head Smash,Extreme Speed,Protect|Jolly|2,32,0,0,0,32||||50|',
  'Sneasler||Grassy Seed|Unburden|Close Combat,Dire Claw,Fake Out,Protect|Adamant|2,32,0,0,0,32||||50|',
].join(']');
function run(seed, p1team, p2team, lead1, lead2, c1, c2, verbose) {
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed});
  b.setPlayer('p1', {name: 'Me', team: p1team});
  b.setPlayer('p2', {name: 'Them', team: p2team});
  b.choose('p1', 'team ' + lead1); b.choose('p2', 'team ' + lead2);
  b.choose('p1', c1); b.choose('p2', c2);
  if (verbose) console.log(b.log.filter(l => !/^\|(t:|j|c|gametype|player|gen|tier|rule|clearpoke|poke|teampreview|teamsize|seed|timestamp)\b|^\|$/.test(l)).join('\n'));
  return b;
}
const t0 = Date.now();
const b = run([1, 2, 3, 4], MINE, THEM, '5623', '1234', 'move 1 2 mega, move 3 2', 'move 1 1 mega, move 3', true);
for (const s of b.sides) for (const p of s.active) console.log(s.id, p.species.name, p.hp + '/' + p.maxhp, JSON.stringify(p.boosts), p.status, p.storedStats);
console.log('field', Object.keys(b.field.pseudoWeather), b.field.weather, b.field.terrain, b.sides.map(s => Object.keys(s.sideConditions)));
let n = 0; const t1 = Date.now(); for (let i = 0; i < 200; i++) { run([i, 7, 9, 11], MINE, THEM, '5623', '1234', 'move 1 2 mega, move 3 2', 'move 1 1 mega, move 3'); n++; }
console.log('ms per battle', (Date.now() - t1) / n);
