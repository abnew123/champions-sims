const {Battle} = require('pokemon-showdown');
const SET = {
  Rillaboom: 'Rillaboom||Miracle Seed|Grassy Surge|Fake Out,Grassy Glide,Wood Hammer,U-turn|Adamant|18,25,5,0,10,8||||50|',
  Incineroar: 'Incineroar||Sitrus Berry|Intimidate|Fake Out,Throat Chop,Flare Blitz,Parting Shot|Careful|32,0,20,0,14,0||||50|',
  Sneasler: 'Sneasler||Grassy Seed|Unburden|Close Combat,Dire Claw,Acrobatics,Protect|Adamant|14,20,0,0,0,32||||50|',
  Gholdengo: 'Gholdengo||Focus Sash|Good as Gold|Make It Rain,Shadow Ball,Power Gem,Protect|Modest|2,0,0,32,0,32||||50|',
  Kingambit: 'Kingambit||Chople Berry|Defiant|Kowtow Cleave,Sucker Punch,Iron Head,Low Kick|Adamant|32,14,20,0,0,0||||50|',
  Salamence: 'Salamence||Salamencite|Intimidate|Hyper Voice,Double-Edge,Tailwind,Protect|Naive|1,21,0,15,0,29||||50|',
};
const T = {
  Raichu: 'Raichu||Raichunite Y|Lightning Rod|Fake Out,Zap Cannon,Focus Blast,Protect|Timid|2,0,0,32,0,32||||50|',
  Gholdengo: 'Gholdengo||Life Orb|Good as Gold|Make It Rain,Shadow Ball,Nasty Plot,Protect|Timid|2,0,0,32,0,32||||50|',
  Rillaboom: 'Rillaboom||Miracle Seed|Grassy Surge|Fake Out,Grassy Glide,Wood Hammer,High Horsepower|Adamant|32,32,0,0,2,0||||50|',
  Salamence: 'Salamence||Salamencite|Intimidate|Hyper Voice,Draco Meteor,Tailwind,Protect|Timid|2,0,0,32,0,32||||50|',
};
function run(seed, mine, theirs, c1, c2, verbose) {
  const b = new Battle({formatid: 'gen9championsdoublescustomgame', seed});
  b.setPlayer('p1', {name: 'Me', team: mine.map(n => SET[n]).join(']')});
  b.setPlayer('p2', {name: 'Them', team: theirs.map(n => T[n]).join(']')});
  const ok = [b.choose('p1', 'team 1234'), b.choose('p2', 'team 1234'), b.choose('p1', c1), b.choose('p2', c2)];
  if (verbose) { console.log('choose ok', ok, 'turn', b.turn); console.log(b.log.filter(l => /^\|(move|-damage|-heal|-fail|cant|-activate|-mega|detailschange|-sidestart|-fieldstart|-boost|-unboost|-ability|-status|faint|turn|-singleturn|-crit|-supereffective|-resisted|-immune|-enditem|-item|switch|-start|error)/.test(l)).join('\n')); }
  return b;
}
const b = run([1, 2, 3, 4], ['Kingambit', 'Salamence', 'Gholdengo', 'Incineroar'], ['Raichu', 'Gholdengo', 'Rillaboom', 'Salamence'], 'move 1 2, move 3 mega', 'move 1 1 mega, move 3', true);
for (const s of b.sides) for (const p of s.active) console.log(s.id, p.species.name, p.hp + '/' + p.maxhp, JSON.stringify(p.boosts), p.status || '-', JSON.stringify(p.storedStats));
console.log('field', Object.keys(b.field.pseudoWeather), b.field.weather, b.field.terrain, b.sides.map(s => Object.keys(s.sideConditions)));
const t1 = Date.now(); for (let i = 0; i < 300; i++) run([i, 7, 9, 11], ['Kingambit', 'Salamence', 'Gholdengo', 'Incineroar'], ['Raichu', 'Gholdengo', 'Rillaboom', 'Salamence'], 'move 1 2, move 3 mega', 'move 1 1 mega, move 3');
console.log('ms per battle incl T1', (Date.now() - t1) / 300);
