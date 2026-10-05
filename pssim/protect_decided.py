"""Double Protect outside decided positions (2026-10-05). The same measure as protect_replays.py / protect_sim.py (after a fresh successful
Protect, how often the Pokemon's next action is Protect again), counted only when the position at that second decision is still open:
win chance between LO and HI (default 2% and 98%; also shown for 5-95 and 10-90).
  real: win chance = the real-game value model (results/fit_real_value.json, 11 replay features) at the start of that turn
  sim:  both the planner's own value (EG_VALUE weights on the logged features; Perish Song adjustment left out) and the same real-game
        model applied to the sim position (one yardstick for both). Needs a run with BATTLE_TURNS=1 and BATTLE_FEATS=1.
Also prints calibration: how often positions the model puts below 2% / above 98% are actually won.
usage: python3 protect_decided.py real
       python3 protect_decided.py sim <results dir> [value json=egvalue7.json]"""
import json, glob, os, sys, math, collections
RV = json.load(open('results/fit_real_value.json')); WR = RV['real']             # [intercept, 11 weights]
SIM_IDX = [0, 1, 2, 3, 9, 10, 11, 12, 13, 14, 15]
sig = lambda z: 1 / (1 + math.exp(-max(-40, min(40, z))))
real_value = lambda f11: sig(WR[0] + sum(w * x for w, x in zip(WR[1:], f11)))
BANDS = [('all', 0.0, 1.0), ('2-98%', 0.02, 0.98), ('5-95%', 0.05, 0.95), ('10-90%', 0.10, 0.90)]
PROTECT = {'Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Baneful Bunker', 'Silk Trap', 'Burning Bulwark', 'Obstruct'}
def show(tag, opps):
    """opps: list of (value at the second decision from the acting side's view, protected again?, switched?, trick room up?)"""
    print(f"{tag}: {len(opps)} chances to Protect again")
    for nm, lo, hi in BANDS:
        L = [o for o in opps if lo < o[0] < hi] if nm != 'all' else opps
        if not L: continue
        tr = [o for o in L if o[3]]; no = [o for o in L if not o[3]]
        r = lambda X: f"{100 * sum(o[1] for o in X) / len(X):.1f}% of {len(X)}" if X else '-'
        print(f"   win chance {nm:7s} ({100 * len(L) / len(opps):3.0f}% of chances): Protect again {r(L)} | Trick Room up {r(tr)} | down {r(no)} | switch out {100 * sum(o[2] for o in L) / len(L):.1f}%")
    out = [o for o in opps if not (0.02 < o[0] < 0.98)]
    if out: print(f"   outside 2-98% ({len(out)}): Protect again {100 * sum(o[1] for o in out) / len(out):.1f}% (losing side <2%: "
                  f"{100 * sum(o[1] for o in out if o[0] <= 0.02) / max(1, sum(1 for o in out if o[0] <= 0.02)):.1f}% of {sum(1 for o in out if o[0] <= 0.02)}; "
                  f"winning side >98%: {100 * sum(o[1] for o in out if o[0] >= 0.98) / max(1, sum(1 for o in out if o[0] >= 0.98)):.1f}% of {sum(1 for o in out if o[0] >= 0.98)})")
def calib(tag, pos):
    """pos: list of (value, won)"""
    for nm, f in (('below 2%', lambda v: v < 0.02), ('2-10%', lambda v: 0.02 <= v < 0.10), ('90-98%', lambda v: 0.90 < v <= 0.98), ('above 98%', lambda v: v > 0.98)):
        L = [y for v, y in pos if f(v)]
        if L: print(f"   calibration, {tag}: positions rated {nm}: {len(L)} ({100 * len(L) / len(pos):.0f}% of all), actually won {100 * sum(L) / len(L):.1f}%")
EDGES = [0, .02, .05, .10, .20, .35, .50, .65, .80, .90, .95, .98, 1.0000001]
def bucket_rows(opps):
    """Protect-again rate by win-chance bucket: [lo, hi, chances, protected again, switched out]"""
    out = []
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        L = [o for o in opps if lo <= o[0] < hi]; out.append([lo, min(hi, 1.0), len(L), sum(o[1] for o in L), sum(o[2] for o in L)])
    return out
def calib_rows(pos):
    """calibration by the same buckets, both sides of every position: [lo, hi, positions, mean rated win chance, actual wins]"""
    P = pos + [(1 - v, 1 - y) for v, y in pos]; out = []
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        L = [(v, y) for v, y in P if lo <= v < hi]; out.append([lo, min(hi, 1.0), len(L), (sum(v for v, _ in L) / len(L)) if L else None, sum(y for _, y in L)])
    return out
if sys.argv[1] == 'real':
    import protect_replays as PR, replay_feats as RF
    idx = json.load(open('replays_protect/index.json')); opps = []; pos = []; ng = 0
    for f in sorted(glob.glob('replays_protect/*.log')):
        rid = os.path.basename(f)[:-4]
        if not idx.get(rid, {}).get('fmt', '').endswith('bo3'): continue
        log = open(f).read()
        if '|showteam|' not in log: continue
        try: rows, w, _ = RF.game(log)
        except Exception: continue
        if w is None or not rows: continue
        ng += 1; val = {t: real_value(fx) for t, fx in rows}                   # p1's win chance at the start of turn t
        for t, fx in rows: pos.append((val[t], 1 if w == 'p1' else 0))
        T = PR.acts(log)                                                      # T[i] = turn i + 1
        for i in range(len(T) - 1):
            for p, a in T[i]['act'].items():
                fresh = a[0] == 'move' and a[1] in PROTECT and a[2] and not (i > 0 and T[i - 1]['act'].get(p, ('',))[0] == 'move' and T[i - 1]['act'][p][1] in PROTECT)
                if not fresh: continue
                nxt = T[i + 1]['act'].get(p)
                if nxt is None or T[i + 1]['start'].get(p) != T[i]['start'].get(p) or (i + 2) not in val: continue
                v = val[i + 2] if p.startswith('p1') else 1 - val[i + 2]
                opps.append((v, nxt[0] == 'move' and nxt[1] in PROTECT, nxt[0] == 'switch', T[i + 1]['tr']))
    show(f"real Bo3 ({ng} games; win chance from the real-game value model)", opps); calib('real-game model on real games', pos)
    json.dump({'games': ng, 'protect': bucket_rows(opps), 'calib': calib_rows(pos)}, open('results/protect_decided_real.json', 'w'))
else:
    import protect_sim as PS
    d = sys.argv[2]; ev = json.load(open(sys.argv[3] if len(sys.argv) > 3 else 'egvalue7.json')); b0, W = ev['b0'], ev['w']
    own = lambda F: sig(b0 + sum(w * x for w, x in zip(W, F)))
    O = {(s, y): [] for s in 'ab' for y in ('own', 'real')}; pos = {'own': [], 'real': []}; ng = 0
    for f in glob.glob(d + '/*.json') + glob.glob(d + '_*/*.json'):          # one folder, or <d>_a, <d>_b, ... (a run split in parts)
        try: r = json.load(open(f))
        except Exception: continue
        fe = r.get('feats') or []
        if len(fe) != len(r['rows']): continue
        for g, ft in zip(r['rows'], fe):
            S = g.get('states') or []; F = ft['F']
            if g.get('v') not in (0, 1, 0.0, 1.0) or len(F) < len(S): continue
            ng += 1
            vo = [own(x) for x in F]; vr = [real_value([x[i] for i in SIM_IDX]) for x in F]
            for k in range(len(S)): pos['own'].append((vo[k], g['v'])); pos['real'].append((vr[k], g['v']))
            for side in 'ab':
                A = [PS.parse(s[side]) for s in S]
                for t in range(len(A) - 1):
                    for mon, a in A[t].items():
                        if a not in PROTECT or (t > 0 and A[t - 1].get(mon) in PROTECT): continue
                        nxt = A[t + 1].get(mon)
                        if nxt is None: continue
                        for y, vv in (('own', vo), ('real', vr)):
                            v = vv[t + 1] if side == 'a' else 1 - vv[t + 1]
                            O[(side, y)].append((v, nxt in PROTECT, nxt == 'switch', S[t + 1].get('tr', 0) > 0))
    for side, nm in (('b', 'theirs'), ('a', 'mine')):
        show(f"sim {nm} ({ng} games; win chance from the planner's own value)", O[(side, 'own')])
        show(f"sim {nm} ({ng} games; win chance from the real-game value model)", O[(side, 'real')])
    calib("planner's value on sim games", pos['own']); calib('real-game model on sim games', pos['real'])
    json.dump({'games': ng, 'protect': {f'{nm}_{y}': bucket_rows(O[(sd, y)]) for sd, nm in (('b', 'theirs'), ('a', 'mine')) for y in ('own', 'real')},
               'calib': {y: calib_rows(pos[y]) for y in ('own', 'real')}}, open('results/protect_decided_sim.json', 'w'))
