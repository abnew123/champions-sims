"""Mechanics notes for the opponent cards (notes.json), from the turn-one plans: a note only where the mechanic is in play against at
least a quarter (Fake Out: half) of the card's simulated leads. At most two per card.
  python3 card_notes.py      (from sheets/frankfurt-239/)  -> prints the notes; --write writes notes.json"""
import json, sys, collections
sys.path.insert(0, '../../sheetkit')
from page import dex, idf
t = json.load(open('t1.json'))['plans']; M = json.load(open('../../sheetkit/opponents/opp_model.json')); D = dex()

def forme(card, sp):
    """their Pokemon as it plays: (types, ability id, move ids), after Mega Evolution if it holds its stone"""
    s = M[card]['sets'].get(sp)
    if not s: return [], '', [], sp
    item, ab, _, mv = s.split(' (')[0].split('|'); sd = D['species'].get(idf(sp))
    if sd is None: return [], ab, mv.split('/'), sp            # a species the damage data lacks: its set's ability and moves still count
    mega = (D['items'].get(item) or {}).get('megaStone') or {}
    if sd['name'] in mega: sd = D['species'][idf(mega[sd['name']])]; ab = idf(sd['abilities']['0'])
    return sd['types'], ab, mv.split('/'), shown(sd['name'])

def shown(n):
    """Charizard-Mega-Y -> Mega Charizard Y"""
    if '-Mega' not in n: return n
    b, _, x = n.partition('-Mega'); return f"Mega {b}{' ' + x.strip('-') if x else ''}"

WEATHER = {'drought': 'sun', 'sandstream': 'sand', 'snowwarning': 'snow'}
TERRAIN = {'grassysurge': 'Grassy Terrain', 'psychicsurge': 'Psychic Terrain', 'electricsurge': 'Electric Terrain', 'mistysurge': 'Misty Terrain'}
BLOCK = {'armortail': 'Armor Tail', 'queenlymajesty': 'Queenly Majesty', 'dazzling': 'Dazzling'}
S = collections.defaultdict(collections.Counter); who = collections.defaultdict(lambda: collections.defaultdict(set)); lead = {}; four = {}
for key, v in t.items():
    card, ours, theirs = key.split('||'); our = ours.split('+'); lead[card] = our; four[card] = set(our) | set(v['back'])
    S[card]['tot'] += v['share']; seen = set()
    for sp in theirs.split(' + '):
        types, ab, mv, nm = forme(card, sp)
        for k, ok in (('fo', 'fakeout' in mv), ('dark', 'Dark' in types), ('psy', ab == 'psychicsurge'), ('block', ab in BLOCK),
                      ('terrain', ab in TERRAIN), *((w, WEATHER.get(ab) == w) for w in ('sun', 'sand', 'snow'))):
            if ok:
                if k not in seen: S[card][k] += v['share']; seen.add(k)
                who[card][k].add({'terrain': TERRAIN.get(ab), 'block': f"{nm}&rsquo;s {BLOCK.get(ab)}"}.get(k, nm))

def names(card, k): return ' and '.join(sorted(who[card][k]))
notes = {}
for card, s in S.items():
    f = {k: s[k] / s['tot'] for k in s if k != 'tot'}; our = lead[card]; out = []
    for w, rest in (('sun', 'your Water moves are halved, Hurricane hits half the time, Weather Ball turns Fire'),
                    ('sand', 'Weather Ball turns Rock'), ('snow', 'Weather Ball turns Ice')):
        if f.get(w, 0) >= 0.25:
            out.append(f'{names(card, w)}&rsquo;s {w} replaces your rain: {rest}, and Swift Swim and Electro Shot&rsquo;s one-turn fire are off '
                       'until Pelipper comes back in.')
    if 'Indeedee-F' in our and f.get('fo', 0) >= 0.5:
        out.append('Your Indeedee&rsquo;s Psychic Terrain keeps their Fake Out off ' +
                   ('Indeedee, but not off Pelipper, which flies.' if 'Pelipper' in our else 'both of you.'))
    if 'Grimmsnarl' in our:
        why = [x for x, k in ((f'Dark types ({names(card, "dark")})', 'dark'), ('anything on the ground while their Indeedee&rsquo;s terrain is up', 'psy'),
                              (f'their side while {names(card, "block")} is in', 'block')) if f.get(k, 0) >= 0.25]
        if why: out.append('Grimmsnarl&rsquo;s Parting Shot fails into ' + (why[0] if len(why) == 1 else ', into '.join(why[:-1]) + ' and into ' + why[-1])
                           + '; screens still go up.')
    if 'Metagross' in four[card] and f.get('terrain', 0) >= 0.25:
        out.append(f'Their {names(card, "terrain")} also lets Metagross&rsquo;s Steel Roller work, and Steel Roller ends it.')
    if out: notes[card] = ' '.join(out[:2])
for c, n in notes.items(): print(f'{c}: {n}')
if '--write' in sys.argv: json.dump(notes, open('notes.json', 'w'), indent=1, ensure_ascii=False); print(f'notes.json: {len(notes)} cards')
