import numpy as np, final4 as F
k = ('Perish trap', 'Salamence+Kingambit', 'Gengar + Vivillon'); r, s = F.res[k]
Ab, Ac, groups, keepc, A = s['Ab'], s['Ac'], s['groups'], s['keepc'], s['acts']
th = r['thActs']
rows = ['Salamence: Hyper Voice | Kingambit: Sucker Punch -> Gengar', 'Salamence: Hyper Voice | Kingambit: Kowtow Cleave -> Gengar',
        'Salamence: Tailwind | Kingambit: Kowtow Cleave -> Gengar', 'Salamence: Protect | Kingambit: Kowtow Cleave -> Gengar',
        'Salamence: Double-Edge -> Gengar | Kingambit: Kowtow Cleave -> Gengar', 'Salamence: Hyper Voice | Kingambit: Kowtow Cleave -> Vivillon',
        'Salamence: Double-Edge -> Gengar | Kingambit: Sucker Punch -> Gengar']
idx = [A.index(a) if a in A else None for a in rows]
print('rows present:', [a for a, i in zip(rows, idx) if i is not None])
print('\ncol p  keep  their action' + ''.join(f'  {j}' for j in range(len(rows))))
for j, t in enumerate(th):
    print(f"{t['p']:.3f} {'K' if keepc[j] else ' '} {t['label'][:66]:66s} " + '  '.join(f"{Ab[i, j]:.3f}" if i is not None else '  -  ' for i in idx))
for a, i in zip(rows, idx):
    if i is None: continue
    x = np.zeros(len(A)); x[i] = 1
    pop = sum(g['p'] * (x @ Ab)[g['cols']].min() for g in groups.values()); worst = (x @ Ac)[keepc].min()
    wj = int(np.argmin(np.where(keepc, x @ Ac, 9)))
    print(f"{a:70s} ladder {pop:.3f}  reader {worst:.3f}  (reader's reply: {th[wj]['label']})")
print('\ngroups (their per-Pokemon move choices, targets adversarial):')
for g, v in groups.items(): print(f"  {v['p']:.3f}  {g}")
