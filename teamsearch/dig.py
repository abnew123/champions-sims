"""Logged battles for the archetype matchups where the sim disagrees with real regional results (archmatch.py --regionals):
each case = a climb team (its latest six and the brings the climb chose for that archetype) vs one replay-model archetype,
GAMES per opposing lead pair, with BATTLE_LOG=1. Saves full logs to dig/<case>.json and prints a condensed play-by-play.
  TS_THREADS=3 python3 dig.py [case ...]        (default: all cases)
"""
import json, os, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import evaluate as E
P = E.P
LOGF = os.path.join(HERE, 'cloud_results', 'climb_log.jsonl')
CASES = {   # case: (start, archetype, why)
    'perish_f10': ('Frankfurt-10', 'Perish trap', 'Perish opponents: sim teams win 76%, real 48%'),
    'perish_tr6': ('trick_room_six', 'Perish trap', 'Perish opponents: sim teams win 76%, real 48%'),
    'rain_vs_tr': ('Frankfurt-14', 'Trick Room without Indeedee', 'Rain vs Trick Room: sim 71%, real 47%'),
    'sand_vs_snow': ('Baltimore-01', 'Snow', 'Sand vs Snow: sim 36%, real 53%'),
}
GAMES = int(os.environ.get('DIG_GAMES', 2))

def final_team(start):
    r = [json.loads(l) for l in open(LOGF) if json.loads(l)['start'] == start][-1]
    moved = r['best']['diff'] > r['best']['se']
    team = [g for g in r['team'] if g != r['best']['out']] + [r['best']['into']] if moved else r['team']
    return team, (r['brings_best'] if moved else r['brings_current'])

def condensed(log, me_species):
    """one line per turn: what each active Pokemon did (Showdown protocol lines), plus faints / weather / field changes"""
    out, cur = [], []
    for l in (log or '').split('\n') if isinstance(log, str) else (log or []):
        p = l.split('|')
        if len(p) < 2: continue
        if p[1] == 'turn':
            if cur: out.append(' · '.join(cur))
            cur = [f'T{p[2]}:']
        elif p[1] in ('move',): cur.append(f"{p[2][:3]} {p[2][5:]} {p[3]}" + (f" → {p[4][5:]}" if len(p) > 4 and p[4] else ''))
        elif p[1] in ('switch', 'drag'): cur.append(f"{p[2][:3]} in {p[3].split(',')[0]}")
        elif p[1] == 'faint': cur.append(f"✗ {p[2][5:]}")
        elif p[1] in ('-weather', '-fieldstart', '-fieldend', '-sidestart', '-sideend') and (len(p) < 4 or '[upkeep]' not in l): cur.append(f"[{p[2]}{(' ' + p[3]) if len(p) > 3 and p[1] != '-weather' else ''}]")
        elif p[1] == 'win': cur.append(f"WIN {p[2]}")
    if cur: out.append(' · '.join(cur))
    return out

if __name__ == '__main__':
    os.environ['BATTLE_LOG'] = '1'
    os.environ.setdefault('TS_BATTLE_BIN', os.path.join(E.ROOT, 'native', 'champ', 'bin', 'champ-battle-v3'))
    os.makedirs(os.path.join(HERE, 'dig'), exist_ok=True)
    for case in (sys.argv[1:] or CASES):
        start, arch, why = CASES[case]
        team, brings = final_team(start)
        lead, back = brings[arch]
        sp = lambda g: E.G[g]['species']
        jobs = [dict(arch=arch, k=k, lead=[sp(g) for g in lead], back=[sp(g) for g in back]) for k in range(P.K)]
        rows = E.run_jobs(team, jobs, GAMES, 777000, int(os.environ.get('TS_THREADS', 3)), f'dig_{case}')
        json.dump(rows, open(os.path.join(HERE, 'dig', case + '.json'), 'w'))
        wins = sum(x['v'] for r in rows for x in r['rows']); n = sum(len(r['rows']) for r in rows)
        print(f"\n===== {case}: {start} ({', '.join(sorted(sp(g) for g in team))}) vs {arch} — {why}")
        print(f"brings: lead {' + '.join(sp(g) for g in lead)}, back {' + '.join(sp(g) for g in back)}; our win share {wins}/{n}")
        for r in rows:
            for x in r['rows']:
                print(f"--- vs {r['pair']} (their four: {', '.join(r['theirs'])}) g{x['g']}: {'WIN' if x['v'] >= 0.5 else 'LOSS'} in {x['turns']} turns"
                      + (f", TR {x['trTurns']} turns" if x.get('trTurns') else ''))
                for line in condensed(x.get('log'), None)[:14]: print('   ', line)
