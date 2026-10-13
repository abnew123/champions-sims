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
// strict (the eval bar's reading): a percent stands for every HP Showdown shows as it (ceil, 99 until full), so a move whose power or an
// ability whose effect depends on HP (Water Spout, Eruption, Multiscale) is worked out at both ends; Psychic Fangs and the like break the
// target side's screens before they hit
const shown = (h, M) => h >= M ? 100 : Math.min(99, Math.max(1, Math.ceil(100 * h / M)));
const hps = (p, h) => {
  if (!h) return [p.hp];
  if (h[0] === 'abs') return [Math.max(1, Math.min(p.maxhp, h[1]))];
  const c = []; for (let x = 1; x <= p.maxhp; x++) if (shown(x, p.maxhp) === h[1]) c.push(x);
  return c.length ? [c[0], c[c.length - 1]] : [Math.max(1, Math.min(p.maxhp, Math.round(p.maxhp * h[1] / 100)))];
};
const BREAKS = new Set(['brickbreak', 'psychicfangs', 'ragingbull']);
const out = JSON.parse(fs.readFileSync(qf)).map(q => {
  try {
    const {b} = rebuild(q.spec, false);
    const att = b.sides[q.att[0]].pokemon[q.att[1]], def = b.sides[q.def[0]].pokemon[q.def[1]];
    if (q.helping) att.addVolatile('helpinghand');
    if (q.strict && BREAKS.has(toID(q.move))) for (const c of ['reflect', 'lightscreen', 'auroraveil']) def.side.removeSideCondition(c);
    const roll = r => {
      const move = dex.getActiveMove(toID(q.move));
      if (q.strict) { b.activeMove = move; b.activePokemon = att; b.activeTarget = def; if (q.strict >= 2) move.hit = 1; }   // a move in use; its first hit (strict 2)
      b.singleEvent('ModifyType', move, null, att, def, move, move); b.runEvent('ModifyType', att, def, move, move);
      b.singleEvent('ModifyMove', move, null, att, def, move, move); b.runEvent('ModifyMove', att, def, move, move);
      // typeDue: Protean / Libero make the user the move's type as it hits (onPrepareHit, not run here), once a stint; Mega Greninja's other
      // moves came out at 1.6 of predicted without it (mega_check.py, 2026-10-12)
      if (q.spec.typeDue && (att.ability === 'protean' || att.ability === 'libero') && !att.abilityState[att.ability] && move.type !== '???' && att.getTypes().join() !== move.type) att.setType(move.type);
      move.willCrit = !!q.crit; if (q.spread) move.spreadHit = true;
      b.randomizer = d => Math.trunc(Math.trunc(d * (100 - r)) / 100);
      const d = b.actions.getDamage(att, def, move, true);
      return typeof d === 'number' ? d : null;
    };
    if (!q.strict) { setHp(att, (q.hp || {}).att); setHp(def, (q.hp || {}).def); return {lo: roll(15), hi: roll(0), maxhp: def.maxhp}; }
    let lo = null, hi = null;
    for (const ha of hps(att, (q.hp || {}).att)) for (const hd of hps(def, (q.hp || {}).def)) {
      att.hp = ha; def.hp = hd; const a = roll(15), z = roll(0);
      if (a === null || z === null) return {lo: null, hi: null, maxhp: def.maxhp};
      lo = lo === null ? a : Math.min(lo, a); hi = hi === null ? z : Math.max(hi, z);
    }
    return {lo, hi, maxhp: def.maxhp};
  } catch (e) { return {error: String(e.message).slice(0, 120)}; }
});
fs.writeFileSync(outf, JSON.stringify(out));
