"""Plan against the top three guesses at the opponent's unseen back row instead of the single most likely one? (2026-10-12 evening, the
user: work towards a trustworthy best move.) For every decision in the bot's saved games where the opponent still had unseen Pokemon and
the game later showed all four it brought, the position is built with each of the top three back-row hypotheses (botpos) and with the
truth, and solved with the bot's current settings. The bot's mix now is the top hypothesis's; the alternative is the hypotheses' mixes
weighted by their odds. Both are valued in the true position (each joint option's value against the opponent's equilibrium there),
against the mix planned on the truth: the loss of each, per decision, all decisions counted (a right first guess too, where mixing can
cost).
  .venv/bin/python3 bot/back3_test.py build | eval [threads] | evaltruth [threads] | score
  meval [threads] | bayes: one game over the guesses (the opponent knowing its back row) instead of mixing the guesses' mixes"""
import os, sys, json, collections, time, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'evalbar')); sys.path.insert(0, os.path.join(ROOT, 'bot'))
os.environ.setdefault('CHAMP_MAIN', ROOT)
OUT = os.path.join(ROOT, 'bot', 'out', 'back3'); os.makedirs(OUT, exist_ok=True)
POS, EVAL, META = os.path.join(OUT, 'pos.jsonl'), os.path.join(OUT, 'eval.jsonl'), os.path.join(OUT, 'meta.json')
TPOS, TEVAL = os.path.join(OUT, 'truth_pos.jsonl'), os.path.join(OUT, 'truth_eval.jsonl')   # the true positions again, every joint option reported
MPOS, MEVAL = os.path.join(OUT, 'hyp_pos.jsonl'), os.path.join(OUT, 'hyp_meval.jsonl')     # the hypotheses again, with the bot's matrix (EVAL_MATRIX=1)
K = 3
def build():
    import replay as R; R.BATON_PASS = True
    import belief_test as BT, botpos as BP, live as LV, position as POS_
    specs_all = []; meta = []; tally = collections.Counter(); fin_cache = {}
    for g, team, log, req, turn in BT.decisions():
        op = 'p2' if g['side'] == 'p1' else 'p1'
        if g['room'] not in fin_cache: fin_cache[g['room']] = R.parse(open(os.path.join(ROOT, 'bot', 'out', g['room'] + '.log'), errors='ignore').read())['final']
        brought = [m['sp'] for m in fin_cache[g['room']][op]['mons'] if m.get('seen', True)]
        try: specs, info = BP.bot_position(log, req, g['side'], topk=20, team=POS_.export(team['sets']), tag='b3')
        except Exception: continue
        if not specs or not info.get('need'): continue
        H = info['hyp']; seen_now = {m['sp'] for m in R.parse(log)['steps'][-1]['state'][op]['mons']}
        if len(brought) < 4: tally['back row never fully shown'] += 1; continue
        true_back = sorted(sp for sp in brought if sp not in seen_now)
        if len(true_back) != info['need']: tally['inconsistent'] += 1; continue
        k = next((i for i, (w, c) in enumerate(H) if sorted(c) == true_back), None)
        if k is None: tally['true back row not among the candidates'] += 1; continue
        name = f"{g['room'][-14:]} t{turn}"; top = H[:K]; tw = sum(w for w, _ in top)
        for h in range(len(top)):
            sp = json.loads(json.dumps(specs[h])); sp[1]['name'] = f'{name} h{h}'; specs_all.append((1.0, sp[1]))
        sp = json.loads(json.dumps(specs[k])); sp[1]['name'] = f'{name} truth'; specs_all.append((1.0, sp[1]))
        meta.append({'name': name, 'weights': [w / tw for w, _ in top], 'truth_rank': k, 'room': g['room'], 'turn': turn})
        tally['scored'] += 1; tally[f'truth is hypothesis {k + 1}' if k < K else 'truth beyond the top three'] += 1
    if os.path.exists(POS): os.remove(POS)
    LV.positions(specs_all, POS); json.dump(meta, open(META, 'w'))
    print(dict(tally)); print(f'{len(meta)} decisions, {len(specs_all)} positions -> {POS}')
def evaluate(threads=2):
    import contempt as C
    C.run_evalpos(POS, EVAL, 'back row: top three guesses vs one, bot decisions', 'back3', threads, False)
def evaltruth(threads=2):
    """the true positions with every joint option's value (EVAL_TOP: the default reports the top 8 only, too few to value the
    hypotheses' mixes in the true position)"""
    import contempt as C
    with open(TPOS, 'w') as o:
        for l in open(POS):
            if json.loads(l)['name'].endswith(' truth p1'): o.write(l)
    C.run_evalpos(TPOS, TEVAL, 'back row: the true positions, every option', 'back3_truth', threads, False, {'EVAL_TOP': '2000'})
def meval(threads=2):
    """the hypotheses' positions with the payoff matrix the live bot builds under contempt (the staged search, then EVAL_MATRIX=1)"""
    import contempt as C
    with open(MPOS, 'w') as o:
        for l in open(POS):
            if not json.loads(l)['name'].endswith(' truth p1'): o.write(l)
    C.run_evalpos(MPOS, MEVAL, 'back row: one game over the top three guesses (matrices)', 'back3m', threads, False, {'EVAL_MATRIX': '1'})
def bayes():
    """One game over the back-row guesses: the opponent knows its back row, we only know the odds. Our mix x (over the joint options
    every guess's matrix has) maximises sum_h p_h min_j (x.A_h)_j, each guess's columns its own (an LP). Against the top guess's
    equilibrium on its matrix and the mixes-weighted version; all valued in the true position as in score (planner points)."""
    import numpy as np
    from scipy.optimize import linprog
    meta = json.load(open(META)); E = {r['name']: r for r in map(json.loads, open(MEVAL)) if 'error' not in r and 'matrix' in r}
    T = {r['name']: r for r in map(json.loads, open(TEVAL)) if 'error' not in r}
    def lp(As, ps):
        n = As[0].shape[0]; H = len(As)
        A_ub = np.vstack([np.c_[-A.T, np.eye(H)[[h] * A.shape[1]]] for h, A in enumerate(As)])
        res = linprog(np.r_[np.zeros(n), -np.array(ps)], A_ub=A_ub, b_ub=np.zeros(len(A_ub)), A_eq=np.r_[np.ones(n), np.zeros(H)][None], b_eq=[1.0],
                      bounds=[(0, None)] * n + [(None, None)] * H, method='highs')
        return res.x[:n]
    out = collections.defaultdict(list); G = []; skipped = collections.Counter()
    for m in meta:
        hs = [E.get(f"{m['name']} h{h} p1") for h in range(len(m['weights']))]; tr = T.get(f"{m['name']} truth p1")
        if tr is None or any(h is None for h in hs): skipped['missing'] += 1; continue
        vt = {j['label']: j['v'] for j in tr['sides'][0]['joint']}
        mats = []
        for r in hs:
            A = np.array([[np.nan if x is None else x for x in row] for row in r['matrix']['v1']], float)
            if np.isnan(A).any(): A = np.where(np.isnan(A), np.nanmean(A, axis=1)[:, None], A)
            mats.append((r['matrix']['rl'], A, np.array(r['matrix']['x'], float)))
        rows = [l for l in mats[0][0] if all(l in set(rl) for rl, _, _ in mats[1:])]
        if not rows: skipped['no shared rows'] += 1; continue
        As = [A[[rl.index(l) for l in rows]] for rl, A, _ in mats]
        def val(x):
            if any(l not in vt for l, w in x.items() if w > 1e-6): return None
            return sum(w * vt[l] for l, w in x.items() if w > 1e-6) / sum(x.values())
        x1 = dict(zip(mats[0][0], mats[0][2]))                                   # the top guess's equilibrium (the bot's mix now)
        x3 = collections.Counter()
        for w, (rl, _, x) in zip(m['weights'], mats):
            for l, p in zip(rl, x): x3[l] += w * p
        xb = dict(zip(rows, lp(As, m['weights'])))
        xt = {j['label']: j['w'] for j in tr['sides'][0]['joint'] if j['w'] > 1e-4}
        v1, v3, vb, vtt = val(x1), val(dict(x3)), val(xb), val(xt)
        if None in (v1, v3, vb, vtt): skipped['an option missing in the true position'] += 1; continue
        out['top guess (matrix equilibrium)'].append(vtt - v1); out['mixes weighted'].append(vtt - v3); out['one game over the guesses'].append(vtt - vb)
        out['one game minus top guess (gain)'].append(vb - v1)
        out['  first guess right' if m['truth_rank'] == 0 else '  first guess wrong'].append(vb - v1)
        G.append(m['room'])
    print(f"{len(G)} decisions ({len(set(G))} games); skipped {dict(skipped)}; planner points per decision below the mix planned on the truth "
          "(± clustered by game)")
    Ga = np.array(G)
    for k, xs in out.items():
        xs = np.array(xs); g = Ga if len(xs) == len(Ga) else None
        se = (math.sqrt(sum(((xs[g == x] - xs.mean()).sum()) ** 2 for x in set(G))) / len(xs)) if g is not None else xs.std(ddof=1) / len(xs) ** 0.5
        print(f"  {k:36s} {100 * xs.mean():+6.2f}  ± {100 * se:.2f}  (n {len(xs)})")
def score():
    meta = json.load(open(META)); E = {r['name']: r for r in map(json.loads, open(EVAL)) if 'error' not in r}
    if os.path.exists(TEVAL): E.update({r['name']: r for r in map(json.loads, open(TEVAL)) if 'error' not in r})
    out = collections.defaultdict(list); G = []
    for m in meta:
        hs = [E.get(f"{m['name']} h{h} p1") for h in range(len(m['weights']))]; tr = E.get(f"{m['name']} truth p1")
        if tr is None or any(h is None for h in hs): continue
        vt = {j['label']: j['v'] for j in tr['sides'][0]['joint']}
        mix = lambda r: {j['label']: j['w'] for j in r['sides'][0]['joint'] if j['w'] > 1e-4}
        def val(x):
            tot = sum(x.values());
            if any(l not in vt for l in x): return None
            return sum(w * vt[l] for l, w in x.items()) / tot
        x1 = mix(hs[0]); x3 = collections.Counter()
        for w, r in zip(m['weights'], hs):
            for l, p in mix(r).items(): x3[l] += w * p
        xt = mix(tr); v1, v3, vt_ = val(x1), val(dict(x3)), val(xt)
        if None in (v1, v3, vt_): continue
        out['top guess'].append(vt_ - v1); out['top three, weighted'].append(vt_ - v3)
        out['top three minus top guess (gain)'].append(v3 - v1); G.append(m['room'])
        out['first guess right' if m['truth_rank'] == 0 else 'first guess wrong'].append(v3 - v1)
    print(f"{len(G)} decisions, planner points per decision (the mix's value in the true position, below the mix planned on the truth)")
    for k, xs in out.items():
        n = len(xs); mu = sum(xs) / n; sd = (sum((x - mu) ** 2 for x in xs) / max(1, n - 1)) ** 0.5
        print(f"  {k:36s} {100 * mu:+6.2f}  ± {100 * sd / n ** 0.5:.2f}  (n {n})")
if __name__ == '__main__':
    a = sys.argv[1:]
    {'build': build, 'eval': lambda: evaluate(int(a[1]) if len(a) > 1 else 2), 'evaltruth': lambda: evaltruth(int(a[1]) if len(a) > 1 else 2), 'score': score,
     'meval': lambda: meval(int(a[1]) if len(a) > 1 else 2), 'bayes': bayes}[a[0]]()
