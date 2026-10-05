# Merge every refined matchup (old top leads + Salamence leads), fold in Indeedee-F items, solve without turn-1 Make It Rain,
# then apply the display rule: show Salamence + Kingambit / + Rillaboom (or another Salamence lead) when within 5 points of the top lead.
import json, glob, os, copy, re, collections, numpy as np
os.environ['EXCLUDE_MOVES'] = 'Make It Rain'
from analyze import solve, lp_blend
ITEMW = {'rockyhelmet': 0.47, 'colburberry': 0.31, 'psychicseed': 0.20}
KEYS = ['A', 'N', 'F', 'koMine', 'koTheirs', 'tw', 'tr']
def key(r): return (r['arch'], '+'.join(r['myLead']), r['pair'])
def load_dir(d):
    out = {}
    for fn in glob.glob(d + '/*.json'): r = json.load(open(fn)); out[key(r)] = r
    return out
refined = [load_dir(d) for d in ('results/s2', 'results/p2', 'results/s3', 'results/sal2')]
items = {it: {**load_dir('results/s3_' + it), **load_dir('results/sal2_' + it)} for it in ('colburberry', 'psychicseed')}
sel = json.load(open('sel_s3.json')) + json.load(open('sel_sal.json'))
seen = set(); SEL = []
for j in sel:
    k = (j['arch'], '+'.join(j['lead']), j['pair'])
    if k in seen: continue
    seen.add(k); SEL.append(j)
def merge(j):
    k = (j['arch'], '+'.join(j['lead']), j['pair']); parts = [d[k] for d in refined if k in d]
    base = copy.deepcopy(parts[0]); th = [t['label'] for t in base['thActs']]
    for p in parts: assert [t['label'] for t in p['thActs']] == th, k
    rows = {}
    for p in parts:
        for i, a in enumerate(p['myActs']):
            if a in j['rows'] and a not in rows: rows[a] = {kk: p[kk][i] for kk in KEYS}
    missing = [a for a in j['rows'] if a not in rows]; assert not missing, (k, missing[:3])
    base['myActs'] = list(j['rows'])
    for kk in KEYS: base[kk] = [rows[a][kk] for a in j['rows']]
    base['wp0'] = next((p['wp0'] for p in parts if p.get('wp0') is not None), None)
    return base
def mix_items(r, j):
    k = (j['arch'], '+'.join(j['lead']), j['pair'])
    if 'Indeedee-F' not in j['pair'].split(' + '): return r, False
    if not all(k in items[it] for it in items): return r, 'MISSING'
    out = copy.deepcopy(r); tot = sum(ITEMW.values()); variants = {'rockyhelmet': r, **{it: items[it][k] for it in items}}
    idx = {it: {a: i for i, a in enumerate(v['myActs'])} for it, v in variants.items()}
    for kk in ('A', 'N', 'koMine', 'koTheirs', 'tw', 'tr'):
        M = np.zeros((len(r['myActs']), len(r['thActs'])))
        for it, v in variants.items():
            M += ITEMW[it] / tot * np.array([[np.nan if x is None else x for x in v[kk][idx[it][a]]] for a in r['myActs']], float)
        out[kk] = M.tolist()
    return out, True
res = {}
for j in SEL:
    r = merge(j); r, mixed = mix_items(r, j); r['itemMix'] = mixed
    res[(j['arch'], '+'.join(j['lead']), j['pair'])] = (r, solve(r))
def simple(k):
    r, s = res[k]; Ab, Ac, groups, keepc, acts = s['Ab'], s['Ac'], s['groups'], s['keepc'], s['acts']
    full = (s['pop_m'] + s['worst_m']) / 2; order = list(np.argsort(-s['xm'])); best = None; singles = []
    for i in range(len(acts)):
        x = np.zeros(len(acts)); x[i] = 1
        pop = float(sum(g['p'] * (x @ Ab)[g['cols']].min() for g in groups.values())); worst = float((x @ Ac)[keepc].min()); singles.append(((pop + worst) / 2, pop, worst, i))
    singles.sort(reverse=True)
    for idx in [[singles[0][3]]] + [order[:m] for m in (2, 3)] + [[singles[0][3], jj] for jj in order[:3] if jj != singles[0][3]]:
        idx = list(dict.fromkeys(idx))
        if len(idx) == 1: xs = np.zeros(len(acts)); xs[idx[0]] = 1; pop, worst = singles[0][1], singles[0][2]
        else: xr, pop, worst = lp_blend(Ab[idx], Ac[idx], groups, keepc); xs = np.zeros(len(acts)); xs[idx] = xr
        if (pop + worst) / 2 >= full - 0.005 and (best is None or (xs > 0.03).sum() < (best[0] > 0.03).sum()): best = (xs, pop, worst)
    if best is None: xr, pop, worst = lp_blend(Ab[order[:3]], Ac[order[:3]], groups, keepc); xs = np.zeros(len(acts)); xs[order[:3]] = xr; best = (xs, pop, worst)
    xs, pop, worst = best
    return {'lines': sorted([(float(xs[i]), acts[i]) for i in range(len(acts)) if xs[i] > 0.03], reverse=True), 'pop': pop, 'worst': worst,
            'reader': [(float(s['yc'][i]), r['thActs'][i]['label']) for i in np.argsort(-s['yc']) if s['yc'][i] > 0.1][:3], 'share': r['share'], 'back': r['myBack'], 'itemMix': r['itemMix']}
cond = {}
for line in open('cond_shares.txt').read().strip().split('\n'):
    kk, v = line.split('": "'); kk = kk.strip().strip('"'); v = v.rstrip('",')
    cond[kk] = {m.group(1).strip(): (float(m.group(2)), float(m.group(3))) for m in re.finditer(r'([^;:]+?): yes ([\d.]+) / no ([\d.]+)', v)}
SIMPLE = {}
def value(arch, lead, weights=None):
    rows = []
    for k in res:
        if k[0] != arch or k[1] != lead: continue
        if k not in SIMPLE: SIMPLE[k] = simple(k)
        w = (weights.get(k[2], 0) if weights is not None else res[k][0]['share'])
        rows.append((w, SIMPLE[k]['pop'], SIMPLE[k]['worst']))
    W = sum(r[0] for r in rows)
    if not rows or W == 0: return None
    return (sum(w * p for w, p, _ in rows) / W, sum(w * q for w, _, q in rows) / W)
def is_sal(l): return 'Salamence' in l.split('+')
def default(l): return is_sal(l) and ('Kingambit' in l or 'Rillaboom' in l)
out = {}
for arch in sorted({k[0] for k in res}):
    conds = [(None, None)] + [(ck.split(' | ')[1], i) for ck in cond if ck.split(' | ')[0] == arch for i in (0, 1)]
    out[arch] = {}
    for tell, idx in conds:
        ws = None if tell is None else {p: x[idx] for p, x in cond[f'{arch} | {tell}'].items()}
        leads = sorted({k[1] for k in res if k[0] == arch})
        vals = {l: value(arch, l, ws) for l in leads}; vals = {l: v for l, v in vals.items() if v}
        blend = {l: (v[0] + v[1]) / 2 for l, v in vals.items()}
        top = max(blend, key=blend.get); T = blend[top]
        show = [l for l in leads if default(l) and l in blend and blend[l] >= T - 0.05]
        if not show:
            sal = sorted([l for l in blend if is_sal(l) and blend[l] >= T - 0.05], key=lambda l: -blend[l])
            show = sal[:1]
        if not show: show = [top]
        bestsal = max([l for l in blend if is_sal(l)], key=lambda l: blend[l], default=None)
        tag = 'all' if tell is None else f"{tell} {'yes' if idx == 0 else 'no'}"
        out[arch][tag] = {'top': [top, vals[top]], 'show': [[l, vals[l]] for l in show], 'bestSal': [bestsal, vals.get(bestsal)] if bestsal else None,
                          'all': sorted([[l, vals[l][0], vals[l][1], blend[l]] for l in vals], key=lambda x: -x[3])}
        print(f"{arch[:28]:28s} {tag:16s} top {top} {T:.3f} | show " + ', '.join(f"{l} {blend[l]:.3f}" for l in show) + (f" | best Sal {bestsal} {blend[bestsal]:.3f}" if bestsal else ''))
json.dump({'display': out, 'plans': {'||'.join(k): v for k, v in SIMPLE.items()}}, open('final4.json', 'w'), indent=1)
