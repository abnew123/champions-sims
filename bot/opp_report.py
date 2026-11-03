#!/usr/bin/env python3
"""Results by opponent since a time (default the last 24 hours), from bot/out/games.jsonl and the battle logs'
|player| and |poke| lines (chat lines are never read). Since Showdown's bot opt-in (2026-10-20) many opponents are
other bots; this shows who we meet, how we do against each, and the team each brought.

  python3 bot/opp_report.py [since, ISO UTC like 2026-11-03T00:41]"""
import collections, datetime, glob, json, sys

OUT = 'bot/out/'
FMT = {'gen9championsvgc2026regmc': 'Bo1', 'gen9championsvgc2026regmcbo3': 'Bo3'}


def log_info(room, side):
    f = glob.glob(OUT + room + '*.log')
    name, team = None, []
    if not f: return name, team
    for line in open(f[0], errors='replace'):
        if line.startswith('|player|'):
            p = line.rstrip('\n').split('|')
            if len(p) > 3 and p[2] != side and p[3]: name = p[3]
        elif line.startswith('|poke|') and not line.startswith('|poke|' + side + '|'):
            team.append(line.split('|')[3].split(',')[0])
    return name, team


def main():
    since = sys.argv[1] if len(sys.argv) > 1 else (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat()[:19]
    G = [g for g in map(json.loads, open(OUT + 'games.jsonl')) if 'arm' in g and g['when'][:19] >= since]
    by = collections.OrderedDict()
    for g in G:
        name, team = log_info(g['room'], g['side'])
        b = by.setdefault(name or '?', {'games': collections.Counter(), 'matches': collections.defaultdict(list), 'teams': set(), 'rating': None})
        fm = FMT.get(g.get('format'), '?')
        b['games'][fm, g['won']] += 1
        if fm == 'Bo3': b['matches'][g.get('match')].append(g['won'])
        if team: b['teams'].add(' / '.join(sorted(team)))
        b['rating'] = g['oppRating']
    print(f"{len(G)} games since {since} UTC against {len(by)} opponents")
    for name, b in sorted(by.items(), key=lambda kv: -sum(kv[1]['games'].values())):
        parts = []
        for fm in ('Bo1', 'Bo3'):
            w, l = b['games'][fm, True], b['games'][fm, False]
            if w + l: parts.append(f"{fm} {w}-{l}")
        mw = sum(1 for m in b['matches'].values() if sum(m) * 2 > len(m))
        if b['matches']: parts.append(f"matches {mw}-{len(b['matches']) - mw}")
        print(f"  {name:20s} {', '.join(parts):34s} rating {b['rating']}")
        for t in sorted(b['teams']): print(f"      {t}")


if __name__ == '__main__':
    main()
