"""Which sixth member is strongest with the core the climb converged on? (user, 2026-10-06)
Core five, fixed: Mega Delphox (M-Delphox#1), Scarf Garchomp (Garchomp#1), Mega Charizard Y (M-Charizard Y#2), Sitrus Incineroar
(Incineroar#2) and Focus Sash Kingambit (Kingambit#3, so Life Orb stays free for Gholdengo under item clause). Sixth: Archaludon#3
(Leftovers), Gholdengo#2 (Life Orb) or Rillaboom#1 (Miracle Seed), the sets the climb chose. Each team gets the climb's bring search,
then BATCHES batches of fresh paired confirm games (54 jobs x 4 per batch; the same seeds for all three teams). Setup: cloud/run_env.sh's
(v16g + TS_PERISH=real when run after a climb); this script pins TS_SIM / TS_PERISH itself.
  TS_THREADS=90 python3 sixth.py [batches=8]
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.setdefault('TS_SIM', 'v16g'); os.environ.setdefault('TS_PERISH', 'real')
import evaluate as E, climb as C
CORE = ['M-Delphox#1', 'Garchomp#1', 'M-Charizard Y#2', 'Incineroar#2', 'Kingambit#3']
SIXTH = ['Archaludon#3', 'Gholdengo#2', 'Rillaboom#1']
BATCHES = int(sys.argv[1]) if len(sys.argv) > 1 else 8
if __name__ == '__main__':
    teams = [CORE + [s] for s in SIXTH]
    os.environ['TS_BRING_K'] = '3'
    scr = E.search_many(teams, 9000)                                           # the climb's bring search (seed 9000)
    brings = [r['chosen'] for r in scr]
    res = [E.evaluate_fixed(teams, brings, 4, 950000 + 50 * b) for b in range(BATCHES)]
    out = {}
    print(time.strftime('%I:%M %p'), f"{E.sim()}, {BATCHES} batches x {len(E.live_archs()) * E.P.K * 4} games per team")
    for i, s in enumerate(SIXTH):
        sc = sum(r[i]['score'] for r in res) / BATCHES
        by = {a: sum(r[i]['by_arch'][a] for r in res) / BATCHES for a in E.ARCHS}
        out[s] = dict(score=sc, by_arch=by, brings=brings[i])
        print(f"  {s:14s} {100 * sc:5.1f}   " + '  '.join(f"{a.split()[0][:8]} {100 * by[a]:4.1f}" for a in E.ARCHS))
    print('paired differences (pooled over batches, ± SE):')
    for i in range(3):
        for j in range(i + 1, 3):
            m, se = C.pooled([(r[i], r[j]) for r in res])
            print(f"  {SIXTH[j]} - {SIXTH[i]}: {100 * m:+.1f} ± {100 * se:.1f}")
            out[f'{SIXTH[j]} - {SIXTH[i]}'] = dict(diff=m, se=se)
    json.dump(out, open(os.path.join(HERE, 'runs', 'sixth_result.json'), 'w'), indent=1)
