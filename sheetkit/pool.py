"""A sheet's own opponent pool (sheet.json "pool"), for a sheet built against a later meta than Battle sim's pool (pssim/opp_pool.json,
Sep 9 - Oct 4). Same entries as opp_pool.build, from the cached public Showdown Reg M-C Bo3 games of a date window
(pssim/replays_protect, extended with `protect_replays.py new`), with a weight per entry: with "by_player" each player counts once per
card (the busiest players, mostly ladder bots, would otherwise fill a card with one team), else every side counts 1. Our ladder bot's
sides and the sixes in bot/teams.json are left out. Cards, their models and their sixes (opponents.py, optimal.card_sixes) are then
built from this pool, weighted, in the shapes opp_pool.model and opp_pool.sixes write. No usernames are stored: "player" is a number
within the file.

  sheet.json  "pool": {"from": "2026-10-13", "to": "2026-11-13", "by_player": true}
  python3 sheetkit/kit.py <team> opponents     builds work/pool.json, then the cards in sheets/<team>/opponents/ (opponents.py)"""
import os, sys, json, glob, random, datetime, collections
from common import ROOT, PSSIM, rj, wj

RULES_FILE = os.path.join(PSSIM, 'results', 'core_rules_both_100.json')

def path(sheet): return sheet.w('pool.json')
def card_group(e): return e['group'] if e['group'] != 'other' else 'other:' + e['arch']

def build(sheet):
    """work/pool.json from the replays in the sheet's window (needs the venv: opp_pool.parse and the classifiers import numpy)"""
    sys.path.insert(0, PSSIM)
    from opp_pool import parse
    from pro_replays import arch
    from cluster_opps import tag, norm
    cfg = sheet.cfg['pool']; A, B = cfg['from'], cfg['to']
    RP = os.path.join(PSSIM, 'replays_protect'); rules = rj(RULES_FILE)
    own = {frozenset(s['species'] for s in t['sets']) for t in rj(os.path.join(ROOT, 'bot', 'teams.json'))}
    bot = {}                                                     # our ladder bot's games: game id -> its side
    for l in open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl')):
        if l.strip(): g = json.loads(l); bot['-'.join(g['room'].split('-')[1:3])] = g['side']
    day = lambda t: datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d')
    idx = rj(os.path.join(RP, 'index.json')); entries = []; by_six = collections.defaultdict(list); players = {}
    for f in sorted(glob.glob(os.path.join(RP, '*bo3-*.log'))):
        gid = os.path.basename(f)[:-4]; t = (idx.get(gid) or {}).get('time')
        if not t or not (A <= day(t) <= B): continue
        log = open(f, encoding='utf-8', errors='replace').read(); sides, winner, turns = parse(log)
        who = {p[2]: p[3].strip().lower() for p in (l.split('|') for l in log.split('\n') if l.startswith('|player|')) if len(p) > 3 and p[3]}
        for s in ('p1', 'p2'):
            sd = sides[s]
            if bot.get(gid) == s or not sd['six'] or len(sd['six']) != 6 or len(sd['lead']) != 2: continue
            species = [m['species'] for m in sd['six']]
            if frozenset(species) in own: continue
            lead = [sd['lead'].get(s + 'a'), sd['lead'].get(s + 'b')]
            if any(x is None or x not in species for x in lead): continue
            e = {'id': gid, 'side': s, 'six': sd['six'], 'lead': lead, 'seen': [x for x in sd['seen'] if x in species], 'rating': idx[gid].get('rating'),
                 'won': None if winner is None else winner == s, 'turns': turns, 't1': {sp: sd['t1'].get(sp, '(none)') for sp in lead},
                 'mega': sd['mega'], 'day': day(t), 'player': players.setdefault(who.get(s, gid + s), len(players))}
            entries.append(e); by_six[frozenset(species)].append(e)
    players.clear()
    rng = random.Random(0)                                       # brings filled to four as opp_pool.build does
    for e in entries:
        species = [m['species'] for m in e['six']]; bring = list(e['seen'])[:4]; e['bring_seen'] = len(bring)
        if len(bring) < 4:
            others = collections.Counter(x for o in by_six[frozenset(species)] if o is not e for x in o['seen'] if x not in bring)
            for x, _ in others.most_common():
                if len(bring) >= 4: break
                bring.append(x)
            rest = [x for x in species if x not in bring]; rng.shuffle(rest)
            while len(bring) < 4: bring.append(rest.pop())
        e['bring'] = bring; e['arch'] = arch([norm(x) for x in species]); e['group'] = tag(species, rules)
    per = collections.Counter((e['player'], card_group(e)) for e in entries)
    for e in entries: e['w'] = 1 / per[e['player'], card_group(e)] if cfg.get('by_player') else 1.0
    wj({'window': [A, B], 'by_player': bool(cfg.get('by_player')), 'rules': rules, 'entries': entries,
        'note': f'public Showdown Reg M-C Bo3 sides with an open team sheet, {A} to {B} (local dates), our bot\'s sides and own sixes left out; '
                '"player" numbers distinct players within this file only; "w" is the entry\'s weight; no usernames'}, path(sheet))
    W = sum(e['w'] for e in entries)
    print(f"{len(entries)} sides from {len(set(e['id'] for e in entries))} games, {A} to {B}; {len(set(e['player'] for e in entries))} players; "
          f"weight {W:.0f}; in a core group {100 * sum(e['w'] for e in entries if e['group'] != 'other') / W:.1f}%")

def load(sheet):
    if not os.path.exists(path(sheet)): sys.exit(f"no {os.path.relpath(path(sheet), ROOT)}: run `kit.py {sheet.slug} opponents` first")
    return rj(path(sheet))['entries']

def toid(x): return ''.join(c for c in x.lower() if c.isalnum())
def in_group(e, group):                                          # as opp_pool.in_group
    if group == 'all': return True
    if group.startswith('arch:'): return e['arch'] == group[5:]
    if group.startswith('other:'): return e['group'] == 'other' and e['arch'] == group[6:]
    return e['group'] == group

def model(entries, group, pairs_n=6):
    """opp_pool.model, weighted: {n, sides, group, sets, pairs: [{pair, n, share, win, hiShare, t1, mega, back}]}; n counts weight"""
    ents = [e for e in entries if in_group(e, group)]; N = sum(e['w'] for e in ents)
    cnt = collections.defaultdict(collections.Counter); tot = collections.Counter()
    for e in ents:
        for m in e['six']:
            key = f"{toid(m['item'])}|{toid(m['ability'])}|{m['nature']}|{'/'.join(sorted(toid(x) for x in m['moves']))}"
            cnt[m['species']][key] += e['w']; tot[m['species']] += e['w']
    sets = {sp: f"{c.most_common(1)[0][0]} ({c.most_common(1)[0][1]:.0f}/{tot[sp]:.0f})" for sp, c in cnt.items()}
    by_pair = collections.defaultdict(list)
    for e in ents: by_pair[' + '.join(sorted(e['lead']))].append(e)
    hi = [e for e in ents if (e['rating'] or 0) >= 1400]; H = sum(e['w'] for e in hi)
    pairs = []
    for pair, es in sorted(by_pair.items(), key=lambda kv: -sum(e['w'] for e in kv[1]))[:pairs_n]:
        n = sum(e['w'] for e in es); leads = pair.split(' + '); t1 = {}
        for sp in leads:
            c = collections.Counter()
            for e in es: c[e['t1'].get(sp, '(none)')] += e['w']
            t1[sp] = ', '.join(f"{a}:{v / n:.2f}" for a, v in c.most_common())
        mega = collections.Counter(); back = collections.Counter()
        for e in es:
            for sp in e['mega']:
                if sp in leads: mega[sp] += e['w']
            for x in e['bring']:
                if x not in leads: back[x] += e['w']
        won = [(e['w'], e['won']) for e in es if e['won'] is not None]; ww = sum(w for w, _ in won)
        pairs.append({'pair': pair, 'n': round(n, 2), 'sides': len(es), 'share': round(n / N, 4), 'win': round(sum(w for w, x in won if x) / ww, 3) if ww else None,
                      'hiShare': round(sum(e['w'] for e in hi if ' + '.join(sorted(e['lead'])) == pair) / H, 4) if H else None,
                      't1': t1, 'mega': {k: round(v, 2) for k, v in mega.items()}, 'back': ', '.join(f"{x}:{v / n:.2f}" for x, v in back.most_common(6))})
    return {'n': round(N, 2), 'sides': len(ents), 'group': group, 'sets': sets, 'pairs': pairs}

def sixes(entries, group, n):
    """opp_pool.sixes, weighted: the group's n most common sixes (by weight) with each species' most common set; count is weight"""
    ents = [e for e in entries if in_group(e, group)]
    by = collections.defaultdict(list)
    for e in ents: by[frozenset(m['species'] for m in e['six'])].append(e)
    tot = sum(e['w'] for e in ents); out = []
    for six, es in sorted(by.items(), key=lambda kv: -sum(e['w'] for e in kv[1]))[:n]:
        sets = []
        for sp in sorted(six):
            c = collections.Counter()
            for e in es:
                for m in e['six']:
                    if m['species'] == sp: c[json.dumps(m, sort_keys=True)] += e['w']
            sets.append(json.loads(c.most_common(1)[0][0]))
        w = sum(e['w'] for e in es)
        out.append({'six': sets, 'count': round(w, 2), 'sides': len(es), 'weight': w / tot, 'group': group})
    return {'group': group, 'sides': len(ents), 'distinct_sixes': len(by), 'covered': sum(x['count'] for x in out) / max(1e-9, tot), 'sixes': out}

if __name__ == '__main__':                                       # python3 sheetkit/pool.py <team> build (the kit runs this with the venv)
    from common import Sheet
    if sys.argv[2] == 'build': build(Sheet(sys.argv[1]))
