# Why ladder and reader differ for one plan: our fixed mix vs each opposing click (population weight vs worst case).
import json, sys, numpy as np
from trlib import load, solved
arch, lead, pair = sys.argv[1], sys.argv[2], sys.argv[3]; REF = sys.argv[4] if len(sys.argv) > 4 else 'results/v7'
A = json.load(open('tr_final_v7.json')); P = A['plans'][f'{arch}||{lead}||{pair}']
res = load(REF); r = res[(arch, lead, pair)]; s = solved(r)
x = np.zeros(len(s['acts']))
for p, a in P['mix']: x[s['acts'].index(a)] += p / 100
print('plan:', ' / '.join(f"{p}% {a}" for p, a in P['mix']), f"| ladder {100*P['pop']:.1f} reader {100*P['worst']:.1f}")
vb = x @ s['Ab']; vc = x @ s['Ac']
print('\nladder groups (their click type, how often ladder players click it, our win chance vs their best targeting within it):')
for g, d in sorted(s['groups'].items(), key=lambda kv: -kv[1]['p']):
    cols = d['cols']; j = cols[int(np.argmin(vb[cols]))]
    print(f"  {100*d['p']:5.1f}%  {g[:70]:70s} -> {100*vb[cols].min():5.1f}  (worst target: {r['thActs'][j]['label'][:80]})")
print('\nreader: their clicks that do best against this mix:')
for j in np.argsort(vc)[:6]:
    if s['keepc'][j]: print(f"  {100*vc[j]:5.1f}  {r['thActs'][j]['label']}   [ladder clicks this type {100*r['thActs'][j]['p']:.1f}%]")
print('\nour two lines vs the reader click:')
j = int(np.argmin(np.where(s['keepc'], vc, 9)))
for p, a in P['mix']: i = s['acts'].index(a); print(f"  {p}% {a}: {100*s['Ac'][i, j]:.1f}")
