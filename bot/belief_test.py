"""How much do better beliefs about the opponent's spreads help the bot? (2026-10-11, the user, after the Eval bar's Speed inference.)
Every turn decision the bot made in its saved ladder games is rebuilt twice, with an older position builder and with the current one
(each from its own evalbar folder), and both are evaluated by the engine (champ evalpos, 32 seeds, staged, every joint option listed).
Taking the current builder's position as the truth, a decision's gain is the value of the mix the current builder would play minus the
value of the mix the old one would play, both read off the current position's joint values. Decisions whose positions agree on every
opposing Speed and stat are skipped (their gain is zero by construction).
  build: .venv/bin/python3 bot/belief_test.py build <evalbar dir> <out prefix>     (one process per builder)
  score: .venv/bin/python3 bot/belief_test.py score <old prefix> <new prefix>"""
import os, sys, json, glob, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def decisions():
    G = [json.loads(l) for l in open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl'))]
    teams = {t['name']: t for t in json.load(open(os.path.join(ROOT, 'bot', 'teams.json')))}
    pool = {t['name']: t for t in json.load(open(os.path.join(ROOT, 'bot', 'out', 'regional_pool.json')))} if os.path.exists(os.path.join(ROOT, 'bot', 'out', 'regional_pool.json')) else {}
    for g in G:
        f = os.path.join(ROOT, 'bot', 'out', g['room'] + '.log')
        team = teams.get(g.get('team')) or pool.get(g.get('team'))
        if not os.path.exists(f) or not team: continue
        # Showdown sends a turn's request right after the log chunk that ends with |turn|N: each move request (one with a top-level
        # 'active', not a replacement) is a decision, made on the log up to it (2026-10-12: this used to pair turn N's log with the
        # request of turn N-1)
        L = open(f, errors='ignore').read().split('\n'); turn = 0
        for i, l in enumerate(L):
            if l.startswith('|turn|'): turn = int(l.split('|')[2])
            elif l.startswith('|request|'):
                try: req = json.loads(l[9:])
                except Exception: continue
                if req.get('active') and not req.get('forceSwitch') and not req.get('wait') and turn:
                    yield g, team, '\n'.join(L[:i]), req, turn
def build(evalbar, prefix):
    sys.path.insert(0, evalbar); sys.path.insert(0, os.path.join(ROOT, 'bot'))
    os.environ.setdefault('CHAMP_MAIN', ROOT)
    import botpos as BP, live as LV, position as POS
    specs_all = []; meta = []
    for g, team, log, req, turn in decisions():
        try: specs, info = BP.bot_position(log, req, g['side'], topk=1, team=POS.export(team['sets']), tag='bot')
        except Exception as e: continue
        if not specs: continue
        w, sp = specs[0]; sp = json.loads(json.dumps(sp)); sp['name'] = f"{g['room'][-14:]} t{turn}"
        specs_all.append((1.0, sp)); meta.append({'name': sp['name'] + ' p1', 'room': g['room'], 'turn': turn})
    posf = prefix + '.pos.jsonl'
    if os.path.exists(posf): os.remove(posf)
    LV.positions(specs_all, posf)
    json.dump(meta, open(prefix + '.meta.json', 'w'))
    print(f"{evalbar}: {len(specs_all)} decisions -> {posf}")
def stats_of(pos):
    """each opposing Pokemon's stats in a position (side 1 of the bot's view)"""
    return {p['species']: p['storedStats'] for p in pos['state']['sides'][1]['pokemon']}
def score(old, new):
    O = {r['name']: r for r in map(json.loads, open(old + '.pos.jsonl'))}; N = {r['name']: r for r in map(json.loads, open(new + '.pos.jsonl'))}
    common = [k for k in N if k in O]
    diff = [k for k in common if stats_of(O[k]) != stats_of(N[k])]
    print(f"{len(common)} decisions built by both; opposing stats differ in {len(diff)}")
    if not diff: return
    for tag, P in (('old', O), ('new', N)):
        f = f'{new}.diff_{tag}.pos.jsonl'
        with open(f, 'w') as h:
            for k in diff: h.write(json.dumps(P[k]) + '\n')
    env = dict(os.environ, RACE_TIES='avg', EVAL_SEEDS='32', EVAL_ADAPT='1', EVAL_TOP='2000', EG_VALUE='egvalue9_sym2.json', RACE='1', TRSYM='1',
               CALC_DATA='../native/champions_data.json', GRID_DIR=os.path.join(ROOT, 'evalbar', 'out', 'emptygrid'), EG_MEGA_TIE='0',
               EG_LAST_PROTECT='0', EG_NO_DOUBLE_PROTECT='0')
    os.makedirs(env['GRID_DIR'], exist_ok=True)
    for tag in ('old', 'new'):
        out = f'{new}.diff_{tag}.eval.jsonl'
        if os.path.exists(out): os.remove(out)
        subprocess.run([os.path.join(ROOT, 'native', 'champ', 'bin', 'battlesim-champ'), 'evalpos', '../native/engine_data_full.json', f'{new}.diff_{tag}.pos.jsonl', out, '6'],
                       cwd=os.path.join(ROOT, 'pssim'), env=env, check=True, capture_output=True)
    EO = {r['name']: r for r in map(json.loads, open(f'{new}.diff_old.eval.jsonl')) if 'error' not in r}
    EN = {r['name']: r for r in map(json.loads, open(f'{new}.diff_new.eval.jsonl')) if 'error' not in r}
    gains = []; unmatched = 0
    for k in diff:
        if k not in EO or k not in EN: continue
        vnew = {j['label']: j['v'] for j in EN[k]['sides'][0]['joint']}
        xo = [(j['label'], j['w']) for j in EO[k]['sides'][0]['joint'] if j['w'] > 1e-4]
        xn = [(j['label'], j['w']) for j in EN[k]['sides'][0]['joint'] if j['w'] > 1e-4]
        if any(lab not in vnew for lab, _ in xo): unmatched += 1; continue
        val = lambda x: sum(w * vnew[lab] for lab, w in x) / max(1e-9, sum(w for _, w in x))
        gains.append((val(xn) - val(xo), k))
    if not gains: print('nothing scored'); return
    g = [x for x, _ in gains]; mu = sum(g) / len(g)
    games = len(set(k.split(' t')[0] for _, k in gains))
    print(f"scored {len(g)} decisions with different beliefs ({unmatched} skipped: an old option missing from the new list), in {games} games")
    print(f"  gain per such decision {100 * mu:+.2f} points (win chance, raw value); total {100 * sum(g):+.1f} points over {games} games = {100 * sum(g) / games:+.2f} per game that had any")
    print(f"  of all {len(common)} decisions: {100 * sum(g) / len(common):+.3f} points per decision; decisions where the choice moved by 5+ points: {sum(1 for x in g if abs(x) >= 0.05)}")
    for x, k in sorted(gains, reverse=True)[:5]: print(f"    {100 * x:+.1f}  {k}")
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'build': build(a[1], a[2])
    else: score(a[1], a[2])
