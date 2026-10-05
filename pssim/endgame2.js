// 2v2 endgame: my two vs their two, both fresh, with Trick Room up for K more turns (the lead set it, then traded).
// Every turn both sides play the Nash mix of a one-turn matrix game (every joint action, exact Showdown mechanics,
// scored by a simple position value); the real turn is then played from those mixes. Repeated to the end of the game.
//   usage: node endgame.js <arch> <Mine1,Mine2> <Their1,Their2> [games] [K]
'use strict';
const {Battle, PRNG, Dex} = require('pokemon-showdown');
const dex = Dex.mod('champions');
const fs = require('fs');
const T = require('./t1sim.js');
const seedmix = require('./seedmix.js');
const FMT = 'gen9championsdoublescustomgame';
const toID = x => (x || '').toLowerCase().replace(/[^a-z0-9]/g, '');
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

const PRIM = new Map();
function prim(p) {
  const key = p.set.species + '|' + p.moveSlots.map(m => m.id).join(',');
  if (!PRIM.has(key)) { let ph = 0, sp = 0; for (const m of p.moveSlots) { const c = dex.moves.get(m.id).category; if (c === 'Physical') ph++; else if (c === 'Special') sp++; } PRIM.set(key, ph >= sp ? 'atk' : 'spa'); }
  return PRIM.get(key);
}
// position features (my side minus theirs): HP share (in Pokemon), Pokemon alive, attack-stat stages, Trick Room turns x speed edge,
// Choice-locked into a status move, Choice-locked into an attack
function feats(b) {
  const side = s => {
    const alive = s.pokemon.filter(p => !p.fainted);
    const hp = alive.reduce((t, p) => t + p.hp / p.maxhp, 0);
    const bst = s.active.reduce((t, p) => t + (p && !p.fainted ? Math.max(-3, Math.min(3, p.boosts[prim(p)])) + 0.3 * Math.max(-2, Math.min(2, p.boosts.spe)) : 0), 0);
    let lockS = 0, lockA = 0;
    for (const p of s.active) if (p && !p.fainted && p.volatiles.choicelock) { const mv = dex.moves.get(p.volatiles.choicelock.move); if (mv.category === 'Status') lockS++; else lockA++; }
    const spe = alive.reduce((t, p) => t + p.getStat('spe', true, true), 0) / Math.max(1, alive.length);
    return {hp, n: alive.length, bst, lockS, lockA, spe};
  };
  const [a, o] = b.sides.map(side); const tr = b.field.pseudoWeather.trickroom;
  const cnt = (s, v) => s.active.filter(p => p && !p.fainted && p.volatiles[v]).length;
  const st = (s, L) => s.pokemon.filter(p => !p.fainted && L.includes(p.status)).length;
  const sc = (s, k) => s.sideConditions[k] ? s.sideConditions[k].duration || 1 : 0;
  const tricked = s => s.active.filter(p => p && !p.fainted && /^choice/.test(p.item) && !/^choice/.test(toID(p.set.item))).length;
  const D = (f) => f(b.sides[0]) - f(b.sides[1]);
  return [a.hp - o.hp, a.n - o.n, a.bst - o.bst, tr ? tr.duration * Math.tanh((o.spe - a.spe) / 15) : 0, a.lockS - o.lockS, a.lockA - o.lockA, ...gridFeats(b),
    cnt(b.sides[0], 'mustrecharge') - cnt(b.sides[1], 'mustrecharge'), cnt(b.sides[0], 'stall') - cnt(b.sides[1], 'stall'),
    typeEdge(b, b.sides[0], b.sides[1]) - typeEdge(b, b.sides[1], b.sides[0]),
    D(s => st(s, ['slp', 'frz'])), D(s => st(s, ['par'])), D(s => st(s, ['brn', 'psn', 'tox'])),
    tr ? 0 : D(s => sc(s, 'tailwind')), D(s => sc(s, 'reflect') + sc(s, 'lightscreen') + sc(s, 'auroraveil')),
    D(s => cnt(s, 'encore')), D(tricked)];
}
// one-on-one matchup grid (mxtr, the sheet's Matchups tab): my Pokemon vs each threat, with and without Trick Room
const GRID = {};
for (const [k, f] of [['tr', 'gx_cells_tr_inc'], ['notr', 'gx_cells_notr_inc']]) {
  GRID[k] = {};
  for (const suf of ['', '_ext']) { const p = `${__dirname}/../mxtr/${f}${suf}.json`; if (fs.existsSync(p)) Object.assign(GRID[k], JSON.parse(fs.readFileSync(p))); }
}
const GFOES = new Set(Object.keys(GRID.tr).map(k => k.split('|')[0]));
const GVAL = {counter: 1, check: 0.75, wall: 0.5, guess: 0.5, lost: 0};
const GN = new Map();
function gname(p) {
  const key = p.species.name + '|' + p.item; if (GN.has(key)) return GN.get(key);
  const r = gname_(p); GN.set(key, r); return r;
}
function gname_(p) {
  const base = p.species.baseSpecies; const alias = {'Arcanine-Hisui': 'Arcanine-H', 'Floette-Eternal': 'M-Floette', 'Floette': 'M-Floette'};
  if (alias[base]) return alias[base];
  const mega = [...GFOES].find(g => g === 'M-' + base || g.startsWith('M-' + base + ' '));
  if (mega && (p.species.isMega || /ite( [xyz])?$/i.test(dex.items.get(p.item).name) || !GFOES.has(base))) return mega;
  return GFOES.has(base) ? base : null;
}
function gcell(tr, foe, mine) { const c = GRID[tr ? 'tr' : 'notr'][`${foe}|${mine}`]; return c ? (c.v === 'roll' ? c.roll / 100 : GVAL[c.v] ?? 0.5) : null; }
// coverage: avg over their alive Pokemon of my best answer; exposure: avg over my alive Pokemon of its worst matchup (0 = loses to something)
function gridFeats(b) {
  const tr = !!b.field.pseudoWeather.trickroom;
  const mine = b.sides[0].pokemon.filter(p => !p.fainted).map(p => p.species.baseSpecies.replace(/-Mega.*/, ''));
  const foes = b.sides[1].pokemon.filter(p => !p.fainted).map(gname).filter(Boolean);
  if (!mine.length || !foes.length) return [0, 0];
  const cov = foes.reduce((t, f) => t + Math.max(0, ...mine.map(m => gcell(tr, f, m) ?? 0)), 0) / foes.length;
  const exp = mine.reduce((t, m) => t + Math.min(1, ...foes.map(f => gcell(tr, f, m) ?? 0.5)), 0) / mine.length;
  return [cov - 0.5, exp - 0.5];
}

// typing from the actual moves on the field: for each opposing Pokemon, the best type multiplier any of my remaining attacks gets
// (log2: immune -2, resisted -1, neutral 0, super effective 1, 4x 2), averaged; mine minus theirs
const WB = {sunnyday: 'Fire', desolateland: 'Fire', raindance: 'Water', primordialsea: 'Water', sandstorm: 'Rock', snowscape: 'Ice', hail: 'Ice'};
const TP = {psychicterrain: 'Psychic', grassyterrain: 'Grass', electricterrain: 'Electric', mistyterrain: 'Fairy'};
const ATE = {pixilate: 'Fairy', aerilate: 'Flying', refrigerate: 'Ice', galvanize: 'Electric'};
function moveType(b, p, mv) {
  if (mv.id === 'weatherball') return WB[b.field.weather] || 'Normal';
  if (mv.id === 'terrainpulse') return TP[b.field.terrain] || 'Normal';
  if (mv.type === 'Normal' && ATE[p.getAbility().id]) return ATE[p.getAbility().id];
  return mv.type;
}
function typeEdge(b, att, def) {
  const A = att.pokemon.filter(p => !p.fainted), D = def.pokemon.filter(p => !p.fainted);
  if (!A.length || !D.length) return 0;
  let t = 0;
  for (const d of D) {
    let best = -2;
    for (const a of A) for (const m of a.moveSlots) {
      const mv = dex.moves.get(m.id); if (mv.category === 'Status' || mv.id === 'fakeout') continue;
      const ty = moveType(b, a, mv); if (!dex.getImmunity(ty, d.getTypes()) || (ty === 'Ground' && d.hasAbility('levitate'))) continue;
      best = Math.max(best, Math.max(-2, Math.min(2, dex.getEffectiveness(ty, d.getTypes()))));
    }
    t += best;
  }
  return t / D.length;
}

// EG_AUTOPILOT: my side clicks a fixed simple plan instead of its equilibrium mix (their side still plays its full equilibrium, unaware):
// set Trick Room whenever it is down; Fake Out on the first turn out (the foe with the bigger attacking stat); Helping Hand an attacking partner;
// Eruption / Water Spout at half HP or more; otherwise the attack with the best power x STAB x type x weather, at its best target. Never Protect.
const WXM = {sunnyday: {Fire: 1.5, Water: 0.5}, desolateland: {Fire: 1.5, Water: 0}, raindance: {Water: 1.5, Fire: 0.5}, primordialsea: {Water: 1.5, Fire: 0}};
function autoChoice(b, side) {
  const parts = []; let megaUsed = false;
  for (let i = 0; i < 2; i++) {
    const p = side.active[i];
    if (!p || p.fainted) { parts.push('pass'); continue; }
    const req = side.activeRequest && side.activeRequest.active && side.activeRequest.active[i]; if (!req) { parts.push('pass'); continue; }
    const mega = req.canMegaEvo && !megaUsed ? ' mega' : ''; if (mega) megaUsed = true;
    const moves = req.moves.map((m, k) => ({...m, k: k + 1, mv: dex.moves.get(m.id)})).filter(m => !m.disabled);
    const foes = side.foe.active.map((f, t) => ({f, t: t + 1})).filter(x => x.f && !x.f.fainted);
    const ally = side.active[1 - i], allyUp = ally && !ally.fainted && ally.moveSlots.some(m => dex.moves.get(m.id).category !== 'Status');
    const has = id => moves.find(m => m.id === id);
    const eff = (ty, f) => (!dex.getImmunity(ty, f.getTypes()) || (ty === 'Ground' && f.hasAbility('levitate'))) ? 0 : Math.pow(2, dex.getEffectiveness(ty, f.getTypes()));
    let c = null;
    if (!b.field.pseudoWeather.trickroom && has('trickroom')) c = `move ${has('trickroom').k}${mega}`;
    else if (has('fakeout') && p.activeMoveActions === 0 && foes.some(x => eff('Normal', x.f) > 0)) {
      // stat stages but no ability/item modifiers: those (Torrent, Blaze, ...) read the move being used and crash outside a move
      const atk = f => Math.max(f.getStat('atk', false, true), f.getStat('spa', false, true));
      const t = foes.filter(x => eff('Normal', x.f) > 0).sort((a, d) => atk(d.f) - atk(a.f))[0];
      c = `move ${has('fakeout').k} ${t.t}${mega}`;
    } else if (has('helpinghand') && allyUp) c = `move ${has('helpinghand').k} ${i === 0 ? -2 : -1}${mega}`;
    else {
      let best = null;
      for (const m of moves) {
        const mv = m.mv; if (mv.category === 'Status' || ['fakeout', 'suckerpunch'].includes(mv.id)) continue;
        let bp = mv.basePower || 60; const ty = moveType(b, p, mv);
        if (['eruption', 'waterspout'].includes(mv.id)) { if (p.hp / p.maxhp < 0.5) continue; bp = 150 * p.hp / p.maxhp; }
        if (mv.id === 'weatherball' && WB[b.field.weather]) bp = 100;
        const stab = p.getTypes().includes(ty) || (mv.id === 'weatherball' && false) ? 1.5 : 1; const wx = (WXM[b.field.weather] || {})[ty] ?? 1;
        const spread = ['allAdjacentFoes', 'allAdjacent'].includes(mv.target);
        if (spread) { const v = foes.reduce((t, x) => t + bp * stab * wx * eff(ty, x.f) * (foes.length > 1 ? 0.75 : 1), 0); if (v > 0 && (!best || v > best.v)) best = {v, c: `move ${m.k}${mega}`}; }
        else if (FOE_TARGETS.has(mv.target)) for (const x of foes) { const v = bp * stab * wx * eff(ty, x.f) * (1.2 - 0.2 * x.f.hp / x.f.maxhp); if (v > 0 && (!best || v > best.v)) best = {v, c: `move ${m.k} ${x.t}${mega}`}; }
      }
      c = best ? best.c : `move ${moves[0] ? moves[0].k : 1}${mega}`;
    }
    parts.push(c);
  }
  return parts.join(', ');
}

// EG_VALUE=<json>: logistic weights fit on 2v2 outcomes (eg_fitvalue.py); otherwise the hand-set score (v10)
const VW = process.env.EG_VALUE ? JSON.parse(fs.readFileSync(process.env.EG_VALUE)) : null;
// Perish Song (hand-set; too few Perish games to fit). Counts resolve at end of turn in Speed order, reversed under Trick Room, and when
// both sides' last Pokemon faint together the side whose Pokemon fainted LAST wins (checked in the engine). So:
//  - everyone left is under Perish: the race is decided unless a KO changes it first -> about +-3 on the logit (~95/5)
//  - otherwise each doomed Pokemon loses part of its value: 0.8 x (HP and alive weights) / turns left
function perishAdj(b) {
  const alive = b.sides.map(s => s.pokemon.filter(p => !p.fainted));
  const t = p => p.volatiles.perishsong ? p.volatiles.perishsong.duration : null;
  if (!alive[0].length || !alive[1].length) return 0;
  if (alive.every(L => L.every(p => t(p) != null))) {
    const tmax = alive.map(L => Math.max(...L.map(t)));
    if (tmax[0] !== tmax[1]) return tmax[0] > tmax[1] ? 3 : -3;
    const tr = b.field.pseudoWeather.trickroom; const trThen = tr && tr.duration >= tmax[0];
    const last = [...alive[0].filter(p => t(p) === tmax[0]).map(p => [0, p.getStat('spe', true, true)]), ...alive[1].filter(p => t(p) === tmax[1]).map(p => [1, p.getStat('spe', true, true)])]
      .sort((a, c) => trThen ? a[1] - c[1] : c[1] - a[1]).pop();   // residual order: fastest first (slowest first under Trick Room); the last one wins
    return last[0] === 0 ? 3 : -3;
  }
  let z = 0;
  for (const [k, L] of alive.entries()) for (const p of L) if (t(p) != null)
    z += (k === 0 ? -1 : 1) * 0.8 * (VW.w[0] * p.hp / p.maxhp + VW.w[1]) / Math.max(1, t(p));
  return z;
}
function value(b) {
  if (b.ended) return b.winner === 'Me' ? 1 : b.winner ? 0 : 0.5;
  const f = feats(b);
  if (VW) { const z = VW.b0 + VW.w.reduce((t, w, k) => t + w * f[k], 0) + perishAdj(b); return 1 / (1 + Math.exp(-z)); }
  const x = f[0] + 0.3 * f[2] + 0.08 * f[3] - 0.5 * f[4] - 0.1 * f[5];
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

// one turn as a zero-sum matrix game: every joint action for each side, each cell averaged over the planning seeds
function solveTurn(b, cseeds) {
  const mine = jointOptions(b, b.sides[0]), theirs = jointOptions(b, b.sides[1]);
  const snap = JSON.stringify(b.toJSON());
  const A = mine.map(() => new Array(theirs.length).fill(0.5));
  for (let i = 0; i < mine.length; i++) for (let j = 0; j < theirs.length; j++) {
    let s = 0;
    for (const cs of cseeds) {
      const c = Battle.fromJSON(snap); c.prng = new PRNG(cs);
      if (!c.choose('p1', mine[i]) || !c.choose('p2', theirs[j])) { s = NaN; break; }
      s += value(c);
    }
    A[i][j] = s / cseeds.length;
  }
  // drop rows/columns the engine refused
  const okR = mine.map((_, i) => A[i].every(v => !Number.isNaN(v))), okC = theirs.map((_, j) => A.every((r, i) => !okR[i] || !Number.isNaN(r[j])));
  const R = mine.filter((_, i) => okR[i]), C = theirs.filter((_, j) => okC[j]);
  const M = A.filter((_, i) => okR[i]).map(r => r.filter((_, j) => okC[j]));
  if (!R.length || !C.length) return {R, C, M, x: null, y: null, v: null, snap};
  const [x, y] = nash(M);
  const v = M.reduce((t, row, a) => t + x[a] * row.reduce((u, w, c) => u + w * y[c], 0), 0);
  return {R, C, M, x, y, v, snap};
}

function playGame(mySets, thSets, g, K, log) {
  const b = start(mySets, thSets, seedmix(1e6 + g), K);
  let rs = seedmix(7e6 + g)[0] * 65536 + seedmix(7e6 + g)[1]; const rng = () => (rs = (rs * 1103515245 + 12345) % 2147483648) / 2147483648;
  const F = []; let turn = 1;
  for (; !b.ended && turn <= MAXTURN; turn++) {
    F.push(feats(b).map(v => +v.toFixed(3)));
    // each cell averages NS planning seeds, so chance (a repeated Protect, rolls, misses, crits) isn't fixed one way while planning
    const cseeds = Array.from({length: NS}, (_, k) => seedmix(3e6 + g * 50 + turn + 1e5 * k));
    const {R, C, M, x, y} = solveTurn(b, cseeds);
    if (process.env.EG_AUDIT && x) {
      const A = playGame.audit = playGame.audit || {};
      const acc = (side, L, p, pick) => {
        const seen = new Set();
        L.forEach((ch, k) => ch.split(', ').forEach((c, i) => {
          const mon = side.active[i]; if (!mon || !c.startsWith('move')) return;
          const mv = mon.moveSlots[+c.split(' ')[1] - 1]; if (!mv) return;
          const key = `${side.id}|${mon.set.species}|${mv.move}`; const e = A[key] = A[key] || [0, 0, 0];
          if (!seen.has(key)) { seen.add(key); e[0]++; }
          e[1] += p[k]; if (k === pick) e[2]++;
        }));
      };
      var auditPick = (i, j) => { acc(b.sides[0], R, x, i); acc(b.sides[1], C, y, j); };
    }
    if (log && log.snaps) log.snaps.push(b.toJSON());
    if (!R.length || !C.length) {                  // nothing the engine accepts (odd request state): let it choose
      for (const side of b.sides) if (!side.isChoiceDone()) side.autoChoose();
      if (b.allChoicesDone()) b.commitChoices(); else break;
      if (log) log.push(`T${turn} (engine default choices)`); continue;
    }
    if (process.env.EG_DEBUG && turn <= +process.env.EG_DEBUG) {      // each option's payoff against the other side's mix
      const rv = M.map(r => r.reduce((t, v, c) => t + v * y[c], 0)), cv = C.map((_, c) => M.reduce((t, r, a) => t + r[c] * x[a], 0));
      const show = (vals, L, side, mine) => vals.map((v, k) => [v, k]).sort((a, b) => mine ? b[0] - a[0] : a[0] - b[0]).slice(0, 8)
        .map(([v, k]) => `   ${(100 * v).toFixed(1)}  ${label(b, side, L[k])}`).join('\n');
      console.log(`T${turn} game value ${(100 * rv.reduce((t, v, a) => t + v * x[a], 0)).toFixed(1)}\n  my options vs their mix (higher is better for me):\n${show(rv, R, b.sides[0], true)}\n  their options vs my mix (lower is better for them):\n${show(cv, C, b.sides[1], false)}`);
    }
    let i = sample(x, rng); const j = sample(y, rng);
    if (process.env.EG_AUTOPILOT) { const a = R.indexOf(autoChoice(b, b.sides[0])); if (a >= 0) i = a; else (playGame.autoMiss = (playGame.autoMiss || 0) + 1); }
    if (process.env.EG_AUDIT && typeof auditPick === 'function') auditPick(i, j);
    if (log) {
      log.push(`T${turn} ${label(b, b.sides[0], R[i])}  ||  ${label(b, b.sides[1], C[j])}   [${R.length}x${C.length}, my mix top ${Math.max(...x).toFixed(2)}]`);
      const top = (p, L, side) => p.map((v, k) => [v, k]).sort((a, c) => c[0] - a[0]).filter(([v], n) => n < 4 && v >= 0.04).map(([v, k]) => [label(b, side, L[k]), +v.toFixed(2)]);
      (log.turns = log.turns || []).push({turn, my: top(x, R, b.sides[0]), th: top(y, C, b.sides[1]), myPick: label(b, b.sides[0], R[i]), thPick: label(b, b.sides[1], C[j]),
        value: +M.reduce((t, row, a) => t + x[a] * row.reduce((u, v, c) => u + v * y[c], 0), 0).toFixed(3), size: [R.length, C.length]});
    }
    b.choose('p1', R[i]); b.choose('p2', C[j]);
  }
  playGame.last = {turns: turn - 1, feats: F, ended: b.ended, winner: b.winner};
  if (log) log.full = b.log.slice();
  if (log) log.b = b.log.filter(l => /^\|(move|-damage|faint|-fieldend|-fieldstart|turn|-weather|-mega|win|-crit|-supereffective|-activate)\|/.test(l)).join('\n');
  return value(b);
}

function sets(arch, mine, theirs) {
  return [mine.map(n => T.toSet({...T.MY[n], species: T.MY[n].species})), theirs.map(sp => T.toSet(T.oppSet(arch, sp, [])))];
}
function matchup(arch, mine, theirs, games, K) {
  const [ms, ts] = sets(arch, mine, theirs); let s = 0; const vs = []; let fails = 0; const turns = []; const feats_ = [];
  for (let g = 0; g < games; g++) {
    // EG_KMIX: Trick Room-up matchups play their games with 2, 3, 3, 4 turns of it left (25/50/25: set on turn 1 or 2, back in on turn 3 or 4)
    const Kg = process.env.EG_KMIX && K > 0 ? [2, 3, 3, 4][g % 4] : K;
    let v; try { v = playGame(ms, ts, g, Kg); } catch (e) { fails++; console.error(`game ${g} failed: ${e.message}`); continue; }
    s += v; vs.push(+v.toFixed(3)); turns.push(playGame.last.turns);
    if (process.env.EG_FEATS) feats_.push({v, F: playGame.last.feats}); }
  const out = {arch, mine, theirs, K, games: vs.length, fails, v: vs.length ? s / vs.length : null, vs, turns};
  if (process.env.EG_FEATS) out.feats = feats_;
  if (process.env.EG_AUDIT) { out.audit = playGame.audit || {}; playGame.audit = {}; }
  return out;
}
function matchupSets(ms, ts, games, K, meta) {
  let s = 0; const vs = []; const turns = []; let fails = 0;
  for (let g = 0; g < games; g++) {
    const Kg = process.env.EG_KMIX && K > 0 ? [2, 3, 3, 4][g % 4] : K;
    let v; try { v = playGame(ms, ts, g, Kg); } catch (e) { fails++; console.error(`game ${g} failed: ${e.message}`); continue; }
    s += v; vs.push(+v.toFixed(3)); turns.push(playGame.last.turns); }
  return {...meta, K, games: vs.length, fails, v: vs.length ? s / vs.length : null, vs, turns, autoMiss: playGame.autoMiss || 0};
}
module.exports = {matchupSets, matchup, playGame, sets, solveTurn, nash, label, value, feats, seedmix, Battle, PRNG};

if (require.main === module) {
  const [arch, m, t, games = '4', K = '3'] = process.argv.slice(2);
  const [ms, ts] = sets(arch, m.split(','), t.split(','));
  const t0 = Date.now(); let s = 0;
  for (let g = 0; g < +games; g++) { const log = []; const v = playGame(ms, ts, g, +K, log); s += v;
    console.log(`game ${g}: ${v.toFixed(2)}\n  ` + log.join('\n  ')); if (process.env.SHOWLOG) console.log(log.b); }
  console.log(`mean ${(s / +games).toFixed(3)}  ${((Date.now() - t0) / 1000).toFixed(1)}s`);
}
