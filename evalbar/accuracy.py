"""How good is the bar? Scores win-chance models on the cached real games, at the start of every turn, against who won.
Everything is scored out of sample: five folds split by game, each model fitted on four and scored on the fifth (fits are logistic
regressions on features that flip sign when the sides are swapped, so every model is symmetric between the players).
  version 0          the eleven replay features (pssim/replay_feats.py)
With engine results (lines from the engine's position evaluation, named "<replay id> t<turn> p1"), on the positions that have them:
  engine value       the engine's one-turn equilibrium value, rescaled to real outcomes (one weight on its log-odds)
  engine static      the same for the value function at the position, no lookahead
  engine features    the planner's full feature vector, weights refitted on real games
  v0 + engine        the eleven replay features plus the engine value's log-odds
Prints and writes: log loss and Brier score per position (a coin flip scores 0.693 and 0.25), how often the favourite won, the same by turn
number, and calibration (of the positions rated 60-70%, how many were won).
usage (needs numpy: the main folder's .venv): python3 evalbar/accuracy.py [engine results .jsonl ...]
       writes evalbar/results/accuracy_v0.json, or accuracy_engine.json when engine results are given"""
import os, sys, json, math, zlib
import numpy as np
import common as C
RF = C.replay_feats(); sys.path.insert(0, C.PSSIM)
from fit_real_value import fit
EDGES = [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0000001]
fold = lambda rid: zlib.crc32(rid.encode()) % 5
logit = lambda v: math.log(min(1 - 1e-4, max(1e-4, v)) / (1 - min(1 - 1e-4, max(1e-4, v))))
def score(rows):
    """rows: (game, turn, player 1's win chance, player 1 won)"""
    p = np.clip(np.array([r[2] for r in rows]), 1e-6, 1 - 1e-6); y = np.array([r[3] for r in rows], float)
    ll = -(y * np.log(p) + (1 - y) * np.log(1 - p)); fav = (p > .5) == (y > .5)
    by_game = {}
    for r, l in zip(rows, ll): by_game.setdefault(r[0], []).append(l)
    out = {'positions': len(rows), 'games': len(by_game), 'log_loss': float(ll.mean()), 'log_loss_per_game': float(np.mean([np.mean(v) for v in by_game.values()])),
           'brier': float(((p - y) ** 2).mean()), 'favourite_won': float(fav[p != .5].mean()), 'by_turn': [], 'calibration': []}
    turns = np.array([r[1] for r in rows])
    for t in range(1, 13):
        m = turns == t if t < 12 else turns >= 12
        if m.sum(): out['by_turn'].append({'turn': t if t < 12 else '12+', 'positions': int(m.sum()), 'log_loss': float(ll[m].mean()), 'favourite_won': float(fav[m].mean())})
    P = np.r_[p, 1 - p]; Y = np.r_[y, 1 - y]                                   # every position from both sides
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        m = (P >= lo) & (P < hi)
        if m.sum(): out['calibration'].append({'lo': lo, 'hi': min(hi, 1.0), 'positions': int(m.sum()), 'rated': float(P[m].mean()), 'won': float(Y[m].mean())})
    return out
def show(tag, s):
    print(f"{tag}: {s['games']} games, {s['positions']} positions | log loss {s['log_loss']:.4f} (per game {s['log_loss_per_game']:.4f}; coin flip 0.6931) | "
          f"Brier {s['brier']:.4f} | favourite won {100 * s['favourite_won']:.1f}%")
    print('   by turn: ' + '  '.join(f"t{b['turn']} {b['log_loss']:.3f}/{100 * b['favourite_won']:.0f}%" for b in s['by_turn']))
    print('   calibration (rated -> won): ' + '  '.join(f"{100 * c['rated']:.0f}->{100 * c['won']:.0f}" for c in s['calibration']))
def cv(rows, feats):
    """rows: dicts with g, t, y; feats(row) -> feature list. Out-of-sample predictions as (game, turn, p, won)."""
    scored = []
    for k in range(5):
        X = []; y = []
        for r in rows:
            if fold(r['g']) == k: continue
            f = feats(r); X.append(f); y.append(r['y']); X.append([-v for v in f]); y.append(1 - r['y'])
        w = fit(np.array(X, float), np.array(y, float)).tolist()
        scored += [(r['g'], r['t'], C.v0(w, feats(r)), r['y']) for r in rows if fold(r['g']) == k]
    return scored
def real_rows():
    rows = []
    for rid, log in C.games():
        try: fr, w, _ = RF.game(log)
        except Exception: continue
        if w is not None and fr: rows += [{'g': rid, 't': t, 'f': f, 'y': 1 if w == 'p1' else 0} for t, f in fr]
    return rows
if __name__ == '__main__':
    rows = real_rows(); out = {}
    if len(sys.argv) < 2:
        s = score(cv(rows, lambda r: r['f'])); show('version 0, out of sample', s)
        outf = os.path.join(C.HERE, 'results', 'accuracy_v0.json'); out = {'model': 'v0: 11 replay features, logistic, 5-fold by game', **s}
    else:
        eng = {}
        for f in sys.argv[1:]:
            for l in open(f):
                d = json.loads(l)
                if d.get('value') is not None and d['name'].endswith(' p1'): eng[d['name'][:-3]] = d
        sub = [{**r, 'e': eng[f"{r['g']} t{r['t']}"]} for r in rows if f"{r['g']} t{r['t']}" in eng]
        models = {'version 0 (same positions)': lambda r: r['f'], 'engine value': lambda r: [logit(r['e']['value'])],
                  'v0 + engine': lambda r: r['f'] + [logit(r['e']['value'])]}
        if sub and sub[0]['e'].get('static') is not None: models['engine static'] = lambda r: [logit(r['e']['static'])]
        if sub and sub[0]['e'].get('feats'): models['engine features'] = lambda r: r['e']['feats']
        for nm, fx in models.items():
            s = score(cv(sub, fx)); show(nm, s); out[nm] = s
        outf = os.path.join(C.HERE, 'results', 'accuracy_engine.json')
    os.makedirs(os.path.dirname(outf), exist_ok=True); json.dump(out, open(outf, 'w'), indent=1)
