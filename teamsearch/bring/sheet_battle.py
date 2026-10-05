"""Battle check of bring policies on the held-out Trick Room six: the sheet's picks (lead solver + 2v2 back rows) vs the
outcome-fitted heuristic vs the human-fitted heuristic, same 60 jobs and seeds for all three (paired).
  python3 sheet_battle.py [per_job=4]          (TS_THREADS, TS_PARALLEL as for evaluate.py)"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import evaluate as E
import compare_sheet as CS
P = E.P
team = CS.team; by_name = {v: k for k, v in CS.name.items()}
pj = int(sys.argv[1]) if len(sys.argv) > 1 else 4
S = CS.sheet_picks()
fixed = {'sheet': {a: ([by_name[x] for x in S[a][0][0]], [by_name[x] for x in S[a][0][1]]) for a in P.ARCH_SHARE},
         'human': {a: P.choose(team, a)[:2] for a in P.ARCH_SHARE},
         'fitted': {a: P.choose_outcome(team, a)[:2] for a in P.ARCH_SHARE} if os.path.exists(P.OUTCOME) else None}
res = {}
for lab, fx in fixed.items():
    if fx is None: continue
    res[lab] = E.run_team(team, pj, 777, int(os.environ.get('TS_THREADS', 13)), fixed=fx, label=f'check_{lab}')
base = res['sheet']
print(f"{'archetype':32s} " + ' '.join(f'{l:>8s}' for l in res))
for a in P.ARCH_SHARE: print(f'{a:32s} ' + ' '.join(f"{100 * r['by_arch'][a]:8.1f}" for r in res.values()))
print(f"{'weighted':32s} " + ' '.join(f"{100 * r['score']:8.1f}" for r in res.values()) + f"   ({base['games']} games each)")
for lab, r in res.items():
    if lab != 'sheet':
        import climb as C
        m, se = C.paired(base, r); print(f'{lab} - sheet: {100 * m:+.1f} (SE {100 * se:.1f})')
json.dump({l: dict(score=r['score'], by_arch=r['by_arch'], games=r['games']) for l, r in res.items()}, open(os.path.join(HERE, 'sheet_battle.json'), 'w'), indent=1)
