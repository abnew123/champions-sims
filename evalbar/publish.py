"""The public eval bar on the user's site: the local page's data (auto.py's program on port 8768) uploaded to the site's Netlify
function in the form the public page reads, and that page as one standalone file.
  python3 evalbar/publish.py page <out.html> [base=/api/evalbar]   the public page (the site keeps it as static/evalbar/index.html)
  python3 evalbar/publish.py sample <dir>                           head.json and the game files as they would go up now, with
                                                                    "Player 1" / "Player 2" for the players' names (for the site's tests)
  python3 evalbar/publish.py once                                   upload what changed, once
auto.py uploads every 10 seconds when ~/.config/evalbar/site.json ({"base": the site's /api/evalbar URL, "token"}) exists. What goes up:
  head.json              {"schema": 1, "updated", "stream": {"id", "title", "live"}, "status", "games": [{"key", "v", "title", "versus",
                         "turns", "winner"}]}, changed only when something in it changes
  <stream id>-g<n>.json  each game as the local page has it, without the reconciler's checks (the public page is read-only); "v" is a
                         hash of the file, so a game file's URL with its version never changes content
The players' names from the scoreboard stay on: the user chose to show them on the public bar and game list (2026-10-10)."""
import os, re, sys, json, time, hashlib, urllib.request
import common as C
SITE = os.environ.get('EVALBAR_SITE') or os.path.expanduser('~/.config/evalbar/site.json')   # EVALBAR_SITE: another file, for tests
LOCAL = 'http://127.0.0.1:8768/data.json'
LIMIT = 500_000                                                          # the site refuses bodies over 512 KB
def public(d, title=None):
    """the local page's data -> (head without 'updated', {key: file text})"""
    vid = re.sub(r'[^A-Za-z0-9_-]', '', (d.get('video') or {}).get('id') or '') or 'none'
    files = {}; games = []
    for i, g in enumerate(d.get('games') or []):
        g = {**g, 'steps': [{k: v for k, v in st.items() if k != 'checks'} for st in g.get('steps') or []]}
        body = json.dumps(g, ensure_ascii=False, separators=(',', ':')); key = f'{vid}-g{i + 1}.json'
        files[key] = body
        games.append({'key': key, 'v': int(hashlib.sha1(body.encode()).hexdigest()[:12], 16), 'title': g.get('title'), 'versus': g.get('versus'),
                      'turns': len(g['steps']), 'winner': g.get('winner')})
    return {'schema': 1, 'stream': {'id': vid, 'title': title, 'live': bool((d.get('video') or {}).get('live'))},
            'status': (d.get('live') or {}).get('status'), 'games': games}, files
def put(cfg, key, body):
    req = urllib.request.Request(f"{cfg['base'].rstrip('/')}/{key}", data=body.encode(), method='PUT',
                                 headers={'Authorization': f"Bearer {cfg['token']}", 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r: return r.status
class Publisher:
    """what has gone up, so each tick sends only what changed (game files first, then the head that points at them)"""
    def __init__(s, port=8768): s.sent = {}; s.head = None; s.title = None; s.local = f'http://127.0.0.1:{port}/data.json'
    def tick(s, log=print):
        if not os.path.exists(SITE): return
        try: d = json.load(urllib.request.urlopen(s.local, timeout=10))
        except Exception: return                                          # the local page is not up (starting, or paused)
        cfg = json.load(open(SITE)); head, files = public(d, s.title)
        try:
            for k, body in files.items():
                h = hashlib.sha1(body.encode()).hexdigest()
                if s.sent.get(k) == h: continue
                if len(body.encode()) > LIMIT: log(f'publish: {k} is {len(body.encode()) // 1000} KB, over the limit; not sent'); s.sent[k] = h; continue
                put(cfg, k, body); s.sent[k] = h
            hb = json.dumps(head, sort_keys=True)
            if hb != s.head: put(cfg, 'head.json', json.dumps({**head, 'updated': int(time.time())}, ensure_ascii=False)); s.head = hb
        except Exception as e: log(f'publish: {type(e).__name__} {getattr(e, "code", "")} {e}'.strip())
def page(out, base='/api/evalbar'):
    html = open(os.path.join(C.HERE, 'page.html')).read().replace('<title>Eval Bar</title>', '<title>Champions Eval Bar</title>', 1)
    html = html.replace('/*DATA*/null', json.dumps({'games': [], 'video': None, 'live': {'url': None, 'status': 'starting', 'format': 'Champions broadcast',
                                                                                         'public': {'base': base}}}))
    open(out, 'w').write('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                         '<style>body{margin:0}</style></head><body>' + html + '</body></html>')
    print(f'{out}: the public page, reading {base}')
def sample(d_out):
    d = json.load(urllib.request.urlopen(LOCAL, timeout=10))
    for g in d.get('games') or []: g['players'] = None; g['versus'] = None     # samples go into the site's repo: no real names
    head, files = public(d, 'VGC Day 1 | 2027 Pokémon Louisville Regional Championships'); os.makedirs(d_out, exist_ok=True)
    for k, body in files.items(): open(os.path.join(d_out, k), 'w').write(body)
    open(os.path.join(d_out, 'head.json'), 'w').write(json.dumps({**head, 'updated': int(time.time())}, ensure_ascii=False))
    print(f'{d_out}: head.json and {len(files)} game files, players as Player 1 / Player 2')
if __name__ == '__main__':
    a = sys.argv[1:]; kw = dict(x.split('=', 1) for x in a if '=' in x); pos = [x for x in a if '=' not in x]
    if pos[:1] == ['page']: page(pos[1], kw.get('base', '/api/evalbar'))
    elif pos[:1] == ['sample']: sample(pos[1])
    elif pos[:1] == ['once']: Publisher().tick()
    else: sys.exit(__doc__)
