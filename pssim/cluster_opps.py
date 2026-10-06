"""Opponent clusters (2026-10-06): group real sixes by what they contain instead of the name-based archetype rules (pro_replays.arch), for
the sim's opponent pool. Sixes come from the Reg M-C regionals (teamsearch/regmatch/*.json: standings with team sheets; git-ignored)
and the public ladder (teamsearch/bring/previews.json: Bo3 team previews; git-ignored); only species-level results are written.
Distance = 1 - Jaccard(six, six) on normalised species (Mega formes folded into the base, Indeedee-F kept apart). Weighted k-medoids
(unique sixes weighted by how often they occur; k-means++ seeding, several restarts) for a range of k, with per k: total cost, mean
within-cluster Jaccard (weighted), silhouette, smallest / largest cluster, share of the corpus in clusters with at least MIN members,
and stability (two random halves clustered separately, every six assigned to its nearest medoid, adjusted Rand index between them).
  ../.venv/bin/python3 cluster_opps.py scan [kmin=4] [kmax=40]        -> results/cluster_scan.txt (+ .json)
  ../.venv/bin/python3 cluster_opps.py show <k>                        -> results/clusters_k<k>.txt / .json: each cluster's medoid,
                                                                          size in each corpus, core species (share of members), rule
                                                                          archetype composition, and the nearest named archetype
env: CORPUS=regional|ladder|both (default both; the clustering is done on the union so cluster ids are shared, frequencies per corpus)
     SEED=<int>  RESTARTS=<n, default 6>  IDF=1 (weighted Jaccard: species weighted by log(teams / teams containing them))"""
import json, os, sys, collections, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pro_replays import arch
HERE = os.path.dirname(os.path.abspath(__file__)); TS = os.path.join(HERE, '..', 'teamsearch')
FORM = {'Indeedee [Female]': 'Indeedee-F', 'Indeedee [Male]': 'Indeedee', 'Ninetales [Alolan Form]': 'Ninetales-Alola'}
def norm(s):
    s = FORM.get(s, s.split(' [')[0]); s = s.split('-Mega')[0]
    return {'Floette-Eternal': 'Floette', 'Floette-Mega': 'Floette'}.get(s, s)
def load():
    """(frozenset six, corpus) for every team: regional sheets (one per player) and ladder previews (one per player per game)"""
    out = []
    for f in ('f192.json', 'f193.json', 'f194.json'):
        for p in json.load(open(os.path.join(TS, 'regmatch', f))):
            dl = p.get('decklist') or []
            if len(dl) == 6: out.append((frozenset(norm(m['name']) for m in dl), 'regional'))
    for g in json.load(open(os.path.join(TS, 'bring', 'previews.json')))['games']:
        for s in ('p1', 'p2'):
            six = g[s].get('six') or []
            if len(six) == 6: out.append((frozenset(norm(x) for x in six), 'ladder'))
    return out
def corpus(which):
    rows = load()
    if which != 'both': rows = [r for r in rows if r[1] == which]
    cnt = collections.Counter(); per = collections.defaultdict(collections.Counter)
    for six, c in rows: cnt[six] += 1; per[six][c] += 1
    U = list(cnt); w = np.array([cnt[s] for s in U], float)
    n = len(U); D = np.zeros((n, n), np.float32)
    sets = [set(s) for s in U]
    # IDF=1: weighted Jaccard, each species weighted by log(teams / teams containing it), so staples count less than distinctive cores
    sw = collections.Counter()
    for six, c in rows:
        for x in six: sw[x] += 1
    idf = {x: math.log(len(rows) / c) for x, c in sw.items()} if os.environ.get('IDF') else {x: 1.0 for x in sw}
    tw = [sum(idf[x] for x in s) for s in sets]
    for i in range(n):
        a = sets[i]
        for j in range(i + 1, n):
            inter = sum(idf[x] for x in a & sets[j]); D[i, j] = D[j, i] = 1.0 - inter / (tw[i] + tw[j] - inter)
    return U, w, D, per, len(rows)
def kmedoids(D, w, k, rng, restarts=6, iters=50):
    n = len(w); best = None
    for _ in range(restarts):
        # k-means++ style seeding on weighted distances
        med = [rng.choice(n, p=w / w.sum())]
        for _ in range(1, k):
            d = D[:, med].min(1) ** 2 * w; d[med] = 0
            med.append(rng.choice(n, p=d / d.sum()) if d.sum() > 0 else rng.choice(n))
        med = np.array(med)
        for _ in range(iters):
            lab = D[:, med].argmin(1)
            new = med.copy()
            for c in range(k):
                idx = np.where(lab == c)[0]
                if len(idx) == 0: continue
                sub = D[np.ix_(idx, idx)] * w[idx][None, :]
                new[c] = idx[sub.sum(1).argmin()]
            if (new == med).all(): break
            med = new
        lab = D[:, med].argmin(1); cost = (D[np.arange(n), med[lab]] * w).sum()
        if best is None or cost < best[0]: best = (cost, med, lab)
    return best
def silhouette(D, w, lab, k):
    n = len(w); s = np.zeros(n)
    for i in range(n):
        own = lab == i * 0 + lab[i]; own[i] = False
        a = (D[i, own] * w[own]).sum() / max(w[own].sum(), 1e-9) if own.any() else 0.0
        b = min(((D[i, lab == c] * w[lab == c]).sum() / w[lab == c].sum()) for c in range(k) if c != lab[i] and (lab == c).any())
        s[i] = (b - a) / max(a, b, 1e-9)
    return float((s * w).sum() / w.sum())
def ari(a, b, w):
    """adjusted Rand index between two labellings of weighted points (weights expanded as counts)"""
    a = np.repeat(a, w.astype(int)); b = np.repeat(b, w.astype(int))
    ct = collections.Counter(zip(a, b)); ra = collections.Counter(a); cb = collections.Counter(b); n = len(a)
    comb = lambda x: x * (x - 1) / 2
    idx = sum(comb(v) for v in ct.values()); ea = sum(comb(v) for v in ra.values()); eb = sum(comb(v) for v in cb.values())
    exp = ea * eb / comb(n); mx = (ea + eb) / 2
    return float((idx - exp) / (mx - exp)) if mx != exp else 1.0
MIN = 40
def scan(kmin, kmax):
    which = os.environ.get('CORPUS', 'both'); seed = int(os.environ.get('SEED', '0')); rs = int(os.environ.get('RESTARTS', '6'))
    U, w, D, per, N = corpus(which); n = len(U); rng = np.random.default_rng(seed)
    print(f"{which}: {N} teams, {n} distinct sixes; rule archetypes' mean within-group Jaccard for comparison:")
    tags = np.array([arch(sorted(s)) for s in U]); lines = []
    for t in sorted(set(tags)):
        idx = np.where(tags == t)[0]
        if len(idx) < 2: continue
        sub = 1 - D[np.ix_(idx, idx)]; ww = w[idx]; W = ww[:, None] * ww[None, :]; np.fill_diagonal(W, 0)
        lines.append(f"   {t:32s} teams {int(ww.sum()):5d}  mean Jaccard {float((sub * W).sum() / W.sum()):.2f}")
    print('\n'.join(lines))
    hdr = f"{'k':>3s} {'cost/team':>9s} {'within J':>8s} {'silh':>6s} {'min':>5s} {'max':>5s} {'share>=%d' % MIN:>9s} {'ARI':>6s}"; print(hdr); rows = []
    half = rng.random(n) < 0.5
    for k in range(kmin, kmax + 1):
        cost, med, lab = kmedoids(D, w, k, rng, rs)
        within = 0.0
        for c in range(k):
            idx = np.where(lab == c)[0]; ww = w[idx]
            if len(idx) < 2: continue
            sub = 1 - D[np.ix_(idx, idx)]; W = ww[:, None] * ww[None, :]; np.fill_diagonal(W, 0)
            within += (sub * W).sum() / W.sum() * ww.sum()
        within /= w.sum()
        sizes = np.array([w[lab == c].sum() for c in range(k)])
        share = sizes[sizes >= MIN].sum() / w.sum()
        sil = silhouette(D, w, lab, k)
        # stability: cluster each half, assign everyone to the nearest medoid of each, compare
        labs = []
        for m in (half, ~half):
            idx = np.where(m)[0]; _, medh, _ = kmedoids(D[np.ix_(idx, idx)], w[idx], k, rng, max(2, rs // 2)); labs.append(D[:, idx[medh]].argmin(1))
        st = ari(labs[0], labs[1], w)
        row = f"{k:3d} {cost / w.sum():9.3f} {within:8.2f} {sil:6.3f} {int(sizes.min()):5d} {int(sizes.max()):5d} {share:9.2f} {st:6.2f}"; print(row, flush=True)
        rows.append({'k': k, 'cost_per_team': cost / w.sum(), 'within_jaccard': within, 'silhouette': sil, 'min': int(sizes.min()), 'max': int(sizes.max()), 'share_min': share, 'ari': st})
    os.makedirs('results', exist_ok=True)
    which = which + ('_idf' if os.environ.get('IDF') else '')
    open(f'results/cluster_scan_{which}.txt', 'w').write('\n'.join(lines + [hdr] + [f"{r['k']:3d} {r['cost_per_team']:9.3f} {r['within_jaccard']:8.2f} {r['silhouette']:6.3f} {r['min']:5d} {r['max']:5d} {r['share_min']:9.2f} {r['ari']:6.2f}" for r in rows]) + '\n')
    json.dump({'corpus': which, 'teams': N, 'distinct': n, 'rows': rows}, open(f'results/cluster_scan_{which}.json', 'w'), indent=1)
def show(k):
    which = os.environ.get('CORPUS', 'both'); seed = int(os.environ.get('SEED', '0')); rs = int(os.environ.get('RESTARTS', '6'))
    U, w, D, per, N = corpus(which); rng = np.random.default_rng(seed)
    cost, med, lab = kmedoids(D, w, k, rng, rs)
    out = []; js = []
    order = sorted(range(k), key=lambda c: -w[lab == c].sum())
    for c in order:
        idx = np.where(lab == c)[0]; ww = w[idx]; tot = ww.sum()
        reg = sum(per[U[i]]['regional'] for i in idx); lad = sum(per[U[i]]['ladder'] for i in idx)
        core = collections.Counter()
        for i in idx:
            for s in U[i]: core[s] += w[i]
        comp = collections.Counter()
        for i in idx: comp[arch(sorted(U[i]))] += w[i]
        sub = 1 - D[np.ix_(idx, idx)]; W = ww[:, None] * ww[None, :]; np.fill_diagonal(W, 0); wj = float((sub * W).sum() / W.sum()) if len(idx) > 1 else 1.0
        near = comp.most_common(1)[0][0]
        out.append(f"cluster {c:2d}: {int(tot):4d} teams (regional {reg}, ladder {lad}); within Jaccard {wj:.2f}; nearest archetype {near} ({100 * comp[near] / tot:.0f}%)\n"
                   f"   medoid: {', '.join(sorted(U[med[c]]))}\n"
                   f"   core:   {', '.join(f'{s} {100 * v / tot:.0f}%' for s, v in core.most_common(9))}\n"
                   f"   rules:  {', '.join(f'{a} {100 * v / tot:.0f}%' for a, v in comp.most_common(4))}")
        js.append({'cluster': int(c), 'teams': int(tot), 'regional': int(reg), 'ladder': int(lad), 'within_jaccard': wj, 'medoid': sorted(U[med[c]]),
                   'core': [(s, v / tot) for s, v in core.most_common(12)], 'rules': {a: v / tot for a, v in comp.items()}, 'nearest': near})
    txt = f"{which}: {N} teams, k = {k}, cost per team {cost / w.sum():.3f}\n" + '\n'.join(out) + '\n'
    print(txt); os.makedirs('results', exist_ok=True)
    which = which + ('_idf' if os.environ.get('IDF') else '')
    open(f'results/clusters_k{k}_{which}.txt', 'w').write(txt); json.dump(js, open(f'results/clusters_k{k}_{which}.json', 'w'), indent=1)
if __name__ == '__main__':
    if sys.argv[1] == 'scan': scan(int(sys.argv[2]) if len(sys.argv) > 2 else 4, int(sys.argv[3]) if len(sys.argv) > 3 else 40)
    elif sys.argv[1] == 'show': show(int(sys.argv[2]))

def cores(min_support):
    """core-based groups: repeatedly take the species pair (or triple, when it covers at least 60% of the pair's teams) with the most
    unassigned teams, assign every unassigned team containing it, until the best remaining pair covers fewer than min_support teams;
    the rest is 'other'. Nameable by construction (the core is the name); the number of groups follows from the support threshold."""
    which = os.environ.get('CORPUS', 'both'); rows = load()
    if which != 'both': rows = [r for r in rows if r[1] == which]
    sixes = [set(s) for s, _ in rows]; src = [c for _, c in rows]; n = len(rows)
    left = set(range(n)); groups = []
    from itertools import combinations
    df = collections.Counter(x for s in sixes for x in s); lift_min = float(os.environ.get('LIFT', '2.0'))
    while True:
        pc = collections.Counter()
        for i in left:
            for p in combinations(sorted(sixes[i]), 2): pc[p] += 1
        # candidate cores: pairs that co-occur at least LIFT times more often than chance over the whole corpus (so staples such as
        # Incineroar + Rillaboom do not define a group), ranked by how many unassigned teams they cover
        cand = [(sup, p) for p, sup in pc.items() if sup >= min_support and sup * n / (df[p[0]] * df[p[1]]) >= lift_min]
        if not cand: break
        sup, pair = max(cand)
        members = [i for i in left if set(pair) <= sixes[i]]
        # extend to a triple when one third species rides along with at least 60% of them
        tc = collections.Counter(x for i in members for x in sixes[i] if x not in pair)
        core = set(pair)
        if tc and tc.most_common(1)[0][1] >= 0.6 * len(members):
            third = tc.most_common(1)[0][0]; core.add(third); members = [i for i in members if third in sixes[i]]
        for i in members: left.discard(i)
        groups.append((core, members))
    out = [f"{which}: {n} teams, min support {min_support}, lift >= {lift_min}: {len(groups)} core groups cover {100 * (1 - len(left) / n):.0f}% of teams; other = {len(left)}"]
    for core, members in groups:
        tot = len(members); reg = sum(1 for i in members if src[i] == 'regional'); lad = tot - reg
        sub = [sixes[i] for i in members]
        if tot > 1:
            import random; rnd = random.Random(0); pairs = [(rnd.randrange(tot), rnd.randrange(tot)) for _ in range(min(4000, tot * tot))]
            wj = sum(len(sub[a] & sub[b]) / len(sub[a] | sub[b]) for a, b in pairs if a != b) / max(1, sum(1 for a, b in pairs if a != b))
        else: wj = 1.0
        other = collections.Counter(x for s in sub for x in s if x not in core); comp = collections.Counter(arch(sorted(s)) for s in sub)
        out.append(f"{' + '.join(sorted(core)):40s} {tot:5d} (reg {reg:4d}, lad {lad:4d}) within J {wj:.2f} | with: {', '.join(f'{x} {100 * v / tot:.0f}%' for x, v in other.most_common(5))} | rules: {', '.join(f'{a} {100 * v / tot:.0f}%' for a, v in comp.most_common(3))}")
    rest = collections.Counter(arch(sorted(sixes[i])) for i in left)
    out.append(f"other: rules {', '.join(f'{a} {v}' for a, v in rest.most_common(6))}")
    txt = '\n'.join(out) + '\n'; print(txt)
    os.makedirs('results', exist_ok=True); open(f'results/cores_{which}_{min_support}.txt', 'w').write(txt)
if __name__ == '__main__' and sys.argv[1] == 'cores': cores(int(sys.argv[2]) if len(sys.argv) > 2 else 100)

def mine_rules(rows, min_support, lift_min):
    """an ordered list of human-checkable rules {name, all: [species], none: [species]} from frequent, above-chance species cores:
    greedy by coverage of unassigned teams; a core pair grows to a triple when one species rides along with >= 60% of its teams; a group
    is split in two when some other species is on 30-70% of its teams with both halves >= min_support ("also has X" / "without X")."""
    from itertools import combinations
    sixes = [set(s) for s, _ in rows]; n = len(sixes); df = collections.Counter(x for s in sixes for x in s)
    left = set(range(n)); groups = []
    while True:
        pc = collections.Counter()
        for i in left:
            for p in combinations(sorted(sixes[i]), 2): pc[p] += 1
        cand = [(sup, p) for p, sup in pc.items() if sup >= min_support and sup * n / (df[p[0]] * df[p[1]]) >= lift_min]
        if not cand: break
        sup, pair = max(cand); core = set(pair); members = [i for i in left if core <= sixes[i]]
        tc = collections.Counter(x for i in members for x in sixes[i] if x not in core)
        if tc and tc.most_common(1)[0][1] >= 0.6 * len(members):
            third = tc.most_common(1)[0][0]; core.add(third); members = [i for i in members if third in sixes[i]]
        # split on a species that divides the group
        tc = collections.Counter(x for i in members for x in sixes[i] if x not in core)
        split = None
        for x, c in tc.most_common():
            if min_support <= c <= len(members) - min_support and 0.3 <= c / len(members) <= 0.7: split = x; break
        if split:
            a = [i for i in members if split in sixes[i]]; b = [i for i in members if split not in sixes[i]]
            groups.append((core | {split}, set(), a)); groups.append((core, {split}, b))
        else: groups.append((core, set(), members))
        for i in members: left.discard(i)
    return groups, left, sixes
def rules(min_support=100):
    which = os.environ.get('CORPUS', 'both'); rows = load()
    if which != 'both': rows = [r for r in rows if r[1] == which]
    lift_min = float(os.environ.get('LIFT', '2.0')); groups, left, sixes = mine_rules(rows, min_support, lift_min)
    src = [c for _, c in rows]; n = len(rows); out = []; js = []
    out.append(f"{which}: {n} teams; min support {min_support}, lift >= {lift_min}: {len(groups)} rules cover {100 * (1 - len(left) / n):.0f}%, other {len(left)}")
    out.append("apply in order; the first rule whose species are all present (and none of the excluded ones) names the team")
    for k, (core, none, members) in enumerate(groups):
        tot = len(members); reg = sum(1 for i in members if src[i] == 'regional'); lad = tot - reg
        comp = collections.Counter(arch(sorted(sixes[i])) for i in members); near = comp.most_common(1)[0][0]
        others = collections.Counter(x for i in members for x in sixes[i] if x not in core)
        rule = ' + '.join(sorted(core)) + (f"  (without {', '.join(sorted(none))})" if none else '')
        name = f"{near}: {' + '.join(sorted(core))}" + (f" (no {', '.join(sorted(none))})" if none else '')
        out.append(f"{k + 1:2d}. {rule:55s} {tot:5d} teams (reg {reg:4d}, lad {lad:4d}) | usually with {', '.join(f'{x} {100 * v / tot:.0f}%' for x, v in others.most_common(4))} | rules now: {', '.join(f'{a} {100 * v / tot:.0f}%' for a, v in comp.most_common(3))}")
        js.append({'name': name, 'all': sorted(core), 'none': sorted(none), 'teams': tot, 'regional': reg, 'ladder': lad, 'nearest': near,
                   'with': [(x, round(v / tot, 3)) for x, v in others.most_common(8)], 'rules_now': {a: round(v / tot, 3) for a, v in comp.items()}})
    rest = collections.Counter(arch(sorted(sixes[i])) for i in left)
    out.append(f"other ({len(left)}): by the current rules {', '.join(f'{a} {v}' for a, v in rest.most_common(8))}")
    txt = '\n'.join(out) + '\n'; print(txt); os.makedirs('results', exist_ok=True)
    open(f'results/core_rules_{which}_{min_support}.txt', 'w').write(txt); json.dump(js, open(f'results/core_rules_{which}_{min_support}.json', 'w'), indent=1)
def tag(six, rules_list):
    """the first rule a six satisfies, else 'other'"""
    s = set(norm(x) for x in six)
    for r in rules_list:
        if set(r['all']) <= s and not (set(r['none']) & s): return r['name']
    return 'other'
if __name__ == '__main__' and sys.argv[1] == 'rules': rules(int(sys.argv[2]) if len(sys.argv) > 2 else 100)
