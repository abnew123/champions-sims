"""Stage 1 refinement (user, 2026-10-06): once a climb has converged, try each member of its best teams with that species' other common
regional sets (another moveset, nature, ability or item; the climb itself only ever had one set per species and item, e.g. the
dual-weather Hurricane Charizard Y). One member's set changes at a time, judged like a climb swap, repeated until no change passes:
  alternatives  per member: the same battle forme's grid sets seen >= TS_REFINE_MIN (2) times at the regionals, distinct in item /
                ability / nature / moves, engine-supported, no item clash; the TS_REFINE_ALT (4) most common
  screening     the climb's bring search for the team and every variant
  confirm       the TS_REFINE_TOPK (6) variants with the best screening gain, paired games, then climb.sharpen's sequential rule
                (change if gain - 2 SE > 0 and a fresh hold batch's gain is positive, drop if gain + 1 SE < 2 points, up to 8
                batches). Bring luck is held out: where a
                variant's bring for an opponent group uses neither the old nor the new set, it plays the team's own bring there
Runs under whatever setup the environment gives (e.g. cloud/run_env_poolmiss.sh: pool opponents, misses doubled). Teams: the best
N teams of a climb (latest confirm score per start, as report.py) plus the user's current core (sixth.py's core + Archaludon).
Files: refine_<sim>_state.json, refine_<sim>_log.jsonl, refine_<sim>_progress.json in TS_REFINE_DIR (default teamsearch/).
  (<climb dir> <climb prefix> [N] can be just 'core': only the user's core)
  python3 refine.py list <climb dir> <climb prefix> [N=5]     teams, their alternatives, and which alternatives lack matrix cells
  python3 refine.py cells <climb dir> <climb prefix> [N=5]    compute the missing cells (mx/grid_pool.py, NPROC processes)
  python3 refine.py run <climb dir> <climb prefix> [N=5]      the refinement (TS_PARALLEL x TS_THREADS); resumes from its state file
  TS_REFINE_TEST=1: plumbing check (1 alternative per member, top 1, 1 round, bring_k 1)
"""
import json, os, sys, time, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
TEST = os.environ.get('TS_REFINE_TEST') == '1'
OUTD = os.environ.get('TS_REFINE_DIR', HERE)
SIM = os.environ.get('TS_SIM', 'v3')
os.environ['TS_PROGRESS'] = os.path.join(OUTD, f'refine_{SIM}_progress.json')        # climb.sharpen's progress marker: never a climb's
import climb as C, evaluate as E
GRID = C.GRID
SUPPORT = json.load(open(os.path.join(HERE, 'support.json')))
MIN_RC = int(os.environ.get('TS_REFINE_MIN', 2)); ALT_K = 1 if TEST else int(os.environ.get('TS_REFINE_ALT', 4))
TOP_K = 1 if TEST else int(os.environ.get('TS_REFINE_TOPK', 6)); ROUNDS = 1 if TEST else int(os.environ.get('TS_REFINE_ROUNDS', 4))
BRING_K = 1 if TEST else 3
CORE = ['M-Delphox#1', 'Garchomp#1', 'M-Charizard Y#2', 'Incineroar#2', 'Kingambit#3', 'Archaludon#3']   # sixth.py's best
STATE = os.path.join(OUTD, f'refine_{SIM}_state.json'); LOG = os.path.join(OUTD, f'refine_{SIM}_log.jsonl')

def content(g):
    s = GRID[g]; return (s['item'], s['ability'], s['nature'], tuple(sorted(s['moves'])))

def has_cells(g): return all(os.path.exists(os.path.join(HERE, 'mx', 'out', t, g.replace('/', '_') + '.json')) for t in ('tr', 'notr'))

def alternatives(team, i):
    """the most common other regional sets of member i's battle forme that the team can hold"""
    g = team[i]; f = C.forme(g); items = {C.item(x) for j, x in enumerate(team) if j != i} - {None}; best = {}
    for x, s in GRID.items():
        if x.startswith('smogon:') or x in SUPPORT or C.forme(x) != f or (s.get('regional_count') or 0) < MIN_RC: continue
        if content(x) == content(g) or C.item(x) in items: continue
        k = content(x)
        if k not in best or s['regional_count'] > GRID[best[k]]['regional_count']: best[k] = x
    return sorted(best.values(), key=lambda x: -GRID[x]['regional_count'])[:ALT_K]

def variants(team):
    return [(i, team[i], a, team[:i] + [a] + team[i + 1:], '') for i in range(len(team)) for a in alternatives(team, i)]

def merge_brings(base_b, var_b, old, new):
    """the variant's bring where it or the team's own bring involves the changed member; elsewhere the team's (no bring luck)"""
    out = {}
    for k, vb in var_b.items():
        bb = base_b[k]
        out[k] = vb if (new in list(vb[0]) + list(vb[1]) or old in list(bb[0]) + list(bb[1])) else bb
    return out

def best_teams(d, prefix, n):
    """{start: team} for the n best teams of a climb by latest confirm score (as report.py), distinct teams only"""
    latest = {}
    for line in open(os.path.join(d, f'{prefix}_log.jsonl')):
        r = json.loads(line); moved = r.get('verdict') == 'move'
        team = list(r['team'])
        if moved: team[r['best']['slot']] = r['best']['into']
        latest[r['start']] = (r['score_best'] if moved else r['score'], team)
    out, seen = {}, set()
    for s, (sc, t) in sorted(latest.items(), key=lambda kv: -kv[1][0]):
        if C.key(t) in seen: continue
        seen.add(C.key(t)); out[s] = t
        if len(out) == n: break
    return out

def teams_from(args):
    if args[:1] == ['core']: return {'core: Delphox, Scarf Garchomp, Charizard Y, Archaludon': CORE}
    d = os.path.join(HERE, args[0]) if not os.path.isabs(args[0]) else args[0]
    t = best_teams(d, args[1], int(args[2]) if len(args) > 2 else 5)
    if C.key(CORE) not in {C.key(x) for x in t.values()}: t['core: Delphox, Scarf Garchomp, Charizard Y, Archaludon'] = CORE
    return t

def show(g):
    s = GRID[g]; return f"{g} ({s['nature']}, {s['ability']}, {s['item']}: {' / '.join(s['moves'])})"

def run(teams):
    st = json.load(open(STATE)) if os.path.exists(STATE) else dict(round=0, teams={n: dict(team=t, done=False, path=[]) for n, t in teams.items()})
    print(time.strftime('%I:%M %p'), f"refine: setup {E.sim()}, {'pool opponents' if E.pool_mode() else 'archetype models'}, {len(st['teams'])} teams", flush=True)
    while st['round'] < ROUNDS:
        active = [n for n, t in st['teams'].items() if not t['done']]
        if not active: break
        r = st['round'] + 1; seed_s, seed_c = 70000 + 1000 * r, 870000 + 1000 * r
        V = {n: variants(st['teams'][n]['team']) for n in active}
        miss = sorted({x[2] for v in V.values() for x in v if not has_cells(x[2])})
        if miss: sys.exit(f"missing matrix cells for {len(miss)} sets: run 'refine.py cells ...' first: {miss}")
        scr_teams = list({C.key_s(t): t for n in active for t in [st['teams'][n]['team']] + [x[3] for x in V[n]]}.values())
        print(time.strftime('%I:%M %p'), f"round {r}: {len(active)} teams, {sum(map(len, V.values()))} variants", flush=True)
        os.environ['TS_BRING_K'] = str(BRING_K)
        C.progress(round=r, mode='refine', phase='screen', starts=len(active), teams=len(scr_teams), seed=seed_s, per_job=1, jobs_per_team=C.live_jobs('screen'))
        scr = dict(zip(map(C.key_s, scr_teams), E.search_many(scr_teams, seed_s)))
        plan = {}
        for n in active:
            cur = st['teams'][n]['team']; cb = scr[C.key_s(cur)]['chosen']
            ranked = sorted(V[n], key=lambda x: -C.paired(scr[C.key_s(cur)], scr[C.key_s(x[3])])[0])
            plan[n] = dict(cur=cur, cb=cb, ranked=ranked, cands=[(x, merge_brings(cb, scr[C.key_s(x[3])]['chosen'], x[1], x[2])) for x in ranked[:TOP_K]])
        runs = {}
        for p in plan.values():
            for t, b in [(p['cur'], p['cb'])] + [(x[3], b) for x, b in p['cands']]:
                runs[(C.key_s(t), json.dumps(b, sort_keys=True))] = (t, b)
        keys = list(runs)
        C.progress(round=r, mode='refine', phase='confirm', starts=len(active), teams=len(keys), seed=seed_c, per_job=1 if E.pool_mode() else 4, jobs_per_team=C.live_jobs())
        con = dict(zip(keys, E.evaluate_fixed([runs[k][0] for k in keys], [runs[k][1] for k in keys], 4, seed_c)))
        rk = lambda t, b: (C.key_s(t), json.dumps(b, sort_keys=True))
        items = [dict(start=n, cur=p['cur'], cur_brings=p['cb'],
                      cands=[dict(x=x, team=x[3], brings=b, batches=[(con[rk(p['cur'], p['cb'])], con[rk(x[3], b)])]) for x, b in p['cands']])
                 for n, p in plan.items()]
        C.sharpen(items, seed_c, 'refine', r)
        log = open(LOG, 'a')
        for it in items:
            n = it['start']; p = plan[n]; t = st['teams'][n]
            stats = [(C.pooled(c['batches']), c) for c in it['cands']]
            rec = dict(round=r, start=n, team=p['cur'], score=con[rk(p['cur'], p['cb'])]['score'], verdict=it['verdict'],
                       screened=[dict(slot=x[0], out=x[1], into=x[2], diff=C.paired(scr[C.key_s(p['cur'])], scr[C.key_s(x[3])])[0]) for x in p['ranked']],
                       confirmed=[dict(slot=c['x'][0], out=c['x'][1], into=c['x'][2], diff=m, se=se, batches=len(c['batches'])) for (m, se), c in stats])
            if it['verdict'] == 'move':
                c = it['pick']; (m, se) = C.pooled(c['batches'])
                rec['change'] = dict(slot=c['x'][0], out=c['x'][1], into=c['x'][2], diff=m, se=se)
                t['team'] = c['team']; t['path'].append(rec['change'])
            else: t['done'] = True
            log.write(json.dumps(rec) + '\n'); log.flush()
            best = max(stats, key=lambda s: s[0][0]) if stats else None
            msg = (f"CHANGE {rec['change']['out']} -> {rec['change']['into']} {100 * rec['change']['diff']:+.1f} ± {100 * rec['change']['se']:.1f}"
                   if it['verdict'] == 'move' else f"no change ({it['verdict']}); best tried {best[1]['x'][1]} -> {best[1]['x'][2]} "
                   f"{100 * best[0][0]:+.1f} ± {100 * best[0][1]:.1f}" if best else 'no alternatives')
            print(f"  {n[:40]:40s} {msg}", flush=True)
        st['round'] = r; json.dump(st, open(STATE, 'w'), indent=1)
    C.progress(round=st['round'], mode='refine', phase='done', starts=len(st['teams']))
    print('\nrefined teams:')
    for n, t in st['teams'].items():
        print(f"  {n}: " + (', '.join(f"{c['out']} -> {c['into']} ({100 * c['diff']:+.1f} ± {100 * c['se']:.1f})" for c in t['path']) or 'no change'))
        for g in t['team']: print(f"      {show(g)}")

if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    teams = teams_from(args)
    if cmd == 'list':
        miss = set()
        for n, t in teams.items():
            print(f"{n}:")
            for i, g in enumerate(t):
                alts = alternatives(t, i); miss |= {a for a in alts if not has_cells(a)}
                print(f"  {show(g)}"); [print(f"      alt {show(a)}  x{GRID[a]['regional_count']}{'' if has_cells(a) else '  (no cells yet)'}") for a in alts]
        print(f"\n{sum(len(variants(t)) for t in teams.values())} variants; {len(miss)} alternatives lack matrix cells")
    elif cmd == 'cells':
        miss = sorted({x[2] for t in teams.values() for x in variants(t) if not has_cells(x[2])})
        print(f"{len(miss)} sets need cells", flush=True)
        for tr in ('0', '1'):
            if miss: subprocess.run([sys.executable, 'grid_pool.py'] + miss, cwd=os.path.join(HERE, 'mx'), check=True, env=dict(os.environ, TR=tr))
    elif cmd == 'run': run(teams)
