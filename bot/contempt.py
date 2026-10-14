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
  live / livescore    the bot's live version: the staged one-turn search it runs now plus the matrix at each cell's precision
                      (EVAL_MATRIX=1), the plays hidden (as live), choosing; scored on the set's full matrices (luck sample B)
  hipick [nfit]      stronger players (bot/out/contempt/hi_pools.json): nfit fit positions from unused games with both players rated
                      1300-1449 and two scoring turns from each unused game with a 1450+ player (CONTEMPT_SET=hi)
  CONTEMPT_SET picks the files (<set>pos.jsonl ...); CONTEMPT_MODEL the human model score / livescore use; CONTEMPT_OPPMIN keeps only
  the decisions against players rated that or more
  .venv/bin/python3 bot/contempt.py pick 400 | eval 2 | score"""
# Results (2026-10-12 evening): pilot 300 games (lean low-rated): c 0.5 +1.02 ± 0.18 a decision for +0.54 against a perfect opponent.
# 999 games with both players rated 1300+ (median 1368; 1,975 decisions, refitted model): c 0.25 +0.46 ± 0.08 for ~0; c 0.5 +0.95 ± 0.11
# for +0.34; c 0.75 +1.15 ± 0.16 for +2.1; c 1.0 +0.62 ± 0.26 for +8.9 (full exploitation overshoots: the model is not that good).
# Opponents rated 1368+: c 0.5 +0.97 ± 0.16. Valued by the bot's own matrix (an upper estimate), luck independent between choice and score.
# The live version (the bot's staged search + EVAL_MATRIX=1, the plays hidden; scored on the full matrices): c 0.5 +0.88 ± 0.10 for 2.28
# against a perfect opponent where the bot's current mix pays 2.34 (no extra price); c 0.25 +0.51 for 1.82. On for the Bo3 bot at 0.5.
# Stronger players (the same evening): 186 unused games with a 1450+ player (CONTEMPT_SET=hi), live version, decisions against 1450+
# players (359): c 0.5 +0.97 ± 0.28 for 2.45 where c 0 pays 2.55; c 0.25 +0.73 ± 0.16 for 1.99; c 0.75 +1.27 ± 0.47 for 4.66. The 999-game
# set's 240 decisions against 1450+ players: c 0.5 +0.63 ± 0.26, c 0.25 +0.61 ± 0.16. So the gain holds at the top of the ladder.
# The model refitted on 733 games with both players 1300-1449 (bot/out/contempt/human_model_hi.json, lam 0.5, tau 0.16): log score per
# slot decision of 1450+ players -1.625 vs the deployed model's -1.627 (the planner's mix -2.033); c 0.5 +1.02 and +0.61 on the two sets.
# No better: the deployed model stays.
import os, sys, json, math, random, collections, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'pssim')); sys.path.insert(0, os.path.join(ROOT, 'bot')); sys.path.insert(0, os.path.join(ROOT, 'evalbar'))
OUT = os.path.join(ROOT, 'bot', 'out', 'contempt'); os.makedirs(OUT, exist_ok=True)
TAG = os.environ.get('CONTEMPT_SET', '')   # a further scoring set: CONTEMPT_SET=s2 -> s2pos.jsonl / s2eval.jsonl (the pilot is the default)
POS, EVAL = os.path.join(OUT, TAG + 'pos.jsonl'), os.path.join(OUT, TAG + 'eval.jsonl')
FITPOS, FITEVAL = os.path.join(OUT, TAG + 'fit_pos.jsonl'), os.path.join(OUT, TAG + 'fit_eval.jsonl')
MODEL_OUT = os.path.join(OUT, f'human_model{"_" + TAG if TAG else ""}.json')                 # what fit writes
MODEL = os.environ.get('CONTEMPT_MODEL') or os.path.join(OUT, 'human_model.json')           # what score / livescore use
OPPMIN = int(os.environ.get('CONTEMPT_OPPMIN', '0'))                                          # score only the decisions against players rated this or more
import live as LV; CAL = LV.CAL   # the Eval bar's rescale for the engine and net the bot runs (0.676; 0.7538 was v25's, until 2026-10-14)
CS = [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]

def ratings(game):
    """{'p1': rating, 'p2': rating} from the cached replay"""
    f = os.path.join(ROOT, 'pssim', 'replays_protect', game + '.log'); out = {}
    if os.path.exists(f):
        for l in open(f, errors='ignore'):
            if l.startswith('|player|'):
                p = l.rstrip('\n').split('|')
                if len(p) >= 6 and p[5].strip().isdigit(): out[p[2]] = int(p[5])
    return out
def known(a):
    return bool(a) and all(x is not None and x.get('choice') is not None and not x.get('unsure') for x in a)
def pick(n, seed=1):
    by_game = collections.defaultdict(list)
    with open(os.path.join(ROOT, 'pssim', 'results', 'value', 'real_new.pos.jsonl')) as f:
        for l in f:
            r = json.loads(l)
            if known(r.get('actual')) and known(r.get('their_actual')): by_game[r['name'].split(' ')[0]].append(l)
    minr = int(os.environ.get('CONTEMPT_MINRATING', '0'))   # both players rated at least this (closer to the bot's opponents)
    if minr:
        def rated(g):
            f = os.path.join(ROOT, 'pssim', 'replays_protect', g + '.log'); rs = []
            if os.path.exists(f):
                for l in open(f, errors='ignore'):
                    if l.startswith('|player|'):
                        p = l.rstrip('\n').split('|')
                        if len(p) >= 6 and p[5].strip().isdigit(): rs.append(int(p[5]))
            return len(rs) == 2 and min(rs) >= minr
        by_game = {g: v for g, v in by_game.items() if rated(g)}
    used = set()   # games already in another set (the pilot, the model fit, earlier scoring sets)
    for f in [os.path.join(OUT, x) for x in os.listdir(OUT) if x.endswith('pos.jsonl') and os.path.join(OUT, x) != POS]:
        used |= {json.loads(l)['name'].split(' ')[0] for l in open(f)}
    rnd = random.Random(seed); games = sorted(g for g in by_game if g not in used); rnd.shuffle(games)
    with open(POS, 'w') as o:
        for g in games[:n]:
            r = json.loads(rnd.choice(by_game[g]))
            for tag in ('A', 'B'): o.write(json.dumps({**r, 'name': f"{r['name']} s{tag}"}) + '\n')
    print(f'{min(n, len(games))} positions from {len(by_game)} games with both plays known -> {POS} (twice each)')

def run_evalpos(posf, outf, title, card, threads, matrix, extra=None):
    pssim = os.path.join(ROOT, 'pssim')
    n = sum(1 for _ in open(posf))
    d = os.path.join(ROOT, 'evalbar', 'out', 'battlesim'); os.makedirs(d, exist_ok=True)
    json.dump({'title': 'Battle sim: ' + title, 'out': os.path.relpath(outf, os.path.join(ROOT, 'evalbar', 'out')),
               'total': n, 'done0': sum(1 for _ in open(outf)) if os.path.exists(outf) else 0, 'started': time.time(), 'threads': threads,
               'seeds': 8 if matrix else 32, 'staged': not matrix}, open(os.path.join(d, card + '.run.json'), 'w'))
    env = {**os.environ, 'RACE_TIES': 'avg', 'EG_VALUE': 'egvalue9_sym2.json', 'RACE': '1', 'TRSYM': '1', 'RACE_PRIO': '1', 'FEATS22': '1',
           'CALC_DATA': '../native/champions_data_full.json', 'EG_VNET': os.path.join(ROOT, 'bot', 'value', 'vnet_h64_search_fc.json'),
           'GRID_DIR': os.path.join(pssim, 'results', 'value', 'emptygrid'), 'EG_MEGA_TIE': '0',
           **({'EVAL_MATRIX': 'full', 'EVAL_SEEDS': '8'} if matrix else {'EVAL_SEEDS': '32', 'EVAL_ADAPT': '1'}), **(extra or {})}
    import subprocess
    subprocess.run([os.path.join(ROOT, 'native', 'champ', 'bin', 'battlesim-champ-bot'), 'evalpos', '../native/engine_data_full.json', posf, outf, str(threads)],
                   cwd=pssim, env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def evaluate(threads=2): run_evalpos(POS, EVAL, f'contempt, full payoff matrices on human games{" (" + TAG + ")" if TAG else ""}', 'contempt' + TAG, threads, True)
LPOS, LEVAL = os.path.join(OUT, TAG + 'live_pos.jsonl'), os.path.join(OUT, TAG + 'live_eval.jsonl')
def live(threads=2):
    with open(LPOS, 'w') as o:
        for l in open(POS):
            r = json.loads(l)
            if r['name'].endswith(' sA'):
                r['name'] = r['name'][:-3] + ' sL'; r['actual'] = [None, None]; r['their_actual'] = [None, None]; o.write(json.dumps(r) + '\n')
    run_evalpos(LPOS, LEVAL, f'contempt, the live version on human games{" (" + TAG + ")" if TAG else ""}', 'contempt_live' + TAG, threads, False, {'EVAL_MATRIX': '1'})
def livescore():
    import numpy as np
    from scipy.optimize import linprog
    import exploit_test as XT, human_lines as HL
    M = json.load(open(MODEL if os.path.exists(MODEL) else XT.MODEL)); print('human model:', MODEL if os.path.exists(MODEL) else XT.MODEL)
    real = np.vectorize(lambda v: HL.resc(v, CAL))
    def solve(A, q=None, c=0.0):
        n, k = A.shape; obj = np.r_[np.zeros(n), -1.0] if q is None else np.r_[-c * (A @ q), -(1 - c)]
        res = linprog(obj, A_ub=np.c_[-A.T, np.ones(k)], b_ub=np.zeros(k), A_eq=np.r_[np.ones(n), 0.0][None], b_eq=[1.0], bounds=[(0, None)] * n + [(None, None)], method='highs')
        return res.x[:n], (-res.fun if q is None else None)
    L = {r['name'].rsplit(' s', 1)[0]: r for r in map(json.loads, open(LEVAL)) if 'error' not in r and 'matrix' in r}
    B = {r['name'].rsplit(' s', 1)[0]: r for r in map(json.loads, open(EVAL)) if 'error' not in r and 'matrix' in r and r['name'].endswith(' sB')}
    res = collections.defaultdict(list); games = []; opp_rating = []; nan_cells = 0; skipped = collections.Counter()
    for base, l in L.items():
        b = B.get(base)
        if not b: skipped['no full matrix'] += 1; continue
        if l['matrix']['rows'] != b['matrix']['rows'] or l['matrix']['cols'] != b['matrix']['cols']: skipped['option lists differ'] += 1; continue
        A0 = np.array([[np.nan if x is None else x for x in row] for row in l['matrix']['v1']], float); B0 = np.array(b['matrix']['v1'], float)
        if np.isnan(A0).any():   # a cell never sampled: its row's mean
            nan_cells += int(np.isnan(A0).sum()); rm = np.nanmean(A0, axis=1); A0 = np.where(np.isnan(A0), rm[:, None], A0)
        for us in (0, 1):
            them = 1 - us
            A = real(A0) if us == 0 else 1 - real(A0).T; Bm = real(B0) if us == 0 else 1 - real(B0).T
            cols = b['matrix']['cols'] if us == 0 else b['matrix']['rows']
            played = [next((o for o in sl['options'] if o.get('actual')), None) for sl in b['sides'][them]['slots']]
            if any(p is None for p in played): skipped['play not found'] += 1; continue
            want = [p['c'] for p in played]
            act = next((j for j, c in enumerate(cols) if all(x == y for x, y in zip(c, want))), None)
            if act is None: skipped['play not found'] += 1; continue
            slots = l['sides'][them]['slots']
            sp = [{json.dumps(o['c']): p for o, p in zip(sl['options'], XT.probs([(o['label'], o['w'], o['v']) for o in sl['options']], M))} for sl in slots]
            q = np.array([math.prod(sp[i].get(json.dumps(c[i]), 1e-6) for i in range(len(c))) for c in cols]); q /= q.sum()
            x_live = np.array(l['matrix']['x'] if us == 0 else l['matrix']['y'], float); x_live /= x_live.sum()   # the mix the bot plays now
            vB = solve(Bm)[1]; base_v = x_live @ Bm[:, act]
            res['c=0 (no contempt): price vs a perfect opponent'].append(vB - (x_live @ Bm).min())
            for c in (0.25, 0.5, 0.75):
                x = solve(A, q, c)[0]
                res[f'c={c:.2f} gain vs the actual play'].append(x @ Bm[:, act] - base_v)
                res[f'c={c:.2f} price vs a perfect opponent'].append(vB - (x @ Bm).min())
            games.append(base.split(' ')[0])
            pv = base.split(' ')[-1]; opp_rating.append(ratings(games[-1]).get([pv, 'p2' if pv == 'p1' else 'p1'][them], -1))
    print(f"{len(games)} decisions ({len(set(games))} games); never-sampled cells filled: {nan_cells}; skipped: {dict(skipped)}")
    G = np.array(games); OR = np.array(opp_rating)
    def show(mask, label):
        print(label)
        for k, xs in res.items():
            xs = np.array(xs)[mask]; g = G[mask]
            if not len(xs): continue
            se = math.sqrt(sum(((xs[g == x] - xs.mean()).sum()) ** 2 for x in set(g))) / len(xs)
            print(f"  {k:52s} {100 * xs.mean():+7.2f}  ± {100 * se:.2f}")
    show(OR >= OPPMIN if OPPMIN else np.ones(len(G), bool), f'opponent rated {OPPMIN}+ ({int((OR >= OPPMIN).sum())} decisions)' if OPPMIN else 'all')
def hipick(nfit=3000, per_game=2, seed=7):
    """from bot/out/contempt/hi_pools.json: CONTEMPT_SET's fit positions (any turn of the fit games, nfit of them) and its scoring
    positions (per_game turns with both plays known from each eval game, each twice for luck samples A and B)"""
    P = json.load(open(os.path.join(OUT, 'hi_pools.json'))); fit_g, ev_g = set(P['fit']), set(P['eval'])
    fitrows, evrows = [], collections.defaultdict(list)
    for part in ('fit', 'hold', 'new'):
        for l in open(os.path.join(ROOT, 'pssim', 'results', 'value', f'real_{part}.pos.jsonl')):
            g = l[l.index('"name": "') + 9:].split(' ')[0] if '"name": "' in l else json.loads(l)['name'].split(' ')[0]
            if g in fit_g: fitrows.append(l)
            elif g in ev_g:
                r = json.loads(l)
                if known(r.get('actual')) and known(r.get('their_actual')): evrows[g].append(r)
    rnd = random.Random(seed); rnd.shuffle(fitrows)
    with open(FITPOS, 'w') as o:
        for l in fitrows[:nfit]: o.write(l if l.endswith('\n') else l + '\n')
    n = 0
    with open(POS, 'w') as o:
        for g in sorted(evrows):
            for r in rnd.sample(evrows[g], min(per_game, len(evrows[g]))):
                for tag in ('A', 'B'): o.write(json.dumps({**r, 'name': f"{r['name']} s{tag}"}) + '\n')
                n += 1
    print(f'{min(nfit, len(fitrows))} fit positions -> {FITPOS}; {n} scoring positions from {len(evrows)} games -> {POS}')
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
    json.dump(best, open(MODEL_OUT, 'w')); print('->', MODEL_OUT)

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
    res = collections.defaultdict(list); games = []; opp_rating = []
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
            rt = ratings(base.split(' ')[0]); pv = base.split(' ')[-1]          # the position's view (p1 / p2) is side 0
            sides = [pv, 'p2' if pv == 'p1' else 'p1']; opp_rating.append(rt.get(sides[them]))
            if OPPMIN and (opp_rating[-1] or 0) < OPPMIN:                         # (the rows just added are dropped below)
                for k in list(res): res[k].pop()
                games.pop(); opp_rating.pop(); continue
    n = len(res['ceiling: best answer to the actual play'])
    print(f"{n} decisions ({len(set(games))} games), real win chance points per decision; ± one standard error, clustered by game")
    G = np.array(games); OR = np.array([r if r is not None else -1 for r in opp_rating])
    def show(mask, label):
        print(label)
        for k, xs in res.items():
            xs = np.array(xs)[mask]; g = G[mask]
            if not len(xs): continue
            se = math.sqrt(sum(((xs[g == x] - xs.mean()).sum()) ** 2 for x in set(g))) / len(xs)
            print(f"  {k:46s} {100 * xs.mean():+7.2f}  ± {100 * se:.2f}")
    show(np.ones(len(G), bool), 'all')
    known_r = OR[OR > 0]
    if len(known_r) > 20:
        cut = float(np.median(known_r))
        show((OR > 0) & (OR < cut), f'opponent rated under {cut:.0f} ({int(((OR > 0) & (OR < cut)).sum())} decisions)')
        show(OR >= cut, f'opponent rated {cut:.0f} or more ({int((OR >= cut).sum())} decisions)')

if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'pick': pick(int(a[1]), int(a[2]) if len(a) > 2 else 1)
    elif a[0] == 'eval': evaluate(int(a[1]) if len(a) > 1 else 2)
    elif a[0] == 'score': score()
    elif a[0] == 'fitpick': fitpick(int(a[1]), int(a[2]) if len(a) > 2 else 2)
    elif a[0] == 'fiteval': fiteval(int(a[1]) if len(a) > 1 else 2)
    elif a[0] == 'fit': fit()
    elif a[0] == 'live': live(int(a[1]) if len(a) > 1 else 2)
    elif a[0] == 'hipick': hipick(int(a[1]) if len(a) > 1 else 3000)
    elif a[0] == 'livescore': livescore()
