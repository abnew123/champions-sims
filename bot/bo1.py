"""Playing without open team sheets (Bo1; 2026-10-12, the user: guess items, natures and moves the way spreads are guessed, and update
them as the game shows more). The opponent's six species are known from team preview (|poke| lines). Each one starts as its commonest
whole set on real open sheets (bot/set_prior.py: item, ability, nature, moves), then narrows to the commonest set consistent with what the
game has revealed: moves it used, its item (shown, consumed, knocked off, Mega Evolution, item-triggered damage or healing), its ability
(announced or named as a [from] source). With no consistent whole set the guess is built part by part: the revealed parts plus the
commonest of the rest. The guess is written into the log as an ordinary |showteam| line, so everything downstream (spread inference,
sheet picks, the position builder) works as with open sheets; spreads are then inferred as usual.
  reveals(lines, side) -> {species id: {'moves', 'item', 'ability'}}
  guess(species, rev) -> (species, item, ability, nature, moves)          (packed names, as sheets write them)
  inject(lines, side, my_sets=None) -> lines with |showteam| for side (guessed) and, given our sets, for us (known), if absent"""
import os, re, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
toid = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
pack = lambda s: re.sub(r'[^A-Za-z0-9]', '', s or '')
_P = None
def prior():
    global _P
    if _P is None: _P = json.load(open(os.path.join(ROOT, 'bot', 'out', 'set_prior.json')))
    return _P
def base(sp): return re.sub(r'-Mega(-[XYZ])?$', '', sp)
def reveals(lines, side):
    """per opposing species (base species id): moves it used, its original item, its ability; 'mega' if it Mega Evolved"""
    nick = {}; out = {}
    def mon(ref):
        if not ref or not ref.startswith(side) or ': ' not in ref: return None
        sp = nick.get(ref.split(': ', 1)[1])
        if sp is None: return None
        return out.setdefault(toid(sp), {'moves': set(), 'item': None, 'ability': None, 'mega': False})
    for l in lines:
        p = l.split('|')
        if len(p) < 3: continue
        k = p[1]; tags = {x.split(']', 1)[0][1:]: x.split(']', 1)[1].strip() for x in p[3:] if x.startswith('[') and ']' in x}
        if k in ('switch', 'drag', 'replace') and len(p) > 3 and p[2].startswith(side):
            nick[p[2].split(': ', 1)[1]] = base(p[3].split(',')[0])
        elif k == 'move' and len(p) > 3:
            m = mon(p[2])
            if m is not None and ('from' not in tags or tags['from'].endswith('lockedmove')): m['moves'].add(toid(p[3]))
        elif k == '-mega' and len(p) > 4:
            m = mon(p[2])
            if m is not None: m['item'] = toid(p[4]); m['mega'] = True
        elif k == '-enditem' and len(p) > 3:
            m = mon(p[2])
            if m is not None and m['item'] is None: m['item'] = toid(p[3])
        elif k == '-item' and len(p) > 3:
            m = mon(p[2])                                             # Frisk shows the real item; Trick / Switcheroo hands over a new one
            if m is not None and m['item'] is None and not tags.get('from', '').lower().startswith('move:'): m['item'] = toid(p[3])
        elif k == '-ability' and len(p) > 3:
            m = mon(p[2])
            if m is not None and not m['mega'] and m['ability'] is None and 'from' not in tags: m['ability'] = toid(p[3])
        f = tags.get('from', '')
        if f.startswith('item:') or f.startswith('ability:'):
            m = mon(tags.get('of') or p[2]) if (tags.get('of') or '').startswith(side) or ('of' not in tags) else None
            if m is not None:
                what = toid(f.split(':', 1)[1])
                if f.startswith('item:') and m['item'] is None: m['item'] = what
                if f.startswith('ability:') and m['ability'] is None and not m['mega']: m['ability'] = what
    return out
def guess(species, rev=None):
    """the commonest whole set consistent with the reveals, else part by part; None if the species was never seen on a sheet"""
    P = prior().get(toid(species))
    if not P: return None
    rev = rev or {'moves': set(), 'item': None, 'ability': None}
    ok = lambda s: (rev['item'] is None or toid(s[1][0]) == rev['item']) and (rev['ability'] is None or toid(s[1][1]) == rev['ability']) \
        and rev['moves'] <= {toid(m) for m in s[2]}
    for n, (item, ab, nat), moves in P['sets']:
        if ok((n, (item, ab, nat), moves)): return (P['species'], item, ab, nat, list(moves))
    pick = lambda key, want: next((x for x, _ in P[key] if want is None or toid(x) == want), want or (P[key][0][0] if P[key] else ''))
    item = pick('item', rev['item']); ab = pick('ability', rev['ability']); nat = P['nature'][0][0] if P['nature'] else 'Serious'
    moves = [m for m, _ in P['move'] if toid(m) in rev['moves']]
    moves += [m for m, _ in P['move'] if m not in moves][:max(0, 4 - len(moves))]
    return (P['species'], item, ab, nat, moves[:4] if len(rev['moves']) <= 4 else moves)
def packed(sets):
    return ']'.join(f"{sp}||{item}|{ab}|{','.join(moves)}|{nat}||||||50|" for sp, item, ab, nat, moves in sets)
def inject(lines, side, my_sets=None, my_side=None):
    """the log with a guessed |showteam| for `side` (and our own, known, for my_side) when the log has none; lines as a list"""
    have = {l.split('|')[2] for l in lines if l.startswith('|showteam|') and len(l.split('|')) > 2}
    add = []
    if side not in have:
        six = [l.split('|')[3].split(',')[0] for l in lines if l.startswith(f'|poke|{side}|')]
        rv = reveals(lines, side)
        sets = [g for g in (guess(sp, rv.get(toid(base(sp)))) for sp in six) if g]
        if sets: add.append(f'|showteam|{side}|{packed(sets)}')
    if my_sets and my_side and my_side not in have:
        add.append(f"|showteam|{my_side}|{packed([(s['species'], pack(s['item']), pack(s['ability']), s['nature'], [pack(m) for m in s['moves']]) for s in my_sets])}")
    if not add: return lines
    k = max((i for i, l in enumerate(lines) if l.startswith('|poke|') or l.startswith('|teampreview')), default=-1)
    return lines[:k + 1] + add + lines[k + 1:]
