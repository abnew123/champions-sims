"""Look for bad plays in the bot's saved games (2026-10-12, the user: bugs that make for terrible play, not only broken ones). Every
check is about what the bot could know when it chose: the field at the turn's start and the opponent's open team sheet (|showteam|
gives items, abilities and moves). Kinds: a single-target move into a target that sat there since the turn's start and is immune by
type or by its listed ability; a priority move into Psychic Terrain that was up at the turn's start; a single-target move pulled by a
Lightning Rod / Storm Drain that was on the field all turn; the bot's own move failing for a reason visible at the turn's start (Fake
Out after the first turn, Tailwind / weather / terrain / Trick Room already up, status into a statused target); damage the bot's spread
moves did to its own partner; turns a Mega the request offered went unused, and Mega stones never used before the holder fainted.
  .venv/bin/python3 bot/play_scan.py [kind substring to list in full]"""
import json, os, sys, re, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, 'native', 'engine_data_full.json')))
toid = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
MOVES = {toid(m['name']): m for m in D['moves'].values()}
SPEC = {toid(s['name']): s for s in D['species'].values()}
TYPES = D['types']
ABIL_IMMUNE = {'levitate': 'Ground', 'flashfire': 'Fire', 'waterabsorb': 'Water', 'stormdrain': 'Water', 'dryskin': 'Water', 'voltabsorb': 'Electric',
               'lightningrod': 'Electric', 'motordrive': 'Electric', 'sapsipper': 'Grass', 'eartheater': 'Ground', 'wellbakedbody': 'Fire'}
REDIRECT = {'lightningrod': 'Electric', 'stormdrain': 'Water'}
G = [json.loads(l) for l in open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl'))]
found = collections.defaultdict(list)
def add(kind, g, turn, what): found[kind].append((g['room'][-12:], turn, what))
def types_of(sp):
    s = SPEC.get(toid(sp)) or SPEC.get(toid(sp.split('-')[0])) or {}
    return s.get('types', [])
def immune_by_type(mtype, sp):
    return any(TYPES.get(t, {}).get(mtype) == 3 for t in types_of(sp))
def grounded(sp, abil):
    return 'Flying' not in types_of(sp) and toid(abil) != 'levitate'
def sheet(L, side):
    """species (base id) -> {item, ability, moves} from the side's |showteam| line"""
    out = {}
    for l in L:
        if l.startswith(f'|showteam|{side}|'):
            for m in l.split('|', 3)[3].split(']'):
                f = m.split('|')
                if len(f) > 5: out[toid(f[0] or f[1]).split('mega')[0]] = {'item': f[2], 'ability': f[3], 'moves': f[4].split(',')}
    return out
for g in G:
    f = os.path.join(ROOT, 'bot', 'out', g['room'] + '.log')
    if not os.path.exists(f): continue
    me = g['side']; op = 'p2' if me == 'p1' else 'p1'
    L = open(f, errors='ignore').read().split('\n')
    sh = {me: sheet(L, me), op: sheet(L, op)}
    abil = lambda side, sp: (sh[side].get(toid(sp).split('mega')[0]) or {}).get('ability', '')
    # live state: position -> species; per position, the line index of its latest switch; per mon (side, nick) -> status, turns in
    pos = {}; sw_at = {}; status = {}; first_turn = {}; turn = 0; start_i = 0
    snap = {}; field = {'tw': {me: False, op: False}, 'weather': '', 'terrain': '', 'tr': False}; field0 = dict(field)
    mega_used = False; mega_offer = {}; foe_fell = False
    megas_done = set(); stone_holders = {}
    i = 0
    while i < len(L):
        l = L[i]; p = l.split('|'); k = p[1] if len(p) > 1 else ''
        if k == 'request' and len(p) > 2:
            try: rq = json.loads(l[9:])
            except Exception: rq = None
            if rq and rq.get('active') and not rq.get('forceSwitch'):
                mega_offer = {chr(97 + j): a.get('canMegaEvo') for j, a in enumerate(rq['active'])}
                for j, a in enumerate(rq['active']):
                    if a.get('canMegaEvo') and j < len(rq['side']['pokemon']): stone_holders[rq['side']['pokemon'][j]['details'].split(',')[0]] = True
        if k == 'turn':
            # the turn that just ended: a Mega the request offered and the bot let pass
            if turn > 0:
                for ps, offered in mega_offer.items():
                    if offered and not mega_used and (me + ps) in pos and not snap.get('megaed_' + ps) and pos.get(me + ps):
                        add('a Mega the request offered went unused that turn', g, turn, pos[me + ps])
            turn = int(p[2]); start_i = i; snap = dict(pos); field0 = {**field, 'tw': dict(field['tw'])}; mega_offer = {}; foe_fell = False
            first0 = dict(first_turn)
        elif k in ('switch', 'drag', 'replace') and len(p) > 3:
            ps = p[2][:3]; sp = p[3].split(',')[0]; pos[ps] = sp; sw_at[ps] = i
            if k != 'replace': first_turn[ps] = turn + (0 if turn == 0 else 1)   # the next turn is its first for Fake Out
            if k == 'switch' and p[2].startswith(me) and turn == 0: first_turn[ps] = 1
        elif k == 'detailschange' and len(p) > 3: pos[p[2][:3]] = p[3].split(',')[0]
        elif k == '-mega' and len(p) > 2:
            if p[2].startswith(me): mega_used = True; snap['megaed_' + p[2][2]] = True; megas_done.add(p[3] if len(p) > 3 else '')
        elif k == 'faint' and len(p) > 2:
            ps = p[2][:3]
            if p[2].startswith(op): foe_fell = True
            if p[2].startswith(me) and not mega_used and stone_holders.get(snap.get(ps, pos.get(ps, '')).split('-Mega')[0]):
                add('a Mega-capable Pokemon fainted with the Mega never used (none used that game)', g, turn, pos.get(ps, ''))
        elif k in ('-status',) and len(p) > 3: status[p[2][:3] + pos.get(p[2][:3], '')] = p[3]
        elif k == '-curestatus' and len(p) > 2: status.pop(p[2][:3] + pos.get(p[2][:3], ''), None)
        elif k == '-sidestart' and 'Tailwind' in l: field['tw'][p[2][:2]] = True
        elif k == '-sideend' and 'Tailwind' in l: field['tw'][p[2][:2]] = False
        elif k == '-weather' and len(p) > 2: field['weather'] = '' if p[2] == 'none' else p[2]
        elif k == '-fieldstart' and len(p) > 2:
            if 'Trick Room' in l: field['tr'] = True
            elif 'Terrain' in l: field['terrain'] = p[2].replace('move: ', '')
        elif k == '-fieldend' and len(p) > 2:
            if 'Trick Room' in l: field['tr'] = False
            elif 'Terrain' in l: field['terrain'] = ''
        elif k == 'move' and len(p) > 3 and p[2].startswith(me):
            ps = p[2][:3]; mon = pos.get(ps, '?'); mv = MOVES.get(toid(p[3]), {}); mname = p[3]
            tgt = p[4] if len(p) > 4 else ''; tp = tgt[:3]; spread = any(x.startswith('[spread]') for x in p[5:])
            # this move's own result lines: up to the next move / switch / blank line
            j = i + 1; res = []
            while j < len(L) and L[j] and not L[j].startswith(('|move|', '|switch|', '|drag|', '|turn|', '|upkeep', '|cant|')): res.append(L[j]); j += 1
            # the target sat there since the turn began, and no foe fell before this move (a fallen target's move is retargeted)
            stayed = tp in snap and snap.get(tp) == pos.get(tp) and sw_at.get(tp, -1) < start_i and not foe_fell
            tsp = pos.get(tp, '')
            single = mv.get('target') in ('normal', 'any', 'adjacentFoe') and not spread
            if single and tp.startswith(op) and stayed and mv.get('category') in ('Physical', 'Special', 'Status'):
                mt = mv.get('type'); a = abil(op, tsp)
                if mv.get('category') != 'Status' and immune_by_type(mt, tsp) and any(r.startswith('|-immune|' + tp) for r in res):
                    add('single-target move into a type immunity on the field since the turn began', g, turn, f'{mon}: {mname} -> {tsp} (other foe {snap.get(op + ("b" if tp[2] == "a" else "a"), "none")})')
                elif mv.get('category') != 'Status' and ABIL_IMMUNE.get(toid(a)) == mt:
                    add("single-target move into the target's listed ability", g, turn, f'{mon}: {mname} -> {tsp} ({a})')
            if single and mv.get('priority', 0) > 0 and field0['terrain'] == 'Psychic Terrain' and tp.startswith(op) and stayed and grounded(tsp, abil(op, tsp)) and mv.get('category') != 'Status':
                add('priority move into Psychic Terrain that was up at the turn start', g, turn, f'{mon}: {mname} -> {tsp}')
            # redirection by an ability that was on the field all turn
            if single and tp.startswith(op):
                for q in ('a', 'b'):
                    rp = op + q; rsp = snap.get(rp)
                    if rsp and rsp == pos.get(rp) and sw_at.get(rp, -1) < start_i and REDIRECT.get(toid(abil(op, rsp))) == mv.get('type') and tsp == rsp:
                        add('single-target move pulled into a Lightning Rod / Storm Drain on the field all turn', g, turn, f'{mon}: {mname} -> {rsp} ({abil(op, rsp)})')
            fails = [] if '[notarget]' in l else [r for r in res if r.startswith('|-fail|' + p[2]) or (r.startswith('|-fail|') and '[from]' not in r and 'unboost' not in r)]
            why = None
            if mname == 'Fake Out' and first0.get(ps, 0) != turn and first_turn.get(ps, 0) != turn: why = 'Fake Out after its first turn'
            if mname == 'Tailwind' and field0['tw'][me]: why = 'Tailwind already up'
            if mname == 'Trick Room' and field0['tr']: why = 'Trick Room already up (this ends it)'
            if mname in ('Rain Dance', 'Sunny Day', 'Sandstorm', 'Snowscape') and field0['weather'] and toid(field0['weather']) == toid(mname).replace('dance', 'dance').replace('sunnyday', 'sunnyday'): why = 'that weather already up'
            if mv.get('category') == 'Status' and mv.get('status') and tp.startswith(op) and stayed and status.get(tp + tsp): why = f'{mname} into a target already {status.get(tp + tsp)}'
            if why: add("the bot's move could not work, visibly at the turn start", g, turn, f'{mon}: {mname} ({why})' + (' [failed]' if fails else ''))
            elif fails and mname not in ('Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Silk Trap', 'Baneful Bunker', 'Burning Bulwark', 'Sucker Punch', 'Wide Guard', 'Quick Guard'):
                add("the bot's move failed (other)", g, turn, f'{mon}: {mname} -> {tsp} {fails[0][:70]}')
            for r in res:   # spread damage to the bot's own partner
                q = r.split('|')
                if spread and len(q) > 3 and q[1] == '-damage' and q[2].startswith(me) and q[2][:3] != ps and '[from]' not in r:
                    add("the bot's spread move hit its own partner", g, turn, f'{mon}: {mname} -> {pos.get(q[2][:3])} now {q[3]}')
        i += 1
kinds = sys.argv[1] if len(sys.argv) > 1 else None
print(f"{len(G)} games scanned")
for kind, items in sorted(found.items(), key=lambda kv: -len(kv[1])):
    print(f"\n{kind}: {len(items)}")
    for room, t, what in (items if kinds and kinds in kind else items[:8]): print(f"   ..{room} T{t}: {what}")
