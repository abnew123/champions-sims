# Old seeding ([k,101,211,307]) vs well-mixed seeds on 12 random refined cells of the old lead sheet.
# If |old - A| is no bigger than |A - B| (two independent well-mixed runs), the old seeding added no error beyond Monte Carlo noise.
import json, os, numpy as np
os.environ['EXCLUDE_MOVES'] = 'Make It Rain'
from analyze import solve
idx = json.load(open('jobs_seedchk_idx.json'))
rows = []
for j, i in enumerate(idx):
    fo, fa, fb = f'results/s2/{i}.json', f'results/seedchkA/{j}.json', f'results/seedchkB/{j}.json'
    if not (os.path.exists(fa) and os.path.exists(fb)): continue
    so, sa, sb = (solve(json.load(open(f))) for f in (fo, fa, fb))
    v = lambda s: np.array([s['pop_m'], s['worst_m'], (s['pop_m'] + s['worst_m']) / 2])
    r = json.load(open(fo)); rows.append((r['arch'], r['pair'], '+'.join(r['myLead']), v(so), v(sa), v(sb)))
for a, p, l, o, x, y in rows: print(f'{a[:22]:22s} {p[:26]:26s} {l:22s} blend old {o[2]:.3f}  A {x[2]:.3f}  B {y[2]:.3f}')
if rows:
    O = np.array([r[3] for r in rows]); A = np.array([r[4] for r in rows]); B = np.array([r[5] for r in rows])
    for k, name in enumerate(['pop', 'worst', 'blend']):
        print(f'{name:6s} mean|old-A| {np.abs(O[:, k] - A[:, k]).mean():.4f}  mean|old-B| {np.abs(O[:, k] - B[:, k]).mean():.4f}  mean|A-B| {np.abs(A[:, k] - B[:, k]).mean():.4f}  mean(old-avg(A,B)) {(O[:, k] - (A[:, k] + B[:, k]) / 2).mean():+.4f}')
    print(len(rows), 'cells')
