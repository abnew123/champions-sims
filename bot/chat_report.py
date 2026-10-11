"""Chat to the bot: every line opponents or onlookers wrote in the bot's battle rooms, and every PM, from bot/out/chat.jsonl (the client
logs them live since 2026-10-11) plus the battle-room chat in the saved room logs (bot/out/battle-*.log). Prints them oldest first with
the room's last digits, so the user can see how people take the bot. Outputs carry usernames: they stay in bot/out/ (git-ignored).
  .venv/bin/python3 bot/chat_report.py [--since 2026-10-11T03:00]"""
import json, os, sys, glob
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
since = sys.argv[sys.argv.index('--since') + 1] if '--since' in sys.argv else ''
rows = []
if os.path.exists(os.path.join(OUT, 'chat.jsonl')):
    rows += [json.loads(l) for l in open(os.path.join(OUT, 'chat.jsonl')) if l.strip()]
seen = {(r['room'], r['from'], r['text']) for r in rows}
me = None
for f in sorted(glob.glob(os.path.join(OUT, 'battle-*.log'))):
    if '_' in os.path.basename(f) or 'regmb' in f: continue        # local test rooms
    room = os.path.basename(f)[:-4]; when = ''
    for l in open(f):
        p = l.rstrip('\n').split('|')
        if len(p) > 2 and p[1] == 't:': when = p[2]
        if len(p) > 3 and p[1] in ('c', 'c:'):
            who, text = (p[2], '|'.join(p[3:])) if p[1] == 'c' else (p[3], '|'.join(p[4:]))
            who = who.lstrip('~&@%+*#☆ ').strip()
            if who in ('', '~') or text.startswith('/') or 'bot' in who.lower(): continue
            if (room, who, text) in seen: continue
            rows.append({'when': when, 'room': room, 'from': who, 'text': text})
rows = [r for r in rows if str(r['when']) >= since]
print(f"{len(rows)} chat lines to the bot")
for r in rows: print(f"  {str(r['when'])[:16]:16s} {r['room'][-10:]:10s} {r['from']}: {r['text'][:200]}")
