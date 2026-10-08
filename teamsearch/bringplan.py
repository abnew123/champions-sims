"""Plan-aware bring step for pool climbs (user, 2026-10-07; TS_BRING_MODE=plan in poolmode.search_team).
Why: the synergy check and the Trick Room six test showed the engine plays a team's plan well from good leads (the TR six: 70.3 with
the TR sheet's plans, 61.9 with the climb's bring search, 42.9 with the imitation model), but the climb's bring step rarely finds those
leads: its shortlist is the outcome model's top 3 (fitted on champ-battle-v2 vs archetype models, no plan features) and its screen is
2 games per candidate. So setters look cheap and the climb trades them for generalists.
Shortlist per opponent group (unique choices, at most K = TS_PLAN_K, default 7: with 6, a second Trick Room setter's candidate crowds out others), each tagged with where it came from:
  model      the outcome model's top 2 (the old shortlist's head)
  human      the imitation model's most human-like bring and leads
  real       what real players with similar teams (>= 4 shared species, the four all in our six) brought and led, against this
             opponent group if there are such games, else against any (opp_pool.json; rating-weighted)
  plan:X     for each plan the team has (Trick Room, Rain / Sun / Sand / Snow, Psychic / Grassy / Electric Terrain, Tailwind, Fake Out or
             redirection plus setup), the outcome model's best choice among those that put the plan on the field and aren't listed yet
The screen (poolmode.search_team_plan): every candidate x TS_PLAN_S1 (2) entries, the best TS_PLAN_KEEP (2) x TS_PLAN_S2 (6) more.
  python3 bringplan.py <start name> [group]      the team's plans and its shortlist (no battles)
"""
import json, os, sys, functools, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import climb as C, sets_lib as L
G = C.GRID
MOVES = json.load(open(os.path.join(HERE, '..', 'native', 'champions_data.json')))['moves']
mid = lambda n: ''.join(c for c in n.lower() if c.isalnum())
K_PLAN = int(os.environ.get('TS_PLAN_K', 7))
SETUP = {'Swords Dance', 'Nasty Plot', 'Dragon Dance', 'Calm Mind', 'Coil', 'Quiver Dance', 'Bulk Up', 'Shell Smash', 'Belly Drum',
         'Shift Gear', 'Victory Dance', 'Iron Defense', 'Agility', 'Tail Glow', 'Curse', 'Trick Room'}
SLOW_NATURES = {'Brave', 'Quiet', 'Relaxed', 'Sassy'}

def ability(g):
    """the battle ability: a Mega Stone holder's Mega ability"""
    it = L.DEX['items'].get(L.idf(G[g]['item'] or ''), {}) or {}
    ms = it.get('megaStone')
    if ms:
        sp = L.DEX['species'].get(L.idf(ms if isinstance(ms, str) else list(ms.values())[0]), {})
        return (sp.get('abilities') or {}).get('0')
    return G[g]['ability']

def spe(g):
    """base Speed of the set's battle forme (a Mega Stone holder's Mega)"""
    return (L.DEX['species'].get(L.idf(C.forme(g)), {}) or L.DEX['species'][L.idf(G[g]['species'])])['stats']['spe']

def slow(g):
    return spe(g) <= 60 or (G[g]['nature'] in SLOW_NATURES and G[g]['evs'][5] == 0)

def moves(g): return G[g]['moves']
def mtype(m): return (MOVES.get(mid(m)) or {}).get('type')
def damaging(m): return (MOVES.get(mid(m)) or {}).get('category') in ('Physical', 'Special')
def has(g, *ms): return any(m in moves(g) for m in ms)
def attacks_of(g, *types): return any(damaging(m) and mtype(m) in types for m in moves(g))

def plans(team):
    """[(plan name, predicate on (lead set, four set))]: the plans this six can run"""
    out = []
    tr = [g for g in team if 'Trick Room' in moves(g)]
    if tr and sum(1 for g in team if slow(g)) >= 2:
        sl = {g for g in team if slow(g)}
        for x in tr[:2]:                                                # one candidate per setter (the model may favour the weaker one)
            out.append((f"plan:Trick Room ({G[x]['species']})", lambda lead, four, x=x: x in lead and len((sl & four) - {x}) >= 1))
        guard = {g for g in team if has(g, 'Fake Out', 'Follow Me', 'Rage Powder')}
        if guard - set(tr):
            out.append(('plan:Trick Room + guard', lambda lead, four: any(s in lead for s in tr) and bool((guard - set(tr)) & lead) and len(sl & four) >= 2))
    weather = {'Drizzle': ('Rain', lambda g: ability(g) in ('Swift Swim', 'Rain Dish') or attacks_of(g, 'Water') or has(g, 'Electro Shot', 'Hurricane', 'Thunder', 'Weather Ball')),
               'Drought': ('Sun', lambda g: ability(g) in ('Chlorophyll', 'Solar Power', 'Protosynthesis') or attacks_of(g, 'Fire') or has(g, 'Solar Beam', 'Solar Blade', 'Weather Ball')),
               'Sand Stream': ('Sand', lambda g: ability(g) in ('Sand Rush', 'Sand Force') or 'Rock' in (L.DEX['species'].get(L.idf(C.forme(g)), {}) or {}).get('types', [])),
               'Snow Warning': ('Snow', lambda g: ability(g) == 'Slush Rush' or has(g, 'Blizzard', 'Aurora Veil'))}
    terrain = {'Psychic Surge': ('Psychic Terrain', lambda g: has(g, 'Expanding Force') or attacks_of(g, 'Psychic')),
               'Grassy Surge': ('Grassy Terrain', lambda g: has(g, 'Grassy Glide') or attacks_of(g, 'Grass')),
               'Electric Surge': ('Electric Terrain', lambda g: has(g, 'Rising Voltage') or attacks_of(g, 'Electric'))}
    for ab, (name, user) in list(weather.items()) + list(terrain.items()):
        setters = [g for g in team if ability(g) == ab]; users = {g for g in team if user(g)} - set(setters)
        if setters and users:
            out.append((f'plan:{name}', lambda lead, four, s=tuple(setters), u=frozenset(users): any(x in lead for x in s) and bool(u & four)))
    tw = [g for g in team if 'Tailwind' in moves(g)]
    if tw: out.append(('plan:Tailwind', lambda lead, four, s=tuple(tw): any(x in lead for x in s)))
    sup = {g for g in team if has(g, 'Fake Out', 'Follow Me', 'Rage Powder')}; setup = {g for g in team if set(moves(g)) & (SETUP - {'Trick Room'})}
    if sup and setup - sup:
        out.append(('plan:support + setup', lambda lead, four, a=frozenset(sup), b=frozenset(setup): bool(a & lead) and bool((b - a) & lead)))
    return out

@functools.lru_cache(maxsize=None)
def _real_index():
    """[(own species frozenset, bring species tuple (lead order), opponent group, weight)] from the pool's two-sided games"""
    import poolmode as PM
    side_group = {(e['id'], e['side']): k for k, es in PM.entries().items() for e in es}
    by_game = collections.defaultdict(dict)
    for k, es in PM.entries().items():
        for e in es: by_game[e['id']][e['side']] = e
    out = []
    for gid, sides in by_game.items():
        for s, e in sides.items():
            o = [x for t, x in sides.items() if t != s]
            if not o: continue
            w = 3 if (e['rating'] or 0) >= 1500 else 2 if (e['rating'] or 0) >= 1300 else 1
            out.append((frozenset(x['species'] for x in e['six']), tuple(e['bring']), side_group[(o[0]['id'], o[0]['side'])], w))
    return out

def real_choice(team, key):
    """the (lead idx, back idx) real players with similar sixes used most against this group (or any group), or None"""
    sp = {G[g]['species']: i for i, g in enumerate(team)}; S = set(sp)
    for want_group in (True, False):
        votes = collections.Counter()
        for six, br, grp, w in _real_index():
            if want_group and grp != key: continue
            ov = len(six & S)
            if ov < 4 or not set(br) <= S: continue
            votes[(tuple(sorted(sp[x] for x in br[:2])), tuple(sorted(sp[x] for x in br[2:])))] += w * (ov - 3)
        if votes: return votes.most_common(1)[0][0]
    return None

def shortlist(team, key, k=K_PLAN):
    """[(lead gids, back gids, tag)] for one opponent group, unique, at most k"""
    import poolmode as PM
    idx = {g: i for i, g in enumerate(team)}
    norm = lambda l, b: (tuple(sorted(idx[g] for g in l)), tuple(sorted(idx[g] for g in b)))
    R = PM.ranked(team, key); out, seen = [], set()
    def add(l, b, tag):
        n = norm(l, b)
        if n not in seen and len(out) < k: seen.add(n); out.append(([team[i] for i in n[0]], [team[i] for i in n[1]], tag))
    for l, b in R[:2]: add(l, b, 'model')
    h = PM.human_ranked(team, key)[0]; add(h[0], h[1], 'human')
    rc = real_choice(team, key)
    if rc: add([team[i] for i in rc[0]], [team[i] for i in rc[1]], 'real')
    for name, ok in plans(team):                                       # each plan adds its best choice not already listed
        best = next(((l, b) for l, b in R if ok(set(l), set(l) | set(b)) and norm(l, b) not in seen), None)
        if best: add(best[0], best[1], name)
    for l, b in R[2:]:
        if len(out) >= k: break
        add(l, b, 'model')
    return out

if __name__ == '__main__':
    os.environ.setdefault('TS_OPP', 'pool')
    import poolmode as PM
    team = C.INDEX[sys.argv[1]]['gids'] if sys.argv[1] in C.INDEX else sys.argv[1].split(',')
    print('plans:', [n for n, _ in plans(team)] or 'none')
    K, SH = PM.keys()
    for key in ([sys.argv[2]] if len(sys.argv) > 2 else K[:4]):
        print(f"\n{key} ({100 * SH[key]:.1f}%)")
        for l, b, tag in shortlist(team, key):
            print(f"  {tag:24s} lead {' + '.join(G[g]['species'] for g in l):28s} back {' + '.join(G[g]['species'] for g in b)}")
