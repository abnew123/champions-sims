"""Live progress page for the sim batches: finds runs from the pssim/*.log start lines ("HH:MM:SS <jobs.json> -> <outdir>, ..."),
counts result files against the job count, and estimates time left from the rate since the run started. Refreshes every 10 s.
usage: python3 status_server.py [port=8766]"""
import http.server, json, os, re, glob, time, datetime, html, sys, subprocess, runpy
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pssim')
START = re.compile(r'^(\d\d:\d\d:\d\d) (\S+\.json) -> (\S+?),')
DONE = re.compile(r'^(\d\d:\d\d:\d\d) done:')

def runs():
    out = []
    for log in glob.glob(os.path.join(ROOT, '*.log')):
        try: lines = open(log, errors='replace').read().splitlines()
        except OSError: continue
        day = datetime.date.fromtimestamp(os.path.getmtime(log))
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
                pm = re.match(r'^(\d+) starting positions', x)
                if pm: positions = int(pm.group(1))
            st = datetime.datetime.combine(day, datetime.time.fromisoformat(m.group(1)))
            if st > datetime.datetime.now() + datetime.timedelta(minutes=1): st -= datetime.timedelta(days=1)
            try: total = len(json.load(open(jobs)))
            except Exception: total = None
            gm = re.search(r', (\d+) games', l)
            if positions and gm and int(gm.group(1)) > 0: total = positions // int(gm.group(1))
            files = glob.glob(os.path.join(outdir, '*.json')) if os.path.isdir(outdir) else []
            new = sum(os.path.getmtime(f) >= st.timestamp() for f in files)
            stopped = done_line is None and later_start
            out.append(dict(log=os.path.basename(log), jobs=m.group(2), outdir=m.group(3), start=st, done=len(files), new=new, total=total,
                            finished=done_line is not None, stopped=stopped, mtime=max([os.path.getmtime(f) for f in files] or [st.timestamp()])))
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

def page():
    now = datetime.datetime.now(); rows = []
    ps = subprocess.run(['ps', '-axo', 'command'], capture_output=True, text=True).stdout   # a run is live while its workers are
    live = lambda r: any((('node' in l or re.search(r'champ(-battle-v\d+)? (battle|plan|spot)', l)) and (' ' + r['outdir'] + ' ') in (l + ' ')) for l in ps.splitlines())
    # one entry per output folder (its latest start); drop entries with nothing to show
    latest = {}
    for r in runs():
        if r['outdir'] not in latest: latest[r['outdir']] = r
    R = [r for r in latest.values() if live(r) or (r['total'] and r['done'] > 0)]
    active = [r for r in R if live(r)]
    recent = [r for r in R if r not in active and (now - r['start']).total_seconds() < 2 * 86400][:4]
    def card(r, is_live):
        tot = r['total'] or 0; frac = r['done'] / tot if tot else 0; el = (now - r['start']).total_seconds()
        rate = r['new'] / el if el > 0 else 0; left = (tot - r['done']) / rate if rate > 0 and is_live else None
        missing = tot - r['done']
        if is_live: state, label = 'running', 'Running'
        elif missing <= 0: state, label = 'finished', 'Complete'
        else: state, label = 'stopped', 'Incomplete'
        ended = datetime.datetime.fromtimestamp(r['mtime'])
        lines = [f'{r["done"]} of {tot} done ({100*frac:.0f}%)']
        if is_live:
            lines.append(f'started {ampm(r["start"])}, running {fmt(el)}')
            lines.append(f'about {fmt(left)} left (done around {ampm(now + datetime.timedelta(seconds=left))})' if left is not None else 'estimating time left…')
        else:
            lines.append(f'{ampm(r["start"])} to {ampm(ended)}')
        note = ''
        if not is_live and missing > 0:
            c = crashed_workers(r)
            note = f'{missing} still to run' + (f' &mdash; {c} worker{"s" if c != 1 else ""} crashed partway; rerunning picks up the rest' if c else ' &mdash; stopped before the end; rerunning picks up the rest')
        return f'''<div class="card {state}"><div class="top"><b>{html.escape(r["outdir"].replace("results/", ""))}</b><span class="st">{label}</span></div>
          <div class="bar"><div style="width:{100*frac:.1f}%"></div></div>
          <div class="meta">{"".join(f"<span>{x}</span>" for x in lines)}</div>
          {f'<div class="note">{note}</div>' if note else ''}</div>'''
    body = (''.join(card(r, True) for r in active) or '<p class="idle">Nothing running right now.</p>') + \
           ('<h2>Recent</h2>' + ''.join(card(r, False) for r in recent) if recent else '')
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sim progress</title><style>
:root{{--bg:#f5f6f8;--panel:#fff;--ink:#15171a;--ink2:#666b73;--rule:#dfe2e7;--acc:#1f6feb;--ok:#00734f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#131518;--panel:#1b1d21;--ink:#f1f3f5;--ink2:#9da3ab;--rule:#2c3036;--acc:#58a6ff;--ok:#4cc79a}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,system-ui,sans-serif}}.wrap{{max-width:760px;margin:0 auto;padding:20px 16px 40px}}
h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:15px;color:var(--ink2);margin:22px 0 8px;font-weight:600}}.now{{color:var(--ink2);font-size:13px;margin-bottom:14px}}
.card{{background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:12px 14px;margin-bottom:10px}}.top{{display:flex;justify-content:space-between;gap:8px}}
.st{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--acc);font-weight:700}}.finished .st{{color:var(--ok)}}.stopped .st{{color:#c9822b}}.stopped .bar div{{background:#c9822b}}
.bar{{height:10px;background:var(--rule);border-radius:5px;overflow:hidden;margin:9px 0 7px}}.bar div{{height:100%;background:var(--acc)}}.finished .bar div{{background:var(--ok)}}
.meta{{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:13.5px}}.note{{font-size:13px;color:var(--ink2);margin-top:6px}}.idle{{color:var(--ink2)}}</style></head>
<body><div class="wrap" id="wrap"><h1>Sim progress</h1><div class="now">Updated {ampm(now, True)} &middot; refreshes every 10 s</div>{body}</div>
<script>
// update in place every 10 s (no full reload, so the page never goes blank between updates)
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
    http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1]) if len(sys.argv) > 1 else 8766), H).serve_forever()
