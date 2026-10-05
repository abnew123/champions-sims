"""The bring heuristic's four and leads for the Trick Room six vs the sheet's picks (lead solver + 2v2 back rows), per archetype.
  python3 compare_sheet.py            (sheet data: tr_leads_data.json at the project root)"""
import json, os, sys
import policy as P
MODEL = sys.argv[1] if len(sys.argv) > 1 else None                     # a human-style model file; default: the policy in use
HERE = os.path.dirname(os.path.abspath(__file__))
TAB = {'tw': 'Tailwind goodstuffs', 'indeedee': 'Indeedee TR / Psychic Terrain', 'sun': 'Sun', 'rain': 'Rain', 'balance': 'Balance, no speed control',
       'sand': 'Sand', 'snow': 'Snow', 'tr': 'Trick Room without Indeedee', 'rainsun': 'Rain + sun', 'perish': 'Perish trap'}
team = json.load(open(os.path.join(HERE, '..', 'teams', 'start', 'index.json')))['trick_room_six']['gids']
name = {g: P.Fx.G[g]['species'].replace('Indeedee-F', 'Indeedee') for g in team}
def sheet_picks():
    """{arch: [(lead names, back names)]} from the sheet, best pick first"""
    out = {}
    for t in json.load(open(os.path.join(P.Fx.L.ROOT, 'tr_leads_data.json'))):
        if t['k'] in TAB: out[TAB[t['k']]] = [(p['lead'], [x.strip() for x in p['back'].split(',')]) for p in t['picks']]
    return out
if __name__ == '__main__':
    same4 = samelead = 0; S = sheet_picks()
    for arch in P.ARCH_SHARE:
        lead, back, lp = P.choose(team, arch, MODEL) if MODEL else P.chooser()(team, arch)
        ml, mb = sorted(name[g] for g in lead), sorted(name[g] for g in back)
        sl, sb = sorted(S[arch][0][0]), sorted(S[arch][0][1])
        same4 += sorted(ml + mb) == sorted(sl + sb); samelead += ml == sl
        print(f"{arch:32s} heuristic {'+'.join(ml):22s} / {'+'.join(mb):22s}   sheet {'+'.join(sl):22s} / {'+'.join(sb)}")
    print(f"same four {same4}/10, same leads {samelead}/10")
