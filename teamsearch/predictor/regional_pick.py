"""Picking a team for a regional, backtested on the five M-C regionals (the user, 2026-11-28: "if you were trying to predict the best
team to bring to a regional, what strategy would you use? can you backtest on M-C's regionals?").

For each event, with only what was known before its first day: every team brought there (open team sheets, regionals/) gets a
score from each way of choosing, and the ways are compared on how those teams really did (match win rate over all their matches,
Day 2, top cut). A way that sorts the brought teams well is one you could pick a team with.
  field      the matchup predictor (fitted on every ladder and online-tournament game before the event, M-B and M-C) against the
             expected field: M-C ladder and online-tournament sheets of the 14 days before (28 if under 150 players), one vote per
             player; Bo3 match win share against it
  oracle     the same against the event's real field (what knowing the field exactly would add)
  popular    the six's share of players in those 14 days
  record     the six's game record in M-C ladder and online-tournament games before the event, shrunk: (wins + 10) / (games + 20)
  topcut     the six's online-tournament top-cut rate before the event (top eighth, at least top 4), shrunk to the base rate
  sim        the battle sim's team strength (regsim: fitted on its 6 games per real pairing; no data, so nothing to leak)
  blends     equal-weight averages of z-scores (within each event)
Caveat: regional players are anonymous here, so pilot skill cannot be held out; strong players choosing a team flatters it, and
that helps popular / record / topcut the most.
  teamsearch/bin/teamsearch-py predictor/regional_pick.py      -> predictor/regional_pick.json, lines in predictor.log
"""
import os, sys, json, glob, time, calendar, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M, meta as X
from parse_games import OFFMETA, TOURS
TS = os.path.dirname(M.HERE); sys.path.insert(0, TS)
import regsim, sets_lib as L
OUT = os.path.join(M.HERE, 'regional_pick.json')
EVENTS = {'Baltimore': '2026-09-18', 'Brisbane': '2026-09-26', 'Frankfurt': '2026-09-26', 'Recife': '2026-10-03', 'Louisville': '2026-10-09'}
USE = ('sp', 'tok', 'attr', 'pair', 'tpair', 'pl', 'rat')
BO3 = lambda p: p * p * (3 - 2 * p)
DAY = 86400

def results(R):
    """per player: matches, wins, Day 2, top cut (byes and unreported results left out)"""
    d1, d2, cut = regsim.structure(R)
    later = {x for r in range(d1 + 1, d1 + d2 + 1) for m in R.get(str(r), []) for x in m[:2] if x}
    top = {x for m in R.get(str(d1 + d2 + 1), []) for x in m[:2] if x} if cut > 1 else set()
    n, w = collections.Counter(), collections.Counter()
    for ms in R.values():
        for a, b, win in ms:
            if a and b and win in (a, b): n[a] += 1; n[b] += 1; w[win] += 1
    return {p: dict(n=n[p], w=w[p], day2=p in later, top=p in top) for p in n}

def tour_cuts(t_end):
    """six key -> (entries, top-cut entries) in M-C online tournaments before t_end"""
    c = collections.defaultdict(lambda: [0, 0])
    for f in glob.glob(os.path.join(TOURS, '*.json')):
        if f.endswith('index.json'): continue
        d = json.load(open(f))
        if d.get('no_sheets') or d['t']['format'] != 'M-C' or OFFMETA.search(d['t']['name']): continue
        if calendar.timegm(time.strptime(d['t']['date'][:19], '%Y-%m-%dT%H:%M:%S')) >= t_end: continue
        cut = max(4, (d['t'].get('players') or 0) // 8)
        for p in d['standings']:
            dl = p.get('decklist') or []
            if len(dl) != 6: continue
            k = tuple(sorted(M.idf(x.get('id') or x.get('name')) for x in dl)); c[k][0] += 1; c[k][1] += bool(p.get('placing') and p['placing'] <= cut)
    return c

def zs(v):
    v = np.asarray(v, dtype=float); s = v.std(); return (v - v.mean()) / s if s > 0 else v * 0

def main():
    t0 = time.time()
    rows, y, meta = M.load(lambda g: g['src'] in ('ladder', 'online')); lam = json.load(open(os.path.join(M.HERE, 'lambdas.json')))
    R0 = json.load(open(os.path.join(M.ROOT, 'regionals', 'regional_sets.json'))); F0 = json.load(open(os.path.join(M.ROOT, 'regionals', 'field_sets.json')))
    sheets = {k: [L.normalize(dict(s)) for s in v] for k, v in {**R0, **F0}.items() if len(v) == 6}
    P = json.load(open(os.path.join(M.ROOT, 'regionals', 'pairings.json')))
    teams = json.load(open(os.path.join(TS, 'regsim', 'teams.json')))
    s_sim, _ = regsim.fit([d for d in map(json.loads, open(os.path.join(TS, 'regsim', 'games.jsonl'))) if d['n']], teams)
    M.say(f"regional pick: {len(sheets)} regional sheets; sim strengths for {len(s_sim)} teams")
    models, recs = {}, []
    for ev, d0 in EVENTS.items():
        te = calendar.timegm(time.strptime(d0, '%Y-%m-%d')); hi = X.day(te - DAY)
        if d0 not in models:
            pre = [i for i, g in enumerate(meta) if g['t'] < te]
            models[d0] = M.Model(lam, use=USE).fit([rows[i] for i in pre], y[pre])
            M.say(f"  score (regional pick fits): {len(models)}/{len(set(EVENTS.values()))} fits, {int((time.time() - t0) / 60)} min")
        m = models[d0]
        for days in (14, 28):
            lo = X.day(te - days * DAY); sd = X.sides(meta, rows, 'M-C', lo, hi)
            if len({p for p, *_ in sd}) >= 150: break
        keys, groups, _, x, _ = X.pool(sd, min_players=1); FP = M.Pool(m, groups)
        npl = collections.Counter(); seen_by = collections.defaultdict(set)
        for p, k, *_ in sd: seen_by[k].add(p)
        nplay = len({p for p, *_ in sd}); pop = {k: len(v) / nplay for k, v in seen_by.items()}
        rec = collections.defaultdict(lambda: [0, 0])
        for g, (A, B, *_) in zip(meta, rows):
            if g['reg'] == 'M-C' and g['t'] < te:
                for T, wv in ((A, g['win']), (B, 1 - g['win'])): r = rec[tuple(sorted(T.sp))]; r[0] += wv; r[1] += 1
        tc = tour_cuts(te); base = sum(v[1] for v in tc.values()) / max(1, sum(v[0] for v in tc.values()))
        res = results(P[ev]['rounds'])
        ks = [p for p in res if f'{ev}|{p}' in sheets and res[p]['n'] >= 3]
        T_ = [M.Team([s['species'] for s in sheets[f'{ev}|{p}']], sheets[f'{ev}|{p}']) for p in ks]
        AP = M.Pool(m, [[T] for T in T_])
        field = BO3(1 / (1 + np.exp(-AP.cross(FP)))) @ x
        evp = M.Pool(m, [[T] for T in T_]); oracle = BO3(1 / (1 + np.exp(-evp.logits()))).mean(1)
        for i, (p, T) in enumerate(zip(ks, T_)):
            k = tuple(sorted(T.sp)); r = rec.get(k, (0, 0)); c = tc.get(k, (0, 0))
            recs.append(dict(ev=ev, p=p, key=k, field=float(field[i]), oracle=float(oracle[i]), popular=pop.get(k, 0.0),
                             record=(r[0] + 10) / (r[1] + 20), games_before=r[1], topcut=(c[1] + 20 * base) / (c[0] + 20), entries_before=c[0],
                             sim=s_sim.get(f'{ev}|{p}', np.nan), **res[p]))
        M.say(f"  {ev} ({d0}): {len(ks)} players with a sheet; expected field {nplay} players ({lo} to {hi}); sixes seen online or on ladder before:"
              f" {sum(1 for r in recs if r['ev'] == ev and r['games_before'] > 0)}")
    # blends, z-scored within each event
    for ev in EVENTS:
        idx = [i for i, r in enumerate(recs) if r['ev'] == ev]
        for nm in ('field', 'record', 'topcut', 'popular', 'sim'):
            v = np.array([recs[i][nm] for i in idx]); v = np.where(np.isnan(v), np.nanmean(v), v); z = zs(v)
            for j, i in enumerate(idx): recs[i]['z_' + nm] = float(z[j])
    blends = {'field + record': ('field', 'record'), 'field + topcut': ('field', 'topcut'), 'field + record + topcut': ('field', 'record', 'topcut'),
              'record + topcut': ('record', 'topcut')}
    for r in recs:
        for nm, parts in blends.items(): r[nm] = float(np.mean([r['z_' + q] for q in parts]))
    ways = ['field', 'oracle', 'popular', 'record', 'topcut', 'sim'] + list(blends)
    J = dict(players=len(recs), ways={}); n = np.array([r['n'] for r in recs]); wr = np.array([r['w'] / r['n'] for r in recs])
    d2 = np.array([r['day2'] for r in recs]); tp = np.array([r['top'] for r in recs]); evs = np.array([r['ev'] for r in recs])
    seen = np.array([r['games_before'] >= 20 for r in recs])
    M.say(f"  all five events: {len(recs)} players; match win rate {100 * np.average(wr, weights=n):.1f}%, Day 2 {100 * d2.mean():.1f}%, top cut {100 * tp.mean():.2f}%"
          f"   ({int(seen.sum())} brought a six with 20+ games before the event)")
    M.say("  way: correlation with real match win rate (weighted by matches; within events) | top 5% / top 10% of each event by the way:"
          " match win rate, Day 2 rate, top-cut rate | the same correlation among the sixes with 20+ games before")
    def within_corr(v, sel):
        a, b, ww = [], [], []
        for ev in EVENTS:
            e = sel & (evs == ev)
            if e.sum() < 10: continue
            a += list(v[e] - np.average(v[e], weights=n[e])); b += list(wr[e] - np.average(wr[e], weights=n[e])); ww += list(n[e])
        a, b, ww = map(np.array, (a, b, ww)); return float(np.sum(ww * a * b) / np.sqrt(np.sum(ww * a * a) * np.sum(ww * b * b)))
    for wy in ways:
        v = np.array([r[wy] for r in recs], dtype=float); v = np.where(np.isnan(v), np.nanmean(v), v)
        out = dict(corr=within_corr(v, np.ones(len(v), bool)), corr_seen=within_corr(v, seen))
        for q in (0.05, 0.10):
            sel = np.zeros(len(v), bool)
            for ev in EVENTS:
                e = np.where(evs == ev)[0]; o = e[np.argsort(-v[e] + 1e-9 * np.random.default_rng(0).random(len(e)))][:max(3, int(q * len(e)))]; sel[o] = True
            out[f'top{int(q * 100)}'] = dict(n=int(sel.sum()), win=float(np.average(wr[sel], weights=n[sel])), day2=float(d2[sel].mean()), top=float(tp[sel].mean()))
        J['ways'][wy] = out
        M.say(f"    {wy:24s} corr {out['corr']:+.3f} | top 5%: {100 * out['top5']['win']:.1f}% / Day 2 {100 * out['top5']['day2']:.0f}% / cut {100 * out['top5']['top']:.1f}%"
              f" | top 10%: {100 * out['top10']['win']:.1f}% / {100 * out['top10']['day2']:.0f}% / {100 * out['top10']['top']:.1f}% | seen-six corr {out['corr_seen']:+.3f}")
    # what each way would have recommended (its top six at each event) and how its pilots did
    J['picks'] = {}
    for wy in ('field', 'record', 'topcut', 'field + record + topcut'):
        J['picks'][wy] = {}
        for ev in EVENTS:
            e = [r for r in recs if r['ev'] == ev]; best = max(e, key=lambda r: r[wy]); same = [r for r in e if r['key'] == best['key']]
            J['picks'][wy][ev] = dict(six=list(best['key']), pilots=len(same), wins=sum(r['w'] for r in same), matches=sum(r['n'] for r in same),
                                      day2=sum(r['day2'] for r in same), top=sum(r['top'] for r in same))
        M.say(f"    {wy} picks: " + '; '.join(f"{ev} {'/'.join(v['six'])} ({v['pilots']} pilots, {v['wins']}-{v['matches'] - v['wins']}, Day 2 {v['day2']}, cut {v['top']})"
                                         for ev, v in J['picks'][wy].items()))
    json.dump(J, open(OUT, 'w'), indent=1)
    M.say(f"regional pick done ({int((time.time() - t0) / 60)} min)")

if __name__ == '__main__': main()
