"""Opponents' stat points, which the open team sheets do not show (the user's idea, 2026-10-11): the species' spreads from the Smogon Reg M-C
stats in order of use (regionals/smogon_mc_2026-09_moveset.txt), those with the nature its team sheet shows; the most used one the game has
not ruled out, else the next, and so on. What rules a spread out so far: the order two Pokemon moved in, when the other one's Speed is
known exactly (a bot's own Pokemon, from its requests) and nothing else could explain the order. When every listed spread is ruled out,
the most used one with its Speed points moved just enough to fit.
  ranked(species, nature, item) -> [(share, evs)]   evs as [hp, atk, def, spa, spd, spe] stat points
  observations(log, known_side, known_speed) -> [obs]   known_speed(species, forme) -> that Pokemon's raw Speed
  pick(species, nature, item, guess, obs) -> (evs, why)
Speed in Champions at level 50: (2 base + 31 + 2 points) / 2 + 5, times the nature."""
import os, re, json, collections
import common as C, replay as R
toid = R.toid
E = json.load(open(os.path.join(C.MAIN, 'native', 'engine_data_full.json')))
STATS = os.path.join(C.REPO, 'regionals', 'smogon_mc_2026-09_moveset.txt')
ORDER = ['hp', 'atk', 'def', 'spa', 'spd', 'spe']
_TABLE = None
def table():
    """species id -> [(share, nature, evs)] in the order the stats list them"""
    global _TABLE
    if _TABLE is None:
        _TABLE = collections.defaultdict(list); name = None; part = None; lines = open(STATS).read().split('\n')
        for i, l in enumerate(lines):
            t = l.strip().strip('|').strip()
            if l.strip().startswith('+'): continue
            if i > 0 and lines[i - 1].strip().startswith('+') and i + 1 < len(lines) and lines[i + 1].strip().startswith('+') and t and '%' not in t and ':' not in t:
                if t in ('Abilities', 'Items', 'Spreads', 'Moves', 'Teammates', 'Checks and Counters', 'Tera Types'): part = t
                else: name = toid(t); part = None
                continue
            if t in ('Abilities', 'Items', 'Spreads', 'Moves', 'Teammates', 'Checks and Counters', 'Tera Types'): part = t; continue
            m = re.match(r'(\w+):(\d+)/(\d+)/(\d+)/(\d+)/(\d+)/(\d+)\s+([\d.]+)%', t)
            if part == 'Spreads' and name and m: _TABLE[name].append((float(m.group(8)) / 100, m.group(1), [int(x) for x in m.group(2, 3, 4, 5, 6, 7)]))
    return _TABLE
def mega_of(species, item): return (E['items'].get(toid(item), {}).get('megaStone') or {}).get(species)
def ranked(species, nature, item=''):
    """the listed spreads with this nature, most used first (a Mega's own list first, as spots.evs_for)"""
    T = table()
    for key in (toid(mega_of(species, item) or ''), toid(species)):
        rows = [(w, evs) for w, n, evs in T.get(key, []) if n == nature]
        if rows: return rows
    return []
def raw_speed(forme, evs, nature):
    sp = E['species'].get(toid(forme))
    if not sp: return None
    n = E['natures'].get(toid(nature), {}); m = 1.1 if n.get('plus') == 'spe' else 0.9 if n.get('minus') == 'spe' else 1.0
    return int(((2 * sp['stats']['spe'] + 31 + 2 * evs[5]) * 50 // 100 + 5) * m)
STAGE = {-6: 2 / 8, -5: 2 / 7, -4: 2 / 6, -3: 2 / 5, -2: 2 / 4, -1: 2 / 3, 0: 1, 1: 1.5, 2: 2, 3: 2.5, 4: 3, 5: 3.5, 6: 4}
WEATHER_SPEED = {'Swift Swim': 'RainDance', 'Chlorophyll': 'SunnyDay', 'Sand Rush': 'Sandstorm', 'Slush Rush': 'Snowscape'}
def effective(raw, mods):
    """the Speed the turn order uses: stages, then Choice Scarf, a weather ability, Tailwind, paralysis"""
    v = int(raw * STAGE.get(mods['stage'], 1))
    if mods['scarf']: v *= 1.5
    if mods['weather_x2']: v *= 2
    if mods['tailwind']: v *= 2
    if mods['par']: v *= 0.5
    return v
SKIP_TURN = {'After You', 'Quash', 'Instruct', 'Ally Switch'}               # moves that change the order of what follows
def speed_line(l):
    """a line that can change a Pokemon's Speed or the turn order mid-turn"""
    p = l.split('|')
    if len(p) < 3: return False
    k = p[1]
    if k in ('-boost', '-unboost', '-setboost'): return len(p) > 3 and p[3] == 'spe'
    if k in ('-clearallboost', '-clearboost', '-clearnegativeboost', '-swapboost', '-copyboost', '-invertboost', '-formechange', '-transform'): return True
    if k == '-status': return len(p) > 3 and p[3] == 'par'
    if k in ('-sidestart', '-sideend'): return 'Tailwind' in l
    if k in ('-fieldstart', '-fieldend'): return 'Trick Room' in l
    if k in ('-enditem', '-item'): return 'Choice Scarf' in l
    if k == '-weather': return '[upkeep]' not in l
    return False
def priority(move, ability, hp_full):
    m = E['moves'].get(toid(move), {}); p = m.get('priority', 0)
    if ability == 'Prankster' and m.get('category') == 'Status': p += 1
    if ability == 'Triage' and (m.get('flags') or {}).get('heal'): p += 3
    if ability == 'Gale Wings' and m.get('type') == 'Flying' and hp_full: p += 1
    return p
def observations(log, known_side, known_speed, sheets):
    """the turns where a Pokemon of the other side and one of the known side moved at the same priority, nothing having changed either
    one's Speed or the field before the second of them moved: [{turn, species, forme, first, tr, mods, known}] with known the known
    Pokemon's effective Speed and mods the other one's modifiers (its raw Speed is what is unknown)"""
    out = []; g = R.parse(log); steps = {s['turn']: s for s in g['steps'] if s['turn'] >= 1 and s['state']}
    L = log.split('\n'); turn = 0; seg = []
    def flush(t, seg):
        st = steps.get(t)
        if not st or any(l.startswith('|move|') and l.split('|')[3] in SKIP_TURN for l in seg): return
        state = st['state']; f = state['field']; forme = {}; switched = set(); moves = []; dirty = False
        for l in seg:
            p = l.split('|')
            if len(p) < 3: continue
            if p[1] in ('switch', 'drag', 'replace'): switched.add(p[2][:3])
            elif p[1] == 'detailschange': forme[p[2][:3]] = p[3].split(',')[0]
            elif p[1] == '-activate' and re.search(r'Quick Claw|Custap|Quick Draw', l): dirty = True
            elif speed_line(l) and moves: dirty = True                            # something changed Speed or the field mid-turn
            elif p[1] == 'move' and not re.search(r'\[from\](?! lockedmove)', l) and not dirty: moves.append((p[2][:3], p[3]))
        mon_at = lambda pos: next((m for m in state[pos[:2]]['mons'] if m['pos'] == pos[2] and not m['f']), None)
        def mods(pos, m, item, ability):
            sd = pos[:2]
            return {'stage': (m['b'] or {}).get('spe', 0), 'scarf': toid(item) == 'choicescarf' and not m['gone'], 'tailwind': state[sd]['tailwind'] > 0,
                    'par': m['st'] == 'par' and ability != 'Quick Feet', 'weather_x2': WEATHER_SPEED.get(ability) == f['weather'] and bool(f['weather'])}
        for i, (pa, ma) in enumerate(moves):
            for pb, mb in moves[i + 1:]:
                if pa[:2] == pb[:2] or pa in switched or pb in switched: continue
                ka, kb = (pa, pb) if pa[:2] == known_side else (pb, pa)
                if ka[:2] != known_side: continue
                mk, mu = mon_at(ka), mon_at(kb)
                if not mk or not mu: continue
                shk = sheets[ka[:2]].get(toid(mk['sp'])) or {}; shu = sheets[kb[:2]].get(toid(mu['sp'])) or {}
                if 'Unburden' in (shk.get('ability'), shu.get('ability')) or 'Quick Feet' in (shk.get('ability'), shu.get('ability')): continue
                movek, moveu = (ma, mb) if pa == ka else (mb, ma)
                if priority(movek, shk.get('ability'), mk['hp'] == 100) != priority(moveu, shu.get('ability'), mu['hp'] == 100): continue
                fk = forme.get(ka) or (mk['forme'] or mk['sp']); fu = forme.get(kb) or (mu['forme'] or mu['sp'])
                if mk['mega'] and ka not in forme: fk = mega_of(mk['sp'], shk.get('item', '')) or fk
                if mu['mega'] and kb not in forme: fu = mega_of(mu['sp'], shu.get('item', '')) or fu
                rk = known_speed(mk['sp'], fk)
                if rk is None: continue
                out.append({'turn': t, 'species': mu['sp'], 'forme': fu, 'first': pa == kb, 'tr': f['tr'] > 0,
                            'mods': mods(kb, mu, shu.get('item', ''), shu.get('ability')), 'known': effective(rk, mods(ka, mk, shk.get('item', ''), shk.get('ability'))),
                            'against': mk['sp']})
    for l in L:
        if l.startswith('|turn|'):
            if turn: flush(turn, seg)
            turn = int(l[6:]); seg = []
        elif turn: seg.append(l)
    if turn: flush(turn, seg)
    return out
def fits(evs, nature, ob):
    raw = raw_speed(ob['forme'], evs, nature)
    if raw is None: return True
    u = effective(raw, ob['mods']); k = ob['known']; faster = u > k + 1; slower = u < k - 1   # within 1: a tie (or rounding), either order
    went_first = ob['first'] != ob['tr']                                    # under Trick Room the slower one goes first
    return not slower if went_first else not faster
def pick(species, nature, item, guess, obs):
    """the most used listed spread (with this nature) that fits what the game showed, else the old guess if it fits, else the most used one
    with its Speed points moved as little as fits: (evs, why)"""
    obs = [o for o in obs if toid(o['species']) == toid(species)]
    cands = [(w, evs, f'Smogon #{i + 1} ({100 * w:.0f}%)') for i, (w, evs) in enumerate(ranked(species, nature, item))] + [(0, list(guess), 'the plain guess')]
    for w, evs, name in cands:
        if all(fits(evs, nature, o) for o in obs): return list(evs), name + (f', fits {len(obs)} observed turn orders' if obs else '')
    top = cands[0][1]
    for d in sorted(range(33), key=lambda x: abs(x - top[5])):
        evs = top[:5] + [d]
        if all(fits(evs, nature, o) for o in obs): return evs, f'{cands[0][2]} with {d} Speed points (the turn order rules out every listed spread)'
    return list(top), f'{cands[0][2]} (no spread fits every observed turn order)'
def refine(log, gp, sets, known_side, known_evs):
    """the other side's spreads in sets picked against the turn order the log shows; known_evs {species id: (evs, nature)} for the known
    side's Pokemon (a bot's own). Returns {species: why}"""
    def ks(species, forme):
        k = known_evs.get(toid(species)) or known_evs.get(toid(species.split('-')[0]))
        return raw_speed(forme, *k) if k else None
    obs = observations(log, known_side, ks, gp['sheets'])
    other = 'p2' if known_side == 'p1' else 'p1'; why = {}
    for sp, st in sets[other].items():
        if st: evs, why[sp] = pick(sp, st['nature'], st['item'], st['evs'], obs); sets[other][sp] = {**st, 'evs': evs}
    return why
