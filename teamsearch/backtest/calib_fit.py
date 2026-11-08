"""M-B calibration fit (the user, 2026-11-07: goal 1, the meta estimate, calibrates the sim on real outcomes, player errors included; M-B
data only). Reads calib_mb.jsonl (v41n1) and calib_mb_v43.jsonl (v43n1, the games whose fours carry a v43 mechanic; a game's v43 line
replaces its v41 line). Leaves out the Sep 1-4 games whose sheets carry anything seen only on those days (out-of-format sheets the M-B
ladder let through) and games without sim games.
Models of side p1's real result, weighted logistic regression with L2 (no intercept: every term flips sign with the sides):
  coin          0.5
  raw sim       the sim's share of p1 wins over its 12 games, (w + 0.5) / (n + 1)
  slope         b * logit(raw sim)
  + traits      + p1 - p2 generic trait differences (Trick Room, Tailwind, Perish, Fake Out, redirection, screens, Intimidate, terrain,
                Megas, each weather; mean base Speed)
  + type pairs  + one term per pair of generic team types (+1 when p1 is the first type, -1 when p2 is)
  no sim        traits and type pairs without the sim
Weights: inverse sampling (each type pair's usable games / its sampled games), so the scores estimate the whole usable M-B ladder.
Scores: log loss under 10-fold cross-validation grouped by player pair (a Bo3's games stay together), L2 strength picked inside each
training fold by the same grouped CV; paired differences with standard errors. Then the full-data fit's coefficients and, per type
pair, real against sim win rates: real from all usable M-B games of the pair (no sim needed), the sim from the sampled ones.
  bin/teamsearch-py backtest/calib_fit.py          -> report on stdout, calib_fit.json
"""
import json, os, sys, math, collections, random
import numpy as np
from scipy.optimize import minimize
HERE = os.path.dirname(os.path.abspath(__file__)); TS = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, TS); sys.path.insert(0, os.path.join(TS, '..', 'pssim'))
os.environ.setdefault('TS_MOVESET', os.path.join('backtest', 'smogon_mb_2026-08_moveset.txt'))
import sets_lib as L
import calib_mb as CM
TRAITS = ['tr', 'tailwind', 'perish', 'fakeout', 'redirect', 'screens', 'intimidate', 'terrain', 'mega', 'sun', 'rain', 'sand', 'snow', 'speed']
TYPES = ['Trick Room', 'Perish', 'Rain', 'Sun', 'Sand', 'Snow', 'Tailwind', 'Other']
PAIRS = [(a, b) for i, a in enumerate(TYPES) for b in TYPES[i + 1:]]
LAMS = [0.1, 1, 3, 10, 30, 100, 300]

def window_games():
    """game ids from Sep 1-4 whose sheets carry a forme, item, ability or move seen only on those days"""
    P = json.load(open(os.path.join(HERE, 'mb_pool.json')))['entries']
    W = lambda d: '2026-09-01' <= d <= '2026-09-04'
    def things(s):
        s = L.normalize(s); yield 'forme', L.battle_forme(s['species'], s.get('item'))
        for k in ('item', 'ability'):
            if s.get(k): yield k, s[k]
        for m in s.get('moves') or []: yield 'move', m
    seen_out, inw = set(), collections.defaultdict(set)
    for e in P:
        for s in e['six']:
            for t in things(s):
                if W(e['day']): inw[t].add(e['id'])
                else: seen_out.add(t)
    return set().union(*(g for t, g in inw.items() if t not in seen_out))

def load():
    rows = {}
    for f in ('calib_mb.jsonl', 'calib_mb_v43.jsonl'):                  # v43 last: its line replaces the v41 one
        for l in open(os.path.join(HERE, f)): r = json.loads(l); r['engine'] = f; rows[r['id']] = r
    return rows

def features(r, kind):
    s = r['sim']; w, n = s['p1_wins'] + (s['p2_n'] - s['p2_wins']), s['p1_n'] + s['p2_n']
    p = (w + 0.5) / (n + 1); x = []
    if kind in ('slope', 'traits', 'full'): x.append(math.log(p / (1 - p)))
    if kind in ('traits', 'full', 'nosim'):
        t1, t2 = r['traits']['p1'], r['traits']['p2']
        x += [((t1.get(k) or 0) - (t2.get(k) or 0)) / (10 if k == 'speed' else 1) for k in TRAITS]
    if kind in ('full', 'nosim'):
        a, b = r['types']['p1'], r['types']['p2']
        x += [(a == u and b == v) - (a == v and b == u) for u, v in PAIRS]
    return x, p

def fit(X, y, w, lam, free0):
    """weighted logistic regression, no intercept; L2 lam on every coefficient but the sim slope (column 0 when free0)"""
    m = np.ones(X.shape[1]); m[0] = 0.0 if free0 else 1.0
    def f(b):
        z = X @ b; ll = w * (np.logaddexp(0, z) - y * z)
        return ll.sum() + 0.5 * lam * ((m * b) @ b), X.T @ (w * (1 / (1 + np.exp(-z)) - y)) + lam * m * b
    return minimize(f, np.zeros(X.shape[1]), jac=True, method='L-BFGS-B').x

def logloss(p, y): p = np.clip(p, 1e-6, 1 - 1e-6); return -(y * np.log(p) + (1 - y) * np.log(1 - p))

def folds(groups, k, seed):
    g = sorted(set(groups)); random.Random(seed).shuffle(g); fo = {x: i % k for i, x in enumerate(g)}
    return np.array([fo[x] for x in groups])

def cv_pred(X, y, w, groups, free0, k=10, seed=0):
    """out-of-fold predictions; lam chosen per training fold by an inner grouped CV"""
    F = folds(groups, k, seed); pred = np.zeros(len(y)); lams = []
    for i in range(k):
        tr, te = F != i, F == i
        gi = [g for g, t in zip(groups, tr) if t]; Fi = folds(gi, 5, seed + 1 + i)
        best = None
        for lam in LAMS:
            ll = 0.0
            for j in range(5):
                a, b = Fi != j, Fi == j
                beta = fit(X[tr][a], y[tr][a], w[tr][a], lam, free0)
                ll += (w[tr][b] * logloss(1 / (1 + np.exp(-X[tr][b] @ beta)), y[tr][b])).sum()
            if best is None or ll < best[0]: best = (ll, lam)
        lams.append(best[1]); beta = fit(X[tr], y[tr], w[tr], best[1], free0)
        pred[te] = 1 / (1 + np.exp(-X[te] @ beta))
    return pred, lams

def main():
    rows = load(); win = window_games()
    G, full = CM.games(); pick, strata, cap = CM.sample(G, 2500)
    tot = collections.Counter(' vs '.join(sorted((CM.type_of(CM.traits(sd['p1']['six'])), CM.type_of(CM.traits(sd['p2']['six']))))) for _, sd in G)
    wt = {k: tot[k] / v for k, v in strata.items() if v}
    keep = [r for r in rows.values() if r['id'] not in win and r['sim']['p1_n'] + r['sim']['p2_n'] > 0]
    out = dict(games=len(keep), window_left_out=sum(r in win for r in rows), no_sim=sum(1 for r in rows.values() if r['sim']['p1_n'] + r['sim']['p2_n'] == 0),
               on_v43=sum(r['engine'].endswith('_v43.jsonl') for r in keep))
    y = np.array([float(r['won_p1']) for r in keep]); w = np.array([wt[' vs '.join(sorted((r['types']['p1'], r['types']['p2'])))] for r in keep])
    w = w / w.mean(); groups = [tuple(sorted(r['players'])) for r in keep]
    print(f"{out['games']} M-B games ({out['on_v43']} on v43; {out['window_left_out']} Sep 1-4 out-of-format games and {out['no_sim']} without "
          f"sim games left out), {len(set(groups))} player pairs; p1 won {100 * (w * y).sum() / w.sum():.1f}% (weighted)")
    preds = {'coin': np.full(len(y), 0.5), 'raw sim': np.array([features(r, 'raw')[1] for r in keep])}
    names = {'slope': 'slope', 'traits': '+ traits', 'full': '+ type pairs', 'nosim': 'no sim'}
    Xs, lam_used = {}, {}
    for kind, nm in names.items():
        Xs[kind] = np.array([features(r, kind)[0] for r in keep], dtype=float)
        preds[nm], lam_used[nm] = cv_pred(Xs[kind], y, w, groups, kind != 'nosim')
    ll = {n: w * logloss(p, y) for n, p in preds.items()}; W = w.sum()
    print('\nlog loss per game, cross-validated, weighted (lower is better); differences paired, +- one standard error:')
    print(f"  {'model':14s} {'log loss':>9s} {'vs coin':>16s} {'vs raw sim':>16s}  L2 picked")
    out['scores'] = {}
    for n in preds:
        m = ll[n].sum() / W; dc = ll[n] - ll['coin']; dr = ll[n] - ll['raw sim']
        sc = lambda d: (d.sum() / W, math.sqrt((w * (d / w - d.sum() / W) ** 2).sum() / W / (len(d) - 1)))
        (a, sa), (b, sb) = sc(dc), sc(dr)
        out['scores'][n] = dict(logloss=round(m, 4), vs_coin=[round(a, 4), round(sa, 4)], vs_raw=[round(b, 4), round(sb, 4)], lams=lam_used.get(n))
        print(f"  {n:14s} {m:9.4f} {a:+8.4f} +- {sa:.4f} {b:+8.4f} +- {sb:.4f}  {', '.join(map(str, lam_used.get(n) or [])) if n in lam_used else ''}")
    # full-data fit of the type-pair model, its lam the most common pick
    lam = collections.Counter(lam_used['+ type pairs']).most_common(1)[0][0]; beta = fit(Xs['full'], y, w, lam, True)
    labels = ['logit(sim)'] + [f'{k} diff' for k in TRAITS] + [f'{a} vs {b}' for a, b in PAIRS]
    out['coef'] = {l: round(float(b), 3) for l, b in zip(labels, beta)}
    print(f"\nfull-data fit (+ type pairs, L2 {lam}): sim slope {beta[0]:.3f} (1 = trust the sim's odds as they are, 0 = ignore them)")
    print('  traits (log-odds per unit of p1 - p2; Speed per 10 base points): ' + ', '.join(f"{k} {b:+.2f}" for k, b in zip(TRAITS, beta[1:15])))
    allg = collections.defaultdict(list)                                  # real results of every usable game, as the first type of the pair
    for gid, sd in G:
        if gid in win: continue
        t1, t2 = CM.type_of(CM.traits(sd['p1']['six'])), CM.type_of(CM.traits(sd['p2']['six']))
        if t1 != t2: allg[(t1, t2) if TYPES.index(t1) < TYPES.index(t2) else (t2, t1)].append(float(bool(sd['p1']['won'])) if TYPES.index(t1) < TYPES.index(t2) else 1.0 - bool(sd['p1']['won']))
    print('\nper type pair: the first type\'s real win rate (all usable M-B games of the pair) against the sim\'s (sampled games, weighted);')
    print('real - sim +- one standard error; the model\'s term at equal sim and traits')
    out['pairs'] = {}
    for (a, b), c in zip(PAIRS, beta[15:]):
        idx = [i for i, r in enumerate(keep) if {r['types']['p1'], r['types']['p2']} == {a, b}]
        if not idx: continue
        sgn = np.array([1.0 if keep[i]['types']['p1'] == a else -1.0 for i in idx]); yy = np.where(sgn > 0, y[idx], 1 - y[idx])
        ps = np.where(sgn > 0, preds['raw sim'][idx], 1 - preds['raw sim'][idx]); ww = w[idx]
        sim = (ww * ps).sum() / ww.sum(); ra = allg[(a, b)]; real = sum(ra) / len(ra)
        sd_ = math.sqrt(real * (1 - real) / len(ra) + (ww * (ps - sim) ** 2).sum() / ww.sum() / len(idx))
        out['pairs'][f'{a} vs {b}'] = dict(n_sim=len(idx), n_real=len(ra), real=round(real, 3), sim=round(sim, 3), se=round(sd_, 3), term=round(float(c), 3))
        print(f"  {a + ' vs ' + b:22s} real {100 * real:5.1f}% ({len(ra):4d} games)   sim {100 * sim:5.1f}% ({len(idx):2d})   "
              f"{100 * (real - sim):+5.1f} +- {100 * sd_:.1f}{' *' if abs(real - sim) > 2 * sd_ else '  '}   term {c:+.2f}")
    json.dump(out, open(os.path.join(HERE, 'calib_fit.json'), 'w'), indent=1)

if __name__ == '__main__': main()
