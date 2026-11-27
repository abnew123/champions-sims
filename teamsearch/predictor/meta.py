"""Meta estimate with the matchup predictor (the user, 2026-11-27: play many teams against each other with the predictor to estimate
the M-D meta once it is live), and its backtest on M-B and M-C.

Given every game up to a date: fit the predictor on them; the pool is every six seen so far (grouped by species, set details
averaged), weighted by how many players brought it (one vote per player, as backtest/compare.py counts usage); then replicator
dynamics on the predicted win chances: each step, x_i <- x_i * exp(eta * (win share of i against the field - the field's mean)).
A team's formes (Megas apart) give the predicted usage. Two readings: the pool's own usage after the steps ("pool"), and the
usage seen so far plus the pool's change ("seen + shift"; the pool leaves out sixes seen once, and this keeps them).
Backtest: from what was known on a date, predict a later window's real usage, against "seen so far carries over". Scores as
backtest/compare.py: rank correlation over formes at >= 2% and total variation distance (lower is closer).
  M-B: known up to Aug 25 -> real Sep 5-8 (our M-B replays start Aug 19; Sep 1-4 holds the out-of-format window, left out)
  M-C: known up to Oct 6 and up to Oct 13 -> real "settled" window Oct 14 - Nov 6 (backtest/mc_truth.json)
The number of steps is read off M-B and then applied to M-C, so M-C is a fair test.
  teamsearch/bin/teamsearch-py predictor/meta.py backtest [--ladder-only]   -> predictor/meta_backtest.json, lines in predictor.log
"""
import os, sys, json, math, time, datetime, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M
TS = os.path.dirname(M.HERE); sys.path.insert(0, TS); sys.path.insert(0, os.path.join(TS, 'backtest')); sys.path.insert(0, os.path.join(M.ROOT, 'pssim'))
import sets_lib as L
from compare import usage, score
OUT = os.path.join(M.HERE, 'meta_backtest.json')
STEPS = (0, 2, 5, 10, 20, 40, 80, 160)
ETA = 1.0
CHOSEN = 5           # read off the M-B case (Nov 27 backtest: best there; long runs drift away from the real meta in every case)
day = lambda t: datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d')

def formes(six, sets):
    by = {M.idf(s['species']): s for s in (sets or [])}
    return [L.battle_forme(x, (by.get(M.idf(x)) or {}).get('item')) for x in six]

def sides(meta, rows, reg, lo, hi, src=None):
    """[(player, six key, Team, formes)] for every sheet of `reg` played between day lo and day hi (inclusive); src: 'ladder' /
    'online' / None for both"""
    out = []
    for g, (A, B, *_) in zip(meta, rows):
        if g['reg'] != reg or not (lo <= day(g['t']) <= hi) or (src and g['src'] != src): continue
        out.append((g['p1'], tuple(sorted(A.sp)), A, formes(g['six1'], g['sets1'])))
        out.append((g['p2'], tuple(sorted(B.sp)), B, formes(g['six2'], g['sets2'])))
    return out

def pool(sd, min_players=2):
    """groups of sheets by six, the weight of each (one vote per player), and each group's forme shares"""
    per = collections.defaultdict(list)
    for p, k, T, f in sd: per[p].append((k, T, f))
    w, insts, players = collections.Counter(), collections.defaultdict(list), collections.defaultdict(set)
    for p, L_ in per.items():
        for k, T, f in L_: w[k] += 1 / len(L_) / len(per); insts[k].append((T, f)); players[k].add(p)
    keys = [k for k in w if len(players[k]) >= min_players]
    groups = [[T for T, _ in insts[k]] for k in keys]
    F = []
    for k in keys:
        c = collections.Counter(f for _, fs in insts[k] for f in set(fs)); F.append({f: n / len(insts[k]) for f, n in c.items()})
    x0 = np.array([w[k] for k in keys]); return keys, groups, F, x0 / x0.sum(), float(x0.sum())

def replicate(P, x0, steps=STEPS, eta=ETA):
    x = x0.copy(); out = {0: x.copy()}; s = 0
    for target in steps[1:]:
        while s < target:
            f = P @ x; x = x * np.exp(eta * (f - x @ f)); x /= x.sum(); s += 1
        out[target] = x.copy()
    return out

def use_of(x, F):
    u = collections.Counter()
    for xi, Fi in zip(x, F):
        for f, v in Fi.items(): u[f] += xi * v
    return dict(u)

def predict(rows, y, meta, reg, known_lo, known_hi, lam):
    """fit on every game up to known_hi (ladder and, when loaded, online tournaments: they predict both better, evaluate.py
    online); pool = `reg` ladder sheets in [known_lo, known_hi]; returns readings by step"""
    fit = [i for i, g in enumerate(meta) if day(g['t']) <= known_hi]
    m = M.Model(lam, use=('sp', 'tok', 'attr', 'pair', 'tpair', 'pl', 'rat')).fit([rows[i] for i in fit], y[fit])
    sd = sides(meta, rows, reg, known_lo, known_hi, 'ladder'); seen, _ = usage([(p, f) for p, _, _, f in sd])
    keys, groups, F, x0, cover = pool(sd)
    Z = M.Pool(m, groups).logits(); P = 1 / (1 + np.exp(-Z))
    xs = replicate(P, x0); base = use_of(x0, F)
    pred = {}
    for s, x in xs.items():
        u = use_of(x, F)
        pred[s] = dict(pool=u, shift={f: max(0.0, seen.get(f, 0) + u.get(f, 0) - base.get(f, 0)) for f in set(seen) | set(u)})
    return dict(fit_games=len(fit), sheets=len(sd), pool=len(keys), cover=cover, seen=seen, pred=pred, m=m, keys=keys, xs=xs, F=F)

def backtest():
    srcs = ('ladder',) + (('online',) if '--ladder-only' not in sys.argv else ())
    rows, y, meta = M.load(lambda g: g['src'] in srcs); lam = json.load(open(os.path.join(M.HERE, 'lambdas.json')))
    J = dict(fit_on='+'.join(srcs))
    M.say(f"meta backtest: the predictor fitted on {' and '.join(srcs)} games")
    cases = [('M-B: known to Aug 25, real Sep 5-8', 'M-B', ('2026-08-01', '2026-08-25'), ('2026-09-05', '2026-09-08')),
             ('M-C: known to Oct 6, real settled', 'M-C', ('2026-09-09', '2026-10-06'), ('2026-10-14', '2026-11-06')),
             ('M-C: known to Oct 13, real settled', 'M-C', ('2026-09-09', '2026-10-13'), ('2026-10-14', '2026-11-06'))]
    for name, reg, (klo, khi), (rlo, rhi) in cases:
        t0 = time.time(); r = predict(rows, y, meta, reg, klo, khi, lam)
        real, n = usage([(p, f) for p, _, _, f in sides(meta, rows, reg, rlo, rhi, 'ladder')])
        res = dict(fit_games=r['fit_games'], sheets=r['sheets'], pool=r['pool'], cover=r['cover'], real_players=n,
                   carried=score(r['seen'], real), steps={s: dict(pool=score(v['pool'], real), shift=score(v['shift'], real)) for s, v in r['pred'].items()})
        J[name] = res
        M.say(f"meta backtest {name}: fit on {r['fit_games']} games; pool {r['pool']} sixes seen by 2+ players ({100 * r['cover']:.0f}% of the votes);"
              f" real {n} players; seen so far carried over: rank corr {res['carried']['spearman']:.2f} / distance {res['carried']['tv']:.2f}  ({round(time.time() - t0)} s)")
        for s, v in res['steps'].items():
            M.say(f"    {s:4d} steps: pool {v['pool']['spearman']:.2f} / {v['pool']['tv']:.2f}   seen + shift {v['shift']['spearman']:.2f} / {v['shift']['tv']:.2f}")
        pc = r['pred'][CHOSEN]['shift']
        mv = sorted(((f, r['seen'].get(f, 0), pc.get(f, 0), real.get(f, 0)) for f in set(r['seen']) | set(real)
                     if max(r['seen'].get(f, 0), real.get(f, 0)) >= 0.05), key=lambda t: -abs(t[2] - t[1]))
        J[name]['movers'] = mv
        right = sum(1 for f, a, b, c in mv if abs(b - a) >= 0.005 and (b - a) * (c - a) > 0); called = sum(1 for f, a, b, c in mv if abs(b - a) >= 0.005)
        M.say(f"    at {CHOSEN} steps: the {called} formes it moves by half a point or more (of those at 5%+ seen or real) moved the same way in reality for {right};"
              f" biggest calls: " + ', '.join(f"{f} {100 * a:.0f}->{100 * b:.0f} (real {100 * c:.0f})" for f, a, b, c in mv[:6]))
        json.dump(J, open(OUT, 'w'), indent=1)
    M.say("meta backtest done")

if __name__ == '__main__':
    if sys.argv[1:2] == ['backtest']: backtest()
