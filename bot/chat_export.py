"""bot/out/chat.jsonl as plain text for the user (2026-10-13, the user: send the chat file when there are new messages):
bot/out/chat_export.txt, one line a message (local time, room or PM, sender, text). Prints counts only, never the text: chat stays
unread by Claude (the user's rule against prompt injection through chat).
  .venv/bin/python3 bot/chat_export.py"""
import json, os, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC, OUT = os.path.join(ROOT, 'bot', 'out', 'chat.jsonl'), os.path.join(ROOT, 'bot', 'out', 'chat_export.txt')
n = 0
with open(OUT, 'w') as o:
    for l in open(SRC) if os.path.exists(SRC) else []:
        if not l.strip(): continue
        r = json.loads(l); n += 1
        t = datetime.datetime.fromisoformat(r['when'].replace('Z', '+00:00')).astimezone().strftime('%Y-%m-%d %I:%M %p').replace(' 0', ' ')
        where = ('battle ' + r['room'].split('-')[-1][:14]) if r.get('room') else 'PM'
        o.write(f"{t}  {where}  {r.get('from', '')}: {r.get('text', '')}\n")
print(f'{n} messages -> {OUT}')
