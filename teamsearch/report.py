"""Climb report from climb_log.jsonl (+ climb_state.json): each start's path, the best teams by their latest confirm score
(fresh paired games: unbiased, but round-to-round seeds differ, so compare loosely), and which starts converge on similar sixes.
  python3 report.py [results dir = cloud_results]
"""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else 'cloud_results')
sys.path.insert(0, HERE)
import sets_lib as L
G = json.load(open(os.path.join(HERE, 'grid_sets.json')))
log = [json.loads(l) for l in open(os.path.join(D, 'climb_log.jsonl'))]
st = json.load(open(os.path.join(D, 'climb_state.json')))
sp = lambda g: G[g]['species'] + ('*' if (L.DEX['items'].get(L.idf(G[g]['item'] or ''), {}) or {}).get('megaStone') else '')
latest = {}                                   # start -> (round, final team, its confirm score, moved in that round)
for r in log:                                 # a move = the sequential test's verdict (older logs: the old gain > 1 SE rule)
    moved = r['verdict'] == 'move' if 'verdict' in r else r['best']['diff'] > r['best']['se']
    team = st['teams'][r['start']]['team']    # the state is authoritative (undecided swaps are not moves)
    latest[r['start']] = (r['round'], team, r['score_best'] if moved else r['score'], moved, r['score'] if r['round'] == 1 else None)
first = {r['start']: r['score'] for r in log if r['round'] == 1}
print(f"after round {st['round']}: {sum(1 for t in st['teams'].values() if not t['done'])} of {len(st['teams'])} starts still climbing\n")
print('best teams so far (latest confirm win share vs the archetype field; * = Mega Stone; ^ = just moved: that score is its first\n'
      'batch as the winning candidate, so it runs high; start score in round 1 for reference):')
for n, (rnd, team, sc, moved, _) in sorted(latest.items(), key=lambda kv: -kv[1][2])[:15]:
    path = ' → '.join(f"{p['out'].split('#')[0]}→{p['into'].split('#')[0]}" for p in st['teams'][n]['path']) or 'no swaps'
    print(f"  {100 * sc:5.1f}{'^' if moved else ' '} (start {100 * first[n]:5.1f})  {n:16s} {', '.join(sorted(sp(g) for g in team))}")
    print(f"         path: {path}{'' if st['teams'][n]['done'] else '  [still climbing]'}")
for n in ('trick_room_six', 'low_variance_six'):
    if n in latest:
        rnd, team, sc, moved, _ = latest[n]
        print(f"\n{n}: {100 * sc:.1f} ({'still climbing' if not st['teams'][n]['done'] else 'local max'}), "
              f"path: {' → '.join(p['out'] + '→' + p['into'] for p in st['teams'][n]['path']) or 'no swaps'}")
# convergence: starts whose current sixes share 5+ species
cur = {n: frozenset(G[g]['species'] for g in latest[n][1]) for n in latest}
groups = []
for n in sorted(cur, key=lambda n: -latest[n][2]):
    for g in groups:
        if len(cur[n] & cur[g[0]]) >= 5: g.append(n); break
    else: groups.append([n])
print('\nstarts now within one species of each other:')
for g in groups:
    if len(g) > 1: print(f"  {len(g)}: {', '.join(g)}  core {', '.join(sorted(set.intersection(*(set(cur[x]) for x in g))))}")
into = collections.Counter(p['into'].split('#')[0] for t in st['teams'].values() for p in t['path'])
outs = collections.Counter(p['out'].split('#')[0] for t in st['teams'].values() for p in t['path'])
print('\nmost added:', ', '.join(f'{k} {v}' for k, v in into.most_common(8)))
print('most removed:', ', '.join(f'{k} {v}' for k, v in outs.most_common(8)))
