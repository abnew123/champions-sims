"""The eval number's unit (chess shows +1.3 next to the win chance; its unit is a pawn): here one Pokemon. Over every turn of the cached
Showdown Bo3 games, how much one Pokemon more left (of the four brought) moves the log-odds of winning: a logistic fit of the result on the
difference in Pokemon left, symmetric (each turn also seen from the other side). The page shows log-odds of its win chance divided by this,
so +1.0 means as far ahead as being a whole Pokemon up, on average.
  python3 evalbar/unit.py        -> evalbar/results/eval_unit.json"""
import os, sys, json, math
import common as C, procs as P, replay as R
def fit(x, y):
    w = 0.5
    for _ in range(60):
        g = h = 0.0
        for xi, yi in zip(x, y):
            for a, b in ((xi, yi), (-xi, 1 - yi)):
                p = 1 / (1 + math.exp(-w * a)); g += (b - p) * a; h += p * (1 - p) * a * a
        w += g / h
    return w
if __name__ == '__main__':
    P.own()
    x, y, games = [], [], 0
    for rid, log in C.games():
        try: g = R.parse(log)
        except Exception: continue
        if g['winner'] is None or g['forfeit']: continue
        games += 1
        for st in g['steps']:
            if st['turn'] < 1: continue
            left = {sd: 4 - sum(1 for m in st['state'][sd]['mons'] if m['f']) for sd in ('p1', 'p2')}
            x.append(left['p1'] - left['p2']); y.append(1 if g['winner'] == 'p1' else 0)
    w = fit(x, y)
    by = {}
    for xi, yi in zip(x, y): by.setdefault(xi, []).append(yi)
    out = {'unit_logodds': round(w, 3), 'games': games, 'turns': len(x), 'win_rate_by_difference': {str(k): [round(sum(v) / len(v), 3), len(v)] for k, v in sorted(by.items())}}
    json.dump(out, open(os.path.join(C.HERE, 'results', 'eval_unit.json'), 'w'), indent=1); print(json.dumps(out))
