"""The Trick Room six played with the TR sheet's own plans (sheets/trick-room-six/picks.json: a lead pair and back pair per opponent
core group), with and without its plan pieces (user / Battle sim, 2026-10-07: the synergy check's missing half). The sheet never brings
Indeedee-F, so the setter tested is Farigiraf (led vs 80% of the meta), plus Torkoal (brought vs 84%); control: Incineroar -> Gholdengo.
A swapped version keeps the sheet's plan: the incoming member takes the outgoing one's slot (lead slot included), so only the Pokemon
changes. Groups the sheet doesn't name use its pick for the same archetype ('other/X' -> 'Other X'). BATCHES paired confirm batches
on fresh pool entries (4 x 224 games per version), overall and per opponent group where the swapped member is in the plan.
  TS_SIM=v20g TS_PARALLEL=30 TS_THREADS=3 python3 trsix_sheet.py [batches=4]
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['TS_OPP'] = 'pool'; os.environ.setdefault('TS_SIM', 'v20g')
import climb as C, evaluate as E, poolmode as PM
G = C.GRID
VARIANTS = [('break', 'Farigiraf', 'Gholdengo#1'), ('break', 'Farigiraf', 'Garchomp#1'), ('break', 'Farigiraf', 'Rillaboom#1'),
            ('break', 'Torkoal', 'Gholdengo#1'), ('break', 'Torkoal', 'Garchomp#1'), ('control', 'Incineroar', 'Gholdengo#1')]

def sheet_plans(team):
    K, _ = PM.keys(); P = json.load(open(os.path.join(HERE, '..', 'sheets', 'trick-room-six', 'picks.json')))['picks']
    by_sp = {G[g]['species']: g for g in team}; out = {}
    for k in K:
        p = P.get(k) or P.get('Other ' + k.split('/', 1)[1] if k.startswith('other/') else '') \
            or next((v for kk, v in P.items() if kk.split(':')[0] == k.split('/')[-1]), None)       # e.g. other/Sand -> a 'Sand: ...' pick
        out[k] = ([by_sp[x] for x in p['lead']], [by_sp[x] for x in p['back']])
    return out

def swap(team, plans, out_sp, into):
    old = next(g for g in team if G[g]['species'] == out_sp)
    t = [into if g == old else g for g in team]
    items = [C.item(g) for g in t if C.item(g)]; assert len(items) == len(set(items)), 'item clause'
    return old, t, {k: ([into if g == old else g for g in l], [into if g == old else g for g in b]) for k, (l, b) in plans.items()}

if __name__ == '__main__':
    B = int(sys.argv[1]) if len(sys.argv) > 1 else 4; thr = int(os.environ.get('TS_THREADS', 3))
    team = C.INDEX['trick_room_six']['gids']; base = sheet_plans(team); _, SH = PM.keys()
    vs = [(kind, out_sp, into) + swap(team, base, out_sp, into) for kind, out_sp, into in VARIANTS]
    print(time.strftime('%I:%M %p'), f"{E.sim()}: trick_room_six with the sheet's plans, {len(vs)} variants, {B} batches", flush=True)
    items = [(team, base, b) for b in range(B)] + [(v[4], v[5], b) for v in vs for b in range(B)]
    res = E.parallel(lambda x: PM.evaluate_team(x[0], x[1], 996000 + 50 * x[2], thr), items, 'confirm')
    r0 = res[:B]; s0 = sum(r['score'] for r in r0) / B
    print(f"\ntrick_room_six, sheet plans: {100 * s0:.1f}")
    out = []
    for i, (kind, out_sp, into, old, t, plans) in enumerate(vs):
        rv = res[B * (i + 1): B * (i + 2)]
        m, se = C.pooled(list(zip(r0, rv)))
        used = [k for k in SH if old in base[k][0] + base[k][1]]
        led = sum(SH[k] for k in SH if old in base[k][0])
        by = {k: sum(b['by_arch'][k] - a['by_arch'][k] for a, b in zip(r0, rv)) / B for k in used}
        print(f"  {kind:7s} {out_sp:10s} -> {into:13s} {100 * m:+5.1f} ± {100 * se:.1f}   ({out_sp} brought vs {100 * sum(SH[k] for k in used):.0f}% of the meta, led vs {100 * led:.0f}%)")
        worst = sorted(by, key=lambda k: by[k])[:4]
        print('      biggest losses by group: ' + '; '.join(f"{k[:38]} ({100 * SH[k]:.0f}%) {100 * by[k]:+.0f}" for k in worst))
        out.append(dict(kind=kind, out=old, into=into, diff=m, se=se, by_group=by))
    json.dump(dict(base=s0, variants=out), open(os.path.join(HERE, 'runs', f'trsix_sheet_{E.sim()}.json'), 'w'), indent=1)
