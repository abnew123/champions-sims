"""The Trick Room six against the rain teams that beat it on the ladder (2026-11-05, the user: "let's study the rain matchup in
self-play"). Two other bots on the ladder won most of their Bo3 games against it with Pelipper + Archaludon rain; the Trick Room
sheet's own bring sims already rate "Rain: Archaludon + Pelipper" its worst card (13.9% for its best four against theirs). Here the
exact sixes they brought, the fours they chose, and every four of ours, in self-play with the bot's engine.
  configs   from the bot's saved Bo3 logs against those opponents (their usernames in the git-ignored bot/out/rain_opponents.json, a list;
            only |player|, |poke|, |showteam|, |switch|, |drag|, |request|, |win|
            lines are read; chat never): each opposing six (open team sheet; spreads as the bot assumes them, evalbar/spots.py evs_for),
            each four they brought (leads, and the back as far as it showed), each four we brought (our first request) and the result
  jobs      every four of ours (90: lead pair + back pair) against the chosen opposing fours, explicit teams for native/battle_starts.js
  report    win rate of each of our fours against each opposing four and overall, with the bring the bot actually used
  .venv/bin/python3 bot/rain_study.py configs [opponent ...]        -> pssim/results/rain/configs.json
  .venv/bin/python3 bot/rain_study.py jobs <min games a four=3>     -> pssim/results/rain/jobs.json
  .venv/bin/python3 bot/rain_study.py report <result dir>
  .venv/bin/python3 bot/rain_study.py confirm <matrix result dir> [top=6]  -> pssim/results/rain/confirm_jobs.json (then rain_matrix.sh
            JOBS=.../confirm_jobs.json TAG=confirm G0=1000 G=24)"""
import os, sys, json, glob, itertools, collections, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'bot')); sys.path.insert(0, os.path.join(ROOT, 'evalbar'))
OUT = os.path.join(ROOT, 'pssim', 'results', 'rain'); os.makedirs(OUT, exist_ok=True)
SAFE = ('player', 'poke', 'showteam', 'switch', 'drag', 'request', 'win', 'turn')
toid = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
base = lambda s: re.sub(r'-Mega(-[XYZ])?$', '', s.split(',')[0].strip())


def lines(room):
    f = os.path.join(ROOT, 'bot', 'out', room + '.log')
    return [l.rstrip('\n') for l in open(f, errors='ignore') if l.startswith('|') and l.split('|')[1] in SAFE] if os.path.exists(f) else []


def game_info(g):
    import brain
    L = lines(g['room']); me = g['side']; them = 'p2' if me == 'p1' else 'p1'
    name = next((l.split('|')[3] for l in L if l.startswith(f'|player|{them}|')), None)
    six = brain.showteam(L, them)
    leads, seen, turn1 = [], [], False
    for l in L:
        p = l.split('|')
        if p[1] == 'turn': turn1 = True
        if p[1] in ('switch', 'drag') and p[2].startswith(them):
            sp = base(p[3])
            if not turn1 and len(leads) < 2 and sp not in leads: leads.append(sp)
            if sp not in seen: seen.append(sp)
    ours = None
    for l in L:
        p = l.split('|', 2)
        if p[1] == 'request' and len(p) > 2 and p[2].strip():
            try: r = json.loads(p[2])
            except Exception: continue
            if r.get('teamPreview'): continue
            ours = [base(x['details']) for x in r['side']['pokemon']][:4]; break
    return {'room': g['room'], 'when': g['when'], 'won': g['won'], 'team': g.get('team'), 'opp': name, 'six': six,
            'their_lead': sorted(leads), 'their_back_seen': sorted(s for s in seen if s not in leads), 'our_four': ours}


def configs(names):
    G = [json.loads(l) for l in open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl')) if l.strip()]
    G = [g for g in G if (g.get('format') or 'gen9championsvgc2026regmcbo3').endswith('bo3') and g.get('won') is not None and g.get('team') == 'Trick Room six'
         and g['when'] >= '2026-11-02']
    import opp_report as OR
    G = [g for g in G if (OR.log_info(g['room'], g['side'])[0] or '') in names]
    rows = [game_info(g) for g in G]
    sixes = collections.defaultdict(list)
    for r in rows:
        if r['six'] and any(s['species'] == 'Pelipper' for s in r['six']): sixes[' / '.join(sorted(base(s['species']) for s in r['six']))].append(r)
    out = []
    for key, R in sorted(sixes.items(), key=lambda kv: -len(kv[1])):
        six = R[0]['six']; spe = {base(s['species']): s for s in six}
        fours = collections.Counter(); wins = collections.Counter()
        for r in R:
            back = r['their_back_seen']
            k = (tuple(r['their_lead']), tuple(back))
            fours[k] += 1; wins[k] += 1 if r['won'] else 0
        ours = collections.Counter((tuple(r['our_four'][:2]), tuple(sorted(r['our_four'][2:]))) for r in R if r['our_four'])
        out.append({'six': key, 'games': len(R), 'won': sum(1 for r in R if r['won']), 'by': dict(collections.Counter(r['opp'] for r in R)),
                    'sets': six, 'their_fours': [{'lead': list(l), 'back_seen': list(b), 'games': n, 'won': wins[(l, b)]} for (l, b), n in fours.most_common()],
                    'our_fours': [{'lead': list(l), 'back': list(b), 'games': n} for (l, b), n in ours.most_common()]})
    json.dump(out, open(os.path.join(OUT, 'configs.json'), 'w'), indent=1)
    for o in out:
        print(f"{o['six']}: {o['games']} games, we won {o['won']} {o['by']}")
        for f in o['their_fours'][:6]: print(f"    they: lead {' + '.join(f['lead'])}, back seen {' + '.join(f['back_seen']) or '-'}: {f['games']} games, we won {f['won']}")
        for f in o['our_fours'][:3]: print(f"    we:   lead {' + '.join(f['lead'])}, back {' + '.join(f['back'])}: {f['games']} games")


def full_set(s):
    import spots
    s = dict(s); s['species'] = 'Floette-Eternal' if s['species'] == 'Floette' else s['species']
    if not any(s.get('evs') or []): s['evs'] = list(spots.evs_for(s['species'], s.get('item', ''), s.get('nature', 'Serious'), s.get('moves', [])))
    return s


def jobs(min_games=3):
    """every four of ours against each opposing four seen min_games times with its whole back: [{mine, theirs, meta}]"""
    C = json.load(open(os.path.join(OUT, 'configs.json')))
    ours = {t['name']: t for t in json.load(open(os.path.join(ROOT, 'bot', 'teams.json')))}['Trick Room six']['sets']
    mine = {s['species']: s for s in ours}; names = [s['species'] for s in ours]
    J = []; cfgs = []
    for c in C:
        sets = {base(x['species']): full_set(x) for x in c['sets']}
        for f in c['their_fours']:
            if f['games'] < min_games or len(f['back_seen']) != 2 or not all(b in sets for b in f['lead'] + f['back_seen']): continue
            cfgs.append({'six': c['six'], 'lead': f['lead'], 'back': f['back_seen'], 'games': f['games'], 'won': f['won']})
            theirs = [sets[x] for x in f['lead'] + f['back_seen']]
            for lead in itertools.combinations(names, 2):
                for back in itertools.combinations([n for n in names if n not in lead], 2):
                    J.append({'mine': [mine[x] for x in lead + back], 'theirs': theirs,
                              'meta': {'cfg': len(cfgs) - 1, 'six': c['six'], 'their_lead': f['lead'], 'their_back': f['back_seen']}})
    json.dump(J, open(os.path.join(OUT, 'jobs.json'), 'w')); json.dump(cfgs, open(os.path.join(OUT, 'cfgs.json'), 'w'), indent=1)
    print(f"{len(J)} jobs: {len(J) // max(len(cfgs), 1)} fours of ours against {len(cfgs)} opposing fours")
    for i, c in enumerate(cfgs): print(f"  {i}: {c['six']} | lead {' + '.join(c['lead'])}, back {' + '.join(c['back'])} ({c['games']} real games, we won {c['won']})")


def report(d):
    import math
    cfgs = json.load(open(os.path.join(OUT, 'cfgs.json'))); C = json.load(open(os.path.join(OUT, 'configs.json')))
    used = collections.Counter()
    for c in C:
        for f in c['our_fours']: used[(tuple(sorted(f['lead'])), tuple(sorted(f['back'])))] += f['games']
    R = collections.defaultdict(lambda: collections.defaultdict(list))
    for f in glob.glob(os.path.join(d, '*.json')):
        j = json.load(open(f)); m = j.get('meta') or j
        k = (tuple(sorted(j.get('lead') or m.get('lead'))), tuple(sorted(j.get('back') or m.get('back'))))
        for r in j.get('rows', []):
            if r.get('v') is not None: R[k][m['cfg']].append(r['v'])
    wt = [c['games'] for c in cfgs]; W = sum(wt)
    def score(k):
        per = [sum(R[k][i]) / len(R[k][i]) if R[k][i] else float('nan') for i in range(len(cfgs))]
        have = [(w, p) for w, p in zip(wt, per) if p == p]   # a run still going: the opposing fours played so far, reweighted
        return (sum(w * p for w, p in have) / sum(w for w, _ in have) if have else float('nan')), per, sum(len(R[k][i]) for i in range(len(cfgs)))
    rows = sorted(((score(k), k) for k in R), key=lambda x: -x[0][0])
    print(f"{len(R)} fours of ours; win rate against each opposing four (weighted by its real games: " + ', '.join(f'{i}: {c["games"]}' for i, c in enumerate(cfgs)) + ')')
    for (s, per, n), k in rows[:15] + [x for x in rows[15:] if used[x[1]]]:
        print(f"  {s:5.1%}  lead {' + '.join(k[0]):24s} back {' + '.join(k[1]):24s} " + ' '.join(f'{p:5.1%}' for p in per) + f"  ({n} games)" + (f"   <- the bot brought it {used[k]} times" if used[k] else ''))


def confirm(d, top=6):
    """the matrix's top fours and every four the bot brought, against the same opposing fours, for a run on fresh game indices
    (rain_matrix.sh JOBS=confirm_jobs.json TAG=confirm G0=1000): the best of 90 on the same games is flattered, fresh games are not"""
    J = json.load(open(os.path.join(OUT, 'jobs.json'))); C = json.load(open(os.path.join(OUT, 'configs.json')))
    R = collections.defaultdict(list)
    for f in glob.glob(os.path.join(d, '*.json')):
        j = json.load(open(f)); R[(tuple(sorted(j['lead'])), tuple(sorted(j['back'])))] += [r['v'] for r in j.get('rows', []) if r.get('v') is not None]
    cfgs = json.load(open(os.path.join(OUT, 'cfgs.json'))); wt = [c['games'] for c in cfgs]
    def sc(k):
        per = collections.defaultdict(list)
        for f in glob.glob(os.path.join(d, '*.json')):
            j = json.load(open(f))
            if (tuple(sorted(j['lead'])), tuple(sorted(j['back']))) == k: per[j['cfg']] += [r['v'] for r in j['rows'] if r.get('v') is not None]
        return sum(wt[i] * sum(v) / len(v) for i, v in per.items() if v) / sum(wt[i] for i, v in per.items() if v)
    ranked = sorted(R, key=lambda k: -sc(k))
    used = [k for c in C for k in [(tuple(sorted(f['lead'])), tuple(sorted(f['back']))) for f in c['our_fours'] if f['games'] >= 5]]
    keep = list(dict.fromkeys(ranked[:top] + used))
    key = lambda j: (tuple(sorted(x['species'] for x in j['mine'][:2])), tuple(sorted(x['species'] for x in j['mine'][2:])))
    CJ = [j for j in J if key(j) in keep]
    json.dump(CJ, open(os.path.join(OUT, 'confirm_jobs.json'), 'w'))
    print(f"{len(CJ)} jobs: {len(keep)} fours against {len(cfgs)} opposing fours")
    for k in keep: print(f"  lead {' + '.join(k[0])}, back {' + '.join(k[1])}" + ('  (the bot brought it)' if k in used else ''))


if __name__ == '__main__':
    if sys.argv[1] == 'configs': configs(sys.argv[2:] or json.load(open(os.path.join(ROOT, 'bot', 'out', 'rain_opponents.json'))))
    elif sys.argv[1] == 'jobs': jobs(int(sys.argv[2]) if len(sys.argv) > 2 else 3)
    elif sys.argv[1] == 'report': report(sys.argv[2])
    elif sys.argv[1] == 'confirm': confirm(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 6)
