# Pick previously-missing leads worth a 12-seed run: stage-1 blend within MARGIN of the archetype's stage-1 top.
# Rows kept per cell: top-12 by exploit value plus anything in the exploit / Nash / blend mixes (same rule as sal_select.py).
import json, glob, os, sys, numpy as np
os.environ['EXCLUDE_MOVES'] = 'Make It Rain'
from analyze import solve
MARGIN = float(sys.argv[1]) if len(sys.argv) > 1 else 0.05; NROW = 12
rank = json.load(open('miss_rank.json'))
jobs = json.load(open('jobs_miss.json'))
pick = []
for arch, leads in rank.items():
    top = max(v[0] for v in leads.values())
    for lead, (b, p, q, new, ref) in leads.items():
        if new and b >= top - MARGIN: pick.append((arch, lead, b, top))
for a, l, b, t in sorted(pick): print(f'{a:30s} {l:24s} stage-1 {b:.3f}  top {t:.3f}  gap {100 * (t - b):.1f}')
sel = []
for i, j in enumerate(jobs):
    if not any(j['arch'] == a and '+'.join(sorted(j['lead'])) == l for a, l, _, _ in pick): continue
    r = json.load(open(f'results/miss1/{i}.json')); s = solve(r); acts = s['acts']
    keep = set(np.argsort(-s['pb'])[:NROW]) | set(np.where(s['xb'] > 0.02)[0]) | set(np.where(s['xc'] > 0.02)[0]) | set(np.where(s['xm'] > 0.02)[0])
    sel.append(dict(j, rows=[acts[k] for k in sorted(keep)], missing=[acts[k] for k in sorted(keep)]))
items = [dict(j) for j in sel if 'Indeedee-F' in j['pair'].split(' + ')]
json.dump(sel, open('sel_miss.json', 'w')); json.dump(sel, open('jobs_miss2.json', 'w')); json.dump(items, open('jobs_miss2_items.json', 'w'))
print(f'{len(pick)} leads, {len(sel)} jobs, {sum(len(j["rows"]) for j in sel)} rows; item-variant jobs {len(items)}')
