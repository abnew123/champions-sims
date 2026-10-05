"""Indeedee-slot study summary (2026-10-03): for each team (current six, or a candidate in Indeedee-F's slot) and archetype, the best
lead by lead score (tr_final_m_<name>.json from sp_lead_cmp.py) and the best back pair from the other four by 2v2 win share
(results/sp_base for pairs without the slot; results/sp_<name> for the slot's pairs), with Trick Room up and down weighted equally.
Archetype-weighted totals at the bottom.
usage: python3 sp_team_cmp.py <name> [...]        (name "base" = current six; others = the candidate tags)"""
import json, glob, sys, os, itertools, collections
SLOT = os.environ.get('SLOT', 'Indeedee-F')   # the team member being replaced
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
SIX = ['Blastoise', 'Torkoal', 'Indeedee-F', 'Farigiraf', 'Kingambit', 'Incineroar']
LABEL = {'base': 'Indeedee-F (now)', 'ibase': 'Indeedee-F (now)', 'indatk': 'Indeedee-F +Psychic', 'indot': 'Indeedee-F Own Tempo', 'sinis': 'Sinistcha', 'hatt': 'Hatterene', 'rilla': 'Rillaboom', 'rilla2': 'Rillaboom (100% moves) for Indeedee', 'rillaX': 'Rillaboom (100% moves) for Incineroar', 'xbase': 'Incineroar (now)'}
def v2(dirs):
    """(arch, frozenset pair, tr up) -> weighted win share over their pairs"""
    acc = collections.defaultdict(lambda: [0.0, 0.0])
    for d in dirs:
        for f in glob.glob(d + '/*.json'):
            r = json.load(open(f))
            if r['v'] is None: continue
            k = (r['arch'], frozenset(r['mine']), r['K'] > 0); acc[k][0] += r['w'] * r['v']; acc[k][1] += r['w']
    return {k: a / b for k, (a, b) in acc.items() if b}
base2 = v2(['results/sp_base'])
tot = {}
for name in sys.argv[1:]:
    slot = v2([f'results/sp_{name}']) if name != 'base' else {}
    V = {k: (slot[k] if SLOT in k[1] and k in slot else val) for k, val in base2.items()}
    V.update(slot)
    D = json.load(open(f'tr_final_m_{name}.json'))
    lt = bt = 0.0; rows = []
    for a, w in SH.items():
        lead, _, _, score, _ = max(D['leads'][a]['all']['vals'], key=lambda v: v[3])
        rest = [m for m in SIX if m not in lead.split('+')]
        bp = max(itertools.combinations(rest, 2), key=lambda p: (V.get((a, frozenset(p), True), 0) + V.get((a, frozenset(p), False), 0)))
        bv = (V.get((a, frozenset(bp), True), 0) + V.get((a, frozenset(bp), False), 0)) / 2
        lt += w * score; bt += w * bv
        rows.append(f"  {a[:28]:28s} lead {lead.replace(SLOT, 'SLOT'):24s} {100*score:5.1f} | back {'+'.join(bp).replace(SLOT, 'SLOT'):24s} {100*bv:5.1f}")
    tot[name] = (lt / sum(SH.values()), bt / sum(SH.values()))
    print(f'\n== {LABEL.get(name, name)}  (SLOT = this Pokemon)'); print('\n'.join(rows))
print('\narchetype-weighted: best-lead score | best back pair 2v2 win share (Trick Room up/down averaged)')
for n, (l, b) in tot.items(): print(f'  {LABEL.get(n, n):22s} {100*l:6.2f} | {100*b:6.2f}')
