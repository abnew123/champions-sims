"""Score two evalpos runs of the same positions against the games' real results (deep_values.sh: the anytime search with and without
depth at the same budget). Log loss of side 0's value (no rescale: both runs are the same engine and net), the paired difference with a
standard error clustered by game, and how far the decisions moved: each side's joint mix (total variation) and how often its top joint
option changed. Positions named "<game> t<turn> p1[ <kind>]" (the value data's names; deep_endgames' starts add the endgame kind).
  ../.venv/bin/python3 deep_values.py <eval A> <eval B>"""
import os, sys, json, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(HERE, 'results', 'value')
def main(fa, fb):
    meta = {}
    for part in ('hold', 'fit', 'new'):
        f = os.path.join(R, f'real_{part}.meta.jsonl')
        if os.path.exists(f):
            for l in open(f): m = json.loads(l); meta[m['name']] = (m['y'], m['game'])
    ld = lambda f: {r['name']: r for r in map(json.loads, open(f)) if 'error' not in r and 'sides' in r}
    A, B = ld(fa), ld(fb)
    look = lambda k: meta.get(k) or meta.get(k.rsplit(' ', 1)[0])
    ll = lambda v, y: -math.log(min(1 - 1e-4, max(1e-4, v if y else 1 - v)))
    mix = lambda r, s: {j['label']: j['w'] for j in r['sides'][s]['joint']}
    tv = lambda p, q: 0.5 * sum(abs(p.get(k, 0) - q.get(k, 0)) for k in set(p) | set(q))
    by = collections.defaultdict(list); la = lb = 0.0; n = 0; tvs = []; top = 0; deep = []
    for k in A:
        if k not in B or not look(k): continue
        y, g = look(k); a, b = ll(A[k]['value'], y), ll(B[k]['value'], y)
        la += a; lb += b; n += 1; by[g].append(b - a)
        for s in (0, 1):
            ma, mb = mix(A[k], s), mix(B[k], s); tvs.append(tv(ma, mb))
            if ma and mb and max(ma, key=ma.get) != max(mb, key=mb.get): top += 1
        deep.append(B[k].get('deep_rolls', 0))
    if not n: print('nothing to compare'); return
    mu = (lb - la) / n
    se = math.sqrt(sum((sum(v) - mu * len(v)) ** 2 for v in by.values())) / n
    print(f"{n} positions from {len(by)} games: log loss {la / n:.4f} (A) -> {lb / n:.4f} (B), {mu:+.4f} +- {se:.4f}")
    print(f"  the decisions: mixes moved {sum(tvs) / len(tvs):.3f} (total variation, both sides); a side's top joint option changed in {top} of {2 * n}")
    if any(deep): print(f"  B's deep rolls a position: median {sorted(deep)[len(deep) // 2]}")
if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
