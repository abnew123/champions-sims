"""Replay -> what the engine needs to rebuild the position at the start of every turn (positions.js turns these into engine states).
Hindsight and guesses, as the handoff allows for step 1: each side's four are the Pokemon that appeared anywhere in the game; sets are the
open team sheet (item, ability, nature, moves); stat points are not on the sheet, so they are the species' most common spread
(regionals/smogon_mc_sets.json) when its nature agrees with the sheet, else the most used spread with the sheet's nature in the Smogon
stats (spreads.ranked), else a plain spread that fits the nature. A brought Pokemon that never
came in is replaced by a stand-in from the unused team-sheet entries. Moves and items the engine data lacks are dropped from the set (listed
in the spec's 'dropped'); a species, form or ability it lacks rules the game out.
specs(rid, log) -> (list of position specs, reason the game was skipped or ''); each turn's position through battlestate.py, as the
live page and the bot build theirs.
usage: python3 evalbar/spots.py <out.json> <replay id> [more ids]     (ids as in the replay cache, without .log)"""
import os, sys, json
import common as C, replay as R
E = json.load(open(os.path.join(C.MAIN, 'native', 'engine_data_spot.json')))
SM = json.load(open(os.path.join(C.REPO, 'regionals', 'smogon_mc_sets.json')))
MV = json.load(open(os.path.join(C.PSSIM, 'dex_moves_types.json')))['moves']
toid = R.toid; ORDER = ['hp', 'atk', 'def', 'spa', 'spd', 'spe']
def mega_of(species, item): return (E['items'].get(toid(item), {}).get('megaStone') or {}).get(species)
def evs_for(species, item, nature, moves):
    import spreads
    if spreads.FITTED and spreads.fitted(species, nature): return spreads.fitted(species, nature)   # the eval bar's: fitted to the replays
    nat = E['natures'].get(toid(nature), {}); plus = nat.get('plus')
    base = SM.get(mega_of(species, item) or '') or SM.get(species)
    if base and (base['nature'] == nature or E['natures'].get(toid(base['nature']), {}).get('plus') == plus): return list(base['evs'])
    import spreads                                                          # the most used listed spread with this nature (2026-10-11)
    r = spreads.ranked(species, nature, item)
    if r: return list(r[0][1])
    cat = [MV.get(toid(m), {}).get('cat') for m in moves]; att = 'atk' if cat.count('Physical') >= cat.count('Special') else 'spa'
    ev = dict.fromkeys(ORDER, 0)
    if plus == 'spe': ev.update({'spe': 32, att: 32, 'hp': 2})
    elif plus in ('atk', 'spa'): ev.update({plus: 32, 'hp': 32, 'spd': 2})
    elif plus in ('def', 'spd'): ev.update({'hp': 32, plus: 32, ('spd' if plus == 'def' else 'def'): 2})
    elif base: return list(base['evs'])
    else: ev.update({'hp': 32, att: 32, 'spe': 2})
    return [ev[k] for k in ORDER]
def missing(st):
    """parts of a set the engine data does not have: (species, forms and abilities, which rule the game out; moves and items, which are dropped)"""
    hard = []
    if toid(st['species']) not in E['species']: hard.append(st['species'])
    mg = mega_of(st['species'], st['item'])
    if mg and toid(mg) not in E['species']: hard.append(mg)
    if toid(st['ability']) not in E['abilities']: hard.append(st['ability'])
    return hard, [m for m in st['moves'] if toid(m) not in E['moves']] + ([st['item']] if st['item'] and toid(st['item']) not in E['items'] else [])
def fit_set(st, dropped):
    """the set as the engine can play it: unknown moves and an unknown item are left out (and listed in dropped); None if that cannot be done"""
    hard, soft = missing(st)
    if hard: return None, hard
    moves = [m for m in st['moves'] if toid(m) in E['moves']]
    if not moves: return None, soft
    dropped += soft
    item = st['item'] if toid(st['item']) in E['items'] else ''
    return {**st, 'moves': moves, 'item': item, 'evs': evs_for(st['species'], st['item'], st['nature'], st['moves'])}, []
def specs(rid, log):
    g = R.parse(log)
    if g['odd']: return [], 'mechanic not rebuilt: ' + ', '.join(g['odd'])
    formes = {m['forme'] for s in g['steps'] if s['state'] for sd in ('p1', 'p2') for m in s['state'][sd]['mons'] if m['forme']}
    if any(toid(x) not in E['species'] for x in formes): return [], 'not in the engine data: ' + ', '.join(sorted(formes))
    sets = {}; guess = {'p1': [], 'p2': []}; dropped = []
    for sd in ('p1', 'p2'):
        seen = set()
        for m in g['final'][sd]['mons']:
            key = toid(m['sp']) if toid(m['sp']) in g['sheets'][sd] else toid(m['sp'].split('-')[0])
            sh = g['sheets'][sd].get(key)
            if not sh: return [], 'no team sheet entry'
            seen.add(key); st, bad = fit_set({'species': m['sp'], 'item': sh['item'], 'ability': sh['ability'], 'nature': sh['nature'], 'moves': sh['moves']}, dropped)
            if not st: return [], 'not in the engine data: ' + ', '.join(bad)
            sets[(sd, m['sp'])] = st
        # a brought Pokemon that never came in is unknown even in hindsight: stand in the first unused team-sheet entries the engine knows
        megas = sum(bool(mega_of(sets[(sd, m['sp'])]['species'], sets[(sd, m['sp'])]['item'])) for m in g['final'][sd]['mons'])
        rest = [sh for key, sh in g['sheets'][sd].items() if key not in seen]
        rest.sort(key=lambda sh: bool(mega_of(sh['species'], sh['item'])) and megas > 0)          # prefer not to add a second Mega Stone holder
        for sh in rest:
            if len(g['final'][sd]['mons']) + len(guess[sd]) >= 4: break
            st, bad = fit_set({'species': sh['species'], 'item': sh['item'], 'ability': sh['ability'], 'nature': sh['nature'], 'moves': sh['moves']}, [])
            if st: guess[sd].append(st)
        if len(g['final'][sd]['mons']) + len(guess[sd]) < 4: return [], 'a brought Pokemon never appeared and no stand-in is in the engine data'
    import battlestate as BS                                                # the builder every reader uses (it imports this module)
    out = []
    for s in g['steps']:
        if s['turn'] < 1: continue
        order = {sd: BS.order(s['state'][sd]) for sd in ('p1', 'p2')}
        sides = [BS.side(s['state'][sd], [BS.mon(m, sets[(sd, m['sp'])]) for m in order[sd]] + [BS.fresh(st, True) for st in guess[sd]]) for sd in ('p1', 'p2')]
        out.append(BS.spec(f"{rid} t{s['turn']}", s, sides, BS.acts(s, order), len(guess['p1']) + len(guess['p2']), dropped=dropped))
    return out, ''
if __name__ == '__main__':
    allspecs = []
    for rid in sys.argv[2:]:
        sp, why = specs(rid, open(os.path.join(C.LOGS, rid + '.log')).read())
        print(f"{rid}: {len(sp)} positions" + (f" (skipped: {why})" if why else '')); allspecs += sp
    json.dump(allspecs, open(sys.argv[1], 'w'))
