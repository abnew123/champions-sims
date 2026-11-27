"""Online tournament feed for the matchup predictor (the user, 2026-11-27: start on the tournament feed). Limitless's public API
(play.limitlesstcg.com/api) lists several Champions VGC online tournaments a day, each with every player's open team sheet and
every match's game-by-game winners: more games than the ladder replays, from stronger players on average, and a read on the
field that pro play draws from.

Each run lists the VGC tournaments in the formats from Reg M-B on (M-D and later are picked up when Limitless lists them) and
saves standings and pairings for the ones not saved yet, as raw JSON in predictor/tours/ (git-ignored: it has player names).
Polite: the API allows 50 requests in 5 minutes without a key, so one request each 6.2 s, and a 429 waits out its Retry-After.
A full backfill (about 1,200 tournaments, two requests each) takes about 4 hours; later runs list only the newest pages.
collect.py runs this after the replays, so the LaunchAgent keeps it current.
  teamsearch/bin/teamsearch-py predictor/fetch_tours.py [max tournaments]     -> predictor/tours/<id>.json, lines in collect.log
"""
import os, sys, json, time, fcntl, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, 'tours'); LOG = os.path.join(HERE, 'collect.log')
API = 'https://play.limitlesstcg.com/api'
UA = {'User-Agent': 'champions-sims research (personal, low rate)'}
FORMATS = ('M-B', 'M-C', 'M-D', 'M-E', 'M-F', 'M-G', 'M-H')

def say(s):
    with open(LOG, 'a') as f: f.write(f"{time.strftime('%m-%d %I:%M %p')} {s}\n")

PACE = 6.2

def get(path):
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(API + path, headers=UA), timeout=30) as r:
                time.sleep(PACE); return json.loads(r.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            time.sleep((int(e.headers.get('retry-after') or 60) + 2) if e.code == 429 else 10 + 20 * k)
        except Exception: time.sleep(10 + 20 * k)
    return None

def listing(pages=60):
    out = []
    for f in FORMATS:
        for pg in range(1, pages + 1):
            d = get(f'/tournaments?game=VGC&format={f}&limit=100&page={pg}')
            if not d: break
            out += [t for t in d if t.get('format') == f]
            if len(d) < 100: break
    return out

def main(cap=int(sys.argv[1]) if len(sys.argv) > 1 else 10 ** 6):
    os.makedirs(D, exist_ok=True); t0 = time.time()
    lock = open(os.path.join(D, '.lock'), 'w')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: say('tours: a run is already going; skipped'); return
    old = json.load(open(os.path.join(D, 'index.json'))) if os.path.exists(os.path.join(D, 'index.json')) else {}
    ts = listing(2 if old else 60); idx = old | {t['id']: t for t in ts}; ts = list(idx.values())
    json.dump(idx, open(os.path.join(D, 'index.json'), 'w'))
    todo = [t for t in sorted(ts, key=lambda t: (t['format'], t['date']), reverse=True)
            if t.get('players', 0) >= 8 and not os.path.exists(os.path.join(D, t['id'] + '.json'))][:cap]
    got = 0
    for k, t in enumerate(todo, 1):
        st = get(f"/tournaments/{t['id']}/standings")
        if st is None: continue                                          # not reachable now (rate limit): try again next run
        if not any(p.get('decklist') for p in st): open(os.path.join(D, t['id'] + '.json'), 'w').write('{"no_sheets": true}'); continue
        pr = get(f"/tournaments/{t['id']}/pairings")
        if pr is None: continue
        json.dump(dict(t=t, standings=st, pairings=pr), open(os.path.join(D, t['id'] + '.json'), 'w')); got += 1
        if k % 50 == 0: say(f"  tours: {k}/{len(todo)} tournaments")
    by = {}
    for t in ts: by[t['format']] = by.get(t['format'], 0) + 1
    say(f"tours: {len(ts)} listed ({', '.join(f'{f} {n}' for f, n in sorted(by.items()))}); {got} new saved; {int(time.time() - t0)} s")

if __name__ == '__main__': main()
