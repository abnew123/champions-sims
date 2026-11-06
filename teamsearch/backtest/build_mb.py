"""M-B to M-C self-play backtest (the user, 2026-11-06), step 2: from the M-B replays (fetch_mb.py), with no M-C data, build under
backtest/:
  mb_pool.json        one entry per side of each cached M-B Bo3 game with an open team sheet (pool_window.py's shape; "player" numbers
                      distinct players within this file only; no names)
  mb_field.json       the starting field: M-B's most common sixes over the last FIELD_DAYS days, one vote per player (at least
                      MIN_PLAYERS, at most N_FIELD), each as 6 grid ids (each species' most common set among that six's sheets)
  mb_swap_pool.json   the climb's catalog in swap_pool.json's shape: the formes on >= MIN_USE of M-B players' teams, per forme the item
                      clusters with >= 25% of its sets (max 2) with their most common nature, ability and moves, plus item-clause
                      fallbacks (build_sets.py's rules); and M-C's new species (NEW, Vice's list of the 34) with blind sets (blind())
  mb_blind.json       how each blind set was chosen; prior_zero.json: the new base species, for TS_PRIOR_ZERO
  cells_mb.txt        grid ids without one-on-one cells
Spreads: sheets don't show them; L.fill_spread fills them from Smogon's August 2026 Reg M-B Bo3 stats (TS_MOVESET, required here), else
the nature's role default; never September's M-C stats. New sets join grid_sets.json under new ids (existing ids never change).
  TS_MOVESET=backtest/smogon_mb_2026-08_moveset.txt python3 backtest/build_mb.py
"""
import json, os, sys, glob, random, datetime, collections, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); TS = os.path.dirname(HERE); ROOT = os.path.dirname(TS)
sys.path.insert(0, TS); sys.path.insert(0, os.path.join(ROOT, 'pssim'))
import sets_lib as L
import build_lowelo_starts as B
from build_meta_candidates import gid_of
from opp_pool import parse
from pro_replays import arch
from cluster_opps import tag, norm
RP = os.path.join(HERE, 'replays_mb'); RULES = json.load(open(os.path.join(ROOT, 'pssim', 'results', 'core_rules_both_100.json')))
FIELD_DAYS, MIN_PLAYERS, N_FIELD, MIN_USE = 14, 3, 16, 0.03
NEW = ['Wigglytuff', 'Persian', 'Persian-Alola', 'Farfetch’d', 'Mr. Mime', 'Swalot', 'Salamence', 'Gogoat', 'Golisopod', 'Rillaboom',
       'Cinderace', 'Inteleon', 'Thievul', 'Toxtricity', 'Toxtricity-Low-Key', 'Grapploct', 'Perrserker', 'Sirfetch’d', 'Pincurchin',
       'Indeedee', 'Indeedee-F', 'Arboliva', 'Squawkabilly', 'Mabosstiff', 'Baxcalibur']        # Squawkabilly: one plumage stands for four
# generic game knowledge for blind sets (no M-C data): moves no sensible day-one set runs, and one Protect-like move per set
EXCLUDE = {'Last Resort', 'Belch', 'Focus Punch', 'Future Sight', 'Doom Desire', 'Dream Eater', 'Synchronoise', 'Fling', 'Natural Gift',
           'Spit Up', 'Stockpile', 'Swallow', 'Endeavor', 'Counter', 'Mirror Coat', 'Metal Burst', 'Bide', 'Snore', 'Sleep Talk', 'Outrage',
           'Petal Dance', 'Thrash', 'Raging Fury', 'Final Gambit', 'Memento', 'Self-Destruct', 'Explosion', 'Misty Explosion', 'Struggle',
           'Rest', 'Curse', 'Frustration', 'Return', 'Echoed Voice', 'Round', 'Rollout', 'Ice Ball', 'Fury Cutter', 'Avalanche', 'Revenge',
           'Payback', 'Assurance', 'Steel Beam', 'Mind Blown', 'Chloroblast', 'Shell Trap', 'Beak Blast'}
PROTECTS = ['Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Baneful Bunker', 'Silk Trap', 'Burning Bulwark', 'Obstruct']
NEW_MEGA = ['Absol-Mega-Z', 'Salamence-Mega', 'Garchomp-Mega-Z', 'Lucario-Mega-Z', 'Golisopod-Mega', 'Baxcalibur-Mega']
day = lambda t: datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d')
forme = lambda s: L.battle_forme(s['species'], s['item'])

def pool():
    """pool_window.py's entries from the M-B cache"""
    idx = json.load(open(os.path.join(RP, 'index.json'))); entries = []; by_six = collections.defaultdict(list); players = {}
    for f in sorted(glob.glob(os.path.join(RP, '*bo3-*.log'))):
        gid = os.path.basename(f)[:-4]; t = (idx.get(gid) or {}).get('time')
        if not t: continue
        log = open(f, encoding='utf-8', errors='replace').read(); sides, winner, turns = parse(log)
        who = {p[2]: p[3].strip().lower() for p in (l.split('|') for l in log.split('\n') if l.startswith('|player|')) if len(p) > 3 and p[3]}
        for s in ('p1', 'p2'):
            sd = sides[s]
            if not sd['six'] or len(sd['six']) != 6 or len(sd['lead']) != 2: continue
            species = [m['species'] for m in sd['six']]
            lead = [sd['lead'].get(s + 'a'), sd['lead'].get(s + 'b')]
            if any(x is None or x not in species for x in lead): continue
            e = {'id': gid, 'side': s, 'six': sd['six'], 'lead': lead, 'seen': [x for x in sd['seen'] if x in species], 'rating': idx[gid].get('rating'),
                 'won': None if winner is None else winner == s, 'turns': turns, 'mega': sd['mega'], 'day': day(t),
                 'player': players.setdefault(who.get(s, gid + s), len(players))}
            entries.append(e); by_six[frozenset(species)].append(e)
    players.clear()
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
        e['bring'] = bring; e['arch'] = arch([norm(x) for x in species]); e['group'] = tag(species, RULES)
    return entries

def ok_set(s): return bool(s.get('moves')) and bool(s.get('nature')) and s.get('species')

def upstream_learnsets(names):
    """{name: move ids} from Showdown's current Champions learnsets (learnsets_champions_upstream.ts, fetched 2026-11-06): M-C's new
    species learn moves the pre-M-C data lacks (Rillaboom's Fake Out). Learnsets come with an announcement; usage doesn't."""
    import re
    s = open(os.path.join(HERE, 'learnsets_champions_upstream.ts')).read(); out = {}
    for n in names:
        sid = L.idf(n.split('-Mega')[0]) if '-Mega' in n else L.idf(n)
        m = re.search(r'\n\t' + sid + r': \{\s*learnset: \{(.*?)\n\t\t\}', s, re.S)
        if m: out[n] = re.findall(r'\n\t\t\t(\w+):', m.group(1))
        else: print('no upstream learnset for', n)
    return out

def dexdump(names, over):
    tmp = os.path.join(HERE, '.dex_in.json'); tov = os.path.join(HERE, '.dex_over.json'); out = os.path.join(HERE, 'dex_mb.json')
    json.dump(sorted(set(names)), open(tmp, 'w'), ensure_ascii=False); json.dump(over, open(tov, 'w'), ensure_ascii=False)
    subprocess.run(['node', os.path.join(HERE, 'dexdump.js'), tmp, out, tov], check=True, capture_output=True); os.remove(tmp); os.remove(tov)
    return json.load(open(out))

def priors(sets, dd):
    """from M-B sets only: p(move) = share of sets that run it among sets whose species can learn it (>= 20 such sets), and the
    items by role (support: two or more status moves besides Protect; offense: the rest), mega stones and one-species items left out"""
    learn, used = collections.Counter(), collections.Counter(); items = {'support': collections.Counter(), 'offense': collections.Counter()}
    for s in sets:
        d = dd.get(forme(s)) or dd.get(s['species'])
        if not d: continue
        for m in d['moves']:
            learn[m] += 1; used[m] += m in s['moves']
        it = L.DEX['items'].get(L.idf(s['item'] or ''), {}) or {}
        if s['item'] and not it.get('megaStone') and not it.get('itemUser'):
            items[role(s['moves'], d)][s['item']] += 1
    return {m: used[m] / n for m, n in learn.items() if n >= 20}, items

def role(moves, d): return 'support' if sum(1 for m in moves if m in d['moves'] and d['moves'][m]['cat'] == 'Status' and m != 'Protect') >= 2 else 'offense'

def attack_value(m, mv, d):
    if mv['cat'] == 'Status' or not mv['bp']: return None
    st = d['stats']; hits = mv['multihit']; hits = (3 if isinstance(hits, list) else hits) or 1
    v = mv['bp'] * hits * (1.5 if mv['type'] in d['types'] else 1.0) * (st['atk'] if mv['cat'] == 'Physical' else st['spa']) * min(mv['acc'], 100) / 100
    v *= 1.2 if mv['target'] in ('allAdjacentFoes',) else 0.9 if mv['target'] == 'allAdjacent' else 1.0
    v *= 0.4 if mv['recharge'] else 0.5 if mv['charge'] else 0.3 if mv['selfdestruct'] else 0.85 if mv['recoil'] else 1.0
    return v * (1.1 if mv['pri'] > 0 else 1.0)

def blind(name, d, base_d, p, items):
    """M-C's new species with no M-C data: two sets per forme, from moves the engine runs, not in EXCLUDE, attacks at >= 80% accuracy
    and no negative priority, one Protect-like move (the most popular in M-B). 'balanced': the four moves with the best score, a move's
    score being its M-B popularity among species that learn it (status), or for attacks the larger of that and half that plus half
    its damage value against the species' best, popularity scaled by the move's attacking stat over the species' better one (0.3
    popularity when no M-B species learns it), one attack per type, at least one STAB
    attack. 'offense': Protect and the three best-scoring attacks, one per type, at least one STAB. Ability: Showdown's highest-rated. Item: a Mega's stone, else M-B's
    most common item for the set's role (no Choice item with a status move). Nature: + the attacking stat, or + Speed when base Speed
    >= 80; Speed-lowering when base Speed <= 50; + the matching defence for support sets."""
    eng = lambda m: L.idf(m) in B.ENG['moves'] and m not in B.UNPORTED and m not in EXCLUDE
    mv = {m: x for m, x in d['moves'].items() if eng(m) and (x['cat'] == 'Status' or (x['acc'] >= 80 and x['pri'] >= 0))}
    pr = [m for m in PROTECTS if m in mv]; prot = max(pr, key=lambda m: (p.get(m, 0.0), m == 'Protect')) if pr else None
    for m in pr:
        if m != prot: mv.pop(m)
    av = {m: attack_value(m, x, d) for m, x in mv.items()}; av = {m: v for m, v in av.items() if v}
    top = max(av.values()) if av else 1.0; an = {m: v / top for m, v in av.items()}
    st = d['stats']; fit = lambda m: (st['atk'] if mv[m]['cat'] == 'Physical' else st['spa']) / max(st['atk'], st['spa'])
    score = {m: max(p.get(m, 0.0) * fit(m), 0.5 * an[m] + 0.5 * p.get(m, 0.3) * fit(m)) if m in an else p.get(m, 0.05) for m in mv}
    stab = lambda m: m in an and mv[m]['type'] in d['types']
    def pick(order, n=4):
        out, types = [], set()
        for m in order:
            if m in an and mv[m]['type'] in types: continue
            out.append(m); types |= {mv[m]['type']} if m in an else set()
            if len(out) == n: break
        if out and not any(stab(m) for m in out) and any(stab(m) for m in an):
            best = max((m for m in an if stab(m)), key=lambda m: an[m]); worst = min((m for m in out if m in an), key=lambda m: score[m], default=out[-1])
            out[out.index(worst)] = best
        return out
    balanced = pick(sorted(mv, key=lambda m: (-score[m], m)))
    offense = ([prot] if prot else []) + pick(sorted(an, key=lambda m: (-score[m], m)), 4 - bool(prot))
    ab_d = base_d or d
    ability = max(ab_d['abilities'], key=lambda a: (ab_d['abilities'][a] or 0, -list(ab_d['abilities']).index(a)))
    phys = st['atk'] >= st['spa']; out = []
    for kind, moves in (('balanced', balanced), ('offense', offense)):
        if len(moves) < 4 or any(set(moves) == set(o['moves']) for o in out): continue
        r = role(moves, d)
        if d['requiredItem']: cands = [d['requiredItem']]
        else:
            status = any(mv[m]['cat'] == 'Status' for m in moves)
            cands = [i for i, _ in items[r].most_common() if not (status and i.startswith('Choice'))][:3]
        if st['spe'] <= 50: nat = 'Brave' if phys else 'Quiet'
        elif r == 'support': nat = 'Careful' if phys else 'Calm'
        elif st['spe'] >= 80: nat = 'Jolly' if phys else 'Timid'
        else: nat = 'Adamant' if phys else 'Modest'
        for k, it in enumerate(cands):
            out.append(dict(species=(base_d or d)['name'], item=it, ability=ability, nature=nat, moves=list(moves), kind=kind, fallback=k > 0))
    return out

def main():
    assert os.environ.get('TS_MOVESET', '').endswith('smogon_mb_2026-08_moveset.txt'), 'run with TS_MOVESET=backtest/smogon_mb_2026-08_moveset.txt'
    E = pool(); last = max(e['day'] for e in E); first = min(e['day'] for e in E)
    fstart = (datetime.date.fromisoformat(last) - datetime.timedelta(days=FIELD_DAYS - 1)).isoformat()
    note = (f'one entry per side of a cached public Showdown Reg M-B Bo3 game with an open team sheet, {first} to {last} (local dates); '
            'sets from the sheet; "player" numbers distinct players within this file only; no usernames')
    json.dump({'rules': RULES, 'entries': E, 'note': note, 'window': [first, last]}, open(os.path.join(HERE, 'mb_pool.json'), 'w'))
    full = [e for e in E if all(ok_set(s) for s in e['six'])]
    newset = {L.idf(x) for x in NEW} | {L.idf(x.split('-Mega')[0]) for x in NEW_MEGA if x.split('-Mega')[0] in NEW}
    leaked = sorted({s['species'] for e in full for s in e['six'] if L.idf(s['species']) in newset})
    if leaked: print('warning: M-C species on M-B sheets:', leaked)
    # one set per (player, forme, set) for the catalog and priors
    per = {}
    for e in full:
        for s in e['six']:
            s = L.normalize(s); per[(e['player'], json.dumps(s, sort_keys=True))] = (e['player'], s)
    nplay = len({e['player'] for e in full}); sets = [s for _, s in per.values()]
    users = collections.defaultdict(set)
    for pl, s in per.values(): users[forme(s)].add(pl)
    dd = dexdump([forme(s) for s in sets] + [s['species'] for s in sets] + NEW + NEW_MEGA + [x.split('-Mega')[0] for x in NEW_MEGA],
                 upstream_learnsets(NEW + NEW_MEGA + [x.split('-Mega')[0] for x in NEW_MEGA if x.split('-Mega')[0] in NEW]))
    p, items = priors(sets, dd)
    gid = {L.set_key({k: v for k, v in s.items() if k != 'regional_count'}): g for g, s in B.G.items()}
    nper = collections.Counter()
    for g in B.G:
        fid, n = g.rsplit('#', 1)
        if n.isdigit(): nper[fid] = max(nper[fid], int(n))
    # catalog (build_sets.py's rules on M-B sets)
    by = collections.defaultdict(list)
    for s in sets: by[forme(s)].append(s)
    swap = []
    for fm, ss in sorted(by.items(), key=lambda kv: -len(users[kv[0]])):
        if len(users[fm]) < MIN_USE * nplay: continue
        its = collections.Counter(s['item'] for s in ss)
        clusters = [i for i, c in its.most_common() if c >= 0.25 * len(ss)][:2] or [its.most_common(1)[0][0]]
        one_item = its.most_common(1)[0][1] >= 0.85 * len(ss)
        fallbacks = [] if one_item else [i for i, c in its.most_common() if i and i not in clusters and c >= 0.05 * len(ss)]
        for it in clusters + fallbacks:
            cs = [s for s in ss if s['item'] == it]; nat = collections.Counter(s['nature'] for s in cs).most_common(1)[0][0]
            cs2 = [s for s in cs if s['nature'] == nat]; ab = collections.Counter(s['ability'] for s in cs2).most_common(1)[0][0]
            mv = collections.Counter(tuple(sorted(s['moves'])) for s in cs2).most_common(1)[0][0]
            ex = next(s for s in cs2 if tuple(sorted(s['moves'])) == mv)
            f = B.full(dict(species=ex['species'], item=it, ability=ab, nature=nat, moves=list(ex['moves'])))
            if not B.runnable(f): continue
            swap.append(dict(forme=fm, use=round(100 * len(users[fm]) / nplay, 1), cluster_share=round(100 * len(cs) / len(ss)),
                             gid=gid_of(f, gid, nper), fallback=it in fallbacks, one_item=one_item))
    nb = len(swap); why = {}
    for name in NEW + NEW_MEGA:
        d = dd.get(name)
        if not d: print('no data for', name); continue
        base_d = dd.get(name.split('-Mega')[0]) if '-Mega' in name else None
        for s in blind(name, d, base_d, p, items):
            f = B.full({k: v for k, v in s.items() if k not in ('kind', 'fallback')})
            if not B.runnable(f): print('  not runnable:', name, f['moves'], f['ability']); continue
            g = gid_of(f, gid, nper); why[g] = dict(forme=name, kind=s['kind'], fallback=s['fallback'])
            swap.append(dict(forme=forme(f), use=0.0, cluster_share=50, gid=g, fallback=s['fallback'], one_item=bool(d['requiredItem']), blind=True))
    # starting field
    six_players = collections.defaultdict(set)
    for e in full:
        if e['day'] >= fstart: six_players[frozenset(s['species'] for s in e['six'])].add(e['player'])
    fplay = len({e['player'] for e in full if e['day'] >= fstart}); field = {}
    for six, ps in sorted(six_players.items(), key=lambda t: (-len(t[1]), sorted(t[0]))):
        if len(field) == N_FIELD or len(ps) < MIN_PLAYERS: break
        cnt = collections.defaultdict(collections.Counter)
        for e in full:
            if e['day'] >= fstart and frozenset(s['species'] for s in e['six']) == six:
                for s in e['six']: cnt[s['species']][json.dumps(L.normalize(s), sort_keys=True)] += 1
        team = [B.full(json.loads(cnt[sp].most_common(1)[0][0])) for sp in sorted(six)]
        if not all(B.runnable(f) for f in team): print('  field six skipped (engine):', sorted(six)); continue
        field[f"mb{len(field) + 1}"] = dict(gids=[gid_of(f, gid, nper) for f in team], players=len(ps), share=len(ps) / fplay,
                                           species=[forme(f) for f in team])
    if os.environ.get('DRY') != '1': json.dump(B.G, open(B.GPATH, 'w'), indent=0)        # DRY=1: a test run on a partial fetch
    json.dump(swap, open(os.path.join(HERE, 'mb_swap_pool.json'), 'w'), indent=1)
    json.dump(field, open(os.path.join(HERE, 'mb_field.json'), 'w'), indent=1)
    json.dump(dict(priors={m: round(x, 3) for m, x in sorted(p.items(), key=lambda t: -t[1])}, items={r: c.most_common(8) for r, c in items.items()},
                   sets={g: dict(why[g], set=B.G[g]) for g in why}), open(os.path.join(HERE, 'mb_blind.json'), 'w'), indent=1, ensure_ascii=False)
    json.dump(sorted({L.DEX['species'].get(L.idf(x), {}).get('name', x) for x in NEW} | {x.split('-Mega')[0] for x in NEW_MEGA if x.split('-Mega')[0] in NEW}),
              open(os.path.join(HERE, 'prior_zero.json'), 'w'), ensure_ascii=False)
    has = lambda g: all(os.path.exists(os.path.join(TS, 'mx', 'out', t, g.replace('/', '_') + '.json')) for t in ('tr', 'notr'))
    need = sorted({x['gid'] for x in swap} | {g for t in field.values() for g in t['gids']}); miss = [g for g in need if not has(g)]
    open(os.path.join(TS, 'cells_mb.txt'), 'w').write('\n'.join(miss) + ('\n' if miss else ''))
    print(f"{len(E)} entries ({len(full)} with full sheets) from {first} to {last}, {nplay} players; catalog {nb} M-B sets "
          f"({len({x['forme'] for x in swap[:nb]})} formes) + {len(swap) - nb} blind; field {len(field)} sixes "
          f"({100 * sum(t['share'] for t in field.values()):.1f}% of players since {fstart}); {len(miss)} sets need cells")
    for n, t in field.items(): print(f"  {n} {100 * t['share']:4.1f}%  " + ', '.join(t['species']))

if __name__ == '__main__': main()
