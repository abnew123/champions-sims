"""egvalue10 (2026-10-07): the position value refitted on REAL positions (cached ladder Bo3 games with open sheets, every turn rebuilt by
Eval bar's position builder, both sides' brought four and sets known) with champ-battle-v21's 25 features (`champ feats` with RACE=1
RACE_PRIO=1 FEATS21=1). human_lines.py found the sym2 value misrating positions after priority attacks (+10), speed control (+12),
pivots (-7) and with screens (-13), and Sun sides 7 points too high / Snow and Trick Room 6-8 too low; this fit adds the features for
those and refits the rest on real outcomes. Symmetric (every position also mirrored, intercept 0), weights shrunk toward sym2's (new
features toward 0) by a small ridge; weights sym2 hand-set stay fixed unless FREE_ALL=1.
  ../.venv/bin/python3 build_egvalue10.py <feats_fit.jsonl> <feats_hold.jsonl> <out.json> [ridge=1.0]
Reports held-out log loss (static value, per position; by game for the SE) of sym2's static value, the 20-feature refit and the 25-feature
refit, each with its own rescale (log-odds x c fitted on the fit set), and the held-out rating bias by team style (opp_pool.json groups).
Outcomes from replays_protect/<id>.log (names only compared, never kept)."""
import json, os, sys, math, collections, random
import numpy as np
from scipy.optimize import minimize
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from human_lines import winner
HERE = os.path.dirname(os.path.abspath(__file__))
NAMES21 = ['priority edge', 'speed stages', 'stat drops', 'weather turns x benefit', 'Taunted']
NAMES22 = ['Trick Room potential', 'Tailwind potential', 'bench edge']
NAMES23 = ['race: support edge']
# RACE_SUPPORT=classes (39 features: 28 + one per support class, no single support edge): side difference of the race units with the class usable
NAMES24 = ['support: ' + x for x in ('Fake Out (fresh)', 'Follow Me / Rage Powder', 'Tailwind (down, slower)', 'Trick Room (down, slower)', 'screens (down)', 'Parting Shot', 'Helping Hand', 'Wide Guard', 'sleep move', 'Will-O-Wisp / Thunder Wave', 'Taunt / Encore')]
def load(f):
    rows = []; wins = {}
    for l in open(f):
        r = json.loads(l)
        if 'error' in r: continue
        gid = r['name'].split(' ')[0]
        if gid not in wins: wins[gid] = winner(gid)
        if wins[gid] is None: continue
        rows.append((gid, r['turn'], np.array(r['feats'], float), 1.0 if wins[gid] == 'p1' else 0.0, r['static']))
    return rows
def fit(X, y, w0, fixed, ridge, shared=(), shrink=0.0):
    """symmetric logistic regression: minimise log loss over the positions and their mirrors (-X, 1-y), no intercept, ridge toward w0;
    `shared`: columns shrunk toward their common mean with weight `shrink` (per mean log loss, not divided by n): the support classes"""
    Xs = np.vstack([X, -X]); ys = np.concatenate([y, 1 - y]); n = len(ys)
    free = np.array([i for i in range(X.shape[1]) if i not in fixed])
    sh = np.array([i for i in shared if i in free], int)
    def unpack(p): w = w0.copy(); w[free] = p; return w
    def f(p):
        w = unpack(p); z = Xs @ w; z = np.clip(z, -30, 30)
        ll = np.mean(np.logaddexp(0, -z) * ys + np.logaddexp(0, z) * (1 - ys))
        g = (Xs.T @ (1 / (1 + np.exp(-z)) - ys)) / n
        pen = ridge * np.sum((w[free] - w0[free]) ** 2) / n; gpen = 2 * ridge * (w[free] - w0[free]) / n
        if len(sh) and shrink > 0:
            d = w[sh] - w[sh].mean(); pen += shrink * np.sum(d ** 2); gs = np.zeros(len(w)); gs[sh] = 2 * shrink * d
            gpen = gpen + gs[free]
        return ll + pen, g[free] + gpen
    r = minimize(f, w0[free], jac=True, method='L-BFGS-B')
    return unpack(r.x)
def rescale(z, y):
    """c minimising log loss of sigmoid(c z)"""
    def f(c): zz = np.clip(c[0] * z, -30, 30); return np.mean(np.logaddexp(0, -zz) * y + np.logaddexp(0, zz) * (1 - y))
    return minimize(f, [1.0], method='Nelder-Mead').x[0]
def logloss(z, y, games):
    zz = np.clip(z, -30, 30); l = np.logaddexp(0, -zz) * y + np.logaddexp(0, zz) * (1 - y)
    byg = collections.defaultdict(list)
    for g, v in zip(games, l): byg[g].append(v)
    keys = list(byg); rnd = random.Random(5); ms = []
    for _ in range(200):
        flat = [x for k in [rnd.choice(keys) for _ in keys] for x in byg[k]]; ms.append(np.mean(flat))
    return float(np.mean(l)), float(np.std(ms))
def team_bias(z, y, games, pool_groups):
    """actual - rated, both sides, by the side's team archetype (positions, games, mean, SE by game)"""
    p = 1 / (1 + np.exp(-np.clip(z, -30, 30))); out = {}
    for key in ('arch', 'group'):
        byg = collections.defaultdict(lambda: collections.defaultdict(list))
        for g, pi, yi in zip(games, p, y):
            e = pool_groups.get(g)
            if not e: continue
            byg[e['p1'][key]][g].append(yi - pi); byg[e['p2'][key]][g].append((1 - yi) - (1 - pi))
        res = []
        for name, bg in byg.items():
            l = [x for v in bg.values() for x in v]
            if len(bg) < 8: continue
            keys = list(bg); rnd = random.Random(3); ms = []
            for _ in range(200): flat = [x for k in [rnd.choice(keys) for _ in keys] for x in bg[k]]; ms.append(np.mean(flat))
            res.append({'team': name, 'positions': len(l), 'games': len(bg), 'bias': float(np.mean(l)), 'se': float(np.std(ms))})
        out[key] = sorted(res, key=lambda r: -r['positions'])
    return out
def main(fitf, holdf, outf, ridge):
    sym2 = json.load(open(os.path.join(HERE, 'egvalue9_sym2.json')))
    names = sym2['names'][:20] + NAMES21 + NAMES22 + NAMES23
    fit_rows = load(fitf); hold_rows = load(holdf)
    print(f"fit: {len(fit_rows)} positions, {len(set(r[0] for r in fit_rows))} games; held out: {len(hold_rows)} positions, {len(set(r[0] for r in hold_rows))} games")
    X = np.array([r[2] for r in fit_rows]); y = np.array([r[3] for r in fit_rows]); G = [r[0] for r in fit_rows]
    Xh = np.array([r[2] for r in hold_rows]); yh = np.array([r[3] for r in hold_rows]); Gh = [r[0] for r in hold_rows]
    nf = X.shape[1]; assert nf in (25, 28, 29, 39), nf
    if nf == 39: names = sym2['names'][:20] + NAMES21 + NAMES22 + NAMES24
    names = names[:nf]
    shared = list(range(28, 39)) if nf == 39 else []; shrink = float(os.environ.get('CLASS_SHRINK', '0'))
    w0 = np.zeros(nf); w0[:20] = sym2['w']
    fixed = set() if os.environ.get('FREE_ALL') else {sym2['names'].index(k) for k in sym2['hand_set']}
    fixed |= {6, 7}   # grid features: always 0 here
    pool = json.load(open(os.path.join(HERE, 'opp_pool.json')))
    pg = collections.defaultdict(dict)
    for e in pool['entries']: pg[e['id']][e['side']] = {'arch': e.get('arch'), 'group': e.get('group')}
    pg = {k: v for k, v in pg.items() if 'p1' in v and 'p2' in v}
    report = {}
    models = {'sym2 static (as is)': (w0.copy(), slice(0, 20)), '20 features refit': (None, slice(0, 20)), '25 features refit': (None, slice(0, 25))}
    if nf >= 28: models['28 features refit'] = (None, slice(0, 28))
    if nf == 29: models['29 features refit'] = (None, slice(0, 29))
    if nf == 39: models['39 features refit'] = (None, slice(0, 39))
    last = f'{nf} features refit'
    out_w = None
    for label, (w, sl) in models.items():
        cols = list(range(nf))[sl]
        if w is None:
            fx = set(i for i in fixed if i in cols)
            wf = fit(X[:, cols], y, w0[cols], fx, ridge, [i for i in shared if i in cols], shrink); w = np.zeros(nf); w[cols] = wf
        z = X @ w; c = rescale(z, y)
        zh = Xh @ w
        ll_raw = logloss(zh, yh, Gh); ll = logloss(c * zh, yh, Gh)
        tb = team_bias(c * zh, yh, Gh, pg)
        report[label] = {'w': [float(x) for x in w], 'rescale': float(c), 'holdout_logloss_raw': ll_raw, 'holdout_logloss_rescaled': ll, 'team_bias': tb}
        print(f"\n== {label}: rescale {c:.3f}; held-out log loss raw {ll_raw[0]:.4f}, rescaled {ll[0]:.4f} ± {ll[1]:.4f}")
        for i in cols:
            if w[i] != 0 or i >= 20: print(f"   {w[i]:+.3f}  {names[i]}" + ("  (fixed)" if i in fixed else "") + (f"  (sym2 {w0[i]:+.3f})" if i < 20 and abs(w[i] - w0[i]) > 1e-9 else ""))
        print("   bias by archetype (actual - rated, points):", ", ".join(f"{t['team']} {100 * t['bias']:+.1f}±{100 * t['se']:.1f}" for t in tb['arch']))
        if label == last: out_w = w
        if label == last and nf == 39:
            # identifiability: bootstrap by game (40 resamples) the class weights; also each class's credit in KO-edge units
            keys = sorted(set(G)); byg = collections.defaultdict(list)
            for i, g in enumerate(G): byg[g].append(i)
            rnd = random.Random(11); boots = []
            for _ in range(int(os.environ.get('BOOTS', '40'))):
                idx = np.array([i for k in [rnd.choice(keys) for _ in keys] for i in byg[k]])
                boots.append(fit(X[idx], y[idx], w0, fixed, ridge, shared, shrink))
            B = np.array(boots); se = B.std(axis=0); ko = w[names.index('race: KO edge')]
            print(f"   class weights (bootstrap SE by game, {len(boots)} resamples); credit in KO-edge units = weight / KO-edge weight {ko:+.3f}:")
            for i in shared:
                nz = int(np.sum(X[:, i] != 0))
                print(f"     {w[i]:+.3f} ± {se[i]:.3f}  {names[i]:38s} {nz:6d} positions; credit {w[i] / ko:+.2f} ± {se[i] / abs(ko):.2f} KO")
            report[label]['class_se'] = {names[i]: float(se[i]) for i in shared}; report[label]['ko_weight'] = float(ko)
    json.dump({'b0': 0.0, 'w': [float(x) for x in out_w], 'names': names, 'hand_set': {} if os.environ.get('FREE_ALL') else sym2['hand_set'],
               'rescale': report[last]['rescale'], 'ridge': ridge,
               'note': 'egvalue10: symmetric value refitted on real ladder positions (every turn of the cached Bo3 games outside the eval bar\'s 560 held-out games) with champ-battle-v21\'s features (25: FEATS21; 28: FEATS22). Use with RACE=1 RACE_PRIO=1 FEATS21=1 (or FEATS22=1) CALC_DATA=... TRSYM=1 and an empty GRID_DIR. The eval bar rescales its one-turn value separately.'},
              open(outf, 'w'), indent=1)
    os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
    json.dump(report, open(os.path.join(HERE, 'results', 'egvalue10_fit.json'), 'w'), indent=1)
if __name__ == '__main__':
    a = sys.argv[1:]; main(a[0], a[1], a[2], float(a[3]) if len(a) > 3 else 1.0)
