"""P(Trick Room is up after turn one), whoever set it, for every solved lead plan: my plan mix against their reader mix and against
the ladder click rates (each click type's targets spread evenly), blended like the lead scores (READER_W). From the raw cells, where
feature 8 is nonzero exactly when one side set Trick Room (two in one turn cancel).
usage: READER_W=0.75 python3 tr_up.py <tr_final.json> <resultsDir> <out.json>"""
import json, glob, sys, os, collections
LAM = float(os.environ.get('READER_W', '0.5'))
D = json.load(open(sys.argv[1])); res = {}
for f in glob.glob(sys.argv[2] + '/*.json'):
    r = json.load(open(f)); res[f"{r['arch']}||{'+'.join(r['myLead'])}||{r['pair']}"] = r
out = {}
for key, p in D['plans'].items():
    r = res.get(key)
    if r is None: continue
    rows = {a: i for i, a in enumerate(r['myActs'])}; cols = {t['label']: j for j, t in enumerate(r['thActs'])}
    up = lambda i, j: sum(fx[8] != 0 for fx in r['F'][i][j]) / max(1, len(r['F'][i][j]))
    x = [(pc / 100, rows[a]) for pc, a in p['mix'] if a in rows]
    yr = [(q, cols[lab]) for q, lab in (p.get('reader') or []) if lab in cols]
    g = collections.defaultdict(list)
    for j, t in enumerate(r['thActs']): g[t['group']].append((t['p'], j))
    yl = [(L[0][0] / len(L), j) for L in g.values() for _, j in L]
    pr = sum(a * b * up(i, j) for a, i in x for b, j in yr) / max(1e-9, sum(b for b, _ in yr)) if yr else None
    pl = sum(a * b * up(i, j) for a, i in x for b, j in yl) / max(1e-9, sum(b for b, _ in yl))
    out[key] = round(pl if pr is None else (1 - LAM) * pl + LAM * pr, 3)
json.dump(out, open(sys.argv[3], 'w'), indent=0); print(len(out), 'plans')
