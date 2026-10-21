"""Does the net fitted on the depth-at-4x search's values (value2's d4 net) remove the drift the Eval bar found? (2026-10-20, the user: "go
ahead with the offline check on the d4 net".) The Eval bar's ledger (evalbar/ledger.py replays, db84d43) measured, in people's games,
the next turn's search value less the value function at the same position, for the side that had just played each kind of thing: the
deployed net overrates a side that just used Fake Out (3.0), Tailwind (1.9), screens, Helping Hand, attacks, and underrates one that just
Protected (2.2), used a status move, redirected or switched; the bot plays the overrated kinds and its opponents the underrated ones, the
-13 / -23 points a game of drift in its own games. Here the same measure for two nets on the value rebuild's held-out parts (hold, val;
the d4 net was fitted on fit_sub), against the d4 search (real_<part>_d4.eval.jsonl): the deployed net (bot/value/vnet_h64_search_acc.json)
and the d4 net (results/value2/vnet_h64_search_fit_sub_d4.json), both computed here from the positions' features (real_<part>.vfeats.jsonl)
the way the engine does (VNet::value without the Perish term). Also each net's log loss against the games' results.
  ../.venv/bin/python3 drift_nets.py
Result (2026-10-20; 19,122 side-steps in 2,478 held-out games): the deployed net reproduces the Eval bar's numbers (after Fake Out -3.02,
Protect +2.19, Tailwind -1.92, attacks -0.78, spread -1.03, screens -1.33, status +1.97); the d4 net -0.81, +0.17, +0.16, -0.14, -0.44,
+1.00, +1.48: root mean square over the kinds 1.45 -> 0.62. Against the games' results both are alike (log loss on hold with a scale
fitted on val: 0.5204 deployed, 0.5246 d4, difference +0.004 +- 0.011; the d4 net's scale 0.671 against 0.798)."""
import os, sys, json, math, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'evalbar'))
import diverge as D
V2 = os.path.join(HERE, 'results', 'value2')
NETS = {'deployed (acc)': os.path.join(ROOT, 'bot', 'value', 'vnet_h64_search_acc.json'), 'd4': os.path.join(V2, 'vnet_h64_search_fit_sub_d4.json')}
def h(net, e):
    W = np.array(net['W']); sd = np.array(net['sd']); v = np.array(net['v'])
    return np.tanh((e / sd) @ W.T) @ v
sig = lambda z: 1 / (1 + np.exp(-z))
def main():
    nets = {k: json.load(open(f)) for k, f in NETS.items()}
    Mv = json.load(open(os.path.join(ROOT, 'native', 'engine_data_full.json')))['moves']
    pos = {}; outc = collections.defaultdict(list)
    for part in ('hold', 'val'):
        meta = {m['name']: m for m in map(json.loads, open(os.path.join(V2, f'real_{part}.meta.jsonl')))}
        F = {}
        for l in open(os.path.join(V2, f'real_{part}.vfeats.jsonl')):
            r = json.loads(l)
            if 'error' in r: continue
            x = np.array(r['x'][:28]); E = np.concatenate([r['f0'], r['f1'], r['g0'], x]); S = np.concatenate([r['f1'], r['f0'], r['g1'], -x])
            F[r['name']] = (E, S)
        names = sorted(F); EE = np.array([F[n][0] for n in names]); SS = np.array([F[n][1] for n in names])
        val = {k: dict(zip(names, sig(np.clip(h(net, EE) - h(net, SS), -30, 30)))) for k, net in nets.items()}
        for n in names:
            if n in meta:
                for k in nets: outc[k].append((val[k][n], meta[n]['y'], meta[n]['game']))
        for l in open(os.path.join(V2, 'box', f'real_{part}_d4.eval.jsonl')):
            e = json.loads(l)
            if 'sides' not in e or e['name'] not in val['d4']: continue
            info = []
            for s_ in (0, 1):
                top, kinds, known = True, set(), True
                for sl in e['sides'][s_]['slots']:
                    o = sl['options']
                    if len(o) < 2: continue
                    pl = [x for x in o if x.get('actual')]
                    if not pl: known = False; continue
                    kinds.add(D.kind(pl[0]['label'], pl[0]['c'], Mv)); top = top and bool(max(o, key=lambda x: x['w']).get('actual'))
                info.append({'top': top and known, 'kinds': kinds, 'known': known})
            pos[(e['name'].split(' ')[0], e['turn'])] = {'d': {k: D.R(e['value']) - D.R(val[k][e['name']]) for k in nets}, 'info': info,
                                                         'eng': D.R(e['value']) - D.R(e['static']) if e.get('static') is not None else None}
    rows = []
    for (g, t), p_ in pos.items():
        q = pos.get((g, t + 1))
        if not q: continue
        for s_ in (0, 1):
            if p_['info'][s_]['known'] and p_['info'][1 - s_]['known']:
                sgn = 1 if s_ == 0 else -1
                rows.append({'g': g, 'd': {k: sgn * v for k, v in q['d'].items()}, 'eng': None if q['eng'] is None else sgn * q['eng'],
                             'top': p_['info'][s_]['top'], 'own': p_['info'][s_]['kinds']})
    def ms(xs, key):
        by = collections.defaultdict(lambda: [0.0, 0])
        for r in xs:
            v = r['eng'] if key == 'engine' else r['d'][key]
            if v is None: continue
            by[r['g']][0] += v; by[r['g']][1] += 1
        S = np.array([v[0] for v in by.values()]); N = np.array([v[1] for v in by.values()])
        pick = np.random.default_rng(1).integers(0, len(S), (400, len(S)))
        return 100 * S.sum() / N.sum(), 100 * np.std(S[pick].sum(1) / N[pick].sum(1))
    keys = ['engine'] + list(nets)
    print(f"{len(rows)} side-steps in {len({r['g'] for r in rows})} held-out games (hold + val); drift for the side that played it, points "
          f"(the d4 search less the value function); 'engine' = the static the search run itself recorded")
    print(f"  {'':46s}" + ''.join(f"{k:>22s}" for k in keys))
    def line(lab, xs):
        print(f"  {lab[:46]:46s}" + ''.join('{:>22s}'.format('%+.2f ± %.2f' % ms(xs, k)) for k in keys) + f"  ({len(xs)})")
    line('all', rows); line('played the top option in every slot', [r for r in rows if r['top']])
    print('  by what the side played the turn before:')
    for k, n in collections.Counter(k for r in rows for k in r['own']).most_common():
        if n >= 300: line('    ' + k, [r for r in rows if k in r['own']])
    rms = {k: math.sqrt(np.mean([ms([r for r in rows if kd in r['own']], k)[0] ** 2 for kd, n in collections.Counter(x for r in rows for x in r['own']).items() if n >= 300]))
           for k in keys}
    print('  root mean square over the kinds:', ', '.join(f'{k} {v:.2f}' for k, v in rms.items()))
    print('log loss against the games\' results (held-out positions, no rescale):')
    for k, xs in outc.items():
        p = np.clip(np.array([x[0] for x in xs]), 1e-4, 1 - 1e-4); y = np.array([x[1] for x in xs])
        print(f"  {k:16s} {np.mean(-(y * np.log(p) + (1 - y) * np.log(1 - p))):.4f}  ({len(xs)} positions)")
if __name__ == '__main__': main()
