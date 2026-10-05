"""How good is the bar? Scores a win-chance model on the cached real games, at the start of every turn, against who won.
Version 0 (the eleven replay features -> logistic model) is scored out of sample: five folds split by game, fitted on four, scored on the fifth.
Prints and writes: log loss and Brier score per position (a coin flip scores 0.693 and 0.25), how often the favourite won, the same by turn
number, and calibration (of the positions rated 60-70%, how many were won).
usage (needs numpy: the main folder's .venv): python3 evalbar/accuracy.py [out.json=evalbar/results/accuracy_v0.json]"""
import os, sys, json, math, zlib
import numpy as np
import common as C
RF = C.replay_feats(); sys.path.insert(0, C.PSSIM)
from fit_real_value import fit
EDGES = [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0000001]
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
if __name__ == '__main__':
    G = []
    for rid, log in C.games():
        try: rows, w, _ = RF.game(log)
        except Exception: continue
        if w is not None and rows: G.append((rid, rows, 1 if w == 'p1' else 0))
    fold = lambda rid: zlib.crc32(rid.encode()) % 5
    scored = []
    for k in range(5):
        X = []; y = []
        for rid, rows, won in G:
            if fold(rid) == k: continue
            for t, f in rows: X.append(f); y.append(won); X.append([-v for v in f]); y.append(1 - won)
        w = fit(np.array(X, float), np.array(y, float)).tolist()
        for rid, rows, won in G:
            if fold(rid) == k: scored += [(rid, t, C.v0(w, f), won) for t, f in rows]
    s = score(scored); show('version 0, out of sample', s)
    outf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(C.HERE, 'results', 'accuracy_v0.json')
    os.makedirs(os.path.dirname(outf), exist_ok=True); json.dump({'model': 'v0: 11 replay features, logistic, 5-fold by game', **s}, open(outf, 'w'), indent=1)
