"""Shared helpers for teamsearch: Smogon M-C moveset stats, regional open team sheets, spread filling, set keys.

Open team sheets show species, item, ability, nature and moves but not stat points; spreads are filled from Smogon's
M-C moveset stats (Sep 2026): the most common spread with the same nature for the battle forme (Mega forme for a
Mega Stone holder), else a role default (see fill_spread).
"""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
DEX = json.load(open(os.path.join(ROOT, 'native', 'champions_data.json')))
def idf(s): return re.sub(r'[^a-z0-9]', '', s.lower())

def parse_moveset(path=os.path.join(ROOT, 'regionals', 'smogon_mc_2026-09_moveset.txt')):
    """{species: {'Spreads': [(nature, [6 SP], pct)], 'Items': [(name, pct)], 'Moves': ..., 'Abilities': ..., 'count': raw}}"""
    out, cur, sec = {}, None, None
    lines = open(path).read().splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r'^\| (.+?) +\|$', ln)
        if not m: continue
        txt = m.group(1).strip()
        prev = lines[i - 1] if i else ''
        if prev.startswith('+') and i + 1 < len(lines) and lines[i + 1].startswith('+') and not txt.startswith(('Raw count', 'Avg', 'Viability')) \
                and txt not in ('Abilities', 'Items', 'Spreads', 'Moves', 'Teammates', 'Checks and Counters'):
            cur = txt; out[cur] = {'Spreads': [], 'Items': [], 'Moves': [], 'Abilities': []}; sec = None; continue
        if cur is None: continue
        if txt in ('Abilities', 'Items', 'Spreads', 'Moves', 'Teammates', 'Checks and Counters'): sec = txt; continue
        if txt.startswith('Raw count'): out[cur]['count'] = int(txt.split(':')[1]); continue
        if sec in ('Abilities', 'Items', 'Moves'):
            mm = re.match(r'^(.+?) ([\d.]+)%$', txt)
            if mm and mm.group(1) != 'Other': out[cur][sec].append((mm.group(1), float(mm.group(2))))
        elif sec == 'Spreads':
            mm = re.match(r'^(\w+):([\d/]+) ([\d.]+)%$', txt)
            if mm: out[cur]['Spreads'].append((mm.group(1), [int(x) for x in mm.group(2).split('/')], float(mm.group(3))))
    return out

MS = parse_moveset()
NATURES = DEX['natures']

def battle_forme(species, item):
    """name of the forme it fights as (Mega forme for a Mega Stone holder)"""
    ms = (DEX['items'].get(idf(item or ''), {}) or {}).get('megaStone') or {}
    if ms: return next(iter(ms.values()))
    return DEX['species'].get(idf(species), {}).get('name', species)      # (a few species aren't in the engine data)

def fill_spread(species, item, nature, moves):
    """(SP spread, how it was chosen)"""
    forme = battle_forme(species, item)
    for nm in (forme, DEX['species'].get(idf(species), {}).get('name', species)):
        for nat, sp, pct in MS.get(nm, {}).get('Spreads', []):
            if nat == nature: return sp, f"Smogon {nm} {nat} {pct}%"
    # role default from the nature: +stat gets 32, and Speed 32 unless the nature lowers Speed (Trick Room)
    n = NATURES.get(idf(nature), {})
    plus, minus = n.get('plus'), n.get('minus')
    cats = [DEX['moves'][idf(m)]['category'] for m in moves if idf(m) in DEX['moves']]
    main = plus if plus in ('atk', 'spa') else ('atk' if cats.count('Physical') >= cats.count('Special') else 'spa')
    order = ['hp', 'atk', 'def', 'spa', 'spd', 'spe']
    sp = [0] * 6
    if minus == 'spe' or plus in ('def', 'spd'):
        sp[0] = 32; sp[order.index(main)] = 32 if plus not in ('def', 'spd') else 0
        if plus in ('def', 'spd'): sp[order.index(plus)] = 32
        sp[order.index('spd' if plus != 'spd' else 'def')] += 2
    else:
        sp[order.index(main)] = 32; sp[5] = 32; sp[0] = 2
    return sp, f"default for {nature}"

SPECIES_ALIAS = {'Alolan Ninetales': 'Ninetales-Alola', 'Alolan Persian': 'Persian-Alola', 'Eternal Flower Floette': 'Floette-Eternal',
                 'Female Indeedee': 'Indeedee-F', 'Female Meowstic': 'Meowstic-F', 'Heat Rotom': 'Rotom-Heat', 'Wash Rotom': 'Rotom-Wash',
                 'Hisuian Arcanine': 'Arcanine-Hisui', 'Hisuian Goodra': 'Goodra-Hisui', 'Hisuian Zoroark': 'Zoroark-Hisui',
                 'Paldean Tauros Aqua Breed': 'Tauros-Paldea-Aqua'}

def normalize(s):
    """an open-team-sheet set in Showdown names (empty move slots and the parser's 'Held Item:' glitch dropped)"""
    out = dict(s)
    out['species'] = SPECIES_ALIAS.get(s['species'], s['species'])
    out['moves'] = [m for m in s['moves'] if m and m != '-']
    if not s.get('item') or s['item'] == 'Held Item:': out['item'] = ''
    out['nature'] = (s.get('nature') or 'Serious').replace('Naïve', 'Naive')
    return out

def set_key(s):
    """identity of a set for caching: species, item, ability, nature, sorted moves, spread"""
    return '|'.join([s['species'], s.get('item') or '', s.get('ability') or '', s.get('nature') or '', ','.join(sorted(s['moves'])),
                     '/'.join(map(str, s['evs']))])
