"""Real ladder games for the matchup predictor (the user, 2026-11-27: a lighter, data-driven predictor of how teams match up, not
the battle sim, so the M-D meta can be estimated from many simulated teams; it should be accurate in general rather than
encode our understanding of the game).

Reads the saved Showdown replays: M-C Bo3 / Bo1 (pssim/replays_protect), M-B Bo3 (teamsearch/backtest/replays_mb), and what
collect.py saves from Nov 27 on (predictor/replays: the rest of M-C, then M-D and later regulations).
One row per game: both sixes from team preview, full sets when the players accepted open team sheets, which Pokemon
Mega Evolved, which four were brought, the winner, both players' ladder ratings before the game, and the Bo3 match.
Online tournaments (fetch_tours.py, predictor/tours/) add one row per game with src 'online'.
Player names are never written: a player is a number assigned in this run (stable for a given set of files). Games with
the ladder bot (bot/account.json) are left out, and so are the M-B games with out-of-format sheets (Sep 1-4: a species outside
M-B's dex, or Assault Vest, Choice Band, Power Herb, Ability Shield).
  teamsearch/bin/teamsearch-py parse_games.py            -> games.jsonl.gz
"""
import os, re, sys, json, gzip, glob, time, collections, calendar
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = [os.path.join(ROOT, 'pssim', 'replays_protect'), os.path.join(ROOT, 'teamsearch', 'backtest', 'replays_mb'), os.path.join(HERE, 'replays')]
OUT = os.path.join(HERE, 'games.jsonl.gz'); LOG = os.path.join(HERE, 'predictor.log')
MB_DEX = set(json.load(open(os.path.join(ROOT, 'teamsearch', 'backtest', 'dex_mb.json'))))
MB_BAD_ITEMS = {'AssaultVest', 'ChoiceBand', 'PowerHerb', 'AbilityShield', 'Assault Vest', 'Choice Band', 'Power Herb', 'Ability Shield'}

def say(s):
    with open(LOG, 'a') as f: f.write(f"{time.strftime('%I:%M %p')} {s}\n")

def species(details): return re.sub(r'-Mega(-[XYZ])?$', '', details.split(',')[0].strip())

def packed(team):
    """Showdown packed team -> [{species, item, ability, moves, nature}]"""
    out = []
    for p in team.split(']'):
        f = p.split('|')
        if len(f) < 7: continue
        out.append(dict(species=f[1] or f[0], item=f[2], ability=f[3], moves=[m for m in f[4].split(',') if m], nature=f[5]))
    return out

def parse(path):
    try: L = open(path, encoding='utf-8', errors='replace').read().split('\n')
    except OSError: return None
    g = dict(id=os.path.basename(path)[:-4], t=None, g=None, match=None, names={}, six={'p1': [], 'p2': []}, sets={}, mega={},
             brought={'p1': [], 'p2': []}, rating={}, win=None, tier=None)
    rat = {}
    for l in L:
        if l.startswith('|player|'):
            p = l.split('|')
            if len(p) > 3 and p[3]: g['names'][p[2]] = p[3]
        elif l.startswith('|poke|'):
            p = l.split('|'); g['six'][p[2]].append(species(p[3]))
        elif l.startswith('|t:|') and g['t'] is None: g['t'] = int(l[4:])
        elif l.startswith('|tier|'): g['tier'] = l[6:]
        elif l.startswith('|uhtml|bestof|'):
            m = re.search(r'Game (\d)</strong> of <a href="/game-bestof3-([^"]+)"', l)
            if m: g['g'], g['match'] = int(m.group(1)), m.group(2)
        elif l.startswith('|showteam|'):
            p = l.split('|', 3); g['sets'][p[2]] = packed(p[3])
        elif l.startswith('|-mega|'):
            p = l.split('|'); g['mega'][p[2][:2]] = p[3].split(',')[0].strip()
        elif l.startswith('|switch|') or l.startswith('|drag|'):
            p = l.split('|'); side, sp = p[2][:2], species(p[3])
            if sp not in g['brought'][side] and len(g['brought'][side]) < 4: g['brought'][side].append(sp)
        elif l.startswith('|win|'): g['win'] = l[5:].strip()
        elif l.startswith('|tie'): g['win'] = ''
        elif l.startswith('|raw|') and 'rating:' in l:
            m = re.match(r"\|raw\|(.+?)'s rating: (\d+) &rarr;", l)
            if m: rat[m.group(1)] = int(m.group(2))
    if g['win'] is None or len(g['six']['p1']) != 6 or len(g['six']['p2']) != 6: return None
    for side, n in g['names'].items():
        if n in rat: g['rating'][side] = rat[n]
    return g

TOURS = os.path.join(HERE, 'tours')
OFFMETA = re.compile(r'off.?meta|mono|draft|random|singles|\bbss\b|1v1|little cup|\blc\b|\buu\b|\bnu\b|\bru\b|\bpu\b', re.I)

def tours(pid, ladder_rows):
    """one row per game from the saved online tournaments (fetch_tours.py): both open team sheets, the game's winner; src 'online'.
    Left out: events named as off-meta or another ruleset, sheets that are not six Pokemon, sheets with a species never seen on
    that regulation's ladder (once the ladder has 1,000+ games), byes, ties and unreported games."""
    idf = lambda x: re.sub(r'[^a-z0-9]', '', (x or '').lower())
    lad = collections.defaultdict(set); nl = collections.Counter()
    for r in ladder_rows:
        nl[r['reg']] += 1; lad[r['reg']] |= {idf(x) for x in r['six1'] + r['six2']}
    rows, skip = [], collections.Counter()
    for f in sorted(glob.glob(os.path.join(TOURS, '*.json'))):
        if f.endswith('index.json'): continue
        d = json.load(open(f))
        if d.get('no_sheets'): continue
        T = d['t']; reg = T['format']
        if OFFMETA.search(T['name']): skip['off-meta or other-ruleset events'] += 1; continue
        t0 = calendar.timegm(time.strptime(T['date'][:19], '%Y-%m-%dT%H:%M:%S'))
        legal = lad[reg] if nl[reg] >= 1000 else None
        sheet = {}
        for p in d['standings']:
            dl = p.get('decklist') or []
            sets = [dict(species=x.get('id') or x.get('name'), item=x.get('item') or '', ability=x.get('ability') or '',
                         moves=[m for m in (x.get('attacks') or []) if m], nature=x.get('nature') or '') for x in dl]
            if len(sets) != 6: skip['sheets not six'] += 1; continue
            if legal is not None and any(idf(s['species']) not in legal for s in sets): skip['sheets with a species off the ladder'] += 1; continue
            sheet[p['player']] = sets
        for k, m in enumerate(d['pairings']):
            a, b = m.get('player1'), m.get('player2')
            if not a or not b or a not in sheet or b not in sheet: continue
            games = [v.get('winner') for _, v in sorted((m.get('games') or {}).items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 0)]
            if not games and m.get('winner') in (a, b): games = [m['winner']]
            for gi, w in enumerate(games, 1):
                if w not in (a, b): skip['ties or unreported games'] += 1; continue
                ids = [pid.setdefault('lt:' + x.lower(), len(pid)) for x in (a, b)]
                rows.append(dict(id=f"lt-{T['id']}-{k}-{gi}", fmt='limitless-' + reg, reg=reg, src='online', t=int(t0 + 2400 * (m.get('round') or 0) + 60 * gi),
                                 g=gi, match=f"lt-{T['id']}-{k}", p1=ids[0], p2=ids[1], r1=None, r2=None,
                                 six1=[s['species'] for s in sheet[a]], six2=[s['species'] for s in sheet[b]], sets1=sheet[a], sets2=sheet[b],
                                 mega1=None, mega2=None, b1=[], b2=[], win=int(w == a), phase=m.get('phase')))
    return rows, skip

def main():
    files = sorted({os.path.basename(f): f for d in SRC for f in glob.glob(os.path.join(d, '*.log'))}.values())
    botname = json.load(open(os.path.join(ROOT, 'bot', 'account.json')))['name'].lower()
    say(f"parse: {len(files)} replay files")
    pid, rows, skip = {}, [], {'unreadable or incomplete': 0, 'the ladder bot': 0, 'M-B out-of-format sheet': 0, 'not Champions': 0}
    with Pool(int(os.environ.get('TS_THREADS', 3))) as pool:
        for k, g in enumerate(pool.imap(parse, files, chunksize=64), 1):
            if k % 10000 == 0: say(f"  parse: {k}/{len(files)} files")
            if g is None: skip['unreadable or incomplete'] += 1; continue
            fmt = re.sub(r'^(smogtours-|eternity-)', '', g['id']).rsplit('-', 1)[0]
            if 'champions' not in fmt or not re.search(r'regm[a-z]', fmt): skip['not Champions'] += 1; continue
            if any(n.lower() == botname for n in g['names'].values()): skip['the ladder bot'] += 1; continue
            if 'regmb' in fmt and (any(x not in MB_DEX for x in g['six']['p1'] + g['six']['p2'])
                                   or any(s['item'] in MB_BAD_ITEMS for v in g['sets'].values() for s in v)): skip['M-B out-of-format sheet'] += 1; continue
            ids = {s: pid.setdefault(g['names'].get(s, f"?{g['id']}{s}").lower(), len(pid)) for s in ('p1', 'p2')}
            win = 1 if g['win'] == g['names'].get('p1') else 0 if g['win'] == g['names'].get('p2') else None
            if win is None: skip['unreadable or incomplete'] += 1; continue
            rows.append(dict(id=g['id'], fmt=fmt, reg='M-' + re.search(r'regm([a-z])', fmt).group(1).upper(), src='tour' if g['id'].startswith(('smogtours', 'eternity')) else 'ladder',
                             t=g['t'], g=g['g'], match=g['match'], p1=ids['p1'], p2=ids['p2'], r1=g['rating'].get('p1'), r2=g['rating'].get('p2'),
                             six1=g['six']['p1'], six2=g['six']['p2'], sets1=g['sets'].get('p1'), sets2=g['sets'].get('p2'),
                             mega1=g['mega'].get('p1'), mega2=g['mega'].get('p2'), b1=g['brought']['p1'], b2=g['brought']['p2'], win=win))
    # Sep 1-4 M-B games whose sheets hold anything never seen in M-B outside those days (M-C items, abilities, moves)
    w0, w1 = time.mktime((2026, 9, 1, 0, 0, 0, 0, 0, -1)), time.mktime((2026, 9, 5, 0, 0, 0, 0, 0, -1))
    inw = lambda r: r['reg'] == 'M-B' and r['t'] and w0 <= r['t'] < w1
    toks = lambda r: {(k, x) for v in (r['sets1'] or [], r['sets2'] or []) for s in v for k, x in [('i', s['item']), ('a', s['ability'])] + [('m', m) for m in s['moves']]}
    seen = set().union(*[toks(r) for r in rows if r['reg'] == 'M-B' and not inw(r)])
    keep = [r for r in rows if not (inw(r) and toks(r) - seen)]; skip['M-B out-of-format sheet'] += len(rows) - len(keep); rows = keep
    if os.path.isdir(TOURS):
        trows, tskip = tours(pid, rows); rows += trows; skip.update(tskip)
    with gzip.open(OUT, 'wt') as f:
        for r in sorted(rows, key=lambda r: (r['t'] or 0, r['id'])): f.write(json.dumps(r) + '\n')
    by = {}
    for r in rows: by[(r['reg'], r['src'])] = by.get((r['reg'], r['src']), 0) + 1
    say(f"parse done: {len(rows)} games ({', '.join(f'{a} {b} {n}' for (a, b), n in sorted(by.items()))}); left out: "
        + ', '.join(f'{k} {v}' for k, v in skip.items() if v)
        + f"; open team sheets in {sum(1 for r in rows if r['sets1'] and r['sets2'])}, rated {sum(1 for r in rows if r['r1'] and r['r2'])}")

if __name__ == '__main__': main()
