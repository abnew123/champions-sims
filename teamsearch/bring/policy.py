"""Bring policy for the hill climb: for one of my sixes and an opposing archetype (the replay model, pssim/opp_model_{a,b}.json),
pick the four to bring and the two to lead with the fitted bring heuristic (bring_model.json from fit.py): the (bring, lead)
with the highest log P(bring) + log P(lead | bring).

The archetype's likely six: each of its 6 modelled lead pairs (shares renormalized) contributes its two leads (weight 1) and its
back-row rates; a species' weight is its share-weighted chance of being on the field, 0..1.
"""
import json, os, math, functools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
import feats as Fx
PS = os.path.join(Fx.L.ROOT, 'pssim')
OPP = {**json.load(open(os.path.join(PS, 'opp_model_a.json'))), **json.load(open(os.path.join(PS, 'opp_model_b.json')))}
ARCH_SHARE = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
              'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}   # as pssim/sp_team_cmp.py
K = 6

def pair_shares(arch):
    ps = OPP[arch]['pairs'][:K]; tot = sum(p['share'] for p in ps)
    return [p['share'] / tot for p in ps]

@functools.lru_cache(maxsize=None)
def opp_six(arch, min_w=0.05):
    w = {}
    for p, sh in zip(OPP[arch]['pairs'][:K], pair_shares(arch)):
        for sp in p['pair'].split(' + '): w[sp] = w.get(sp, 0) + sh
        for part in p.get('back', '').split(','):
            if ':' in part:
                sp, r = part.strip().rsplit(':', 1); w[sp] = w.get(sp, 0) + sh * float(r)
    out = [(Fx.canon(sp), round(x, 3)) for sp, x in sorted(w.items(), key=lambda t: -t[1]) if x >= min_w]
    return tuple((g, x) for g, x in out if g)

@functools.lru_cache(maxsize=None)
def model(path=os.path.join(HERE, 'bring_model.json')):
    m = json.load(open(path))
    return (np.array(list(m['bring'].values())), np.array(list(m['lead'].values())), m['prior_bring'], m['prior_lead'])

def choose(team, arch, path=os.path.join(HERE, 'bring_model.json')):
    """team: 6 grid ids -> (lead gids, back gids, log-prob of that choice)"""
    wB, wL, pb, pl = model(path)
    m = Fx.Matchup(list(team), list(opp_six(arch)))
    sp = [Fx.G[g]['species'] for g in team]
    def lsm(u): u = np.asarray(u); return u - (u.max() + math.log(np.exp(u - u.max()).sum()))
    uB = lsm([np.dot(wB, m.bring_feats(S) + [sum(pb.get(sp[i], 0.0) for i in S)]) for S in Fx.BRINGS])
    best = None
    for b, S in enumerate(Fx.BRINGS):
        Ls = Fx.leads(S)
        uL = lsm([np.dot(wL, m.lead_feats(Lp, S) + [sum(pl.get(sp[i], 0.0) for i in Lp)]) for Lp in Ls])
        for l, Lp in enumerate(Ls):
            v = uB[b] + uL[l]
            if best is None or v > best[0]: best = (v, Lp, tuple(i for i in S if i not in Lp))
    v, Lp, back = best
    return [team[i] for i in Lp], [team[i] for i in back], float(v)

def matrix_score(team, path=os.path.join(HERE, 'bring_model.json')):
    """cheap team strength for pre-filtering: archetype-weighted one-on-one coverage and exposure of the chosen four"""
    tot = 0.0
    for arch, sh in ARCH_SHARE.items():
        lead, back, _ = chooser()(team, arch)
        m = Fx.Matchup(list(team), list(opp_six(arch))); S = tuple(sorted(team.index(g) for g in lead + back))
        f = m.bring_feats(S)
        cov = f[1] if f[7] else f[0]                                   # with a Trick Room setter brought: the Trick Room cells
        tot += sh * (cov + f[2]) / 2
    return tot / sum(ARCH_SHARE.values())

OUTCOME = os.path.join(HERE, 'outcome_model.json')
def choose_outcome(team, arch, path=OUTCOME):
    """the (lead, back) with the best predicted win share under the outcome-fitted weights (fit_outcome.py)"""
    import fit_outcome as FO
    w = np.array(json.load(open(path))['w'])
    hl, m = FO.human_logp(list(team), arch)
    v, Lp, B = max(((float(np.dot(w, FO.feats(m, hl, Lp, B))), Lp, B) for (Lp, B) in hl), key=lambda t: t[0])
    return [team[i] for i in Lp], [team[i] for i in B], v

def chooser():
    """outcome-fitted brings once outcome_model.json exists (TS_BRING=human forces the replay-fitted model)"""
    return choose_outcome if os.path.exists(OUTCOME) and os.environ.get('TS_BRING', 'outcome') == 'outcome' else choose

def ranked_outcome(team, arch, path=OUTCOME):
    """all 90 (lead, back) choices, best predicted first, under the outcome-fitted weights"""
    import fit_outcome as FO
    w = np.array(json.load(open(path))['w'])
    hl, m = FO.human_logp(list(team), arch)
    r = sorted(((float(np.dot(w, FO.feats(m, hl, Lp, B))), Lp, B) for (Lp, B) in hl), key=lambda t: -t[0])
    return [([team[i] for i in Lp], [team[i] for i in B]) for _, Lp, B in r]
