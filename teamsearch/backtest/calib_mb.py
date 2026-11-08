"""M-B calibration sims (the user, 2026-11-07: "start the calibration sims"). Goal 1 of two: the meta estimate should calibrate the sim on
real outcomes, player errors included (easier teams are over-represented in a meta); goal 2, a team for that meta, keeps the raw sim.
For the M-B to M-C backtest the calibration uses M-B ladder games only (backtest/mb_pool.json: public Bo3 games, Aug 19 - Sep 8, both
open team sheets and the winner; no M-C data).
The sim (v41n1) plays N sampled real games as they were played: both sheets' sets (spreads from August's M-B stats, L.fill_spread via
TS_MOVESET), each side's four as brought, leads first (the log's leads and revealed Pokemon, completed as in build_mb.pool()). R games
with each side as "mine", independent seeds -> the sim's win chance for the game's side p1. calibrate later fits real outcomes on it.
Sampling: games whose 12 sets the engine runs, stratified by the pair of generic team types (type_of: Trick Room, Perish, a weather,
Tailwind, other; from moves and abilities, so they apply to M-C's new species too, and never M-C-derived core rules): each type pair
gets min(its games, a cap), the cap set so the total is N.
Out: backtest/calib_mb.jsonl, one line per game (game id, side p1's result, ratings, both sides' generic traits, the sim's wins as
each side); resumable (done games are skipped; the game cache keeps finished battles). Log backtest/calib_mb.log (progress card).
  TS_MOVESET=backtest/smogon_mb_2026-08_moveset.txt bin/teamsearch-py backtest/calib_mb.py [N=2500] [R=6]
v43 (the user, 2026-11-07: "we should support Bug Bite, Cute Charm, ..."): v41 left some mechanics unsupported (6% of sim games).
Battle sim's champ-battle-v43 ports them; games whose brought fours carry none of them are identical on v41 and v43. The games whose
fours carry one (calib_v43_affected.json, 258 of the 2,500) are left out of the v41 pass and played on v43n1 (starts rebuilt with
genders) into calib_mb_v43.jsonl; the fit takes a game's v43 line over its v41 line.
  TS_MOVESET=... bin/teamsearch-py backtest/calib_mb.py v43 [N=2500] [R=6]
"""
import json, os, sys, time, random, hashlib, collections
HERE = os.path.dirname(os.path.abspath(__file__)); TS = os.path.dirname(HERE)
sys.path.insert(0, TS); sys.path.insert(0, os.path.join(TS, '..', 'pssim'))
os.environ.setdefault('TS_SIM', 'v41n1'); os.environ.setdefault('TS_GAME_CACHE', os.path.join(TS, 'cache_bt', 'games.sqlite'))
import sets_lib as L
import evaluate as E
import build_lowelo_starts as B
V43 = len(sys.argv) > 1 and sys.argv[1] == 'v43'
if V43: sys.argv.pop(1); os.environ['TS_SIM'] = 'v43n1'
AFF = set(json.load(open(os.path.join(HERE, 'calib_v43_affected.json')))['affected'])
OUT = os.path.join(HERE, 'calib_mb_v43.jsonl' if V43 else 'calib_mb.jsonl'); LOG = os.path.join(HERE, 'calib_mb.log'); CHUNK = 100; SEED0 = 770000
FULL = os.path.join('..', 'native', 'engine_data_full.json')
WEATHER = {'Drought': 'sun', 'Drizzle': 'rain', 'Sand Stream': 'sand', 'Snow Warning': 'snow', 'Orichalcum Pulse': 'sun'}
REDIRECT = {'Follow Me', 'Rage Powder'}; SCREENS = {'Reflect', 'Light Screen', 'Aurora Veil'}
SURGE = {'Grassy Surge', 'Psychic Surge', 'Electric Surge', 'Misty Surge'}

def say(s):
    with open(LOG, 'a') as f: f.write(f"{time.strftime('%I:%M %p')} {s}\n")

def traits(six):
    """generic team traits from the sets (a Mega counts with its Mega ability and stats)"""
    t = collections.Counter(); spe = []
    for s in six:
        fm = L.battle_forme(s['species'], s.get('item')); d = L.DEX['species'].get(L.idf(fm)) or L.DEX['species'].get(L.idf(s['species'])) or {}
        mega = bool(d.get('isMega')); ab = next(iter(d['abilities'].values())) if mega and d.get('abilities') else s.get('ability')
        mv = set(s.get('moves') or [])
        t['tr'] += 'Trick Room' in mv; t['tailwind'] += 'Tailwind' in mv; t['perish'] += 'Perish Song' in mv
        t['fakeout'] += 'Fake Out' in mv; t['redirect'] += bool(mv & REDIRECT); t['screens'] += bool(mv & SCREENS)
        t['intimidate'] += ab == 'Intimidate'; t['terrain'] += ab in SURGE; t['mega'] += mega
        w = WEATHER.get(ab) or ('sun' if 'Sunny Day' in mv else 'rain' if 'Rain Dance' in mv else None)
        if w: t[w] += 1
        if d.get('stats'): spe.append(d['stats']['spe'])
    t = dict(t); t['speed'] = round(sum(spe) / len(spe), 1) if spe else None
    return t

def type_of(t):
    if t.get('tr'): return 'Trick Room'
    if t.get('perish'): return 'Perish'
    for w in ('rain', 'sun', 'sand', 'snow'):
        if t.get(w): return w.capitalize()
    return 'Tailwind' if t.get('tailwind') else 'Other'

def four(e):
    lead = list(e['lead']); rest = [x for x in e['bring'] if x not in lead]
    return lead + rest if len(lead) == 2 and len(lead + rest) == 4 else None

def games():
    """[(game id, {p1: entry, p2: entry})] with both sheets runnable, a winner and a four per side"""
    by = collections.defaultdict(dict)
    for e in json.load(open(os.path.join(HERE, 'mb_pool.json')))['entries']: by[e['id']][e['side']] = e
    out, full = [], {}
    for gid, sd in by.items():
        if set(sd) != {'p1', 'p2'} or sd['p1']['won'] is None or not all(four(sd[s]) for s in sd): continue
        ok = True
        for s in ('p1', 'p2'):
            for x in sd[s]['six']:
                k = json.dumps(x, sort_keys=True)
                if k not in full:
                    try: f = B.full(L.normalize(x)); full[k] = f if B.runnable(f) else None
                    except Exception: full[k] = None
                ok &= full[k] is not None
        if ok: out.append((gid, sd))
    return out, full

def sample(G, n):
    rng = random.Random(0); by = collections.defaultdict(list)
    for g in G: by[tuple(sorted((type_of(traits(g[1]['p1']['six'])), type_of(traits(g[1]['p2']['six'])))))].append(g)
    lo, hi = 1, max(len(v) for v in by.values())
    while lo < hi:                                                       # the smallest cap that reaches n
        c = (lo + hi) // 2
        if sum(min(len(v), c) for v in by.values()) >= n: hi = c
        else: lo = c + 1
    pick = []
    for k in sorted(by): pick += rng.sample(by[k], min(len(by[k]), lo))
    rng.shuffle(pick)
    return pick[:n], {f'{a} vs {b}': min(len(v), lo) for (a, b), v in sorted(by.items())}, lo

def main():
    assert os.environ.get('TS_MOVESET', '').endswith('smogon_mb_2026-08_moveset.txt'), 'run with TS_MOVESET=backtest/smogon_mb_2026-08_moveset.txt'
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2500; R = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    thr = int(os.environ.get('TS_THREADS', 3))
    G, full = games(); pick, strata, cap = sample(G, n)
    pick = [g for g in pick if (g[0] in AFF) == V43]                     # v43 mechanics: on v43n1 only; the rest on v41n1
    done = {json.loads(l)['id'] for l in open(OUT)} if os.path.exists(OUT) else set()
    todo = [g for g in pick if g[0] not in done]
    say(f"{E.sim()}: calibration sims on {len(pick)} of {len(G)} usable M-B games ({len(todo)} to play), {R} games a side each, {thr} threads; "
        + ("the games whose fours carry a v43 mechanic" if V43 else
           f"type pairs capped at {cap} games, less the {len(AFF)} on v43: " + ', '.join(f'{k} {v}' for k, v in strata.items())))
    gids = tuple(json.load(open(os.path.join(HERE, 'mb_field.json')))['mb1']['gids'])         # names the run folders only (explicit jobs)
    import poolmode as PM
    t0 = time.time(); nd = len(pick) - len(todo)
    for c in range(0, len(todo), CHUNK):
        part = todo[c:c + CHUNK]; jobs, meta = [], []
        for gid, sd in part:
            sets = {s: {x['species']: full[json.dumps(x, sort_keys=True)] for x in sd[s]['six']} for s in ('p1', 'p2')}
            fours = {s: [{k: sets[s][sp][k] for k in ('species', 'item', 'ability', 'nature', 'evs', 'moves')} for sp in four(sd[s])] for s in ('p1', 'p2')}
            for me, op in (('p1', 'p2'), ('p2', 'p1')):
                for r in range(R):
                    si = int(hashlib.md5(f'{gid}|{me}|{r}'.encode()).hexdigest()[:8], 16) % 10 ** 8
                    jobs.append(dict(mine=fours[me], theirs=fours[op], meta=dict(pool_id=gid, pool_side=me, group='calib', arch='', rating=sd[me]['rating'], seed_index=si)))
                    meta.append((gid, me))
        h = hashlib.md5(json.dumps([g for g, _ in part]).encode()).hexdigest()[:8]
        rows = E.run_jobs(gids, jobs, 1, SEED0, thr, f'calibmb_{E.sim()}_{h}', extra=dict(TS_ENGINE_DATA=FULL, SEED_PER_JOB='1'))
        acc = collections.defaultdict(lambda: [0.0, 0])
        for m, r in zip(meta, rows):
            w, k = PM._wins(r); acc[m][0] += w; acc[m][1] += k
        with open(OUT, 'a') as f:
            for gid, sd in part:
                (w1, n1), (w2, n2) = acc[(gid, 'p1')], acc[(gid, 'p2')]
                f.write(json.dumps(dict(id=gid, won_p1=bool(sd['p1']['won']), rating=sd['p1']['rating'], day=sd['p1']['day'],
                                        players=[sd['p1']['player'], sd['p2']['player']],
                                        traits={s: traits(sd[s]['six']) for s in ('p1', 'p2')}, types={s: type_of(traits(sd[s]['six'])) for s in ('p1', 'p2')},
                                        sim=dict(p1_wins=w1, p1_n=n1, p2_wins=w2, p2_n=n2),
                                        p_sim=round((w1 + (n2 - w2)) / (n1 + n2), 4) if n1 + n2 else None)) + '\n')
        nd += len(part)
        say(f"  score (real M-B games{', v43' if V43 else ''}): {nd}/{len(pick)} games, {int((time.time() - t0) / 60)} min")
    say('calibration sims on v43 done' if V43 else 'calibration sims done')

if __name__ == '__main__': main()
