"""Did contempt get punished in the bot's own Bo3 games? (2026-10-13, the user: the Trick Room six went 8-18 with contempt 0.5 on;
"if you can find a reason specifically in the games we played where contempt got punished happy to turn it off".) Every decision of the
Trick Room six's Bo3 games from CONTEMPT_FROM back is rebuilt as the bot saw it (botpos, the log up to its request) and solved twice on
independent luck: the bot's live version (the staged search + its matrix, EVAL_MATRIX=1), which gives the equilibrium mix (c 0) and the
contempt mix (c 0.5, position.contempt_mix), and the full payoff matrix with both sides' actual plays marked, which scores them. Per
decision: the contempt mix's value against what the opponent actually played, minus the equilibrium's (real win chance points), and the
decisions where contempt cost the most, with what the bot leaned towards and what the opponent did. The games before contempt went on
(the bot played the equilibrium there) are the control.
  .venv/bin/python3 bot/contempt_bot.py build [n_before] | eval [threads] | score
Result (11:58 am Oct 13; 28 games with contempt, 230 decisions, 190 scored; a slot that never moved averaged by the opponent's equilibrium):
against what the opponents actually played, the contempt mix did +0.64 ± 0.25 real points a decision better than the equilibrium (game 1
+0.45 ± 0.53, games 2-3 +0.76 ± 0.22; their whole play shown +0.75 ± 0.40), for the same price against a perfect opponent (1.76 -> 1.71).
The 22 games before: contempt would have gained +0.17 ± 0.14. One decision cost much (-16.7: Trick Room into Wood Hammer); no pattern. So the
8-18 start was not contempt's choices as the engine values them: contempt stays on, more games first (the user)."""
import os, sys, json, math, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'evalbar')); sys.path.insert(0, os.path.join(ROOT, 'bot')); sys.path.insert(0, os.path.join(ROOT, 'pssim'))
os.environ.setdefault('CHAMP_MAIN', ROOT)
OUT = os.path.join(ROOT, 'bot', 'out', 'contempt_bot'); os.makedirs(OUT, exist_ok=True)
POS, META = os.path.join(OUT, 'pos.jsonl'), os.path.join(OUT, 'meta.json')
LPOS, LEVAL, BPOS, BEVAL = (os.path.join(OUT, x) for x in ('live_pos.jsonl', 'live_eval.jsonl', 'full_pos.jsonl', 'full_eval.jsonl'))
ON = os.environ.get('CONTEMPT_FROM', '2026-10-13T02:06')     # contempt 0.5 on for Bo3 (limits.json, 10:06 pm Oct 12)
UNTIL = os.environ.get('CONTEMPT_UNTIL', '2026-10-13T15:02')  # the fitted spreads went on for Bo3 after this (11:02 am Oct 13)
FMT = 'gen9championsvgc2026regmcbo3'
def build(n_before=22):
    import replay as R; R.BATON_PASS = True; R.MEGA_ABIL = True
    import spreads; spreads.FITTED = False
    import belief_test as BT, botpos as BP, live as LV, position as POS_
    G = [json.loads(l) for l in open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl')) if '"arm"' in l]
    tr = [g for g in G if g.get('format', FMT) == FMT and g.get('team') == 'Trick Room six' and g['when'] < UNTIL]
    after = [g['room'] for g in tr if g['when'] >= ON]; before = [g['room'] for g in tr if g['when'] < ON][-n_before:]
    rooms = set(after) | set(before); specs_all = []; meta = []; tally = collections.Counter(); full = {}
    seen = collections.Counter(); gameno = {}
    for g in tr: seen[g.get('match') or g['room']] += 1; gameno[g['room']] = seen[g.get('match') or g['room']]   # game 1, 2, 3 of its match
    for g, team, log, req, turn in BT.decisions():
        if g['room'] not in rooms: continue
        try: specs, info = BP.bot_position(log, req, g['side'], topk=1, team=POS_.export(team['sets']), tag='cb')
        except Exception as e: tally['build failed'] += 1; continue
        if not specs: tally['no position'] += 1; continue
        if g['room'] not in full: full[g['room']] = R.parse(open(os.path.join(ROOT, 'bot', 'out', g['room'] + '.log'), errors='ignore').read())
        i = log.rfind('\n|turn|'); j = log.find('\n', i + 1); pre = log[:j + 1] if j >= 0 else log + '\n'
        step = R.parse(pre)['steps'][-1]; st = step['state']; opp = 'p2' if g['side'] == 'p1' else 'p1'
        later = next((x for x in full[g['room']]['steps'] if x['turn'] == step['turn']), None)
        if later is None: tally['turn not in the log'] += 1; continue
        # the actual plays as live.specs_for marks them: by engine slot (actives first), targets mapped to the engine's slots
        order = {sd: sorted(st[sd]['mons'], key=lambda m: (0 if m['pos'] == 'a' else 1 if m['pos'] == 'b' else 2 if not m['f'] else 3)) for sd in (g['side'], opp)}
        eng = {sd: {m['pos']: 'ab'[k] for k, m in enumerate(order[sd][:2]) if m['pos']} for sd in (g['side'], opp)}
        def act(sd, k):
            m = order[sd][k] if k < len(order[sd]) else None
            a = later['acts'].get(sd + m['pos']) if m and m['pos'] else None
            # the position lists the bot's side first, as 'p1': a real side label becomes the position's (the bot as p2 had its targets
            # read as the other side's)
            if a and a.get('target'): a = {**a, 'target': ('p1' if a['target'][:2] == g['side'] else 'p2') + eng[a['target'][:2]].get(a['target'][2], a['target'][2])}
            return a
        w, sp = specs[0]; name = f"{g['room'][-14:]} t{turn}"; sp = {**sp, 'name': name}
        specs_all.append((1.0, {**sp, 'name': name + ' L'}))
        specs_all.append((1.0, {**sp, 'name': name + ' B', 'acts': [[act(g['side'], 0), act(g['side'], 1)], [act(opp, 0), act(opp, 1)]]}))
        meta.append({'name': name, 'room': g['room'], 'match': g.get('match') or g['room'], 'turn': turn, 'contempt': g['when'] >= ON, 'won': g['won'], 'game': gameno[g['room']],
                     'opp': g.get('oppRating')})
        tally['contempt' if g['when'] >= ON else 'before'] += 1
    if os.path.exists(POS): os.remove(POS)
    LV.positions(specs_all, POS); json.dump(meta, open(META, 'w'))
    with open(LPOS, 'w') as a, open(BPOS, 'w') as b:
        for l in open(POS): (a if json.loads(l)['name'].endswith(' L p1') else b).write(l)
    print(dict(tally), f'{len(after)} games with contempt, {len(before)} before')
def evaluate(threads=7):
    import contempt as C, threading
    a = threading.Thread(target=C.run_evalpos, args=(LPOS, LEVAL, "contempt in the bot's games: the live version", 'contempt_bot_live', max(1, threads * 3 // 7), False, {'EVAL_MATRIX': '1'}))
    a.start(); C.run_evalpos(BPOS, BEVAL, "contempt in the bot's games: full matrices, actual plays", 'contempt_bot_full', max(1, threads - threads * 3 // 7), True); a.join()
def score(show=12):
    import numpy as np
    from scipy.optimize import linprog
    import human_lines as HL, position as POS_
    import live as LV; real = np.vectorize(lambda v: HL.resc(v, LV.CAL))   # the bot's own logged values: its engine's CAL (0.676 since 2026-10-14)
    meta = {m['name']: m for m in json.load(open(META))}
    L = {r['name'][:-5]: r for r in map(json.loads, open(LEVAL)) if 'error' not in r and 'matrix' in r}
    B = {r['name'][:-5]: r for r in map(json.loads, open(BEVAL)) if 'error' not in r and 'matrix' in r}
    def nash(A):
        n, k = A.shape
        res = linprog(np.r_[np.zeros(n), -1.0], A_ub=np.c_[-A.T, np.ones(k)], b_ub=np.zeros(k), A_eq=np.r_[np.ones(n), 0.0][None], b_eq=[1.0],
                      bounds=[(0, None)] * n + [(None, None)], method='highs')
        return -res.fun
    rows = []; skipped = collections.Counter(); g1 = {}
    for name, m in meta.items():
        l, b = L.get(name), B.get(name)
        if not l or not b: skipped['not evaluated'] += 1; continue
        played = [next((o for o in sl['options'] if o.get('actual')), None) for sl in b['sides'][1]['slots']]
        if all(p is None for p in played): skipped['none of their plays shown'] += 1; continue
        # a slot whose play never showed (KO'd or flinched before it moved: common under Trick Room) is averaged over its options by the
        # opponent's equilibrium in the full matrix; the columns that match the plays that did show
        cols = [j for j, c in enumerate(b['matrix']['cols']) if all(p is None or x == p['c'] for x, p in zip(c, played))]
        if not cols: skipped['their play not a column'] += 1; continue
        y = np.array(b['matrix']['y'], float)[cols]; y = y / y.sum() if y.sum() > 0 else np.ones(len(cols)) / len(cols)
        Bm = real(np.array(b['matrix']['v1'], float)); brow = {lab: i for i, lab in enumerate(b['matrix']['rl'])}
        Bm = np.c_[Bm, Bm[:, cols] @ y]; act = Bm.shape[1] - 1                    # their play, as one more column
        x0 = {lab: w for lab, w in zip(l['matrix']['rl'], l['matrix']['x']) if w > 1e-4}; t = sum(x0.values()); x0 = {k: v / t for k, v in x0.items()}
        xc = {j['label']: j['w'] for j in POS_.contempt_mix(l, 0.5)}
        if any(k not in brow for k in list(x0) + list(xc)): skipped['an option missing in the full matrix'] += 1; continue
        val = lambda x, col: sum(w * Bm[brow[k], col] for k, w in x.items())
        worst = lambda x: min(sum(w * Bm[brow[k], j] for k, w in x.items()) for j in range(Bm.shape[1] - 1))
        vB = nash(Bm[:, :-1])
        mine = [next((o for o in sl['options'] if o.get('actual')), None) for sl in b['sides'][0]['slots']]
        shift = sorted(((xc.get(k, 0) - x0.get(k, 0), k) for k in set(x0) | set(xc)), reverse=True)
        rows.append({**m, 'full': all(p is not None for p in played), 'gain': val(xc, act) - val(x0, act), 'price0': vB - worst(x0), 'pricec': vB - worst(xc),
                     'their': ' | '.join(f"{sl['mon']}: {p['label'] if p else '(did not move)'}" for sl, p in zip(b['sides'][1]['slots'], played)),
                     'mine': ' | '.join(f"{sl['mon']}: {p['label']}" for sl, p in zip(b['sides'][0]['slots'], mine) if p),
                     'towards': shift[0], 'away': shift[-1]})
    print(f"{len(rows)} decisions ({len({r['room'] for r in rows})} games); skipped {dict(skipped)}; real win chance points a decision, ± clustered by game")
    def show_(sel, lab):
        xs = [r for r in rows if sel(r)]
        if not xs: return
        g = collections.defaultdict(float)
        for r in xs: g[r['room']] += r['gain'] - sum(y['gain'] for y in xs) / len(xs)
        mu = sum(r['gain'] for r in xs) / len(xs); se = math.sqrt(sum(v * v for v in g.values())) / len(xs)
        p0 = sum(r['price0'] for r in xs) / len(xs); pc = sum(r['pricec'] for r in xs) / len(xs)
        print(f"  {lab:44s} n {len(xs):4d}  contempt's gain vs their actual play {100 * mu:+6.2f} ± {100 * se:.2f}   price vs a perfect opponent {100 * p0:.2f} -> {100 * pc:.2f}")
    for c, lab in ((True, 'contempt on (played)'), (False, 'before (the equilibrium played)')):
        show_(lambda r: r['contempt'] == c, lab)
        show_(lambda r: r['contempt'] == c and r['game'] == 1, '  game 1')
        show_(lambda r: r['contempt'] == c and r['game'] > 1, '  games 2-3')
        show_(lambda r: r['contempt'] == c and r['full'], '  their whole play shown')
    print(f'\nwhere contempt cost the most in the games it was on (the gain against what the opponent did):')
    for r in sorted([r for r in rows if r['contempt']], key=lambda r: r['gain'])[:show]:
        print(f"  {r['room'][-12:]} game {r['game']} t{r['turn']:<2d} {100 * r['gain']:+6.1f}  {'W' if r['won'] else 'L'}  leaned towards {r['towards'][1]} ({100 * r['towards'][0]:+.0f}%),"
              f" away from {r['away'][1]} ({100 * r['away'][0]:+.0f}%); they played {r['their']}")
if __name__ == '__main__':
    a = sys.argv[1:]
    {'build': lambda: build(int(a[1]) if len(a) > 1 else 22), 'eval': lambda: evaluate(int(a[1]) if len(a) > 1 else 7), 'score': score}[a[0]]()
