"""Protect chains by the bot's own Pokemon: for every finished or running game in bot/out/battle-*.log, the runs of Protect (or Detect,
Spiky Shield, etc.: any move named in STALL) the same Pokemon used on consecutive turns, longest first, with whether each one worked.
The user (2026-10-11): Archaludon's Leftovers chains are fine; a lot of chaining on any other Pokemon means giving the bot the self-play
turn solver (its double-Protect check, DP2).
  .venv/bin/python3 bot/protect_report.py [min chain=3]"""
import os, sys, glob, re
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
STALL = {'Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Baneful Bunker', 'Burning Bulwark', 'Silk Trap', 'Obstruct'}
mn = int(sys.argv[1]) if len(sys.argv) > 1 else 3
chains = []
for f in sorted(glob.glob(os.path.join(OUT, 'battle-gen9championsvgc2026regmc*.log')), key=os.path.getmtime):
    lines = open(f, errors='ignore').read().split('\n')
    side = next((l.split('|')[2] for l in lines if l.startswith('|player|') and 'abnew123' in l.lower()), None)
    if not side: continue
    turn = 0; last = {}; run = {}   # slot species -> current chain [(turn, worked)]
    pending = None
    for l in lines:
        p = l.split('|')
        if len(p) < 2: continue
        if p[1] == 'turn': turn = int(p[2])
        elif p[1] == 'move' and len(p) > 3 and p[2].startswith(side):
            mon = p[2].split(': ', 1)[1]
            if p[3] in STALL:
                worked = not l.endswith('[still]') and '||' not in l
                ch = run.get(mon, [])
                if ch and ch[-1][0] == turn - 1: ch.append((turn, worked))
                else: ch = [(turn, worked)]
                run[mon] = ch
                if len(ch) >= mn: chains.append((os.path.basename(f)[-16:-4], mon, list(ch)))
            else: run[mon] = []
best = {}
for room, mon, ch in chains: best[(room, mon, ch[0][0])] = ch
rows = sorted(((len(ch), room, mon, ch) for (room, mon, _), ch in best.items()), reverse=True)
print(f"Protect chains of {mn}+ turns by the bot's Pokemon: {len(rows)}")
for n, room, mon, ch in rows: print(f"  {n} turns  {mon:12s} room ..{room}  turns {ch[0][0]}-{ch[-1][0]}  worked {''.join('y' if w else 'n' for _, w in ch)}")
