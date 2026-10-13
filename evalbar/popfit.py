"""Default spreads fitted to what the replays show (the user asked, 2026-10-12: Smogon's most used spread for a nature can be far from what
most players run; Mega Floette's no-bulk spread fit the physical hits in 15 of 98 games). For each species and nature, the whole spread
(66 points, at most 32 a stat, on a grid of 4) that fits the most evidence in the cached Reg M-C replays:
  hits it took     which (HP, Def) or (HP, SpD) fit the damage (damage.js, exact; the attacker at its Smogon default)
  hits it gave     which Atk or SpA fit (the target at its Smogon default)
  turn order       which Spe fits (spreads.observations, exact Speed; the other Pokemon at its Smogon default)
Ties (evidence that does not tell values apart) go to the spread closest to Smogon's most used. A fifth of the games (by a hash of the
id) are held out: the report compares how much of their evidence Smogon's spread and the fitted one fit.
  python3 evalbar/popfit.py collect k/n [games=N]   share k of n of the replays -> out/popfit/obs_k_of_n.jsonl (resumable, progress card)
  python3 evalbar/popfit.py fit                       -> evalbar/default_spreads.json and a report
  python3 evalbar/popfit.py ctx [B F kappa]           the same by team core and set, held out: how much more of each Pokemon's evidence it fits
Nothing reads default_spreads.json yet: it is for review first."""
import os, re, sys, json, time, zlib, random, itertools, subprocess, collections
import common as C, live as L, replay as R, spreads as SPR, procs as P, mega_check as MC
OUT = os.path.join(C.HERE, 'out', 'popfit'); G = list(range(0, 33, 4)); CAP = 400     # per species, nature and kind, over all shares
toid = R.toid
def default(sp, nat):
    """Smogon's most used spread for this species and nature; without one for the nature, the species' most used of any nature"""
    rk = SPR.ranked(sp, nat)
    if rk: return list(rk[0][1])
    rows = SPR.table().get(toid(sp)) or SPR.table().get(toid(sp.split('-')[0])) or []
    return list(max(rows, key=lambda r: r[0])[2]) if rows else None
def held(rid): return zlib.crc32(rid.encode()) % 5 == 0
def collect(k, n, limit=None):
    os.makedirs(OUT, exist_ok=True); part = os.path.join(OUT, f'obs_{k}_of_{n}.jsonl'); prog = part[:-6] + '.games'
    games = sorted(rid for rid, _ in C.games() if 'regmcbo3' in rid); random.Random(7).shuffle(games); games = games[k::n][:limit] if limit else games[k::n]
    done = {l.strip() for l in open(prog)} if os.path.exists(prog) else set()
    count = collections.Counter()
    if os.path.exists(part):
        for l in open(part):
            x = json.loads(l)
            if x['k'] != 'spe': count[(x['sp'], x['nat'], x['k'])] += 1
    json.dump({'title': f'Fitted default spreads: evidence, share {k + 1} of {n} (games)', 'out': os.path.relpath(prog, os.path.join(C.HERE, 'out')), 'total': len(games),
               'done0': len(done), 'started': time.time(), 'threads': 2, 'seeds': 0, 'staged': False}, open(prog + '.run.json', 'w'))
    cap = CAP // n + 1; qf, of = os.path.join(OUT, f'q{os.getpid()}.json'), os.path.join(OUT, f'r{os.getpid()}.json')
    for rid in games:
        if rid in done: continue
        recs = []
        try: recs = game_records(rid, open(os.path.join(C.LOGS, rid + '.log')).read(), count, cap, qf, of)
        except Exception as e: recs = []
        with open(part, 'a') as fh: fh.writelines(json.dumps(r) + '\n' for r in recs)
        with open(prog, 'a') as fh: fh.write(rid + '\n')
def game_records(rid, log, count, cap, qf, of):
    hold = held(rid); recs = []; queries = []; plan = []
    gp = R.parse(log); sheets = gp['sheets']
    def ctx(sd, sp):
        """for spreads by team core and set (the user, 2026-10-12, after setguess.py): the player's other five and this one's item and moves"""
        sh = sheets.get(sd) or {}; b = toid(re.sub(r'-Mega(-[A-Z])?$', '', sp))
        me = sh.get(toid(sp)) or sh.get(b) or next((v for k, v in sh.items() if k.startswith(b)), {})     # Floette-Mega -> Floette-Eternal
        return {'side': sd, 'mates': sorted(v['species'] for v in sh.values() if v is not me), 'item': me.get('item', ''), 'moves': sorted(me.get('moves') or [])}
    for q, m in MC.hits(rid, log, sample=1.0):
        d, a = q['def'], q['att']
        for role, sp, nat, kind in (('def', m['dbase'], m['dnat'], 'tp' if m['cat'] == 'Physical' else 'ts'), ('att', m['abase'], m['anat'], 'dp' if m['cat'] == 'Physical' else 'ds')):
            if not sp or not nat or count[(sp, nat, kind)] >= cap: continue
            base = default(sp, nat) or q['spec']['sides'][(d if role == 'def' else a)[0]]['mons'][(d if role == 'def' else a)[1]].get('evs')
            if not base: continue
            if role == 'def': cells = [(h, x) for h in G for x in G]; idx = 2 if kind == 'tp' else 4
            else: cells = [(x,) for x in G]; idx = 1 if kind == 'dp' else 3
            for c in cells:
                e = list(base)
                if role == 'def': e[0], e[idx] = c
                else: e[idx] = c[0]
                q2 = json.loads(json.dumps(q)); w = d if role == 'def' else a; q2['spec']['sides'][w[0]]['mons'][w[1]]['evs'] = e; queries.append(q2)
            plan.append((sp, nat, kind, cells, m['pct'], ctx('p1' if (d if role == 'def' else a)[0] == 0 else 'p2', sp))); count[(sp, nat, kind)] += 1
    if queries:
        json.dump(queries, open(qf, 'w'))
        subprocess.run([P.exe('node'), os.path.join(C.HERE, 'damage.js'), qf, of], cwd=os.path.join(C.MAIN, 'pssim'), check=True, capture_output=True)
        res = iter(json.load(open(of)))
        for sp, nat, kind, cells, pct, cx in plan:
            rs = [next(res) for _ in cells]
            if any(r is None or r.get('lo') is None for r in rs): continue
            fit = [list(c) for c, r in zip(cells, rs) if SPR.damage_fits({'pct': tuple(pct), 'atleast': False}, r, 0)]
            recs.append({'game': rid, 'hold': hold, 'k': kind, 'sp': sp, 'nat': nat, 'fit': fit, **cx})
    # turn order: each side in turn as the 'known' one at its Smogon default, the other's Speed on the grid
    for ks in ('p1', 'p2'):
        def known(species, forme, ks=ks):
            st = sheets[ks].get(toid(species)) or sheets[ks].get(toid(species.split('-')[0])) or {}
            e = default(species, st.get('nature')) if st.get('nature') else None
            return SPR.raw_speed(forme, e, st['nature']) if e else None
        other = 'p2' if ks == 'p1' else 'p1'
        for ob in SPR.observations(log, ks, known, sheets, 3):
            st = sheets[other].get(toid(ob['species'])) or sheets[other].get(toid(ob['species'].split('-')[0])) or {}
            nat = st.get('nature')
            if not nat: continue
            sp = next((k_ for k_ in [ob['species']]), ob['species'])
            fit = [[x] for x in G if SPR.fits([0, 0, 0, 0, 0, x], nat, ob)]
            recs.append({'game': rid, 'hold': hold, 'k': 'spe', 'sp': sp, 'nat': nat, 'fit': fit, **ctx(other, sp)})
    return recs
def fit():
    import glob
    recs = [json.loads(l) for f in glob.glob(os.path.join(OUT, 'obs_*.jsonl')) for l in open(f)]
    by = collections.defaultdict(list)
    for r in recs: by[(r['sp'], r['nat'])].append(r)
    nearest = lambda v: min(G, key=lambda g: abs(g - v))
    def tables(rs):
        T = {'tp': collections.Counter(), 'ts': collections.Counter(), 'dp': collections.Counter(), 'ds': collections.Counter(), 'spe': collections.Counter()}; N = collections.Counter()
        for r in rs:
            N[r['k']] += 1
            for c in r['fit']: T[r['k']][tuple(c)] += 1
        return T, N
    def score(T, e):
        hp, at, de, sa, sd, sp = (nearest(v) for v in e)
        return T['tp'][(hp, de)] + T['ts'][(hp, sd)] + T['dp'][(at,)] + T['ds'][(sa,)] + T['spe'][(sp,)]
    out, report = {}, []
    for (sp, nat), rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        train = [r for r in rs if not r['hold']]; test = [r for r in rs if r['hold']]
        if len(train) < 40: continue
        T, N = tables(train); base = default(sp, nat) or [2, 0, 0, 32, 0, 32]
        best, bkey = None, None
        for hp, at, de, sa, sd in itertools.product(G, G, G, G, G):
            room = 66 - hp - at - de - sa - sd
            if room < 0: continue
            for spv in (x for x in G if x <= min(32, room)):
                e = [hp, at, de, sa, sd, spv]
                key = (score(T, e), -sum(abs(x - y) for x, y in zip(e, base)))
                if bkey is None or key > bkey: best, bkey = e, key
        left = 66 - sum(best)                                                   # what the grid leaves (2 at most a stat) goes where Smogon's has it
        for i in sorted(range(6), key=lambda i: -base[i]):
            add = min(left, 32 - best[i]); best[i] += add; left -= add
            if not left: break
        Tt, Nt = tables(test); tot = sum(Nt.values())
        out[f'{toid(sp)}|{nat}'] = best
        report.append({'species': sp, 'nature': nat, 'evidence': len(train), 'smogon': base, 'fitted': best,
                       'train_fit': [round(score(T, base) / max(1, sum(N.values())), 3), round(score(T, best) / max(1, sum(N.values())), 3)],
                       'held_out_fit': [round(score(Tt, base) / max(1, tot), 3), round(score(Tt, best) / max(1, tot), 3)] if tot else None, 'held_out_n': tot})
    json.dump({'spreads': out, 'report': report}, open(os.path.join(C.HERE, 'default_spreads.json'), 'w'), indent=0)
    ho = [r for r in report if r['held_out_fit'] and r['held_out_n'] >= 20]
    print(f"{len(report)} species+natures fitted; held out (>= 20 pieces of evidence): Smogon's spread fits {sum(r['held_out_fit'][0] * r['held_out_n'] for r in ho) / max(1, sum(r['held_out_n'] for r in ho)):.3f}, the fitted one {sum(r['held_out_fit'][1] * r['held_out_n'] for r in ho) / max(1, sum(r['held_out_n'] for r in ho)):.3f}")
    for r in report[:25]: print(f"  {r['species']:18s} {r['nature']:8s} n={r['evidence']:5d}  Smogon {r['smogon']} -> {r['fitted']}  held out {r['held_out_fit']} (n={r['held_out_n']})")
OFF = {'tp': 0, 'ts': 81, 'dp': 162, 'ds': 171, 'spe': 180}
MINN = int(os.environ.get('POPFIT_MINN', 40))                           # training Pokemon a species and nature needs (lower only for tests)
nearest = lambda v: min(G, key=lambda g: abs(g - v))
def cell(k, c):
    gi = G.index; return OFF[k] + (gi(c[0]) * 9 + gi(c[1]) if k in ('tp', 'ts') else gi(c[0]))
def best_spread(T, base, eps=1e-6):
    """the spread (66 points, at most 32 a stat, on the grid) that fits the most of evidence table T (189 cells), ties to the closest to base:
    for each HP, a knapsack over Atk, Def, Sp. Atk, Sp. Def and Speed in steps of 4"""
    best = None
    for h in G:
        hi = G.index(h)
        opts = [[(T[OFF['dp'] + j] - eps * abs(x - base[1]), x) for j, x in enumerate(G)],
                [(T[OFF['tp'] + hi * 9 + j] - eps * abs(x - base[2]), x) for j, x in enumerate(G)],
                [(T[OFF['ds'] + j] - eps * abs(x - base[3]), x) for j, x in enumerate(G)],
                [(T[OFF['ts'] + hi * 9 + j] - eps * abs(x - base[4]), x) for j, x in enumerate(G)],
                [(T[OFF['spe'] + j] - eps * abs(x - base[5]), x) for j, x in enumerate(G)]]
        dp = {0: (0.0, [])}
        for o in opts:
            nd = {}
            for used, (v, xs) in dp.items():
                for val, x in o:
                    u = used + x
                    if h + u > 66: continue
                    if u not in nd or v + val > nd[u][0]: nd[u] = (v + val, xs + [x])
            dp = nd
        v, xs = max(dp.values()); v -= eps * abs(h - base[0])
        if best is None or v > best[0]: best = (v, [h] + xs)
    return best[1]
def ctx(B=20.0, F=4.0, kappa=2.0, nq=6000, minsh=3):
    """spreads by team core and set (the user, 2026-10-12: like setguess.py, for spreads): each held-out player's Pokemon (game, side,
    species) gets the spread that fits the most training evidence of its species and nature, each piece counted B^(teammates shared - 5)
    (teams sharing at least minsh), F times more when the set (item and moves) is the same, plus kappa pieces' worth of the species-and-
    nature whole; scored by how much of that Pokemon's own evidence (hits taken and given, turn order) it fits, against Smogon's spread and
    the species-and-nature fit"""
    import glob
    inst = collections.defaultdict(lambda: {'T': collections.Counter(), 'N': 0})
    for f in glob.glob(os.path.join(OUT, 'obs_*.jsonl')):
        for l in open(f):
            r = json.loads(l)
            if 'mates' not in r: continue
            x = inst[(r['sp'], r['nat'], r['game'], r['side'])]; x.update(hold=r['hold'], mates=frozenset(r['mates']), set=(r['item'], tuple(r['moves'])))
            for c in r['fit']: x['T'][cell(r['k'], c)] += 1
            x['N'] += 1
    by = collections.defaultdict(list)
    for (sp, nat, g, sd), x in inst.items(): by[(sp, nat)].append(x)
    rng = random.Random(7); tot = [0.0, 0.0, 0.0, 0]; per = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0])
    queries = [(k, x) for k, xs in by.items() for x in xs if x['hold']]; rng.shuffle(queries)
    pre = {}
    for (sp, nat), q in queries[:int(nq)]:
        if (sp, nat) not in pre:
            tr = [x for x in by[(sp, nat)] if not x['hold']]
            if len(tr) < MINN: pre[(sp, nat)] = None; continue
            Tg = [0.0] * 189; post = collections.defaultdict(list)
            for i, x in enumerate(tr):
                for c, v in x['T'].items(): Tg[c] += v
                for m in x['mates']: post[m].append(i)
            Ng = sum(x['N'] for x in tr); base = default(sp, nat) or [2, 0, 0, 32, 0, 32]
            pre[(sp, nat)] = (tr, post, [v / Ng for v in Tg], base, best_spread(Tg, base))
        P_ = pre[(sp, nat)]
        if not P_: continue
        tr, post, Tgn, base, glob_best = P_
        shared = collections.Counter(i for m in q['mates'] for i in post.get(m, ()))
        Tc = [kappa * v for v in Tgn]
        for i, sh in shared.items():
            if sh < minsh: continue
            w = B ** (sh - 5) * (F if tr[i]['set'] == q['set'] else 1.0)
            for c, v in tr[i]['T'].items(): Tc[c] += w * v
        e = best_spread(Tc, base); T = q['T']
        score = lambda s_: (T.get(OFF['tp'] + G.index(nearest(s_[0])) * 9 + G.index(nearest(s_[2])), 0) + T.get(OFF['ts'] + G.index(nearest(s_[0])) * 9 + G.index(nearest(s_[4])), 0)
                            + T.get(OFF['dp'] + G.index(nearest(s_[1])), 0) + T.get(OFF['ds'] + G.index(nearest(s_[3])), 0) + T.get(OFF['spe'] + G.index(nearest(s_[5])), 0))
        for acc in (tot, per[sp]):
            acc[0] += score(base); acc[1] += score(glob_best); acc[2] += score(e); acc[3] += q['N']
    print(f"held-out evidence fitted ({tot[3]} pieces, {min(int(nq), len(queries))} Pokemon): Smogon's spread {tot[0] / max(1, tot[3]):.3f}, "
          f"species and nature fit {tot[1] / max(1, tot[3]):.3f}, by team core and set {tot[2] / max(1, tot[3]):.3f}  (B {B}, F {F}, kappa {kappa})")
    for sp, v in sorted(per.items(), key=lambda kv: -kv[1][3])[:15]: print(f"  {sp:18s} {v[3]:5d}  {v[0] / v[3]:.3f}  {v[1] / v[3]:.3f}  {v[2] / v[3]:.3f}")
    return tot
if __name__ == '__main__':
    P.own(); R.BATON_PASS = R.MEGA_ABIL = True
    a = sys.argv[1:]
    if a and a[0] == 'collect':
        k, n = map(int, a[1].split('/')); collect(k, n, next((int(x[6:]) for x in a if x.startswith('games=')), None))
    elif a and a[0] == 'fit': fit()
    elif a and a[0] == 'ctx': ctx(*(float(x) for x in a[1:4]))
    else: sys.exit(__doc__)
