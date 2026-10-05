"""Does the value's baseline (intercept) matter for team scores? (with Battle sim, 2026-10-05.) egvalue9 has slopes shared over
eleven teams and a per-team intercept; the planner has no absolute win-chance thresholds, so a wrong baseline can only act
through the sigmoid's curvature (risk attitude, mixed strategies). The 10 simcmp teams, full 60 jobs, their confirm seeds and
brings (paired with every other setup), under two arms:
  v12g = pssim/egvalue9.json for every team (the general intercept; also the sim-vs-real bar run: simreal.py v8 v12g)
  v12t = pssim/egvalue9_teams/<team key>.json, each team's own intercept (same slopes)
If team scores move by no more than ~1-2 points and the ranking holds, the general file is fine for the climb.
Threads: decomp_threads.txt if present (re-read before each team), else TS_THREADS.
  python3 intercept_test.py [--report]
"""
import json, os, sys, time, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.pop('TS_PERISH', None)
import evaluate as E, simcmp as S
import climb as C

def thr():
    try: return int(open(os.path.join(HERE, 'decomp_threads.txt')).read())
    except Exception: return int(os.environ.get('TS_THREADS', 3))

if __name__ == '__main__':
    report = '--report' in sys.argv; res = {}
    for arm in ('v12g', 'v12t'):
        os.environ['TS_SIM'] = arm                      # (after importing simcmp, which sets TS_SIM=v8)
        for n in S.DEFAULT:
            team, fixed, label, seed = S.latest(n)
            if arm == 'v12t': os.environ['TS_EG_VALUE'] = os.path.join(E.PS, 'egvalue9_teams', E.team_key(team) + '.json')
            else: os.environ.pop('TS_EG_VALUE', None)
            if report:
                try: r = E.read(os.path.join(HERE, 'runs', f'{E.team_key(team)}_{label}'), E.out_tag(seed, 4))
                except Exception: continue
            else:
                r = E.run_team(team, 4, seed, thr(), fixed=fixed, label=label)
                print(time.strftime('%I:%M %p'), arm, n, f"{100 * r['score']:.1f}", flush=True)
            res.setdefault(n, {})[arm] = r
    os.environ.pop('TS_EG_VALUE', None)
    done = [n for n in S.DEFAULT if len(res.get(n, {})) == 2]
    if not done: sys.exit()
    rank = {arm: {n: i + 1 for i, n in enumerate(sorted(done, key=lambda n: -res[n][arm]['score']))} for arm in ('v12g', 'v12t')}
    print(f"\n{'team':17s} {'general':>8s} {'own':>7s} {'own - general':>14s}  rank general -> own")
    ds = []
    for n in sorted(done, key=lambda n: -res[n]['v12g']['score']):
        m, se = C.paired(res[n]['v12g'], res[n]['v12t']); ds.append(m)
        print(f"{n:17s} {100 * res[n]['v12g']['score']:7.1f} {100 * res[n]['v12t']['score']:7.1f} {100 * m:+8.1f} ± {100 * se:.1f}   "
              f"{rank['v12g'][n]:2d} -> {rank['v12t'][n]:2d}")
    k = len(done); rg = [rank['v12g'][n] for n in done]; rt = [rank['v12t'][n] for n in done]
    rho = 1 - 6 * sum((a - b) ** 2 for a, b in zip(rg, rt)) / (k * (k * k - 1))
    print(f"\nmean |own - general| {100 * sum(map(abs, ds)) / k:.1f} points; rank correlation {rho:.2f} over {k} teams")
