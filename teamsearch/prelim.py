"""Preliminary look at a running climb round, from the bring-search result files (screening scores: best of 3 bring choices per
archetype, 6 games each, so selection-biased upward by about the same amount for every team; noisy, SE several points).
  python3 prelim.py [round=1]
"""
import json, os, sys, random, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
import climb as C
import evaluate as E
P = E.P
rnd = int(sys.argv[1]) if len(sys.argv) > 1 else 1
K = C.ROUND_CFG['thorough']['bring_k']; seed = 1000 * rnd
msc = json.load(open(os.path.join(HERE, f'climb_prefilter_r{rnd}.json')))
cfg = C.ROUND_CFG['thorough']

def screen(gids):
    d = os.path.join(HERE, 'runs', f'search{K}_{E.team_key(gids)}'); out = os.path.join(d, f'out_{seed}_1')
    if not os.path.isdir(out): return None
    jobs = json.load(open(os.path.join(d, 'jobs.json')))
    if len(os.listdir(out)) < len(jobs): return None
    by = {}
    for ai, a in enumerate(E.ARCHS):
        sh = P.pair_shares(a); best = None
        for c in range(K):
            num = den = 0.0
            for k in range(P.K):
                r = json.load(open(os.path.join(out, f'{(ai * K + c) * P.K + k}.json')))
                vs = [x['v'] for x in r['rows'] if not x.get('unsupported')]
                if vs: num += sh[k] * sum(vs) / len(vs); den += sh[k]
            v = num / den if den else 0
            if best is None or v > best[0]: best = (v, jobs[(ai * K + c) * P.K]['lead'], jobs[(ai * K + c) * P.K]['back'])
        by[a] = best
    return sum(P.ARCH_SHARE[a] * by[a][0] for a in by) / sum(P.ARCH_SHARE.values()), by

starts = {n: v['gids'] for n, v in C.INDEX.items()}
cur, gains, into, mat_pairs, rand_g, top_g = {}, [], collections.Counter(), [], [], []
for n, t in starts.items():
    nb = C.neighbours(t, None)
    ms = sorted(((msc[C.key_s(x[3])], x) for x in nb), key=lambda z: -z[0])
    rng = random.Random(f'{n}|{rnd}'); rest = [x for _, x in ms[cfg['prefilter']:]]
    top = [x for _, x in ms[:cfg['prefilter']]]; rnd_x = rng.sample(rest, min(cfg['random_extra'], len(rest)))
    s0 = screen(t)
    if C.key_s(t) not in msc: msc[C.key_s(t)] = P.matrix_score(t)
    if s0: cur[n] = s0
    for x in top + rnd_x:
        s = screen(x[3])
        if s and s0:
            g = s[0] - s0[0]; gains.append((g, n, x[1], x[2])); mat_pairs.append((msc[C.key_s(x[3])] - msc[C.key_s(t)], g))
            (rand_g if x in rnd_x else top_g).append(g)
            if g > 0.05: into[x[2].split('#')[0]] += 1

print(f'screened: {len(cur)} of {len(starts)} start teams, {len(gains)} swaps with both sides done\n')
print('start teams by screening score (win share vs the ladder field, best-of-3 brings):')
for n, (s, by) in sorted(cur.items(), key=lambda z: -z[1][0])[:12]:
    sp = ', '.join(sorted(E.G[g]['species'] for g in starts[n]))
    print(f'  {100 * s:5.1f}  {n:16s} {C.INDEX[n]["arch"]:12s} {sp}')
print('  ...')
for n, (s, by) in sorted(cur.items(), key=lambda z: -z[1][0])[-3:]:
    print(f'  {100 * s:5.1f}  {n:16s} {C.INDEX[n]["arch"]}')
print('\nbiggest screened gains (screen-vs-screen, noisy; confirm stage decides):')
for g, n, o, i in sorted(gains, reverse=True)[:12]: print(f'  {100 * g:+5.1f}  {n:16s} {o:>18s} -> {i}')
print('\nspecies most often in a swap screened +5 or better:', ', '.join(f'{s} {c}' for s, c in into.most_common(10)))
if mat_pairs:
    a = np.array(mat_pairs); print(f'\npre-filter check: corr(matrix gain, screened gain) = {np.corrcoef(a[:, 0], a[:, 1])[0, 1]:+.2f} over {len(a)} swaps; '
                                   f'mean screened gain of pre-filtered top-10 {100 * np.mean(top_g):+.1f} vs random swaps {100 * np.mean(rand_g):+.1f} ({len(rand_g)})')
