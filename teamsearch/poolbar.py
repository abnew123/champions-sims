"""Validate Battle sim's empirical opponent pool (pssim/opp_pool.json, 2026-10-06) with the sim-vs-real bar.
The 10 simcmp teams (their latest six and their climb brings per rule archetype) play real pool entries (the entry's six with its sets,
their four as actually brought, in lead order), one game per entry, the same entries in the same order for every team (common random
numbers; SEED_PER_JOB=1 gives each entry its own battle and sampling seeds). Pool teams use moves and species outside the climb's spot data, so these battles run on native/engine_data_full.json.
Compared, on one footing, with the archetype models (the same 10 teams' archetype confirm games under the same setup):
  sim: our teams' mean win share vs an opponent group     real: the field's per-game win rate vs that group (1 - its own rate)
with each side's overall offset removed (our teams are climbed), gaps in log-odds, RMS over groups with enough data. Groups are the
rule archetypes (pro_replays.arch, as in simreal.py) and Battle sim's core-rule groups (results/group_real.json; regional and ladder).
  TS_SIM=v17g TS_PARALLEL=30 TS_THREADS=3 python3 poolbar.py run [entries=2500] [min rating=0]
        battles: pool games (each team's entries in CHUNKS processes, identical chunks for every team), then the archetype baseline.
        Many small processes, never one big one: one champ process with ~90 threads ran ~6x slower per game on the box.
  TS_SIM=v17g python3 poolbar.py report
Threads: decomp_threads.txt if present (re-read per team), else TS_THREADS.
"""
import json, os, sys, math, random, collections, time
HERE = os.path.dirname(os.path.abspath(__file__)); PS = os.path.join(HERE, '..', 'pssim')
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'bring')); sys.path.insert(0, PS)
sim_setup = os.environ.get('TS_SIM', 'v17g'); os.environ.pop('TS_PERISH', None)      # the bar plays every archetype, Perish included
import evaluate as E, simcmp as S
os.environ['TS_SIM'] = sim_setup                                                   # (simcmp sets TS_SIM=v8 on import)
_argv, sys.argv = sys.argv, sys.argv[:1]                                          # archmatch parses the command line on import
import archmatch as AM
sys.argv = _argv
from opp_pool import spread
CHUNKS = 3; SEED = 700000; FULL = os.path.join('..', 'native', 'engine_data_full.json')
INV = {short: full for full, short in AM.ARCH_MAP.items()}
SHORT = {'Rain + Sun': 'Rain + Sun', 'Trick Room': 'Trick Room'}                   # pro_replays.arch already returns the short names

def thr():
    try: return int(open(os.path.join(HERE, 'decomp_threads.txt')).read())
    except Exception: return int(os.environ.get('TS_THREADS', 3))

def sample(n, min_rating=0):
    """n pool entries, rating-weighted without replacement (as opp_pool.jobs: >= 1500: 3, >= 1300: 2, else 1), fixed seed"""
    pool = [e for e in json.load(open(os.path.join(PS, 'opp_pool.json')))['entries'] if (e['rating'] or 0) >= min_rating and len(e['bring']) == 4]
    w = [3 if (e['rating'] or 0) >= 1500 else 2 if (e['rating'] or 0) >= 1300 else 1 for e in pool]
    rng = random.Random(0); keys = sorted(range(len(pool)), key=lambda i: rng.random() ** (1 / w[i]), reverse=True)   # weighted sampling w/o replacement
    return [pool[i] for i in keys[:n]]

def jobs_for(team, fixed, entries):
    sets = {E.G[g]['species']: {k: E.G[g][k] for k in ('species', 'item', 'ability', 'nature', 'evs', 'moves')} for g in team}
    J = []
    for e in entries:
        lead, back = fixed[INV[e['arch']]]
        mine = [sets[E.G[g]['species']] for g in list(lead) + list(back)]
        six = {m['species']: m for m in e['six']}
        theirs = [{**six[x], 'evs': spread(x, six[x]['nature'])} for x in e['bring']]
        J.append(dict(mine=mine, theirs=theirs, meta=dict(pool_id=e['id'], pool_side=e['side'], group=e['group'], arch=e['arch'], rating=e['rating'])))
    return J

def run(n, min_rating):
    entries = sample(n, min_rating)
    print(time.strftime('%I:%M %p'), f"{len(entries)} pool entries; groups: {len(set(e['group'] for e in entries))}; setup {E.sim()}", flush=True)
    os.environ['TS_ENGINE_DATA'] = FULL
    os.environ['SEED_PER_JOB'] = '1'          # battle_starts.js: independent battle/sampling seeds per one-game job, same across our teams
    k = -(-len(entries) // CHUNKS)
    work = [(name, c) for name in S.DEFAULT for c in range(CHUNKS)]
    def one(item):
        name, c = item; team, fixed, label, seed = S.latest(name)
        return E.run_jobs(team, jobs_for(team, fixed, entries[c * k:(c + 1) * k]), 1, SEED, thr(), f'poolbar_c{c}')
    E.parallel(one, work, 'pool games')
    os.environ.pop('TS_ENGINE_DATA'); os.environ.pop('SEED_PER_JOB')
    base = [S.latest(name) for name in S.DEFAULT]                     # the archetype baseline under the same setup (confirm seeds, 60 jobs x 4)
    E.parallel(lambda b: E.run_team(b[0], 4, b[3], thr(), fixed=b[1], label=b[2]), base, 'archetype baseline')
    json.dump([e['id'] + '|' + e['side'] for e in entries], open(os.path.join(HERE, f'poolbar_entries_{E.sim()}.json'), 'w'))

lg = lambda p: math.log(max(1e-3, min(1 - 1e-3, p)) / (1 - max(1e-3, min(1 - 1e-3, p))))
def gaps(sim, real, weights):
    """sim, real: {group: rate}; weights: {group: n}; offset = weighted mean log-odds difference; returns ({group: gap}, rms)"""
    gs = [g for g in sim if g in real]
    off = sum(weights[g] * (lg(sim[g]) - lg(real[g])) for g in gs) / sum(weights[g] for g in gs)
    gap = {g: lg(sim[g]) - lg(real[g]) - off for g in gs}
    return gap, math.sqrt(sum(weights[g] * gap[g] ** 2 for g in gs) / sum(weights[g] for g in gs))

def real_vs_arch():
    """the field's per-game win rate against each rule archetype at the regionals"""
    rw, rn = AM.real_regionals(); w = collections.Counter(); n = collections.Counter()
    for (a, b), k in rn.items(): n[b] += k; w[b] += rw[(a, b)]                    # matches vs b, won by the side facing b
    return {b: AM.game_rate(w[b] / n[b]) for b in n if n[b] >= 50}, n

def report():
    entries = set(json.load(open(os.path.join(HERE, f'poolbar_entries_{E.sim()}.json'))))
    by_group = collections.defaultdict(lambda: [0.0, 0]); by_arch = collections.defaultdict(lambda: [0.0, 0]); arch_models = collections.defaultdict(list)
    for name in S.DEFAULT:
        team, fixed, label, seed = S.latest(name)
        for c in range(CHUNKS):
            rd = os.path.join(HERE, 'runs', f'poolbar_c{c}_{E.team_key(team)}'); d = os.path.join(rd, f'out_{E.out_tag(SEED, 1)}')
            metas = [j['meta'] for j in json.load(open(os.path.join(rd, 'jobs.json')))]
            for f in os.listdir(d):
                r = json.load(open(os.path.join(d, f))); m = metas[r['job']]
                for x in r['rows']:
                    if x.get('unsupported'): continue
                    by_group[m['group']][0] += x['v']; by_group[m['group']][1] += 1
                    by_arch[m['arch']][0] += x['v']; by_arch[m['arch']][1] += 1
        res = E.read(os.path.join(HERE, 'runs', f'{E.team_key(team)}_{label}'), E.out_tag(seed, 4))
        for a, v in res['by_arch'].items(): arch_models[AM.ARCH_MAP[a]].append(v)
    real_a, nreal = real_vs_arch()
    pool_a = {a: s / k for a, (s, k) in by_arch.items() if k >= 100}
    model_a = {a: sum(v) / len(v) for a, v in arch_models.items()}
    wa = {a: nreal[a] for a in real_a}
    print(f"games: pool {sum(k for _, k in by_group.values())} over {len(entries)} entries x 10 teams")
    print(f"\nby rule archetype (real = the field's per-game win rate vs it at the regionals; gap after offset, log-odds):")
    for label_, sim in (('archetype models', model_a), ('real-game pool', pool_a)):
        for excl in (False, True):
            s_ = {a: v for a, v in sim.items() if not (excl and a == 'Perish')}
            g, rms = gaps(s_, real_a, wa)
            if not excl: G1 = g
            print(f"  {label_:17s} RMS {'without Perish' if excl else 'all archetypes'}: {rms:.2f}")
        print('   ' + '  '.join(f"{a} {G1[a]:+.2f}" for a in sorted(G1, key=lambda a: -wa[a])))
    R = json.load(open(os.path.join(PS, 'results', 'group_real.json')))
    pool_g = {g: s / k for g, (s, k) in by_group.items() if k >= 200}
    for src in ('regional', 'ladder'):
        tot = collections.Counter(); won = collections.Counter()
        for c in R['cells']:
            if c.get(src) and c['vs'] in pool_g: tot[c['vs']] += c[src][1]; won[c['vs']] += c[src][1] * c[src][2]   # [wins, n, per-game rate of 'group' vs 'vs']
        real_g = {g: won[g] / tot[g] for g in tot if tot[g] >= 100}
        g, rms = gaps(pool_g, real_g, {k: tot[k] for k in real_g})
        print(f"\nby core-rule group vs {src} reality (groups with >= 200 sim games and >= 100 real games: {len(g)}): RMS {rms:.2f}")
        for k in sorted(g, key=lambda k: -tot[k])[:14]:
            print(f"  {k[:58]:58s} sim {100 * pool_g[k]:5.1f}  real {100 * real_g[k]:5.1f}  gap {g[k]:+.2f}")

if __name__ == '__main__':
    if sys.argv[1] == 'run': run(int(sys.argv[2]) if len(sys.argv) > 2 else 2500, int(sys.argv[3]) if len(sys.argv) > 3 else 0)
    else: report()
