"""Blend who-you-face weights: LADDER share of last week's public M-C Bo3 ladder teams (pssim/endpairs.json) and the rest from the Reg M-C
regionals' listed teams (regional_teams.json). Outputs archetype shares and, per archetype, each Pokemon's ratio blended/ladder presence
(clipped to [1/3, 3]) for reweighting ladder lead pairs and 2v2 pairs.  usage: python3 blend_weights.py [ladder_share=0.7] [out=weights_blend.json]"""
import json, sys, collections
LS = float(sys.argv[1]) if len(sys.argv) > 1 else 0.7; outf = sys.argv[2] if len(sys.argv) > 2 else 'weights_blend.json'
TAB2ARCH = {'Tailwind': 'Tailwind goodstuffs', 'Indeedee TR': 'Indeedee TR / Psychic Terrain', 'Balance': 'Balance, no speed control', 'Trick Room': 'Trick Room without Indeedee',
            'Rain + Sun': 'Rain + sun', 'Perish': 'Perish trap', 'Sun': 'Sun', 'Rain': 'Rain', 'Sand': 'Sand', 'Snow': 'Snow'}
norm = lambda s: {'Sinistcha-Masterpiece': 'Sinistcha', 'Maushold-Four': 'Maushold', 'Vivillon-Modern': 'Vivillon'}.get(s, s)
lad = [{'arch': r['arch'], 'six': [norm(x) for x in r['six']]} for r in json.load(open('../pssim/endpairs.json'))['rows']]
reg = json.load(open('regional_teams.json'))
def shares(T): c = collections.Counter(t['arch'] for t in T); n = len(T); return {a: c[a] / n for a in TAB2ARCH}
sl, sr = shares(lad), shares(reg)
arch_share = {TAB2ARCH[a]: round(100 * (LS * sl[a] + (1 - LS) * sr[a]), 2) for a in TAB2ARCH}
ratio = {}
for tab, arch in TAB2ARCH.items():
    L = [t for t in lad if t['arch'] == tab]; R = [t for t in reg if t['arch'] == tab]
    pl = collections.Counter(m for t in L for m in set(t['six'])); pr = collections.Counter(m for t in R for m in set(t['six']))
    r = {}
    for m in set(pl) | set(pr):
        a = pl[m] / max(1, len(L)); b = pr[m] / max(1, len(R)) if R else a
        if a == 0: continue                                   # a ladder pair can't contain it anyway
        r[m] = round(min(3, max(1 / 3, (LS * a + (1 - LS) * b) / a)), 3)
    ratio[arch] = r
json.dump({'ladder_share': LS, 'arch_share': arch_share, 'ratio': ratio, 'n_ladder': len(lad), 'n_regional': len(reg)}, open(outf, 'w'), indent=1)
print('archetype shares (blend):', arch_share)
for arch in ('Tailwind goodstuffs', 'Perish trap', 'Trick Room without Indeedee', 'Sun'):
    r = ratio[arch]; up = sorted(r.items(), key=lambda kv: -kv[1])[:5]; dn = sorted(r.items(), key=lambda kv: kv[1])[:5]
    print(f"  {arch[:24]:24s} up: {', '.join(f'{m} x{v:.2f}' for m, v in up)} | down: {', '.join(f'{m} x{v:.2f}' for m, v in dn)}")
