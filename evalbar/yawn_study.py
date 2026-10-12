"""After a Yawn lands, does the player switch the drowsy Pokemon out on the next turn (so it never falls asleep) or leave it in?
Human players from the cached Reg M-C Bo3 replays, and the Showdown bot (and its human opponents) from its own logs.
  python3 evalbar/yawn_study.py            writes evalbar/yawn_study.json
A Yawn counts only when the player could have switched: a healthy Pokemon in the back, not trapped (Shadow Tag, Arena Trap, Magnet
Pull, Mean Look and the like), and the game went on to the next turn. Outcomes on that turn: 'switched' (a switch chosen at the start
of the turn), 'pivot' (its own U-turn, Parting Shot and the like), 'forced' (Eject Button, Roar, Emergency Exit...), 'slept', 'fainted'
(before the end of the turn), 'blocked' (stayed in but did not fall asleep: Misty Terrain, Safeguard, a cured Yawn...)."""
import os, re, sys, json, glob, collections
import common as C
toid = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
E = json.load(open(os.path.join(C.MAIN, 'native', 'engine_data_full.json')))
PIVOT = {'uturn', 'voltswitch', 'flipturn', 'partingshot', 'teleport', 'batonpass', 'shedtail', 'chillyreception'}
PARTIAL = {'bind', 'wrap', 'firespin', 'whirlpool', 'sandtomb', 'magmastorm', 'infestation', 'snaptrap', 'thundercage', 'jawlock'}
def types(sp):
    d = E['species'].get(toid(sp)) or E['species'].get(toid(sp.split('-')[0])) or {}
    return set(d.get('types') or [])
def ability(sheet, sp):
    """the ability of species sp: a Mega's own, else the team sheet's"""
    d = E['species'].get(toid(sp)) or {}
    if '-Mega' in sp: return toid((d.get('abilities') or {}).get('0'))
    return sheet.get(toid(sp)) or sheet.get(toid(sp.split('-')[0])) or ''
def trapped(sp, own_ab, foes, vol):
    """is a Pokemon of species sp trapped by the foes on the field [(species, ability)] or a trapping effect on it"""
    if vol: return True
    ty = types(sp)
    if 'Ghost' in ty: return False
    for fsp, ab in foes:
        if ab == 'shadowtag' and own_ab != 'shadowtag': return True
        if ab == 'arenatrap' and 'Flying' not in ty and own_ab != 'levitate': return True
        if ab == 'magnetpull' and 'Steel' in ty: return True
    return False
def study(log, bot=None):
    """[(side, kind, outcome, rating, turn, species)] for every Yawn that landed: turn is the one after it (the decision), species the
    drowsy Pokemon's; kind 'bot' for the bot's own Pokemon, else 'human'"""
    L = log.split('\n'); size = {'p1': 4, 'p2': 4}; sheet = {'p1': {}, 'p2': {}}; rating = {}
    for l in L:
        p = l.split('|')
        if len(p) > 3 and p[1] == 'teamsize': size[p[2]] = int(p[3])
        if len(p) > 3 and p[1] == 'showteam':
            for m in '|'.join(p[3:]).split(']'):
                f = m.split('|')
                if len(f) > 3: sheet[p[2]][toid(f[1] or f[0])] = toid(f[3])
        if len(p) > 5 and p[1] == 'player' and p[5].strip().isdigit(): rating[p[2]] = int(p[5])
    act = {}; fnt = {'p1': 0, 'p2': 0}; vol = set(); blocks = collections.defaultdict(list); start = {}; t = 0; yawns = []
    for l in L:
        p = l.split('|')
        if len(p) < 2: continue
        if p[1] == 'turn':
            t = int(p[2]); start[t] = ({k: dict(v) for k, v in act.items()}, dict(fnt), set(vol)); continue
        blocks[t].append(p)
        if p[1] in ('switch', 'drag', 'replace') and len(p) > 3:
            slot = p[2][:3]; old = act.get(slot)
            if old: vol.discard(old['nick'])
            act[slot] = {'nick': p[2][5:], 'sp': p[3].split(',')[0], 'f': False}
        elif p[1] == 'detailschange' and p[2][:3] in act: act[p[2][:3]]['sp'] = p[3].split(',')[0]
        elif p[1] == 'faint' and p[2][:3] in act: act[p[2][:3]]['f'] = True; fnt[p[2][:2]] += 1
        elif p[1] == 'swap' and len(p) > 3:
            sd = p[2][:2]; a, b = act.get(sd + 'a'), act.get(sd + 'b'); act[sd + 'a'], act[sd + 'b'] = b, a
        elif p[1] == '-activate' and len(p) > 3 and (p[3] == 'trapped' or toid(p[3].replace('move: ', '')) in PARTIAL): vol.add(p[2][5:])
        elif p[1] == '-end' and len(p) > 3 and ('partiallytrapped' in l or toid(p[3].replace('move: ', '')) in PARTIAL): vol.discard(p[2][5:])
        elif p[1] == '-start' and len(p) > 3 and p[3] in ('move: Yawn', 'Yawn'): yawns.append((t, p[2][:3], p[2][5:]))
    out = []
    for ty, slot, nick in yawns:
        sd = slot[:2]; foe = 'p2' if sd == 'p1' else 'p1'
        kind = 'bot' if bot and sd == bot else 'human'
        if ty + 1 not in start: continue                                   # the game ended first
        a, f, v = start[ty + 1]
        me = next((m for s, m in a.items() if s[:2] == sd and m['nick'] == nick and not m['f']), None)
        if not me: continue                                                # gone before the turn started (fainted, forced out)
        on = sum(1 for s, m in a.items() if s[:2] == sd and not m['f'])
        if size[sd] - f[sd] - on <= 0: out.append((sd, kind, 'no bench', rating.get(sd), ty + 1, me['sp'])); continue
        foes = [(m['sp'], ability(sheet[foe], m['sp'])) for s, m in a.items() if s[:2] == foe and not m['f']]
        if trapped(me['sp'], ability(sheet[sd], me['sp']), foes, nick in v): out.append((sd, kind, 'trapped', rating.get(sd), ty + 1, me['sp'])); continue
        res = 'blocked'; pivot = forced = False; cur = next(s for s, m in a.items() if s[:2] == sd and m['nick'] == nick)
        for p in blocks[ty + 1]:
            if len(p) < 3: continue
            who = p[2][5:] if len(p[2]) > 5 else ''
            if p[1] == 'move' and who == nick and p[2][:2] == sd and len(p) > 3 and toid(p[3]) in PIVOT: pivot = True
            elif p[1] in ('-enditem', '-activate') and who == nick and p[2][:2] == sd and len(p) > 3 and any(k in p[3] for k in ('Eject Button', 'Eject Pack', 'Emergency Exit', 'Wimp Out')): forced = True
            elif p[1] == 'swap' and who == nick and p[2][:2] == sd: cur = sd + ('b' if cur[2] == 'a' else 'a')
            elif p[1] in ('switch', 'drag', 'replace') and p[2][:3] == cur:
                res = 'forced' if p[1] == 'drag' or forced else 'pivot' if pivot else 'switched'; break
            elif p[1] == 'faint' and who == nick and p[2][:2] == sd: res = 'fainted'; break
            elif p[1] == '-status' and who == nick and p[2][:2] == sd and len(p) > 3 and p[3] == 'slp': res = 'slept'; break
        out.append((sd, kind, res, rating.get(sd), ty + 1, me['sp']))
    return out
def bot_side(log):
    m = re.search(r'\|request\|\{.*?"side":\{[^{}]*?"id":"(p[12])"', log)
    return m.group(1) if m else None
def tally(rows):
    c = collections.Counter(r for r in rows)
    can = sum(v for k, v in c.items() if k not in ('no bench', 'trapped'))
    left = c['switched'] + c['pivot']
    return {'yawns': sum(c.values()), 'could_switch': can, 'left_by_choice': left, 'left_share': round(left / can, 3) if can else None,
            **{k: c[k] for k in ('switched', 'pivot', 'slept', 'fainted', 'blocked', 'forced', 'no bench', 'trapped')}}
if __name__ == '__main__':
    groups = collections.defaultdict(list); games = collections.Counter()
    for rid, log in C.games():
        if 'Yawn' not in log: continue
        rows = study(log)
        if rows: games['replays'] += 1
        for sd, kind, res, rt, *_ in rows:
            groups['human (replays)'].append(res)
            if rt and rt >= 1500: groups['human (replays, rated 1500+)'].append(res)
    for f in sorted(glob.glob(os.path.join(C.MAIN, 'bot', 'out', 'battle-*.log'))):
        if not re.search(r'-\d{6,}(-[a-z0-9]+)?\.log$', f): continue
        log = open(f).read()
        if 'Yawn' not in log: continue
        rows = study(log, bot_side(log))
        if rows: games['bot'] += 1
        for sd, kind, res, rt, *_ in rows: groups['bot' if kind == 'bot' else 'human (vs the bot)'].append(res)
    out = {'games_with_a_yawn': dict(games), 'groups': {k: tally(v) for k, v in groups.items()}}
    json.dump(out, open(os.path.join(C.HERE, 'yawn_study.json'), 'w'), indent=1)
    for k, v in out['groups'].items(): print(f"{k:30s} {v}")
    print(dict(games))
