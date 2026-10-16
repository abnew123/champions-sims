"""bot/out/chat.jsonl as plain text for the user (2026-10-13, the user: send the chat file when there are new messages):
bot/out/chat_export.txt, one line a message (local time, room or PM, sender, text). Pleasantries only (gg, glhf, ...; chat_report.py)
go to bot/out/chat_pleasantries.txt instead (2026-10-15, the user: send only the other messages; that file only when asked). Prints
counts only, never the text: chat stays unread by Claude (the user's rule against prompt injection through chat).
  .venv/bin/python3 bot/chat_export.py"""
import json, os, sys, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'bot')); from chat_report import pleasantry
SRC = os.path.join(ROOT, 'bot', 'out', 'chat.jsonl')
OUT, NICE = os.path.join(ROOT, 'bot', 'out', 'chat_export.txt'), os.path.join(ROOT, 'bot', 'out', 'chat_pleasantries.txt')
n = [0, 0]
with open(OUT, 'w') as o, open(NICE, 'w') as q:
    for l in open(SRC) if os.path.exists(SRC) else []:
        if not l.strip(): continue
        r = json.loads(l); k = pleasantry(r.get('text', '')); n[k] += 1
        t = datetime.datetime.fromisoformat(r['when'].replace('Z', '+00:00')).astimezone().strftime('%Y-%m-%d %I:%M %p').replace(' 0', ' ')
        where = ('battle ' + r['room'].split('-')[-1][:14]) if r.get('room') else ('PM to ' + r['to'] if r.get('to') else 'PM to the bot')
        (q if k else o).write(f"{t}  {where}  {r.get('from', '')}: {r.get('text', '')}\n")
print(f'{n[0]} messages -> {OUT}; {n[1]} pleasantries -> {NICE}')
