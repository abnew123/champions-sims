"""Replay log -> the position at the start of every turn and what happened in each turn, for the eval bar page.
Nothing with a name leaves this module: players are 'p1' / 'p2' and every Pokemon is called by its species (nicknames are dropped).
parse(log) returns {'steps': [...], 'winner': 'p1'|'p2'|None, 'forfeit': bool, 'perish': bool, 'rating': mean rating or None, 'sheets': team
sheets, 'odd': mechanics the engine rebuild does not handle (Illusion, Transform)}.
A step is one turn: {'turn': t, 'state': position at the start of turn t, 'events': what happened in turn t, 'acts': what each slot chose
({'p1a': {'move', 'target' slot or '', 'mega', 'unsure' (the target may have been redirected)} | {'switch': species}}; a slot that could not
act, e.g. flinched, is missing)}; step 0 is the leads.
A text is a list of segments: a plain string, or [side, name] for a Pokemon (so the page can colour it by side).
usage: python3 replay.py <log>     (prints the game as text, for checking)"""
import re, sys, json
toid = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
PROTECT = {'Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Baneful Bunker', 'Silk Trap', 'Burning Bulwark', 'Obstruct'}
STAT = {'atk': 'Attack', 'def': 'Defense', 'spa': 'Sp. Atk', 'spd': 'Sp. Def', 'spe': 'Speed', 'accuracy': 'accuracy', 'evasion': 'evasion'}
STATUS = {'slp': 'fell asleep', 'brn': 'was burned', 'par': 'was paralysed', 'psn': 'was poisoned', 'tox': 'was badly poisoned', 'frz': 'was frozen'}
WEATHER = {'RainDance': 'Rain', 'SunnyDay': 'Sun', 'Sandstorm': 'Sandstorm', 'Snowscape': 'Snow', 'Snow': 'Snow', 'Hail': 'Hail',
           'DesolateLand': 'Harsh sun', 'PrimordialSea': 'Heavy rain', 'DeltaStream': 'Strong winds'}
WROCK = {'RainDance': 'damprock', 'SunnyDay': 'heatrock', 'Sandstorm': 'smoothrock', 'Snowscape': 'icyrock', 'Snow': 'icyrock'}
SCREENS = ('Reflect', 'Light Screen', 'Aurora Veil')
BINDING = {'Bind', 'Wrap', 'Fire Spin', 'Whirlpool', 'Sand Tomb', 'Clamp', 'Infestation', 'Magma Storm', 'Snap Trap', 'Thunder Cage'}
BATON_PASS = False                                                        # the eval bar's programs set it (live.py, reach.py); the bot's do not yet
MEGA_ABIL = False                                                         # Mega Evolution ends an ability gained in battle (Trace's); the eval bar's programs set it, the bot's not yet
PASSED = {'Substitute', 'confusion', 'Leech Seed', 'Heal Block', 'Focus Energy', 'Curse', 'Aqua Ring', 'Ingrain', 'Magnet Rise', 'Power Trick', 'Gastro Acid',
          'Embargo', 'Telekinesis', 'Laser Focus'}                       # the volatiles Baton Pass hands on (Showdown's noCopy is false)
CANT = {'flinch': 'flinched', 'slp': 'is asleep', 'par': 'is fully paralysed', 'frz': 'is frozen solid', 'recharge': 'must recharge',
        'Focus Punch': 'lost its focus', 'move: Taunt': "can't use the move (Taunt)", 'Disable': "can't use the move (Disable)",
        'move: Throat Chop': "can't use the move (Throat Chop)", 'move: Heal Block': "can't use the move (Heal Block)"}
clean = lambda s: re.sub(r'^(move|ability|item): ', '', s)
def camel(s):
    """'SitrusBerry' (team sheets drop the spaces) -> 'Sitrus Berry'"""
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', s)
def disp(forme):
    """'Charizard-Mega-Y' -> 'Mega Charizard Y'"""
    if '-Mega' in forme:
        base, _, suf = forme.partition('-Mega'); return 'Mega ' + base + (' ' + suf.strip('-') if suf.strip('-') else '')
    return forme
def parse_sheet(s):
    """team sheet line -> {species id: {'item', 'ability', 'moves', 'nature'}} with display names"""
    out = {}
    for blob in s.split(']'):
        f = blob.split('|')
        if len(f) < 6: continue
        out[toid(f[1] or f[0])] = {'species': f[1] or f[0], 'item': camel(f[2]), 'ability': camel(f[3]), 'moves': [camel(m) for m in f[4].split(',') if m], 'nature': f[5]}
    return out
class Mon:
    def __init__(s, side, species, sheet):
        s.side = side; s.species = species; s.forme = species; s.temp = False; s.hp = 100; s.status = ''; s.fainted = False; s.boosts = {}
        s.set = sheet.get(toid(species)) or sheet.get(toid(species.split('-')[0])) or {}
        s.item = s.set.get('item', ''); s.item_gone = False; s.vol = set()
        # for rebuilding the position in the engine: has it used a move action since coming in (Fake Out), did it Protect last turn,
        # the move a Choice item locks it into, turns already slept, has it Mega Evolved; volturn: for each volatile, [the turn it started,
        # what the Pokemon was doing then: 'waits' (its move that turn still to come), 'moving' (its own move was running: Cursed Body),
        # 'moved' (on the field since the turn started, its action done), 'new' (it came in that turn)], for positions.js's countdowns
        s.moved = False; s.stall = False; s.prot = False; s.lock = ''; s.slept = 0; s.mega = False; s.last = ''; s.volarg = {}; s.volturn = {}
        s.unburden = False; s.perish = 0                                  # its item gone since it came in (Unburden); Perish Song's count
        s.abil = ''                                                         # an ability it gained in battle (Trace, Skill Swap, Role Play...)
        s.toxn = 0; s.ptrap = None                                          # Toxic's ticks since it came in; a binding move on it [move, ticks, user]
        s.types = None; s.tadd = ''; s.protean = False                      # types changed in battle (Soak, Protean, Double Shock), a type added, Protean / Libero used
        s.syrup = False                                                     # its Supersweet Syrup has activated: once a battle, kept through switches
    def leave(s):
        s.boosts = {}; s.vol = set(); s.moved = False; s.stall = False; s.prot = False; s.lock = ''; s.last = ''; s.volarg = {}; s.volturn = {}
        s.unburden = False; s.perish = 0; s.abil = ''; s.toxn = 0; s.ptrap = None; s.types = None; s.tadd = ''; s.protean = False
        if s.temp: s.forme = s.species; s.temp = False                  # a form taken in battle (Aegislash's Blade) ends on switching out
    def ref(s): return [s.side, disp(s.forme)]
def hpval(tok):
    tok = tok.split()[0] if tok else ''
    if tok == '0' or 'fnt' in tok: return 0
    m = re.match(r'(\d+)/(\d+)', tok)
    return max(1, round(100 * int(m.group(1)) / int(m.group(2)))) if m else None
def parse(log):
    names = {}; sheets = {'p1': {}, 'p2': {}}; mons = {'p1': {}, 'p2': {}}; order = {'p1': [], 'p2': []}; active = {}; ratings = {}
    field = {'weather': '', 'wturns': 0, 'terrain': '', 'tturns': 0, 'tr': 0}
    sidec = {s: {'tailwind': 0, 'screens': {}, 'hazards': []} for s in ('p1', 'p2')}
    steps = []; events = []; cur = [None]; pend = {}; turn = 0; phase = 'lead'; winner = None; forfeit = False; perish = False; last_user = [None]
    acts = {}; start_active = {}; moved_yet = [False]; mega_now = set(); redirect = set(); odd = set(); last_move = [None]
    onstart = set(); acted = set()                                           # this turn: the Pokemon on the field when it started, those that have acted
    def mon(ident):
        nick = ident.split(': ', 1)[1] if ': ' in ident else ident
        return mons[ident[:2]].get(nick)
    def tags(p): return {m.group(1): m.group(2).strip() for x in p for m in [re.match(r'\[(\w+)\]\s?(.*)', x)] if m}
    def ev(side, head): cur[0] = {'side': side, 'head': head, 'notes': []}; events.append(cur[0]); pend.clear(); return cur[0]
    def note(segs):
        if cur[0] is None: ev(None, ['End of turn'] if phase == 'residual' else ['Before the turn'] if phase in ('lead', 'between') else ['Effects'])
        cur[0]['notes'].append(segs)
    def why(t):
        f = t.get('from', '')
        if not f: return ''
        f = clean(f); f = {'brn': 'burn', 'psn': 'poison', 'tox': 'poison', 'Recoil': 'recoil', 'recoil': 'recoil', 'confusion': 'confusion'}.get(f, f)
        return f' ({f})'
    def snapshot():
        S = {}
        for sd in ('p1', 'p2'):
            slot = {nick: pos[2] for pos, nick in active.items() if pos[:2] == sd}
            S[sd] = {'mons': [{'n': disp(m.forme), 'hp': m.hp, 'st': m.status, 'f': m.fainted, 'b': {k: v for k, v in m.boosts.items() if v},
                               'item': m.item, 'gone': m.item_gone, 'slot': '' if m.fainted else slot.get(nick, ''), 'seen': True,
                               'sp': m.species, 'forme': '' if m.mega or m.forme == m.species else m.forme, 'pos': slot.get(nick, ''), 'mega': m.mega, 'moved': m.moved, 'stall': m.stall, 'lock': m.lock, 'slept': m.slept, 'vol': sorted(m.vol), 'last': m.last, 'volarg': dict(m.volarg),
                               'volturn': {v: list(x) for v, x in m.volturn.items() if v in m.vol}, 'unb': m.unburden, 'perish': m.perish, 'abil': m.abil,
                               'toxn': m.toxn, 'ptrap': list(m.ptrap) if m.ptrap else None, 'types': m.types, 'tadd': m.tadd, 'protean': m.protean, 'syrup': m.syrup}
                              for nick in order[sd] for m in [mons[sd][nick]]],
                     'tailwind': sidec[sd]['tailwind'], 'screens': {k: v for k, v in sidec[sd]['screens'].items() if v}, 'hazards': list(sidec[sd]['hazards'])}
        S['perish'] = perish
        S['field'] = {'weather': WEATHER.get(field['weather'], field['weather']), 'wturns': field['wturns'], 'terrain': field['terrain'].replace(' Terrain', ''),
                      'tturns': field['tturns'], 'tr': field['tr']}
        return S
    def tick():
        """end of turn: durations count down"""
        for k in ('wturns', 'tturns', 'tr'): field[k] = max(0, field[k] - 1)
        for sd in sidec:
            sidec[sd]['tailwind'] = max(0, sidec[sd]['tailwind'] - 1)
            for w in sidec[sd]['screens']: sidec[sd]['screens'][w] = max(0, sidec[sd]['screens'][w] - 1)
    L = log.split('\n')
    for li, l in enumerate(L):
        p = l.split('|')
        if len(p) < 2: continue
        k = p[1]; t = tags(p[2:])
        if k == '':
            # an empty line starts the end-of-turn effects, unless it only opens the next chunk of the log (then a '|t:|' line follows)
            if phase == 'actions' and not (li + 1 < len(L) and L[li + 1].startswith('|t:|')): phase = 'residual'; cur[0] = None
        elif k == 'player' and len(p) > 3 and p[3]:
            names[p[2]] = p[3]
            if len(p) > 5 and p[5].strip().isdigit(): ratings[p[2]] = int(p[5])
        elif k == 'showteam': sheets[p[2]] = parse_sheet('|'.join(p[3:]))
        elif k in ('switch', 'drag', 'replace'):
            pos = p[2][:3]; sd = pos[:2]; nick = p[2].split(': ', 1)[1]; species = p[3].split(',')[0]
            old = mons[sd].get(active.get(pos))
            # Baton Pass hands on the stat stages and the effects Showdown copies (copyVolatileFrom); Shed Tail only its Substitute
            via = clean(t.get('from', '')) if k == 'switch' else ''
            passed = None
            if BATON_PASS and old and via in ('Baton Pass', 'Shed Tail'):
                keep = PASSED if via == 'Baton Pass' else {'Substitute'}
                passed = (dict(old.boosts) if via == 'Baton Pass' else {}, {v for v in old.vol if v in keep},
                          {v: x for v, x in old.volturn.items() if v in keep}, {v: x for v, x in old.volarg.items() if v in keep}, old.perish if via == 'Baton Pass' else 0)
            if old and k != 'replace': old.leave()
            if k == 'replace': odd.add('Illusion')
            if k == 'switch' and phase == 'actions' and not moved_yet[0] and pos not in acts and old is not None and not old.fainted:
                acts[pos] = {'switch': species}                          # a switch before anything has moved is the player's choice
            if nick not in mons[sd]: mons[sd][nick] = Mon(sd, species, sheets[sd]); order[sd].append(nick)
            m = mons[sd][nick]; active[pos] = nick
            if passed:
                m.boosts, m.vol, m.volturn, m.volarg, m.perish = passed[0], set(passed[1]), dict(passed[2]), dict(passed[3]), passed[4]
            if k != 'replace': onstart.discard(id(m))
            if len(p) > 4:
                v = hpval(p[4]); m.hp = v if v is not None else m.hp; st = p[4].split(); m.status = st[1] if len(st) > 1 and st[1] != 'fnt' else m.status
            if k == 'replace': ev(sd, [m.ref(), "'s Illusion ended"])
            elif k == 'drag': ev(sd, [m.ref(), ' was dragged in'])
            elif phase == 'lead': ev(sd, ['Lead: ', m.ref()])
            elif old is None or old.fainted or old is m: ev(sd, ['Sent in ', m.ref()])
            else: ev(sd, [old.ref(), ' switched out for ', m.ref()])
        elif k == 'swap':
            m = mon(p[2]); pos = p[2][:3]; other = pos[:2] + ('b' if pos[2] == 'a' else 'a')
            active[pos], active[other] = active.get(other), active.get(pos)
            active.update({q: n for q, n in list(active.items()) if n is not None})
            for q in (pos, other):
                if active.get(q) is None: active.pop(q, None)
            if m: note([m.ref(), ' changed places with its partner'])
        elif k == 'detailschange' or k == '-formechange':
            m = mon(p[2])
            if m:
                m.forme = p[3].split(',')[0]
                if k == 'detailschange' and 'Mega' in m.forme:
                    m.mega = True; mega_now.add(id(m)); ev(m.side, [[m.side, disp(m.species)], ' Mega Evolved'])
                    # its Mega ability replaces what Trace copied (kept, positions.js's abilDue gave Mega Gardevoir the traced Intimidate for
                    # Pixilate: its Hyper Voice came out Normal-type, a median 1.7 of predicted in 131 hits; mega_check.py, 2026-10-12)
                    if MEGA_ABIL: m.abil = ''
                    m.types = None; m.tadd = ''; m.protean = False             # a new species: its own types (setSpecies), a fresh ability state
                elif k == '-formechange': m.temp = m.forme != m.species
        elif k == 'move':
            m = mon(p[2]); tg = mon(p[4]) if len(p) > 4 and p[4] else None; last_user[0] = m; last_move[0] = p[3]
            if not m: continue
            pos = p[2][:3]; own = 'from' not in t or clean(t['from']) == 'lockedmove'
            if own and 'from' in t and steps and tg is not None:                  # a charging move fires (Electro Shot, Solar Beam): its target
                a0 = steps[-1]['acts'].get(pos)                                  # was chosen last turn, when the log showed none
                if a0 and a0.get('move') == p[3] and not a0.get('target') and 'spread' not in t: a0['target'] = p[4][:3]
            if own:
                if pos not in acts and active.get(pos) == start_active.get(pos):
                    tpos = p[4][:3] if tg is not None and 'spread' not in t else ''
                    acts[pos] = {'move': p[3], 'target': tpos, 'mega': id(m) in mega_now, 'unsure': bool(tpos) and tpos[:2] in redirect}
                    if tg is not None and 'spread' in t: acts[pos]['spreadTarget'] = p[4][:3]   # the one it aimed at (Expanding Force in Psychic Terrain)
                moved_yet[0] = True; m.moved = True; m.last = p[3]; m.vol.discard('charging'); acted.add(id(m))
                if toid(m.item) in ('choicescarf', 'choiceband', 'choicespecs') and not m.item_gone: m.lock = p[3]
            head = [m.ref(), ' used ', p[3]]
            if tg is not None and tg is not m and 'spread' not in t: head += [' on ', tg.ref()]
            e = ev(m.side, head)
            if 'from' in t and clean(t['from']) not in ('lockedmove',): e['head'].append(f" ({clean(t['from'])})")
            if 'miss' in t: pass
            if p[3] == 'Perish Song': perish = True
        elif k == 'cant' and p[3].startswith('ability: ') and len(p) > 4 and t.get('of'):
            # Armor Tail, Dazzling, Queenly Majesty: |cant|<holder>|ability: X|<move>|[of] <user>: the user's move, aimed at the holder, stopped
            u = mon(t['of']); h = mon(p[2]); upos = t['of'][:3]
            if u:
                a0 = acts.get(upos)                                          # Showdown logs the move first, with no target ("[still]")
                if a0 and a0.get('move') == p[4] and not a0.get('target'): a0['target'] = p[2][:3]
                elif upos not in acts and active.get(upos) == start_active.get(upos):
                    acts[upos] = {'move': p[4], 'target': p[2][:3], 'mega': id(u) in mega_now, 'unsure': False}
                e0 = events[-1] if events else None
                if e0 and e0['head'] == [u.ref(), ' used ', p[4]] and h: e0['head'] += [' on ', h.ref()]; cur[0] = e0
                else: ev(u.side, [u.ref(), ' used ', p[4]] + ([' on ', h.ref()] if h else []))
                note([u.ref(), f": stopped by {clean(p[3])}"]); moved_yet[0] = True; u.moved = True; u.last = p[4]; acted.add(id(u))
        elif k == 'cant':
            m = mon(p[2])
            if m and p[2][:3] not in acts and active.get(p[2][:3]) == start_active.get(p[2][:3]): acts[p[2][:3]] = {'none': 'cant', 'mega': id(m) in mega_now}   # it did not switch
            if m:
                ev(m.side, [m.ref(), ' ' + CANT.get(p[3], f"can't move ({clean(p[3])})")]); moved_yet[0] = True; m.moved = True; acted.add(id(m))
                if p[3] == 'slp': m.slept += 1
        elif k in ('-damage', '-heal', '-sethp'):
            m = mon(p[2]); v = hpval(p[3]) if len(p) > 3 else None
            if m and k == '-damage' and clean(t.get('from', '')) == 'psn' and m.status == 'tox': m.toxn += 1
            if m and k == '-damage' and 'partiallytrapped' in t and m.ptrap: m.ptrap[1] += 1
            if m and v is not None:
                extra = pend.pop(id(m), [])
                if m.hp != v or extra:
                    txt = f' {m.hp}% → {v}%' + why(t) + (f" ({', '.join(extra)})" if extra else '')
                    if cur[0] is None or phase == 'residual' and cur[0]['side']: cur[0] = None
                    note([m.ref(), txt])
                m.hp = v
                if k == '-heal' and v > 0 and m.fainted: m.fainted = False             # Revival Blessing brings back a fainted one in the back
                st = p[3].split(); m.status = st[1] if len(st) > 1 and st[1] != 'fnt' else m.status
        elif k == 'faint':
            m = mon(p[2])
            if m:
                pos = p[2][:3]                                                   # it fainted before acting: what it chose is not shown, but it
                if phase != 'residual' and pos not in acts and active.get(pos) == start_active.get(pos):   # did not switch, nor
                    acts[pos] = {'none': 'fainted', 'by': last_move[0], 'mega': id(m) in mega_now}   # use a move that goes before the one that knocked it out
                m.fainted = True; m.hp = 0; m.status = ''; m.boosts = {}
                last = cur[0]['notes'][-1] if cur[0] and cur[0]['notes'] else None
                if last and last[0] == m.ref() and '→' in str(last[1]): last.append(', fainted')
                else: note([m.ref(), ' fainted'])
        elif k in ('-supereffective', '-resisted', '-crit'):
            m = mon(p[2])
            if m: pend.setdefault(id(m), []).append({'-supereffective': 'super effective', '-resisted': 'resisted', '-crit': 'critical hit'}[k])
        elif k == '-immune':
            m = mon(p[2])
            if m: note([m.ref(), ' is immune' + why(t)])
        elif k == '-miss':
            m = mon(p[3]) if len(p) > 3 and p[3] else None
            note(['Missed ', m.ref()] if m else ['Missed'])
        elif k == '-fail':
            m = mon(p[2]); note([m.ref(), ': it failed'] if m else ['It failed'])
        elif k == '-block':
            m = mon(p[2])
            if m: note([m.ref(), ' was protected' + (f' ({clean(p[3])})' if len(p) > 3 else '')])
        elif k == '-activate':
            m = mon(p[2]) if p[2] else None; what = clean(p[3]) if len(p) > 3 else ''
            if m and what in BINDING and t.get('of'):                           # bound: Infestation, Whirlpool, Fire Spin... (partiallytrapped)
                u = mon(t['of']); m.ptrap = [what, 0, u.species if u else '']
            if what == 'Skill Swap' and len(p) > 5 and t.get('of'):            # the user gets the target's ability, and back
                tg = mon(t['of'])
                if m: m.abil = p[4]
                if tg: tg.abil = p[5]
            if m and what in ('Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Baneful Bunker', 'Silk Trap', 'Burning Bulwark', 'Obstruct', 'Wide Guard', 'Quick Guard'):
                note([m.ref(), f' was protected ({what})' if what != 'Protect' else ' protected itself'])
            elif m and what == 'confusion': note([m.ref(), ' is confused'])
            elif m and what and what not in ('Psychic Terrain', 'Substitute'): note([m.ref(), f': {what}'])
            elif m and what == 'Psychic Terrain': note([m.ref(), ' is shielded by Psychic Terrain'])
            elif m and what == 'Substitute': note([m.ref(), "'s Substitute took the hit"])
        elif k == '-status':
            m = mon(p[2])
            if m: m.status = p[3]; m.slept = 0; m.toxn = 0; note([m.ref(), ' ' + STATUS.get(p[3], p[3]) + why(t)])
        elif k == '-curestatus':
            m = mon(p[2])
            if m: note([m.ref(), ' woke up' if m.status == 'slp' else ' was cured']); m.status = ''
        elif k in ('-boost', '-unboost'):
            m = mon(p[2])
            if m:
                d = int(p[4]) * (1 if k == '-boost' else -1); m.boosts[p[3]] = max(-6, min(6, m.boosts.get(p[3], 0) + d))
                note([m.ref(), f" {STAT.get(p[3], p[3])} {'+' if d > 0 else '−'}{abs(d)}" + why(t)])
        elif k == '-setboost':
            m = mon(p[2])
            if m: m.boosts[p[3]] = int(p[4]); note([m.ref(), f" {STAT.get(p[3], p[3])} set to {int(p[4]):+d}" + why(t)])
        elif k in ('-clearboost', '-clearallboost', '-clearnegativeboost'):
            m = mon(p[2]) if len(p) > 2 and p[2] else None
            if k == '-clearallboost':
                for sd in mons:
                    for x in mons[sd].values(): x.boosts = {}
                note(['All stat changes were reset'])
            elif m and k == '-clearboost': m.boosts = {}; note([m.ref(), "'s stat changes were reset"])
            elif m: m.boosts = {s: v for s, v in m.boosts.items() if v > 0}; note([m.ref(), "'s lowered stats were restored" + why(t)])
        elif k in ('-copyboost', '-swapboost'):
            m = mon(p[2]); o = mon(p[3])
            if m and o:
                if k == '-copyboost': m.boosts = dict(o.boosts); note([m.ref(), ' copied ', o.ref(), "'s stat changes"])
                else: m.boosts, o.boosts = o.boosts, m.boosts; note([m.ref(), ' swapped stat changes with ', o.ref()])
        elif k == '-ability':
            m = mon(p[2])
            if m and re.search(r'\[from\] (ability: (Trace|Receiver|Power of Alchemy)|move: (Role Play|Entrainment|Doodle|Simple Beam|Worry Seed))', l): m.abil = p[3]
            if m and p[3] == 'Supersweet Syrup' and '[from]' not in l: m.syrup = True
            if m and p[3] not in ('Stamina',): note([m.ref(), f"'s {p[3]}"])
        elif k in ('-enditem', '-item'):
            m = mon(p[2])
            if m:
                if k == '-enditem':
                    m.item_gone = True; m.unburden = True
                    if toid(p[3]) == 'whiteherb' and 'eat' not in t and clean(t.get('from', '')) != 'Knock Off':   # it put lowered stats back to 0
                        m.boosts = {b: v for b, v in m.boosts.items() if v > 0}
                    note([m.ref(), f" ate its {p[3]}" if 'eat' in t else f"'s {p[3]} was knocked off" if clean(t.get('from', '')) == 'Knock Off' else f"'s {p[3]} was used up"])
                else: m.item = p[3]; m.item_gone = False; m.unburden = False; note([m.ref(), f' now holds {p[3]}' + why(t)])
        elif k in ('-start', '-end'):
            m = mon(p[2]); what = clean(p[3]) if len(p) > 3 else ''
            if not m: continue
            if k == '-end' and 'partiallytrapped' in t: m.ptrap = None
            if what.startswith('perish'):
                perish = True
                if what[-1].isdigit(): m.perish = int(what[-1])
                if what != 'perish3' or k == '-end': note([m.ref(), f" Perish count {what[-1]}"])
                elif not (cur[0] and ['Perish count 3 for every Pokémon on the field'] in cur[0]['notes']): note(['Perish count 3 for every Pokémon on the field'])
            elif what == 'typechange':
                if k == '-start' and len(p) > 4: m.types = p[4].split('/')       # Soak, Protean / Libero, Double Shock and Burn Up ('???' for a lost only type)
                if k == '-start' and re.search(r'\[from\] ability: (Protean|Libero)', l): m.protean = True   # once per switch-in
                note([m.ref(), f" became {p[4]}-type" if len(p) > 4 else ' changed type'])
            elif what == 'typeadd':
                if k == '-start' and len(p) > 4: m.tadd = p[4]                   # Forest's Curse, Trick-or-Treat
                note([m.ref(), f" gained the {p[4]} type" if len(p) > 4 else ' gained a type'])
            elif k == '-start':
                if what == 'Encore': m.volarg[what] = m.last
                if what == 'Disable' and len(p) > 4: m.volarg[what] = p[4]
                if what == 'Heal Block': m.volarg[what] = last_move[0] or ''      # Psychic Noise's lasts 2 turns, the move's 5
                if what in ('Leech Seed', 'Yawn'):                              # who put it there: its slot, on this side ('a') or the other ('f'); the
                    up = t['of'][:3] if t.get('of') else None                    # line's [of] (Yawn's), else the move's user (Leech Seed's has none)
                    if not up and last_user[0]:
                        u = last_user[0]; up = next((q for q, nk in active.items() if q[:2] == u.side and nk and mons[u.side].get(nk) is u), None)
                    if up: m.volarg[what] = ('a' if up[:2] == m.side else 'f') + up[2]
                act = phase in ('actions', 'residual')                        # else it started before the turn's actions (switch-ins)
                m.volturn[what] = [turn if act else turn + 1, 'moving' if act and last_user[0] is m and phase == 'actions' else 'new' if id(m) not in onstart
                                   else 'moved' if id(m) in acted else 'waits']
                m.vol.add(what); note([m.ref(), {'confusion': ' became confused', 'Substitute': ' put up a Substitute'}.get(what, f': {what} started')])
            else: m.vol.discard(what); m.volturn.pop(what, None); note([m.ref(), {'confusion': ' snapped out of confusion', 'Substitute': "'s Substitute broke", 'Illusion': "'s Illusion ended"}.get(what, f': {what} ended')])
        elif k == '-prepare':
            m = mon(p[2])
            if m: m.vol.add('charging')                                   # first turn of a two-turn move; '-anim' follows if it fires at once
        elif k == '-anim':
            m = mon(p[2]); pos = p[2][:3]
            if m: m.vol.discard('charging')
            if m and pos in acts and acts[pos].get('move') == p[3] and not acts[pos]['target'] and len(p) > 4 and p[4]: acts[pos]['target'] = p[4][:3]
        elif k == '-hitcount': note([f'Hit {p[3]} times'])
        elif k == '-ohko': note(['One-hit KO'])
        elif k == '-mustrecharge':
            m = mon(p[2])
            if m: note([m.ref(), ' must recharge next turn'])
        elif k == '-transform':
            m = mon(p[2]); o = mon(p[3])
            if m and o: note([m.ref(), ' transformed into ', o.ref()]); odd.add('Transform')
        elif k == '-weather':
            w = p[2]
            if 'upkeep' in t: continue
            if w == 'none': note([f"{WEATHER.get(field['weather'], 'The weather')} ended"]); field['weather'] = ''; field['wturns'] = 0
            else:
                src = mon(t['of']) if 'of' in t else last_user[0]
                field['weather'] = w; field['wturns'] = 8 if src and toid(src.item) == WROCK.get(w) and not src.item_gone else 5
                note([f"{WEATHER.get(w, w)} started" + why(t)])
        elif k == '-fieldstart':
            what = clean(p[2]); src = mon(t['of']) if 'of' in t else last_user[0]
            if what == 'Trick Room': field['tr'] = 5
            elif 'Terrain' in what: field['terrain'] = what; field['tturns'] = 8 if src and toid(src.item) == 'terrainextender' and not src.item_gone else 5
            note([f'{what} started' + why(t)])
        elif k == '-fix' and len(p) > 3:                                     # a correction the user chose (evalbar/rules.py): set it as given
            w = p[2]
            if w == 'boost':
                m = mon(p[3])
                if m: m.boosts[p[4]] = int(p[5])
            elif w == 'weather': field['weather'] = '' if p[3] == 'none' else p[3]; field['wturns'] = int(p[4])
            elif w == 'terrain': field['terrain'] = '' if p[3] == 'none' else p[3] + ' Terrain'; field['tturns'] = int(p[4])
            elif w == 'tr': field['tr'] = int(p[3])
            elif w == 'tailwind': sidec[p[3]]['tailwind'] = int(p[4])
            elif w == 'screen': sidec[p[3]]['screens'][p[4]] = int(p[5])
        elif k == '-fieldend':
            what = clean(p[2])
            if what == 'Trick Room': field['tr'] = 0
            elif 'Terrain' in what: field['terrain'] = ''; field['tturns'] = 0
            note([f'{what} ended'])
        elif k in ('-sidestart', '-sideend'):
            sd = p[2][:2]; what = clean(p[3]); who = f"Player {sd[1]}'s side"
            if k == '-sidestart':
                if what == 'Tailwind': sidec[sd]['tailwind'] = 4
                elif what in SCREENS: sidec[sd]['screens'][what] = 8 if last_user[0] and toid(last_user[0].item) == 'lightclay' and not last_user[0].item_gone else 5
                elif what not in sidec[sd]['hazards']: sidec[sd]['hazards'].append(what)
                note([f'{what} started on {who}'])
            else:
                if what == 'Tailwind': sidec[sd]['tailwind'] = 0
                elif what in SCREENS: sidec[sd]['screens'][what] = 0
                elif what in sidec[sd]['hazards']: sidec[sd]['hazards'].remove(what)
                note([f'{what} ended on {who}'])
        elif k == '-message' and len(p) > 2 and p[2].endswith(' forfeited.'):
            who = names.get('p1'), names.get('p2'); nm = p[2][:-len(' forfeited.')]
            sd = 'p1' if nm == who[0] else 'p2' if nm == who[1] else None
            forfeit = True; ev(sd, [f'Player {sd[1]} forfeited' if sd else 'A player forfeited'])
        elif k == '-singleturn':
            m = mon(p[2]); what = clean(p[3]) if len(p) > 3 else ''
            if m and what in PROTECT: m.prot = True
            if m and what in ('Follow Me', 'Rage Powder', 'Spotlight'): redirect.add(m.side)
        elif k == 'upkeep': tick(); phase = 'between'; cur[0] = None
        elif k == 'turn':
            steps.append({'turn': turn, 'state': state0 if turn else None, 'events': events, 'acts': acts})
            turn = int(p[2]); events = []; cur[0] = None; pend.clear(); phase = 'actions'
            for sd in mons:
                for m in mons[sd].values(): m.stall = m.prot; m.prot = False
            state0 = snapshot(); acts = {}; start_active = dict(active); moved_yet[0] = False; mega_now.clear(); redirect.clear()
            onstart.clear(); onstart.update(id(mons[pos[:2]][nick]) for pos, nick in active.items() if nick in mons[pos[:2]]); acted.clear()
        elif k == 'win': winner = next((s for s, n in names.items() if n == p[2]), None)
    steps.append({'turn': turn, 'state': state0 if turn else None, 'events': events, 'acts': acts})
    final = snapshot()
    # hindsight: every position lists the Pokemon the player brought, in order of appearance; those not yet sent in are 'seen': False
    for st in [s['state'] for s in steps if s['state']] + [final]:
        for sd in ('p1', 'p2'):
            for nick in order[sd][len(st[sd]['mons']):]:
                m = mons[sd][nick]; st[sd]['mons'].append({'n': disp(m.species), 'hp': 100, 'st': '', 'f': False, 'b': {}, 'item': m.set.get('item', ''), 'gone': False, 'slot': '', 'seen': False,
                                           'sp': m.species, 'forme': '', 'pos': '', 'mega': False, 'moved': False, 'stall': False, 'lock': '', 'slept': 0, 'vol': [], 'last': '', 'volarg': {}, 'volturn': {}})
    # for the caller's leak check: nicknames that are not just the species, and the usernames
    hidden = sorted({n for sd in mons for n in mons[sd] if not toid(mons[sd][n].species).startswith(toid(n))} | {n for n in names.values() if n})
    return {'steps': steps, 'final': final, 'winner': winner, 'forfeit': forfeit, 'perish': perish, 'brought': {sd: len(order[sd]) for sd in order},
            'sheets': sheets, 'odd': sorted(odd),
            'rating': sum(ratings.values()) / len(ratings) if len(ratings) == 2 else None, '_hidden': hidden}
def flat(segs): return ''.join(x if isinstance(x, str) else f'{x[0].upper()} {x[1]}' for x in segs)
if __name__ == '__main__':
    g = parse(open(sys.argv[1]).read())
    for s in g['steps']:
        print(f"--- turn {s['turn']}" + ('' if not s['state'] else '   ' + ' | '.join(' '.join(f"{m['n']}{'*' if m['slot'] else ''} {m['hp']}" for m in s['state'][sd]['mons']) for sd in ('p1', 'p2')) + f"   {s['state']['field']}"))
        for e in s['events']:
            print('  ', flat(e['head']))
            for n in e['notes']: print('       ', flat(n))
    print('winner', g['winner'], 'forfeit', g['forfeit'], 'perish', g['perish'], 'brought', g['brought'])
