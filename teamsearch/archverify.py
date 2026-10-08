"""After the per-archetype climb (user, 2026-10-08): replay each start's final team against the start itself on fresh opponents,
so the reported gains don't carry the climb's selection luck. Both teams get the climb's bring search (as configured: plan-aware), on
a seed the climb never used; then BATCHES paired confirm batches. Reports, per archetype, every start's start -> final with the
verified gain, and the best distinct final teams with their sets.
  . cloud/run_env_arch.sh && TS_PARALLEL=30 TS_THREADS=3 python3 archverify.py [batches=4]
"""
import json, os, sys, time, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import climb as C, evaluate as E, poolmode as PM
G = C.GRID
def show(g): s = G[g]; return f"{s['species']} @ {s['item'] or '-'} ({s['nature']}, {s['ability']}): {' / '.join(s['moves'])}"
if __name__ == '__main__':
    B = int(sys.argv[1]) if len(sys.argv) > 1 else 4; thr = int(os.environ.get('TS_THREADS', 3))
    st = json.load(open(C.STATE))
    pairs = {n: (C.INDEX[n]['gids'], t['team']) for n, t in st['teams'].items()}
    teams = list({C.key_s(x): x for a, b in pairs.values() for x in (a, b)}.values())
    print(time.strftime('%I:%M %p'), f"{E.sim()}: {len(pairs)} starts, {len(teams)} distinct teams, {B} batches", flush=True)
    scr = dict(zip(map(C.key_s, teams), E.search_many(teams, 98000)))
    items = [(C.key_s(t), b) for t in teams for b in range(B)]
    by_key = {C.key_s(t): t for t in teams}
    res = dict(zip(items, E.parallel(lambda x: PM.evaluate_team(by_key[x[0]], scr[x[0]]['chosen'], 998000 + 50 * x[1], thr), items, 'confirm')))
    score = {k: sum(res[(k, b)]['score'] for b in range(B)) / B for k in by_key}
    out = collections.defaultdict(list)
    for n, (a, b) in pairs.items():
        ka, kb = C.key_s(a), C.key_s(b)
        m, se = C.pooled([(res[(ka, i)], res[(kb, i)]) for i in range(B)]) if ka != kb else (0.0, 0.0)
        out[st['teams'][n].get('arch', C.arch_of(a))].append(dict(start=n, start_score=score[ka], final_score=score[kb], gain=m, se=se,
                                                                  swaps=[(p['out'], p['into']) for p in st['teams'][n]['path']], team=b))
    for a, rows in out.items():
        print(f"\n=== {a}")
        for r in sorted(rows, key=lambda r: -r['final_score']):
            sw = ', '.join(f"{o.split('#')[0]} -> {i.split('#')[0]}" for o, i in r['swaps']) or 'no swaps'
            print(f"  {r['start']:16s} start {100 * r['start_score']:5.1f} -> final {100 * r['final_score']:5.1f}   verified {100 * r['gain']:+5.1f} ± {100 * r['se']:.1f}   ({sw})")
        seen = []
        for r in sorted(rows, key=lambda r: -r['final_score']):
            sp = {G[g]['species'] for g in r['team']}
            if any(len(sp & s) >= 5 for s in seen): continue
            seen.append(sp)
            if len(seen) > 3: break
            print(f"  best #{len(seen)}: {r['start']} (final {100 * r['final_score']:.1f})")
            for g in r['team']: print(f"      {show(g)}")
    json.dump(out, open(os.path.join(HERE, 'runs', 'archverify.json'), 'w'), indent=1)
