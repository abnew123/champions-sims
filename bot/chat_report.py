"""Chat to the bot, as counts only (2026-10-11, the user: people's messages must never reach an assistant, so only the user reads the
text, in bot/out/chat.jsonl). Prints how many messages there are, how many in battle rooms and in private, and how many are new since a
time; never the text or the senders.
  .venv/bin/python3 bot/chat_report.py [--since 2026-10-11T03:00]"""
import json, os, sys
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
since = sys.argv[sys.argv.index('--since') + 1] if '--since' in sys.argv else ''
f = os.path.join(OUT, 'chat.jsonl')
rows = [json.loads(l) for l in open(f) if l.strip()] if os.path.exists(f) else []
new = [r for r in rows if r['when'] >= since] if since else rows
print(f"{len(rows)} chat messages recorded ({sum(1 for r in rows if r['room'])} in battle rooms, {sum(1 for r in rows if not r['room'])} private)"
      + (f"; {len(new)} since {since}" if since else '') + "; the text is for the user to read in bot/out/chat.jsonl")
