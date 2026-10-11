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
WEATHER_SPEED = {'Swift Swim': ('Rain', 'Heavy rain'), 'Chlorophyll': ('Sun', 'Harsh sun'), 'Sand Rush': ('Sandstorm',), 'Slush Rush': ('Snow',)}   # as replay.py names weather
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
RESIDUAL = re.compile(r'\[from\] (Sandstorm|item: Leftovers|item: Black Sludge|Grassy Terrain|psn|brn|Leech Seed|Salt Cure)(?:\||$)')
SWITCH_IN = {'Intimidate', 'Drought', 'Drizzle', 'Sand Stream', 'Snow Warning', 'Orichalcum Pulse', 'Hadron Engine', 'Psychic Surge', 'Grassy Surge',
             'Electric Surge', 'Misty Surge', 'Pressure', 'Mold Breaker', 'Teravolt', 'Turboblaze', 'Trace', 'Download', 'Supreme Overlord',
             'Hospitality', 'Costar', 'Screen Cleaner', 'Curious Medicine', 'Air Lock', 'Cloud Nine'}
def observations(log, known_side, known_speed, sheets):
    """the orders the log shows between a Pokemon of the other side and one of the known side where Speed decided it (Trick Room
    reversing it) and nothing could have changed either one's Speed or the field in between:
      start     whose switch-in ability (Intimidate, weather, terrain, ...) went first as the battle began
      switch    who switched out first at the start of a turn          mega   who Mega Evolved first (both at their old Speed)
      move      who moved first at the same priority
      residual  who took or regained HP first from the same end-of-turn effect (sand, poison, burn, Leftovers, Black Sludge, Grassy
                Terrain, Leech Seed, Salt Cure), or counted down Perish Song first
    [{turn, kind, species, forme, first, tr, mods, known}]: known is the known Pokemon's effective Speed, mods the other one's modifiers
    (its raw Speed is what is unknown)"""
    out = []; g = R.parse(log); states = {s['turn']: s['state'] for s in g['steps'] if s['turn'] >= 1 and s['state']}
    nick = {}
    for l in log.split('\n'):
        p = l.split('|')
        if len(p) > 3 and p[1] in ('switch', 'drag', 'replace'): nick[(p[2][:2], p[2].split(': ', 1)[1])] = p[3].split(',')[0]
    base = lambda sp: toid(sp.split('-')[0])
    def mon(state, ident):
        sp = nick.get((ident[:2], ident.split(': ', 1)[1])) if ident and ': ' in ident else None
        return sp and next((m for m in state[ident[:2]]['mons'] if base(m['sp']) == base(sp) and not m['f']), None)
    def sheet(sd, m): return sheets[sd].get(toid(m['sp'])) or sheets[sd].get(base(m['sp'])) or {}
    def forme(sd, m, now):                                                   # the forme whose Speed counts: the Mega once it has evolved
        return (m['forme'] or mega_of(m['sp'], sheet(sd, m).get('item', '')) or m['sp']) if now and m['mega'] else (m['forme'] if m['forme'] and 'Mega' not in m['forme'] else m['sp'])
    def add(t, kind, first, second, ctx):
        """first acted before second, each (side, mon, forme); ctx: tr, weather, tailwind {side: bool}, stage (False: Speed stages not counted)"""
        if first[0] == second[0] or known_side not in (first[0], second[0]) or not first[1] or not second[1]: return
        (sk, mk, fk), (su, mu, fu) = (first, second) if first[0] == known_side else (second, first)
        shk, shu = sheet(sk, mk), sheet(su, mu)
        if {'Unburden', 'Quick Feet', 'Speed Boost', 'Slow Start'} & {shk.get('ability'), shu.get('ability')}: return
        rk = known_speed(mk['sp'], fk)
        if rk is None: return
        def mods(sd, m, sh, forme):
            ab = sh.get('ability'); mg = E['species'].get(toid(forme)) if toid(forme) != toid(m['sp']) else None
            if mg and 'mega' in toid(forme): ab = (mg.get('abilities') or {}).get('0', ab)   # a Mega has its own ability (Mega Swampert: Swift Swim)
            return {'stage': (m['b'] or {}).get('spe', 0) if ctx.get('stage', True) else 0, 'scarf': toid(sh.get('item', '')) == 'choicescarf' and not m['gone'],
                    'tailwind': ctx['tailwind'][sd], 'par': m['st'] == 'par' and ab != 'Quick Feet', 'weather_x2': bool(ctx['weather']) and ctx['weather'] in WEATHER_SPEED.get(ab, ())}
        out.append({'turn': t, 'kind': kind, 'species': mu['sp'], 'forme': fu, 'first': su == first[0], 'tr': ctx['tr'],
                    'mods': mods(su, mu, shu, fu), 'known': effective(rk, mods(sk, mk, shk, fk)), 'against': mk['sp']})
    def pairs(t, kind, actors, ctx_at):
        for i, a in enumerate(actors):
            for b in actors[i + 1:]: add(t, kind, a[1], b[1], ctx_at(b[0]))
    L = log.split('\n'); cut = [i for i, l in enumerate(L) if l.startswith('|turn|')]
    # the start of the battle: switch-in abilities in Speed order (before any weather, Speed stages, Trick Room or Tailwind)
    if cut and 1 in states:
        st1 = states[1]; seen = []; acts = []
        for l in L[:cut[0]]:
            p = l.split('|')
            if len(p) < 4: continue
            who = p[2] if p[1] == '-ability' and p[3] in SWITCH_IN else None
            m_ = re.search(r'\[from\] ability: ([^|]+)\|\[of\] (p[12][ab]: [^|]+)', l)
            if p[1] in ('-weather', '-fieldstart') and m_ and m_.group(1) in SWITCH_IN: who = m_.group(2)
            if who and who[:3] not in seen:
                seen.append(who[:3]); m = mon(st1, who); acts.append((len(acts), (who[:2], m, m and forme(who[:2], m, False))))
        pairs(1, 'start', acts, lambda i: {'tr': False, 'weather': '', 'tailwind': {'p1': False, 'p2': False}, 'stage': False})
    for k, a in enumerate(cut):
        t = int(L[a][6:]); st = states.get(t)
        if not st: continue
        seg = L[a + 1:cut[k + 1] if k + 1 < len(cut) else len(L)]
        if any(l.startswith('|move|') and l.split('|')[3] in SKIP_TURN for l in seg): continue
        f = st['field']; tw = {sd: st[sd]['tailwind'] > 0 for sd in ('p1', 'p2')}
        ctx0 = lambda i: {'tr': f['tr'] > 0, 'weather': f['weather'], 'tailwind': tw}
        mon_at = lambda pos: next((m for m in st[pos[:2]]['mons'] if m['pos'] == pos[2] and not m['f']), None)
        first_move = next((i for i, l in enumerate(seg) if l.startswith('|move|')), len(seg))
        # the start of the turn: switches (by the Pokemon going out) and Mega Evolutions, each in Speed order
        sw, mg, dirty = [], [], False
        for i, l in enumerate(seg[:first_move]):
            p = l.split('|')
            if speed_line(l) or '-activate' in l and re.search(r'Quick Claw|Custap|Quick Draw', l): dirty = True
            if dirty or len(p) < 3: continue
            if p[1] == 'switch' and mon_at(p[2][:3]): m = mon_at(p[2][:3]); sw.append((i, (p[2][:2], m, forme(p[2][:2], m, True))))
            elif p[1] == 'detailschange' and 'Mega' in l and mon_at(p[2][:3]): m = mon_at(p[2][:3]); mg.append((i, (p[2][:2], m, forme(p[2][:2], m, False))))
        pairs(t, 'switch', sw, ctx0); pairs(t, 'mega', mg, ctx0)
        # moves at the same priority, with the weather as it stood when they began (a Mega's Drought at the start of the turn)
        wl = next((l.split('|')[2] for l in reversed(seg[:first_move]) if l.startswith('|-weather|') and '[upkeep]' not in l), None)
        w_moves = f['weather'] if wl is None else '' if wl == 'none' else R.WEATHER.get(wl, wl)
        formes = {}; switched = set(); moves = []; dirty = False
        for l in seg:
            p = l.split('|')
            if len(p) < 3: continue
            if p[1] in ('switch', 'drag', 'replace'): switched.add(p[2][:3])
            elif p[1] == 'detailschange': formes[p[2][:3]] = p[3].split(',')[0]
            elif p[1] == '-activate' and re.search(r'Quick Claw|Custap|Quick Draw', l): dirty = True
            elif speed_line(l) and moves: dirty = True
            elif p[1] == 'move' and not re.search(r'\[from\](?! lockedmove)', l) and not dirty: moves.append((p[2][:3], p[3]))
        for i, (pa, ma) in enumerate(moves):
            for pb, mb in moves[i + 1:]:
                if pa in switched or pb in switched: continue
                A, B = mon_at(pa), mon_at(pb)
                if not A or not B or pa[:2] == pb[:2]: continue
                if 'Grassy Glide' in (ma, mb): continue                          # +1 in Grassy Terrain: whether it was up at that moment
                if priority(ma, sheet(pa[:2], A).get('ability'), A['hp'] == 100) != priority(mb, sheet(pb[:2], B).get('ability'), B['hp'] == 100): continue
                fa = formes.get(pa) or forme(pa[:2], A, True); fb = formes.get(pb) or forme(pb[:2], B, True)
                add(t, 'move', (pa[:2], A, fa), (pb[:2], B, fb), {'tr': f['tr'] > 0, 'weather': w_moves, 'tailwind': tw})
        # the end of the turn: the same effect on each Pokemon in Speed order, with the field as it stood at that line
        if '|upkeep' not in seg: continue
        up = seg.index('|upkeep'); bl = max((i for i in range(up) if seg[i] == '|'), default=None)
        if bl is None: continue
        res = seg[bl + 1:up]; nxt = states.get(t + 1) or g['final']
        if any(speed_line(l) and not re.match(r'\|-(sideend|fieldend|weather)\|', l) for l in res): continue   # Speed Boost and the like
        w_before = next((l.split('|')[2] for l in reversed(seg[:bl]) if l.startswith('|-weather|') and '[upkeep]' not in l), None)
        w_turn = (R.WEATHER.get(w_before, w_before) if w_before != 'none' else '') if w_before is not None else f['weather']
        def ctx_res(i, res=res, nxt=nxt, w_turn=w_turn):
            ended = lambda pat: any(re.search(pat, l) for l in res[:i])
            later = lambda pat: any(re.search(pat, l) for l in res[i:])
            return {'tr': (nxt['field']['tr'] > 0 or later(r'^\|-fieldend\|.*Trick Room')) and not ended(r'^\|-fieldend\|.*Trick Room'),
                    'weather': '' if ended(r'^\|-weather\|none') else w_turn,
                    'tailwind': {sd: (nxt[sd]['tailwind'] > 0 or later(rf'^\|-sideend\|{sd}: .*Tailwind')) and not ended(rf'^\|-sideend\|{sd}: .*Tailwind') for sd in ('p1', 'p2')}}
        groups = collections.defaultdict(list)
        for i, l in enumerate(res):
            p = l.split('|')
            if len(p) < 4: continue
            key = 'perish' if p[1] == '-start' and p[3].startswith('perish') else (RESIDUAL.search(l).group(1) if p[1] in ('-damage', '-heal') and RESIDUAL.search(l) else None)
            if key and not any(x[1][0] == p[2][:3] for x in groups[key]):
                m = mon(nxt, p[2]); groups[key].append((i, (p[2][:3], (p[2][:2], m, m and forme(p[2][:2], m, True)))))
        for key, items in groups.items(): pairs(t, 'residual', [(i, a) for i, (_, a) in items], ctx_res)
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
