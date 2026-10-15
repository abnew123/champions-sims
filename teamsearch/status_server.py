"""Live progress page for all sims: the team search's stages (below) plus the other thread's runs (the project's status_server.py,
port 8766, run read-only and embedded). Team-search cards, one per stage —
one-on-one matrix cells, replay team previews, bring training battles, bring fit + check, hill-climb rounds — with job counts
from the result folders and time left from the rate since the stage started. Refreshes in place every 10 s.
usage: python3 status_server.py [port=8767]
The project's page (status_server.py, port 8766) shows these cards too, via cards() below.
  TS_CLIMB_DIR=cloud_results/v12: read the hill climb from that folder; default: whichever of teamsearch/, cloud_results/v12/ and
  cloud_results/ has the newest climb progress, state or round log (local runs, the AWS rerun's pulled results, the first AWS climb)"""
import http.server, json, os, re, glob, time, datetime, html, sys, subprocess, runpy
TS = os.path.dirname(os.path.abspath(__file__))
J = lambda *p: os.path.join(TS, *p)
CLIMB_DIRS = ['', os.path.join('cloud_results', 'v12'), 'cloud_results']
def climb_dir():
    """(folder relative to teamsearch/, path joiner) for the hill climb's files: TS_CLIMB_DIR, else the candidate with the newest activity.
    Climbs with their own file names (TS_STATE=climb_v27_state.json ...: climb_v27_progress.json, climb_v27_log.jsonl) are found in
    any cloud_results/* folder; the joiner maps climb_progress.json / climb_state.json / climb_log.jsonl to that climb's names."""
    cd = os.environ.get('TS_CLIMB_DIR'); pre = 'climb'
    if cd is None:
        cands = [(d, 'climb') for d in CLIMB_DIRS]
        for f in glob.glob(J('cloud_results', '*', 'climb_*progress.json')) + glob.glob(J('climb_*progress.json')):
            d = os.path.relpath(os.path.dirname(f), TS); d = '' if d == '.' else d
            cands.append((d, os.path.basename(f)[:-len('_progress.json')]))
        def newest(c):
            d, p = c
            return max([os.path.getmtime(f) for f in (J(d, f'{p}_progress.json'), J(d, f'{p}_state.json'), J(d, 'round.log'),
                                                      J(d, 'round1.log')) if os.path.exists(f)] + [0])
        cd, pre = max(cands, key=newest)
    ren = lambda x: pre + x[len('climb'):] if pre != 'climb' and x in ('climb_progress.json', 'climb_state.json', 'climb_log.jsonl') else x
    return cd, (lambda *p: os.path.join(TS, cd, *p[:-1], ren(p[-1])) if p else os.path.join(TS, cd))

def ampm(t, sec=False): return t.strftime('%-I:%M:%S %p' if sec else '%-I:%M %p').lower()
def fmt(sec):
    sec = int(max(0, sec)); h, r = divmod(sec, 3600); m, s = divmod(r, 60)
    return f'{h}h {m:02d}m' if h else f'{m}m {s:02d}s'
def load(p, default=None):
    try: return json.load(open(p))
    except Exception: return default
def files(pattern): return glob.glob(pattern)
def dt(ts): return datetime.datetime.fromtimestamp(ts)

def card(title, state, done, total, unit, started=None, live=False, rate_files=None, lines=(), note=''):
    """state: running | finished | waiting | stopped"""
    now = time.time(); frac = done / total if total else (1.0 if state == 'finished' else 0.0)
    meta = [f'{done:,} of {total:,} {unit} ({100 * frac:.0f}%)'] if total else []
    if live and started:
        el = now - started; meta.append(f'started {ampm(dt(started))}, running {fmt(el)}')
        new = sum(1 for f in (rate_files or []) if os.path.getmtime(f) >= started)
        rate = new / el if el > 60 else 0
        if rate > 0 and total: left = (total - done) / rate; meta.append(f'about {fmt(left)} left (done around {ampm(dt(now + left))})')
        else: meta.append('estimating time left…')
    meta += list(lines)
    label = {'running': 'Running', 'finished': 'Complete', 'waiting': 'Waiting', 'stopped': 'Stopped'}[state]
    return f'''<div class="card {state}"><div class="top"><b>{html.escape(title)}</b><span class="st">{label}</span></div>
      <div class="bar"><div style="width:{100 * frac:.1f}%"></div></div>
      <div class="meta">{"".join(f"<span>{x}</span>" for x in meta)}</div>{f'<div class="note">{note}</div>' if note else ''}</div>'''

def log_progress(C, phase):
    """(teams done, teams in the stage, teams per minute or None, log mtime) of the current round stage, from the climb's round log
    (round_<name>.log next to climb_<name>_progress.json): the log's "<stage>: n/N teams, m min" lines since the round's last start.
    The rate skips a relaunch's fast-forward through finished teams (lines under 5 min); the log's mtime is when its last line was
    written. Counting result files can't follow a pool climb: its bring search runs two stages under other seeds, and the game cache
    serves many games without a file (2026-10-15, the user: the card showed 0 of 383,786)."""
    base = os.path.basename(C('climb_progress.json'))[len('climb'):-len('_progress.json')]
    log = C(f'round{base}.log')
    if not os.path.exists(log): return None
    label = {'screen': 'bring search', 'confirm': 'confirm games', 'sharpen': 'confirm games'}.get(phase)
    seg = []
    for l in open(log, errors='replace'):
        if re.match(r'^round \d+: sim setup', l) or l.startswith('--- relaunched'): seg = []
        m = re.match(r'^\d\d:\d\d [AP]M\s+' + re.escape(label or '') + r'[^:]*: (\d+)/(\d+) teams, (\d+) min', l)
        if m: seg.append(tuple(map(int, m.groups())))
    if not label or not seg: return None
    n, N, _ = seg[-1]; pts = [x for x in seg if x[2] >= 5]
    rate = (pts[-1][0] - pts[0][0]) / (pts[-1][2] - pts[0][2]) if len(pts) >= 2 and pts[-1][2] > pts[0][2] else None
    return n, N, rate, os.path.getmtime(log)

def other_thread():
    """the other thread's progress cards (the project's status_server.py, run read-only), or a link if its layout changes"""
    try:
        o = runpy.run_path(os.path.join(TS, '..', 'status_server.py'))['page']()
        m = re.search(r'<div class="wrap" id="wrap">(.*?)</div>\s*<script>', o, re.S)
        inner = m.group(1)
        inner = re.sub(r'<h1>.*?</h1>', '', inner, flags=re.S); inner = re.sub(r'<div class="now">.*?</div>', '', inner, count=1, flags=re.S)
        return inner.replace('<h2>Recent</h2>', '<h3>Recent</h3>')
    except Exception as e:
        return f'<p class="idle">Couldn\'t read the other thread\'s page ({html.escape(type(e).__name__)}); it\'s at <a href="http://localhost:8766">localhost:8766</a>.</p>'

def cards():
    """the team search's progress cards as HTML (no heading); the project's page at 8766 calls this"""
    CD, C = climb_dir()
    ps = subprocess.run(['ps', '-axo', 'command'], capture_output=True, text=True).stdout
    running = lambda pat: any(pat in l for l in ps.splitlines())
    cards = []
    # 1. one-on-one matrix cells
    pool = load(J('swap_pool.json'), []); idx = load(J('teams', 'start', 'index.json'), {})
    extra = [l.strip() for l in open(J('mx', 'extra_ids.txt'))] if os.path.exists(J('mx', 'extra_ids.txt')) else []
    ids = set([p['gid'] for p in pool] + [g for v in idx.values() for g in v['gids']] + [e for e in extra if e])
    have = sum(os.path.exists(J('mx', 'out', t, g.replace('/', '_') + '.json')) for t in ('notr', 'tr') for g in ids)
    live = running('grid_pool.py')
    cards.append(card('One-on-one matrix cells', 'running' if live else 'finished' if have >= 2 * len(ids) else 'stopped', have, 2 * len(ids), 'set × mode files'))
    # 2. replay team previews
    pv = load(J('bring', 'previews.json'), {}); ng = len(pv.get('games', [])) if pv else 0
    live = running('fetch_preview.py')
    cards.append(card('Replay team previews (bring heuristic data)', 'running' if live else 'finished' if ng >= 3060 else 'stopped', ng, 3060, 'replays'))
    # 3. bring training battles
    src = open(J('bring', 'train_battles.py')).read(); m = re.search(r"TEAMS = \[(.*?)\]", src, re.S)
    nteams = len(re.findall(r"'([^']+)'", m.group(1))) if m else 12
    dirs = sorted(glob.glob(J('runs', 'train_*')), key=os.path.getmtime)
    per_team = 480; outs = [f for d in dirs for f in files(os.path.join(d, 'out_0_2', '*.json'))]
    live = running('train_battles.py')
    started = min((os.path.getmtime(f) for f in outs), default=None)
    lab = load(J('bring', 'train_labels.json'), [])
    teams_done = len({r['team'] for r in lab}) if lab else 0
    st = 'running' if live else 'finished' if len(outs) >= nteams * per_team else ('waiting' if not outs else 'stopped')
    cards.append(card('Bring training battles', st, len(outs), nteams * per_team, 'jobs (2 games each)', started, live, outs,
                      [f'team {min(teams_done + 1, nteams)} of {nteams}' if live else f'{teams_done} of {nteams} teams labelled']))
    # 4. bring fit + check against the sheet
    om = load(J('bring', 'outcome_model.json')); sb = load(J('bring', 'sheet_battle.json'))
    lines = []
    if om: lines.append(f"fitted picks beat a random pick by {100 * om['heldout_gain']:+.1f} points on held-out teams (human-imitation picks {100 * om['human_gain']:+.1f})")
    if sb: lines.append('Trick Room six, weighted win %: ' + ', '.join(f"{k} {100 * v['score']:.1f}" for k, v in sb.items()))
    live = running('sheet_battle.py') or running('fit_outcome.py')
    chk = [f for f in files(J('runs', '*_check_*', 'out_*', '*.json'))]
    cards.append(card('Bring fit + check vs the sheet', 'running' if live else 'finished' if (om and sb) else 'waiting',
                      len(chk) if live else (2 if om and sb else int(bool(om))), 180 if live else 2, 'jobs' if live else 'steps', lines=lines))
    # 5. hill climb
    stt = load(C('climb_state.json')); pr = load(C('climb_progress.json'))
    live = running('climb.py round') if not CD else bool(pr) and pr.get('phase') != 'done' and \
        time.time() - max([os.path.getmtime(f) for f in files(C('runs', '*', 'out_*', '*.json'))[-2000:]] + [0]) < 1800   # remote: recent results
    if not pr:
        cards.append(card('Hill climb', 'waiting', 0, 0, '', lines=['round 1 starts after the bring check']))
    else:
        phase = pr['phase']; rnd = pr['round']
        if phase in ('screen', 'confirm', 'sharpen'):
            sfx = f"{pr['seed']}_{pr['per_job']}"; tag = pr.get('sim')
            if tag is None:                             # (older climb.py: take the setup whose outputs for this seed are newest)
                ds = files(C('runs', '*', f'out_*{sfx}'))
                tag = max(ds, key=os.path.getmtime).rsplit('/out_', 1)[1][:-len(sfx)].rstrip('_') if ds else 'v3'
                tag = tag or 'v3'
            outs = files(C('runs', '*', f"out_{sfx}" if tag == 'v3' else f"out_{tag}_{sfx}", '*.json'))
            title = f"Hill climb round {rnd} ({pr['mode']}): " + {'screen': 'screening swaps (bring search)', 'confirm': 'confirming the best swaps (fresh games)',
                                                                  'sharpen': f"extra paired batch {pr.get('batch', '')} for undecided swaps"}[phase]
            lp = log_progress(C, phase) if os.environ.get('TS_CLIMB_FILES') != '1' else None
            if lp:                                      # pool climbs: teams done from the round log (see log_progress)
                n, N, rate, t_last = lp; extra = []
                if live and rate:
                    left = (N - n) / rate * 60; done_at = t_last + left
                    extra.append(f"about {fmt(max(0, done_at - time.time()))} left (done around {ampm(dt(done_at))}), {rate:.1f} teams a minute")
                elif live: extra.append('estimating time left…')
                cards.append(card(title, 'running' if live else 'stopped', n, N, 'teams', None, live, None,
                                  extra + [f"{pr['teams']} teams for {pr['starts']} start teams; the log counts teams in tens"]))
            else:
                cards.append(card(title, 'running' if live else 'stopped', len(outs), pr['teams'] * pr.get('jobs_per_team', 60), f"jobs ({pr['per_job']} games each)",
                                  pr['at'], live, outs, [f"{pr['teams']} teams for {pr['starts']} start teams"]))
        else:
            label = {'prefilter': 'matrix pre-filter', 'done': 'finished'}[phase]
            cards.append(card(f"Hill climb round {rnd} ({pr['mode']}): {label}", 'running' if live else 'finished' if phase == 'done' else 'stopped',
                              0, 0, '', lines=[f"{pr.get('moved', '?')} of {pr['starts']} start teams moved to a better team" if phase == 'done' else '']))
    if stt:
        act = sum(1 for t in stt['teams'].values() if not t['done'])
        moves = [json.loads(l) for l in open(C('climb_log.jsonl'))] if os.path.exists(C('climb_log.jsonl')) else []
        last = [m for m in moves if m['round'] == stt['round']]
        rows = ''.join(f"<tr><td>{html.escape(m['start'])}</td><td>{html.escape(m['best']['out'])} → {html.escape(m['best']['into'])}</td>"
                       f"<td>{100 * m['best']['diff']:+.1f} ± {100 * m['best']['se']:.1f}</td><td>{({'move': 'moved', 'stop': 'local max', 'undecided': 'local max (undecided)'}.get(m['verdict'], m['verdict']) if 'verdict' in m else ('moved' if m['best']['diff'] > m['best']['se'] else 'local max'))}</td></tr>"
                       for m in sorted(last, key=lambda m: -m['best']['diff']))
        cards.append(f'''<div class="card finished"><div class="top"><b>Climb state after round {stt['round']}</b><span class="st">{act} still climbing</span></div>
          {f'<table><tr><th>start</th><th>best swap</th><th>gain (win-share pts)</th><th></th></tr>{rows}</table>' if rows else ''}</div>''')
    return ''.join(cards)

def page():
    now = datetime.datetime.now()
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sim progress</title><style>
:root{{--bg:#f5f6f8;--panel:#fff;--ink:#15171a;--ink2:#666b73;--rule:#dfe2e7;--acc:#1f6feb;--ok:#00734f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#131518;--panel:#1b1d21;--ink:#f1f3f5;--ink2:#9da3ab;--rule:#2c3036;--acc:#58a6ff;--ok:#4cc79a}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,system-ui,sans-serif}}.wrap{{max-width:760px;margin:0 auto;padding:20px 16px 40px}}
h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:17px;margin:22px 0 8px}}h3{{font-size:14px;color:var(--ink2);margin:16px 0 8px;font-weight:600}}.idle{{color:var(--ink2)}}.now{{color:var(--ink2);font-size:13px;margin-bottom:14px}}.now a{{color:var(--acc)}}
.card{{background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:12px 14px;margin-bottom:10px}}.top{{display:flex;justify-content:space-between;gap:8px}}
.st{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--acc);font-weight:700;white-space:nowrap}}.finished .st{{color:var(--ok)}}
.stopped .st,.waiting .st{{color:#c9822b}}.stopped .bar div{{background:#c9822b}}
.bar{{height:10px;background:var(--rule);border-radius:5px;overflow:hidden;margin:9px 0 7px}}.bar div{{height:100%;background:var(--acc)}}.finished .bar div{{background:var(--ok)}}
.meta{{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:13.5px}}.note{{font-size:13px;color:var(--ink2);margin-top:6px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}}td,th{{text-align:left;padding:3px 6px;border-top:1px solid var(--rule)}}th{{color:var(--ink2);font-weight:600}}
@media (max-width:520px){{table{{font-size:12px}}}}</style></head>
<body><div class="wrap" id="wrap"><h1>Sim progress</h1>
<div class="now">Updated {ampm(now, True)} &middot; refreshes every 10 s</div>
<h2>Team search (this thread)</h2>{cards()}
<h2>Trick Room six sims (other thread)</h2>{other_thread()}</div>
<script>
setInterval(async () => {{ try {{ const r = await fetch('/?t=' + Date.now(), {{cache: 'no-store'}}); const t = await r.text();
  const d = new DOMParser().parseFromString(t, 'text/html'); const w = d.getElementById('wrap'); if (w) document.getElementById('wrap').innerHTML = w.innerHTML; }} catch (e) {{}} }}, 10000);
</script></body></html>'''

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try: b = runpy.run_path(__file__)['page']().encode()       # re-read this file each time, so page edits need no restart
        except Exception as e: b = f'<pre>status page error: {html.escape(repr(e))}</pre>'.encode()
        self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
if __name__ == '__main__':
    http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1]) if len(sys.argv) > 1 else 8767), H).serve_forever()
