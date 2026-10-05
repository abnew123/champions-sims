"""Back-row scorer: for each archetype and sheet lead, rank the six possible back pairs by how well the brought four
answers what that archetype brings, using the one-on-one matchup grid (mxtr/gx_cells_*).

usage: python3 bring.py [tr_leads_data.json] [--all]
  env GX_TR / GX_NOTR: grid files (default mxtr/gx_cells_{tr,notr}_inc.json, plus *_ext.json if present)

Model (a heuristic, not a simulation):
  - Their four = each common opposing lead pair (weighted by its share) + its replay back-row rates, scaled to two slots.
  - Each foe gets my four's answer value: 0.7 x best answer + 0.3 x second best (a backup if the best one goes down).
    Cell values: counter 1, check 0.75, roll = its win %, wall/guess 0.5, lost 0. Support-only Indeedee-F counts 0.
  - Trick Room weight for the game after turn one: 0.6 x P(TR up after turn one) + 0.3 if a setter is in the back.
  - Speed: the turn-one sims credit Trick Room by tanh((their mean Speed - mine)/15); changing the back changes
    "mine". dTR is that change in win-% points at the lead's TR rate.
"""
import json, os, sys, itertools, math, collections
R = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(R, *a)
SIX = ['Incineroar', 'Indeedee-F', 'Farigiraf', 'Torkoal', 'Kingambit', 'Blastoise']
SETTERS = {'Indeedee-F', 'Farigiraf'}
SHORT = {'Indeedee': 'Indeedee-F'}
VAL = {'counter': 1.0, 'check': 0.75, 'wall': 0.5, 'guess': 0.5, 'lost': 0.0}

def load_grid(f):
    g = json.load(open(f))
    ext = f.replace('.json', '_ext.json')
    if os.path.exists(ext): g.update(json.load(open(ext)))
    return g
GT = load_grid(os.environ.get('GX_TR', P('mxtr/gx_cells_tr_inc.json')))
GN = load_grid(os.environ.get('GX_NOTR', P('mxtr/gx_cells_notr_inc.json')))
FOES = {k.split('|')[0] for k in GT}

def cell(g, foe, mine):
    c = g.get(f'{foe}|{mine}')
    if c is None: return 0.0
    return c['roll'] / 100 if c['v'] == 'roll' else VAL.get(c['v'], 0.5)

def grid_names(sp, mega_frac):
    """replay species -> [(grid name, weight)]; [] if the grid doesn't have it"""
    alias = {'Arcanine-Hisui': 'Arcanine-H', 'Floette-Eternal': 'M-Floette'}
    if sp in alias: return [(alias[sp], 1.0)]
    megas = [g for g in FOES if g == 'M-' + sp or g.startswith('M-' + sp + ' ')]
    if megas and sp in FOES: return [(megas[0], mega_frac), (sp, 1 - mega_frac)]
    if megas: return [(megas[0], 1.0)]
    if sp in FOES: return [(sp, 1.0)]
    return []

O = {**json.load(open(P('pssim/opp_model_a.json'))), **json.load(open(P('pssim/opp_model_b.json')))}
SPD = {}
for f in ('pssim/tr_speeds_inc2.json', 'pssim/tr_speeds_inc.json'):
    if os.path.exists(P(f)): SPD = json.load(open(P(f))); break
MYSPE = {}   # my Speeds, read from the Speed file

def their_fours(arch):
    """[(share, {grid foe: weight}, pair name)], plus the weight of foes the grid lacks"""
    out, missing = [], collections.Counter()
    for p in O[arch]['pairs']:
        w = collections.Counter()
        for sp in p['pair'].split(' + '):
            mf = p['mega'].get(sp, 0) / p['n']
            gn = grid_names(sp, mf)
            if not gn: missing[sp] += p['share']
            for g, x in gn: w[g] += x
        back = [(x.split(':')[0], float(x.split(':')[1])) for x in p['back'].split(', ')]
        scale = 2 / sum(r for _, r in back)
        for sp, r in back:
            gn = grid_names(sp, 0.5)
            if not gn: missing[sp] += p['share'] * r * scale
            for g, x in gn: w[g] += r * scale * x
        out.append((p['share'], w, p['pair']))
    return out, missing

def answer(four, foe, g):
    v = sorted((cell(g, foe, m) for m in four), reverse=True)
    return 0.7 * v[0] + 0.3 * v[1]

def score(arch, four, ptr, back):
    wtr = min(1.0, 0.6 * ptr + (0.3 if SETTERS & set(back) else 0.0))
    fours, _ = their_fours(arch)
    num = den = 0.0
    for s, w, _ in fours:
        for foe, x in w.items():
            num += s * x * (wtr * answer(four, foe, GT) + (1 - wtr) * answer(four, foe, GN)); den += s * x
    return num / den

def tr_speed_delta(arch, lead, back, default_back, ptr):
    """change in the turn-one Trick Room credit (win-% points) from bringing `back` instead of the default"""
    ks = [k for k in SPD if k.startswith(f'{arch}|{"+".join(lead)}|')]
    if not ks: return 0.0
    t = sum(SPD[k]['t'] for k in ks) / len(ks); m0 = sum(SPD[k]['m'] for k in ks) / len(ks)
    mean = lambda xs: sum(MYSPE[x] for x in xs) / 4
    m1 = m0 + mean(list(lead) + list(back)) - mean(list(lead) + list(default_back))
    d = math.tanh((t - m1) / 15) - math.tanh((t - m0) / 15)
    return 100 * 0.25 * 0.638 * d * ptr        # logistic slope ~0.25 near an even game

def main():
    src = next((a for a in sys.argv[1:] if not a.startswith('--')), P('tr_leads_data.json'))
    allp = '--all' in sys.argv
    data = json.load(open(src))
    for k, v in SPD.items():                                  # the Speed file lists the brought four in lead, back order
        a, lead, _ = k.split('|')
        for n, x in zip(lead.split('+'), v['mine']): MYSPE[n] = x
    res = {}
    for tab in data:
        arch = {'Tailwind': 'Tailwind goodstuffs', 'Indeedee TR': 'Indeedee TR / Psychic Terrain', 'Balance': 'Balance, no speed control',
                'Trick Room': 'Trick Room without Indeedee', 'Rain + Sun': 'Rain + sun', 'Perish': 'Perish trap'}.get(tab['tab'], tab['tab'])
        if arch not in O: print('skip', tab['tab']); continue
        _, miss = their_fours(arch)
        tot = sum(p['share'] for p in O[arch]['pairs']) * 4
        print(f"\n== {tab['tab']}   (grid lacks: {', '.join(f'{k} {100*v/tot:.0f}%' for k, v in miss.most_common(4)) or 'none'})")
        for pk in (tab['picks'] if allp else tab['picks'][:1]):
            lead = [SHORT.get(x, x) for x in pk['lead']]
            dback = [SHORT.get(x.strip(), x.strip()) for x in pk['back'].split(',')]
            ptr = (pk.get('tr') or 0) / 100
            rest = [x for x in SIX if x not in lead]
            rows = []
            for back in itertools.combinations(rest, 2):
                s = score(arch, lead + list(back), ptr, back)
                rows.append((s, back, tr_speed_delta(arch, lead, back, dback, ptr)))
            rows.sort(key=lambda r: -r[0])
            base = next(r for r in rows if set(r[1]) == set(dback))
            print(f"  {' + '.join(lead)}  (TR up after T1 {100*ptr:.0f}%)   default back {', '.join(dback)}: {100*base[0]:.1f}")
            for s, back, d in rows:
                mark = '*' if set(back) == set(dback) else ' '
                print(f"   {mark} {', '.join(back):24s} {100*s:5.1f}  ({100*(s-base[0]):+5.1f})   dTR {d:+.1f}")
            res[f"{tab['tab']}|{'+'.join(lead)}"] = [{'back': list(b), 'score': round(100 * s, 1), 'dTR': round(d, 2)} for s, b, d in rows]
    json.dump(res, open(P('bring_scores.json'), 'w'), indent=1)

if __name__ == '__main__': main()
