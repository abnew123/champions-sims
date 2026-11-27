"""Best teams by the matchup predictor (the user, 2026-11-27: separate "what the ladder settles to" from "what the best teams are,
on ladder and in pro play"). This is the second question: which sixes score highest against a given field.

Field (one vote per player, the last DAYS days of the regulation's data): the online-tournament field. The ladder field (--ladder)
is off by default: validated on the following week, neither this ranking nor a six's own record picked the ladder winners
(Nov 27: correlation -0.08 / -0.06 and -0.01 / -0.25); on tournament results the predictor's top fifth won 55.0% against 52.7%
for all, about as well as their own earlier record (54.1-54.9%), with a weaker correlation (0.03-0.14 vs 0.19-0.24). Candidates: every six seen in the last 2 x DAYS days by
2+ players, plus one-Pokemon swaps of the best 150 of them against each field (each species' most common recent set; species and
item clauses kept). Each candidate's score is its predicted game win share against the field. Bootstrap refits (resampled
matches) give a spread, and the ranking uses mean - 1 sd, so a team with thin evidence does not win on noise.
  teamsearch/bin/teamsearch-py predictor/best.py [reg=M-C] [days=14] [--ladder]   -> predictor/best_<reg>.json and .txt
  teamsearch/bin/teamsearch-py predictor/best.py validate [reg] [ladder|online]
"""
import os, sys, json, time, random, hashlib, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M, meta as X
L = X.L
BOOT = int(os.environ.get('TS_BEST_BOOT', 8)); TOPK = 150; NSWAP = 60; SHOW = 15; PER_BASE = 2
USE = ('sp', 'tok', 'attr', 'pair', 'tpair', 'pl', 'rat')   # ladder and tournament games pooled: own tournament weights (sp_on, tok_on)
                                                           # did no better on held-out games (evaluate.py online, Nov 27)

LADDER = '--ladder' in sys.argv     # the ladder-field list is off by default: no out-of-sample signal there (validate, Nov 27)

def lambdas():
    lam = json.load(open(os.path.join(M.HERE, 'lambdas.json')))
    p = os.path.join(M.HERE, 'lambdas_online.json')
    return lam | (json.load(open(p)) if os.path.exists(p) else {})

def recent_sets(meta, reg, lo, hi):
    c = collections.defaultdict(collections.Counter)
    for g in meta:
        if g['reg'] != reg or not (lo <= X.day(g['t']) <= hi): continue
        for sets in (g['sets1'], g['sets2']):
            for s in sets or []:
                c[M.idf(s['species'])][(s['species'], s['item'], s['ability'], s.get('nature', ''), tuple(sorted(s['moves'])))] += 1
    return {sp: [dict(species=k[0], item=k[1], ability=k[2], nature=k[3], moves=list(k[4])) for k, _ in cnt.most_common(5)] for sp, cnt in c.items()}

def field(meta, rows, reg, lo, hi, src):
    sd = X.sides(meta, rows, reg, lo, hi, src)
    if not sd: return None
    keys, groups, F, x, _ = X.pool(sd, min_players=1)
    return dict(keys=keys, groups=groups, x=x, players=len({p for p, *_ in sd}), sheets=len(sd))

def candidates(meta, rows, reg, lo, hi):
    """seen sixes (2+ players): key -> (group of Teams, a representative sheet as sets, n players)"""
    by = collections.defaultdict(list); pl = collections.defaultdict(set)
    for g, (A, B, *_) in zip(meta, rows):
        if g['reg'] != reg or not (lo <= X.day(g['t']) <= hi): continue
        for p, T, sets in ((g['p1'], A, g['sets1']), (g['p2'], B, g['sets2'])):
            if sets: k = tuple(sorted(T.sp)); by[k].append((T, sets)); pl[k].add(p)
    return {k: ([T for T, _ in v], collections.Counter(json.dumps(s, sort_keys=True) for _, s in v).most_common(1)[0][0], len(pl[k]))
            for k, v in by.items() if len(pl[k]) >= 2}

MEGA = set(M.MEGA_OF)
megas = lambda sets: sum(M.idf(s['item']) in MEGA for s in sets)

def swaps(sets, pool_sets, top_species, together):
    """one-Pokemon swaps of a sheet: each slot replaced by each top species' most common set that keeps the species and item
    clauses, at most two Mega Stones (as real sheets: the model adds pieces up and knows nothing of three), and only a species
    that real sheets have paired with at least 3 of the 5 kept (so the model is not asked about combinations it has never seen)"""
    out = []
    have = {M.idf(s['species']) for s in sets}
    for i, s in enumerate(sets):
        keep = [M.idf(x['species']) for j, x in enumerate(sets) if j != i]
        items = {x['item'] for j, x in enumerate(sets) if j != i and x['item']}
        for sp in top_species:
            if sp in have or sum(together[(min(sp, k), max(sp, k))] >= 5 for k in keep) < 3: continue
            new = next((c for c in pool_sets.get(sp, []) if not c['item'] or c['item'] not in items), None)
            if new:
                ns = sets[:i] + [new] + sets[i + 1:]
                if megas(ns) <= 2: out.append((ns, f"{s['species']} -> {new['species']}"))
    return out

def team_of(sets): return M.Team([s['species'] for s in sets], sets)

FOLDS = 5
def fold_of(key): return int(hashlib.md5('|'.join(key).encode()).hexdigest(), 16) % FOLDS

def crossfit(rows, y, lam, use, keys, groups, F, ctx, skip=None):
    """each seen six scored by a model fitted without any game it played (five folds by six), so a six's own results do not
    flatter it; skip: game indices never used for fitting (a later holdout)"""
    sc = np.zeros(len(keys)); kf = np.array([fold_of(k) for k in keys])
    gk = [(fold_of(tuple(sorted(r[0].sp))), fold_of(tuple(sorted(r[1].sp)))) for r in rows]
    for f in range(FOLDS):
        idx = [i for i, (a, b) in enumerate(gk) if a != f and b != f and not (skip is not None and skip[i])]
        mf = M.Model(lam, use=use).fit([rows[i] for i in idx], y[idx]); sel = np.where(kf == f)[0]
        if len(sel): sc[sel] = score(mf, [groups[i] for i in sel], F, ctx)
    return sc

def score(m, cand_groups, F, ctx):
    A = M.Pool(m, cand_groups, ctx); B = M.Pool(m, F['groups'], ctx)
    return (1 / (1 + np.exp(-A.cross(B)))) @ F['x']

def main(reg='M-C', days=14):
    t0 = time.time()
    rows, y, meta = M.load(lambda g: g['src'] in ('ladder', 'online'))
    last = max(X.day(g['t']) for g in meta if g['reg'] == reg)
    d = lambda n: time.strftime('%Y-%m-%d', time.localtime(time.mktime(time.strptime(last, '%Y-%m-%d')) - 86400 * n))
    lo, lo2 = d(days - 1), d(2 * days - 1)
    use = USE
    lam = lambdas(); m = M.Model(lam, use=use).fit(rows, y)
    fields = {k: f for k, f in (('ladder', field(meta, rows, reg, lo, last, 'ladder') if LADDER else None), ('tournaments', field(meta, rows, reg, lo, last, 'online'))) if f}
    C = candidates(meta, rows, reg, lo2, last); keys = list(C)
    psets = recent_sets(meta, reg, lo2, last)
    use_sp = collections.Counter(M.idf(s['species']) for g in meta if g['reg'] == reg and lo <= X.day(g['t']) <= last for v in (g['sets1'], g['sets2']) for s in (v or []))
    top_species = [s for s, _ in use_sp.most_common(NSWAP)]
    together = collections.Counter()
    for g in meta:
        if g['reg'] == reg and lo2 <= X.day(g['t']) <= last:
            for v in (g['six1'], g['six2']):
                ids = sorted({M.idf(x) for x in v})
                for a in range(len(ids)):
                    for b in range(a + 1, len(ids)): together[(ids[a], ids[b])] += 1
    M.say(f"best {reg}: data to {last}; fields: " + ', '.join(f"{k} {f['players']} players / {f['sheets']} sheets" for k, f in fields.items())
          + f"; {len(keys)} sixes seen by 2+ players since {lo2}")
    out = {}
    for name, F in fields.items():
        ctx = int(name == 'tournaments')
        s_in = score(m, [C[k][0] for k in keys], F, ctx)                     # in-sample (full fit), the base for swap deltas
        s0 = crossfit(rows, y, lam, use, keys, [C[k][0] for k in keys], F, ctx)
        base = dict(zip(keys, zip(s0, s_in)))
        best = [keys[i] for i in np.argsort(-s0)[:TOPK]]
        cand = [(k, json.loads(C[k][1]), C[k][0], None, k) for k in keys]
        seen = {tuple(sorted(M.idf(x['species']) for x in json.loads(C[k][1]))) for k in keys}
        for k in best:
            for sets, how in swaps(json.loads(C[k][1]), psets, top_species, together):
                key = tuple(sorted(M.idf(x['species']) for x in sets))
                if key in seen: continue
                seen.add(key); cand.append((key, sets, [team_of(sets)], how, k))
        full = score(m, [c[2] for c in cand], F, ctx)
        sc = np.array([base[c[4]][0] + (full[i] - base[c[4]][1]) for i, c in enumerate(cand)])   # out-of-sample base + the swap's change
        top = list(np.argsort(-np.where([c[3] is None for c in cand], sc, -1))[:300]) + list(np.argsort(-np.where([c[3] is not None for c in cand], sc, -1))[:300])
        out[name] = dict(cand=[cand[i] for i in top], sc=sc[top], full=full[top], boot=[])
        M.say(f"  {name}: {len(cand)} candidates ({len(cand) - len(keys)} one-swap variants); best seen six {100 * s0.max():.1f}% out of sample"
              f" ({100 * s_in.max():.1f}% in sample), median {100 * np.median(s0):.1f}%; best variant {100 * sc[top[300]]:.1f}%")
    # bootstrap refits over matches
    mid = [g.get('match') or g['id'] for g in meta]; groups = collections.defaultdict(list)
    for i, k in enumerate(mid): groups[k].append(i)
    gk = list(groups); rng = random.Random(7)
    for b in range(BOOT):
        idx = [i for k in (gk[rng.randrange(len(gk))] for _ in range(len(gk))) for i in groups[k]]
        mb = M.Model(lam, use=use).fit([rows[i] for i in idx], y[idx])
        for name, F in fields.items():
            o = out[name]; o['boot'].append(o['sc'] + score(mb, [c[2] for c in o['cand']], F, int(name == 'tournaments')) - o['full'])
        M.say(f"  score (bootstrap refits): {b + 1}/{BOOT} fits, {int((time.time() - t0) / 60)} min")
    J, txt = dict(reg=reg, data_to=last, days=days, fields={k: dict(players=f['players'], sheets=f['sheets']) for k, f in fields.items()}), []
    rec = collections.defaultdict(lambda: [0, 0])
    for g, (A, B, *_) in zip(meta, rows):
        if g['reg'] == reg and lo2 <= X.day(g['t']) <= last:
            for T, w in ((A, g['win']), (B, 1 - g['win'])): r = rec[tuple(sorted(T.sp))]; r[0] += w; r[1] += 1
    for name in fields:
        Bm = np.array(out[name]['boot']); mu, sd = Bm.mean(0), Bm.std(0); lcb = mu - sd; J[name] = {}
        txt.append(f"\n{name} field ({J['fields'][name]['players']} players, {lo} to {last}): predicted game win share against it (seen sixes scored by models that"
                   f" never saw their games; a swap adds the change it makes), mean ± sd over {BOOT} refits")
        for part, keep in (('seen sixes (2+ players since ' + lo2 + ')', lambda c: c[3] is None), ('one-swap variants (speculative: never played as a six)', lambda c: c[3] is not None)):
            idx, per = [], collections.Counter()                        # at most PER_BASE variants of one base six (else one weak
            for i in np.argsort(-lcb):                                  # member swapped for anything fills the list)
                c = out[name]['cand'][i]
                if keep(c) and (c[3] is None or per[c[4]] < PER_BASE): idx.append(i); per[c[4]] += c[3] is not None
                if len(idx) >= SHOW: break
            J[name][part] = []
            txt.append(f"  {part}:")
            for r, i in enumerate(idx, 1):
                key, sets, _, how, _ = out[name]["cand"][i]; w, n = rec.get(key, (0, 0))
                formes = [L.battle_forme(s['species'], s['item']) for s in sets]
                J[name][part].append(dict(rank=r, formes=formes, sets=sets, mean=float(mu[i]), sd=float(sd[i]), swap=how, games=n, wins=w))
                txt.append(f"    {r:2d}. {100 * mu[i]:.1f}% ± {100 * sd[i]:.1f}  {' / '.join(formes)}" + (f"   [swap: {how}]" if how else '')
                           + (f"   real: {100 * w / n:.0f}% of {n} games" if n else ''))
    json.dump(J, open(os.path.join(M.HERE, f'best_{reg}.json'), 'w'), indent=1)
    open(os.path.join(M.HERE, f'best_{reg}.txt'), 'w').write(f"Best teams by the matchup predictor, {reg}, data to {last}\n" + '\n'.join(txt) + '\n')
    M.say(f"best {reg} done ({int((time.time() - t0) / 60)} min)")

def validate(reg='M-C', days=14, hold=7, src='ladder'):
    """does the ranking work? Score the sixes seen before the last `hold` days (out of sample, as main) against the field before
    then, and compare with how those sixes did in the last `hold` days (sixes with 15+ games there); against their own earlier
    record (shrunk toward 50%) as the plain alternative"""
    rows, y, meta = M.load(lambda g: g['src'] in ('ladder', 'online'))
    last = max(X.day(g['t']) for g in meta if g['reg'] == reg)
    d = lambda n: time.strftime('%Y-%m-%d', time.localtime(time.mktime(time.strptime(last, '%Y-%m-%d')) - 86400 * n))
    cut = d(hold); lo, lo2 = d(hold + days - 1), d(hold + 2 * days - 1)
    use = USE
    lam = lambdas(); later = np.array([X.day(g['t']) > cut for g in meta])
    F = field(meta, rows, reg, lo, cut, src); C = candidates(meta, rows, reg, lo2, cut); keys = list(C)
    pred = crossfit(rows, y, lam, use, keys, [C[k][0] for k in keys], F, int(src == 'online'), skip=later)
    past, fut = collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0])
    for g, (A, B, *_), lt in zip(meta, rows, later):
        if g['reg'] != reg or (src and g['src'] != src): continue
        if not lt and X.day(g['t']) < lo2: continue
        for T, w in ((A, g['win']), (B, 1 - g['win'])):
            r = (fut if lt else past)[tuple(sorted(T.sp))]; r[0] += w; r[1] += 1
    sel = [i for i, k in enumerate(keys) if fut[k][1] >= 15]
    if not sel: M.say(f"best validate {reg}: no six with 15+ games after {cut}"); return
    real = np.array([fut[keys[i]][0] / fut[keys[i]][1] for i in sel]); n = np.array([fut[keys[i]][1] for i in sel])
    p = pred[sel]; e = np.array([(past[keys[i]][0] + 10) / (past[keys[i]][1] + 20) for i in sel])
    wc = lambda a, b: float(np.cov(a, b, aweights=n)[0, 1] / np.sqrt(np.cov(a, aweights=n) * np.cov(b, aweights=n)))
    top = np.argsort(-p)[:max(5, len(sel) // 5)]; topE = np.argsort(-e)[:max(5, len(sel) // 5)]
    msg = (f"best validate {reg} ({src}): {len(sel)} sixes with 15+ games after {cut} ({int(n.sum())} games); correlation with their real win rate there"
           f" (weighted by games): predictor {wc(p, real):.2f}, own earlier record {wc(e, real):.2f}; the top fifth by the predictor won {100 * np.average(real[top], weights=n[top]):.1f}%,"
           f" by earlier record {100 * np.average(real[topE], weights=n[topE]):.1f}%, all {100 * np.average(real, weights=n):.1f}%")
    M.say(msg); print(msg)

if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if a[:1] == ['validate']: validate(*(a[1:2] or ['M-C']), src=(a[2] if len(a) > 2 else 'ladder'))
    else: main(*(a[:1] or ['M-C']), *[int(x) for x in a[1:2]])
