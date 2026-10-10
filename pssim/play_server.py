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
             EG_VALUE='egvalue9_sym2.json', EG_MEGA_TIE='0')
class Game:
    def __init__(self):
        self.proc = None; self.msg = None; self.waiting = False; self.id = 0; self.log = []; self.tmp = None; self.lock = threading.Lock(); self.err = None
    def start(self, mine, theirs):
        self.stop(); self.id += 1; self.msg = None; self.log = []; self.err = None; self.waiting = True
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
                self.log += [(lt, l) for l in m.get('log', [])]; m['log_all'] = self.log; self.msg = m; self.waiting = False
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
            with G.lock: self.send(200, {'game': G.id, 'waiting': G.waiting, 'msg': G.msg, 'error': G.err})
        else: self.send(404, {'error': 'no'})
    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0); body = json.loads(self.rfile.read(n) or b'{}')
        if self.path == '/start':
            G.start(body['mine'], body['theirs']); self.send(200, {'ok': G.err is None, 'error': G.err})
        elif self.path == '/choose': self.send(200, {'ok': G.choose(body.get('i', 0))})
        elif self.path == '/stop': G.stop(); self.send(200, {'ok': True})
        else: self.send(404, {'error': 'no'})
if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f'play: http://localhost:{port}', flush=True)
    try: ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()
    finally: G.stop()
