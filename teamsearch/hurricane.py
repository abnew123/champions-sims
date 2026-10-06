"""Would the finished climb's best teams do better with Solar Beam Charizard Y instead of Hurricane? (user, 2026-10-06)
The climb's only Charizard Y candidate was M-Charizard Y#2 (Timid, Heat Wave / Weather Ball / Hurricane / Protect), a set that at the
regionals ran only on dual-weather teams (build_sets.modal_set picks the nature first). M-Charizard Y#5 is the same Timid spread with
Solar Beam in place of Hurricane. Each team with #2 among the rerun's best, plus sixth.py's Archaludon team, is played as is and with
#5: each version gets the climb's bring search, then BATCHES batches of paired confirm games (54 jobs x 4 per batch, the same seeds for
both versions). Brisbane-01 is a real dual-weather team (Pelipper), a check where Hurricane should hold up.
Setup: the finished climb's (v16g, Perish from real data); this script pins TS_SIM / TS_PERISH itself.
  TS_PARALLEL=10 TS_THREADS=3 python3 hurricane.py [batches=6]
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['TS_SIM'] = 'v16g'; os.environ['TS_PERISH'] = 'real'; os.environ.pop('TS_OPP', None); os.environ.pop('TS_BATTLE_BIN', None)
import evaluate as E, climb as C
HUR, SB = 'M-Charizard Y#2', 'M-Charizard Y#5'
TEAMS = {   # the rerun's final teams (cloud_results/v12/climb_state.json) with the Hurricane set, best first
    'Frankfurt-04': ['Gholdengo#2', 'M-Delphox#1', 'Incineroar#2', 'Garchomp#1', HUR, 'Kingambit#3'],
    'Baltimore-12-final': ['Garchomp#1', 'Kingambit#1', 'Archaludon#3', 'M-Delphox#1', 'Incineroar#2', HUR],
    'Frankfurt-10': ['Garchomp#1', 'Incineroar#67', HUR, 'Archaludon#3', 'Kingambit#3', 'M-Delphox#1'],
    'Baltimore-08': ['Garchomp#1', 'Kingambit#1', 'Rillaboom#1', HUR, 'Incineroar#17', 'M-Delphox#1'],
    'Brisbane-01': ['Archaludon#1', 'Pelipper#1', 'Grimmsnarl#1', HUR, 'Garchomp#1', 'Venusaur#1'],
    'Baltimore-14': ['Klefki#2', 'Garchomp#1', 'Volcarona#2', 'Archaludon#1', 'M-Salamence#1', HUR],
    'sixth: core + Archaludon': ['M-Delphox#1', 'Garchomp#1', HUR, 'Incineroar#2', 'Kingambit#3', 'Archaludon#3'],
}
BATCHES = int(sys.argv[1]) if len(sys.argv) > 1 else 6
if __name__ == '__main__':
    names = list(TEAMS); teams = []
    for n in names: teams += [TEAMS[n], [SB if g == HUR else g for g in TEAMS[n]]]
    os.environ['TS_BRING_K'] = '3'
    print(time.strftime('%I:%M %p'), f"{E.sim()}, {len(names)} teams x 2 versions, {BATCHES} batches", flush=True)
    scr = E.search_many(teams, 9100)                                            # the climb's bring search
    fixed = [{a: tuple(v) for a, v in r['chosen'].items()} for r in scr]
    for i, t in enumerate(teams): E.prepare(t, fixed[i], f'hurr{i}')            # each folder once, before the parallel runs share it
    runs = [(i, b) for b in range(BATCHES) for i in range(len(teams))]         # one small process per (team, batch)
    flat = dict(zip(runs, E.parallel(lambda ib: E.run_team(teams[ib[0]], 4, 960000 + 50 * ib[1], int(os.environ.get('TS_THREADS', 3)),
                                                             fixed=fixed[ib[0]], label=f'hurr{ib[0]}'), runs, 'hurricane confirm')))
    out = {}; allpairs = []
    print(time.strftime('%I:%M %p'), f"{BATCHES} batches x {len(E.live_archs()) * E.P.K * 4} games per version; Solar Beam minus Hurricane:")
    for k, n in enumerate(names):
        i, j = 2 * k, 2 * k + 1
        pairs = [(flat[(i, b)], flat[(j, b)]) for b in range(BATCHES)]; allpairs += pairs
        m, se = C.pooled(pairs)
        si = sum(p[0]['score'] for p in pairs) / BATCHES; sj = sum(p[1]['score'] for p in pairs) / BATCHES
        by = {a: (sum(p[0]['by_arch'][a] for p in pairs) / BATCHES, sum(p[1]['by_arch'][a] for p in pairs) / BATCHES) for a in E.live_archs()}
        out[n] = dict(hurricane=si, solar_beam=sj, diff=m, se=se, by_arch=by, brings_hurricane=scr[i]['chosen'], brings_solar_beam=scr[j]['chosen'])
        big = sorted(by, key=lambda a: -abs(by[a][1] - by[a][0]))[:3]
        print(f"  {n:26s} Hurricane {100 * si:5.1f}  Solar Beam {100 * sj:5.1f}   {100 * m:+5.1f} ± {100 * se:.1f}   largest: "
              + ', '.join(f"{a.split(',')[0][:14]} {100 * (by[a][1] - by[a][0]):+.1f}" for a in big), flush=True)
    m, se = C.pooled(allpairs); out['all teams'] = dict(diff=m, se=se)
    print(f"  {'all teams pooled':26s} {100 * m:+5.1f} ± {100 * se:.1f}")
    json.dump(out, open(os.path.join(HERE, 'runs', 'hurricane_result.json'), 'w'), indent=1)
