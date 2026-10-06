"""Pool-based evaluation for the hill climb (TS_OPP=pool; user, 2026-10-06, after poolbar.py's validation: RMS 0.18 vs 0.29).
Opponents are real pool entries (pssim/opp_pool.json: a real six with its sets and the four it actually brought, in lead order), not
archetype models. Brings are chosen per bring group: Battle sim's core-rule groups (results/core_rules_both_100.json), with 'other'
split by rule archetype ('other/Sun', ...); the 28 groups with >= 1% of the regional team sheets and >= 8 pool entries, weighted by
their regional share (pool_keys.json, renormalised over those 28: 96% of the meta). Perish is played, not stocked.
  screening (search_team):  per group, the outcome model's top K brings against the group's species profile, each played against
                            E_S pool entries of the group (one game each); the group's best bring is kept
  confirm (evaluate_fixed): per group, E_C pool entries, one game each, with the team's chosen bring for that group
Entries are drawn per (group, seed): the same for every team in a round's batch (paired comparisons), new each batch. Battles use
native/engine_data_full.json and SEED_PER_JOB=1 (independent luck per one-game job). Run dirs carry the sim setup's name, so two pool
climbs (e.g. with and without MISS_DOUBLE) can share one box. Results look like evaluate's (score, by_arch = per group, per_job), plus
w_job, the weight of every job in the score, which climb.paired uses.
  env: TS_POOL_ES (2), TS_POOL_EC (8), TS_BRING_K (3)
"""
import json, os, sys, random, hashlib, functools, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); PS = os.path.join(HERE, '..', 'pssim')
if PS not in sys.path: sys.path.insert(0, PS)
import evaluate as E
P = E.P; Fx = P.Fx
FULL = os.path.join('..', 'native', 'engine_data_full.json')
E_S = int(os.environ.get('TS_POOL_ES', 2)); E_C = int(os.environ.get('TS_POOL_EC', 8))

@functools.lru_cache(maxsize=None)
def keys():
    """(bring groups, their normalised regional shares)"""
    K = json.load(open(os.path.join(HERE, 'pool_keys.json')))['keys']
    use = [k for k, v in K.items() if v['share'] >= 0.01 and v['pool'] >= 8]
    tot = sum(K[k]['share'] for k in use)
    return tuple(use), {k: K[k]['share'] / tot for k in use}

def group_of(six):
    from cluster_opps import tag, norm
    from pro_replays import arch
    g = tag(six, rules())
    return g if g != 'other' else 'other/' + arch([norm(x) for x in six])
@functools.lru_cache(maxsize=None)
def rules(): return json.load(open(os.path.join(PS, 'results', 'core_rules_both_100.json')))

@functools.lru_cache(maxsize=None)
def entries():
    """bring group -> pool entries (with four brought)"""
    out = {}
    for e in json.load(open(os.path.join(PS, 'opp_pool.json')))['entries']:
        if len(e['bring']) == 4: out.setdefault(group_of([s['species'] for s in e['six']]), []).append(e)
    return out

def sample(key, n, seed):
    """n entries of a group, rating-weighted without replacement (>= 1500: 3, >= 1300: 2, else 1), fixed by (group, seed)"""
    c = entries()[key]; rng = random.Random(f'{key}|{seed}')
    w = [3 if (e['rating'] or 0) >= 1500 else 2 if (e['rating'] or 0) >= 1300 else 1 for e in c]
    order = sorted(range(len(c)), key=lambda i: rng.random() ** (1 / w[i]), reverse=True)
    return [c[i] for i in order[:n]]

@functools.lru_cache(maxsize=None)
def opp_six(key, min_w=0.05):
    """the group's species profile for the bring model: share of the group's entries that brought each species (like policy.opp_six)"""
    es = entries()[key]; w = {}
    for e in es:
        for sp in e['bring']: w[sp] = w.get(sp, 0) + 1 / len(es)
    out = [(Fx.canon(sp), round(x, 3)) for sp, x in sorted(w.items(), key=lambda t: -t[1]) if x >= min_w]
    return tuple((g, x) for g, x in out if g)

def ranked(team, key):
    """all (lead, back) choices against a group, best first, under the outcome-fitted bring model (as policy.ranked_outcome)"""
    import fit_outcome as FO
    wB, wL, pb, pl = P.model()
    m = Fx.Matchup(list(team), list(opp_six(key))); sp = [Fx.G[g]['species'] for g in team]
    lsm = lambda u: np.asarray(u) - (max(u) + math.log(sum(math.exp(x - max(u)) for x in u)))
    uB = lsm([float(np.dot(wB, m.bring_feats(S) + [sum(pb.get(sp[i], 0.0) for i in S)])) for S in Fx.BRINGS])
    hl = {}
    for b, S in enumerate(Fx.BRINGS):
        Ls = Fx.leads(S)
        uL = lsm([float(np.dot(wL, m.lead_feats(Lp, S) + [sum(pl.get(sp[i], 0.0) for i in Lp)])) for Lp in Ls])
        for l, Lp in enumerate(Ls): hl[(Lp, tuple(i for i in S if i not in Lp))] = uB[b] + uL[l]
    w = np.array(json.load(open(P.OUTCOME))['w'])
    r = sorted(((float(np.dot(w, FO.feats(m, hl, Lp, B))), Lp, B) for (Lp, B) in hl), key=lambda t: -t[0])
    return [([team[i] for i in Lp], [team[i] for i in B]) for _, Lp, B in r]

def job(team, lead, back, e):
    from opp_pool import spread
    mine = [{k: E.G[g][k] for k in ('species', 'item', 'ability', 'nature', 'evs', 'moves')} for g in list(lead) + list(back)]
    six = {m['species']: m for m in e['six']}
    theirs = [{**six[x], 'evs': spread(x, six[x]['nature'])} for x in e['bring']]
    return dict(mine=mine, theirs=theirs, meta=dict(pool_id=e['id'], pool_side=e['side'], group=e['group'], arch=e['arch'], rating=e['rating']))

def _run(gids, jobs, seed0, threads, label):
    return E.run_jobs(gids, jobs, 1, seed0, threads, label, extra=dict(TS_ENGINE_DATA=FULL, SEED_PER_JOB='1'))   # per run, not os.environ (threads)

def _wins(r):
    """(wins, games) of one job's output; unsupported games and games the engine errored on are left out (an error is reported)"""
    vs = [x['v'] for x in r['rows'] if not x.get('unsupported') and x.get('v') is not None]
    if any(x.get('v') is None and not x.get('unsupported') for x in r['rows']):
        print(f"warning: engine error in job {r.get('job')} ({', '.join(str(x.get('error')) for x in r['rows'] if x.get('v') is None)}), game left out", file=sys.stderr, flush=True)
    return sum(vs), len(vs)

def _result(slots, val, games, extra=None):
    """slots: [(group, entry index)] in job order; val: {slot: (wins, n)} -> evaluate-style result with per-job weights"""
    K, SH = keys(); per = {}; w_job = {}; by = {}
    n_k = {k: sum(1 for kk, _ in slots if kk == k) for k in K}
    for j, (k, ei) in enumerate(slots):
        per[j] = val[(k, ei)]; w_job[j] = SH[k] / n_k[k]
    for k in K:
        xs = [val[(kk, ei)] for kk, ei in slots if kk == k and val[(kk, ei)][1]]
        by[k] = sum(s / n for s, n in xs) / len(xs) if xs else 0.0
    return dict(score=sum(SH[k] * by[k] for k in K), by_arch=by, per_job=per, w_job=w_job, games=games, **(extra or {}))

def search_team(gids, seed0, threads, K=None, sp=1):
    K = K or int(os.environ.get('TS_BRING_K', 3)); G_, _ = keys()
    R = {k: ranked(gids, k)[:K] for k in G_}; ents = {k: sample(k, E_S, seed0) for k in G_}
    jobs, meta = [], []
    for k in G_:
        for c, (lead, back) in enumerate(R[k]):
            for ei, e in enumerate(ents[k]): jobs.append(job(gids, lead, back, e)); meta.append((k, c, ei))
    rows = _run(gids, jobs, seed0, threads, f'psearch{K}_{E.sim()}')
    val = {}
    for (k, c, ei), r in zip(meta, rows): val[(k, c, ei)] = _wins(r)
    mean = lambda k, c: (lambda xs: sum(s / n for s, n in xs) / len(xs) if xs else 0.0)([val[(k, c, ei)] for ei in range(len(ents[k])) if val[(k, c, ei)][1]])
    best = {k: max(range(len(R[k])), key=lambda c: mean(k, c)) for k in G_}
    slots = [(k, ei) for k in G_ for ei in range(len(ents[k]))]
    return _result(slots, {(k, ei): val[(k, best[k], ei)] for k, ei in slots}, sum(n for _, n in val.values()),
                   dict(chosen={k: R[k][best[k]] for k in G_}, rank={k: best[k] + 1 for k in G_}))

def evaluate_team(gids, brings, seed0, threads):
    G_, _ = keys(); ents = {k: sample(k, E_C, seed0) for k in G_}
    jobs, slots = [], []
    for k in G_:
        lead, back = brings[k]
        for ei, e in enumerate(ents[k]): jobs.append(job(gids, lead, back, e)); slots.append((k, ei))
    h = hashlib.md5(json.dumps({k: (list(v[0]), list(v[1])) for k, v in brings.items()}, sort_keys=True).encode()).hexdigest()[:8]
    rows = _run(gids, jobs, seed0, threads, f'pool_{E.sim()}_{h}_{seed0}')
    val = {}
    for s, r in zip(slots, rows): val[s] = _wins(r)
    return _result(slots, val, sum(n for _, n in val.values()))

def jobs_per_team(phase):
    G_, _ = keys()
    return len(G_) * (E_S * int(os.environ.get('TS_BRING_K', 3)) if phase == 'screen' else E_C)
