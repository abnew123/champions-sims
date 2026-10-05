import score, json, sys
D = json.load(open('../native/champions_data.json'))
def candidates(name, natures, w_off=1.0):
    m = next(x for x in score.T if x['name'] == name)
    OS = score.off_scores(m) if m['moves'] else None; DS = score.def_scores(m)
    cats = {D['moves'][mv]['category'] for mv in m['moves']}; oi = 1 if cats == {'Physical'} else 3
    wp, ws = DS[('Serious', 'phys')][1], DS[('Serious', 'spec')][1]
    out = []
    for nat in natures:
        oc, dc = score.classes(nat)
        for o in (range(33) if OS else [0]):
            off = OS[oc][o][0] if OS else 0
            for hp in range(33):
                for df in range(33):
                    rest = 66 - o - hp - df
                    if rest < 0: continue
                    sd = min(32, rest); sp = [hp, 0, df, 0, sd, 0]; sp[oi] = o
                    dp = DS[(dc, 'phys')][0][hp * 33 + df][0]; ds = DS[(dc, 'spec')][0][hp * 33 + sd][0]
                    de = (wp * dp + ws * ds) / (wp + ws)
                    out.append((w_off * off + de, off, de, nat, sp))
    out.sort(key=lambda x: -x[0]); return out
cfg = {'Blastoise': (['Quiet', 'Modest'], 1), 'Torkoal': (['Quiet', 'Modest', 'Relaxed', 'Sassy'], 1), 'Indeedee-F': (['Relaxed', 'Sassy'], 1),
       'Farigiraf': (['Relaxed', 'Sassy', 'Quiet'], 0.3), 'Kingambit': (['Adamant', 'Brave', 'Relaxed', 'Sassy'], 1), 'Incineroar': (['Brave', 'Adamant', 'Relaxed', 'Sassy'], 1)}
for name in (sys.argv[1:] or cfg):
    nats, w = cfg[name]; cur = score.MINE[name]['current']
    c = candidates(name, nats, w)
    cur_row = next(x for x in candidates(name, [cur['nature']], w) if x[4] == cur['evs'])
    print(f'\n######## {name}: current {cur["nature"]} {cur["evs"]}: offense {100*cur_row[1]:.1f} defense {100*cur_row[2]:.1f}  (offense weight {w})')
    shown = 0
    for row in c:
        if shown >= 3: break
        print(f'   option {shown + 1}: {row[3]} {row[4]}  offense {100*row[1]:.1f} defense {100*row[2]:.1f}')
        shown += 1
    best = c[0]
    score.diff(name, (cur['nature'], cur['evs']), (best[3], best[4]))
