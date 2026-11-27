"""How well the matchup predictor calls real games it was not fitted on.
  0. tune: ridge strength per block on team-only log loss (fit before the 60% mark of M-C, validate on 60-80%) -> lambdas.json
  1. ladder: fit on M-B plus the first 80% of M-C ladder games (by time), score the last 20%; each feature block added in turn
  2. regionals: fit on every ladder game, score the 14,811 real M-C regional matches (open team sheets, Bo3) beside the battle
     sim's scores on the same matches (regsim/report.json)
  3. new species: fit on M-B only, score M-C ladder games, split by whether they hold species M-B never had (the M-D situation)
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
    for k, f in (('ladder', ladder), ('regionals', regionals), ('newspecies', newspecies)):
        if what in (k, 'all'): f(J); json.dump(J, open(OUT, 'w'), indent=1)
    M.say(f"evaluate {what} done")
