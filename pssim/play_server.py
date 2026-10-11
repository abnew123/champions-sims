"""Play the planner yourself (2026-10-10). A local page: pick your six (the Trick Room six, or any pool team) and the opponent's six
from the ladder pool, bring four in lead order, then play turn by turn against the planner (champ play: it is side 1, you are side 0,
both sides see everything, as in self-play). The planner runs with the v25 kit setup (sym2 value, DP2, anticipation, free Mega choice).
  ../.venv/bin/python3 play_server.py [port=8765]      then open http://localhost:8765
Needs node + the Showdown engine in pssim/node_modules (battle_starts.js builds the start position) and the champ binary."""
import json, os, sys, subprocess, threading, tempfile, random, shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, HERE)
SM = json.load(open(os.path.join('..', 'regionals', 'smogon_mc_sets.json')))
def spread(species, nature):   # as opp_pool.spread, without that module's imports
    s = SM.get(species) or SM.get(species.split('-')[0])
    if s and s.get('evs'): return s['evs']
    return [32, 32, 0, 0, 2, 0] if nature in ('Adamant', 'Jolly', 'Brave', 'Careful', 'Impish') else [32, 0, 0, 32, 2, 0]
BIN = os.path.join('..', 'native', 'champ', 'bin', 'battlesim-champ'); ENGINE = os.path.join('..', 'native', 'engine_data_full.json')
FLAGS = dict(RACE_TIES='avg', DP2='1', RACE='1', CALC_DATA=os.path.join('..', 'native', 'champions_data.json'), BATTLE_ANTICIPATE='1', TRSYM='1',
             EG_VALUE='egvalue9_sym2.json', EG_MEGA_TIE='0', PLAN_KEEP_IMMUNE='0')   # you may aim at an immune Pokemon (a switch read)
def planner_bring(their_sets, my_sets, rnd):
    """the planner's four and leads against your six, from Team search's bring heuristic (teamsearch/bring: fitted on what Showdown
    M-C Bo3 players brought and led), sampled among the best few (bring, lead) choices so a match does not repeat the same four;
    None when a species is unknown to it (the caller falls back to the pool team's recorded bring)"""
    try:
        for d in ('bring', ''): sys.path.insert(0, os.path.join('..', 'teamsearch', d))
        import feats as Fx, policy as Pol, numpy as np, math
        team = [Fx.canon(x['species']) for x in their_sets]
        if any(g is None for g in team): return None
        opp = [(Fx.canon(x['species']), 1.0) for x in my_sets]; opp = [(g, w) for g, w in opp if g]
        wB, wL, pb, pl = Pol.model(); m = Fx.Matchup(team, opp); sp = [Fx.G[g]['species'] for g in team]
        def lsm(u): u = np.asarray(u, float); return u - (u.max() + math.log(np.exp(u - u.max()).sum()))
        uB = lsm([np.dot(wB, m.bring_feats(S) + [sum(pb.get(sp[i], 0.0) for i in S)]) for S in Fx.BRINGS])
        cands = []
        for b, S in enumerate(Fx.BRINGS):
            Ls = Fx.leads(S); uL = lsm([np.dot(wL, m.lead_feats(Lp, S) + [sum(pl.get(sp[i], 0.0) for i in Lp)]) for Lp in Ls])
            for l, Lp in enumerate(Ls): cands.append((float(uB[b] + uL[l]), Lp, tuple(i for i in S if i not in Lp)))
        cands.sort(key=lambda c: -c[0]); top = cands[:6]
        w = np.exp(np.array([c[0] for c in top]) - top[0][0]); w = w / w.sum()
        v, Lp, back = top[rnd.choices(range(len(top)), weights=w)[0]]
        return [their_sets[i] for i in list(Lp) + list(back)]
    except Exception as e:
        print('planner_bring:', repr(e), flush=True); return None
class Game:
    def __init__(self):
        self.proc = None; self.msg = None; self.waiting = False; self.id = 0; self.log = []; self.tmp = None; self.lock = threading.Lock(); self.err = None
        self.match = None; self.rnd = random.Random(); self.cur = None; self.value = None; self.verdict = None; self.pending_concede = False
        self.store = os.path.join('results', 'play_match.json')   # the match record survives a server restart
        try: self.match = json.load(open(self.store))
        except Exception: self.match = None
    def save(self):
        try: os.makedirs('results', exist_ok=True); json.dump(self.match, open(self.store, 'w'))
        except Exception as e: print('save:', repr(e), flush=True)
    LOG = os.path.join('results', 'play_games.jsonl')   # every finished game, whatever the match: the strength record
    def log_game(self, g):
        try:
            import datetime; os.makedirs('results', exist_ok=True)
            with open(self.LOG, 'a') as f: f.write(json.dumps({'when': datetime.datetime.now().isoformat(timespec='minutes'), 'match': self.match and self.match['key'], **g}) + '\n')
        except Exception as e: print('log:', repr(e), flush=True)
    def record(self):
        """the all-time record from the games log"""
        try: gs = [json.loads(l) for l in open(self.LOG) if l.strip()]
        except Exception: gs = []
        return {'games': len(gs), 'you': sum(1 for g in gs if g.get('winner') == 'you'), 'planner': sum(1 for g in gs if g.get('winner') == 'the planner')}
    def start(self, mine, theirs, match_key=None, their_six=None, my_six=None):
        """mine: your four in lead order; theirs: the planner's four in lead order, or None to let it choose against your six"""
        self.stop(); self.id += 1; self.msg = None; self.log = []; self.err = None; self.waiting = True; self.value = None; self.verdict = None; self.pending_concede = False
        if match_key and self.match and self.match['key'] == match_key: pass
        else: self.match = {'key': match_key, 'games': []} if match_key else None
        if their_six and my_six: theirs = planner_bring(their_six, my_six, self.rnd) or theirs   # its own choice; the recorded bring as the fallback
        if theirs is None and their_six: theirs = their_six[:4]
        self.cur = {'my_four': [x['species'] for x in mine], 'their_four': [x['species'] for x in theirs]}; self.save()
        self.tmp = tempfile.mkdtemp(prefix='battlesim-play-'); os.makedirs(os.path.join(self.tmp, 'grid'), exist_ok=True)
        job = os.path.join(self.tmp, 'job.json'); start = os.path.join(self.tmp, 'start.jsonl')
        json.dump([{'mine': mine, 'theirs': theirs, 'meta': {}}], open(job, 'w'))
        r = subprocess.run(['node', os.path.join('..', 'native', 'battle_starts.js'), job, start, '1'], env={**os.environ, 'SEED_PER_JOB': '1', 'MYTEAM': os.path.join('..', 'native', 'focus_sets_team.json')}, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(start): self.err = 'start failed: ' + (r.stderr or r.stdout)[-800:]; self.waiting = False; return
        env = {**os.environ, **FLAGS, 'GRID_DIR': os.path.join(self.tmp, 'grid')}
        self.proc = subprocess.Popen([BIN, 'play', ENGINE, start], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env, bufsize=1)
        threading.Thread(target=self.reader, args=(self.proc, self.id), daemon=True).start()
    def reader(self, proc, gid):
        for line in proc.stdout:
            line = line.strip()
            if not line.startswith('{'): continue
            try: m = json.loads(line)
            except Exception: continue
            with self.lock:
                if gid != self.id: return
                lt = (m.get('turn') or 1) - 1 if m.get('type') == 'turn' else m.get('turn')   # a turn prompt carries the previous turn's events
                self.log += [(lt, l) for l in m.get('log', [])]; m['log_all'] = self.log
                if 'value' in m: self.value = m.pop('value')   # the planner's view of the turn, never sent to the page
                if m.get('type') == 'verdict':   # the concede check: the planner concedes when its turn value is under 2%, or when it wins (and draws) none of its playouts
                    lost = (1.0 - (m.get('value') or 0.5)) < self.threshold or (m.get('n', 0) > 0 and m.get('planner_wins', 0) == 0 and m.get('draws', 0) == 0)
                    self.verdict = {'conceded': lost}; m['log'] = []
                    if lost: self.pending_concede = True
                    continue
                self.msg = m; self.waiting = False
                if getattr(self, 'pending_concede', False): self.pending_concede = False; threading.Thread(target=self.finish, args=('you', 'the planner conceded'), daemon=True).start()
                if m.get('type') == 'end' and self.match is not None and self.cur:
                    g = {**self.cur, 'winner': m.get('winner'), 'turns': m.get('turn'), **({'how': m['how']} if m.get('how') else {})}
                    self.match['games'].append(g); self.cur = None; self.save(); self.log_game(g)
    def finish(self, winner, how):
        """end the game from the server side: your forfeit, or the planner conceding"""
        with self.lock:
            m = self.msg
            if not m or m.get('type') == 'end' or self.waiting: return False
            end = {'type': 'end', 'turn': m.get('turn'), 'state': m.get('state'), 'winner': winner, 'how': how, 'log_all': self.log}
            self.msg = end
            if self.match is not None and self.cur: g = {**self.cur, 'winner': winner, 'turns': m.get('turn'), 'how': how}; self.match['games'].append(g); self.cur = None; self.save(); self.log_game(g)
        if self.proc:
            try: self.proc.kill()
            except Exception: pass
            self.proc = None
        return True
    threshold = 0.02
    def concede_check(self):
        """ask the engine for its verdict (8 playouts of the planner against itself plus the turn's value); the reader thread applies it"""
        if not self.proc or self.waiting or not self.msg or self.msg.get('type') != 'turn': return {'ok': False, 'reason': 'no position to judge'}
        self.verdict = None; self.waiting = True
        try: self.proc.stdin.write(json.dumps({'check': 'concede'}) + '\n'); self.proc.stdin.flush()
        except Exception as e: self.waiting = False; return {'ok': False, 'reason': str(e)}
        return {'ok': True}
    def choose(self, i):
        if not self.proc or self.waiting or not self.msg or self.msg.get('type') == 'end': return False
        self.waiting = True
        try: self.proc.stdin.write(json.dumps({'choice': int(i)}) + '\n'); self.proc.stdin.flush()
        except Exception as e: self.err = str(e); self.waiting = False; return False
        return True
    def stop(self):
        if self.proc:
            try: self.proc.kill()
            except Exception: pass
        self.proc = None
        if self.tmp: shutil.rmtree(self.tmp, ignore_errors=True); self.tmp = None
G = Game()
def teams():
    mine = json.load(open(os.path.join('..', 'native', 'focus_sets_team.json')))
    out = {'mine': [{'name': 'Trick Room six', 'sets': mine}], 'pool': []}
    pool = json.load(open('opp_pool.json'))['entries']
    good = [e for e in pool if (e.get('rating') or 0) >= 1250 and e.get('bring_seen') == 4 and len(e.get('bring') or []) == 4 and len(e.get('six') or []) == 6]
    rnd = random.Random(17); rnd.shuffle(good)
    for e in good[:600]:
        sets = [{**s, 'evs': spread(s['species'], s['nature'])} for s in e['six']]
        lead = e.get('lead') or e['bring'][:2]; order = list(lead) + [x for x in e['bring'] if x not in lead]
        out['pool'].append({'id': e['id'] + ' ' + e['side'], 'rating': e['rating'], 'arch': e.get('arch'), 'sets': sets, 'bring': order})
    return out
TEAMS = None
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype='application/json'):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        global TEAMS
        if self.path == '/' or self.path.startswith('/?'): self.send(200, open('play_ui.html', 'rb').read(), 'text/html; charset=utf-8')
        elif self.path == '/teams':
            if TEAMS is None: TEAMS = teams()
            self.send(200, TEAMS)
        elif self.path == '/state':
            with G.lock: self.send(200, {'game': G.id, 'waiting': G.waiting, 'msg': G.msg, 'error': G.err, 'match': G.match, 'verdict': getattr(G, 'verdict', None), 'record': G.record()})
        else: self.send(404, {'error': 'no'})
    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0); body = json.loads(self.rfile.read(n) or b'{}')
        if self.path == '/start':
            G.start(body['mine'], body.get('theirs'), body.get('match_key'), body.get('their_six'), body.get('my_six'))
            self.send(200, {'ok': G.err is None, 'error': G.err})
        elif self.path == '/choose': self.send(200, {'ok': G.choose(body.get('i', 0))})
        elif self.path == '/forfeit': self.send(200, {'ok': G.finish('the planner', 'you forfeited')})
        elif self.path == '/concede': self.send(200, G.concede_check())
        elif self.path == '/stop': G.stop(); self.send(200, {'ok': True})
        else: self.send(404, {'error': 'no'})
if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f'play: http://localhost:{port}', flush=True)
    try: ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
    finally: G.stop()
