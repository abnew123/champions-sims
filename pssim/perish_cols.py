import numpy as np, final4 as F
for pair, acts in [('Gengar + Incineroar', ['Salamence: Hyper Voice | Kingambit: Low Kick -> Incineroar', 'Salamence: Double-Edge -> Gengar | Kingambit: Low Kick -> Incineroar', 'Salamence: Hyper Voice | Kingambit: Kowtow Cleave -> Gengar']),
                   ('Gengar + Rillaboom', ['Salamence: Hyper Voice | Kingambit: Kowtow Cleave -> Rillaboom', 'Salamence: Protect | Kingambit: Kowtow Cleave -> Gengar', 'Salamence: Double-Edge -> Gengar | Kingambit: Kowtow Cleave -> Gengar'])]:
    k = ('Perish trap', 'Salamence+Kingambit', pair); r, s = F.res[k]
    Ab, Ac, groups, keepc, A = s['Ab'], s['Ac'], s['groups'], s['keepc'], s['acts']
    th = [t['label'] for t in r['thActs']]; p = [t['p'] for t in r['thActs']]
    print('\n##', pair)
    idx = [A.index(a) for a in acts]
    for j, t in enumerate(th):
        print(f"{p[j]:.3f} {'K' if keepc[j] else ' '} {t[:70]:70s} " + '  '.join(f"{Ab[i, j]:.3f}/{Ac[i, j]:.3f}" for i in idx))
    for i, a in zip(idx, acts):
        x = np.zeros(len(A)); x[i] = 1
        pop = sum(g['p'] * (x @ Ab)[g['cols']].min() for g in groups.values()); worst = (x @ Ac)[keepc].min()
        print(f"   {a}: pop {pop:.3f} worst {worst:.3f}")
