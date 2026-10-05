# Split-half noise of refined lead values: solve each lead on samples 1-6 and 7-12 separately (item-mixed like tr_final),
# SD of a 12-sample lead value ~ SD(half difference)/2.
import sys, copy, collections, numpy as np
from trlib import load, solved, key
ITEMW = {'rockyhelmet': 0.47, 'colburberry': 0.31, 'psychicseed': 0.20}
def half_vals(REF, half):
    base = load(REF); items = {it: load(REF + '_' + it) for it in ('colburberry', 'psychicseed')}
    by = collections.defaultdict(list)
    for k, r in base.items():
        vs = {'rockyhelmet': r}
        if 'Indeedee-F' in r['pair'].split(' + ') and all(k in items[it] for it in items): vs.update({it: items[it][k] for it in items})
        out = copy.deepcopy(r); tot = sum(ITEMW[i] for i in vs)
        out['F'] = [[sum(([fx for fx in v['F'][i][j][half * 6:(half + 1) * 6] for _ in range(round(100 * ITEMW[it] / tot))] for it, v in vs.items()), [])
                     for j in range(len(r['thActs']))] for i in range(len(r['myActs']))]
        s = solved(out); by[(k[0], k[1])].append((r['share'], (s['pop_m'] + s['worst_m']) / 2))
    return {kk: sum(w * v for w, v in L) / sum(w for w, _ in L) for kk, L in by.items()}
for REF in sys.argv[1:]:
    a, b = half_vals(REF, 0), half_vals(REF, 1)
    d = np.array([a[k] - b[k] for k in a]); print(f"{REF}: {len(d)} leads, SD(half diff) {100*d.std():.2f} -> SD of a 12-sample lead value ~ {100*d.std()/2:.2f} points")
