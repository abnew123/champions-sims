// Damage ranges for the eval bar's spread checks (spreads.py): each query rebuilds a turn's position as positions.js does and asks
// Showdown for the damage one Pokemon's move does to another, at the lowest and the highest damage roll (the move's type and its other
// changes applied first, as using it would: Pixilate, Weather Ball, Expanding Force).
// usage (from the main folder's pssim/, where node_modules is): node <this file> <queries.json> <out.json>
// query: {spec, att: [side, k], def: [side, k], move, crit, spread, helping, hp: {att, def}}
//   k: the Pokemon's index in that side's spec mons; hp: [kind, value] with kind 'abs' (HP) or 'pct' (percent of its max HP), or null
// out: [{lo, hi, maxhp} | {error}] in the same order
const path = require('path'), fs = require('fs');
const {rebuild, dex, toID} = require(path.join(__dirname, 'positions.js'));
const [qf, outf] = process.argv.slice(2);
const setHp = (p, h) => { if (!h) return; p.hp = Math.max(1, Math.min(p.maxhp, h[0] === 'abs' ? h[1] : Math.round(p.maxhp * h[1] / 100))); };
const out = JSON.parse(fs.readFileSync(qf)).map(q => {
  try {
    const {b} = rebuild(q.spec, false);
    const att = b.sides[q.att[0]].pokemon[q.att[1]], def = b.sides[q.def[0]].pokemon[q.def[1]];
    setHp(att, (q.hp || {}).att); setHp(def, (q.hp || {}).def);
    if (q.helping) att.addVolatile('helpinghand');
    const roll = r => {
      const move = dex.getActiveMove(toID(q.move));
      b.singleEvent('ModifyType', move, null, att, def, move, move); b.runEvent('ModifyType', att, def, move, move);
      b.singleEvent('ModifyMove', move, null, att, def, move, move); b.runEvent('ModifyMove', att, def, move, move);
      move.willCrit = !!q.crit; if (q.spread) move.spreadHit = true;
      b.randomizer = d => Math.trunc(Math.trunc(d * (100 - r)) / 100);
      const d = b.actions.getDamage(att, def, move, true);
      return typeof d === 'number' ? d : null;
    };
    return {lo: roll(15), hi: roll(0), maxhp: def.maxhp};
  } catch (e) { return {error: String(e.message).slice(0, 120)}; }
});
fs.writeFileSync(outf, JSON.stringify(out));
