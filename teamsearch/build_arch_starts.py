"""Starts for the per-archetype climbs (user, 2026-10-08: "a decent trick room team, a decent sun + rain team, a decent sand team etc."):
for each chosen archetype, its real regional teams by placement (every top-16 team, then the next best placements up to PER), plus the
user's teams of that archetype. Archetypes are pssim/pro_replays.arch (the rule tree that also labels the opponent groups); the climb
keeps each start in its archetype (TS_ARCH_LOCK=1). Writes teams/arch_start/index.json in teams/start/index.json's format (for
TS_INDEX) and lists the sets that still need one-on-one cells.
  python3 build_arch_starts.py ["Rain,Rain + Sun,Balance,Sand,Tailwind"] [per archetype=6]
  the v26 climb (user, 2026-10-12: "top 8 for all regionals (so 40 teams)"): TS_START_TOP=8 TS_START_USER=0 \
    TS_START_OUT=teams/top8_start python3 build_arch_starts.py all 0      (every archetype, places 1-8 only, no user teams)
  then: cd mx && for t in 0 1; do TR=$t NPROC=8 python3 grid_pool.py <ids printed>; done
"""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'pssim'))
import sets_lib as L
from pro_replays import arch
from cluster_opps import norm
G = json.load(open(os.path.join(HERE, 'grid_sets.json'))); SUPPORT = json.load(open(os.path.join(HERE, 'support.json')))
ARCHS = (sys.argv[1] if len(sys.argv) > 1 else 'Rain,Rain + Sun,Balance,Sand,Tailwind').split(',')
PER = int(sys.argv[2]) if len(sys.argv) > 2 else 6
TOP = int(os.environ.get('TS_START_TOP', 16)); USER = os.environ.get('TS_START_USER', '1') == '1'
OUTD = os.path.join(HERE, os.environ.get('TS_START_OUT', os.path.join('teams', 'arch_start')))
FIELDS = ('species', 'item', 'ability', 'nature', 'evs', 'moves')

def arch_of(gids): return arch([norm(G[g]['species']) for g in gids])

def full(s):
    s = L.normalize(s); evs, _ = L.fill_spread(s['species'], s['item'], s['nature'], s['moves'])
    return dict(species=s['species'], item=s['item'], ability=s['ability'], nature=s['nature'], evs=evs, moves=s['moves'])

if __name__ == '__main__':
    T = json.load(open(os.path.join(L.ROOT, 'regionals', 'regional_teams.json'))); R = json.load(open(os.path.join(L.ROOT, 'regionals', 'regional_sets.json')))
    keymap = {L.set_key({k: s[k] for k in FIELDS}): g for g, s in G.items() if not g.startswith('smogon:')}
    user = json.load(open(os.path.join(HERE, 'teams', 'start', 'index.json')))
    index, miss = {}, set(); by = collections.defaultdict(list)
    for t in sorted(T, key=lambda t: (t['place'], t['event'])):
        gids = [keymap.get(L.set_key(full(s))) for s in R[t['event'] + '|' + t['pid']]]
        if None in gids or len(gids) != 6 or any(g in SUPPORT for g in gids): continue
        a = arch_of(gids)
        if (a in ARCHS or ARCHS == ['all']) and (t['place'] <= TOP or len(by[a]) < PER): by[a].append((t, gids))
    if ARCHS == ['all']: ARCHS = sorted(by, key=lambda a: -len(by[a]))
    for a in ARCHS:
        for t, gids in by[a]:
            index[f"{t['event']}-{t['place']}"] = dict(event=t['event'], place=t['place'], arch=a, pid=t['pid'], gids=gids)
        for n, v in user.items():
            if USER and v.get('event') == 'user' and arch_of(v['gids']) == a: index[n] = dict(v, arch=a)
    for v in index.values(): miss |= {g for g in v['gids'] if not all(os.path.exists(os.path.join(HERE, 'mx', 'out', tag, g.replace('/', '_') + '.json')) for tag in ('tr', 'notr'))}
    os.makedirs(OUTD, exist_ok=True)
    json.dump(index, open(os.path.join(OUTD, 'index.json'), 'w'), indent=1)
    for a in ARCHS:
        ns = [n for n, v in index.items() if v['arch'] == a]
        print(f"{a:12s} {len(ns)} starts: {', '.join(ns)}")
    print(f"\n{len(index)} starts; {len(miss)} sets need cells:\n" + ' '.join(sorted(miss)))
