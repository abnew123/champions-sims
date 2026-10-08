"""Does the plan-aware bring step (bringplan.py, TS_BRING_MODE=plan) choose better brings than the climb's old one? (user, 2026-10-07)
For the synergy check's 30 real teams plus the user's Trick Room six: each team's brings from the old search (outcome model top 3 x 2
games) and from the plan-aware search (seed 97000 for both, so the same screening entries), then BATCHES paired confirm batches with
each team's two bring sets on the same fresh entries. Better brings mean a higher confirm score; the gain plan - old per team, overall
and by plan; which shortlist source the chosen brings came from; and the Trick Room six against the TR sheet's own plans on the same
confirm entries (the sheet's plans scored 70.3 on another seed set, the old search 61.9).
  TS_SIM=v20g TS_PARALLEL=30 TS_THREADS=3 python3 bringcheck.py [batches=4]
"""
import json, os, sys, time, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['TS_OPP'] = 'pool'; os.environ.setdefault('TS_SIM', 'v20g')
import climb as C, evaluate as E, poolmode as PM
import synergycheck as SC, trsix_sheet as TS
if __name__ == '__main__':
    B = int(sys.argv[1]) if len(sys.argv) > 1 else 4; thr = int(os.environ.get('TS_THREADS', 3))
    P = SC.plan(); names = [n for n, *_ in P]; plan_of = {n: p for n, p, *_ in P}
    teams = {n: C.INDEX[n]['gids'] for n in names}
    print(time.strftime('%I:%M %p'), f"{E.sim()}: {len(teams)} teams, old vs plan-aware bring search, {B} confirm batches", flush=True)
    os.environ['TS_BRING_K'] = '3'; os.environ.pop('TS_BRING_MODE', None)
    old = dict(zip(names, E.search_many(list(teams.values()), 97000)))
    os.environ['TS_BRING_MODE'] = 'plan'
    new = dict(zip(names, E.search_many(list(teams.values()), 97000)))
    os.environ.pop('TS_BRING_MODE', None)
    sheet = TS.sheet_plans(teams['trick_room_six']) if 'trick_room_six' in teams else None
    items = [(n, lab, b) for n in names for lab in ('old', 'plan') for b in range(B)] + ([('trick_room_six', 'sheet', b) for b in range(B)] if sheet else [])
    brings = lambda n, lab: sheet if lab == 'sheet' else (old if lab == 'old' else new)[n]['chosen']
    res = dict(zip(items, E.parallel(lambda x: PM.evaluate_team(teams[x[0]], brings(x[0], x[1]), 997000 + 50 * x[2], thr), items, 'confirm')))
    out = []; by = collections.defaultdict(list); tags = collections.Counter(); _, SH = PM.keys()
    for n in names:
        m, se = C.pooled([(res[(n, 'old', b)], res[(n, 'plan', b)]) for b in range(B)])
        s0 = sum(res[(n, 'old', b)]['score'] for b in range(B)) / B; s1 = sum(res[(n, 'plan', b)]['score'] for b in range(B)) / B
        same = sum(SH[k] for k in SH if [sorted(x) for x in old[n]['chosen'][k]] == [sorted(x) for x in new[n]['chosen'][k]])
        for k, t in new[n]['tag'].items(): tags[t.split(' (')[0]] += SH[k] / len(names)
        print(f"  {n:16s} {plan_of[n]:16s} old {100 * s0:5.1f}  plan {100 * s1:5.1f}  gain {100 * m:+5.1f} ± {100 * se:.1f}   same brings vs {100 * same:.0f}% of the meta")
        out.append(dict(team=n, plan=plan_of[n], old=s0, new=s1, diff=m, se=se)); by[plan_of[n]].append(m)
    g = [r['diff'] for r in out]
    print(f"\nplan-aware minus old: mean {100 * sum(g) / len(g):+.1f} over {len(g)} teams ({sum(1 for x in g if x > 0)} better, "
          f"{sum(1 for r in out if r['diff'] - 2 * r['se'] > 0)} significantly; {sum(1 for r in out if r['diff'] + 2 * r['se'] < 0)} significantly worse)")
    for p, xs in sorted(by.items()): print(f"  {p:16s} {100 * sum(xs) / len(xs):+5.1f} (n {len(xs)})")
    print('chosen brings came from (meta-weighted share): ' + ', '.join(f"{t} {100 * w:.0f}%" for t, w in tags.most_common()))
    if sheet:
        s = sum(res[('trick_room_six', 'sheet', b)]['score'] for b in range(B)) / B
        for lab in ('old', 'plan'):
            m, se = C.pooled([(res[('trick_room_six', 'sheet', b)], res[('trick_room_six', lab, b)]) for b in range(B)])
            print(f"trick_room_six: {lab} brings minus the sheet's plans {100 * m:+.1f} ± {100 * se:.1f} (sheet {100 * s:.1f})")
    json.dump(out, open(os.path.join(HERE, 'runs', f'bringcheck_{E.sim()}.json'), 'w'), indent=1)
