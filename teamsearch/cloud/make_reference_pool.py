"""The pool smoke test's Mac reference for a sim setup (cloud/reference_pool.json): poolmode.search_team(trick_room_six, seed 123,
K=1) with TS_POOL_ES=1, TS_OPP=pool, the default bring step. A box's build must reproduce score and per-job wins exactly.
Each battle run gets a pssim/teamsearch_reference.log start line, so it shows on the progress page (localhost:8766) as it runs.
  cd teamsearch && bin/teamsearch-py cloud/make_reference_pool.py v26s v26 [threads=3]
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
SIMS_ = [a for a in sys.argv[1:] if not a.isdigit()]; THR = int(next((a for a in sys.argv[1:] if a.isdigit()), 3))
os.environ.update(TS_OPP='pool', TS_POOL_ES='1', TS_BRING_K='1')
import evaluate as E, poolmode as PM
LOG = os.path.join(E.PS, 'teamsearch_reference.log'); REF = os.path.join(HERE, 'cloud', 'reference_pool.json')
_run = E.run_jobs
def run_jobs(gids, jobs, per_job, seed0, threads, label, extra=None):
    d = os.path.join(HERE, 'runs', f'{label}_{E.team_key(gids)}'); os.makedirs(d, exist_ok=True)
    json.dump(jobs, open(os.path.join(d, 'jobs.json'), 'w'))
    rel = lambda p: os.path.relpath(p, E.PS)
    with open(LOG, 'a') as f:
        f.write(f"{time.strftime('%H:%M:%S')} {rel(os.path.join(d, 'jobs.json'))} -> {rel(os.path.join(d, 'out_' + E.out_tag(seed0, per_job)))}, "
                f"{per_job} games, Team search smoke reference {E.sim()}\n")
    r = _run(gids, jobs, per_job, seed0, threads, label, extra)
    with open(LOG, 'a') as f: f.write(f"{time.strftime('%H:%M:%S')} done: {len(jobs)} jobs\n")
    return r
E.run_jobs = run_jobs
team = json.load(open(os.path.join(HERE, 'teams', 'start', 'index.json')))['trick_room_six']['gids']
ref = json.load(open(REF))
for sim in SIMS_:
    os.environ['TS_SIM'] = sim; PM.keys.cache_clear() if hasattr(PM.keys, 'cache_clear') else None
    t0 = time.time(); r = PM.search_team(team, 123, THR, K=1); sec = time.time() - t0
    games = sum(n for _, n in r['per_job'].values())
    ref[sim] = dict(what=f"poolmode.search_team(trick_room_six, seed 123, K=1) with TS_POOL_ES=1, TS_OPP=pool, TS_SIM={sim} on the Mac ({THR} threads)",
                    score=r['score'], per_job={str(k): list(v) for k, v in r['per_job'].items()}, games=games, seconds=round(sec, 1))
    json.dump(ref, open(REF, 'w'), indent=1)
    print(f"{sim}: score {r['score']:.4f}, {games} games in {sec:.0f} s on {THR} threads ({sec * THR / max(1, games):.2f} thread-s per game)", flush=True)
