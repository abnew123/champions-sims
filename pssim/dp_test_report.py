"""Double-Protect ban test report (dp_test_run.sh): my win share per archetype as is and with each side banned from a second Protect in a
row, paired on the same games (opposing leads weighted by replay share), plus each arm's double-Protect rates (protect_sim.py).
  ban mine - base > 0: my planner's second Protects cost me games (it over-uses them)
  ban theirs - base < 0: their planner's second Protects cost them games
usage: python3 dp_test_report.py"""
import json, glob, math, collections, protect_sim
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
def load(arm):
    R = {}; share = {}
    for f in glob.glob(f'results/dp_test_{arm}/*.json'):
        try: r = json.load(open(f))
        except Exception: continue
        R[(r['arch'], r['pair'])] = {g['g']: g['v'] for g in r['rows'] if g.get('v') is not None}; share[(r['arch'], r['pair'])] = r['share']
    return R, share
B, share = load('base')
for arm, name in (('ban0', 'ban my second Protect'), ('ban1', 'ban their second Protect')):
    A, _ = load(arm)
    if not A: continue
    print(f"\n=== {name}: my win share, base -> banned (paired)")
    tot = var_t = W_t = 0.0
    for a in SH:
        teams = [t for t in A if t[0] == a and t in B]
        if not teams: continue
        W = sum(share[t] for t in teams); m = var = mb = ma = 0.0; n = 0
        for t in teams:
            gs = [g for g in A[t] if g in B[t]]
            if len(gs) < 2: continue
            d = [A[t][g] - B[t][g] for g in gs]; w = share[t] / W; mu = sum(d) / len(d)
            m += w * mu; var += w * w * sum((x - mu) ** 2 for x in d) / (len(d) - 1) / len(d); n += len(gs)
            mb += w * sum(B[t][g] for g in gs) / len(gs); ma += w * sum(A[t][g] for g in gs) / len(gs)
        print(f"   {a:30s} {100*mb:5.1f}% -> {100*ma:5.1f}%   {100*m:+5.1f} ± {100*math.sqrt(var):.1f}   ({n} games)")
        tot += SH[a] * m; var_t += SH[a] ** 2 * var; W_t += SH[a]
    print(f"   ladder-weighted: {100*tot/W_t:+.2f} ± {100*math.sqrt(var_t)/W_t:.2f}")
for arm in ('base', 'ban0', 'ban1'):
    if not glob.glob(f'results/dp_test_{arm}/*.json'): continue
    C = protect_sim.count([f'results/dp_test_{arm}'])
    print(f"\n{arm}: " + ' | '.join(f"{'mine' if s == 'a' else 'theirs'} Protect {100*c['protects']/max(1,c['actions']):.1f}% of actions, again after a fresh one "
                                 f"{100*c['double']/max(1,c['opps']):.1f}% of {c['opps']}, switch out {100*c['switch_after']/max(1,c['opps']):.1f}%" for s, c in C.items()))
