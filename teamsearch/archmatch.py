"""Archetype-vs-archetype win rates: real (public M-C Bo3 ladder replays, bring/previews.json) vs our 4v4 sims (every cached
battle in cloud_results/runs: our team vs the replay model of an archetype), to find where the sim disagrees with real play.

Both sides are labelled with the same classifier (pssim/pro_replays.arch on the six species). Our sim teams are climbed and
bring-optimized, so they win more overall; the comparison therefore fits, in log-odds,
    logit(sim) - logit(real) = row offset (our team's archetype) + column offset (opponent archetype) + residual
and reports the column offsets (how much easier/harder each opponent archetype is in the sim) and the largest residuals
(matchup-specific disagreements) with the raw percentages.
  python3 archmatch.py [min real games per cell = 25]
"""
import json, os, sys, glob, math, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'pssim'))
from pro_replays import arch
ARCH_MAP = {'Tailwind goodstuffs': 'Tailwind', 'Indeedee TR / Psychic Terrain': 'Indeedee TR', 'Sun': 'Sun', 'Rain': 'Rain',
            'Balance, no speed control': 'Balance', 'Sand': 'Sand', 'Snow': 'Snow', 'Trick Room without Indeedee': 'Trick Room',
            'Rain + sun': 'Rain + Sun', 'Perish trap': 'Perish'}
NAMES = ['Tailwind', 'Sun', 'Indeedee TR', 'Rain', 'Balance', 'Sand', 'Snow', 'Trick Room', 'Rain + Sun', 'Perish']
args = [a for a in sys.argv[1:] if not a.startswith('--')]
SOURCE = 'regionals' if '--regionals' in sys.argv else 'ladder'
MIN_REAL = int(args[0]) if args else 25

def real():
    w, n = collections.Counter(), collections.Counter()
    for g in json.load(open(os.path.join(HERE, 'bring', 'previews.json')))['games']:
        a, b = g['p1'], g['p2']
        if a['won'] is None or len(a['six']) != 6 or len(b['six']) != 6: continue
        A, B = arch([s.split('-Mega')[0] for s in a['six']]), arch([s.split('-Mega')[0] for s in b['six']])
        for x, y, won in ((A, B, a['won']), (B, A, b['won'])): n[(x, y)] += 1; w[(x, y)] += won
    return w, n

FORM = {'Indeedee [Female]': 'Indeedee-F', 'Indeedee [Male]': 'Indeedee', 'Ninetales [Alolan Form]': 'Ninetales-Alola'}
def pokedata_species(m): return FORM.get(m['name'], m['name'].split(' [')[0])
def game_rate(pm):
    """per-game win rate p whose best-of-3 match win rate p^2 (3 - 2p) equals pm"""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if mid * mid * (3 - 2 * mid) < pm: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def real_regionals():
    """Reg M-C regionals (Baltimore, Brisbane, Frankfurt; pokedata.ovh standings JSON in regmatch/): every Swiss/top-cut match
    with both players' team sheets, counted as (wins, matches) from each player's side; rates are converted to per-game rates
    in the report since the sims are single games"""
    w, n = collections.Counter(), collections.Counter()
    for f in ('f192.json', 'f193.json', 'f194.json'):
        d = json.load(open(os.path.join(HERE, 'regmatch', f)))
        team = {p['name']: arch([pokedata_species(m) for m in p['decklist']]) for p in d if len(p.get('decklist') or []) == 6}
        for p in d:
            if p['name'] not in team: continue
            for r in (p.get('rounds') or {}).values():
                if r.get('name') in team and r.get('result') in ('W', 'L'):
                    k = (team[p['name']], team[r['name']]); n[k] += 1; w[k] += r['result'] == 'W'
    return w, n

def sim(root=os.path.join(HERE, 'cloud_results', 'runs')):
    import policy as P
    w, n = collections.Counter(), collections.Counter()
    for d in glob.glob(os.path.join(root, '*')):
        try: team = json.load(open(os.path.join(d, 'myteam.json'))); jobs = json.load(open(os.path.join(d, 'jobs.json')))
        except Exception: continue
        A = arch(list(team))
        for od in glob.glob(os.path.join(d, 'out_*')):
            for f in os.listdir(od):
                j = json.load(open(os.path.join(od, f))); job = jobs[j['job']]
                vs = [r['v'] for r in j['rows'] if not r.get('unsupported')]
                wt = P.pair_shares(job['arch'])[job['k']] * 6            # weight lead pairs by their share in the archetype
                B = ARCH_MAP[job['arch']]; n[(A, B)] += wt * len(vs); w[(A, B)] += wt * sum(vs)
    return w, n

if __name__ == '__main__':
    sys.path.insert(0, os.path.join(HERE, 'bring'))
    rw, rn = real_regionals() if SOURCE == 'regionals' else real(); sw, sn = sim()
    if SOURCE == 'regionals':                         # Bo3 match rates -> the per-game rates that produce them
        rw = collections.Counter({k: game_rate(rw[k] / rn[k]) * rn[k] for k in rn if rn[k]})
    unit = 'matches' if SOURCE == 'regionals' else 'games'
    print(f'real source: {SOURCE} ({sum(rn.values()) // 2} {unit}; regional match rates shown as per-game equivalents)' if SOURCE == 'regionals' else 'real source: ladder replays')
    lg = lambda p: math.log(max(1e-3, min(1 - 1e-3, p)) / (1 - max(1e-3, min(1 - 1e-3, p))))
    cells = [(a, b) for a in NAMES for b in NAMES if rn[(a, b)] >= MIN_REAL and sn[(a, b)] >= 100]
    # weighted two-way fit of D = logit(sim) - logit(real) = row[a] + col[b] + resid (col[Tailwind] pinned via the mean)
    rows = sorted({a for a, _ in cells}); cols = sorted({b for _, b in cells})
    X = np.zeros((len(cells), len(rows) + len(cols))); y = np.zeros(len(cells)); wt = np.zeros(len(cells))
    for i, (a, b) in enumerate(cells):
        ps, pr = sw[(a, b)] / sn[(a, b)], rw[(a, b)] / rn[(a, b)]
        X[i, rows.index(a)] = 1; X[i, len(rows) + cols.index(b)] = 1; y[i] = lg(ps) - lg(pr)
        wt[i] = 1 / (1 / max(1, rn[(a, b)] * pr * (1 - pr)) + 1 / max(1, sn[(a, b)] * ps * (1 - ps)))     # inverse variance of D
    Wh = np.sqrt(wt); coef = np.linalg.lstsq(X * Wh[:, None], y * Wh, rcond=None)[0]
    rowo, colo = coef[:len(rows)], coef[len(rows):]; shift = colo.mean(); colo -= shift; rowo += shift
    resid = y - X @ np.r_[rowo, colo]
    print(f'{len(cells)} archetype pairs with >= {MIN_REAL} real games and >= 100 sim games\n')
    print('opponent archetype: how often teams beat it, real ladder vs our sims (column offset > 0 = easier in the sim than in real play)')
    for b in sorted(cols, key=lambda b: -colo[cols.index(b)]):
        rr = sum(rw[(a, b)] for a in NAMES) / max(1, sum(rn[(a, b)] for a in NAMES)); ss = sum(sw[(a, b)] for a in NAMES) / max(1, sum(sn[(a, b)] for a in NAMES))
        print(f'  vs {b:12s} real {100 * rr:5.1f}%  sim {100 * ss:5.1f}%   offset {colo[cols.index(b)]:+.2f}')
    print('\nour-team archetype offsets (> 0 = our sim teams of this archetype outperform real teams of it more than average):')
    print('  ' + ', '.join(f'{a} {rowo[rows.index(a)]:+.2f}' for a in sorted(rows, key=lambda a: -rowo[rows.index(a)])))
    print('\nlargest matchup-specific disagreements (after both offsets; residual in log-odds, ± its SE):')
    order = sorted(range(len(cells)), key=lambda i: -abs(resid[i]) * math.sqrt(wt[i]))
    for i in order[:14]:
        a, b = cells[i]; pr, ps = rw[(a, b)] / rn[(a, b)], sw[(a, b)] / sn[(a, b)]
        print(f'  {a:11s} vs {b:11s} real {100 * pr:5.1f}% ({rn[(a, b)]:4d} {unit})  sim {100 * ps:5.1f}% ({sn[(a, b)]:6.0f})  '
              f'residual {resid[i]:+.2f} ± {1 / math.sqrt(wt[i]):.2f}  {"sim too kind to " + a if resid[i] > 0 else "sim too harsh on " + a}')
