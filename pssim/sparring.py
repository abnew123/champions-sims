"""Report of the sparring partner (sparring.sh): the bot with the d4 net against the bot with the deployed net, both against the same
human-model opponent on the same starts and luck (the opponent built on the deployed net, and in the _h4 arms on the d4 net). Per start the d4 net's gain is v(d4_0) - v(acc0) with the bot on side 0 (v: side 0's
result) and v(acc1) - v(d4_1) with it on side 1; standard errors over starts. Arms not yet run are left out.
  ../.venv/bin/python3 sparring.py [scratch dir, default results/sparring]
Result (2026-10-21, 400 pool starts an arm, BATTLE_EVAL 20,000): against the opponent built on the deployed net d4 - deployed -2.5 +- 2.5
(bot on side 0) and -5.6 +- 2.7 (side 1); against the one built on the d4 net +5.1 +- 2.4 (side 0). Each net does about 4 points a game
better against an opponent that judges positions as it does; averaged over the two opponents d4 - deployed is +1.3 +- 1.7: no clear
difference against human-like play, so a large ladder gain (8+ points a game) is unlikely."""
import os, sys, json, glob, math
HERE = os.path.dirname(os.path.abspath(__file__))
SP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'results', 'sparring')
def load(arm):
    out = {}
    for f in glob.glob(os.path.join(SP, f'out_{arm}', '*.json')):
        try: d = json.load(open(f))
        except ValueError: continue
        if 'v' in d: out[d['job']] = d['v']
    return out
def ms(xs):
    n = len(xs); m = sum(xs) / n
    return m, (math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1) / n) if n > 1 else 0.0)
A = {a: load(a) for a in ('acc0', 'd4_0', 'acc1', 'd4_1', 'acc0_h4', 'd4_0_h4')}
print('the bot\'s score against the human model (its share of results):')
for a, r in A.items():
    if r:
        m, se = ms([v if a in ('acc0', 'd4_0', 'acc0_h4', 'd4_0_h4') else 1 - v for v in r.values()]); print(f'  {a:5s} {len(r):4d} games  {100 * m:5.1f}% ± {100 * se:.1f}')
gains = []; res = {}
for lab, (d4, acc, sgn) in (('bot on side 0', ('d4_0', 'acc0', 1)), ('bot on side 1', ('d4_1', 'acc1', -1)),
                             ('bot on side 0, opponent on the d4 net', ('d4_0_h4', 'acc0_h4', 1))):
    jobs = sorted(set(A[d4]) & set(A[acc]))
    if not jobs: continue
    g = [sgn * (A[d4][j] - A[acc][j]) for j in jobs]; gains += g
    res[lab] = (sum(g) / len(g), len(g)); m, se = ms(g); print(f'd4 - deployed, {lab}: {100 * m:+.1f} ± {100 * se:.1f} points a game over {len(jobs)} starts ({sum(1 for x in g if x)} results differ)')
if gains:
    m, se = ms(gains); print(f'd4 - deployed, all pairs: {100 * m:+.1f} ± {100 * se:.1f} points a game over {len(gains)} pairs')
if 'bot on side 0' in res and 'bot on side 0, opponent on the d4 net' in res:
    a, b = res['bot on side 0'][0], res['bot on side 0, opponent on the d4 net'][0]
    print(f'd4 - deployed, bot on side 0, averaged over the two opponents: {100 * (a + b) / 2:+.1f} points a game')
