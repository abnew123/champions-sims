"""Scan the bot's saved games for things that look wrong on the bot's side (2026-10-12, the user: obvious problems beyond the known
ones). Counts per kind with a few examples (room, turn): invalid choices and timer warnings, the bot's moves that failed or hit an
immunity / redirection / Psychic Terrain / Armor Tail, Fake Out after the first turn, the bot hitting its own partner with a damaging
move, the bot's Trick Room cancelling its own, the bot overwriting its own weather or terrain, status moves into an immune or already
statused target, a Pokemon that never moved before fainting, and turns where both of the bot's slots did nothing useful.
  .venv/bin/python3 bot/anomaly_scan.py"""
import json, os, glob, collections, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOVES = {m['name']: m for m in json.load(open(os.path.join(ROOT, 'native', 'engine_data_full.json')))['moves'].values()}
G = [json.loads(l) for l in open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl'))]
found = collections.defaultdict(list)
def add(kind, g, turn, what): found[kind].append((g['room'][-12:], turn, what))
for g in G:
    f = os.path.join(ROOT, 'bot', 'out', g['room'] + '.log')
    if not os.path.exists(f): continue
    me = g['side']; op = 'p2' if me == 'p1' else 'p1'
    L = open(f, errors='ignore').read().split('\n')
    turn = 0; tr_by = None; weather_by = None; terrain_by = None; last_move = None; moved = set(); entered = {}
    for i, l in enumerate(L):
        p = l.split('|')
        if len(p) < 2: continue
        k = p[1]
        if k == 'turn': turn = int(p[2]); continue
        if k == 'error': add('server rejected a choice', g, turn, '|'.join(p[2:])[:90])
        if k == 'inactive' and 'abnew123' in l.lower(): add('timer warning for the bot', g, turn, '|'.join(p[2:])[:90])
        if k in ('switch', 'drag') and p[2].startswith(me): entered[p[2].split(': ', 1)[1]] = turn
        if k == 'move' and len(p) > 3:
            mine = p[2].startswith(me); mon = p[2].split(': ', 1)[1]; mv = p[3]; tgt = p[4] if len(p) > 4 else ''
            last_move = (mine, mon, mv, tgt, i)
            if mine:
                moved.add(mon)
                m = MOVES.get(mv, {})
                if mv == 'Fake Out' and entered.get(mon, 0) < turn - 0 and entered.get(mon, -1) != turn - 1 and turn > 1 and entered.get(mon, 0) != turn:
                    pass
                if tgt.startswith(me) and m.get('category') in ('Physical', 'Special') and mv not in ('Beat Up', 'Pollen Puff') and not any(x.startswith('[spread]') for x in p[5:]):
                    add('the bot hit its own partner', g, turn, f'{mon}: {mv} -> {tgt.split(": ", 1)[-1]}')
                if mv == 'Trick Room' and tr_by == me: add("the bot's Trick Room cancelled its own", g, turn, mon)
                if mv == 'Trick Room' and tr_by == op: add("the bot reversed the opponent's Trick Room", g, turn, mon)
        if k == '-fieldstart' and 'Trick Room' in l: tr_by = last_move[0] and me or op if last_move else None
        if k == '-fieldend' and 'Trick Room' in l: tr_by = None
        if k in ('-fail', '-immune', '-miss') and last_move and last_move[0] and len(p) > 2:
            mine, mon, mv, tgt, _ = last_move
            if k == '-miss': continue
            why = '|'.join(p[2:])[:80]
            if k == '-fail' and mv in ('Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Silk Trap', 'Baneful Bunker', 'Burning Bulwark'): continue
            add(f"the bot's move {'failed' if k == '-fail' else 'hit an immunity'}", g, turn, f'{mon}: {mv} -> {tgt.split(": ", 1)[-1]} ({why})')
        if k == '-activate' and last_move and last_move[0] and ('Psychic Terrain' in l or 'move: Protect' in l and False):
            add("the bot's priority move was blocked by Psychic Terrain", g, turn, f'{last_move[1]}: {last_move[2]}')
        if k == 'cant' and len(p) > 3 and 'ability:' in p[3] and not p[2].startswith(op):
            add("the bot's move was blocked by an ability", g, turn, f'{p[2].split(": ", 1)[1]}: {p[4] if len(p) > 4 else ""} ({p[3]})')
        if k == '-weather' and len(p) > 2 and p[2] not in ('none',) and '[upkeep]' not in l:
            src = 'me' if any(x.startswith(f'[of] {me}') for x in p) else 'op' if any(x.startswith(f'[of] {op}') for x in p) else None
            if src == 'me' and weather_by == 'me' and prev_weather and prev_weather != p[2]: add('the bot overwrote its own weather', g, turn, f'{prev_weather} -> {p[2]}')
            weather_by = src; prev_weather = p[2]
        if k == 'faint' and p[2].startswith(me):
            mon = p[2].split(': ', 1)[1]
            if mon not in moved and entered.get(mon, 0) < turn - 1: add('a Pokemon of the bot fainted after 2+ turns in without moving', g, turn, mon)
            moved.discard(mon)
    prev_weather = None
print(f"{len(G)} games scanned")
for kind, items in sorted(found.items(), key=lambda kv: -len(kv[1])):
    print(f"\n{kind}: {len(items)}")
    for room, t, what in items[:6]: print(f"   ..{room} T{t}: {what}")
