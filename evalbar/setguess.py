"""Set guesses from the rest of the team (the user, 2026-10-12, after a Bo1 bot game where a Quiver Dance Volcarona was taken for the
support set: "Volcarona in that specific team style is basically always a Quiver Dance sweeper"). Learned from every distinct six on the
cached Bo3 open team sheets. For a species and the other five seen at team preview, each whole set (item, ability, nature, four moves) gets a
weight from:
  shared cores     every team with this species, counted B^(shared - 5) by how many of these five teammates it also has: the exact six
                   counts in full (popular teams are copied whole), a team sharing a core of four 1/B, three 1/B^2... (the user: teams are
                   built around cores, and a species' role follows the core)
  the teammates    naive Bayes on which species the other five are, one at a time, over the species' sets seen at least MIN_CLASS times:
                   worth KAPPA teams, so it decides only where no team shares much
  then whatever has been revealed (moves, item, ability) keeps only the sets that have it; if none does, the species' other sets that do,
  by how often they are run; if none at all, the likeliest set with the revealed parts put in.
On held-out teams (a fifth, by team) the whole set (item, ability, nature, moves) is right 24.6% of the time for the species' most common
set, 33.2% with the exact six and naive Bayes, 40% with shared cores (moves right, of 4: 3.07 -> 3.33); build prints the current figures. Names are packed as the sheets write them (FocusSash, QuiverDance), as bot/set_prior.py keeps them.
  python3 evalbar/setguess.py build                         -> out/setguess.json, and the held-out report
  python3 evalbar/setguess.py guess <species> <mate> ... [move=QuiverDance] [item=..] [ability=..]"""
import os, re, sys, json, math, zlib, glob, collections
import common as C
OUT = os.path.join(C.HERE, 'out', 'setguess.json')
MIN_CLASS, MIN_VOCAB = 3, 20
TUNED = {'_tau': 0.5, '_beta': 0.5, '_B': 20.0, '_kappa': 0.01}           # what build chose on 2026-10-12 (held out by team)
toid = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
def base(sp):
    """the species as team preview and the sheets show it: a Mega form's base"""
    return re.sub(r'-Mega(-[A-Z])?$', '', sp or '')
def teams():
    """every distinct six on the Bo3 open team sheets: tuples of (species, item, ability, nature, moves)"""
    out = set()
    for f in glob.glob(os.path.join(C.LOGS, '*regmcbo3*.log')):
        for l in open(f, errors='replace'):
            if l.startswith('|turn|'): break
            if not l.startswith('|showteam|'): continue
            team = []
            for blob in l.rstrip('\n').split('|', 3)[3].split(']'):
                x = blob.split('|')
                if len(x) < 6: continue
                team.append((x[1] or x[0], x[2], x[3], x[5] or 'Serious', tuple(sorted(m for m in x[4].split(',') if m))))
            if len(team) == 6: out.add(tuple(sorted(team)))
    return sorted(out)
def fit(ts):
    """the model from a list of sixes: {species id: {sets, six, vocab}}"""
    rows = collections.defaultdict(list)
    for t in ts:
        for m in t: rows[toid(m[0])].append((m[1:], frozenset(toid(x[0]) for x in t if x is not m), m[0]))
    model = {}
    for sp, rs in rows.items():
        cnt = collections.Counter(s for s, _, _ in rs); mates = collections.defaultdict(collections.Counter)
        for s, ms, _ in rs: mates[s].update(ms)
        vocab = collections.Counter(x for _, ms, _ in rs for x in ms)
        six = collections.defaultdict(collections.Counter)
        for s, ms, _ in rs: six[ms][s] += 1
        order = cnt.most_common(); idx = {s: i for i, (s, _) in enumerate(order)}
        sets = [[list(s[:3]), list(s[3]), n, dict(mates[s]) if n >= MIN_CLASS else {}] for s, n in order]
        model[sp] = {'name': rs[0][2], 'n': len(rs), 'vocab': sorted(v for v, k in vocab.items() if k >= MIN_VOCAB), 'sets': sets,
                     'teams': {','.join(sorted(k)): [[idx[s], n] for s, n in v.items()] for k, v in six.items()}}     # each five teammates: its sets
    return model
_M, _PRE = {}, {}
def model():
    if not _M:
        if not os.path.exists(OUT):                                             # no tuning on a first call (a few seconds): the settings build chose
            M = fit(teams()); M.update(TUNED); os.makedirs(os.path.dirname(OUT), exist_ok=True); json.dump(M, open(OUT, 'w'), separators=(',', ':'))
        _M.update(json.load(open(OUT)))
    return _M
def _key(s): return (tuple(s[0]), tuple(s[1]))
def dist(species, teammates, revealed=None, M=None, tau=None, beta=None, B=None, kappa=None):
    """[(weight, {'item', 'ability', 'nature', 'moves'})], likeliest first, weights summing to 1; [] for a species never on a sheet.
    teammates: the other species at team preview (Mega forms are taken back to their base); revealed: {'moves': [...], 'item', 'ability'}
    in any spelling (Quiver Dance, QuiverDance)"""
    M = M or model(); k = toid(base(species))
    D = M.get(k) or (next((v for x, v in M.items() if x.startswith(k) and isinstance(v, dict)), None) if base(species) != species else None)   # Floette-Mega -> Floette-Eternal
    if not D: return []
    tau = tau if tau is not None else M.get('_tau', TUNED['_tau']); beta = beta if beta is not None else M.get('_beta', TUNED['_beta'])
    B = B if B is not None else M.get('_B', TUNED['_B']); kappa = kappa if kappa is not None else M.get('_kappa', TUNED['_kappa'])
    mates = {toid(base(x)) for x in teammates} - {toid(base(species))}
    sets = D['sets']; tot = sum(s[2] for s in sets)
    # the teammates: naive Bayes over the sets run at least MIN_CLASS times, tempered (tau) so its weights mean what they say
    pre = _PRE.get(id(D))
    if pre is None:                                                             # per set: its score with no teammate, and what each one adds
        pre = []
        for i, (h, mv, n, mt) in enumerate(sets):
            if n < MIN_CLASS: continue
            ps = {v: (mt.get(v, 0) + 0.5) / (n + 1) for v in D['vocab']}
            pre.append((i, math.log(n), sum(math.log(1 - p) for p in ps.values()), {v: math.log(p) - math.log(1 - p) for v, p in ps.items()}))
        _PRE[id(D)] = pre
        _PRE[(id(D), 'teams')] = [(frozenset(k.split(',')) if k else frozenset(), v) for k, v in D['teams'].items()]
    sc = {i: tau * (lp + beta * (c + sum(dl.get(v, 0) for v in mates))) for i, lp, c, dl in pre}   # beta: how far the teammates move it from how often each set is run
    w = {}
    if sc:
        top = max(sc.values()); z = sum(math.exp(v - top) for v in sc.values()); w = {i: math.exp(v - top) / z for i, v in sc.items()}
    # shared cores: every team with this species, by how many of these teammates it shares (B ** 0 = 1 for the exact six); naive Bayes
    # counts as kappa teams
    if B:
        c = collections.Counter()
        for ks, v in _PRE[(id(D), 'teams')]:
            x = B ** (len(ks & mates) - 5)
            for i, n in v: c[i] += n * x
        tot = sum(c.values()); w = {i: (c.get(i, 0) + kappa * w.get(i, 0)) / (tot + kappa) for i in set(c) | set(w)}
    if not w: w = {i: s[2] / tot for i, s in enumerate(sets)}
    rv = revealed or {}; rm = {toid(m) for m in rv.get('moves') or [] if m}; ri, ra = toid(rv.get('item')), toid(rv.get('ability'))
    ok = lambda s: rm <= {toid(m) for m in s[1]} and (not ri or toid(s[0][0]) == ri) and (not ra or toid(s[0][1]) == ra)
    if rm or ri or ra:
        w = {i: x for i, x in w.items() if ok(sets[i])}
        if not w: w = {i: s[2] for i, s in enumerate(sets) if ok(s)}                 # the species' other sets that fit, by how often they are run
        if not w:                                                                   # none fits: the likeliest set with the revealed parts put in
            j = max(range(len(sets)), key=lambda i: (len(rm & {toid(m) for m in sets[i][1]}), sets[i][2]))
            h, mv = sets[j][0], sets[j][1]; names = {toid(m): m for s in sets for m in s[1]}
            moves = [names.get(m, m) for m in sorted(rm)] + [m for m in mv if toid(m) not in rm]
            item = next((s[0][0] for s in sets if toid(s[0][0]) == ri), rv.get('item')) if ri else h[0]
            abil = next((s[0][1] for s in sets if toid(s[0][1]) == ra), rv.get('ability')) if ra else h[1]
            return [(1.0, {'item': item, 'ability': abil, 'nature': h[2], 'moves': moves[:4]})]
    z = sum(w.values())
    return sorted(((x / z, {'item': sets[i][0][0], 'ability': sets[i][0][1], 'nature': sets[i][0][2], 'moves': list(sets[i][1])}) for i, x in w.items() if x > 0),
                  key=lambda t: -t[0])
def best_set(species, teammates, revealed=None):
    """the likeliest set: {'item', 'ability', 'nature', 'moves'} (packed names), or None for a species never on a sheet"""
    d = dist(species, teammates, revealed); return d[0][1] if d else None
def build():
    ts = teams(); test = lambda t: zlib.crc32(repr(t).encode()) % 5 == 0
    tr, te = [t for t in ts if not test(t)], [t for t in ts if test(t)]
    Mt = fit(tr)
    def score(tau, beta, B=0, kappa=0):
        ll = right = mvs = base_r = base_m = n = 0; perr = collections.defaultdict(lambda: [0, 0, 0, 0])
        key = lambda s: (s['item'], s['ability'], s['nature'], tuple(s['moves']))
        for t in te:
            for m in t:
                if toid(m[0]) not in Mt: continue
                d = dist(m[0], [x[0] for x in t if x is not m], None, Mt, tau, beta, B, kappa)
                if not d: continue
                truth = (m[1], m[2], m[3], m[4])
                p = next((x for x, s in d if key(s) == truth), 0); ll -= math.log(max(p, 1e-3)); n += 1
                b = d[0][1]; right += key(b) == truth; mvs += len(set(b['moves']) & set(m[4]))
                top = Mt[toid(m[0])]['sets'][0]; bt = (top[0][0], top[0][1], top[0][2], tuple(top[1]))
                base_r += bt == truth; base_m += len(set(top[1]) & set(m[4]))
                e = perr[m[0]]; e[0] += 1; e[1] += bt == truth; e[2] += key(b) == truth
        return ll / n, right / n, mvs / n, base_r / n, base_m / n, n, perr
    # naive Bayes's beta on its own, then the cores' B and kappa, for the likeliest set (the whole set right most often); then tau for the
    # weights (the held-out sets' log loss)
    beta = max((1.0, 0.7, 0.5, 0.35, 0.25), key=lambda b: score(1.0, b)[1]); nb_only = score(1.0, beta)
    B, kappa = max(((b, k) for b in (8.0, 12.0, 20.0) for k in (0.01, 0.05)), key=lambda bk: score(1.0, beta, *bk)[1])
    tau = min((1.0, 0.7, 0.5), key=lambda t: score(t, beta, B, kappa)[0])
    ll, right, mvs, base_r, base_m, n, perr = score(tau, beta, B, kappa)
    _PRE.clear(); M = fit(ts); M['_tau'], M['_beta'], M['_B'], M['_kappa'] = tau, beta, B, kappa   # (the cache is by object: the held-out model's go with it)
    os.makedirs(os.path.dirname(OUT), exist_ok=True); json.dump(M, open(OUT, 'w'), separators=(',', ':'))
    print(f"{len(ts)} distinct sixes ({len(te)} held out); B {B}, kappa {kappa}, beta {beta}, tau {tau}. Whole set right (item, ability, nature, moves): "
          f"the species' most common {base_r:.3f}, naive Bayes alone {nb_only[1]:.3f}, with shared cores {right:.3f}; moves right of 4: {base_m:.2f} -> {mvs:.2f}; "
          f"log loss {nb_only[0]:.2f} -> {ll:.2f} ({n} held-out Pokemon)")
    for sp, e in sorted(perr.items(), key=lambda kv: -kv[1][0])[:12]: print(f"  {sp:18s} {e[0]:4d}  {e[1] / e[0]:.2f} -> {e[2] / e[0]:.2f}")
if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == 'build': build()
    elif a and a[0] == 'guess':
        rv = {'moves': [x[5:] for x in a if x.startswith('move=')], 'item': next((x[5:] for x in a if x.startswith('item=')), ''),
              'ability': next((x[8:] for x in a if x.startswith('ability=')), '')}
        names = [x for x in a[1:] if '=' not in x]
        for w, s in dist(names[0], names[1:], rv)[:5]: print(f"{w:.2f}  {s['item']:14s} {s['ability']:14s} {s['nature']:8s} {', '.join(s['moves'])}")
    else: sys.exit(__doc__)
