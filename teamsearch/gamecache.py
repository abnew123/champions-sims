"""Cross-team game cache (2026-10-13, the v27 climb): a pool game depends only on our four (sets, lead, back), the opponent entry,
the setup and the seed, so the same game recurs whenever two teams (a start and its neighbours, a candidate and the current team)
bring the same four against the same entry. With Battle sim's per-job seed key (battle_starts.js: job.meta.seed_index, from
(group, entry) only) such a game is identical wherever it sits in a job list (34,242 of 34,263 repeats identical on the last climb's
games even at equal positions; the rest were per-team planner grids, which v26+ no longer use). On that climb 24% of all games
were repeats. One SQLite file (TS_GAME_CACHE), safe for the climb's threads and for separate processes.
"""
import json, os, sqlite3, threading, hashlib
_lock = threading.Lock(); _db = {}

def _conn(path):
    if path not in _db:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        c = sqlite3.connect(path, timeout=120, check_same_thread=False, isolation_level=None)
        c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA synchronous=NORMAL')
        c.execute('CREATE TABLE IF NOT EXISTS games (k TEXT PRIMARY KEY, v TEXT)')
        _db[path] = c
    return _db[path]

def key(setup, engine_data, seed0, per_job, job):
    """the game a job plays: setup name (frozen: binary, value, flags), engine data, seed base, games per job, and the job itself
    (our four in lead/back order, their four, the entry's meta with its seed_index)"""
    return hashlib.sha1(json.dumps([setup, os.path.basename(engine_data), seed0, per_job, job], sort_keys=True).encode()).hexdigest()

def get_many(path, keys):
    out = {}
    with _lock:
        c = _conn(path)
        for i in range(0, len(keys), 500):
            ks = keys[i:i + 500]
            for k, v in c.execute(f"SELECT k, v FROM games WHERE k IN ({','.join('?' * len(ks))})", ks): out[k] = json.loads(v)
    return out

def put_many(path, items):
    with _lock:
        c = _conn(path); c.execute('BEGIN')
        c.executemany('INSERT OR IGNORE INTO games (k, v) VALUES (?, ?)', [(k, json.dumps(v, separators=(',', ':'))) for k, v in items])
        c.execute('COMMIT')

def stats(path):
    with _lock: return _conn(path).execute('SELECT COUNT(*) FROM games').fetchone()[0]
