"""Fit the bring heuristic's weights to what Showdown M-C Bo3 players actually brought and led (previews.json).

Two conditional logits: which four of the six (15 options), then which two of those four lead (6 options), each on feats.py's
features plus a per-species prior (smoothed log-odds of being brought when on the team / of leading when brought, from the
training games only). Held-out games (1 in 5, by replay id) report top-1 / top-3 accuracy against simple baselines.
  python3 fit.py [--winners]        -> bring_model.json      (--winners: fit only on the winning side's choices)
"""
import json, os, sys, math, hashlib, collections
import numpy as np
from scipy.optimize import minimize
HERE = os.path.dirname(os.path.abspath(__file__))
import feats as Fx

def samples(games):
    out, skip = [], collections.Counter()
    for g in games:
        for s, o in (('p1', 'p2'), ('p2', 'p1')):
            me, op = g[s], g[o]
            if len(me['six']) != 6 or len(op['six']) != 6: skip['six'] += 1; continue
            if len(me['brought']) != 4 or len(me['lead']) != 2 or not set(me['lead']) <= set(me['brought']): skip['bring'] += 1; continue
            mine = [Fx.canon(x) for x in me['six']]; theirs = [Fx.canon(x) for x in op['six']]
            if None in mine: skip['no set'] += 1; continue
            try:
                S = tuple(sorted(me['six'].index(x) for x in me['brought'])); Lp = tuple(sorted(me['six'].index(x) for x in me['lead']))
            except ValueError: skip['name'] += 1; continue
            out.append(dict(id=g['id'], won=me['won'], six=me['six'], mine=mine, opp=[(t, 1.0) for t in theirs if t], S=S, L=Lp))
    return out, skip

def test_split(rid): return int(hashlib.md5(rid.encode()).hexdigest(), 16) % 5 == 0

def priors(train):
    on, br, led = collections.Counter(), collections.Counter(), collections.Counter()
    for x in train:
        for i, sp in enumerate(x['six']):
            on[sp] += 1; br[sp] += i in x['S']; led[sp] += i in x['L']
    pb = {sp: math.log((br[sp] + 1) / (on[sp] - br[sp] + 1)) for sp in on}
    pl = {sp: math.log((led[sp] + 1) / (br[sp] - led[sp] + 1)) for sp in on}
    return pb, pl

def design(x, pb, pl):
    m = Fx.Matchup(x['mine'], x['opp'])
    XB = np.array([m.bring_feats(S) + [sum(pb.get(x['six'][i], 0.0) for i in S)] for S in Fx.BRINGS])
    XL = {S: np.array([m.lead_feats(Lp, S) + [sum(pl.get(x['six'][i], 0.0) for i in Lp)] for Lp in Fx.leads(S)]) for S in Fx.BRINGS}
    return XB, XL

def clogit(Xs, ys, l2=0.01):
    k = Xs[0].shape[1]
    def nll(w):
        f, g = 0.0, np.zeros(k)
        for X, y in zip(Xs, ys):
            u = X @ w; u = u - u.max(); p = np.exp(u); p /= p.sum()
            f -= math.log(max(p[y], 1e-300)); g -= X[y] - p @ X
        return f + l2 * w @ w, g + 2 * l2 * w
    r = minimize(nll, np.zeros(k), jac=True, method='L-BFGS-B')
    return r.x

def acc(Xs, ys, w, top=1):
    return np.mean([y in np.argsort(-(X @ w))[:top] for X, y in zip(Xs, ys)])

if __name__ == '__main__':
    winners = '--winners' in sys.argv; noprior = '--noprior' in sys.argv
    games = json.load(open(os.path.join(HERE, 'previews.json')))['games']
    S_all, skip = samples(games)
    print(f'{len(S_all)} decisions from {len(games)} games; skipped {dict(skip)}')
    train = [x for x in S_all if not test_split(x['id']) and (x['won'] or not winners)]
    test = [x for x in S_all if test_split(x['id'])]
    pb, pl = priors(train)
    if noprior: pb, pl = {}, {}                                         # features only, no species popularity
    def build(xs):
        XB, yB, XL, yL = [], [], [], []
        for x in xs:
            b, l = design(x, pb, pl)
            XB.append(b); yB.append(Fx.BRINGS.index(x['S'])); XL.append(l[x['S']]); yL.append(Fx.leads(x['S']).index(x['L']))
        return XB, yB, XL, yL
    trB, tryB, trL, tryL = build(train); teB, teyB, teL, teyL = build(test)
    names_b = Fx.Matchup.BRING_NAMES + ['species_prior']; names_l = Fx.Matchup.LEAD_NAMES + ['species_lead_prior']
    wB = clogit(trB, tryB); wL = clogit(trL, tryL)
    # baselines: species prior only; matrix coverage only
    only = lambda k, j: np.eye(k)[j]
    pri_b, pri_l = only(len(names_b), -1), only(len(names_l), -1)
    cov_b, cov_l = only(len(names_b), 0), only(len(names_l), 0)
    print(f"bring (1 of 15)   held-out top-1 {acc(teB, teyB, wB):.3f}  top-3 {acc(teB, teyB, wB, 3):.3f}   | prior only {acc(teB, teyB, pri_b):.3f}  matrix cov only {acc(teB, teyB, cov_b):.3f}  random {1/15:.3f}")
    print(f"lead given bring  held-out top-1 {acc(teL, teyL, wL):.3f}  top-3 {acc(teL, teyL, wL, 3):.3f}   | prior only {acc(teL, teyL, pri_l):.3f}  matrix cov only {acc(teL, teyL, cov_l):.3f}  random {1/6:.3f}")
    sd_b = np.std(np.vstack(trB), axis=0); sd_l = np.std(np.vstack(trL), axis=0)
    print('bring weights (x feature SD):', ', '.join(f'{n} {w*s:+.2f}' for n, w, s in sorted(zip(names_b, wB, sd_b), key=lambda t: -abs(t[1] * t[2]))))
    print('lead weights  (x feature SD):', ', '.join(f'{n} {w*s:+.2f}' for n, w, s in sorted(zip(names_l, wL, sd_l), key=lambda t: -abs(t[1] * t[2]))))
    json.dump(dict(bring=dict(zip(names_b, wB.tolist())), lead=dict(zip(names_l, wL.tolist())), prior_bring=pb, prior_lead=pl,
                   n_train=len(train), n_test=len(test), winners_only=winners),
              open(os.path.join(HERE, 'bring_model' + ('_win' if winners else '') + ('_noprior' if noprior else '') + '.json'), 'w'), indent=1)
