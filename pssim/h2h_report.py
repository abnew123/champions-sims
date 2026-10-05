"""Head-to-head report (h2h_run.sh): for pairs of arms played on the same games, my win share and the paired difference with its
standard error (opposing leads weighted by replay share, archetypes by ladder share).
Reads h2h_arms.txt for the arm names; compares every arm with a baseline arm.
usage: python3 h2h_report.py <baseline arm> <arm> [<arm> ...]     e.g. python3 h2h_report.py old_old new_old old_new new_new"""
import json, glob, sys, math
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
def load(arm):
    R = {}; share = {}
    for f in glob.glob(f'results/h2h_{arm}/*.json'):
        try: r = json.load(open(f))
        except Exception: continue
        R[(r['arch'], r['pair'])] = {g['g']: g['v'] for g in r['rows'] if g.get('v') is not None}; share[(r['arch'], r['pair'])] = r['share']
    return R, share
def total(R, share, skip=()):
    tot = W = 0.0
    for a in SH:
        if a in skip: continue
        ts = [t for t in R if t[0] == a]
        if not ts: continue
        w = sum(share[t] for t in ts); tot += SH[a] * sum(share[t] * sum(R[t].values()) / len(R[t]) for t in ts) / w; W += SH[a]
    return tot / W if W else float('nan')
def paired(A, B, share, skip=()):
    m = var = W = 0.0; per = {}
    for a in SH:
        if a in skip: continue
        ts = [t for t in B if t[0] == a and t in A]
        if not ts: continue
        w = sum(share[t] for t in ts); ma = va = 0.0
        for t in ts:
            d = [B[t][g] - A[t][g] for g in B[t] if g in A[t]]
            if len(d) < 2: continue
            mu = sum(d) / len(d); ma += share[t] / w * mu; va += (share[t] / w) ** 2 * sum((x - mu) ** 2 for x in d) / (len(d) - 1) / len(d)
        per[a] = (ma, math.sqrt(va)); m += SH[a] * ma; var += SH[a] ** 2 * va; W += SH[a]
    return m / W, math.sqrt(var) / W, per
base = sys.argv[1]; A, share = load(base)
print(f"baseline {base}: my win share {100*total(A, share):.1f}% ({sum(len(v) for v in A.values())} games); without Perish {100*total(A, share, ('Perish trap',)):.1f}%")
for arm in sys.argv[2:]:
    B, sh2 = load(arm)
    if not B: print(f"{arm}: no results"); continue
    m, se, per = paired(A, B, share); m9, se9, _ = paired(A, B, share, ('Perish trap',))
    print(f"{arm}: my win share {100*total(B, sh2):.1f}%; vs {base} {100*m:+.1f} ± {100*se:.1f} (without Perish {100*m9:+.1f} ± {100*se9:.1f}) | "
          + ', '.join(f"{a.split(' ')[0].rstrip(',')} {100*v[0]:+.0f}" for a, v in per.items()))
