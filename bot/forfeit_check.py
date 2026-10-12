"""Were the bot's forfeits lost games? (2026-10-12, the user: look for bugs that make for terrible play.) The bot forfeits when its real
win chance reads under limits.json forfeit_below (2%; brain.py: the engine's one-turn value, rescaled). Each forfeit position is rebuilt
as the bot saw it (botpos, the log up to the request it forfeited at) and played out to the end N times by the self-play planner on
both sides (champ battle: DP2 and the anticipation pass on, as in self-play); the bot's share of wins there is the check.
  .venv/bin/python3 bot/forfeit_check.py <out dir> [games per position=40] [threads=6]"""
import os, sys, json, subprocess, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'evalbar')); sys.path.insert(0, os.path.join(ROOT, 'bot'))
os.environ.setdefault('CHAMP_MAIN', ROOT)
import decision_audit as DA
def main(out, n=40, threads=6):
    import botpos as BP, live as LV, position as POS, replay as R
    out = os.path.abspath(out); os.makedirs(out, exist_ok=True); specs = []; meta = []
    for g, team, L in DA.games():
        k = next((i for i, l in enumerate(L) if l.startswith('|-message|') and l.endswith('abnew123-bot forfeited.')), None)
        if k is None: continue
        i = max((j for j in range(k) if L[j].startswith('|request|') and '"active":[' in L[j] and '"forceSwitch"' not in L[j]), default=None)
        if i is None: continue
        req = json.loads(L[i][9:]); log = '\n'.join(L[:i])
        sp, info = BP.bot_position(log, req, g['side'], topk=1, team=POS.export(team['sets']), tag='ff')
        if not sp: print('not built:', g['room'][-12:], info); continue
        w, s = sp[0]; s = json.loads(json.dumps(s)); s['name'] = f"{g['room'][-14:]} t{s['turn']}"
        specs.append((1.0, s)); st = R.parse(log)['steps'][-1]['state']; me = g['side']; op = 'p2' if me == 'p1' else 'p1'
        left = lambda sd: ', '.join(f"{m['n']} {m['hp']}%" for m in st[sd]['mons'] if not m['f'])
        meta.append({'name': s['name'] + ' p1', 'room': g['room'], 'turn': s['turn'], 'me': left(me), 'them': left(op), 'unseen': 4 - len(st[op]['mons'])})
    posf = os.path.join(out, 'forfeits.pos.jsonl')
    if os.path.exists(posf): os.remove(posf)
    P = LV.positions(specs, posf)
    rnd = random.Random(7); starts = os.path.join(out, 'starts.jsonl')
    with open(starts, 'w') as f:
        for j, m in enumerate(meta):
            for gi in range(n): f.write(json.dumps({'job': j, 'g': gi, 'rng': rnd.randrange(1 << 31), 'state': P[m['name']]['state']}) + '\n')
    env = dict(os.environ, RACE_TIES='avg', DP2='1', RACE='1', CALC_DATA='../native/champions_data.json', BATTLE_ANTICIPATE='1', TRSYM='1',
               EG_VALUE='egvalue9_sym2.json', GRID_DIR=os.path.join(ROOT, 'evalbar', 'out', 'emptygrid'), EG_MEGA_TIE='0')
    res = os.path.join(out, 'games')
    subprocess.run([os.environ['CHAMP_BIN'], 'battle', '../native/engine_data_full.json', starts, res, str(threads)], cwd=os.path.join(ROOT, 'pssim'), env=env, check=True, capture_output=True)
    print(f"{len(meta)} forfeits, {n} self-play games each from the forfeit position (the bot's side first)")
    tot = []
    for j, m in enumerate(meta):
        f = os.path.join(res, f'{j}.json')
        if not os.path.exists(f): continue
        rows = [r['v'] for r in json.load(open(f))['rows'] if r.get('v') is not None]
        v = sum(rows) / max(1, len(rows)); tot.append((v, m))
    for v, m in sorted(tot, key=lambda x: -x[0]):
        print(f"  {100 * v:5.1f}% won  ..{m['room'][-12:]} T{m['turn']}: bot {m['me']}  vs  {m['them']}" + (f" (+{m['unseen']} unseen)" if m['unseen'] else ''))
    if tot: print(f"mean {100 * sum(v for v, _ in tot) / len(tot):.1f}% won; over 10%: {sum(1 for v, _ in tot if v > 0.1)}; over 25%: {sum(1 for v, _ in tot if v > 0.25)}")
if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], int(a[1]) if len(a) > 1 else 40, int(a[2]) if len(a) > 2 else 6)
