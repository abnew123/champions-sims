"""How closely do players' choices follow the engine? For every turn of every game read from a broadcast (broadcast.py), the position as
the players knew it (team sheets, what had come in; the unseen back Pokémon averaged over, as in the live mode) is evaluated, and each
Pokémon's actual choice is compared with the engine's options for it.
Broadcast text names the move but not its target, so choices are compared by action: the move (any target) or the switch. Per action:
  picks   the planner's probability of choosing it (its options' weights summed over targets, averaged over the hypotheses)
  value   that player's win chance with its best target, against the opponent's equilibrium mix, rescaled to real outcomes
Per decision: did the player take the planner's most likely action (top pick), the action with the highest value (best value), the
planner's probability on what they did, the most likely action's share by chance (1 / number of actions), and the regret (best value
minus the value of what they did, in win-chance points).
  python3 evalbar/study.py <broadcast ocr .jsonl> [threads=2]        -> evalbar/out/champions/study/<name>.json and a summary
  python3 evalbar/study.py <broadcast ocr .jsonl> [threads=2] [t0]  t0: the video time of the file's first frame (a followed stream)
  python3 evalbar/study.py publish <broadcast ocr .jsonl>          the committed summary, results/broadcast_study_<name>.json: the measures,
                                                                     per game, and the costly plays (the planner gave them under 5% and they
                                                                     cost over 5 points against its top action) with the turn's VOD time
  python3 evalbar/study.py replays [evalpos output=evalbar/out/acc_eval_sym2.jsonl]
                                                                     the same measures on the Showdown Bo3 accuracy set (560 cached games,
                                                                     every turn already evaluated; full information), for comparison"""
import os, re, sys, json, math, collections
import common as C, procs as P, replay as R, broadcast as BC, live as LV
OUT = os.path.join(C.HERE, 'out', 'champions', 'study')
logit = lambda v: math.log(min(1 - 1e-4, max(1e-4, v)) / (1 - min(1 - 1e-4, max(1e-4, v))))
scale = lambda v: C.sig(LV.CAL * logit(v))
def key(label):
    """an option label -> its action: the move without target or Mega flag, or the switch"""
    if label.startswith('switch to '): return label
    return re.sub(r' \(Mega\)$', '', label.split(' -> ')[0])
def acted(a, state_mon):
    if not a: return None
    if 'switch' in a: return 'switch to ' + a['switch']
    return a.get('move')
def decisions(L, log, g):
    """per turn and side and active Pokémon: the planner's action table and what was played"""
    out = []
    full = R.parse(log)
    for step in full['steps']:
        t = step['turn']
        if t < 1 or not L.weights.get(t): continue
        W = L.weights[t]; ev = {x['name']: x for x in map(json.loads, open(L.evf)) if 'error' not in x}
        names = [n for n in W if n + ' p1' in ev]
        if not names: continue
        tot = sum(W[n] for n in names)
        pre = R.parse(L.upto(log, t)); st = next(x for x in pre['steps'] if x['turn'] == t)['state']
        for si, sd in enumerate(('p1', 'p2')):
            on = sorted([m for m in st[sd]['mons'] if m['pos'] and not m['f']], key=lambda m: m['pos'])
            for m in on:
                played = acted(step['acts'].get(sd + m['pos']), m)
                if not played: continue
                table = collections.defaultdict(lambda: [0.0, 0.0, 0.0])           # action -> [picks, value * weight, weight]
                for n in names:
                    w = W[n] / tot
                    sl = next((x for x in ev[n + ' p1']['sides'][si]['slots'] if R.toid(x['mon']).startswith(R.toid(m['sp'].split('-')[0]))), None)
                    if not sl: continue
                    best = {}
                    for o in sl['options']:
                        k = key(o['label']); best[k] = max(best.get(k, 0), scale(o['v']))
                        table[k][0] += w * o['w']
                    for k, v in best.items(): table[k][1] += w * v; table[k][2] += w
                if not table: continue
                T = {k: (p, vw / ww) for k, (p, vw, ww) in table.items() if ww > 0}
                pk = next((k for k in T if R.toid(k) == R.toid(played)), None)
                if pk is None: continue                                       # an action outside the sets as read (a misread move)
                top = max(T, key=lambda k: T[k][0]); bestv = max(T, key=lambda k: T[k][1])
                out.append({'turn': t, 'side': sd, 'mon': m['sp'], 'played': pk, 'top': top, 'best': bestv, 'p_played': T[pk][0], 'mix': {k: p for k, (p, _) in T.items()},
                            'p_top': T[top][0], 'p_sq': sum(p * p for p, _ in T.values()), 'n': len(T), 'regret': T[bestv][1] - T[pk][1],
                            'v_played': T[pk][1], 'v_best': T[bestv][1], 'v_top': T[top][1],
                            'table': {k: [round(p, 3), round(v, 3)] for k, (p, v) in T.items()}})
    return out
E = json.load(open(os.path.join(C.MAIN, 'native', 'engine_data_full.json')))
PROTECT = {'protect', 'detect', 'spikyshield', 'kingsshield', 'banefulbunker', 'silktrap', 'burningbulwark', 'obstruct'}
def kind(action):
    """an action's category, for comparing how often players and the planner choose each kind"""
    if action.startswith('switch to '): return 'switch'
    i = R.toid(action); mv = E['moves'].get(i, {})
    if i in PROTECT: return 'Protect'
    if i in ('fakeout', 'trickroom', 'tailwind', 'followme', 'ragepowder', 'helpinghand', 'partingshot', 'wideguard'): return mv.get('name', action)
    cat = mv.get('category') or mv.get('cat')
    return 'other status move' if cat == 'Status' else 'attack'
def kinds(D, tag=''):
    """per kind of action: how often it was played against the planner's probability for it (both averaged over decisions)"""
    played = collections.Counter(); planned = collections.Counter()
    for d in D:
        played[kind(d['played'])] += 1
        for k, p in d.get('mix', {}).items(): planned[kind(k)] += p
    n = len(D)
    print(f"{tag}{'kind of action':18s} {'players':>8s} {'planner':>8s}")
    for k in sorted(set(played) | set(planned), key=lambda k: -planned[k]):
        print(f"{tag}{k:18s} {100 * played[k] / n:7.1f}% {100 * planned[k] / n:7.1f}%")
def summary(D, tag=''):
    n = len(D)
    if not n: print(tag, 'no decisions'); return {}
    f = lambda x: sum(x) / n
    s = {'decisions': n, 'top_pick': f([d['played'] == d['top'] for d in D]), 'best_value': f([d['played'] == d['best'] for d in D]),
         'p_played': f([d['p_played'] for d in D]), 'p_if_following_mix': f([d['p_sq'] for d in D]), 'chance': f([1 / d['n'] for d in D]),
         'regret_mean': f([d['regret'] for d in D]), 'regret_median': sorted(d['regret'] for d in D)[n // 2],
         'within_2pts': f([d['regret'] <= 0.02 for d in D]), 'within_5pts': f([d['regret'] <= 0.05 for d in D])}
    print(f"{tag}{n} decisions | took the planner's top pick {100 * s['top_pick']:.0f}% (by chance {100 * s['chance']:.0f}%) | the best-value action "
          f"{100 * s['best_value']:.0f}% | planner's probability on the played action {100 * s['p_played']:.0f}% (if players followed its mix: "
          f"{100 * s['p_if_following_mix']:.0f}%) | regret mean {100 * s['regret_mean']:.1f} pts, median {100 * s['regret_median']:.1f}, "
          f"within 2 pts {100 * s['within_2pts']:.0f}%, within 5 pts {100 * s['within_5pts']:.0f}%")
    return s
def broadcast_study(ocrf, threads=2, t0=0):
    """t0: the video time of the first frame (the turns' video times are kept for the costly plays)"""
    os.makedirs(OUT, exist_ok=True); name = os.path.basename(ocrf).split('.')[0]
    r = BC.read(ocrf, t0); allD = []; games = []
    for g, m in r.logs_meta():
        tag = f"{name}_m{m['match']}g{m['game']}"; f = os.path.join(OUT, tag + '.log'); open(f, 'w').write('\n'.join(g) + '\n')
        L = LV.Live(None, threads, 0, logfile=f, tag=tag, fmt='Champions broadcast')
        if m.get('closed'): L.bo3 = False                                    # no sheets on stream: each species' most common set, as the live page
        log = open(f).read(); gp = R.parse(log)
        for st in gp['steps']:
            if st['turn'] >= 1:
                try: L.evaluate(log, gp, st)
                except Exception as e: print(tag, 'turn', st['turn'], 'not evaluated:', type(e).__name__)
        D = decisions(L, log, gp); allD += [{**d, 'game': tag, 'vt': (m.get('times') or {}).get(d['turn'])} for d in D]
        games.append({'game': tag, 'turns': sum(st['turn'] >= 1 for st in gp['steps']), 'winner': gp['winner'], **summary(D, f'{tag}: ')})
    print(); s = summary(allD, 'ALL: '); kinds(allD, '   ')
    json.dump({'summary': s, 'games': games, 'decisions': allD}, open(os.path.join(OUT, name + '.json'), 'w'), indent=1)
def publish(ocrf):
    name = os.path.basename(ocrf).split('.')[0]; d = json.load(open(os.path.join(OUT, name + '.json'))); D = d['decisions']; n = len(D)
    if any('vt' not in x for x in D):                                    # a study run before the VOD times were kept
        T = {f"{name}_m{m['match']}g{m['game']}": m.get('times') or {} for _, m in BC.read(ocrf).logs_meta()}
        for x in D: x['vt'] = T.get(x['game'], {}).get(x['turn'])
    res = os.path.join(C.HERE, 'results', f'broadcast_study_{name}.json'); old = json.load(open(res)) if os.path.exists(res) else {}
    played = collections.Counter(kind(x['played']) for x in D); planned = collections.Counter()
    for x in D:
        for k, p in x['mix'].items(): planned[kind(k)] += p
    win = {g['game']: g['winner'] for g in d['games']}; short = lambda g: g.replace(name + '_', '')
    costly = sorted([x for x in D if x['p_played'] < 0.05 and x['v_top'] - x['v_played'] > 0.05], key=lambda x: x['v_played'] - x['v_top'])
    out = {'source': old.get('source', name), 'games': len(d['games']), 'matches': len({short(g['game']).split('g')[0] for g in d['games']}), 'summary': d['summary'],
           'by_kind': {k: {'players': played[k] / n, 'planner': planned[k] / n} for k in sorted(set(played) | set(planned), key=lambda k: -planned[k])},
           'per_game': [{'game': short(g['game']), 'turns': g['turns'], 'decisions': g['decisions'], 'top_pick': g['top_pick'], 'regret_mean': g['regret_mean'],
                         'regret_median': g['regret_median']} for g in d['games']],
           'costly_plays_note': "plays the planner gave under 5% that cost over 5 win-chance points against its most likely action (cost = its value "
                                "minus the played action's); video_s is the VOD time of the turn",
           'costly_plays': [{'game': short(x['game']), 'turn': x['turn'], 'side': x['side'], 'mon': x['mon'], 'played': x['played'], 'planner_top': x['top'],
                             'p_played': round(x['p_played'], 4), 'cost': round(x['v_top'] - x['v_played'], 3), 'video_s': x['vt'],
                             'side_won': (win[x['game']] == x['side']) if win.get(x['game']) else None} for x in costly]}
    json.dump(out, open(res, 'w'), indent=1); print(f"{res}: {n} decisions, {len(costly)} costly plays")
def replay_study(evf):
    """the measures on already-evaluated Showdown positions: the played option is the one evalpos marked actual (targets known), compared
    by action like the broadcast"""
    D = []
    for l in open(evf):
        e = json.loads(l)
        if 'error' in e: continue
        for si, side in enumerate(e['sides']):
            for sl in side['slots']:
                pl = next((o for o in sl['options'] if o.get('actual')), None)
                if not pl: continue
                T = collections.defaultdict(lambda: [0.0, 0.0])
                for o in sl['options']:
                    k = key(o['label']); T[k][0] += o['w']; T[k][1] = max(T[k][1], scale(o['v']))
                pk = key(pl['label']); top = max(T, key=lambda k: T[k][0]); bestv = max(T, key=lambda k: T[k][1])
                D.append({'turn': e['turn'], 'played': pk, 'top': top, 'best': bestv, 'p_played': T[pk][0], 'p_top': T[top][0], 'mix': {k: p for k, (p, _) in T.items()},
                          'p_sq': sum(p * p for p, _ in T.values()), 'n': len(T), 'regret': T[bestv][1] - T[pk][1]})
    summary(D, 'Showdown Bo3 (cached games): '); kinds(D, '   ')
    for lo, hi in ((1, 3), (4, 6), (7, 99)): summary([d for d in D if lo <= d['turn'] <= hi], f'   turns {lo}-{hi if hi < 99 else "on"}: ')
if __name__ == '__main__':
    P.own()
    a = sys.argv[1:]
    if a and a[0] == 'replays': replay_study(a[1] if len(a) > 1 else os.path.join(C.HERE, 'out', 'acc_eval_sym2.jsonl'))
    elif a and a[0] == 'publish': publish(a[1])
    elif a: broadcast_study(a[0], int(a[1]) if len(a) > 1 else 2, float(a[2]) if len(a) > 2 else 0)
    else: sys.exit(__doc__)
