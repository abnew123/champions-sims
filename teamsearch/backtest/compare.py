"""M-B to M-C self-play backtest (the user, 2026-11-06), step 4: how close each prediction came to M-C's real meta.
Real usage per forme (battle forme, Megas apart), one vote per player: per player, the share of their sheets with the forme, averaged
over players. From the cached public M-C Bo3 logs (pssim/replays_protect; protocol lines only, players numbered in memory, nothing
named is written), in three windows: weeks 1-2 (Sep 9-22), weeks 3-5 (Sep 23 - Oct 13), settled (Oct 14 - Nov 6); cached in
mc_truth.json (usage only). Predictions: M-B's own usage over its last 14 days, counted the same way (the carry-over baseline), and
each self-play iteration's weighted field (sp_pred_<i>.json: a team's weight on each of its six formes).
Scores per prediction and window: Spearman rank correlation over the formes at >= 2% real or predicted usage; total variation distance
of the usage vectors (each normalised to sum 1); and M-C's new formes: real usage against predicted.
v2 (the user, 2026-11-07; fixed before the v2 run): also v2's iterations (backtest/v2/), the 16-team starting field on its own, and
"M-B + shift": all of M-B's usage plus the field's change since the start (the field is about a third of M-B's players). New-forme
readouts per prediction: flagged = the new formes at >= 5% real settled usage that it puts at >= 3%; false alarms = new formes it puts
at >= 5% that are under 2% real settled.
  python3 backtest/compare.py            -> report on stdout, compare.json
"""
import json, os, sys, glob, datetime, collections
HERE = os.path.dirname(os.path.abspath(__file__)); TS = os.path.dirname(HERE); ROOT = os.path.dirname(TS)
sys.path.insert(0, TS); sys.path.insert(0, os.path.join(ROOT, 'pssim'))
import sets_lib as L
WIN = {'M-C weeks 1-2': ('2026-09-09', '2026-09-22'), 'M-C weeks 3-5': ('2026-09-23', '2026-10-13'), 'M-C settled': ('2026-10-14', '2026-11-06')}
day = lambda t: datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d')
forme = lambda s: L.battle_forme(s['species'], s.get('item'))

def usage(sides):
    """sides: [(player, [formes])] -> {forme: mean over players of the share of their sheets with it}"""
    per = collections.defaultdict(list)
    for p, fs in sides: per[p].append(set(fs))
    u = collections.Counter()
    for sheets in per.values():
        for f in set().union(*sheets): u[f] += sum(f in s for s in sheets) / len(sheets) / len(per)
    return dict(u), len(per)

def truth():
    path = os.path.join(HERE, 'mc_truth.json')
    if os.path.exists(path): return json.load(open(path))
    from opp_pool import parse
    RP = os.path.join(ROOT, 'pssim', 'replays_protect'); idx = json.load(open(os.path.join(RP, 'index.json')))
    sides = {w: [] for w in WIN}; players = {}
    for f in glob.glob(os.path.join(RP, '*bo3-*.log')):
        gid = os.path.basename(f)[:-4]; t = (idx.get(gid) or {}).get('time')
        if not t: continue
        w = next((w for w, (a, b) in WIN.items() if a <= day(t) <= b), None)
        if not w: continue
        log = open(f, encoding='utf-8', errors='replace').read(); sd, _, _ = parse(log)
        who = {p[2]: p[3].strip().lower() for p in (l.split('|') for l in log.split('\n') if l.startswith('|player|')) if len(p) > 3 and p[3]}
        for s in ('p1', 'p2'):
            six = sd[s]['six']
            if six and len(six) == 6: sides[w].append((players.setdefault(who.get(s, gid + s), len(players)), [forme(L.normalize(x)) for x in six]))
    players.clear()
    out = {}
    for w in WIN:
        u, n = usage(sides[w]); out[w] = dict(usage=u, players=n, sheets=len(sides[w]))
    json.dump(out, open(path, 'w'), indent=1)
    return out

def mb_usage():
    P = json.load(open(os.path.join(HERE, 'mb_pool.json')))['entries']; last = max(e['day'] for e in P)
    first = (datetime.date.fromisoformat(last) - datetime.timedelta(days=13)).isoformat()
    return usage([(e['player'], [forme(L.normalize(x)) for x in e['six']]) for e in P if e['day'] >= first])[0]

def spearman(a, b):
    def ranks(x):
        o = sorted(range(len(x)), key=lambda i: x[i]); r = [0.0] * len(x); i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and x[o[j + 1]] == x[o[i]]: j += 1
            for k in range(i, j + 1): r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    ra, rb = ranks(a), ranks(b); ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb)); va = sum((x - ma) ** 2 for x in ra) ** 0.5; vb = sum((y - mb) ** 2 for y in rb) ** 0.5
    return cov / (va * vb) if va and vb else 0.0

def score(pred, real):
    fs = sorted(f for f in set(pred) | set(real) if pred.get(f, 0) >= 0.02 or real.get(f, 0) >= 0.02)
    sp = spearman([pred.get(f, 0) for f in fs], [real.get(f, 0) for f in fs])
    tp, tr = sum(pred.values()), sum(real.values())
    tv = 0.5 * sum(abs(pred.get(f, 0) / tp - real.get(f, 0) / tr) for f in set(pred) | set(real))
    return dict(spearman=round(sp, 3), tv=round(tv, 3), n=len(fs))

def preds_of(d):
    out = {}
    for f in glob.glob(os.path.join(d, 'sp_pred_*.json')):
        p = json.load(open(f)); out[p['iteration']] = p['usage']
    return dict(sorted(out.items()))

def main():
    T = truth(); mb = mb_usage(); preds = {'M-B carried over': mb}
    v1, v2 = preds_of(HERE), preds_of(os.path.join(HERE, 'v2'))
    shift = lambda v, i: {f: max(0.0, mb.get(f, 0) + v[i].get(f, 0) - v[0].get(f, 0)) for f in set(mb) | set(v[i]) | set(v[0])}
    if 0 in v1: preds['16 M-B teams (start)'] = v1[0]
    preds.update({f'self-play {i}': u for i, u in v1.items() if i > 0})
    if v1 and 0 in v1: preds[f'M-B + shift {max(v1)}'] = shift(v1, max(v1))
    preds.update({f'v2 self-play {i}': u for i, u in v2.items() if i > 0})
    preds.update({f'v2 M-B + shift {i}': shift(v2, i) for i in v2 if i > 0 and 0 in v2})
    sys.path.insert(0, HERE); from build_mb import NEW, NEW_MEGA
    new = {L.DEX['species'].get(L.idf(x), {}).get('name', x) for x in NEW} | set(NEW_MEGA)
    real = T['M-C settled']['usage']; big = sorted(f for f in new if real.get(f, 0) >= 0.05)
    out = dict(windows={w: dict(players=T[w]['players'], sheets=T[w]['sheets']) for w in WIN}, scores={}, new={}, big_new=big)
    print('rank correlation / distance (lower is closer) against real usage, one vote per player; new formes flagged (of '
          f'{len(big)} at >= 5% real) and false alarms:')
    print(f"  {'prediction':24s}" + ''.join(f"{w:>24s}" for w in WIN) + '   flagged  false alarms')
    for n, p in preds.items():
        fl = [f for f in big if p.get(f, 0) >= 0.03]; fa = [f for f in new if p.get(f, 0) >= 0.05 and real.get(f, 0) < 0.02]
        out['scores'][n] = dict({w: score(p, T[w]['usage']) for w in WIN}, flagged=fl, false_alarms=fa)
        print(f"  {n:24s}" + ''.join(f"{s['spearman']:>13.2f} / {s['tv']:.2f}  " for w, s in out['scores'][n].items() if w in WIN)
              + f"   {len(fl)} of {len(big)}   {len(fa)}" + (f"  ({', '.join(fa)})" if fa else ''))
    cols = ['M-B carried over'] + [n for n in preds if n.startswith('self-play')][-1:] + [n for n in preds if n.startswith('v2 self-play')]
    print("\nM-C's new formes: real usage (settled; weeks 1-2) against predictions")
    print(f"  {'forme':20s} {'settled':>8s} {'wk 1-2':>7s}" + ''.join(f"{n.replace('self-play', 'sp')[-12:]:>13s}" for n in cols))
    for f in sorted(new, key=lambda f: -real.get(f, 0)):
        r = real.get(f, 0); e = T['M-C weeks 1-2']['usage'].get(f, 0)
        if r < 0.005 and e < 0.005 and all(p.get(f, 0) < 0.005 for p in preds.values()): continue
        out['new'][f] = dict(settled=r, early=e, **{n: p.get(f, 0) for n, p in preds.items()})
        print(f"  {f:20s} {100 * r:7.1f}% {100 * e:6.1f}%" + ''.join(f"{100 * preds[n].get(f, 0):12.1f}%" for n in cols))
    json.dump(out, open(os.path.join(HERE, 'compare.json'), 'w'), indent=1)

if __name__ == '__main__': main()
