"""Mechanics notes for the opponent cards (notes.json), from the turn-one plans: a note only where the mechanic is in play in at least a
quarter (Armor Tail on our side: half) of the card's simulated leads.
  python3 card_notes.py      (from sheets/frankfurt-156/)  -> prints the notes; --write writes notes.json"""
import json, sys, collections
t = json.load(open('t1.json'))['plans']; M = json.load(open('../../sheetkit/opponents/opp_model.json'))
D = json.load(open('../../native/champions_data.json'))
WEATHER = {'drought': 'sun', 'sandstream': 'sand', 'snowwarning': 'snow'}
PRIO_BLOCK = {'armortail': 'Armor Tail', 'queenlymajesty': 'Queenly Majesty', 'dazzling': 'Dazzling'}

def st(card, sp):
    """(ability, Mega ability or '', moves) of their set"""
    s = M[card]['sets'].get(sp)
    if not s: return '', '', []
    item, ab, _, mv = s.split(' (')[0].split('|')
    mega = (D['items'].get(item, {}).get('megaStone') or {}).values()
    mab = next((D['species'][m.lower().replace('-', '')]['abilities']['0'].lower().replace(' ', '') for m in mega), '')
    return ab, mab, mv.split('/')

S = collections.defaultdict(collections.Counter); who = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
for key, v in t.items():
    card, ours, theirs = key.split('||'); their = theirs.split(' + '); our = ours.split('+')
    S[card]['tot'] += v['share']; sets = {sp: st(card, sp) for sp in their}
    if 'Farigiraf' in our and any('fakeout' in s[2] for s in sets.values()): S[card]['fo'] += v['share']
    if {'Basculegion', 'Golisopod'} & set(our):
        blk = [(sp, a if a in PRIO_BLOCK or a == 'psychicsurge' else m) for sp, (a, m, _) in sets.items()
               if a in PRIO_BLOCK or m in PRIO_BLOCK or a == 'psychicsurge']
        if blk: S[card]['prio'] += v['share']
        for x in blk: who[card]['prio'][x] += v['share']
    wx = [(sp, WEATHER.get(a) or WEATHER.get(m), bool(WEATHER.get(m) and not WEATHER.get(a))) for sp, (a, m, _) in sets.items()
          if WEATHER.get(a) or WEATHER.get(m)]
    if wx: S[card]['wx'] += v['share']
    for x in wx: who[card]['wx'][x] += v['share']

def name(sp): return sp.replace('-F', '').replace('-Alola', ' (Alola)')
notes = {}
for card, s in S.items():
    f = {k: s[k] / s['tot'] for k in ('fo', 'prio', 'wx')}; out = []
    if f['wx'] >= 0.25:
        sp, w, mega = who[card]['wx'].most_common(1)[0][0]
        out.append(f"Their {name(sp)}&rsquo;s {w} replaces your rain {'when it Mega Evolves' if mega else 'when it comes in'}, and Pelipper "
                   "coming back in resets it: the weather set last stays. "
                   + ("In sun, Hurricane hits half the time and Water moves do half." if w == 'sun' else "Outside rain, Hurricane can miss and Electro Shot charges a turn."))
    if f['fo'] >= 0.5: out.append('Farigiraf&rsquo;s Armor Tail keeps their Fake Out off both of you.')
    if f['prio'] >= 0.25:
        b = sorted(who[card]['prio'])
        by = ' and '.join(sorted({f"their {name(sp)}&rsquo;s " + ('Psychic Terrain' if a == 'psychicsurge' else PRIO_BLOCK[a]) for sp, a in b}))
        out.append(f"{by[0].upper() + by[1:]} block{'' if ' and ' in by else 's'} your Aqua Jet and Sucker Punch"
                   + (" into anything on the ground." if all(a == 'psychicsurge' for _, a in b) else '.'))
    if out: notes[card] = ' '.join(out)
for c, n in notes.items(): print(f'{c}: {n}')
if '--write' in sys.argv: json.dump(notes, open('notes.json', 'w'), indent=1, ensure_ascii=False); print(f'notes.json: {len(notes)} cards')
