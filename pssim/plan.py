# Blend plan per opposing lead: python3 plan.py <dir> "<arch>" "<Lead1+Lead2>"
import json, glob, sys, numpy as np
from analyze import solve
d, arch, lead = sys.argv[1:4]
rs = sorted([r for r in (json.load(open(f)) for f in glob.glob(d + '/*.json')) if r['arch'] == arch and '+'.join(r['myLead']) == lead], key=lambda r: -r['share'])
def outcome(r, s, x, key):
    S = np.array([[np.nan if v is None else v for v in row] for row in r[key]], float)
    A = np.array([[np.nan if v is None else v for v in row] for row in r['A']], float)
    dbl = np.array([all(part.split(': ', 1)[1].split(' -> ')[0] in ('Protect', 'Detect') for part in a.split(' | ')) for a in r['myActs']])
    S = S[~np.isnan(A).any(axis=1) & ~dbl]
    return sum(g['p'] * float(x @ S[:, g['cols'][int(np.argmin((x @ s['Ab'])[g['cols']]))]]) for g in s['groups'].values())
for r in rs:
    s = solve(r)
    print(f"\nvs {r['pair']} ({100*r['share']:.1f}%) back {'+'.join(r['myBack'])}: blend {s['pop_m']:.3f}/{s['worst_m']:.3f}; exploit {s['vb']:.3f} (adapted {s['exploit_b']:.3f}); nash {s['vc']:.3f}")
    for j in np.argsort(-s['xm']):
        if s['xm'][j] < 0.03: break
        print(f"    {s['xm'][j]:.2f} {s['acts'][j]}")
    x = s['xm']
    print(f"    outcomes: their KOs {outcome(r, s, x, 'koTheirs'):.2f}, my KOs {outcome(r, s, x, 'koMine'):.2f}, TW net {outcome(r, s, x, 'tw'):+.2f}, their TR {outcome(r, s, x, 'tr'):.2f}")
    print('    exploit pure:', s['acts'][int(np.argmax(s['xb']))])
    print('    reader replies:', ' / '.join(f"{s['yc'][j]:.2f} {r['thActs'][j]['label']}" for j in np.argsort(-s['yc']) if s['yc'][j] > 0.08))
