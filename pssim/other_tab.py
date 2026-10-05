"""The sheet's "Other" tab: your best lead and back pair against a random team (archetypes weighted by the ladder/regional blend), with a general
plan (each lead Pokemon's turn-one move mix across all archetypes, with its usual targets) instead of matchup lines.
usage: TR_SPEEDS=... READER_W=0.75 TRMULT_FILE=... python3 other_tab.py <tr_final.json> <trup.json> <eg_summary.json> <weights_blend.json> <out.json>"""
import json, sys, os, collections, re
from trlib import load, solved
fin, trupf, egf, wf, outf = sys.argv[1:6]
LAM = float(os.environ.get('READER_W', '0.75')); BL = lambda a, b: (1 - LAM) * a + LAM * b
D = json.load(open(fin)); PL = D['plans']; TRUP = json.load(open(trupf)); EG = json.load(open(egf))['tr']; W = json.load(open(wf))['arch_share']
SIX = ['Incineroar', 'Indeedee-F', 'Farigiraf', 'Torkoal', 'Kingambit', 'Blastoise']; FB = 'Farigiraf+Blastoise'
S1 = load('results/inc1')
def per_arch(lead):
    """per archetype: (pop, worst, TR click rate, TR up rate, [(pair share, mix lines)]) - refined plans where they exist, else first-pass"""
    out = {}
    for arch in W:
        keys = [k for k in PL if k.startswith(f'{arch}||{lead}||')]
        rows = []
        if keys:
            for k in keys:
                p = PL[k]; tr = sum(pc for pc, a in p['mix'] if ': Trick Room' in a) / 100
                rows.append((p['share'], p['pop'], p['worst'], tr, TRUP.get(k, tr), [(pc / 100, a) for pc, a in p['mix']]))
        else:
            for k, r in S1.items():
                if k[0] != arch or k[1] != lead: continue
                s = solved(r); mix = [(float(x), a) for x, a in zip(s['xm'], s['acts']) if x > 0.03]
                tr = sum(x for x, a in mix if ': Trick Room' in a)
                rows.append((r['share'], s['pop_m'], s['worst_m'], tr, tr, mix))
        if not rows: continue
        t = sum(r[0] for r in rows)
        out[arch] = (sum(r[0] * r[1] for r in rows) / t, sum(r[0] * r[2] for r in rows) / t, sum(r[0] * r[3] for r in rows) / t,
                     sum(r[0] * r[4] for r in rows) / t, [(r[0] / t, r[5]) for r in rows], bool(keys))
    return out
def summarize(lead):
    A = per_arch(lead); tw = sum(W[a] for a in A)
    pop = sum(W[a] * A[a][0] for a in A) / tw; worst = sum(W[a] * A[a][1] for a in A) / tw
    tr = sum(W[a] * A[a][2] for a in A) / tw
    # general plan: each Pokemon's move mix, weighted by archetype share x lead-pair share x line frequency; targets counted per move
    mv = {m: collections.Counter() for m in lead.split('+')}; tg = {m: collections.defaultdict(collections.Counter) for m in lead.split('+')}
    for a, (_, _, _, _, rows, _) in A.items():
        for sh, mix in rows:
            for x, line in mix:
                for part in line.split(' | '):
                    mon, act = part.split(': ', 1); move, _, target = act.partition(' -> ')
                    if move == 'switch': move, target = f'switch to {target}', ''
                    w = W[a] / tw * sh * x; mv[mon][move] += w
                    if target: tg[mon][move][target] += w
    general = {}
    for mon, c in mv.items():
        tot = sum(c.values()); lines = []
        for move, w in c.most_common():
            if w / tot < 0.04: continue
            ts = [t.replace('Indeedee-F', 'Indeedee F').replace('Arcanine-Hisui', 'Arcanine-H').replace('Floette-Eternal', 'Floette') for t, _ in tg[mon][move].most_common(3)]
            lines.append([round(100 * w / tot), move.replace('Kowtow Cleave', 'Kowtow'), ts])
        general[mon.replace('Indeedee-F', 'Indeedee')] = lines
    # back pair: 2v2 win share against each archetype's turn-3 pairs, Trick Room up as often as it is after this lead's turn one
    best = None
    rest = [x for x in SIX if x not in lead.split('+')]
    for i in range(4):
        for j in range(i + 1, 4):
            b = frozenset([rest[i], rest[j]]); v = 0; t = 0
            for a, row in A.items():
                pv = {frozenset(k.split('+')): x for k, x in EG[a]['pairs'].items()}.get(b)
                if pv: v += W[a] * (row[3] * pv[0] + (1 - row[3]) * pv[1]); t += W[a]
            if t and (best is None or v / t > best[0]): best = (v / t, [rest[i], rest[j]])
    return {'lead': lead, 'v': [pop, worst], 'score': BL(pop, worst), 'tr': tr, 'back': best[1], 'general': general, 'refined': sum(r[5] for r in A.values())}
leads = ['+'.join(sorted((a, b), key=SIX.index)) for i, a in enumerate(SIX) for b in SIX[i + 1:]]
canon = {l: next((k.split('||')[1] for k in PL if set(k.split('||')[1].split('+')) == set(l.split('+'))), l) for l in leads}
S = sorted((summarize(canon[l]) for l in leads), key=lambda s: -s['score'])
top = S[0]; fbs = next(s for s in S if s['lead'] == FB)
picks = [fbs, top] if top['lead'] != FB and top['score'] - fbs['score'] <= 0.03 else [top]
for s in S[:5]: print(f"{100*s['score']:5.1f}  {s['lead']:24s} back {', '.join(s['back'])}  TR {100*s['tr']:.0f}%  refined in {s['refined']}/10")
json.dump({'picks': picks, 'top': top['lead'], 'gap': round(100 * (top['score'] - fbs['score']), 1)}, open(outf, 'w'), indent=1)
for p in picks:
    print(f"\n{p['lead']}:"); [print(f"   {m}: " + '; '.join(f"{pc}% {mv}" + (f" ({', '.join(t)})" if t else '') for pc, mv, t in L)) for m, L in p['general'].items()]
