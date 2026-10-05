"""Training data for a multi-team value fit (Battle sim's request, 2026-10-05): the 10 simcmp teams (their latest six and brings)
against all 10 replay archetypes, 60 jobs x 4 games = 2,400 games, fresh seeds, under the candidate setup (TS_SIM=v12: egvalue8,
race, two-turn Protect check) with BATTLE_FEATS=1, so every result row carries its turn-start feature vectors ('F').
Outputs: runs/<team key>_<brings label>/out_v12_610000_4/<job>.json (each file has 'arch' and per-row 'F' and 'v').
Threads: the number in decomp_threads.txt if present (re-read before each team), else TS_THREADS.
  python3 feats_run.py            print the output folders at the end (also written to feats_run_dirs_<setup>.txt)
"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.pop('TS_PERISH', None); os.environ['BATTLE_FEATS'] = '1'
import evaluate as E, simcmp as S
os.environ['TS_SIM'] = os.environ.get('FEATS_SIM', 'v12')     # after importing simcmp, which sets TS_SIM=v8 (the first run, 4:58 am, got v8)
SEED = 610000

def thr():
    try: return int(open(os.path.join(HERE, 'decomp_threads.txt')).read())
    except Exception: return int(os.environ.get('TS_THREADS', 3))

if __name__ == '__main__':
    dirs = []
    for n in S.DEFAULT:
        team, fixed, label, _ = S.latest(n)
        r = E.run_team(team, 4, SEED, thr(), fixed=fixed, label=label)
        d = os.path.join(HERE, 'runs', f'{E.team_key(team)}_{label}', f'out_{E.out_tag(SEED, 4)}')
        dirs.append(d)
        print(time.strftime('%I:%M %p'), n, f"{100 * r['score']:.1f}", d, flush=True)
    open(os.path.join(HERE, f"feats_run_dirs_{E.sim()}.txt"), 'w').write('\n'.join(dirs) + '\n')
