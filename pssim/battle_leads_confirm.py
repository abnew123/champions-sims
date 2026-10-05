"""Confirmation of the full-battle lead picks (2026-10-03): each archetype's top-2 combos replayed on fresh seeds (results/battle_leads3,
games 8-23) vs the sheet's plan on the same seeds (results/b32_v5a, games 8-23). Win share weighted by opposing-lead replay share."""
import json, glob, math, collections
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
def load(d, gs=None):
    R = collections.defaultdict(lambda: collections.defaultdict(dict))
    for f in glob.glob(d + '/*.json'):
        r = json.load(open(f)); key = ('+'.join(r['lead']), '+'.join(r['back']))
        R[r['arch']][key][r['pair']] = (r['share'], [g['v'] for g in r['rows'] if g.get('v') is not None and (gs is None or g['g'] in gs)])
    return R
def score(by):
    W = sum(s for s, vs in by.values() if vs); v = sum(s * sum(vs) / len(vs) for s, vs in by.values() if vs) / W
    n = sum(len(vs) for _, vs in by.values()); return v, math.sqrt(max(v * (1 - v), 0.02) / n), n
C = load('results/battle_leads3'); S = load('results/b32_v5a', set(range(8, 24)))
tot = {'sheet': 0.0, 'best': 0.0}; W = sum(SH.values())
for a in SH:
    (sk, sby), = S[a].items(); sv, sse, sn = score(sby)
    rows = sorted(((score(by), key) for key, by in C[a].items()), key=lambda x: -x[0][0])
    print(f"\n{a}  (share {SH[a]})\n   sheet {sk[0]:24s} back {sk[1]:24s} {100*sv:5.1f} ±{100*sse:3.0f} ({sn} games)")
    for (v, se, n), key in rows: print(f"   new   {key[0]:24s} back {key[1]:24s} {100*v:5.1f} ±{100*se:3.0f} ({n} games)  {100*(v-sv):+5.1f}")
    best = max([sv] + [r[0][0] for r in rows])
    tot['sheet'] += SH[a] * sv; tot['best'] += SH[a] * best
print(f"\nladder-weighted on fresh seeds: sheet plans {100*tot['sheet']/W:.1f}% | best confirmed per archetype {100*tot['best']/W:.1f}%")
