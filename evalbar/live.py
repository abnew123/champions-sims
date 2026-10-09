"""Live spectator mode: the eval bar on a Showdown battle that is going on now, for watching other people's games. Never use it on a game
you are playing, and never pass what it shows to a player during their game.
  python3 evalbar/live.py list [bo1|bo3] [all]                ongoing Reg M-C battles, 8 of each (all: every one): the highest rated
                                                              Bo1 games, the newest Bo3 games (Bo3 rooms show no rating)
  python3 evalbar/live.py watch <room or battle URL> [threads=2] [port=8768]
                                                              follows the battle and serves the page at http://localhost:<port>
It knows what a spectator knows at the start of each turn: both team previews, the Bo3 open team sheets (Bo1: each species' most common
Reg M-C set, with what the game has shown laid on top), the Pokemon that have come in and what happened to them. The Pokemon a player has
not sent in yet are averaged over: for each player the TOPK most likely combinations from their preview (back rates given their leads,
recorded.py back_weight), every pairing of the two players' combinations evaluated by the engine (champ evalpos, as engine.py runs it),
values rescaled to real outcomes. The battle log, positions and results stay in evalbar/out/live/ (git-ignored: the log has usernames).
Needs Node with --experimental-websocket (Node 20.10+)."""
import os, sys, json, math, time, re, itertools, subprocess, threading, collections, http.server
import common as C, replay as R, spots as S, recorded as RC, build as B, engine as EN, procs as P
toid = R.toid
OUT = os.path.join(C.HERE, 'out', 'live'); FEED = os.path.join(C.HERE, 'live_feed.js')
NODE = [P.exe('node'), '--experimental-websocket', '--no-warnings']
FORMATS = {'bo1': 'gen9championsvgc2026regmc', 'bo3': 'gen9championsvgc2026regmcbo3'}
TOPK = 3; CAL = 0.7538                           # the rescale fitted for egvalue9_sym2 (accuracy.py compare)
# the full engine data (every species, move, item and ability Showdown knows; needs champ-battle-v17 or later): spectated teams can be
# anything. v23 (2026-10-09) gives v17's values wherever v17 handled the turn, and handles more abilities, items and moves (Baton Pass too)
os.environ.setdefault('CHAMP_BIN', os.path.join(C.MAIN, 'native', 'champ', 'bin', 'champ-battle-v23'))
os.environ.setdefault('CHAMP_DATA', 'engine_data_full.json')
S.E = RC.E = json.load(open(os.path.join(C.MAIN, 'native', os.environ['CHAMP_DATA'])))
def room_of(x):
    m = re.search(r'(battle-[a-z0-9]+-\d+(?:-[a-z0-9]+)?)', x)
    if not m: sys.exit(f'not a battle room or URL: {x}')
    return m.group(1)
def listing(kind, n=8):
    out = []
    for fmt in ([FORMATS[kind]] if kind else FORMATS.values()):
        r = subprocess.run(NODE + [FEED, 'list', fmt], capture_output=True, text=True, timeout=30)
        out += [{**json.loads(l), 'format': 'Bo3' if fmt.endswith('bo3') else 'Bo1'} for l in r.stdout.splitlines() if l.strip()]
    out.sort(key=lambda x: (-(x['elo'] or 0), -int(re.search(r'-(\d+)(?:-[a-z0-9]+)?$', x['room']).group(1))))   # Bo3 rooms show no rating: newest first
    for fmt in ('Bo1', 'Bo3'):
        rows = [x for x in out if x['format'] == fmt]
        if not rows: continue
        print(f"{fmt}: {len(rows)} battles going on" + (f", the {min(n, len(rows))} {'highest rated' if fmt == 'Bo1' else 'newest (Bo3 shows no rating)'}" if len(rows) > n else ''))
        for x in rows[:n]: print(f"  {'rating ' + str(x['elo']) if x['elo'] else 'no rating  ' if fmt == 'Bo1' else ''}  https://play.pokemonshowdown.com/{x['room']}".replace('    https', '  https'))
def reveals(log):
    """what each Pokemon has shown so far: {(side, species): {'moves': [...], 'item': str, 'ability': str}}"""
    who = {}; out = collections.defaultdict(lambda: {'moves': [], 'item': '', 'ability': ''})
    def key(ident):
        if not ident or ': ' not in ident: return None
        return (ident[:2], who.get(ident[:2] + ':' + ident.split(': ', 1)[1]))
    for l in log.split('\n'):
        p = l.split('|')
        if len(p) < 3: continue
        k = p[1]; tags = {m.group(1): m.group(2).strip() for x in p[2:] for m in [re.match(r'\[(\w+)\]\s?(.*)', x)] if m}
        if k in ('switch', 'drag') and len(p) > 3: who[p[2][:2] + ':' + p[2].split(': ', 1)[1]] = p[3].split(',')[0]
        elif k == 'move' and 'from' not in tags:
            kk = key(p[2])
            if kk and kk[1] and p[3] not in out[kk]['moves']: out[kk]['moves'].append(p[3])
        elif k in ('-enditem', '-item'):
            kk = key(p[2])
            if kk and kk[1]: out[kk]['item'] = re.sub(r'^item: ', '', p[3])
        elif k == '-ability':
            kk = key(p[2])
            if kk and kk[1]: out[kk]['ability'] = re.sub(r'^ability: ', '', p[3])
            continue                                                      # its [from] tag is the same Pokemon's ability (Trace)
        elif k == '-mega' and len(p) > 4:
            kk = key(p[2])
            if kk and kk[1]: out[kk]['item'] = p[4]
        for t, v in tags.items():
            if t == 'from' and v.startswith(('item: ', 'ability: ')):
                kk = key(tags.get('of') or p[2])
                if kk and kk[1]: out[kk]['item' if v.startswith('item') else 'ability'] = v.split(': ', 1)[1]
    return out
def sets_for(g, log, bo3):
    """each player's six as the engine can play them: {side: {species: set or None}}, plus what was left out"""
    six = {sd: [l.split('|')[3].split(',')[0] for l in log.split('\n') if l.startswith(f'|poke|{sd}|')] for sd in ('p1', 'p2')}
    rv = reveals(log); out = {}; dropped = []
    for sd in ('p1', 'p2'):
        out[sd] = {}
        for sp in six[sd]:
            if bo3:
                sh = g['sheets'][sd].get(toid(sp)) or g['sheets'][sd].get(toid(sp.split('-')[0]))
                raw = {'species': sp, 'item': sh['item'], 'ability': sh['ability'], 'nature': sh['nature'], 'moves': sh['moves']} if sh else None
            else:
                try: base = RC.common_set(sp)
                except Exception: base = None
                r = rv.get((sd, sp), {'moves': [], 'item': '', 'ability': ''})
                # a revealed ability counts only if the species can have it (not one its Mega form gained)
                own = set((S.E['species'].get(toid(sp), {}).get('abilities') or {}).values())
                raw = base and {**base, 'moves': list(dict.fromkeys(r['moves'] + base['moves']))[:4], 'item': r['item'] or base['item'],
                                'ability': r['ability'] if r['ability'] in own else base['ability']}
            st, bad = S.fit_set(raw, dropped) if raw else (None, [sp])
            out[sd][sp] = st
    return six, out, dropped
def spec_mon(m, st):
    return {**st, 'forme': m['forme'], 'mega': m['mega'], 'hpPct': m['hp'], 'fainted': m['f'], 'status': m['st'], 'slept': m['slept'], 'boosts': m['b'],
            'itemNow': '' if m['gone'] or toid(st['item']) not in S.E['items'] else st['item'], 'moved': m['moved'], 'stall': m['stall'], 'lock': m['lock'],
            'vol': m['vol'], 'onField': bool(m['pos']), 'last': m['last'], 'volarg': m['volarg']}
def hyps(sd, state, six, sets, leads):
    """the TOPK most likely sets of Pokemon this player has not sent in yet: [(weight, [species])]"""
    known = {m['sp'] for m in state[sd]['mons']}
    pool = [sp for sp in six[sd] if sp not in known and sets[sd].get(sp)]
    need = max(0, 4 - len(known))
    hy = [(math.prod(RC.back_weight(sp, leads[sd]) for sp in c), list(c)) for c in itertools.combinations(pool, min(need, len(pool)))]
    hy.sort(key=lambda x: -x[0]); hy = hy[:TOPK]; tot = sum(w for w, _ in hy) or 1
    return [(w / tot, c) for w, c in hy], pool, need
def specs_for(tag, g, step, six, sets, leads):
    """engine position specs for one turn, one per pairing of the two players' hypotheses: [(weight, spec)]"""
    st = step['state']; H = {sd: hyps(sd, st, six, sets, leads) for sd in ('p1', 'p2')}; out = []
    order = {sd: sorted(st[sd]['mons'], key=lambda m: (0 if m['pos'] == 'a' else 1 if m['pos'] == 'b' else 2 if not m['f'] else 3)) for sd in ('p1', 'p2')}
    eng = {sd: {m['pos']: 'ab'[i] for i, m in enumerate(order[sd][:2]) if m['pos']} for sd in ('p1', 'p2')}
    def act(sd, i):
        m = order[sd][i] if i < len(order[sd]) else None
        a = step['acts'].get(sd + m['pos']) if m and m['pos'] else None
        if a and a.get('target'): a = {**a, 'target': a['target'][:2] + eng[a['target'][:2]].get(a['target'][2], a['target'][2])}
        return a
    for i, (w1, c1) in enumerate(H['p1'][0]):
        for j, (w2, c2) in enumerate(H['p2'][0]):
            sides = []
            for sd, extra in (('p1', c1), ('p2', c2)):
                ms = order[sd]
                bad = [m['sp'] for x in ('p1', 'p2') for m in order[x] if not sets[x].get(m['sp'])]
                if bad: return [], {'missing': sorted(set(bad))}
                mons = [spec_mon(m, sets[sd][m['sp']]) for m in ms]
                mons += [{**sets[sd][sp], 'mega': False, 'hpPct': 100, 'fainted': False, 'status': '', 'slept': 0, 'boosts': {}, 'itemNow': sets[sd][sp]['item'],
                          'moved': False, 'stall': False, 'lock': '', 'vol': [], 'onField': False, 'last': '', 'volarg': {}, 'standIn': True} for sp in extra]
                sides.append({'mons': mons, 'tailwind': st[sd]['tailwind'], 'screens': st[sd]['screens'], 'hazards': st[sd]['hazards']})
            f = st['field']
            out.append((w1 * w2, {'name': f"{tag} t{step['turn']} h{i}{j}", 'turn': step['turn'], 'sides': sides,
                                  'acts': [[act(sd, i) for i in (0, 1)] for sd in ('p1', 'p2')], 'perish': st['perish'], 'standIns': len(c1) + len(c2),
                                  'dropped': [], 'field': {'weather': [f['weather'], f['wturns']] if f['weather'] else None,
                                                           'terrain': [f['terrain'], f['tturns']] if f['terrain'] else None, 'trickroom': f['tr']}}))
    return out, H
def positions(specs, outf):
    tmp = outf + '.specs.json'; json.dump([s for _, s in specs], open(tmp, 'w'))
    subprocess.run([P.exe('node'), os.path.join(C.HERE, 'positions.js'), os.path.abspath(tmp), os.path.abspath(outf), 'p1'], cwd=os.path.join(C.MAIN, 'pssim'),
                   check=True, capture_output=True)
    os.remove(tmp)
    return {x['name']: x for x in map(json.loads, open(outf))}
class Live:
    def __init__(s, room, threads, port, logfile=None, tag=None, fmt=None):
        """room: a Showdown battle room (followed through live_feed.js); or logfile: a battle log another program writes (the broadcast
        reader), with tag naming the outputs and fmt the format line on the page"""
        s.room = room; s.logfile = logfile; s.fmt = fmt
        s.tag = tag or (room.split('-')[-1] if not re.search(r'-\d+-[a-z0-9]+$', room) else room.split('-')[-2])
        s.bo3 = logfile is not None or 'bo3' in room; s.threads = threads; s.port = port; os.makedirs(OUT, exist_ok=True)
        s.log = logfile or os.path.join(OUT, f'{s.tag}.log'); s.evf = os.path.join(OUT, f'{s.tag}_eval.jsonl'); s.data = None; s.status = 'connecting'
        s.weights = {}; s.hyp = {}; s.poscache = {}; s.over = False; s.skip = {}
    def page(s):
        blob = {'games': [], 'live': {'url': 'data.json', 'status': 'connecting'}}
        html = open(os.path.join(C.HERE, 'page.html')).read().replace('<title>Eval Bar</title>', '<title>Live Eval Bar</title>', 1).replace('/*DATA*/null', json.dumps(blob))
        return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<style>body{margin:0}img{max-width:100%}</style></head><body>' + html + '</body></html>')
    def serve(s):
        live = s
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                p = self.path.split('?')[0]
                if p == '/data.json': b = json.dumps(live.data or {'games': [], 'live': {'url': 'data.json', 'status': live.status}}).encode(); ct = 'application/json'
                elif p in ('/', '/index.html'): b = live.page().encode(); ct = 'text/html; charset=utf-8'
                else: self.send_error(404); return
                self.send_response(200); self.send_header('Content-Type', ct); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(b)
            def log_message(self, *a): pass
        threading.Thread(target=http.server.ThreadingHTTPServer(('127.0.0.1', s.port), H).serve_forever, daemon=True).start()
    @staticmethod
    def upto(log, t):
        """the log as a spectator had it when turn t started"""
        i = log.find(f'\n|turn|{t}\n'); return log if i < 0 else log[:i + len(f'\n|turn|{t}\n')]
    def at(s, log, t):
        """engine position specs for turn t, from what was known when it started; the choices made in it (known once it is over) filled in"""
        pre = s.upto(log, t); gp = R.parse(pre); step = next(x for x in gp['steps'] if x['turn'] == t)
        later = next((x for x in R.parse(log)['steps'] if x['turn'] == t), step); step = {**step, 'acts': later['acts']}
        six, sets, _ = sets_for(gp, pre, s.bo3)
        return specs_for(s.tag, gp, step, six, sets, s.leads(pre))
    def build(s, log, g):
        """the page's data from everything evaluated so far"""
        ev = {x['name']: x for x in map(json.loads, open(s.evf)) if 'error' not in x} if os.path.exists(s.evf) else {}
        logit = lambda v: math.log(min(1 - 1e-4, max(1e-4, v)) / (1 - min(1 - 1e-4, max(1e-4, v))))
        scale = lambda v: C.sig(CAL * logit(v))
        steps = []; ps = {}
        for step in g['steps']:
            t = step['turn']
            if t < 1 or not s.weights.get(t): continue
            sp, _ = s.at(log, t); key = (t, json.dumps([x['acts'] for _, x in sp]))
            if key not in s.poscache: s.poscache[key] = positions(sp, os.path.join(OUT, f'{s.tag}_t{t}_acts.jsonl'))
            ps.update(s.poscache[key])
        for step in g['steps']:
            t = step['turn']
            if t < 1 or t not in s.weights: continue
            W = s.weights[t]; names = [n for n in W if n + ' p1' in ev and n + ' p1' in ps]
            if not names: continue
            tot = sum(W[n] for n in names); ws = [W[n] / tot for n in names]
            wp = sum(w * scale(ev[n + ' p1']['value']) for w, n in zip(ws, names))
            opt = B.merge(ws, [B.options(ev[n + ' p1'], ps[n + ' p1'], scale) for n in names])
            state = json.loads(json.dumps(next(x for x in R.parse(s.upto(log, t))['steps'] if x['turn'] == t)['state']))
            for sd in ('p1', 'p2'):
                hy, pool, need = s.hyp[t][sd]
                state[sd]['mons'] = [m for m in state[sd]['mons'] if m['seen']]
                if need and pool:
                    nm = ', '.join(pool[:-1]) + (' or ' if len(pool) > 1 else '') + pool[-1]
                    state[sd]['mons'].append({'n': f"{'one' if need == 1 else need} of {nm}", 'hp': 100, 'st': '', 'f': False, 'b': {}, 'item': '', 'gone': False,
                                              'slot': '', 'seen': False, 'pool': True})
                if not s.bo3:
                    for m in state[sd]['mons']:
                        if not m.get('pool'): m['item'] = ''                 # Bo1: items are unknown unless one activated (shown in the events)
            steps.append({'turn': t, 'wp': wp, 'ev': wp, 'state': state, 'events': step['events'], 'opt': opt, 'hyp': len(names)})
        rating = g['rating']
        game = {'id': s.tag, 'title': 'Live', 'winner': g['winner'], 'forfeit': g['forfeit'], 'perish': g['perish'], 'rating': rating, 'live': True,
                'steps': steps, 'final': {'wp': None if g['winner'] is None else 1.0 if g['winner'] == 'p1' else 0.0, 'state': g['final']}, 'acc': None,
                'engine': {'turns': len(steps), 'seeds': 32, 'staged': True, 'bar': True, 'cal': CAL}}
        d = {'games': [game], 'live': {'url': 'data.json', 'status': s.status, 'format': s.fmt or ('Bo3, open team sheets' if s.bo3 else 'Bo1, closed team sheets')}}
        blob = json.dumps(d, ensure_ascii=False); B.leak_check(blob, [h for h in g['_hidden'] if not re.fullmatch(r'Player [12]', h)])   # the broadcast reader's own labels
        s.data = d
    def leads(s, log):
        out = {'p1': [], 'p2': []}
        for l in log.split('\n'):
            p = l.split('|')
            if len(p) > 3 and p[1] == 'switch' and len(out[p[2][:2]]) < 2: out[p[2][:2]].append(p[3].split(',')[0])
        return out
    def why(s, names):
        """a team sheet that does not list a Pokémon on the field (a misread, or the sheet of another match), or a species the engine lacks"""
        if s.bo3 and any(R.toid(n) not in S.E['species'] for n in names): return 'is not in the engine yet'
        return 'is not on the team sheets as read' if s.bo3 else 'is not in the engine yet'
    def evaluate(s, log, g, step):
        sp, H = s.at(log, step['turn'])
        if not sp:
            s.weights[step['turn']] = {}; s.hyp[step['turn']] = H; s.skip[step['turn']] = H.get('missing', [])
            return s.why(s.skip[step['turn']]) + ': ' + ', '.join(s.skip[step['turn']])
        posf = os.path.join(OUT, f"{s.tag}_t{step['turn']}_pos.jsonl"); positions(sp, posf)
        os.environ['EVAL_TITLE'] = f"Live spectator: turn {step['turn']} ({len(sp)} positions)"
        EN.run(posf, s.evf, s.threads, 32, 1)
        s.weights[step['turn']] = {x['name']: w for w, x in sp}; s.hyp[step['turn']] = H
        return ''
    def run(s):
        class Done:                                                         # a log written by another program: over once it has a result
            def __init__(d, f): d.f = f
            def poll(d): return 0 if os.path.exists(d.f) and '|win|' in open(d.f).read() else None
        feed = Done(s.log) if s.logfile else subprocess.Popen(NODE + [FEED, 'watch', s.room, s.log], stderr=subprocess.PIPE, text=True)
        if s.port: s.serve()
        if s.port: print(f'watching {s.room}: http://localhost:{s.port}  (spectating only; never for a game you are playing)', flush=True)
        seen_len = -1
        while True:
            log = open(s.log).read() if os.path.exists(s.log) else ''
            if '|turn|' not in log:
                s.status = 'waiting for the battle to start' if log else 'connecting'
                if feed.poll() is not None and not s.logfile: print('the feed stopped:', feed.stderr.read().strip()); return
                time.sleep(1); continue
            try: g = R.parse(log)
            except Exception as e: s.status = f'could not read the log ({type(e).__name__})'; time.sleep(1); continue
            todo = [st for st in g['steps'] if st['turn'] >= 1 and st['turn'] not in s.weights]
            if todo:
                step = todo[-1]                                              # the newest turn first; older ones fill in when there is time
                s.status = f"evaluating turn {step['turn']}"; s.build(log, g)
                t0 = time.time(); why = s.evaluate(log, g, step); seen_len = -1
                print(f"turn {step['turn']}: {len(s.weights[step['turn']])} positions in {time.time() - t0:.0f}s" + (f' (skipped: {why})' if why else ''), flush=True)
                continue
            last = g['steps'][-1]['turn']
            status = 'finished' if g['winner'] or feed.poll() is not None else f"turn {last}"
            if s.skip.get(last): status += f" · not evaluated: {', '.join(s.skip[last])} {s.why(s.skip[last])}"
            if len(log) != seen_len or status != s.status:
                s.status = status; s.build(log, g); seen_len = len(log)
            if feed.poll() is not None and not todo and not s.over:
                s.over = True
                if s.port: print(f'battle over; the page stays up at http://localhost:{s.port} until you stop this (Ctrl-C)', flush=True)
            time.sleep(1)
if __name__ == '__main__':
    P.own()
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == 'list':
        k = [x for x in a[1:] if x in FORMATS]; n = 1000 if 'all' in a[1:] else 8
        listing(k[0] if k else None, n)
    elif a[0] == 'watch':
        try: Live(room_of(a[1]), int(a[2]) if len(a) > 2 else 2, int(a[3]) if len(a) > 3 else 8768).run()
        except KeyboardInterrupt: pass
