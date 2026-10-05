# Stage 1 ranking of all 15 leads per archetype (1 sample per cell), then pick contenders for a 12-sample refinement.
import json, sys, os, collections, numpy as np
from trlib import load, solved
# usage: python3 tr_select.py [margin] [cap] [--write] [--res results/tr1] [--jobs jobs_tr1.json] [--out jobs_tr2]
#   ranks each archetype's leads on stage-one results and writes <out>.json + <out>_items.json (Indeedee-F item variants).
#   Ranking uses READER_W (weight on the reader number, default 0.5); set TR_SPEEDS for another team's speed file.
def opt(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default
RES, JOBS, OUT = opt('--res', 'results/tr1'), opt('--jobs', 'jobs_tr1.json'), opt('--out', 'jobs_tr2')
LAM = float(os.environ.get('READER_W', '0.5'))
num = [a for a in sys.argv[1:3] if not a.startswith('--')]
MARGIN = float(num[0]) if len(num) > 0 else 0.05; CAP = int(num[1]) if len(num) > 1 else 5; NROW = 12
res = load(RES); sol = {k: solved(r) for k, r in res.items()}
by = collections.defaultdict(lambda: collections.defaultdict(list))
for k, s in sol.items(): by[k[0]][k[1]].append((res[k]['share'], s['pop_m'], s['worst_m']))
rank = {}
for arch in sorted(by):
    rows = []
    for lead, L in by[arch].items():
        w = np.array([x[0] for x in L]); p = (w * np.array([x[1] for x in L])).sum() / w.sum(); q = (w * np.array([x[2] for x in L])).sum() / w.sum()
        rows.append(((1 - LAM) * p + LAM * q, p, q, lead, len(L)))
    rows.sort(reverse=True); rank[arch] = rows
    print(f'\n## {arch}  ({len(rows)} leads)')
    for b, p, q, l, n in rows: print(f'  {l:22s} {b:.3f}  [{p:.3f}/{q:.3f}] cells {n}{"  <- " if b >= rows[0][0] - MARGIN else ""}')
if '--write' in sys.argv:
    jobs = json.load(open(JOBS)); pick = {}
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
    json.dump(sel, open(OUT + '.json', 'w')); json.dump(items, open(OUT + '_items.json', 'w')); json.dump(pick, open(OUT + '_pick.json', 'w'), indent=1)
    print(f'\npicked {sum(len(v) for v in pick.values())} leads -> {len(sel)} jobs, {sum(len(j["rows"]) for j in sel)} rows; Indeedee-F item jobs {len(items)}')
