# Stage-1 (1-seed) ranking of all 15 lead pairs per archetype, including the previously missing ones (results/miss1).
# Calibrates stage-1 against refined values for leads that have both, then picks missed leads worth a 12-seed refinement.
import json, glob, os, sys, collections, numpy as np
os.environ['EXCLUDE_MOVES'] = 'Make It Rain'
from analyze import solve
def key(r): return (r['arch'], '+'.join(sorted(r['myLead'])), r['pair'])
def load_dir(d):
    out = {}
    for fn in glob.glob(d + '/*.json'): r = json.load(open(fn)); out[key(r)] = r
    return out
s1 = {**load_dir('results/s1'), **load_dir('results/p1'), **load_dir('results/sal1')}
s1 = {k: v for k, v in s1.items() if not (k[0] == 'Perish trap' and v.get('F') and len(v['F'][0][0][0]) == 12)}
miss = load_dir('results/miss1')
allr = {**s1, **miss}
sol = {k: solve(r) for k, r in allr.items()}
val = collections.defaultdict(dict); ncell = collections.Counter()
by = collections.defaultdict(lambda: collections.defaultdict(list))
for k, s in sol.items(): by[k[0]][k[1]].append((allr[k]['share'], s['pop_m'], s['worst_m'])); ncell[(k[0], k[1])] += 1
for arch, leads in by.items():
    for lead, L in leads.items():
        w = np.array([x[0] for x in L]); p = np.array([x[1] for x in L]); q = np.array([x[2] for x in L])
        val[arch][lead] = ((w * p).sum() / w.sum(), (w * q).sum() / w.sum(), ncell[(arch, lead)])
# refined full-mix values (same metric as stage 1) from final4's merged 12-seed set
ref = {}
if '--noref' not in sys.argv:
    import final4 as F
    rv = collections.defaultdict(list)
    for (arch, lead, pair), (r, s) in F.res.items(): rv[(arch, '+'.join(sorted(lead.split('+'))))].append((r['share'], s['pop_m'], s['worst_m']))
    for kk, L in rv.items():
        w = np.array([x[0] for x in L]); ref[kk] = ((w * np.array([x[1] for x in L])).sum() / w.sum() + (w * np.array([x[2] for x in L])).sum() / w.sum()) / 2
missed = {(k[0], k[1]) for k in miss}
out = {}
for arch in sorted(val):
    rows = sorted(((v[0] + v[1]) / 2, l, v) for l, v in val[arch].items())[::-1]
    top = rows[0][0]
    print(f'\n## {arch}  (stage-1 top {top:.3f})')
    for b, l, v in rows:
        tag = 'NEW' if (arch, l) in missed else '   '
        r = ref.get((arch, l)); rs = f'refined {r:.3f} (s1-ref {b - r:+.3f})' if r is not None else ''
        print(f'  {tag} {l:24s} {b:.3f}  [{v[0]:.3f}/{v[1]:.3f}] cells {v[2]}  {rs}')
    out[arch] = {l: [b, v[0], v[1], (arch, l) in missed, ref.get((arch, l))] for b, l, v in rows}
json.dump(out, open('miss_rank.json', 'w'), indent=1)
d = [out[a][l][0] - out[a][l][4] for a in out for l in out[a] if out[a][l][4] is not None]
if d: print(f'\nstage-1 minus refined over {len(d)} leads: mean {np.mean(d):+.3f}, sd {np.std(d):.3f}, range {min(d):+.3f}..{max(d):+.3f}')
