"""Full-battle results per archetype (champ battle output): win share weighted by how often each opposing lead appears (replay share),
Trick Room up by the end of turns 1-3, average game length, voluntary switch rate per decision (an active Pokemon with a bench to switch to; mine / theirs), and the turn-one model's
score for the same plan (tr_leads_data.json `v`: [ladder-ish, reader-ish] lead values) for comparison.
usage: python3 battle_summary.py <results dir> [--logs N]   (N example game logs from the worst archetype)"""
import json, glob, sys, collections
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
TAB = {'Tailwind': 'Tailwind goodstuffs', 'Indeedee TR': 'Indeedee TR / Psychic Terrain', 'Balance': 'Balance, no speed control',
       'Trick Room': 'Trick Room without Indeedee', 'Rain + Sun': 'Rain + sun', 'Perish': 'Perish trap', 'Sun': 'Sun', 'Rain': 'Rain', 'Sand': 'Sand', 'Snow': 'Snow'}
sheet = {TAB[t['tab']]: t['picks'][0]['v'] for t in json.load(open('../tr_leads_data.json')) if t['tab'] in TAB}
R = collections.defaultdict(list)
for f in glob.glob(sys.argv[1] + '/*.json'):
    r = json.load(open(f)); R[r['arch']].append(r)
print(f"{'archetype':28s} {'win%':>5s} {'T1-model':>8s}  {'TR up by T1/T2/T3':>17s} {'turns':>5s} {'switch rate me/them':>19s}  plan")
SD = [0, 0]; SS = [0, 0]
tot = wt = 0.0; worst = None
for a in SH:
    L = R.get(a, []);
    if not L: continue
    W = sum(r['share'] for r in L); win = sum(r['share'] * r['v'] for r in L if r['v'] is not None) / W
    rows = [g for r in L for g in r['rows'] if g.get('v') is not None]
    tr = [sum(g['trBy'][k] for g in rows) / len(rows) for k in range(3)]
    turns = sum(g['turns'] for g in rows) / len(rows)
    sd = [sum(g['slotDecisions'][k] for g in rows) for k in range(2)]; ss = [sum(g['switchSlots'][k] for g in rows) for k in range(2)]
    for k in range(2): SD[k] += sd[k]; SS[k] += ss[k]
    sw = [ss[k] / max(1, sd[k]) for k in range(2)]
    tot += SH[a] * win; wt += SH[a]
    if worst is None or win < worst[0]: worst = (win, a)
    print(f"{a[:28]:28s} {100*win:5.1f} {str(sheet.get(a, '')):>8s}  {' / '.join(f'{100*x:3.0f}%' for x in tr):>17s} {turns:5.1f} {100*sw[0]:9.1f}% / {100*sw[1]:4.1f}%   "
          f"{'+'.join(L[0]['lead'])} | {'+'.join(L[0]['back'])}")
print(f"\nladder-weighted full-battle win share: {100*tot/wt:.1f}%")
print(f"voluntary switch rate per decision, all games: me {100*SS[0]/max(1,SD[0]):.1f}% ({SS[0]}/{SD[0]}), them {100*SS[1]/max(1,SD[1]):.1f}% ({SS[1]}/{SD[1]})")
if '--logs' in sys.argv and worst:
    n = int(sys.argv[sys.argv.index('--logs') + 1]); a = worst[1]
    print(f"\nexample games vs {a}:")
    for r in sorted(R[a], key=lambda r: r['v'] or 0)[:n]:
        g = next(g for g in r['rows'] if g.get('log'))
        print(f"  vs {r['pair']} (+ {', '.join(r['theirs'][2:])}), win share {r['v']:.2f}; game {g['g']}: {'won' if g['v'] > 0.5 else 'lost'}")
        for l in g['log']: print('     ' + l[:200])
