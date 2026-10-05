"""Turn OCR of a recorded Champions battle (ocr.swift output, frames at 2 fps) into a timeline of battle messages and decision points.
usage: python3 parse.py <ocr.jsonl> [fps=2]"""
import json, re, sys, difflib
fps = float(sys.argv[2]) if len(sys.argv) > 2 else 2
# battle messages: the game's own sentence patterns (other windows' text never fits these)
MSG = re.compile(r"( used .+[!l1]$|fainted!|flinched|It's (super|not very) effective|extremely effective|critical hit|sent out |^Go! |come back!|withdrew |"
                 r"protected itself|started to rain|turned harsh|sandstorm kicked|started to snow|twisted the dimensions|dimensions returned|"
                 r"made the opposing side|made your side|now protects|'s .*(fell|rose)|returned its stats|Mega Evolved|is reacting to|restored|"
                 r"hurt by|missed|avoided the attack|But it failed|won the battle|You won|You lost|forfeit|center of attention|ready to help|is paralyzed|fell asleep|"
                 r"was burned|was poisoned|is confused|Tailwind blew|Tailwind petered|rain stopped|sunlight faded|subsided|terrain|Terrain|doesn't affect|"
                 r"no effect|immune|'s (Drizzle|Drought|Intimidate|Sand Stream|Snow Warning|Psychic Surge|Grassy Surge)|perish count|Rank Master)", re.I)
OLD = re.compile(r"(used |fainted|flinched|effective|sent out|^Go! |come back|protected|started to|stopped|Trick Room|twisted|dimensions|Reflect|Light Screen|"
                 r"Tailwind|fell|rose|harshly|sharply|restored|hurt by|missed|avoided|Mega Evol|reacting|won the battle|You lost|You won|burn|paralyz|asleep|"
                 r"poison|Terrain|terrain|White Herb|Sitrus|Berry|Focus Sash|Intimidate|harsh|rain|sunlight|sandstorm|snow|confus|Protect|Follow Me|center of attention|"
                 r"Helping Hand|ready to help|Wide Guard|withdrew|Weather|weather|switched|ability|Ability|critical hit|no effect|doesn't affect|immune|recoil|"
                 r"cut|lowered|boosted|forfeit|Perish|perish|drowsy|fell asleep|woke|frozen|thaw)", re.I)
UI = re.compile(r"(Get Prime|BlueStacks|Communicating|MOVE TIME|Battle Info|Move Info|View Log|Category|Accuracy|Single Target|All Opponents|Contact|Close|Back|"
                r"Moves & More|Hide Summary|Show Summary|Standing By|Select 4|Preparing|Ranked|Season|Effective$)", re.I)
rows = [json.loads(l) for l in open(sys.argv[1])]
rows.sort(key=lambda r: r['file'])
events = []; last = []
for k, r in enumerate(rows):
    t = k / fps
    lines = [x for x in r['lines'] if len(x[0]) > 6]
    # battle text sits in the lower part of the game area, as one long sentence
    msgs = [x[0].strip() for x in lines if MSG.search(x[0]) and not UI.search(x[0]) and len(x[0].split()) >= 2 and len(x[0]) < 90]
    menu = any('MOVE TIME' in x[0] for x in r['lines'])
    for m in msgs:
        if any(difflib.SequenceMatcher(None, m, p).ratio() > 0.85 for p in last): continue
        events.append((t, 'msg', m))
    last = msgs or last[-3:]
    if menu and (not events or events[-1][1] != 'menu' or t - events[-1][0] > 3):
        hp = [x[0] for x in r['lines'] if re.fullmatch(r'\d{1,3} ?[/1л7] ?\d{2,3}', x[0].replace(' ', '')) or re.fullmatch(r'\d{1,3} ?%', x[0])]
        names = [x[0] for x in r['lines'] if re.fullmatch(r"[A-Z][a-z]+(-[A-Za-z]+)?", x[0]) and x[0] not in ('Range', 'Power', 'Back', 'Close')]
        events.append((t, 'menu', ' '.join(names[:6]) + '  ' + ' '.join(hp)))
for t, kind, s in events:
    print(f"{int(t // 60):02d}:{int(t % 60):02d} {'>>' if kind == 'menu' else '  '} {s}")
