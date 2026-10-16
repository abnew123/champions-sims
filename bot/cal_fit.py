"""The bot's own CAL (2026-10-16, after the bot moved to depth at 4x): its saved games rebuilt as it saw them (botpos, top back-row
guess, decision_audit.games) at turns 1, 3 and 5, evaluated with the bot's live search (position.run_eval with limits.json's search for
the game's format), and the weight on the value's log-odds that best predicts the real result (log loss, one weight, no intercept, as
live.CAL is used: real = sigmoid(CAL x logit(value))); SE by bootstrapping games. CAL sets the forfeit line and contempt's real win chance.
  .venv/bin/python3 bot/cal_fit.py build <prefix>            positions -> <prefix>.pos.jsonl, <prefix>.meta.json
  .venv/bin/python3 bot/cal_fit.py eval <prefix> [threads]   the bot's search on them (Bo1 and Bo3 each with its own settings)
  .venv/bin/python3 bot/cal_fit.py fit <prefix>"""
import os, sys, json, math, random, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'evalbar')); sys.path.insert(0, os.path.join(ROOT, 'bot'))
import position as POS   # first: the bot's engine link before the Eval bar's default (live.py would set v25)
TURNS = (1, 3, 5)
def build(prefix):
    import decision_audit as DA, botpos as BP, live as LV, bo1
    specs = {'Bo1': [], 'Bo3': []}; meta = {}
    for g, team, L in DA.games():
        me = g['side']; op = 'p2' if me == 'p1' else 'p1'; fmt = 'Bo1' if g.get('format') == 'gen9championsvgc2026regmc' else 'Bo3'
        turn = 0
        for i, l in enumerate(L):
            if l.startswith('|turn|'): turn = int(l.split('|')[2]); continue
            if turn not in TURNS or not l.startswith('|request|'): continue
            try: req = json.loads(l[9:])
            except Exception: continue
            if not req.get('active') or req.get('forceSwitch') or req.get('wait'): continue
            try: sp, info = BP.bot_position('\n'.join(bo1.inject(list(L[:i]), op, team['sets'], me)), req, me, topk=1, team=POS.export(team['sets']), tag='bot')
            except Exception: continue
            if not sp: continue
            w, s = sp[0]; name = f"{g['room'][-14:]} t{turn}"; s = json.loads(json.dumps(s)); s['name'] = name + s['name'][len(s['name'].split(' h')[0]):]
            specs[fmt].append((w, s)); meta[name] = {'game': g['room'], 'won': bool(g['won']), 'turn': turn, 'format': fmt}
    for fmt, S in specs.items():
        f = f'{prefix}_{fmt}.pos.jsonl'
        if os.path.exists(f): os.remove(f)
        if S: LV.positions(S, f)
    json.dump(meta, open(prefix + '.meta.json', 'w'))
    print({k: len(v) for k, v in specs.items()}, 'positions')
def evaluate(prefix, threads=3):
    for fmt, code in (('Bo1', 'gen9championsvgc2026regmc'), ('Bo3', 'gen9championsvgc2026regmcbo3')):
        posf, outf = f'{prefix}_{fmt}.pos.jsonl', f'{prefix}_{fmt}.eval.jsonl'
        if os.path.exists(posf): POS.run_eval(posf, outf, threads, 32, POS.search_of(code) or None)
def fit(prefix):
    import numpy as np
    from scipy.optimize import minimize_scalar
    meta = json.load(open(prefix + '.meta.json')); rows = []
    for fmt in ('Bo1', 'Bo3'):
        f = f'{prefix}_{fmt}.eval.jsonl'
        if not os.path.exists(f): continue
        for l in open(f):
            r = json.loads(l); name = next((n for n in meta if r.get('name', '').startswith(n + ' ')), None)
            if name is None or 'value' not in r: continue
            v = min(max(r['value'], 1e-4), 1 - 1e-4); rows.append((meta[name], math.log(v / (1 - v))))
    def cal(rs):
        z = np.array([x for _, x in rs]); y = np.array([m['won'] for m, _ in rs], float)
        f = lambda c: np.mean(np.logaddexp(0, -c * z) * y + np.logaddexp(0, c * z) * (1 - y))
        return minimize_scalar(f, bounds=(0.05, 3), method='bounded').x
    def show(label, rs):
        if len(rs) < 50: return
        by = collections.defaultdict(list)
        for r in rs: by[r[0]['game']].append(r)
        keys = list(by); rnd = random.Random(9)
        bs = [cal([r for k in [rnd.choice(keys) for _ in keys] for r in by[k]]) for _ in range(200)]
        print(f'  {label:12s} {len(rs):5d} positions {len(keys):4d} games  CAL {cal(rs):.3f} +- {np.std(bs):.3f}')
    print(f"the bot's CAL with its live search (live.CAL now {POS.LV.CAL})")
    show('all', rows)
    for fmt in ('Bo1', 'Bo3'): show(fmt, [r for r in rows if r[0]['format'] == fmt])
    for t in TURNS: show(f'turn {t}', [r for r in rows if r[0]['turn'] == t])
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'build': build(a[1])
    elif a[0] == 'eval': evaluate(a[1], int(a[2]) if len(a) > 2 else 3)
    elif a[0] == 'fit': fit(a[1])
