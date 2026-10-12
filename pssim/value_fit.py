"""Fit and compare position values on real positions (2026-10-12; value_data.py builds the data). A value scores a position as
sigmoid(h(e) - h(e_swapped)): e = [side 0's matchup features, side 1's, the field as side 0 sees it, plan.rs feats], e_swapped =
[side 1's, side 0's, the field as side 1 sees it, -feats] (champ vfeats), so swapping the sides flips the value exactly. h is linear or a
one-hidden-layer tanh net, fitted with a ridge penalty by L-BFGS. Targets: the game's result (log loss), or the one-turn search's value
(value_data.py search: squared error on its log-odds, i.e. distilling the search into a static value). Everything is scored on the 560
held-out games against real results, as log loss with a rescale fitted on the training games (SE by bootstrapping games).
  ../.venv/bin/python3 value_fit.py compare [target=outcome|search|both]"""
import os, sys, json, math, random, collections
import numpy as np
from scipy.optimize import minimize
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'results', 'value')
def load(part):
    meta = {m['name']: m for m in map(json.loads, open(os.path.join(OUT, f'real_{part}.meta.jsonl')))}
    ev = {}
    pe = os.path.join(OUT, f'real_{part}.eval.jsonl')
    if os.path.exists(pe):
        for l in open(pe):
            r = json.loads(l)
            if 'error' not in r: ev[r['name']] = r['value']
    E, S, y, g, st, sv, names = [], [], [], [], [], [], []
    for l in open(os.path.join(OUT, f'real_{part}.vfeats.jsonl')):
        r = json.loads(l)
        if 'error' in r or r['name'] not in meta: continue
        m = meta[r['name']]; x = np.array(r['x'][:28])
        E.append(np.concatenate([r['f0'], r['f1'], r['g0'], x])); S.append(np.concatenate([r['f1'], r['f0'], r['g1'], -x]))
        y.append(m['y']); g.append(m['game']); st.append(r['static']); sv.append(ev.get(r['name'], np.nan)); names.append(r['name'])
    return dict(E=np.array(E), S=np.array(S), y=np.array(y), g=g, static=np.array(st), search=np.array(sv), names=names)
def lg(p): p = np.clip(p, 1e-4, 1 - 1e-4); return np.log(p / (1 - p))
def ll(z, y): z = np.clip(z, -30, 30); return np.logaddexp(0, -z) * y + np.logaddexp(0, z) * (1 - y)
def rescale(z, y): return minimize(lambda c: ll(c[0] * z, y).mean(), [1.0], method='Nelder-Mead').x[0]
def boot(v, games, B=300):
    by = collections.defaultdict(list)
    for k, x in zip(games, v): by[k].append(x)
    keys = list(by); rnd = random.Random(5)
    return float(np.std([np.mean([x for k in [rnd.choice(keys) for _ in keys] for x in by[k]]) for _ in range(B)]))
class Model:
    """z = h(E) - h(S); h(x) = v . tanh(W x / sd) (hidden > 0) or w . (x / sd)"""
    def __init__(s, hidden, l2, sd): s.h, s.l2, s.sd = hidden, l2, sd
    def _z(s, p, E, S, grad=False):
        En, Sn = E / s.sd, S / s.sd
        if s.h == 0:
            D = En - Sn; z = D @ p
            return (z, lambda e: D.T @ e) if grad else z
        d = E.shape[1]; W = p[:s.h * d].reshape(s.h, d); v = p[s.h * d:]
        HE, HS = np.tanh(En @ W.T), np.tanh(Sn @ W.T); z = (HE - HS) @ v
        if not grad: return z
        def back(e):
            gv = (HE - HS).T @ e
            gE = np.outer(e, v) * (1 - HE ** 2); gS = np.outer(e, v) * (1 - HS ** 2)
            return np.concatenate([(gE.T @ En - gS.T @ Sn).ravel(), gv])
        return z, back
    def fit(s, E, S, target, kind, seed=0):
        d = E.shape[1]; rnd = np.random.default_rng(seed)
        p0 = np.zeros(d) if s.h == 0 else np.concatenate([rnd.normal(0, 0.2, s.h * d), rnd.normal(0, 0.2, s.h)])
        n = len(target)
        def f(p):
            z, back = s._z(p, E, S, True)
            if kind == 'outcome':
                l = ll(z, target).mean(); e = (1 / (1 + np.exp(-np.clip(z, -30, 30))) - target) / n
            else:
                r = z - target; l = np.mean(r ** 2); e = 2 * r / n
            return l + s.l2 * p @ p, back(e) + 2 * s.l2 * p
        s.p = minimize(f, p0, jac=True, method='L-BFGS-B', options={'maxiter': 3000}).x
        return s
    def z(s, E, S): return s._z(s.p, E, S)
def compare(target='outcome'):
    F = load('fit'); H = load('hold')
    sd = np.concatenate([F['E'], F['S']]).std(0); sd = np.where(sd < 1e-3, 1.0, sd)   # near-constant columns are left unscaled
    print(f"fit {len(F['y'])} positions / {len(set(F['g']))} games, held out {len(H['y'])} / {len(set(H['g']))}; {F['E'].shape[1]} inputs per view")
    rows = []
    def report(name, zf, zh):
        c = rescale(zf, F['y']); l = ll(c * zh, H['y']); rows.append((name, l))
        print(f"  {name:46s} held-out log loss {l.mean():.4f} ± {boot(l, H['g']):.4f}")
    report('current static value (sym2), rescaled', lg(F['static']), lg(H['static']))
    if not np.isnan(H['search']).any():
        report('one-turn search (sym2 at the leaves)', lg(np.nan_to_num(F['search'], nan=0.5)), lg(H['search']))
    has_search = not np.isnan(F['search']).any()
    for kind in (['outcome', 'search'] if target == 'both' else [target]):
        if kind == 'search' and not has_search: print('  (no search values for the fit set yet)'); continue
        tgt = F['y'] if kind == 'outcome' else lg(F['search'])
        for h, l2 in ((0, 1e-4), (0, 1e-3), (16, 1e-4), (16, 1e-3), (32, 1e-3), (64, 3e-3)):
            m = Model(h, l2, sd).fit(F['E'], F['S'], tgt, kind)
            report(f"{'linear' if h == 0 else f'net h{h}'} l2 {l2} on {kind}", m.z(F['E'], F['S']), m.z(H['E'], H['S']))
    base = dict(rows)['current static value (sym2), rescaled']
    best = min(rows, key=lambda r: r[1].mean())
    print(f"  best: {best[0]}, {best[1].mean() - base.mean():+.4f} ± {boot(best[1] - base, H['g']):.4f} against the current static value")
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'compare': compare(a[1] if len(a) > 1 else 'outcome')
