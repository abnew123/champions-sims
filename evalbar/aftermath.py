"""Does the engine undervalue setting up and switching? Real-game outcomes against the engine's rating of the positions right after: every
evaluated turn of the cached Showdown Bo3 games (evalpos output, full information), marked with what each side did the turn before and
the boosts it has now, against who won.
  rows       per position: game, turn, value (one-turn lookahead), static (the value function at the position), feats, y (Player 1 won),
             and per side: set up last turn (a status move that raises the user's own stats), switched last turn (a chosen switch, not a
             replacement after a faint), positive boost stages on its active Pokemon now
  residuals  value and static are each rescaled to real outcomes on all positions (one logistic weight, as accuracy.py), then for the
             positions where a side set up or switched, or holds boosts: that side's actual win rate minus its predicted win chance,
             with a standard error from resampling games. Positive = the engine underrates that side. Each side's
             overall residual (Player 1 does a few points worse than rated in this set) is taken out first.
  python3 evalbar/aftermath.py [evalpos output=evalbar/out/acc_eval_sym2.jsonl]   -> evalbar/out/aftermath_rows.jsonl and the table
Needs numpy: run it with the main folder's .venv python."""
import os, sys, json, math, collections
import numpy as np
import common as C, procs as P, replay as R
E = json.load(open(os.path.join(C.MAIN, 'native', 'engine_data_full.json')))
STATS = ('atk', 'def', 'spa', 'spd', 'spe')
def setup(move):
    m = E['moves'].get(R.toid(move), {})
    return m.get('category') == 'Status' and m.get('target') in ('self', 'adjacentAllyOrSelf') and any(v > 0 for v in (m.get('boosts') or {}).values())
def rows(evf):
    ev = {}
    for l in open(evf):
        d = json.loads(l)
        if d.get('value') is not None and d['name'].endswith(' p1'): ev[d['name'][:-3]] = d
    out = []
    for rid, log in C.games():
        if not any(k.startswith(rid + ' ') for k in ev): continue
        try: g = R.parse(log)
        except Exception: continue
        if g['winner'] is None: continue
        steps = {s['turn']: s for s in g['steps']}
        for t, s in steps.items():
            e = ev.get(f'{rid} t{t}')
            if not e or t < 2 or t - 1 not in steps: continue
            prev = steps[t - 1]['acts']; mark = {}
            for sd in ('p1', 'p2'):
                acts = [a for pos, a in prev.items() if pos.startswith(sd) and a]
                on = [m for m in s['state'][sd]['mons'] if m.get('pos') and not m['f']]
                mark[sd] = {'setup': any('move' in a and setup(a['move']) for a in acts), 'switched': any('switch' in a for a in acts),
                            'boosts': sum(max(0, m['b'].get(k, 0)) for m in on for k in STATS)}
            out.append({'g': rid, 't': t, 'value': e['value'], 'static': e['static'], 'feats': e['feats'], 'y': 1 if g['winner'] == 'p1' else 0, **{
                f'{sd}_{k}': v for sd in ('p1', 'p2') for k, v in mark[sd].items()}})
    return out
logit = lambda p: math.log(min(1 - 1e-4, max(1e-4, p)) / (1 - min(1 - 1e-4, max(1e-4, p))))
def fit_scale(x, y):
    """one logistic weight on the log-odds, fitted symmetrically (each row and its mirror)"""
    X = np.concatenate([x, -x]); Y = np.concatenate([y, 1 - y]); w = 1.0
    for _ in range(50):
        p = 1 / (1 + np.exp(-w * X)); g = ((Y - p) * X).sum(); h = (p * (1 - p) * X * X).sum(); w += g / h
    return w
def residual(R_, pred, side_of, bias=None):
    """that side's mean (won - predicted), less that side's mean over all positions (bias: Player 1 does worse than rated in this set),
    and a standard error from resampling games"""
    bias = bias or {'p1': 0, 'p2': 0}
    items = [(r['g'], (r['y'] if s == 'p1' else 1 - r['y']) - (p if s == 'p1' else 1 - p) - bias[s]) for r, p in zip(R_, pred) for s in side_of(r)]
    if not items: return 0, 0, 0
    by = collections.defaultdict(list)
    for g, d in items: by[g].append(d)
    G = list(by); rng = np.random.default_rng(0); mean = sum(d for _, d in items) / len(items)
    bs = []
    for _ in range(1000):
        pick = rng.integers(0, len(G), len(G)); v = [d for i in pick for d in by[G[i]]]; bs.append(sum(v) / len(v))
    return mean, float(np.std(bs)), len(items)
def main(evf):
    R_ = rows(evf); y = np.array([r['y'] for r in R_], float)
    with open(os.path.join(C.HERE, 'out', 'aftermath_rows.jsonl'), 'w') as f:
        for r in R_: f.write(json.dumps(r) + '\n')
    print(f"{len(R_)} positions from {len({r['g'] for r in R_})} games (turn 2 on)")
    subsets = [('set up last turn', lambda r: [s for s in ('p1', 'p2') if r[f'{s}_setup']]),
               ('switched last turn', lambda r: [s for s in ('p1', 'p2') if r[f'{s}_switched']]),
               ('both: set up, and not the other side', lambda r: [s for s in ('p1', 'p2') if r[f'{s}_setup'] and not r[f"{'p2' if s == 'p1' else 'p1'}_setup"]]),
               ('holds +1 or +2 boosts', lambda r: [s for s in ('p1', 'p2') if 1 <= r[f'{s}_boosts'] <= 2]),
               ('holds +3 or more boosts', lambda r: [s for s in ('p1', 'p2') if r[f'{s}_boosts'] >= 3]),
               ('everything (check: near 0)', lambda r: ['p1'])]
    for name in ('value', 'static'):
        x = np.array([logit(r[name]) for r in R_]); w = fit_scale(x, y); pred = 1 / (1 + np.exp(-w * x))
        b1 = residual(R_, pred, lambda r: ['p1'])[0]; bias = {'p1': b1, 'p2': -b1}
        print(f"\n{name} (rescaled with weight {w:.3f} on its log-odds; Player 1 does {100 * b1:+.1f} points against it overall, taken out below):"
              f" that side's actual win rate minus predicted")
        for label, f in subsets[:-1]:
            m, se, n = residual(R_, pred, f, bias)
            print(f"  {label:38s} {n:6d}  {100 * m:+5.1f} points ± {100 * se:.1f}")
if __name__ == '__main__':
    P.own()
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(C.HERE, 'out', 'acc_eval_sym2.jsonl'))
