"""One swap on one start team, measured directly (user, 2026-10-06: Baltimore-06 with Incineroar over Arcanine-H): the climb's
neighbour for that swap (item clause handled as the climb does), each version's own bring search, the swap's brings held equal where
neither member is involved (refine.merge_brings), then BATCHES paired confirm batches on fresh pool entries. Pool opponents; the
setup comes from TS_SIM (v20m: misses doubled, v20g: normal).
  TS_SIM=v20m TS_PARALLEL=12 TS_THREADS=3 python3 swaptest.py <start> <gid out> <species in, or an exact grid id> [batches=6]
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['TS_OPP'] = 'pool'
import climb as C, evaluate as E, poolmode as PM
from refine import merge_brings, show
if __name__ == '__main__':
    start, out_g, into_sp = sys.argv[1:4]; B = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    team = C.INDEX[start]['gids']
    if into_sp in C.GRID:                                              # an exact set (e.g. one the user specified), not a swap candidate
        into_g = into_sp; i = team.index(out_g); var = team[:i] + [into_g] + team[i + 1:]; note = '(exact set)'; into_sp = C.GRID[into_g]['species']
        assert C.item(into_g) not in {C.item(g) for g in team if g != out_g} - {None}, 'item clause'
    else:
        nb = [x for x in C.neighbours(team) if x[1] == out_g and C.GRID[x[2]]['species'] == into_sp]
        assert len(nb) == 1, nb
        _, _, into_g, var, note = nb[0]
    print(time.strftime('%I:%M %p'), f"{E.sim()}: {start}, {show(out_g)} -> {show(into_g)} {note}", flush=True)
    os.environ['TS_BRING_K'] = '3'
    scr = E.search_many([team, var], 90000)
    bb = scr[0]['chosen']; vb = merge_brings(bb, scr[1]['chosen'], out_g, into_g)
    thr = int(os.environ.get('TS_THREADS', 3))
    items = [(t, b, 990000 + 50 * k) for k in range(B) for t, b in ((team, bb), (var, vb))]
    res = E.parallel(lambda x: PM.evaluate_team(x[0], x[1], x[2], thr), items, 'confirm')
    pairs = [(res[2 * k], res[2 * k + 1]) for k in range(B)]
    m, se = C.pooled(pairs)
    s0 = sum(p[0]['score'] for p in pairs) / B; s1 = sum(p[1]['score'] for p in pairs) / B
    _, SH = PM.keys()
    by = {g: sum(p[1]['by_arch'][g] - p[0]['by_arch'][g] for p in pairs) / B for g in SH}
    print(f"  {start}: {100 * s0:.1f}   with {C.GRID[into_g]['species']}: {100 * s1:.1f}   swap {100 * m:+.1f} ± {100 * se:.1f} ({B} batches x {len(pairs[0][0]['per_job'])} games)")
    print('  biggest swings by opponent group (share of meta): ' + '; '.join(f"{g[:40]} ({100 * SH[g]:.0f}%) {100 * by[g]:+.0f}"
                                                                         for g in sorted(by, key=lambda g: -abs(by[g]) * SH[g])[:5]))
    json.dump(dict(start=start, out=out_g, into=into_g, sim=E.sim(), base=s0, swapped=s1, diff=m, se=se, by_group=by),
              open(os.path.join(HERE, 'runs', f'swaptest_{start}_{into_g.replace("#", "_")}_{E.sim()}.json'), 'w'), indent=1)
