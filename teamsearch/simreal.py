"""How close are the sim's archetype matchups to real regional results? For the 10 simcmp teams (their latest six, brings and
confirm seeds), per opposing archetype: the teams' mean sim win share vs the real per-game rate of regional teams of the same
archetypes against it (archmatch.real_regionals, Bo3 match rates converted to per-game). Each setup's overall offset is removed
(our teams are climbed, so they win more than typical teams of their archetype); what's left is the gap in log-odds
(+ = the sim makes that opponent too easy). RMS over all 10 archetypes and over the 9 without Perish (scored from real data
in the climb, see perish_stock.py). Analysis only: reads cached runs.
  python3 simreal.py [setup ...]        setups: v3 (cloud_results) and any TS_SIM name with outputs in runs/ (default: v3 v8)
"""
import json, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'bring'))
setups = [a for a in sys.argv[1:] if not a.startswith('--')] or ['v3', 'v8']
sys.argv = sys.argv[:1]
os.environ.pop('TS_PERISH', None)
import archmatch as AM, evaluate as E, simcmp as S
lg = lambda p: math.log(max(1e-3, min(1 - 1e-3, p)) / (1 - max(1e-3, min(1 - 1e-3, p))))

def load(setup, n):
    team, fixed, label, seed = S.latest(n)
    key = f'{E.team_key(team)}_{label}'
    if setup == 'v3': return E.read(os.path.join(HERE, 'cloud_results', 'runs', key), f'{seed}_4')
    return E.read(os.path.join(HERE, 'runs', key), f'{setup}_{seed}_4')

if __name__ == '__main__':
    rw, rn = AM.real_regionals()
    real = {k: AM.game_rate(rw[k] / rn[k]) for k in rn if rn[k] >= 20}
    teams = [(n, AM.arch([E.G[g]['species'] for g in S.latest(n)[0]])) for n in S.DEFAULT]
    res = {s: {n: load(s, n) for n, _ in teams} for s in setups}
    rows = []
    for a in E.ARCHS:
        B = AM.ARCH_MAP[a]; ok = [(n, A) for n, A in teams if (A, B) in real]
        if len(ok) < 6: continue
        r = sum(real[(A, B)] for _, A in ok) / len(ok)
        rows.append((a, r, {s: sum(res[s][n]['by_arch'][a] for n, _ in ok) / len(ok) for s in setups}))
    print(f"{len(teams)} teams; real = regional teams of the same archetypes (per-game rates)\n")
    print(f"{'opponent':30s} {'real':>6s} " + ' '.join(f"{s:>8s}" for s in setups) + "   gap after offset (log-odds)")
    gaps = {}
    for excl in (False, True):
        use = [x for x in rows if not (excl and x[0] == E.PERISH)]
        for s in setups:
            off = sum(lg(x[2][s]) - lg(x[1]) for x in use) / len(use)
            gaps[(s, excl)] = {x[0]: lg(x[2][s]) - lg(x[1]) - off for x in use}
    for a, r, sim in rows:
        print(f"{a[:30]:30s} {100 * r:5.1f}% " + ' '.join(f"{100 * sim[s]:7.1f}%" for s in setups) + "   "
              + '  '.join(f"{s} {gaps[(s, False)][a]:+.2f}" for s in setups))
    print()
    for s in setups:
        rms = lambda g: math.sqrt(sum(v * v for v in g.values()) / len(g))
        print(f"{s:8s} RMS gap: all 10 {rms(gaps[(s, False)]):.2f}, without Perish {rms(gaps[(s, True)]):.2f} log-odds "
              f"(offset re-fitted on the 9)")
    print("sim-noise floor about 0.14 log-odds per archetype (240 games)")
