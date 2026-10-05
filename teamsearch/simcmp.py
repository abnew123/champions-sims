"""Would the climb's ranking change under the new sim setup? For a handful of teams, replay each team's latest confirm games
(same six, same brings, same 240 seeds) under TS_SIM=v8 (two-turn Protect check, damage-race value features, egvalue7) and
compare with the cached v3 results from the AWS climb (cloud_results/runs). Fixed brings were chosen under v3, which costs every
team a little under v8, about equally.
  TS_THREADS=10 python3 simcmp.py [start ...]      (default: the leaders, the user's teams, unchanged strong starts, a sleep/setup team)
  python3 simcmp.py --report                        print the table from what has been run so far, no battles
"""
import json, os, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ['TS_SIM'] = 'v8'
import evaluate as E
P = E.P
DEFAULT = ['Frankfurt-10', 'Frankfurt-05', 'Baltimore-12',          # the climb's leaders (Mega Delphox + Scarf Garchomp + Incineroar)
           'trick_room_six', 'low_variance_six',                   # the user's teams
           'Baltimore-14', 'Frankfurt-09', 'Frankfurt-15',         # other high finishers; the last two never moved
           'Frankfurt-06', 'Brisbane-07']                          # Venusaur sun (Sleep Powder), Mega Floette (Calm Mind)
log = [json.loads(l) for l in open(os.path.join(HERE, 'cloud_results', 'climb_log.jsonl'))]

def latest(start):
    r = [x for x in log if x['start'] == start][-1]
    moved = r['best']['diff'] > r['best']['se']
    team = [g for g in r['team'] if g != r['best']['out']] + [r['best']['into']] if moved else r['team']
    brings = r['brings_best'] if moved else r['brings_current']
    fixed = {a: (v[0], v[1]) for a, v in brings.items()}
    label = 'fx' + hashlib.md5(json.dumps(fixed, sort_keys=True).encode()).hexdigest()[:8]
    return team, fixed, label, 500000 + 1000 * r['round']

if __name__ == '__main__':
    report = '--report' in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith('--')] or DEFAULT
    thr = int(os.environ.get('TS_THREADS', 3)); rows = []
    for n in names:
        team, fixed, label, seed = latest(n)
        old = E.read(os.path.join(HERE, 'cloud_results', 'runs', f'{E.team_key(team)}_{label}'), f'{seed}_4')
        d = os.path.join(HERE, 'runs', f'{E.team_key(team)}_{label}')
        if report:
            try: new = E.read(d, E.out_tag(seed, 4))
            except Exception: new = None
        else:
            new = E.run_team(team, 4, seed, thr, fixed=fixed, label=label)
            print(f"{n}: v3 {100 * old['score']:.1f} -> v8 {100 * new['score']:.1f}", flush=True)
        rows.append((n, team, old, new))
    done = [r for r in rows if r[3]]
    ro = {r[0]: i + 1 for i, r in enumerate(sorted(done, key=lambda r: -r[2]['score']))}
    rn = {r[0]: i + 1 for i, r in enumerate(sorted(done, key=lambda r: -r[3]['score']))}
    print(f"\n{'team':17s} {'v3':>6s} {'v8':>6s} {'change':>7s}  rank v3 -> v8   (240 games each, SE about 3 points per score)")
    for n, team, old, new in sorted(done, key=lambda r: -r[3]['score']):
        print(f"{n:17s} {100 * old['score']:6.1f} {100 * new['score']:6.1f} {100 * (new['score'] - old['score']):+7.1f}  {ro[n]:2d} -> {rn[n]:2d}   "
              f"{', '.join(sorted(E.G[g]['species'] for g in team))}")
    if done:
        print('\nby opposing archetype, mean over these teams (v3 -> v8):')
        for a in E.ARCHS:
            o = sum(r[2]['by_arch'][a] for r in done) / len(done); w = sum(r[3]['by_arch'][a] for r in done) / len(done)
            print(f"  {a[:30]:30s} {100 * o:5.1f} -> {100 * w:5.1f}  ({100 * (w - o):+.1f})")
        json.dump({r[0]: dict(v3=r[2]['score'], v8=r[3]['score'], v3_by_arch=r[2]['by_arch'], v8_by_arch=r[3]['by_arch']) for r in done},
                  open(os.path.join(HERE, 'simcmp.json'), 'w'), indent=1)
