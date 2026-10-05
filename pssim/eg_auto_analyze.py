"""Autopilot 2v2 results: win share per pair of yours, overall and by half (common / unusual opposing pairs), and where Indeedee + Torkoal
differs most from the best alternative.  usage: python3 eg_auto_analyze.py results/eg_auto"""
import json, glob, sys, math, collections
R = [json.load(open(f)) for f in glob.glob(sys.argv[1] + '/*.json')]; R = [r for r in R if r['v'] is not None]
by = collections.defaultdict(list); cell = {}
for r in R:
    k = ' + '.join(r['mine']).replace('Indeedee-F', 'Indeedee'); by[(k, r['arch'])] += r['vs']; by[(k, 'all')] += r['vs']; cell[(k, ','.join(r['theirs']))] = r['v']
pairs = sorted({k for k, _ in by}, key=lambda k: -sum(by[(k, 'all')]) / len(by[(k, 'all')]))
se = lambda v: math.sqrt(sum((x - sum(v) / len(v)) ** 2 for x in v) / max(1, len(v) - 1) / len(v))
print(f"{'your pair (autopilot, Trick Room up)':34s} {'all':>12s} {'common':>12s} {'unusual':>12s}   games")
for k in pairs:
    row = [by[(k, h)] for h in ('all', 'common', 'unusual')]
    print(f"{k:34s} " + ' '.join(f"{100*sum(v)/len(v):5.1f} +-{100*se(v):3.1f}" if v else '      -     ' for v in row) + f"   {len(row[0])}")
it = 'Indeedee + Torkoal'; others = [k for k in pairs if k != it]
d = []
for (k, t), v in cell.items():
    if k != it: continue
    alt = max(((cell.get((o, t)), o) for o in others if cell.get((o, t)) is not None), default=None)
    if alt: d.append((v - alt[0], t, v, alt))
d.sort()
print('\nWhere Indeedee + Torkoal does worst vs the best alternative:'); [print(f"   {t:30s} I+T {100*v:3.0f}%  vs {a[1]} {100*a[0]:3.0f}%") for x, t, v, a in d[:6]]
print('Where it does best:'); [print(f"   {t:30s} I+T {100*v:3.0f}%  vs {a[1]} {100*a[0]:3.0f}%") for x, t, v, a in d[-6:]]
