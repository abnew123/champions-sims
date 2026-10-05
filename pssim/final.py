# Stage-2 summary: lead values per archetype and per-pair plans for the recommended lead.
import json, glob, sys, collections, numpy as np
from analyze import solve, lp_c, fixed_point, matrices
d = sys.argv[1] if len(sys.argv) > 1 else 'results/s2'
R = [json.load(open(f)) for f in glob.glob(d + '/*.json')]
S = {}
for r in R: S[id(r)] = solve(r)
by = collections.defaultdict(lambda: collections.defaultdict(list))
for r in R: by[r['arch']]['+'.join(r['myLead'])].append(r)
def simple_mix(r, s, k=3):
    """best Nash-style mix using only the top-k actions of the full Nash mix (their double-Protect excluded)"""
    A, N, wp0 = matrices(r)
    dbl = np.array([all(part.split(': ', 1)[1].split(' -> ')[0] in ('Protect', 'Detect') for part in a.split(' | ')) for a in r['myActs']])
    ok = ~np.isnan(A).any(axis=1) & ~dbl; A = A[ok]; N = N[ok]
    PROT = ('Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Baneful Bunker', 'Silk Trap', 'Burning Bulwark', 'Obstruct')
    keepc = np.array([not all(p.split(':', 1)[1] in PROT for p in t['group'].split(' | ')) for t in r['thActs']])
    idx = np.argsort(-s['xc'])[:k]
    v, x, y, _ = fixed_point(lp_c, A[idx][:, keepc], N[idx][:, keepc], wp0, 0.5)
    return v, [(float(x[i]), s['acts'][idx[i]]) for i in range(len(idx)) if x[i] > 0.02]
out = {}
for arch, leads in by.items():
    rows = []
    for lead, L in leads.items():
        w = np.array([r['share'] for r in L]); vb = np.array([S[id(r)]['vb'] for r in L]); vc = np.array([S[id(r)]['vc'] for r in L])
        pm = np.array([S[id(r)]['pop_m'] for r in L]); wm = np.array([S[id(r)]['worst_m'] for r in L])
        rows.append(dict(lead=lead, vb=float((w * vb).sum() / w.sum()), vc=float((w * vc).sum() / w.sum()), n=len(L),
                         pop_m=float((w * pm).sum() / w.sum()), worst_m=float((w * wm).sum() / w.sum())))
    for x in rows: x['blend'] = (x['pop_m'] + x['worst_m']) / 2
    rows.sort(key=lambda x: -x['blend'])
    print(f'\n===== {arch}')
    for x in rows: print(f"   {x['lead']:24s} exploit {x['vb']:.3f}  nash {x['vc']:.3f}  | blend plan: vs ladder {x['pop_m']:.3f}, vs a reader {x['worst_m']:.3f}  (pairs {x['n']})")
    best = rows[0]['lead']; out[arch] = {'leads': rows, 'plans': []}
    for r in sorted(leads[best], key=lambda r: -r['share']):
        s = S[id(r)]; i = int(np.argmax(s['xb'])); sv, sm = simple_mix(r, s)
        plan = dict(pair=r['pair'], share=r['share'], back=r['myBack'], vb=s['vb'], exploit_play=[(float(s['xb'][j]), s['acts'][j]) for j in np.argsort(-s['xb']) if s['xb'][j] > 0.03],
                    adapt=s['exploit_b'], vc=s['vc'], nash=[(float(s['xc'][j]), s['acts'][j]) for j in np.argsort(-s['xc']) if s['xc'][j] > 0.03],
                    simple=sm, simple_v=sv, nash_vs_pop=s['nash_vs_pop'],
                    their_nash=[(float(s['yc'][j]), r['thActs'][j]['label']) for j in np.argsort(-s['yc']) if s['yc'][j] > 0.05])
        out[arch]['plans'].append(plan)
        print(f"  vs {r['pair']} ({100*r['share']:.1f}% of {arch} games) | back {'+'.join(r['myBack'])}")
        print(f"     exploit {s['vb']:.3f} (if they adapt {s['exploit_b']:.3f}): " + ' / '.join(f'{p:.2f} {a}' for p, a in plan['exploit_play']))
        print(f"     nash {s['vc']:.3f} (vs ladder {s['nash_vs_pop']:.3f}); 3-action mix {sv:.3f}: " + ' / '.join(f'{p:.2f} {a}' for p, a in sm))
        plan['blend'] = [(float(s['xm'][j]), s['acts'][j]) for j in np.argsort(-s['xm']) if s['xm'][j] > 0.03]; plan['blend_pop'] = s['pop_m']; plan['blend_worst'] = s['worst_m']
        print(f"     BLEND (vs ladder {s['pop_m']:.3f}, vs reader {s['worst_m']:.3f}): " + ' / '.join(f'{p:.2f} {a}' for p, a in plan['blend']))
        print(f"     their best replies: " + ' / '.join(f'{p:.2f} {a}' for p, a in plan['their_nash']))
json.dump(out, open(d + '_final.json', 'w'), indent=1)
