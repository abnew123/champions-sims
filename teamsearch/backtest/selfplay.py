"""M-B to M-C self-play backtest (the user, 2026-11-06: "go ahead with the M-B to M-C backtest"), step 3: self-play from M-B's field
with M-C's new species in the catalog (build_mb.py), to see whether it would have predicted M-C's meta (compare.py). No M-C data:
the M-B field and sets, August's M-B spreads (TS_MOVESET), blind sets for the new species, their fitted bring priors dropped
(TS_PRIOR_ZERO), the climb's pre-filter weighted by the field (TS_PREFILTER=pool). Sim: v41n1 (Battle sim's screening setup).
Each iteration i (state in sp_state.json; every step is a subprocess, so pool mode reads the current field):
  1. the field as a pool (sp_field_<i>.json, poolmode's TS_POOL_FIELD: each team its own group, exact spreads, a bring per opponent)
  2. score: each field team's bring search against each field team (seed 86000); its chosen fours become its brings; then BATCHES
     batches of 8 games per pair with those brings (seeds 886000 + 50 b) -> payoff matrix (sp_score_<i>.json)
  3. weights: the logit equilibrium of the payoff matrix at BETA (pre-registered 20: a 5-point edge against the mix is e^1 the weight),
     teams under W_MIN dropped, at most N_MAX kept -> the prediction after iteration i (sp_pred_<i>.json; compare.py reads it)
  4. climbs: the top STARTS teams by weight climb against this field (climb.py round thorough, no archetype lock, catalog
     mb_swap_pool.json) for ROUNDS rounds; finals that moved join the field
  nohup bin/teamsearch-py backtest/selfplay.py run &        (cloud/mac_backtest.sh; log backtest/selfplay.log; progress page cards)
v2 (SP_VER=2; the user, 2026-11-07, after v1 never tried Rillaboom or Indeedee-F and piled its weight onto a few teams; fixed before
the v2 run; outputs in backtest/v2/, climb files climb_bt2_*, round_bt2.log; cloud/mac_backtest_v2.sh):
  - catalog mb_swap_pool_v2.json (build_mb.py BLIND=2: ability-aware blind sets)
  - every blind forme gets one screened swap per climb round (climb.py TS_FORCE_NEW, the starts taking turns, rotated by iteration)
  - the climbs' learned pre-filter also learns from earlier iterations' screens (TS_LEARN_HIST)
  - weights by replicator dynamics from M-B's real shares, not the logit equilibrium: w <- w * exp(ETA * (f - mean f)), f = P w,
    ETA 2; a climbed team enters at ENTRY (3%), the rest rescaled; teams under 0.5% dropped. ETA was 10 at launch; its first step
    put 40% on one team (mb4), so the run was stopped a minute in and ETA set on iteration 1's self-play matrix alone, with no M-C
    data: fitness sd there is 7 points, so a team one sd above the mean grows x1.16 a step, and 4 steps without new teams leave
    about 6.6 effective teams (ETA 3: 4.0, 5: 2.1, 10: 2.7, after 77% on one team at step 2)
"""
import json, os, sys, time, subprocess, shutil, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); TS = os.path.dirname(HERE)
ITERS, STARTS, ROUNDS, BATCHES = (int(os.environ.get(k, d)) for k, d in (('SP_ITERS', 4), ('SP_STARTS', 5), ('SP_ROUNDS', 2), ('SP_BATCHES', 2)))
VER = os.environ.get('SP_VER', '1'); V2 = VER == '2'
BETA, W_MIN, N_MAX = float(os.environ.get('SP_BETA', 20)), 0.005 if V2 else 0.01, 20
DYN = os.environ.get('SP_DYN', 'replicator' if V2 else 'qre'); ETA, ENTRY = float(os.environ.get('SP_ETA', 2)), float(os.environ.get('SP_ENTRY', 0.03))
OUT = os.path.join(HERE, 'v2') if V2 else HERE; os.makedirs(OUT, exist_ok=True)
ST = os.path.join(OUT, 'sp_state.json'); LOG = os.path.join(OUT, 'selfplay.log')
A = lambda *p: os.path.join(OUT, *p)                                 # this version's outputs
I = lambda *p: os.path.join(HERE, *p)                                # inputs shared by the versions
CB = 'climb_bt2' if V2 else 'climb_bt'; TAG = 'v41n1' + (' v2' if V2 else '')
ENV = dict(TS_SIM='v41n1', TS_OPP='pool', TS_POOL_FIELD='1', TS_MOVESET=I('smogon_mb_2026-08_moveset.txt'), TS_PRIOR_ZERO=I('prior_zero.json'),
           TS_SWAP_POOL=I('mb_swap_pool_v2.json' if V2 else 'mb_swap_pool.json'), TS_PREFILTER='pool', TS_GAME_CACHE=os.path.join(TS, 'cache_bt', 'games.sqlite'))
DROP = ('TS_BRING_MODE', 'TS_PERISH', 'TS_POOL_WEIGHT', 'TS_BATTLE_BIN', 'TS_ARCH_LOCK', 'TS_POOL_BY_PLAYER', 'TS_INDEX', 'TS_STARTS')

def say(s):
    with open(LOG, 'a') as f: f.write(f"{time.strftime('%I:%M %p')} {s}\n")

def env(i):
    e = {k: v for k, v in os.environ.items() if k not in DROP}
    e.update(ENV, TS_POOL=A(f'sp_field_{i}.json'), TS_POOL_KEYS=A(f'sp_keys_{i}.json'))
    return e

def field_files(i, field):
    """the field as a pool file in TS_POOL_FIELD's shape and its group shares (the weights)"""
    sys.path.insert(0, TS); import climb as C
    es = []
    for n, t in field.items():
        six = [{k: C.GRID[g][k] for k in ('species', 'item', 'ability', 'nature', 'evs', 'moves')} for g in t['gids']]
        es.append(dict(id=n, side='p1', group=n, arch=C.arch_of(t['gids']), rating=None, gids=t['gids'], six=six, bring=t['bring'],
                       bring_by_group=t.get('bring_by_group', {}), w=t['w']))
    json.dump({'entries': es, 'note': f'self-play field, iteration {i} (backtest/selfplay.py)'}, open(A(f'sp_field_{i}.json'), 'w'))
    json.dump({'keys': {n: {'share': t['w'], 'pool': 1} for n, t in field.items()}}, open(A(f'sp_keys_{i}.json'), 'w'), indent=1)

def score(i):
    """(subprocess, TS_POOL = this iteration's field) bring searches, then the payoff matrix"""
    sys.path.insert(0, TS)
    import climb as C, evaluate as E, poolmode as PM
    path = A(f'sp_field_{i}.json'); F = json.load(open(path)); es = F['entries']; names = [e['group'] for e in es]
    teams = [e['gids'] for e in es]; thr = int(os.environ.get('TS_THREADS', 3))
    print(time.strftime('%I:%M %p'), f"{E.sim()}: self-play iteration {i}, {len(teams)} field teams, {BATCHES} batches", flush=True)
    scr = E.search_many(teams, 86000)
    for e, r in zip(es, scr):
        e['bring_by_group'] = {k: [C.GRID[g]['species'] for g in list(lb[0]) + list(lb[1])] for k, lb in r['chosen'].items()}
        e['bring'] = collections.Counter(tuple(b) for b in e['bring_by_group'].values()).most_common(1)[0][0]
    json.dump(F, open(path, 'w'))
    for f in (PM.entries, PM.opp_six, PM._group_of_gids): f.cache_clear()
    items = [(x, b) for x in range(len(teams)) for b in range(BATCHES)]
    res = dict(zip(items, E.parallel(lambda xb: PM.evaluate_team(teams[xb[0]], scr[xb[0]]['chosen'], 886000 + 50 * xb[1], thr), items, 'score')))
    K, _ = PM.keys()
    M = [[sum(res[(x, b)]['by_arch'].get(k, 0.5) for b in range(BATCHES)) / BATCHES for k in names] for x in range(len(teams))]
    json.dump(dict(names=names, M=M, keys=list(K), games=sum(r['games'] for r in res.values()),
                   brings={n: e['bring_by_group'] for n, e in zip(names, es)}), open(A(f'sp_score_{i}.json'), 'w'))
    print(time.strftime('%I:%M %p'), f"payoff matrix: {len(names)} x {len(names)}, {sum(r['games'] for r in res.values())} games", flush=True)

def equilibrium(M, beta, w0=None, steps=4000, a=0.05):
    """the logit (quantal response) equilibrium of the symmetrised game: w = softmax(beta * (P w)), P = (M - M^T)/2 + 1/2"""
    M = np.array(M); P = (M - M.T) / 2 + 0.5; n = len(M); w = np.full(n, 1 / n) if w0 is None else np.array(w0) / sum(w0)
    for _ in range(steps):
        f = P @ w; q = np.exp(beta * (f - f.max())); w = (1 - a) * w + a * q / q.sum()
    return w, P @ w

def replicator(M, w, eta):
    """one replicator step of the symmetrised game from the current shares: w <- w * exp(eta * (P w - w.P w)), renormalised"""
    M = np.array(M); P = (M - M.T) / 2 + 0.5; w = np.array(w, dtype=float) / sum(w); f = P @ w
    w = w * np.exp(eta * (f - w @ f)); return w / w.sum(), f

def climbs(i, field):
    """the top STARTS teams climb against the field; returns {start: final gids} for starts that moved"""
    sys.path.insert(0, TS); import climb as C
    top = sorted(field, key=lambda n: -field[n]['w'])[:STARTS]; d = f'bt{VER if V2 else ""}_start_{i}'
    os.makedirs(os.path.join(TS, 'teams', d), exist_ok=True)
    json.dump({n: dict(event='selfplay', place=None, rating=None, arch=C.arch_of(field[n]['gids']), pid=None, gids=field[n]['gids']) for n in top},
              open(os.path.join(TS, 'teams', d, 'index.json'), 'w'), indent=1)
    e = env(i); e.update(TS_INDEX=f'teams/{d}/index.json', TS_STATE=f'{CB}_state.json', TS_LOG=f'{CB}_log.jsonl',
                         TS_PROGRESS=f'{CB}_progress.json', TS_CACHE_DIR=os.path.join(TS, 'cache_bt', *(['v2'] if V2 else []), f'iter{i}'))
    if V2: e.update(TS_FORCE_NEW='1', TS_FORCE_OFFSET=str(i), TS_LEARN_HIST=':'.join(A(f'iter{j}', f'{CB}_log.jsonl') for j in range(1, i)))
    os.makedirs(e['TS_CACHE_DIR'], exist_ok=True)
    for r in range(ROUNDS):
        st = json.load(open(os.path.join(TS, f'{CB}_state.json'))) if os.path.exists(os.path.join(TS, f'{CB}_state.json')) else None
        if st and all(t['done'] for t in st['teams'].values()): break
        with open(os.path.join(TS, f"round_bt{'2' if V2 else ''}.log"), 'a') as lg:
            lg.write(f"--- self-play iteration {i}, climb round {r + 1}, {time.strftime('%m-%d %I:%M %p')}\n"); lg.flush()
            subprocess.run([os.path.join(TS, 'bin', 'teamsearch-py'), 'climb.py', 'round', 'thorough', CB], cwd=TS, env=e, stdout=lg, stderr=subprocess.STDOUT, check=True)
    st = json.load(open(os.path.join(TS, f'{CB}_state.json')))
    os.makedirs(A(f'iter{i}'), exist_ok=True)
    for f in (f'{CB}_state.json', f'{CB}_log.jsonl', f'{CB}_progress.json'):                      # each iteration's climb starts fresh
        if os.path.exists(os.path.join(TS, f)): shutil.move(os.path.join(TS, f), A(f'iter{i}', f))
    return {n: t['team'] for n, t in st['teams'].items() if sorted(t['team']) != sorted(field[n]['gids'])}

def predict(i, field):
    sys.path.insert(0, TS); import climb as C
    use = collections.Counter()
    for t in field.values():
        for g in t['gids']: use[C.forme(g)] += t['w']
    json.dump(dict(iteration=i, beta=BETA, dyn=DYN, eta=ETA if DYN == 'replicator' else None, field={n: dict(w=t['w'], species=[C.forme(g) for g in t['gids']], origin=t['origin']) for n, t in field.items()},
                   usage=dict(use.most_common())), open(A(f'sp_pred_{i}.json'), 'w'), indent=1)

def run():
    sys.path.insert(0, TS); import climb as C
    if os.path.exists(ST): S = json.load(open(ST))
    else:
        mb = json.load(open(I('mb_field.json'))); pool = json.load(open(I('mb_pool.json')))['entries']; tot = sum(t['share'] for t in mb.values())
        field = {}
        for n, t in mb.items():
            sp = {C.GRID[g]['species'] for g in t['gids']}
            br = collections.Counter(tuple(e['bring']) for e in pool if {s['species'] for s in e['six']} == sp).most_common(1)
            field[n] = dict(gids=t['gids'], w=t['share'] / tot, origin='M-B', bring=list(br[0][0]) if br else [C.GRID[g]['species'] for g in t['gids'][:4]])
        S = dict(iter=0, step='score', field=field)
        json.dump(S, open(ST, 'w'), indent=1); predict(0, field)
        say(f"{TAG}: self-play backtest from {len(field)} M-B sixes; {ITERS} iterations, {STARTS} climbs x {ROUNDS} rounds each, "
            + (f"replicator weights (eta {ETA:g}, entry {100 * ENTRY:g}%)" if DYN == 'replicator' else f"beta {BETA:g}"))
    while S['iter'] < ITERS:
        i = S['iter'] + 1; field = S['field']
        if S['step'] == 'score':
            field_files(i, field); say(f"{TAG}: iteration {i}: scoring {len(field)} field teams")
            with open(LOG, 'a') as lg:
                subprocess.run([os.path.join(TS, 'bin', 'teamsearch-py'), os.path.abspath(__file__), 'score', str(i)], cwd=TS, env=env(i),
                               stdout=lg, stderr=subprocess.STDOUT, check=True)
            R = json.load(open(A(f'sp_score_{i}.json'))); F = json.load(open(A(f'sp_field_{i}.json')))['entries']
            for e in F: field[e['group']].update(bring=list(e['bring']), bring_by_group=e['bring_by_group'])
            w0 = [field[n]['w'] for n in R['names']]
            w, f = replicator(R['M'], w0, ETA) if DYN == 'replicator' else equilibrium(R['M'], BETA, w0)
            keep = sorted((x for x in range(len(w)) if w[x] >= W_MIN), key=lambda x: -w[x])[:N_MAX]; tot = sum(w[x] for x in keep)
            field = {R['names'][x]: dict(field[R['names'][x]], w=float(w[x] / tot), fit=float(f[x])) for x in keep}
            predict(i, field)
            say(f"iteration {i}: weights " + ', '.join(f"{n} {100 * t['w']:.0f}%" for n, t in sorted(field.items(), key=lambda kv: -kv[1]['w'])[:8])
                + f"; {len(R['names']) - len(keep)} dropped")
            S.update(step='climb', field=field); json.dump(S, open(ST, 'w'), indent=1)
        if S['step'] == 'climb':
            field_files(i, field)                                   # the climbs play the equilibrium field with its brings
            say(f"{TAG}: iteration {i}: climbs from {min(STARTS, len(field))} field teams")
            moved = climbs(i, field); w0 = ENTRY if V2 else min(t['w'] for t in field.values())
            for n, g in moved.items():
                field[f'sp{i}-{n}'] = dict(gids=g, w=w0, origin=f'climbed from {n} in iteration {i}', bring=[C.GRID[x]['species'] for x in g[:4]])
            if V2:
                tot = sum(t['w'] for t in field.values())
                for t in field.values(): t['w'] /= tot
            say(f"iteration {i}: {len(moved)} climbs moved: " + '; '.join(f"{n} -> " + ', '.join(C.forme(x) for x in g) for n, g in moved.items()))
            S.update(iter=i, step='score', field=field); json.dump(S, open(ST, 'w'), indent=1)
    say('self-play backtest finished')

if __name__ == '__main__':
    if sys.argv[1:2] == ['score']: score(int(sys.argv[2]))
    elif sys.argv[1:2] == ['run']: run()
