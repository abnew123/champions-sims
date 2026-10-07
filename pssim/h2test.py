"""Does the two-turn horizon (champ-battle-v21 BATTLE_HORIZON=2) play stronger? Head-to-head on mixed-style pool teams (2026-10-07).
  ../.venv/bin/python3 h2test.py jobs <out.json> [per style=30] [opponents each=10]   -> explicit battle_starts.js jobs: for each of 8
      styles (Rain, Sun, Trick Room, Indeedee TR, Tailwind, Snow, Balance, Sand) that many pool sides rated 1250+ with the bring seen
      as side 0, each against random pool sides rated 1100+ (their four as played); deterministic (seed 23)
  SEED_PER_JOB=1 node ../native/battle_starts.js <jobs.json> <starts.jsonl> 1
  then three runs of the same starts with RACE_TIES=avg DP2=1 RACE=1 CALC_DATA=../native/champions_data.json BATTLE_ANTICIPATE=1 TRSYM=1
  EG_VALUE=egvalue9_sym2.json GRID_DIR=<empty dir>: A as is, B + BATTLE_HORIZON=2 BATTLE_HORIZON_SIDE=0, C + BATTLE_HORIZON=2 BATTLE_HORIZON_SIDE=1
  ../.venv/bin/python3 h2test.py report <dirA> <dirB> <dirC>   -> the horizon side's gain overall and by side 0's style, cost per game"""
import json, os, sys, glob, random, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
STYLES = ['Rain', 'Sun', 'Trick Room', 'Indeedee TR', 'Tailwind', 'Snow', 'Balance', 'Sand']
def jobs(outf, per=30, each=10):
    from opp_pool import spread
    pool = json.load(open(os.path.join(HERE, 'opp_pool.json')))['entries']
    rng = random.Random(23)
    good = [e for e in pool if (e['rating'] or 0) >= 1250 and e['bring_seen']]
    by = collections.defaultdict(list)
    for e in good: by[e['arch']].append(e)
    mine = []
    for arch in STYLES:
        es = by[arch][:]; rng.shuffle(es); mine += es[:per]
    opp = [e for e in pool if (e['rating'] or 0) >= 1100]
    def four(e):
        sets = {m['species']: m for m in e['six']}
        return [{**sets[x], 'evs': spread(x, sets[x]['nature'])} for x in e['bring']]
    J = []
    for e in mine:
        for _ in range(each):
            o = rng.choice(opp)
            J.append({'mine': four(e), 'theirs': four(o), 'meta': {'my_arch': e['arch'], 'my_group': e['group'], 'my_id': e['id'], 'arch': o['arch'], 'group': o['group'], 'pool_id': o['id']}})
    json.dump(J, open(outf, 'w')); print(f"{len(J)} jobs -> {outf}")
def load(d):
    out = {}
    for f in glob.glob(os.path.join(d, '*.json')):
        j = json.load(open(f)); out[j['job']] = j
    return out
def cmp(X, Y, label, flip=False):
    ks = sorted(set(X) & set(Y)); d = []; byarch = collections.defaultdict(list); ms = [0, 0]; h2 = 0
    for k in ks:
        vx, vy = X[k]['v'], Y[k]['v']
        if vx is None or vy is None: continue
        dd = (vy - vx) if not flip else (vx - vy)
        d.append(dd); byarch[X[k]['my_arch']].append(dd)
        ms[0] += sum(r['ms'] for r in X[k]['rows']); ms[1] += sum(r['ms'] for r in Y[k]['rows']); h2 += sum(r.get('h2', 0) for r in Y[k]['rows'])
    n = len(d)
    if n < 2: print(label, 'nothing to compare'); return None
    mu = sum(d) / n; se = (sum((x - mu) ** 2 for x in d) / (n - 1)) ** 0.5 / n ** 0.5
    print(f"{label}: {n} games, the horizon side's gain {100 * mu:+.1f} ± {100 * se:.1f} points; unchanged results {sum(1 for x in d if abs(x) < 1e-9)}; ms per game {ms[0] / n:.0f} -> {ms[1] / n:.0f}; horizon cells per game {h2 / n:.0f}")
    for a in STYLES:
        l = byarch.get(a, [])
        if len(l) < 2: continue
        m = sum(l) / len(l); s = (sum((x - m) ** 2 for x in l) / (len(l) - 1)) ** 0.5 / len(l) ** 0.5
        print(f"    side 0 {a:12s} n {len(l):4d}  {100 * m:+6.1f} ± {100 * s:4.1f}")
    return d
def report(a, b, c):
    A, B, C = load(a), load(b), load(c)
    db = cmp(A, B, 'B: side 0 with the horizon vs A') or []
    dc = cmp(A, C, 'C: side 1 with the horizon vs A (gain from side 1\'s view)', flip=True) or []
    d = db + dc
    if d:
        mu = sum(d) / len(d); se = (sum((x - mu) ** 2 for x in d) / (len(d) - 1)) ** 0.5 / len(d) ** 0.5
        print(f"both sides pooled: {len(d)} games, {100 * mu:+.1f} ± {100 * se:.1f} points")
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'jobs': jobs(a[1], int(a[2]) if len(a) > 2 else 30, int(a[3]) if len(a) > 3 else 10)
    elif a[0] == 'report': report(a[1], a[2], a[3])
