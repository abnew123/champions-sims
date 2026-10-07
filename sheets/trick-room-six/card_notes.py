"""Mechanics notes for the opponent cards (notes.json), from the turn-one plans: a note only where the mechanic decides the turn-one
clicks against at least a quarter (Armor Tail on our side: half) of the card's simulated leads.
  python3 card_notes.py      (from sheets/trick-room-six/)  -> prints the notes; --write writes notes.json"""
import json, sys, collections
t = json.load(open('t1.json'))['plans']; M = json.load(open('../../sheetkit/opponents/opp_model.json'))

def st(card, sp):
    s = M[card]['sets'].get(sp)
    if not s: return '', []
    _, ab, _, mv = s.split(' (')[0].split('|'); return ab, mv.split('/')

S = collections.defaultdict(collections.Counter); lead = {}
for key, v in t.items():
    card, ours, theirs = key.split('||'); their = theirs.split(' + '); our = ours.split('+'); lead[card] = our
    S[card]['tot'] += v['share']
    if 'Farigiraf' in our and any('fakeout' in st(card, sp)[1] for sp in their): S[card]['fo'] += v['share']
    if any(st(card, sp)[0] == 'armortail' for sp in their): S[card]['armor'] += v['share']
    if any(st(card, sp)[0] == 'psychicsurge' for sp in their): S[card]['terrain'] += v['share']

notes = {}
for card, s in S.items():
    f = {k: s[k] / s['tot'] for k in ('fo', 'armor', 'terrain')}; our = lead[card]
    prio = [m for m, who in (('Fake Out', {'Blastoise', 'Incineroar'}), ('Sucker Punch', {'Kingambit'})) if who & set(our)]
    prio = ' and '.join(prio); out = []
    fo, armor, terrain = f['fo'] >= 0.5, bool(prio) and f['armor'] >= 0.25, bool(prio) and f['terrain'] >= 0.25
    if fo and armor: out.append(f'Armor Tail works both ways: yours keeps their Fake Out off both of you, and theirs blocks your {prio} while their Farigiraf is in.')
    elif fo: out.append('Farigiraf&rsquo;s Armor Tail keeps their Fake Out off both of you.')
    if armor and terrain: out.append(f'Their Farigiraf&rsquo;s Armor Tail and their Indeedee&rsquo;s Psychic Terrain both block your {prio}.')
    elif armor and not fo: out.append(f'Their Farigiraf&rsquo;s Armor Tail blocks your {prio} while it is in.')
    elif terrain: out.append(f'Their Indeedee&rsquo;s Psychic Terrain blocks your {prio} into anything on the ground.')
    if out: notes[card] = ' '.join(out)
for c, n in notes.items(): print(f'{c}: {n}')
if '--write' in sys.argv: json.dump(notes, open('notes.json', 'w'), indent=1, ensure_ascii=False); print(f'notes.json: {len(notes)} cards')
