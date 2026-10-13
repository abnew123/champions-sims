"""Plan against the top three guesses at the opponent's unseen back row instead of the single most likely one? (2026-10-12 evening, the
user: work towards a trustworthy best move.) For every decision in the bot's saved games where the opponent still had unseen Pokemon and
the game later showed all four it brought, the position is built with each of the top three back-row hypotheses (botpos) and with the
truth, and solved with the bot's current settings. The bot's mix now is the top hypothesis's; the alternative is the hypotheses' mixes
weighted by their odds. Both are valued in the true position (each joint option's value against the opponent's equilibrium there),
against the mix planned on the truth: the loss of each, per decision, all decisions counted (a right first guess too, where mixing can
cost).
  .venv/bin/python3 bot/back3_test.py build | eval [threads] | score"""
import os, sys, json, collections, time, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'evalbar')); sys.path.insert(0, os.path.join(ROOT, 'bot'))
os.environ.setdefault('CHAMP_MAIN', ROOT)
OUT = os.path.join(ROOT, 'bot', 'out', 'back3'); os.makedirs(OUT, exist_ok=True)
POS, EVAL, META = os.path.join(OUT, 'pos.jsonl'), os.path.join(OUT, 'eval.jsonl'), os.path.join(OUT, 'meta.json')
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
def score():
    meta = json.load(open(META)); E = {r['name']: r for r in map(json.loads, open(EVAL)) if 'error' not in r}
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
    {'build': build, 'eval': lambda: evaluate(int(a[1]) if len(a) > 1 else 2), 'score': score}[a[0]]()
