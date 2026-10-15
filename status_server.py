"""One live progress page for every thread's runs, and a viewer for built sheets. Refreshes in place every 10 s.

  Using CPU now  every process using CPU, grouped by thread (process names battlesim- / evalbar- / trsheet- / teamsearch-, or the
               thread's folder in the command line), with idle ones counted, plus the busiest other apps: nothing that uses cores is hidden
  Running now  every active run with a progress stamp, each labelled with its thread (the same cards appear again in the sections below)
  Sheets       the sheet kit's runs (sheetkit/kit.py: bring matrix, confirmation, turn-one lines), on this Mac or pulled from a cloud box
  Battle sim   the simulator thread's batches
  Team search  that thread's stages and hill climb (its own cards, from teamsearch/status_server.py)
  Eval bar     that thread's engine runs (its own cards, from evalbar/status.py; while the thread works in a git worktree, from there)

Runs are found from the pssim/*.log start lines ("HH:MM:SS <jobs.json> -> <outdir>, ..."): result files are counted against the job
count and the time left is estimated from the rate since the run started. A kit run's log is pssim/kit_<team>_<step>.log.
Built sheets: /sheets/<team>/work/preview.html (any file under sheets/ is served, read-only).
usage: python3 status_server.py [port=8766]"""
import http.server, json, os, re, glob, time, datetime, html, sys, subprocess, runpy, inspect, mimetypes
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, 'pssim')
START = re.compile(r'^(\d\d:\d\d:\d\d) (\S+\.json) -> (\S+?),')
DONE = re.compile(r'^(\d\d:\d\d:\d\d) done:')
KIT = re.compile(r'^kit_(.+)_(matrix|confirm|t1|guide|oppbr|optimal|optimal_pool|mix|smoke)\.log$')
STEP = {'matrix': 'bring matrix', 'confirm': 'confirmation', 't1': 'turn-one lines', 'guide': 'strategy-guide battles', 'oppbr': 'their best four', 'optimal': 'both sides pick their four', 'optimal_pool': 'both sides pick their four (real teams)', 'mix': 'mixed brings check', 'smoke': 'dry run'}
CLOUD_FRESH = 25 * 60          # a pulled run counts as still running while its newest result is younger than this (pulls come every 10 min)

def runs():
    out = []
    for log in glob.glob(os.path.join(ROOT, '*.log')):
        try: lines = open(log, errors='replace').read().splitlines()
        except OSError: continue
        day = datetime.date.fromtimestamp(os.path.getmtime(log)); kit = KIT.match(os.path.basename(log))
        for i, l in enumerate(lines):
            m = START.match(l)
            if not m: continue
            jobs, outdir = os.path.join(ROOT, m.group(2)), os.path.join(ROOT, m.group(3))
            # scan this run's own lines (up to the next start line) for its done line and, for native runs on a job subset (JOBS=...),
            # the "<n> starting positions" line: n / games = the jobs actually run
            done_line = None; later_start = False; positions = None
            for x in lines[i + 1:]:
                if START.match(x): later_start = True; break
                if DONE.match(x): done_line = x; break
                pm = re.match(r'^(?:\d\d:\d\d:\d\d )?(\d+) starting positions', x)
                if pm: positions = int(pm.group(1))
            st = datetime.datetime.combine(day, datetime.time.fromisoformat(m.group(1)))
            stamp = outdir + '.run.json'                      # a kit battle run: written when the run starts, so right in any time zone
            if kit and os.path.exists(stamp): st = datetime.datetime.fromtimestamp(os.path.getmtime(stamp))
            elif st > datetime.datetime.now() + datetime.timedelta(minutes=1): st -= datetime.timedelta(days=1)
            try: total = len(json.load(open(jobs)))
            except Exception: total = None
            gm = re.search(r', (\d+) games', l)
            if positions and gm and int(gm.group(1)) > 0 and not kit: total = positions // int(gm.group(1))
            files = glob.glob(os.path.join(outdir, '*.json')) if os.path.isdir(outdir) else []
            new = sum(os.path.getmtime(f) >= st.timestamp() for f in files)
            stopped = done_line is None and later_start
            out.append(dict(log=os.path.basename(log), jobs=m.group(2), outdir=m.group(3), start=st, done=len(files), new=new, total=total,
                            finished=done_line is not None, stopped=stopped, mtime=max([os.path.getmtime(f) for f in files] or [st.timestamp()]),
                            kit=kit.groups() if kit else None))
    out.sort(key=lambda r: r['start'], reverse=True)
    return out

def ampm(t, sec=False): return t.strftime('%-I:%M:%S %p' if sec else '%-I:%M %p').lower()

def fmt(sec):
    sec = int(max(0, sec)); h, r = divmod(sec, 3600); m, s = divmod(r, 60)
    return f'{h}h {m:02d}m' if h else f'{m}m {s:02d}s'

def crashed_workers(r):
    """worker logs (<outdir>.w<k>.log) that end in a Node error"""
    n = 0
    for f in glob.glob(os.path.join(ROOT, r['outdir'] + '.w*.log')):
        try:
            if os.path.getmtime(f) < r['start'].timestamp(): continue
            tail = open(f, errors='replace').read()[-3000:]
            if 'Error' in tail and 'Node.js v' in tail: n += 1
        except OSError: pass
    return n

def title(r):
    if not r['kit']: return r['outdir'].replace('results/', '')
    team, step = r['kit']
    try: name = json.load(open(os.path.join(HERE, 'sheets', team, 'sheet.json'))).get('name', team)
    except Exception: name = team
    variant = re.search(r'res_(\w+)$', r['outdir'])
    return f"{name}: {STEP[step]}" + (f" ({variant.group(1)} variant)" if variant else '')

BOX_FRESH = 45 * 60            # a pulled box run (box_plan.json) counts as running while its newest result is younger than this (pulls every 20 min)

def box_cards():
    """Battle sim's runs on the cloud box, from a box_plan.json in each pulled folder (pssim/results/**/box_plan.json:
    {"title", "start" (ISO, local), "jobs": [{"name", "file", "positions", "cost"}]}): a job counts as done when <name>.done was pulled,
    otherwise by its result file's lines; cost weighs the jobs (a 4x-budget search costs about 4 one-turn ones). Returns [(html, live)]."""
    out = []
    for plan in glob.glob(os.path.join(ROOT, 'results', '**', 'box_plan.json'), recursive=True):
        d = os.path.dirname(plan)
        try:
            p = json.load(open(plan)); st = datetime.datetime.fromisoformat(p['start'])
            done = tot = 0; newest = st.timestamp(); jobs_done = 0
            for j in p['jobs']:
                f = os.path.join(d, j['file']); w = j.get('cost', 1); tot += j['positions'] * w
                if os.path.exists(os.path.join(d, j['name'] + '.done')): n = j['positions']; jobs_done += 1
                elif os.path.exists(f): n = min(j['positions'], sum(1 for _ in open(f, errors='replace')))
                else: n = 0
                done += n * w
                if os.path.exists(f): newest = max(newest, os.path.getmtime(f))
        except Exception: continue
        finished = os.path.exists(os.path.join(d, 'ALL_DONE')); live = not finished and time.time() - newest < BOX_FRESH
        frac = min(1.0, done / tot) if tot else 0; el = newest - st.timestamp(); ended = datetime.datetime.fromtimestamp(newest)
        lines = [f'{jobs_done} of {len(p["jobs"])} jobs done, {100*frac:.0f}% of the work']
        if live:
            left = (tot - done) / (done / el) if done > 0 and el > 60 else None
            lines += [f'started {ampm(st)}, last results pulled {ampm(ended)}',
                      f'about {fmt(left)} left (done around {ampm(ended + datetime.timedelta(seconds=left))})' if left is not None else 'estimating time left…']
            state, label = 'running', 'Running on the cloud box'
        else:
            lines.append(f'{ampm(st)} to {ampm(ended)}'); state, label = ('finished', 'Complete') if finished else ('stopped', 'Incomplete')
        out.append((f'''<div class="card {state}"><div class="top"><b>{html.escape(p.get('title', os.path.relpath(d, ROOT)))}</b><span class="st">{label}</span></div>
          <div class="bar"><div style="width:{100*frac:.1f}%"></div></div>
          <div class="meta">{"".join(f"<span>{x}</span>" for x in lines)}</div></div>''', live, st))
    out.sort(key=lambda c: c[2], reverse=True)
    return [(h, live) for h, live, st in out if live or (datetime.datetime.now() - st).total_seconds() < 2 * 86400]

def team_search():
    """the Team search thread's own cards (teamsearch/status_server.py cards(): it picks its climb folder itself)"""
    try: return runpy.run_path(os.path.join(HERE, 'teamsearch', 'status_server.py'))['cards']()
    except Exception as e: return f'<p class="idle">Couldn&rsquo;t read Team search&rsquo;s cards ({html.escape(type(e).__name__)}).</p>'

def eval_bar():
    """the Eval bar thread's own cards (evalbar/status.py cards()): from this checkout and from every git worktree with stamps from the
    last two days (the thread often works in a worktree, whose runs stamp its own evalbar/out)"""
    fs = [os.path.join(HERE, 'evalbar', 'status.py')]
    for f in glob.glob(os.path.join(HERE, '.claude', 'worktrees', '*', 'evalbar', 'status.py')):
        out = os.path.join(os.path.dirname(f), 'out')
        if any(time.time() - os.path.getmtime(x) < 2 * 86400 for x in glob.glob(os.path.join(out, '**', '*.run.json'), recursive=True)): fs.append(f)
    parts = []
    for f in fs:
        if not os.path.exists(f): continue
        try: h = runpy.run_path(f)['cards']()
        except Exception as e: h = f'<p class="idle">Couldn&rsquo;t read the Eval bar&rsquo;s cards ({html.escape(type(e).__name__)}).</p>'
        if 'class="card' in h: parts.append(h)
    return ''.join(parts) or '<p class="idle">Nothing running right now.</p>'

THREADS = {'kit': 'TR sheet', 'sim': 'Battle sim', 'ts': 'Team search', 'eb': 'Eval bar'}

# ---- every process using CPU (2026-10-12, the user: anything that uses cores must show here, progress stamp or not) ----
PREFIX = {'battlesim-': 'Battle sim', 'evalbar-': 'Eval bar', 'trsheet-': 'TR sheet', 'teamsearch-': 'Team search', 'arc-': 'ARC-AGI-3'}
SHEET_THREAD = {'trick-room-six': 'TR sheet', 'frankfurt-239': 'Frankfurt-239 sheet', 'frankfurt-156': 'Frankfurt-156 sheet'}
def sheet_thread(slug): return SHEET_THREAD.get(slug) or ' '.join(w.capitalize() for w in slug.split('-')) + ' sheet'
SHEET_PATHS = []
for _f in glob.glob(os.path.join(HERE, 'sheets', '*', 'sheet.json')):           # each sheet kit's process prefix (sheet.json proc_prefix) and folder
    _slug = os.path.basename(os.path.dirname(_f))
    try: PREFIX[json.load(open(_f))['proc_prefix'] + '-'] = sheet_thread(_slug)
    except Exception: pass
    SHEET_PATHS.append((f'/sheets/{_slug}/', sheet_thread(_slug)))
PATHS = SHEET_PATHS + [('/evalbar/', 'Eval bar'), ('/teamsearch/', 'Team search'), ('/sheetkit/', 'TR sheet'), ('/sheets/', 'TR sheet'), ('bot/client.js', 'Battle sim (bot)'),
         ('/bot/', 'Battle sim (bot)'), ('/pssim/', 'Battle sim'), ('/native/', 'Battle sim')]
def etime_s(e):
    d, _, rest = e.rpartition('-'); parts = [int(x) for x in rest.split(':')]
    while len(parts) < 3: parts.insert(0, 0)
    return (int(d) if d else 0) * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]
def dur(sec):
    d, r = divmod(sec, 86400); h, r = divmod(r, 3600); m, s_ = divmod(r, 60)
    return f'{d}d {h}h' if d else f'{h}h {m:02d}m' if h else f'{m}m {s_:02d}s'
def who(args):
    exe = os.path.basename(args.split(' ', 1)[0])
    for k, v in PREFIX.items():
        if exe.startswith(k): return v + (' (bot)' if exe.endswith('-bot') or ' play ' in args else '')
    if 'claude-code/' in args or '/Claude.app/' in args: return None                     # Claude sessions: under other apps
    if 'status_server.py' in args: return 'This progress page'
    if '/Kaggle/arc-prize-2026-arc-agi-3' in args: return 'ARC-AGI-3'                    # its Python shows as Homebrew's Python, not arc-* (the ARC thread, 2026-10-13)
    if 'champions-sims' in args or 'bot/client.js' in args:
        for k, v in PATHS:
            if k in args: return v
        return 'Other (this project)'
    return None
def short(args):
    a = args.replace(HERE + '/', '').replace(os.path.expanduser('~'), '~')
    a = re.sub(r'/private/tmp/claude-\d+/[^ ]*/scratchpad/', 'scratch/', a)
    a = re.sub(r'(\S*)\.claude/worktrees/[^/ ]+/', '', a)                                  # a thread's git worktree: drop the prefix
    return a if len(a) <= 150 else a[:147] + '…'
def cpu_section():
    out = subprocess.run(['ps', '-axo', 'pid=,pcpu=,etime=,args='], capture_output=True, text=True).stdout.splitlines()
    ncpu = os.cpu_count() or 1; groups = {}; others = []; total = 0.0
    for l in out:
        m = re.match(r'\s*(\d+)\s+([\d.]+)\s+(\S+)\s+(.*)', l)
        if not m: continue
        pid, cpu, et, args = int(m.group(1)), float(m.group(2)), m.group(3), m.group(4)
        total += cpu; t = who(args)
        if t: groups.setdefault(t, []).append((cpu, pid, etime_s(et), args))
        elif cpu >= 5: others.append((cpu, pid, etime_s(et), args))
    ours = sum(c for g in groups.values() for c, *_ in g)
    rows = []
    for t, ps_ in sorted(groups.items(), key=lambda x: -sum(c for c, *_ in x[1])):
        busy = sorted([x for x in ps_ if x[0] >= 1], reverse=True); idle = len(ps_) - len(busy)
        rows.append(f'<tr class="grp"><th colspan="2">{html.escape(t)}</th><th>{sum(c for c, *_ in ps_) / 100:.1f} cores</th><th></th></tr>')
        for cpu, pid, el, args in busy:
            rows.append(f'<tr><td>{pid}</td><td class="cmd">{html.escape(short(args))}</td><td>{cpu / 100:.2f}</td><td>{dur(el)}</td></tr>')
        if idle: rows.append(f'<tr><td></td><td class="cmd idle">+ {idle} idle process{"es" if idle != 1 else ""} (under 1% CPU)</td><td></td><td></td></tr>')
    if others:
        rows.append(f'<tr class="grp"><th colspan="2">Other apps (not this project)</th><th>{sum(c for c, *_ in others) / 100:.1f} cores</th><th></th></tr>')
        for cpu, pid, el, args in sorted(others, reverse=True)[:6]:
            name = 'Claude (app and sessions)' if ('claude-code/' in args or '/Claude.app/' in args) else os.path.basename(args.split(' --', 1)[0])
            rows.append(f'<tr><td>{pid}</td><td class="cmd">{html.escape(short(name))}</td><td>{cpu / 100:.2f}</td><td>{dur(el)}</td></tr>')
    head = (f'<p class="now">This project: <b>{ours / 100:.1f}</b> of {ncpu} cores &middot; whole Mac: <b>{total / 100:.1f}</b> of {ncpu} '
            f'(ps averages over the last minute or so)</p>')
    return head + '<table class="cpu"><tr><th>pid</th><th>process</th><th>cores</th><th>running for</th></tr>' + ''.join(rows) + '</table>'
def running_cards(h):
    """the running cards in a thread's cards HTML: each <div class="card running ..."> with everything up to its matching </div>"""
    out = []
    for m in re.finditer(r'<div class="card running[^"]*">', h):
        depth = 0
        for t in re.finditer(r'<div\b|</div>', h[m.start():]):
            depth += 1 if t.group() != '</div>' else -1
            if depth == 0: out.append(h[m.start():m.start() + t.end()]); break
    return out
def tagged(c, thread):
    """a card with its thread's name above the title"""
    return c.replace('<div class="top">', f'<div class="who">{html.escape(thread)}</div><div class="top">', 1)

def page():
    """the page, built at most once every 8 s however many tabs poll it (a build takes ~1.5 s of CPU; the cache lives on the sys module,
    which outlasts the runpy re-reads of this file)"""
    c = sys.__dict__.setdefault('_status_page_cache', {})
    if c.get('html') and time.time() - c.get('t', 0) < 8: return c['html']
    h = build_page(); c.update(html=h, t=time.time()); return h

def build_page():
    now = datetime.datetime.now()
    ps = subprocess.run(['ps', '-axo', 'command'], capture_output=True, text=True).stdout   # a local run is live while its workers are
    local = lambda r: any((('node' in l or re.search(r'champ\S* (battle|plan|spot)', l)) and (os.path.basename(r['outdir']) in l) and
                           ((' ' + r['outdir'] + ' ') in (l + ' ') or os.path.normpath(os.path.join(ROOT, r['outdir'])) in l)) for l in ps.splitlines())
    # a kit run pulled from a cloud box has no process here: it is running while unfinished results keep arriving
    cloud = lambda r: bool(r['kit']) and not r['finished'] and not r['stopped'] and r['done'] < (r['total'] or 0) and time.time() - r['mtime'] < CLOUD_FRESH
    live = lambda r: local(r) or cloud(r)
    # one entry per output folder (its latest start); drop entries with nothing to show
    latest = {}
    for r in runs():
        if r['outdir'] not in latest: latest[r['outdir']] = r
    R = [r for r in latest.values() if (live(r) or (r['total'] and r['done'] > 0)) and not (r['kit'] and r['kit'][1] == 'smoke')]
    def card(r, is_live):
        tot = r['total'] or 0; frac = min(1.0, r['done'] / tot) if tot else 0; remote = is_live and not local(r)
        el = ((r['mtime'] if remote else time.time()) - r['start'].timestamp())      # a pulled run: measure up to its newest result
        rate = r['new'] / el if el > 0 else 0; left = (tot - r['done']) / rate if rate > 0 and is_live else None
        missing = tot - r['done']
        if is_live: state, label = 'running', 'Running on the cloud box' if remote else 'Running'
        elif missing <= 0: state, label = 'finished', 'Complete'
        else: state, label = 'stopped', 'Incomplete'
        ended = datetime.datetime.fromtimestamp(r['mtime'])
        lines = [f'{r["done"]:,} of {tot:,} done ({100*frac:.0f}%)']
        if is_live:
            lines.append(f'started {ampm(r["start"])}' + (f', last results pulled {ampm(ended)}' if remote else f', running {fmt(el)}'))
            base = ended if remote else now
            lines.append(f'about {fmt(left)} left (done around {ampm(base + datetime.timedelta(seconds=left))})' if left is not None and el > 60 else 'estimating time left…')
        else:
            lines.append(f'{ampm(r["start"])} to {ampm(ended)}')
        note = ''
        if not is_live and missing > 0:
            c = crashed_workers(r)
            note = f'{missing} still to run' + (f' &mdash; {c} worker{"s" if c != 1 else ""} crashed partway; rerunning picks up the rest' if c else ' &mdash; stopped before the end; rerunning picks up the rest')
        return f'''<div class="card {state}"><div class="top"><b>{html.escape(title(r))}</b><span class="st">{label}</span></div>
          <div class="bar"><div style="width:{100*frac:.1f}%"></div></div>
          <div class="meta">{"".join(f"<span>{x}</span>" for x in lines)}</div>
          {f'<div class="note">{note}</div>' if note else ''}</div>'''
    box = box_cards()
    def section(rs, extra=()):
        active = [r for r in rs if live(r)]
        recent = [r for r in rs if r not in active and (now - r['start']).total_seconds() < 2 * 86400][:3]
        on = ''.join(card(r, True) for r in active) + ''.join(h for h, lv in extra if lv)
        old = ''.join(card(r, False) for r in recent) + ''.join(h for h, lv in extra if not lv)
        return (on or '<p class="idle">Nothing running right now.</p>') + ('<h3>Recent</h3>' + old if old else '')
    # when Team search's page embeds this one (its own port), leave its section to it
    embedded = any(f.filename.endswith(os.path.join('teamsearch', 'status_server.py')) for f in inspect.stack())
    ts = '' if embedded else team_search(); eb = eval_bar()
    # every active run first, labelled with its thread (not on Team search's own page, which embeds this one)
    now_running = [tagged(card(r, True), sheet_thread(r['kit'][0]) if r['kit'] else THREADS['sim']) for r in R if live(r)] + \
                  [tagged(h, THREADS['sim']) for h, lv in box if lv] + \
                  [tagged(c, THREADS['ts']) for c in running_cards(ts)] + [tagged(c, THREADS['eb']) for c in running_cards(eb)]
    top = '' if embedded else f'<h2>Using CPU now</h2>{cpu_section()}<h2>Running now (with progress)</h2>' + (''.join(now_running) or '<p class="idle">Nothing with a progress stamp is running.</p>')
    body = top + f'''<h2>Sheets</h2>{section([r for r in R if r['kit']])}
<h2>Battle sim</h2>{section([r for r in R if not r['kit']], box)}''' + ('' if embedded else f'<h2>Team search</h2>{ts}') + \
           f'<h2>Eval bar</h2>{eb}'
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sim progress</title><style>
:root{{--bg:#f5f6f8;--panel:#fff;--ink:#15171a;--ink2:#666b73;--rule:#dfe2e7;--acc:#1f6feb;--ok:#00734f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#131518;--panel:#1b1d21;--ink:#f1f3f5;--ink2:#9da3ab;--rule:#2c3036;--acc:#58a6ff;--ok:#4cc79a}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,system-ui,sans-serif}}.wrap{{max-width:760px;margin:0 auto;padding:20px 16px 40px}}
h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:17px;margin:24px 0 8px}}h3{{font-size:14px;color:var(--ink2);margin:16px 0 8px;font-weight:600}}.now{{color:var(--ink2);font-size:13px;margin-bottom:6px}}
.card{{background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:12px 14px;margin-bottom:10px}}.top{{display:flex;justify-content:space-between;gap:8px}}
.st{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--acc);font-weight:700;white-space:nowrap}}.finished .st{{color:var(--ok)}}
.stopped .st,.waiting .st{{color:#c9822b}}.stopped .bar div{{background:#c9822b}}
.bar{{height:10px;background:var(--rule);border-radius:5px;overflow:hidden;margin:9px 0 7px}}.bar div{{height:100%;background:var(--acc)}}.finished .bar div{{background:var(--ok)}}
.who{{font-size:11.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--ink2);margin-bottom:3px}}
.meta{{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:13.5px}}.note{{font-size:13px;color:var(--ink2);margin-top:6px}}.idle{{color:var(--ink2)}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}}td,th{{text-align:left;padding:3px 6px;border-top:1px solid var(--rule)}}th{{color:var(--ink2);font-weight:600}}
tr.grp th{{color:var(--ink);padding-top:10px}}td.cmd{{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;word-break:break-all}}td.idle{{color:var(--ink2);font-family:inherit}}
@media (max-width:520px){{table{{font-size:12px}}}}</style></head>
<body><div class="wrap" id="wrap"><h1>Sim progress</h1><div class="now">Updated {ampm(now, True)} &middot; refreshes every 10 s</div>{body}</div>
<script>
// update in place every 10 s (no full reload, so the page never goes blank between updates)
setInterval(async () => {{ try {{ const r = await fetch('/?t=' + Date.now(), {{cache: 'no-store'}}); const t = await r.text();
  const d = new DOMParser().parseFromString(t, 'text/html'); const w = d.getElementById('wrap'); if (w) document.getElementById('wrap').innerHTML = w.innerHTML; }} catch (e) {{}} }}, 10000);
</script></body></html>'''

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0]
        if path.startswith('/sheets/'):                           # a built sheet or any other file under sheets/, read-only
            f = os.path.realpath(os.path.join(HERE, path.lstrip('/'))); base = os.path.realpath(os.path.join(HERE, 'sheets'))
            if not f.startswith(base + os.sep) or not os.path.isfile(f): self.send_error(404); return
            b = open(f, 'rb').read(); ct = mimetypes.guess_type(f)[0] or 'application/octet-stream'
            if ct.startswith('text/') or ct == 'application/json': ct += '; charset=utf-8'
        else:
            try: b = runpy.run_path(__file__)['page']().encode()   # re-read this file each time, so page edits need no restart
            except Exception as e: b = f'<pre>status page error: {html.escape(repr(e))}</pre>'.encode()
            ct = 'text/html; charset=utf-8'
        self.send_response(200); self.send_header('Content-Type', ct); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def log_message(self, *a): pass
if __name__ == '__main__':
    http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1]) if len(sys.argv) > 1 else 8766), H).serve_forever()
