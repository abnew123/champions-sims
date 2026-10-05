"""Hatterene vs Incineroar in the 2v2 endgame: same partner, same opposing back pairs, same seeds.
usage: python3 eg_hat_cmp.py <eg1 dir> <eg_hat dir> [tr_final_v7_r75.json tr_final_inc2_r75.json]"""
import json, glob, sys, collections, itertools
def load(d):
    V = {}; W = collections.defaultdict(dict)
    for f in glob.glob(d + '/*.json'):
        r = json.load(open(f))
        if r['v'] is None: continue
        V[(r['arch'], frozenset(r['mine']), ','.join(r['theirs']), r['K'])] = r['v']; W[r['arch']][','.join(r['theirs'])] = r['w']
    return V, W
V1, W = load(sys.argv[1]); V2, _ = load(sys.argv[2]); V = {**V1, **V2}
SH = {'Tailwind goodstuffs': 26.2, 'Indeedee TR / Psychic Terrain': 11.9, 'Sun': 12.0, 'Rain': 10.5, 'Balance, no speed control': 9.3, 'Sand': 9.0,
      'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
FIVE = ['Indeedee-F', 'Farigiraf', 'Torkoal', 'Kingambit', 'Blastoise']
def val(a, pair, K):
    num = den = 0
    for t, w in W[a].items():
        v = V.get((a, frozenset(pair), t, K))
        if v is not None: num += w * v; den += w
    return num / den if den else None
print('### Pair value, Hatterene + X minus Incineroar + X (win share points), averaged over the five partners')
tot = {3: 0, 0: 0}
for a in sorted(SH, key=lambda a: -SH[a]):
    line = f'{a[:28]:28s} {SH[a]:4.1f}%'
    for K in (3, 0):
        ds = [(x, val(a, ['Hatterene', x], K) - val(a, ['Incineroar', x], K)) for x in FIVE
              if val(a, ['Hatterene', x], K) is not None and val(a, ['Incineroar', x], K) is not None]
        m = sum(d for _, d in ds) / len(ds); tot[K] += SH[a] * m
        best = max(ds, key=lambda z: abs(z[1]))
        line += f'   {"TR up" if K else "no TR"} {100*m:+5.1f} (biggest: with {best[0]} {100*best[1]:+.0f})'
    print(line)
s = sum(SH.values()); print(f"weighted: TR up {100*tot[3]/s:+.1f}   no TR {100*tot[0]/s:+.1f}")
