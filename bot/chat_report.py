"""Chat to the bot, as counts only (2026-10-11, the user: people's messages must never reach an assistant, so only the user reads the
text, in bot/out/chat.jsonl). Prints how many messages there are, how many in battle rooms and in private, and how many are new since a
time; never the text or the senders. Messages that are only a pleasantry are counted on their own and do not need the user's attention
(2026-10-12, the user: over half were gg; ggwp / "gg wp" that evening, ggs 2026-10-13, gl and glhf 2026-10-14; the watcher's own list of
thanks and the like folded in the same day). Matched with case, spaces and punctuation ignored, so "GL HF!" is glhf. bot/out/watch_exp.sh
uses the same test (other_count) to decide whether there is anything new for the user.
  .venv/bin/python3 bot/chat_report.py [--since 2026-10-11T03:00]"""
import json, os, re, sys
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
PLEASANTRIES = {'gg', 'ggs', 'ggwp', 'gl', 'glhf', 'hf', 'wp', 'ty', 'tygg', 'ggty', 'goodgame', 'thanks'}
# emoticons whose letters or digits would survive the punctuation strip ("gl hf <3" read as glhf3; the user, 2026-10-20)
EMOTICON = re.compile(r'<3+|(?<![a-z0-9])(?:[:;=]-?[dpo3]+|x+d+)(?![a-z0-9])')
# repeated letters don't matter either: ggg, gggg wp, tyyy, thankss (the user, 2026-10-20)
def squeeze(s): return re.sub(r'(.)\1+', r'\1', s)
SQUEEZED = {squeeze(p) for p in PLEASANTRIES}
def pleasantry(text): return squeeze(re.sub(r'[^a-z0-9]', '', EMOTICON.sub(' ', text.lower()))) in SQUEEZED
# other bots' canned greetings, left out like pleasantries (the user, 2026-11-03): a message containing any line of the git-ignored
# bot/out/chat_canned.json (they name the bots' accounts), with case, spaces and punctuation ignored
CANNED_F = os.path.join(OUT, 'chat_canned.json')
CANNED = [c for c in (re.sub(r'[^a-z0-9]', '', s.lower()) for s in (json.load(open(CANNED_F)) if os.path.exists(CANNED_F) else [])) if c]
def canned(text): t = re.sub(r'[^a-z0-9]', '', text.lower()); return any(c in t for c in CANNED)
def routine(text): return pleasantry(text) or canned(text)
def rows():
    f = os.path.join(OUT, 'chat.jsonl')
    return [json.loads(l) for l in open(f) if l.strip()] if os.path.exists(f) else []
def other_count(): return sum(1 for r in rows() if not routine(r['text']))
if __name__ == '__main__':
    since = sys.argv[sys.argv.index('--since') + 1] if '--since' in sys.argv else ''
    R = rows(); new = [r for r in R if r['when'] >= since] if since else R
    other = [r for r in R if not routine(r['text'])]; nc = sum(1 for r in R if canned(r['text']) and not pleasantry(r['text']))
    print(f"{len(R)} chat messages recorded: {len(R) - len(other) - nc} only pleasantries (gg, gl, glhf, ...), {nc} canned bot greetings, "
          f"{len(other)} other ({sum(1 for r in other if r['room'])} in battle rooms, {sum(1 for r in other if not r['room'])} private)"
          + (f"; since {since}: {sum(1 for r in new if routine(r['text']))} pleasantries or greetings, {sum(1 for r in new if not routine(r['text']))} other" if since else '')
          + "; the other messages are for the user to read in bot/out/chat.jsonl")
