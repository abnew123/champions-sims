"""The Eval bar thread's cards for the shared progress page (status_server.py at the repo root calls cards()).
One card for the stream watcher (auto.py, out/live/auto.status.json): what it runs, how far its page has got, whether it is paused. Then
one card per engine run started by engine.py (each writes a stamp, out/<output>.run.json): positions done of the total, how long it has
run, and the time left from the rate since it started. The watcher's own per-game runs (live_<video id>_g<n>) are in its card; other
"Live spectator" runs (one turn each) show only while they run."""
import os, re, json, glob, time, datetime, subprocess, html
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
def lines(f):
    n = 0
    try:
        with open(f, 'rb') as h:
            for b in iter(lambda: h.read(1 << 20), b''): n += b.count(b'\n')
    except OSError: pass
    return n
def pid_alive(pid):
    if not pid: return False
    try: os.kill(int(pid), 0); return True
    except (OSError, ValueError): return False
def ampm(t): return datetime.datetime.fromtimestamp(t).strftime('%-I:%M %p').lower()
def fmt(sec):
    sec = int(max(0, sec)); h, r = divmod(sec, 3600); m, s = divmod(r, 60)
    return f'{h}h {m:02d}m' if h else f'{m}m {s:02d}s'
def hm(sec): return f'{int(sec) // 3600}h{int(sec) % 3600 // 60:02d}m'
def watcher():
    """the stream watcher's card, or None when it has not run for two days"""
    try: w = json.load(open(os.path.join(OUT, 'live', 'auto.status.json')))
    except Exception: return None
    now = time.time()
    if now - w['updated'] > 2 * 86400: return None
    try: os.kill(w['pid'], 0); up = now - w['updated'] < 120
    except OSError: up = False
    what = {'follow': 'following', 'serve': 'showing', 'scan': 'reading the recording of'}.get(w.get('mode'), 'waiting for')
    title = f"Stream watcher: {what} {w.get('title') or w.get('vid') or 'a VGC stream'}"
    ev, rd = w.get('evaluated'), w.get('read')
    busy = w.get('mode') == 'follow' or (rd is not None and ev is not None and ev < rd)
    state, label = (('stopped', 'Not running') if not up else ('stopped', 'Paused') if w.get('paused') else
                    ('running', 'Following' if w.get('mode') == 'follow' else 'Evaluating') if busy else ('finished', 'Idle'))
    meta = []
    if w.get('games') is not None: meta.append(f"{w['games']} games, {ev:,} of {rd:,} turns evaluated" if rd else f"{w['games']} games")
    if w.get('at') is not None: meta.append(f"reading {hm(w['at'])} into the stream (a fragment {fmt(now - w['fetched'])} ago)")
    if w.get('paused'): meta.append(f"paused {w['why']}; carries on below 6")
    meta.append(f"{w.get('threads', 2)} engine threads, page at localhost:{w.get('port', 8768)}" + (f", since {ampm(w['started'])}" if w.get('started') else ''))
    if not up: meta.append(f"last heard from {ampm(w['updated'])}")
    frac = min(1.0, ev / rd) if ev is not None and rd else 0
    return f'''<div class="card {state}"><div class="top"><b>{html.escape(title)}</b><span class="st">{label}</span></div>
          <div class="bar"><div style="width:{100 * frac:.1f}%"></div></div>
          <div class="meta">{''.join(f'<span>{html.escape(x)}</span>' for x in meta)}</div></div>'''
WATCHED = re.compile(r'(^|/)live_[\w-]{11}_g\d+_eval\.jsonl$')            # the watcher's per-game runs: in its card
def cards():
    ps = subprocess.run(['ps', '-axo', 'command'], capture_output=True, text=True).stdout.splitlines()
    w = watcher(); out = [w] if w else []
    for st in sorted(glob.glob(os.path.join(OUT, '**', '*.run.json'), recursive=True), key=os.path.getmtime, reverse=True):
        try: r = json.load(open(st))
        except Exception: continue
        if WATCHED.search(r['out']): continue
        outf = os.path.join(OUT, r['out']); done = lines(outf); tot = r['total']; now = time.time()
        # its process: the output's full path, or its folder and name (a bare name like eval.jsonl matched any engine run whose output ended
        # in it, so finished cards showed as running, 2026-10-14)
        key = os.path.join(os.path.basename(os.path.dirname(outf)), os.path.basename(outf))
        live = any(r.get('proc', 'evalpos') in l and (outf in l or key in l) for l in ps) or pid_alive(r.get('pid'))   # a long-lived program's own card
        if not live and (now - os.path.getmtime(st) > 2 * 86400 or r.get('title', '').startswith('Live spectator')): continue
        if live and r.get('pid') and done >= tot and not any(r.get('proc', 'evalpos') in l and (outf in l or key in l) for l in ps): live = False   # its work is done
        last = os.path.getmtime(outf) if os.path.exists(outf) else r['started']
        el = (now if live else last) - r['started']; rate = (done - r['done0']) / el if el > 0 else 0
        frac = min(1.0, done / tot) if tot else 0
        state, label = ('running', 'Running') if live else ('finished', 'Complete') if done >= tot else ('stopped', 'Incomplete')
        meta = [f"{done:,} of {tot:,} {r.get('unit', 'positions')} ({100 * frac:.0f}%)",
                f"{r['threads']} thread{'s' if r['threads'] != 1 else ''}" + (f", {r['seeds']} luck samples{' (staged)' if r.get('staged') else ''}" if r.get('seeds') else '')]
        if live:
            meta.append(f"started {ampm(r['started'])}, running {fmt(el)}")
            left = (tot - done) / rate if rate > 0 else None
            meta.append(f'about {fmt(left)} left (done around {ampm(now + left)})' if left is not None and el > 60 else 'estimating time left…')
        else: meta.append(f"{ampm(r['started'])} to {ampm(last)}")
        note = '' if live or done >= tot else f'{tot - done:,} still to run; rerunning picks up the rest'
        out.append(f'''<div class="card {state}"><div class="top"><b>{html.escape(r['title'])}</b><span class="st">{label}</span></div>
          <div class="bar"><div style="width:{100 * frac:.1f}%"></div></div>
          <div class="meta">{''.join(f'<span>{x}</span>' for x in meta)}</div>{f'<div class="note">{note}</div>' if note else ''}</div>''')
    return ''.join(out) or '<p class="idle">Nothing running right now.</p>'
