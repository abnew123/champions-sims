"""Spread study, 2v2 part: one changed spread vs the current team on the same jobs and seeds (results/sp_base vs results/sp_<tag>).
Win share difference (changed - current), paired by job and game, for Trick Room up (K>0, 2-4 turns left) and not up (K=0).
Archetypes weighted by ladder share, their pairs by replay likelihood (w), my pairs that include the changed Pokemon equally.
usage: python3 sp_compare.py <tag> [<tag> ...]"""
import json, glob, sys, math, collections
SHARE = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
         'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
base = {int(f.split('/')[-1][:-5]): json.load(open(f)) for f in glob.glob('results/sp_base/*.json')}
def agg(items):
    """items: (weight, base games, variant games) -> weighted base win share, diff, SE of diff, games flipped"""
    W = sum(w for w, _, _ in items); b = sum(w * sum(x) / len(x) for w, x, _ in items) / W
    d = sum(w * (sum(y) - sum(x)) / len(x) for w, x, y in items) / W; var = 0.0; flips = [0, 0]
    for w, x, y in items:
        g = [yi - xi for xi, yi in zip(x, y)]; m = sum(g) / len(g)
        var += (w / W) ** 2 * sum((gi - m) ** 2 for gi in g) / max(1, len(g) - 1) / len(g)
        flips[0] += sum(1 for gi in g if gi > 0); flips[1] += sum(1 for gi in g if gi < 0)
    return b, d, math.sqrt(var), flips
for tag in sys.argv[1:]:
    var = {int(f.split('/')[-1][:-5]): json.load(open(f)) for f in glob.glob(f'results/sp_{tag}/*.json')}
    by = collections.defaultdict(list)          # (tr, arch, pair) -> [(w, base vs, variant vs)]
    for i, r in var.items():
        b = base.get(i)
        if not b or r['v'] is None or b['v'] is None: continue
        by[(r['K'] > 0, r['arch'], '+'.join(r['mine']))].append((r['w'], b['vs'], r['vs']))
    pairs = sorted({k[2] for k in by}); print(f'\n=== {tag}: {len(var)} jobs, pairs {", ".join(pairs)}')
    for tr in (True, False):
        items = [(SHARE[a] / len(pairs) * w, x, y) for (t, a, p), L in by.items() if t == tr for w, x, y in L]
        if not items: continue
        b, d, se, fl = agg(items)
        print(f"  Trick Room {'up  ' if tr else 'down'}: current {100*b:5.1f}%, change {100*d:+5.2f} ± {100*se:.2f}  (games won {fl[0]}, lost {fl[1]})")
        for p in pairs:
            b, d, se, fl = agg([(SHARE[a] * w, x, y) for (t, a, q), L in by.items() if t == tr and q == p for w, x, y in L])
            print(f"      {p:24s} {100*b:5.1f}% {100*d:+6.2f} ± {100*se:.2f}  (+{fl[0]} / -{fl[1]})")
        arch = []
        for a in SHARE:
            L = [(w, x, y) for (t, aa, q), LL in by.items() if t == tr and aa == a for w, x, y in LL]
            if L: b, d, se, fl = agg(L); arch.append((d, a, se))
        arch.sort(); print('      by archetype: ' + ', '.join(f'{a.split(" ")[0]} {100*d:+.1f}' for d, a, se in arch))
