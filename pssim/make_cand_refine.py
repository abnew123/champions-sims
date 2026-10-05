# 12-sample refinement jobs for a sixth-slot candidate's leads that came within MARGIN of the best first-pass lead (current or new).
import json, sys, os, collections, numpy as np
from trlib import load
from analyze import solve, W2
tag = sys.argv[1]; MARGIN = float(sys.argv[2]) if len(sys.argv) > 2 else 0.03; CAP = 2; NROW = 12
W1 = W2.copy(); Wx2 = W2.copy(); Wx2[8] *= 2
LAM = float(os.environ.get('READER_W', '0.5'))   # weight on the reader number when ranking leads
def first_pass(d):
    res = load(d); by = collections.defaultdict(lambda: collections.defaultdict(list)); sols = {}
    for k, r in res.items():
        s = solve(r, W1); sols[k] = (r, s); by[k[0]][k[1]].append((r['share'], s['pop_m'], s['worst_m']))
    val = {}
    for arch, leads in by.items():
        for lead, L in leads.items():
            w = np.array([x[0] for x in L]); val[(arch, lead)] = ((1 - LAM) * (w * np.array([x[1] for x in L])).sum() + LAM * (w * np.array([x[2] for x in L])).sum()) / w.sum()
    return val, sols
cur, _ = first_pass(os.environ.get('BASE1', 'results/tr1'))   # stage-one results of the team being compared against; cand, sols = first_pass(f'results/c_{tag}')
pick = {}
for arch in sorted({a for a, _ in cand}):
    top = max([v for (a, _), v in cur.items() if a == arch] + [v for (a, _), v in cand.items() if a == arch])
    rows = sorted(((v, l) for (a, l), v in cand.items() if a == arch and v >= top - MARGIN), reverse=True)[:CAP]
    if rows: pick[arch] = [l for _, l in rows]
jobs = json.load(open(f'jobs_c_{tag}.json')); out = []
for j in jobs:
    k = (j['arch'], '+'.join(j['lead']), j['pair'])
    if k[1] not in pick.get(j['arch'], []): continue
    r, _ = sols[k]; keep = set(); acts = None
    for W in (W1, Wx2):
        s = solve(r, W); acts = s['acts']
        keep |= set(np.argsort(-s['pb'])[:NROW]) | set(np.where(s['xb'] > 0.02)[0]) | set(np.where(s['xc'] > 0.02)[0]) | set(np.where(s['xm'] > 0.02)[0])
    out.append(dict(j, rows=[acts[i] for i in sorted(keep)]))
items = [j for j in out if 'Indeedee-F' in j['pair'].split(' + ')]
json.dump(out, open(f'jobs_r_{tag}.json', 'w')); json.dump(items, open(f'jobs_r_{tag}_items.json', 'w'))
print(tag, {a: l for a, l in pick.items()}); print(len(out), 'jobs,', len(items), 'item-variant jobs')
