# Unrefined leads that might top an archetype at the current reader weight: first-pass values (1 sample) for all 15 Incineroar-team
# leads next to the refined values in tr_final_inc_r75.json.
import json, collections, numpy as np, os
from trlib import load, solved
LAM = float(os.environ.get('READER_W', '0.5'))
def fp(d, skip):
    res = load(d); by = collections.defaultdict(lambda: collections.defaultdict(list))
    for k, r in res.items():
        if skip(k[1]): continue
        s = solved(r); by[k[0]][k[1]].append((r['share'], s['pop_m'], s['worst_m']))
    out = {}
    for arch, leads in by.items():
        for lead, L in leads.items():
            w = np.array([x[0] for x in L]); out[(arch, lead)] = ((1 - LAM) * (w * np.array([x[1] for x in L])).sum() + LAM * (w * np.array([x[2] for x in L])).sum()) / w.sum()
    return out
F = {**fp('results/tr1', lambda l: 'Hatterene' in l), **fp('results/c_incin', lambda l: False)}
R = json.load(open('tr_final_inc_r75.json'))
for arch in sorted({a for a, _ in F}):
    ref = {x[0]: x[3] for x in R['leads'][arch]['all']['vals']}; top = max(ref.values())
    rows = sorted(((v, l) for (a, l), v in F.items() if a == arch), reverse=True)
    flag = [(l, v) for v, l in rows if l not in ref and v >= top - 0.03]
    print(f"{arch[:28]:28s} refined top {100*top:.1f} | first-pass: " + ', '.join(f"{l} {100*v:.1f}{'' if l in ref else '*'}" for v, l in rows[:5]) + (f"   << CHECK {flag}" if flag else ''))
