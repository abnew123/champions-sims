# Solve every lead-vs-lead turn-1 matrix and rank leads per archetype.
# (b) exploit: their per-Pokemon move frequencies fixed at replay rates, targets chosen adversarially vs my mix.
# (c) Nash: they pick any observed action freely.  Turns where nothing changes get the game's own value (fixed point).
import json, glob, os, sys, numpy as np
from scipy.optimize import linprog

W2 = np.array([0.815, 0.235, 0.326, 0.222, 0.016, -0.010, 0.036, 0.465, 0.638, 0.566, 0.444, 0.723])

def matrices(r, W=None):
    if W is None:
        A = np.array([[np.nan if v is None else v for v in row] for row in r['A']], float)
        N = np.array([[0 if v is None else v for v in row] for row in r['N']], float)
        return A, N, r.get('wp0')
    m, n = len(r['F']), len(r['F'][0]); A = np.zeros((m, n)); N = np.zeros((m, n)); wp0 = None
    for i in range(m):
        for j in range(n):
            fx = np.array(r['F'][i][j]); k = fx.shape[1] - 1; z = fx[:, :k] @ W[:k]; wp = 1 / (1 + np.exp(-z)); A[i, j] = wp.mean(); N[i, j] = fx[:, k].mean()
            if wp0 is None and fx[:, k].any(): wp0 = float(wp[fx[:, k] > 0][0])
    return A, N, wp0

def groups_of(r):
    g = {}
    for j, t in enumerate(r['thActs']): g.setdefault(t['group'], {'p': t['p'], 'cols': []})['cols'].append(j)
    tot = sum(v['p'] for v in g.values())
    for v in g.values(): v['p'] /= tot
    return g

def lp_b(A, groups):
    G = list(groups); m = A.shape[0]; ng = len(G)
    c = np.concatenate([np.zeros(m), -np.array([groups[g]['p'] for g in G])])
    rows = []
    for gi, g in enumerate(G):
        for j in groups[g]['cols']:
            row = np.zeros(m + ng); row[:m] = -A[:, j]; row[m + gi] = 1; rows.append(row)
    res = linprog(c, A_ub=np.array(rows), b_ub=np.zeros(len(rows)), A_eq=np.concatenate([np.ones(m), np.zeros(ng)])[None], b_eq=[1],
                  bounds=[(0, None)] * m + [(None, None)] * ng, method='highs')
    return -res.fun, res.x[:m]

def lp_c(A):
    m, n = A.shape
    res = linprog(np.concatenate([np.zeros(m), [-1]]), A_ub=np.hstack([-A.T, np.ones((n, 1))]), b_ub=np.zeros(n),
                  A_eq=np.concatenate([np.ones(m), [0]])[None], b_eq=[1], bounds=[(0, None)] * m + [(None, None)], method='highs')
    res2 = linprog(np.concatenate([np.zeros(n), [1]]), A_ub=np.hstack([A, -np.ones((m, 1))]), b_ub=np.zeros(m),
                   A_eq=np.concatenate([np.ones(n), [0]])[None], b_eq=[1], bounds=[(0, None)] * n + [(None, None)], method='highs')
    return -res.fun, res.x[:m], res2.x[:n]

def fixed_point(solver, A, N, wp0, v0):
    if wp0 is None or not N.any(): return solver(A) + (0,)
    v = v0
    for it in range(60):
        out = solver(A + N * (v - wp0))
        if abs(out[0] - v) < 1e-6: break
        v = out[0]
    return out + (it,)

def lp_blend(Ab, Ac, groups, keepc, lam=0.5):
    """max_x (1-lam)*[value vs ladder frequencies, worst-case targets] + lam*[value vs an opponent who knows x]"""
    G = list(groups); m = Ab.shape[0]; ng = len(G); cols = np.where(keepc)[0]
    c = np.concatenate([np.zeros(m), -(1 - lam) * np.array([groups[g]['p'] for g in G]), [-lam]])
    rows = []
    for gi, g in enumerate(G):
        for j in groups[g]['cols']:
            row = np.zeros(m + ng + 1); row[:m] = -Ab[:, j]; row[m + gi] = 1; rows.append(row)
    for j in cols:
        row = np.zeros(m + ng + 1); row[:m] = -Ac[:, j]; row[-1] = 1; rows.append(row)
    res = linprog(c, A_ub=np.array(rows), b_ub=np.zeros(len(rows)), A_eq=np.concatenate([np.ones(m), np.zeros(ng + 1)])[None], b_eq=[1],
                  bounds=[(0, None)] * m + [(None, None)] * (ng + 1), method='highs')
    x = res.x[:m]
    pop = float(sum(groups[g]['p'] * (x @ Ab)[groups[g]['cols']].min() for g in G)); worst = float((x @ Ac)[cols].min())
    return x, pop, worst

def pure_b(A, groups):
    return np.array([sum(g['p'] * A[i, g['cols']].min() for g in groups.values()) for i in range(A.shape[0])])

def solve(r, W=None):
    A, N, wp0 = matrices(r, W); groups = groups_of(r)
    PROT_ = ('Protect', 'Detect')
    dbl = np.array([all(part.split(': ', 1)[1].split(' -> ')[0] in PROT_ for part in a.split(' | ')) for a in r['myActs']])
    import os
    EXC = [x for x in os.environ.get('EXCLUDE_MOVES', '').split(',') if x]   # e.g. 'Make It Rain' (turn-1 self-drop the player won't click)
    exc = np.array([any(f': {m}' in a for m in EXC) for a in r['myActs']]) if EXC else np.zeros(len(r['myActs']), bool)
    ok = ~np.isnan(A).any(axis=1) & ~dbl & ~exc   # my double Protect is a stall I cannot repeat either; excluded like theirs
    A = A[ok]; N = N[ok]; acts = [a for a, k in zip(r['myActs'], ok) if k]
    vb, xb, _ = fixed_point(lambda M: lp_b(M, groups), A, N, wp0, 0.5)
    # Nash: drop their double-Protect columns (a stall they cannot repeat; its value is not the null 0.5)
    PROT = ('Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Baneful Bunker', 'Silk Trap', 'Burning Bulwark', 'Obstruct')
    keepc = np.array([not all(part.split(':', 1)[1] in PROT for part in t['group'].split(' | ')) for t in r['thActs']])
    vc, xc, yc0, _ = fixed_point(lp_c, A[:, keepc], N[:, keepc], wp0, 0.5)
    yc = np.zeros(A.shape[1]); yc[keepc] = yc0
    Ab = A + N * (vb - wp0) if wp0 is not None else A; Ac = A + N * (vc - wp0) if wp0 is not None else A
    pb = pure_b(Ab, groups)
    exploit_b = float((xb @ Ac)[keepc].min())     # what my exploit mix guarantees if they adapt fully
    nash_vs_pop = float(sum(g['p'] * (xc @ Ab)[g['cols']].min() for g in groups.values()))  # Nash mix vs the population
    xm, pop_m, worst_m = lp_blend(Ab, Ac, groups, keepc, float(os.environ.get('READER_W', '0.5')))
    return dict(vb=vb, xb=xb, vc=vc, xc=xc, yc=yc, pb=pb, acts=acts, groups=groups, exploit_b=exploit_b, nash_vs_pop=nash_vs_pop, Ab=Ab, Ac=Ac,
                xm=xm, pop_m=pop_m, worst_m=worst_m, keepc=keepc)

if __name__ == '__main__':
    d = sys.argv[1] if len(sys.argv) > 1 else 'results/s1'
    jobs = json.load(open('jobs_s1.json'))
    rows = []
    for fn in glob.glob(d + '/*.json'):
        r = json.load(open(fn)); s = solve(r)
        rows.append(dict(arch=r['arch'], pair=r['pair'], share=r['share'], lead='+'.join(r['myLead']), vb=s['vb'], vc=s['vc'], best_pure=float(s['pb'].max()),
                         exploit_b=s['exploit_b'], nash_vs_pop=s['nash_vs_pop'], job=r.get('job')))
    json.dump(rows, open(d + '_summary.json', 'w'))
    import collections
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for x in rows: by[x['arch']][x['lead']].append(x)
    for arch, leads in by.items():
        print('\n==', arch)
        pairs = sorted({x['pair'] for L in leads.values() for x in L}, key=lambda p: -[x['share'] for L in leads.values() for x in L if x['pair'] == p][0])
        out = []
        for lead, L in leads.items():
            w = np.array([x['share'] for x in L]); vb = np.array([x['vb'] for x in L]); vc = np.array([x['vc'] for x in L])
            out.append((float((w * vb).sum() / w.sum()), float((w * vc).sum() / w.sum()), lead, len(L), {x['pair']: (round(x['vb'], 3), round(x['vc'], 3)) for x in L}))
        for vb, vc, lead, n, per in sorted(out, reverse=True):
            print(f'{vb:.3f} {vc:.3f} {lead:24s} n={n} ' + '  '.join(f"{p.split(' + ')[0][:5]}+{p.split(' + ')[1][:5]}:{per[p][0]:.2f}/{per[p][1]:.2f}" for p in pairs if p in per))
