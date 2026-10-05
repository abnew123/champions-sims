# Page data for the Salamence-first Leads tab.
# Rounds every plan to 5% steps, re-scores the rounded mix on the solver matrices, applies the multi-turn Perish overrides,
# recomputes each lead's value (overall and per team-preview tell) from those same displayed lines, and writes leads_v40.json.
import json, math, numpy as np
import final6 as F   # re-runs the merge + solves (same inputs as final4.json)

def round5(lines):
    v = [100 * x for x, _ in lines]; base = [5 * math.floor(x / 5) for x in v]; rem = [x - b for x, b in zip(v, base)]
    for i in sorted(range(len(v)), key=lambda i: -rem[i])[: (100 - sum(base)) // 5]: base[i] += 5
    return [(b, a) for b, (_, a) in zip(base, lines) if b > 0]

def score(k, mix):
    r, s = F.res[k]; Ab, Ac, groups, keepc, acts = s['Ab'], s['Ac'], s['groups'], s['keepc'], s['acts']
    x = np.zeros(len(acts))
    for p, a in mix: x[acts.index(a)] += p / 100
    assert abs(x.sum() - 1) < 1e-9
    return float(sum(g['p'] * (x @ Ab)[g['cols']].min() for g in groups.values())), float((x @ Ac)[keepc].min())

# Considered and dropped: forcing turn-1 Double-Edge on Gengar (perishgame.js). It only helps when Gengar Protects twice in a row
# (escape 79% vs 71%) and costs ~5.5 points on turn one whenever Gengar Protects turn one, so the solver's turn-1 mix stays.
OVR_DROPPED = {('Perish trap', 'Salamence+Kingambit', 'Gengar + Incineroar'): 'Salamence: Double-Edge -> Gengar | Kingambit: Low Kick -> Incineroar',
       ('Perish trap', 'Salamence+Kingambit', 'Gengar + Rillaboom'): 'Salamence: Double-Edge -> Gengar | Kingambit: Kowtow Cleave -> Gengar'}

P = {}
for k in F.res:
    if k not in F.SIMPLE: F.SIMPLE[k] = F.simple(k)
    sp = F.SIMPLE[k]
    if k in {}:
        mix = [(100, OVR[k])]; solver_mix = round5(sp['lines'])
    else:
        mix = round5(sp['lines']); solver_mix = None
    pop, worst = score(k, mix)
    P[k] = {'mix': mix, 'pop': pop, 'worst': worst, 'exact': (sp['pop'], sp['worst']), 'share': sp['share'], 'back': sp['back'],
            'itemMix': sp['itemMix'], 'reader': sp['reader'], 'solverMix': solver_mix,
            'solverVal': score(k, solver_mix) if solver_mix else None}

def lead_value(arch, lead, ws=None):
    rows = [(ws.get(k[2], 0) if ws is not None else P[k]['share'], P[k]['pop'], P[k]['worst']) for k in P if k[0] == arch and k[1] == lead]
    W = sum(w for w, _, _ in rows)
    return None if not rows or W == 0 else (sum(w * a for w, a, _ in rows) / W, sum(w * b for w, _, b in rows) / W)

out = {'leads': {}, 'plans': {}}
for arch in sorted({k[0] for k in P}):
    conds = [('all', None)] + [(f"{ck.split(' | ')[1]} {'yes' if i == 0 else 'no'}", {p: x[i] for p, x in F.cond[ck].items()})
                               for ck in F.cond if ck.split(' | ')[0] == arch for i in (0, 1)]
    out['leads'][arch] = {}
    for tag, ws in conds:
        vals = {l: lead_value(arch, l, ws) for l in sorted({k[1] for k in P if k[0] == arch})}
        vals = {l: v for l, v in vals.items() if v}
        out['leads'][arch][tag] = {'weights': ws, 'vals': sorted([[l, v[0], v[1], (v[0] + v[1]) / 2] for l, v in vals.items()], key=lambda x: -x[3])}
for k, v in P.items(): out['plans']['||'.join(k)] = v
json.dump(out, open('leads_v41.json', 'w'), indent=1)

for arch, tags in out['leads'].items():
    for tag, d in tags.items():
        top = d['vals'][0]
        sal = [x for x in d['vals'] if 'Salamence' in x[0].split('+')]
        print(f"{arch[:26]:26s} {tag:16s} top {top[0]:22s} {top[3]:.4f} | " + ', '.join(f"{x[0]} {x[3]:.4f} ({100 * (top[3] - x[3]):.1f})" for x in sal[:4]))
