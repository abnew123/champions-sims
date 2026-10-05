"""Decider for the sheet's picks (2026-10-04): per archetype, each candidate (lead, back) combo's win share in results/battle_pick_c* (seeds
keyed on the opponent, so combos are compared game by game) plus all earlier full battles (pooled), and the paired difference from the best
candidate with its standard error. Writes the chosen combo per archetype (best decider mean; archetypes not in the decider keep the
pooled leader from battle_pick_cands.json) to battle_picks_final.json.
usage: python3 battle_pick_decide.py"""
import json, glob, math, collections
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
C = json.load(open('battle_pick_cands.json'))
R = collections.defaultdict(lambda: collections.defaultdict(dict))     # arch -> combo -> (pair, g) -> v
share = {}
for f in glob.glob('results/battle_pick_c*/*.json'):
    r = json.load(open(f)); key = ('+'.join(r['lead']), '+'.join(r['back'])); share[(r['arch'], r['pair'])] = r['share']
    for g in r['rows']:
        if g.get('v') is not None: R[r['arch']][key][(r['pair'], g['g'])] = g['v']
def wmean(a, key):
    by = collections.defaultdict(list)
    for (pair, g), v in R[a][key].items(): by[pair].append(v)
    W = sum(share[(a, p)] for p in by); return sum(share[(a, p)] * sum(v) / len(v) for p, v in by.items()) / W, sum(len(v) for v in by.values())
final = {}
for a in SH:
    if a not in R:
        c = C[a][0]; final[a] = {'lead': c['lead'], 'back': c['back'], 'v': c['v'], 'n': c['n'], 'source': 'pooled'}
        print(f"\n{a}: pooled leader {'+'.join(c['lead'])} / {'+'.join(c['back'])} {100*c['v']:.0f}% ({c['n']} games)"); continue
    rows = sorted(((wmean(a, k), k) for k in R[a]), key=lambda x: -x[0][0])
    (bv, bn), bk = rows[0]
    print(f"\n{a}:")
    for (v, n), k in rows:
        pooled = next((c for c in C[a] if '+'.join(c['lead']) == k[0] and '+'.join(c['back']) == k[1]), None)
        if k == bk: d = ''
        else:   # paired difference vs the best on shared (opposing lead, game) cells, share-weighted per opposing lead
            by = collections.defaultdict(list)
            for cell, x in R[a][k].items():
                if cell in R[a][bk]: by[cell[0]].append(x - R[a][bk][cell])
            W = sum(share[(a, p)] for p in by); m = sum(share[(a, p)] * sum(v) / len(v) for p, v in by.items()) / W
            var = sum((share[(a, p)] / W) ** 2 * (sum((y - sum(v) / len(v)) ** 2 for y in v) / max(1, len(v) - 1)) / len(v) for p, v in by.items())
            d = f"  {100*m:+.1f} ± {100*math.sqrt(var):.1f} vs the best"
        print(f"   {k[0]:24s} / {k[1]:24s} decider {100*v:5.1f}% ({n} games); pooled earlier {100*pooled['v']:.0f}% ({pooled['n']}){d}" if pooled else
              f"   {k[0]} / {k[1]} decider {100*v:.1f}% ({n})")
    final[a] = {'lead': bk[0].split('+'), 'back': bk[1].split('+'), 'v': round(bv, 3), 'n': bn, 'source': 'decider'}
json.dump(final, open('battle_picks_final.json', 'w'), indent=1)
W = sum(SH.values()); print(f"\nladder-weighted win share of the final picks: {100*sum(SH[a]*final[a]['v'] for a in SH)/W:.1f}%")
