"""Protect-check decision log report (dplog_run.sh, DP2_LOG=1): for every time a Pokemon that just Protected could Protect again, what the
planner thinks its best Protect-again, other-move and switch options are worth (one turn ahead and two turns ahead, as that side's win
chance), and what each costs in HP in one playout against the other side's likeliest reply (the Pokemon holding the slot: itself, or the
switch-in). "Threatened" = staying in and acting loses HP in that playout.
usage: python3 dplog_report.py [results dir=results/dplog]"""
import json, glob, sys, collections
d = sys.argv[1] if len(sys.argv) > 1 else 'results/dplog'
R = []
for f in glob.glob(d + '/*.json'):
    r = json.load(open(f))
    for g in r['rows']:
        for c in g.get('dp2log') or []: c['arch'] = r['arch']; R.append(c)
def m(x): return sum(x) / len(x) if x else float('nan')
def G(c, k): return next((g for g in c['g'] if g['k'] == k), None)
for side, nm in ((1, 'theirs'), (0, 'mine')):
    C = [c for c in R if c['s'] == side]
    if not C: continue
    full = [c for c in C if G(c, 'switch') and G(c, 'other')]
    print(f"\n=== {nm}: {len(C)} checks; {len(full)} with a switch available; Protect-again dropped in {100*m([c['dropped'] for c in C]):.0f}%")
    def table(L, lab):
        if not L: return
        for depth, key in (('one turn ahead', 'v1'), ('two turns ahead', 'v2')):
            best = collections.Counter(max(('protect', 'other', 'switch'), key=lambda k: G(c, k)[key]) for c in L)
            print(f"   {lab} ({len(L)}), {depth}: best is Protect again {100*best['protect']/len(L):.0f}% / other move {100*best['other']/len(L):.0f}% / switch {100*best['switch']/len(L):.0f}%;"
                  f" mean value Protect {100*m([G(c,'protect')[key] for c in L]):.1f}, other {100*m([G(c,'other')[key] for c in L]):.1f}, switch {100*m([G(c,'switch')[key] for c in L]):.1f}")
        st = [G(c, 'other') for c in L]; sw = [G(c, 'switch') for c in L]; pr = [G(c, 'protect') for c in L]
        print(f"   {lab}: HP in the playout vs their likeliest reply: staying and acting loses {m([g['hp0']-g['hp1'] for g in st]):.0f} points (KO'd {100*m([g['hp1']==0 for g in st]):.0f}%);"
              f" the switch-in loses {m([g['hp0']-g['hp1'] for g in sw]):.0f} (KO'd {100*m([g['hp1']==0 for g in sw]):.0f}%, enters at {m([g['hp0'] for g in sw]):.0f}%);"
              f" Protect again loses {m([g['hp0']-g['hp1'] for g in pr]):.0f} (took nothing {100*m([g['hp0']==g['hp1'] for g in pr]):.0f}%)")
    table(full, 'all')
    thr = [c for c in full if G(c, 'other')['hp0'] - G(c, 'other')['hp1'] > 0]; safe = [c for c in full if c not in thr]
    table(thr, 'threatened'); table([c for c in thr if G(c, 'other')['hp1'] == 0], 'would be KO\'d'); table(safe, 'not threatened')
    table([c for c in full if c['tr'] > 0], 'Trick Room up'); table([c for c in full if c['tr'] == 0], 'no Trick Room')
    # how much better / worse the switch is than Protect again, two turns ahead, among threatened
    if thr:
        dv = sorted(G(c, 'switch')['v2'] - G(c, 'protect')['v2'] for c in thr)
        print(f"   threatened: switch minus Protect-again, two turns ahead: median {100*dv[len(dv)//2]:+.1f}, quartiles {100*dv[len(dv)//4]:+.1f} / {100*dv[3*len(dv)//4]:+.1f}")
