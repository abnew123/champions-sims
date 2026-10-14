"""Evaluator for the hill climb: full 4v4 battles (the other thread's champ battle, stable binary bin/champ-battle-v1) against the
replay archetypes (pssim/opp_model_{a,b}.json): 10 archetypes x their 6 modelled lead pairs = 60 jobs per team, always in the same
order, so game g of job j uses the same opponent and RNG streams for every team (paired comparisons; G0 = seed0).
My four and leads per archetype come from the bring heuristic (bring/policy.py).
Score = sum over archetypes of share x (lead-pair-share-weighted mean win share over its 6 jobs); games with mechanics the engine
can't run ('unsupported') are dropped.

Per team, under runs/<team key>/: myteam.json, jobs.json, grid/ (one-on-one cells for the planner), starts_*.jsonl, out_*/.
  env: TS_SIM (sim setup, see SIMS), TS_PERISH=real (Perish trap from real data, see perish_stock.py), TS_EG_VALUE (value weights, default pssim/egvalue5.json: 4v4 self-play, second round), TS_ANTICIPATE (default 1), TS_PARALLEL (teams at once, default 1), TS_THREADS (threads each)
"""
import json, os, sys, hashlib, subprocess, time, shutil, threading
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..'); PS = os.path.join(ROOT, 'pssim')
sys.path.insert(0, os.path.join(HERE, 'bring')); sys.path.insert(0, os.path.join(HERE, 'mx'))
import policy as P
import merge as MG
import procs                                          # programs run as teamsearch-<name> (user, 2026-10-06)
G = P.Fx.G
ARCHS = list(P.ARCH_SHARE)
# Sim setups (TS_SIM). 'v3' = what rounds 1-4 on AWS used. 'v8' = the other thread's recommendation of 2026-10-04: two-turn
# Protect check, damage-race value features, egvalue7 (status/Tailwind weights from real games). Outputs of non-default setups
# go to out_<sim>_<seed>_<pj>, so caches of different setups never mix.
V12_ENV = {'BATTLE_ANTICIPATE': '1', 'DP2': '1', 'RACE': '1', 'CALC_DATA': '../native/champions_data.json'}
V26_ENV = {'BATTLE_ANTICIPATE': '1', 'DP2': '1', 'RACE': '1', 'RACE_TIES': 'avg', 'TRSYM': '1', 'RACE_PRIO': '1', 'FEATS22': '1',
           'EG_MEGA_TIE': '0', 'CALC_DATA': '../native/champions_data_full.json'}
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
    # v13 (Battle sim, 2026-10-05): v12 + RACE_TIES=avg (the race used to give side 0 every Speed tie; now it averages both
    # orders, so features mirror exactly under a side swap). The climb rerun's setup.
    'v13g': dict(bin='champ-battle-v13', eg='egvalue9.json', env=dict(V12_ENV, RACE_TIES='avg')),
    # v14: the same games as v13, ~25-39% faster (memoised features, mimalloc); taken at a round boundary (outputs tagged v14g)
    'v14g': dict(bin='champ-battle-v14', eg='egvalue9.json', env=dict(V12_ENV, RACE_TIES='avg')),
    # v16: the same games again, ~2.3x faster than v14 (string-free handler lookup, cached effect data)
    'v16g': dict(bin='champ-battle-v16', eg='egvalue9.json', env=dict(V12_ENV, RACE_TIES='avg')),
    # v17: v16 with a 256-bit callback mask (same games); needed for engine_data_full.json (the real-game opponent pool, poolbar.py)
    'v17g': dict(bin='champ-battle-v17', eg='egvalue9.json', env=dict(V12_ENV, RACE_TIES='avg')),
    # v19: the same battles as v16/v17 (no per-call global lock); MISS_DOUBLE=0 doubles our side's misses (user, 2026-10-06): every
    # accuracy roll's final hit chance p becomes max(0, 2p - 100), accuracy-true cases untouched, a rule miss is an ordinary miss
    'v19g': dict(bin='champ-battle-v19', eg='egvalue9.json', env=dict(V12_ENV, RACE_TIES='avg')),
    'v19m': dict(bin='champ-battle-v19', eg='egvalue9.json', env=dict(V12_ENV, RACE_TIES='avg', MISS_DOUBLE='0')),
    # v20 = v19 + a recharge fix (after Hyper Beam a Pokemon had no legal option and ~6% of pool games ended early); games without a
    # recharge turn are identical. The miss-doubling climb runs as v20m.
    'v20g': dict(bin='champ-battle-v20', eg='egvalue9.json', env=dict(V12_ENV, RACE_TIES='avg')),
    'v20m': dict(bin='champ-battle-v20', eg='egvalue9.json', env=dict(V12_ENV, RACE_TIES='avg', MISS_DOUBLE='0')),
    # v26 (Battle sim, 2026-10-13; the next climb's frozen setup): the engine at cb9cf51 with every Oct 12 port and fix (what the
    # live bot runs), the full damage-calc data (1,469 species), Mega choice free (no EG_MEGA_ALWAYS), the h64 value net on both
    # sides on top of egvalue9_sym2 (self-play +4.9 +- 1.5 over sym2 alone; ~2.2x the time per game), and an empty GRID_DIR (the
    # planner no longer reads one-on-one cells; the bring model still does). v26s: the same without the net, its cheaper fallback.
    'v26': dict(bin='champ-battle-v26', eg='egvalue9_sym2.json', grid=False,
                env=dict(V26_ENV, EG_VNET='../bot/value/vnet_h64_search_fc.json')),
    'v26s': dict(bin='champ-battle-v26', eg='egvalue9_sym2.json', grid=False, env=dict(V26_ENV)),
    # v27 (Battle sim, 2026-10-13): v26 game for game, 17% less CPU with the net (the calc data maps on the Fx hasher). The climb's
    # frozen setup. seedkey: pool jobs carry meta.seed_index (from group and entry only), so a game is the same wherever it sits in
    # a job list and TS_GAME_CACHE (gamecache.py) can reuse it across teams; this changes which seeds games get, so v27 results
    # are not paired with v26 ones.
    'v27': dict(bin='champ-battle-v27', eg='egvalue9_sym2.json', grid=False, seedkey=True,
                env=dict(V26_ENV, EG_VNET='../bot/value/vnet_h64_search_fc.json')),
    'v27s': dict(bin='champ-battle-v27', eg='egvalue9_sym2.json', grid=False, seedkey=True, env=dict(V26_ENV)),
    # v28 (Battle sim, 2026-10-13; the climb's frozen setup, at the user's wish): v27 with accuracy-aware value features (hit_chance:
    # No Guard, rain Thunder / Hurricane, sun, snow Blizzard, Compound Eyes, Hustle, Wide Lens, accuracy stages; the turn simulation
    # unchanged) and the h64 net refitted on them (vnet_h64_search_acc.json: self-play +3.4 +- 1.5 over v28s; real-pairings style
    # bias RMS 3.6, about noise). Same flags and data as v27.
    'v28': dict(bin='champ-battle-v28', eg='egvalue9_sym2.json', grid=False, seedkey=True,
                env=dict(V26_ENV, EG_VNET='../bot/value/vnet_h64_search_acc.json')),
    'v28s': dict(bin='champ-battle-v28', eg='egvalue9_sym2.json', grid=False, seedkey=True, env=dict(V26_ENV)),
}
def sim(): return os.environ.get('TS_SIM', 'v3')
def out_tag(seed0, per_job): return f'{seed0}_{per_job}' if sim() == 'v3' else f'{sim()}_{seed0}_{per_job}'
def bin_path():
    """the battle binary, read at call time: TS_BATTLE_BIN if set (climb.py's legacy per-round pin), else the TS_SIM setup's"""
    return os.environ.get('TS_BATTLE_BIN', os.path.join(ROOT, 'native', 'champ', 'bin', SIMS[sim()]['bin']))
EMPTY_GRID = os.path.join(HERE, 'runs', '_empty_grid')
def grid_dir(d):
    """GRID_DIR for a team's battles: its merged one-on-one cells, or an empty folder when the setup's planner reads none (v26)"""
    if SIMS[sim()].get('grid', True): return os.path.join(d, 'grid')
    os.makedirs(EMPTY_GRID, exist_ok=True); return EMPTY_GRID
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
        subprocess.run([procs.node(), '../native/battle_starts.js', jobs_f, starts + '.tmp', str(per_job), str(seed0)],
                       cwd=PS, env=env, check=True, stdout=subprocess.DEVNULL)
        os.replace(starts + '.tmp', starts)
    env.update(sim_env(), GRID_DIR=grid_dir(d))
    subprocess.run(['nice', '-n', '10', procs.battle(bin_path()), 'battle', os.environ.get('TS_ENGINE_DATA', '../native/engine_data_spot.json'), starts, out, str(threads)],
                   cwd=PS, env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return read(d, out_tag(seed0, per_job))

def run_jobs(gids, jobs, per_job, seed0, threads, label, extra=None):
    """run_jobs_raw behind the cross-team game cache (gamecache.py), when TS_GAME_CACHE is set, the setup has a seed key and every
    job carries meta.seed_index: cached games are returned as they are, only the others are played (in a sub-run of their own).
    A game another team of this process is already playing is waited for, not played twice (outside review, 2026-10-14)."""
    path = os.environ.get('TS_GAME_CACHE')
    if not (path and SIMS[sim()].get('seedkey') and jobs and all('seed_index' in (j.get('meta') or {}) for j in jobs)):
        return run_jobs_raw(gids, jobs, per_job, seed0, threads, label, extra)
    import gamecache as GC
    ed = (extra or {}).get('TS_ENGINE_DATA', os.environ.get('TS_ENGINE_DATA', '../native/engine_data_spot.json'))
    keys = [GC.key(sim(), ed, seed0, per_job, j) for j in jobs]; first = {}
    for i, k in enumerate(keys): first.setdefault(k, i)
    have = GC.get_many(path, list(first)); mine, wait = [], {}
    with _PLOCK:
        for k in first:
            if k in have: continue
            if k in _PENDING: wait[k] = _PENDING[k]
            else: _PENDING[k] = threading.Event(); mine.append(k)
    def play(ks, tag):
        sub = [jobs[first[k]] for k in ks]; h = hashlib.md5(json.dumps(sub, sort_keys=True).encode()).hexdigest()[:8]
        rows = run_jobs_raw(gids, sub, per_job, seed0, threads, f'{label}_{tag}{h}', extra)
        GC.put_many(path, list(zip(ks, rows))); have.update(zip(ks, rows))
    try:
        if mine: play(mine, 'c')
    finally:
        with _PLOCK:
            for k in mine: _PENDING.pop(k).set()
    if wait:
        for ev in wait.values(): ev.wait()
        have.update(GC.get_many(path, list(wait)))
        left = [k for k in wait if k not in have]                       # the other team's run failed: play them here
        if left: play(left, 'w')
    with _PLOCK:
        CACHE_STATS['jobs'] += len(jobs); CACHE_STATS['unique'] += len(first); CACHE_STATS['played'] += len(mine)
        CACHE_STATS['waited'] += len(wait)
    return [have[k] for k in keys]
CACHE_STATS = {'jobs': 0, 'unique': 0, 'played': 0, 'waited': 0}
_PENDING = {}; _PLOCK = threading.Lock()

def run_jobs_raw(gids, jobs, per_job, seed0, threads, label, extra=None):
    """battles for an explicit job list (archetype mode: {arch, k, lead, back} with my species names) -> list of per-job rows.
    extra: environment for this run only (e.g. TS_ENGINE_DATA, SEED_PER_JOB), never written to os.environ: teams run in threads of one
    process, and a shared os.environ let one team unset another's engine data mid-launch (2026-10-06)"""
    d = os.path.join(HERE, 'runs', f'{label}_{team_key(gids)}'); os.makedirs(d, exist_ok=True)
    team = {G[g]['species']: {k: G[g][k] for k in ('species', 'item', 'ability', 'nature', 'evs', 'moves')} for g in gids}
    starts, out = os.path.join(d, f'starts_{seed0}_{per_job}.jsonl'), os.path.join(d, f'out_{out_tag(seed0, per_job)}')
    jp = os.path.join(d, 'jobs.json')
    if os.path.exists(jp) and (os.path.exists(starts) or os.path.exists(out)) and \
            json.dumps(json.load(open(jp)), sort_keys=True) != json.dumps(jobs, sort_keys=True):
        stamp = time.strftime('%Y%m%d%H%M%S')                    # same label, other jobs (a changed shortlist or pool; outside review,
        for f in (starts, out):                                   # 2026-10-14): never attach the old games to the new jobs
            if os.path.exists(f): os.replace(f, f'{f}.stale{stamp}')
    json.dump(team, open(os.path.join(d, 'myteam.json'), 'w'), indent=1); json.dump(jobs, open(jp, 'w'))
    if SIMS[sim()].get('grid', True) and MG.merge_gids(os.path.join(d, 'grid'), gids): raise RuntimeError('missing one-on-one cells')
    env = dict(os.environ, MYTEAM=os.path.join(d, 'myteam.json'), **(extra or {}))
    if not os.path.exists(starts):
        subprocess.run([procs.node(), '../native/battle_starts.js', os.path.join(d, 'jobs.json'), starts + '.tmp', str(per_job), str(seed0)],
                       cwd=PS, env=env, check=True, stdout=subprocess.DEVNULL)
        os.replace(starts + '.tmp', starts)
    env.update(sim_env(), GRID_DIR=grid_dir(d)); threads = max(threads, BOOST[0])
    subprocess.run(['nice', '-n', '10', procs.battle(bin_path()), 'battle', env.get('TS_ENGINE_DATA', '../native/engine_data_spot.json'), starts, out, str(threads)],
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

_TL = threading.local()   # per worker thread: battle threads for the item it runs (set by parallel(), read by run_jobs_raw)
class _Boost:
    def __getitem__(self, i): return getattr(_TL, 'boost', 0)
BOOST = _Boost()
def parallel(fn, items, label):
    """fn over items, TS_PARALLEL at once. An item that starts when fewer than TS_PARALLEL items are left (a small stage, or a stage's
    tail) runs with TS_PARALLEL x TS_THREADS / (items left) threads (2026-10-13: the last climb's late rounds left 60% of the box idle;
    outside review 2026-10-14: the tail of a stage too). Thread counts never change results. Prints the stage's game counts."""
    par = int(os.environ.get('TS_PARALLEL', 1)); done = [0]; started = [0]; t0 = time.time(); lk = threading.Lock()
    thr = int(os.environ.get('TS_THREADS', 3)); c0 = dict(CACHE_STATS)
    def one(x):
        with lk: started[0] += 1; left = len(items) - started[0] + 1
        _TL.boost = (par * thr) // left if left < par else 0
        try: r = fn(x)
        finally: _TL.boost = 0
        with lk: done[0] += 1; n = done[0]
        if n % 10 == 0 or n == len(items):
            print(time.strftime('%I:%M %p'), f'  {label}: {n}/{len(items)} teams, {(time.time() - t0) / 60:.0f} min', flush=True)
        return r
    with ThreadPoolExecutor(par) as ex: res = list(ex.map(one, items))
    d = {k: CACHE_STATS[k] - c0[k] for k in CACHE_STATS}
    if d['jobs']: print(time.strftime('%I:%M %p'), f"  {label}: games asked {d['jobs']}, distinct per team {d['unique']}, played {d['played']}, "
                        f"waited for another team {d['waited']}, cached {d['unique'] - d['played'] - d['waited']} ({(time.time() - t0) / 60:.0f} min)", flush=True)
    return res

def pool_mode(): return os.environ.get('TS_OPP') == 'pool'        # real-game opponent pool (poolmode.py) instead of archetype models

def search_many(teams, seed0):
    thr = int(os.environ.get('TS_THREADS', 3))
    if pool_mode():
        import poolmode
        return parallel(lambda t: poolmode.search_team(t, seed0, thr), teams, f'bring search (seed {seed0})')
    return parallel(lambda t: search_team(t, seed0, thr), teams, f'bring search (seed {seed0})')

def evaluate_fixed(teams, brings, per_job, seed0):
    """fresh paired games with given brings per team (brings[i] = {arch: (lead gids, back gids)})"""
    thr = int(os.environ.get('TS_THREADS', 3))
    if pool_mode():                                                    # (pool entries are one game each; per_job is not used)
        import poolmode
        return parallel(lambda tb: poolmode.evaluate_team(tb[0], tb[1], seed0, thr), list(zip(teams, brings)), f'confirm games (seed {seed0})')
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
