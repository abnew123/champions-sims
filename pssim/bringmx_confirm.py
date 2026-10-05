"""Confirmation for the bring matrix (2026-10-04). Picking the best of 90 combos on the same games flatters the winner, so each archetype's
top N combos from results/bringmx_* plus the sheet's pick (battle_picks_final.json) are replayed on fresh games (first game index 1000).
  jobs:   [ONLY=0,2,...] python3 bringmx_confirm.py jobs [N=5] [out=bringcf_jobs.json]     (slow archetypes first, so one big run has no long tail)
  decide: python3 bringmx_confirm.py decide [results dirs glob=results/bringcf_*]    (paired on fresh games only; a pick changes when the fresh leader beats it by >= 1.5 SE; writes bringcf_picks.json)"""
import json, glob, sys, os, math, collections
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
short = lambda m: m.replace('Indeedee-F', 'Indeedee')
picks = json.load(open('battle_picks_final.json'))
def load(pattern):
    """(arch, opposing lead pair) -> combo (lead fs, back fs) -> {g: v}; plus shares, names, ms per game"""
    V = collections.defaultdict(dict); share = {}; names = {}; ms = collections.defaultdict(list)
    for f in glob.glob(pattern):
        try: r = json.load(open(f))
        except Exception: continue
        key = (frozenset(r['lead']), frozenset(r['back'])); names[key] = (r['lead'], r['back'])
        V[(r['arch'], r['pair'])][key] = {g['g']: g['v'] for g in r['rows'] if g.get('v') is not None}
        share[(r['arch'], r['pair'])] = r['share']; ms[r['arch']] += [g.get('ms', 0) for g in r['rows']]
    return V, share, names, ms
def mean(x): return sum(x) / len(x) if x else float('nan')
def ranked(V, share, a):
    teams = [t for t in V if t[0] == a]; combos = set.intersection(*(set(V[t]) for t in teams)); W = sum(share[t] for t in teams)
    win = {c: sum(share[t] * mean(list(V[t][c].values())) for t in teams) / W for c in combos}
    return teams, sorted(combos, key=lambda c: -win[c]), win
def name(names, c): l, b = names[c]; return f"{'+'.join(map(short, l))} / {'+'.join(map(short, b))}"
if sys.argv[1] == 'jobs':
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 5; out = sys.argv[3] if len(sys.argv) > 3 else 'bringcf_jobs.json'
    V, share, names, ms = load('results/bringmx_*/*.json'); jobs = []
    only = [list(SH)[int(i)] for i in os.environ['ONLY'].split(',')] if os.environ.get('ONLY') else list(SH)   # ONLY=0,2: archetype indices
    for a in sorted(only, key=lambda a: -mean(ms[a])):
        teams, rows, win = ranked(V, share, a)
        pk = (frozenset(picks[a]['lead']), frozenset(picks[a]['back']))
        cand = rows[:N] + ([pk] if pk not in rows[:N] else [])
        print(f"{a} ({mean(ms[a])/1000:.1f} s/game): " + ' | '.join(f"{name(names, c)} {100*win[c]:.0f}%{' (sheet)' if c == pk else ''}" for c in cand))
        for c in cand:
            lead, back = names[c]
            for k in range(6): jobs.append({'arch': a, 'k': k, 'lead': lead, 'back': back})
    json.dump(jobs, open(out, 'w')); print(f"{len(jobs)} jobs -> {out}")
else:
    d = sys.argv[2] if len(sys.argv) > 2 else 'results/bringcf_*'
    V, share, names, _ = load(d + '/*.json'); M, mshare, mnames, _ = load('results/bringmx_*/*.json'); names.update(mnames)
    final = {}; tot = tot_sheet = 0.0
    for a in SH:
        teams, rows, win = ranked(V, share, a)
        if not rows: continue
        best = rows[0]; pk = (frozenset(picks[a]['lead']), frozenset(picks[a]['back']))
        _, _, mwin = ranked(M, mshare, a)
        def gap(c):
            m = var = 0.0; W = sum(share[t] for t in teams)
            for t in teams:
                d = [V[t][c][g] - V[t][best][g] for g in V[t][c] if g in V[t][best]]
                w = share[t] / W; mu = mean(d); m += w * mu; var += w * w * sum((x - mu) ** 2 for x in d) / (len(d) - 1) / len(d)
            return m, math.sqrt(var)
        n = sum(len(V[t][best]) for t in teams)
        print(f"\n=== {a} ({SH[a]}%), {n} fresh games per combo")
        for c in rows:
            g = '' if c == best else '  %+.1f ± %.1f vs the best' % tuple(100 * x for x in gap(c))
            print(f"   {name(names, c):40s} fresh {100*win[c]:5.1f}%  (bring matrix {100*mwin.get(c, float('nan')):.0f}%){g}{'   <- sheet' if c == pk else ''}")
        # keep the sheet's pick unless the fresh-game leader beats it by at least 1.5 standard errors (paired)
        sg, sse = gap(pk) if pk in win and pk != best else (0.0, 1.0)
        ch = best if pk not in win or -sg >= 1.5 * sse else pk
        lead, back = names[ch]
        final[a] = {'lead': lead, 'back': back, 'v': round(win[ch], 3), 'n': n, 'source': 'bring matrix + fresh confirmation',
                    'changed': ch != pk, 'best': name(names, best), 'best_v': round(win[best], 3), 'sheet_v': round(win[pk], 3) if pk in win else None}
        print(f"   -> {'NEW PICK ' if ch != pk else 'keep '}{name(names, ch)} ({100*win[ch]:.1f}%)")
        tot += SH[a] * win[ch]; tot_sheet += SH[a] * win.get(pk, float('nan'))
    W = sum(SH.values())
    print(f"\nladder-weighted on fresh games: new picks {100*tot/W:.1f}% | current sheet picks {100*tot_sheet/W:.1f}%")
    json.dump(final, open('bringcf_picks.json', 'w'), indent=1)
