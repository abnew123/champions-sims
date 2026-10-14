"""How bad are the bot's worst plays? (2026-10-12, the user: look for bugs that make for terrible play.) Every decision in the saved
ladder games is rebuilt as the bot saw it (botpos, the log up to its request) and solved by the engine the way the bot solves it
(champ evalpos, 32 seeds, staged):
  turns          what the bot played (from the log) against the best joint option, both valued against the opponent's equilibrium mix:
                 regret = best value - played value (win chance, raw engine value). Large regrets are either the mix's small weights on
                 worse options (bot/planner_issues.md 2) or a live decision that differs from the rebuilt one.
  replacements   after a faint, the bot picks its replacement by the engine's static value at the next turn's start (position.py
                 replacement); here every candidate is solved with the one-turn search instead, and the bot's pick is compared to the best.
  .venv/bin/python3 bot/decision_audit.py build <prefix>      positions (prefix: a path without extension, e.g. bot/out/pos/audit)
  .venv/bin/python3 bot/decision_audit.py eval <prefix> [threads=6]
  .venv/bin/python3 bot/decision_audit.py report <prefix> [n=25]"""
import os, sys, json, itertools, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'evalbar')); sys.path.insert(0, os.path.join(ROOT, 'bot'))
os.environ.setdefault('CHAMP_MAIN', ROOT)
import belief_test as BT
def toid(s): return ''.join(c for c in (s or '').lower() if c.isalnum())
def games():
    G = [json.loads(l) for l in open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl'))]
    teams = {t['name']: t for t in json.load(open(os.path.join(ROOT, 'bot', 'teams.json')))}
    pf = os.path.join(ROOT, 'bot', 'out', 'regional_pool.json')
    # games with a team no longer in the pool (the Perish Song teams, dropped 2026-10-12) are skipped
    pool ={t['name']: t for t in json.load(open(pf))} if os.path.exists(pf) else {}
    # AUDIT_FORMAT / AUDIT_SINCE / AUDIT_UNTIL (2026-10-14, the Bo1 slump): only that format's games, recorded in [since, until) (UTC ISO)
    fmt, since, until = os.environ.get('AUDIT_FORMAT'), os.environ.get('AUDIT_SINCE', ''), os.environ.get('AUDIT_UNTIL', '9')
    for g in G:
        if fmt and g.get('format', 'gen9championsvgc2026regmcbo3') != fmt: continue
        if not (since <= g['when'] < until): continue
        f = os.path.join(ROOT, 'bot', 'out', g['room'] + '.log')
        team = teams.get(g.get('team')) or pool.get(g.get('team'))
        if os.path.exists(f) and team: yield g, team, open(f, errors='ignore').read().split('\n')
def engine_order(st, side, req=None):
    """position letter -> engine slot letter: the engine lists the living actives first (a lone Pokemon in position b is slot a)"""
    if req is not None:
        on = [k for k in (0, 1) if k < len(req['side']['pokemon']) and req['side']['pokemon'][k].get('active') and not req['side']['pokemon'][k]['condition'].endswith(' fnt')]
        return {'ab'[k]: 'ab'[i] for i, k in enumerate(on)}
    on = sorted([m for m in st[side]['mons'] if m['pos'] in ('a', 'b') and not m['f']], key=lambda m: m['pos'])
    return {m['pos']: 'ab'[i] for i, m in enumerate(on)}
def build(prefix):
    import botpos as BP, live as LV, position as POS, replay as R
    turn_specs = []; rep_specs = []; meta = {'turns': {}, 'reps': {}}
    for g, team, L in games():
        me = g['side']; op = 'p2' if me == 'p1' else 'p1'; full = '\n'.join(L)
        steps = {s['turn']: s for s in R.parse(full)['steps']}
        turn = 0; exp = POS.export(team['sets'])
        for i, l in enumerate(L):
            if l.startswith('|turn|'): turn = int(l.split('|')[2]); continue
            if not l.startswith('|request|'): continue
            try: req = json.loads(l[9:])
            except Exception: continue
            # as brain.py does: a log without open sheets (Bo1) gets the opponent's guessed sets and ours written in as sheets (bot/bo1.py)
            import bo1; log = '\n'.join(bo1.inject(list(L[:i]), op, team['sets'], me))
            if req.get('active') and not req.get('forceSwitch') and not req.get('wait') and turn:
                try: specs, info = BP.bot_position(log, req, me, topk=1, team=exp, tag='bot')
                except Exception: continue
                if not specs: continue
                st = R.parse(log)['steps'][-1]['state']; acts = (steps.get(turn) or {}).get('acts', {})
                eng = {me: engine_order(st, me, req), op: engine_order(st, op)}
                def act(sd, j):
                    pos = next((p for p, e in eng[sd].items() if e == 'ab'[j]), None)
                    a = acts.get(sd + pos) if pos else None
                    if a and a.get('target'):
                        ts = a['target'][:2]; a = {**a, 'target': ('p1' if ts == me else 'p2') + eng[ts].get(a['target'][2], a['target'][2])}
                    return a
                name = f"{g['room'][-14:]} t{turn}"
                for w, sp in specs:
                    sp = json.loads(json.dumps(sp)); sp['name'] = name + sp['name'][len(sp['name'].split(' h')[0]):]
                    sp['acts'] = [[act(me, 0), act(me, 1)], [act(op, 0), act(op, 1)]]
                    turn_specs.append((w, sp))
                meta['turns'][name] = {'room': g['room'], 'turn': turn, 'team': g['team'], 'won': g['won'], 'w': [w for w, _ in specs]}
            elif req.get('forceSwitch') and not req.get('wait'):
                need = req['forceSwitch']; mons = req['side']['pokemon']; slots = [k for k, m in enumerate(need) if m]
                bench = [p['details'].split(',')[0] for p in mons if not p.get('active') and not p['condition'].endswith(' fnt')]
                cands = list(itertools.permutations(bench, min(len(slots), len(bench))))
                if len(cands) < 2: continue
                # what the bot sent in: its side's switch lines after the request, up to the next turn
                chosen = {}
                for l2 in L[i + 1:]:
                    if l2.startswith('|turn|'): break
                    q = l2.split('|')
                    if len(q) > 3 and q[1] == 'switch' and q[2].startswith(me) and 'ab'.index(q[2][2]) in slots and q[2][2] not in chosen: chosen[q[2][2]] = q[3].split(',')[0]
                name = f"{g['room'][-14:]} r{turn}_{i}"; meta['reps'][name] = {'room': g['room'], 'turn': turn, 'chosen': chosen, 'cands': {}}
                for ci, cand in enumerate(cands):
                    rep = {'ab'[slots[j]]: sp for j, sp in enumerate(cand)}
                    try: specs, info = BP.bot_replacement(log, req, me, rep, topk=1)
                    except Exception: specs = []
                    if not specs: continue
                    cn = f'{name} c{ci}'; meta['reps'][name]['cands'][cn] = {'rep': rep, 'w': []}
                    for k, (w, sp) in enumerate(specs):
                        sp = json.loads(json.dumps(sp)); sp['name'] = f'{cn} b{k}'; rep_specs.append((w, sp)); meta['reps'][name]['cands'][cn]['w'].append([sp['name'] + ' p1', w])
    for tag, S in (('turns', turn_specs), ('reps', rep_specs)):
        f = f'{prefix}_{tag}.pos.jsonl'
        if os.path.exists(f): os.remove(f)
        if S: LV.positions(S, f)
    json.dump(meta, open(prefix + '.meta.json', 'w'))
    print(f"{len(meta['turns'])} turn decisions ({len(turn_specs)} positions), {len(meta['reps'])} replacements ({len(rep_specs)} positions) -> {prefix}_*.pos.jsonl")
def evaluate(prefix, threads=6):
    if os.environ.get('AUDIT_LIVE'):   # the bot's own pipeline (position.run_eval: its engine link, net, calc data and own-side rules)
        import position as POS
        for tag in ('turns', 'reps'):
            posf = f'{prefix}_{tag}.pos.jsonl'; outf = f'{prefix}_{tag}.eval.jsonl'
            if os.path.exists(posf):
                if os.path.exists(outf): os.remove(outf)
                POS.run_eval(posf, outf, threads, 32)
        return
    import engine as EN
    env = {'EG_MEGA_TIE': '0', 'EG_LAST_PROTECT': '0', 'EG_NO_DOUBLE_PROTECT': '0'}
    os.environ.update({k: v for k, v in env.items() if k not in os.environ})
    os.environ.setdefault('CHAMP_BIN', os.path.join(ROOT, 'native', 'champ', 'bin', 'battlesim-champ'))   # the bot's engine (position.py); os.environ.setdefault('CHAMP_DATA', 'engine_data_full.json')
    for tag in ('turns', 'reps'):
        posf = f'{prefix}_{tag}.pos.jsonl'; outf = f'{prefix}_{tag}.eval.jsonl'
        if os.path.exists(posf): EN.run(posf, outf, threads, 32, 1)
def report(prefix, n=25):
    meta = json.load(open(prefix + '.meta.json'))
    rows = {}
    for tag in ('turns', 'reps'):
        f = f'{prefix}_{tag}.eval.jsonl'
        if os.path.exists(f): rows.update({r['name']: r for r in map(json.loads, open(f)) if 'error' not in r})
    # turns: the first hypothesis (topk=1: there is one)
    T = []
    for name, m in meta['turns'].items():
        r = rows.get(name + ' h0 p1')
        if not r: continue
        s0 = r['sides'][0]; best = max(j['v'] for j in s0['joint']) if s0['joint'] else None
        if best is None or s0.get('actual_v') is None: continue
        pick = max(s0['joint'], key=lambda j: j['v'])
        played = [next((o['label'] for o in sl['options'] if o.get('actual')), '?') for sl in s0['slots']]
        T.append((best - s0['actual_v'], name, m, best, s0['actual_v'], pick['label'], ' | '.join(f"{sl['mon']}: {p}" for sl, p in zip(s0['slots'], played)), r['value']))
    print(f"turns: {len(T)} decisions with the played option known (of {len(meta['turns'])})")
    if T:
        rg = sorted(x[0] for x in T)
        for c in (0.02, 0.05, 0.10, 0.20): print(f"  regret over {100 * c:.0f} points: {sum(1 for x in rg if x > c)}")
        print(f"  mean regret {100 * sum(rg) / len(rg):.2f} points per decision")
        print("  worst:")
        for x in sorted(T, reverse=True)[:n]:
            print(f"    -{100 * x[0]:4.1f}  {x[1]}  (game value {100 * x[7]:.0f}%)\n           played {x[6]}  [{100 * x[4]:.0f}%]\n           best   {x[5]}  [{100 * x[3]:.0f}%]")
    RP = []
    for name, m in meta['reps'].items():
        vals = {}
        for cn, c in m['cands'].items():
            ws = [(rows[k]['value'], w) for k, w in c['w'] if k in rows]
            if ws: vals[cn] = (sum(v * w for v, w in ws) / sum(w for _, w in ws), c['rep'])
        if len(vals) < 2: continue
        ch = next((cn for cn, (v, rep) in vals.items() if all(toid(rep.get(s, '')).split('mega')[0] == toid(sp).split('mega')[0] for s, sp in m['chosen'].items()) and m['chosen']), None)
        if not ch: continue
        bn = max(vals, key=lambda k: vals[k][0])
        RP.append((vals[bn][0] - vals[ch][0], name, m, vals[ch], vals[bn], len(vals)))
    print(f"\nreplacements: {len(RP)} with two or more candidates and the pick known")
    if RP:
        rg = sorted(x[0] for x in RP)
        for c in (0.02, 0.05, 0.10, 0.20): print(f"  the search prefers another candidate by over {100 * c:.0f} points: {sum(1 for x in rg if x > c)}")
        print(f"  mean regret {100 * sum(rg) / len(rg):.2f} points per replacement; the search agrees with the pick in {sum(1 for x in RP if x[0] <= 1e-9)}")
        for x in sorted(RP, reverse=True)[:n]:
            print(f"    -{100 * x[0]:4.1f}  {x[1]}  chose {x[3][1]} [{100 * x[3][0]:.0f}%], search best {x[4][1]} [{100 * x[4][0]:.0f}%] of {x[5]}")
def exact(prefix, cut=0.05, threads=6):
    """The staged solve gives options outside the mix only 2-8 seeds per cell, so the best of many such options reads high (a 62% double
    switch that is noise). Here the decisions whose staged regret is over `cut` are solved again with every cell at 32 seeds
    (EVAL_MATRIX=full) and the zero-sum game solved exactly (linear programming): regret = the best row against the opponent's exact
    mix minus the played row, and the played row's weight in the exact mix."""
    import numpy as np, engine as EN
    from scipy.optimize import linprog
    meta = json.load(open(prefix + '.meta.json'))
    rows = {r['name']: r for r in map(json.loads, open(f'{prefix}_turns.eval.jsonl')) if 'error' not in r}
    pick = []
    for name, m in meta['turns'].items():
        r = rows.get(name + ' h0 p1')
        if r and r['sides'][0].get('actual_v') is not None and r['sides'][0]['joint'] and max(j['v'] for j in r['sides'][0]['joint']) - r['sides'][0]['actual_v'] > cut: pick.append(name + ' h0')
    P = [json.loads(l) for l in open(f'{prefix}_turns.pos.jsonl')]
    posf = f'{prefix}_exact.pos.jsonl'; outf = f'{prefix}_exact.eval.jsonl'
    with open(posf, 'w') as f:
        for p in P:
            if p['name'].rsplit(' ', 1)[0] in pick: f.write(json.dumps(p) + '\n')
    os.environ.setdefault('CHAMP_BIN', os.path.join(ROOT, 'native', 'champ', 'bin', 'battlesim-champ')); os.environ.setdefault('CHAMP_DATA', 'engine_data_full.json')
    os.environ.update({'EG_MEGA_TIE': '0', 'EG_LAST_PROTECT': '0', 'EG_NO_DOUBLE_PROTECT': '0'})
    EN.run(posf, outf, threads, 32, 1, extra={'EVAL_MATRIX': 'full'})
    def solve(A):   # row player maximizes: max v s.t. A^T x >= v, sum x = 1
        n, k = A.shape
        res = linprog(np.r_[np.zeros(n), -1.0], A_ub=np.c_[-A.T, np.ones(k)], b_ub=np.zeros(k), A_eq=np.r_[np.ones(n), 0.0][None], b_eq=[1.0],
                      bounds=[(0, None)] * n + [(None, None)], method='highs')
        return res.x[:n], -res.fun
    out = []
    for r in map(json.loads, open(outf)):
        if 'error' in r or 'matrix' not in r: continue
        M = r['matrix']; A = np.array(M['v1'], float); x, v = solve(A); y, _ = solve(1 - A.T)
        s0 = r['sides'][0]
        played = [next((o for o in sl['options'] if o.get('actual')), None) for sl in s0['slots']]
        lab = ' | '.join(f"{sl['mon']}: {o['label']}" for sl, o in zip(s0['slots'], played) if o)
        k = next((i for i, l in enumerate(M['rl']) if l == lab), None)
        if k is None: continue
        vs = A @ y; b = int(np.argmax(vs))
        out.append((float(vs[b] - vs[k]), r['name'], float(x[k]), lab, M['rl'][b], float(vs[k]), float(vs[b]), v))
    out.sort(reverse=True)
    print(f"{len(out)} decisions re-solved exactly (staged regret over {100 * cut:.0f} points: {len(pick)})")
    for c in (0.02, 0.05, 0.10): print(f"  exact regret over {100 * c:.0f} points: {sum(1 for x in out if x[0] > c)}")
    for x in out[:20]:
        print(f"    -{100 * x[0]:4.1f}  {x[1]}  played (weight {100 * x[2]:.0f}% in the exact mix) {x[3]} [{100 * x[5]:.0f}%]\n           best {x[4]} [{100 * x[6]:.0f}%]  game {100 * x[7]:.0f}%")
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'build': build(a[1])
    elif a[0] == 'eval': evaluate(a[1], int(a[2]) if len(a) > 2 else 6)
    elif a[0] == 'report': report(a[1], int(a[2]) if len(a) > 2 else 25)
    elif a[0] == 'exact': exact(a[1], float(a[2]) if len(a) > 2 else 0.05, int(a[3]) if len(a) > 3 else 6)
