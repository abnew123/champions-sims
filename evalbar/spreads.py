"""Opponents' stat points, which the open team sheets do not show (the user's idea, 2026-10-11): the species' spreads from the Smogon Reg M-C
stats in order of use (regionals/smogon_mc_2026-09_moveset.txt), those with the nature its team sheet shows; the most used one the game has
not ruled out, else the next, and so on. What rules a spread out so far: the order two Pokemon moved in, when the other one's Speed is
known exactly (a bot's own Pokemon, from its requests) and nothing else could explain the order. When every listed spread is ruled out,
the most used one with its Speed points moved just enough to fit.
  ranked(species, nature, item) -> [(share, evs)]   evs as [hp, atk, def, spa, spd, spe] stat points
  observations(log, known_side, known_speed) -> [obs]   known_speed(species, forme) -> that Pokemon's raw Speed
  pick(species, nature, item, guess, obs) -> (evs, why)
Speed in Champions at level 50: (2 base + 31 + 2 points) / 2 + 5, times the nature."""
import os, re, json, math, collections
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
# fitted defaults (the user, 2026-10-13: "wire them in"): for each species and nature the whole spread that fits the most of the replays'
# evidence (popfit.py: hits taken and given, turn order; held out, it fits 87.9% of each Pokemon's evidence against 85.1% for Smogon's most
# used). With FITTED the eval bar's programs take it as the default and as the first candidate when a game's hits and turn order pick one;
# the bot's do not set it yet, and the analyses that measure against Smogon's list (popfit, spread_fit) leave it off
FITTED = False
_FIT = None
def fitted(species, nature):
    """the fitted spread for this species (its base form, as the sheets name it) and nature, or None"""
    global _FIT
    if _FIT is None:
        f = os.path.join(C.HERE, 'default_spreads.json'); _FIT = json.load(open(f))['spreads'] if os.path.exists(f) else {}
    e = _FIT.get(f"{toid(species)}|{nature}") or _FIT.get(f"{toid(species.split('-')[0])}|{nature}")
    return list(e) if e else None
def candidates(species, nature, item=''):
    """[(share, evs, name)]: the fitted spread first (with FITTED), then Smogon's listed ones, most used first"""
    f = fitted(species, nature) if FITTED else None
    return ([(None, f, 'fitted to the replays')] if f else []) + [(w, list(e), f'Smogon #{i + 1} ({100 * w:.0f}%)') for i, (w, e) in enumerate(ranked(species, nature, item))]
def raw_speed(forme, evs, nature):
    sp = E['species'].get(toid(forme))
    if not sp: return None
    n = E['natures'].get(toid(nature), {}); m = 1.1 if n.get('plus') == 'spe' else 0.9 if n.get('minus') == 'spe' else 1.0
    return int(((2 * sp['stats']['spe'] + 31 + 2 * evs[5]) * 50 // 100 + 5) * m)
STAGE = {-6: 2 / 8, -5: 2 / 7, -4: 2 / 6, -3: 2 / 5, -2: 2 / 4, -1: 2 / 3, 0: 1, 1: 1.5, 2: 2, 3: 2.5, 4: 3, 5: 3.5, 6: 4}
WEATHER_SPEED = {'Swift Swim': ('Rain', 'Heavy rain'), 'Chlorophyll': ('Sun', 'Harsh sun'), 'Sand Rush': ('Sandstorm',), 'Slush Rush': ('Snow',)}   # as replay.py names weather
TERRAIN_SPEED = {'Surge Surfer': 'Electric'}                                 # as replay.py names terrain (the eval bar's strict reading)
TERRAIN_LINE = re.compile(r'^\|-field(start|end)\|move: (\w+) Terrain')
def exact_speed(raw, mods):
    """Showdown's action Speed, as the engine has it exactly (Battle sim, 2026-10-12): the stage with a floor, the ModifySpe chain
    (Tailwind, a weather or terrain ability, Choice Scarf) in 4096ths and applied rounding half down, paralysis last (its finalModify),
    at most 10000. x2 and x1.5 are exact in 4096ths, so their order does not matter"""
    b = max(-6, min(6, mods['stage'])); half = [2, 3, 4, 5, 6, 7, 8]
    s = raw * half[b] // 2 if b >= 0 else raw * 2 // half[-b]
    mod = 4096
    for on, m in ((mods.get('tailwind'), 2), (mods.get('weather_x2'), 2), (mods.get('terrain_x2'), 2), (mods.get('scarf'), 1.5)):
        if on: mod = (mod * int(m * 4096) + 2048) >> 12
    s = (s * mod + 2047) // 4096
    if mods.get('par'): s = s * 50 // 100
    return min(s, 10000)
def effective(raw, mods):
    """the Speed the turn order uses: stages, then Choice Scarf, a weather or terrain ability, Tailwind, paralysis (exact: Showdown's
    integer arithmetic, the eval bar's strict level 3)"""
    if mods.get('exact'): return exact_speed(raw, mods)
    v = int(raw * STAGE.get(mods['stage'], 1))
    if mods['scarf']: v *= 1.5
    if mods['weather_x2']: v *= 2
    if mods.get('terrain_x2'): v *= 2
    if mods['tailwind']: v *= 2
    if mods['par']: v *= 0.5
    return v
SKIP_TURN = {'After You', 'Quash', 'Instruct', 'Ally Switch'}               # moves that change the order of what follows
def speed_line(l, strict=False):
    """a line that can change a Pokemon's Speed or the turn order mid-turn (strict: a terrain starting or ending too, for Surge Surfer)"""
    if strict and TERRAIN_LINE.match(l): return True
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
def observations(log, known_side, known_speed, sheets, strict=False):
    """the orders the log shows between a Pokemon of the other side and one of the known side where Speed decided it (Trick Room
    reversing it) and nothing could have changed either one's Speed or the field in between:
      start     whose switch-in ability (Intimidate, weather, terrain, ...) went first as the battle began
      switch    who switched out first at the start of a turn          mega   who Mega Evolved first (both at their old Speed)
      move      who moved first at the same priority
      residual  who took or regained HP first from the same end-of-turn effect (sand, poison, burn, Leftovers, Black Sludge, Grassy
                Terrain, Leech Seed, Salt Cure), or counted down Perish Song first
    [{turn, kind, species, forme, first, tr, mods, known}]: known is the known Pokemon's effective Speed, mods the other one's modifiers
    (its raw Speed is what is unknown). strict (the eval bar's): Surge Surfer in Electric Terrain, the terrain as it stood at each point"""
    out = []; g = R.parse(log); states = {s['turn']: s['state'] for s in g['steps'] if s['turn'] >= 1 and s['state']}
    surge = strict and any(v and v.get('ability') in TERRAIN_SPEED for sd in sheets for v in sheets[sd].values())   # terrain can change a Speed
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
        """first acted before second, each (side, mon, forme); ctx: tr, weather, terrain, tailwind {side: bool}, stage (False: Speed stages not counted)"""
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
                    'tailwind': ctx['tailwind'][sd], 'par': m['st'] == 'par' and ab != 'Quick Feet', 'weather_x2': bool(ctx['weather']) and ctx['weather'] in WEATHER_SPEED.get(ab, ()),
                    **({'terrain_x2': True} if strict and ab in TERRAIN_SPEED and ctx.get('terrain') == TERRAIN_SPEED[ab] else {}),
                    **({'exact': True} if strict and strict >= 3 else {})}
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
        ctx0 = lambda i: {'tr': f['tr'] > 0, 'weather': f['weather'], 'terrain': f.get('terrain') or '', 'tailwind': tw}
        mon_at = lambda pos: next((m for m in st[pos[:2]]['mons'] if m['pos'] == pos[2] and not m['f']), None)
        first_move = next((i for i, l in enumerate(seg) if l.startswith('|move|')), len(seg))
        # the start of the turn: switches (by the Pokemon going out) and Mega Evolutions, each in Speed order
        sw, mg, dirty = [], [], False
        for i, l in enumerate(seg[:first_move]):
            p = l.split('|')
            if speed_line(l, surge) or '-activate' in l and re.search(r'Quick Claw|Custap|Quick Draw', l): dirty = True
            if dirty or len(p) < 3: continue
            if p[1] == 'switch' and mon_at(p[2][:3]): m = mon_at(p[2][:3]); sw.append((i, (p[2][:2], m, forme(p[2][:2], m, True))))
            elif p[1] == 'detailschange' and 'Mega' in l and mon_at(p[2][:3]): m = mon_at(p[2][:3]); mg.append((i, (p[2][:2], m, forme(p[2][:2], m, False))))
        pairs(t, 'switch', sw, ctx0); pairs(t, 'mega', mg, ctx0)
        # moves at the same priority, with the weather as it stood when they began (a Mega's Drought at the start of the turn)
        wl = next((l.split('|')[2] for l in reversed(seg[:first_move]) if l.startswith('|-weather|') and '[upkeep]' not in l), None)
        w_moves = f['weather'] if wl is None else '' if wl == 'none' else R.WEATHER.get(wl, wl)
        tl = next((TERRAIN_LINE.match(l) for l in reversed(seg[:first_move]) if TERRAIN_LINE.match(l)), None)
        t_moves = (f.get('terrain') or '') if tl is None else tl.group(2) if tl.group(1) == 'start' else ''
        formes = {}; switched = set(); moves = []; dirty = False
        for l in seg:
            p = l.split('|')
            if len(p) < 3: continue
            if p[1] in ('switch', 'drag', 'replace'): switched.add(p[2][:3])
            elif p[1] == 'detailschange': formes[p[2][:3]] = p[3].split(',')[0]
            elif p[1] == '-activate' and re.search(r'Quick Claw|Custap|Quick Draw', l): dirty = True
            elif speed_line(l, surge) and moves: dirty = True
            elif p[1] == 'move' and not re.search(r'\[from\](?! lockedmove)', l) and not dirty: moves.append((p[2][:3], p[3]))
        for i, (pa, ma) in enumerate(moves):
            for pb, mb in moves[i + 1:]:
                if pa in switched or pb in switched: continue
                A, B = mon_at(pa), mon_at(pb)
                if not A or not B or pa[:2] == pb[:2]: continue
                if 'Grassy Glide' in (ma, mb): continue                          # +1 in Grassy Terrain: whether it was up at that moment
                if priority(ma, sheet(pa[:2], A).get('ability'), A['hp'] == 100) != priority(mb, sheet(pb[:2], B).get('ability'), B['hp'] == 100): continue
                fa = formes.get(pa) or forme(pa[:2], A, True); fb = formes.get(pb) or forme(pb[:2], B, True)
                add(t, 'move', (pa[:2], A, fa), (pb[:2], B, fb), {'tr': f['tr'] > 0, 'weather': w_moves, 'terrain': t_moves, 'tailwind': tw})
        # the end of the turn: the same effect on each Pokemon in Speed order, with the field as it stood at that line
        if '|upkeep' not in seg: continue
        up = seg.index('|upkeep'); bl = max((i for i in range(up) if seg[i] == '|'), default=None)
        if bl is None: continue
        res = seg[bl + 1:up]; nxt = states.get(t + 1) or g['final']
        if any(speed_line(l) and not re.match(r'\|-(sideend|fieldend|weather)\|', l) for l in res): continue   # Speed Boost and the like
        w_before = next((l.split('|')[2] for l in reversed(seg[:bl]) if l.startswith('|-weather|') and '[upkeep]' not in l), None)
        w_turn = (R.WEATHER.get(w_before, w_before) if w_before != 'none' else '') if w_before is not None else f['weather']
        tb = next((TERRAIN_LINE.match(l) for l in reversed(seg[:bl]) if TERRAIN_LINE.match(l)), None)
        t_turn = (f.get('terrain') or '') if tb is None else tb.group(2) if tb.group(1) == 'start' else ''
        def ctx_res(i, res=res, nxt=nxt, w_turn=w_turn, t_turn=t_turn):
            ended = lambda pat: any(re.search(pat, l) for l in res[:i])
            later = lambda pat: any(re.search(pat, l) for l in res[i:])
            return {'tr': (nxt['field']['tr'] > 0 or later(r'^\|-fieldend\|.*Trick Room')) and not ended(r'^\|-fieldend\|.*Trick Room'),
                    'weather': '' if ended(r'^\|-weather\|none') else w_turn,
                    'terrain': '' if ended(r'^\|-fieldend\|move: \w+ Terrain') else t_turn,
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
    u = effective(raw, ob['mods']); k = ob['known']
    if ob['mods'].get('exact'): faster = u > k; slower = u < k             # exact (strict 3): only an equal Speed is a tie
    else: faster = u > k + 1; slower = u < k - 1                            # within 1: a tie (or rounding), either order
    went_first = ob['first'] != ob['tr']                                    # under Trick Room the slower one goes first
    return not slower if went_first else not faster
def pick(species, nature, item, guess, obs, misses=None, nd=0):
    """the most used listed spread (with this nature) that fits what the game showed (the turn order, and with misses(evs) the hits it
    does not fit), else the old guess if it fits, else (the hits ruling every spread out) the one missing the fewest hits, and if the turn
    order rules that out, it with its Speed points moved as little as fits: (evs, why)"""
    obs = [o for o in obs if toid(o['species']) == toid(species)]
    cands = candidates(species, nature, item) + [(0, list(guess), 'the plain guess')]
    seen = (f', fits {len(obs)} observed turn orders' if obs else '') + (f', {nd} hits' if nd else '')
    m = {tuple(e): (misses(e) if misses else 0) for _, e, _ in cands}
    for w, evs, name in cands:
        if m[tuple(evs)] == 0 and all(fits(evs, nature, o) for o in obs): return list(evs), name + seen
    if misses and min(m.values()) > 0:                                        # the hits rule every spread out: the closest, then the turn order
        k = min(range(len(cands)), key=lambda i: (m[tuple(cands[i][1])], i)); cands = [cands[k]] + cands[:k] + cands[k + 1:]
        if all(fits(cands[0][1], nature, o) for o in obs): return list(cands[0][1]), f"{cands[0][2]}, missing {m[tuple(cands[0][1])]} of {nd} hits (the closest)"
    else: cands = sorted(cands, key=lambda c: m[tuple(c[1])] > 0)            # spreads that fit the hits first
    top = cands[0][1]
    for d in sorted(range(33), key=lambda x: abs(x - top[5])):
        evs = top[:5] + [d]
        if all(fits(evs, nature, o) for o in obs): return evs, f'{cands[0][2]} with {d} Speed points (the turn order rules out every listed spread)'
    return list(top), f'{cands[0][2]} (no spread fits every observed turn order)'
# ---- damage (the user's next step, 2026-10-11): what a hit did, against what Showdown says each candidate spread allows ----
FIXED_DMG = {'Seismic Toss', 'Night Shade', 'Super Fang', 'Ruination', 'Final Gambit', 'Endeavor', 'Counter', 'Mirror Coat', 'Metal Burst', 'Psywave',
             # damage that depends on the order of the turn, which a rebuilt position does not have
             'Payback', 'Bolt Beak', 'Fishious Rend', 'Avalanche', 'Revenge', 'Assurance', 'Stomping Tantrum', 'Temper Flare', 'Retaliate', 'Lash Out'}
ORDER_ABILITIES = {'Analytic', 'Stakeout'}
SD_WEATHER = {'RainDance': 'Rain', 'SunnyDay': 'Sun', 'Sandstorm': 'Sandstorm', 'Snowscape': 'Snow', 'Snow': 'Snow', 'Hail': 'Hail',
              'DesolateLand': 'Harsh sun', 'PrimordialSea': 'Heavy rain', 'DeltaStream': 'Strong winds', 'none': None}
def damage_observations(log, known_side, mid_weather=False):
    """hits between a Pokemon of the known side and one of the other, where nothing changed either one's stats, item or form, the
    weather, terrain or screens earlier in the turn: [{turn, n, att, def, move, crit, spread, helping, hp: {att, def}, d | pct, atleast}]
    att / def as 'p1a' positions at the start of the turn; d the exact damage when the target is the known side's (its HP is exact),
    pct (before, after) percents when it is the other side's; atleast when it fainted or Focus Sash / Sturdy held (the hit did at least that).
    mid_weather (strict, a level: the bot's is 1 since the user OK'd it on 2026-10-12, the eval bar's 2): a hit after the weather changed
    earlier in the turn (a Mega Charizard Y's Drought) is kept, with 'weather' the weather it landed in, instead of left out; at 2 also a
    hit after the turn changed a stat stage (Intimidate, Defiant: 'boosts', applied) and a multi-hit move's first hit"""
    out = []; L = log.split('\n'); cut = [i for i, l in enumerate(L) if l.startswith('|turn|')]
    hp = {}                                                                   # 'p1a' -> (current, max) for the known side, percent for the other
    def read_hp(pos, tok):
        tok = tok.split()[0] if tok else ''
        if 'fnt' in tok or tok == '0': return 0
        m = re.match(r'(\d+)/(\d+)', tok)
        return (int(m.group(1)), int(m.group(2))) if m and pos[:2] == known_side else int(m.group(1)) if m else None
    for l in L[:cut[0] if cut else len(L)]:                                   # the leads
        p = l.split('|')
        if len(p) > 4 and p[1] in ('switch', 'drag', 'replace'): hp[p[2][:3]] = read_hp(p[2][:3], p[4])
    for k in cut:
        l = L[k]
        if True:
            t = int(l[6:]); end = cut[cut.index(k) + 1] if cut.index(k) + 1 < len(cut) else len(L); seg = L[k + 1:end]
            changed = set(); helping = set(); switched = set(); megas = set(); n = 0; i = 0; dirty = [False]; wx = [None]; bd = {}
            def track(l2):
                """what a line changes for the hits after it this turn"""
                q = l2.split('|')
                if len(q) < 3: return
                kind = q[1]
                if kind in ('switch', 'drag', 'replace'): switched.add(q[2][:3]); hp[q[2][:3]] = read_hp(q[2][:3], q[4] if len(q) > 4 else '')
                elif kind == 'detailschange' and 'Mega' in l2: megas.add(q[2][:3])
                elif kind == '-clearallboost': dirty[0] = True
                elif mid_weather >= 2 and kind in ('-boost', '-unboost') and len(q) > 4 and q[4].isdigit():   # strict 2: kept as a change to its stages
                    c_ = bd.setdefault(q[2][:3], {}); c_[q[3]] = c_.get(q[3], 0) + (int(q[4]) if kind == '-boost' else -int(q[4]))
                elif mid_weather >= 2 and kind == '-ability' and len(q) > 3 and q[3] == 'Intimidate': pass   # the holder's own stats are as they were
                elif kind in ('-boost', '-unboost', '-setboost', '-clearboost', '-clearnegativeboost', '-swapboost', '-copyboost', '-invertboost',
                              '-status', '-enditem', '-item', '-formechange', '-transform', '-start', '-ability'): changed.add(q[2][:3])
                elif kind == '-weather' and '[upkeep]' not in l2 and mid_weather and q[2] in SD_WEATHER: wx[0] = q[2]
                elif kind in ('-weather', '-fieldstart', '-fieldend', '-sidestart', '-sideend') and '[upkeep]' not in l2: dirty[0] = True
                elif kind in ('-damage', '-heal', '-sethp') and len(q) > 3:
                    v = read_hp(q[2][:3], q[3])
                    if v is not None: hp[q[2][:3]] = v
            while i < len(seg):
                l2 = seg[i]; q = l2.split('|')
                if len(q) < 3: i += 1; continue
                kind = q[1]
                if kind != 'move' or re.search(r'\[from\](?! lockedmove)', l2): track(l2); i += 1; continue
                if True:
                    dirty_field = dirty[0]
                    att = q[2][:3]; move = q[3]
                    if move == 'Helping Hand' and len(q) > 4 and q[4]: helping.add(q[4][:3])
                    block = []; j = i + 1
                    while j < len(seg) and not re.match(r'\|(move|switch|drag|replace)\||^\|$', seg[j]): block.append(seg[j]); j += 1
                    multi = any(x.startswith('|-hitcount|') for x in block); first = set()   # strict 2: a multi-hit move's first hit is an ordinary hit
                    skip = dirty_field or att in changed or att in switched or move in FIXED_DMG or (multi and not mid_weather >= 2)
                    crit = {x.split('|')[2][:3] for x in block if x.startswith('|-crit|')}
                    held = {x.split('|')[2][:3] for x in block if re.match(r'\|-enditem\|[^|]+\|Focus Sash|\|-activate\|[^|]+\|ability: Sturdy', x)}
                    nosub = {x.split('|')[2][:3] for x in block if re.search(r'Substitute|Disguise|Ice Face', x)}
                    before = dict(hp); boosted = set(); pcrit = set()
                    for x in block:                                           # the hits, and HP as the block leaves it
                        y = x.split('|')
                        if len(y) > 2 and y[1] == '-crit': pcrit.add(y[2][:3])         # a crit marks the hit that follows it (each hit of a multi-hit move)
                        if len(y) > 2 and y[1] in ('-boost', '-unboost', '-setboost', '-clearboost', '-enditem', '-item', '-formechange'): boosted.add(y[2][:3])   # mid-move (Electro Shot's charge)
                        if att in boosted: skip = True
                        if len(y) > 3 and y[1] in ('-damage', '-heal', '-sethp'):
                            v = read_hp(y[2][:3], y[3])
                            if y[1] == '-damage' and '[from]' not in x and not skip and not (multi and y[2][:3] in first):
                                d_ = y[2][:3]; first.add(d_)
                                if d_[:2] != att[:2] and known_side in (att[:2], d_[:2]) and d_ not in changed and d_ not in switched and d_ not in nosub and d_ not in boosted and before.get(d_) is not None and v is not None:
                                    ob = {'turn': t, 'n': n, 'att': att, 'def': d_, 'move': move, 'crit': (d_ in pcrit) if multi else d_ in crit, 'spread': '[spread]' in l2, 'helping': att in helping,
                                          'megas': sorted(megas), 'atleast': v == 0 or d_ in held, **({'weather': wx[0]} if wx[0] else {}),
                                          **({'boosts': {k_: dict(bd[k_]) for k_ in (att, d_) if bd.get(k_)}} if bd.get(att) or bd.get(d_) else {})}
                                    ha = before.get(att); hd = before[d_]
                                    ob['hp'] = {'att': ['abs', ha[0]] if isinstance(ha, tuple) else ['pct', ha] if ha else None, 'def': ['abs', hd[0]] if isinstance(hd, tuple) else ['pct', hd]}
                                    if d_[:2] == known_side: ob['d'] = hd[0] - (v[0] if isinstance(v, tuple) else 0)
                                    else: ob['pct'] = (hd, v if isinstance(v, int) else 0)
                                    out.append(ob); n += 1
                        track(x)                                          # the turn goes on: screens, boosts, items set in this block
                    i = j; continue
    return out
def shown(h, M):
    """the percent Showdown shows for h of M HP"""
    return 100 if h >= M else min(99, max(1, math.ceil(100 * h / M)))
def damage_fits(ob, r, slack=1):
    """does the hit fit Showdown's range r {lo, hi, maxhp} for this candidate? slack: HP either way (1 for the frozen bot's reading; the
    eval bar's strict one has none: on 806 hits in simulated battles with known spreads every hit landed inside the range or missed by more)"""
    if not r or r.get('error') or r.get('lo') is None: return True                # the calculation could not be made: no evidence
    lo, hi, M = r['lo'] + 1 - slack, r['hi'] - 1 + slack, r['maxhp']
    if 'd' in ob: return hi >= ob['d'] - 1 if ob['atleast'] else lo - 1 <= ob['d'] <= hi + 1
    p0, p1 = ob['pct']; H0 = [h for h in range(1, M + 1) if shown(h, M) == p0]; H1 = [0] if p1 == 0 else [h for h in range(1, M + 1) if shown(h, M) == p1]
    if not H0 or not H1: return True
    if ob['atleast']: return hi >= min(H0) - 1
    return lo - 1 <= max(H0) - min(H1) and min(H0) - max(H1) <= hi + 1
_DCACHE = {}
def damage_ranges(gp, sets, known_side, known_evs, dobs, cands, strict=False):
    """{(obs index, species, evs): Showdown's range} for each damage observation and each candidate spread of the other side's Pokemon
    in it, through damage.js (cached: a hit and a spread are worked out once). strict: damage.js's exact reading (a percent stands for each HP
    it could be, screens broken first by Psychic Fangs and the like)"""
    import live as LV, procs as P, battlestate as BS, subprocess, tempfile, hashlib
    steps = {x['turn']: x['state'] for x in gp['steps'] if x['state']}; other = 'p2' if known_side == 'p1' else 'p1'
    want = []; res = {}
    for oi, ob in enumerate(dobs):
        st = steps.get(ob['turn'])
        if not st: continue
        upos = ob['att'] if ob['att'][:2] == other else ob['def']
        um = next((m for m in st[other]['mons'] if m['pos'] == upos[2] and not m['f']), None)
        if not um or um['sp'] not in cands: continue
        order = {sd: sorted(st[sd]['mons'], key=lambda m: (0 if m['pos'] == 'a' else 1 if m['pos'] == 'b' else 2 if not m['f'] else 3)) for sd in ('p1', 'p2')}
        def idx(pos): return next((i for i, m in enumerate(order[pos[:2]]) if m['pos'] == pos[2] and not m['f']), None)
        ia, idf = idx(ob['att']), idx(ob['def'])
        if ia is None or idf is None: continue
        am = order[ob['att'][:2]][ia]; aset = sets[ob['att'][:2]].get(am['sp']) or {}
        mf = mega_of(am['sp'], aset.get('item', '')) if (am['mega'] or ob['att'] in ob['megas']) else None
        if aset.get('ability') in ORDER_ABILITIES or (mf and (E['species'].get(toid(mf), {}).get('abilities') or {}).get('0') in ORDER_ABILITIES): continue
        for evs in cands[um['sp']]:
            key = (hashlib.md5(json.dumps([strict, ob, um['sp'], [[m['sp'], m['hp'], m['b'], m['st'], m['gone']] for sd in ('p1', 'p2') for m in order[sd]], st['field']], sort_keys=True).encode()).hexdigest(), tuple(evs))
            if key in _DCACHE: res[(oi, um['sp'], tuple(evs))] = _DCACHE[key]; continue
            sides = []
            for sd in ('p1', 'p2'):
                mons = []
                for m in order[sd]:
                    s_ = sets[sd].get(m['sp']) or next((v for k_, v in sets[sd].items() if v and toid(k_.split('-')[0]) == toid(m['sp'].split('-')[0])), None)
                    if not s_: break
                    s_ = dict(s_)
                    if sd == known_side and known_evs.get(toid(m['sp'].split('-')[0])): s_['evs'] = list(known_evs[toid(m['sp'].split('-')[0])][0])
                    if sd == other and m['sp'] == um['sp']: s_['evs'] = list(evs)
                    x = BS.mon(m, s_, {})                        # the damage check's positions ask for none of positions.js's fixes
                    if sd + m['pos'] in ob['megas']: x['mega'] = True
                    if (ob.get('boosts') or {}).get(sd + m['pos']):                # stages changed earlier in the turn (Intimidate, Defiant)
                        x['boosts'] = {**(x.get('boosts') or {})}
                        for k_, v_ in ob['boosts'][sd + m['pos']].items(): x['boosts'][k_] = max(-6, min(6, x['boosts'].get(k_, 0) + v_))
                    mons.append(x)
                else:
                    while len(mons) < 4: mons.append({**mons[-1], 'fainted': True, 'onField': False})   # a full team for 'team 1234'
                    sides.append({'mons': mons, 'tailwind': st[sd]['tailwind'], 'screens': st[sd]['screens'], 'hazards': st[sd]['hazards']}); continue
                break
            if len(sides) < 2: continue
            f = st['field']
            spec = {'name': 'dmg', 'turn': ob['turn'], 'sides': sides, 'acts': [[None, None], [None, None]], 'perish': st['perish'], 'standIns': 0, 'dropped': [],
                    'field': {'weather': [f['weather'], f['wturns']] if f['weather'] else None, 'terrain': [f['terrain'], f['tturns']] if f['terrain'] else None, 'trickroom': f['tr']}}
            if ob.get('weather'): spec['field']['weather'] = [SD_WEATHER[ob['weather']], 5] if SD_WEATHER[ob['weather']] else None   # as it landed
            want.append((key, (oi, um['sp'], tuple(evs)), {'spec': spec, 'att': [0 if ob['att'][:2] == 'p1' else 1, ia], 'def': [0 if ob['def'][:2] == 'p1' else 1, idf],
                                                          'move': ob['move'], 'crit': ob['crit'], 'spread': ob['spread'], 'helping': ob['helping'], 'hp': ob['hp'],
                                                          **({'strict': int(strict)} if strict else {})}))
    if want:
        with tempfile.TemporaryDirectory() as d:
            qf, of = os.path.join(d, 'q.json'), os.path.join(d, 'r.json'); json.dump([w[2] for w in want], open(qf, 'w'))
            r = subprocess.run([P.exe('node'), os.path.join(C.HERE, 'damage.js'), qf, of], cwd=os.path.join(C.MAIN, 'pssim'), capture_output=True, text=True)
            got = json.load(open(of)) if r.returncode == 0 and os.path.exists(of) else [None] * len(want)
        for (key, k2, _), g_ in zip(want, got): _DCACHE[key] = g_; res[k2] = g_
    return res
def refine(log, gp, sets, known_side, known_evs, strict=False):
    """the other side's spreads in sets picked against the turn order the log shows; known_evs {species id: (evs, nature)} for the known
    side's Pokemon (a bot's own). Returns {species: why}"""
    def ks(species, forme):
        k = known_evs.get(toid(species)) or known_evs.get(toid(species.split('-')[0]))
        return raw_speed(forme, *k) if k else None
    obs = observations(log, known_side, ks, gp['sheets'], strict)
    other = 'p2' if known_side == 'p1' else 'p1'; why = {}
    dobs = damage_observations(log, known_side, strict)                         # strict: the eval bar's (the frozen bot's is the older reading)
    cands = {sp: [list(e) for _, e, _ in candidates(sp, st['nature'], st['item'])] + [list(st['evs'])] for sp, st in sets[other].items() if st}
    R_ = damage_ranges(gp, sets, known_side, known_evs, dobs, cands, strict) if dobs else {}
    for sp, st in sets[other].items():
        if not st: continue
        mine = [(oi, ob) for oi, ob in enumerate(dobs) if any(k[0] == oi and k[1] == sp for k in R_)]
        misses = lambda evs, sp=sp, mine=mine: sum(not damage_fits(ob, R_.get((oi, sp, tuple(evs))), 0 if strict else 1) for oi, ob in mine)
        evs, why[sp] = pick(sp, st['nature'], st['item'], st['evs'], obs, misses if mine else None, len(mine))
        if strict and mine and misses(evs) > 0:                              # no listed spread fits the hits: look nearby
            near = nearby(gp, sets, known_side, known_evs, dobs, sp, st, mine, obs, misses, strict)
            if near: evs, why[sp] = near
        sets[other][sp] = {**st, 'evs': evs}
    return why
STATS6 = ['HP', 'Atk', 'Def', 'SpA', 'SpD', 'Spe']
def nearby(gp, sets, known_side, known_evs, dobs, sp, st, mine, obs, misses0, strict=True):
    """the eval bar's strict reading, when the hits rule out every listed spread (about half of each species' use is outside Smogon's
    list): the most used spreads (and the plain guess) with points moved into the stats the missed hits involve (HP and the defence a
    hit on it used, the attack stat of a hit by it), at most two moves, keeping the turn order; fewest missed hits, then the smallest
    change, then the most used start. (evs, why) or None if nothing nearby misses fewer hits. The user asked for it (2026-10-12): a
    Charizard, a Gholdengo and an Indeedee survived on 1% hits their guessed spreads could not"""
    other = 'p2' if known_side == 'p1' else 'p1'
    bases = [(name.split(' (')[0], list(e)) for _, e, name in candidates(sp, st['nature'], st['item'])[:4 if FITTED else 3]] + [('the plain guess', list(st['evs']))]
    mobs = [o for o in obs if toid(o['species']) == toid(sp)]
    def targets(evs):
        out = set()
        for oi, ob in mine:
            cat = (E['moves'].get(toid(ob['move'])) or {}).get('category')
            if ob['def'][:2] == other: out |= {0, 2 if cat == 'Physical' else 4}
            else: out.add(1 if cat == 'Physical' else 3)
        return out
    def moves(evs):
        for t in targets(evs):
            for f in range(6):
                if f == t or f in targets(evs): continue
                for d in (2, 4, 6, 8, 10, 12, 16, 20, 24, 28, 32):
                    if evs[f] >= d and evs[t] + d <= 32:
                        e = list(evs); e[f] -= d; e[t] += d; yield e, d, f, t
    best = None; m0 = misses0(bases[0][1]); allc = {}
    frontier = [(name, e, 0, '') for name, e in bases]
    for rnd in range(2):
        cand = {}
        for name, e0, d0, how0 in frontier:
            for e, d, f, t in moves(e0):
                if tuple(e) in cand or tuple(e) in allc or not all(fits(e, st['nature'], o) for o in mobs): continue
                cand[tuple(e)] = (name, d0 + d, (how0 + ', ' if how0 else '') + f'{d} from {STATS6[f]} to {STATS6[t]}')
        if not cand: break
        allc.update(cand)
        R2 = damage_ranges(gp, sets, known_side, known_evs, dobs, {sp: [list(e) for e in cand]}, strict)
        scored = sorted((sum(not damage_fits(ob, R2.get((oi, sp, e)), 0) for oi, ob in mine), cand[e][1], [b[0] for b in bases].index(cand[e][0]), e) for e in cand)
        top = scored[0]
        if best is None or top[:3] < best[:3]: best = top
        if top[0] == 0: break
        frontier = [(cand[e][0], list(e), cand[e][1], cand[e][2]) for _, _, _, e in scored[:4]]
    if best is None or best[0] >= min(m0, min(misses0(e) for _, e in bases)): return None
    name, _, how = allc[best[3]]
    return list(best[3]), f"{name} with {how} ({'fits' if best[0] == 0 else f'misses {best[0]} of'} {len(mine)} hits; no listed spread does)"
