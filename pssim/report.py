# Detailed turn-1 plan for one archetype + lead: python3 report.py <resultsDir> "<arch>" "<Lead1+Lead2>"
import json, glob, sys, numpy as np
from analyze import solve
d, arch, lead = sys.argv[1:4]
rs = [json.load(open(f)) for f in glob.glob(d + '/*.json')]
rs = sorted([r for r in rs if r['arch'] == arch and '+'.join(r['myLead']) == lead], key=lambda r: -r['share'])
def stat(r, s, x, M, key):
    S = np.array([[np.nan if v is None else v for v in row] for row in r[key]], float)
    ok = ~np.isnan(np.array([[np.nan if v is None else v for v in row] for row in r['A']], float)).any(axis=1); S = S[ok]
    tot = 0
    for g in s['groups'].values():
        cols = g['cols']; j = cols[int(np.argmin((x @ M)[cols]))]; tot += g['p'] * float(x @ S[:, j])
    return tot
for r in rs:
    s = solve(r); acts = s['acts']
    print(f"\n### vs {r['pair']} (share {r['share']:.3f}, n={r['n']}, seeds {r['seeds']}) back {'+'.join(r['myBack'])}")
    print('their T1 (per mon, replay):', '; '.join(sorted({g.split(' | ')[0] for g in s['groups']})), '/', '; '.join(sorted({g.split(' | ')[1] for g in s['groups']})))
    print(f"(b) exploit value {s['vb']:.3f}  [if they fully adapt to it: {s['exploit_b']:.3f}]")
    for i in np.argsort(-s['xb']):
        if s['xb'][i] < 0.03: break
        print(f"    {s['xb'][i]:.2f}  {acts[i]}   (pure {s['pb'][i]:.3f})")
    print('    top pure:', ' || '.join(f"{s['pb'][i]:.3f} {acts[i]}" for i in np.argsort(-s['pb'])[:5]))
    print(f"    outcomes under (b): my KOs taken {stat(r, s, s['xb'], s['Ab'], 'koMine'):.2f}, their KOs taken {stat(r, s, s['xb'], s['Ab'], 'koTheirs'):.2f}, TW net {stat(r, s, s['xb'], s['Ab'], 'tw'):+.2f}, their TR up {stat(r, s, s['xb'], s['Ab'], 'tr'):.2f}")
    print(f"(c) Nash value {s['vc']:.3f}  [Nash mix vs the ladder: {s['nash_vs_pop']:.3f}]")
    for i in np.argsort(-s['xc']):
        if s['xc'][i] < 0.03: break
        print(f"    me {s['xc'][i]:.2f}  {acts[i]}")
    for j in np.argsort(-s['yc']):
        if s['yc'][j] < 0.03: break
        print(f"    them {s['yc'][j]:.2f}  {r['thActs'][j]['label']}")
