// 2v2 endgame: my two vs their two, both fresh, with Trick Room up for K more turns (the lead set it, then traded).
// Every turn both sides play the Nash mix of a one-turn matrix game (every joint action, exact Showdown mechanics,
// scored by a simple position value); the real turn is then played from those mixes. Repeated to the end of the game.
//   usage: node endgame.js <arch> <Mine1,Mine2> <Their1,Their2> [games] [K]
'use strict';
const {Battle, PRNG, Dex} = require('pokemon-showdown');
const dex = Dex.mod('champions');
const T = require('./t1sim.js');
const seedmix = require('./seedmix.js');
const FMT = 'gen9championsdoublescustomgame';
const MAXTURN = 15;
const NS = +(process.env.EG_SEEDS || 1);   // planning seeds per cell (1 = the v10 runs)
const FOE_TARGETS = new Set(['normal', 'any', 'adjacentFoe']);
const SKIP = new Set(['healingwish', 'memento']);        // no bench to bring in

function effect(moveType, def) {
  let m = 1; for (const t of def.getTypes()) { if (!dex.getImmunity(moveType, t)) return 0; m *= Math.pow(2, dex.getEffectiveness(moveType, t)); } return m;
}

function slotOptions(b, side, i) {
  const p = side.active[i];
  if (!p || p.fainted) return ['pass'];
  const req = side.activeRequest && side.activeRequest.active && side.activeRequest.active[i];
  if (!req) return ['pass'];
  const mega = req.canMegaEvo ? ' mega' : '';
  const foes = side.foe.active; const out = [];
  req.moves.forEach((m, k) => {
    if (m.disabled || SKIP.has(m.id)) return;
    if (m.id === 'fakeout' && p.activeMoveActions > 0) return;                  // fails after the first turn out (Showdown's own test; activeTurns is already 1 on turn 1)
    if (/^choice/.test(p.item) && ['protect', 'detect'].includes(m.id)) return;   // nobody Protects into a Choice lock (one-turn planning can't see the cost)
    if (m.id === 'trickroom' && b.field.pseudoWeather.trickroom && side.id === 'p1') return;   // I never undo my own Trick Room
    const mv = dex.moves.get(m.id);
    if (FOE_TARGETS.has(mv.target)) {
      foes.forEach((f, t) => {
        if (!f || f.fainted) return;
        if (mv.category !== 'Status' && effect(mv.type, f) === 0 && mv.id !== 'weatherball' && mv.id !== 'terrainpulse') return;
        out.push(`move ${k + 1} ${t + 1}${mega}`);
      });
    } else if (mv.target === 'adjacentAlly') {
      const a = side.active[1 - i]; if (a && !a.fainted) out.push(`move ${k + 1} ${i === 0 ? -2 : -1}${mega}`);
    } else out.push(`move ${k + 1}${mega}`);
  });
  return out.length ? out : ['move 1'];
}
function jointOptions(b, side) {
  const a = slotOptions(b, side, 0), c = slotOptions(b, side, 1), out = [];
  for (const x of a) for (const y of c) {
    if (x.includes('mega') && y.includes('mega')) { out.push(x + ', ' + y.replace(' mega', '')); continue; }
    out.push(x + ', ' + y);
  }
  return out;
}

// position value for me, 0..1: HP share, plus Trick Room turns for the slower side
function value(b) {
  if (b.ended) return b.winner === 'Me' ? 1 : b.winner ? 0 : 0.5;
  const hp = s => s.pokemon.reduce((t, p) => t + (p.fainted ? 0 : p.hp / p.maxhp), 0);
  const spe = s => { const a = s.pokemon.filter(p => !p.fainted); return a.reduce((t, p) => t + p.getStat('spe', true, true), 0) / Math.max(1, a.length); };
  const [me, th] = b.sides;
  // stat stages on the attacking stat each Pokemon uses (from its moves), ~0.3 of a Pokemon's HP per stage (the replay-fitted
  // win model puts a boost stage at ~0.4 of a lost Pokemon), so setup moves and Intimidate count
  const prim = p => { let ph = 0, sp = 0; for (const m of p.moveSlots) { const c = dex.moves.get(m.id).category; if (c === 'Physical') ph++; else if (c === 'Special') sp++; } return ph >= sp ? 'atk' : 'spa'; };
  const bst = s => s.active.reduce((t, p) => t + (p && !p.fainted ? Math.max(-3, Math.min(3, p.boosts[prim(p)])) + 0.3 * Math.max(-2, Math.min(2, p.boosts.spe)) : 0), 0);
  let x = hp(me) - hp(th) + 0.3 * (bst(me) - bst(th));
  const tr = b.field.pseudoWeather.trickroom;
  if (tr) x += 0.08 * tr.duration * Math.tanh((spe(th) - spe(me)) / 15);
  return Math.min(1, Math.max(0, 0.5 + 0.25 * x));
}

// zero-sum matrix game, row player maximises: regret matching, returns average strategies
function nash(A, iters = 400) {
  const m = A.length, n = A[0].length;
  const rr = new Float64Array(m), rc = new Float64Array(n), sr = new Float64Array(m), sc = new Float64Array(n);
  const norm = r => { let t = 0; const p = new Float64Array(r.length); for (let i = 0; i < r.length; i++) { p[i] = Math.max(0, r[i]); t += p[i]; }
    if (t <= 0) p.fill(1 / r.length); else for (let i = 0; i < p.length; i++) p[i] /= t; return p; };
  for (let it = 0; it < iters; it++) {
    const x = norm(rr), y = norm(rc);
    const ur = new Float64Array(m), uc = new Float64Array(n); let v = 0;
    for (let i = 0; i < m; i++) { let s = 0; for (let j = 0; j < n; j++) s += A[i][j] * y[j]; ur[i] = s; v += x[i] * s; }
    for (let j = 0; j < n; j++) { let s = 0; for (let i = 0; i < m; i++) s += A[i][j] * x[i]; uc[j] = -s; }
    for (let i = 0; i < m; i++) { rr[i] = Math.max(0, rr[i] + ur[i] - v); sr[i] += x[i]; }
    for (let j = 0; j < n; j++) { rc[j] = Math.max(0, rc[j] + uc[j] + v); sc[j] += y[j]; }
  }
  const ts = sr.reduce((a, b) => a + b, 0), tc = sc.reduce((a, b) => a + b, 0);
  return [Array.from(sr, v => v / ts), Array.from(sc, v => v / tc)];
}
function label(b, side, choice) {
  return choice.split(', ').map((c, i) => { const p = side.active[i]; if (c === 'pass' || !p) return '-';
    const [, k, t] = c.replace(' mega', '').split(' '); const mv = p.moveSlots[+k - 1]; let tg = '';
    if (t && +t > 0) { const f = side.foe.active[+t - 1]; tg = ' -> ' + (f ? f.name : '?'); } else if (t) tg = ' -> ally';
    return `${p.name}: ${mv ? mv.move : c}${tg}${c.includes('mega') ? ' (mega)' : ''}`; }).join(' + ');
}
function sample(p, rng) { let r = rng(), k = 0; for (; k < p.length - 1; k++) { r -= p[k]; if (r <= 0) break; } return k; }

function start(mySets, thSets, seed, K) {
  const b = new Battle({formatid: FMT, seed}); b.debugMode = false;
  b.setPlayer('p1', {name: 'Me', team: mySets}); b.setPlayer('p2', {name: 'Them', team: thSets});
  b.choose('p1', 'team 12'); b.choose('p2', 'team 12');
  if (K > 0) { b.field.addPseudoWeather('trickroom', b.sides[0].active[0]); b.field.pseudoWeather.trickroom.duration = K; }
  return b;
}

function playGame(mySets, thSets, g, K, log) {
  const b = start(mySets, thSets, seedmix(1e6 + g), K);
  let rs = seedmix(7e6 + g)[0] * 65536 + seedmix(7e6 + g)[1]; const rng = () => (rs = (rs * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let turn = 1; !b.ended && turn <= MAXTURN; turn++) {
    const mine = jointOptions(b, b.sides[0]), theirs = jointOptions(b, b.sides[1]);
    // each cell averages NS planning seeds, so chance (a repeated Protect, rolls, misses, crits) isn't fixed one way while planning
    const snap = JSON.stringify(b.toJSON()); const cseeds = Array.from({length: NS}, (_, k) => seedmix(3e6 + g * 50 + turn + 1e5 * k));
    const A = mine.map(() => new Array(theirs.length).fill(0.5));
    for (let i = 0; i < mine.length; i++) for (let j = 0; j < theirs.length; j++) {
      let s = 0;
      for (const cs of cseeds) {
        const c = Battle.fromJSON(snap); c.prng = new PRNG(cs);
        if (!c.choose('p1', mine[i]) || !c.choose('p2', theirs[j])) { s = NaN; break; }
        s += value(c);
      }
      A[i][j] = s / NS;
    }
    // drop rows/columns the engine refused
    const okR = mine.map((_, i) => A[i].every(v => !Number.isNaN(v))), okC = theirs.map((_, j) => A.every((r, i) => !okR[i] || !Number.isNaN(r[j])));
    const R = mine.filter((_, i) => okR[i]), C = theirs.filter((_, j) => okC[j]);
    const M = A.filter((_, i) => okR[i]).map(r => r.filter((_, j) => okC[j]));
    if (!R.length || !C.length) {                  // nothing the engine accepts (odd request state): let it choose
      for (const side of b.sides) if (!side.isChoiceDone()) side.autoChoose();
      if (b.allChoicesDone()) b.commitChoices(); else break;
      if (log) log.push(`T${turn} (engine default choices)`); continue;
    }
    const [x, y] = nash(M);
    if (process.env.EG_DEBUG && turn <= +process.env.EG_DEBUG) {      // each option's payoff against the other side's mix
      const rv = M.map(r => r.reduce((t, v, c) => t + v * y[c], 0)), cv = C.map((_, c) => M.reduce((t, r, a) => t + r[c] * x[a], 0));
      const show = (vals, L, side, mine) => vals.map((v, k) => [v, k]).sort((a, b) => mine ? b[0] - a[0] : a[0] - b[0]).slice(0, 8)
        .map(([v, k]) => `   ${(100 * v).toFixed(1)}  ${label(b, side, L[k])}`).join('\n');
      console.log(`T${turn} game value ${(100 * rv.reduce((t, v, a) => t + v * x[a], 0)).toFixed(1)}\n  my options vs their mix (higher is better for me):\n${show(rv, R, b.sides[0], true)}\n  their options vs my mix (lower is better for them):\n${show(cv, C, b.sides[1], false)}`);
    }
    const i = sample(x, rng), j = sample(y, rng);
    if (log) {
      log.push(`T${turn} ${label(b, b.sides[0], R[i])}  ||  ${label(b, b.sides[1], C[j])}   [${R.length}x${C.length}, my mix top ${Math.max(...x).toFixed(2)}]`);
      const top = (p, L, side) => p.map((v, k) => [v, k]).sort((a, c) => c[0] - a[0]).filter(([v], n) => n < 4 && v >= 0.04).map(([v, k]) => [label(b, side, L[k]), +v.toFixed(2)]);
      (log.turns = log.turns || []).push({turn, my: top(x, R, b.sides[0]), th: top(y, C, b.sides[1]), myPick: label(b, b.sides[0], R[i]), thPick: label(b, b.sides[1], C[j]),
        value: +M.reduce((t, row, a) => t + x[a] * row.reduce((u, v, c) => u + v * y[c], 0), 0).toFixed(3), size: [R.length, C.length]});
    }
    b.choose('p1', R[i]); b.choose('p2', C[j]);
  }
  if (log) log.full = b.log.slice();
  if (log) log.b = b.log.filter(l => /^\|(move|-damage|faint|-fieldend|-fieldstart|turn|-weather|-mega|win|-crit|-supereffective|-activate)\|/.test(l)).join('\n');
  return value(b);
}

function sets(arch, mine, theirs) {
  return [mine.map(n => T.toSet({...T.MY[n], species: T.MY[n].species})), theirs.map(sp => T.toSet(T.oppSet(arch, sp, [])))];
}
function matchup(arch, mine, theirs, games, K) {
  const [ms, ts] = sets(arch, mine, theirs); let s = 0; const vs = []; let fails = 0;
  for (let g = 0; g < games; g++) {
    let v; try { v = playGame(ms, ts, g, K); } catch (e) { fails++; console.error(`game ${g} failed: ${e.message}`); continue; }
    s += v; vs.push(+v.toFixed(3)); }
  return {arch, mine, theirs, K, games: vs.length, fails, v: vs.length ? s / vs.length : null, vs};
}
module.exports = {matchup, playGame, sets};

if (require.main === module) {
  const [arch, m, t, games = '4', K = '3'] = process.argv.slice(2);
  const [ms, ts] = sets(arch, m.split(','), t.split(','));
  const t0 = Date.now(); let s = 0;
  for (let g = 0; g < +games; g++) { const log = []; const v = playGame(ms, ts, g, +K, log); s += v;
    console.log(`game ${g}: ${v.toFixed(2)}\n  ` + log.join('\n  ')); if (process.env.SHOWLOG) console.log(log.b); }
  console.log(`mean ${(s / +games).toFixed(3)}  ${((Date.now() - t0) / 1000).toFixed(1)}s`);
}
