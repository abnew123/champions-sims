"""2v2 endgame results (eg_run.sh output): back-pair ranking per sheet lead, and what Trick Room is worth.
usage: python3 eg_analyze.py <resultsDir> [../tr_leads_data.json] [--json out.json]
  V(mine, theirs, K) = my win share over the games; their back pairs are weighted by replay likelihood (w).
  TR worth = V(K turns of Trick Room) - V(no Trick Room), same pairs, same seeds.
"""
import json, glob, sys, os, itertools, math, collections
d = sys.argv[1]; outj = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
src = next((a for a in sys.argv[2:] if a.endswith('.json') and a != outj), '../tr_leads_data.json')
V = collections.defaultdict(dict); W = collections.defaultdict(dict); G = collections.defaultdict(dict)
for f in glob.glob(d + '/*.json'):
    r = json.load(open(f)); m = frozenset(r['mine']); t = ','.join(r['theirs'])
    if r['v'] is None: continue
    V[(r['arch'], m, t)][r['K']] = r['v']; G[(r['arch'], m, t)][r['K']] = r['vs']; W[r['arch']][t] = r['w']
# PAIR_RATIO: reweight their pairs by the regional blend (regionals/blend_weights.py)
if os.environ.get('PAIR_RATIO'):
    RAT = json.load(open(os.environ['PAIR_RATIO']))['ratio']
    for a in W:
        for t in W[a]: W[a][t] *= math.prod(RAT.get(a, {}).get(m, 1.0) for m in t.split(','))
ARCHS = list(W)
SHORT = {'Indeedee': 'Indeedee-F'}
TAB = {'Tailwind': 'Tailwind goodstuffs', 'Indeedee TR': 'Indeedee TR / Psychic Terrain', 'Balance': 'Balance, no speed control',
       'Trick Room': 'Trick Room without Indeedee', 'Rain + Sun': 'Rain + sun', 'Perish': 'Perish trap'}
SIX = ['Incineroar', 'Indeedee-F', 'Farigiraf', 'Torkoal', 'Kingambit', 'Blastoise']
Kup = max(k for v in V.values() for k in v)

def val(arch, pair, K):
    """weighted win share and its standard error (games are ~Bernoulli)"""
    num = den = var = 0.0; n = 0
    for t, w in W[arch].items():
        v = V.get((arch, frozenset(pair), t), {}).get(K)
        if v is None: continue
        g = G[(arch, frozenset(pair), t)][K]; num += w * v; den += w
        s2 = sum((x - v) ** 2 for x in g) / max(1, len(g) - 1); var += w * w * s2 / len(g); n += len(g)
    return (num / den, math.sqrt(var) / den, n) if den else (None, None, 0)

out = {'tr': {}, 'back': {}}
print(f'### What Trick Room is worth in the 2v2 ({Kup} turns up vs none), my win share, weighted over their back pairs')
print(f"{'archetype':30s} {'mean dTR':>8s}   pairs that gain most / least")
for a in ARCHS:
    rows = []
    for p in itertools.combinations(SIX, 2):
        up, se, _ = val(a, p, Kup); dn, _, _ = val(a, p, 0)
        if up is not None and dn is not None: rows.append((up - dn, p, up, dn))
    if not rows: continue
    rows.sort(reverse=True); m = sum(r[0] for r in rows) / len(rows)
    out['tr'][a] = {'mean': round(m, 3), 'pairs': {'+'.join(p): [round(up, 3), round(dn, 3)] for _, p, up, dn in rows}}
    best = ', '.join(f"{'+'.join(p)} {100*x:+.0f}" for x, p, *_ in rows[:3]); worst = ', '.join(f"{'+'.join(p)} {100*x:+.0f}" for x, p, *_ in rows[-2:])
    print(f'{a[:30]:30s} {100*m:+7.1f}   {best} | {worst}')

print(f'\n### Back pair for each sheet lead: win share in the 2v2 with Trick Room up ({Kup} turns) [and with none]')
for tab in json.load(open(src)):
    a = TAB.get(tab['tab'], tab['tab'])
    if a not in W: continue
    for pk in tab['picks']:
        lead = [SHORT.get(x, x) for x in pk['lead']]; dback = {SHORT.get(x.strip(), x.strip()) for x in pk['back'].split(',')}
        rest = [x for x in SIX if x not in lead]; rows = []
        for b in itertools.combinations(rest, 2):
            up, se, n = val(a, b, Kup); dn, _, _ = val(a, b, 0)
            if up is None or dn is None: continue
            # the back sees Trick Room about as often as the lead sets it
            ptr = (pk.get('tr') or 0) / 100; mix = ptr * up + (1 - ptr) * dn
            rows.append((mix, b, up, dn, se))
        rows.sort(key=lambda r: -r[0]); base = next((r for r in rows if set(r[1]) == dback), None)
        if base is None: continue
        tag = pk.get('tag') or ''
        print(f"\n{tab['tab']} {tag} | {' + '.join(lead)} (sets TR {pk.get('tr') or 0}%)  now: {', '.join(sorted(dback))} {100*base[0]:.0f}")
        for mix, b, up, dn, se in rows:
            print(f"   {'*' if set(b) == dback else ' '} {', '.join(b):24s} {100*mix:4.0f}  ({100*(mix-base[0]):+4.0f})   TR {100*up:3.0f} / none {100*dn:3.0f}   +-{100*se:.0f}")
        out['back'][f"{tab['tab']}|{'+'.join(lead)}"] = [{'back': list(b), 'v': round(mix, 3), 'tr': round(up, 3), 'notr': round(dn, 3), 'se': round(se, 3)} for mix, b, up, dn, se in rows]
if outj: json.dump(out, open(outj, 'w'), indent=1)
