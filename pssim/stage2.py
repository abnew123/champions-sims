# Build stage-2 jobs: top leads per archetype from stage 1, re-simulated with more seeds on the rows that matter.
import json, glob, sys, numpy as np, collections
from analyze import solve
TOPL = int(sys.argv[1]) if len(sys.argv) > 1 else 3; NROW = int(sys.argv[2]) if len(sys.argv) > 2 else 12
S1DIR = sys.argv[3] if len(sys.argv) > 3 else 'results/s1'; JF = sys.argv[4] if len(sys.argv) > 4 else 'jobs_s1.json'; OUT = sys.argv[5] if len(sys.argv) > 5 else 'jobs_s2.json'
jobs = json.load(open(JF))
res = {}
for fn in glob.glob(S1DIR + '/*.json'):
    r = json.load(open(fn)); res[r['job']] = (r, solve(r))
by = collections.defaultdict(lambda: collections.defaultdict(list))
for i, (r, s) in res.items(): by[r['arch']]['+'.join(r['myLead'])].append((r['share'], s['vb'], s['vc'], i))
out = []
for arch, leads in by.items():
    score = {l: sum(w * vb for w, vb, vc, i in L) / sum(w for w, *_ in L) for l, L in leads.items()}
    scorec = {l: sum(w * vc for w, vb, vc, i in L) / sum(w for w, *_ in L) for l, L in leads.items()}
    top = sorted(score, key=lambda l: -score[l])[:TOPL]
    for l in sorted(scorec, key=lambda l: -scorec[l])[:2]:
        if l not in top: top.append(l)
    print(arch, top)
    for l in top:
        for w, vb, vc, i in leads[l]:
            r, s = res[i]; acts = s['acts']
            keep = set(np.argsort(-s['pb'])[:NROW]) | set(np.where(s['xb'] > 0.02)[0]) | set(np.where(s['xc'] > 0.02)[0])
            j = dict(jobs[i]); j['rows'] = [acts[k] for k in sorted(keep)]; j['s1'] = i; out.append(j)
json.dump(out, open(OUT, 'w'))
print(len(out), 'jobs', sum(len(j['rows']) * (j['cells'] // max(1, len(res[j['s1']][0]['myActs']))) for j in out), 'cells/seed')
