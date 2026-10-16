"""Live spectator mode: the eval bar on a Showdown battle that is going on now, for watching other people's games. Never use it on a game
you are playing, and never pass what it shows to a player during their game.
  python3 evalbar/live.py list [bo1|bo3] [all]                ongoing Reg M-C battles, 8 of each (all: every one): the highest rated
                                                              Bo1 games, the newest Bo3 games (Bo3 rooms show no rating)
  python3 evalbar/live.py watch <room or battle URL> [threads=2] [port=8768]
                                                              follows the battle and serves the page at http://localhost:<port>
  python3 evalbar/live.py bot [threads=2] [port=8769]       the bot's newest game, then each new one as it starts, on one page
  python3 evalbar/live.py bot <room or battle URL> [threads=2] [port=8769]
                                                              a game of the Showdown bot (bot/), from its own log: the bot's side
                                                              exactly (its requests, its team's spreads), the opponent as a spectator
It knows what a spectator knows at the start of each turn: both team previews, the Bo3 open team sheets (Bo1: each species' most common
Reg M-C set, with what the game has shown laid on top), the Pokemon that have come in and what happened to them. The Pokemon a player has
not sent in yet are averaged over: for each player the TOPK most likely combinations from their preview (back rates given their leads,
recorded.py back_weight), every pairing of the two players' combinations evaluated by the engine (champ evalpos, as engine.py runs it),
values rescaled to real outcomes. The battle log, positions and results stay in evalbar/out/live/ (git-ignored: the log has usernames).
Needs Node with --experimental-websocket (Node 20.10+)."""
import os, sys, json, math, time, re, glob, itertools, subprocess, threading, collections, http.server
import common as C, replay as R, spots as S, recorded as RC, build as B, engine as EN, procs as P, battlestate as BS
toid = R.toid
OUT = os.path.join(C.HERE, 'out', 'live'); FEED = os.path.join(C.HERE, 'live_feed.js')
NODE = [P.exe('node'), '--experimental-websocket', '--no-warnings']
FORMATS = {'bo1': 'gen9championsvgc2026regmc', 'bo3': 'gen9championsvgc2026regmcbo3'}
TOPK = 3; CAL_V25 = 0.7538                       # the rescale fitted for champ-battle-v25 with egvalue9_sym2 (accuracy.py compare)
# the engine the eval bar reads with (the user, 2026-10-13: "lets move both over"): champ-battle-v30 (v29 fixed) with the learned value net, set as the
# bot runs it (Battle sim) but without the bot's own-side rules (EG_LAST_PROTECT, EG_NO_DOUBLE_PROTECT). Its reads go to files named for it
# (<tag>_eval_<ENGINE>.jsonl, _refined_<ENGINE>, _luck_<ENGINE>); earlier engines' (EARLIER) stay readable, each rescaled with its own CAL, until a
# turn is read again, and a turn or luck pass read by one is not read again
ENGINE = 'v34'                                                               # v34 (Battle sim, 2026-10-14): v31 plus the immune-target filter judging a move by its type as used
                                                                             # (v32) and a Mega copy by the Mega's ability (v33): an -ate move into a Ghost, Scrappy Fake Out; 1.25x faster
# each engine's rescale for the bar (accuracy.py compare, 32 seeds staged). v31's and v34's (2026-10-16): Battle sim's rebuild of the 891 hold
# games through today's spots.specs (pssim/results/value2/real_hold.pos.jsonl, 6,381 positions; on the 560 calibration games alone 0.754 and
# 0.758). The rebuilt positions predict better: on the 560 games' 3,968, v31 0.5003 against 0.5172 on the Oct 5 build (-0.0169 +- 0.0049);
# v34 0.4997, -0.0004 +- 0.0003 against v31 on all 6,381. The bar's v31 reads were mostly of positions built this way (live.specs_for, then
# battlestate from 2026-10-14), so they take the new weight
CALS = {'v25': CAL_V25, 'v31': 0.782, 'v34': 0.785}
BAR_CAL = CALS[ENGINE]
EARLIER = [('', CALS['v25']), ('_v31', CALS['v31'])]                         # earlier engines' reads (file suffix, CAL), oldest first: shown with their own CAL until read again
CAL = 0.676                                                                  # the bot's, not the bar's: bot/brain.py, position.py, contempt.py and contempt_bot.py read live.CAL (v31's
                                                                             # on the Oct 5 calibration positions, log loss 0.5186); a change here changes the live bot's play
EVAL_ENV = {'CHAMP_BIN': os.path.join(C.MAIN, 'native', 'champ', 'bin', 'champ-battle-v34'), 'EG_VNET': os.path.join(C.MAIN, 'bot', 'value', 'vnet_h64_search_acc.json'),
            'RACE_PRIO': '1', 'FEATS22': '1', 'EG_MEGA_TIE': '0', 'CALC_DATA': '../native/champions_data_full.json', 'CHAMP_DATA': 'engine_data_full.json'}
# the full engine data (every species, move, item and ability Showdown knows; needs champ-battle-v17 or later): spectated teams can be
# anything. v23 (2026-10-09) gives v17's values wherever v17 handled the turn, and handles more abilities, items and moves (Baton Pass too).
# v25 (the bot's build) also offers a Mega Stone holder's moves without the Mega Evolution, so a player who holds it is not shown as
# having Mega Evolved, with a tie-break toward the Mega when the two are worth the same (EG_MEGA_TIE)
os.environ.setdefault('CHAMP_BIN', os.path.join(C.MAIN, 'native', 'champ', 'bin', 'champ-battle-v25'))
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
                # the likeliest whole set given the other five at team preview and what it has shown (setguess.py): Volcarona runs Quiver
                # Dance on 79% of the Bo3 teams that also have Rillaboom and Basculegion, 47% of all its teams (its most common set is support)
                import setguess as SG, spreads as SPR
                gs = SG.best_set(sp, [x for x in six[sd] if x != sp], {**r, 'ability': r['ability'] if r['ability'] in own else ''})
                if gs:
                    it, nat, mv = R.camel(gs['item']), gs['nature'], [R.camel(m) for m in gs['moves']]
                    rk = SPR.candidates(sp, nat, it)
                    raw = {'species': sp, 'item': it, 'ability': R.camel(gs['ability']), 'nature': nat, 'moves': mv,
                           'evs': list(rk[0][1]) if rk else S.evs_for(sp, it, nat, mv)}
                else:
                    raw = base and {**base, 'moves': list(dict.fromkeys(r['moves'] + base['moves']))[:4], 'item': r['item'] or base['item'],
                                    'ability': r['ability'] if r['ability'] in own else base['ability']}
            st, bad = S.fit_set(raw, dropped) if raw else (None, [sp])
            out[sd][sp] = st
    return six, out, dropped
def hyps(sd, state, six, sets, leads, topk=TOPK):
    """the TOPK most likely sets of Pokemon this player has not sent in yet: [(weight, [species])]"""
    known = {m['sp'] for m in state[sd]['mons']}
    pool = [sp for sp in six[sd] if sp not in known and sets[sd].get(sp)]
    need = max(0, 4 - len(known))
    hy = [(math.prod(RC.back_weight(sp, leads[sd]) for sp in c), list(c)) for c in itertools.combinations(pool, min(need, len(pool)))]
    hy.sort(key=lambda x: -x[0]); hy = hy[:topk]; tot = sum(w for w, _ in hy) or 1
    return [(w / tot, c) for w, c in hy], pool, need
def specs_for(tag, g, step, six, sets, leads, own=None):
    """engine position specs for one turn, one per pairing of the two players' hypotheses: [(weight, spec)]. own: (side, its Pokemon as
    the engine plays them) for a side known exactly (a bot's own side from its request, botpos.own_side): no hypotheses for it"""
    st = step['state']; H = {sd: ([(1.0, [])], [], 0) if own and sd == own[0] else hyps(sd, st, six, sets, leads) for sd in ('p1', 'p2')}; out = []
    order = {sd: BS.order(st[sd]) for sd in ('p1', 'p2')}; acts = BS.acts(step, order)
    bad = [m['sp'] for x in ('p1', 'p2') for m in order[x] if not sets[x].get(m['sp'])]
    if bad: return [], {'missing': sorted(set(bad))}
    for i, (w1, c1) in enumerate(H['p1'][0]):
        for j, (w2, c2) in enumerate(H['p2'][0]):
            sides = [BS.side(st[sd], own[1] if own and sd == own[0] else [BS.mon(m, sets[sd][m['sp']]) for m in order[sd]] + [BS.fresh(sets[sd][sp], True) for sp in extra])
                     for sd, extra in (('p1', c1), ('p2', c2))]
            out.append((w1 * w2, BS.spec(f"{tag} t{step['turn']} h{i}{j}", step, sides, acts, len(c1) + len(c2))))
    return out, H
SLEEP = ((2, 1 / 3), (3, 2 / 3))                                        # Champions: a sleep counter of 2 or 3 (Showdown's champions mod)
def sleep_cases(specs):
    """[(weight, spec)] -> the same with each Pokemon asleep on the field split by its hidden sleep counter: 2 (1/3) or 3 (2/3), less the
    turns it has already slept (Early Bird counts each twice), the cases it would already have woken in left out. sleepStart tells
    positions.js which; a sleeping Pokemon on the bench keeps the likelier 3"""
    out = []
    for w, sp in specs:
        cases = [(w, sp, [])]
        for si, sd in enumerate(sp['sides']):
            for k, m in enumerate(sd['mons']):
                if m.get('status') != 'slp' or not m.get('onField') or m.get('fainted'): continue
                d = 2 if toid(m.get('ability')) == 'earlybird' else 1
                ok = [(n, q) for n, q in SLEEP if n - d * (m.get('slept') or 0) >= 1]
                tot = sum(q for _, q in ok)
                if len(ok) < 2: continue
                cases = [(cw * q / tot, cs, tags + [(si, k, n)]) for cw, cs, tags in cases for n, q in ok]
        for cw, cs, tags in cases:
            if not tags: out.append((cw, cs)); continue
            x = json.loads(json.dumps(cs))
            for si, k, n in tags: x['sides'][si]['mons'][k]['sleepStart'] = n
            x['name'] = cs['name'] + 's' + ''.join(str(n) for _, _, n in tags)
            out.append((cw, x))
    return out
SIDE = re.compile(r'(?<![A-Za-z0-9])p([12])(?=[ab]?(?:[:|,\]"]|$))')
def bot_first(log):
    """a bot's own log with the bot as Player 1: when its requests say it is p2, every side reference (p1, p2a, "id":"p2", ...) is swapped"""
    m = re.search(r'\|request\|\{.*?"side":\{[^{}]*?"id":"(p[12])"', log)
    if not m or m.group(1) == 'p1': return log
    return '\n'.join(SIDE.sub(lambda x: 'p' + ('2' if x.group(1) == '1' else '1'), l) for l in log.split('\n'))
def bot_team(log, sd):
    """the bot's team with its spreads (bot/teams.json, Battle sim's): the one whose six match the bot's team preview"""
    f = os.path.join(C.MAIN, 'bot', 'teams.json')
    if not os.path.exists(f): return None
    six = {toid(l.split('|')[3].split(',')[0]) for l in log.split('\n') if l.startswith(f'|poke|{sd}|')}
    return next((t['sets'] for t in json.load(open(f)) if {toid(x['species']) for x in t['sets']} == six), None)
# the luck pass's engine: evalpos with actual_replace (Battle sim, 2026-10-12), which replays the actual joint choices' cell with the
# Pokemon each player actually sent in after a faint or a pivot (actual_cell), so a replacement choice is not counted as luck
LUCK_BIN = os.path.join(C.MAIN, 'native', 'champ', 'bin', 'champ-dev-2026-10-12c')   # 12c: partly known choices too
def replacements(log, t):
    """{side: [species]} the Pokemon each side sent in during turn t after it began (U-turn, Parting Shot, Eject Button, Emergency Exit) and
    after faints at its end, in the order the log shows them; switches at its start are choices of the turn, drags are not choices"""
    i = log.find(f'\n|turn|{t}\n'); out = {'p1': [], 'p2': []}
    if i < 0: return out
    j = log.find('\n|turn|', i + 1); seg = log[i + 1:j if j > 0 else len(log)].split('\n')
    k = next((n for n, l in enumerate(seg) if l.startswith('|move|') or l == '|upkeep'), len(seg))
    for l in seg[k:]:
        p = l.split('|')
        if len(p) > 3 and p[1] == 'switch' and p[2][:2] in out: out[p[2][:2]].append(p[3].split(',')[0])
    return out
def records(f):
    """an engine output .jsonl -> {name: record}, without errors; a line still being written (the engine appends as it goes) is skipped"""
    out = {}
    if os.path.exists(f):
        for l in open(f):
            try: x = json.loads(l)
            except ValueError: continue
            if 'error' not in x: out[x['name']] = x
    return out
def positions(specs, outf):
    tmp = outf + '.specs.json'; json.dump([s for _, s in specs], open(tmp, 'w'))
    subprocess.run([P.exe('node'), os.path.join(C.HERE, 'positions.js'), os.path.abspath(tmp), os.path.abspath(outf), 'p1'], cwd=os.path.join(C.MAIN, 'pssim'),
                   check=True, capture_output=True)
    os.remove(tmp)
    return {x['name']: x for x in map(json.loads, open(outf))}
# A broadcast's games each have a Live in one process (broadcast.py's Runner): one of them builds or evaluates at a time, so a page
# rebuilt from a record (a restart, serve) runs one engine with `threads` workers, not one per game
WORK = threading.Lock()
LUCK = threading.Lock()                                                  # the luck passes, one game at a time
class Live:
    def __init__(s, room, threads, port, logfile=None, tag=None, fmt=None):
        """room: a Showdown battle room (followed through live_feed.js); or logfile: a battle log another program writes (the broadcast
        reader), with tag naming the outputs and fmt the format line on the page"""
        s.room = room; s.logfile = logfile; s.fmt = fmt
        s.tag = tag or (room.split('-')[-1] if not re.search(r'-\d+-[a-z0-9]+$', room) else room.split('-')[-2])
        s.bo3 = 'bo3' in room if room else logfile is not None; s.threads = threads; s.port = port; os.makedirs(OUT, exist_ok=True)
        s.log = logfile or os.path.join(OUT, f'{s.tag}.log'); s.evf = os.path.join(OUT, f'{s.tag}_eval_{ENGINE}.jsonl'); s.data = None; s.status = 'connecting'
        s.prior = [{k: os.path.join(OUT, f'{s.tag}_{k}{x}.jsonl') for k in ('eval', 'refined', 'luck')} | {'cal': c} for x, c in EARLIER]   # earlier engines' reads
        s.weights = {}; s.hyp = {}; s.poscache = {}; s.over = False; s.skip = {}
        s.exact = False; s.team = None; s.back = {}; s.bot_side = None; s.held = None; s.spread_why = {}
        s.luck = False; s.lf = os.path.join(OUT, f'{s.tag}_luck_{ENGINE}.jsonl'); s.luck_state = None; s.lweights = {}; s.dirty = False; s.page_cache = None
        s.rf = os.path.join(OUT, f'{s.tag}_refined_{ENGINE}.jsonl'); s.live_seeds = 32; s.refining = False; s.saved = False   # the two reads (2026-10-13)   # luck: after the game      # a Showdown bot's own log (bot/): its side known from its requests
        # the user's verdicts where the battle text and the rules disagree (broadcasts: evalbar/rules.py), kept beside the log
        s.fixf = os.path.join(OUT, f'{s.tag}_fixes.json'); s.fixes = json.load(open(s.fixf)) if logfile and os.path.exists(s.fixf) else {}; s.redo = None
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
    def with_fixes(s, log):
        """the log with the corrections the user chose (the rules' version) put in just before the turns they belong to"""
        if not s.fixes: return log
        out = []
        for l in log.split('\n'):
            if l.startswith('|turn|'):
                for f in s.fixes.get(l.split('|')[2], {}).values():
                    if f['choice'] == 'rules': out.extend(f['lines'])
            out.append(l)
        return '\n'.join(out)
    def add_fix(s, turn, key, choice, check):
        """the user's verdict on a check: 'messages', 'rules', or 'none' to take it back"""
        if choice == 'none':
            s.fixes.get(str(turn), {}).pop(key, None)
            if not s.fixes.get(str(turn)): s.fixes.pop(str(turn), None)
        else: s.fixes.setdefault(str(turn), {})[key] = {'choice': choice, 'lines': check.get('fix', []), 'what': check['what'], 'messages': check['messages'], 'rules': check['rules']}
        json.dump(s.fixes, open(s.fixf, 'w'), indent=1); s.redo = min(s.redo or 10 ** 6, int(turn))
    def checks(s, log):
        """{turn: [check]}: where the battle text and the rules disagree (log: with the user's corrections), with the user's verdicts"""
        if not s.logfile or not s.bo3 or s.exact: return {}                           # the rules need the team sheets' abilities and items
        import rules as RU
        try: found = RU.compare(log)
        except Exception: return {}
        out = {}
        for t, cs in found.items():
            for c in cs: out.setdefault(t, []).append({**c, 'choice': (s.fixes.get(str(t), {}).get(c['key']) or {}).get('choice')})
        for t, fx in s.fixes.items():                                      # settled ones that no longer show as disagreements
            for key, f in fx.items():
                if not any(c['key'] == key for c in out.get(int(t), [])):
                    out.setdefault(int(t), []).append({'key': key, 'what': f['what'], 'messages': f['messages'], 'rules': f['rules'], 'fix': f['lines'], 'choice': f['choice']})
        return out
    def redo_from(s, t0):
        """a correction at turn t0: that turn and the later ones are evaluated again"""
        for t in [t for t in s.weights if t >= t0]: s.weights.pop(t, None); s.hyp.pop(t, None)
        s.poscache = {k: v for k, v in s.poscache.items() if k[0] < t0}
        with LUCK:                                                           # a background read under way ends first; its turns go too
            for f in [s.evf, s.rf] + [p[k] for p in s.prior for k in ('eval', 'refined')]:
                if os.path.exists(f):
                    keep = [l for l in open(f) if int((re.search(r' t(\d+) ', json.loads(l).get('name', '')) or [0, 0])[1]) < t0]
                    open(f, 'w').writelines(keep)
    @staticmethod
    def upto(log, t):
        """the log as a spectator had it when turn t started"""
        i = log.find(f'\n|turn|{t}\n'); return log if i < 0 else log[:i + len(f'\n|turn|{t}\n')]
    def at(s, log, t, hindsight=False):
        """engine position specs for turn t, from what was known when it started; the choices made in it (known once it is over) filled in.
        hindsight (the luck pass): each player's Pokemon and the opponent's spreads as the whole game showed them, so that luck counts the
        dice (rolls, crits, accuracy, speed ties, added effects), not what was hidden at the time (the user, 2026-10-12: Game 24's Charizard
        survived a Sucker Punch the guessed spread could not). Names get ' L' after the tag"""
        pre = s.upto(log, t); gp = R.parse(pre); step = next(x for x in gp['steps'] if x['turn'] == t)
        full = R.parse(log); later = next((x for x in full['steps'] if x['turn'] == t), step); step = {**step, 'acts': later['acts']}
        rq0 = s.request(log, t) if '|bot-choice|' in log else None
        if rq0:                                                             # the bot's own choice where the log shows it only in part
            acts = dict(step['acts'])
            for pos, a in s.choice(log, t, rq0).items():
                old = acts.get(pos)
                if not old or old.get('none') or ('move' in old and not old.get('target') and a.get('move') == old.get('move')) or not ('move' in old or 'switch' in old): acts[pos] = a
            step = {**step, 'acts': acts}
        src, gsrc = pre, gp
        if hindsight and later is not step:
            st = json.loads(json.dumps(step['state']))
            for sd in ('p1', 'p2'): st[sd] = later['state'][sd]               # all four each brought ('seen': False for those not in yet)
            step = {**step, 'state': st}; src, gsrc = log, full
        six, sets, dropped = sets_for(gsrc, src, s.bo3); own = None
        rq = s.request(log, t) if '|request|' in log else None
        if rq:                                                              # a bot's own log: its side as its request shows it, no guessing
            import botpos as BP
            sd = rq['side']['id']; s.bot_side = sd
            if s.team is None: s.team = bot_team(pre, sd)
            mons, why = BP.own_side(step['state'][sd], sets[sd], rq, BP.team_sets(s.team), dropped, slots=True)
            why_sp = BP.refine_opponent(src, gsrc, sets, sd, rq, strict=3)   # the opponent's spreads against the turn order seen so far
            if not hindsight: s.spread_why[t] = why_sp
            if mons:
                own = (sd, mons); seen = {toid(m['sp'].split('-')[0]) for m in step['state'][sd]['mons']}
                s.back[t] = [r['details'].split(',')[0] for r in rq['side']['pokemon'] if toid(r['details'].split(',')[0].split('-')[0]) not in seen]
        sp, H = specs_for(s.tag + (' L' if hindsight else ''), gp, step, six, sets, s.leads(pre), own)
        if hindsight:                                                       # the replacements each player chose in the turn (actual_replace)
            rep = replacements(log, t)
            for _, x in sp: x['replace'] = rep
        return sleep_cases(sp), H
    @staticmethod
    def choice(log, t, rq):
        """what the bot chose at the start of turn t, from the |bot-choice|<rqid>|<choice> line its client writes after answering a request
        (bot/client.js, from 2026-10-12): {'p1a': act, ...} in replay.py's act format, its own side ('p1' once bot_first has run); {} if
        the log has no such line (older games, or 'default' / 'forfeit')"""
        m = re.search(r'\n\|bot-choice\|' + str(rq.get('rqid')) + r'\|([^\n]*)', log)
        if not m or not rq.get('active'): return {}
        sd = rq['side']['id']; foe = 'p2' if sd == 'p1' else 'p1'; out = {}
        for i, part in enumerate(m.group(1).split(',')[:len(rq['active'])]):
            w = part.split()
            if not w or w[0] in ('default', 'forfeit', 'pass'): continue
            if w[0] == 'switch' and len(w) > 1 and w[1].isdigit():
                out[sd + 'ab'[i]] = {'switch': rq['side']['pokemon'][int(w[1]) - 1]['details'].split(',')[0]}
            elif w[0] == 'move' and len(w) > 1 and w[1].isdigit():
                mv = (rq['active'][i].get('moves') or [{}])[int(w[1]) - 1]; t_ = next((x for x in w[2:] if re.fullmatch(r'-?[12]', x)), None)
                tgt = '' if t_ is None else (foe + 'ab'[int(t_) - 1] if int(t_) > 0 else sd + 'ab'[-int(t_) - 1])
                out[sd + 'ab'[i]] = {'move': mv.get('move', ''), 'target': tgt, 'mega': 'mega' in w[2:], 'unsure': False}
        return out
    @staticmethod
    def request(log, t):
        """a bot's own log, which records its |request|s: the one it answered at the start of turn t (logged just after the |turn| line)"""
        i = log.find(f'\n|turn|{t}\n')
        if i < 0: return None
        j = log.find('\n|turn|', i + 1)
        for l in log[i:j if j > 0 else len(log)].split('\n'):
            if l.startswith('|request|') and l[9:].strip():
                try: rq = json.loads(l[9:])
                except ValueError: continue                                  # read while the bot was rewriting the file
                if rq.get('side') and not (rq.get('forceSwitch') or rq.get('wait') or rq.get('teamPreview')): return rq
        return None
    def build(s, log, g):
        """the page's data from everything evaluated so far"""
        # each name's read: the background one (REFINE_SEEDS) where it is done, else the quick one; this engine's, else the newest earlier
        # engine's from before a switch, each rescaled with its own engine's CAL
        logit = lambda v: math.log(min(1 - 1e-4, max(1e-4, v)) / (1 - min(1 - 1e-4, max(1e-4, v))))
        ev, cal, rv = {}, {}, set()
        for p in s.prior + [{'eval': s.evf, 'refined': s.rf, 'cal': BAR_CAL}]:
            for k in ('eval', 'refined'):
                for n, x in records(p[k]).items():
                    ev[n] = x; cal[n] = p['cal']; (rv.add if k == 'refined' else rv.discard)(n)
        sc = lambda n: (lambda v: C.sig(cal[n] * logit(v)))
        lucks = [(records(s.lf), BAR_CAL)] + [(records(p['luck']), p['cal']) for p in reversed(s.prior)]   # the luck pass: this engine's, else the newest earlier one
        steps = []; ps = {}; CH = s.checks(log); lps = {}
        for t in s.lweights: lps.update(records(os.path.join(OUT, f'{s.tag}_t{t}_luckpos.jsonl')))
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
            wp = sum(w * sc(n + ' p1')(ev[n + ' p1']['value']) for w, n in zip(ws, names))
            opt = B.merge(ws, [B.options(ev[n + ' p1'], ps[n + ' p1'], sc(n + ' p1')) for n in names])
            state = json.loads(json.dumps(next(x for x in R.parse(s.upto(log, t))['steps'] if x['turn'] == t)['state']))
            for sd in ('p1', 'p2'):
                hy, pool, need = s.hyp[t][sd]
                state[sd]['mons'] = [m for m in state[sd]['mons'] if m['seen']]
                if sd == s.bot_side and s.back.get(t):                          # the bot's own back row, from its request
                    nm = ', '.join(s.back[t][:-1]) + (' and ' if len(s.back[t]) > 1 else '') + s.back[t][-1]
                    state[sd]['mons'].append({'n': f'in the back: {nm}', 'hp': 100, 'st': '', 'f': False, 'b': {}, 'item': '', 'gone': False, 'slot': '', 'seen': False, 'pool': True})
                if need and pool:
                    nm = ', '.join(pool[:-1]) + (' or ' if len(pool) > 1 else '') + pool[-1]
                    state[sd]['mons'].append({'n': f"{'one' if need == 1 else need} of {nm}", 'hp': 100, 'st': '', 'f': False, 'b': {}, 'item': '', 'gone': False,
                                              'slot': '', 'seen': False, 'pool': True})
                if not s.bo3 and sd != s.bot_side:                             # (the bot knows its own items)
                    for m in state[sd]['mons']:
                        if not m.get('pool'): m['item'] = ''                 # Bo1: items are unknown unless one activated (shown in the events)
            ex = [(w, B.expected(ev[n + ' p1'], ps[n + ' p1']), sc(n + ' p1')) for w, n in zip(ws, names)]; ex = [(w, f(x)) for w, x, f in ex if x is not None]
            after = sum(w * sc(n + ' p1')(ev[n + ' p1']['static']) for w, n in zip(ws, names))   # the value function here, no lookahead
            LW = s.lweights.get(t) or {}
            lev, lc = next(((L, c) for L, c in lucks if LW and all(n in L for n in LW)), lucks[0])
            lscale = lambda v: C.sig(lc * logit(v))
            if LW and all(n in lev and n in lps for n in LW):                  # the luck pass, in hindsight: both from its own positions
                ex = [(w, lev[n]['actual_cell']['v'] if lev[n].get('actual_cell') else B.expected(lev[n], lps[n])) for n, w in LW.items()]   # actual_cell: with the
                ex = [(w, lscale(x)) for w, x in ex if x is not None]           # replacements made (choices all known); else the matrix's cells
                after = sum(w * lscale(lev[n]['static']) for n, w in LW.items()) / sum(LW.values())
            steps.append({'turn': t, 'wp': wp, 'ev': wp, 'state': state, 'events': step['events'], 'opt': opt, 'hyp': len(names), 'checks': CH.get(t, []),
                          'tier': 'refined' if all(n + ' p1' in rv for n in names) else 'quick',
                          'expected': sum(w * x for w, x in ex) / sum(w for w, _ in ex) if ex else None, 'after': after})
        # luck (the user's idea, 2026-10-11): the turn's outcome against what the choices both sides made were expected to give, both
        # with the value function before any lookahead: the next turn's start, or the result after the last turn (not a forfeit)
        for i, st in enumerate(steps):
            nxt = steps[i + 1] if i + 1 < len(steps) and steps[i + 1]['turn'] == st['turn'] + 1 else None
            end = None if g['forfeit'] or not g['winner'] or nxt or st['turn'] != g['steps'][-1]['turn'] else (1.0 if g['winner'] == 'p1' else 0.0)
            post = nxt['after'] if nxt else end
            st['luck'] = None if post is None or st['expected'] is None else post - st['expected']
        for st in steps: st.pop('after', None)
        lk = [st['luck'] for st in steps if st['luck'] is not None]
        rating = g['rating']
        game = {'id': s.tag, 'title': 'Live', 'winner': g['winner'], 'forfeit': g['forfeit'], 'perish': g['perish'], 'rating': rating, 'live': True,
                'steps': steps, 'final': {'wp': None if g['winner'] is None else 1.0 if g['winner'] == 'p1' else 0.0, 'state': g['final']}, 'acc': None,
                'engine': {'turns': len(steps), 'seeds': 32, 'staged': True, 'bar': True, 'cal': BAR_CAL},
                'luck': {'p1': sum(lk), 'turns': len(lk)} if lk and s.luck_state == 'done' else None}
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
    def luck_pass(s, log, turns):
        """after the game, for reviews: each turn again with the payoff table (evalpos EVAL_MATRIX), one engine thread at the lowest priority
        and one game at a time, apart from the live evaluation's lock, so a game going on is not slowed"""
        for t in turns:
            posf = os.path.join(OUT, f'{s.tag}_t{t}_luckpos.jsonl')         # with the choices made: their cells get every sample, and each
            sp = s.at(log, t, hindsight=True)[0]; s.lweights[t] = {x['name'] + ' p1': w for w, x in sp}
            if os.path.exists(posf) and any(all(n in records(p['luck']) for n in s.lweights[t]) for p in s.prior): continue   # an earlier engine's: kept
            positions(sp, posf)                                              # side's actual_v (what its choice cost) comes out
            with LUCK: EN.run(posf, s.lf, 1, 32, 1, extra={**EVAL_ENV, 'EVAL_MATRIX': '1'}, nice=19)
            s.dirty = True
        s.dirty = True; s.luck_state = 'done'                                # dirty first: the run loop saves a finished page only once it is rebuilt with the luck
        if s.tag.startswith('bot_'):                                        # the bot page's progress card: one line per game whose luck is done
            with open(os.path.join(OUT, 'bot_luck.games'), 'a') as fh: fh.write(s.tag + '\n')
    def evaluate(s, log, g, step):
        sp, H = s.at(log, step['turn'])
        if not sp:
            s.weights[step['turn']] = {}; s.hyp[step['turn']] = H; s.skip[step['turn']] = H.get('missing', [])
            return s.why(s.skip[step['turn']]) + ': ' + ', '.join(s.skip[step['turn']])
        posf = os.path.join(OUT, f"{s.tag}_t{step['turn']}_pos.jsonl")
        os.environ['EVAL_TITLE'] = f"Live spectator: turn {step['turn']} ({len(sp)} positions)"
        have = set(records(s.rf)) | set(records(s.evf)) | {n for p in s.prior for k in ('eval', 'refined') for n in records(p[k])}
        read = all(x['name'] + ' p1' in have for _, x in sp)                 # a turn read before is not read again (a page rebuilt after a switch
        if not read or not os.path.exists(posf): positions(sp, posf)          # keeps its positions file too)
        if not read: EN.run(posf, s.evf, s.threads, s.live_seeds, 1, extra=EVAL_ENV)
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
            if s.redo is not None: t0, s.redo = s.redo, None; s.redo_from(t0)
            log = s.with_fixes(open(s.log).read()) if os.path.exists(s.log) else ''
            if s.exact: log = bot_first(log)                                 # the bot on the left, as Player 1
            if '|turn|' not in log:
                s.status = 'waiting for the battle to start' if log else 'connecting'
                if feed.poll() is not None and not s.logfile: print('the feed stopped:', feed.stderr.read().strip()); return
                time.sleep(1); continue
            try: g = R.parse(log)
            except Exception as e: s.status = f'could not read the log ({type(e).__name__})'; time.sleep(1); continue
            todo = [st for st in g['steps'] if st['turn'] >= 1 and st['turn'] not in s.weights]
            if todo and s.exact and not g['winner'] and todo[-1]['turn'] == g['steps'][-1]['turn'] and not s.request(log, todo[-1]['turn']):
                s.held = s.held or time.time()                               # the bot logs a turn's request just after its |turn| line
                if time.time() - s.held < 15: time.sleep(1); continue
            s.held = None
            if todo:
                step = todo[-1]                                              # the newest turn first; older ones fill in when there is time
                s.status = f"evaluating turn {step['turn']}"
                with WORK: s.build(log, g); t0 = time.time(); why = s.evaluate(log, g, step)
                seen_len = -1
                print(f"turn {step['turn']}: {len(s.weights[step['turn']])} positions in {time.time() - t0:.0f}s" + (f' (skipped: {why})' if why else ''), flush=True)
                continue
            last = g['steps'][-1]['turn']
            status = 'finished' if g['winner'] or feed.poll() is not None else f"turn {last}"
            if s.luck and status == 'finished' and s.luck_state is None:
                s.luck_state = 'running'; threading.Thread(target=s.luck_pass, args=(log, sorted(t for t, w in s.weights.items() if w)), daemon=True).start()
            if s.skip.get(last): status += f" · not evaluated: {', '.join(s.skip[last])} {s.why(s.skip[last])}"
            if len(log) != seen_len or status != s.status or s.dirty:
                s.status = status; s.dirty = False
                with WORK: s.build(log, g)
                seen_len = len(log)
            if s.page_cache and status == 'finished' and not todo and (not s.luck or s.luck_state == 'done') and not s.dirty:
                tmp = s.page_cache + '.tmp'; json.dump({'v': PAGE_V, 'data': s.data, 'refined': ENGINE if s.refining else False}, open(tmp, 'w'), ensure_ascii=False); os.replace(tmp, s.page_cache)
                s.saved = True; return                                                       # the bot page: a finished game is read from its file from now on
            if feed.poll() is not None and not todo and not s.over:
                s.over = True
                if s.port: print(f'battle over; the page stays up at http://localhost:{s.port} until you stop this (Ctrl-C)', flush=True)
            time.sleep(1)
# the bot page's finished games are saved as their pages (out/live/bot_<n>_page.json) once evaluated and their luck worked out, so a restart
# reads them instead of rebuilding every turn (about an hour for 400 games). PAGE_V: raise it when a change should rebuild them all
PAGE_V = 2                                                                   # 2: the v34 switch (2026-10-16), every saved page rescaled with its reads' CAL
# two reads (the user, 2026-10-13: "run a fast version for live, then rerun a slower version in the background"): the bot page reads each turn
# quickly as it is played (LIVE_SEEDS), and a background pass reads every saved game again (REFINE_SEEDS, newest first, one engine thread at
# the lowest priority, sharing the luck pass's) and saves its page again; the page marks turns still on the quick read. The engine's budgeted
# search (Battle sim's planner_issues 18) will replace the seed counts with budgets and a per-position uncertainty
LIVE_SEEDS, REFINE_SEEDS = 8, 128
# the bot page's background read is off (the user, 2026-10-14: hundreds of games re-read take longer than an engine version lasts); its games
# are read once, at the full 32 rolls, and the page shows no "quick read" note. Streams keep both reads (a stream day is about 3 hours of it)
BOT_REFINE = False
BUSY = 9.0                                                                   # the background read waits while everything else keeps this many cores busy
def others_busy():
    """cores busy outside this program's process group (its engines included), ps's recent CPU share summed, as auto.py counts them"""
    tot, me = 0.0, os.getpgrp()
    for l in subprocess.run(['ps', '-Aeo', 'pgid=,pcpu='], capture_output=True, text=True).stdout.splitlines():
        p = l.split()
        try:
            if len(p) == 2 and int(p[0]) != me: tot += float(p[1])
        except ValueError: pass
    return tot / 100
class Finished:
    """a finished bot game read from its saved page: what BotRunner.serve needs of a Live"""
    def __init__(s, room, fmt, data, refined=False): s.room, s.fmt, s.data, s.status, s.refined = room, fmt, data, 'finished', refined
def evalbar_mode():
    """the eval bar's own reading, switched on by its programs' entry points (live.py, broadcast.py for the streams, reach.py), never by the
    bot's, which makes its own choices: the fitted default spreads and the damage check's positions with the same positions.js fixes as the
    rest (battlestate.FLAGS). The parser's fixes (Baton Pass, a Mega ending a traced ability) are on by default for every reader since
    2026-10-14; set here too for older code. The streams had none of these until 2026-10-14 (broadcast.py's entry point never set them)"""
    import spreads, battlestate as BS
    R.BATON_PASS = R.MEGA_ABIL = True; spreads.FITTED = True; spreads.DMG_FLAGS = dict(BS.FLAGS)
def botfmt(room):
    """the bot page's format line: its Bo1 games (since 2026-10-12) have no team sheets, so the opponent's sets are guessed as a spectator's"""
    return ('Bo3, open team sheets' if 'bo3' in room else 'Bo1, closed team sheets') + ' · the bot is Player 1, its side from its own log'
class BotRunner:
    """the Showdown bot's games (bot/out/ in the main checkout) on one page: every ladder game so far when this starts, then each game it
    starts, as it plays it. The page moves on to a new game when it is showing the latest one."""
    def __init__(s, threads, port):
        s.dir = os.path.join(C.MAIN, 'bot', 'out'); s.threads = threads; s.port = port; s.lives = []; s.files = []; s.known = set(); s._when = (None, {})
    def when(s, room):
        """when the bot played this room (bot/out/games.jsonl, UTC), for the game list (the user, 2026-10-14: a game found by its time)"""
        f = os.path.join(s.dir, 'games.jsonl'); m = os.path.getmtime(f) if os.path.exists(f) else None
        if m != s._when[0]:
            w = {}
            for l in open(f) if m else []:
                try: x = json.loads(l); w[x['room']] = x.get('when')
                except Exception: pass
            s._when = (m, w)
        return s._when[1].get(room) or s._when[1].get(re.sub(r'-[a-z0-9]+$', '', room) if room.count('-') > 2 else room)
    def serve(s):
        run = s
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                p = self.path.split('?')[0]
                if p == '/data.json':
                    games = []
                    for i, lv in enumerate(run.lives):
                        if lv.data and lv.data['games']:
                            games.append({**lv.data['games'][0], 'title': f'Game {i + 1}', 'idx': i, 'versus': f'Game {i + 1}',
                                          'group': 'Bo3' if 'bo3' in lv.room else 'Bo1', 'format': lv.fmt, 'refines': BOT_REFINE, 'when': run.when(lv.room)})   # the page's format toggle and game list (the user, 2026-10-13)
                    last = run.lives[-1] if run.lives else None
                    st = "waiting for the bot's next game" if not last or last.status == 'finished' else last.status
                    b = json.dumps({'games': games, 'live': {'url': 'data.json', 'status': st, 'format': last.fmt if last else botfmt('')}}).encode()
                    ct = 'application/json'
                elif p in ('/', '/index.html'): b = Live.page(None).encode(); ct = 'text/html; charset=utf-8'
                else: self.send_error(404); return
                self.send_response(200); self.send_header('Content-Type', ct); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(b)
            def log_message(self, *a): pass
        threading.Thread(target=http.server.ThreadingHTTPServer(('127.0.0.1', s.port), H).serve_forever, daemon=True).start()
    def refine(s):
        """the background read: the newest saved game not yet refined gets every turn's positions read again at REFINE_SEEDS, then its page
        is rebuilt from them (a Live on its cached files, in this thread) and saved again with refined set"""
        prog = os.path.join(OUT, 'bot_refined.games'); shown = None; t0 = time.time()
        while not s.lives: time.sleep(5)
        while True:
            done = [re.search(r'-(\d+)(?:-[a-z0-9]+)?$', lv.room).group(1) for lv in list(s.lives) if isinstance(lv, Finished) and lv.refined == ENGINE]
            if (len(done), len(s.lives)) != shown:                         # the card: games read again (from earlier runs too) of all games loaded
                open(prog, 'w').writelines(x + '\n' for x in done)
                if shown is None: d0 = len(done)
                json.dump({'title': f"The bot's games: read again at {REFINE_SEEDS} rolls (games, up to 3 engine threads at the lowest priority)",
                           'out': os.path.relpath(prog, os.path.join(C.HERE, 'out')), 'total': len(s.lives), 'done0': d0, 'started': t0, 'threads': 3,
                           'seeds': REFINE_SEEDS, 'staged': True, 'pid': os.getpid(), 'unit': 'games'}, open(prog + '.run.json', 'w')); shown = (len(done), len(s.lives))   # pid: running while this page is
            todo = [i for i, lv in enumerate(s.lives) if (isinstance(lv, Finished) and lv.refined != ENGINE) or (isinstance(lv, Live) and lv.saved and not lv.refining)]
            if not todo: time.sleep(30); continue
            i = todo[-1]; old = s.lives[i]; num = re.search(r'-(\d+)(?:-[a-z0-9]+)?$', old.room).group(1); tag = 'bot_' + num
            rf = os.path.join(OUT, f'{tag}_refined_{ENGINE}.jsonl')
            for posf in sorted(glob.glob(os.path.join(OUT, f'{tag}_t*_pos.jsonl')), key=lambda f: -int(re.search(r'_t(\d+)_pos', f).group(1))):
                while (busy := others_busy()) >= BUSY: time.sleep(30)         # the lowest-priority work on the Mac: it waits under the 10-core cap,
                thr = 3 if busy < 5 else 2 if busy < 7 else 1                  # and takes more threads when the Mac is quiet
                with LUCK: EN.run(posf, rf, thr, REFINE_SEEDS, 1, extra=EVAL_ENV, nice=19)
            f = os.path.join(s.dir, old.room + '.log'); pc = os.path.join(OUT, f'{tag}_page.json')
            lv = Live(old.room, s.threads, 0, logfile=f, tag=tag, fmt=botfmt(old.room)); lv.page_cache = pc; lv.exact = True; lv.luck = True; lv.refining = True
            lv.run()                                                         # the old page stays up until the rebuilt one replaces it
            s.lives[i] = Finished(old.room, botfmt(old.room), lv.data, ENGINE)
    def run(s):
        s.serve(); print(f"the bot's games: http://localhost:{s.port}", flush=True)
        if BOT_REFINE and os.environ.get('EVALBAR_REFINE', '1') == '1': threading.Thread(target=s.refine, daemon=True).start()   # =0: none (a CAL refit pending)
        # a progress card on the shared status page (status.py): the bot's games whose luck is worked out, of all its ladder games
        prog = os.path.join(OUT, 'bot_luck.games'); open(prog, 'w').close()
        n = len([f for f in glob.glob(os.path.join(s.dir, 'battle-*.log')) if re.search(r'-\d{6,}(-[a-z0-9]+)?\.log$', f)])
        json.dump({'title': "The bot's games: luck worked out (games, one engine thread at the lowest priority)", 'out': os.path.relpath(prog, os.path.join(C.HERE, 'out')),
                   'total': n, 'done0': 0, 'started': time.time(), 'threads': 1, 'seeds': 32, 'staged': True, 'pid': os.getpid(), 'unit': 'games'}, open(prog + '.run.json', 'w'))
        while True:
            fs = sorted((f for f in glob.glob(os.path.join(s.dir, 'battle-*.log')) if re.search(r'-\d{6,}(-[a-z0-9]+)?\.log$', f)),
                        key=lambda f: int(re.search(r'-(\d{6,})(?:-[a-z0-9]+)?\.log$', f).group(1)))   # ladder rooms, not local test games; by battle number,
            # which keeps each game's number (by modification time a log touched after its game moved, 2026-10-13)
            if not s.files and not s.known: new = fs; s.known = set(fs)         # at the start: every ladder game so far, for reviews
            else: new = [f for f in fs if f not in s.known]; s.known |= set(new)
            for f in new:
                room = os.path.basename(f)[:-4]; num = re.search(r'-(\d+)(?:-[a-z0-9]+)?$', room).group(1); s.files.append(f)
                pc = os.path.join(OUT, f'bot_{num}_page.json'); c = None
                if os.path.exists(pc):
                    try: c = json.load(open(pc))
                    except Exception: c = None
                if c and c.get('v') == PAGE_V:                               # a finished game: its page as saved, no thread (2026-10-13)
                    s.lives.append(Finished(room, botfmt(room), c['data'], c.get('refined', False)))
                    with open(os.path.join(OUT, 'bot_luck.games'), 'a') as fh: fh.write('bot_' + num + '\n')   # its luck is worked out (the card)
                    continue
                lv = Live(room, s.threads, 0, logfile=f, tag='bot_' + num, fmt=botfmt(room)); lv.page_cache = pc; lv.live_seeds = LIVE_SEEDS if BOT_REFINE else 32
                lv.exact = True; lv.luck = True; s.lives.append(lv); threading.Thread(target=lv.run, daemon=True).start()
                print(time.strftime('%-I:%M %p'), 'following the bot\'s game', num, flush=True)
            time.sleep(5)
if __name__ == '__main__':
    P.own(); evalbar_mode()
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == 'list':
        k = [x for x in a[1:] if x in FORMATS]; n = 1000 if 'all' in a[1:] else 8
        listing(k[0] if k else None, n)
    elif a[0] == 'bot' and not (len(a) > 1 and 'battle-' in a[1]):          # every game the bot plays from now on, on one page
        try: BotRunner(int(a[1]) if len(a) > 1 else 2, int(a[2]) if len(a) > 2 else 8769).run()
        except KeyboardInterrupt: pass
    elif a[0] == 'bot':
        # a game the Showdown bot (bot/) plays or played, from its own log in the main checkout's bot/out/: its side as it knows it
        room = room_of(a[1]); f = os.path.join(C.MAIN, 'bot', 'out', room + '.log')
        L = Live(room, int(a[2]) if len(a) > 2 else 2, int(a[3]) if len(a) > 3 else 8769, logfile=f, tag='bot_' + re.search(r'-(\d+)(?:-[a-z0-9]+)?$', room).group(1),
                 fmt=botfmt(room))
        L.exact = True; L.luck = True
        try: L.run()
        except KeyboardInterrupt: pass
    elif a[0] == 'watch':
        try: Live(room_of(a[1]), int(a[2]) if len(a) > 2 else 2, int(a[3]) if len(a) > 3 else 8768).run()
        except KeyboardInterrupt: pass
