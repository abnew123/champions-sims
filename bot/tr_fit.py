"""Fit the Trick Room correction (2026-11-04, the user: "let's fit a correction for trick room turns left"). The audits of the Trick Room
six's ladder games found the engine overrating the bot while its Trick Room ran down: 7 to 11 points a decision unexplained with 1 to 3
turns left. On every rebuilt ladder decision (bot/decision_audit.py build, AUDIT_LIVE) with the engine's static value (champ feats, the
bot's environment: the learned value with its Perish and progress terms), a logistic fit of the game's result on
    a x (the static value's log-odds) + b + sum over k of c_k x [Trick Room up with k turns left] x (+1 if it favours the bot, -1 if the opponent:
    the slower side on average)
by maximum likelihood, standard errors clustered by game. The engine's correction (TR_CORR, champ-battle-v40) is then -c_k / a log-odds
from the side it favours: what the net's leaves should be charged so the bot's value is calibrated against real results. Fitted on the
training prefixes, then the log loss of the held-out ones with and without it.
  .venv/bin/python3 bot/tr_fit.py fit <train prefix> ... -- <test prefix> ...     (each with _turns.pos.jsonl, _turns.feats.jsonl, .meta.json)
  .venv/bin/python3 bot/tr_fit.py starts <out prefix> <prefix> ...                 (self-play starts, see starts())"""
import os, sys, json, math, collections
import numpy as np
K = 4   # turns-left buckets 1..4 (a value of 5 is read as 4: the turn Trick Room went up, before the end of turn counts it down)


def rows(prefix):
    meta = json.load(open(prefix + '.meta.json'))['turns']
    stat = {r['name']: r['static'] for r in map(json.loads, open(prefix + '_turns.feats.jsonl')) if 'static' in r}
    out = []
    for l in open(prefix + '_turns.pos.jsonl'):
        p = json.loads(l); name = p['name']; base = name.rsplit(' h', 1)[0]; m = meta.get(base)
        if not m or m.get('won') is None or name not in stat: continue
        v = min(max(stat[name], 1e-4), 1 - 1e-4)
        tr = p['state']['field'].get('pseudoWeather', {}).get('trickroom')
        d = min(max(int(tr.get('duration') or 0), 0), K) if tr else 0
        # the side Trick Room favours: the slower on average over its living Pokemon (the engine's tr_keep under TRSYM), not the setter
        # the state records (the position builder gives every Trick Room up at the root side 0 as its source)
        ms = [np.mean([q['storedStats']['spe'] for q in sd['pokemon'] if q.get('hp', 0) > 0 and not q.get('fainted')] or [0]) for sd in p['state']['sides']]
        own = 0 if not tr or ms[0] == ms[1] else (1 if ms[0] < ms[1] else -1)
        out.append({'game': m['room'], 'z': math.log(v / (1 - v)), 'd': d if own else 0, 'own': own, 'y': 1.0 if m['won'] else 0.0, 'team': m.get('team')})
    return out


def design(R, tr=True):
    X = [[r['z'], 1.0] + ([r['own'] * (r['d'] == k) for k in range(1, K + 1)] if tr else []) for r in R]
    return np.array(X, float), np.array([r['y'] for r in R]), [r['game'] for r in R]


def logit_fit(X, y, g, iters=50):
    w = np.zeros(X.shape[1]); w[0] = 0.7
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ w)); W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + 1e-6 * np.eye(len(w)); step = np.linalg.solve(H, X.T @ (y - p)); w += step
        if np.abs(step).max() < 1e-9: break
    p = 1 / (1 + np.exp(-X @ w)); H = X.T @ (X * (p * (1 - p))[:, None]); Hi = np.linalg.inv(H)
    S = collections.defaultdict(lambda: np.zeros(len(w)))
    for xi, yi, pi, gi in zip(X, y, p, g): S[gi] += xi * (yi - pi)
    B = sum(np.outer(s, s) for s in S.values())
    return w, np.sqrt(np.diag(Hi @ B @ Hi))


def loss(X, y, w):
    p = np.clip(1 / (1 + np.exp(-X @ w)), 1e-9, 1 - 1e-9); return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def main(train, test):
    R = [r for p in train for r in rows(p)]; T = [r for p in test for r in rows(p)]
    games = lambda Z: len({r['game'] for r in Z})
    print(f"train: {len(R)} decisions in {games(R)} games; test: {len(T)} in {games(T)}")
    for name, Z in (('train', R), ('test', T)):
        c = collections.Counter((r['own'], r['d']) for r in Z if r['own'])
        print(f"  {name} Trick Room decisions (side it favours, turns left): " + ', '.join(f"{'bot' if o == 1 else 'opp'} {d}: {n}" for (o, d), n in sorted(c.items())))
    X, y, g = design(R); w, se = logit_fit(X, y, g)
    print(f"fit: a {w[0]:.3f} ± {se[0]:.3f}, b {w[1]:+.3f} ± {se[1]:.3f}")
    corr = []
    for k in range(1, K + 1):
        c, s = w[1 + k], se[1 + k]; corr.append(-c / w[0])
        print(f"  {k} turn{'s' if k > 1 else ''} left: c {c:+.3f} ± {s:.3f} (real log-odds for the side it favours)  ->  TR_CORR {-c / w[0]:+.3f} ± {s / w[0]:.3f} (engine log-odds)")
    X0, y0, g0 = design(R, tr=False); w0, _ = logit_fit(X0, y0, g0)
    Xt, yt, _ = design(T); Xt0, _, _ = design(T, tr=False)
    print(f"held-out log loss: without the term {loss(Xt0, yt, w0):.4f}, with it {loss(Xt, yt, w):.4f}  (train: {loss(X0, y, w0):.4f} -> {loss(X, y, w):.4f})")
    ll = lambda X_, w_: -(yt * np.log(np.clip(1 / (1 + np.exp(-X_ @ w_)), 1e-9, 1)) + (1 - yt) * np.log(np.clip(1 - 1 / (1 + np.exp(-X_ @ w_)), 1e-9, 1)))
    dg = collections.defaultdict(float)
    for r, d in zip(T, ll(Xt, w) - ll(Xt0, w0)): dg[r['game']] += d
    dv = np.array(list(dg.values())); print(f"  the change per held-out decision {dv.sum() / len(T):+.4f} ± {dv.std(ddof=1) * math.sqrt(len(dv)) / len(T):.4f} (SE by game)")
    # the held-out decisions with the bot's Trick Room up: mean predicted win chance against the result, with and without the term
    for name, sel in (('bot Trick Room up', lambda r: r['own'] == 1), ('opponent Trick Room up', lambda r: r['own'] == -1), ('no Trick Room', lambda r: r['own'] == 0)):
        idx = [i for i, r in enumerate(T) if sel(r)]
        if not idx: continue
        p0 = 1 / (1 + np.exp(-Xt0[idx] @ w0)); p1 = 1 / (1 + np.exp(-Xt[idx] @ w))
        print(f"  held-out {name:24s} n {len(idx):4d}: won {yt[idx].mean():.3f}, predicted {p0.mean():.3f} without, {p1.mean():.3f} with")
    print('TR_CORR=' + ','.join(f'{max(c, 0.0):.2f}' for c in corr))


def starts(out, prefixes, n_bot=200, n_opp=80, n_t1=80):
    """self-play starts for TR_CORR against none (pssim/deep_endgames.sh, TR_CORR_SIDE=s0 / s1): per game, the first rebuilt decision with
    Trick Room just up (4 turns left), kind by the side it favours, n_bot of the bot's and n_opp of the opponent's; and n_t1 of the Trick
    Room six's games from their first decision (whether and when to set it); each drawn at random, one start a game"""
    import random
    by = {'bot Trick Room': {}, 'opponent Trick Room': {}, 'Trick Room six, turn 1': {}}
    for pre in prefixes:
        meta = json.load(open(pre + '.meta.json'))['turns']
        for l in open(pre + '_turns.pos.jsonl'):
            p = json.loads(l); tr = p['state']['field'].get('pseudoWeather', {}).get('trickroom')
            m = meta.get(p['name'].rsplit(' h', 1)[0])
            if not m: continue
            if m.get('turn') == 1 and m.get('team') == 'Trick Room six' and not tr: by['Trick Room six, turn 1'].setdefault(m['room'], (p, m))
            if not tr or int(tr.get('duration') or 0) < 4: continue
            ms = [np.mean([q['storedStats']['spe'] for q in sd['pokemon'] if q.get('hp', 0) > 0 and not q.get('fainted')] or [0]) for sd in p['state']['sides']]
            if ms[0] == ms[1]: continue
            k = 'bot Trick Room' if ms[0] < ms[1] else 'opponent Trick Room'
            by[k].setdefault(m['room'], (p, m))
    rnd = random.Random(41); S = []
    for k, n in (('bot Trick Room', n_bot), ('opponent Trick Room', n_opp), ('Trick Room six, turn 1', n_t1)):
        G = sorted(by[k]); rnd.shuffle(G)
        for room in G[:n]:
            p, m = by[k][room]
            S.append({'job': len(S), 'g': 0, 'rng': float(rnd.randrange(1, 2 ** 31)), 'kind': k, 'state': p['state'], 'meta': {'kind': k, 'name': p['name'], 'real_won': m.get('won')}})
    with open(out + '.jsonl', 'w') as f:
        for x in S: f.write(json.dumps(x) + '\n')
    json.dump([x['job'] for x in S], open(out + '.jobs.json', 'w'))
    print(len(S), 'starts:', {k: min(n, len(by[k])) for k, n in (('bot Trick Room', n_bot), ('opponent Trick Room', n_opp), ('Trick Room six, turn 1', n_t1))}, 'of', {k: len(v) for k, v in by.items()})


if __name__ == '__main__':
    a = sys.argv[2:]
    if sys.argv[1] == 'starts': starts(a[0], a[1:])
    else: i = a.index('--'); main(a[:i], a[i + 1:])
