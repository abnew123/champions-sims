"""After a round of the miss-doubling climb (user, 2026-10-06): did it find a strategy that profits from its own misses?
The set pool holds no Blunder Policy and the climb's move data has no crash moves, so what can pay off is: Stomping Tantrum /
Temper Flare (doubled after a failed move), accuracy abilities (No Guard is a legitimate bypass, Compound Eyes / Keen Eye / Victory
Star raise p before the rule doubles the miss chance), and more inaccurate moves than the control climb. Compares the miss climb
(climb_poolmiss) with the control (climb_pool) and with the starts, and lists the miss climb's swaps that brought one in.
  ../.venv/bin/python3 misscheck.py [results dir = cloud_results/pool] [miss prefix = climb_poolmiss] [control prefix = climb_pool]
"""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import evaluate as E
M = json.load(open(os.path.join(HERE, '..', 'native', 'champions_data_full.json')))['moves']
mid = lambda n: ''.join(c for c in n.lower() if c.isalnum())
BOOSTED = {'stompingtantrum', 'temperflare'}
ABIL = {'No Guard', 'Compound Eyes', 'Keen Eye', 'Victory Star', 'Hustle'}

def acc(mv):
    x = M.get(mid(mv)); a = x['accuracy'] if x else True
    return None if a is True else a

def flags(g):
    s = E.G[g]; out = [m for m in s['moves'] if mid(m) in BOOSTED]
    if s['item'] == 'Blunder Policy': out.append('Blunder Policy')
    if s['ability'] in ABIL: out.append(s['ability'])
    out += [m for m in s['moves'] if (M.get(mid(m)) or {}).get('hasCrashDamage')]
    return out

def profile(teams):
    """per team list: sets with a flag, inaccurate moves (count, mean hit chance as written; under the rule max(0, 2p - 100))"""
    f = collections.Counter(); n_inacc = 0; ps = []; n_moves = 0
    for t in teams:
        for g in t:
            for x in flags(g): f[x] += 1
            for mv in E.G[g]['moves']:
                n_moves += 1; a = acc(mv)
                if a is not None and a < 100: n_inacc += 1; ps.append(a)
    k = max(1, len(teams))
    return dict(flags=dict(f), inaccurate_per_team=n_inacc / k, mean_p=sum(ps) / len(ps) if ps else None,
                mean_p_rule=sum(max(0, 2 * p - 100) for p in ps) / len(ps) if ps else None)

def load(d, prefix):
    s = json.load(open(os.path.join(d, f'{prefix}_state.json'))); return s

if __name__ == '__main__':
    d = os.path.join(HERE, sys.argv[1] if len(sys.argv) > 1 else os.path.join('cloud_results', 'pool'))
    miss = sys.argv[2] if len(sys.argv) > 2 else 'climb_poolmiss'; ctrl = sys.argv[3] if len(sys.argv) > 3 else 'climb_pool'
    S = {p: load(d, p) for p in (miss, ctrl) if os.path.exists(os.path.join(d, f'{p}_state.json'))}
    starts = {}
    for name, t in S[miss]['teams'].items():                       # undo the path to get the start
        team = list(t['team'])
        for step in reversed(t['path']): team[step['slot']] = step['out']
        starts[name] = team
    rows = [('starts', profile(starts.values()))] + [(p + f" (round {S[p]['round']})", profile([t['team'] for t in S[p]['teams'].values()])) for p in S]
    for label, r in rows:
        mp = f"{r['mean_p']:.1f}" if r['mean_p'] is not None else '-'
        mr = f"{r['mean_p_rule']:.1f}" if r['mean_p_rule'] is not None else '-'
        print(f"{label:28s} inaccurate moves per team {r['inaccurate_per_team']:.2f} (mean accuracy {mp}, under the rule {mr})   flagged sets: {r['flags']}")
    print(f"\n{miss}: swaps that brought in a flagged set or more inaccurate moves")
    for name, t in S[miss]['teams'].items():
        for step in t['path']:
            fi, fo = flags(step['into']), flags(step['out'])
            ai = sum(1 for m in E.G[step['into']]['moves'] if (acc(m) or 100) < 100); ao = sum(1 for m in E.G[step['out']]['moves'] if (acc(m) or 100) < 100)
            if fi and fi != fo or ai > ao:
                print(f"  {name:22s} {step['out']:18s} -> {step['into']:18s} +{100 * step['diff']:.1f} ± {100 * step['se']:.1f}   "
                      f"in: {', '.join(fi) or '-'} / {ai} inaccurate   out: {', '.join(fo) or '-'} / {ao} inaccurate   "
                      f"moves in: {', '.join(E.G[step['into']]['moves'])}")
