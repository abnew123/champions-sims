"""Position value from real games vs from self-play (2026-10-04): logistic regression of "this side wins" on the planner's features that
replays can reproduce (replay_feats.py), fitted on real Bo3 games and, with the same features, on the self-play games egvalue5 was fitted
on (results/battle_train2, BATTLE_FEATS). Standard errors from a bootstrap over games. Also each weight relative to the HP weight, since the
overall scale differs (real outcomes are noisier).
usage: ../.venv/bin/python3 fit_real_value.py [replay feats json=results/replay_feats.json] [self-play dir=results/battle_train2]"""
import json, glob, sys, numpy as np
NAMES = ['hp', 'n', 'bst', 'tr', 'stall', 'te', 'slp', 'par', 'brn', 'tw', 'scr']
SIM_IDX = [0, 1, 2, 3, 9, 10, 11, 12, 13, 14, 15]          # the same features in plan.rs feats order
def fit(X, y, l2=1e-3, it=30):
    """logistic regression with intercept by Newton's method"""
    A = np.hstack([np.ones((len(X), 1)), X]); w = np.zeros(A.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-A @ w)); g = A.T @ (p - y) + l2 * np.r_[0, w[1:]]
        H = (A * (p * (1 - p))[:, None]).T @ A + l2 * np.diag(np.r_[0, np.ones(A.shape[1] - 1)])
        w -= np.linalg.solve(H, g)
    return w
def boot(groups, X, y, B=200, seed=1):
    ug = np.unique(groups); idx = {g: np.where(groups == g)[0] for g in ug}; rng = np.random.default_rng(seed); W = []
    for _ in range(B):
        pick = rng.choice(ug, len(ug)); rows = np.concatenate([idx[g] for g in pick]); W.append(fit(X[rows], y[rows]))
    return np.std(W, axis=0)
if __name__ == '__main__':
    rf = sys.argv[1] if len(sys.argv) > 1 else 'results/replay_feats.json'; sd = sys.argv[2] if len(sys.argv) > 2 else 'results/battle_train2'
    d = json.load(open(rf)); Xr = np.array([r['f'] for r in d['rows']], float); yr = np.array([r['y'] for r in d['rows']], float)
    gr = np.array([r['g'] for r in d['rows']])
    Xs, ys, gs = [], [], []
    for f in glob.glob(sd + '/*.json'):
        r = json.load(open(f))
        for k, g in enumerate(r.get('feats', [])):
            if g['v'] not in (0, 1): continue
            for fx in g['F']: Xs.append([fx[i] for i in SIM_IDX]); ys.append(g['v']); gs.append(f'{f}:{k}')
    Xs, ys, gs = np.array(Xs, float), np.array(ys, float), np.array(gs)
    wr, ws = fit(Xr, yr), fit(Xs, ys)
    er, es = boot(gr, Xr, yr), boot(gs, Xs, ys, B=50)
    print(f"real Bo3: {len(np.unique(gr))} games, {len(yr) // 2} positions (each from both sides) | self-play: {len(np.unique(gs))} games, {len(ys)} positions")
    print(f"{'feature':8s} {'real':>15s} {'self-play':>15s}   {'real / hp':>9s} {'self-play / hp':>14s}")
    for k, nm in enumerate(['(intercept)'] + NAMES):
        rel = '' if k == 0 else f"{wr[k] / wr[1]:9.2f} {ws[k] / ws[1]:14.2f}"
        print(f"{nm:8s} {wr[k]:+7.3f} ± {er[k]:.3f} {ws[k]:+7.3f} ± {es[k]:.3f}   {rel}")
    json.dump({'names': NAMES, 'real': wr.tolist(), 'real_se': er.tolist(), 'selfplay': ws.tolist(), 'selfplay_se': es.tolist(),
               'n_real_games': int(len(np.unique(gr))), 'n_selfplay_games': int(len(np.unique(gs)))}, open('results/fit_real_value.json', 'w'), indent=1)
