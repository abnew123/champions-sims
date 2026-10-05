# Shared helpers for the Trick Room team sheet: load results, credit a turn-one Trick Room to the slower team, solve.
import json, glob, math, os, numpy as np
os.environ.setdefault('EXCLUDE_MOVES', '')
from analyze import solve, W2
# TR_CREDIT=fitted: leave Trick Room as simulated (it counts for whoever set it, the replay fit); for teams not built around Trick Room.
# Default (slower-four): credit it to the slower brought four, as below.
CREDIT = os.environ.get('TR_CREDIT', 'slower-four')
SPD = json.load(open(os.path.join(os.path.dirname(__file__) or '.', os.environ.get('TR_SPEEDS', 'tr_speeds.json')))) if CREDIT != 'fitted' else {}   # TR_SPEEDS: another team's back rows
# TRMULT_FILE: per-archetype multipliers on the Trick Room credit (from the 2v2 endgame, eg_trmult.py); default 1
TRM = json.load(open(os.environ['TRMULT_FILE'])) if os.environ.get('TRMULT_FILE') else {}
def key(r): return (r['arch'], '+'.join(r['myLead']), r['pair'])
def tr_credit(r):
    v = SPD[f"{r['arch']}|{'+'.join(r['myLead'])}|{r['pair']}"]
    return math.tanh((v['t'] - v['m']) / 15.0)          # +1: Trick Room up helps me (my four are much slower)
def adjust(r):
    """Trick Room up after turn one (feature 8 nonzero: exactly one side set it) scores for the slower team, whoever set it."""
    if CREDIT == 'fitted': r['trCredit'] = None; return r
    s = tr_credit(r) * TRM.get(r['arch'], 1.0)
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
