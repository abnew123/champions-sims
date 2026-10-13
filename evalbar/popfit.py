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
Nothing reads default_spreads.json yet: it is for review first."""
import os, sys, json, time, zlib, random, itertools, subprocess, collections
import common as C, live as L, replay as R, spreads as SPR, procs as P, mega_check as MC
OUT = os.path.join(C.HERE, 'out', 'popfit'); G = list(range(0, 33, 4)); CAP = 260     # per species, nature and kind, over all shares
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
            plan.append((sp, nat, kind, cells, m['pct'])); count[(sp, nat, kind)] += 1
    if queries:
        json.dump(queries, open(qf, 'w'))
        subprocess.run([P.exe('node'), os.path.join(C.HERE, 'damage.js'), qf, of], cwd=os.path.join(C.MAIN, 'pssim'), check=True, capture_output=True)
        res = iter(json.load(open(of)))
        for sp, nat, kind, cells, pct in plan:
            rs = [next(res) for _ in cells]
            if any(r is None or r.get('lo') is None for r in rs): continue
            fit = [list(c) for c, r in zip(cells, rs) if SPR.damage_fits({'pct': tuple(pct), 'atleast': False}, r, 0)]
            recs.append({'game': rid, 'hold': hold, 'k': kind, 'sp': sp, 'nat': nat, 'fit': fit})
    # turn order: each side in turn as the 'known' one at its Smogon default, the other's Speed on the grid
    gp = R.parse(log); sheets = gp['sheets']
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
            recs.append({'game': rid, 'hold': hold, 'k': 'spe', 'sp': sp, 'nat': nat, 'fit': fit})
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
if __name__ == '__main__':
    P.own(); R.BATON_PASS = R.MEGA_ABIL = True
    a = sys.argv[1:]
    if a and a[0] == 'collect':
        k, n = map(int, a[1].split('/')); collect(k, n, next((int(x[6:]) for x in a if x.startswith('games=')), None))
    elif a and a[0] == 'fit': fit()
    else: sys.exit(__doc__)
