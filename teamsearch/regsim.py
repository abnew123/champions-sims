"""The Reg M-C regionals through the sim (the user, 2026-11-25: "could we run each past regional through our sim and see how things
would've gone? in two ways 1) random monte carlo 2) preserve the known matchups (but don't keep the results)").
Data: every round's pairings and every player's open team sheet (regionals/fetch_field.py: Baltimore, Brisbane, Frankfurt, Recife,
Louisville). Sheets have no stat points: spreads are filled from the M-C usage stats (sets_lib.fill_spread), and the sets join
grid_sets.json under new ids as in build_lowelo_starts.py. A team with a set the engine can't run is left out (unknown).
Odds of one match: R games with each player as the engine's "mine" side (v43n1); each game, each side brings four and leads two
sampled from the ladder-fitted imitation model (bring/policy.py) against the opposing six: how players pick, not the climb's bring
search, which under-leads Trick Room setters. Game win chance p -> best-of-3 p^2 (3 - 2p).
  sets      field sets into grid_sets.json; regsim/teams.json {"<event>|<pid>": {gids, arch}}; cells_regsim.txt (sets without cells)
  play      every real match between two known teams; regsim/games.jsonl, one line a match (resumes; game cache cache_reg/)
  report    way 2 (the real pairings, the sim's odds in place of the results) and way 1 (Monte Carlo of each event: a team-strength
            plus archetype-pair model fitted on the sim games, then Swiss rounds, the Day 2 cut and top cut as each event ran them);
            regsim/report.txt, regsim/report.json
  TS_THREADS=4 bin/teamsearch-py regsim.py sets|play|report
"""
import json, os, sys, time, math, random, hashlib, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'pssim'))
os.environ.setdefault('TS_SIM', 'v43n1'); os.environ.setdefault('TS_GAME_CACHE', os.path.join(HERE, 'cache_reg', 'games.sqlite'))
import numpy as np
REG = os.path.join(HERE, '..', 'regionals'); OUT = os.path.join(HERE, 'regsim'); os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, 'regsim.log'); TEAMS = os.path.join(OUT, 'teams.json'); GAMES = os.path.join(OUT, 'games.jsonl')
FULL = os.path.join('..', 'native', 'engine_data_full.json')
R_SIDE = 3; SEED0 = 880000; CHUNK = 400; C_CAL = 0.72                      # C_CAL: the M-B calibration's slope on the sim's true odds
BO3 = lambda p: p * p * (3 - 2 * p)
logit = lambda p: math.log(p / (1 - p))
sig = lambda x: 1 / (1 + math.exp(-x))

def say(s):
    with open(LOG, 'a') as f: f.write(f"{time.strftime('%I:%M %p')} {s}\n")

def sets():
    import build_lowelo_starts as B, sets_lib as L
    from pro_replays import arch
    from cluster_opps import norm
    UNPORTED = {'Revival Blessing', 'Beat Up'}                               # v43 runs Magician and Wandering Spirit (B.UNPORTED predates it)
    E_ = B.ENG
    runnable = lambda f: (L.idf(f['species']) in E_['species'] and (not f['item'] or L.idf(f['item']) in E_['items'])
                          and L.idf(f['ability']) in E_['abilities'] and all(L.idf(m) in E_['moves'] for m in f['moves'])
                          and len(f['moves']) == 4 and not UNPORTED & set(f['moves'] + [f['ability']]))
    T = json.load(open(os.path.join(REG, 'field_teams.json')))
    RS = json.load(open(os.path.join(REG, 'regional_sets.json'))); FS = json.load(open(os.path.join(REG, 'field_sets.json')))
    G = B.G; gid = {L.set_key({k: v for k, v in s.items() if k != 'regional_count'}): g for g, s in G.items()}
    per = collections.Counter()
    for g in G:
        fid, n = g.rsplit('#', 1)
        if n.isdigit(): per[fid] = max(per[fid], int(n))
    teams, why, new = {}, collections.Counter(), 0
    for t in T:
        k = f"{t['event']}|{t['pid']}"; raw = RS.get(k) or FS.get(k)
        try: team = [B.full(s) for s in raw]
        except Exception: why['sheet'] += 1; continue
        if not all(runnable(f) for f in team): why['engine'] += 1; continue
        gids = []
        for f in team:
            sk = L.set_key(f)
            if sk not in gid:
                fid = B.forme_id(L.battle_forme(f['species'], f['item'])); per[fid] += 1; gid[sk] = f"{fid}#{per[fid]}"
                G[gid[sk]] = dict(f, regional_count=0); new += 1
            gids.append(gid[sk])
        teams[k] = dict(gids=gids, arch=arch([norm(f['species']) for f in team]))       # from the Showdown names (fetch_field's predate species_name)
    json.dump(G, open(B.GPATH, 'w'), indent=0); json.dump(teams, open(TEAMS, 'w'))
    has = lambda g: all(os.path.exists(os.path.join(HERE, 'mx', 'out', m, g.replace('/', '_') + '.json')) for m in ('tr', 'notr'))
    miss = sorted({g for v in teams.values() for g in v['gids'] if not has(g)})
    open(os.path.join(HERE, 'cells_regsim.txt'), 'w').write('\n'.join(miss) + ('\n' if miss else ''))
    say(f"field sets: {len(teams)} of {len(T)} teams runnable (left out: {dict(why)}); {new} new set ids; {len(miss)} sets need cells")

def matches():
    """[(event, round, table, p1, p2, real winner or None)] between two known teams"""
    teams = json.load(open(TEAMS)); P = json.load(open(os.path.join(REG, 'pairings.json'))); out = []
    for ev in P:
        for r, ms in sorted(P[ev]['rounds'].items(), key=lambda kv: int(kv[0])):
            for t, (a, b, w) in enumerate(ms):
                if b and f'{ev}|{a}' in teams and f'{ev}|{b}' in teams: out.append((ev, int(r), t, a, b, w))
    return out

class Brings:
    """the imitation model's (lead, back) distribution for a six against a given opposing six"""
    def __init__(self):
        import evaluate as E
        self.P = E.P; self.Fx = E.P.Fx; self.m = self.P.model(); self.cache = {}
    def dist(self, team, opp):
        k = (tuple(team), tuple(opp))
        if k not in self.cache:
            wB, wL, pb, pl = self.m; Fx = self.Fx
            m = Fx.Matchup(list(team), [(g, 4 / 6) for g in opp]); sp = [Fx.G[g]['species'] for g in team]
            lsm = lambda u: np.asarray(u) - (max(u) + math.log(sum(math.exp(x - max(u)) for x in u)))
            uB = lsm([float(np.dot(wB, m.bring_feats(S) + [sum(pb.get(sp[i], 0.0) for i in S)])) for S in Fx.BRINGS])
            ch, lp = [], []
            for b, S in enumerate(Fx.BRINGS):
                Ls = Fx.leads(S)
                uL = lsm([float(np.dot(wL, m.lead_feats(Lp, S) + [sum(pl.get(sp[i], 0.0) for i in Lp)])) for Lp in Ls])
                for l, Lp in enumerate(Ls): ch.append([team[i] for i in Lp] + [team[i] for i in S if i not in Lp]); lp.append(uB[b] + uL[l])
            pr = np.exp(np.array(lp) - max(lp)); self.cache[k] = (ch, pr / pr.sum())
            if len(self.cache) > 20000: self.cache.pop(next(iter(self.cache)))
        return self.cache[k]
    def sample(self, team, opp, rng):
        ch, pr = self.dist(team, opp); return ch[int(np.searchsorted(np.cumsum(pr), rng.random() * pr.sum()))]

def play():
    import evaluate as E, poolmode as PM
    teams = json.load(open(TEAMS)); M = matches(); BR = Brings(); G = E.G
    done = {(d['ev'], d['r'], d['t']) for d in map(json.loads, open(GAMES))} if os.path.exists(GAMES) else set()
    todo = [m for m in M if m[:3] not in done]; thr = int(os.environ.get('TS_THREADS', 4))
    nall = sum(1 for m in json.load(open(os.path.join(REG, 'pairings.json'))).values() for ms in m['rounds'].values() for x in ms if x[1])
    say(f"{E.sim()}: {len(M)} of {nall} regional matches have both teams known; {len(todo)} to play, {2 * R_SIDE} games each, {thr} threads")
    four = lambda gs: [{k: G[g][k] for k in ('species', 'item', 'ability', 'nature', 'evs', 'moves')} for g in gs]
    label = tuple(teams[next(iter(teams))]['gids']); t0 = time.time(); gdone = 2 * R_SIDE * (len(M) - len(todo)); gall = 2 * R_SIDE * len(M)
    for c in range(0, len(todo), CHUNK):
        part = todo[c:c + CHUNK]; jobs, meta = [], []
        for ev, r, t, a, b, w in part:
            A, Bt = teams[f'{ev}|{a}']['gids'], teams[f'{ev}|{b}']['gids']
            for side, (me, op) in enumerate(((A, Bt), (Bt, A))):
                for k in range(R_SIDE):
                    tag = f'{ev}|{r}|{t}|{side}|{k}'; rng = random.Random(tag)
                    jobs.append(dict(mine=four(BR.sample(me, op, rng)), theirs=four(BR.sample(op, me, rng)),
                                     meta=dict(pool_id=tag, pool_side='p1', group='regsim', arch='', seed_index=int(hashlib.md5(tag.encode()).hexdigest()[:8], 16) % 10 ** 8)))
                    meta.append(((ev, r, t), side))
        h = hashlib.md5(json.dumps([m[:3] for m in part]).encode()).hexdigest()[:8]
        rows = E.run_jobs(label, jobs, 1, SEED0, thr, f'regsim_{E.sim()}_{h}', extra=dict(TS_ENGINE_DATA=FULL, SEED_PER_JOB='1'))
        acc = collections.defaultdict(lambda: [0.0, 0])
        for (key, side), row in zip(meta, rows):
            wv, n = PM._wins(row); acc[key][0] += wv if side == 0 else n - wv; acc[key][1] += n
        with open(GAMES, 'a') as f:
            for ev, r, t, a, b, w in part:
                aw, n = acc[(ev, r, t)]; f.write(json.dumps(dict(ev=ev, r=r, t=t, p1=a, p2=b, winner=w, p1_wins=aw, n=n)) + '\n')
        gdone += 2 * R_SIDE * len(part)
        say(f"  score (regional matches): {gdone}/{gall} games, {int((time.time() - t0) / 60)} min")
    say('regional matches done')

# ---------------------------------------------------------------- report
def structure(rounds):
    """(Day 1 rounds, Day 2 Swiss rounds, top cut size) from each round's table count"""
    n = [len(rounds[str(r)]) for r in range(1, len(rounds) + 1)]
    cut = 0
    while cut < len(n) - 1 and n[-1 - cut] == 2 ** cut and n[-2 - cut] > n[-1 - cut]: cut += 1   # 1, 2, 4, 8 tables from the final back, each after a cut
    d1 = next((i for i in range(2, len(n) - cut) if n[i] < 0.6 * n[i - 1]), len(n) - cut)
    return d1, len(n) - cut - d1, 2 ** cut

def fit(games, teams, lam=1.0):
    """per-game logistic model: logit P(a beats b) = s_a - s_b + g[arch_a, arch_b] (g antisymmetric), ridge lam on s and g,
    fitted on the sim's games (wins of n per match) by Newton steps"""
    keys = sorted({k for d in games for k in (f"{d['ev']}|{d['p1']}", f"{d['ev']}|{d['p2']}")}); ix = {k: i for i, k in enumerate(keys)}
    archs = sorted({teams[k]['arch'] for k in keys}); ia = {a: i for i, a in enumerate(archs)}
    pairs = [(i, j) for i in range(len(archs)) for j in range(i + 1, len(archs))]; ip = {p: n for n, p in enumerate(pairs)}
    import scipy.sparse as sp
    nT, nP = len(keys), len(pairs); ri, ci, vv = [], [], []; y = np.zeros(len(games)); n = np.zeros(len(games))
    for r, d in enumerate(games):
        a, b = f"{d['ev']}|{d['p1']}", f"{d['ev']}|{d['p2']}"; ri += [r, r]; ci += [ix[a], ix[b]]; vv += [1.0, -1.0]
        u, v = ia[teams[a]['arch']], ia[teams[b]['arch']]
        if u != v: ri.append(r); ci.append(nT + ip[(min(u, v), max(u, v))]); vv.append(1.0 if u < v else -1.0)
        y[r], n[r] = d['p1_wins'], d['n']
    X = sp.csr_matrix((vv, (ri, ci)), shape=(len(games), nT + nP)); w = np.zeros(nT + nP)
    for _ in range(25):
        p = 1 / (1 + np.exp(-(X @ w))); g = X.T @ (y - n * p) - lam * w
        H = (X.T @ sp.diags(n * p * (1 - p)) @ X).toarray() + lam * np.eye(len(w)); step = np.linalg.solve(H, g); w += step
        if np.abs(step).max() < 1e-6: break
    s = {k: w[ix[k]] for k in keys}
    gm = {}
    for (u, v), m in ip.items(): gm[(archs[u], archs[v])] = w[nT + m]; gm[(archs[v], archs[u])] = -w[nT + m]
    return s, gm

def tourney(players, q, d1, d2, cut, rng, day2_wins):
    """one Swiss event: players [key], q(a, b) = match win chance; Swiss pairing within record (random order, adjacent pairs),
    a bye to the last player of an odd round; Day 2 for day2_wins+ wins after Day 1; top cut by wins (ties random), seeded 1 v cut"""
    W = {p: 0 for p in players}
    def swiss(ps, rounds):
        for _ in range(rounds):
            order = sorted(ps, key=lambda p: (-W[p], rng.random()))
            if len(order) % 2: W[order.pop()] += 1
            for i in range(0, len(order), 2):
                a, b = order[i], order[i + 1]; W[a if rng.random() < q(a, b) else b] += 1
    swiss(players, d1)
    day2 = [p for p in players if W[p] >= day2_wins]; swiss(day2, d2)
    top = sorted(day2, key=lambda p: (-W[p], rng.random()))[:cut]; alive = top
    while len(alive) > 1:
        alive = [(a if rng.random() < q(a, b) else b) for a, b in zip(alive[:len(alive) // 2], reversed(alive[len(alive) // 2:]))]
    return set(day2), set(top), alive[0]

def report(runs=int(os.environ.get('TS_REG_RUNS', 1000))):
    teams = json.load(open(TEAMS)); P = json.load(open(os.path.join(REG, 'pairings.json')))
    games = [d for d in map(json.loads, open(GAMES)) if d['n']]
    L, J = [], {}
    def out(s=''): L.append(s)
    # ---- way 2: the real pairings
    s, gm = fit(games, teams)
    gx = lambda a, b: s[a] - s[b] + gm.get((teams[a]['arch'], teams[b]['arch']), 0.0)       # the model's game log-odds
    rows = []
    for d in games:
        if d['winner'] not in (d['p1'], d['p2']): continue
        a, b = f"{d['ev']}|{d['p1']}", f"{d['ev']}|{d['p2']}"
        rows.append(dict(a=a, b=b, y=int(d['winner'] == d['p1']), direct=logit((d['p1_wins'] + 1) / (d['n'] + 2)), model=gx(a, b), ev=d['ev'], r=d['r']))
    out(f"Way 2: the real pairings ({len(rows)} decided matches between known teams, of {len(games)} played in the sim)")
    J['way2'] = {}
    for kind in ('direct', 'model'):
        for c in (1.0, C_CAL):
            q = np.clip([BO3(sig(c * x[kind])) for x in rows], 1e-6, 1 - 1e-6); y = np.array([x['y'] for x in rows])   # c shrinks the game odds
            ll = -np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)); acc = np.mean((q > 0.5) == (y == 1))
            z = np.log(q / (1 - q)); b = 0.0
            for _ in range(30):                                                   # slope of the real result on the sim's log-odds
                p = 1 / (1 + np.exp(-b * z)); b += np.sum(z * (y - p)) / max(np.sum(z * z * p * (1 - p)), 1e-9)
            J['way2'][f'{kind}_c{c}'] = dict(logloss=ll, acc=acc, slope=b)
            out(f"  {kind:6s} odds{'' if c == 1 else f', game odds x{c}':15s}: favourite won {100 * acc:.1f}%, log loss {ll:.4f} (coin flip 0.6931), slope {b:.2f}")
    exp, act, cnt = collections.Counter(), collections.Counter(), collections.Counter()
    for x in rows:
        q = BO3(sig(x['model']))
        for k, e, r in ((x['a'], q, x['y']), (x['b'], 1 - q, 1 - x['y'])): exp[k] += e; act[k] += r; cnt[k] += 1
    ks = [k for k in cnt if cnt[k] >= 5]
    r_pl = np.corrcoef([exp[k] / cnt[k] for k in ks], [act[k] / cnt[k] for k in ks])[0, 1]
    out(f"  players with >= 5 known matches: {len(ks)}; correlation of the sim's expected win share with the real one: {r_pl:.2f}")
    J['way2']['player_corr'] = r_pl
    out("  by archetype (matches between known teams): real match win share vs the sim's expected")
    ar = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for k in cnt: v = ar[teams[k]['arch']]; v[0] += act[k]; v[1] += exp[k]; v[2] += cnt[k]
    for a, (r_, e_, n_) in sorted(ar.items(), key=lambda kv: -kv[1][2]):
        if n_ >= 50: out(f"    {a:16s} {n_:5d} matches   real {100 * r_ / n_:5.1f}%   sim {100 * e_ / n_:5.1f}%   gap {100 * (r_ - e_) / n_:+5.1f}")
    J['way2']['arch'] = {a: dict(n=v[2], real=v[0] / v[2], sim=v[1] / v[2]) for a, v in ar.items()}
    # ---- way 1: Monte Carlo of each event
    out(); out(f"Way 1: Monte Carlo, {runs} runs of each event a setting (model odds; unknown teams at the field's average strength, no archetype term)")
    J['way1'] = {}
    for ev in P:
        R = P[ev]['rounds']; d1, d2, cut = structure(R)
        players = sorted({x for ms in R.values() for m in ms for x in m[:2] if x})
        later = {x for r in range(d1 + 1, d1 + d2 + 1) for m in R.get(str(r), []) for x in m[:2] if x}
        topr = {x for m in R.get(str(d1 + d2 + 1), []) for x in m[:2] if x} if cut > 1 else set()
        champ = R[str(len(R))][0][2]
        W = collections.Counter()
        for r in range(1, d1 + 1):
            for a, b, w in R[str(r)]:
                if w: W[w] += 1
                elif not b: W[a] += 1
        lw = sorted(W[p] for p in later); d2w = lw[len(lw) // 50] if lw else 0    # the Day 2 record (a stray 5-win Day 2 player at Baltimore)
        keyof = {p: f'{ev}|{p}' for p in players}; known = {p for p in players if keyof[p] in s}
        mean_s = np.mean([s[keyof[p]] for p in known]) if known else 0.0
        st = {p: (s[keyof[p]] if p in known else mean_s) for p in players}; ar_ = {p: teams[keyof[p]]['arch'] if p in known else None for p in players}
        J['way1'][ev] = dict(players=len(players), known=len(known), day1=d1, day2=d2, cut=cut, day2_wins=d2w)
        out(f"  {ev}: {len(players)} players ({len(known)} known teams), {d1} Day 1 rounds, Day 2 at {d2w}+ wins, {d2} Day 2 rounds, top {cut}")
        for c in (1.0, C_CAL):
            cache = {}
            def q(a, b, c=c):
                k = (a, b)
                if k not in cache:
                    x = st[a] - st[b] + (gm.get((ar_[a], ar_[b]), 0.0) if ar_[a] and ar_[b] else 0.0); cache[k] = BO3(sig(c * x))
                return cache[k]
            rng = random.Random(f'{ev}|{c}'); n2, nt, nw = collections.Counter(), collections.Counter(), collections.Counter()
            for _ in range(runs):
                a2, at, aw = tourney(players, q, d1, d2, cut, rng, d2w)
                for p in a2: n2[p] += 1
                for p in at: nt[p] += 1
                nw[aw] += 1
            pd2 = {p: n2[p] / runs for p in players}
            real2 = [pd2[p] for p in players if p in later]; other = [pd2[p] for p in players if p not in later]
            auc = np.mean([1.0 if x > y else 0.5 if x == y else 0.0 for x in real2 for y in rng.sample(other, min(len(other), 300))])
            ranks = sorted(players, key=lambda p: -nw[p]); cr = ranks.index(champ) + 1 if champ in ranks else None
            arch2 = collections.Counter(); arch2r = collections.Counter(); archt = collections.Counter(); archtr = collections.Counter()
            for p in players:
                a = ar_[p] or 'unknown'; arch2[a] += pd2[p]; archt[a] += nt[p] / runs
                if p in later: arch2r[a] += 1
                if p in topr: archtr[a] += 1
            tag = 'raw' if c == 1 else f'x{c}'
            J['way1'][ev][tag] = dict(day2_auc=auc, champ_p=nw[champ] / runs, champ_rank=cr, real_day2_mean=float(np.mean(real2)) if real2 else None,
                                      arch_day2={a: dict(sim=arch2[a], real=arch2r[a]) for a in arch2},
                                      arch_top={a: dict(sim=archt[a], real=archtr[a]) for a in archt},
                                      top_teams=[dict(arch=ar_[p], win=nw[p] / runs, top=nt[p] / runs, day2=pd2[p], real_day2=p in later,
                                                      real_top=p in topr, real_win=p == champ) for p in ranks[:10]])
            out(f"    {tag:5s}: real Day 2 players had a {100 * np.mean(real2):.0f}% sim chance of Day 2 (others {100 * np.mean(other):.0f}%; AUC {auc:.2f});"
                f" the real winner won {100 * nw[champ] / runs:.1f}% of runs (rank {cr})")
            top_a = sorted(arch2, key=lambda a: -arch2[a])[:6]
            out("           Day 2 by archetype, sim vs real: " + ', '.join(f"{a} {arch2[a]:.0f}/{arch2r[a]}" for a in top_a))
            if cut > 1: out(f"           top {cut} by archetype, sim vs real: " + ', '.join(f"{a} {archt[a]:.1f}/{archtr[a]}" for a in sorted(archt, key=lambda a: -archt[a])[:6]))
    open(os.path.join(OUT, 'report.txt'), 'w').write('\n'.join(L) + '\n'); json.dump(J, open(os.path.join(OUT, 'report.json'), 'w'), indent=1)
    print('\n'.join(L)); say('report done')

if __name__ == '__main__':
    {'sets': sets, 'play': play, 'report': report}[sys.argv[1]]()
