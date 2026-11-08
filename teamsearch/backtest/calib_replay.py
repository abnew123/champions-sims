"""v2's self-play weights again with calibrated payoffs (goal 1, the meta estimate; the M-B calibration, backtest/calib_fit.py). No new
sims: v2's payoff matrices (backtest/v2/sp_score_<i>.json), its climbed teams entering when they did, the same replicator (eta 2,
entry 3%, under 0.5% dropped, at most 20 kept); only each symmetrised payoff p becomes sigmoid(c * logit(p)) first.
c from the calibration: real M-B outcomes ~ 0.538 x logit(sim) on 12 sim games a game; their split-half correlation (6 vs 6) is 0.600,
so 0.2 a game, reliability 0.75 at 12 games and the slope on the sim's true odds 0.538 / 0.75 = 0.72. A symmetrised cell holds 32 games
(reliability 0.89), so the expected real payoff given the cell is c = 0.72 x 0.89 = 0.64; 0.72 and 0.54 bracket it. c = 1 replays
v2 as run (checked against sp_pred_<i>.json). The climbs stay v2's: under calibrated weights other teams might have climbed.
Out: backtest/v2/cal<c>/sp_pred_<i>.json (compare.py reads them).
  python3 backtest/calib_replay.py
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); V2 = os.path.join(HERE, 'v2')
sys.path.insert(0, HERE); from selfplay import replicator
ETA, ENTRY, W_MIN, N_MAX, ITERS = 2.0, 0.03, 0.005, 20, 4
CS = (1.0, 0.72, 0.64, 0.54)

def shrink(M, c):
    M = np.array(M); P = (M - M.T) / 2 + 0.5
    if c == 1: return P
    P = np.clip(P, 1 / 64, 63 / 64)
    return 1 / (1 + np.exp(-c * np.log(P / (1 - P))))

def replay(c):
    preds = {i: json.load(open(os.path.join(V2, f'sp_pred_{i}.json'))) for i in range(ITERS + 1)}
    species = {n: t['species'] for p in preds.values() for n, t in p['field'].items()}
    w = {n: t['w'] for n, t in preds[0]['field'].items()}; out = {}
    for i in range(1, ITERS + 1):
        R = json.load(open(os.path.join(V2, f'sp_score_{i}.json')))
        w0 = [w.get(n, ENTRY) for n in R['names']]; tot = sum(w0)               # climbed teams enter at 3%, the rest rescaled
        x, f = replicator(shrink(R['M'], c), [v / tot for v in w0], ETA)
        keep = sorted((k for k in range(len(x)) if x[k] >= W_MIN), key=lambda k: -x[k])[:N_MAX]; tot = sum(x[k] for k in keep)
        w = {R['names'][k]: float(x[k] / tot) for k in keep}
        use = {}
        for n, v in w.items():
            for s in species[n]: use[s] = use.get(s, 0) + v
        out[i] = dict(iteration=i, c=c, eta=ETA, field={n: dict(w=v, species=species[n]) for n, v in w.items()},
                      usage=dict(sorted(use.items(), key=lambda kv: -kv[1])))
        if c == 1:
            dev = max(abs(w.get(n, 0) - preds[i]['field'].get(n, {}).get('w', 0)) for n in set(w) | set(preds[i]['field']))
            assert dev < 1e-9, f'c = 1 should replay v2: iteration {i} off by {dev}'
    return out

def main():
    for c in CS:
        out = replay(c)
        if c == 1: print('c = 1 replays v2 exactly'); continue
        d = os.path.join(V2, f'cal{c:.2f}'); os.makedirs(d, exist_ok=True)
        for i, p in out.items(): json.dump(p, open(os.path.join(d, f'sp_pred_{i}.json'), 'w'), indent=1)
        top = sorted(out[ITERS]['field'].items(), key=lambda kv: -kv[1]['w'])[:8]
        print(f"c = {c:.2f}, iteration {ITERS}: " + ', '.join(f"{n} {100 * t['w']:.0f}%" for n, t in top) + f"; {len(out[ITERS]['field'])} kept")

if __name__ == '__main__': main()
