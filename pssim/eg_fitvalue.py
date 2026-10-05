"""Fit the 2v2 position score to game outcomes: logistic regression of "I win this game" on the position features at the start
of each turn (endgame2.js feats: HP share, Pokemon alive, stat stages, Trick Room turns x speed edge, Choice-locked status / attack).
usage: python3 eg_fitvalue.py <resultsDir with EG_FEATS output> <out.json>"""
import json, glob, sys, numpy as np
from scipy.optimize import minimize
names = ['HP share (Pokemon)', 'Pokemon alive', 'attack stages', 'TR turns x speed edge', 'locked into status', 'locked into attack', 'grid coverage', 'grid exposure', 'must recharge', 'Protected last turn', 'type edge', 'asleep/frozen', 'paralysed', 'burned/poisoned', 'Tailwind turns (no TR)', 'screen turns', 'Encored', 'holding a Tricked Choice item']
NF = len(names)
USE = [int(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 else list(range(NF))
X, y = [], []
for f in glob.glob(sys.argv[1] + '/*.json'):
    r = json.load(open(f))
    for g in r.get('feats', []):
        if g['v'] not in (0, 1): continue                     # unfinished games carry no outcome
        for k, fx in enumerate(g['F']):
            X.append(fx); y.append(g['v'])
X = np.array(X, float)[:, USE]; y = np.array(y, float); n, d = X.shape; names = [names[k] for k in USE]
def nll(p):
    z = p[0] + X @ p[1:]; return np.sum(np.logaddexp(0, z) - y * z) + 0.5 * 1e-3 * np.sum(p[1:] ** 2)
p = minimize(nll, np.zeros(d + 1), method='BFGS').x
H = np.linalg.inv(minimize(nll, p, method='BFGS').hess_inv) if False else None
pred = 1 / (1 + np.exp(-(p[0] + X @ p[1:])))
print(f'{n} positions from {len(set(map(tuple, X)))} distinct; win rate {y.mean():.3f}; log loss {-np.mean(y*np.log(pred+1e-9)+(1-y)*np.log(1-pred+1e-9)):.3f} (constant {-(y.mean()*np.log(y.mean())+(1-y.mean())*np.log(1-y.mean())):.3f})')
for nm, w in zip(['intercept'] + names, p): print(f'  {nm:24s} {w:+.3f}')
for lab, f in (('even, fresh', [0]*NF), ('one Pokemon up (2v1, full HP)', [1, 1]+[0]*(NF-2)), ('2v1, TR 3 turns for me', [1, 1, 0, 3]+[0]*(NF-4)),
               ('even, TR 3 turns for me', [0, 0, 0, 3]+[0]*(NF-4)), ('even, +2 attack', [0, 0, 2]+[0]*(NF-3)), ('even, my answers cover theirs', [0]*6+[0.4, 0.2]+[0]*(NF-8))):
    f = [f[k] for k in USE]; print(f'  {lab:32s} -> {100 / (1 + np.exp(-(p[0] + np.dot(p[1:], f)))):.0f}%')
json.dump({'b0': float(p[0]), 'w': [float(dict(zip(USE, p[1:])).get(k, 0.0)) for k in range(NF)], 'names': names, 'n': int(n)}, open(sys.argv[2], 'w'), indent=1)
