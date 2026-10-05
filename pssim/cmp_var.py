# Leads re-simulated with one item changed vs the current sheet (tr_final_v7.json); fitted model, 0.5 ladder + 0.5 reader.
import json, sys
A = json.load(open('tr_final_v7.json')); B = json.load(open(sys.argv[1])); label = sys.argv[2] if len(sys.argv) > 2 else 'variant'
W = {'Tailwind goodstuffs': 26.2, 'Indeedee TR / Psychic Terrain': 11.9, 'Sun': 12.0, 'Rain': 10.5, 'Balance, no speed control': 9.3, 'Sand': 9.0,
     'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}          # archetype shares of M-C teams
print(f"{'archetype':30s} {'lead':22s} {'now':>6s} {label:>8s} {'diff':>6s}  (top lead now)")
per = {}; better = worse = 0
for arch, T in B['leads'].items():
    va = {v[0]: v for v in A['leads'][arch]['all']['vals']}; top = A['leads'][arch]['all']['vals'][0]
    for v in T['all']['vals']:
        a = va[v[0]]; d = 100 * (v[3] - a[3]); per.setdefault(v[0], []).append((arch, d)); better += d > 0.05; worse += d < -0.05
        print(f"{arch[:30]:30s} {v[0]:22s} {100*a[3]:6.1f} {100*v[3]:8.1f} {d:+6.1f}  ({top[0]} {100*top[3]:.1f})")
print(f"\nbetter in {better}, worse in {worse} lead/archetype pairs")
for l, xs in per.items():
    wsum = sum(W[a] for a, _ in xs); print(f"  {l:22s} archetype-weighted change {sum(W[a]*d for a, d in xs)/wsum:+.2f} over {len(xs)} archetypes")
rows = sorted((100 * ((p['pop'] + p['worst']) / 2 - (A['plans'][k]['pop'] + A['plans'][k]['worst']) / 2), k) for k, p in B['plans'].items() if k in A['plans'])
print('largest moves by opposing lead:'); [print(f"  {d:+6.1f}  {k.replace('||', ' | ')}") for d, k in rows[:5] + rows[-5:]]
