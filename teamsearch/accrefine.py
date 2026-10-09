"""Accuracy refinement (user, 2026-10-08): for the per-archetype climb's best teams, swap sets only (same species and battle forme, so
never another Pokemon or a Mega-forme change) toward more 100%-accurate moves, accepting any swap that doesn't make the team worse.
  accurate moves  moves that effectively always hit in the team's own conditions (sure_hit: No Guard, Hurricane / Thunder with a rain
                  setter, Blizzard with a snow setter, Toxic from Poison types, Compound Eyes, Wide Lens, Hustle)
  candidates      per member, the TS_ACC_ALT (3) most common regional sets (seen >= 2 times, engine-supported, no item clash) that raise
                  the team's accurate-move count
  test            the configured bring search for the team and each candidate (plan-aware in cloud/run_env_arch.sh), brings held equal
                  where neither the old nor the new set is involved, then BATCHES (4) paired confirm batches
  accept          gain + TS_ACC_Z (1.0) x SE >= 0 ("doesn't actively worsen": -0.1 +- 1.5 passes, -2.0 +- 1.5 doesn't); among accepted
                  candidates the largest accuracy gain, then the largest score gain. Rounds repeat until no candidate is accepted.
  final check     each changed team against its original on fresh games (seed 85000 / 885000; 79000 / 879000 before 2026-10-08,
                  which round 3 had used too), since small accepted losses can add up
Teams: the best TS_ACC_TOP (2) distinct final teams per archetype from runs/archverify.json (archverify.py), or named starts.
  . cloud/run_env_arch.sh && python3 accrefine.py cells            matrix cells the candidates still need (NPROC processes)
  . cloud/run_env_arch.sh && TS_PARALLEL=30 TS_THREADS=3 python3 accrefine.py run [batches=4] [start names, comma-separated]
  . cloud/run_env_arch.sh && TS_PARALLEL=30 TS_THREADS=3 python3 accrefine.py final [batches=4]   only the final check, from runs/accrefine.json
"""
import json, os, sys, time, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import climb as C, evaluate as E, poolmode as PM, bringplan as BP
G = C.GRID; SUPPORT = json.load(open(os.path.join(HERE, 'support.json')))
MOVES = json.load(open(os.path.join(HERE, '..', 'native', 'champions_data.json')))['moves']
mid = lambda n: ''.join(c for c in n.lower() if c.isalnum())
ALT = int(os.environ.get('TS_ACC_ALT', 3)); Z = float(os.environ.get('TS_ACC_Z', 1.0)); TOP = int(os.environ.get('TS_ACC_TOP', 2))
OUT = os.path.join(HERE, 'runs', 'accrefine.json')

def sure_hit(team, g, m, rain=None, snow=None):
    """does move m of member g effectively always hit, in this team's own conditions? (user, 2026-10-08: "anything else that can be
    100% should also be considered"): accuracy True or 100; No Guard (Mega Raichu Y); Hurricane / Thunder with a rain setter on the
    team (Drizzle, or a Rain Dance user), Blizzard with a snow setter (Snow Warning incl. Mega Froslass, or Snowscape / Chilly
    Reception); Toxic from a Poison type; Compound Eyes x1.3, Wide Lens x1.1; Hustle x0.8 on physical moves"""
    if rain is None: rain = any(BP.ability(x) == 'Drizzle' or 'Rain Dance' in G[x]['moves'] for x in team)
    if snow is None: snow = any(BP.ability(x) == 'Snow Warning' or {'Snowscape', 'Chilly Reception'} & set(G[x]['moves']) for x in team)
    mv = MOVES.get(mid(m)) or {}; a = mv.get('accuracy', True); ab = BP.ability(g)
    if a is True or ab == 'No Guard': return True
    if (m in ('Hurricane', 'Thunder') and rain) or (m == 'Blizzard' and snow): return True
    if m == 'Toxic' and 'Poison' in ((C.L.DEX['species'].get(C.L.idf(C.forme(g))) or {}).get('types') or []): return True
    a *= 1.3 if ab == 'Compound Eyes' else 1.0
    a *= 1.1 if G[g]['item'] == 'Wide Lens' else 1.0
    a *= 0.8 if ab == 'Hustle' and mv.get('category') == 'Physical' else 1.0
    return a >= 100

def accurate(team):
    rain = any(BP.ability(x) == 'Drizzle' or 'Rain Dance' in G[x]['moves'] for x in team)
    snow = any(BP.ability(x) == 'Snow Warning' or {'Snowscape', 'Chilly Reception'} & set(G[x]['moves']) for x in team)
    return sum(sure_hit(team, g, m, rain, snow) for g in team for m in G[g]['moves'])

def has_cells(g): return all(os.path.exists(os.path.join(HERE, 'mx', 'out', t, g.replace('/', '_') + '.json')) for t in ('tr', 'notr'))

def candidates(team):
    """[(slot, old, new, new team, accuracy gain)]"""
    base = accurate(team); out = []
    for i, g in enumerate(team):
        f = C.forme(g); items = {C.item(x) for j, x in enumerate(team) if j != i} - {None}; best = {}
        for x, s in G.items():
            if x.startswith('smogon:') or x in SUPPORT or C.forme(x) != f or (s.get('regional_count') or 0) < 2 or C.item(x) in items: continue
            t = team[:i] + [x] + team[i + 1:]; d = accurate(t) - base
            if d > 0:
                k = (s['item'], s['ability'], s['nature'], tuple(sorted(s['moves'])))
                if k not in best or s['regional_count'] > G[best[k][0]]['regional_count']: best[k] = (x, t, d)
        for x, t, d in sorted(best.values(), key=lambda v: -G[v[0]]['regional_count'])[:ALT]: out.append((i, g, x, t, d))
    return out

def teams_to_refine(names=None):
    if names:                                                          # named starts: their final teams in the climb state
        st = json.load(open(C.STATE))['teams']; return {n: st[n]['team'] if n in st else C.INDEX[n]['gids'] for n in names}
    V = json.load(open(os.path.join(HERE, 'runs', 'archverify.json'))); out = {}
    for a, rows in V.items():
        seen = []
        for r in sorted(rows, key=lambda r: -r['final_score']):
            sp = {G[g]['species'] for g in r['team']}
            if any(len(sp & s) >= 5 for s in seen): continue
            seen.append(sp); out[r['start']] = r['team']
            if len(seen) == TOP: break
    return out

def show(g): s = G[g]; return f"{s['species']} @ {s['item'] or '-'} ({s['nature']}): {' / '.join(s['moves'])}"

def cells_for(gids):
    miss = sorted({g for g in gids if not has_cells(g)})
    print(f"{len(miss)} sets need cells", flush=True)
    for tr in ('0', '1'):
        if miss: subprocess.run([sys.executable, 'grid_pool.py'] + miss, cwd=os.path.join(HERE, 'mx'), check=True, env=dict(os.environ, TR=tr))

def final_check(state, T, B):
    """the safeguard: each changed team against its original on fresh games, since small accepted losses can add up"""
    changed = {n: (T[n], st_['team']) for n, st_ in state.items() if st_['path']}
    if changed:
        both = list({C.key_s(t): t for a, b in changed.values() for t in (a, b)}.values())
        print(time.strftime('%I:%M %p'), f"final check: {len(changed)} changed teams against their originals, {B} batches", flush=True)
        scr = dict(zip(map(C.key_s, both), E.search_many(both, 85000))); thr = int(os.environ.get('TS_THREADS', 3))
        items = [(C.key_s(t), b) for t in both for b in range(B)]; by = {C.key_s(t): t for t in both}
        res = dict(zip(items, E.parallel(lambda kb: PM.evaluate_team(by[kb[0]], scr[kb[0]]['chosen'], 885000 + 50 * kb[1], thr), items, 'final check')))
        sc = lambda t: sum(res[(C.key_s(t), i)]['score'] for i in range(B)) / B
        for n, (a, b) in changed.items():
            m, se = C.pooled([(res[(C.key_s(a), i)], res[(C.key_s(b), i)]) for i in range(B)])
            state[n]['total'] = dict(diff=m, se=se, before=sc(a), after=sc(b))
            print(f"  {n}: refined vs original on fresh games {100 * m:+.1f} ± {100 * se:.1f} ({100 * sc(a):.1f} -> {100 * sc(b):.1f})", flush=True)
    print('\nrefined teams (accurate moves before -> after):')
    for n, s in state.items():
        tot = f" (overall {100 * s['total']['diff']:+.1f} ± {100 * s['total']['se']:.1f})" if s.get('total') else ''
        print(f"  {n}: {s['accurate0']} -> {accurate(s['team'])} of 24{tot}; " + (', '.join(f"{p['out']} -> {p['into']} ({100 * p['diff']:+.1f} ± {100 * p['se']:.1f})" for p in s['path']) or 'no change'))
        for g in s['team']: print(f"      {show(g)}")

def run(B, names):
    T = teams_to_refine(names); state = {n: dict(team=t, path=[], done=False, accurate0=accurate(t)) for n, t in T.items()}
    print(time.strftime('%I:%M %p'), f"{E.sim()}: {len(T)} teams, accept if gain + {Z} SE >= 0, {B} batches", flush=True)
    uses = lambda br, g: g in list(br[0]) + list(br[1])
    for r in range(1, 6):
        active = [n for n, s in state.items() if not s['done']]
        V = {n: candidates(state[n]['team']) for n in active}
        for n in active:
            if not V[n]: state[n]['done'] = True
        active = [n for n in active if V[n]]
        if not active: break
        miss = sorted({x[2] for n in active for x in V[n] if not has_cells(x[2])})
        if miss: sys.exit(f"missing matrix cells: {miss}: run 'accrefine.py cells' first")
        teams = list({C.key_s(t): t for n in active for t in [state[n]['team']] + [x[3] for x in V[n]]}.values())
        print(time.strftime('%I:%M %p'), f"round {r}: {len(active)} teams, {sum(len(V[n]) for n in active)} candidates", flush=True)
        scr = dict(zip(map(C.key_s, teams), E.search_many(teams, 76000 + 1000 * r)))
        runs = {}; plan = {}
        for n in active:
            cur = state[n]['team']; cb = scr[C.key_s(cur)]['chosen']; plan[n] = (cur, cb, [])
            runs[(C.key_s(cur), json.dumps(cb, sort_keys=True))] = (cur, cb)
            for x in V[n]:
                vb = {k: (v if uses(v, x[2]) or uses(cb[k], x[1]) else cb[k]) for k, v in scr[C.key_s(x[3])]['chosen'].items()}
                plan[n][2].append((x, vb)); runs[(C.key_s(x[3]), json.dumps(vb, sort_keys=True))] = (x[3], vb)
        keys = list(runs); thr = int(os.environ.get('TS_THREADS', 3))
        items = [(k, b) for k in keys for b in range(B)]
        res = dict(zip(items, E.parallel(lambda kb: PM.evaluate_team(runs[kb[0]][0], runs[kb[0]][1], 876000 + 1000 * r + 50 * kb[1], thr), items, 'confirm')))
        for n in active:
            cur, cb, cands = plan[n]; kc = (C.key_s(cur), json.dumps(cb, sort_keys=True)); ok = []
            for x, vb in cands:
                m, se = C.pooled([(res[(kc, b)], res[((C.key_s(x[3]), json.dumps(vb, sort_keys=True)), b)]) for b in range(B)])
                print(f"  {n:16s} {show(x[1])}\n  {'':16s}   -> {show(x[2])}   +{x[4]} accurate, {100 * m:+.1f} ± {100 * se:.1f}{'   accepted' if m + Z * se >= 0 else ''}", flush=True)
                if m + Z * se >= 0: ok.append((x[4], m, se, x))
            if ok:
                d, m, se, x = max(ok, key=lambda o: (o[0], o[1]))
                state[n]['team'] = x[3]; state[n]['path'].append(dict(out=x[1], into=x[2], accurate_gain=d, diff=m, se=se))
                print(f"  {n}: CHANGE {x[1]} -> {x[2]} (+{d} accurate, {100 * m:+.1f} ± {100 * se:.1f})", flush=True)
            else: state[n]['done'] = True; print(f"  {n}: no change", flush=True)
        json.dump(state, open(OUT, 'w'), indent=1)
    final_check(state, T, B)
    json.dump(state, open(OUT, 'w'), indent=1)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'cells': cells_for({x[2] for t in teams_to_refine(sys.argv[2].split(',') if len(sys.argv) > 2 else None).values() for x in candidates(t)})
    elif cmd == 'run': run(int(sys.argv[2]) if len(sys.argv) > 2 else 4, sys.argv[3].split(',') if len(sys.argv) > 3 else None)
    elif cmd == 'final':                                               # only the final check, on a finished refinement's state
        state = json.load(open(OUT)); T = teams_to_refine(); T.update(teams_to_refine([n for n in state if n not in T]) if set(state) - set(T) else {})
        for n, s in state.items():                                     # the original, replayed through the accepted swaps, is the refined team
            t = list(T[n])
            for p in s['path']: t[t.index(p['out'])] = p['into']
            assert t == s['team'] and accurate(T[n]) == s['accurate0'], n
        cells_for({g for n, s in state.items() if s['path'] for g in T[n] + s['team']})
        final_check(state, T, int(sys.argv[2]) if len(sys.argv) > 2 else 4); json.dump(state, open(OUT, 'w'), indent=1)
