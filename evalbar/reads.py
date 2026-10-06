"""Were the costly plays reads? For each play the study found costly (study.py: the planner gave it under 5% and it cost over 5 points
against the planner's top action), the turn's payoff matrix (evalpos with EVAL_MATRIX=1: every joint action of one side against every
joint action of the other; champ-battle-v18, every cell at 32 seeds) answers two questions:
  hindsight   against what the opponent actually did that turn, how did the play do next to the planner's top action? Also how far it
              was from the best answer to what the opponent did.
  lines       which of the opponent's joint actions make the play better than the planner's top action, how much the planner's mix put on
              them, and how far the opponent's mix would have to lean toward the best of them before the play breaks even (the share of the
              mix moved, taken from the lines worst for the play).
What was played is matched exactly where the broadcast reader found the target (broadcast.py: the HP box that pops up), and by move with
any target where it did not: the play itself and the planner's top action then take their best target, an opponent's move counts every
target weighted by the planner's mix. The partner is held to what it actually did (any action if the broadcast did not show it). Values
are the acting player's win chance, rescaled as on the page; hypotheses about unseen back Pokemon are averaged with the live mode's weights.
  python3 evalbar/reads.py run [threads=3]      the costly plays' turns through evalpos with the matrix (evalbar/out/reads/)
  python3 evalbar/reads.py report               the two measures per play -> evalbar/out/reads/reads.json and a table"""
import os, sys, json, collections
import common as C, procs as P, replay as R, live as LV, engine as EN, study as ST
OUT = os.path.join(C.HERE, 'out', 'reads')
STUDY = os.path.join(C.HERE, 'out', 'champions', 'study')
def plays():
    return json.load(open(os.path.join(C.HERE, 'results', 'broadcast_study_day1.json')))['costly_plays']
def decisions():
    """(game, turn, side, mon) -> the study's decision (what was played, the planner's table)"""
    return {(d['game'].replace('day1_', ''), d['turn'], d['side'], d['mon']): d for d in json.load(open(os.path.join(STUDY, 'day1.json')))['decisions']}
def turns():
    return sorted({(p['game'], p['turn']) for p in plays()})
def posfile(g, t): return os.path.join(LV.OUT, f'day1_{g}_t{t}_pos.jsonl')
def evfile(g, t): return os.path.join(OUT, f'day1_{g}_t{t}_eval.jsonl')
def run(threads=3):
    # champ-battle-v18: v17 plus EVAL_MATRIX; 'full' gives every cell all 32 seeds (the break-even reads every opponent line)
    os.makedirs(OUT, exist_ok=True); os.environ['EVAL_MATRIX'] = 'full'
    os.environ['CHAMP_BIN'] = os.path.join(C.MAIN, 'native', 'champ', 'bin', 'champ-battle-v18')
    for i, (g, t) in enumerate(turns()):
        os.environ['EVAL_TITLE'] = f'Reads: {g} turn {t} ({i + 1} of {len(turns())})'
        EN.run(posfile(g, t), evfile(g, t), threads, 32, 1)
def weights(g, t):
    f = os.path.join(STUDY, f'day1_{g}.log'); L = LV.Live(None, 1, 0, logfile=f, tag='day1_' + g, fmt='Champions broadcast')
    sp, _ = L.at(open(f).read(), t); return {x['name']: w for w, x in sp}
def keys(side):
    """one side of an evalpos line -> {slot: (mon, {choice: action key})}"""
    return {sl['slot']: (sl['mon'], {json.dumps(o['c'][:2]): ST.key(o['label']) for o in sl['options']}) for sl in side['slots']}
def find(K, mon): return next((i for i, (m, _) in K.items() if R.toid(m).startswith(R.toid(mon.split('-')[0]))), None)
def line_label(label): return label.replace(' | ', ' + ')
def measure(e, pos, side, mon, played, top, partner, opp):
    """one hypothesis: the measures for one play. pos: its position line (the actual choices, with targets where the broadcast showed
    them); partner: (mon, action or None); opp: [(mon, action or None)] for the opponent's actives"""
    M = e['matrix']; me = 0 if side == 'p1' else 1
    rows, cols, rl, cl = (M['rows'], M['cols'], M['rl'], M['cl']) if me == 0 else (M['cols'], M['rows'], M['cl'], M['rl'])
    mix = M['y'] if me == 0 else M['x']
    own = (lambda i, j: ST.scale(M['v1'][i][j])) if me == 0 else (lambda i, j: 1 - ST.scale(M['v1'][j][i]))
    mine, theirs = keys(e['sides'][me]), keys(e['sides'][1 - me])
    act_me, act_opp = (pos['actual'], pos['their_actual']) if me == 0 else (pos['their_actual'], pos['actual'])
    k = find(mine, mon)
    if k is None: return None
    pk = find(mine, partner[0]) if partner[0] else None
    key = lambda K, sl, c: K[sl][1].get(json.dumps(c[:2])) if c else None
    exact = lambda acts, sl: (acts[sl] or {}).get('choice') if sl is not None and sl < len(acts) else None
    def fits(K, acts, sl, c, action):
        """a row's (or column's) choice for slot sl against what was played there: the exact choice when its target is known"""
        if sl is None or action is None: return True
        a = exact(acts, sl)
        if a and key(K, sl, a) == action: return c is not None and c[:2] == a[:2]
        return key(K, sl, c) == action
    def rows_for(action):
        return [i for i, r in enumerate(rows) if key(mine, k, r[k]) == action and fits(mine, act_me, pk, r[pk] if pk is not None else None, partner[1])
                and (action != played or fits(mine, act_me, k, r[k], played))]
    actions = sorted({key(mine, k, r[k]) for r in rows if r[k]} - {None})
    R_ = {a: rows_for(a) for a in actions}
    if not R_.get(played) or not R_.get(top): return None
    V = {a: [max(own(i, j) for i in R_[a]) for j in range(len(cols))] for a in actions if R_[a]}
    tot = sum(mix) or 1; y = [w / tot for w in mix]
    oslot = [(find(theirs, m), a) for m, a in opp]
    act = [j for j, c in enumerate(cols) if all(fits(theirs, act_opp, sl, c[sl] if sl is not None else None, a) for sl, a in oslot)]
    if not act: return None
    wa = [y[j] for j in act]; s_ = sum(wa); wa = [w / s_ for w in wa] if s_ > 1e-6 else [1 / len(act)] * len(act)
    post = {a: sum(w * V[a][j] for w, j in zip(wa, act)) for a in V}
    ante = {a: sum(y[j] * V[a][j] for j in range(len(cols))) for a in V}
    d = [V[played][j] - V[top][j] for j in range(len(cols))]
    # break-even: move mix weight from the lines worst for the play to the line best for it until the play matches the top action
    best = max(range(len(d)), key=lambda j: d[j]); need = -sum(y[j] * d[j] for j in range(len(d))); moved = 0.0
    if need > 0 and d[best] > 0:
        for j in sorted(range(len(d)), key=lambda j: d[j]):
            if need <= 0 or d[j] >= d[best]: break
            m = min(y[j], need / (d[best] - d[j])); moved += m; need -= m * (d[best] - d[j])
    shift = moved if need <= 1e-9 else None if need > 0 else 0.0
    lines = sorted(((d[j], y[j], cl[j]) for j in range(len(d)) if d[j] > 0), reverse=True)
    return {'ante_played': ante[played], 'ante_top': ante[top], 'post_played': post[played], 'post_top': post[top], 'post_best': max(post.values()),
            'post_best_action': max(post, key=post.get), 'mass_better': sum(y[j] for j in range(len(d)) if d[j] > 0), 'shift': shift,
            'lines': [{'line': line_label(l), 'gain': g, 'mix': w} for g, w, l in lines[:5]], 'actual_lines': len(act),
            'exact': bool(exact(act_me, k)) and all(exact(act_opp, sl) for sl, _ in oslot if sl is not None)}
def report():
    D = decisions(); out = []
    for p in plays():
        g, t, sd = p['game'], p['turn'], p['side']; od = 'p2' if sd == 'p1' else 'p1'
        here = {k: v for k, v in D.items() if k[0] == g and k[1] == t}
        partner = next(((k[3], v['played']) for k, v in here.items() if k[2] == sd and k[3] != p['mon']), (None, None))
        opp = [(k[3], v['played']) for k, v in here.items() if k[2] == od]
        if not os.path.exists(evfile(g, t)): out.append({**p, 'measured': False}); continue
        W = weights(g, t); ev = {x['name']: x for x in map(json.loads, open(evfile(g, t))) if 'error' not in x and 'matrix' in x}
        pos = {x['name']: x for x in map(json.loads, open(posfile(g, t)))}
        res = [(W[n], measure(ev[n + ' p1'], pos[n + ' p1'], sd, p['mon'], p['played'], p['planner_top'], partner, opp)) for n in W if n + ' p1' in ev]
        res = [(w, m) for w, m in res if m]
        if not res: out.append({**p, 'measured': False}); continue
        tot = sum(w for w, _ in res); avg = lambda k: sum(w * m[k] for w, m in res) / tot
        lines = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
        for w, m in res:
            for x in m['lines']: L = lines[x['line']]; L[0] += w * x['gain']; L[1] += w * x['mix']; L[2] += w
        shifts = [(w, m['shift']) for w, m in res]
        out.append({**p, 'measured': True, 'hypotheses': len(res), 'partner': partner, 'opp': opp, 'exact': all(m['exact'] for _, m in res),
                    **{k: avg(k) for k in ('ante_played', 'ante_top', 'post_played', 'post_top', 'post_best', 'mass_better')},
                    'post_best_action': collections.Counter(m['post_best_action'] for _, m in res).most_common(1)[0][0],
                    'shift': None if any(s is None for _, s in shifts) else sum(w * s for w, s in shifts) / tot,
                    'lines': sorted(({'line': l, 'gain': a / n, 'mix': b / n} for l, (a, b, n) in lines.items()), key=lambda x: -x['gain'])[:5]})
    json.dump(out, open(os.path.join(OUT, 'reads.json'), 'w'), indent=1)
    print(f"{'play':58s} {'cost':>5s} {'vs actual':>9s} {'to best':>7s} {'better on':>9s} {'lean':>6s}")
    for x in out:
        if not x.get('measured'): print(f"{x['game']} t{x['turn']} {x['side']} {x['mon']}: not measured"); continue
        nm = f"{x['game']} t{x['turn']} {x['side']} {x['mon']} {x['played']} (top {x['planner_top']})"[:58]
        lean = 'never' if x['shift'] is None else f"{100 * x['shift']:.0f}%"
        print(f"{nm:58s} {100 * (x['ante_top'] - x['ante_played']):5.1f} {100 * (x['post_top'] - x['post_played']):9.1f} {100 * (x['post_best'] - x['post_played']):7.1f} "
              f"{100 * x['mass_better']:8.0f}% {lean:>6s}")
if __name__ == '__main__':
    P.own()
    a = sys.argv[1:]
    if a and a[0] == 'run': run(int(a[1]) if len(a) > 1 else 3)
    elif a and a[0] == 'report': report()
    else: sys.exit(__doc__)
