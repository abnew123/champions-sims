"""Blend opposing sets: per archetype and Pokemon, the ladder's modal set (opp_model "sets", with its share of that Pokemon's ladder sets) vs the
Reg M-C regional team-list sets (items, abilities, natures, moves; no spreads). Score = LS x ladder share (modal set only) + (1-LS) x regional
share; the top-scoring set is used. Writes overrides only where the choice changes.  usage: python3 blend_sets.py [ladder_share=0.7] [out.json]"""
import json, sys, re, collections
LS = float(sys.argv[1]) if len(sys.argv) > 1 else 0.7; outf = sys.argv[2] if len(sys.argv) > 2 else 'opp_sets_blend.json'
TAB2ARCH = {'Tailwind': 'Tailwind goodstuffs', 'Indeedee TR': 'Indeedee TR / Psychic Terrain', 'Balance': 'Balance, no speed control', 'Trick Room': 'Trick Room without Indeedee',
            'Rain + Sun': 'Rain + sun', 'Perish': 'Perish trap', 'Sun': 'Sun', 'Rain': 'Rain', 'Sand': 'Sand', 'Snow': 'Snow'}
toid = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
SPN = {'Female Indeedee': 'Indeedee-F', 'Male Indeedee': 'Indeedee', 'Indeedee': 'Indeedee', 'Hisuian Arcanine': 'Arcanine-Hisui', 'Arcanine-Hisui': 'Arcanine-Hisui',
       'Floette-Eternal': 'Floette-Eternal', 'Eternal Floette': 'Floette-Eternal', 'Eternal Flower Floette': 'Floette-Eternal', 'Hisuian Typhlosion': 'Typhlosion-Hisui', 'Alolan Ninetales': 'Ninetales-Alola'}
O = {**json.load(open('../pssim/opp_model_a.json')), **json.load(open('../pssim/opp_model_b.json'))}
teams = {f"{t['event']}|{t['pid']}": t for t in json.load(open('regional_teams.json'))}
sets = json.load(open('regional_sets.json'))
reg = collections.defaultdict(collections.Counter)            # (arch, species) -> Counter(set string)
for k, S in sets.items():
    t = teams.get(k)
    if not t: continue
    arch = TAB2ARCH[t['arch']]
    for s in S:
        sp = SPN.get(s['species'], s['species'])
        key = f"{toid(s['item'])}|{toid(s['ability'])}|{s['nature']}|{'/'.join(sorted(toid(m) for m in s['moves']))}"
        reg[(arch, sp)][key] += 1
def parse_ladder(v):
    m = re.match(r'(.*?) \((\d+)/(\d+)\)$', v)
    if not m: return v, 1.0
    a, b, c = m.groups(); it, ab, nat, mv = a.split('|'); return f"{it}|{ab}|{nat}|{'/'.join(sorted(mv.split('/')))}", int(b) / int(c)
over, report = collections.defaultdict(dict), []
for arch, d in O.items():
    for sp, v in d['sets'].items():
        lset, lsh = parse_ladder(v); R = reg.get((arch, sp), collections.Counter()); n = sum(R.values())
        score = collections.Counter({lset: LS * lsh})
        for s, c in R.items(): score[s] += (1 - LS) * c / n
        best, bs = score.most_common(1)[0]
        if best != lset:
            over[arch][sp] = best
            report.append((arch, sp, lset, round(lsh, 2), best, round(R[best] / n, 2), n))
json.dump(over, open(outf, 'w'), indent=1)
print(f'{len(report)} set changes (ladder modal set -> regional set):')
for arch, sp, a, la, b, rb, n in report:
    da = a.split('|'); db = b.split('|'); diff = [f"{lab}: {x} -> {y}" for lab, x, y in zip(('item', 'ability', 'nature', 'moves'), da, db) if x != y]
    print(f"  {arch[:22]:22s} {sp:16s} (ladder {int(100*la)}% of its sets, regionals {int(100*rb)}% of {n})  " + '; '.join(diff))
