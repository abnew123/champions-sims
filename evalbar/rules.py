"""Two versions of a broadcast game's state, for checking the reader. The battle text says what changed ("The opposing Archaludon's Defense
rose!"), but a misread or missed message changes the state the bar evaluates. The rules version keeps the log's facts (who came in, who
used which move on whom, Protect, misses, immunities, super-effective and critical hits, hit counts, faints, HP) and drops its stat and
field messages, deriving them instead from the rules: abilities on entry (Intimidate, Drizzle, Psychic Surge, ...) and on being hit
(Stamina, Weakness Policy, Justified, ...), each move's stat changes (Close Combat, Calm Mind, Snarl, Lumina Crash, Parting Shot, Electro
Shot's charge), Speed Boost, and weather / terrain / Trick Room / Tailwind / screens with their durations; abilities and items come from
the team sheets. Where the two versions disagree at the start of a turn, the page flags it and the user says which is right.
  compare(log) -> {turn: [check]}: check = {'key', 'what', 'messages', 'rules', 'fix': log lines that make the state the rules' version}
  python3 evalbar/rules.py <broadcast game log>        prints the checks"""
import os, re, sys, json, collections
import common as C, replay as R
toid = R.toid
E = json.load(open(os.path.join(C.MAIN, 'native', 'engine_data_full.json')))
STATS = ('atk', 'def', 'spa', 'spd', 'spe'); STATNAME = {'atk': 'Attack', 'def': 'Defense', 'spa': 'Sp. Atk', 'spd': 'Sp. Def', 'spe': 'Speed'}
MESSAGE_LINES = ('-boost', '-unboost', '-setboost', '-clearallboost', '-clearboost', '-weather', '-fieldstart', '-fieldend', '-sidestart', '-sideend')
NO_DROPS = {'Clear Body', 'White Smoke', 'Full Metal Body'}                                # no stat drops from foes
NO_INTIMIDATE = NO_DROPS | {'Hyper Cutter', 'Inner Focus', 'Oblivious', 'Own Tempo', 'Scrappy'}
WEATHER_AB = {'Drizzle': 'RainDance', 'Drought': 'SunnyDay', 'Orichalcum Pulse': 'SunnyDay', 'Sand Stream': 'Sandstorm', 'Snow Warning': 'Snowscape'}
TERRAIN_AB = {'Electric Surge': 'Electric', 'Hadron Engine': 'Electric', 'Grassy Surge': 'Grassy', 'Misty Surge': 'Misty', 'Psychic Surge': 'Psychic'}
WEATHER_MOVE = {'raindance': 'RainDance', 'sunnyday': 'SunnyDay', 'sandstorm': 'Sandstorm', 'snowscape': 'Snowscape', 'chillyreception': 'Snowscape'}
TERRAIN_MOVE = {'electricterrain': 'Electric', 'grassyterrain': 'Grassy', 'mistyterrain': 'Misty', 'psychicterrain': 'Psychic'}
ROCK = {'RainDance': 'Damp Rock', 'SunnyDay': 'Heat Rock', 'Sandstorm': 'Smooth Rock', 'Snowscape': 'Icy Rock'}
TARGET_DROPS = {'partingshot': {'atk': -1, 'spa': -1}}                                    # stat changes the data leaves to code
CHARGE = {'electroshot': 'RainDance', 'meteorbeam': None}                               # +1 Sp. Atk while charging; in this weather it fires at once
SCREENS = {'reflect': 'Reflect', 'lightscreen': 'Light Screen', 'auroraveil': 'Aurora Veil'}
ABSORB = {'Levitate': 'Ground', 'Earth Eater': 'Ground', 'Flash Fire': 'Fire', 'Well-Baked Body': 'Fire', 'Water Absorb': 'Water', 'Storm Drain': 'Water',
          'Dry Skin': 'Water', 'Volt Absorb': 'Electric', 'Lightning Rod': 'Electric', 'Motor Drive': 'Electric', 'Sap Sipper': 'Grass'}
def on_hit(ability, mv, crit):
    """stat changes an ability makes when its Pokemon is hit by a damaging move"""
    t = mv.get('type'); cat = mv.get('category')
    return {'Stamina': {'def': 1}, 'Justified': {'atk': 1} if t == 'Dark' else None, 'Thermal Exchange': {'atk': 1} if t == 'Fire' else None,
            'Steam Engine': {'spe': 6} if t in ('Fire', 'Water') else None, 'Water Compaction': {'def': 2} if t == 'Water' else None,
            'Rattled': {'spe': 1} if t in ('Bug', 'Dark', 'Ghost') else None, 'Weak Armor': {'def': -1, 'spe': 2} if cat == 'Physical' else None,
            'Anger Point': {'atk': 12} if crit else None}.get(ability)
def effectiveness(mtype, types):
    """the type chart: 0 immune, else the multiplier"""
    x = 1.0
    for t in types:
        c = E['types'].get(t, {}).get(mtype, 0)
        x *= {0: 1, 1: 2, 2: 0.5, 3: 0}[c]
    return x
def derive(log):
    """the log with its stat and field messages replaced by the rules' version of them"""
    L = log.split('\n'); sheets = R.parse(log)['sheets']
    out = []; active = {}; abil = {}; item = {}; used = set(); field = {}; prot = set(); fresh = set(); charging = {}; last_move = {}; batch = []
    stage = collections.defaultdict(lambda: dict.fromkeys(STATS, 0))                    # the stat stages as the rules have them, for caps and White Herb
    megas = {}                                                                            # (side, species) -> the Mega's ability: it stays Mega after switching out
    nick = {}
    canon = lambda kind, x: E[kind].get(toid(x), {}).get('name', x) if x else ''        # "Goodas Gold" (a team sheet drops the spaces) -> Good as Gold
    def sp_of(ident): return active.get(ident[:3])
    def ab(pos): return abil.get(pos, '')
    def foes(pos): return [p for p in active if p[:2] != pos[:2]]
    def emit(*lines): out.extend(lines)
    def ident(pos): return f"{pos}: {nick.get(pos, active[pos])}"                         # as the log names it
    def boost(pos, ch, src=None, cause=''):
        """stat changes to the Pokemon at pos; src: the foe that caused them (for abilities that block or answer drops)"""
        if pos not in active or not ch: return
        drops = {k: v for k, v in ch.items() if v < 0}
        if src and src[:2] != pos[:2] and drops:
            if ab(pos) in NO_DROPS or item.get(pos) == 'Clear Amulet': ch = {k: v for k, v in ch.items() if v > 0}
            elif ab(pos) == 'Mirror Armor': boost(src, drops); ch = {k: v for k, v in ch.items() if v > 0}
        for k, v in ch.items():
            if v and k in stage[pos]:
                stage[pos][k] = max(-6, min(6, stage[pos][k] + v))
                emit(f"|{'-boost' if v > 0 else '-unboost'}|{ident(pos)}|{k}|{abs(v)}" + (f'|[from] {cause}' if cause else ''))
        if src and src[:2] != pos[:2] and any(v < 0 for v in ch.values()):
            if ab(pos) == 'Defiant': boost(pos, {'atk': 2})
            if ab(pos) == 'Competitive': boost(pos, {'spa': 2})
        low = [k for k, v in stage[pos].items() if v < 0]
        if low and item.get(pos) == 'White Herb':                                # it puts lowered stats back to 0, once
            for k in low: stage[pos][k] = 0; emit(f'|-setboost|{ident(pos)}|{k}|0|[from] item: White Herb')
            emit(f'|-enditem|{ident(pos)}|White Herb'); used.add((pos, toid(active[pos]))); item[pos] = ''
    def set_field(kind, what, setter):
        if kind == 'weather':
            if field.get('weather', [None])[0] == what: return
            field['weather'] = [what, 8 if item.get(setter) == ROCK.get(what) else 5]
            emit(f"|-weather|{what}|[of] {ident(setter)}" if setter in active else f'|-weather|{what}')
        else:
            if field.get('terrain', [None])[0] == what: return
            field['terrain'] = [what, 8 if item.get(setter) == 'Terrain Extender' else 5]
            emit(f"|-fieldstart|move: {what} Terrain|[of] {ident(setter)}" if setter in active else f'|-fieldstart|move: {what} Terrain')
    def entry(pos):
        """abilities that act when a Pokemon comes in (or Mega Evolves)"""
        a = ab(pos)
        if a == 'Intimidate':
            for f in foes(pos):
                fa = ab(f)
                if fa in NO_INTIMIDATE or item.get(f) == 'Clear Amulet': continue
                if fa == 'Guard Dog': boost(f, {'atk': 1}); continue
                if fa == 'Mirror Armor': boost(pos, {'atk': -1}); continue
                boost(f, {'atk': -1}, src=pos, cause='ability: Intimidate')
                if fa == 'Rattled': boost(f, {'spe': 1})
        if a in WEATHER_AB: set_field('weather', WEATHER_AB[a], pos)
        if a in TERRAIN_AB: set_field('terrain', TERRAIN_AB[a], pos)
    def flush_batch():
        for pos in batch: entry(pos)
        batch.clear()
    def set_mon(pos, species):
        st = sheets.get(pos[:2], {}).get(toid(species)) or next((v for k, v in sheets.get(pos[:2], {}).items() if toid(species).startswith(k)), {})
        active[pos] = species.split(',')[0]; abil[pos] = megas.get((pos[:2], toid(species.split(',')[0])), canon('abilities', st.get('ability', '')))
        item[pos] = canon('items', st.get('item', ''))
        if (pos, toid(species)) in used: item[pos] = ''
    # the facts of each move: the lines after it until the next action
    blocks = {}
    cur = None
    for i, l in enumerate(L):
        p = l.split('|')
        if len(p) > 1 and p[1] in ('move', 'switch', 'upkeep', 'turn', 'drag'): cur = i if p[1] == 'move' else None
        elif cur is not None: blocks.setdefault(cur, []).append(p)
    for i, l in enumerate(L):
        p = l.split('|'); k = p[1] if len(p) > 1 else ''
        if k != 'switch' and k != 'drag' and batch: flush_batch()
        if k in MESSAGE_LINES: continue
        out.append(l)
        if k == 'turn': prot.clear(); fresh.clear()
        elif k in ('switch', 'drag'):
            pos = p[2][:3]; set_mon(pos, p[3]); nick[pos] = p[2].split(': ', 1)[1]; fresh.add(pos); batch.append(pos); charging.pop(pos, None); stage.pop(pos, None)
        elif k == 'detailschange' and 'Mega' in (p[3] if len(p) > 3 else ''):
            pos = p[2][:3]; mg = E['species'].get(toid(p[3].split(',')[0]), {})
            if mg.get('abilities'):
                abil[pos] = mg['abilities'].get('0', abil.get(pos, '')); megas[(pos[:2], toid(active.get(pos, '')))] = abil[pos]; entry(pos)
        elif k == 'faint': active.pop(p[2][:3], None); stage.pop(p[2][:3], None)
        elif k == '-singleturn' and 'Protect' in l: prot.add(p[2][:3])
        elif k == '-enditem': used.add((p[2][:3], toid(active.get(p[2][:3], '')))); item[p[2][:3]] = ''
        elif k == 'upkeep':
            for pos in list(active):
                if ab(pos) == 'Speed Boost' and pos not in fresh: boost(pos, {'spe': 1})
            if 'tr' in field:
                field['tr'] -= 1
                if field['tr'] <= 0: del field['tr']
            for kind in ('weather', 'terrain'):
                if kind in field:
                    field[kind][1] -= 1
                    if field[kind][1] <= 0:
                        emit('|-weather|none' if kind == 'weather' else f'|-fieldend|move: {field[kind][0]} Terrain'); del field[kind]
        elif k == 'move':
            pos = p[2][:3]; mid = toid(p[3]); mv = E['moves'].get(mid, {}); fx = blocks.get(i, [])
            if pos not in active: continue
            facts = collections.defaultdict(set); hits = {}
            for q in fx:
                if len(q) > 2 and q[1] in ('-immune', '-miss', '-supereffective', '-crit', '-singleturn', '-fail'):
                    facts[q[1]].add((q[3] if q[1] == '-miss' and len(q) > 3 else q[2])[:3])
                if len(q) > 3 and q[1] == '-hitcount': hits[q[2][:3]] = int(q[3])
                if len(q) > 2 and q[1] == '-singleturn' and 'Protect' in '|'.join(q): prot.add(q[2][:3])
            tgt = mv.get('target', ''); tpos = p[4][:3] if len(p) > 4 and p[4] else None
            if tgt in ('allAdjacentFoes',): T = foes(pos)
            elif tgt == 'allAdjacent': T = [x for x in active if x != pos]
            elif tgt in ('normal', 'any', 'adjacentFoe', 'adjacentAlly', 'adjacentAllyOrSelf', 'randomNormal'): T = [tpos] if tpos in active else []
            else: T = []
            mtype = mv.get('type')
            def lands(t):
                if t in prot and mid not in ('feint',) or t in facts['-immune'] or t in facts['-miss']: return False
                if mv.get('category') != 'Status' and effectiveness(mtype, E['species'].get(toid(active[t]), {}).get('types', [])) == 0: return False
                if ABSORB.get(ab(t)) == mtype and t[:2] != pos[:2]: return False
                if mv.get('category') == 'Status' and t[:2] != pos[:2] and ab(t) == 'Good as Gold': return False
                return True
            hit = [t for t in T if lands(t)]
            if pos in facts['-fail']: continue
            # the user's own stat changes
            if mid in CHARGE:
                instant = CHARGE[mid] and field.get('weather', [None])[0] == CHARGE[mid]
                if charging.pop(pos, None) != mid:                               # the charge turn (or the whole move, in its weather)
                    boost(pos, {'spa': 1})
                    if not instant: charging[pos] = mid
            if mv.get('category') == 'Status' and tgt == 'self' and mv.get('boosts'): boost(pos, mv['boosts'])
            if (mv.get('self') or {}).get('boosts') and (hit or not T): boost(pos, mv['self']['boosts'])
            for sec in mv.get('secondaries') or []:
                if sec.get('chance') == 100 and (sec.get('self') or {}).get('boosts') and hit and ab(pos) != 'Sheer Force': boost(pos, sec['self']['boosts'])
            # the targets'
            for t in hit:
                if t not in active: continue
                if t[:2] != pos[:2] and mv.get('category') == 'Status' and ab(t) == 'Magic Bounce':
                    if mv.get('boosts') or mid in TARGET_DROPS: boost(pos, mv.get('boosts') or TARGET_DROPS[mid], src=t)
                    continue
                if mv.get('category') == 'Status' and tgt != 'self' and (mv.get('boosts') or mid in TARGET_DROPS):
                    boost(t, mv.get('boosts') or TARGET_DROPS[mid], src=pos)
                if mv.get('category') != 'Status':
                    if ab(pos) != 'Sheer Force' and ab(t) != 'Shield Dust' and item.get(t) != 'Covert Cloak':
                        for sec in mv.get('secondaries') or []:
                            if sec.get('chance') == 100 and sec.get('boosts'): boost(t, sec['boosts'], src=pos)
                    n = hits.get(t) or (2 if ab(pos) == 'Parental Bond' else 1)
                    for _ in range(n):
                        ch = on_hit(ab(t), mv, t in facts['-crit'])
                        if ch: boost(t, ch, cause=f'ability: {ab(t)}')
                    if t in facts['-supereffective'] and item.get(t) == 'Weakness Policy':
                        boost(t, {'atk': 2, 'spa': 2}); emit(f'|-enditem|{ident(t)}|Weakness Policy'); used.add((t, toid(active[t]))); item[t] = ''
                    if ab(t) == 'Seed Sower': set_field('terrain', 'Grassy', t)
            # field moves
            if mid in WEATHER_MOVE: set_field('weather', WEATHER_MOVE[mid], pos)
            if mid in TERRAIN_MOVE: set_field('terrain', TERRAIN_MOVE[mid], pos)
            if mid == 'trickroom':
                if field.pop('tr', None): emit('|-fieldend|move: Trick Room')
                else: emit('|-fieldstart|move: Trick Room'); field['tr'] = 5
            if mid == 'tailwind': emit(f'|-sidestart|{pos[:2]}: Player|move: Tailwind')
            if mid in SCREENS and not (mid == 'auroraveil' and field.get('weather', [None])[0] != 'Snowscape'): emit(f'|-sidestart|{pos[:2]}: Player|{SCREENS[mid]}')
            if mid in ('haze',): emit('|-clearallboost')
            if mid == 'clearsmog':
                for t in hit: emit(f'|-clearboost|{ident(t)}')
            last_move[pos] = mid
    if batch: flush_batch()
    return '\n'.join(out)
def snapshot(step):
    """what the two versions are compared on: the active Pokemon's stat stages, and the field"""
    s = step['state']; out = {}
    for sd in ('p1', 'p2'):
        for m in s[sd]['mons']:
            if m.get('pos') and not m['f']:
                for k in STATS: out[('boost', sd, m['pos'], m['n'], k)] = m['b'].get(k, 0)
        out[('tailwind', sd)] = bool(s[sd]['tailwind'])
        for scr in ('Reflect', 'Light Screen', 'Aurora Veil'): out[('screen', sd, scr)] = bool(s[sd]['screens'].get(scr))
    f = s['field']; out[('weather',)] = f['weather'] or ''; out[('terrain',)] = f['terrain'] or ''; out[('tr',)] = bool(f['tr'])
    return out, s
def fix_lines(key, rstate):
    """log lines that set this part of the state to the rules' version"""
    if key[0] == 'boost':
        _, sd, pos, n, k = key; m = next(m for m in rstate[sd]['mons'] if m.get('pos') == pos and not m['f'])
        return [f"|-fix|boost|{sd}{pos}: {m['n']}|{k}|{m['b'].get(k, 0)}"]
    f = rstate['field']
    if key[0] == 'weather': return [f"|-fix|weather|{next((w for w, n in R.WEATHER.items() if n == f['weather']), f['weather']) or 'none'}|{f['wturns']}"]
    if key[0] == 'terrain': return [f"|-fix|terrain|{f['terrain'] or 'none'}|{f['tturns']}"]
    if key[0] == 'tr': return [f"|-fix|tr|{f['tr']}"]
    if key[0] == 'tailwind': return [f"|-fix|tailwind|{key[1]}|{rstate[key[1]]['tailwind']}"]
    if key[0] == 'screen': return [f"|-fix|screen|{key[1]}|{key[2]}|{rstate[key[1]]['screens'].get(key[2], 0)}"]
    return []
def describe(key, a, b):
    who = lambda sd: 'Player ' + sd[1]
    if key[0] == 'boost': return f"{key[3]}'s {STATNAME[key[4]]}", (f'{a:+d}' if a else '0'), (f'{b:+d}' if b else '0')
    if key[0] == 'weather': return 'Weather', a or 'none', b or 'none'
    if key[0] == 'terrain': return 'Terrain', (a + ' Terrain') if a else 'none', (b + ' Terrain') if b else 'none'
    if key[0] == 'tr': return 'Trick Room', 'up' if a else 'not up', 'up' if b else 'not up'
    if key[0] == 'tailwind': return f'Tailwind for {who(key[1])}', 'up' if a else 'not up', 'up' if b else 'not up'
    if key[0] == 'screen': return f'{key[2]} for {who(key[1])}', 'up' if a else 'not up', 'up' if b else 'not up'
def compare(log):
    """the turns where the messages' and the rules' versions disagree, each disagreement shown at the turn it first appears"""
    gm = {s['turn']: s for s in R.parse(log)['steps'] if s['turn'] >= 1}; gr = {s['turn']: s for s in R.parse(derive(log))['steps'] if s['turn'] >= 1}
    out = {}; prev = {}
    for t in sorted(gm):
        if t not in gr: continue
        (a, _), (b, rs) = snapshot(gm[t]), snapshot(gr[t]); now = {}
        for key in set(a) | set(b):
            if key[0] == 'boost' and (key not in a or key not in b): continue      # a Pokemon the two versions place differently: not a stat question
            if a.get(key) != b.get(key):
                now[key] = (b.get(key) - a.get(key)) if key[0] == 'boost' else (a.get(key), b.get(key))   # a stat: the gap, so a carried-over miss is not flagged again
                if prev.get(key) != now[key]:
                    what, va, vb = describe(key, a.get(key), b.get(key))
                    out.setdefault(t, []).append({'key': '|'.join(map(str, key)), 'what': what, 'messages': va, 'rules': vb, 'fix': fix_lines(key, rs)})
        prev = now
    return out
if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    for t, cs in sorted(compare(open(sys.argv[1]).read()).items()):
        for c in cs: print(f"turn {t}: {c['what']}: messages {c['messages']}, rules {c['rules']}")
