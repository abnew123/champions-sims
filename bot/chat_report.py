"""Chat to the bot, as counts only (2026-10-11, the user: people's messages must never reach an assistant, so only the user reads the
text, in bot/out/chat.jsonl). Prints how many messages there are, how many in battle rooms and in private, and how many are new since a
time; never the text or the senders. Messages that are just "gg" (any capitalisation, trailing exclamation marks) are counted on
their own (2026-10-12, the user: over half were gg; ggwp and "gg wp" count with them since that evening).
  .venv/bin/python3 bot/chat_report.py [--since 2026-10-11T03:00]"""
import json, os, sys
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
since = sys.argv[sys.argv.index('--since') + 1] if '--since' in sys.argv else ''
f = os.path.join(OUT, 'chat.jsonl')
rows = [json.loads(l) for l in open(f) if l.strip()] if os.path.exists(f) else []
new = [r for r in rows if r['when'] >= since] if since else rows
gg = lambda r: r['text'].strip().lower().rstrip('!').strip() in ('gg', 'ggwp', 'gg wp', 'ggs')   # 2026-10-12 evening, the user: ggwp counts too; 2026-10-13: ggs
other = [r for r in rows if not gg(r)]
print(f"{len(rows)} chat messages recorded: {len(rows) - len(other)} just gg / ggwp, {len(other)} other ({sum(1 for r in other if r['room'])} in battle rooms, "
      f"{sum(1 for r in other if not r['room'])} private)" + (f"; since {since}: {sum(1 for r in new if gg(r))} gg, {sum(1 for r in new if not gg(r))} other" if since else '')
      + "; the other messages are for the user to read in bot/out/chat.jsonl")
