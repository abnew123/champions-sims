"""The Eval bar thread's cards for the shared progress page (status_server.py at the repo root calls cards()).
One card per engine run started by engine.py (each writes a stamp, out/<output>.run.json): positions done of the total, how long it has
run, and the time left from the rate since it started."""
import os, json, glob, time, datetime, subprocess, html
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
def lines(f):
    n = 0
    try:
        with open(f, 'rb') as h:
            for b in iter(lambda: h.read(1 << 20), b''): n += b.count(b'\n')
    except OSError: pass
    return n
def ampm(t): return datetime.datetime.fromtimestamp(t).strftime('%-I:%M %p').lower()
def fmt(sec):
    sec = int(max(0, sec)); h, r = divmod(sec, 3600); m, s = divmod(r, 60)
    return f'{h}h {m:02d}m' if h else f'{m}m {s:02d}s'
def cards():
    ps = subprocess.run(['ps', '-axo', 'command'], capture_output=True, text=True).stdout.splitlines()
    out = []
    for st in sorted(glob.glob(os.path.join(OUT, '*.run.json')), key=os.path.getmtime, reverse=True):
        try: r = json.load(open(st))
        except Exception: continue
        outf = os.path.join(OUT, r['out']); done = lines(outf); tot = r['total']; now = time.time()
        live = any('evalpos' in l and outf in l for l in ps)
        if not live and now - os.path.getmtime(st) > 2 * 86400: continue
        last = os.path.getmtime(outf) if os.path.exists(outf) else r['started']
        el = (now if live else last) - r['started']; rate = (done - r['done0']) / el if el > 0 else 0
        frac = min(1.0, done / tot) if tot else 0
        state, label = ('running', 'Running') if live else ('finished', 'Complete') if done >= tot else ('stopped', 'Incomplete')
        meta = [f'{done:,} of {tot:,} positions ({100 * frac:.0f}%)', f"{r['threads']} thread{'s' if r['threads'] != 1 else ''}, "
                f"{r['seeds']} luck samples{' (staged)' if r.get('staged') else ''}"]
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
