# Merge refined cells (old refined rows + new rows), fold in Indeedee-F's item mix, solve with turn-1 Make It Rain excluded.
import json, glob, os, copy, collections, re, numpy as np
os.environ['EXCLUDE_MOVES'] = 'Make It Rain'
from analyze import solve
ITEMW = {'rockyhelmet': 0.47, 'colburberry': 0.31, 'psychicseed': 0.20}   # replay shares of Indeedee-F items (Sitrus folded into Rocky: both die the same way)
KEYS = ['A', 'N', 'F', 'koMine', 'koTheirs', 'tw', 'tr']
def key(r): return (r['arch'], '+'.join(r['myLead']), r['pair'])
def load_dir(d):
    out = {}
    for fn in glob.glob(d + '/*.json'): r = json.load(open(fn)); out[key(r)] = r
    return out
s2 = {**load_dir('results/s2'), **load_dir('results/p2')}
s3 = load_dir('results/s3'); items = {it: load_dir('results/s3_' + it) for it in ('colburberry', 'psychicseed')}
sel = json.load(open('sel_s3.json'))
def merge(j):
    k = (j['arch'], '+'.join(j['lead']), j['pair']); parts = [x for x in (s2.get(k), s3.get(k)) if x]
    base = copy.deepcopy(parts[0]); th = [t['label'] for t in base['thActs']]
    for p in parts: assert [t['label'] for t in p['thActs']] == th, k
    rows = {}
    for p in parts:
        for i, a in enumerate(p['myActs']):
            if a in j['rows'] and a not in rows: rows[a] = {kk: p[kk][i] for kk in KEYS}
    missing = [a for a in j['rows'] if a not in rows]
    assert not missing, (k, missing[:3])
    base['myActs'] = list(j['rows']); base['seeds'] = 12
    for kk in KEYS: base[kk] = [rows[a][kk] for a in j['rows']]
    base['wp0'] = next((p['wp0'] for p in parts if p.get('wp0') is not None), None)
    return base
def mix_items(r, j):
    k = (j['arch'], '+'.join(j['lead']), j['pair'])
    if 'Indeedee-F' not in j['pair'].split(' + ') or not all(k in items[it] for it in items): return r, False
    out = copy.deepcopy(r); tot = sum(ITEMW.values())
    variants = {'rockyhelmet': r, **{it: items[it][k] for it in items}}
    idx = {it: {a: i for i, a in enumerate(v['myActs'])} for it, v in variants.items()}
    for kk in ('A', 'N', 'koMine', 'koTheirs', 'tw', 'tr'):
        M = np.zeros((len(r['myActs']), len(r['thActs'])))
        for it, v in variants.items():
            X = np.array([[np.nan if x is None else x for x in v[kk][idx[it][a]]] for a in r['myActs']], float)
            M += ITEMW[it] / tot * X
        out[kk] = M.tolist()
    return out, True
res = {}
for j in sel:
    r = merge(j); r, mixed = mix_items(r, j); r['itemMix'] = mixed
    s = solve(r); res[(j['arch'], '+'.join(j['lead']), j['pair'])] = (r, s)
# lead values
cond = {}
for line in open('cond_shares.txt').read().strip().split('\n'):
    kk, v = line.split('": "'); kk = kk.strip().strip('"'); v = v.rstrip('",')
    cond[kk] = {m.group(1).strip(): (float(m.group(2)), float(m.group(3))) for m in re.finditer(r'([^;:]+?): yes ([\d.]+) / no ([\d.]+)', v)}
def lead_val(arch, lead, weights=None):
    L = [(k, v) for k, v in res.items() if k[0] == arch and k[1] == lead]
    w = np.array([(weights.get(k[2], 0) if weights is not None else v[0]['share']) for k, v in L]); 
    if w.sum() == 0: return None
    pm = np.array([v[1]['pop_m'] for k, v in L]); wm = np.array([v[1]['worst_m'] for k, v in L])
    return float((w * pm).sum() / w.sum()), float((w * wm).sum() / w.sum()), float(w.sum())
out = {}
for arch in sorted({k[0] for k in res}):
    leads = sorted({k[1] for k in res if k[0] == arch})
    vals = sorted([(sum(lead_val(arch, l)[:2]) / 2, l, lead_val(arch, l)) for l in leads], reverse=True)
    print(f'\n===== {arch}')
    for b, l, (p, w, _) in vals: print(f'   {l:24s} ladder {p:.3f} reader {w:.3f} blend {b:.3f}')
    for ck, cv in cond.items():
        if ck.split(' | ')[0] != arch: continue
        for idx, lab in ((0, 'yes'), (1, 'no')):
            ws = {p: x[idx] for p, x in cv.items()}
            cv_vals = sorted([(sum(lead_val(arch, l, ws)[:2]) / 2, l, lead_val(arch, l, ws)) for l in leads if lead_val(arch, l, ws)], reverse=True)
            print(f'   [{ck.split(" | ")[1]} {lab}] ' + ' | '.join(f'{l} {p:.3f}/{w:.3f}' for b, l, (p, w, c) in cv_vals[:3]) + f'  (covers {cv_vals[0][2][2]:.0f}%)')
    out[arch] = {'leads': [(l, p, w) for b, l, (p, w, _) in vals]}
json.dump({f'{k[0]}||{k[1]}||{k[2]}': {'share': v[0]['share'], 'n': v[0]['n'], 'back': v[0]['myBack'], 'itemMix': v[0]['itemMix'], 'pop': v[1]['pop_m'], 'worst': v[1]['worst_m'], 'vb': v[1]['vb'], 'vc': v[1]['vc'],
           'blend': [(float(v[1]['xm'][i]), v[1]['acts'][i]) for i in np.argsort(-v[1]['xm']) if v[1]['xm'][i] > 0.03],
           'exploit': v[1]['acts'][int(np.argmax(v[1]['xb']))], 'adapt': v[1]['exploit_b'],
           'reader': [(float(v[1]['yc'][i]), v[0]['thActs'][i]['label']) for i in np.argsort(-v[1]['yc']) if v[1]['yc'][i] > 0.08]} for k, v in res.items()},
          open('final3.json', 'w'), indent=1)

# ---- simplified plans: the fewest lines (<=3) that keep the blend objective within 0.005 of the full mix
import pickle
from analyze import lp_blend
simp = {}
for k, (r, s) in res.items():
    Ab, Ac, groups, keepc, acts = s['Ab'], s['Ac'], s['groups'], s['keepc'], s['acts']
    full = (s['pop_m'] + s['worst_m']) / 2; order = list(np.argsort(-s['xm']))
    best = None
    # single best action by the blend objective
    singles = []
    for i in range(len(acts)):
        x = np.zeros(len(acts)); x[i] = 1
        pop = float(sum(g['p'] * (x @ Ab)[g['cols']].min() for g in groups.values())); worst = float((x @ Ac)[keepc].min())
        singles.append(((pop + worst) / 2, pop, worst, i))
    singles.sort(reverse=True)
    cands = [[singles[0][3]]] + [order[:m] for m in (2, 3)] + [[singles[0][3], j] for j in order[:3] if j != singles[0][3]]
    for idx in cands:
        idx = list(dict.fromkeys(idx))
        if len(idx) == 1: x = np.zeros(len(acts)); x[idx[0]] = 1; xs = x; pop, worst = singles[0][1], singles[0][2]
        else:
            xr, pop, worst = lp_blend(Ab[idx], Ac[idx], groups, keepc); xs = np.zeros(len(acts)); xs[idx] = xr
        obj = (pop + worst) / 2
        if obj >= full - 0.005 and (best is None or len([v for v in xs if v > 0.03]) < len([v for v in best[0] if v > 0.03])): best = (xs, pop, worst)
    if best is None:
        xr, pop, worst = lp_blend(Ab[order[:3]], Ac[order[:3]], groups, keepc); xs = np.zeros(len(acts)); xs[order[:3]] = xr; best = (xs, pop, worst)
    xs, pop, worst = best
    lines = sorted([(float(xs[i]), acts[i]) for i in range(len(acts)) if xs[i] > 0.03], reverse=True)
    simp['||'.join(k)] = {'lines': lines, 'pop': pop, 'worst': worst, 'full_pop': s['pop_m'], 'full_worst': s['worst_m'], 'share': r['share'], 'back': r['myBack'], 'itemMix': r['itemMix'],
                          'reader': [(float(s['yc'][i]), r['thActs'][i]['label']) for i in np.argsort(-s['yc']) if s['yc'][i] > 0.1][:3]}
json.dump(simp, open('simple3.json', 'w'), indent=1)
