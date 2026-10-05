"""Score Stat Point spreads from tables.json (champ spreads): offense = usage-weighted share of threats my best attack OHKOs (a 2HKO
counts half); defense = usage-weighted share of the threats' common attacks I survive (one hit and two hits count half each).
Speed SP stays 0 (Trick Room). usage: python3 score.py [name]"""
import json, sys, itertools
T = json.load(open('tables.json')); TH = json.load(open('threats.json')); MINE = {m['name']: m for m in json.load(open('mine.json'))}
W = [t['weight'] for t in TH]
NAT = {'Adamant': ('atk', 'spa'), 'Brave': ('atk', 'spe'), 'Modest': ('spa', 'atk'), 'Quiet': ('spa', 'spe'), 'Bold': ('def', 'atk'), 'Relaxed': ('def', 'spe'),
       'Impish': ('def', 'spa'), 'Calm': ('spd', 'atk'), 'Sassy': ('spd', 'spe'), 'Careful': ('spd', 'spa'), 'Serious': (None, None)}
def off_scores(m):
    """per offense nature class and SP: [score, per-threat value]"""
    out = {}
    for o in m['offense']:
        rows = []
        for sp, per_t in enumerate(o['by_sp']):
            vals = [max(((c[0] / 16) + 0.5 * (c[1] / 256 - c[0] / 16)) for c in mv) if mv else 0 for mv in per_t]
            rows.append((sum(w * v for w, v in zip(W, vals)) / sum(W), vals))
        out[o['nature']] = rows
    return out
def def_scores(m):
    out = {}
    for dn in m['defense']:
        for key in ('phys', 'spec'):
            mv = m['dmoves'][key]; wts = [x[2] * x[3] for x in mv]; tot = sum(wts)
            grid = []
            for cell in dn[key]:
                vals = [0.5 * c[0] / 16 + 0.5 * c[1] / 256 for c in cell]
                grid.append((sum(w * v for w, v in zip(wts, vals)) / tot, vals))
            out[(dn['nature'], key)] = (grid, tot)
    return out
def analyze(name):
    m = next(x for x in T if x['name'] == name); me = MINE[name]
    phys_att = any(True for _ in m['moves']) and m['offense'] and None
    cats = set()
    D = json.load(open('../native/champions_data.json'))
    for mv in m['moves']: cats.add(D['moves'][mv]['category'])
    off_stat = 'atk' if cats == {'Physical'} else 'spa' if cats else None
    OS = off_scores(m) if off_stat else None; DS = def_scores(m)
    wp, ws = DS[('Serious', 'phys')][1], DS[('Serious', 'spec')][1]
    def evaluate(nature, sp):
        plus, minus = NAT[nature]
        oc = 'Brave' if plus == 'atk' else 'Quiet' if plus == 'spa' else 'Serious'
        dc = 'Relaxed' if plus == 'def' else 'Sassy' if plus == 'spd' else 'Serious'
        off = OS[oc][sp[1] if off_stat == 'atk' else sp[3]][0] if off_stat else 0
        hp = sp[0]
        dp = DS[(dc, 'phys')][0][hp * 33 + sp[2]][0]; ds = DS[(dc, 'spec')][0][hp * 33 + sp[4]][0]
        return off, (wp * dp + ws * ds) / (wp + ws), dp, ds
    cur = me['current']; c = evaluate(cur['nature'], cur['evs'])
    natures = [n for n, (p, q) in NAT.items() if n != 'Serious' and q in ('spe',) + (('atk' if off_stat == 'spa' else 'spa'),) and p != q
               and (p in ('def', 'spd') or p == off_stat)] if off_stat else ['Relaxed', 'Sassy', 'Bold', 'Calm', 'Impish', 'Careful']
    cands = []
    for nat in natures:
        for o in (range(33) if off_stat else [0]):
            for hp in range(33):
                for df in range(33):
                    rest = 66 - o - hp - df
                    if rest < 0: continue
                    sd = min(32, rest)
                    sp = [hp, o if off_stat == 'atk' else 0, df, o if off_stat == 'spa' else 0, sd, 0]
                    cands.append((nat, evaluate(nat, sp), sp))
    print(f'\n=== {name}: current {cur["nature"]} {cur["evs"]} -> offense {100*c[0]:.1f}  defense {100*c[1]:.1f} (physical {100*c[2]:.1f}, special {100*c[3]:.1f})')
    best = {}
    for nat, f, sp in cands:
        o = sp[1] if off_stat == 'atk' else sp[3]
        k = (nat, o)
        if k not in best or f[1] > best[k][1][1]: best[k] = (nat, f, sp)
    for nat in sorted({n for n, _ in best}, key=lambda n: -max(best[(n, o)][1][0] + best[(n, o)][1][1] for (m, o) in best if m == n)):
        print(f'   {nat}: best bulk at each attack level')
        for o in [32, 28, 24, 20, 16, 12, 8, 0] if off_stat else [0]:
            n_, f, sp = best[(nat, o)]
            print(f'      attack SP {o:2d}  {sp}  offense {100*f[0]:5.1f}  defense {100*f[1]:5.1f} (phys {100*f[2]:.1f}, spec {100*f[3]:.1f})  total {100*(f[0]+f[1]):.1f}')
    top = max(cands, key=lambda x: x[1][0] + x[1][1])
    print(f'   best total: {top[0]} {top[2]} offense {100*top[1][0]:.1f} defense {100*top[1][1]:.1f}')
    return OS, DS, evaluate, best, off_stat
if __name__ == '__main__':
    for n in (sys.argv[1:] or [x['name'] for x in T]): analyze(n)

def raw_def(m, dnat, key, hp, d):
    dn = next(x for x in m['defense'] if x['nature'] == dnat)
    return [(c[0] / 16, c[1] / 256) for c in dn[key][hp * 33 + d]]
def raw_off(m, onat, sp):
    o = next(x for x in m['offense'] if x['nature'] == onat)
    return [[(c[0] / 16, c[1] / 256) for c in mv] for mv in o['by_sp'][sp]]
def classes(nature):
    plus = NAT[nature][0]
    return ('Brave' if plus == 'atk' else 'Quiet' if plus == 'spa' else 'Serious', 'Relaxed' if plus == 'def' else 'Sassy' if plus == 'spd' else 'Serious')
def diff(name, a, b, min_change=0.2):
    """benchmarks that change between spreads a=(nature, sp) and b: KOs on threats, hits survived"""
    m = next(x for x in T if x['name'] == name)
    D = json.load(open('../native/champions_data.json'))
    cats = {D['moves'][mv]['category'] for mv in m['moves']}
    oi = 1 if cats == {'Physical'} else 3
    rows = []
    if m['moves']:
        oa, ob = raw_off(m, classes(a[0])[0], a[1][oi]), raw_off(m, classes(b[0])[0], b[1][oi])
        for k, t in enumerate(TH):
            for mi, mv in enumerate(m['moves']):
                (a1, a2), (b1, b2) = oa[k][mi], ob[k][mi]
                if abs(b1 - a1) >= min_change: rows.append((t['weight'] * abs(b1 - a1), f"   {'+' if b1 > a1 else '-'} {mv} OHKO {t['name']}: {100*a1:.0f}% -> {100*b1:.0f}%  (usage {100*t['weight']:.1f}%)"))
                elif abs(b2 - a2) >= min_change: rows.append((0.5 * t['weight'] * abs(b2 - a2), f"   {'+' if b2 > a2 else '-'} {mv} 2HKO {t['name']}: {100*a2:.0f}% -> {100*b2:.0f}%  (usage {100*t['weight']:.1f}%)"))
    for key, di in (('phys', 2), ('spec', 4)):
        da = raw_def(m, classes(a[0])[1], key, a[1][0], a[1][di]); db = raw_def(m, classes(b[0])[1], key, b[1][0], b[1][di])
        for (tn, mv, use, w), (a1, a2), (b1, b2) in zip(m['dmoves'][key], da, db):
            if abs(b1 - a1) >= min_change: rows.append((w * use * abs(b1 - a1), f"   {'+' if b1 > a1 else '-'} survives {tn} {mv}: {100*a1:.0f}% -> {100*b1:.0f}%  (usage {100*w:.1f}%, move {100*use:.0f}%)"))
            elif abs(b2 - a2) >= min_change: rows.append((0.5 * w * use * abs(b2 - a2), f"   {'+' if b2 > a2 else '-'} survives two {tn} {mv}: {100*a2:.0f}% -> {100*b2:.0f}%  (usage {100*w:.1f}%, move {100*use:.0f}%)"))
    rows.sort(key=lambda r: -r[0])
    print(f'\n{name}: {a[0]} {a[1]}  ->  {b[0]} {b[1]}')
    for _, r in rows[:18]: print(r)
