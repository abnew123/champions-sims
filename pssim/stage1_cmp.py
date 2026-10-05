# First-pass (1 sample) lead values: the current 15 lead pairs (results/tr1) next to each candidate's five new pairs.
import json, collections, numpy as np, sys, os
from trlib import load, solved
def values(d):
    res = load(d); by = collections.defaultdict(lambda: collections.defaultdict(list))
    for k, r in res.items():
        s = solved(r); by[k[0]][k[1]].append((r['share'], s['pop_m'], s['worst_m']))
    out = {}
    for arch, leads in by.items():
        for lead, L in leads.items():
            w = np.array([x[0] for x in L]); p = (w * np.array([x[1] for x in L])).sum() / w.sum(); q = (w * np.array([x[2] for x in L])).sum() / w.sum()
            LAM = float(os.environ.get('READER_W', '0.5')); out[(arch, lead)] = ((1 - LAM) * p + LAM * q, len(L))
    return out
cur = values(os.environ.get('BASE1', 'results/tr1'))           # stage-one results of the team being compared against
tags = [t for t in sys.argv[1:] if os.path.isdir(f'results/c_{t}')]
cand = {t: values(f'results/c_{t}') for t in tags}
archs = sorted({a for a, _ in cur})
for arch in archs:
    rows = sorted(((v[0], l, 'now') for (a, l), v in cur.items() if a == arch), reverse=True)
    top = rows[0]; hat = next((r for r in rows if os.environ.get('DROP', 'Hatterene') in r[1]), (0, 'none', 'now'))
    line = f"{arch[:28]:28s} top now {top[1]:22s} {100*top[0]:.1f} | best {os.environ.get('DROP', 'Hatterene')} {hat[1]:22s} {100*hat[0]:.1f}"
    for t in tags:
        cr = sorted(((v[0], l) for (a, l), v in cand[t].items() if a == arch), reverse=True)
        if cr: line += f" | best {t}: {cr[0][1]} {100*cr[0][0]:.1f} ({100*(cr[0][0]-top[0]):+.1f})"
    print(line)
