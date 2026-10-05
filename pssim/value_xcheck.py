"""How well does a value file rate positions from other teams' games? (2026-10-05)
Scores every logged position (BATTLE_FEATS output: file-level 'feats' = [{v, F}]) with a value file and reports, per group of folders:
log loss, mean rated win chance vs actual win rate, and the same split by Trick Room state at that position (feature 3 = Trick Room
turns x tanh((their mean Speed - mine) / 15): > 0 Trick Room up and good for side 0, < 0 up and good for side 1, 0 down).
The Perish Song adjustment is not in the logged features, so Perish games are rated without it.
usage: ../.venv/bin/python3 value_xcheck.py <value.json> <label>=<dir or @file listing dirs> [...]"""
import json, glob, sys, os, numpy as np
ev = json.load(open(sys.argv[1])); b0 = ev['b0']; W = np.array(ev['w'], float)
def dirs(spec):
    if spec.startswith('@'): return [l.strip() for l in open(spec[1:]) if l.strip()]
    return [spec]
def load(ds):
    X, y, G, A = [], [], [], []
    for d in ds:
        for f in glob.glob(d + '/*.json'):
            try: r = json.load(open(f))
            except Exception: continue
            for k, g in enumerate(r.get('feats') or []):
                if g['v'] not in (0, 1): continue
                for fx in g['F']:
                    x = list(fx[:len(W)]) + [0.0] * max(0, len(W) - len(fx)); X.append(x); y.append(g['v']); G.append(f'{f}:{k}'); A.append(r['arch'])
    return np.array(X, float), np.array(y, float), np.array(G), np.array(A)
def rep(lab, P, y, m):
    if m.sum() < 30: return
    p = np.clip(P[m], 1e-9, 1 - 1e-9); yy = y[m]
    print(f"   {lab:42s} {m.sum():6d} positions: rated {100*p.mean():5.1f}% | actual {100*yy.mean():5.1f}% | gap {100*(yy.mean()-p.mean()):+5.1f} | log loss {-np.mean(yy*np.log(p)+(1-yy)*np.log(1-p)):.3f}")
for spec in sys.argv[2:]:
    lab, _, src = spec.partition('='); X, y, G, A = load(dirs(src))
    if not len(y): print(lab, 'no positions'); continue
    P = 1 / (1 + np.exp(-(b0 + X @ W)))
    print(f"{lab}: {len(np.unique(G))} games (side 0's view; gap > 0 = the value under-rates side 0)")
    rep('all positions', P, y, np.ones(len(y), bool))
    tr = X[:, 3]
    rep('Trick Room down', P, y, tr == 0); rep('Trick Room up, good for side 0', P, y, tr > 0.05); rep('Trick Room up, good for side 1', P, y, tr < -0.05)
    for a in sorted(set(A)):
        m = (A == a) & (tr < -0.05)
        if m.sum() >= 150: rep(f'  good for side 1, vs {a[:22]}', P, y, m)
    for lo, hi in ((0, .2), (.2, .5), (.5, .8), (.8, 1.01)):
        m = (P >= lo) & (P < hi); rep(f'rated {100*lo:.0f}-{100*min(hi,1):.0f}%', P, y, m)
