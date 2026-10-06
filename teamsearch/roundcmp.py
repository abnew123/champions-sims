"""Compare one round of two climbs from the same starts (user, 2026-10-06: does the pool-based control's round 1 look like the
finished archetype-model climb's round 1? If so, only the miss climb continues). Per start: each climb's verdict and best swap.
Summary: verdict agreement, same swap / same set in / same species in, the sets most often brought in, and how the starts rank
(Spearman of their scores: the two climbs score on different footings, so ranks rather than levels).
  python3 roundcmp.py [A dir = cloud_results/v12] [A prefix = climb] [B dir = cloud_results/pool] [B prefix = climb_pool] [round = 1]
"""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sp = lambda g: g.split('#')[0]

def rows(d, prefix, rnd):
    out = {}
    for line in open(os.path.join(HERE, d, f'{prefix}_log.jsonl')):
        x = json.loads(line)
        if x['round'] == rnd:
            if 'verdict' not in x:                     # the first AWS climb's log: it moved when the best swap's diff beat its SE
                b = x.get('best'); x['verdict'] = 'move' if x.get('moved', b and b['diff'] > b.get('se', 0)) else 'stop'
            out[x['start']] = x
    return out

def spearman(a, b):
    rk = lambda v: {k: i for i, k in enumerate(sorted(v, key=v.get))}
    ra, rb = rk(a), rk(b); n = len(a)
    return 1 - 6 * sum((ra[k] - rb[k]) ** 2 for k in a) / (n * (n * n - 1)) if n > 2 else float('nan')

if __name__ == '__main__':
    a = sys.argv[1:] + [None] * 5
    A = rows(a[0] or os.path.join('cloud_results', 'v12'), a[1] or 'climb', int(a[4] or 1))
    B = rows(a[2] or os.path.join('cloud_results', 'pool'), a[3] or 'climb_pool', int(a[4] or 1))
    common = sorted(set(A) & set(B))
    print(f"{len(common)} starts in both (A {len(A)}, B {len(B)})\n")
    print(f"{'start':24s} {'A verdict':10s} {'A swap':40s} {'B verdict':10s} {'B swap':40s}")
    same = collections.Counter(); ina = collections.Counter(); inb = collections.Counter()
    for s in common:
        x, y = A[s], B[s]; bx, by = x.get('best') or {}, y.get('best') or {}
        fx = f"{bx.get('out', '-')} -> {bx.get('into', '-')}" if x['verdict'] == 'move' else '-'
        fy = f"{by.get('out', '-')} -> {by.get('into', '-')}" if y['verdict'] == 'move' else '-'
        mark = ''
        if x['verdict'] == y['verdict']: same['verdict'] += 1
        if x['verdict'] == 'move': ina[bx['into']] += 1
        if y['verdict'] == 'move': inb[by['into']] += 1
        if x['verdict'] == 'move' and y['verdict'] == 'move':
            same['both move'] += 1
            if bx['into'] == by['into']: same['same set in'] += 1; mark = '  same in'
            if sp(bx['into']) == sp(by['into']): same['same species in'] += 1
            if bx['into'] == by['into'] and bx['out'] == by['out']: same['same swap'] += 1; mark = '  same swap'
        print(f"{s:24s} {x['verdict']:10s} {fx:40s} {y['verdict']:10s} {fy:40s}{mark}")
    n = len(common)
    print(f"\nverdict agrees: {same['verdict']}/{n}. Both moved: {same['both move']}; of those, same swap {same['same swap']}, "
          f"same set in {same['same set in']}, same species in {same['same species in']}")
    print(f"moves: A {sum(ina.values())}, B {sum(inb.values())}")
    print("sets brought in most often:  A: " + ', '.join(f'{k} {v}' for k, v in ina.most_common(8)))
    print("                             B: " + ', '.join(f'{k} {v}' for k, v in inb.most_common(8)))
    print(f"start ranking, Spearman of round scores: {spearman({s: A[s]['score'] for s in common}, {s: B[s]['score'] for s in common}):.2f}"
          f";  of best-neighbour scores: {spearman({s: A[s]['score_best'] for s in common}, {s: B[s]['score_best'] for s in common}):.2f}")
