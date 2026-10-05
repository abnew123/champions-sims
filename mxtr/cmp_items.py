# Compare one-on-one grid columns across items. Value per cell: counter 1, check .8, wall .3, guess p*.8, roll p*.6, lost 0.
# Weighted two ways: every threat equally, and by usage (op.gg % or, for ladder-rank rows, 2%; the six added Trick Room threats 2%).
import json
use = json.load(open('../team-sheet.html.usage.json'))
def w(f): u = use.get(f); return (u if isinstance(u, (int, float)) else 2.0) if u is not None else 2.0
def val(c):
    v = c['v']; p = (c.get('pct') or 0) / 100
    return {'counter': 1.0, 'check': 0.8, 'wall': 0.3, 'lost': 0.0}.get(v, p * (0.8 if v == 'guess' else 0.6))
lab = lambda c: {'counter':'CTR','check':'chk','guess':'?','wall':'wall','roll':'~','lost':'-'}[c['v']]+(str(c['pct']) if c['v'] in('roll','guess') else '')+('*' if c.get('dep') else '')
PUB = {tr: json.load(open(f'gx_cells_{tr}.json')) for tr in ('tr', 'notr')}
SETS = {'Kingambit': [('Chople (now)', None), ('Black Glasses', 'BlackGlasses'), ('Life Orb', 'LifeOrb'), ('Occa', 'Occa'), ('Focus Sash', 'kgsash')],
        'Torkoal': [('Charcoal (now)', None), ('Life Orb', 'LifeOrb'), ('Leftovers', 'Leftovers')],
        'Hatterene': [('Life Orb (now)', None), ('Fairy Feather', 'FairyFeather'), ('Focus Sash', 'FocusSash'), ('Sitrus', 'Sitrus')],
        'Farigiraf': [('Sitrus (now)', None), ('Colbur', 'Colbur')]}
def load(mon, tag, tr):
    if tag is None: return {k: v for k, v in PUB[tr].items() if k.endswith('|' + mon)}
    if tag == 'kgsash': return json.load(open(f'gx_cells_{tr}_kg_Brave_sash.json'))
    return json.load(open(f'gx_cells_{tr}_it_{mon}_{tag}.json'))
for mon, variants in SETS.items():
    print(f'\n######## {mon}')
    for tr in ('tr', 'notr'):
        base = load(mon, None, tr); keys = list(base)
        print(f"  {'Trick Room up' if tr == 'tr' else 'No Trick Room'}:")
        for name, tag in variants:
            d = load(mon, tag, tr)
            eq = sum(val(d[k]) for k in keys) / len(keys); uw = sum(w(k.split('|')[0]) * val(d[k]) for k in keys) / sum(w(k.split('|')[0]) for k in keys)
            ch = [f"{k.split('|')[0]} {lab(base[k])}->{lab(d[k])}" for k in keys if lab(base[k]) != lab(d[k])]
            print(f"    {name:16s} score {100*eq:5.1f} (usage-weighted {100*uw:5.1f})  " + ('; '.join(ch) if tag else ''))
