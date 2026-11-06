"""Candidate teams to score against a current-meta pool (the user, 2026-11-06, via TR sheet: is the Trick Room six still the team to
play? the bot's TR six fell from 51% Oct 11-20 to 43% Nov 3-6). Writes teams/meta_<last day>.json ({name: [6 set ids]},
scoreteams.py's input) from:
  - the bot's teams (bot/teams.json), with their exact sets and spreads;
  - the v33 climb's verified finals (archverify_v33.json), the N_FINALS best;
  - the pool's most common sixes over its last DAYS days, counted one vote per player, the N_SIXES most common: each species' most
    common set among entries with that six, spread filled as for the regional sets (pool entries carry no EVs).
New sets join grid_sets.json under new ids (existing ids never change), as in build_lowelo_starts.py; sets without one-on-one cells are
listed in cells_meta.txt. No player numbers or names are written.
  python3 build_meta_candidates.py <pool.json> [N_SIXES=6] [DAYS=6] [N_FINALS=6]
"""
import json, os, sys, collections, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import build_lowelo_starts as B
L = B.L; G = B.G

def gid_of(f, gid, per):
    """the set's id in grid_sets.json, adding it under a new id when it isn't there"""
    sk = L.set_key(f)
    if sk not in gid:
        fid = B.forme_id(L.battle_forme(f['species'], f['item'])); per[fid] += 1; gid[sk] = f"{fid}#{per[fid]}"
        G[gid[sk]] = dict(f, regional_count=0)
    return gid[sk]

if __name__ == '__main__':
    pool = sys.argv[1]; NS = int(sys.argv[2]) if len(sys.argv) > 2 else 6; DAYS = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    NF = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    gid = {L.set_key({k: v for k, v in s.items() if k != 'regional_count'}): g for g, s in G.items()}
    per = collections.Counter()
    for g in G:
        fid, n = g.rsplit('#', 1)
        if n.isdigit(): per[fid] = max(per[fid], int(n))
    out, n0 = {}, len(G)
    for t in json.load(open(os.path.join(HERE, '..', 'bot', 'teams.json'))):                  # the bot's teams, exact sets
        fs = [dict(species=s['species'], item=s['item'], ability=s['ability'], nature=s['nature'], evs=list(s['evs']), moves=list(s['moves'])) for s in t['sets']]
        out[f"bot: {t['name']}"] = [gid_of(L.normalize(f), gid, per) for f in fs]
    av = json.load(open(os.path.join(HERE, 'archverify_v33.json')))                             # the v33 climb's verified finals
    fin = sorted((x for v in av.values() for x in v), key=lambda x: -x['final_score'])[:NF]
    for x in fin: out[f"v33 final: {x['start']}"] = list(x['team'])
    P = json.load(open(pool))['entries']                                                        # the pool's most common sixes
    last = max(e['day'] for e in P); first = (datetime.date.fromisoformat(last) - datetime.timedelta(days=DAYS - 1)).isoformat()
    rec = [e for e in P if e['day'] >= first and len(e['six']) == 6 and all(s.get('moves') and s.get('nature') for s in e['six'])]
    players = collections.defaultdict(set)
    for e in rec: players[tuple(sorted(s['species'] for s in e['six']))].add(e['player'])
    nplay = len({e['player'] for e in rec}); picked = 0
    for six, ps in sorted(players.items(), key=lambda t: -len(t[1])):
        if picked == NS: break
        sets = collections.defaultdict(collections.Counter)
        for e in rec:
            if tuple(sorted(s['species'] for s in e['six'])) == six:
                for s in e['six']: sets[s['species']][json.dumps(s, sort_keys=True)] += 1
        try: team = [B.full(json.loads(sets[sp].most_common(1)[0][0])) for sp in six]
        except Exception: continue
        if not all(B.runnable(f) for f in team): print('  skipped (engine lacks a move or ability):', ', '.join(six)); continue
        picked += 1; out[f"meta {picked}: {', '.join(six)} ({100 * len(ps) / nplay:.1f}% of players)"] = [gid_of(f, gid, per) for f in team]
    json.dump(G, open(B.GPATH, 'w'), indent=0)
    json.dump(out, open(os.path.join(HERE, 'teams', f'meta_{last}.json'), 'w'), indent=1)
    has = lambda g: all(os.path.exists(os.path.join(HERE, 'mx', 'out', t, g.replace('/', '_') + '.json')) for t in ('tr', 'notr'))
    miss = sorted({g for t in out.values() for g in t if not has(g)})
    open(os.path.join(HERE, 'cells_meta.txt'), 'w').write('\n'.join(miss) + ('\n' if miss else ''))
    print(f"{len(out)} candidates ({len(rec)} entries from {first} to {last}, {nplay} players); {len(G) - n0} new set ids; {len(miss)} sets need cells")
    for n, t in out.items(): print(f"  {n}\n      " + ', '.join(G[g]['species'] for g in t))
