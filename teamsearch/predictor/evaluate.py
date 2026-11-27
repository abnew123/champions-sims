"""How well the matchup predictor calls real games it was not fitted on.
  0. tune: ridge strength per block on team-only log loss (fit before the 60% mark of M-C, validate on 60-80%) -> lambdas.json
  1. ladder: fit on M-B plus the first 80% of M-C ladder games (by time), score the last 20%; each feature block added in turn
  2. regionals: fit on every ladder game, score the 14,811 real M-C regional matches (open team sheets, Bo3) beside the battle
     sim's scores on the same matches (regsim/report.json)
  3. new species: fit on M-B only, score M-C ladder games, split by whether they hold species M-B never had (the M-D situation)
  4. online: what the online-tournament games (Limitless, fetch_tours.py) add. Ridge for the tournament blocks (sp_on, tok_on:
     fit before the 60% mark, validate on M-C tournament games at 60-80%) -> lambdas_online.json; the last 20% of ladder and
     tournament games under three fits (ladder games only / tournament games pooled in / pooled with their own weights); the
     regionals with every game, and with only the games played before each event (what the predictor could have said then)
Team-only scores leave the rating gap out at prediction time (the model's use is team against team).
  teamsearch/bin/teamsearch-py predictor/evaluate.py [ladder|regionals|newspecies|all]  -> predictor/eval.json, lines in predictor.log
"""
import os, sys, json, math, collections, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M
HERE = M.HERE; ROOT = M.ROOT
OUT = os.path.join(HERE, 'eval.json')
OFF = 1e12
BO3 = lambda p: p * p * (3 - 2 * p)

GRID = (30.0, 100.0, 300.0, 1000.0, 3000.0, 10000.0, 30000.0)
TUNE = os.path.join(HERE, 'lambdas.json')
FULL = ('sp', 'tok', 'attr', 'pair', 'tpair', 'pl', 'rat')

def variants(lam):
    """each block added in turn, at the tuned ridge strengths (the player and rating blocks are skill controls, in every fit)"""
    ctl = ('pl', 'rat')
    return [('skill controls only', ctl), ('species', ('sp',) + ctl), ('+ set details', ('sp', 'tok') + ctl),
            ('+ types and stats', ('sp', 'tok', 'attr') + ctl), ('+ species pairs', ('sp', 'tok', 'attr', 'pair') + ctl),
            ('+ type pairs (full)', FULL)]

def score(z, y):
    return dict(n=len(y), logloss=M.logloss(z, y), acc=float(np.mean((z > 0) == (y == 1))))

def no_rat(rows): return [(A, B, None) for A, B, *_ in rows]

def temper(z, y):
    """the scale c minimising log loss of c * z (a calibration fitted on validation games)"""
    c = 1.0
    for _ in range(50):
        p = 1 / (1 + np.exp(-c * z)); g = np.sum(z * (p - y)); h = np.sum(z * z * p * (1 - p)) + 1e-9; c -= g / h
    return float(c)

def split(meta):
    tc = sorted(g['t'] for g in meta if g['reg'] == 'M-C'); c60, c80 = tc[int(0.6 * len(tc))], tc[int(0.8 * len(tc))]
    tr = [i for i, g in enumerate(meta) if g['reg'] == 'M-B' or g['t'] < c60]
    va = [i for i, g in enumerate(meta) if g['reg'] == 'M-C' and c60 <= g['t'] < c80]
    te = [i for i, g in enumerate(meta) if g['reg'] == 'M-C' and g['t'] >= c80]
    return tr, va, te, c60, c80

def tune(rows, y, meta):
    """ridge strength per block by coordinate search on team-only log loss: fit on M-B + M-C before the 60% mark, score 60-80%"""
    tr, va, _, c60, c80 = split(meta)
    lam = dict(M.Model().lam); R, V = [rows[i] for i in tr], no_rat([rows[i] for i in va]); best = None
    M.say(f"tune: fit on {len(tr)} games, validate on {len(va)} M-C games ({time.strftime('%b %d', time.localtime(c60))} - {time.strftime('%b %d', time.localtime(c80))})")
    t0, k, nfit = time.time(), 0, 6 * len(GRID)
    for b in ('sp', 'tok', 'attr', 'pair', 'tpair', 'pl'):
        res = {}
        for v in GRID:
            m = M.Model(lam | {b: v}, use=FULL).fit(R, y[tr]); res[v] = M.logloss(m.logit(V), y[va]); k += 1
            M.say(f"  score (ridge tuning): {k}/{nfit} fits, {int((time.time() - t0) / 60)} min")
        lam[b] = min(res, key=res.get); best = res[lam[b]]
        M.say(f"  {b:6s} ridge {lam[b]:g}: validation log loss {best:.4f}   (" + ', '.join(f"{k:g} {x:.4f}" for k, x in res.items()) + ")")
    json.dump(lam, open(TUNE, 'w'), indent=1)
    return lam

def lambdas(rows, y, meta):
    return json.load(open(TUNE)) if os.path.exists(TUNE) else tune(rows, y, meta)

def ladder(J):
    rows, y, meta = M.load(lambda g: g['src'] == 'ladder'); lam = lambdas(rows, y, meta)
    tr, va, te, c60, c80 = split(meta); fit = tr + va
    rated = np.array([rows[i][2] is not None for i in te])
    M.say(f"evaluate ladder: fit on {len(fit)} games, score the last {len(te)} M-C games ({rated.sum()} rated), from {time.strftime('%b %d', time.localtime(c80))}")
    J['ladder'] = dict(lambdas=lam)
    for name, use in variants(lam):
        t0 = time.time(); m = M.Model(lam, use=use).fit([rows[i] for i in fit], y[fit])
        yt = y[te]; zt = m.logit(no_rat([rows[i] for i in te])); zr = m.logit([rows[i][:3] for i in te])
        s = dict(team=score(zt, yt), with_rating_rated=score(zr[rated], yt[rated]), sec=round(time.time() - t0))
        J['ladder'][name] = s
        M.say(f"  {name:22s} team only: log loss {s['team']['logloss']:.4f}, favourite won {100 * s['team']['acc']:.1f}%   rated games with the gap:"
              f" {s['with_rating_rated']['logloss']:.4f} / {100 * s['with_rating_rated']['acc']:.1f}%   ({s['sec']} s)")

def regional_rows():
    import importlib.util
    sys.path.insert(0, os.path.join(ROOT, 'teamsearch')); import sets_lib as L
    R = json.load(open(os.path.join(ROOT, 'regionals', 'regional_sets.json'))); F = json.load(open(os.path.join(ROOT, 'regionals', 'field_sets.json')))
    sheets = {k: [L.normalize(dict(s)) for s in v] for k, v in {**R, **F}.items() if len(v) == 6}
    rows, y, meta = [], [], []
    for l in open(os.path.join(ROOT, 'teamsearch', 'regsim', 'games.jsonl')):
        d = json.loads(l); a, b = f"{d['ev']}|{d['p1']}", f"{d['ev']}|{d['p2']}"
        if d['winner'] not in (d['p1'], d['p2']) or a not in sheets or b not in sheets: continue
        A = M.Team([s['species'] for s in sheets[a]], sheets[a]); B = M.Team([s['species'] for s in sheets[b]], sheets[b])
        rows.append((A, B, None)); y.append(int(d['winner'] == d['p1'])); meta.append(dict(d, a=a, b=b))
    return rows, np.array(y, dtype=float), meta

def match_score(z, ry):
    """game log-odds -> Bo3 match log loss, favourite hit rate and the slope of real results on the predicted match log-odds"""
    p = 1 / (1 + np.exp(-z)); q = np.clip(BO3(p), 1e-9, 1 - 1e-9); zq = np.log(q / (1 - q)); s = score(zq, ry); b = 0.0
    for _ in range(30):
        pp = 1 / (1 + np.exp(-b * zq)); b += np.sum(zq * (ry - pp)) / max(np.sum(zq * zq * pp * (1 - pp)), 1e-9)
    s['slope'] = float(b); return s

TUNE_ON = os.path.join(HERE, 'lambdas_online.json')
GRID_ON = (300.0, 1000.0, 3000.0, 10000.0, 30000.0)
ON = ('sp_on', 'tok_on')
EVENTS = {'Baltimore': '2026-09-18', 'Brisbane': '2026-09-26', 'Frankfurt': '2026-09-26', 'Recife': '2026-10-03', 'Louisville': '2026-10-09'}

def as_ctx(rows, c): return [(A, B, None, None, c) for A, B, *_ in rows]

def online(J):
    import calendar
    rows, y, meta = M.load(lambda g: g['src'] in ('ladder', 'online')); lam = json.load(open(TUNE))
    I = lambda f: [i for i, g in enumerate(meta) if f(g)]
    lad = lambda g: g['src'] == 'ladder'; mc = lambda g: g['reg'] == 'M-C'
    tc = sorted(g['t'] for g in meta if mc(g) and lad(g)); c60, c80 = tc[int(0.6 * len(tc))], tc[int(0.8 * len(tc))]
    tr_a = I(lambda g: not mc(g) or g['t'] < c60)
    va_l = I(lambda g: mc(g) and lad(g) and c60 <= g['t'] < c80); va_o = I(lambda g: mc(g) and not lad(g) and c60 <= g['t'] < c80)
    te_l = I(lambda g: mc(g) and lad(g) and g['t'] >= c80); te_o = I(lambda g: mc(g) and not lad(g) and g['t'] >= c80)
    rr, ry, rmeta = regional_rows()
    nfit = (0 if os.path.exists(TUNE_ON) else 2 * len(GRID_ON)) + 3 + 3 + 3 * len(EVENTS); k = [0]; t0 = time.time()
    def fit(idx, use, lm):
        m = M.Model(lm, use=use).fit([rows[i] for i in idx], y[idx]); k[0] += 1
        M.say(f"  score (tournament test): {k[0]}/{nfit} fits, {int((time.time() - t0) / 60)} min"); return m
    day = lambda t: time.strftime('%b %d', time.gmtime(t))
    M.say(f"evaluate online: {len(rows)} games ({sum(1 for g in meta if not lad(g))} from online tournaments); split at {day(c60)} / {day(c80)}")
    J['online'] = dict(split=[c60, c80])
    # 1. ridge for the tournament blocks
    if os.path.exists(TUNE_ON): lon = json.load(open(TUNE_ON))
    else:
        lon = dict(sp_on=1000.0, tok_on=1000.0); V = as_ctx([rows[i] for i in va_o], 1)
        for b in ON:
            res = {v: M.logloss(fit(tr_a, FULL + ON, lam | lon | {b: v}).logit(V), y[va_o]) for v in GRID_ON}
            lon[b] = min(res, key=res.get)
            M.say(f"  {b:6s} ridge {lon[b]:g}: tournament validation log loss {res[lon[b]]:.4f}   (" + ', '.join(f"{a:g} {x:.4f}" for a, x in res.items()) + ")")
        json.dump(lon, open(TUNE_ON, 'w'), indent=1)
    J['online']['lambdas'] = lon; L2 = lam | lon
    # 2. the last 20% of M-C, ladder and tournament games
    fits = [('ladder games only', [i for i in tr_a + va_l + va_o if lad(meta[i])], FULL),
            ('+ tournament games, pooled', tr_a + va_l + va_o, FULL), ('+ tournament games, own weights', tr_a + va_l + va_o, FULL + ON)]
    M.say(f"  last 20%: {len(te_l)} ladder games, {len(te_o)} tournament games, from {day(c80)}")
    J['online']['holdout'] = {}
    for name, idx, use in fits:
        m = fit(idx, use, L2); on = 'sp_on' in use
        sl = score(m.logit(as_ctx([rows[i] for i in te_l], 0)), y[te_l]); so = score(m.logit(as_ctx([rows[i] for i in te_o], int(on))), y[te_o])
        J['online']['holdout'][name] = dict(ladder=sl, tournament=so)
        M.say(f"    {name:32s} ladder {sl['logloss']:.4f} / {100 * sl['acc']:.1f}%   tournament {so['logloss']:.4f} / {100 * so['acc']:.1f}%")
    # 3. regionals: with every game (as test 2), then with only the games before each event
    J['online']['regionals_all'] = {}
    M.say(f"  regionals, fitted on every game ({len(rr)} matches; the sim: 0.7212 raw, 0.6862 with a hindsight shrink, 54.7%)")
    for name, f, use in (('ladder games only', lad, FULL), ('+ tournament games, pooled', None, FULL), ('+ tournament games, own weights', None, FULL + ON)):
        m = fit(I(f) if f else list(range(len(rows))), use, L2)
        for c in ((0, 1) if 'sp_on' in use else (0,)):
            s = match_score(m.logit(as_ctx(rr, c)), ry); nm = name + (', as a tournament' if c else ''); J['online']['regionals_all'][nm] = s
            M.say(f"    {nm:46s} {s['logloss']:.4f} / {100 * s['acc']:.1f}%, slope {s['slope']:.2f}")
    ev = np.array([d['ev'] for d in rmeta]); zs = collections.defaultdict(lambda: np.zeros(len(rr)))
    for e, d0 in EVENTS.items():
        t_e = calendar.timegm(time.strptime(d0, '%Y-%m-%d')); sel = np.where(ev == e)[0]; R = [rr[i] for i in sel]
        before = lambda g: g['t'] < t_e
        nl = sum(1 for g in meta if before(g) and mc(g) and lad(g)); no = sum(1 for g in meta if before(g) and mc(g) and not lad(g))
        msg = []
        for name, f, use in (('ladder games only', lambda g: lad(g) and before(g), FULL), ('+ tournament games, pooled', before, FULL),
                             ('+ tournament games, own weights', before, FULL + ON)):
            m = fit(I(f), use, L2)
            for c in ((0, 1) if 'sp_on' in use else (0,)):
                nm = name + (', as a tournament' if c else ''); z = m.logit(as_ctx(R, c)); zs[nm][sel] = z
                s = match_score(z, ry[sel]); msg.append(f"{nm} {s['logloss']:.4f}/{100 * s['acc']:.1f}%")
        M.say(f"    {e} ({d0}; M-C games before it: ladder {nl}, tournament {no}, sheets {len(sel)} matches): " + '; '.join(msg))
    J['online']['regionals_before'] = {}
    M.say(f"  regionals, each fitted only on the games before it (all five events together):")
    for nm, z in zs.items():
        s = match_score(z, ry); J['online']['regionals_before'][nm] = s
        M.say(f"    {nm:46s} {s['logloss']:.4f} / {100 * s['acc']:.1f}%, slope {s['slope']:.2f}")

def regionals(J):
    rows, y, meta = M.load(lambda g: g['src'] == 'ladder'); lam = lambdas(rows, y, meta)
    rr, ry, rmeta = regional_rows()
    M.say(f"evaluate regionals: fit on all {len(rows)} ladder games, score {len(rr)} regional matches (Bo3)")
    teams = json.load(open(os.path.join(ROOT, 'teamsearch', 'regsim', 'teams.json')))
    sim = json.load(open(os.path.join(ROOT, 'teamsearch', 'regsim', 'report.json')))['way2']
    J['regionals'] = dict(sim=dict(raw=sim['model_c1.0'], best_shrink=sim.get('model_best_c')))
    for name, use in variants(lam)[1:]:
        m = M.Model(lam, use=use).fit(rows, y); z = m.logit(rr); p = 1 / (1 + np.exp(-z)); q = np.clip(BO3(p), 1e-9, 1 - 1e-9)
        zq = np.log(q / (1 - q)); s = score(zq, ry)
        b = 0.0                                                               # slope of real results on the predicted match log-odds
        for _ in range(30):
            pp = 1 / (1 + np.exp(-b * zq)); b += np.sum(zq * (ry - pp)) / max(np.sum(zq * zq * pp * (1 - pp)), 1e-9)
        s['slope'] = b; J['regionals'][name] = s
        M.say(f"  {name:22s} match log loss {s['logloss']:.4f} (coin flip 0.6931), favourite won {100 * s['acc']:.1f}%, slope {b:.2f}")
    # by archetype and by player, for the full model, as the sim's report does
    exp, act, cnt = collections.Counter(), collections.Counter(), collections.Counter()
    for (d, qq, yy) in zip(rmeta, q, ry):
        for k, e, r in ((d['a'], qq, yy), (d['b'], 1 - qq, 1 - yy)): exp[k] += e; act[k] += r; cnt[k] += 1
    ks = [k for k in cnt if cnt[k] >= 5]
    J['regionals']['player_corr'] = float(np.corrcoef([exp[k] / cnt[k] for k in ks], [act[k] / cnt[k] for k in ks])[0, 1])
    ar = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for k in cnt:
        a = teams.get(k, {}).get('arch', '?'); v = ar[a]; v[0] += act[k]; v[1] += exp[k]; v[2] += cnt[k]
    J['regionals']['arch'] = {a: dict(n=n, real=r / n, pred=e / n) for a, (r, e, n) in ar.items() if n >= 50}
    M.say(f"  player correlation {J['regionals']['player_corr']:.2f}; archetype gaps (real - predicted): "
          + ', '.join(f"{a} {100 * (v['real'] - v['pred']):+.1f}" for a, v in sorted(J['regionals']['arch'].items(), key=lambda kv: -kv[1]['n'])))

def newspecies(J):
    rows, y, meta = M.load(lambda g: g['src'] == 'ladder'); lam = lambdas(rows, y, meta)
    mb = [i for i, g in enumerate(meta) if g['reg'] == 'M-B']; mc = [i for i, g in enumerate(meta) if g['reg'] == 'M-C']
    seen = {s for i in mb for T in rows[i][:2] for s in T.sp}
    new = np.array([any(s not in seen for T in rows[i][:2] for s in T.sp) for i in mc])
    M.say(f"evaluate new species: fit on {len(mb)} M-B games, score {len(mc)} M-C games ({new.sum()} with a species M-B never had)")
    J['newspecies'] = {}
    for name, use in variants(lam)[1:]:
        m = M.Model(lam, use=use).fit([rows[i] for i in mb], y[mb]); z = m.logit(no_rat([rows[i] for i in mc])); yt = y[mc]
        s = dict(all=score(z, yt), new=score(z[new], yt[new]), old=score(z[~new], yt[~new])); J['newspecies'][name] = s
        M.say(f"  {name:22s} all {s['all']['logloss']:.4f} / {100 * s['all']['acc']:.1f}%   with new species {s['new']['logloss']:.4f} / {100 * s['new']['acc']:.1f}%"
              f"   without {s['old']['logloss']:.4f} / {100 * s['old']['acc']:.1f}%")

if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    J = json.load(open(OUT)) if os.path.exists(OUT) else {}
    if what == 'tune':
        rows, y, meta = M.load(lambda g: g['src'] == 'ladder'); tune(rows, y, meta)
    for k, f in (('ladder', ladder), ('regionals', regionals), ('newspecies', newspecies), ('online', online)):
        if what in (k, 'all'): f(J); json.dump(J, open(OUT, 'w'), indent=1)
    M.say(f"evaluate {what} done")
