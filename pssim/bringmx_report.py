"""Bring matrix (2026-10-04): every (lead, back) combo of my six (90) against each archetype's six most common opposing leads, 16 paired
games each (seeds keyed on the opponent, so all 90 combos see the same random streams), real team (myteam_real.json).
  A. per archetype: the best combos, where the sheet's pick (battle_picks_final.json) ranks, and its paired gap to the best
  B. per archetype: what bringing / leading each of my Pokemon is worth
  C. species tells: for each opposing Pokemon X, how the worth of bringing each of mine changes when X is in their four, measured against
     the same archetype's average (so it is an adjustment to the sheet's tab, not an archetype effect)
Opposing teams weighted by archetype ladder share x replay share of their lead pair.
usage: python3 bringmx_report.py [results dir prefix=results/bringmx_]"""
import json, glob, sys, math, collections
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
MINE = ['Blastoise', 'Torkoal', 'Indeedee-F', 'Farigiraf', 'Kingambit', 'Incineroar']
short = lambda m: m.replace('Indeedee-F', 'Indeedee')
pre = sys.argv[1] if len(sys.argv) > 1 else 'results/bringmx_'
V = collections.defaultdict(dict)        # (arch, k) -> (lead fs, back fs) -> {g: v}
info = {}                                # (arch, k) -> (share, their four)
names = {}
for f in glob.glob(pre + '*/*.json'):
    try: r = json.load(open(f))
    except Exception: continue
    a = r['arch']; k = r['pair']
    key = (frozenset(r['lead']), frozenset(r['back'])); names[key] = (r['lead'], r['back'])
    V[(a, k)][key] = {g['g']: g['v'] for g in r['rows'] if g.get('v') is not None}
    info[(a, k)] = (r['share'], r['theirs'])
picks = json.load(open('battle_picks_final.json'))
def combo_name(key): l, b = names[key]; return f"{'+'.join(map(short, l))} / {'+'.join(map(short, b))}"
def mean(x): return sum(x) / len(x) if x else float('nan')
tot = sum(len(d) for d in V.values()); print(f"{tot} (team, combo) jobs read, {sum(len(g) for d in V.values() for g in d.values())} games")

# A. combos per archetype
pick_tot = best_tot = Wtot = 0.0
for a in SH:
    teams = [t for t in V if t[0] == a]
    if not teams: continue
    combos = set.intersection(*(set(V[t]) for t in teams))
    if not combos: continue
    W = sum(info[t][0] for t in teams)
    def win(c): return sum(info[t][0] * mean(list(V[t][c].values())) for t in teams) / W
    rows = sorted(combos, key=lambda c: -win(c)); best = rows[0]
    pk = (frozenset(picks[a]['lead']), frozenset(picks[a]['back']))
    def gap(c):              # paired difference vs the best, share-weighted over opposing teams; SE from per-game differences
        m = var = 0.0
        for t in teams:
            d = [V[t][c][g] - V[t][best][g] for g in V[t][c] if g in V[t][best]]
            if len(d) < 2: continue
            w = info[t][0] / W; mu = mean(d); m += w * mu; var += w * w * sum((x - mu) ** 2 for x in d) / (len(d) - 1) / len(d)
        return m, math.sqrt(var)
    n = min(len(V[t][best]) for t in teams)
    print(f"\n=== {a} ({SH[a]}%): {len(combos)} combos, {len(teams)} opposing teams, {n} games each")
    for i, c in enumerate(rows[:6]):
        g = '' if c == best else '  %+.1f ± %.1f' % tuple(100 * x for x in gap(c))
        print(f"  {i+1:2d}. {combo_name(c):40s} {100*win(c):5.1f}%{g}{'   <- sheet' if c == pk else ''}")
    if pk in combos and pk not in rows[:6]:
        m, se = gap(pk); print(f"  {rows.index(pk)+1:2d}. {combo_name(pk):40s} {100*win(pk):5.1f}%  {100*m:+.1f} ± {100*se:.1f}   <- sheet")
    if pk in combos: pick_tot += SH[a] * win(pk); best_tot += SH[a] * win(best); Wtot += SH[a]
    # B. worth of bringing / leading each of mine (paired by game across combos)
    parts = []
    for m in MINE:
        bring = sum(info[t][0] * (mean([mean(list(V[t][c].values())) for c in combos if m in c[0] | c[1]]) -
                                   mean([mean(list(V[t][c].values())) for c in combos if m not in c[0] | c[1]])) for t in teams) / W
        lead = sum(info[t][0] * (mean([mean(list(V[t][c].values())) for c in combos if m in c[0]]) -
                                  mean([mean(list(V[t][c].values())) for c in combos if m in c[1]])) for t in teams) / W
        parts.append(f"{short(m)} {100*bring:+.0f} (lead vs back {100*lead:+.0f})")
    print('  worth of bringing: ' + ', '.join(parts))
if Wtot: print(f"\nladder-weighted (archetypes with all combos): sheet picks {100*pick_tot/Wtot:.1f}% | best of 90 here {100*best_tot/Wtot:.1f}%"
               " (best-of-90 is optimistic: picked on the same games)")

# C. species tells
def bring_value(t, m):
    """per opposing team: mean win of combos bringing m minus combos without m, with a standard error from the per-game paired differences"""
    cs = list(V[t]); gs = set.intersection(*(set(V[t][c]) for c in cs))
    d = [mean([V[t][c][g] for c in cs if m in c[0] | c[1]]) - mean([V[t][c][g] for c in cs if m not in c[0] | c[1]]) for g in gs]
    mu = mean(d); return mu, math.sqrt(sum((x - mu) ** 2 for x in d) / max(1, len(d) - 1) / max(1, len(d)))
BV = {(t, m): bring_value(t, m) for t in V if len(V[t]) >= 80 for m in MINE}
teams = sorted({t for t, _ in BV});
if not teams: sys.exit()
arch_bv = {}
for a in SH:
    ts = [t for t in teams if t[0] == a]
    if ts:
        for m in MINE: arch_bv[(a, m)] = sum(info[t][0] * BV[(t, m)][0] for t in ts) / sum(info[t][0] for t in ts)
base = lambda n: n.split('-Mega')[0]
spec = collections.defaultdict(list)
for t in teams:
    for x in set(map(base, info[t][1])): spec[x].append(t)
wt = lambda t: SH[t[0]] * info[t][0]
print(f"\n=== species tells ({len(teams)} opposing teams): change in what bringing each of mine is worth when X is in their four, vs the same "
      "archetype's average (win-% points; * = more than 2 standard errors)")
print('  ' + ' ' * 22 + ''.join(f"{short(m):>11s}" for m in MINE) + '   teams (archetypes)')
Wall = sum(wt(t) for t in teams)
for x, ts in sorted(spec.items(), key=lambda kv: -sum(wt(t) for t in kv[1])):
    if len(ts) < 2: continue
    W = sum(wt(t) for t in ts); cells = []
    for m in MINE:
        d = sum(wt(t) * (BV[(t, m)][0] - arch_bv[(t[0], m)]) for t in ts) / W
        se = math.sqrt(sum((wt(t) / W) ** 2 * BV[(t, m)][1] ** 2 for t in ts))
        cells.append(f"{100*d:+6.0f}{'*' if abs(d) > 2 * se else ' '}   ")
    archs = collections.Counter(t[0].split(' ')[0].split('/')[0].rstrip(',') for t in ts)
    print(f"  {x:22s}" + ''.join(cells) + f"  {len(ts)} ({', '.join(f'{k} {v}' for k, v in archs.most_common(3))}); {100*W/Wall:.0f}% of weight")
