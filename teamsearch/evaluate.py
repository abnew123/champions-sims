"""Evaluator for the hill climb: full 4v4 battles (the other thread's champ battle, stable binary bin/champ-battle-v1) against the
replay archetypes (pssim/opp_model_{a,b}.json): 10 archetypes x their 6 modelled lead pairs = 60 jobs per team, always in the same
order, so game g of job j uses the same opponent and RNG streams for every team (paired comparisons; G0 = seed0).
My four and leads per archetype come from the bring heuristic (bring/policy.py).
Score = sum over archetypes of share x (lead-pair-share-weighted mean win share over its 6 jobs); games with mechanics the engine
can't run ('unsupported') are dropped.

Per team, under runs/<team key>/: myteam.json, jobs.json, grid/ (one-on-one cells for the planner), starts_*.jsonl, out_*/.
  env: TS_SIM (sim setup, see SIMS), TS_PERISH=real (Perish trap from real data, see perish_stock.py), TS_EG_VALUE (value weights, default pssim/egvalue5.json: 4v4 self-play, second round), TS_ANTICIPATE (default 1), TS_PARALLEL (teams at once, default 1), TS_THREADS (threads each)
"""
import json, os, sys, hashlib, subprocess, time, shutil
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..'); PS = os.path.join(ROOT, 'pssim')
sys.path.insert(0, os.path.join(HERE, 'bring')); sys.path.insert(0, os.path.join(HERE, 'mx'))
import policy as P
import merge as MG
G = P.Fx.G
ARCHS = list(P.ARCH_SHARE)
# Sim setups (TS_SIM). 'v3' = what rounds 1-4 on AWS used. 'v8' = the other thread's recommendation of 2026-10-04: two-turn
# Protect check, damage-race value features, egvalue7 (status/Tailwind weights from real games). Outputs of non-default setups
# go to out_<sim>_<seed>_<pj>, so caches of different setups never mix.
V12_ENV = {'BATTLE_ANTICIPATE': '1', 'DP2': '1', 'RACE': '1', 'CALC_DATA': '../native/champions_data.json'}
SIMS = {
    'v3': dict(bin='champ-battle-v3', eg='egvalue5.json', env={'BATTLE_ANTICIPATE': '1'}),
    'v8': dict(bin='champ-battle-v8', eg='egvalue7.json',
               env={'BATTLE_ANTICIPATE': '1', 'DP2': '1', 'RACE': '1', 'CALC_DATA': '../native/champions_data.json'}),
    # in-between setups for Battle sim's decomposition of v3 -> v8 (decomp.py): status weights only; status weights + race
    'v8b': dict(bin='champ-battle-v8', eg='egvalue6b.json', env={'BATTLE_ANTICIPATE': '1'}),
    'v8c': dict(bin='champ-battle-v8', eg='egvalue7.json',
                env={'BATTLE_ANTICIPATE': '1', 'RACE': '1', 'CALC_DATA': '../native/champions_data.json'}),
    # v12 (Battle sim, 2026-10-05): egvalue8 refit; eg_b = side 1's (the opponent's) value file when it differs from ours.
    # 'v12' is the candidate (race on both sides); the others split the race by side (decomp.py).
    'v12': dict(bin='champ-battle-v12', eg='egvalue8.json', env=V12_ENV),
    'v12nr': dict(bin='champ-battle-v12', eg='egvalue8_norace.json', env=V12_ENV),
    'v12ro': dict(bin='champ-battle-v12', eg='egvalue8.json', eg_b='egvalue8_norace.json', env=V12_ENV),
    'v12rt': dict(bin='champ-battle-v12', eg='egvalue8_norace.json', eg_b='egvalue8.json', env=V12_ENV),
    # egvalue9 (shared slopes over eleven teams): 'v12g' = the general intercept; 'v12t' = the same, run with each team's own
    # intercept file via TS_EG_VALUE (intercept_test.py), kept under its own output tag
    'v12g': dict(bin='champ-battle-v12', eg='egvalue9.json', env=V12_ENV),
    'v12t': dict(bin='champ-battle-v12', eg='egvalue9.json', env=V12_ENV),
}
def sim(): return os.environ.get('TS_SIM', 'v3')
def out_tag(seed0, per_job): return f'{seed0}_{per_job}' if sim() == 'v3' else f'{sim()}_{seed0}_{per_job}'
def bin_path():
    """the battle binary, read at call time: TS_BATTLE_BIN if set (climb.py's legacy per-round pin), else the TS_SIM setup's"""
    return os.environ.get('TS_BATTLE_BIN', os.path.join(ROOT, 'native', 'champ', 'bin', SIMS[sim()]['bin']))
def sim_env():
    e = dict(SIMS[sim()]['env']); e['EG_VALUE'] = os.environ.get('TS_EG_VALUE', os.path.join(PS, SIMS[sim()]['eg']))
    if SIMS[sim()].get('eg_b'): e['EG_VALUE_B'] = os.path.join(PS, SIMS[sim()]['eg_b'])
    if 'TS_ANTICIPATE' in os.environ: e['BATTLE_ANTICIPATE'] = os.environ['TS_ANTICIPATE']
    return e

# Perish trap from real data (TS_PERISH=real; user, 2026-10-05; table from perish_stock.py): its 6 jobs are skipped and the
# archetype is scored at the real regional rate that teams of our team's archetype had against Perish. Perish is the last
# archetype, so the other 54 jobs keep their indices (and their paired seeds).
PERISH = 'Perish trap'
assert ARCHS[-1] == PERISH
def perish_real(): return os.environ.get('TS_PERISH') == 'real'
def live_archs(): return [a for a in ARCHS if not (perish_real() and a == PERISH)]
_STOCK = {}
def perish_stock(species):
    """real per-game win rate vs Perish for a team of these species (pssim/pro_replays.arch labels, as in archmatch.py)"""
    if not _STOCK:
        _STOCK.update(json.load(open(os.path.join(HERE, 'perish_stock.json'))))
        if PS not in sys.path: sys.path.insert(0, PS)
    from pro_replays import arch
    return _STOCK['rate'].get(arch(list(species)), _STOCK['pooled'])

def team_key(gids): return hashlib.md5('|'.join(sorted(gids)).encode()).hexdigest()[:12]

def prepare(gids, fixed=None, label=''):
    """team files + bring choices; returns the run directory.
    fixed: {arch: (lead gids, back gids)} to override the heuristic (e.g. the sheet's picks), stored under its own label"""
    d = os.path.join(HERE, 'runs', team_key(gids) + (f'_{label}' if label else ''))
    pick = P.chooser()
    stamp = '|'.join(f"{os.path.getmtime(f):.0f}" for f in (os.path.join(HERE, 'bring', 'bring_model.json'), P.OUTCOME) if os.path.exists(f)) \
            + f'|{pick.__name__}'                                                          # brings depend on the fitted model(s)
    tj = os.path.join(d, 'team.json')
    def ensure_grid():                                  # (grid/ isn't copied home from the cloud; rebuild it if missing)
        if not os.path.exists(os.path.join(d, 'grid', 'gx_cells_tr_inc.json')): MG.merge_gids(os.path.join(d, 'grid'), gids)
    if fixed is not None and os.path.exists(tj) and os.path.exists(os.path.join(d, 'jobs.json')):
        ensure_grid(); return d                         # fixed brings don't depend on the bring model: never wipe these results
    if os.path.exists(tj) and json.load(open(tj)).get('model_stamp') == stamp and json.load(open(tj)).get('cells_complete'):
        ensure_grid(); return d
    if fixed is None: shutil.rmtree(d, ignore_errors=True)                                  # stale brings: battles redone too
    os.makedirs(d, exist_ok=True)
    team = {G[g]['species']: {k: G[g][k] for k in ('species', 'item', 'ability', 'nature', 'evs', 'moves')} for g in gids}
    json.dump(team, open(os.path.join(d, 'myteam.json'), 'w'), indent=1)
    jobs, brings = [], {}
    for arch in ARCHS:
        lead, back, lp = (*fixed[arch], None) if fixed and arch in fixed else pick(gids, arch)
        brings[arch] = dict(lead=lead, back=back, logp=lp)
        for k in range(P.K):
            jobs.append(dict(arch=arch, k=k, lead=[G[g]['species'] for g in lead], back=[G[g]['species'] for g in back]))
    json.dump(jobs, open(os.path.join(d, 'jobs.json'), 'w'), indent=0)
    miss = MG.merge_gids(os.path.join(d, 'grid'), gids)
    if miss: print('  warning: no one-on-one cells for', miss, flush=True)
    json.dump(dict(gids=gids, brings=brings, model_stamp=stamp, cells_complete=not miss), open(tj, 'w'), indent=1)
    return d

def run_team(gids, per_job, seed0, threads, fixed=None, label=''):
    d = prepare(gids, fixed, label)
    tag = f'{seed0}_{per_job}'
    jobs_f, sfx = os.path.join(d, 'jobs.json'), ''
    if perish_real():                                   # only the live archetypes' jobs (a prefix of jobs.json)
        jobs_f, sfx = os.path.join(d, 'jobs_live.json'), '_live'
        json.dump(json.load(open(os.path.join(d, 'jobs.json')))[:len(live_archs()) * P.K], open(jobs_f, 'w'), indent=0)
    starts, out = os.path.join(d, f'starts_{tag}{sfx}.jsonl'), os.path.join(d, f'out_{out_tag(seed0, per_job)}')
    env = dict(os.environ, MYTEAM=os.path.join(d, 'myteam.json'))
    if not os.path.exists(starts):
        subprocess.run(['node', '../native/battle_starts.js', jobs_f, starts + '.tmp', str(per_job), str(seed0)],
                       cwd=PS, env=env, check=True, stdout=subprocess.DEVNULL)
        os.replace(starts + '.tmp', starts)
    env.update(sim_env(), GRID_DIR=os.path.join(d, 'grid'))
    subprocess.run(['nice', '-n', '10', bin_path(), 'battle', '../native/engine_data_spot.json', starts, out, str(threads)],
                   cwd=PS, env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return read(d, out_tag(seed0, per_job))

def run_jobs(gids, jobs, per_job, seed0, threads, label):
    """battles for an explicit job list (archetype mode: {arch, k, lead, back} with my species names) -> list of per-job rows"""
    d = os.path.join(HERE, 'runs', f'{label}_{team_key(gids)}'); os.makedirs(d, exist_ok=True)
    team = {G[g]['species']: {k: G[g][k] for k in ('species', 'item', 'ability', 'nature', 'evs', 'moves')} for g in gids}
    json.dump(team, open(os.path.join(d, 'myteam.json'), 'w'), indent=1); json.dump(jobs, open(os.path.join(d, 'jobs.json'), 'w'))
    if MG.merge_gids(os.path.join(d, 'grid'), gids): raise RuntimeError('missing one-on-one cells')
    starts, out = os.path.join(d, f'starts_{seed0}_{per_job}.jsonl'), os.path.join(d, f'out_{out_tag(seed0, per_job)}')
    env = dict(os.environ, MYTEAM=os.path.join(d, 'myteam.json'))
    if not os.path.exists(starts):
        subprocess.run(['node', '../native/battle_starts.js', os.path.join(d, 'jobs.json'), starts + '.tmp', str(per_job), str(seed0)],
                       cwd=PS, env=env, check=True, stdout=subprocess.DEVNULL)
        os.replace(starts + '.tmp', starts)
    env.update(sim_env(), GRID_DIR=os.path.join(d, 'grid'))
    subprocess.run(['nice', '-n', '10', bin_path(), 'battle', '../native/engine_data_spot.json', starts, out, str(threads)],
                   cwd=PS, env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return [json.load(open(os.path.join(out, f'{j}.json'))) for j in range(len(jobs))]

def read(d, tag):
    jobs = json.load(open(os.path.join(d, 'jobs.json')))
    live = live_archs(); per = {}
    for j, job in enumerate(jobs):
        if job['arch'] not in live: continue
        r = json.load(open(os.path.join(d, f'out_{tag}', f'{j}.json')))
        vs = [row['v'] for row in r['rows'] if not row.get('unsupported')]
        per[j] = (sum(vs), len(vs))
    score, games, by_arch = 0.0, 0, {}
    for arch in ARCHS:
        if arch not in live:
            by_arch[arch] = perish_stock(json.load(open(os.path.join(d, 'myteam.json'))))
            score += P.ARCH_SHARE[arch] * by_arch[arch]; continue
        shares = P.pair_shares(arch); num = den = 0.0
        for k in range(P.K):
            j = ARCHS.index(arch) * P.K + k; s, n = per[j]; games += n
            if n: num += shares[k] * s / n; den += shares[k]
        by_arch[arch] = num / den if den else None
        score += P.ARCH_SHARE[arch] * (by_arch[arch] or 0)
    return dict(score=score / sum(P.ARCH_SHARE.values()), games=games, by_arch=by_arch, per_job=per)

def search_team(gids, seed0, threads, K=None, sp=1):
    """bring search: battle the outcome-fitted model's top K (lead, back) choices per archetype, sp games per opposing lead pair,
    and keep each archetype's best. Returns the chosen brings and their (selection-biased) results, laid out as the usual 60 jobs."""
    K = K or int(os.environ.get('TS_BRING_K', 3))
    live = live_archs()
    R = {a: P.ranked_outcome(gids, a)[:K] for a in live}
    jobs, meta = [], []
    for a in live:
        for c, (lead, back) in enumerate(R[a]):
            for k in range(P.K):
                jobs.append(dict(arch=a, k=k, lead=[G[g]['species'] for g in lead], back=[G[g]['species'] for g in back])); meta.append((a, c, k))
    rows = run_jobs(gids, jobs, sp, seed0, threads, f'search{K}')
    val = {}
    for (a, c, k), r in zip(meta, rows):
        vs = [x['v'] for x in r['rows'] if not x.get('unsupported')]; val[(a, c, k)] = (sum(vs), len(vs))
    def arch_v(a, c):
        sh = P.pair_shares(a); num = den = 0.0
        for k in range(P.K):
            s_, n_ = val[(a, c, k)]
            if n_: num += sh[k] * s_ / n_; den += sh[k]
        return num / den if den else 0.0
    best = {a: max(range(len(R[a])), key=lambda c: arch_v(a, c)) for a in live}
    per = {ARCHS.index(a) * P.K + k: val[(a, best[a], k)] for a in live for k in range(P.K)}
    by_arch = {a: arch_v(a, best[a]) if a in live else perish_stock([G[g]['species'] for g in gids]) for a in ARCHS}
    return dict(score=sum(P.ARCH_SHARE[a] * by_arch[a] for a in ARCHS) / sum(P.ARCH_SHARE.values()), by_arch=by_arch, per_job=per,
                games=sum(n for _, n in val.values()), chosen={a: R[a][best[a]] for a in live}, rank={a: best[a] + 1 for a in live})

def parallel(fn, items, label):
    par = int(os.environ.get('TS_PARALLEL', 1)); done = [0]; t0 = time.time()
    def one(x):
        r = fn(x); done[0] += 1
        if done[0] % 10 == 0 or done[0] == len(items):
            print(time.strftime('%I:%M %p'), f'  {label}: {done[0]}/{len(items)} teams, {(time.time() - t0) / 60:.0f} min', flush=True)
        return r
    with ThreadPoolExecutor(par) as ex: return list(ex.map(one, items))

def search_many(teams, seed0):
    thr = int(os.environ.get('TS_THREADS', 3))
    return parallel(lambda t: search_team(t, seed0, thr), teams, f'bring search (seed {seed0})')

def evaluate_fixed(teams, brings, per_job, seed0):
    """fresh paired games with given brings per team (brings[i] = {arch: (lead gids, back gids)})"""
    thr = int(os.environ.get('TS_THREADS', 3))
    return parallel(lambda tb: run_team(tb[0], per_job, seed0, thr, fixed=tb[1], label=f'fx{hashlib.md5(json.dumps(tb[1], sort_keys=True).encode()).hexdigest()[:8]}'),
                    list(zip(teams, brings)), f'confirm games (seed {seed0})')

def evaluate(teams, per_job, seed0):
    """teams: lists of 6 grid ids -> list of result dicts (score = archetype-weighted win share)"""
    par = int(os.environ.get('TS_PARALLEL', 1)); thr = int(os.environ.get('TS_THREADS', 3))
    done = [0]; t0 = time.time()
    def one(t):
        r = run_team(t, per_job, seed0, thr); done[0] += 1
        if done[0] % 10 == 0 or done[0] == len(teams):
            print(time.strftime('%I:%M %p'), f'  evaluated {done[0]}/{len(teams)} teams ({per_job} per job, seed {seed0}), '
                  f'{(time.time() - t0) / 60:.0f} min', flush=True)
        return r
    with ThreadPoolExecutor(par) as ex:
        return list(ex.map(one, teams))

if __name__ == '__main__':          # smoke test: python3 evaluate.py <start team name> [per_job] [seed0]
    idx = json.load(open(os.path.join(HERE, 'teams', 'start', 'index.json')))
    t0 = time.time()
    r = evaluate([idx[sys.argv[1]]['gids']], int(sys.argv[2]) if len(sys.argv) > 2 else 1, int(sys.argv[3]) if len(sys.argv) > 3 else 0)
    print(json.dumps(r[0], indent=1), f'{time.time() - t0:.0f}s')
