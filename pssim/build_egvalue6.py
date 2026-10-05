"""egvalue6 (2026-10-04): position value with the 11 replay-reproducible weights taken from real Bo3 games (fit_real_value.py ->
results/fit_real_value.json: HP share, Pokemon left, boosts, Trick Room x speed, Protected last turn, type edge, asleep, paralysed,
burned/poisoned, Tailwind, screens) as fixed relative weights. On the self-play games (results/battle_train2) only the intercept, one
overall scale for that real-weight block and the two matchup-grid weights are fitted; the hand-set features keep egvalue5's values
(Choice-locked status / attack, must recharge, Encored, Tricked Choice item).
usage: ../.venv/bin/python3 build_egvalue6.py"""
import json, glob, numpy as np
from fit_real_value import SIM_IDX
R = json.load(open('results/fit_real_value.json')); e5 = json.load(open('egvalue5.json'))
wr = np.array(R['real'][1:])                        # real weights for SIM_IDX features (intercept dropped: mirrored data)
GRID = [6, 7]; HAND = [4, 5, 8, 16, 17]
X, y = [], []
for f in glob.glob('results/battle_train2/*.json'):
    r = json.load(open(f))
    for g in r.get('feats', []):
        if g['v'] in (0, 1):
            for fx in g['F']: X.append(fx); y.append(g['v'])
X, y = np.array(X, float), np.array(y, float)
off = X[:, HAND] @ np.array([e5['w'][i] for i in HAND])
A = np.column_stack([np.ones(len(X)), X[:, SIM_IDX] @ wr, X[:, GRID]])
w = np.zeros(A.shape[1])
for _ in range(30):                                  # logistic regression with offset, Newton's method
    p = 1 / (1 + np.exp(-(A @ w + off))); g = A.T @ (p - y) + 1e-3 * np.r_[0, w[1:]]
    H = (A * (p * (1 - p))[:, None]).T @ A + 1e-3 * np.diag(np.r_[0, np.ones(A.shape[1] - 1)]); w -= np.linalg.solve(H, g)
b0, s, g0, g1 = w
W = list(e5['w'])
for k, i in enumerate(SIM_IDX): W[i] = float(s * wr[k])
W[6], W[7] = float(g0), float(g1)
p = 1 / (1 + np.exp(-(A @ w + off))); ll = -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
out = {'b0': float(b0), 'w': W, 'names': e5['names'], 'hand_set': e5['hand_set'],
       'note': f'Relative weights of the 11 replay features from {R["n_real_games"]} real Bo3 games (results/fit_real_value.json), scaled by {s:.3f}; '
               'intercept, scale and grid weights fitted on results/battle_train2 with those fixed; hand-set as egvalue5.'}
json.dump(out, open('egvalue6.json', 'w'), indent=1)
print(f'scale {s:.3f}, b0 {b0:+.3f}, grid {g0:+.3f} / {g1:+.3f}; self-play log loss {ll:.4f}')
for nm, a, b in zip(e5['names'], e5['w'], W): print(f'   {nm:30s} {a:+.3f} -> {b:+.3f}')
