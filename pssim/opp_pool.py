"""Empirical opponent pool (2026-10-06): real games instead of archetype models. Every side of every cached Showdown Reg M-C Bo3 game
with an open team sheet becomes one pool entry: the six with its sets (species, item, ability, moves, nature from |showteam|; stat points
are never shown, so each species gets its usual spread from regionals/smogon_mc_sets.json, else a flat 32/32/0/0/2/0-style default),
the lead pair and the four brought as actually played, the players' rating, the result, and the team's group under the core rules
(results/core_rules_both_<support>.json from cluster_opps.py rules; the current if/else archetype as a fallback name). No usernames.
  ../.venv/bin/python3 opp_pool.py build [rules json]        -> opp_pool.json (+ a summary on stdout)
  ../.venv/bin/python3 opp_pool.py jobs <myteam.json> <lead a,b> <back c,d> <n> <out jobs.json> [min rating] [group filter]
        n explicit jobs for champ battle (battle_starts.js explicit mode): our four fixed, their four from n pool entries drawn without
        replacement, weighted by rating band (>= 1500: 3, >= 1300: 2, else 1; unrated 1); the job's meta carries the entry's group.
  ../.venv/bin/python3 opp_pool.py sixes <group | all> <N> <out.json> [min rating]
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
    sides = {'p1': {'six': None, 'lead': {}, 'seen': []}, 'p2': {'six': None, 'lead': {}, 'seen': []}}; turn = 0; win = None; names = {}
    for l in log.split('\n'):
        p = l.split('|')
        if len(p) < 3: continue
        if p[1] == 'player' and len(p) > 3: names[p[2]] = p[3]
        elif p[1] == 'showteam' and p[2] in sides: sides[p[2]]['six'] = sheet('|'.join(p[3:]))
        elif p[1] in ('switch', 'drag') and p[2][:2] in sides:
            sd = sides[p[2][:2]]; sp = base(p[3])
            if sp not in sd['seen']: sd['seen'].append(sp)
            if turn == 0: sd['lead'][p[2][:3]] = sp
        elif p[1] == 'turn': turn = int(p[2])
        elif p[1] == 'win': win = p[2]
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
            e = {'id': gid, 'side': s, 'six': sd['six'], 'lead': lead, 'seen': seen, 'rating': rating, 'won': None if winner is None else winner == s, 'turns': turns}
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
    cand = [e for e in pool if (e['rating'] or 0) >= min_rating and (group is None or e['group'] == group)]
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
    ents = [e for e in pool if (group == 'all' or e['group'] == group) and (e['rating'] or 0) >= min_rating]
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
if __name__ == '__main__':
    if sys.argv[1] == 'sixes': sixes(sys.argv[2], int(sys.argv[3]), sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 0)
    elif sys.argv[1] == 'build': build(sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'results', 'core_rules_both_100.json'))
    elif sys.argv[1] == 'jobs': jobs(sys.argv[2], sys.argv[3].split(','), sys.argv[4].split(','), int(sys.argv[5]), sys.argv[6], int(sys.argv[7]) if len(sys.argv) > 7 else 0, sys.argv[8] if len(sys.argv) > 8 else None)
