"""Does not knowing the opponent's spreads explain how players differ from the planner? The planner is handed one spread per Pokemon (the
species' most common one for its team-sheet nature: spots.py evs_for); players see the sheet (item, ability, nature, moves) but not the
stat points. For every turn of the day-1 broadcast games, the most likely position as the players knew it is evaluated three ways, every
cell of the payoff matrix computed (champ-battle-v18, EVAL_MATRIX=full):
  known       the planner's usual spreads, 32 samples per cell
  uncertain   4 versions with one side's spreads drawn from a pool per Pokemon (pool(): the Smogon spreads with the sheet's nature, and an
              offensive and a bulky spread), 8 samples each, so the same 32 samples per cell. Player 1's mix is solved
              on the average of the 4 matrices where Player 2's spreads were drawn, and Player 2's on those where Player 1's were: each
              player unsure of the other's spreads, sure of their own.
Both are solved the way evalpos solves a turn (plan.rs nash: 400 rounds of regret matching; the switch anticipation pass), and compared
with what players chose (the study's decisions, by action): top-pick agreement, the planner's probability on the played action, the log
score (mean ln of that probability, floored at 0.001) and the planned shares of Protect, switch and attack.
  python3 evalbar/uncertain.py build                 the positions (evalbar/out/uncertain/)
  python3 evalbar/uncertain.py run [threads=3]       evalpos on them
  python3 evalbar/uncertain.py report                the comparison
Needs numpy: run it with the main folder's .venv python (it keeps the evalbar-py name)."""
import os, sys, re, json, math, copy, random, collections
import numpy as np
import common as C, procs as P, replay as R, live as LV, engine as EN, study as ST, reads as RD
OUT = os.path.join(C.HERE, 'out', 'uncertain'); K = 4
STATS = os.path.join(C.REPO, 'regionals', 'smogon_mc_2026-09_moveset.txt')
ORDER = ['hp', 'atk', 'def', 'spa', 'spd', 'spe']
def smogon_spreads():
    """{species: [(nature, [stat points], usage %)]} from the Smogon moveset stats"""
    out = {}; name = None; inside = False; L = open(STATS).read().split('\n')
    for i, l in enumerate(L):
        m = re.match(r'^\s*\| ([^|]+?)\s+\|\s*$', l)
        if m and i and L[i - 1].strip().startswith('+--') and i + 1 < len(L) and L[i + 1].strip().startswith('+--') and '%' not in m.group(1):
            name = m.group(1); inside = False; continue
        if m and m.group(1) == 'Spreads': inside = True; continue
        if inside:
            s = re.match(r'^\s*\| (\w+):(\d+)/(\d+)/(\d+)/(\d+)/(\d+)/(\d+) ([\d.]+)%', l)
            if s: out.setdefault(name, []).append((s.group(1), [int(x) for x in s.groups()[1:7]], float(s.group(8))))
            elif not l.strip().startswith('| Other'): inside = False
    return out
SPREADS = None
def pool(mon):
    """the spreads a player would think likely for this Pokemon. The Smogon stats list only the top six spreads (most usage is "Other"), so
    half the weight goes to the listed spreads with its nature (or the same raised stat), by usage, and a quarter each to an offensive and a
    bulky spread that fit the nature (no Speed investment under a Speed-lowering nature)"""
    global SPREADS
    if SPREADS is None: SPREADS = smogon_spreads()
    E = LV.S.E; nat = lambda n: E['natures'].get(R.toid(n), {})
    sp = mon['species']; mg = LV.S.mega_of(sp, mon.get('item', ''))
    rows = SPREADS.get(mg or '', []) or SPREADS.get(sp, []); plus, minus = nat(mon['nature']).get('plus'), nat(mon['nature']).get('minus')
    same = [(evs, w) for n, evs, w in rows if n == mon['nature']] or [(evs, w) for n, evs, w in rows if plus and nat(n).get('plus') == plus]
    if not same: same = [(list(mon['evs']), 1.0)]
    tot = sum(w for _, w in same); out = [(e, 0.5 * w / tot) for e, w in same]
    cat = [LV.S.MV.get(R.toid(m), {}).get('cat') for m in mon.get('moves', [])]
    att = plus if plus in ('atk', 'spa') else ('atk' if cat.count('Physical') >= cat.count('Special') else 'spa')
    off = dict.fromkeys(ORDER, 0); off.update({att: 32, 'hp': 2} if minus != 'spe' else {att: 32, 'hp': 32}); off.setdefault('spe', 0)
    if minus != 'spe': off['spe'] = 32
    else: off['spd'] = 2
    bulk = dict.fromkeys(ORDER, 0)
    bulk.update({'hp': 32, plus: 32, ('spd' if plus == 'def' else 'def'): 2} if plus in ('def', 'spd') else {'hp': 32, 'def': 12, 'spd': 12, att: 10})
    return out + [([off[k] for k in ORDER], 0.25), ([bulk[k] for k in ORDER], 0.25)]
def variant(spec, side, k):
    """a copy of the position with one side's spreads drawn from their pools"""
    v = copy.deepcopy(spec); v['name'] = f"{spec['name']} s{side}k{k}"
    for i, mon in enumerate(v['sides'][side]['mons']):
        P_ = pool(mon); rng = random.Random(f"{spec['name']}|{side}|{k}|{i}")
        mon['evs'] = list(rng.choices([e for e, _ in P_], weights=[w for _, w in P_])[0])
    return v
def games():
    return sorted(f[:-4] for f in os.listdir(ST.OUT) if re.fullmatch(r'day1_m\d+g\d+\.log', f))
def build():
    os.makedirs(OUT, exist_ok=True); n = 0
    for tag in games():
        f = os.path.join(ST.OUT, tag + '.log'); log = open(f).read(); g = R.parse(log)
        L = LV.Live(None, 1, 0, logfile=f, tag=tag, fmt='Champions broadcast'); base = []; var = []
        for st in g['steps']:
            if st['turn'] < 1: continue
            sp, _ = L.at(log, st['turn'])
            if not sp: continue
            w, spec = max(sp, key=lambda x: x[0]); base.append((1, spec))
            var += [(1, variant(spec, side, k)) for side in (0, 1) for k in range(K)]
        if not base: continue
        LV.positions(base, os.path.join(OUT, tag + '_base_pos.jsonl')); LV.positions(var, os.path.join(OUT, tag + '_var_pos.jsonl')); n += len(base)
    print(n, 'turns,', n * (1 + 2 * K), 'positions')
def run(threads=3):
    os.environ['EVAL_MATRIX'] = 'full'; os.environ['CHAMP_BIN'] = os.path.join(C.MAIN, 'native', 'champ', 'bin', 'champ-battle-v18')
    for i, tag in enumerate(games()):
        for kind, seeds in (('base', 32), ('var', 8)):
            pf = os.path.join(OUT, f'{tag}_{kind}_pos.jsonl')
            if not os.path.exists(pf): continue
            os.environ['EVAL_TITLE'] = f'Spread uncertainty: {tag} {kind} ({i + 1} of {len(games())})'
            EN.run(pf, os.path.join(OUT, f'{tag}_{kind}_eval.jsonl'), threads, seeds, 1)
# ---- the turn solved as evalpos solves it (plan.rs nash and eval_one's solve)
def nash(a, iters=400):
    m, n = a.shape; rr = np.zeros(m); rc = np.zeros(n); sr = np.zeros(m); sc = np.zeros(n)
    def norm(r):
        p = np.maximum(r, 0); t = p.sum(); return p / t if t > 0 else np.full(len(r), 1 / len(r))
    for _ in range(iters):
        x, y = norm(rr), norm(rc); ur = a @ y; v = x @ ur; uc = -(x @ a)
        rr = np.maximum(rr + ur - v, 0); sr += x; rc = np.maximum(rc + uc + v, 0); sc += y
    return sr / sr.sum(), sc / sc.sum()
def solve(V, rows, cols):
    """V: side 0's values, rows x cols; rows / cols: joint actions as [slot0 c, slot1 c] -> the two mixes"""
    sw = lambda c: any(x and x[0] == 'switch' for x in c)
    mns = [i for i, r in enumerate(rows) if not sw(r)]; tns = [j for j, c in enumerate(cols) if not sw(c)]
    x = nash(V[:, tns])[0] if tns else np.full(len(rows), 1 / len(rows))
    y = nash(V[mns, :])[1] if mns else np.full(len(cols), 1 / len(cols))
    isw = [i for i in range(len(rows)) if sw(rows[i]) and x[i] > 0.02]; jsw = [j for j in range(len(cols)) if sw(cols[j]) and y[j] > 0.02]
    if jsw: x = nash(V[:, tns + jsw])[0]
    if isw: y = nash(V[mns + isw, :])[1]
    return x, y
def per_action(e, mix, side, mon):
    """a joint mix -> {action: probability} for one Pokemon"""
    M = e['matrix']; joints = M['rows'] if side == 0 else M['cols']; K_ = RD.keys(e['sides'][side]); sl = RD.find(K_, mon)
    if sl is None: return None
    out = collections.Counter()
    for p, j in zip(mix, joints):
        a = K_[sl][1].get(json.dumps(j[sl][:2])) if j[sl] else None
        if a: out[a] += p
    return out
def report():
    D = collections.defaultdict(list)
    for d in json.load(open(os.path.join(ST.OUT, 'day1.json')))['decisions']: D[(d['game'], d['turn'])].append(d)
    res = {'known': [], 'uncertain': []}; skipped = 0
    for tag in games():
        bf, vf = (os.path.join(OUT, f'{tag}_{k}_eval.jsonl') for k in ('base', 'var'))
        if not (os.path.exists(bf) and os.path.exists(vf)): continue
        base = {x['name']: x for x in map(json.loads, open(bf)) if 'matrix' in x}; var = {x['name']: x for x in map(json.loads, open(vf)) if 'matrix' in x}
        for name, e in base.items():
            t = e['turn']; M = e['matrix']; stem = name[:-3]                  # "<game> t<turn> h<k>" without " p1"
            V0 = np.array(M['v1']); x0, y0 = solve(V0, M['rows'], M['cols'])
            avg = {}
            for side in (0, 1):
                vs = [var.get(f'{stem} s{side}k{k} p1') for k in range(K)]
                vs = [v for v in vs if v and v['matrix']['rl'] == M['rl'] and v['matrix']['cl'] == M['cl']]
                avg[side] = np.mean([np.array(v['matrix']['v1']) for v in vs], axis=0) if len(vs) == K else None
            if avg[0] is None or avg[1] is None: skipped += 1; continue
            x1 = solve(avg[1], M['rows'], M['cols'])[0]; y1 = solve(avg[0], M['rows'], M['cols'])[1]   # P1 unsure of P2's spreads, and back
            for d in D[(tag, t)]:
                s = 0 if d['side'] == 'p1' else 1
                for kind, mix in (('known', x0 if s == 0 else y0), ('uncertain', x1 if s == 0 else y1)):
                    pa = per_action(e, mix, s, d['mon'])
                    if pa and d['played'] in pa: res[kind].append({'p': pa[d['played']], 'mix': dict(pa), 'played': d['played'], 'top': max(pa, key=pa.get)})
    n = min(len(res['known']), len(res['uncertain']))
    print(f"{n} decisions ({skipped} turns skipped: a variant's actions differed or was missing)")
    for kind, R_ in res.items():
        top = sum(r['played'] == r['top'] for r in R_) / len(R_); pp = sum(r['p'] for r in R_) / len(R_)
        ll = sum(math.log(max(1e-3, r['p'])) for r in R_) / len(R_); sharp = sum(max(r['mix'].values()) for r in R_) / len(R_)
        sh = collections.Counter()
        for r in R_:
            for a, p in r['mix'].items(): sh[ST.kind(a)] += p / len(R_)
        print(f"{kind:9s}: top pick {100 * top:.1f}% | probability on the played action {100 * pp:.1f}% | log score {ll:.3f} | top option's "
              f"probability {100 * sharp:.1f}% | planned Protect {100 * sh['Protect']:.1f}% switch {100 * sh['switch']:.1f}% attack {100 * sh['attack']:.1f}%")
    pl = collections.Counter(ST.kind(r['played']) for r in res['known'])
    print(f"played   : Protect {100 * pl['Protect'] / len(res['known']):.1f}% switch {100 * pl['switch'] / len(res['known']):.1f}% attack {100 * pl['attack'] / len(res['known']):.1f}%")
    json.dump(res, open(os.path.join(OUT, 'report.json'), 'w'))
if __name__ == '__main__':
    P.own()
    a = sys.argv[1:]
    if a and a[0] == 'build': build()
    elif a and a[0] == 'run': run(int(a[1]) if len(a) > 1 else 3)
    elif a and a[0] == 'report': report()
    else: sys.exit(__doc__)
