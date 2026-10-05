# Lead values conditional on a team-preview tell (pair shares from the replays, conditional on the tell)
import json, glob, collections, re, sys
from analyze import solve
txt = open('cond_shares.txt').read()
C = {}
for line in txt.strip().split('\n'):
    k, v = line.split('": "'); k = k.strip().strip('"'); v = v.rstrip('",')
    C[k] = {m.group(1): (float(m.group(2)), float(m.group(3))) for m in re.finditer(r'([^;:]+?): yes ([\d.]+) / no ([\d.]+)', v)}
    C[k] = {p.strip(): x for p, x in C[k].items()}
dirs = sys.argv[1:] or ['results/s2']
R = [json.load(open(f)) for d in dirs for f in glob.glob(d + '/*.json')]
V = collections.defaultdict(dict)
for r in R: s = solve(r); V[(r['arch'], '+'.join(r['myLead']))][r['pair']] = (s['pop_m'] + s['worst_m']) / 2
for k, sh in C.items():
    arch, tell = k.split(' | ')
    print(f'\n{arch}, {tell} in their six:')
    for (a, lead), vals in sorted(V.items()):
        if a != arch: continue
        out = []
        for idx, lab in ((0, 'yes'), (1, 'no')):
            w = {p: sh[p][idx] for p in vals if p in sh}; tot = sum(w.values())
            out.append(f"{lab}: {sum(w[p] * vals[p] for p in w) / tot:.3f} (covers {tot:.0f}%)" if tot > 0 else f'{lab}: n/a')
        print(f'   {lead:22s} ' + '   '.join(out))
