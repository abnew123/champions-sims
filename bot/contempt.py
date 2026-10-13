"""A contempt dial for the bot (2026-10-12 evening, the user: "a 'contempt' setting like chess engines have, where the bot would deviate
from its view of the optimal play to go for the exploitative play"), measured offline on human-vs-human ladder games.

The dial is a restricted Nash response: with contempt c the bot assumes the opponent plays as the human model predicts with probability
c and as a perfect adversary otherwise, and plays the mix that is best against that: max_x [c x.A.q + (1 - c) min_j x.A_j] (an LP).
c = 0 is the equilibrium the bot plays now; c = 1 the best answer to the model. A position's payoff matrix is evaluated twice on
independent luck samples: the first chooses each c's mix, the second scores it, so the noise that makes an option look best does not
also make it score well.

  pick  <n> [seed]   n positions from the week's replays (pssim/results/value/real_new: games the human model was not fitted on),
                     one per game, both players' plays fully known; each written twice (luck samples A and B)
  eval  [threads]    champ evalpos with the bot's settings, every cell of the payoff matrix (EVAL_MATRIX=full, 8 seeds a cell)
  score              per decision and per c: the gain over the equilibrium against what the opponent actually did, and the price
                     against a perfect opponent (exploitability); both sides of each position are scored, in real win chance (x CAL)
  fitpick <n> [seed]  n positions for refitting the human model on the bot's current values (the learned net), from other games
  fiteval [threads]   the staged one-turn search on them (the bot's settings, no matrix)
  fit                 the model refitted (fit on half the games, scored on the other half) -> bot/out/contempt/human_model.json, which
                      score uses from then on (the first model, bot/out/pos/human_model.json, was fitted on the static value's options)
  .venv/bin/python3 bot/contempt.py pick 400 | eval 2 | score"""
import os, sys, json, math, random, collections, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'pssim')); sys.path.insert(0, os.path.join(ROOT, 'bot')); sys.path.insert(0, os.path.join(ROOT, 'evalbar'))
OUT = os.path.join(ROOT, 'bot', 'out', 'contempt'); os.makedirs(OUT, exist_ok=True)
POS, EVAL = os.path.join(OUT, 'pos.jsonl'), os.path.join(OUT, 'eval.jsonl')
FITPOS, FITEVAL, MODEL = os.path.join(OUT, 'fit_pos.jsonl'), os.path.join(OUT, 'fit_eval.jsonl'), os.path.join(OUT, 'human_model.json')
CAL = 0.7538
CS = [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]

def known(a):
    return bool(a) and all(x is not None and x.get('choice') is not None and not x.get('unsure') for x in a)
def pick(n, seed=1):
    by_game = collections.defaultdict(list)
    with open(os.path.join(ROOT, 'pssim', 'results', 'value', 'real_new.pos.jsonl')) as f:
        for l in f:
            r = json.loads(l)
            if known(r.get('actual')) and known(r.get('their_actual')): by_game[r['name'].split(' ')[0]].append(l)
    rnd = random.Random(seed); games = sorted(by_game); rnd.shuffle(games)
    with open(POS, 'w') as o:
        for g in games[:n]:
            r = json.loads(rnd.choice(by_game[g]))
            for tag in ('A', 'B'): o.write(json.dumps({**r, 'name': f"{r['name']} s{tag}"}) + '\n')
    print(f'{min(n, len(games))} positions from {len(by_game)} games with both plays known -> {POS} (twice each)')

def run_evalpos(posf, outf, title, card, threads, matrix):
    pssim = os.path.join(ROOT, 'pssim')
    n = sum(1 for _ in open(posf))
    d = os.path.join(ROOT, 'evalbar', 'out', 'battlesim'); os.makedirs(d, exist_ok=True)
    json.dump({'title': 'Battle sim: ' + title, 'out': os.path.relpath(outf, os.path.join(ROOT, 'evalbar', 'out')),
               'total': n, 'done0': sum(1 for _ in open(outf)) if os.path.exists(outf) else 0, 'started': time.time(), 'threads': threads,
               'seeds': 8 if matrix else 32, 'staged': not matrix}, open(os.path.join(d, card + '.run.json'), 'w'))
    env = {**os.environ, 'RACE_TIES': 'avg', 'EG_VALUE': 'egvalue9_sym2.json', 'RACE': '1', 'TRSYM': '1', 'RACE_PRIO': '1', 'FEATS22': '1',
           'CALC_DATA': '../native/champions_data_full.json', 'EG_VNET': os.path.join(ROOT, 'bot', 'value', 'vnet_h64_search_fc.json'),
           'GRID_DIR': os.path.join(pssim, 'results', 'value', 'emptygrid'), 'EG_MEGA_TIE': '0',
           **({'EVAL_MATRIX': 'full', 'EVAL_SEEDS': '8'} if matrix else {'EVAL_SEEDS': '32', 'EVAL_ADAPT': '1'})}
    import subprocess
    subprocess.run([os.path.join(ROOT, 'native', 'champ', 'bin', 'battlesim-champ-bot'), 'evalpos', '../native/engine_data_full.json', posf, outf, str(threads)],
                   cwd=pssim, env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def evaluate(threads=2): run_evalpos(POS, EVAL, 'contempt, full payoff matrices on human games', 'contempt', threads, True)
def fitpick(n, seed=2):
    taken = {json.loads(l)['name'].split(' ')[0] for l in open(POS)} if os.path.exists(POS) else set()
    by_game = collections.defaultdict(list)
    with open(os.path.join(ROOT, 'pssim', 'results', 'value', 'real_new.pos.jsonl')) as f:
        for l in f:
            g = json.loads(l)['name'].split(' ')[0]
            if g not in taken: by_game[g].append(l)
    rnd = random.Random(seed); games = sorted(by_game); rnd.shuffle(games)
    with open(FITPOS, 'w') as o:
        for g in games[:n]: o.write(rnd.choice(by_game[g]))
    print(f'{min(n, len(games))} positions for the model fit, none from the {len(taken)} scoring games -> {FITPOS}')
def fiteval(threads=2): run_evalpos(FITPOS, FITEVAL, 'contempt, human model refit (one-turn search on human games)', 'contempt_fit', threads, False)
def fit():
    import exploit_test as XT, human_lines as HL
    rows = [json.loads(l) for l in open(FITEVAL) if 'error' not in l]
    by = collections.defaultdict(list)
    for r in rows: by[r['name'].split(' ')[0]].append(r)
    games = sorted(by); random.Random(3).shuffle(games); half = set(games[:len(games) // 2])
    A = list(XT.slot_rows([r for g in games if g in half for r in by[g]])); B = list(XT.slot_rows([r for g in games if g not in half for r in by[g]]))
    hum = collections.Counter(); plan = collections.Counter()
    for opts, k in A:
        hum[HL.kind(opts[k][0])[0]] += 1
        for l, w, v in opts: plan[HL.kind(l)[0]] += w
    fac = {kd: (hum[kd] + 1) / (plan[kd] + 1) for kd in set(hum) | set(plan)}
    ll = lambda M, part: sum(math.log(max(1e-9, XT.probs(opts, M)[k])) for opts, k in part) / len(part)
    best = max(({'lam': lam, 'tau': tau, 'fac': fac} for lam in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8) for tau in (0.01, 0.02, 0.04, 0.08, 0.16, 0.3, 0.5, 1.0)),
               key=lambda M: ll(M, A))
    old = json.load(open(XT.MODEL))
    print(f"{len(A) + len(B)} human slot decisions from {len(games)} games (fit on half the games, scored on the other half; log score, higher is better):")
    print(f"  planner's mix (2% floor) {ll({'lam': 0.02, 'tau': 10.0, 'fac': {}}, B):.3f};  the first model {ll(old, B):.3f};  refitted {ll(best, B):.3f} (lam {best['lam']}, tau {best['tau']})")
    json.dump(best, open(MODEL, 'w'))

def score():
    import numpy as np
    from scipy.optimize import linprog
    import exploit_test as XT, human_lines as HL
    M = json.load(open(MODEL if os.path.exists(MODEL) else XT.MODEL)); print('human model:', MODEL if os.path.exists(MODEL) else XT.MODEL)
    real = np.vectorize(lambda v: HL.resc(v, CAL))
    def nash(A):
        n, k = A.shape
        res = linprog(np.r_[np.zeros(n), -1.0], A_ub=np.c_[-A.T, np.ones(k)], b_ub=np.zeros(k), A_eq=np.r_[np.ones(n), 0.0][None], b_eq=[1.0],
                      bounds=[(0, None)] * n + [(None, None)], method='highs')
        return res.x[:n], -res.fun
    def rnr(A, q, c):
        """max_x c x.A.q + (1 - c) t, t <= x.A_j for every column j"""
        n, k = A.shape
        res = linprog(np.r_[-c * (A @ q), -(1 - c)], A_ub=np.c_[-A.T, np.ones(k)], b_ub=np.zeros(k), A_eq=np.r_[np.ones(n), 0.0][None], b_eq=[1.0],
                      bounds=[(0, None)] * n + [(None, None)], method='highs')
        return res.x[:n]
    rows = collections.defaultdict(dict)
    for r in map(json.loads, open(EVAL)):
        if 'error' in r or 'matrix' not in r: continue
        base, tag = r['name'].rsplit(' s', 1); rows[base][tag] = r
    res = collections.defaultdict(list); games = []
    for base, d in rows.items():
        if 'A' not in d or 'B' not in d: continue
        a_, b_ = d['A'], d['B']
        if a_['matrix']['rows'] != b_['matrix']['rows'] or a_['matrix']['cols'] != b_['matrix']['cols']: continue
        A0, B0 = np.array(a_['matrix']['v1'], float), np.array(b_['matrix']['v1'], float)
        if np.isnan(A0).any() or np.isnan(B0).any(): continue
        for us in (0, 1):
            them = 1 - us
            A = real(A0) if us == 0 else 1 - real(A0).T; B = real(B0) if us == 0 else 1 - real(B0).T
            cols = a_['matrix']['cols'] if us == 0 else a_['matrix']['rows']
            slots = a_['sides'][them]['slots']
            played = [next((o for o in sl['options'] if o.get('actual')), None) for sl in slots]
            if any(p is None for p in played): continue
            want = [p['c'] for p in played]
            act = next((j for j, c in enumerate(cols) if all(x == y for x, y in zip(c, want))), None)
            if act is None: continue
            # the model's prediction of each opposing slot, then of each column (slots taken as independent)
            sp = [{json.dumps(o['c']): p for o, p in zip(sl['options'], XT.probs([(o['label'], o['w'], o['v']) for o in sl['options']], M))} for sl in slots]
            q = np.array([math.prod(sp[i].get(json.dumps(c[i]), 1e-6) for i in range(len(c))) for c in cols]); q /= q.sum()
            x0, _ = nash(A); vB = nash(B)[1]
            base_v = x0 @ B[:, act]
            res['model probability of the actual column'].append(q[act])
            res['ceiling: best answer to the actual play'].append(B[:, act].max() - base_v)
            for c in CS:
                x = x0 if c == 0 else rnr(A, q, c)
                res[f'c={c:.2f} gain vs the actual play'].append(x @ B[:, act] - base_v)
                res[f'c={c:.2f} price vs a perfect opponent'].append(vB - (x @ B).min())
            games.append(base.split(' ')[0])
    n = len(res['ceiling: best answer to the actual play'])
    print(f"{n} decisions ({len(set(games))} games), real win chance points per decision; ± one standard error, clustered by game")
    G = np.array(games)
    for k, xs in res.items():
        xs = np.array(xs)
        se = math.sqrt(sum(((xs[G == g] - xs.mean()).sum()) ** 2 for g in set(games))) / len(xs)
        print(f"  {k:46s} {100 * xs.mean():+7.2f}  ± {100 * se:.2f}")

if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'pick': pick(int(a[1]), int(a[2]) if len(a) > 2 else 1)
    elif a[0] == 'eval': evaluate(int(a[1]) if len(a) > 1 else 2)
    elif a[0] == 'score': score()
    elif a[0] == 'fitpick': fitpick(int(a[1]), int(a[2]) if len(a) > 2 else 2)
    elif a[0] == 'fiteval': fiteval(int(a[1]) if len(a) > 1 else 2)
    elif a[0] == 'fit': fit()
