import json, glob, sys, collections
from analyze import solve
d = sys.argv[1]; arch_f = sys.argv[2] if len(sys.argv) > 2 else None
R = [json.load(open(f)) for f in glob.glob(d + '/*.json')]
T = collections.defaultdict(dict); shares = {}
for r in R:
    if arch_f and r['arch'] != arch_f: continue
    s = solve(r); T[(r['arch'], '+'.join(r['myLead']))][r['pair']] = (s['pop_m'], s['worst_m']); shares[(r['arch'], r['pair'])] = r['share']
archs = sorted({a for a, l in T})
for a in archs:
    pairs = sorted({p for (aa, l), v in T.items() if aa == a for p in v}, key=lambda p: -shares[(a, p)])
    print(f'\n{a}: ' + ' | '.join(f"{p} {100*shares[(a,p)]:.1f}%" for p in pairs))
    for (aa, l), v in sorted(T.items()):
        if aa != a: continue
        print(f'  {l:22s} ' + '  '.join(f"{v[p][0]:.2f}/{v[p][1]:.2f}" if p in v else '   --    ' for p in pairs))
