"""Per-archetype Trick Room multipliers for the lead sims, from the 2v2 endgame.
usage: python3 eg_trmult.py <eg_summary.json> <out.json>
The lead model credits Trick Room up after turn one with 0.638 x tanh((their Speed - mine)/15) on the logit (fit on replays).
The 2v2 says how much Trick Room is actually worth for this team against each archetype (dTR = win share with 3 turns up
minus with none). We keep the replay fit's overall size (the share-weighted average worth is unchanged) and redistribute it
across archetypes in proportion to dTR: mult_a = (k x dTR_a) / current_a, k = avg(current) / avg(dTR). Negative dTR -> 0.
"""
import json, math, sys, os, collections
S = json.load(open('tr_speeds_inc2.json')); E = json.load(open(sys.argv[1]))
SH = {'Tailwind goodstuffs': 26.2, 'Indeedee TR / Psychic Terrain': 11.9, 'Sun': 12.0, 'Rain': 10.5, 'Balance, no speed control': 9.3, 'Sand': 9.0,
      'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
if os.environ.get('ARCH_W'): SH = json.load(open(os.environ['ARCH_W']))['arch_share']   # e.g. the ladder/regional blend
c = collections.defaultdict(list)
for k, v in S.items(): c[k.split('|')[0]].append(math.tanh((v['t'] - v['m']) / 15))
cur = {a: 1 / (1 + math.exp(-0.638 * sum(x) / len(x))) - 0.5 for a, x in c.items()}
d = {a: max(0.0, E['tr'][a]['mean']) for a in SH}
tot = sum(SH.values()); k = sum(SH[a] * cur[a] for a in SH) / sum(SH[a] * d[a] for a in SH)
out = {}
print(f"{'archetype':30s} {'lead model now':>14s} {'2v2 dTR':>8s} {'new':>6s} {'mult':>5s}")
for a in sorted(SH, key=lambda a: -SH[a]):
    tgt = k * d[a]
    # multiplier on the credit s such that sigma(0.638 * m * s) - 0.5 = tgt
    s = sum(c[a]) / len(c[a]); m = (math.log((0.5 + tgt) / (0.5 - tgt)) / 0.638 / s) if tgt > 0 else 0.0
    out[a] = round(m, 3)
    print(f"{a[:30]:30s} {100*cur[a]:+13.1f}  {100*E['tr'][a]['mean']:+7.1f}  {100*tgt:+5.1f}  {m:5.2f}")
json.dump(out, open(sys.argv[2], 'w'), indent=1); print('k =', round(k, 3))
