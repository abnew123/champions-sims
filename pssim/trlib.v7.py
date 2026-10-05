# Shared helpers for the Trick Room team sheet: load results, credit a turn-one Trick Room to the slower team, solve.
import json, glob, math, os, numpy as np
os.environ.setdefault('EXCLUDE_MOVES', '')
from analyze import solve, W2
SPD = json.load(open(os.path.join(os.path.dirname(__file__) or '.', 'tr_speeds.json')))
def key(r): return (r['arch'], '+'.join(r['myLead']), r['pair'])
def tr_credit(r):
    v = SPD[f"{r['arch']}|{'+'.join(r['myLead'])}|{r['pair']}"]
    return math.tanh((v['t'] - v['m']) / 15.0)          # +1: Trick Room up helps me (my four are much slower)
def adjust(r):
    """Trick Room up after turn one (feature 8 nonzero: exactly one side set it) scores for the slower team, whoever set it."""
    s = tr_credit(r)
    for row in r['F']:
        for cell in row:
            for fx in cell:
                if fx[8] != 0: fx[8] = s
    r['trCredit'] = s
    return r
def load(d):
    out = {}
    for fn in glob.glob(d + '/*.json'):
        r = adjust(json.load(open(fn))); out[key(r)] = r
    return out
W = W2.copy(); W[8] *= float(os.environ.get('TRMULT', '1'))
def solved(r): return solve(r, W)
