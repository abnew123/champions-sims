# Solve one turn-1 matrix: (b) their move frequencies fixed from replays, targets adversarial; (c) full Nash.
import json, sys, numpy as np
from scipy.optimize import linprog

def load(fn):
    r = json.load(open(fn)); A = np.array([[np.nan if v is None else v for v in row] for row in r['A']], float)
    return r, A

def solve_b(r, A):
    """max_x sum_g q_g z_g  s.t. z_g <= (x^T A)[:,j] for every target variant j of group g."""
    groups = {}; 
    for j, t in enumerate(r['thActs']): groups.setdefault(t['group'], {'p': t['p'], 'cols': []})['cols'].append(j)
    G = list(groups); m, n = A.shape; ng = len(G)
    # variables: x (m), z (ng)
    c = np.concatenate([np.zeros(m), -np.array([groups[g]['p'] for g in G])])
    rows, b = [], []
    for gi, g in enumerate(G):
        for j in groups[g]['cols']:
            row = np.zeros(m + ng); row[:m] = -A[:, j]; row[m + gi] = 1; rows.append(row); b.append(0)
    Aeq = np.concatenate([np.ones(m), np.zeros(ng)])[None]
    res = linprog(c, A_ub=np.array(rows), b_ub=np.array(b), A_eq=Aeq, b_eq=[1], bounds=[(0, None)] * m + [(None, None)] * ng, method='highs')
    x = res.x[:m]; return -res.fun, x, groups

def pure_b(r, A):
    """value of each pure action vs fixed frequencies with worst-case targets"""
    groups = {}
    for j, t in enumerate(r['thActs']): groups.setdefault(t['group'], {'p': t['p'], 'cols': []})['cols'].append(j)
    tot = sum(g['p'] for g in groups.values())
    return np.array([sum(g['p'] * A[i, g['cols']].min() for g in groups.values()) / tot for i in range(A.shape[0])])

def pure_avg(r, A):
    """value vs fixed frequencies with targets split evenly (a less pessimistic reading)"""
    groups = {}
    for j, t in enumerate(r['thActs']): groups.setdefault(t['group'], {'p': t['p'], 'cols': []})['cols'].append(j)
    tot = sum(g['p'] for g in groups.values())
    return np.array([sum(g['p'] * A[i, g['cols']].mean() for g in groups.values()) / tot for i in range(A.shape[0])])

def solve_c(A):
    """Nash: max_x v s.t. v <= x^T A[:,j] for all j"""
    m, n = A.shape
    c = np.concatenate([np.zeros(m), [-1]])
    Aub = np.hstack([-A.T, np.ones((n, 1))]); bub = np.zeros(n)
    Aeq = np.concatenate([np.ones(m), [0]])[None]
    res = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=[1], bounds=[(0, None)] * m + [(None, None)], method='highs')
    x = res.x[:m]
    # their side
    c2 = np.concatenate([np.zeros(n), [1]])
    Aub2 = np.hstack([A, -np.ones((m, 1))]); 
    Aeq2 = np.concatenate([np.ones(n), [0]])[None]
    res2 = linprog(c2, A_ub=Aub2, b_ub=np.zeros(m), A_eq=Aeq2, b_eq=[1], bounds=[(0, None)] * n + [(None, None)], method='highs')
    return -res.fun, x, res2.x[:n]

if __name__ == '__main__':
    r, A = load(sys.argv[1])
    print(r['arch'], '|', r['pair'], 'vs', '+'.join(r['myLead']), 'back', '+'.join(r['myBack']), A.shape, 'nan', np.isnan(A).sum())
    vb, xb, groups = solve_b(r, A); pb = pure_b(r, A); pa = pure_avg(r, A)
    order = np.argsort(-pb)
    print(f'(b) fixed-frequency, worst-case targets: value {vb:.3f}')
    for i in np.where(xb > 0.01)[0]: print(f'   {xb[i]:.2f}  {r["myActs"][i]}  (pure {pb[i]:.3f})')
    print('   best pure (worst-case targets / even targets):')
    for i in order[:8]: print(f'   {pb[i]:.3f} / {pa[i]:.3f}  {r["myActs"][i]}')
    vc, xc, yc = solve_c(A)
    print(f'(c) Nash value {vc:.3f}')
    for i in np.where(xc > 0.01)[0]: print(f'   me {xc[i]:.2f}  {r["myActs"][i]}')
    for j in np.where(yc > 0.01)[0]: print(f'   them {yc[j]:.2f}  {r["thActs"][j]["label"]}')
