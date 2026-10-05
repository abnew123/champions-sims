"""Multi-team value fit (2026-10-05): the same model as build_egvalue8.py (status / Tailwind tied to the HP weight at real-game ratios,
hand-set features fixed) fitted on self-play from several teams: the TR six (results/refit8) and Team search's ten comparison teams
(BATTLE_FEATS output folders, one per team). Compares: TR six only, the other teams only, pooled with one intercept, and pooled with one
intercept per team (shared slopes); each model's 5-fold log loss on each group (game-level folds); the weights side by side.
SPLIT_TR=1 gives Trick Room two weights: turns x speed edge when it favours side 0, and when it favours side 1 (needs a planner that
computes that feature; analysis only until then).
usage: ../.venv/bin/python3 build_egvalue9.py <TR six dir> <@file listing the other teams' dirs> [out.json: writes the pooled fit]
env: W_TR=<share of the total weight given to the TR six's games, default: by game count>"""
import json, glob, sys, os, numpy as np
e7 = json.load(open('egvalue7.json')); R = json.load(open('results/fit_real_value.json')); real = dict(zip(R['names'], R['real'][1:]))
HAND = [4, 5, 8, 16, 17]; TIED = {11: 'slp', 12: 'par', 13: 'brn', 14: 'tw'}; ratio = {i: real[k] / real['hp'] for i, k in TIED.items()}
FREE = [1, 2, 3, 6, 7, 9, 10, 15, 18, 19]; SPLIT = bool(os.environ.get('SPLIT_TR'))
names = e7['names']
def load(ds):
    X, y, G, T = [], [], [], []
    for d in ds:
        for f in glob.glob(d + '/*.json'):
            try: r = json.load(open(f))
            except Exception: continue
            for k, g in enumerate(r.get('feats') or []):
                if g['v'] not in (0, 1): continue
                for fx in g['F']:
                    if len(fx) >= 20: X.append(fx[:20]); y.append(g['v']); G.append(f'{f}:{k}'); T.append(d)
    return np.array(X, float), np.array(y, float), np.array(G), np.array(T)
tr_dir = sys.argv[1]; others = [l.strip() for l in open(sys.argv[2][1:]) if l.strip()]
Xa, ya, Ga, Ta = load([tr_dir]); Xb, yb, Gb, Tb = load(others)
X = np.vstack([Xa, Xb]); y = np.r_[ya, yb]; G = np.r_[Ga, Gb]; T = np.r_[Ta, Tb]; isA = np.r_[np.ones(len(ya), bool), np.zeros(len(yb), bool)]
teams = [tr_dir] + others; tid = np.array([teams.index(t) for t in T])
def design(X):
    comp = X[:, 0] + sum(ratio[i] * X[:, i] for i in TIED)
    cols = [comp] + [X[:, i] for i in FREE]; labels = ['HP share (+ tied status / Tailwind)'] + [names[i] if i < 18 else ('race: KO edge', 'race: HP edge')[i - 18] for i in FREE]
    if SPLIT:
        k = 1 + FREE.index(3); cols[k] = np.maximum(X[:, 3], 0); labels[k] = 'Trick Room x speed, favouring side 0'
        cols.insert(k + 1, np.minimum(X[:, 3], 0)); labels.insert(k + 1, 'Trick Room x speed, favouring side 1')
    return np.column_stack(cols), labels
A, labels = design(X); off = X[:, HAND] @ np.array([e7['w'][i] for i in HAND])
def fit(A, y, off, sw, D=None, l2=1e-3, it=40):
    """weighted logistic regression; D = optional dummy columns (per-team intercepts) replacing the single intercept"""
    A1 = np.column_stack([np.ones(len(A)) if D is None else D, A]); nd = 1 if D is None else D.shape[1]; w = np.zeros(A1.shape[1])
    pen = np.r_[np.zeros(nd), np.ones(A.shape[1])] * l2
    for _ in range(it):
        p = 1 / (1 + np.exp(-(A1 @ w + off))); g = A1.T @ (sw * (p - y)) + pen * w
        H = (A1 * (sw * p * (1 - p))[:, None]).T @ A1 + np.diag(pen) + 1e-9 * np.eye(A1.shape[1]); w -= np.linalg.solve(H, g)
    return w, nd
wtr = os.environ.get('W_TR'); sw = np.ones(len(y))
if wtr: f = float(wtr); sw[isA] = f * len(y) / isA.sum(); sw[~isA] = (1 - f) * len(y) / (~isA).sum()
D = np.zeros((len(y), len(teams))); D[np.arange(len(y)), tid] = 1
ug = np.unique(G); rng = np.random.default_rng(0); fold = dict(zip(ug, rng.integers(0, 5, len(ug)))); fi = np.array([fold[g] for g in G])
def cv(train_mask, use_D):
    P = np.zeros(len(y))
    for k in range(5):
        tr = (fi != k) & train_mask; te = fi == k
        w, nd = fit(A[tr], y[tr], off[tr], sw[tr], D[tr] if use_D else None)
        z = (D[te] @ w[:nd] if use_D else w[0]) + A[te] @ w[nd:] + off[te]; P[te] = 1 / (1 + np.exp(-z))
    return np.clip(P, 1e-9, 1 - 1e-9)
def ll(P, m): return -np.mean(y[m] * np.log(P[m]) + (1 - y[m]) * np.log(1 - P[m]))
models = {'TR six only': (isA, False), 'other teams only': (~isA, False), 'pooled, one intercept': (np.ones(len(y), bool), False), 'pooled, intercept per team': (np.ones(len(y), bool), True)}
print(f"TR six: {len(np.unique(Ga))} games, {len(ya)} positions, win rate {ya.mean():.3f} | other teams: {len(np.unique(Gb))} games, {len(yb)} positions, win rate {yb.mean():.3f}")
print(f"{'5-fold log loss on:':34s} {'TR six':>8s} {'others':>8s}")
fits = {}
for nm, (m, useD) in models.items():
    P = cv(m, useD); w, nd = fit(A[m], y[m], off[m], sw[m], D[m] if useD else None); fits[nm] = (w, nd)
    print(f"   {nm:31s} {ll(P, isA):8.4f} {ll(P, ~isA):8.4f}")
print(f"\n{'weights':38s}" + ''.join(f"{nm[:24]:>26s}" for nm in models))
print(f"{'intercept':38s}" + ''.join((f"{fits[nm][0][0]:>26.3f}" if fits[nm][1] == 1 else f"{'TR six %+.2f, others %+.2f..%+.2f' % (fits[nm][0][0], fits[nm][0][1:fits[nm][1]].min(), fits[nm][0][1:fits[nm][1]].max()):>26s}") for nm in models))
for k, lab in enumerate(labels): print(f"{lab[:37]:38s}" + ''.join(f"{fits[nm][0][fits[nm][1] + k]:>26.3f}" for nm in models))
if len(sys.argv) > 3 and not SPLIT:
    w, nd = fits['pooled, intercept per team']; sl = w[nd:]; Wv = list(e7['w'])
    Wv[0] = float(sl[0])
    for i in TIED: Wv[i] = float(ratio[i] * sl[0])
    for k, i in enumerate(FREE): Wv[i] = float(sl[k + 1])
    b_tr = float(w[0]); b_oth = float(np.mean(w[1:nd])); key = lambda t: os.path.basename(os.path.dirname(t.rstrip('/'))).split('_')[0]      # runs/<12-hex team key>_<...>/out_... -> the team key
    base = {'w': Wv, 'names': names + ['race: KO edge', 'race: HP edge'], 'hand_set': e7['hand_set'], 'b0_by_team': {('tr_six' if t == tr_dir else key(t)): float(v) for t, v in zip(teams, w[:nd])}}
    note = 'Slopes shared across the TR six and Team search\'s ten teams (pooled fit, one intercept per team). Needs RACE=1 CALC_DATA=... '
    stem = sys.argv[3][:-5] if sys.argv[3].endswith('.json') else sys.argv[3]
    json.dump({'b0': b_oth, **base, 'note': note + 'This file: the general intercept (mean of the ten teams).'}, open(stem + '.json', 'w'), indent=1)
    json.dump({'b0': b_tr, **base, 'note': note + 'This file: the TR six\'s intercept.'}, open(stem + '_tr6.json', 'w'), indent=1)
    os.makedirs(stem + '_teams', exist_ok=True)
    for t, v in zip(teams[1:], w[1:nd]): json.dump({'b0': float(v), **base, 'note': note + f'This file: the intercept of team {key(t)}.'}, open(f'{stem}_teams/{key(t)}.json', 'w'), indent=1)
    print(f"\nwrote {stem}.json (general intercept {b_oth:+.3f}), {stem}_tr6.json ({b_tr:+.3f}) and {stem}_teams/<team key>.json ({nd - 1} teams)")
