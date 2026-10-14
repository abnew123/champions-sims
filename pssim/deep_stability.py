"""Score deep_stability.sh: for each setting, how far its answer moves with the luck alone (two runs, EVAL_KEY_SALT 1 and 2: joint mixes'
total variation and how often a side's top joint option differs; the value's mean absolute change) and its log loss against the real
results (the two runs' average), with the paired difference against the setting without depth (SE clustered by game).
  ../.venv/bin/python3 deep_stability.py <scratch dir>"""
import os, sys, json, math, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(HERE, 'results', 'value')
def main(sp):
    meta = {}
    for part in ('hold', 'fit'):
        for l in open(os.path.join(R, f'real_{part}.meta.jsonl')): m = json.loads(l); meta[m['name']] = (m['y'], m['game'])
    ld = lambda f: {r['name']: r for r in map(json.loads, open(f)) if 'error' not in r and 'sides' in r} if os.path.exists(f) else {}
    tags = sorted({os.path.basename(f)[5:].rsplit('_s', 1)[0] for f in glob.glob(os.path.join(sp, 'stab_*_s1.eval.jsonl'))}, key=lambda t: (t != 'd0', t))
    runs = {t: (ld(os.path.join(sp, f'stab_{t}_s1.eval.jsonl')), ld(os.path.join(sp, f'stab_{t}_s2.eval.jsonl'))) for t in tags}
    common = set.intersection(*[set(a) & set(b) for a, b in runs.values()]) if runs else set()
    common = {k for k in common if k in meta}
    ll = lambda v, y: -math.log(min(1 - 1e-4, max(1e-4, v if y else 1 - v)))
    mix = lambda r, s: {j['label']: j['w'] for j in r['sides'][s]['joint']}
    tv = lambda p, q: 0.5 * sum(abs(p.get(k, 0) - q.get(k, 0)) for k in set(p) | set(q))
    def loss(t, k): a, b = runs[t]; y = meta[k][0]; return (ll(a[k]['value'], y) + ll(b[k]['value'], y)) / 2
    print(f"{len(common)} positions in every run")
    print(f"{'setting':8s} {'moves with luck: mixes':>22s} {'top differs':>12s} {'|dvalue|':>9s} {'log loss':>9s} {'vs no depth':>16s} {'deep rolls':>11s}")
    for t in tags:
        a, b = runs[t]; tvs = []; top = 0; dv = []; deep = []
        for k in common:
            for s in (0, 1):
                ma, mb = mix(a[k], s), mix(b[k], s); tvs.append(tv(ma, mb))
                if ma and mb and max(ma, key=ma.get) != max(mb, key=mb.get): top += 1
            dv.append(abs(a[k]['value'] - b[k]['value'])); deep.append(a[k].get('deep_rolls', 0))
        L = sum(loss(t, k) for k in common) / len(common)
        if t != 'd0' and 'd0' in runs:
            by = collections.defaultdict(list)
            for k in common: by[meta[k][1]].append(loss(t, k) - loss('d0', k))
            n = len(common); mu = sum(sum(v) for v in by.values()) / n
            se = math.sqrt(sum((sum(v) - mu * len(v)) ** 2 for v in by.values())) / n; vs = f"{mu:+.4f} +- {se:.4f}"
        else: vs = ''
        print(f"{t:8s} {sum(tvs) / len(tvs):22.3f} {top / (2 * len(common)):12.1%} {sum(dv) / len(dv):9.4f} {L:9.4f} {vs:>16s} {sorted(deep)[len(deep) // 2]:11d}")
if __name__ == '__main__': main(sys.argv[1])
