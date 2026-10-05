"""Torkoal spread A/B (tork_ab_run.sh): per tab that brings Torkoal, win share with the old (32 HP / 2 SpD) and new (12 HP / 22 SpD) spread
on the same games, the paired difference with its standard error (opposing leads weighted by replay share), and how many games came out
differently. Ladder-weighted totals over those tabs and over the whole ladder (tabs without Torkoal count as no change).
usage: python3 tork_ab_report.py"""
import json, glob, math, collections
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
R = {arm: collections.defaultdict(dict) for arm in ('old', 'new')}; share = {}
for arm in R:
    for f in glob.glob(f'results/tork_ab_{arm}/*.json'):
        try: r = json.load(open(f))
        except Exception: continue
        R[arm][(r['arch'], r['pair'])] = {g['g']: g['v'] for g in r['rows'] if g.get('v') is not None}; share[(r['arch'], r['pair'])] = r['share']
tot = {'d': 0.0, 'var': 0.0, 'w': 0.0}
print(f"{'tab':30s} {'old':>6s} {'new':>6s}   new - old        games differing")
for a in SH:
    teams = [t for t in R['new'] if t[0] == a and t in R['old']]
    if not teams: continue
    W = sum(share[t] for t in teams); m = var = mo = mn = 0.0; n = nd = 0
    for t in teams:
        gs = [g for g in R['new'][t] if g in R['old'][t]]
        if len(gs) < 2: continue
        d = [R['new'][t][g] - R['old'][t][g] for g in gs]; w = share[t] / W; mu = sum(d) / len(d)
        m += w * mu; var += w * w * sum((x - mu) ** 2 for x in d) / (len(d) - 1) / len(d)
        mo += w * sum(R['old'][t][g] for g in gs) / len(gs); mn += w * sum(R['new'][t][g] for g in gs) / len(gs)
        n += len(gs); nd += sum(1 for x in d if x != 0)
    print(f"{a:30s} {100*mo:5.1f}% {100*mn:5.1f}%   {100*m:+5.1f} ± {100*math.sqrt(var):.1f}    {nd} of {n}")
    tot['d'] += SH[a] * m; tot['var'] += SH[a] ** 2 * var; tot['w'] += SH[a]
if tot['w']:
    print(f"\nladder-weighted over these tabs: {100*tot['d']/tot['w']:+.2f} ± {100*math.sqrt(tot['var'])/tot['w']:.2f}"
          f" | over the whole ladder: {100*tot['d']/sum(SH.values()):+.2f} ± {100*math.sqrt(tot['var'])/sum(SH.values()):.2f}")
