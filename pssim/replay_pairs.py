"""The sim replaying real pairings (2026-10-07): every cached Bo3 game whose two sides both have their brought four seen and both players
rated at least `min rating`, played by the planner from the humans' own leads and brings on both sides. Scored by style: the sim's win rate
against the real one on the same games, so a style the planner plays too well or too poorly shows up without any bring / lead confound
(in pool-vs-pool tests a team's bring, tailored to the opponent it really faced, meets a random opponent, which costs Trick Room and spares
Rain). Perish teams stay off in the sim (it cannot play the trap).
  ../.venv/bin/python3 replay_pairs.py jobs <out.json> [min rating=1150]     -> explicit battle_starts.js jobs with meta real_won
  SEED_PER_JOB=1 node ../native/battle_starts.js <jobs.json> <starts.jsonl> 1
  env <setup flags> champ-battle-v21 battle ../native/engine_data_full.json <starts.jsonl> <outdir> <threads>
  ../.venv/bin/python3 replay_pairs.py report <outdir> [<outdir> ...]       -> agreement, sim - real by style (and by rating band)"""
import json, os, sys, glob, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
STYLES = ['Rain', 'Sun', 'Trick Room', 'Indeedee TR', 'Tailwind', 'Snow', 'Balance', 'Sand', 'Perish', 'Rain + Sun']
def jobs(outf, min_rating=1150):
    from opp_pool import spread
    pool = json.load(open(os.path.join(HERE, 'opp_pool.json')))['entries']
    byg = collections.defaultdict(dict)
    for e in pool: byg[e['id']][e['side']] = e
    def four(e):
        sets = {m['species']: m for m in e['six']}
        return [{**sets[x], 'evs': spread(x, sets[x]['nature'])} for x in e['bring']]
    J = []
    for gid, s in sorted(byg.items()):
        if 'p1' not in s or 'p2' not in s: continue
        a, b = s['p1'], s['p2']
        if a['won'] is None or not a['bring_seen'] or not b['bring_seen'] or min(a['rating'] or 0, b['rating'] or 0) < min_rating: continue
        J.append({'mine': four(a), 'theirs': four(b), 'meta': {'pool_id': gid, 'my_arch': a['arch'], 'arch': b['arch'], 'my_group': a['group'], 'group': b['group'],
                                                            'real_won': a['won'], 'rating': min(a['rating'], b['rating'])}})
    json.dump(J, open(outf, 'w')); print(f"{len(J)} real pairings -> {outf}")
def report(dirs):
    for d in dirs:
        rows = [j for j in (json.load(open(f)) for f in glob.glob(os.path.join(d, '*.json'))) if j['v'] is not None]
        n = len(rows)
        if not n: print(d, 'empty'); continue
        agree = sum(1 for j in rows if (j['v'] > 0.5) == bool(j['real_won'])) / n
        print(f"\n== {d}: {n} games; sim winner = real winner {100 * agree:.1f}%; sim p1 win {100 * sum(j['v'] for j in rows) / n:.1f}% vs real {100 * sum(j['real_won'] for j in rows) / n:.1f}%")
        print(f"{'style':12s} {'games':>5s} {'sim win%':>8s} {'real win%':>9s} {'sim - real':>12s}")
        for s in STYLES:
            sim, real = [], []
            for j in rows:
                if j['my_arch'] == s: sim.append(j['v']); real.append(j['real_won'])
                if j['arch'] == s: sim.append(1 - j['v']); real.append(1 - j['real_won'])
            if len(sim) < 30: continue
            ms = sum(sim) / len(sim); mr = sum(real) / len(real); se = math.sqrt(2 * 0.25 / len(sim))
            print(f"{s:12s} {len(sim):5d} {100 * ms:8.1f} {100 * mr:9.1f} {100 * (ms - mr):+8.1f} ± {100 * se:3.1f}")
        # PAIRS=<jobs.json> (2026-10-13, the user: Mega Raichu-Y, No Guard's sure Zap Cannon / Focus Blast): the same by the side that
        # brought a Pokemon holding the item, if the job file is given; one row per item in PAIRS_ITEMS (default Raichunite Y)
        if os.environ.get('PAIRS'):
            J = json.load(open(os.environ['PAIRS']))
            for item in os.environ.get('PAIRS_ITEMS', 'Raichunite Y').split(','):
                sim, real = [], []
                for j in rows:
                    jb = J[j['job']]
                    if any(x.get('item') == item for x in jb['mine']): sim.append(j['v']); real.append(j['real_won'])
                    if any(x.get('item') == item for x in jb['theirs']): sim.append(1 - j['v']); real.append(1 - j['real_won'])
                if sim:
                    ms = sum(sim) / len(sim); mr = sum(real) / len(real); se = math.sqrt(2 * 0.25 / len(sim))
                    print(f"{'brought ' + item:22s} {len(sim):5d} {100 * ms:8.1f} {100 * mr:9.1f} {100 * (ms - mr):+8.1f} ± {100 * se:3.1f}")
        for lo, hi in ((1150, 1250), (1250, 1350), (1350, 9999)):
            rr = [j for j in rows if lo <= j['rating'] < hi]
            if rr: print(f"  rating {lo}-{hi}: {len(rr)} games, agreement {100 * sum(1 for j in rr if (j['v'] > 0.5) == bool(j['real_won'])) / len(rr):.1f}%")
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'jobs': jobs(a[1], int(a[2]) if len(a) > 2 else 1150)
    elif a[0] == 'report': report(a[1:])
