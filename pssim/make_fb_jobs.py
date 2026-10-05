# Refinement jobs for Farigiraf+Blastoise in the two archetypes where it was not a contender (Rain, Trick Room without Indeedee).
# Rows kept exactly as tr_select.py keeps them, under both the fitted and the doubled Trick Room weights (union).
import json, numpy as np
from trlib import load
from analyze import solve, W2
NROW = 12; W1 = W2.copy(); Wx2 = W2.copy(); Wx2[8] *= 2
res = load('results/tr1'); jobs = json.load(open('jobs_tr1.json')); base = json.load(open('jobs_tr2.json'))
new = []
for j in jobs:
    if j['arch'] not in ('Rain', 'Trick Room without Indeedee') or j['lead'] != ['Farigiraf', 'Blastoise']: continue
    k = (j['arch'], 'Farigiraf+Blastoise', j['pair']); keep = set(); acts = None
    for W in (W1, Wx2):
        s = solve(res[k], W); acts = s['acts']
        keep |= set(np.argsort(-s['pb'])[:NROW]) | set(np.where(s['xb'] > 0.02)[0]) | set(np.where(s['xc'] > 0.02)[0]) | set(np.where(s['xm'] > 0.02)[0])
    new.append(dict(j, rows=[acts[i] for i in sorted(keep)]))
    print(j['arch'], '|', j['pair'], '|', len(keep), 'rows of', len(acts))
json.dump(base + new, open('jobs_tr2_plus.json', 'w'))
print('jobs', len(base), '->', len(base) + len(new))
