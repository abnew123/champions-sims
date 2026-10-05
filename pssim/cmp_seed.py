# Indeedee leads: Colbur Berry (tr_final.json) vs Psychic Seed (tr_final_seed.json), fitted win model, 0.5 ladder + 0.5 reader.
import json
A = json.load(open('tr_final.json')); B = json.load(open('tr_final_seed.json'))
print(f"{'archetype':32s} {'lead':22s} {'Colbur':>7s} {'Seed':>7s} {'diff':>6s}   top lead (Colbur run)")
tot = {}
for arch, T in B['leads'].items():
    va = {v[0]: v for v in A['leads'][arch]['all']['vals']}; top = A['leads'][arch]['all']['vals'][0]
    for v in T['all']['vals']:
        l = v[0]; a = va[l]; d = 100 * (v[3] - a[3]); tot.setdefault(l, []).append(d)
        print(f"{arch[:32]:32s} {l:22s} {100*a[3]:7.1f} {100*v[3]:7.1f} {d:+6.1f}   {top[0]} {100*top[3]:.1f}")
print()
for l, ds in tot.items(): print(f"{l:22s} mean change {sum(ds)/len(ds):+.2f} over {len(ds)} archetypes")
print('\nper opposing lead (largest moves):')
rows = []
for k, p in B['plans'].items():
    if k in A['plans']:
        pa = A['plans'][k]; rows.append((100 * ((p['pop'] + p['worst']) / 2 - (pa['pop'] + pa['worst']) / 2), k, p['share']))
rows.sort()
for d, k, sh in rows[:6] + rows[-6:]: print(f"  {d:+6.1f}  {k.replace('||', ' | ')}  (share {100*sh:.1f}%)")
