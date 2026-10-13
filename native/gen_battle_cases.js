// Mid-battle differential cases for the native turn engine (2026-10-12): gen_turn_cases.js starts every case fresh after team preview, so
// statuses, volatiles, hazards, screens, used items, fainted allies, later-turn Fake Outs and low PP only ever arise inside the one turn.
// Here Showdown plays whole battles between real team sheets (native/real_teams.jsonl: the open team sheets of the cached Bo3 replays,
// generic spreads by nature) with random legal choices, and every turn becomes a case: the state before it, then the turn played in the
// four RNG modes (lo / hi / mid / real), each with its post-turn state, log and the next request. The battle goes on from the real-RNG
// branch. Choices: random legal moves, an attack aimed at the ally now and then, the Mega 70% of the time, a switch about 15% of the time.
// usage (from pssim/): node ../native/gen_battle_cases.js <battles> <out.jsonl> [seed]      env TEAMS=<jsonl>, MAXTURN (default 25)
// About 110 KB a case (five full states): 1,000 battles make ~13,000 cases, ~1.5 GB; delete the file once checked.
// check: DIFF_FULL=1 ORDER=1 champ turn ../native/engine_data_full.json <out.jsonl> lo,hi,mid,real
const path = require('path'), fs = require('fs');
const {Battle, Dex} = require(path.resolve('node_modules/pokemon-showdown')); const dex = Dex.mod('champions');
const T = require(path.resolve('t1sim.js'));
const {exportState} = require(path.resolve(__dirname, 'export_state.js'));
const [N, outf, seed0 = '1'] = process.argv.slice(2);
const MAXTURN = +(process.env.MAXTURN || 25);
let rs = (+seed0 * 2654435761) >>> 0;
const rnd = () => { rs = (rs + 0x6D2B79F5) >>> 0; let t = rs; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const pick = a => a[Math.floor(rnd() * a.length)];
const dEV = n => ['Adamant', 'Jolly', 'Naughty', 'Lonely'].includes(n) ? [2, 32, 0, 0, 0, 32] : ['Modest', 'Timid', 'Mild', 'Rash', 'Hasty', 'Naive'].includes(n) ? [2, 0, 0, 32, 0, 32]
  : n === 'Brave' ? [32, 32, 2, 0, 0, 0] : n === 'Quiet' ? [32, 0, 2, 32, 0, 0] : ['Calm', 'Careful', 'Sassy'].includes(n) ? [32, 0, 14, 0, 20, 0] : [32, 0, 20, 0, 14, 0];
const ok = s => dex.species.get(s.species).exists && s.moves.length && s.moves.every(m => dex.moves.get(m).exists) && dex.items.get(s.item).exists !== false
  && dex.abilities.get(s.ability).exists && dex.natures.get(s.nature).exists;
const TEAMS = fs.readFileSync(process.env.TEAMS || path.resolve(__dirname, 'real_teams.jsonl'), 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l)).filter(t => t.length === 6 && t.every(ok));
const mk = s => T.toSet({species: dex.species.get(s.species).name, item: dex.items.get(s.item).name || '', ability: dex.abilities.get(s.ability).name,
  moves: s.moves.map(m => dex.moves.get(m).name), nature: dex.natures.get(s.nature).name, evs: dEV(dex.natures.get(s.nature).name)});
function fakePRNG(mode) {
  // q<n>: every draw is the fraction n/1000 (separates chances that lo / hi / mid cannot, e.g. 3/10 from 1/2)
  const q = mode[0] === 'q' ? +mode.slice(1) / 1000 : null;
  const r = q !== null ? ((from, to) => from === undefined ? q : to === undefined ? Math.floor(q * from) : from + Math.floor(q * (to - from)))
    : (from, to) => from === undefined ? {lo: 0, hi: 0.999999, mid: 0.5}[mode] : to === undefined ? {lo: 0, hi: from - 1, mid: Math.floor(from / 2)}[mode] : {lo: from, hi: to - 1, mid: from + Math.floor((to - from) / 2)}[mode];
  return {random: r, randomChance: (n, d) => r(d) < n, sample: items => items[r(items.length)],
    shuffle(items, start = 0, end = items.length) { while (start < end - 1) { const ni = r(start, end); if (start !== ni) [items[start], items[ni]] = [items[ni], items[start]]; start++; } },
    getSeed: () => 'fake', startingSeed: 'fake', clone() { return fakePRNG(mode); }};
}
function choicesFor(side) {
  const out = []; const req = side.activeRequest;
  if (!req || req.wait || !req.active) return null;
  for (let i = 0; i < 2; i++) {
    const p = side.active[i], ra = req.active[i];
    if (!p || p.fainted || !ra) { out.push('pass'); continue; }
    const opts = [];
    ra.moves.forEach((m, k) => { if (m.disabled) return; const mv = dex.moves.get(m.id);
      const ally = side.active[1 - i] && !side.active[1 - i].fainted ? `move ${k + 1} ${i === 0 ? -2 : -1}` : null;
      if (['normal', 'any', 'adjacentFoe'].includes(mv.target)) {
        for (const t of [1, 2]) if (side.foe.active[t - 1] && !side.foe.active[t - 1].fainted) opts.push(`move ${k + 1} ${t}`);
        if (ally && mv.target !== 'adjacentFoe' && rnd() < 0.08) opts.push(ally);
        if (!opts.length || !opts.some(o => o.startsWith(`move ${k + 1} `))) opts.push(`move ${k + 1} 1`);
      } else if (mv.target === 'adjacentAlly') { if (ally) opts.push(ally); }
      else opts.push(`move ${k + 1}`); });
    const bench = side.pokemon.map((q, k) => k).filter(k => k >= 2 && !side.pokemon[k].fainted && !out.includes(`switch ${k + 1}`));
    if (bench.length && !ra.trapped && !ra.maybeTrapped && rnd() < 0.15) { out.push(`switch ${pick(bench) + 1}`); continue; }
    if (!opts.length) return null;
    let c = pick(opts);
    if (ra.canMegaEvo && !out.some(x => x.includes('mega')) && rnd() < 0.7) c += ' mega';
    out.push(c);
  }
  return out.join(', ');
}
// mid-turn / end-of-turn switch requests (U-turn, faints with a bench): random legal switches, recorded for the native replay
function answerSwitches(b) {
  const switches = []; let guard = 0;
  while (!b.ended && b.requestState === 'switch' && guard++ < 10) {
    for (const s of b.sides) {
      const req = s.activeRequest; if (!req || !req.forceSwitch) continue;
      let avail = s.pokemon.map((q, k) => k).filter(k => k >= 2 && !s.pokemon[k].fainted); const parts = [];
      for (let i = 0; i < 2; i++) {
        // Revival Blessing (2026-10-13): that slot's request takes a fainted Pokemon to revive, not a bench one
        const a = s.active[i]; const revive = req.forceSwitch[i] && a && s.slotConditions[a.position] && s.slotConditions[a.position]['revivalblessing'];
        if (revive) { const f = s.pokemon.map((q, k) => k).filter(k => s.pokemon[k].fainted); if (!f.length) { parts.push('pass'); continue; } parts.push(`switch ${pick(f) + 1}`); continue; }
        if (!req.forceSwitch[i] || !avail.length) { parts.push('pass'); continue; }
        const k = pick(avail); avail = avail.filter(x => x !== k); parts.push(`switch ${k + 1}`);
      }
      const c = parts.join(', '); switches.push([s.n, c]);
      if (!b.choose(s.id, c)) return null;
    }
  }
  return b.requestState === 'switch' ? null : switches;
}
// the next request as Showdown sends it: each active slot's moves with their disabled flags
const reqOf = b => b.ended ? null : b.sides.map(s => { const r = s.activeRequest; if (!r || !r.active) return {wait: true};
  return {active: r.active.map(a => ({moves: a.moves.map(m => ({id: m.id, disabled: !!m.disabled})), trapped: !!a.trapped, maybeTrapped: !!a.maybeTrapped, canMegaEvo: !!a.canMegaEvo}))}; });
const LOGRE = /^\|(move|-damage|-heal|faint|cant|-fail|-miss|-immune|-activate|-boost|-unboost|-status|-crit|-start|-end|-sidestart|-sideend|-fieldstart|-fieldend|-weather|-mega|-enditem|-item|switch|drag|turn|upkeep)\|/;
const fd = fs.openSync(outf, 'w'); let n = 0, battles = 0, tries = 0, errs = 0;
while (battles < +N && tries < +N * 5) {
  tries++;
  const [t1, t2] = [pick(TEAMS), pick(TEAMS)];
  const four = () => { const k = [0, 1, 2, 3, 4, 5]; for (let i = 5; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [k[i], k[j]] = [k[j], k[i]]; } return k.slice(0, 4).map(x => x + 1).join(''); };
  let main;
  try {
    main = new Battle({formatid: 'gen9championsdoublescustomgame', seed: [1, 2, 3, Math.floor(rnd() * 60000)]}); main.debugMode = false;
    main.setPlayer('p1', {name: 'A', team: t1.map(mk)}); main.setPlayer('p2', {name: 'B', team: t2.map(mk)});
    main.choose('p1', 'team ' + four()); main.choose('p2', 'team ' + four());
    if (!answerSwitches(main)) continue;
  } catch (e) { errs++; continue; }
  battles++;
  for (let guard = 0; !main.ended && main.turn <= MAXTURN && guard < 60; guard++) {
    const c1 = choicesFor(main.sides[0]), c2 = choicesFor(main.sides[1]);
    if (!c1 || !c2) break;
    const pre = exportState(main); const snap = JSON.stringify(main.toJSON());
    const res = {}; let good = true, next = null;
    for (const mode of (process.env.RNGMODES || 'lo,hi,mid,real').split(',').sort((a, b) => (a === 'real') - (b === 'real'))) {   // real last: the battle goes on from it
      try {
        const b = Battle.fromJSON(snap); b.debugMode = false;
        if (mode !== 'real') b.prng = fakePRNG(mode);
        const logStart = b.log.length;
        // TRACE=<battle>:<turn>: that turn's real-RNG log with the number of draws so far on each line (to stderr), for DRAWTRACE=1 champ turn
        const trace = mode === 'real' && process.env.TRACE === `${battles}:${main.turn}`;
        if (trace) { let k = 0; const nx = b.prng.rng.next.bind(b.prng.rng); b.prng.rng.next = () => { k++; console.error(`draw ${k} [${b.getAllActive().map(p => p.species.id + ':' + p.speed).join(' ')}] q[${b.queue.list.map(a => a.choice + ':' + (a.pokemon ? a.pokemon.species.id : '')).join(' ')}]: ` + new Error().stack.split('\n').slice(2, 9).map(x => x.trim().replace(/^at /, '').replace(/ \(.*\/dist\//, ' (')).join(' < ')); return nx(); };
          const op = b.log.push; b.log.push = function (...a) { return op.apply(this, a.map(x => `${x} #${k}`)); }; }
        if (!b.choose('p1', c1) || !b.choose('p2', c2)) { good = false; break; }
        const switches = answerSwitches(b); if (!switches) { good = false; break; }
        res[mode] = {switches, post: exportState(b), req: reqOf(b), log: b.log.slice(logStart).filter(l => LOGRE.test(l))};
        if (mode === 'real') next = b;
        if (trace) console.error(b.log.slice(logStart).join('\n'));
      } catch (e) { errs++; good = false; break; }
    }
    if (!good) break;
    fs.writeSync(fd, JSON.stringify({id: n, battle: battles, turn: main.turn, choices: [c1, c2], pre, ...res}) + '\n'); n++;
    main = next;
  }
}
fs.closeSync(fd); console.log(`${battles} battles, ${n} turn cases (${tries} tries, ${errs} errors) -> ${outf}`);
