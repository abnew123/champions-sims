"""Score named teams on the configured opponent field (user, 2026-10-08: the regional Rain teams whose 24 moves are all sure hits,
without Floette-Eternal, which the user can't recruit). Each team gets the configured bring search (plan-aware in
cloud/run_env_arch.sh) on fresh seeds (86000 / 886000), then BATCHES confirm batches; reference teams can ride along in the same file.
Scores from separate runs differ by a few points (bring-search luck, different games): compare teams within one run.
  . cloud/run_env_arch.sh && TS_PARALLEL=30 TS_THREADS=3 python3 scoreteams.py <teams.json: {name: [6 set ids]}> [batches=6]
Writes runs/scoreteams_<file stem>.json.
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import climb as C, evaluate as E, poolmode as PM, accrefine as A
G = C.GRID
if __name__ == '__main__':
    T = json.load(open(sys.argv[1])); B = int(sys.argv[2]) if len(sys.argv) > 2 else 6; thr = int(os.environ.get('TS_THREADS', 3))
    A.cells_for({g for t in T.values() for g in t})
    teams = list({C.key_s(t): t for t in T.values()}.values()); by = {C.key_s(t): t for t in teams}
    print(time.strftime('%I:%M %p'), f"{E.sim()}: {len(teams)} teams, {B} batches", flush=True)
    scr = dict(zip(map(C.key_s, teams), E.search_many(teams, 86000)))
    items = [(k, b) for k in by for b in range(B)]
    res = dict(zip(items, E.parallel(lambda kb: PM.evaluate_team(by[kb[0]], scr[kb[0]]['chosen'], 886000 + 50 * kb[1], thr), items, 'score')))
    zero = lambda r: dict(per_job={j: (0, 1) for j in r['per_job']}, w_job=r['w_job'], by_arch={k: 0.0 for k in r['by_arch']})
    out = []
    for n, t in T.items():
        k = C.key_s(t); _, se = C.pooled([(zero(res[(k, b)]), res[(k, b)]) for b in range(B)])
        out.append(dict(name=n, score=sum(res[(k, b)]['score'] for b in range(B)) / B, se=se, sure_hits=A.accurate(t), team=t, brings=scr[k]['chosen']))
    print('\nscores (win share against the field; ± over games only, not bring-search luck):')
    for r in sorted(out, key=lambda r: -r['score']):
        print(f"  {r['name']:22s} {100 * r['score']:5.1f} ± {100 * r['se']:.1f}   sure hits {r['sure_hits']}/24   "
              + ', '.join(('M-' if C.is_mega(g) else '') + G[g]['species'] for g in r['team']), flush=True)
    for r in sorted(out, key=lambda r: -r['score']):
        print(f"\n  {r['name']}"); [print(f"      {A.show(g)}") for g in r['team']]
    json.dump(out, open(os.path.join(HERE, 'runs', f"scoreteams_{os.path.splitext(os.path.basename(sys.argv[1]))[0]}.json"), 'w'), indent=1)
