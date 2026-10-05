"""Replay -> what the engine needs to rebuild the position at the start of every turn (positions.js turns these into engine states).
Hindsight and guesses, as the handoff allows for step 1: each side's four are the Pokemon that appeared anywhere in the game; sets are the
open team sheet (item, ability, nature, moves); stat points are not on the sheet, so they are the species' most common spread
(regionals/smogon_mc_sets.json) when its nature agrees with the sheet, else a plain spread that fits the nature.
specs(rid, log) -> (list of position specs, reason the game was skipped or '').
usage: python3 evalbar/spots.py <out.json> <replay id> [more ids]     (ids as in the replay cache, without .log)"""
import os, sys, json
import common as C, replay as R
E = json.load(open(os.path.join(C.MAIN, 'native', 'engine_data_spot.json')))
SM = json.load(open(os.path.join(C.REPO, 'regionals', 'smogon_mc_sets.json')))
MV = json.load(open(os.path.join(C.PSSIM, 'dex_moves_types.json')))['moves']
toid = R.toid; ORDER = ['hp', 'atk', 'def', 'spa', 'spd', 'spe']
def mega_of(species, item): return (E['items'].get(toid(item), {}).get('megaStone') or {}).get(species)
def evs_for(species, item, nature, moves):
    nat = E['natures'].get(toid(nature), {}); plus = nat.get('plus')
    base = SM.get(mega_of(species, item) or '') or SM.get(species)
    if base and (base['nature'] == nature or E['natures'].get(toid(base['nature']), {}).get('plus') == plus): return list(base['evs'])
    cat = [MV.get(toid(m), {}).get('cat') for m in moves]; att = 'atk' if cat.count('Physical') >= cat.count('Special') else 'spa'
    ev = dict.fromkeys(ORDER, 0)
    if plus == 'spe': ev.update({'spe': 32, att: 32, 'hp': 2})
    elif plus in ('atk', 'spa'): ev.update({plus: 32, 'hp': 32, 'spd': 2})
    elif plus in ('def', 'spd'): ev.update({'hp': 32, plus: 32, ('spd' if plus == 'def' else 'def'): 2})
    elif base: return list(base['evs'])
    else: ev.update({'hp': 32, att: 32, 'spe': 2})
    return [ev[k] for k in ORDER]
def missing(st):
    """parts of a set the engine data does not have"""
    out = []
    if toid(st['species']) not in E['species']: out.append(st['species'])
    mg = mega_of(st['species'], st['item'])
    if mg and toid(mg) not in E['species']: out.append(mg)
    if st['item'] and toid(st['item']) not in E['items']: out.append(st['item'])
    if toid(st['ability']) not in E['abilities']: out.append(st['ability'])
    return out + [m for m in st['moves'] if toid(m) not in E['moves']]
def specs(rid, log):
    g = R.parse(log)
    if g['odd']: return [], 'mechanic not rebuilt: ' + ', '.join(g['odd'])
    sets = {}; guess = {'p1': [], 'p2': []}
    for sd in ('p1', 'p2'):
        seen = set()
        for m in g['final'][sd]['mons']:
            key = toid(m['sp']) if toid(m['sp']) in g['sheets'][sd] else toid(m['sp'].split('-')[0])
            sh = g['sheets'][sd].get(key)
            if not sh: return [], 'no team sheet entry'
            seen.add(key); st = {'species': m['sp'], 'item': sh['item'], 'ability': sh['ability'], 'nature': sh['nature'], 'moves': sh['moves']}
            if missing(st): return [], 'not in the engine data: ' + ', '.join(missing(st))
            st['evs'] = evs_for(m['sp'], sh['item'], sh['nature'], sh['moves']); sets[(sd, m['sp'])] = st
        # a brought Pokemon that never came in is unknown even in hindsight: stand in the first unused team-sheet entries the engine knows
        megas = sum(bool(mega_of(sets[(sd, m['sp'])]['species'], sets[(sd, m['sp'])]['item'])) for m in g['final'][sd]['mons'])
        rest = [sh for key, sh in g['sheets'][sd].items() if key not in seen]
        rest.sort(key=lambda sh: bool(mega_of(sh['species'], sh['item'])) and megas > 0)          # prefer not to add a second Mega Stone holder
        for sh in rest:
            if len(g['final'][sd]['mons']) + len(guess[sd]) >= 4: break
            st = {'species': sh['species'], 'item': sh['item'], 'ability': sh['ability'], 'nature': sh['nature'], 'moves': sh['moves']}
            if missing(st): continue
            st['evs'] = evs_for(sh['species'], sh['item'], sh['nature'], sh['moves']); guess[sd].append(st)
        if len(g['final'][sd]['mons']) + len(guess[sd]) < 4: return [], 'a brought Pokemon never appeared and no stand-in is in the engine data'
    out = []
    for s in g['steps']:
        if s['turn'] < 1: continue
        sides = []
        for sd in ('p1', 'p2'):
            S = s['state'][sd]; ms = S['mons']
            order = sorted(ms, key=lambda m: (0 if m['pos'] == 'a' else 1 if m['pos'] == 'b' else 2 if not m['f'] else 3))
            mons = [{**sets[(sd, m['sp'])], 'mega': m['mega'], 'hpPct': m['hp'], 'fainted': m['f'], 'status': m['st'], 'slept': m['slept'], 'boosts': m['b'],
                     'itemNow': '' if m['gone'] else m['item'], 'moved': m['moved'], 'stall': m['stall'], 'lock': m['lock'], 'vol': m['vol'], 'onField': bool(m['pos']),
                     'last': m['last'], 'volarg': m['volarg']} for m in order]
            mons += [{**st, 'mega': False, 'hpPct': 100, 'fainted': False, 'status': '', 'slept': 0, 'boosts': {}, 'itemNow': st['item'], 'moved': False, 'stall': False,
                      'lock': '', 'vol': [], 'onField': False, 'last': '', 'volarg': {}, 'standIn': True} for st in guess[sd]]
            sides.append({'mons': mons, 'tailwind': S['tailwind'], 'screens': S['screens'], 'hazards': S['hazards']})
        f = s['state']['field']
        acts = [[s['acts'].get(sd + x) for x in 'ab'] for sd in ('p1', 'p2')]
        out.append({'name': f"{rid} t{s['turn']}", 'turn': s['turn'], 'sides': sides, 'acts': acts, 'perish': s['state']['perish'], 'standIns': len(guess['p1']) + len(guess['p2']),
                    'field': {'weather': [f['weather'], f['wturns']] if f['weather'] else None, 'terrain': [f['terrain'], f['tturns']] if f['terrain'] else None, 'trickroom': f['tr']}})
    return out, ''
if __name__ == '__main__':
    allspecs = []
    for rid in sys.argv[2:]:
        sp, why = specs(rid, open(os.path.join(C.LOGS, rid + '.log')).read())
        print(f"{rid}: {len(sp)} positions" + (f" (skipped: {why})" if why else '')); allspecs += sp
    json.dump(allspecs, open(sys.argv[1], 'w'))
