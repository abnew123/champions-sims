"""What does the learned value get wrong in Trick Room positions? (2026-11-04, the user: "Yes" to fitting it on self-play.) The engine
overrates the side Trick Room favours against itself too: on 200 real starts with our Trick Room just up it predicts 60% and self-play
gives 50% (real games 46%), so self-play can supply the data. pssim/tr_value_data.sh plays real Trick Room starts with BATTLE_VFEATS=1:
the net's inputs at every turn's start (vfeats: f0 / f1 per side, g0 / g1 for the field, the 28 plan features x) and its static value.
A flat correction per phase (TR_CORR, champ-battle-v40) fixed the level but not the play, since one turn's leaves share a phase and get
the same shift. Here the correction also depends on what differs between leaves: by maximum likelihood (ridge on the slopes, the penalty
chosen by 5-fold cross-validation over games), the result on
    a x (the static value's log-odds) + b + c_phase x s + [Trick Room up] x w_up . u + [after it] x w_after . u
s = +1 when Trick Room favours side 0 (the slower on average over its living Pokemon), -1 when side 1; phases: Trick Room up with 1 / 2 /
3 / 4 turns left, and after it (down, the slower side has used a Trick Room); u = (f0 - f1, g0 - g1, x), the net's own antisymmetric
inputs, so the corrected value stays symmetric. The engine adds the fitted terms / a to the net's log-odds (TR_HEAD, champ-battle-v41).
  .venv/bin/python3 bot/tr_value.py fit <self-play out dir> [export.json]      (games whose job is a multiple of 5 are left out: the A/B's starts)
  .venv/bin/python3 bot/tr_value.py abstarts <starts prefix> <out prefix> [games a start=2]   (those left-out starts, for deep_endgames.sh)
  .venv/bin/python3 bot/tr_value.py real <export.json> <prefix> ...    (real ladder decisions: <prefix>_turns.pos.jsonl / .vfeats.jsonl / .meta.json)"""
import os, sys, json, glob, math, collections
import numpy as np
SIDE = ["alive", "hp", "actives", "bench alive", "bench hp", "damage potential", "focus potential", "foes KO-able alone", "foes KO-able first",
        "foes KO-able by focus", "outspeeds", "priority potential", "spread potential", "Protect on hand", "Fake Out on hand", "redirection on hand",
        "speed control on hand", "Intimidate on the bench", "bench threat", "bench switch-in", "actives in danger", "primary boosts", "Speed boosts",
        "defence boosts", "asleep/frozen", "paralysed", "burned/poisoned", "Mega available", "choice-locked", "Taunted/Encored", "Substitute", "setup on hand"]
FIELD = ["Trick Room turns", "Trick Room favours me", "my Tailwind", "their Tailwind", "my screens", "their screens", "grassy", "psychic",
         "electric", "misty", "weather turns", "turn"]
NAMES = [f'{n} (0 - 1)' for n in SIDE] + [f'field: {n} (0 - 1)' for n in FIELD] + [f'plan feat {k}' for k in range(28)]
PH = ['TR 1 left', 'TR 2 left', 'TR 3 left', 'TR 4 left', 'after TR']


def phase(tr, spe, tru):
    """(phase or None, s): s = +1 if Trick Room favours side 0 (slower on average), -1 if side 1, 0 on a tie"""
    if spe[0] == spe[1]: return None, 0
    s = 1 if spe[0] < spe[1] else -1
    if tr: return f'TR {min(int(tr), 4)} left', s
    if tru[0 if s == 1 else 1]: return 'after TR', s
    return None, s


def unit(r):
    return np.array(r['f0']) - np.array(r['f1']), np.array(r['g0']) - np.array(r['g1']), np.array(r['x'][:28] + [0.0] * (28 - len(r['x'][:28])))


def rows_selfplay(d):
    R = []
    for f in glob.glob(os.path.join(d, '*.json')):
        j = json.load(open(f)); r = (j.get('rows') or [{}])[0]
        if r.get('v') is None or not r.get('VF'): continue
        for x in r['VF']:
            ph, s = phase(x['tr'], x['spe'], x['tru']); df, dg, xx = unit(x)
            R.append({'game': j['job'], 'z': x['static'], 'ph': ph, 's': s, 'u': np.concatenate([df, dg, xx]), 'y': float(r['v']), 'kind': j.get('kind')})
    return R


def design(R, sd, terms):
    """columns: z, 1, then per term set: 'const' the 5 phase constants x s; 'slope' w_up . u and w_after . u (u scaled by sd)"""
    n = len(R); cols = [np.array([math.log(min(max(r['z'], 1e-6), 1 - 1e-6) / (1 - min(max(r['z'], 1e-6), 1 - 1e-6))) for r in R]), np.ones(n)]
    if 'const' in terms:
        for p in PH: cols.append(np.array([r['s'] * (r['ph'] == p) for r in R], float))
    if 'slope' in terms:
        U = np.array([r['u'] for r in R]) / sd
        up = np.array([r['ph'] is not None and r['ph'] != 'after TR' for r in R], float); af = np.array([r['ph'] == 'after TR' for r in R], float)
        cols += list((U * up[:, None]).T) + list((U * af[:, None]).T)
    X = np.column_stack(cols); pen = np.zeros(X.shape[1]); pen[2 + (5 if 'const' in terms else 0):] = 1.0
    return X, pen


def fit(X, y, pen, lam, iters=60):
    w = np.zeros(X.shape[1]); w[0] = 0.8
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ w)); W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + lam * np.diag(pen) + 1e-8 * np.eye(len(w))
        step = np.linalg.solve(H, X.T @ (y - p) - lam * pen * w); w += step
        if np.abs(step).max() < 1e-8: break
    return w


def ll(X, y, w):
    p = np.clip(1 / (1 + np.exp(-X @ w)), 1e-9, 1 - 1e-9); return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def cv(R, sd, terms, lam, k=5):
    games = sorted({r['game'] for r in R}); fold = {g: i % k for i, g in enumerate(np.random.RandomState(7).permutation(games))}
    X, pen = design(R, sd, terms); y = np.array([r['y'] for r in R]); f = np.array([fold[r['game']] for r in R]); out = np.zeros(len(R))
    for i in range(k):
        w = fit(X[f != i], y[f != i], pen, lam); out[f == i] = ll(X[f == i], y[f == i], w)
    return out


def se_by_game(R, d):
    g = collections.defaultdict(float)
    for r, x in zip(R, d): g[r['game']] += x
    v = np.array(list(g.values())); return v.sum() / len(R), v.std(ddof=1) * math.sqrt(len(v)) / len(R)


HOLD = 5   # games with job % HOLD == 0 stay out of the fit: their starts are the self-play A/B's


def main_fit(d, export=None):
    R = [r for r in rows_selfplay(d) if r['game'] % HOLD]; y = np.array([r['y'] for r in R])
    print(f"{len(R)} positions in {len({r['game'] for r in R})} self-play games; " + ', '.join(f'{p}: {sum(1 for r in R if r["ph"] == p)}' for p in PH))
    tr = [r for r in R if r['ph']]; sd = np.array([r['u'] for r in tr]).std(axis=0); sd[sd < 1e-9] = 1.0
    base = cv(R, sd, (), 0.0); const = cv(R, sd, ('const',), 0.0)
    print(f"cross-validated log loss: the value alone {base.mean():.4f}, + phase constants {const.mean():.4f} ({'%+.4f ± %.4f' % se_by_game(R, const - base)})")
    best = None
    for lam in (1, 3, 10, 30, 100, 300, 1000):
        full = cv(R, sd, ('const', 'slope'), lam); m, s = se_by_game(R, full - base)
        print(f"  + slopes, ridge {lam:5d}: {full.mean():.4f} ({m:+.4f} ± {s:.4f} against the value alone; {'%+.4f' % se_by_game(R, full - const)[0]} against the constants)")
        if best is None or full.mean() < best[1]: best = (lam, full.mean())
    lam = best[0]; X, pen = design(R, sd, ('const', 'slope')); w = fit(X, y, pen, lam); a = w[0]
    print(f"fit on all with ridge {lam}: a {a:.3f}, b {w[1]:+.3f}; phase constants (engine log-odds for the side Trick Room favours): " +
          ', '.join(f'{p} {-w[2 + i] / a:+.3f}' for i, p in enumerate(PH)))
    nu = len(sd); wu, wa = w[7:7 + nu] / sd, w[7 + nu:7 + 2 * nu] / sd
    for name, ww in (('Trick Room up', w[7:7 + nu]), ('after it', w[7 + nu:7 + 2 * nu])):
        top = np.argsort(-np.abs(ww))[:8]
        print(f"  largest slopes, {name} (real log-odds per sd of the input, side 0's view): " + '; '.join(f'{NAMES[k]} {ww[k]:+.3f}' for k in top))
    if export:
        json.dump({'a': a, 'const': [w[2 + i] / a for i in range(5)], 'up': list(wu / a), 'after': list(wa / a), 'ridge': lam, 'names': NAMES,
                   'note': 'champ-battle-v41 TR_HEAD: added to the net log-odds (side 0 view): const[phase] x s + w . (f0 - f1, g0 - g1, x); phases TR 1-4 left, after'},
                  open(export, 'w'), indent=1)
        print('->', export)


def main_real(export, prefixes):
    """the self-play fit on real ladder decisions: a and b refit there, the correction as exported (no refit of its terms)"""
    E = json.load(open(export)); R = []
    for pre in prefixes:
        meta = json.load(open(pre + '.meta.json'))['turns']; vf = {r['name']: r for r in map(json.loads, open(pre + '_turns.vfeats.jsonl')) if 'f0' in r}
        for l in open(pre + '_turns.pos.jsonl'):
            p = json.loads(l); m = meta.get(p['name'].rsplit(' h', 1)[0]); x = vf.get(p['name'])
            if not m or m.get('won') is None or not x: continue
            st = p['state']; tr = st['field'].get('pseudoWeather', {}).get('trickroom')
            spe = [np.mean([q['storedStats']['spe'] for q in sd['pokemon'] if q.get('hp', 0) > 0 and not q.get('fainted')] or [0]) for sd in st['sides']]
            tru = [any(y['id'] == 'trickroom' and y['pp'] < y['maxpp'] for q in sd['pokemon'] for y in q.get('moveSlots', [])) for sd in st['sides']]
            ph, s = phase(int(tr.get('duration') or 0) if tr else 0, spe, tru); df, dg, xx = unit(x)
            R.append({'game': m['room'], 'z': x['static'], 'ph': ph, 's': s, 'u': np.concatenate([df, dg, xx]), 'y': 1.0 if m['won'] else 0.0})
    y = np.array([r['y'] for r in R]); z = np.array([math.log(min(max(r['z'], 1e-6), 1 - 1e-6) / (1 - min(max(r['z'], 1e-6), 1 - 1e-6))) for r in R])
    corr = np.array([(E['const'][PH.index(r['ph'])] * r['s'] + float(np.dot(E['after' if r['ph'] == 'after TR' else 'up'], r['u']))) if r['ph'] else 0.0 for r in R])
    for name, zz in (('the value alone', z), ('with the self-play correction', z + corr)):
        X = np.column_stack([zz, np.ones(len(R))]); w = fit(X, y, np.zeros(2), 0.0); l = ll(X, y, w)
        if name == 'the value alone': l0 = l
        print(f"  {len(R)} real decisions, {name}: log loss {l.mean():.4f} (a {w[0]:.3f})" + ('' if name == 'the value alone' else f"; change {'%+.4f ± %.4f' % se_by_game(R, l - l0)}"))
    for p in PH + [None]:
        idx = [i for i, r in enumerate(R) if r['ph'] == p and r['s']]
        if idx: print(f"    {str(p):10s} n {len(idx):5d}: mean correction for the favoured side {np.mean([corr[i] * R[i]['s'] for i in idx]):+.3f}")


def abstarts(pre, out, games=2):
    """the starts the fit left out (job % HOLD == 0), each `games` times on fresh luck, renumbered for champ battle"""
    import random
    rnd = random.Random(43); S = []
    for l in open(pre + '.jsonl'):
        st = json.loads(l)
        if st['job'] % HOLD: continue
        for g in range(games):
            S.append({**st, 'job': len(S), 'g': 0, 'rng': float(rnd.randrange(1, 2 ** 31)), 'meta': {**st.get('meta', {}), 'fit_job': st['job'], 'rep': g}})
    with open(out + '.jsonl', 'w') as f:
        for x in S: f.write(json.dumps(x) + '\n')
    json.dump([x['job'] for x in S], open(out + '.jobs.json', 'w'))
    print(len(S), 'starts:', dict(collections.Counter(x['kind'] for x in S)))


if __name__ == '__main__':
    if sys.argv[1] == 'fit': main_fit(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif sys.argv[1] == 'abstarts': abstarts(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 2)
    elif sys.argv[1] == 'real': main_real(sys.argv[2], sys.argv[3:])
