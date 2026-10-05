"""egvalue8 (2026-10-05): position value refitted on self-play with the settled sets (Torkoal 32 HP / 2 SpD), the sheet kit's generic
one-on-one grid and the candidate planner (results/refit8: champ-battle-v8, DP2=1 RACE=1, played with egvalue7; refit8_run.sh).
  - asleep/frozen, paralysed, burned/poisoned and Tailwind keep their real-game ratio to the HP weight (results/fit_real_value.json): they
    are tied to HP share in one composite feature, so they scale with the fitted HP weight (egvalue7 kept their absolute values).
  - hand-set features keep egvalue7's values (Choice-locked status / attack, must recharge, Encored, Tricked Choice item).
  - fitted: intercept, the HP composite, Pokemon alive, boosts, Trick Room x speed, grid coverage / exposure, Protected last turn,
    type edge, screens, race KO edge, race HP edge.
Prints bootstrap standard errors, game-level 5-fold log loss, and calibration by win-chance bucket on the held-out predictions (both
sides of every position). TR_REAL=1 also ties the Trick Room feature to its real-game ratio (a variant to compare, not the default).
usage: ../.venv/bin/python3 build_egvalue8.py [self-play dir=results/refit8] [out=egvalue8.json]"""
import json, glob, sys, os, numpy as np
d = sys.argv[1] if len(sys.argv) > 1 else 'results/refit8'; outf = sys.argv[2] if len(sys.argv) > 2 else 'egvalue8.json'
e7 = json.load(open('egvalue7.json')); R = json.load(open('results/fit_real_value.json')); real = dict(zip(R['names'], R['real'][1:]))
HAND = [4, 5, 8, 16, 17]; TIED = {11: 'slp', 12: 'par', 13: 'brn', 14: 'tw'}
if os.environ.get('TR_REAL'): TIED[3] = 'tr'
ratio = {i: real[k] / real['hp'] for i, k in TIED.items()}
FREE = [i for i in (1, 2, 3, 6, 7, 9, 10, 15, 18, 19) if i not in TIED and not (os.environ.get('NORACE') and i >= 18)]   # NORACE=1: no race weights (a comparison variant)
X, y, G = [], [], []
for f in glob.glob(d + '/*.json'):
    r = json.load(open(f))
    for k, g in enumerate(r.get('feats', [])):
        if g['v'] not in (0, 1): continue
        for fx in g['F']:
            if len(fx) >= 20: X.append(fx[:20]); y.append(g['v']); G.append(f'{f}:{k}')
X, y, G = np.array(X, float), np.array(y, float), np.array(G)
off = X[:, HAND] @ np.array([e7['w'][i] for i in HAND])
comp = X[:, 0] + sum(ratio[i] * X[:, i] for i in TIED)               # HP share + real-game-ratio features
A = np.column_stack([comp, X[:, FREE]])
def fit(A, y, off, l2=1e-3, it=30):
    A1 = np.column_stack([np.ones(len(A)), A]); w = np.zeros(A1.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-(A1 @ w + off))); g = A1.T @ (p - y) + l2 * np.r_[0, w[1:]]
        H = (A1 * (p * (1 - p))[:, None]).T @ A1 + l2 * np.diag(np.r_[0, np.ones(A1.shape[1] - 1)]); w -= np.linalg.solve(H, g)
    return w
ug = np.unique(G); rng = np.random.default_rng(0); fold = dict(zip(ug, rng.integers(0, 5, len(ug)))); fi = np.array([fold[g] for g in G])
def cv(A):
    P = np.zeros(len(y))
    for k in range(5):
        tr, te = fi != k, fi == k; w = fit(A[tr], y[tr], off[tr]); P[te] = 1 / (1 + np.exp(-(w[0] + A[te] @ w[1:] + off[te])))
    P = np.clip(P, 1e-9, 1 - 1e-9); return -np.mean(y * np.log(P) + (1 - y) * np.log(1 - P)), P
ll, P = cv(A); ll_norace, _ = cv(A[:, :-2]) if not os.environ.get('NORACE') else (float('nan'), None)
print(f"{len(ug)} games, {len(y)} positions; my win rate {y.mean():.3f}; 5-fold log loss {ll:.4f} (without the race features {ll_norace:.4f})")
w = fit(A, y, off)
idx = {g: np.where(G == g)[0] for g in ug}; B = []
for _ in range(40):
    rows = np.concatenate([idx[g] for g in rng.choice(ug, len(ug))]); B.append(fit(A[rows], y[rows], off[rows]))
se = np.std(B, axis=0)
names = e7['names']; W = list(e7['w'])
W[0] = float(w[1]); W = W[:18] + [0.0, 0.0] if os.environ.get('NORACE') else W
for i in TIED: W[i] = float(ratio[i] * w[1])
for k, i in enumerate(FREE): W[i] = float(w[k + 2])
print(f"   {'intercept':30s} {e7['b0']:+.3f} -> {w[0]:+.3f} ± {se[0]:.3f}")
for i, nm in enumerate(names):
    tag = f"± {se[1]:.3f}" if i == 0 else f"± {se[FREE.index(i) + 2]:.3f}" if i in FREE else f"(= {ratio[i]:+.2f} x HP weight, real games)" if i in TIED else '(hand-set)'
    print(f"   {nm:30s} {e7['w'][i]:+.3f} -> {W[i]:+.3f} {tag}")
EDGES = [0, .02, .05, .10, .20, .35, .50, .65, .80, .90, .95, .98, 1.0000001]
PP = np.r_[P, 1 - P]; YY = np.r_[y, 1 - y]; cal = []
print('   calibration on held-out games (rated -> actual, positions):')
for lo, hi in zip(EDGES[:-1], EDGES[1:]):
    m = (PP >= lo) & (PP < hi)
    if m.sum(): cal.append([lo, min(hi, 1.0), int(m.sum()), float(PP[m].mean()), float(YY[m].sum())]); print(f"      {100*lo:3.0f}-{100*min(hi,1):3.0f}%: {100*PP[m].mean():5.1f} -> {100*YY[m].mean():5.1f}  ({m.sum()})")
json.dump({'b0': float(w[0]), 'w': W, 'names': names, 'hand_set': e7['hand_set'], 'calib': cal,
           'note': f'Refit on {d} ({len(ug)} self-play games: Torkoal 32 HP / 2 SpD, generic grid, champ-battle-v8 DP2 RACE, played with egvalue7). '
                   'asleep/paralysed/burned/Tailwind' + ('/Trick Room' if 3 in TIED else '') + ' tied to the HP weight at their real-game ratios; hand-set as egvalue5. Needs RACE=1 CALC_DATA=...'},
          open(outf, 'w'), indent=1)
