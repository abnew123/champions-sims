"""Engine evaluation of replay positions: builds the positions and runs the engine's `evalpos` (champ-battle-v16) with the bar's settings (egvalue9_sym2.json: the symmetric value with Trick Room tied to its real-game weight; the symmetric value
file, damage race with Speed ties averaged, either side may reverse Trick Room, no matchup grid).
  python3 evalbar/engine.py positions <out.jsonl> [both|p1] <replay id ...>      positions for these games (default view: p1; evalpos reports both sides)
  python3 evalbar/engine.py positions <out.jsonl> [both|p1] sample <n> [skip]    for n cached games in a fixed shuffled order, after skipping `skip`
  python3 evalbar/engine.py run <positions.jsonl> <out.jsonl> [threads=1] [seeds=32] [staged=1]
staged=1 (EVAL_ADAPT): every cell gets 2 samples of the turn's luck, options still in contention 8, the closest ones all `seeds`; options
more than 0.15 below a side's best keep their rough 2-sample value. staged=0 gives every cell `seeds` samples.
A run appends to <out.jsonl> and skips positions already in it, so it resumes. It writes <out.jsonl>.run.json for the progress page at
localhost:8766 (status.py); EVAL_TITLE names its card. EG_VALUE picks another value file (in the main folder's pssim/);
CHAMP_BIN and CHAMP_DATA (a file in native/) another engine and data (the live mode: champ-battle-v23 with engine_data_full.json). Agree cores with the other threads before threads > 1."""
import os, sys, json, zlib, time, subprocess
import common as C, procs as P
BIN = os.environ.get('CHAMP_BIN') or os.path.join(C.MAIN, 'native', 'champ', 'bin', 'champ-battle-v16'); MP = os.path.join(C.MAIN, 'pssim')
def positions(outf, views, ids):
    import spots as S
    specs = []; skipped = {}
    for rid in ids:
        sp, why = S.specs(rid, open(os.path.join(C.LOGS, rid + '.log')).read())
        if why: skipped[why.split(':')[0]] = skipped.get(why.split(':')[0], 0) + 1
        specs += sp
    tmp = outf + '.specs.json'; json.dump(specs, open(tmp, 'w'))
    subprocess.run([P.exe('node'), os.path.join(C.HERE, 'positions.js'), os.path.abspath(tmp), os.path.abspath(outf), views], cwd=MP, check=True)
    os.remove(tmp); print(f"{len(ids)} games, {len(specs)} turns; skipped games: {skipped or 'none'}")
def sample(n, skip=0):
    """cached games in a fixed pseudo-random order (by a hash of the replay id), so a larger sample extends a smaller one"""
    ids = sorted((rid for rid, _ in C.games()), key=lambda r: zlib.crc32(('s' + r).encode()))
    return ids[skip:skip + n]
def count(f): return sum(1 for _ in open(f, 'rb')) if os.path.exists(f) else 0
def stamp(posf, outf, threads, seeds, staged, title=None):
    """<out>.run.json, read by status.py for the shared progress page"""
    json.dump({'title': title or os.environ.get('EVAL_TITLE') or os.path.basename(outf), 'out': os.path.relpath(outf, os.path.dirname(os.path.abspath(outf))),
               'total': count(posf), 'done0': count(outf), 'started': time.time(), 'threads': threads, 'seeds': seeds, 'staged': bool(staged)},
              open(outf + '.run.json', 'w'))
def run(posf, outf, threads=1, seeds=32, staged=1, extra=None, nice=0):
    """extra: more environment for this run only (EVAL_MATRIX for the luck pass); nice: run the engine at that lower priority"""
    grid = os.path.join(C.HERE, 'out', 'emptygrid'); os.makedirs(grid, exist_ok=True); stamp(posf, outf, threads, seeds, staged)
    env = {**os.environ, 'RACE_TIES': 'avg', 'EVAL_SEEDS': str(seeds), **({'EVAL_ADAPT': '1'} if staged else {}), 'EG_VALUE': os.environ.get('EG_VALUE', 'egvalue9_sym2.json'), 'RACE': '1', 'TRSYM': '1',
           'CALC_DATA': '../native/champions_data.json', 'GRID_DIR': grid, **(extra or {})}       # extra can override any of these
    alt = (extra or {}).get('CHAMP_BIN')                                     # another engine for this run only (the luck pass), under its own link
    subprocess.run([P.exe('champ', alt, name='champ-alt') if alt else P.exe('champ', os.environ.get('CHAMP_BIN') or BIN), 'evalpos', '../native/' + ((extra or {}).get('CHAMP_DATA') or os.environ.get('CHAMP_DATA', 'engine_data_spot.json')), os.path.abspath(posf), os.path.abspath(outf), str(threads)], cwd=MP, env=env, check=True,
                   preexec_fn=(lambda: os.nice(nice)) if nice else None)
if __name__ == '__main__':
    P.own()
    a = sys.argv[1:]
    if a[0] == 'positions':
        views = a[2] if a[2] in ('both', 'p1') else 'p1'; rest = a[3:] if a[2] in ('both', 'p1') else a[2:]
        positions(a[1], views, sample(int(rest[1]), int(rest[2]) if len(rest) > 2 else 0) if rest[0] == 'sample' else rest)
    elif a[0] == 'run': run(a[1], a[2], *(int(x) for x in a[3:6]))
