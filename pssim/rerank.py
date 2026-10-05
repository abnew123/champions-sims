# Stage-1 re-rank with turn-1 Make It Rain excluded; pick leads + rows for a refined pass (reusing refined cells already simulated).
import json, glob, collections, os, numpy as np
os.environ['EXCLUDE_MOVES'] = 'Make It Rain'
from analyze import solve
NROW = 12
def load_dir(d):
    out = {}
    for fn in glob.glob(d + '/*.json'):
        r = json.load(open(fn)); out[(r['arch'], '+'.join(r['myLead']), r['pair'])] = r
    return out
s1 = {**load_dir('results/s1'), **{k: v for k, v in load_dir('results/p1').items()}}   # Perish from the perish-aware run
s2 = {**load_dir('results/s2'), **{k: v for k, v in load_dir('results/p2').items()}}
jobs1 = json.load(open('jobs_s1.json'))
by = collections.defaultdict(lambda: collections.defaultdict(list)); sol = {}
for key, r in s1.items():
    s = solve(r); sol[key] = s; by[r['arch']][key[1]].append((r['share'], s))
sel = []; summary = {}
for arch, leads in by.items():
    rows = []
    for lead, L in leads.items():
        w = np.array([x[0] for x in L]); pm = np.array([x[1]['pop_m'] for x in L]); wm = np.array([x[1]['worst_m'] for x in L]); vc = np.array([x[1]['vc'] for x in L])
        rows.append((float(((w * pm).sum() + (w * wm).sum()) / 2 / w.sum()), float((w * vc).sum() / w.sum()), lead))
    rows.sort(reverse=True); summary[arch] = rows
    pick = [l for _, _, l in rows[:3]]
    for _, _, l in sorted(rows, key=lambda x: -x[1])[:2]:
        if l not in pick: pick.append(l)
    if arch == 'Perish trap' and 'Kingambit+Gholdengo' not in pick: pick.append('Kingambit+Gholdengo')
    for l in pick:
        for key in [k for k in s1 if k[0] == arch and k[1] == l]:
            s = sol[key]; acts = s['acts']
            keep = set(np.argsort(-s['pb'])[:NROW]) | set(np.where(s['xb'] > 0.02)[0]) | set(np.where(s['xc'] > 0.02)[0]) | set(np.where(s['xm'] > 0.02)[0])
            want = [acts[k] for k in sorted(keep)]
            have = set(s2[key]['myActs']) if key in s2 else set()
            job = next(j for j in jobs1 if j['arch'] == arch and '+'.join(j['lead']) == l and j['pair'] == key[2])
            sel.append(dict(job, rows=want, missing=[a for a in want if a not in have], has_s2=key in s2))
for arch, rows in summary.items():
    print(f'\n{arch}:'); [print(f'   {b:.3f} nash {c:.3f} {l}') for b, c, l in rows[:5]]
todo = [dict(j, rows=j['missing']) for j in sel if j['missing']]
json.dump(sel, open('sel_s3.json', 'w')); json.dump(todo, open('jobs_s3.json', 'w'))
cells = 0
for j in todo:
    r = s1[(j['arch'], '+'.join(j['lead']), j['pair'])]; cells += len(j['rows']) * len(r['thActs'])
print(f'\n{len(sel)} refined jobs; {len(todo)} need new rows; {cells} cells/seed -> ~{cells*12*5.8/1000/60/2:.0f} min on 2 cores at 12 seeds')
