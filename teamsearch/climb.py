"""Hill climb over sixes (user's plan, 2026-10-03): from each start team, try every one-member swap, keep the best, repeat.

Neighbours of a team (rules agreed with the user, 2026-10-03):
  - replace any one member with any swap-pool set (swap_pool.json, non-fallback), including another set of the same species
  - species clause by base species (Indeedee / Indeedee-F, Garchomp / Mega Garchomp Z count as one)
  - item clause: if the candidate's item clashes with a teammate's, use that species' next item-clause fallback set that doesn't
    clash; a species that clearly uses one item (top item >= 85% of its regional sets, every Mega) is skipped instead
  - Mega Stones: no cap in round 1; if no team's accepted round-1 swap has 3+ stones, cap at 2 from round 2 on
Each round (evaluate.py: 4v4 battles vs the 10 replay archetypes x 6 lead pairs; brings from bring/policy.py):
  pre-filter every neighbour by the one-on-one matrix score (bring/policy.matrix_score) to the top `prefilter`, plus `random_extra`
  random ones (to check the pre-filter); screen those and the current team with screen_pj games per job; re-test the current team
  and the best top_k with confirm_pj games per job on new seeds; move to the best if its pooled paired gain > MARGIN x SE.

  python3 climb.py stats                     neighbourhood sizes per start team (no sims)
  python3 climb.py round [thorough|lean]     play the next round (state: climb_state.json, log: climb_log.jsonl)
  python3 climb.py sharpen                   one-off: re-test marginal past moves and stopped starts' near-misses (sequential rule)
"""
import json, os, sys, math, collections, time
import multiprocessing as mp
import sets_lib as L
HERE = L.HERE
GRID = json.load(open(os.path.join(HERE, 'grid_sets.json')))
POOL = json.load(open(os.path.join(HERE, 'swap_pool.json')))
INDEX = json.load(open(os.environ.get('TS_INDEX') or os.path.join(HERE, 'teams', 'start', 'index.json')))   # TS_INDEX: e.g. teams/arch_start/index.json
CANDS = [p['gid'] for p in POOL if not p['fallback']]
FALLBACKS = collections.defaultdict(list)                      # forme -> fallback gids, most common item first
for p in sorted((p for p in POOL if p['fallback']), key=lambda p: -p['cluster_share']): FALLBACKS[p['forme']].append(p['gid'])
ONE_ITEM = {p['forme'] for p in POOL if p['one_item']}
MARGIN = float(os.environ.get('MARGIN', 1.0))                    # move only if the paired gain beats this many SEs

def base(g): return L.DEX['species'][L.idf(GRID[g]['species'])]['base']
def item(g): return GRID[g]['item'] or None
def forme(g): return L.battle_forme(GRID[g]['species'], GRID[g]['item'])
def is_mega(g): return bool((L.DEX['items'].get(L.idf(GRID[g]['item'] or ''), {}) or {}).get('megaStone'))
def megas(team): return sum(map(is_mega, team))
def key(team): return tuple(sorted(team))
def arch_of(team):
    """the rule archetype (pssim/pro_replays.arch, as the opponent groups use it)"""
    sys.path.insert(0, os.path.join(HERE, '..', 'pssim'))
    from pro_replays import arch
    from cluster_opps import norm
    return arch([norm(GRID[g]['species']) for g in team])
def team_json(team):
    """MYTEAM format (keys = species), for the sims"""
    return {GRID[g]['species']: {k: GRID[g][k] for k in ('species', 'item', 'ability', 'nature', 'evs', 'moves')} for g in team}

def neighbours(team, cap=None):
    """[(slot, out gid, in gid, new team, note)], one per distinct new team"""
    out, seen = [], {key(team)}
    for i, old in enumerate(team):
        rest = team[:i] + team[i + 1:]
        bases = {base(g) for g in rest}; items = {item(g) for g in rest} - {None}
        for c in CANDS:
            if c == old or base(c) in bases: continue
            g, note = c, ''
            if item(c) in items:
                f = forme(c)
                if f in ONE_ITEM: continue                        # clearly one item: skip the swap
                g = next((x for x in FALLBACKS[f] if item(x) not in items), None)
                if g is None or g == old: continue
                note = f'item clause: {GRID[c]["item"]} -> {GRID[g]["item"]}'
            new = rest[:i] + [g] + rest[i:]
            if cap is not None and megas(new) > cap: continue
            if key(new) in seen: continue
            seen.add(key(new)); out.append((i, old, g, new, note))
    return out

# ---------------- one round of the climb (state in climb_state.json, so each round can be reviewed) ----------------
ROUND_CFG = {   # round 1 "thorough" (user, 2026-10-03); later rounds may switch to "lean" after review
    # screening = bring search (top bring_k choices per archetype x 6 opposing leads x 1 game); confirm = fresh paired games with the
    # chosen brings, confirm_pj per job (x 60 jobs). Bring search added 2026-10-03 after the Trick Room six check: heuristic brings
    # alone lost 12.5 points to the sheet's picks; the top-4 shortlist, battle-tested, matched them (72.3 vs 72.5).
    'thorough': dict(prefilter=10, random_extra=2, bring_k=3, top_k=3, confirm_pj=4),
    'lean': dict(prefilter=5, random_extra=1, bring_k=3, top_k=1, confirm_pj=3),
    'test': dict(prefilter=1, random_extra=1, bring_k=1, top_k=1, confirm_pj=1),             # plumbing check only
}
# Sequential testing (user, 2026-10-04: "rerun the ones within error ... ignore the swaps that are clearly bad and sharpen the
# ones we aren't sure about"). A candidate swap is
#   better   if pooled gain - z*SE > 0             -> move to the best such candidate (z = 2: a no-effect swap passes ~2.5%)
#   dropped  if pooled gain + z_drop*SE < delta    -> unlikely to be worth delta = 2 win-share points (z_drop = 1); smaller
#                                                     gains can't be verified at sane cost, and dropping no-effect swaps early
#                                                     is what keeps sharpening cheap
#   undecided otherwise                       -> another batch of batch_pj games per job (x 60 jobs) for it and the current team,
#                                                fresh paired seeds, up to max_batches batches in all (the confirm batch is batch 0)
# Replaces the old rule (best of top_k accepted at gain > 1 SE), which accepted a no-effect swap about 40% of the time.
# Hold batch (user, 2026-10-06, after a Farigiraf set swap passed at +14.4 +- 5.2 on one batch): a candidate that clears the bar is
# not accepted yet: it gets one more fresh batch, and moves only if that batch's gain is positive AND all its batches pooled still clear
# gain - z*SE > 0. If not, it stays undecided (a later clear needs another positive batch). A clear in the last allowed batch gets its
# hold batch past max_batches. Without it, a fluke passed ~2.3% per look; with it, about 1%. TS_SEQ_HOLD=0 restores the old rule.
SEQ = dict(z=float(os.environ.get('TS_SEQ_Z', 2.0)), z_drop=float(os.environ.get('TS_SEQ_ZDROP', 1.0)), delta=float(os.environ.get('TS_SEQ_DELTA', 0.02)),
           batch_pj=int(os.environ.get('TS_SEQ_BATCH_PJ', 4)), max_batches=int(os.environ.get('TS_SEQ_MAX', 8)),
           hold=os.environ.get('TS_SEQ_HOLD', '1') == '1')
STATE = os.environ.get('TS_STATE', os.path.join(HERE, 'climb_state.json'))
LOG = os.environ.get('TS_LOG', os.path.join(HERE, 'climb_log.jsonl'))

def paired(a, b):
    """archetype-weighted mean and SE of (b - a) over the 60 jobs, from per-job win shares on the same seeds"""
    import evaluate as E
    import numpy as np
    d, w = [], []
    for j in a['per_job']:
        (sa, na), (sb, nb) = a['per_job'][j], b['per_job'][j]
        if na and nb:
            d.append(sb / nb - sa / na)
            if 'w_job' in a: w.append(a['w_job'][j])                    # pool mode: each job's weight in the score
            else:
                arch = E.ARCHS[int(j) // E.P.K]; k = int(j) % E.P.K
                w.append(E.P.ARCH_SHARE[arch] * E.P.pair_shares(arch)[k])
    d, w = np.array(d), np.array(w) / sum(w)
    m = float(w @ d); se = float(np.sqrt(np.sum(w ** 2 * (d - m) ** 2) * len(d) / max(1, len(d) - 1)))
    if E.perish_real():                 # Perish is a fixed real rate per team archetype: no noise, only a shift if the archetype changes
        f = E.P.ARCH_SHARE[E.PERISH] / sum(E.P.ARCH_SHARE.values())
        m, se = (1 - f) * m + f * (b['by_arch'][E.PERISH] - a['by_arch'][E.PERISH]), (1 - f) * se
    return m, se

def pooled(batches):
    """gain and SE of candidate over current, pooled over independent paired batches [(current result, candidate result)]"""
    ms = [paired(a, b) for a, b in batches]
    m = sum(x for x, _ in ms) / len(ms); se = (sum(e * e for _, e in ms)) ** 0.5 / len(ms)
    return m, se

def verdict(cands):
    """('move', best clearly-better cand) | ('stop', None) | ('more', undecided cands); cands carry 'batches'.
    With SEQ['hold'], a candidate that clears the bar is marked c['hold_at'] (the index of its hold batch) and counts as undecided
    until that batch is in; it is better only if the hold batch's gain is positive and the pooled gain still clears."""
    st = [(pooled(c['batches']), c) for c in cands]; better, und = [], []
    for (m, se), c in st:
        if m - SEQ['z'] * se > 0:
            if not SEQ.get('hold'): better.append((m, c)); continue
            h = c.get('hold_at')
            if h is not None and len(c['batches']) > h:
                if pooled(c['batches'][h:])[0] > 0: better.append((m, c)); continue
                c['holds_failed'] = c.get('holds_failed', 0) + 1
                c['hold_at'] = len(c['batches'])                           # did not hold: any later move needs another positive batch
            elif h is None: c['hold_at'] = len(c['batches'])
            und.append(c)
        else:
            c.pop('hold_at', None)
            if m + SEQ['z_drop'] * se >= SEQ['delta']: und.append(c)
    if better: return 'move', max(better, key=lambda t: t[0])[1]
    return ('more', und) if und else ('stop', None)

def sharpen(items, seed_base, label, rnd=None):
    """items: [{start, cur, cur_brings, cur_batches: [result], cands: [{x, team, brings, batches: [(cur res, cand res)]}]}].
    Adds batches for undecided candidates until each item is decided or has max_batches. Sets item['verdict'], item['pick']."""
    import evaluate as E
    for b in range(1, SEQ['max_batches'] + 2):
        need = []
        for it in items:
            if it.get('verdict') in ('move', 'stop'): continue
            v, c = verdict(it['cands'])
            if v == 'more' and b >= SEQ['max_batches']:                     # at the limit, only a pending hold batch still runs
                c = [x for x in c if b == SEQ['max_batches'] and x.get('hold_at') == len(x['batches'])]
            if v != 'more' or not c:
                it['verdict'], it['pick'] = ('undecided', None) if v == 'more' else (v, c); continue
            it['pending'] = c; need.append(it)
        if not need: break
        seed = seed_base + 50 * b                                          # batch 0 used [seed_base, seed_base + confirm_pj)
        runs = {}
        for it in need:
            runs[(key_s(it['cur']), json.dumps(it['cur_brings'], sort_keys=True))] = (it['cur'], it['cur_brings'])
            for c in it['pending']: runs[(key_s(c['team']), json.dumps(c['brings'], sort_keys=True))] = (c['team'], c['brings'])
        keys = list(runs)
        progress(round=rnd, mode=label, phase='sharpen', batch=b, starts=len(need), teams=len(keys), seed=seed, per_job=1 if os.environ.get('TS_OPP') == 'pool' else SEQ['batch_pj'], jobs_per_team=live_jobs())
        print(time.strftime('%I:%M %p'), f"  {label}: batch {b}: {len(need)} undecided start(s), {len(keys)} teams x {60 * SEQ['batch_pj']} games", flush=True)
        res = dict(zip(keys, E.evaluate_fixed([runs[k][0] for k in keys], [runs[k][1] for k in keys], SEQ['batch_pj'], seed)))
        for it in need:
            cr = res[(key_s(it['cur']), json.dumps(it['cur_brings'], sort_keys=True))]
            for c in it['pending']: c['batches'].append((cr, res[(key_s(c['team']), json.dumps(c['brings'], sort_keys=True))]))
        for it in need: it.pop('pending', None)
    for it in items: it.setdefault('verdict', 'undecided'); it.setdefault('pick', None)
    return items

PROGRESS = os.environ.get('TS_PROGRESS', os.path.join(HERE, 'climb_progress.json'))
def progress(**k):
    """phase marker for status_server.py: which battles the current phase is waiting for (sim = the output tag's setup)"""
    json.dump(dict(k, at=time.time(), sim=os.environ.get('TS_SIM', 'v3')), open(PROGRESS, 'w'))
def live_jobs(phase='confirm'):
    """battle jobs per team: 6 lead pairs x the archetypes actually battled (Perish is skipped with TS_PERISH=real; x bring_k when
    screening); in pool mode, groups x entries"""
    import evaluate as E
    if E.pool_mode():
        import poolmode
        return poolmode.jobs_per_team(phase)
    return len(E.live_archs()) * E.P.K * (ROUND_CFG['thorough']['bring_k'] if phase == 'screen' else 1)

def run_round(mode):
    import random, evaluate as E, policy as P
    cfg = ROUND_CFG[mode]
    only = os.environ.get('TS_STARTS')                                 # e.g. a plumbing test on two starts
    st = json.load(open(STATE)) if os.path.exists(STATE) else dict(round=0, cap=None, teams={n: dict(team=v['gids'], done=False, path=[], arch=arch_of(v['gids']))
                                                                       for n, v in INDEX.items() if not only or n in only.split(',')})
    rnd = st['round'] + 1; seed_s, seed_c = 1000 * rnd, 500000 + 1000 * rnd
    print(f"round {rnd}: sim setup {E.sim()}, battle binary {os.path.basename(E.bin_path())}", flush=True)   # TS_SIM (default v3)
    active = [n for n, t in st['teams'].items() if not t['done']]
    plan = {}
    progress(round=rnd, mode=mode, phase='prefilter', starts=len(active))
    lock = os.environ.get('TS_ARCH_LOCK') == '1'                       # per-archetype climbs: only swaps that keep the start's archetype
    nbs = {n: [x for x in neighbours(st['teams'][n]['team'], st['cap']) if not lock or arch_of(x[3]) == st['teams'][n].get('arch', arch_of(INDEX[n]['gids']))]
           for n in active}
    flat = list({key_s(x[3]): x[3] for n in active for x in nbs[n]}.values())
    t0 = time.time()
    cache = os.path.join(os.environ.get('TS_CACHE_DIR', HERE), f'climb_prefilter_r{rnd}.json')   # so a relaunch skips this step
    msc = json.load(open(cache)) if os.path.exists(cache) else {}
    todo = [t for t in flat if key_s(t) not in msc]
    if todo:
        with mp.get_context('spawn').Pool(int(os.environ.get('TS_PREFILTER_PROCS', 12))) as pool:      # pre-filter by the matrix score
            msc.update(zip(map(key_s, todo), pool.map(_matrix_score, todo, chunksize=20)))
        json.dump(msc, open(cache, 'w'))
    print(f"round {rnd}: matrix pre-filter of {len(flat)} neighbour teams ({len(todo)} new) in {(time.time() - t0) / 60:.1f} min", flush=True)
    lp = learned_prefilter(LOG)
    print(f"round {rnd}: pre-filter = {'learned from earlier rounds (set effects + matrix score)' if lp else 'matrix score'}", flush=True)
    for n in active:
        cur = st['teams'][n]['team']; nb = nbs[n]
        ms = [((lp(x[1], x[2], msc[key_s(x[3])]) if lp else msc[key_s(x[3])]), x) for x in nb]; ms.sort(key=lambda t: -t[0])
        rng = random.Random(f'{n}|{rnd}')
        rest = [x for _, x in ms[cfg['prefilter']:]]
        plan[n] = dict(cur=cur, top=[x for _, x in ms[:cfg['prefilter']]], rand=rng.sample(rest, min(cfg['random_extra'], len(rest))),
                       mscore={key_s(x[3]): sc for sc, x in ms}, n_nb=len(nb))
    games = sum(60 * (cfg['bring_k'] * (1 + len(p['top']) + len(p['rand'])) + cfg['confirm_pj'] * (1 + cfg['top_k'])) for p in plan.values())
    print(f"round {rnd} ({mode}): {len(active)} teams, about {games} games", flush=True)
    uniq = lambda ts: list({key_s(t): t for t in ts}.values())
    # starts interleaved (2026-10-14): a start's neighbours share most fours, so run them apart and the later ones find those games in
    # the game cache instead of playing them at the same time (the order never changes a result)
    mix = lambda ls: [l[i] for i in range(max(map(len, ls), default=0)) for l in ls if i < len(l)]
    scr_teams = uniq([p['cur'] for p in plan.values()] + mix([[x[3] for x in p['top'] + p['rand']] for p in plan.values()]))
    progress(round=rnd, mode=mode, phase='screen', starts=len(active), teams=len(scr_teams), seed=seed_s, per_job=1, jobs_per_team=live_jobs('screen'))
    os.environ['TS_BRING_K'] = str(cfg['bring_k'])
    scr = dict(zip(map(key_s, scr_teams), E.search_many(scr_teams, seed_s)))
    for n, p in plan.items():
        p['ranked'] = sorted(p['top'] + p['rand'], key=lambda x: -paired(scr[key_s(p['cur'])], scr[key_s(x[3])])[0])[:cfg['top_k']]
    con_teams = uniq([p['cur'] for p in plan.values()] + mix([[x[3] for x in p['ranked']] for p in plan.values()]))
    progress(round=rnd, mode=mode, phase='confirm', starts=len(active), teams=len(con_teams), seed=seed_c, per_job=1 if os.environ.get('TS_OPP') == 'pool' else cfg['confirm_pj'], jobs_per_team=live_jobs())
    con = dict(zip(map(key_s, con_teams), E.evaluate_fixed(con_teams, [scr[key_s(t)]['chosen'] for t in con_teams], cfg['confirm_pj'], seed_c)))
    accepted_megas = []
    items = [dict(start=n, cur=p['cur'], cur_brings=scr[key_s(p['cur'])]['chosen'],
                  cands=[dict(x=x, team=x[3], brings=scr[key_s(x[3])]['chosen'], batches=[(con[key_s(p['cur'])], con[key_s(x[3])])])
                         for x in p['ranked']]) for n, p in plan.items()]
    sharpen(items, seed_c, mode, rnd)                                    # fresh paired games only (screening picked the brings)
    by_start = {it['start']: it for it in items}
    log = open(LOG, 'a')
    for n, p in plan.items():
        it = by_start[n]
        stats = [(pooled(c['batches']), c) for c in it['cands']]
        (m, se), c = (pooled(it['pick']['batches']), it['pick']) if it['pick'] else max(stats, key=lambda t: t[0][0])
        x = c['x']
        t = st['teams'][n]
        rec = dict(round=rnd, mode=mode, start=n, team=p['cur'], score=con[key_s(p['cur'])]['score'], n_neighbours=p['n_nb'],
                   brings_current=scr[key_s(p['cur'])]['chosen'], brings_best=scr[key_s(x[3])]['chosen'], score_best=con[key_s(x[3])]['score'],
                   bring_tags=scr[key_s(x[3])].get('tag'),                         # plan-aware bring search: where each chosen bring came from
                   best=dict(slot=x[0], out=x[1], into=x[2], note=x[4], diff=m, se=se, matrix=p['mscore'][key_s(x[3])],
                             from_random=x in p['rand']),
                   screened=[dict(out=y[1], into=y[2], diff=paired(scr[key_s(p['cur'])], scr[key_s(y[3])])[0], matrix=p['mscore'][key_s(y[3])],
                                  random=y in p['rand']) for y in p['top'] + p['rand']], cap=st['cap'],
                   verdict=it['verdict'], seq=SEQ, confirmed=[dict(out=cc['x'][1], into=cc['x'][2], diff=mm, se=ss, batches=len(cc['batches']), holds_failed=cc.get('holds_failed', 0))
                                                              for (mm, ss), cc in stats])
        if it['verdict'] == 'move':
            t['team'] = x[3]; t['path'].append(rec['best']); accepted_megas.append(megas(x[3]))
        else:
            t['done'] = True
        log.write(json.dumps(rec) + '\n'); log.flush()
        print(f"  {n:16s} {x[1]:>16s} -> {x[2]:16s} {m:+.3f} (SE {se:.3f}, {len(c['batches'])} batch{'es' if len(c['batches']) > 1 else ''})  "
              f"{'MOVE' if it['verdict'] == 'move' else 'local max' if it['verdict'] == 'stop' else 'local max (undecided)'}", flush=True)
    if rnd == 1 and st['cap'] is None and not any(c >= 3 for c in accepted_megas):
        st['cap'] = 2; print("no round-1 move reached 3+ Mega Stones: capping at 2 from round 2", flush=True)
    st['round'] = rnd; json.dump(st, open(STATE, 'w'), indent=1)
    progress(round=rnd, mode=mode, phase='done', starts=len(active), moved=sum(1 for n in active if not st['teams'][n]['done']))

def key_s(team): return '|'.join(sorted(team))

def sharpen_pass(seed_base=900000):
    """One-off pass over a finished climb's state (old >1-SE rule) with the sequential rule:
      1. each start's latest move, if it was marginal (gain - z*SE <= 0): re-test the team before vs after it; if the move is
         clearly not worth it, revert it and let that start climb again;
      2. each start that stopped: re-test the top_k swaps confirmed in its last round; move if one is now clearly better.
    Batch 0 is the original confirm games (re-read from the runs/ cache when present); extra batches use fresh seeds from
    seed_base. Log: climb_sharpen.jsonl."""
    import evaluate as E
    st = json.load(open(STATE)); log = [json.loads(l) for l in open(LOG)]
    cfg = ROUND_CFG['thorough']; z = SEQ['z']
    swap = lambda team, o, i: [g for g in team if g != o] + [i]
    as_fixed = lambda b: {a: (v[0], v[1]) for a, v in b.items()}
    # 1. marginal latest moves
    ver = []
    for n, t in st['teams'].items():
        if not t['path']: continue
        last = t['path'][-1]
        r = [x for x in log if x['start'] == n and x['best']['out'] == last['out'] and x['best']['into'] == last['into']][-1]
        if r['best']['diff'] - z * r['best']['se'] > 0: continue
        pre, post = r['team'], swap(r['team'], last['out'], last['into'])
        b0 = E.evaluate_fixed([pre, post], [as_fixed(r['brings_current']), as_fixed(r['brings_best'])], cfg['confirm_pj'], 500000 + 1000 * r['round'])
        ver.append(dict(start=n, kind='verify', cur=pre, cur_brings=as_fixed(r['brings_current']),
                        cands=[dict(x=(r['best']['slot'], last['out'], last['into'], post, ''), team=post, brings=as_fixed(r['brings_best']), batches=[tuple(b0)])]))
    print(f"sharpen: re-testing {len(ver)} marginal latest moves", flush=True)
    sharpen(ver, seed_base, 'verify')
    reverted = []
    for it in ver:
        if it['verdict'] == 'stop':
            t = st['teams'][it['start']]; t['team'] = it['cur']; t['path'].pop(); t['done'] = False; reverted.append(it['start'])
    # 2. near-misses of stopped starts
    near = []
    for n, t in st['teams'].items():
        if not t['done']: continue
        r = [x for x in log if x['start'] == n][-1]
        cands = sorted(r['screened'], key=lambda y: -y['diff'])[:cfg['top_k']]
        teams = [r['team']] + [swap(r['team'], y['out'], y['into']) for y in cands]
        os.environ['TS_BRING_K'] = str(cfg['bring_k'])
        sr = E.search_many(teams, 1000 * r['round'])                     # cached screening -> the same chosen brings
        b0 = E.evaluate_fixed(teams, [x['chosen'] for x in sr], cfg['confirm_pj'], 500000 + 1000 * r['round'])
        near.append(dict(start=n, kind='near-miss', cur=teams[0], cur_brings=sr[0]['chosen'],
                         cands=[dict(x=(None, y['out'], y['into'], tm, ''), team=tm, brings=s_['chosen'], batches=[(b0[0], b0[i + 1])])
                                for i, (y, tm, s_) in enumerate(zip(cands, teams[1:], sr[1:]))]))
    print(f"sharpen: re-testing near-misses of {len(near)} stopped starts", flush=True)
    sharpen(near, seed_base + 5000, 'near-miss')
    moved = []
    out = open(os.path.join(os.path.dirname(LOG), 'climb_sharpen.jsonl'), 'a')
    for it in ver + near:
        stats = [dict(out=c['x'][1], into=c['x'][2], diff=pooled(c['batches'])[0], se=pooled(c['batches'])[1], batches=len(c['batches'])) for c in it['cands']]
        if it['kind'] == 'near-miss' and it['verdict'] == 'move':
            c = it['pick']; m, se = pooled(c['batches']); t = st['teams'][it['start']]
            t['team'] = c['team']; t['done'] = False
            t['path'].append(dict(slot=None, out=c['x'][1], into=c['x'][2], note='sharpen', diff=m, se=se, matrix=None, from_random=False))
            moved.append(it['start'])
        out.write(json.dumps(dict(start=it['start'], kind=it['kind'], verdict=it['verdict'], seq=SEQ, cands=stats,
                                  reverted=it['start'] in reverted and it['kind'] == 'verify')) + '\n')
        best = max(stats, key=lambda d: d['diff'])
        print(f"  {it['kind']:9s} {it['start']:16s} {best['out']:>16s} -> {best['into']:16s} {best['diff']:+.3f} (SE {best['se']:.3f}, "
              f"{best['batches']} batches)  {it['verdict']}{'  REVERTED' if it['start'] in reverted and it['kind'] == 'verify' else ''}", flush=True)
    st['sharpened'] = time.strftime('%Y-%m-%d %H:%M'); json.dump(st, open(STATE, 'w'), indent=1)
    print(f"sharpen: reverted {len(reverted)} moves, {len(moved)} stopped starts moved; "
          f"{sum(1 for t in st['teams'].values() if not t['done'])} starts climbing again", flush=True)

def learned_prefilter(log_path, lam=3.0):
    """pre-filter learned from earlier rounds' screened swaps (added 2026-10-04 after round 1: the matrix score alone had a
    within-team correlation of +0.20 with the screened gain; incoming/outgoing set effects + the matrix score, ridge, +0.30 on
    held-out starts). Returns score(out gid, in gid, matrix score of the new team) or None if there's no history."""
    import numpy as np
    if not os.path.exists(log_path): return None
    rows = [(s['out'], s['into'], s['matrix'], s['diff']) for l in open(log_path) for s in json.loads(l).get('screened', [])]
    if len(rows) < 50: return None
    intos = sorted({r[1] for r in rows}); outs = sorted({r[0] for r in rows})
    ii = {g: i for i, g in enumerate(intos)}; oi = {g: len(intos) + i for i, g in enumerate(outs)}; k = len(intos) + len(outs) + 1
    A = np.zeros((len(rows), k)); y = np.array([r[3] for r in rows])
    for n, (o, i, m, d) in enumerate(rows): A[n, ii[i]] = 1; A[n, oi[o]] = 1; A[n, -1] = m
    w = np.linalg.solve(A.T @ A + lam * np.eye(k), A.T @ (y - y.mean()))
    return lambda o, i, m: (w[ii[i]] if i in ii else 0.0) + (w[oi[o]] if o in oi else 0.0) + w[-1] * m
def _matrix_score(team):
    import evaluate as E                                               # (puts bring/ on the path in a spawned worker)
    return E.P.matrix_score(team)

if __name__ == '__main__':
    starts = {n: v['gids'] for n, v in INDEX.items()}
    if sys.argv[1:2] == ['stats']:
        tot = 0
        for n, t in starts.items():
            nb = neighbours(t); tot += len(nb)
            m3 = sum(megas(x[3]) >= 3 for x in nb); fb = sum(bool(x[4]) for x in nb)
            print(f"{n:16s} megas {megas(t)}  neighbours {len(nb):3d}  (3+ Megas {m3:3d}, via item fallback {fb:2d}, with cap 2: {len(neighbours(t, 2))})")
        print(f"total {tot} neighbours over {len(starts)} starts")
        for mode, c in ROUND_CFG.items():
            g = len(starts) * 60 * (c['bring_k'] * (1 + c['prefilter'] + c['random_extra']) + c['confirm_pj'] * (1 + c['top_k']))
            print(f"  a {mode} round: about {g} games = {g * 5.5 / 3600 / 12:.1f} h on 12 threads at 5.5 s/game")
    elif sys.argv[1:2] == ['sharpen']:
        sharpen_pass()
    elif sys.argv[1:2] == ['round']:
        run_round(sys.argv[2] if len(sys.argv) > 2 else 'thorough')
    else:
        print(__doc__)
