"""Elo sanity check for the position value (2026-10-04). Fits the 11 replay-reproducible weights (fit_real_value.py) on real Bo3 games split
by the players' mean rating, and on each self-play generation (results/battle_train: played with egvalue2 -> egvalue4; results/battle_train2:
played with egvalue4 -> egvalue5; generation 0 = egvalue2's hand-set weights). Weights are compared relative to the HP weight.
  direction test: does each self-play round move the weights the same way that rising Elo does (cosine of the two changes, per feature)?
  prediction test: log loss on the top-rated games (game-level 5-fold) for each set of relative weights, with only scale and intercept refit.
usage: ../.venv/bin/python3 elo_check.py [cutoffs, e.g. 1100,1250]"""
import json, glob, sys, numpy as np
from fit_real_value import fit, boot, NAMES, SIM_IDX
cut = [float(x) for x in sys.argv[1].split(',')] if len(sys.argv) > 1 else [1100, 1250]
d = json.load(open('results/replay_feats.json')); R = [r for r in d['rows'] if r.get('r')]
X = np.array([r['f'] for r in R], float); y = np.array([r['y'] for r in R], float); g = np.array([r['g'] for r in R]); rt = np.array([r['r'] for r in R], float)
bins = [(-1e9, cut[0])] + [(cut[i], cut[i + 1]) for i in range(len(cut) - 1)] + [(cut[-1], 1e9)]
lab = [f"<{cut[0]:.0f}"] + [f"{a:.0f}-{b:.0f}" for a, b in bins[1:-1]] + [f">={cut[-1]:.0f}"]
W = {}
for (a, b), nm in zip(bins, lab):
    m = (rt >= a) & (rt < b); W[nm] = (fit(X[m], y[m]), boot(g[m], X[m], y[m], B=100), len(np.unique(g[m])))
def selfplay(dirn):
    Xs, ys, gs = [], [], []
    for f in glob.glob(dirn + '/*.json'):
        r = json.load(open(f))
        for k, gg in enumerate(r.get('feats', [])):
            if gg['v'] not in (0, 1): continue
            for fx in gg['F']: Xs.append([fx[i] for i in SIM_IDX]); ys.append(gg['v']); gs.append(f'{f}:{k}')
    return np.array(Xs, float), np.array(ys, float), np.array(gs)
e2 = json.load(open('egvalue2.json'))
S = {'gen0 (egvalue2, hand)': np.r_[e2['b0'], [e2['w'][i] for i in SIM_IDX]]}
for nm, dirn in (('gen1 (egvalue2 games)', 'results/battle_train'), ('gen2 (egvalue4 games)', 'results/battle_train2')):
    Xs, ys, gs = selfplay(dirn); S[nm] = fit(Xs, ys)
rel = lambda w: w[1:] / w[1]
cols = list(W) + list(S)
print('weights relative to HP (real by rating, then self-play generations):')
print(f"{'':8s}" + ''.join(f"{c[:20]:>22s}" for c in cols))
print(f"{'games':8s}" + ''.join(f"{W[c][2]:>22d}" for c in W) + ''.join(f"{'':>22s}" for c in S))
print(f"{'hp abs':8s}" + ''.join(f"{W[c][0][1]:>15.2f} ± {W[c][1][1]:.2f}" for c in W) + ''.join(f"{S[c][1]:>22.2f}" for c in S))
for k, nm in enumerate(NAMES):
    if k == 0: continue
    print(f"{nm:8s}" + ''.join(f"{rel(W[c][0])[k]:>15.2f} ± {W[c][1][k + 1] / abs(W[c][0][1]):.2f}" for c in W) + ''.join(f"{rel(S[c])[k]:>22.2f}" for c in S))
lo, hi = list(W)[0], list(W)[-1]; s_names = list(S)
d_elo = rel(W[hi][0]) - rel(W[lo][0])
for a, b in zip(s_names[:-1], s_names[1:]):
    d_sp = rel(S[b]) - rel(S[a]); c = float(d_sp[1:] @ d_elo[1:] / (np.linalg.norm(d_sp[1:]) * np.linalg.norm(d_elo[1:]) + 1e-12))
    agree = [NAMES[k] for k in range(1, len(NAMES)) if np.sign(d_sp[k]) == np.sign(d_elo[k]) and abs(d_elo[k]) > 0.05]
    disagree = [NAMES[k] for k in range(1, len(NAMES)) if np.sign(d_sp[k]) != np.sign(d_elo[k]) and abs(d_elo[k]) > 0.05]
    print(f"\n{a} -> {b}: cosine with the low->high Elo change {c:+.2f}; same direction: {', '.join(agree) or '-'}; opposite: {', '.join(disagree) or '-'}")
# prediction on the top bracket: relative weights fixed, scale + intercept refit, game-level 5-fold
m = rt >= bins[-1][0]; Xh, yh, gh = X[m], y[m], g[m]; ug = np.unique(gh); rng = np.random.default_rng(0); fold = dict(zip(ug, rng.integers(0, 5, len(ug))))
fi = np.array([fold[x] for x in gh])
def ll(direction=None, refit_all=False):
    tot = 0.0
    for k in range(5):
        tr, te = fi != k, fi == k
        if refit_all: w = fit(Xh[tr], yh[tr]); z = w[0] + Xh[te] @ w[1:]
        else:
            u = Xh @ direction; w = fit(u[tr, None], yh[tr]); z = w[0] + w[1] * u[te]
        p = np.clip(1 / (1 + np.exp(-z)), 1e-9, 1 - 1e-9); tot += -np.sum(yh[te] * np.log(p) + (1 - yh[te]) * np.log(1 - p))
    return tot / len(yh)
print(f"\nlog loss on {lab[-1]} games ({len(ug)} games; lower is better; coin flip 0.693):")
print(f"   fitted on these games (5-fold)        {ll(refit_all=True):.4f}")
for c in W:
    if c != hi: print(f"   real {c:30s}  {ll(W[c][0][1:]):.4f}")
for c in S: print(f"   self-play {c:25s}  {ll(S[c][1:]):.4f}")
print(f"   HP only                               {ll(np.eye(len(NAMES))[0]):.4f}")
