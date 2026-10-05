# Trick Room team sheet data: merge refined matchups (+ opposing Indeedee-F item variants), credit Trick Room to the slower
# team, solve, simplify each plan to a few lines, round to 5%, re-score as rounded, and value every lead per archetype and tell.
import json, glob, os, sys, copy, re, math, collections, numpy as np
from trlib import load, solved, key
from analyze import lp_blend
LAM = float(os.environ.get('READER_W', '0.5'))   # weight on the reader number (0.5: even blend)
def BL(pop, worst): return (1 - LAM) * pop + LAM * worst
REF = sys.argv[1] if len(sys.argv) > 1 else 'results/tr2'
ITEMW = {'rockyhelmet': 0.47, 'colburberry': 0.31, 'psychicseed': 0.20}
base = load(REF); items = {it: load(REF + '_' + it) for it in ('colburberry', 'psychicseed')}
def mix_items(r):
    k = key(r)
    if 'Indeedee-F' not in r['pair'].split(' + '): return r, False
    if not all(k in items[it] for it in items): return r, 'missing'
    out = copy.deepcopy(r); variants = {'rockyhelmet': r, **{it: items[it][k] for it in items}}; tot = sum(ITEMW.values())
    for v in variants.values(): assert v['myActs'] == r['myActs'] and [t['label'] for t in v['thActs']] == [t['label'] for t in r['thActs']], k
    # mix per cell and per sample: stack the three variants' feature samples with their weights by repeating rows (12 samples each)
    F = []
    for i in range(len(r['myActs'])):
        row = []
        for j in range(len(r['thActs'])):
            cell = []
            for it, v in variants.items():
                w = round(100 * ITEMW[it] / tot)
                cell += [fx for fx in v['F'][i][j] for _ in range(w)]
            row.append(cell)
        F.append(row)
    out['F'] = F
    return out, True
res = {}
for k, r in base.items():
    r, mixed = mix_items(r); r['itemMix'] = mixed; res[k] = (r, solved(r))
def simple(k):
    r, s = res[k]; Ab, Ac, groups, keepc, acts = s['Ab'], s['Ac'], s['groups'], s['keepc'], s['acts']
    full = BL(s['pop_m'], s['worst_m']); order = list(np.argsort(-s['xm'])); best = None; singles = []
    for i in range(len(acts)):
        x = np.zeros(len(acts)); x[i] = 1
        pop = float(sum(g['p'] * (x @ Ab)[g['cols']].min() for g in groups.values())); worst = float((x @ Ac)[keepc].min()); singles.append((BL(pop, worst), pop, worst, i))
    singles.sort(reverse=True)
    for idx in [[singles[0][3]]] + [order[:m] for m in (2, 3)] + [[singles[0][3], jj] for jj in order[:3] if jj != singles[0][3]]:
        idx = list(dict.fromkeys(idx))
        if len(idx) == 1: xs = np.zeros(len(acts)); xs[idx[0]] = 1; pop, worst = singles[0][1], singles[0][2]
        else: xr, pop, worst = lp_blend(Ab[idx], Ac[idx], groups, keepc, LAM); xs = np.zeros(len(acts)); xs[idx] = xr
        if BL(pop, worst) >= full - 0.005 and (best is None or (xs > 0.03).sum() < (best[0] > 0.03).sum()): best = (xs, pop, worst)
    if best is None: xr, pop, worst = lp_blend(Ab[order[:3]], Ac[order[:3]], groups, keepc, LAM); xs = np.zeros(len(acts)); xs[order[:3]] = xr; best = (xs, pop, worst)
    xs, pop, worst = best
    return {'lines': sorted([(float(xs[i]), acts[i]) for i in range(len(acts)) if xs[i] > 0.03], reverse=True), 'pop': pop, 'worst': worst, 'full': (s['pop_m'], s['worst_m']),
            'reader': [(float(s['yc'][i]), r['thActs'][i]['label']) for i in np.argsort(-s['yc']) if s['yc'][i] > 0.1][:3], 'share': r['share'], 'back': r['myBack'],
            'itemMix': r['itemMix'], 'trCredit': r['trCredit']}
def round5(lines):
    v = [100 * x for x, _ in lines]; b = [5 * math.floor(x / 5) for x in v]; rem = [x - y for x, y in zip(v, b)]
    for i in sorted(range(len(v)), key=lambda i: -rem[i])[: (100 - sum(b)) // 5]: b[i] += 5
    return [(y, a) for y, (_, a) in zip(b, lines) if y > 0]
def score(k, mix):
    r, s = res[k]; Ab, Ac, groups, keepc, acts = s['Ab'], s['Ac'], s['groups'], s['keepc'], s['acts']
    x = np.zeros(len(acts))
    for p, a in mix: x[acts.index(a)] += p / 100
    assert abs(x.sum() - 1) < 1e-9
    return float(sum(g['p'] * (x @ Ab)[g['cols']].min() for g in groups.values())), float((x @ Ac)[keepc].min())
import trlib
from analyze import solve as _solve, W2 as _W2
def score_on(s, mix):
    Ab, Ac, groups, keepc, acts = s['Ab'], s['Ac'], s['groups'], s['keepc'], s['acts']
    x = np.zeros(len(acts))
    for p, a in mix: x[acts.index(a)] += p / 100
    return float(sum(g['p'] * (x @ Ab)[g['cols']].min() for g in groups.values())), float((x @ Ac)[keepc].min())
P = {}
for k in res:
    sp = simple(k); mix = round5(sp['lines']); pop, worst = score(k, mix)
    P[k] = dict(sp, mix=mix, pop=pop, worst=worst, lines=None)
    if trlib.W[8] != _W2[8]:                      # Trick Room reweighted: also score this plan with the fitted weights
        P[k]['pop1'], P[k]['worst1'] = score_on(_solve(res[k][0], _W2), mix)
cond = {}
for line in open('cond_shares.txt').read().strip().split('\n'):
    kk, v = line.split('": "'); kk = kk.strip().strip('"'); v = v.rstrip('",')
    cond[kk] = {m.group(1).strip(): (float(m.group(2)), float(m.group(3))) for m in re.finditer(r'([^;:]+?): yes ([\d.]+) / no ([\d.]+)', v)}
# PAIR_RATIO: reweight their lead pairs by how common the two Pokemon are once regional teams are blended in (regionals/blend_weights.py),
# keeping each archetype's (and each tell's) total weight unchanged
if os.environ.get('PAIR_RATIO'):
    RAT = json.load(open(os.environ['PAIR_RATIO']))['ratio']
    fr = lambda arch, pair: math.prod(RAT.get(arch, {}).get(m, 1.0) for m in pair.split(' + '))
    for arch in {k[0] for k in P}:
        sh = {k[2]: P[k]['share'] for k in P if k[0] == arch}
        tot, new = sum(sh.values()), {p: v * fr(arch, p) for p, v in sh.items()}
        scale = tot / sum(new.values())
        for k in P:
            if k[0] == arch: P[k]['share_ladder'] = P[k]['share']; P[k]['share'] = new[k[2]] * scale
    for ck, d in cond.items():
        arch = ck.split(' | ')[0]
        for i in (0, 1):
            tot = sum(x[i] for x in d.values()); nw = {p: x[i] * fr(arch, p) for p, x in d.items()}; sc = tot / sum(nw.values()) if sum(nw.values()) else 1
            for p in d: d[p] = tuple(nw[p] * sc if j == i else d[p][j] for j in (0, 1))
def lead_value(arch, lead, ws=None):
    rows = [(ws.get(k[2], 0) if ws is not None else P[k]['share'], P[k]['pop'], P[k]['worst']) for k in P if k[0] == arch and k[1] == lead]
    W = sum(w for w, _, _ in rows)
    return None if not rows or W == 0 else (sum(w * a for w, a, _ in rows) / W, sum(w * b for w, _, b in rows) / W, len(rows))
out = {'leads': {}, 'plans': {}}
for arch in sorted({k[0] for k in P}):
    conds = [('all', None)] + [(f"{ck.split(' | ')[1]} {'yes' if i == 0 else 'no'}", {p: x[i] for p, x in cond[ck].items()}) for ck in cond if ck.split(' | ')[0] == arch for i in (0, 1)]
    out['leads'][arch] = {}
    for tag, ws in conds:
        vals = {l: lead_value(arch, l, ws) for l in sorted({k[1] for k in P if k[0] == arch})}; vals = {l: v for l, v in vals.items() if v}
        out['leads'][arch][tag] = {'weights': ws, 'vals': sorted([[l, v[0], v[1], BL(v[0], v[1]), v[2]] for l, v in vals.items()], key=lambda x: -x[3])}
for k, v in P.items(): out['plans']['||'.join(k)] = v
json.dump(out, open(sys.argv[2] if len(sys.argv) > 2 else 'tr_final.json', 'w'), indent=1)
for arch, tags in out['leads'].items():
    for tag, d in tags.items():
        print(f"{arch[:26]:26s} {tag:16s} " + ' | '.join(f"{x[0]} {x[3]:.3f} [{x[1]:.2f}/{x[2]:.2f}] n{x[4]}" for x in d['vals'][:4]))
