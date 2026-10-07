"""Synergy sanity check (user, 2026-10-07): does the sim value a team's game plan, or does it prefer six individually strong Pokemon?
Real regional top-16 teams (and the user's Trick Room six, whose Indeedee-F the old climb swapped for Gholdengo) with a clear plan (Trick Room, Psychic Terrain, Tailwind, Rain, Sun, Sand, by the start index's rule
archetype) get their plan's enabler swapped for a strong generalist (the first 3 of GENERALISTS the team can take: no species clash,
item clause handled as the climb does). Control: the same generalist swap on a random non-enabler member, so a break is judged
against an ordinary swap, not against zero. Each version gets the climb's bring search; brings that involve neither the outgoing nor
the incoming member are held equal to the team's own (no bring luck); then BATCHES paired confirm batches on fresh pool entries.
If the sim often prefers the broken teams, or a break costs no more than the control, the evaluator undervalues synergy (Battle sim's
area); if breaks clearly hurt, the climb's one-swap search is the bigger problem (package swaps).
  TS_SIM=v20g TS_PARALLEL=60 TS_THREADS=3 python3 synergycheck.py plan        teams, enablers and variants; missing matrix cells
  NPROC=48 python3 synergycheck.py cells                                       compute the missing cells
  TS_SIM=v20g TS_PARALLEL=60 TS_THREADS=3 python3 synergycheck.py run [batches=4]
  TS_SYN_TEST=1: plumbing check (2 teams, 1 break + control, one entry per group)
"""
import json, os, sys, time, random, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['TS_OPP'] = 'pool'; os.environ.setdefault('TS_SIM', 'v20g')
TEST = os.environ.get('TS_SYN_TEST') == '1'
if TEST: os.environ.update(TS_POOL_ES='1', TS_POOL_EC='1')
import climb as C, evaluate as E, poolmode as PM, sets_lib as L
from refine import has_cells, show
G = C.GRID
GENERALISTS = ['Kingambit#1', 'Gholdengo#1', 'Garchomp#1', 'Incineroar#1', 'Rillaboom#1', 'Sneasler#1', 'Kingambit#2']
TR_FIRST = ('Indeedee-F', 'Indeedee', 'Farigiraf', 'Sinistcha', 'Hatterene')

def ability(g):
    """the battle ability: a Mega Stone holder's Mega ability"""
    it = L.DEX['items'].get(L.idf(G[g]['item'] or ''), {}) or {}
    ms = it.get('megaStone')
    if ms:
        sp = L.DEX['species'].get(L.idf(ms if isinstance(ms, str) else list(ms.values())[0]), {})
        return (sp.get('abilities') or {}).get('0')
    return G[g]['ability']

def enabler(team, arch):
    """(plan, the member that enables it) or None"""
    has = lambda pred: [g for g in team if pred(g)]
    if arch in ('Trick Room', 'Indeedee TR'):
        tr = sorted(has(lambda g: 'Trick Room' in G[g]['moves']), key=lambda g: (G[g]['species'] not in TR_FIRST, team.index(g)))
        if tr: return 'Trick Room', tr[0]
        ps = has(lambda g: ability(g) == 'Psychic Surge')
        return ('Psychic Terrain', ps[0]) if ps else None
    for a, plan, ab in (('Tailwind', 'Tailwind', None), ('Rain', 'Rain', 'Drizzle'), ('Sun', 'Sun', 'Drought'), ('Sand', 'Sand', 'Sand Stream')):
        if arch == a:
            x = has(lambda g: 'Tailwind' in G[g]['moves']) if ab is None else has(lambda g: ability(g) == ab)
            return (plan, x[0]) if x else None
    return None

def spe(g):
    """base Speed of the set's battle forme (a Mega Stone holder's Mega)"""
    return (L.DEX['species'].get(L.idf(C.forme(g)), {}) or L.DEX['species'][L.idf(G[g]['species'])])['stats']['spe']

def speed_note(team):
    """(average base Speed, members with base Speed <= 60): Battle sim's Trick Room credit is turns left x tanh(speed edge / 15) with
    the edge from the average Speed of each side's living Pokemon, so a half-slow team gets about half the credit"""
    v = [spe(g) for g in team]; return sum(v) / len(v), sum(1 for x in v if x <= 60)

def swap_to(team, out, into_sp):
    if G[out]['species'] == into_sp: return None                          # a different species, never another set of the same one
    nb = [x for x in C.neighbours(team) if x[1] == out and G[x[2]]['species'] == into_sp]
    return nb[0] if nb else None

def plan():
    """[(start, plan, enabler, [(kind, out, in gid, team)])]"""
    out = []
    for n, v in C.INDEX.items():
        if not (n == 'trick_room_six' or n.split('-')[-1].isdigit()): continue   # regional top-16 teams and the user's Trick Room six
        e = enabler(v['gids'], v.get('arch'))
        if not e: continue
        team = v['gids']; vs = []
        for g in GENERALISTS:
            x = swap_to(team, e[1], G[g]['species'])
            if x and all(y[2] != x[2] for y in vs): vs.append(('break', e[1], x[2], x[3]))
            if len(vs) == (1 if TEST else 3): break
        others = [g for g in team if g != e[1]]; rng = random.Random(n)
        for o in rng.sample(others, len(others)):
            x = next((swap_to(team, o, G[g]['species']) for g in GENERALISTS if swap_to(team, o, G[g]['species'])), None)
            if x: vs.append(('control', o, x[2], x[3])); break
        out.append((n, e[0], e[1], vs))
        if TEST and len(out) == 2: break
    return out

def run(B):
    P = plan(); _, SH = PM.keys()
    teams = list({C.key_s(t): t for n, p, e, vs in P for t in [C.INDEX[n]['gids']] + [v[3] for v in vs]}.values())
    miss = sorted({g for t in teams for g in t if not has_cells(g)})
    if miss: sys.exit(f"missing matrix cells: {miss}: run 'synergycheck.py cells' first")
    print(time.strftime('%I:%M %p'), f"{E.sim()}: {len(P)} teams, {sum(len(vs) for *_, vs in P)} variants, {len(teams)} teams to play, {B} batches", flush=True)
    os.environ['TS_BRING_K'] = '1' if TEST else '3'
    scr = dict(zip(map(C.key_s, teams), E.search_many(teams, 95000)))
    uses = lambda br, g: g in list(br[0]) + list(br[1])
    runs = {}
    for n, p, e, vs in P:
        base = C.INDEX[n]['gids']; bb = scr[C.key_s(base)]['chosen']; runs[(C.key_s(base), json.dumps(bb, sort_keys=True))] = (base, bb)
        for v in vs:
            vb = {k: (x if uses(x, v[2]) or uses(bb[k], v[1]) else bb[k]) for k, x in scr[C.key_s(v[3])]['chosen'].items()}
            runs[(C.key_s(v[3]), json.dumps(vb, sort_keys=True))] = (v[3], vb)
    keys = list(runs); thr = int(os.environ.get('TS_THREADS', 3))
    items = [(k, b) for b in range(B) for k in keys]
    res = dict(zip(items, E.parallel(lambda kb: PM.evaluate_team(runs[kb[0]][0], runs[kb[0]][1], 995000 + 50 * kb[1], thr), items, 'confirm')))
    out = []; agg = {'break': [], 'control': []}
    for n, p, e, vs in P:
        base = C.INDEX[n]['gids']; bb = scr[C.key_s(base)]['chosen']; kb = (C.key_s(base), json.dumps(bb, sort_keys=True))
        s0 = sum(res[(kb, b)]['score'] for b in range(B)) / B
        print(f"\n{n} ({p}; enabler {show(e)}): {100 * s0:.1f}")
        for kind, o, i, t in vs:
            vb = {k: (x if uses(x, i) or uses(bb[k], o) else bb[k]) for k, x in scr[C.key_s(t)]['chosen'].items()}
            kv = (C.key_s(t), json.dumps(vb, sort_keys=True))
            m, se = C.pooled([(res[(kb, b)], res[(kv, b)]) for b in range(B)])
            (a0, s0n), (a1, s1n) = speed_note(base), speed_note(t)
            agg[kind].append(m); out.append(dict(start=n, plan=p, kind=kind, out=o, into=i, diff=m, se=se, avg_spe=(a0, a1), slow=(s0n, s1n)))
            print(f"  {kind:7s} {o.split('#')[0]:12s} -> {i:14s} {100 * m:+5.1f} ± {100 * se:.1f}   avg base Speed {a0:.0f} -> {a1:.0f}, slow members {s0n} -> {s1n}"
                  f"{'   sim prefers the break' if kind == 'break' and m - 2 * se > 0 else ''}")
    mb = sum(agg['break']) / len(agg['break']); mc = sum(agg['control']) / max(1, len(agg['control']))
    nb = len(agg['break']); pos = sum(1 for r in out if r['kind'] == 'break' and r['diff'] > 0); sig = sum(1 for r in out if r['kind'] == 'break' and r['diff'] - 2 * r['se'] > 0)
    print(f"\nbreaking the plan: mean {100 * mb:+.1f} over {nb} swaps ({pos} positive, {sig} significantly); control swaps: mean {100 * mc:+.1f}")
    for p in sorted({r['plan'] for r in out}):
        xs = [r['diff'] for r in out if r['plan'] == p and r['kind'] == 'break']; cs = [r['diff'] for r in out if r['plan'] == p and r['kind'] == 'control']
        print(f"  {p:16s} breaks {100 * sum(xs) / len(xs):+5.1f} (n {len(xs)})   controls {100 * sum(cs) / max(1, len(cs)):+5.1f} (n {len(cs)})")
    tr = [r for r in out if r['plan'] == 'Trick Room' and r['kind'] == 'break']
    if len(tr) > 3:                                                    # Battle sim's check: does removing the setter cost less on fast teams?
        import numpy as np
        print(f"  Trick Room breaks: gain vs the team's own average base Speed, correlation {np.corrcoef([r['avg_spe'][0] for r in tr], [r['diff'] for r in tr])[0, 1]:+.2f} (n {len(tr)})")
    json.dump(out, open(os.path.join(HERE, 'runs', f'synergy_{E.sim()}.json'), 'w'), indent=1)

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'plan'
    if cmd == 'plan':
        P = plan(); miss = set()
        for n, p, e, vs in P:
            print(f"{n:16s} {p:16s} enabler {show(e)}")
            for kind, o, i, t in vs:
                print(f"    {kind:7s} {o:16s} -> {i}{'' if has_cells(i) else '   (no cells yet)'}"); miss |= {i} if not has_cells(i) else set()
        print(f"\n{len(P)} teams, {sum(len(vs) for *_, vs in P)} variants; {len(miss)} sets without cells")
    elif cmd == 'cells':
        miss = sorted({g for *_, vs in plan() for v in vs for g in v[3] if not has_cells(g)})
        print(f"{len(miss)} sets need cells", flush=True)
        for tr in ('0', '1'):
            if miss: subprocess.run([sys.executable, 'grid_pool.py'] + miss, cwd=os.path.join(HERE, 'mx'), check=True, env=dict(os.environ, TR=tr))
    elif cmd == 'run': run(int(sys.argv[2]) if len(sys.argv) > 2 else (1 if TEST else 4))
