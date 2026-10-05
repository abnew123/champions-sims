"""Which part of the v3 -> v8 change made Sun, Indeedee TR and Snow harder? (Battle sim's request, 2026-10-05.) The 10 simcmp teams,
same brings and seeds as their confirm games, against those three archetypes only, under four setups:
  A = v3 + egvalue5 (cached, cloud_results)   B = v8 binary + egvalue6b (status weights only)
  C = B's binary + egvalue7 + RACE (no DP2)   D = v8 = C + DP2 (cached, runs/)
Per setup: pair-share-weighted mean win share per archetype, and how often Trick Room was up by turn 3 / at any point
(over the 8 teams without a Trick Room move, so that Trick Room is the opponent's).
  TS_THREADS=3 python3 decomp.py [--report]
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.pop('TS_PERISH', None)
import evaluate as E, simcmp as S
P = E.P
ARCHS = ['Sun', 'Indeedee TR / Psychic Terrain', 'Snow']

def summarize(rows_by_job, jobs):
    """{arch: (win share, n games, TR by turn 3, TR at any point)} from per-job row lists"""
    out = {}
    for a in ARCHS:
        sh = P.pair_shares(a); num = den = 0.0; n = tr3 = trany = 0
        for j, job in enumerate(jobs):
            if job['arch'] != a: continue
            vs = [x for x in rows_by_job[j] if not x.get('unsupported')]
            if vs: num += sh[job['k']] * sum(x['v'] for x in vs) / len(vs); den += sh[job['k']]
            n += len(vs); tr3 += sum(bool(x['trBy'][2]) for x in vs); trany += sum(x['trTurns'] > 0 for x in vs)
        out[a] = (num / den if den else None, n, tr3, trany)
    return out

def cached(d, tag):
    jobs = json.load(open(os.path.join(d, 'jobs.json')))
    return summarize({j: json.load(open(os.path.join(d, f'out_{tag}', f'{j}.json')))['rows'] for j in range(len(jobs))}, jobs)

if __name__ == '__main__':
    thr = int(os.environ.get('TS_THREADS', 3)); res = {}
    for n in S.DEFAULT:
        team, fixed, label, seed = S.latest(n)
        key = f'{E.team_key(team)}_{label}'
        jobs = [j for j in json.load(open(os.path.join(HERE, 'runs', key, 'jobs.json'))) if j['arch'] in ARCHS]
        r = dict(A=cached(os.path.join(HERE, 'cloud_results', 'runs', key), f'{seed}_4'),
                 D=cached(os.path.join(HERE, 'runs', key), f'v8_{seed}_4'))
        for setup, simname in (('B', 'v8b'), ('C', 'v8c')):
            os.environ['TS_SIM'] = simname
            if '--report' in sys.argv:
                d = os.path.join(HERE, 'runs', f'decomp_{simname}_{E.team_key(team)}', f'out_{simname}_{seed}_4')
                if not os.path.isdir(d): continue
                rows = [json.load(open(os.path.join(d, f'{j}.json'))) for j in range(len(jobs))]
            else:
                rows = E.run_jobs(team, jobs, 4, seed, thr, f'decomp_{simname}')
            r[setup] = summarize({j: x['rows'] for j, x in enumerate(rows)}, jobs)
        res[n] = r
        print(n, ' '.join(f"{s}:{100 * sum(r[s][a][0] for a in ARCHS) / 3:.1f}" for s in 'ABCD' if s in r), flush=True)
    has_tr = {n for n in S.DEFAULT if any('Trick Room' in E.G[g]['moves'] for g in S.latest(n)[0])}
    print(f"\nmean win share over the {len(res)} teams (A = v3, B = + status weights, C = + race, D = + two-turn Protect check = v8)")
    for a in ARCHS:
        print(f"  {a[:28]:28s} " + '   '.join(f"{s} {100 * sum(res[n][s][a][0] for n in res) / len(res):5.1f}" for s in 'ABCD' if all(s in res[n] for n in res)))
    print(f"\nTrick Room up by turn 3 / at any point (the {len(res) - len(has_tr & set(res))} teams without a Trick Room move)")
    for a in ARCHS:
        cells = []
        for s in 'ABCD':
            if not all(s in res[n] for n in res): continue
            g = sum(res[n][s][a][1] for n in res if n not in has_tr)
            cells.append(f"{s} {100 * sum(res[n][s][a][2] for n in res if n not in has_tr) / g:4.1f} / {100 * sum(res[n][s][a][3] for n in res if n not in has_tr) / g:4.1f}%")
        print(f"  {a[:28]:28s} " + '   '.join(cells))
    json.dump(res, open(os.path.join(HERE, 'decomp.json'), 'w'), indent=1)
