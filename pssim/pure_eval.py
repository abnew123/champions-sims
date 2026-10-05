# value (vs ladder / vs reader) of a fixed pure turn-1 line, for the lines I override by hand
import json, os, sys, numpy as np
os.environ['EXCLUDE_MOVES'] = 'Make It Rain'
import final3  # rebuilds merged results in final3.res
from analyze import solve
def pure(arch, lead, pair, label):
    r, s = final3.res[(arch, lead, pair)]; i = s['acts'].index(label); x = np.zeros(len(s['acts'])); x[i] = 1
    pop = float(sum(g['p'] * (x @ s['Ab'])[g['cols']].min() for g in s['groups'].values())); worst = float((x @ s['Ac'])[s['keepc']].min())
    return round(pop, 3), round(worst, 3)
print('Perish G+I lead:', pure('Perish trap', 'Kingambit+Gholdengo', 'Gengar + Incineroar', 'Kingambit: Low Kick -> Incineroar | Gholdengo: Shadow Ball -> Gengar'))
print('Perish Gengar+Vivillon:', pure('Perish trap', 'Kingambit+Gholdengo', 'Gengar + Vivillon', 'Kingambit: Sucker Punch -> Gengar | Gholdengo: Shadow Ball -> Gengar'))
