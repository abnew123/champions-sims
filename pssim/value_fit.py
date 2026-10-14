"""Fit and compare position values on real positions (2026-10-12; value_data.py builds the data). A value scores a position as
sigmoid(h(e) - h(e_swapped)): e = [side 0's matchup features, side 1's, the field as side 0 sees it, plan.rs feats], e_swapped =
[side 1's, side 0's, the field as side 1 sees it, -feats] (champ vfeats), so swapping the sides flips the value exactly. h is linear or a
one-hidden-layer tanh net, fitted with a ridge penalty by L-BFGS. Targets: the game's result (log loss), or the one-turn search's value
(value_data.py search: squared error on its log-odds, i.e. distilling the search into a static value). Everything is scored on the 560
held-out games against real results, as log loss with a rescale fitted on the training games (SE by bootstrapping games).
  ../.venv/bin/python3 value_fit.py compare [target=outcome|search|both] [parts=fit[,new]] [configs=hidden:l2,...]"""
import os, sys, json, math, random, collections
import numpy as np
from scipy.optimize import minimize
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'results', 'value')
def load(part):
    meta = {m['name']: m for m in map(json.loads, open(os.path.join(OUT, f'real_{part}.meta.jsonl')))}
    ev = {}
    # env VALUE_SUFFIX (e.g. _fc, 2026-10-12: features with the full calc data): features from real_<part>.vfeats<suffix>.jsonl and search
    # values overridden by real_<part><suffix>.eval.jsonl where that file has them (the positions the search was redone for)
    # VALUE_EVAL_SUFFIXES (2026-10-13): several override layers in order, e.g. _fc,_acc (the accuracy fix's redone searches over the full
    # calc data's); default VALUE_SUFFIX alone
    sfx = os.environ.get('VALUE_SUFFIX', ''); layers = [x for x in os.environ.get('VALUE_EVAL_SUFFIXES', sfx).split(',') if x]
    # once the base search is stamped with its positions' hash (value_data.py, 2026-10-14), every file read must carry the same stamp:
    # the _fc / _acc layers and features of an older rebuild are refused rather than mixed in by name (the outside review)
    base = os.path.join(OUT, f'real_{part}.eval.jsonl')
    want = open(base + '.src').read().strip() if os.path.exists(base + '.src') else None
    def ok(f):
        if want is None: return True
        got = open(f + '.src').read().strip() if os.path.exists(f + '.src') else None
        if got != want: print(f'  skipping {os.path.basename(f)}: made from other positions than the current real_{part}.pos.jsonl'); return False
        return True
    for pe in [base] + [os.path.join(OUT, f'real_{part}{x}.eval.jsonl') for x in layers]:
        if os.path.exists(pe) and ok(pe):
            for l in open(pe):
                r = json.loads(l)
                if 'error' not in r: ev[r['name']] = r['value']
    E, S, y, g, st, sv, names, rt = [], [], [], [], [], [], [], []
    vf = os.path.join(OUT, f"real_{part}.vfeats{os.environ.get('VALUE_SUFFIX', '')}.jsonl")
    if not ok(vf): raise SystemExit(f'the features in {os.path.basename(vf)} do not belong to the current positions: run value_data.py feats')
    for l in open(vf):
        r = json.loads(l)
        if 'error' in r or r['name'] not in meta: continue
        m = meta[r['name']]; x = np.array(r['x'][:28])
        E.append(np.concatenate([r['f0'], r['f1'], r['g0'], x])); S.append(np.concatenate([r['f1'], r['f0'], r['g1'], -x]))
        y.append(m['y']); g.append(m['game']); st.append(r['static']); sv.append(ev.get(r['name'], np.nan)); names.append(r['name'])
        rt.append(m.get('rating') or 0.0)
    return dict(E=np.array(E), S=np.array(S), y=np.array(y), g=g, static=np.array(st), search=np.array(sv), names=names, rating=np.array(rt))
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
        n = len(target[0]) if kind == 'mix' else len(target)
        def f(p):
            z, back = s._z(p, E, S, True)
            if kind == 'outcome':
                l = ll(z, target).mean(); e = (1 / (1 + np.exp(-np.clip(z, -30, 30))) - target) / n
            elif kind == 'mix':
                yv, sv = target; a = float(os.environ.get('MIX_W', 0.1)); r = z - sv
                l = ll(z, yv).mean() + a * np.mean(r ** 2); e = (1 / (1 + np.exp(-np.clip(z, -30, 30))) - yv) / n + a * 2 * r / n
            else:
                r = z - target; l = np.mean(r ** 2); e = 2 * r / n
            return l + s.l2 * p @ p, back(e) + 2 * s.l2 * p
        s.p = minimize(f, p0, jac=True, method='L-BFGS-B', options={'maxiter': 3000}).x
        return s
    def z(s, E, S): return s._z(s.p, E, S)
def load_parts(parts):
    """the training parts together; env MIN_RATING keeps only positions from games whose players' mean rating is at least that"""
    D = [load(p) for p in parts]
    F = {k: (np.concatenate([d[k] for d in D]) if isinstance(D[0][k], np.ndarray) else sum((d[k] for d in D), [])) for k in D[0]}
    mr = float(os.environ.get('MIN_RATING', 0))
    if mr:
        keep = F['rating'] >= mr
        F = {k: (v[keep] if isinstance(v, np.ndarray) else [x for x, kk in zip(v, keep) if kk]) for k, v in F.items()}
    return F
def compare(target='outcome', parts=('fit',), configs=None):
    F = load_parts(parts); H = load('hold')
    sd = np.concatenate([F['E'], F['S']]).std(0); sd = np.where(sd < 1e-3, 1.0, sd)   # near-constant columns are left unscaled
    print(f"fit {len(F['y'])} positions / {len(set(F['g']))} games{' (rating ' + os.environ['MIN_RATING'] + '+)' if os.environ.get('MIN_RATING') else ''}, held out {len(H['y'])} / {len(set(H['g']))}; {F['E'].shape[1]} inputs per view")
    rows = []
    def report(name, zf, zh):
        c = rescale(zf, F['y']); l = ll(c * zh, H['y']); rows.append((name, l))
        print(f"  {name:46s} held-out log loss {l.mean():.4f} ± {boot(l, H['g']):.4f}")
    report('current static value (sym2), rescaled', lg(F['static']), lg(H['static']))
    if not np.isnan(H['search']).any():
        report('one-turn search (sym2 at the leaves)', lg(np.nan_to_num(F['search'], nan=0.5)), lg(H['search']))
    has_search = not np.isnan(F['search']).any()
    for kind in (['outcome', 'search'] if target == 'both' else [target]):
        if kind in ('search', 'mix') and not has_search: print('  (no search values for the fit set yet)'); continue
        tgt = F['y'] if kind == 'outcome' else lg(F['search']) if kind == 'search' else (F['y'], lg(F['search']))
        for h, l2 in (configs or ((0, 1e-4), (0, 1e-3), (16, 1e-4), (16, 1e-3), (32, 1e-3), (64, 3e-3))):
            m = Model(h, l2, sd).fit(F['E'], F['S'], tgt, kind)
            report(f"{'linear' if h == 0 else f'net h{h}'} l2 {l2} on {kind}", m.z(F['E'], F['S']), m.z(H['E'], H['S']))
    base = dict(rows)['current static value (sym2), rescaled']
    best = min(rows, key=lambda r: r[1].mean())
    print(f"  best: {best[0]}, {best[1].mean() - base.mean():+.4f} ± {boot(best[1] - base, H['g']):.4f} against the current static value")
def export(hidden=16, l2=1e-3, target='search', out=None, parts=('fit',)):
    """fit h on the training parts and write it for the engine (EG_VNET): input scales, weights, and the sizes of the vfeats blocks"""
    F = load_parts(parts); H = load('hold')
    sd = np.concatenate([F['E'], F['S']]).std(0); sd = np.where(sd < 1e-3, 1.0, sd)
    tgt = lg(F['search']) if target == 'search' else F['y'] if target == 'outcome' else (F['y'], lg(F['search']))
    m = Model(hidden, l2, sd).fit(F['E'], F['S'], tgt, target)
    d = F['E'].shape[1]
    W = m.p[:hidden * d].reshape(hidden, d).tolist() if hidden else None; v = m.p[hidden * d:].tolist() if hidden else m.p.tolist()
    zh = m.z(H['E'], H['S']); c = rescale(m.z(F['E'], F['S']), F['y'])
    print(f"h{hidden} l2 {l2} on {target}: held-out log loss {ll(c * zh, H['y']).mean():.4f} (rescale {c:.3f})")
    out = out or os.path.join(OUT, f"vnet_h{hidden}_{target}{'_' + '+'.join(parts) if parts != ('fit',) else ''}{os.environ.get('VALUE_SUFFIX', '')}.json")
    json.dump({'hidden': hidden, 'sd': sd.tolist(), 'W': W, 'v': v, 'blocks': {'side': 32, 'field': 12, 'x': 28}, 'target': target, 'l2': l2,
               'note': 'value = sigmoid(h(e) - h(e_swapped)); e = [side 0, side 1, field for 0, plan.rs feats[:28]] (value_fit.py)'}, open(out, 'w'))
    print('->', out)
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'compare':
        cf = [tuple(float(x) if '.' in x or 'e' in x else int(x) for x in c.split(':')) for c in a[3].split(',')] if len(a) > 3 else None
        compare(a[1] if len(a) > 1 else 'outcome', tuple(a[2].split(',')) if len(a) > 2 else ('fit',), cf)
    elif a[0] == 'export': export(int(a[1]) if len(a) > 1 else 16, float(a[2]) if len(a) > 2 else 1e-3, a[3] if len(a) > 3 else 'search',
                                  parts=tuple(a[4].split(',')) if len(a) > 4 else ('fit',))
