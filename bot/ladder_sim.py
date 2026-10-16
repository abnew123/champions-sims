"""Does the climb's simulator predict the bot's real ladder results? (2026-10-16, the user: check the sim against the ladder before
trusting what the climb finds.) Each of the bot's saved games is rebuilt at its first turn as the bot saw it (botpos, topk 1: our four
exact, the opponent's leads as seen, their back row the bot's top guess, their sets from the open sheet in Bo3 or the guessed sets in
Bo1), then played out K times by the climb's setup (teamsearch v33n1: champ battle, sym2 + the h64 net on both sides, one luck seed a
cell; ladder_sim.sh). The bot's games are a clean test of the sim: our side was played by the same planner, so what is left is the
human opponent, the hidden information and the engine itself. Scored as the sim's win share against the real result: overall,
calibration, log loss, and by format, our team, our style and the opponent's style, and by whether the back-row guess was right.
  .venv/bin/python3 bot/ladder_sim.py build <prefix> [K=4]      -> <prefix>.jsonl / <prefix>.jobs.json (battle starts), <prefix>.meta.json
  SP=<prefix's folder> ../pssim/ladder_sim.sh                     (the climb's setup over the starts, a progress card)
  .venv/bin/python3 bot/ladder_sim.py report <prefix> <outdir>"""
import os, sys, json, glob, math, random, collections, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ('evalbar', 'bot', 'pssim'): sys.path.insert(0, os.path.join(ROOT, p))
os.environ.setdefault('CHAMP_MAIN', ROOT)
def base(sp): return re.sub(r'-mega(-[xyz])?$', '', sp.strip().lower())
def build(prefix, K=4):
    import decision_audit as DA, botpos as BP, position as POS, live as LV, bo1
    from cluster_opps import norm
    from pro_replays import arch
    specs, meta = [], {}
    for g, team, L in DA.games():
        me = g['side']; op = 'p2' if me == 'p1' else 'p1'
        try:
            t1 = next(i for i, l in enumerate(L) if l.startswith('|turn|1'))
            i = next(k for k in range(t1, len(L)) if L[k].startswith('|request|') and (lambda r: r.get('active') and not r.get('forceSwitch') and not r.get('wait'))(json.loads(L[k][9:])))
        except (StopIteration, ValueError): continue
        req = json.loads(L[i][9:]); log = '\n'.join(bo1.inject(list(L[:i]), op, team['sets'], me))
        try: sp, info = BP.bot_position(log, req, me, topk=1, team=POS.export(team['sets']), tag='bot')
        except Exception: continue
        if not sp: continue
        w, s = sp[0]; name = f"{g['room'][-14:]} t1"; s = json.loads(json.dumps(s)); s['name'] = name + s['name'][len(s['name'].split(' h')[0]):]
        six = {sd: [l.split('|')[3].split(',')[0] for l in L if l.startswith(f'|poke|{sd}|')] for sd in (me, op)}
        seen = set()
        for l in L:
            q = l.split('|')
            if len(q) > 3 and q[1] in ('switch', 'drag') and q[2].startswith(op): seen.add(base(q[3].split(',')[0]))
        hyp = (info.get('hyp') or [(0, [])])[0][1]
        leads = set(base(q.split('|')[3].split(',')[0]) for q in L[:t1] if q.startswith(f'|switch|{op}'))
        guess = leads | set(base(x) for x in hyp)
        meta[name] = {'room': g['room'], 'format': 'Bo1' if g.get('format') == 'gen9championsvgc2026regmc' else 'Bo3', 'won': bool(g['won']),
                      'team': 'regional pool' if re.match(r'f\d+ #', g.get('team') or '') else g.get('team'), 'my_arch': arch([norm(x) for x in six[me]]),
                      'arch': arch([norm(x) for x in six[op]]), 'opp_rating': g.get('oppRating'), 'my_rating': g.get('myRating'),
                      'back_known': len(seen) == 4, 'back_right': len(seen) == 4 and guess == seen, 'turns': g.get('turns')}
        specs.append((w, s))
    posf = prefix + '.pos.jsonl'
    if os.path.exists(posf): os.remove(posf)
    LV.positions(specs, posf)
    rnd = random.Random(16); starts = []; jobs = {}
    for l in open(posf):
        r = json.loads(l); name = next((n for n in meta if r['name'].startswith(n + ' ')), None)
        if name is None or r.get('error'): continue
        j = len(jobs); jobs[j] = name
        for k in range(K): starts.append({'job': j, 'g': k, 'rng': float(rnd.randrange(1, 2 ** 31)), 'state': r['state'], 'meta': {'name': name, **meta[name]}})
    with open(prefix + '.jsonl', 'w') as f:
        for s in starts: f.write(json.dumps(s) + '\n')
    json.dump(sorted(jobs), open(prefix + '.jobs.json', 'w')); json.dump({'jobs': jobs, 'meta': meta, 'K': K}, open(prefix + '.meta.json', 'w'))
    print(f'{len(jobs)} games rebuilt at turn 1 ({len(meta) - len(jobs)} more without a position), {len(starts)} starts -> {prefix}.jsonl')
def report(prefix, outdir):
    M = json.load(open(prefix + '.meta.json')); jobs, meta = M['jobs'], M['meta']
    R = []
    for f in glob.glob(os.path.join(outdir, '*.json')):
        o = json.load(open(f)); vs = [r['v'] for r in o.get('rows', []) if r.get('v') is not None]
        if not vs: continue
        m = meta[jobs[str(o['job'])]]; R.append({**m, 'p': sum(vs) / len(vs), 'n': len(vs)})
    n = len(R)
    if not n: print('nothing yet'); return
    def line(name, rs):
        k = len(rs)
        if k < 15: return
        ps = sum(r['p'] for r in rs) / k; ws = sum(r['won'] for r in rs) / k
        d = [r['won'] - r['p'] for r in rs]; md = sum(d) / k; se = math.sqrt(sum((x - md) ** 2 for x in d) / max(k - 1, 1) / k)
        print(f"  {name:24s} {k:4d}  sim {100 * ps:5.1f}%  real {100 * ws:5.1f}%  real - sim {100 * (ws - ps):+5.1f} ± {100 * se:3.1f}")
    print(f"{n} games, {sum(r['n'] for r in R)} sim playouts from turn 1")
    line('all', R)
    cl = lambda p: min(max(p, 0.03), 0.97)
    ll = -sum(math.log(cl(r['p'])) if r['won'] else math.log(1 - cl(r['p'])) for r in R) / n
    base_rate = sum(r['won'] for r in R) / n; ll0 = -(base_rate * math.log(base_rate) + (1 - base_rate) * math.log(1 - base_rate))
    agree = [r for r in R if abs(r['p'] - 0.5) > 1e-9]
    print(f"  log loss {ll:.4f} (base rate alone {ll0:.4f}); sim's favourite won {100 * sum((r['p'] > 0.5) == r['won'] for r in agree) / max(len(agree), 1):.1f}% of {len(agree)} games")
    print('calibration (sim win share bin: games, sim, real)')
    for lo, hi in ((0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)):
        rs = [r for r in R if lo <= r['p'] < hi]
        if rs: print(f"  {lo:.1f}-{min(hi, 1):.1f}  {len(rs):4d}  {100 * sum(r['p'] for r in rs) / len(rs):5.1f}%  {100 * sum(r['won'] for r in rs) / len(rs):5.1f}%")
    for key, title in (('format', 'by format'), ('team', 'by our team'), ('my_arch', 'by our style'), ('arch', "by the opponent's style")):
        print(title)
        by = collections.defaultdict(list)
        for r in R: by[r[key]].append(r)
        for k in sorted(by, key=lambda k: -len(by[k])): line(str(k), by[k])
    print("by the back-row guess (games where all four of theirs were seen)")
    line('guess right', [r for r in R if r['back_known'] and r['back_right']]); line('guess wrong', [r for r in R if r['back_known'] and not r['back_right']])
    tr = [r for r in R if r['team'] == 'Trick Room six']
    if tr:
        print("Trick Room six by the opponent's style")
        by = collections.defaultdict(list)
        for r in tr: by[r['arch']].append(r)
        for k in sorted(by, key=lambda k: -len(by[k])): line(str(k), by[k])
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'build': build(a[1], int(a[2]) if len(a) > 2 else 4)
    elif a[0] == 'report': report(a[1], a[2])
