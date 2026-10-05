"""Which value-function features are redundant or useless? Uses the turn-start feature vectors saved in the other thread's self-play
battles (pssim/results/battle_train2: the data egvalue5 was fitted on; 18 features, names from pssim/egvalue5.json) with each
game's outcome. Reports: how often each feature is non-zero, the most correlated pairs, PCA of the standardized features,
variance inflation (VIF), and drop-one ablation: the rise in held-out log loss (5-fold, split by game) when a feature is removed
from a freely refitted logistic model. Caveat: self-play of the Trick Room six only, so rare states (sleep, Encore, ...) barely occur.
  python3 value_pca.py [results dir = battle_train2]
"""
import json, os, sys, glob, math
import numpy as np
from scipy.optimize import minimize
PS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pssim')
names = json.load(open(os.path.join(PS, 'egvalue5.json')))['names']
X, y, gid = [], [], []
for f in glob.glob(os.path.join(PS, 'results', sys.argv[1] if len(sys.argv) > 1 else 'battle_train2', '*.json')):
    r = json.load(open(f))
    for gi, g in enumerate(r.get('feats', [])):
        for fx in g['F']:
            X.append(fx); y.append(g['v']); gid.append(hash((f, gi)))
X = np.array(X, float); y = np.array(y, float); gid = np.array(gid)
n, d = X.shape
print(f'{n} positions from {len(set(gid))} games, {d} features\n')
nz = (np.abs(X) > 1e-9).mean(0); sd = X.std(0)
print('feature                         non-zero   SD')
for i, nm in enumerate(names): print(f'  {nm:30s} {100 * nz[i]:6.1f}%  {sd[i]:.3f}')
live = [i for i in range(d) if sd[i] > 1e-9]
Z = (X[:, live] - X[:, live].mean(0)) / X[:, live].std(0)
C = np.corrcoef(Z, rowvar=False)
pairs = sorted(((abs(C[a, b]), C[a, b], live[a], live[b]) for a in range(len(live)) for b in range(a + 1, len(live))), reverse=True)[:8]
print('\nmost correlated pairs:'); [print(f'  {c:+.2f}  {names[i]}  ~  {names[j]}') for _, c, i, j in pairs]
ev, vec = np.linalg.eigh(C); order = np.argsort(ev)[::-1]; ev, vec = ev[order], vec[:, order]
cum = np.cumsum(ev) / ev.sum()
print(f'\nPCA (standardized): components needed for 80% / 90% / 95% of variance: '
      f'{int(np.searchsorted(cum, .8)) + 1} / {int(np.searchsorted(cum, .9)) + 1} / {int(np.searchsorted(cum, .95)) + 1} of {len(live)}')
for k in range(3):
    top = sorted(range(len(live)), key=lambda a: -abs(vec[a, k]))[:4]
    print(f'  PC{k + 1} ({100 * ev[k] / ev.sum():.0f}%): ' + ', '.join(f'{names[live[a]]} {vec[a, k]:+.2f}' for a in top))
vif = np.diag(np.linalg.inv(C))
print('\nvariance inflation (> 5 = largely explained by the other features):')
print('  ' + ', '.join(f'{names[live[a]]} {vif[a]:.1f}' for a in sorted(range(len(live)), key=lambda a: -vif[a])[:6]))

def fit(A, b):
    A1 = np.c_[np.ones(len(A)), A]
    def nll(w):
        z = A1 @ w; p = 1 / (1 + np.exp(-z)); p = np.clip(p, 1e-9, 1 - 1e-9)
        return -(b * np.log(p) + (1 - b) * np.log(1 - p)).mean() + 1e-4 * w[1:] @ w[1:], A1.T @ (p - b) / len(b) + np.r_[0, 2e-4 * w[1:]]
    return minimize(nll, np.zeros(A1.shape[1]), jac=True, method='L-BFGS-B').x
def cv_logloss(cols):
    folds = np.abs(gid) % 5; tot = 0.0
    for k in range(5):
        tr, te = folds != k, folds == k
        w = fit(Z[tr][:, cols], y[tr]); z = np.c_[np.ones(te.sum()), Z[te][:, cols]] @ w; p = np.clip(1 / (1 + np.exp(-z)), 1e-9, 1 - 1e-9)
        tot += -(y[te] * np.log(p) + (1 - y[te]) * np.log(1 - p)).sum()
    return tot / n
allc = list(range(len(live))); base = cv_logloss(allc)
print(f'\ndrop-one ablation (held-out log loss {base:.4f} with all features; rise when a feature is removed):')
res = sorted(((cv_logloss([c for c in allc if c != a]) - base, names[live[a]]) for a in allc), reverse=True)
for dl, nm in res: print(f'  {dl * 1000:+7.2f} ×1e-3  {nm}')
