"""The Play Pokémon channel's VGC streams, hands-free, on the local page (http://localhost:8768): while a main VGC stream is live
("VGC Day 2 | 2027 Pokémon Louisville Regional Championships"; not the Feature Station streams), follow it; between streams, show the
newest one.
  python3 evalbar/auto.py [threads=2] [port=8768]   the supervisor (the LaunchAgent runs this)
  python3 evalbar/auto.py streams                   the channel's VGC streams as the supervisor sees them
  python3 evalbar/auto.py install | uninstall       a LaunchAgent that keeps the supervisor running from the main checkout (started at
                                                    login, started again if it stops)
Every 30 seconds (the channel page every 5 minutes):
  - a VGC stream is live: follow it (from its start if there is no record of it yet, else from where the record stops). A follow that
    gets no new fragment for 5 minutes is started again (the fragment URL lasts about 6 hours). The Mac stays awake while it follows,
    on mains power only (caffeinate -s)
  - none is live: serve the newest VGC stream. One never read (the Mac was off) is read from the recording first (scan, 1 OCR worker
    and 2 fetchers), then served
  - CPU: a follow or scan, or a serve while it is evaluating, pauses (its whole process group, the page too) while everything else on the
    Mac (the Eval bar thread's other programs included) keeps 8 or more cores busy, and carries on below 6
  - the public page on the user's site: every 10 seconds what changed goes up (publish.py), once ~/.config/evalbar/site.json exists
The supervisor's log is evalbar/out/live/auto.log, its programs' output evalbar/out/live/auto_child.log."""
import os, re, sys, json, time, signal, plistlib, threading, subprocess
import common as C, procs as P, publish as PB
CHANNEL = 'https://www.youtube.com/@PlayPokemon/streams'
VGC = re.compile(r'^VGC Day \d+ \| \d{4} Pokémon .+ Championships$')
LIVE = os.path.join(C.HERE, 'out', 'live')
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36'
LABEL = 'local.evalbar.auto'; AGENT = os.path.expanduser(f'~/Library/LaunchAgents/{LABEL}.plist')
PAUSE, RESUME = 8, 6                                                     # other programs' busy cores
def log(*a): print(time.strftime('%-m/%-d %-I:%M %p'), *a, flush=True)
def tag(vid): return 'live_' + re.sub(r'\W', '', vid)[:16]                # as broadcast.py names a stream's files
def keep(vid): return os.path.join(LIVE, tag(vid) + '.ocr.jsonl')
def record(vid): return os.path.exists(keep(vid)) and not os.path.exists(keep(vid) + '.frames')   # a scan under way keeps its frames folder
def streams():
    """the channel's streams, newest first: [{'id', 'title', 'state': 'live', 'upcoming' or 'past'}]"""
    html = subprocess.run(['curl', '-sL', '--max-time', '30', '-A', UA, '-H', 'Accept-Language: en-US', CHANNEL], capture_output=True, text=True).stdout
    m = re.search(r'var ytInitialData = (\{.*?\});</script>', html, re.S)
    if not m: raise RuntimeError('no video list on the channel page')
    out = []
    def texts(x, acc):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ('text', 'content') and isinstance(v, str): acc.append(v)
                else: texts(v, acc)
        elif isinstance(x, list):
            for y in x: texts(y, acc)
        return acc
    def walk(x):
        if isinstance(x, dict):
            v = x.get('lockupViewModel')
            if v:
                badges = [b.strip().lower() for b in texts(v.get('contentImage', {}), [])]   # "LIVE", "Upcoming", or the length of a recording
                out.append({'id': v.get('contentId'), 'title': v.get('metadata', {}).get('lockupMetadataViewModel', {}).get('title', {}).get('content', ''),
                            'state': 'live' if 'live' in badges else 'upcoming' if 'upcoming' in badges else 'past'})
                return
            for y in x.values(): walk(y)
        elif isinstance(x, list):
            for y in x: walk(y)
    walk(json.loads(m.group(1)))
    return out
def busy_in(group):
    """cores busy in one process group"""
    tot = 0.0
    for l in subprocess.run(['ps', '-Aeo', 'pgid=,pcpu='], capture_output=True, text=True).stdout.splitlines():
        p = l.split()
        try:
            if len(p) == 2 and int(p[0]) == group: tot += float(p[1])
        except ValueError: pass
    return tot / 100
def others_busy(group=None):
    """cores busy with everything but the supervisor and its program's process group (ps's recent CPU share, summed); the Eval bar
    thread's other evalbar- processes count, since they are not the supervisor's to pause"""
    tot = 0.0
    for l in subprocess.run(['ps', '-Aeo', 'pid=,pgid=,pcpu='], capture_output=True, text=True).stdout.splitlines():
        p = l.split()
        try:
            if len(p) == 3 and int(p[0]) != os.getpid() and int(p[1]) != group: tot += float(p[2])
        except ValueError: pass
    return tot / 100
class Child:
    """the one program the supervisor runs: follow, serve or scan of one stream, in its own process group"""
    def __init__(s, threads, port):
        s.threads = threads; s.port = port; s.p = s.awake = None; s.mode = s.vid = None; s.since = 0; s.paused = False; s.fails = 0
    def alive(s): return s.p is not None and s.p.poll() is None
    def start(s, mode, vid):
        s.stop(); s.mode, s.vid = mode, vid
        if mode == 'follow': args = ['follow', vid] + ([] if record(vid) else ['at=0:00:00'])   # a stream new to the reader: from its start
        elif mode == 'serve': args = ['serve', vid]
        else: args = ['scan', vid, keep(vid), '1', '2']
        if mode != 'scan': args += [f'threads={s.threads}', f'port={s.port}']
        out = open(os.path.join(LIVE, 'auto_child.log'), 'a'); out.write(f"\n== {time.strftime('%-m/%-d %-I:%M %p')} {' '.join(args)}\n"); out.flush()
        s.p = subprocess.Popen([P.python(), os.path.join(C.HERE, 'broadcast.py')] + args, cwd=C.HERE, stdout=out, stderr=subprocess.STDOUT,
                               start_new_session=True)
        if s.awake: s.awake.poll()
        if mode == 'follow': s.awake = subprocess.Popen(['caffeinate', '-s', '-w', str(s.p.pid)])   # awake while it follows, on mains power
        s.since = time.time(); s.paused = False; log('started', ' '.join(args))
    def signal(s, sig):
        try: os.killpg(s.p.pid, sig)
        except (ProcessLookupError, PermissionError): pass
    def stop(s):
        if not s.alive(): s.p = None; return
        if s.paused: s.signal(signal.SIGCONT)
        s.signal(signal.SIGTERM)
        try: s.p.wait(15)
        except subprocess.TimeoutExpired: s.signal(signal.SIGKILL); s.p.wait()
        log('stopped', s.mode, s.vid); s.p = None
    def guard(s):
        """pause the program while the rest of the Mac is busy: a follow or scan always, a serve only while it is evaluating (an idle
        serve costs nothing, and pausing it would take the page down)"""
        if not s.alive(): return
        busy = others_busy(s.p.pid)                                   # its program leads its own process group
        working = s.mode != 'serve' or busy_in(s.p.pid) >= 0.5
        if not s.paused and working and busy >= PAUSE: s.signal(signal.SIGSTOP); s.paused = True; log(f'paused: other programs keep {busy:.1f} cores busy')
        elif s.paused and busy < RESUME: s.signal(signal.SIGCONT); s.paused = False; s.since = time.time(); log(f'carrying on ({busy:.1f} cores busy)')
    def stalled(s):
        """a follow that has fetched no fragment for 5 minutes (not counting its first 5 minutes or a pause)"""
        if s.mode != 'follow' or s.paused or time.time() - s.since < 300: return False
        pos = os.path.join(LIVE, tag(s.vid) + '_sq.txt')
        return not os.path.exists(pos) or time.time() - os.path.getmtime(pos) > 300
def main(threads=2, port=8768):
    os.makedirs(LIVE, exist_ok=True); child = Child(threads, port); seen = []; checked = 0; pub = PB.Publisher(port)
    def publish():
        while True:
            pub.tick(log); time.sleep(10)
    threading.Thread(target=publish, daemon=True).start()
    def bye(*a): child.stop(); sys.exit(0)
    signal.signal(signal.SIGTERM, bye); signal.signal(signal.SIGINT, bye)
    log(f'watching {CHANNEL} (page at http://localhost:{port})')
    while True:
        if time.time() - checked >= 300:
            checked = time.time()
            try:
                now = [x for x in streams() if VGC.match(x['title'])]
                if [(x['id'], x['state']) for x in now] != [(x['id'], x['state']) for x in seen]:
                    log('VGC streams:', '; '.join(f"{x['title']} ({x['state']})" for x in now[:4]))
                seen = now
            except Exception as e: log('channel page:', type(e).__name__, e)
        live = next((x for x in seen if x['state'] == 'live'), None); past = next((x for x in seen if x['state'] == 'past'), None)
        if live: want = ('follow', live['id'])
        elif past: want = ('serve' if record(past['id']) else 'scan', past['id'])     # a finished scan turns into serve
        else: want = None
        if want and (child.mode, child.vid) != want: child.fails = 0; child.start(*want)
        elif child.mode and not child.alive():                                  # it stopped by itself: start it again, waiting longer each time
            code = child.p.returncode if child.p else None
            if time.time() - child.since >= min(1800, 120 * 2 ** child.fails):
                log(f'{child.mode} {child.vid} stopped (exit {code}); starting it again'); child.fails += 1; child.start(child.mode, child.vid)
        elif child.stalled(): log('no new fragment for 5 minutes: starting the follow again'); child.start('follow', child.vid)
        pub.title = next((x['title'] for x in seen if x['id'] == child.vid), None)
        child.guard()
        time.sleep(30)
def install():
    """the LaunchAgent: the supervisor from the main checkout, with this shell's PATH (yt-dlp, ffmpeg)"""
    here = os.path.join(C.MAIN, 'evalbar'); py = os.path.join(C.MAIN, '.venv', 'bin', 'python3')
    if not os.path.exists(os.path.join(here, 'auto.py')): sys.exit('auto.py is not in the main checkout yet: merge it to main first')
    os.makedirs(os.path.join(here, 'out', 'live'), exist_ok=True); os.makedirs(os.path.dirname(AGENT), exist_ok=True)
    plistlib.dump({'Label': LABEL, 'ProgramArguments': [py if os.path.exists(py) else sys.executable, os.path.join(here, 'auto.py')],
                   'WorkingDirectory': here, 'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 60, 'Nice': 10,
                   'EnvironmentVariables': {'PATH': os.environ.get('PATH', '/usr/bin:/bin')},
                   'StandardOutPath': os.path.join(here, 'out', 'live', 'auto.log'), 'StandardErrorPath': os.path.join(here, 'out', 'live', 'auto.log')},
                  open(AGENT, 'wb'))
    dom = f'gui/{os.getuid()}'
    subprocess.run(['launchctl', 'bootout', f'{dom}/{LABEL}'], capture_output=True)
    subprocess.run(['launchctl', 'bootstrap', dom, AGENT], check=True); print(f'installed {LABEL}; log in {here}/out/live/auto.log')
def uninstall():
    subprocess.run(['launchctl', 'bootout', f'gui/{os.getuid()}/{LABEL}'], capture_output=True)
    if os.path.exists(AGENT): os.remove(AGENT)
    print(f'removed {LABEL}')
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['streams']:
        for x in streams():
            if VGC.match(x['title']): print(f"{x['state']:9s} {x['id']}  {x['title']}{'  (read)' if record(x['id']) else ''}")
    elif a[:1] == ['install']: install()
    elif a[:1] == ['uninstall']: uninstall()
    else:
        P.own(); kw = dict(x.split('=', 1) for x in a if '=' in x)
        main(int(kw.get('threads', 2)), int(kw.get('port', 8768)))
