"""How good is the bar? Scores win-chance models on the cached real games, at the start of every turn, against who won.
Everything is scored out of sample: five folds split by game, each model fitted on four and scored on the fifth (fits are logistic
regressions on features that flip sign when the sides are swapped, so every model is symmetric between the players).
  version 0          the eleven replay features (pssim/replay_feats.py)
With engine results (lines from the engine's position evaluation, named "<replay id> t<turn> p1"), on the positions that have them:
  engine value       the engine's one-turn equilibrium value, rescaled to real outcomes (one weight on its log-odds)
  engine static      the same for the value function at the position, no lookahead
  engine features    the planner's full feature vector, weights refitted on real games
  v0 + engine        version 0's win chance and the engine value together (two weights on their log-odds); also with the static value
  v0 + engine features
Prints and writes: log loss and Brier score per position (a coin flip scores 0.693 and 0.25), how often the favourite won, the same by turn
number, and calibration (of the positions rated 60-70%, how many were won).
usage (needs numpy: the main folder's .venv): python3 evalbar/accuracy.py [engine results .jsonl ...]
       writes evalbar/results/accuracy_v0.json, or accuracy_engine.json when engine results are given
       python3 evalbar/accuracy.py compare <name>=<engine results .jsonl> <name>=<...> [out.json]
       the engine value from each run, rescaled the same way, on the positions all runs share: overall and with Trick Room up"""
import os, sys, json, math, zlib
import numpy as np
import common as C, procs as P
RF = C.replay_feats(); sys.path.insert(0, C.PSSIM)
from fit_real_value import fit
EDGES = [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0000001]
# folds by match (the games of one Bo3 together), from Battle sim's grouping (pssim/results/value2/match_groups.json: game id -> a hash of the two
# players and the day, no names); a game it lacks is its own match. Until 2026-10-15 folds split by game, so a Bo3 could sit in two folds
_MG = os.path.join(C.MAIN, 'pssim', 'results', 'value2', 'match_groups.json')
MATCH = json.load(open(_MG)) if os.path.exists(_MG) else {}
fold = lambda rid: zlib.crc32(MATCH.get(rid, rid).encode()) % 5
logit = lambda v: math.log(min(1 - 1e-4, max(1e-4, v)) / (1 - min(1 - 1e-4, max(1e-4, v))))
def score(rows):
    """rows: (game, turn, player 1's win chance, player 1 won)"""
    p = np.clip(np.array([r[2] for r in rows]), 1e-6, 1 - 1e-6); y = np.array([r[3] for r in rows], float)
    ll = -(y * np.log(p) + (1 - y) * np.log(1 - p)); fav = (p > .5) == (y > .5)
    by_game = {}
    for r, l in zip(rows, ll): by_game.setdefault(r[0], []).append(l)
    out = {'positions': len(rows), 'games': len(by_game), 'log_loss': float(ll.mean()), 'log_loss_per_game': float(np.mean([np.mean(v) for v in by_game.values()])),
           'brier': float(((p - y) ** 2).mean()), 'favourite_won': float(fav[p != .5].mean()), 'by_turn': [], 'calibration': []}
    turns = np.array([r[1] for r in rows])
    for t in range(1, 13):
        m = turns == t if t < 12 else turns >= 12
        if m.sum(): out['by_turn'].append({'turn': t if t < 12 else '12+', 'positions': int(m.sum()), 'log_loss': float(ll[m].mean()), 'favourite_won': float(fav[m].mean())})
    P = np.r_[p, 1 - p]; Y = np.r_[y, 1 - y]                                   # every position from both sides
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        m = (P >= lo) & (P < hi)
        if m.sum(): out['calibration'].append({'lo': lo, 'hi': min(hi, 1.0), 'positions': int(m.sum()), 'rated': float(P[m].mean()), 'won': float(Y[m].mean())})
    return out
def show(tag, s):
    print(f"{tag}: {s['games']} games, {s['positions']} positions | log loss {s['log_loss']:.4f} (per game {s['log_loss_per_game']:.4f}; coin flip 0.6931) | "
          f"Brier {s['brier']:.4f} | favourite won {100 * s['favourite_won']:.1f}%")
    print('   by turn: ' + '  '.join(f"t{b['turn']} {b['log_loss']:.3f}/{100 * b['favourite_won']:.0f}%" for b in s['by_turn']))
    print('   calibration (rated -> won): ' + '  '.join(f"{100 * c['rated']:.0f}->{100 * c['won']:.0f}" for c in s['calibration']))
def paired(a, b, B=2000):
    """log loss of predictions a minus b on the same positions, with a standard error from resampling games"""
    ll = lambda r: -math.log(min(1 - 1e-6, max(1e-6, r[2] if r[3] else 1 - r[2])))
    kb = {(r[0], r[1]): ll(r) for r in b}; d = {}
    for r in a: d.setdefault(r[0], []).append(ll(r) - kb[(r[0], r[1])])
    G = [np.array(v) for v in d.values()]; n = np.array([len(v) for v in G]); t = np.array([v.sum() for v in G]); rng = np.random.default_rng(1)
    idx = rng.integers(0, len(G), (B, len(G)))
    return float(t.sum() / n.sum()), float(np.std(t[idx].sum(1) / n[idx].sum(1)))
def cv(rows, feats):
    """rows: dicts with g, t, y; feats(row) -> feature list. Out-of-sample predictions as (game, turn, p, won)."""
    scored = []
    for k in range(5):
        X = []; y = []
        for r in rows:
            if fold(r['g']) == k: continue
            f = feats(r); X.append(f); y.append(r['y']); X.append([-v for v in f]); y.append(1 - r['y'])
        w = fit(np.array(X, float), np.array(y, float)).tolist()
        scored += [(r['g'], r['t'], C.v0(w, feats(r)), r['y']) for r in rows if fold(r['g']) == k]
    return scored
def real_rows():
    rows = []
    for rid, log in C.games():
        try: fr, w, _ = RF.game(log)
        except Exception: continue
        if w is not None and fr: rows += [{'g': rid, 't': t, 'f': f, 'y': 1 if w == 'p1' else 0} for t, f in fr]
    return rows
def load_engine(f):
    eng = {}
    for l in open(f):
        d = json.loads(l)
        if d.get('value') is not None and d['name'].endswith(' p1'): eng[d['name'][:-3]] = d
    return eng
def compare(args, rows):
    runs = [a.split('=', 1) for a in args if '=' in a]; outf = next((a for a in args if '=' not in a), None)
    E = {nm: load_engine(f) for nm, f in runs}
    keys = set.intersection(*(set(e) for e in E.values()))
    sub = [{**r, 'e': {nm: E[nm][f"{r['g']} t{r['t']}"] for nm in E}} for r in rows if f"{r['g']} t{r['t']}" in keys]
    tr = lambda r: r['e'][runs[0][0]]['feats'][3] != 0                          # Trick Room up (its feature is non-zero)
    P = {}; out = {'positions': len(sub), 'tr_positions': sum(map(tr, sub))}
    for nm in E:
        P[nm] = cv(sub, lambda r, nm=nm: [logit(r['e'][nm]['value'])])
        X = np.array([[logit(r['e'][nm]['value'])] for r in sub] + [[-logit(r['e'][nm]['value'])] for r in sub]); y = np.array([r['y'] for r in sub] + [1 - r['y'] for r in sub], float)
        trk = {(r['g'], r['t']) for r in sub if tr(r)}
        s_all = score(P[nm]); s_tr = score([p for p in P[nm] if (p[0], p[1]) in trk])
        out[nm] = {'all': s_all, 'trick_room_up': s_tr, 'weight': fit(X, y).tolist()}
        print(f"{nm}: log loss {s_all['log_loss']:.4f}, favourite won {100 * s_all['favourite_won']:.1f}% | Trick Room up ({s_tr['positions']} positions): "
              f"log loss {s_tr['log_loss']:.4f}, favourite won {100 * s_tr['favourite_won']:.1f}% | weight on log-odds {out[nm]['weight'][1]:.3f}")
    names = list(E)
    for a in names[1:]:
        trk = {(r['g'], r['t']) for r in sub if tr(r)}
        d_all = paired(P[a], P[names[0]]); d_tr = paired([p for p in P[a] if (p[0], p[1]) in trk], [p for p in P[names[0]] if (p[0], p[1]) in trk])
        out[f'{a} - {names[0]}'] = {'all': d_all, 'trick_room_up': d_tr}
        print(f"{a} minus {names[0]}: log loss {d_all[0]:+.4f} ± {d_all[1]:.4f} overall, {d_tr[0]:+.4f} ± {d_tr[1]:.4f} with Trick Room up")
    if outf: json.dump(out, open(outf, 'w'), indent=1)
if __name__ == '__main__':
    P.own()
    rows = real_rows(); out = {}
    if len(sys.argv) > 1 and sys.argv[1] == 'compare': compare(sys.argv[2:], rows); sys.exit()
    if len(sys.argv) < 2:
        s = score(cv(rows, lambda r: r['f'])); show('version 0, out of sample', s)
        outf = os.path.join(C.HERE, 'results', 'accuracy_v0.json'); out = {'model': 'v0: 11 replay features, logistic, 5-fold by game', **s}
    else:
        eng = {}
        for f in sys.argv[1:]:
            for l in open(f):
                d = json.loads(l)
                if d.get('value') is not None and d['name'].endswith(' p1'): eng[d['name'][:-3]] = d
        # version 0 is fitted on all the real games outside the fold, not only those with engine results; its out-of-fold win chance is
        # then one input of the combined model
        v0p = {(g, t): p for g, t, p, _ in cv(rows, lambda r: r['f'])}
        sub = [{**r, 'e': eng[f"{r['g']} t{r['t']}"], 'v0': v0p[(r['g'], r['t'])]} for r in rows if f"{r['g']} t{r['t']}" in eng]
        base = [(r['g'], r['t'], r['v0'], r['y']) for r in sub]
        s = score(base); show('version 0 (same positions)', s); out['version 0 (same positions)'] = s
        models = {'engine value': lambda r: [logit(r['e']['value'])], 'engine static': lambda r: [logit(r['e']['static'])],
                  'v0 + engine': lambda r: [logit(r['v0']), logit(r['e']['value'])], 'v0 + engine static': lambda r: [logit(r['v0']), logit(r['e']['static'])],
                  'v0 + engine value + static': lambda r: [logit(r['v0']), logit(r['e']['value']), logit(r['e']['static'])],
                  'engine features': lambda r: r['e']['feats'], 'v0 + engine features': lambda r: [logit(r['v0'])] + r['e']['feats']}
        for nm, fx in models.items():
            pr = cv(sub, fx); s = score(pr); s['vs_version_0'] = paired(pr, base); show(nm, s); out[nm] = s
            print(f"   log loss against version 0 on the same positions: {s['vs_version_0'][0]:+.4f} ± {s['vs_version_0'][1]:.4f}")
        X = np.array([models['v0 + engine'](r) for r in sub] + [[-v for v in models['v0 + engine'](r)] for r in sub]); y = np.array([r['y'] for r in sub] + [1 - r['y'] for r in sub], float)
        out['weights'] = {'v0 + engine (all positions; intercept, v0 log-odds, engine log-odds)': fit(X, y).tolist(),
                          'engine value (intercept, engine log-odds)': fit(X[:, 1:], y).tolist()}
        print('weights:', json.dumps(out['weights']))
        outf = os.path.join(C.HERE, 'results', 'accuracy_engine.json')
    os.makedirs(os.path.dirname(outf), exist_ok=True); json.dump(out, open(outf, 'w'), indent=1)
