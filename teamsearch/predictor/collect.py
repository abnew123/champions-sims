"""Replay collection for the matchup predictor (the user, 2026-11-27: collect replays from the day M-D goes live, Dec 2, so the
predictor can learn the new species within days). Run every two hours by a LaunchAgent (install_collector.sh).

Each run: read Showdown's format list (config/formats.ts on GitHub) for the Champions VGC formats from Reg M-C on (M-D and later
are picked up the day they appear; the guessed M-D ids are tried as well), then walk each format's public replay search from the
newest page back and save the logs not yet saved, stopping at two fully saved pages in a row. The newest regulation goes first.
A run fetches at most CAP logs (the M-C backlog since Nov 13 fills over several runs). Polite: one request each 0.5 s.
Logs carry player names, so they go to predictor/replays/ (git-ignored) with an index of id, format, rating and upload time.
Then fetch_tours.py for the online tournaments.
  teamsearch/bin/teamsearch-py predictor/collect.py            -> predictor/replays/, lines in predictor/collect.log
"""
import os, re, sys, json, time, fcntl, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
D = os.path.join(HERE, 'replays'); OLD = os.path.join(ROOT, 'pssim', 'replays_protect'); LOG = os.path.join(HERE, 'collect.log')
UA = {'User-Agent': 'champions-sims research (personal, low rate)'}
CAP = int(os.environ.get('TS_COLLECT_CAP', 4000)); PAUSE = 0.5
GUESS = ['gen9championsvgc2026regmdbo3', 'gen9championsvgc2026regmd', 'gen9championsvgc2027regmdbo3', 'gen9championsvgc2027regmd']

def say(s):
    with open(LOG, 'a') as f: f.write(f"{time.strftime('%m-%d %I:%M %p')} {s}\n")

def get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                time.sleep(PAUSE); return r.read().decode('utf-8', 'replace')
        except Exception: time.sleep(3 + 5 * k)
    return None

def formats():
    """Champions VGC format ids from Reg M-C on, newest regulation first"""
    src = get('https://raw.githubusercontent.com/smogon/pokemon-showdown/master/config/formats.ts') or ''
    ids = {re.sub(r'[^a-z0-9]', '', n.lower()) for n in re.findall(r'name: "(\[Gen 9 Champions\] VGC \d+ Reg M-[A-Z][^"]*)"', src)}
    ids |= set(GUESS) | {'gen9championsvgc2026regmcbo3', 'gen9championsvgc2026regmc'}
    reg = lambda i: re.search(r'regm([a-z])', i).group(1)
    return sorted((i for i in ids if reg(i) >= 'c'), key=lambda i: (-ord(reg(i)), 'bo3' not in i))

def saved(rid): return os.path.exists(os.path.join(D, rid + '.log')) or os.path.exists(os.path.join(OLD, rid + '.log'))

def walk(fmt, idx, budget, stop_after=2):
    before, full, got, pages = None, 0, 0, 0
    while got < budget:
        txt = get(f'https://replay.pokemonshowdown.com/search.json?format={fmt}' + (f'&before={before}' if before else ''))
        if not txt: break
        try: res = json.loads(txt)
        except ValueError: break
        if not res: break
        pages += 1; new = 0
        for r in res[:50]:
            idx.setdefault(r['id'], {'fmt': fmt, 'rating': r.get('rating'), 'time': r.get('uploadtime')})
            if saved(r['id']): continue
            log = get(f"https://replay.pokemonshowdown.com/{r['id']}.log")
            if log: open(os.path.join(D, r['id'] + '.log'), 'w').write(log); new += 1; got += 1
            if got >= budget: break
        full = full + 1 if new == 0 else 0
        if full >= stop_after or len(res) <= 50: break
        before = res[min(len(res), 50) - 1]['uploadtime']
        if pages % 20 == 0: json.dump(idx, open(os.path.join(D, 'index.json'), 'w'))
    return got, pages

def main():
    os.makedirs(D, exist_ok=True)
    lock = open(os.path.join(D, '.lock'), 'w')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: say('collect: a run is already going; skipped'); return
    idx = json.load(open(os.path.join(D, 'index.json'))) if os.path.exists(os.path.join(D, 'index.json')) else {}
    t0 = time.time(); left = CAP; out = []
    for fmt in formats():
        if left <= 0: break
        got, pages = walk(fmt, idx, left); left -= got
        if pages: out.append(f"{fmt} +{got} ({pages} pages)")
        json.dump(idx, open(os.path.join(D, 'index.json'), 'w'))
    n = collections_count(idx)
    say(f"collect: {', '.join(out) or 'nothing listed'}; saved so far: {n}; {int(time.time() - t0)} s")
    lock.close()
    import fetch_tours; fetch_tours.main()                               # the online tournaments (it skips itself if a run is going)

def collections_count(idx):
    c = {}
    for k in idx:
        if saved(k): f = idx[k]['fmt']; c[f] = c.get(f, 0) + 1
    return ', '.join(f"{f} {n}" for f, n in sorted(c.items())) or 'none'

if __name__ == '__main__': main()
