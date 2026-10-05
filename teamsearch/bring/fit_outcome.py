"""Fit the bring heuristic to battle outcomes (train_labels.json from train_battles.py).

Within each team x archetype (8 tested choices), regress win share on the bring + lead features and the human-fitted model's
log-probability of that choice (so ladder habits can still count, as one feature). Group means are removed, so only differences
between a team's own choices matter. Ridge strength by leave-one-team-out. Reports, on held-out teams, the mean win share of the
model's pick among the 8 vs a random pick, the human model's pick and the best of the 8.
  python3 fit_outcome.py            -> outcome_model.json
"""
import json, os, math, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
import policy as P
Fx = P.Fx
NAMES = Fx.Matchup.BRING_NAMES + Fx.Matchup.LEAD_NAMES + ['human_logp']

def human_logp(team, arch, path=os.path.join(HERE, 'bring_model.json')):
    """log P(lead, back) under the human-fitted model, for all 90 choices"""
    wB, wL, pb, pl = P.model(path)
    m = Fx.Matchup(list(team), list(P.opp_six(arch))); sp = [Fx.G[g]['species'] for g in team]
    lsm = lambda u: np.asarray(u) - (max(u) + math.log(sum(math.exp(x - max(u)) for x in u)))
    uB = lsm([float(np.dot(wB, m.bring_feats(S) + [sum(pb.get(sp[i], 0.0) for i in S)])) for S in Fx.BRINGS])
    out = {}
    for b, S in enumerate(Fx.BRINGS):
        Ls = Fx.leads(S)
        uL = lsm([float(np.dot(wL, m.lead_feats(Lp, S) + [sum(pl.get(sp[i], 0.0) for i in Lp)])) for Lp in Ls])
        for l, Lp in enumerate(Ls): out[(Lp, tuple(i for i in S if i not in Lp))] = uB[b] + uL[l]
    return out, m

def feats(m, hl, Lp, B):
    S = tuple(sorted(Lp + B))
    return m.bring_feats(S) + m.lead_feats(tuple(Lp), S) + [hl[(tuple(Lp), tuple(B))]]

def ridge(X, y, lam):
    k = X.shape[1]; return np.linalg.solve(X.T @ X + lam * np.eye(k), X.T @ y)

if __name__ == '__main__':
    L = [r for r in json.load(open(os.path.join(HERE, 'train_labels.json'))) if r['win'] is not None]
    groups = collections.defaultdict(list)
    for r in L: groups[(r['team'], r['arch'])].append(r)
    G = {}
    for (team, arch), rs in groups.items():
        hl, m = human_logp(rs[0]['gids'], arch)
        X = np.array([feats(m, hl, r['lead'], r['back']) for r in rs]); y = np.array([r['win'] for r in rs])
        G[(team, arch)] = (X, y, rs)
    teams = sorted({t for t, _ in G})
    sd = np.std(np.vstack([X - X.mean(0) for X, _, _ in G.values()]), axis=0); sd[sd == 0] = 1
    def design(keys):
        X = np.vstack([(G[k][0] - G[k][0].mean(0)) / sd for k in keys]); y = np.concatenate([G[k][1] - G[k][1].mean() for k in keys])
        return X, y
    best = None
    for lam in (1, 10, 100, 300, 1000, 3000, 10000, 1e5):
        pick = []
        for t in teams:
            w = ridge(*design([k for k in G if k[0] != t]), lam)
            for k in G:
                if k[0] != t: continue
                X, y, rs = G[k]; pick.append(y[int(np.argmax(((X - X.mean(0)) / sd) @ w))] - y.mean())
        gain = float(np.mean(pick))
        print(f'ridge {lam:5g}: held-out pick beats a random pick by {100 * gain:+.2f} win-share points')
        if best is None or gain > best[1]: best = (lam, gain)
    lam = best[0]
    human = np.mean([y[0] - y.mean() for X, y, rs in G.values()])           # choice 0 = the human model's top pick
    oracle = np.mean([y.max() - y.mean() for X, y, rs in G.values()])
    print(f'chosen ridge {lam}: model pick {100 * best[1]:+.2f}, human model pick {100 * human:+.2f}, best of 8 (noisy, optimistic) {100 * oracle:+.2f}')
    w = ridge(*design(list(G)), lam)
    wn = w / np.abs(w).max()                                              # only the direction matters for picking
    print('relative weights (per SD, largest = 1):', ', '.join(f'{n} {x:+.2f}' for n, x in sorted(zip(NAMES, wn), key=lambda t: -abs(t[1]))[:16]))
    json.dump(dict(names=NAMES, w=(w / sd).tolist(), ridge=lam, heldout_gain=best[1], human_gain=float(human), n_groups=len(G)),
              open(os.path.join(HERE, 'outcome_model.json'), 'w'), indent=1)
