"""Type-preserving pair swaps, probed on the per-archetype climb's final teams (user, 2026-10-08): two members (types A/B and C/D) are
replaced by two newcomers whose types together are exactly the same set (e.g. A/C + B/D), the case single swaps can't reach when the
team needs all four types and no other A/B or C/D Pokemon is good enough. Newcomers come from the climb's swap pool (or, with
TS_PAIR_POOL=wide, every battle forme on >= 1% of regional teams); TS_PAIR_RULE=superset allows extra types (each newcomer carries one
of the old pair's types). Each pair must keep the archetype, the item clause and <= 2 Mega Stones. Every candidate is played against
its team: the configured bring search for both, brings held equal where none of the four members is involved, BATCHES paired confirm
batches. A probe: nothing is accepted; it reports every swap's gain.
  . cloud/run_env_arch.sh && TS_PARALLEL=30 TS_THREADS=3 python3 pairprobe.py [batches=4]       (python3 pairprobe.py list: no battles)
"""
import json, os, sys, time, itertools, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import climb as C, evaluate as E, poolmode as PM, sets_lib as L
G = C.GRID
RULE = os.environ.get('TS_PAIR_RULE', 'exact'); POOLK = os.environ.get('TS_PAIR_POOL', 'swap')

def types(g): return frozenset((L.DEX['species'].get(L.idf(C.forme(g))) or L.DEX['species'][L.idf(G[g]['species'])])['types'])

def pool():
    if POOLK != 'wide': return list(C.CANDS)
    n = len(json.load(open(os.path.join(L.ROOT, 'regionals', 'regional_teams.json')))); use = collections.Counter(); best = {}
    for g, s in G.items():
        if g.startswith('smogon:'): continue
        f = C.forme(g); use[f] += s.get('regional_count') or 0
        if f not in best or (s.get('regional_count') or 0) > (G[best[f]].get('regional_count') or 0): best[f] = g
    return [best[f] for f in best if use[f] >= 0.01 * n]

def pair_swaps(team, arch, cands):
    out = []
    for i, j in itertools.combinations(range(6), 2):
        U = types(team[i]) | types(team[j]); rest = [g for k, g in enumerate(team) if k not in (i, j)]
        rest_sp = {C.base(g) for g in rest}; rest_items = {C.item(g) for g in rest} - {None}; gone = {C.base(team[i]), C.base(team[j])}
        ok = [c for c in cands if C.base(c) not in rest_sp | gone and C.item(c) not in rest_items and (RULE == 'superset' or types(c) <= U)]
        for a, b in itertools.combinations(ok, 2):
            tu = types(a) | types(b)
            if C.base(a) == C.base(b) or (C.item(a) and C.item(a) == C.item(b)): continue
            if RULE == 'exact' and tu != U: continue
            if RULE == 'superset' and not (U <= tu and U & types(a) and U & types(b)): continue
            new = rest + [a, b]
            if C.megas(new) > 2 or C.arch_of(new) != arch: continue
            out.append((team[i], team[j], a, b, new))
    return out

def tstr(g): return f"{G[g]['species']}{'*' if C.is_mega(g) else ''} ({'/'.join(sorted(types(g)))})"

if __name__ == '__main__':
    st = json.load(open(C.STATE))['teams']; cands = pool()
    P = [(n, t, ps) for n, t in st.items() for ps in [pair_swaps(t['team'], t['arch'], cands)] if ps]
    print(time.strftime('%I:%M %p'), f"{E.sim()}: rule {RULE}, pool {POOLK} ({len(cands)} sets): {sum(len(ps) for *_, ps in P)} pair swaps on {len(P)} teams", flush=True)
    for n, t, ps in P:
        for o1, o2, a, b, _ in ps: print(f"  {n:16s} {tstr(o1)} + {tstr(o2)} -> {tstr(a)} + {tstr(b)}")
    if sys.argv[1:2] == ['list']: sys.exit()
    B = int(sys.argv[1]) if len(sys.argv) > 1 else 4; thr = int(os.environ.get('TS_THREADS', 3))
    teams = list({C.key_s(x): x for n, t, ps in P for x in [t['team']] + [p[4] for p in ps]}.values())
    scr = dict(zip(map(C.key_s, teams), E.search_many(teams, 81000)))
    uses = lambda br, gs: any(g in list(br[0]) + list(br[1]) for g in gs)
    runs = {}; plan = []
    for n, t, ps in P:
        cb = scr[C.key_s(t['team'])]['chosen']; kb = (C.key_s(t['team']), json.dumps(cb, sort_keys=True)); runs[kb] = (t['team'], cb)
        for p in ps:
            vb = {k: (v if uses(v, p[2:4]) or uses(cb[k], p[0:2]) else cb[k]) for k, v in scr[C.key_s(p[4])]['chosen'].items()}
            kv = (C.key_s(p[4]), json.dumps(vb, sort_keys=True)); runs[kv] = (p[4], vb); plan.append((n, p, kb, kv))
    items = [(k, b) for k in runs for b in range(B)]
    res = dict(zip(items, E.parallel(lambda kb: PM.evaluate_team(runs[kb[0]][0], runs[kb[0]][1], 881000 + 50 * kb[1], thr), items, 'confirm')))
    out = []
    print(f"\npair swaps, gain over the team ({B} paired batches):")
    for n, p, kb, kv in sorted(plan, key=lambda x: x[0]):
        m, se = C.pooled([(res[(kb, b)], res[(kv, b)]) for b in range(B)])
        print(f"  {n:16s} {tstr(p[0])} + {tstr(p[1])} -> {tstr(p[2])} + {tstr(p[3])}   {100 * m:+5.1f} ± {100 * se:.1f}", flush=True)
        out.append(dict(team=n, out=p[:2], into=p[2:4], diff=m, se=se))
    json.dump(out, open(os.path.join(HERE, 'runs', f'pairprobe_{RULE}_{POOLK}.json'), 'w'), indent=1)
