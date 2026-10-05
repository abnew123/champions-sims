# Sixth-slot candidates on the one-on-one grid: team coverage = best answer among the fixed four plus the candidate, per threat.
import json
use = json.load(open('../team-sheet.html.usage.json'))
def w(f): u = use.get(f); return (u if isinstance(u, (int, float)) else 2.0) if u is not None else 2.0
RANK = {'counter': 5, 'check': 4, 'guess': 3, 'wall': 2, 'roll': 1, 'lost': 0}
def val(c):
    v = c['v']; p = (c.get('pct') or 0) / 100
    return {'counter': 1.0, 'check': 0.8, 'wall': 0.3, 'lost': 0.0}.get(v, p * (0.8 if v == 'guess' else 0.6))
lab = lambda c: {'counter':'CTR','check':'chk','guess':'?','wall':'wall','roll':'~','lost':'-'}[c['v']]+(str(c['pct']) if c['v'] in('roll','guess') else '')+('*' if c.get('dep') else '')
FOUR = ["Blastoise","Torkoal","Farigiraf","Kingambit"]
CANDS = ["Hatterene","Sylveon","Incineroar","Armarouge","Sinistcha","Grimmsnarl","Milotic","Archaludon","M-Gardevoir"]
out = {}
for tr in ('tr','notr'):
    g = json.load(open(f'gx_cells_{tr}.json')); foes = []
    for k in g:
        f = k.split('|')[0]
        if f not in foes: foes.append(f)
    col = {c: ({f: g[f'{f}|{c}'] for f in foes} if c == 'Hatterene' else {k.split('|')[0]: v for k, v in json.load(open(f'gx_cells_{tr}_cand_{c}.json')).items()}) for c in CANDS}
    W = sum(w(f) for f in foes)
    base = {f: max((g[f'{f}|{m}'] for m in FOUR), key=val) for f in foes}
    b_sc = sum(w(f) * val(base[f]) for f in foes) / W; b_n = sum(RANK[base[f]['v']] >= 4 for f in foes)
    print(f"\n== {'Trick Room up' if tr == 'tr' else 'No Trick Room'}: the four without a sixth: team score {100*b_sc:.1f}, {b_n}/35 threats with a counter or check")
    print(f"   {'sixth':12s} {'own':>5s} {'team':>6s} {'gain':>6s} {'answered':>9s}   fills / upgrades")
    rows = []
    for c in CANDS:
        own = sum(w(f) * val(col[c][f]) for f in foes) / W
        best = {f: max([base[f], col[c][f]], key=val) for f in foes}
        sc = sum(w(f) * val(best[f]) for f in foes) / W; n = sum(RANK[best[f]['v']] >= 4 for f in foes)
        up = [f"{f} {lab(col[c][f])}" for f in foes if val(col[c][f]) > val(base[f]) + 1e-9 and RANK[col[c][f]['v']] >= 4 and RANK[base[f]['v']] < 4]
        rows.append((sc, c, own, n, up)); out.setdefault(c, {})[tr] = (sc, own, n)
    for sc, c, own, n, up in sorted(rows, reverse=True):
        print(f"   {c:12s} {100*own:5.1f} {100*sc:6.1f} {100*(sc-b_sc):+6.1f} {n:>6d}/35   {'; '.join(up)}")
json.dump(out, open('cands_summary.json', 'w'))
