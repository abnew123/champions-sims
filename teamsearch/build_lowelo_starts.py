"""Starts for a sanity-check climb (user, 2026-10-16: "take random low elo showdown teams to make sure we aren't just too harsh on
our swap criteria"): N random distinct teams rated under MAX_RATING from the real-game pool (pssim/opp_pool.json, Showdown Bo3 open
team sheets), with every set the engine can run. Their sets join grid_sets.json under new ids (existing ids never change; a set
already there keeps its id); spreads are filled as for the regional sets (sets_lib.fill_spread). Writes teams/lowelo_start/index.json
(TS_INDEX format, names Ladder-01..; no player names) and cells_lowelo.txt (sets without one-on-one cells).
  python3 build_lowelo_starts.py [n=20] [max rating=1150] [seed=20261016]
"""
import json, os, sys, random, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'pssim'))
import sets_lib as L
from pro_replays import arch
from cluster_opps import norm
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20; MAXR = int(sys.argv[2]) if len(sys.argv) > 2 else 1150
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 20261016
GPATH = os.path.join(HERE, 'grid_sets.json'); G = json.load(open(GPATH))
ENG = json.load(open(os.path.join(HERE, '..', 'native', 'engine_data_full.json')))
UNPORTED = {'Revival Blessing', 'Beat Up', 'Magician', 'Wandering Spirit'}

def forme_id(forme):
    if '-Mega' in forme:
        base, suf = forme.split('-Mega', 1)
        return 'M-' + base + (' ' + suf.lstrip('-') if suf.lstrip('-') else '')
    return {'Arcanine-Hisui': 'Arcanine-H'}.get(forme, forme)

def full(s):
    s = L.normalize(dict(s)); evs, _ = L.fill_spread(s['species'], s['item'], s['nature'], s['moves'])
    return dict(species=s['species'], item=s['item'], ability=s['ability'], nature=s['nature'], evs=evs, moves=s['moves'])

def runnable(f):
    ok = L.idf(f['species']) in ENG['species'] and (not f['item'] or L.idf(f['item']) in ENG['items']) and L.idf(f['ability']) in ENG['abilities']
    return ok and all(L.idf(m) in ENG['moves'] for m in f['moves']) and not (UNPORTED & set(f['moves'] + [f['ability']])) and len(f['moves']) == 4

if __name__ == '__main__':
    P = json.load(open(os.path.join(HERE, '..', 'pssim', 'opp_pool.json')))['entries']
    cands = {}
    for e in P:
        if not (e.get('rating') and e['rating'] < MAXR and len(e['six']) == 6) or not all(s.get('moves') and s.get('nature') for s in e['six']): continue
        try: team = [full(s) for s in e['six']]
        except Exception: continue
        if not all(runnable(f) for f in team) or len({f['species'] for f in team}) < 6: continue
        items = [f['item'] for f in team if f['item']]
        if len(items) != len(set(items)): continue                                  # item clause
        cands.setdefault(tuple(sorted(L.set_key(f) for f in team)), (team, e['rating']))
    keys = sorted(cands); pick = random.Random(SEED).sample(keys, min(N, len(keys)))
    gid = {L.set_key({k: v for k, v in s.items() if k != 'regional_count'}): g for g, s in G.items()}
    per = collections.Counter()
    for g in G:
        fid, n = g.rsplit('#', 1)
        if n.isdigit(): per[fid] = max(per[fid], int(n))
    index = {}; new = 0
    for i, k in enumerate(pick, 1):
        team, rating = cands[k]; gids = []
        for f in team:
            sk = L.set_key(f)
            if sk not in gid:
                fid = forme_id(L.battle_forme(f['species'], f['item'])); per[fid] += 1; gid[sk] = f"{fid}#{per[fid]}"
                G[gid[sk]] = dict(f, regional_count=0); new += 1
            gids.append(gid[sk])
        index[f'Ladder-{i:02d}'] = dict(event='ladder', place=None, rating=rating, arch=arch([norm(f['species']) for f in team]), pid=None, gids=gids)
    json.dump(G, open(GPATH, 'w'), indent=0)
    os.makedirs(os.path.join(HERE, 'teams', 'lowelo_start'), exist_ok=True)
    json.dump(index, open(os.path.join(HERE, 'teams', 'lowelo_start', 'index.json'), 'w'), indent=1)
    has = lambda g: all(os.path.exists(os.path.join(HERE, 'mx', 'out', t, g.replace('/', '_') + '.json')) for t in ('tr', 'notr'))
    miss = sorted({g for v in index.values() for g in v['gids'] if not has(g)})
    open(os.path.join(HERE, 'cells_lowelo.txt'), 'w').write('\n'.join(miss) + '\n')
    print(f"{len(cands)} runnable distinct teams under {MAXR}; picked {len(index)}; {new} new set ids; {len(miss)} sets need cells")
    for n, v in index.items(): print(f"  {n} {v['rating']} {v['arch']:11s} " + ', '.join(G[g]['species'] for g in v['gids']))
