"""Empirical opponent pool (2026-10-06): real games instead of archetype models. Every side of every cached Showdown Reg M-C Bo3 game
with an open team sheet becomes one pool entry: the six with its sets (species, item, ability, moves, nature from |showteam|; stat points
are never shown, so each species gets its usual spread from regionals/smogon_mc_sets.json, else a flat 32/32/0/0/2/0-style default),
the lead pair and the four brought as actually played, the players' rating, the result, and the team's group under the core rules
(results/core_rules_both_<support>.json from cluster_opps.py rules; the current if/else archetype as a fallback name). No usernames.
  ../.venv/bin/python3 opp_pool.py build [rules json]        -> opp_pool.json (+ a summary on stdout)
  ../.venv/bin/python3 opp_pool.py jobs <myteam.json> <lead a,b> <back c,d> <n> <out jobs.json> [min rating] [group filter]
        n explicit jobs for champ battle (battle_starts.js explicit mode): our four fixed, their four from n pool entries drawn without
        replacement, weighted by rating band (>= 1500: 3, >= 1300: 2, else 1; unrated 1); the job's meta carries the entry's group.
  ../.venv/bin/python3 opp_pool.py model <group | arch:<name> | other:<name> | all> <out.json> [pairs=6] [min rating]
        the old opp_model shape for one group ({n, sets, pairs: [{pair, n, share, win, hiShare, t1, mega, back}]}: sets as
        "item|ability|Nature|moves (count/total)", t1 as "Move:rate, (switch):rate, ..." per lead, back as "Species:share, ..."), so
        t1sim.js runs on core-rule groups unchanged; hiShare = the pair's share among sides rated 1400 or more.
  ../.venv/bin/python3 opp_pool.py sixes <group | arch:<name> | other:<name> | all> <N> <out.json> [min rating]
        the N most common sixes of a group (species sets; a six's sets are the most common per species among its games), each with its
        weight (share of the group's sides), count, lead pairs and brought fours with counts: for the sheet kit's optimal-pick step.
A game whose side showed fewer than four Pokemon (it ended early) gets the missing bring slots filled from the same six's other games
when there are any, else from the unseen Pokemon at random (bring_seen says how many were real)."""
import json, os, sys, re, glob, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pro_replays import arch, base
from cluster_opps import tag, norm
HERE = os.path.dirname(os.path.abspath(__file__)); RP = os.path.join(HERE, 'replays_protect')
SM = json.load(open(os.path.join(HERE, '..', 'regionals', 'smogon_mc_sets.json')))
def spread(species, nature):
    s = SM.get(species) or SM.get(species.split('-')[0])
    if s and s.get('evs'): return s['evs']
    return [32, 32, 0, 0, 2, 0] if nature in ('Adamant', 'Jolly', 'Brave', 'Careful', 'Impish') else [32, 0, 0, 32, 2, 0]
def name_of(camel):
    """|showteam| writes names without spaces (FakeOut, SitrusBerry, Charizardite Y as CharizarditeY): put the spaces back"""
    return re.sub(r'(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d)', ' ', camel).replace('Charizardite Y', 'Charizardite Y').strip()
def sheet(line):
    out = []
    for blob in line.split(']'):
        f = blob.split('|')
        if len(f) < 6: continue
        species = (f[1] or f[0]).strip(); species = re.sub(r'-\*$', '', species)
        out.append({'species': species, 'item': name_of(f[2]), 'ability': name_of(f[3]), 'moves': [name_of(m) for m in f[4].split(',') if m], 'nature': f[5] or 'Serious'})
    return out
def parse(log):
    """per side: team sheet, lead per slot, species seen, turn-one action per lead species ("Move Name", "(switch)", "(flinched)",
    "(none)") with the foe species targeted when there is one, and the species that Mega Evolved"""
    sides = {s: {'six': None, 'lead': {}, 'seen': [], 't1': {}, 't1t': {}, 'mega': []} for s in ('p1', 'p2')}; turn = 0; win = None; names = {}
    nick = {}   # "p1a: Nick" -> species currently in that slot
    fainted = set()
    for l in log.split('\n'):
        p = l.split('|')
        if len(p) < 3: continue
        if p[1] == 'player' and len(p) > 3: names[p[2]] = p[3]
        elif p[1] == 'showteam' and p[2] in sides: sides[p[2]]['six'] = sheet('|'.join(p[3:]))
        elif p[1] in ('switch', 'drag') and p[2][:2] in sides:
            sd = sides[p[2][:2]]; sp = base(p[3]); slot = p[2][:3]
            if turn == 1 and p[1] == 'switch' and slot in sd['lead'] and sd['lead'][slot] not in sd['t1']:
                sd['t1'][sd['lead'][slot]] = '(none)' if slot in fainted else '(switch)'   # a replacement for a fainted lead is not a choice
            nick[p[2].split('|')[0]] = sp
            if sp not in sd['seen']: sd['seen'].append(sp)
            if turn == 0: sd['lead'][slot] = sp
        elif p[1] == 'move' and turn == 1 and p[2][:2] in sides:
            sd = sides[p[2][:2]]; sp = nick.get(p[2]); tgt = nick.get(p[4]) if len(p) > 4 else None
            if sp and sp not in sd['t1']:
                sd['t1'][sp] = p[3]
                if tgt and len(p) > 4 and p[4][:2] != p[2][:2]: sd['t1t'][sp] = tgt
        elif p[1] == 'faint' and p[2][:2] in sides: fainted.add(p[2][:3])
        elif p[1] == 'cant' and turn == 1 and p[2][:2] in sides:
            sd = sides[p[2][:2]]; sp = nick.get(p[2])
            if sp and sp not in sd['t1']: sd['t1'][sp] = '(flinched)' if 'flinch' in l else '(none)'
        elif p[1] == '-mega' and p[2][:2] in sides:
            sp = nick.get(p[2]); sd = sides[p[2][:2]]
            if sp and sp not in sd['mega']: sd['mega'].append(sp)
        elif p[1] == 'turn': turn = int(p[2])
        elif p[1] == 'win': win = p[2]
    for sd in sides.values():
        for sp in sd['lead'].values():
            if sp not in sd['t1']: sd['t1'][sp] = '(none)'
    winner = next((s for s, nm in names.items() if nm == win), None)
    return sides, winner, turn
def build(rules_path):
    rules = json.load(open(rules_path)) if rules_path and os.path.exists(rules_path) else []
    idx = json.load(open(os.path.join(RP, 'index.json')))
    entries = []; by_six = collections.defaultdict(list)
    for f in sorted(glob.glob(os.path.join(RP, '*.log'))):
        gid = os.path.basename(f)[:-4]
        if 'bo3' not in gid: continue
        sides, winner, turns = parse(open(f, encoding='utf-8', errors='replace').read())
        rating = (idx.get(gid) or {}).get('rating')
        for s in ('p1', 'p2'):
            sd = sides[s]
            if not sd['six'] or len(sd['six']) != 6 or len(sd['lead']) != 2: continue
            species = [m['species'] for m in sd['six']]
            lead = [sd['lead'].get(s + 'a'), sd['lead'].get(s + 'b')]
            if any(x is None or x not in species for x in lead): continue
            seen = [x for x in sd['seen'] if x in species]
            e = {'id': gid, 'side': s, 'six': sd['six'], 'lead': lead, 'seen': seen, 'rating': rating, 'won': None if winner is None else winner == s, 'turns': turns,
                 't1': {sp: sd['t1'].get(sp, '(none)') for sp in lead}, 't1t': {sp: sd['t1t'][sp] for sp in lead if sp in sd['t1t']}, 'mega': sd['mega']}
            entries.append(e); by_six[frozenset(species)].append(e)
    # fill brings to four
    rng = random.Random(0)
    for e in entries:
        species = [m['species'] for m in e['six']]; bring = list(e['seen'])[:4]; e['bring_seen'] = len(bring)
        if len(bring) < 4:
            others = collections.Counter(x for o in by_six[frozenset(species)] if o is not e for x in o['seen'] if x not in bring)
            for x, _ in others.most_common():
                if len(bring) >= 4: break
                bring.append(x)
            rest = [x for x in species if x not in bring]; rng.shuffle(rest)
            while len(bring) < 4: bring.append(rest.pop())
        e['bring'] = bring
        e['arch'] = arch([norm(x) for x in species]); e['group'] = tag(species, rules) if rules else e['arch']
    out = {'rules': rules, 'entries': entries, 'note': 'one entry per side of a cached Showdown Reg M-C Bo3 game with an open team sheet; sets from the sheet, spreads by species default; no usernames'}
    json.dump(out, open(os.path.join(HERE, 'opp_pool.json'), 'w'))
    rated = [e for e in entries if e['rating']]
    print(f"{len(entries)} entries from {len(set(e['id'] for e in entries))} games; bring fully seen {sum(e['bring_seen'] == 4 for e in entries)}, 3 seen {sum(e['bring_seen'] == 3 for e in entries)}, fewer {sum(e['bring_seen'] < 3 for e in entries)}; rated {len(rated)} (median {sorted(e['rating'] for e in rated)[len(rated) // 2] if rated else 0})")
    g = collections.Counter(e['group'] for e in entries)
    print('groups:'); [print(f"   {k:60s} {v:5d} ({100 * v / len(entries):.1f}%)") for k, v in g.most_common()]
def jobs(myteam, lead, back, n, outf, min_rating=0, group=None):
    pool = json.load(open(os.path.join(HERE, 'opp_pool.json')))['entries']
    team = json.load(open(myteam)); team = team if isinstance(team, list) else list(team.values())
    mine = [next(s for s in team if s['species'] == x) for x in lead + back]
    cand = [e for e in pool if (e['rating'] or 0) >= min_rating and (group is None or in_group(e, group))]
    w = [3 if (e['rating'] or 0) >= 1500 else 2 if (e['rating'] or 0) >= 1300 else 1 for e in cand]
    rng = random.Random(0); picked = []; idxs = list(range(len(cand)))
    while len(picked) < min(n, len(cand)):
        i = rng.choices(idxs, weights=[w[j] for j in idxs])[0]; picked.append(cand[i]); idxs.remove(i)
    J = []
    for e in picked:
        sets = {m['species']: m for m in e['six']}
        theirs = [{**sets[x], 'evs': spread(x, sets[x]['nature'])} for x in e['bring']]   # lead a, lead b, back, back as played
        J.append({'mine': mine, 'theirs': theirs, 'meta': {'pool_id': e['id'], 'pool_side': e['side'], 'group': e['group'], 'arch': e['arch'], 'rating': e['rating'], 'bring_seen': e['bring_seen']}})
    json.dump(J, open(outf, 'w')); print(f"{len(J)} jobs -> {outf} (from {len(cand)} candidates)")
def sixes(group, n, outf, min_rating=0):
    pool = json.load(open(os.path.join(HERE, 'opp_pool.json')))['entries']
    ents = [e for e in pool if in_group(e, group) and (e['rating'] or 0) >= min_rating]
    by = collections.defaultdict(list)
    for e in ents: by[frozenset(m['species'] for m in e['six'])].append(e)
    tot = len(ents); out = []
    for six, es in sorted(by.items(), key=lambda kv: -len(kv[1]))[:n]:
        sets = []
        for sp in sorted(six):
            c = collections.Counter(json.dumps(m, sort_keys=True) for e in es for m in e['six'] if m['species'] == sp)
            sets.append(json.loads(c.most_common(1)[0][0]))
        leads = collections.Counter(' + '.join(sorted(e['lead'])) for e in es); brings = collections.Counter(' + '.join(sorted(e['bring'])) for e in es if e['bring_seen'] == 4)
        out.append({'six': sets, 'count': len(es), 'weight': len(es) / tot, 'group': group, 'leads': dict(leads.most_common()), 'brings': dict(brings.most_common(8)),
                    'won': sum(1 for e in es if e['won']) / max(1, sum(1 for e in es if e['won'] is not None))})
    json.dump({'group': group, 'sides': tot, 'distinct_sixes': len(by), 'covered': sum(x['count'] for x in out) / max(1, tot), 'sixes': out}, open(outf, 'w'), indent=1)
    print(f"{group}: {tot} sides, {len(by)} distinct sixes; top {len(out)} cover {100 * sum(x['count'] for x in out) / max(1, tot):.0f}% -> {outf}")
def toid(x): return ''.join(c for c in x.lower() if c.isalnum())
def in_group(e, group):
    """group selectors: a core-rule group name; 'arch:<name>' = every entry of that pro_replays archetype; 'other:<name>' = entries no
    core rule names whose archetype is <name> (the sheets' fallback cards); 'all'"""
    if group == 'all': return True
    if group.startswith('arch:'): return e['arch'] == group[5:]
    if group.startswith('other:'): return e['group'] == 'other' and e['arch'] == group[6:]
    return e['group'] == group
def model(group, outf, pairs_n=6, min_rating=0):
    """the old opp_model shape for one group ({n, sets, pairs: [{pair, n, share, win, hiShare, t1, mega, back}]}), so t1sim.js runs on
    core-rule groups unchanged. group = a core-rule group name, 'arch:<name>' (pro_replays.arch) or 'all'."""
    pool = json.load(open(os.path.join(HERE, 'opp_pool.json')))['entries']
    ents = [e for e in pool if (e['rating'] or 0) >= min_rating and in_group(e, group)]
    N = len(ents)
    # sets: each species' most common set among the group's sheets, in the old string form
    cnt = collections.defaultdict(collections.Counter); tot = collections.Counter()
    for e in ents:
        for m in e['six']:
            key = f"{toid(m['item'])}|{toid(m['ability'])}|{m['nature']}|{'/'.join(sorted(toid(x) for x in m['moves']))}"
            cnt[m['species']][key] += 1; tot[m['species']] += 1
    sets = {sp: f"{c.most_common(1)[0][0]} ({c.most_common(1)[0][1]}/{tot[sp]})" for sp, c in cnt.items()}
    by_pair = collections.defaultdict(list)
    for e in ents: by_pair[' + '.join(sorted(e['lead']))].append(e)
    hi = [e for e in ents if (e['rating'] or 0) >= 1400]
    pairs = []
    for pair, es in sorted(by_pair.items(), key=lambda kv: -len(kv[1]))[:pairs_n]:
        n = len(es); leads = pair.split(' + ')
        t1 = {}
        for sp in leads:
            c = collections.Counter(e['t1'].get(sp, '(none)') for e in es)
            t1[sp] = ', '.join(f"{a}:{v / n:.2f}" for a, v in c.most_common())
        mega = collections.Counter(sp for e in es for sp in e['mega'] if sp in leads)
        back = collections.Counter(x for e in es for x in e['bring'] if x not in leads)
        won = [e['won'] for e in es if e['won'] is not None]
        pairs.append({'pair': pair, 'n': n, 'share': round(n / N, 4), 'win': round(sum(won) / len(won), 3) if won else None,
                      'hiShare': round(sum(1 for e in hi if ' + '.join(sorted(e['lead'])) == pair) / len(hi), 4) if hi else None,
                      't1': t1, 'mega': dict(mega), 'back': ', '.join(f"{x}:{v / n:.2f}" for x, v in back.most_common(6))})
    out = {'n': N, 'group': group, 'sets': sets, 'pairs': pairs}
    json.dump(out, open(outf, 'w'), indent=1); print(f"{group}: {N} sides, {len(by_pair)} lead pairs; top {len(pairs)} cover {100 * sum(p['n'] for p in pairs) / max(1, N):.0f}% -> {outf}")
if __name__ == '__main__':
    if sys.argv[1] == 'model': model(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 6, int(sys.argv[5]) if len(sys.argv) > 5 else 0)
    elif sys.argv[1] == 'sixes': sixes(sys.argv[2], int(sys.argv[3]), sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 0)
    elif sys.argv[1] == 'build': build(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'results', 'core_rules_both_100.json'))
    elif sys.argv[1] == 'jobs': jobs(sys.argv[2], sys.argv[3].split(','), sys.argv[4].split(','), int(sys.argv[5]), sys.argv[6], int(sys.argv[7]) if len(sys.argv) > 7 else 0, sys.argv[8] if len(sys.argv) > 8 else None)
