"""Full-battle lead picks (2026-10-03): rank each archetype's (lead, back row) combos by win share in full battles, weighted by how often
each opposing lead appears (replay share). Reads any number of result folders and pools games of the same (arch, lead, back, opposing
lead) job, so a confirmation round (other seeds) adds to stage two. Marks the sheet's plan.
usage: python3 battle_leads_rank.py <results dir> [...] [--confirm N out.json G0]   (writes jobs for each archetype's top N combos)"""
import json, glob, sys, math, collections
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
TAB = {'Tailwind': 'Tailwind goodstuffs', 'Indeedee TR': 'Indeedee TR / Psychic Terrain', 'Balance': 'Balance, no speed control',
       'Trick Room': 'Trick Room without Indeedee', 'Rain + Sun': 'Rain + sun', 'Perish': 'Perish trap', 'Sun': 'Sun', 'Rain': 'Rain', 'Sand': 'Sand', 'Snow': 'Snow'}
fix = lambda n: 'Indeedee-F' if n == 'Indeedee' else n
SHEET = {TAB[t['tab']]: (frozenset(fix(x) for x in t['picks'][0]['lead']), frozenset(fix(x.strip()) for x in t['picks'][0]['back'].split(',')))
         for t in json.load(open('../tr_leads_data.json')) if t['tab'] in TAB}
args = [a for a in sys.argv[1:] if not a.startswith('--')]
conf = sys.argv[sys.argv.index('--confirm') + 1:sys.argv.index('--confirm') + 4] if '--confirm' in sys.argv else None
dirs = [a for a in args if conf is None or a not in conf]
G = collections.defaultdict(lambda: collections.defaultdict(list))     # arch -> (lead, back) -> list of (k, share, game values)
meta = {}
for d in dirs:
    for f in glob.glob(d + '/*.json'):
        r = json.load(open(f)); key = (frozenset(r['lead']), frozenset(r['back']))
        G[r['arch']][key].append((r['pair'], r['share'], [g['v'] for g in r['rows'] if g.get('v') is not None]))
        meta[(r['arch'], key)] = (r['lead'], r['back'])
best = {}; tot_best = tot_sheet = 0.0; jobs = []
for a in SH:
    rows = []
    for key, L in G[a].items():
        by = collections.defaultdict(lambda: [0.0, []])
        for pair, share, vs in L: by[pair][0] = share; by[pair][1] += vs
        W = sum(s for s, _ in by.values()); v = sum(s * sum(vs) / len(vs) for s, vs in by.values() if vs) / W
        n = sum(len(vs) for _, vs in by.values()); se = math.sqrt(max(v * (1 - v), 0.02) / max(n, 1))
        rows.append((v, se, n, key))
    rows.sort(key=lambda x: -x[0])
    if not rows: continue
    print(f"\n{a}  (share {SH[a]})")
    for v, se, n, key in rows[:6]:
        lead, back = meta[(a, key)]
        print(f"   {100*v:5.1f} ±{100*se:3.0f} ({n:3d} games)  {'+'.join(lead):24s} back {'+'.join(back):24s}{'   <- sheet' if key == SHEET[a] else ''}")
    sh = next((r for r in rows if r[3] == SHEET[a]), None)
    if sh is None: print(f"   (sheet plan {'+'.join(sorted(SHEET[a][0]))} | {'+'.join(sorted(SHEET[a][1]))} not in this run)")
    tot_best += SH[a] * rows[0][0]; tot_sheet += SH[a] * (sh[0] if sh else float('nan'))
    if conf:
        for v, se, n, key in rows[:int(conf[0])]:
            lead, back = meta[(a, key)]
            for k in range(6): jobs.append({'arch': a, 'k': k, 'lead': lead, 'back': back})
W = sum(SH.values())
print(f"\nladder-weighted: best combo per archetype {100*tot_best/W:.1f}% | sheet plans {100*tot_sheet/W:.1f}%  (best-of-several is optimistic until confirmed on new seeds)")
if conf: json.dump(jobs, open(conf[1], 'w')); print(f"{len(jobs)} confirmation jobs -> {conf[1]} (run with first game index {conf[2]})")
