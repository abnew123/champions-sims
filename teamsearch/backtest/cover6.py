"""How close generated sixes (backtest/gen6.py) come to M-C's real teams (the user, 2026-11-08: generate whole sixes, then check
coverage before any sims). Fixed and committed together with gen6.py before any number was seen.
Real teams: M-C's settled window (Oct 14 - Nov 6, compare.py's), every open sheet, one vote per player; cached in
backtest/gen6/mc_settled.json ({sorted formes: weight}; no players). For a real six, d = 6 - its largest forme overlap with any
generated six: the swaps from the nearest one. Its floor is the count of its formes outside the generator's universe.
Rows: every backtest/gen6 generator file at N = 1000 and 4000 (prefixes), v2's self-play field (every team it ever weighted) and
M-B's most common sixes. Columns: share of real teams with d <= 1 and d <= 2 and mean d, over all teams and over the teams with one
of M-C's big new formes (compare.json big_new: >= 5% real settled); d <= 2 per big new forme. Floor rows per universe.
  python3 backtest/cover6.py   -> report on stdout, backtest/gen6/coverage.json
"""
import json, os, sys, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); GEN = os.path.join(HERE, 'gen6')
sys.path.insert(0, HERE)
import compare as CP
NS = (1000, 4000)

def real():
    path = os.path.join(GEN, 'mc_settled.json')
    if os.path.exists(path): return json.load(open(path))
    from opp_pool import parse
    RP = os.path.join(CP.ROOT, 'pssim', 'replays_protect'); idx = json.load(open(os.path.join(RP, 'index.json'))); a, b = CP.WIN['M-C settled']
    per, players = {}, {}
    for f in glob.glob(os.path.join(RP, '*bo3-*.log')):
        gid = os.path.basename(f)[:-4]; t = (idx.get(gid) or {}).get('time')
        if not t or not a <= CP.day(t) <= b: continue
        log = open(f, encoding='utf-8', errors='replace').read(); sd, _, _ = parse(log)
        who = {p[2]: p[3].strip().lower() for p in (l.split('|') for l in log.split('\n') if l.startswith('|player|')) if len(p) > 3 and p[3]}
        for s in ('p1', 'p2'):
            six = sd[s]['six']
            if six and len(six) == 6:
                per.setdefault(players.setdefault(who.get(s, gid + s), len(players)), []).append('|'.join(sorted(CP.forme(CP.L.normalize(x)) for x in six)))
    players.clear(); out = {}
    for sheets in per.values():
        for k in sheets: out[k] = out.get(k, 0) + 1 / len(sheets) / len(per)
    os.makedirs(GEN, exist_ok=True); json.dump(out, open(path, 'w'))
    return out

def dist(R, gens, idx):
    """d per real six against a list of generated sixes"""
    G = np.zeros((len(gens), len(idx)), np.float32)
    for i, six in enumerate(gens):
        for f in six:
            if f in idx: G[i, idx[f]] = 1
    best = np.zeros(len(R), np.float32)
    for c in range(0, len(R), 2000): best[c:c + 2000] = (R[c:c + 2000] @ G.T).max(axis=1)
    return 6 - best

def main():
    T = real(); keys = list(T); w = np.array([T[k] for k in keys]); w /= w.sum(); sixes = [k.split('|') for k in keys]
    big = json.load(open(os.path.join(HERE, 'compare.json')))['big_new']
    files = {os.path.basename(f)[:-5]: json.load(open(f)) for f in sorted(glob.glob(os.path.join(GEN, '*.json'))) if os.path.basename(f) not in ('mc_settled.json', 'coverage.json')}
    rows = {}
    v2 = {tuple(sorted(t['species'])) for f in glob.glob(os.path.join(HERE, 'v2', 'sp_pred_*.json')) for t in json.load(open(f))['field'].values()}
    rows[f'v2 self-play field ({len(v2)})'] = [list(x) for x in v2]
    for name, d in files.items():
        for n in NS: rows[f'{name} {n}'] = [x['formes'] for x in d['sixes'][:n]]
    allf = sorted({f for s in sixes for f in s} | {f for r in rows.values() for s in r for f in s}); idx = {f: i for i, f in enumerate(allf)}
    R = np.zeros((len(sixes), len(idx)), np.float32)
    for i, s in enumerate(sixes):
        for f in s: R[i, idx[f]] = 1
    has = np.array([any(f in big for f in s) for s in sixes]); per = {f: np.array([f in s for s in sixes]) for f in big}
    def stats(d):
        st = lambda m: dict(le1=float(w[m] @ (d[m] <= 1) / w[m].sum()), le2=float(w[m] @ (d[m] <= 2) / w[m].sum()), mean=float(w[m] @ d[m] / w[m].sum()))
        return dict(all=st(np.ones(len(d), bool)), new=st(has), **{f: float(w[per[f]] @ (d[per[f]] <= 2) / w[per[f]].sum()) for f in big})
    out = dict(real_sixes=len(sixes), big_new=big, new_share=float(w @ has), rows={})
    for name, gens in rows.items(): out['rows'][name] = stats(dist(R, gens, idx))
    for uni in sorted({d['universe'] for d in files.values() if d.get('universe')}):
        U = set(next(d['U'] for d in files.values() if d.get('universe') == uni)); fl = np.array([sum(f not in U for f in s) for s in sixes], np.float32)
        out['rows'][f'floor, universe {uni}'] = stats(fl)
    print(f"{len(sixes)} distinct real sixes (M-C settled, one vote per player); {100 * out['new_share']:.0f}% carry a big new forme ({', '.join(big)})")
    print(f"  {'generator':28s} {'all: d<=1':>9s} {'d<=2':>6s} {'mean d':>7s}   {'new: d<=1':>9s} {'d<=2':>6s} {'mean d':>7s}   " + ''.join(f"{f[:12]:>13s}" for f in big))
    for name, s in out['rows'].items():
        print(f"  {name:28s} {100 * s['all']['le1']:8.0f}% {100 * s['all']['le2']:5.0f}% {s['all']['mean']:7.2f}   {100 * s['new']['le1']:8.0f}% {100 * s['new']['le2']:5.0f}% {s['new']['mean']:7.2f}   "
              + ''.join(f"{100 * s[f]:12.0f}%" for f in big))
    json.dump(out, open(os.path.join(GEN, 'coverage.json'), 'w'), indent=1)

if __name__ == '__main__': main()
