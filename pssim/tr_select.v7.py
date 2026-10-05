# Stage 1 ranking of all 15 leads per archetype (1 sample per cell), then pick contenders for a 12-sample refinement.
import json, sys, collections, numpy as np
from trlib import load, solved
MARGIN = float(sys.argv[1]) if len(sys.argv) > 1 else 0.05; CAP = int(sys.argv[2]) if len(sys.argv) > 2 else 5; NROW = 12
res = load('results/tr1'); sol = {k: solved(r) for k, r in res.items()}
by = collections.defaultdict(lambda: collections.defaultdict(list))
for k, s in sol.items(): by[k[0]][k[1]].append((res[k]['share'], s['pop_m'], s['worst_m']))
rank = {}
for arch in sorted(by):
    rows = []
    for lead, L in by[arch].items():
        w = np.array([x[0] for x in L]); p = (w * np.array([x[1] for x in L])).sum() / w.sum(); q = (w * np.array([x[2] for x in L])).sum() / w.sum()
        rows.append(((p + q) / 2, p, q, lead, len(L)))
    rows.sort(reverse=True); rank[arch] = rows
    print(f'\n## {arch}  ({len(rows)} leads)')
    for b, p, q, l, n in rows: print(f'  {l:22s} {b:.3f}  [{p:.3f}/{q:.3f}] cells {n}{"  <- " if b >= rows[0][0] - MARGIN else ""}')
if '--write' in sys.argv:
    jobs = json.load(open('jobs_tr1.json')); pick = {}
    for arch, rows in rank.items():
        top = rows[0][0]; pick[arch] = [l for b, p, q, l, n in rows if b >= top - MARGIN][:CAP]
    sel = []
    for j in jobs:
        k = (j['arch'], '+'.join(j['lead']), j['pair'])
        if k[1] not in pick.get(j['arch'], []) or k not in sol: continue
        s = sol[k]; acts = s['acts']
        keep = set(np.argsort(-s['pb'])[:NROW]) | set(np.where(s['xb'] > 0.02)[0]) | set(np.where(s['xc'] > 0.02)[0]) | set(np.where(s['xm'] > 0.02)[0])
        sel.append(dict(j, rows=[acts[i] for i in sorted(keep)]))
    items = [j for j in sel if 'Indeedee-F' in j['pair'].split(' + ')]
    json.dump(sel, open('jobs_tr2.json', 'w')); json.dump(items, open('jobs_tr2_items.json', 'w')); json.dump(pick, open('tr_pick.json', 'w'), indent=1)
    print(f'\npicked {sum(len(v) for v in pick.values())} leads -> {len(sel)} jobs, {sum(len(j["rows"]) for j in sel)} rows; Indeedee-F item jobs {len(items)}')
