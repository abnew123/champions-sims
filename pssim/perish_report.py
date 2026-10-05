"""Perish play report: two result folders on the same games (BATTLE_TURNS=1), e.g. results/perish_base vs results/perish_p2.
Per folder: my win share, game length, how often the opponents click Perish Song (games with one, clicks per game, turn of the first),
how often Mega Gengar leaves the field by choice, and how often it is on the field when Perish Song is clicked. Then the paired
difference in my win share (opposing leads weighted by replay share).
usage: python3 perish_report.py <dir A> <dir B>"""
import json, glob, sys, math, collections
def load(d):
    R = {}; share = {}; st = collections.Counter(); first = []
    for f in glob.glob(d + '/*.json'):
        r = json.load(open(f)); key = r['pair']; share[key] = r['share']; R[key] = {}
        for g in r['rows']:
            if g.get('v') is None: continue
            R[key][g['g']] = g['v']; S = g.get('states') or []; st['games'] += 1; st['turns'] += g['turns']; sang = False
            for s in S:
                b = s['b']
                n = b.count('Perish Song')
                if n:
                    st['clicks'] += n; st['with_gengar'] += ('Gengar-Mega' in b or any(m[0] == 'Gengar-Mega' for m in s['them']))
                    if not sang: first.append(s['t']); sang = True
                st['gengar_out'] += b.count('Gengar-Mega: switch to')
                st['gengar_turns'] += any(m[0] == 'Gengar-Mega' for m in s['them'])
                st['my_switch'] += s['a'].count('switch to'); st['my_acts'] += len([x for x in s['a'].split(' | ') if ': ' in x])
            st['sang'] += sang
    return R, share, st, first
A, sh, sa, fa = load(sys.argv[1]); B, _, sb, fb = load(sys.argv[2])
for lab, R, st, first in ((sys.argv[1], A, sa, fa), (sys.argv[2], B, sb, fb)):
    W = sum(sh[k] for k in R); win = sum(sh[k] * sum(v.values()) / len(v) for k, v in R.items()) / W; n = st['games']
    print(f"{lab}: {n} games, my win share {100*win:.1f}%, {st['turns']/n:.1f} turns; Perish Song in {100*st['sang']/n:.0f}% of games "
          f"({st['clicks']/n:.2f} clicks/game, first on turn {sum(first)/max(1,len(first)):.1f}, Mega Gengar on the field for {100*st['with_gengar']/max(1,st['clicks']):.0f}% of clicks); "
          f"Mega Gengar switches out {st['gengar_out']/n:.2f} times/game ({100*st['gengar_out']/max(1,st['gengar_turns']):.0f}% of its turns); my switches {100*st['my_switch']/max(1,st['my_acts']):.0f}% of actions")
    for k in sorted(R, key=lambda k: -sh[k]): print(f"     vs {k:26s} {100*sum(R[k].values())/len(R[k]):5.1f}%")
W = sum(sh[k] for k in B if k in A); m = var = 0.0
for k in B:
    if k not in A: continue
    d = [B[k][g] - A[k][g] for g in B[k] if g in A[k]]; w = sh[k] / W; mu = sum(d) / len(d); m += w * mu; var += w * w * sum((x - mu) ** 2 for x in d) / (len(d) - 1) / len(d)
print(f"paired difference in my win share, B - A: {100*m:+.1f} ± {100*math.sqrt(var):.1f}")
