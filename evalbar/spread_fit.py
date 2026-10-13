"""Which bulk investments fit the damage a species actually took, game by game (the user asked, 2026-10-12, to check that Mega Floette's
lower-than-predicted damage taken is its spread and not its data): for each cached replay where it took clean hits, every (HP, Def,
SpD) point investment on a grid is tried against every hit (damage.js, the attackers at their guessed spreads), and the investments
that fit all of that game's hits (exactly, no slack) are kept. Summed over games: how often the most used Smogon spread fits, and what
the fitting investments look like.
  python3 evalbar/spread_fit.py <species, e.g. Floette-Mega> [games=400]      -> evalbar/out/spreadfit/<species>.json and a summary"""
import os, sys, json, time, statistics, subprocess, collections
import common as C, spreads as SPR, procs as P, replay as R, mega_check as MC
OUT = os.path.join(C.HERE, 'out', 'spreadfit'); STEP = [0, 4, 8, 12, 16, 20, 24, 28, 32]
def grid(nature):
    """(hp, def, spd) points totalling at most 66, the rest put in Sp. Atk then Speed (they do not change damage taken)"""
    for hp in STEP:
        for de in STEP:
            for sd in STEP:
                if hp + de + sd <= 66:
                    rest = 66 - hp - de - sd; spa = min(32, rest); spe = min(32, rest - spa)
                    yield [hp, 0, de, spa, sd, spe]
def fits(pct, r):
    if not r or r.get('lo') is None: return None
    return SPR.damage_fits({'pct': tuple(pct), 'atleast': False}, r, 0)
if __name__ == '__main__':
    P.own(); R.BATON_PASS = R.MEGA_ABIL = True
    who = sys.argv[1]; n = next((int(x[6:]) for x in sys.argv[2:] if x.startswith('games=')), 400)
    os.makedirs(OUT, exist_ok=True); prog = os.path.join(OUT, who + '.games'); open(prog, 'w').close()
    games = [(rid, log) for rid, log in C.games() if 'regmcbo3' in rid and who.split('-')[0] in log]
    json.dump({'title': f'Spread fit: {who} (games scanned)', 'out': os.path.relpath(prog, os.path.join(C.HERE, 'out')), 'total': len(games), 'done0': 0,
               'started': time.time(), 'threads': 2, 'seeds': 0, 'staged': False}, open(prog + '.run.json', 'w'))
    per_game = []; qf, of = os.path.join(OUT, 'q.json'), os.path.join(OUT, 'r.json')
    for rid, log in games:
        with open(prog, 'a') as fh: fh.write(rid + '\n')
        if len(per_game) >= n: break
        try: hs = [(q, m) for q, m in MC.hits(rid, log) if m['def'] == who]
        except Exception: continue
        if not hs: continue
        d = hs[0][0]['def']; nature = hs[0][0]['spec']['sides'][d[0]]['mons'][d[1]].get('nature')
        pts = list(grid(nature)); queries = []
        for q, m in hs:
            for e in pts:
                q2 = json.loads(json.dumps(q)); q2['spec']['sides'][q['def'][0]]['mons'][q['def'][1]]['evs'] = e; queries.append(q2)
        json.dump(queries, open(qf, 'w'))
        subprocess.run([P.exe('node'), os.path.join(C.HERE, 'damage.js'), qf, of], cwd=os.path.join(C.MAIN, 'pssim'), check=True, capture_output=True)
        res = json.load(open(of)); ok = {tuple(e): True for e in pts}
        for i, (q, m) in enumerate(hs):
            for j, e in enumerate(pts):
                f = fits(m['pct'], res[i * len(pts) + j])
                if f is False: ok[tuple(e)] = False
        per_game.append({'game': rid.split('-')[-1], 'nature': nature, 'hits': [(m['att'], m['move'], m['cat'], m['pct']) for _, m in hs],
                         'fit': [list(e) for e in pts if ok[tuple(e)]]})
    json.dump(per_game, open(os.path.join(OUT, who + '.json'), 'w'))
    # summary: does Smogon's most used spread (for that nature) fit, and the investments that do
    top = collections.Counter(); fit1 = nofit = 0; hpdef = collections.Counter(); bulk = []
    for g in per_game:
        rk = SPR.ranked(who.replace('-Mega', '-Eternal') if 'Floette' in who else who.split('-Mega')[0], g['nature'], '') or SPR.ranked(who.split('-')[0], g['nature'], '')
        s1 = rk[0][1] if rk else None
        if not g['fit']: nofit += 1; continue
        if s1 and any(abs(e[0] - s1[0]) <= 2 and abs(e[2] - s1[2]) <= 2 and abs(e[4] - s1[4]) <= 2 for e in g['fit']): fit1 += 1
        bulk.append(statistics.median([e[0] + e[2] + e[4] for e in g['fit']]))
        for e in g['fit']: hpdef[(e[0], e[2], e[4])] += 1 / len(g['fit'])
    k = len(per_game)
    print(f'{who}: {k} games with clean hits taken; no investment on the grid fits {nofit}; Smogon #1 (for the nature) fits {fit1} of {k - nofit}')
    if bulk: print(f'  bulk points (HP+Def+SpD) of the fitting investments, median per game: median {statistics.median(bulk)}, quartiles {[round(x) for x in statistics.quantiles(bulk, n=4)]}')
    print('  most supported (HP, Def, SpD):', [(k_, round(v, 1)) for k_, v in hpdef.most_common(8)])
