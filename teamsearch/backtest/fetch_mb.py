"""M-B to M-C self-play backtest (the user, 2026-11-06: "go ahead with the M-B to M-C backtest"), step 1: the public Showdown Reg M-B
Bo3 replays of M-B's last weeks, the meta as it stood just before M-C. Cached in backtest/replays_mb/ (git-ignored: logs carry names
and chat; only protocol lines are ever read from them, as pssim/opp_pool.parse does). Polite as pssim/protect_replays.py (~0.3 s
between requests, resumes): the replay search's pages back in time from the newest, logs downloaded only for games uploaded within
[FIRST, LAST] (local dates); stops at the first page older than FIRST.
  python3 backtest/fetch_mb.py [first = 2026-08-19] [last = 2026-09-08]     -> replays_mb/<id>.log, replays_mb/index.json; log fetch_mb.log
"""
import json, os, sys, time, datetime, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, 'replays_mb'); os.makedirs(D, exist_ok=True)
FMT = 'gen9championsvgc2026regmbbo3'
FIRST = sys.argv[1] if len(sys.argv) > 1 else '2026-08-19'; LAST = sys.argv[2] if len(sys.argv) > 2 else '2026-09-08'
UA = {'User-Agent': 'champions-sims research (personal, low rate)'}
day = lambda t: datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d')
LOG = open(os.path.join(HERE, 'fetch_mb.log'), 'a')
def say(s): LOG.write(f"{datetime.datetime.now().strftime('%I:%M %p')} {s}\n"); LOG.flush()

def get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r: return r.read().decode()
        except Exception: time.sleep(2 + 3 * k)
    return None

def main():
    ip = os.path.join(D, 'index.json'); idx = json.load(open(ip)) if os.path.exists(ip) else {}
    before = None; got = 0; pg = 0
    say(f"fetching {FMT} from {FIRST} to {LAST}; {len(idx)} cached")
    while True:
        txt = get(f'https://replay.pokemonshowdown.com/search.json?format={FMT}' + (f'&before={before}' if before else '')); time.sleep(0.3)
        if not txt: say('search failed three times; stopping (rerun resumes)'); break
        res = json.loads(txt); pg += 1
        if not res: break
        for r in res[:50]:
            d = day(r['uploadtime'])
            if not (FIRST <= d <= LAST): continue
            p = os.path.join(D, f"{r['id']}.log")
            if r['id'] in idx and os.path.exists(p): continue
            log = get(f"https://replay.pokemonshowdown.com/{r['id']}.log"); time.sleep(0.3)
            if log: open(p, 'w').write(log); idx[r['id']] = {'fmt': FMT, 'rating': r.get('rating'), 'time': r['uploadtime']}; got += 1
        before = res[-1]['uploadtime']; json.dump(idx, open(ip, 'w'))
        if pg % 5 == 0 or day(before) < FIRST: say(f"page {pg}: back to {day(before)}, {got} new logs, {len(idx)} in the window")
        if day(before) < FIRST or len(res) <= 50: break
    say(f"fetch done: {len(idx)} logs from {FIRST} to {LAST}")

if __name__ == '__main__': main()
