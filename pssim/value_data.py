"""Training data for a better position value (2026-10-12, the user: start working towards a better position score). Every turn of the
cached ladder Bo3 games with open sheets (replays_protect/, both sides human) rebuilt as an engine position by the Eval bar's builder
(evalbar/spots.py: hindsight fours and sets, the usual spreads), Player 1's view, with the game's result:
  results/value/real_<part>.pos.jsonl   positions.js lines (state, name "<game> t<turn> p1")
  results/value/real_<part>.meta.jsonl  {name, game, turn, y (Player 1 won), rating (the two players' mean, if shown)}
part 'hold' = Eval bar's 560 accuracy-set games (the held-out set every value comparison here uses), 'fit' = the rest.
  ../.venv/bin/python3 value_data.py positions        (about 4,500 games; skips games the builder cannot rebuild)
  ../.venv/bin/python3 value_data.py search [threads=6]   results/value/real_<part>.eval.jsonl: the one-turn search on every position
      (champ evalpos as the planner runs it: 32 seeds, staged, sym2, no side-specific flags; about 1 s a position on one core)
  ../.venv/bin/python3 value_data.py feats [parts]    results/value/real_<part>.feats.jsonl / .vfeats.jsonl: champ feats (the 28 v22
      features, static) and champ vfeats (the matchup features, dev build)
  ../.venv/bin/python3 value_data.py positions new    games fetched since (in neither set) -> part 'new'; then search 6 new, feats new
  VALUE_OUT=results/value2 ../.venv/bin/python3 value_data.py rebuild    the rebuild by match (2026-10-15; see rebuild)
Outcomes and ratings come from the logs; names are only compared to find the winner, never kept."""
import os, sys, json, glob, collections, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'evalbar'))
OUT = os.environ.get('VALUE_OUT') or os.path.join(HERE, 'results', 'value')   # VALUE_OUT: another data folder (the rebuild, results/value2)
HOLD_SRC = os.path.join(ROOT, '.claude', 'worktrees', 'happy-hawking-473e61', 'evalbar', 'out', 'acc_p1.jsonl')
def held_games():
    """the Eval bar's accuracy-set games (names of its positions), or a saved copy of the list"""
    keep = os.path.join(OUT, 'hold_games.json')
    if os.path.exists(keep): return set(json.load(open(keep)))
    g = sorted({json.loads(l)['name'].split(' ')[0] for l in open(HOLD_SRC)})
    os.makedirs(OUT, exist_ok=True); json.dump(g, open(keep, 'w')); return set(g)
def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()
def stale(out, src):
    """an output made from another version of its positions file (its <out>.src stamp differs, or it has none) is removed, so evalpos's
    resume-by-name never keeps search targets of positions that were rebuilt (the outside review, 2026-10-14: a position rebuilt from a
    win to a loss still scored 1.0). Returns the source's hash, to stamp the output with once it is complete."""
    h = sha(src); st = out + '.src'
    if os.path.exists(out) and (not os.path.exists(st) or open(st).read().strip() != h):
        os.remove(out); print('removed a stale output:', os.path.basename(out))
    return h
def stamp(out, h): open(out + '.src', 'w').write(h + '\n')
def outcome(log):
    players, win, ratings = {}, None, []
    for l in log.split('\n'):
        if l.startswith('|player|'):
            f = l.split('|')
            if len(f) > 3 and f[3]:
                players[f[3]] = f[2]
                if len(f) > 5 and f[5].strip().isdigit(): ratings.append(int(f[5]))
        elif l.startswith('|win|'): win = l.split('|')[2]
    w = players.get(win) if win else None
    return (None if w is None else 1.0 if w == 'p1' else 0.0), (sum(ratings) / len(ratings) if len(ratings) == 2 else None)
def positions(new=False):
    """new: only games in neither the fit nor the held-out set (replays fetched later) -> part 'new'"""
    import spots as SP, live as LV
    held = held_games(); os.makedirs(OUT, exist_ok=True)
    known = set()
    if new:
        for part in ('fit', 'hold'): known |= {json.loads(l)['game'] for l in open(os.path.join(OUT, f'real_{part}.meta.jsonl'))}
    parts = ('new',) if new else ('fit', 'hold')
    specs = {k: [] for k in parts}; meta = {k: [] for k in parts}; why = collections.Counter()
    for f in sorted(glob.glob(os.path.join(HERE, 'replays_protect', '*.log'))):
        gid = os.path.basename(f)[:-4]
        if new and gid in known: continue
        log = open(f, errors='replace').read()
        if '|showteam|' not in log: why['no open sheets'] += 1; continue
        y, rating = outcome(log)
        if y is None: why['no winner'] += 1; continue
        try: sp, w = SP.specs(gid, log)
        except Exception as e: why['builder error'] += 1; continue
        if not sp: why[w or 'nothing built'] += 1; continue
        part = 'new' if new else 'hold' if gid in held else 'fit'
        for s in sp:
            specs[part].append((1.0, s)); meta[part].append({'name': s['name'] + ' p1', 'game': gid, 'turn': s['turn'], 'y': y, 'rating': rating})
    for part in parts:
        posf = os.path.join(OUT, f'real_{part}.pos.jsonl')
        if os.path.exists(posf): os.remove(posf)
        for i in range(0, len(specs[part]), 2000):   # positions.js appends; chunks keep node's memory small
            tmp = posf + f'.{i}'
            LV.positions(specs[part][i:i + 2000], tmp)
            with open(posf, 'a') as o: o.write(open(tmp).read())
            os.remove(tmp)
        with open(os.path.join(OUT, f'real_{part}.meta.jsonl'), 'w') as o:
            for m in meta[part]: o.write(json.dumps(m) + '\n')
        print(f"{part}: {len(meta[part])} positions from {len({m['game'] for m in meta[part]})} games -> {posf}")
    print('skipped games:', dict(why))
def match_key(log):
    """the Bo3 match a cached game belongs to: its two players (compared, never kept) and its day; a rematch the same day joins it"""
    names = sorted(l.split('|')[3].strip().lower() for l in log.split('\n') if l.startswith('|player|') and len(l.split('|')) > 3 and l.split('|')[3])
    t = next((int(l.split('|')[2]) for l in log.split('\n') if l.startswith('|t:|') and l.split('|')[2].strip().isdigit()), 0)
    return hashlib.sha256(('|'.join(names) + '|' + str(t // 86400)).encode()).hexdigest()[:16]
def rebuild():
    """The value data rebuilt (2026-10-15, the outside review: the cached positions predate the shared builder's fixes, and 238 of the 560
    held-out games share a Bo3 match with a training game). Every cached game with open sheets through the Eval bar's current builder
    (spots.specs: battlestate, the parser fixes on by default), read as the Bo3 bot reads (spreads.FITTED on, DMG_FLAGS empty), and split
    by match: 'hold' = every match holding one of the Eval bar's 560 accuracy games (the final test), 'val' = a fixed tenth of the other
    matches (model selection), 'fit' = the rest. Into VALUE_OUT (results/value2), with the match on each meta line."""
    import spots as SP, live as LV, spreads
    spreads.FITTED = True; spreads.DMG_FLAGS = {}
    held = held_games(); os.makedirs(OUT, exist_ok=True)
    games = []; why = collections.Counter()
    for f in sorted(glob.glob(os.path.join(HERE, 'replays_protect', '*.log'))):
        gid = os.path.basename(f)[:-4]; log = open(f, errors='replace').read()
        if '|showteam|' not in log: why['no open sheets'] += 1; continue
        y, rating = outcome(log)
        if y is None: why['no winner'] += 1; continue
        games.append((gid, log, y, rating, match_key(log)))
    if os.environ.get('REBUILD_LIMIT'): games = games[:int(os.environ['REBUILD_LIMIT'])]   # a smoke test on the first n games
    hold_m = {m for gid, _, _, _, m in games if gid in held}
    part_of = lambda gid, m: 'hold' if m in hold_m else 'val' if int(m, 16) % 10 == 0 else 'fit'
    parts = ('fit', 'val', 'hold'); specs = {k: [] for k in parts}; meta = {k: [] for k in parts}
    for i, (gid, log, y, rating, m) in enumerate(games):
        if i % 2000 == 0: print(f"{i} / {len(games)} games", flush=True)
        try: sp, w = SP.specs(gid, log)
        except Exception as e: why['builder error'] += 1; continue
        if not sp: why[w or 'nothing built'] += 1; continue
        part = part_of(gid, m)
        for x in sp:
            specs[part].append((1.0, x)); meta[part].append({'name': x['name'] + ' p1', 'game': gid, 'match': m, 'turn': x['turn'], 'y': y, 'rating': rating})
    for part in parts:
        posf = os.path.join(OUT, f'real_{part}.pos.jsonl')
        if os.path.exists(posf): os.remove(posf)
        for i in range(0, len(specs[part]), 2000):
            tmp = posf + f'.{i}'
            LV.positions(specs[part][i:i + 2000], tmp)
            with open(posf, 'a') as o: o.write(open(tmp).read())
            os.remove(tmp)
        with open(os.path.join(OUT, f'real_{part}.meta.jsonl'), 'w') as o:
            for x in meta[part]: o.write(json.dumps(x) + '\n')
        print(f"{part}: {len(meta[part])} positions from {len({x['game'] for x in meta[part]})} games, {len({x['match'] for x in meta[part]})} matches -> {posf}", flush=True)
    print('skipped games:', dict(why))
ENV = dict(RACE_TIES='avg', RACE='1', TRSYM='1', CALC_DATA='../native/champions_data.json', EG_VALUE='egvalue9_sym2.json', EG_MEGA_TIE='0')
BIN = os.path.join(ROOT, 'native', 'champ', 'bin', 'battlesim-champ'); DATA = '../native/engine_data_full.json'
def grid():
    g = os.path.join(OUT, 'emptygrid'); os.makedirs(g, exist_ok=True); return g
def search(threads=6, parts=('hold', 'fit')):
    import subprocess
    env = dict(os.environ, **ENV, EVAL_SEEDS='32', EVAL_ADAPT='1', GRID_DIR=grid())
    for part in parts:
        src, out = os.path.join(OUT, f'real_{part}.pos.jsonl'), os.path.join(OUT, f'real_{part}.eval.jsonl')
        h = stale(out, src)   # a resumed run continues only on the same positions
        subprocess.run([BIN, 'evalpos', DATA, src, out, str(threads)], cwd=HERE, env=env, check=True); stamp(out, h)
def feats(parts=('hold', 'fit')):
    """champ feats (the 28 v22 features) and champ vfeats (vfeats.rs, the dev build) for each part"""
    import subprocess
    env = dict(os.environ, **ENV, RACE_PRIO='1', FEATS22='1', GRID_DIR=grid())
    for part in parts:
        for cmd, binary in (('feats', BIN), ('vfeats', BIN + '-dev')):
            out, src = os.path.join(OUT, f'real_{part}.{cmd}.jsonl'), os.path.join(OUT, f'real_{part}.pos.jsonl')
            if os.path.exists(out): os.remove(out)
            h = sha(src); subprocess.run([binary, cmd, DATA, src, out, '2'], cwd=HERE, env=env, check=True); stamp(out, h)
if __name__ == '__main__':
    a = sys.argv[1:]
    P = tuple(a[2].split(',')) if len(a) > 2 else ('hold', 'fit')
    {'rebuild': rebuild, 'positions': lambda: positions(len(a) > 1 and a[1] == 'new'), 'search': lambda: search(int(a[1]) if len(a) > 1 else 6, P),
     'feats': lambda: feats(tuple(a[1].split(',')) if len(a) > 1 else ('hold', 'fit'))}[a[0]]()
