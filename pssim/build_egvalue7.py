"""egvalue7 (2026-10-04): position value with the damage-race features (champ-battle-v6, RACE=1: features 18 KO edge, 19 HP edge).
Fitted on the self-play games in results/race_train (BATTLE_FEATS, played with egvalue6b). Held fixed: asleep/paralysed/burned/Tailwind
from real games (as egvalue6b) and the hand-set features (Choice lock status/attack, must recharge, Encored, Tricked Choice item);
fitted: intercept, HP share, Pokemon alive, boosts, Trick Room x speed, the two grid features, Protected last turn, type edge, screens and
the two race features. Prints game-level 5-fold log loss with and without the race features, and bootstrap standard errors.
usage: ../.venv/bin/python3 build_egvalue7.py [self-play dir=results/race_train]"""
import json, glob, sys, numpy as np
d = sys.argv[1] if len(sys.argv) > 1 else 'results/race_train'
e6 = json.load(open('egvalue6b.json'))
FIXED = [4, 5, 8, 11, 12, 13, 14, 16, 17]; FIT = [0, 1, 2, 3, 6, 7, 9, 10, 15, 18, 19]
X, y, G = [], [], []
for f in glob.glob(d + '/*.json'):
    r = json.load(open(f))
    for k, g in enumerate(r.get('feats', [])):
        if g['v'] not in (0, 1): continue
        for fx in g['F']:
            if len(fx) < 20: continue
            X.append(fx); y.append(g['v']); G.append(f'{f}:{k}')
X, y, G = np.array(X, float), np.array(y, float), np.array(G)
off = X[:, FIXED] @ np.array([e6['w'][i] for i in FIXED])
def fit(A, y, off, l2=1e-3, it=30):
    A = np.column_stack([np.ones(len(A)), A]); w = np.zeros(A.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-(A @ w + off))); g = A.T @ (p - y) + l2 * np.r_[0, w[1:]]
        H = (A * (p * (1 - p))[:, None]).T @ A + l2 * np.diag(np.r_[0, np.ones(A.shape[1] - 1)]); w -= np.linalg.solve(H, g)
    return w
def cv(cols):
    ug = np.unique(G); rng = np.random.default_rng(0); fold = dict(zip(ug, rng.integers(0, 5, len(ug)))); fi = np.array([fold[g] for g in G]); tot = 0.0
    for k in range(5):
        tr, te = fi != k, fi == k; w = fit(X[tr][:, cols], y[tr], off[tr])
        p = np.clip(1 / (1 + np.exp(-(w[0] + X[te][:, cols] @ w[1:] + off[te]))), 1e-9, 1 - 1e-9); tot += -np.sum(y[te] * np.log(p) + (1 - y[te]) * np.log(1 - p))
    return tot / len(y)
print(f"{len(np.unique(G))} games, {len(y)} positions; win rate {y.mean():.3f}")
print(f"5-fold log loss: without race features {cv(FIT[:-2]):.4f} | with {cv(FIT):.4f}")
w = fit(X[:, FIT], y, off)
ug = np.unique(G); idx = {g: np.where(G == g)[0] for g in ug}; rng = np.random.default_rng(1); B = []
for _ in range(40):
    rows = np.concatenate([idx[g] for g in rng.choice(ug, len(ug))]); B.append(fit(X[rows][:, FIT], y[rows], off[rows]))
se = np.std(B, axis=0)
names = e6['names'] + ['race: KO edge', 'race: HP edge']
W = list(e6['w']) + [0.0, 0.0]
for k, i in enumerate(FIT): W[i] = float(w[k + 1])
print(f"   {'intercept':30s} {e6['b0']:+.3f} -> {w[0]:+.3f} ± {se[0]:.3f}")
for i, nm in enumerate(names):
    k = FIT.index(i) + 1 if i in FIT else None
    old = e6['w'][i] if i < len(e6['w']) else 0.0
    print(f"   {nm:30s} {old:+.3f} -> {W[i]:+.3f}" + (f" ± {se[k]:.3f}" if k else "   (fixed)"))
json.dump({'b0': float(w[0]), 'w': W, 'names': names, 'hand_set': e6['hand_set'],
           'note': f'Race features (champ-battle-v6, RACE=1) fitted on {d} ({len(np.unique(G))} self-play games played with egvalue6b); '
                   'asleep/paralysed/burned/Tailwind from real games as egvalue6b; hand-set as egvalue5. Needs RACE=1 CALC_DATA=... to apply.'},
          open('egvalue7.json', 'w'), indent=1)
