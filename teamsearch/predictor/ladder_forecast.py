"""Ladder forecast (the user, 2026-11-27: separate "what the ladder settles to" from "what the best teams are"; the ladder is not
fully rational, so its forecast is a model of how ladder usage moves, not of which teams are best). This is the first question.

Per forme f and week w (Monday to Sunday, UTC; one vote per player as backtest/compare.py counts usage), the forecast of ladder
usage h weeks on is  u(w + h) = (u(w) + EPS) * exp(b . x) - EPS,  rescaled to the same total, with
  tour      log of tournament usage that week over ladder usage (all online-tournament players: does the ladder follow them?)
  topcut    the same for the online-tournament top cuts (top eighth, at least the top 4)
  momentum  log of ladder usage this week over the week before
  strength  the matchup predictor's pull: log of (usage + its 5-step replicator change) over usage, fitted on every game to the
            week's end and the ladder sheets of the last 14 days (as meta.py)
b by weighted least squares on the log changes of every earlier transition (formes at 1%+ at either end, weight = usage at the
two ends), M-B and M-C together. Rolling test: each transition is forecast with b fitted only on transitions whose target week
had ended by then; scored as compare.py (rank correlation over formes at 2%+, distance), against "this week carries over" and
the replicator reading alone. Also the lead-lag check: the coefficient of each signal alone, with a bootstrap over formes.
Our ladder replays reach 1,000 games a week only from Sep 28, three weeks into M-C, so the opening weeks (when usage moves most)
are tested on the online-tournament field instead ('tours'): does next week's tournament field follow this week's top cuts?
  teamsearch/bin/teamsearch-py predictor/ladder_forecast.py [tours]  -> predictor/ladder_forecast.json, lines in predictor.log
"""
import os, sys, json, glob, time, calendar, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M, meta as X
from compare import usage, score
from parse_games import OFFMETA, TOURS
L = X.L
OUT = os.path.join(M.HERE, 'ladder_forecast.json')
EPS = 0.005; MINU = 0.01; MIN_GAMES = 1000; HS = (1, 2); WK = 7 * 86400
FEATS = ('tour', 'topcut', 'momentum', 'strength')
VARIANTS = [('carry over', ()), ('tournament usage', ('tour',)), ('top cuts', ('topcut',)), ('momentum', ('momentum',)),
            ('predictor strength', ('strength',)), ('tournament + momentum', ('tour', 'momentum')), ('all four', FEATS)]
week = lambda t: (int(t) // 86400 - (int(t) // 86400 + 3) % 7) * 86400              # Monday 00:00 UTC
wname = lambda w: time.strftime('%b %d', time.gmtime(w))

def ladder_weeks(meta):
    sd, n = collections.defaultdict(list), collections.Counter()
    for g in meta:
        if g['src'] != 'ladder': continue
        k = (g['reg'], week(g['t'])); n[k] += 1
        sd[k] += [(g['p1'], X.formes(g['six1'], g['sets1'])), (g['p2'], X.formes(g['six2'], g['sets2']))]
    return {k: usage(s)[0] for k, s in sd.items() if n[k] >= MIN_GAMES}, n

def tour_weeks():
    """online-tournament usage by (reg, week), all players and top cuts (names stay in memory: one vote per player)"""
    al, tp = collections.defaultdict(list), collections.defaultdict(list)
    for f in glob.glob(os.path.join(TOURS, '*.json')):
        if f.endswith('index.json'): continue
        d = json.load(open(f))
        if d.get('no_sheets') or OFFMETA.search(d['t']['name']): continue
        T = d['t']; k = (T['format'], week(calendar.timegm(time.strptime(T['date'][:19], '%Y-%m-%dT%H:%M:%S'))))
        cut = max(4, (T.get('players') or 0) // 8)
        for p in d['standings']:
            dl = p.get('decklist') or []
            if len(dl) != 6: continue
            fs = [L.battle_forme(x.get('id') or x.get('name'), x.get('item')) for x in dl]
            al[k].append((p['player'], fs))
            if p.get('placing') and p['placing'] <= cut: tp[k].append((p['player'], fs))
    return ({k: usage(s)[0] for k, s in al.items() if len(s) >= 200}, {k: usage(s)[0] for k, s in tp.items() if len(s) >= 40},
            {k: len(s) for k, s in al.items()})

def strength(rows, y, meta, reg, w, lam, use):
    """the predictor's 5-step replicator change in forme usage, from what was known at the end of week w"""
    end = w + WK; fit = [i for i, g in enumerate(meta) if g['t'] < end]
    m = M.Model(lam, use=use).fit([rows[i] for i in fit], y[fit])
    sd = []
    for g, (A, B, *_) in zip(meta, rows):
        if g['reg'] == reg and g['src'] == 'ladder' and end - 2 * WK <= g['t'] < end:
            sd += [(g['p1'], tuple(sorted(A.sp)), A, X.formes(g['six1'], g['sets1'])), (g['p2'], tuple(sorted(B.sp)), B, X.formes(g['six2'], g['sets2']))]
    keys, groups, F, x0, _ = X.pool(sd)
    P = 1 / (1 + np.exp(-M.Pool(m, groups).logits())); xs = X.replicate(P, x0, steps=(0, X.CHOSEN))
    a, b = X.use_of(x0, F), X.use_of(xs[X.CHOSEN], F)
    return {f: b.get(f, 0) - a.get(f, 0) for f in set(a) | set(b)}

def features(f, k, LW, TA, TT, SH):
    reg, w = k; u = LW[k].get(f, 0.0); lu = np.log(u + EPS)
    prev = LW.get((reg, w - WK))
    return dict(tour=np.log(TA[k].get(f, 0) + EPS) - lu if k in TA else 0.0,
                topcut=np.log(TT[k].get(f, 0) + EPS) - lu if k in TT else 0.0,
                momentum=lu - np.log(prev.get(f, 0) + EPS) if prev is not None else 0.0,
                strength=np.log(max(u + SH[k].get(f, 0), 0) + EPS) - lu if k in SH else 0.0)

def transitions(LW, TA, TT, SH, h):
    out = []
    for (reg, w) in sorted(LW):
        t = (reg, w + h * WK)
        if t not in LW or (reg, w) not in SH: continue
        fs = [f for f in set(LW[(reg, w)]) | set(LW[t]) if max(LW[(reg, w)].get(f, 0), LW[t].get(f, 0)) >= MINU]
        X_ = np.array([[features(f, (reg, w), LW, TA, TT, SH)[k] for k in FEATS] for f in fs])
        yv = np.array([np.log(LW[t].get(f, 0) + EPS) - np.log(LW[(reg, w)].get(f, 0) + EPS) for f in fs])
        wt = np.array([LW[(reg, w)].get(f, 0) + LW[t].get(f, 0) for f in fs])
        out.append(dict(reg=reg, w=w, t=t[1], fs=fs, X=X_, y=yv, wt=wt))
    return out

def fit_b(tr, cols):
    if not cols or not tr: return np.zeros(len(cols))
    Xa = np.vstack([d['X'][:, cols] for d in tr]); ya = np.concatenate([d['y'] for d in tr]); wa = np.concatenate([d['wt'] for d in tr])
    A = Xa.T @ (Xa * wa[:, None]) + 1e-3 * np.eye(len(cols)); return np.linalg.solve(A, Xa.T @ (wa * ya))

def forecast(k, b, cols, LW, TA, TT, SH):
    u0 = LW[k]; fs = set(u0) | ({f for f, v in TA.get(k, {}).items() if v >= MINU} if 0 in cols else set())
    u = {}
    for f in fs:
        x = features(f, k, LW, TA, TT, SH); z = sum(bi * x[FEATS[c]] for bi, c in zip(b, cols))
        u[f] = max(0.0, (u0.get(f, 0) + EPS) * np.exp(z) - EPS)
    s = sum(u.values()); t = sum(u0.values()); return {f: v * t / s for f, v in u.items()}

def leadlag(trs, B=500, seed=1):
    """each signal alone on every M-C transition: coefficient, bootstrap 90% interval (resampling formes), weighted R^2"""
    rng = np.random.default_rng(seed); out = {}
    mc = [d for d in trs if d['reg'] == 'M-C']
    rowsf = collections.defaultdict(list)
    for d in mc:
        for i, f in enumerate(d['fs']): rowsf[f].append((d['X'][i], d['y'][i], d['wt'][i]))
    fl = list(rowsf)
    for c, name in enumerate(FEATS):
        def est(sel):
            x = np.array([r[0][c] for f in sel for r in rowsf[f]]); yv = np.array([r[1] for f in sel for r in rowsf[f]]); w = np.array([r[2] for f in sel for r in rowsf[f]])
            bb = np.sum(w * x * yv) / max(np.sum(w * x * x), 1e-12); r2 = 1 - np.sum(w * (yv - bb * x) ** 2) / max(np.sum(w * yv * yv), 1e-12); return bb, r2
        b0, r2 = est(fl); bs = sorted(est([fl[i] for i in rng.integers(0, len(fl), len(fl))])[0] for _ in range(B))
        out[name] = dict(coef=float(b0), lo=float(bs[int(0.05 * B)]), hi=float(bs[int(0.95 * B)]), r2=float(r2))
    return out

def main():
    t0 = time.time()
    rows, y, meta = M.load(lambda g: g['src'] in ('ladder', 'online'))
    lam = json.load(open(os.path.join(M.HERE, 'lambdas.json'))); use = ('sp', 'tok', 'attr', 'pair', 'tpair', 'pl', 'rat')
    LW, n = ladder_weeks(meta); TA, TT, NT = tour_weeks()
    M.say(f"ladder forecast: ladder weeks with {MIN_GAMES}+ games: " + ', '.join(f"{r} {wname(w)}" for r, w in sorted(LW))
          + f"; tournament weeks: {len(TA)} (top cuts {len(TT)})")
    known = [k for k in sorted(LW) if any((k[0], k[1] + h * WK) in LW for h in HS)]
    SH = {}
    for j, (reg, w) in enumerate(known, 1):
        SH[(reg, w)] = strength(rows, y, meta, reg, w, lam, use)
        M.say(f"  score (predictor fits): {j}/{len(known)} fits, {int((time.time() - t0) / 60)} min")
    J = dict(weeks={f"{r} {wname(w)}": dict(ladder_games=n[(r, w)], tournament_players=NT.get((r, w), 0)) for r, w in sorted(LW)})
    for h in HS:
        trs = transitions(LW, TA, TT, SH, h); J[f'h{h}'] = H = dict(leadlag=leadlag(trs), rolling={})
        M.say(f"  {h} week{'s' if h > 1 else ''} ahead: {len(trs)} transitions ({sum(d['reg'] == 'M-C' for d in trs)} in M-C)")
        M.say("    each signal alone on M-C (coefficient on the log change, 90% interval over formes, R^2): "
              + '; '.join(f"{k} {v['coef']:+.2f} [{v['lo']:+.2f}, {v['hi']:+.2f}] R2 {v['r2']:.2f}" for k, v in H['leadlag'].items()))
        tests = [d for d in trs if d['reg'] == 'M-C' and any(e['t'] <= d['w'] for e in trs)]
        res = collections.defaultdict(list)
        for d in tests:
            tr = [e for e in trs if e['t'] <= d['w']]; k = (d['reg'], d['w']); real = LW[(d['reg'], d['t'])]
            for name, fe in VARIANTS:
                cols = [FEATS.index(x) for x in fe]; b = fit_b(tr, cols)
                res[name].append(dict(w=wname(d['w']), b=[float(v) for v in b], **score(forecast(k, b, cols, LW, TA, TT, SH), real)))
            sh = {f: max(0.0, LW[k].get(f, 0) + SH[k].get(f, 0)) for f in set(LW[k]) | set(SH[k])}
            res['replicator reading (meta.py)'].append(dict(w=wname(d['w']), **score(sh, real)))
        H['rolling'] = dict(res)
        base = np.array([r['tv'] for r in res['carry over']])
        M.say(f"    rolling test on {len(tests)} M-C weeks ({', '.join(r['w'] for r in res['carry over'])}): mean rank corr / distance, weeks closer than carry-over")
        for name, rs in res.items():
            tv = np.array([r['tv'] for r in rs])
            M.say(f"      {name:30s} {np.mean([r['spearman'] for r in rs]):.3f} / {np.mean(tv):.3f}   closer {int(np.sum(tv < base - 1e-9))}/{len(rs)}"
                  + (f"   last b {', '.join(f'{v:+.2f}' for v in rs[-1]['b'])}" if rs[-1].get('b') else ''))
    json.dump(J, open(OUT, 'w'), indent=1)
    M.say(f"ladder forecast done ({int((time.time() - t0) / 60)} min)")

def tours_follow():
    """the same forecast on the online-tournament field: features top cut gap and momentum, from week 1 of each regulation"""
    TA, TT, NT = tour_weeks(); TA = {k: v for k, v in TA.items() if NT[k] >= 500}
    J = json.load(open(OUT)) if os.path.exists(OUT) else {}; J['tours'] = {}
    feats = ('topcut', 'momentum'); var = [('carry over', ()), ('top cuts', ('topcut',)), ('momentum', ('momentum',)), ('both', feats)]
    M.say(f"field forecast (online tournaments): weeks with 500+ players: " + ', '.join(f"{r} {wname(w)}" for r, w in sorted(TA)))
    for h in HS:
        trs = []
        for (reg, w) in sorted(TA):
            t = (reg, w + h * WK)
            if t not in TA: continue
            fs = [f for f in set(TA[(reg, w)]) | set(TA[t]) if max(TA[(reg, w)].get(f, 0), TA[t].get(f, 0)) >= MINU]
            def fx(f):
                u = TA[(reg, w)].get(f, 0); lu = np.log(u + EPS); prev = TA.get((reg, w - WK))
                return [np.log(TT[(reg, w)].get(f, 0) + EPS) - lu if (reg, w) in TT else 0.0, lu - np.log(prev.get(f, 0) + EPS) if prev else 0.0]
            trs.append(dict(reg=reg, w=w, t=t[1], fs=fs, X=np.array([fx(f) for f in fs]),
                            y=np.array([np.log(TA[t].get(f, 0) + EPS) - np.log(TA[(reg, w)].get(f, 0) + EPS) for f in fs]),
                            wt=np.array([TA[(reg, w)].get(f, 0) + TA[t].get(f, 0) for f in fs])))
        res = collections.defaultdict(list)
        for d in trs:
            tr = [e for e in trs if e['t'] <= d['w']]
            if not tr: continue
            u0 = TA[(d['reg'], d['w'])]; real = TA[(d['reg'], d['t'])]
            for name, fe in var:
                cols = [feats.index(x) for x in fe]; b = fit_b(tr, cols) if cols else np.zeros(0)
                u = {}
                for f in set(u0) | {f for f, v in TT.get((d['reg'], d['w']), {}).items() if v >= MINU}:
                    x = fx_ = None
                    lu = np.log(u0.get(f, 0) + EPS); prev = TA.get((d['reg'], d['w'] - WK))
                    xv = [np.log(TT[(d['reg'], d['w'])].get(f, 0) + EPS) - lu if (d['reg'], d['w']) in TT else 0.0, lu - np.log(prev.get(f, 0) + EPS) if prev else 0.0]
                    u[f] = max(0.0, (u0.get(f, 0) + EPS) * np.exp(sum(bi * xv[c] for bi, c in zip(b, cols))) - EPS)
                s_ = sum(u.values()); tt = sum(u0.values()); u = {f: v * tt / s_ for f, v in u.items()}
                res[name].append(dict(reg=d['reg'], w=wname(d['w']), b=[float(v) for v in b], **score(u, real)))
        J['tours'][f'h{h}'] = dict(res)
        base = {(r['reg'], r['w']): r['tv'] for r in res['carry over']}
        M.say(f"  {h} week{'s' if h > 1 else ''} ahead, rolling ({len(res['carry over'])} weeks; M-C opening weeks first): mean rank corr / distance, weeks closer than carry-over")
        for name, rs in res.items():
            for lab, keep in (('all', lambda r: True), ('M-C first 4 weeks', lambda r: r['reg'] == 'M-C' and r['w'] in ('Sep 14', 'Sep 21', 'Sep 28', 'Oct 05'))):
                rr = [r for r in rs if keep(r)]
                if not rr: continue
                M.say(f"    {name:12s} {lab:18s} {np.mean([r['spearman'] for r in rr]):.3f} / {np.mean([r['tv'] for r in rr]):.3f}   closer {sum(r['tv'] < base[(r['reg'], r['w'])] - 1e-9 for r in rr)}/{len(rr)}"
                      + (f"   last b {', '.join(f'{v:+.2f}' for v in rr[-1]['b'])}" if rr[-1]['b'] else ''))
    json.dump(J, open(OUT, 'w'), indent=1)

if __name__ == '__main__':
    if sys.argv[1:] == ['tours']: tours_follow()
    else: main()
