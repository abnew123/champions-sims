"""Does a battle-tested shortlist close the gap to the sheet's picks? Trick Room six: per archetype, battle the outcome-fitted
model's top K choices (search seeds), keep each archetype's best, then re-test the kept picks on fresh seeds (unbiased).
  python3 search_check.py [K=4] [per_job=4]"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import evaluate as E
import compare_sheet as CS
P = E.P; team = CS.team; thr = int(os.environ.get('TS_THREADS', 11))
K = int(sys.argv[1]) if len(sys.argv) > 1 else 4; pj = int(sys.argv[2]) if len(sys.argv) > 2 else 4
R = {a: P.ranked_outcome(team, a)[:K] for a in P.ARCH_SHARE}
res = [E.run_team(team, pj, 4242, thr, fixed={a: R[a][i] for a in R}, label=f'search{i}') for i in range(K)]
best = {a: max(range(K), key=lambda i: res[i]['by_arch'][a]) for a in R}
chosen = {a: R[a][best[a]] for a in R}
print('search (selection-biased):', f"{100 * sum(P.ARCH_SHARE[a] * res[best[a]]['by_arch'][a] for a in R) / sum(P.ARCH_SHARE.values()):.1f}")
fresh = E.run_team(team, pj, 777, thr, fixed=chosen, label='search_kept')           # seed 777 = the sheet check's seeds
sb = json.load(open(os.path.join(HERE, 'sheet_battle.json')))
print(f"{'archetype':32s}    sheet   fitted   search  (kept choice rank)")
for a in P.ARCH_SHARE:
    print(f"{a:32s} {100 * sb['sheet']['by_arch'][a]:8.1f} {100 * sb['fitted']['by_arch'][a]:8.1f} {100 * fresh['by_arch'][a]:8.1f}   #{best[a] + 1}")
print(f"{'weighted':32s} {100 * sb['sheet']['score']:8.1f} {100 * sb['fitted']['score']:8.1f} {100 * fresh['score']:8.1f}")
json.dump(dict(K=K, per_job=pj, chosen={a: dict(lead=c[0], back=c[1], rank=best[a] + 1) for a, c in chosen.items()}, fresh_score=fresh['score'],
               fresh_by_arch=fresh['by_arch']), open(os.path.join(HERE, 'search_check.json'), 'w'), indent=1)
