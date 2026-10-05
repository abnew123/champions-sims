"""Build the hill-climb inputs (user's plan, 2026-10-03: start from each Reg M-C regional's top 16, swap one member at a time).

Writes, all under teamsearch/:
  teams/start/<Event>-<place>.json   the 48 top-16 teams (Baltimore, Brisbane, Frankfurt), MYTEAM format, + trick_room_six.json
  teams/start/index.json             per start team: event, place, archetype, player id, member grid ids, spread sources
  swap_pool.json                     the swap candidates: species with >= MIN_USE of the 768 regional teams; per species the item
                                     clusters with >= 25% of its sets (max 2), each with its most common nature, ability and four moves;
                                     plus item-clause fallbacks (fallback: true), used only when a candidate's item clashes
  field/regional_field.json          all 768 regional teams (top 256 per event), normalized, spreads filled: an opponent pool
  grid_sets.json                     every distinct set above, keyed by grid id (one-on-one matrix cells are per set)
  support.json                       sets with species/moves/items/abilities the engine can't run
Spreads: open team sheets don't show stat points; see sets_lib.fill_spread.
"""
import json, os, collections
import sets_lib as L
HERE = L.HERE
MIN_USE = float(os.environ.get('MIN_USE', '0.04'))
ONE_ITEM = 0.85          # a species "clearly uses one item" when its top item is on >= 85% of its regional sets
FALLBACK_MIN = 0.05
T = json.load(open(os.path.join(L.ROOT, 'regionals', 'regional_teams.json')))
R = json.load(open(os.path.join(L.ROOT, 'regionals', 'regional_sets.json')))
RUST_UNSUPPORTED = {'Revival Blessing', 'Healing Wish', 'Baton Pass', 'Ally Switch', 'Beat Up', 'Magician', 'Wandering Spirit'}

def forme_id(forme):
    """threat-style name: Salamence-Mega -> M-Salamence, Charizard-Mega-Y -> M-Charizard Y, Arcanine-Hisui -> Arcanine-H"""
    if '-Mega' in forme:
        base, suf = forme.split('-Mega', 1)
        return 'M-' + base + (' ' + suf.lstrip('-') if suf.lstrip('-') else '')
    return {'Arcanine-Hisui': 'Arcanine-H'}.get(forme, forme)

def full(s):
    s = L.normalize(s)
    evs, how = L.fill_spread(s['species'], s['item'], s['nature'], s['moves'])
    return dict(species=s['species'], item=s['item'], ability=s['ability'], nature=s['nature'], evs=evs, moves=s['moves']), how

# ---- every set we need, with grid ids (numbered per forme by how often the exact set appears in the regionals) ----
seen = collections.Counter(); sets = {}
for t in T:
    for s in R[t['event'] + '|' + t['pid']]:
        f, _ = full(s); k = L.set_key(f); seen[k] += 1; sets[k] = f
TR6 = json.load(open(os.path.join(HERE, 'teams', 'trick_room_six.json')))
USER_TEAMS = {'trick_room_six': ('Indeedee TR', TR6),                                    # the user's own teams, as extra starts
              'low_variance_six': ('Tailwind', json.load(open(os.path.join(HERE, 'teams', 'low_variance_six.json'))))}
for _, ut in USER_TEAMS.values():
    for s in ut.values():
        f = dict(species=s['species'], item=s['item'], ability=s['ability'], nature=s['nature'], evs=s['evs'], moves=s['moves'])
        sets.setdefault(L.set_key(f), f)

# ---- swap pool ----
by = collections.defaultdict(list)
for t in T:
    for s in R[t['event'] + '|' + t['pid']]:
        f, _ = full(s); by[L.battle_forme(f['species'], f['item'])].append(f)
pool = []
def modal_set(ss, it):
    """the most common nature, then ability and four moves, among a species' sets holding item it"""
    cs = [s for s in ss if s['item'] == it]
    nat = collections.Counter(s['nature'] for s in cs).most_common(1)[0][0]
    cs2 = [s for s in cs if s['nature'] == nat]
    ab = collections.Counter(s['ability'] for s in cs2).most_common(1)[0][0]
    mv = collections.Counter(tuple(sorted(s['moves'])) for s in cs2).most_common(1)[0][0]
    ex = next(s for s in cs2 if tuple(sorted(s['moves'])) == mv)
    return cs, dict(species=ex['species'], item=it, ability=ab, nature=nat, evs=L.fill_spread(ex['species'], it, nat, list(mv))[0], moves=list(ex['moves']))
for forme, ss in sorted(by.items(), key=lambda kv: -len(kv[1])):
    if len(ss) < MIN_USE * len(T): continue
    items = collections.Counter(s['item'] for s in ss)
    clusters = [i for i, c in items.most_common() if c >= 0.25 * len(ss)][:2] or [items.most_common(1)[0][0]]
    one_item = items.most_common(1)[0][1] >= ONE_ITEM * len(ss)
    # item-clause fallbacks (user, 2026-10-03): a species that doesn't clearly use one item gets its other items
    # with >= FALLBACK_MIN share as sets used only when a candidate's item clashes with a teammate's
    fallbacks = [] if one_item else [i for i, c in items.most_common() if i and i not in clusters and c >= FALLBACK_MIN * len(ss)]
    for it in clusters + fallbacks:
        cs, f = modal_set(ss, it)
        sets.setdefault(L.set_key(f), f)
        pool.append(dict(forme=forme, use=round(100 * len(ss) / len(T), 1), cluster_share=round(100 * len(cs) / len(ss)), key=L.set_key(f),
                         fallback=it in fallbacks, one_item=one_item))

# grid ids
gid = {}; per = collections.Counter()
GPATH = os.path.join(HERE, 'grid_sets.json')
if os.path.exists(GPATH):                       # ids are cache keys for mx/out: never renumber
    for g, s in json.load(open(GPATH)).items():
        s = {k: v for k, v in s.items() if k != 'regional_count'}
        gid[L.set_key(s)] = g; fid, n = g.rsplit('#', 1); per[fid] = max(per[fid], int(n))
for k in sorted(sets, key=lambda k: (-seen[k], k)):
    if k in gid: continue
    fid = forme_id(L.battle_forme(sets[k]['species'], sets[k]['item']))
    per[fid] += 1; gid[k] = f"{fid}#{per[fid]}"
grid = {gid[k]: dict(sets[k], regional_count=seen[k]) for k in sets}
if os.path.exists(GPATH):                       # keep sets no longer used (e.g. a user team's old spread): old results name them
    for g, s in json.load(open(GPATH)).items(): grid.setdefault(g, s)
json.dump(grid, open(GPATH, 'w'), indent=0)
for p in pool: p['gid'] = gid[p.pop('key')]
json.dump(pool, open(os.path.join(HERE, 'swap_pool.json'), 'w'), indent=1)

# ---- start teams + field ----
os.makedirs(os.path.join(HERE, 'teams', 'start'), exist_ok=True); os.makedirs(os.path.join(HERE, 'field'), exist_ok=True)
index = {}; field = []
for t in T:
    team, gids, hows = {}, [], []
    for s in R[t['event'] + '|' + t['pid']]:
        f, how = full(s); team[f['species']] = f; gids.append(gid[L.set_key(f)]); hows.append(how)
    field.append(dict(event=t['event'], place=t['place'], day2=t['day2'], arch=t['arch'], pid=t['pid'], gids=gids, team=team))
    if t['place'] <= 16:
        name = f"{t['event']}-{t['place']:02d}"
        json.dump(team, open(os.path.join(HERE, 'teams', 'start', name + '.json'), 'w'), indent=1)
        index[name] = dict(event=t['event'], place=t['place'], arch=t['arch'], pid=t['pid'], gids=gids, spreads=hows)
for name, (arch, ut) in USER_TEAMS.items():
    json.dump(ut, open(os.path.join(HERE, 'teams', 'start', name + '.json'), 'w'), indent=1)
    index[name] = dict(event='user', place=None, arch=arch, pid=None,
                       gids=[gid[L.set_key(dict(species=s['species'], item=s['item'], ability=s['ability'], nature=s['nature'],
                                                  evs=s['evs'], moves=s['moves']))] for s in ut.values()], spreads=['user'] * 6)
FINALS = os.path.join(HERE, 'teams', 'climb_finals.json')      # earlier climbs' best sixes as extra starts (user, 2026-10-05)
if os.path.exists(FINALS):
    for name, f in json.load(open(FINALS)).items():
        team = {grid[g]['species']: {k: v for k, v in grid[g].items() if k != 'regional_count'} for g in f['gids']}
        json.dump(team, open(os.path.join(HERE, 'teams', 'start', name + '.json'), 'w'), indent=1)
        index[name] = dict(event='climb', place=None, arch=None, pid=None, gids=f['gids'], spreads=['climb'] * 6, note=f['note'])
json.dump(index, open(os.path.join(HERE, 'teams', 'start', 'index.json'), 'w'), indent=1)
json.dump(field, open(os.path.join(HERE, 'field', 'regional_field.json'), 'w'))

# ---- engine support ----
bad = {}
for g, s in grid.items():
    why = []
    if L.idf(s['species']) not in L.DEX['species']: why.append('species ' + s['species'])
    if s['item'] and L.idf(s['item']) not in L.DEX['items']: why.append('item ' + s['item'])
    if L.idf(s['ability']) not in L.DEX['abilities']: why.append('ability ' + s['ability'])
    why += ['move ' + m for m in s['moves'] if L.idf(m) not in L.DEX['moves']]
    why += ['not ported to Rust: ' + x for x in s['moves'] + [s['ability']] if x in RUST_UNSUPPORTED]
    if why: bad[g] = why
json.dump(bad, open(os.path.join(HERE, 'support.json'), 'w'), indent=1)
start_g = {g for v in index.values() for g in v['gids']}
print(f"{len(index)} start teams, {sum(not p['fallback'] for p in pool)} swap sets + {sum(p['fallback'] for p in pool)} item-clause fallbacks over {len({p['forme'] for p in pool})} species, {len(field)} field teams, "
      f"{len(grid)} distinct sets ({len(start_g | {p['gid'] for p in pool})} in start teams + swap pool); {len(bad)} sets with engine gaps")
