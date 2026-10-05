# Stage-1 values for all leads (turn-1 Make It Rain excluded); pick Salamence leads to refine and their rows.
import json, glob, os, collections, numpy as np
os.environ['EXCLUDE_MOVES'] = 'Make It Rain'
from analyze import solve
NROW = 12; MARGIN = 0.08
def key(r): return (r['arch'], '+'.join(r['myLead']), r['pair'])
def load_dir(d):
    out = {}
    for fn in glob.glob(d + '/*.json'): r = json.load(open(fn)); out[key(r)] = r
    return out
s1 = {**load_dir('results/s1'), **load_dir('results/p1'), **load_dir('results/sal1')}
s1 = {k: v for k, v in s1.items() if not (k[0] == 'Perish trap' and v.get('F') and len(v['F'][0][0][0]) == 12)}  # Perish must come from the perish-aware runs
refined = {**load_dir('results/s2'), **load_dir('results/p2'), **load_dir('results/s3')}
jobs_all = json.load(open('jobs_s1.json')) + json.load(open('jobs_sal.json'))
sol = {k: solve(r) for k, r in s1.items()}
by = collections.defaultdict(lambda: collections.defaultdict(list))
for k, s in sol.items(): by[k[0]][k[1]].append((s1[k]['share'], s))
sel = []; report = []
for arch, leads in by.items():
    val = {}
    for lead, L in leads.items():
        w = np.array([x[0] for x in L]); pm = np.array([x[1]['pop_m'] for x in L]); wm = np.array([x[1]['worst_m'] for x in L])
        val[lead] = float(((w * pm).sum() + (w * wm).sum()) / 2 / w.sum())
    top = max(val.values())
    sal = sorted([(v, l) for l, v in val.items() if 'Salamence' in l.split('+')], reverse=True)
    # his defaults (Salamence + Kingambit / + Rillaboom) when within reach, plus the best other Salamence lead if it beats both
    dv = {l: v for v, l in sal if l.split('+')[0 if l.startswith('Salamence') else 1] and ('Kingambit' in l or 'Rillaboom' in l)}
    pick = [l for l, v in dv.items() if v >= top - 0.10]
    others = [(v, l) for v, l in sal if l not in dv]
    if others and others[0][0] > max(dv.values(), default=0) and others[0][0] >= top - MARGIN: pick.append(others[0][1])
    report.append((arch, top, max(val, key=val.get), sal))
    for l in pick:
        for k in [k for k in s1 if k[0] == arch and k[1] == l]:
            s = sol[k]; acts = s['acts']
            keep = set(np.argsort(-s['pb'])[:NROW]) | set(np.where(s['xb'] > 0.02)[0]) | set(np.where(s['xc'] > 0.02)[0]) | set(np.where(s['xm'] > 0.02)[0])
            want = [acts[i] for i in sorted(keep)]
            have = set(refined[k]['myActs']) if k in refined else set()
            job = next(j for j in jobs_all if j['arch'] == arch and '+'.join(j['lead']) == l and j['pair'] == k[2])
            sel.append(dict(job, rows=want, missing=[a for a in want if a not in have]))
for arch, top, tl, sal in report:
    print(f'{arch:30s} top(stage1) {top:.3f} {tl:24s} | ' + ', '.join(f'{l} {v:.3f}' for v, l in sal[:5]))
todo = [dict(j, rows=j['missing']) for j in sel if j['missing']]
items = [dict(j) for j in sel if 'Indeedee-F' in j['pair'].split(' + ')]
json.dump(sel, open('sel_sal.json', 'w')); json.dump(todo, open('jobs_sal2.json', 'w')); json.dump(items, open('jobs_sal2_items.json', 'w'))
cells = sum(len(j['rows']) * len(s1[(j['arch'], '+'.join(j['lead']), j['pair'])]['thActs']) for j in todo)
icells = sum(len(j['rows']) * len(s1[(j['arch'], '+'.join(j['lead']), j['pair'])]['thActs']) for j in items)
print(f'\n{len(sel)} refined Salamence jobs, {len(todo)} need new rows: {cells} cells -> ~{cells*12*5.8/1000/60/2:.0f} min; item variants {len(items)} jobs x2 -> ~{icells*2*12*5.8/1000/60/2:.0f} min')
