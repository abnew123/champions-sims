"""Where do the bot's ladder opponents' 'mistakes' go? (2026-10-12, the user: the bot's turn-1 win chance predicts its results, yet
against the bot's equilibrium mix any opponent play outside its own mix can only help the bot, so the estimate should creep up; which
of the human 'mistakes' are not mistakes?) On bot/decision_audit.py's rebuilt and solved decisions (the bot's games, the plays both
sides made known from the logs):
  ledger   per decision where both sides' plays are known: the model's predicted change of the bot's win chance from the opponent's play
           (its joint action valued against the bot's mix, minus the game value) and from the bot's own play, against the change that
           happened (the next decision's estimate, or the result after the last one); all as real win chances (log-odds x CAL)
  lines    every opponent slot play, classed by kind (pssim/human_lines.py's classes), disliked (under 5% in the planner's mix for it) or
           agreed (30%+): the opponent's actual win rate minus the planner's rating of the play (its best joint containing it against the
           bot's mix, rescaled). Positive: the play works better than the planner says. Standard errors clustered by game.
  .venv/bin/python3 bot/ladder_lines.py <audit prefix, e.g. bot/out/pos/audit>"""
import os, sys, json, math, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'pssim'))
import human_lines as HL
CAL = 0.7538   # the sym2-era solves this analysis was run on (v25); the live bot uses live.CAL (0.676) since 2026-10-14
real = lambda v: HL.resc(v, CAL)
def cse(pairs):
    """mean and game-clustered standard error of values given as (game, x)"""
    by = collections.defaultdict(list)
    for g, x in pairs: by[g].append(x)
    n = sum(len(v) for v in by.values())
    if n == 0: return 0.0, 0.0, 0
    mu = sum(x for _, x in pairs) / n
    var = sum((sum(x - mu for x in v)) ** 2 for v in by.values()) / n ** 2
    return mu, var ** 0.5, n
def main(prefix):
    meta = json.load(open(prefix + '.meta.json'))['turns']
    rows = {r['name']: r for r in map(json.loads, open(prefix + '_turns.eval.jsonl')) if 'error' not in r}
    G = {g['room']: g for g in map(json.loads, open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl')))}
    seq = collections.defaultdict(list)
    for name, m in meta.items():
        r = rows.get(name + ' h0 p1')
        if r and G[m['room']]['won'] is not None: seq[m['room']].append((m['turn'], r))
    led = []; lines = []
    for room, D in seq.items():
        D.sort(key=lambda x: x[0]); won = 1.0 if G[room]['won'] else 0.0
        for i, (t, r) in enumerate(D):
            s0, s1 = r['sides'][0], r['sides'][1]; v = r['value']
            nxt = real(D[i + 1][1]['value']) if i + 1 < len(D) and D[i + 1][0] == t + 1 else (won if i + 1 == len(D) else None)
            if s0.get('actual_v') is not None and s1.get('actual_v') is not None and nxt is not None:
                led.append((room, real(1 - s1['actual_v']) - real(v), real(s0['actual_v']) - real(v), nxt - real(v)))
            for sl in s1['slots']:
                o = next((x for x in sl['options'] if x.get('actual')), None)
                if not o: continue
                kd, _ = HL.kind(o['label'])
                lines.append((room, kd, o['w'], (1 - won) - real(o['v']), real(max(x['v'] for x in sl['options'])) - real(o['v'])))
    print(f"ledger: {len(led)} decisions with both plays known, in {len(set(x[0] for x in led))} games (bot's win chance, points)")
    for lab, k in (("predicted from the opponent's play", 1), ("predicted from the bot's own play", 2), ('what happened', 3)):
        mu, se, n = cse([(x[0], x[k]) for x in led]); print(f"  {lab:38s} {100 * mu:+6.2f} ± {100 * se:.2f} per decision")
    mu, se, n = cse([(x[0], x[3] - x[1] - x[2]) for x in led]); print(f"  {'happened minus predicted':38s} {100 * mu:+6.2f} ± {100 * se:.2f} per decision")
    print(f"\nopponent slot plays: {len(lines)}; by kind, the opponent's win rate minus the planner's rating of the play (points, ± SE by game)")
    print(f"  {'kind':22s} {'n':>5s} {'share':>6s} {'disliked n':>10s} {'their regret':>12s} {'disliked: actual-rated':>22s} {'agreed: actual-rated':>21s}")
    K = collections.defaultdict(list)
    for x in lines: K[x[1]].append(x)
    for kd, xs in sorted(K.items(), key=lambda kv: -len(kv[1])):
        dis = [x for x in xs if x[2] < 0.05]; agr = [x for x in xs if x[2] >= 0.3]
        md, sd, nd = cse([(x[0], x[3]) for x in dis]); ma, sa, na = cse([(x[0], x[3]) for x in agr])
        reg = sum(x[4] for x in dis) / max(1, len(dis))
        print(f"  {kd:22s} {len(xs):5d} {100 * len(xs) / len(lines):5.1f}% {nd:10d} {100 * reg:11.1f}  {100 * md:+12.1f} ± {100 * sd:4.1f}     {100 * ma:+10.1f} ± {100 * sa:4.1f} (n {na})")
    dis = [x for x in lines if x[2] < 0.05]; agr = [x for x in lines if x[2] >= 0.3]
    md, sd, nd = cse([(x[0], x[3]) for x in dis]); ma, sa, na = cse([(x[0], x[3]) for x in agr])
    print(f"  all disliked plays (n {nd}): {100 * md:+.1f} ± {100 * sd:.1f}; all agreed plays (n {na}): {100 * ma:+.1f} ± {100 * sa:.1f}; the planner charges the disliked ones {100 * sum(x[4] for x in dis) / max(1, nd):.1f} points each")
if __name__ == '__main__':
    main(sys.argv[1])
