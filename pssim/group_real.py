"""Real win rates by core group (2026-10-06), the reference for the sim-vs-real bar once the sim plays the empirical opponent pool.
Two sources: the Reg M-C regionals (teamsearch/regmatch/*.json: every Swiss / top-cut match between two players with team sheets,
best-of-3 results converted to per-game rates as archmatch.py does) and the ladder (opp_pool.json: both sides of every cached Bo3 game,
single games). Groups from the core rules used by the pool (opp_pool.json carries them); teams no rule names are 'other'.
  ../.venv/bin/python3 group_real.py [min matches per cell = 15]   -> results/group_real.txt + .json
Per group: share of teams and overall win rate in each source; per group pair with enough matches: real per-game win rate and count."""
import json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cluster_opps import tag, norm
HERE = os.path.dirname(os.path.abspath(__file__)); TS = os.path.join(HERE, '..', 'teamsearch')
FORM = {'Indeedee [Female]': 'Indeedee-F', 'Indeedee [Male]': 'Indeedee', 'Ninetales [Alolan Form]': 'Ninetales-Alola'}
def game_rate(pm):
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if mid * mid * (3 - 2 * mid) < pm: lo = mid
        else: hi = mid
    return (lo + hi) / 2
def main(min_n):
    pool = json.load(open(os.path.join(HERE, 'opp_pool.json'))); rules = pool['rules']
    # regionals: matches between sheeted players
    rw, rn = collections.Counter(), collections.Counter(); rteams = collections.Counter()
    for f in ('f192.json', 'f193.json', 'f194.json'):
        d = json.load(open(os.path.join(TS, 'regmatch', f)))
        grp = {p['name']: tag([FORM.get(m['name'], m['name'].split(' [')[0]) for m in p['decklist']], rules) for p in d if len(p.get('decklist') or []) == 6}
        for g in grp.values(): rteams[g] += 1
        for p in d:
            if p['name'] not in grp: continue
            for r in (p.get('rounds') or {}).values():
                if r.get('name') in grp and r.get('result') in ('W', 'L'):
                    k = (grp[p['name']], grp[r['name']]); rn[k] += 1; rw[k] += r['result'] == 'W'
    # ladder: both sides of each pool game
    by_game = collections.defaultdict(dict)
    for e in pool['entries']: by_game[e['id']][e['side']] = e
    lw, ln = collections.Counter(), collections.Counter(); lteams = collections.Counter()
    for gid, sides in by_game.items():
        if 'p1' not in sides or 'p2' not in sides: continue
        a, b = sides['p1'], sides['p2']
        if a['won'] is None: continue
        for x, y in ((a, b), (b, a)):
            lteams[x['group']] += 1; k = (x['group'], y['group']); ln[k] += 1; lw[k] += x['won']
    groups = sorted(set(rteams) | set(lteams), key=lambda g: -(rteams[g] + lteams[g]))
    out = [f"{'group':62s} {'regional teams':>14s} {'win%':>5s} {'ladder sides':>12s} {'win%':>5s}"]
    for g in groups:
        rwin = sum(rw[(g, h)] for h in groups); rtot = sum(rn[(g, h)] for h in groups); lwin = sum(lw[(g, h)] for h in groups); ltot = sum(ln[(g, h)] for h in groups)
        out.append(f"{g[:62]:62s} {rteams[g]:14d} {100 * game_rate(rwin / rtot) if rtot else 0:5.1f} {lteams[g]:12d} {100 * lwin / ltot if ltot else 0:5.1f}")
    out.append(f"\ngroup pairs with at least {min_n} matches (regional: per-game rate from Bo3 results; ladder: single games)")
    cells = []
    for g in groups:
        for h in groups:
            if rn[(g, h)] >= min_n or ln[(g, h)] >= min_n:
                rr = game_rate(rw[(g, h)] / rn[(g, h)]) if rn[(g, h)] else None; lr = lw[(g, h)] / ln[(g, h)] if ln[(g, h)] else None
                cells.append({'group': g, 'vs': h, 'regional': [rw[(g, h)], rn[(g, h)], rr], 'ladder': [lw[(g, h)], ln[(g, h)], lr]})
                fr = f"{100 * rr:5.1f}%" if rr is not None else "   - "; fl = f"{100 * lr:5.1f}%" if lr is not None else "   - "
                out.append(f"{g[:40]:40s} vs {h[:40]:40s} regional {fr} ({rn[(g, h)]:3d}) ladder {fl} ({ln[(g, h)]:3d})")
    txt = '\n'.join(out) + '\n'; print(txt); os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
    open(os.path.join(HERE, 'results', 'group_real.txt'), 'w').write(txt)
    json.dump({'groups': [{'group': g, 'regional_teams': rteams[g], 'ladder_sides': lteams[g]} for g in groups], 'cells': cells}, open(os.path.join(HERE, 'results', 'group_real.json'), 'w'), indent=1)
if __name__ == '__main__': main(int(sys.argv[1]) if len(sys.argv) > 1 else 15)
