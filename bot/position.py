"""Position building and the decision for one turn (bot/brain.py calls these).
  build(log_lines, request, side) -> (specs, info) from the Eval bar thread's evalbar/botpos.py: the opponent's side as a spectator knows
       it (open sheets, reveals, its most likely back row), our side exactly from the |request|; we are side 0
  decide(specs, request, side) -> ("move 1 2, move 2 1", note): live.positions writes the engine position, engine.run evaluates it
       (champ evalpos, 32 seeds, staged, the kit's value), a joint action is sampled from side 0's mix and mapped to /choose syntax
  replacement(request, log, side) -> "switch 3[, switch 4]" for a forceSwitch request (each candidate by the one-turn search)"""
import os, sys, json, random, re, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); EB = os.path.join(ROOT, 'evalbar')
sys.path.insert(0, EB); sys.path.insert(0, os.path.join(ROOT, 'pssim'))
# the bot's engine (2026-10-12, the user: go with the search-trained learned value; evening: "put all the changes in"): a frozen copy of
# the dev build with the day's Showdown-exact fixes and ports (bin/champ-bot-2026-10-12b, sha256 beside it; the morning's was -12),
# scoring every leaf with the h64 net distilled from the one-turn search, refitted on the full damage-calc data
# (bot/value/vnet_h64_search_fc.json: held-out search tied with the first net, self-play +4.9 ± 1.5 against the static value over 1,600
# games); the net's inputs need RACE_PRIO and FEATS22, and CALC_DATA must be champions_data_full.json, which it was fitted with.
# 2026-10-13 evening (the user: "lets move both over"): champ-battle-v29 (the accuracy fix, Revival Blessing, Unseen Fist, Flying Press
# and the other ports, partner targets) through its own link, so a brain started before the move keeps the old engine and net together
# until its restart; the net refitted after the accuracy fix (vnet_h64_search_acc.json: the features changed with it)
os.environ.setdefault('CHAMP_BIN', os.path.join(ROOT, 'native', 'champ', 'bin', 'battlesim-champ29-bot'))
os.environ.setdefault('EG_VNET', os.path.join(ROOT, 'bot', 'value', 'vnet_h64_search_acc.json'))
os.environ.setdefault('RACE_PRIO', '1'); os.environ.setdefault('FEATS22', '1')
os.environ.setdefault('CHAMP_DATA', 'engine_data_full.json')
os.environ.setdefault('EG_MEGA_TIE', '0')
os.environ.setdefault('EG_LAST_PROTECT', '0')   # our last Pokemon never Protects when it changes nothing (side 0 is the bot); the user, 2026-10-11
os.environ.setdefault('EG_NO_DOUBLE_PROTECT', '0')   # and no Pokemon of ours Protects two turns running (the user, 2026-10-11; self-play -1.2 +- 0.7)
STALL = {'Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Baneful Bunker', 'Burning Bulwark', 'Silk Trap', 'Obstruct', 'Max Guard'}
def protect_chains(log, side):
    """per Pokemon of ours (by species), how many turns running it has used a Protect-type move up to now (success or not)"""
    text = '\n'.join(log) if isinstance(log, list) else (log or ''); turn = 0; last = {}; chain = {}
    for l in text.split('\n'):
        p = l.split('|')
        if len(p) > 2 and p[1] == 'turn': turn = int(p[2])
        elif len(p) > 3 and p[1] == 'move' and p[2].startswith(side) and not any(x.startswith('[from]') for x in p[4:]):
            mon = p[2].split(': ', 1)[-1]
            if p[3] in STALL: chain[mon] = chain.get(mon, 0) + 1 if last.get(mon) == turn - 1 else 1; last[mon] = turn
            else: chain[mon] = 0
    return {m: c for m, c in chain.items() if last.get(m) == turn - 1}
import botpos as BP, live as LV, engine as EN
import procs as P
for _prog, _path in (('champ', os.environ['CHAMP_BIN']), ('node', None)):   # the Eval bar's process-name links, made once here so two
    try: P.exe(_prog, _path)                                                   # brains starting together do not race to create them
    except FileExistsError: pass
OUT = os.path.join(ROOT, 'bot', 'out', 'pos'); os.makedirs(OUT, exist_ok=True)
D = json.load(open(os.path.join(ROOT, 'native', 'engine_data_full.json'))); TYPES = D['types']; MOVES = D['moves']
SPECIES = {s['name']: s for s in D['species'].values()}
toid = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
STAT = ['HP', 'Atk', 'Def', 'SpA', 'SpD', 'Spe']
def export(sets):
    """our team as a Showdown export (stat points on the EVs line, as botpos reads them), so our own spreads are exact, not guessed"""
    out = []
    for x in sets:
        ev = ' / '.join(f'{v} {STAT[i]}' for i, v in enumerate(x.get('evs') or []) if v)
        out.append('\n'.join([f"{x['species']} @ {x['item']}", f"Ability: {x['ability']}"] + ([f'EVs: {ev}'] if ev else []) + [f"{x['nature']} Nature"] + [f'- {m}' for m in x['moves']]))
    return '\n\n'.join(out)
def build(log, request, side, topk=1, team=None):
    text = '\n'.join(log) if isinstance(log, list) else log
    specs, info = BP.bot_position(text, request, side, topk=topk, team=export(team) if team else None, tag='bot')
    if not specs: raise RuntimeError('no position: ' + str(info.get('skip')))
    return specs, info
def run_eval(posf, outf, threads=2, seeds=32, extra=None):
    """champ evalpos as the Eval bar's engine.run does it, but started through the bot's own link (CHAMP_BIN: battlesim-champ-bot), not
    the shared evalbar-champ link that every caller repoints to its own binary (2026-10-12: the bot could start the Eval bar's engine)"""
    import subprocess
    grid = os.path.join(EB, 'out', 'emptygrid'); os.makedirs(grid, exist_ok=True)
    env = {**os.environ, 'RACE_TIES': 'avg', 'EVAL_SEEDS': str(seeds), 'EVAL_ADAPT': '1', 'EG_VALUE': os.environ.get('EG_VALUE', 'egvalue9_sym2.json'), 'RACE': '1', 'TRSYM': '1',
           'CALC_DATA': '../native/champions_data_full.json', 'GRID_DIR': grid, **(extra or {})}
    subprocess.run([os.environ['CHAMP_BIN'], 'evalpos', '../native/' + os.environ['CHAMP_DATA'], os.path.abspath(posf), os.path.abspath(outf), str(threads)],
                   cwd=os.path.join(ROOT, 'pssim'), env=env, check=True)
# contempt (2026-10-12 evening, the user: the Bo3 bot as the exploiter): limits.json "contempt": {format: c}, read every decision; 0 = the
# equilibrium as before. With c > 0 the bot plays the restricted Nash response of bot/contempt.py: the opponent plays the human model's
# prediction with probability c and adversarially otherwise, solved on the turn's payoff matrix at each cell's precision (EVAL_MATRIX=1).
# Measured offline on 999 rated human games: c 0.5 +0.95 ± 0.11 real points a decision against what people played, +0.34 against a
# perfect opponent.
CONTEMPT_MODEL = os.path.join(ROOT, 'bot', 'out', 'contempt', 'human_model.json')
def contempt_of(fmt):
    try: return float((json.load(open(os.path.join(ROOT, 'bot', 'limits.json'))).get('contempt') or {}).get(fmt or '', 0.0))
    except Exception: return 0.0
def opponent_model(r, M):
    """the human model's probability of each opposing joint option (columns of r's matrix), the slots taken as independent"""
    import exploit_test as XT
    sp = {}
    for sl in r['sides'][1]['slots']:
        sp[sl['slot']] = {json.dumps(o['c']): p for o, p in zip(sl['options'], XT.probs([(o['label'], o['w'], o['v']) for o in sl['options']], M))}
    out = []
    for col in r['matrix']['cols']:
        pr = 1.0
        for i, c in enumerate(col):
            if c is not None and i in sp: pr *= sp[i].get(json.dumps(c), 1e-6)
        out.append(pr)
    t = sum(out) or 1.0
    return [x / t for x in out]
def contempt_mix(r, c):
    """[{label, w}] over the bot's joint options: max_x c x.A.q + (1 - c) min_j x.A_j on the matrix in real win chance"""
    import numpy as np
    from scipy.optimize import linprog
    import human_lines as HL
    M = json.load(open(CONTEMPT_MODEL)); mx = r['matrix']
    A0 = np.array([[np.nan if x is None else x for x in row] for row in mx['v1']], float)
    if np.isnan(A0).any(): rm = np.nanmean(A0, axis=1); A0 = np.where(np.isnan(A0), rm[:, None], A0)
    A = np.vectorize(lambda v: HL.resc(v, LV.CAL))(A0); q = np.array(opponent_model(r, M)); n, k = A.shape
    res = linprog(np.r_[-c * (A @ q), -(1 - c)], A_ub=np.c_[-A.T, np.ones(k)], b_ub=np.zeros(k), A_eq=np.r_[np.ones(n), 0.0][None], b_eq=[1.0],
                  bounds=[(0, None)] * n + [(None, None)], method='highs')
    x = res.x[:n]
    return [{'label': mx['rl'][i], 'w': float(x[i]), 'v': float(A[i] @ q)} for i in range(n) if x[i] > 1e-4]
# the back-row game (2026-10-12 night, the user: towards a trustworthy best move): limits.json "back_row_game": {format: k}, read every
# decision; with k > 1 and the opponent's back row unseen, the bot builds its k most likely back rows (botpos) and plays one game over
# them: the opponent knows its back row, the bot only the odds, max_x sum_h p_h [c x.A_h.q_h + (1 - c) min_j x.A_h_j] over the joint
# options every guess's matrix has (c = the contempt, 0 for the equilibrium). Measured on 781 of the bot's own decisions with the back
# row later shown (bot/back3_test.py bayes): 0.52 ± 0.07 planner points a decision below the plan on the true back row, against 0.90 for
# the top guess alone and 0.97 for the guesses' mixes weighted (a gain of +0.38 ± 0.09; +0.86 when the top guess is wrong, -0.16 ± 0.10
# when it is right). The k positions run on k threads: about the time of one (median 5.8 s vs 5.2 s on 12 saved decisions). The user
# (2026-10-12): the bot sticks to the top guess only; back_row_game stays unset.
def back_row_k(fmt):
    try: return max(1, int((json.load(open(os.path.join(ROOT, 'bot', 'limits.json'))).get('back_row_game') or {}).get(fmt or '', 1)))
    except Exception: return 1
def guesses_mix(hs, c):
    """[{label, w, v}] over the bot's joint options: one game over the back-row guesses hs [(weight, eval row with a matrix)]"""
    import numpy as np
    from scipy.optimize import linprog
    import human_lines as HL
    M = json.load(open(CONTEMPT_MODEL)) if c > 0 else None
    tot = sum(w for w, _ in hs); G = []
    for w, r in hs:
        mx = r['matrix']; A0 = np.array([[np.nan if x is None else x for x in row] for row in mx['v1']], float)
        if np.isnan(A0).any(): rm = np.nanmean(A0, axis=1); A0 = np.where(np.isnan(A0), rm[:, None], A0)
        G.append((w / tot, mx['rl'], np.vectorize(lambda v: HL.resc(v, LV.CAL))(A0), np.array(opponent_model(r, M)) if c > 0 else None,
                  np.array(mx['y'], float) / (sum(mx['y']) or 1.0)))
    rows = [l for l in G[0][1] if all(l in set(g[1]) for g in G[1:])]
    if not rows: return None
    As = [A[[rl.index(l) for l in rows]] for _, rl, A, _, _ in G]; ps = np.array([g[0] for g in G]); n, H = len(rows), len(G)
    obj = np.r_[-c * sum(p * (A @ q) for (p, _, _, q, _), A in zip(G, As)) if c > 0 else np.zeros(n), -(1 - c) * ps]
    A_ub = np.vstack([np.c_[-A.T, np.tile(np.eye(H)[h], (A.shape[1], 1))] for h, A in enumerate(As)])
    res = linprog(obj, A_ub=A_ub, b_ub=np.zeros(len(A_ub)), A_eq=np.r_[np.ones(n), np.zeros(H)][None], b_eq=[1.0],
                  bounds=[(0, None)] * n + [(None, None)] * H, method='highs')
    if res.status != 0: return None
    x = res.x[:n]; v = sum(p * (A @ y) for (p, _, _, _, y), A in zip(G, As))
    return [{'label': rows[i], 'w': float(x[i]), 'v': float(v[i])} for i in range(n) if x[i] > 1e-4]
def decide(specs, request, side, threads=2, seeds=32, log=None, cap=None, fmt=None):
    tag = f"t{request.get('rqid', 0)}_{random.randrange(1 << 20):05x}"
    posf = os.path.join(OUT, tag + '.pos.jsonl'); outf = os.path.join(OUT, tag + '.eval.jsonl')
    ps = LV.positions(specs, posf)
    c = contempt_of(fmt); multi = len(specs) > 1
    run_eval(posf, outf, max(threads, len(specs)) if multi else threads, seeds, {'EVAL_MATRIX': '1'} if c > 0 or multi else None)
    rows = {r['name']: r for r in map(json.loads, open(outf)) if 'error' not in r}
    w0, spec0 = specs[0]; name = spec0['name'] + ' p1'
    r = rows.get(name) or next(iter(rows.values()))
    # the engine finds nothing to choose (its position is over, or a side has no options, e.g. a last Pokemon locked into a charge):
    # Showdown's default, which is the only move then (a local test game, 2026-10-14)
    if 'sides' not in r: return 'default', 'no engine choices: ' + str(r.get('note', '')), r.get('value', 0.5)
    s0 = r['sides'][0]; joint = [j for j in s0['joint'] if j['w'] > 0]; value = r['value']; how = ''
    hs = [(w, rows[sp['name'] + ' p1']) for w, sp in specs if rows.get(sp['name'] + ' p1', {}).get('matrix')] if multi else []
    if len(hs) > 1:
        try:
            mix = guesses_mix(hs, c)
            if mix: joint = mix; value = sum(w * h['value'] for w, h in hs) / sum(w for w, _ in hs); how = f', one game over {len(hs)} back rows'
        except Exception as e: sys.stderr.write(f'back-row game failed, the top guess played: {e}\n')
    if not how and c > 0 and r.get('matrix'):
        try: joint = contempt_mix(r, c) or joint
        except Exception as e: sys.stderr.write(f'contempt failed, equilibrium played: {e}\n')
    # the hard cap (limits.json protect_chain_cap, the user: 4): a Pokemon that has used Protect that many turns running may not again;
    # the joint options that have it Protect are dropped and the rest renormalized (if nothing is left, the cap gives way)
    if cap and log is not None:
        ch = protect_chains(log, side)
        def capped(j):
            for part in j['label'].split(' | '):
                mon, _, act = part.partition(': ')
                if act.replace(' (Mega)', '') in STALL and max((c for m, c in ch.items() if mon.startswith(m) or m.startswith(mon.split('-Mega')[0])), default=0) >= cap: return True
            return False
        kept = [j for j in joint if not capped(j)]
        if kept and len(kept) < len(joint): joint = kept
    # map the engine's slots to Showdown's positions: the engine lists only living actives (a lone Pokemon is slot 0 even when it
    # stands in position b), Showdown's request lists every position; a fainted position gets 'pass'
    act = request.get('active') or []; team_now = request['side']['pokemon']
    base = lambda n: toid(n.split(',')[0]).replace('mega', '') if n else ''
    pos_slot = {}
    for i in range(len(act)):
        if i >= len(team_now) or team_now[i]['condition'].endswith(' fnt'): continue
        sp = base(team_now[i]['details'])
        k = next((x for x, sl in enumerate(s0['slots']) if base(sl['mon']) == sp or base(sl['mon']).startswith(sp) or sp.startswith(base(sl['mon']))), None)
        if k is not None: pos_slot[i] = k
    def command(j):
        """the /choose string for joint option j, or None if the request rules it out (no PP, disabled, trapped, no such move)"""
        parts = [p.strip() for p in j['label'].split(' | ')]; out = []
        for i in range(len(act)):
            if i not in pos_slot: out.append('pass'); continue
            sl = s0['slots'][pos_slot[i]]
            lab = next((p.split(': ', 1)[1] for p in parts if p.startswith(sl['mon'] + ': ')), None)
            opt = next((o for o in sl['options'] if o['label'] == lab), None) if lab else None
            if not opt: out.append('default'); continue
            c = opt['c']; a = act[i]; rmoves = a.get('moves') or []
            if c[0] == 'switch':
                # trapped only: maybeTrapped is Showdown hiding whether a foe's ability traps, and the switch is legal unless it does (the
                # server then refuses it and re-sends the request with trapped; the outside review, 2026-10-14)
                if a.get('trapped'): return None
                out.append('switch ' + str(team_index(request, lab.replace('switch to ', '')))); continue
            mv, t, mega = c
            if len(rmoves) == 1: out.append('move 1'); continue                       # a locked turn (charging, recharging, locked move)
            if mv >= len(rmoves) or rmoves[mv].get('disabled') or rmoves[mv].get('pp', 1) <= 0: return None
            tgt = rmoves[mv].get('target')
            cmd = f'move {mv + 1}'
            if tgt in ('normal', 'any', 'adjacentFoe'):
                if not t:   # the engine had no target (one foe left): aim at the foe that is there
                    foes = [x for x in (spec_foes or [1, 2])]; t = foes[0] if foes else 1
                cmd += f' {t}'
            elif tgt in ('adjacentAlly', 'adjacentAllyOrSelf') and t: cmd += f' {t}'
            if mega and a.get('canMegaEvo'): cmd += ' mega'
            out.append(cmd)
        return ', '.join(out)
    try:   # the opposing positions that hold a living Pokemon (1 = a, 2 = b), from the engine position
        st1 = (ps.get(name) or next(iter(ps.values())))['state']['sides'][1]
        spec_foes = [i + 1 for i, x in enumerate(st1.get('active') or []) if x is not None and not st1['pokemon'][x].get('fainted')]
    except Exception: spec_foes = None
    valid = [(j, command(j)) for j in joint]; valid = [(j, c) for j, c in valid if c]
    if not valid:
        # nothing in the mix is allowed (a choice refused and the request re-sent, e.g. a hidden Imprison disable revealed; 2026-10-13):
        # the best-valued joint option the request allows, from the listed joint options, then from each slot's own options
        listed = sorted(s0['joint'], key=lambda j: -j.get('v', 0.0))
        valid = [(j, cm) for j, cm in ((j, command(j)) for j in listed) if cm][:1]
        if not valid:
            import itertools
            tops = [sorted(sl['options'], key=lambda o: -o.get('v', 0.0))[:5] for sl in s0['slots']]
            for combo in sorted(itertools.product(*tops), key=lambda cb: -sum(o.get('v', 0.0) for o in cb)):
                j = {'label': ' | '.join(f"{sl['mon']}: {o['label']}" for sl, o in zip(s0['slots'], combo)), 'w': 1.0}
                cm = command(j)
                if cm: valid = [(j, cm)]; break
        if valid: valid = [({**valid[0][0], 'w': 1.0}, valid[0][1])]
    if not valid: return 'default', 'no option the request allows: default', value
    pick, choice = random.choices(valid, weights=[j['w'] for j, _ in valid])[0]
    note = f"{pick['label']} ({100 * pick['w']:.0f}%, value {100 * value:.0f}%" + (f", contempt {c}" if c > 0 else '') + how + ")"
    return choice, note, value
def team_index(request, species):
    """1-based index in request.side.pokemon of the named Pokemon (by species, forme-insensitive)"""
    want = toid(species)
    for i, p in enumerate(request['side']['pokemon']):
        sp = toid(p['details'].split(',')[0])
        if sp == want or sp.split('mega')[0] == want.split('mega')[0]: return i + 1
    raise RuntimeError('no such team member: ' + species)
def static_values(specs, tag):
    """the engine's static value of each spec (champ feats: a millisecond each), by spec name"""
    posf = os.path.join(OUT, tag + '.pos.jsonl'); outf = os.path.join(OUT, tag + '.feats.jsonl')
    LV.positions(specs, posf)
    if os.path.exists(outf): os.remove(outf)
    grid = os.path.join(EB, 'out', 'emptygrid'); os.makedirs(grid, exist_ok=True)
    env = dict(os.environ, RACE_TIES='avg', EG_VALUE=os.environ.get('EG_VALUE', 'egvalue9_sym2.json'), RACE='1', TRSYM='1', CALC_DATA='../native/champions_data_full.json', GRID_DIR=grid)
    import subprocess
    subprocess.run([os.environ['CHAMP_BIN'], 'feats', '../native/' + os.environ['CHAMP_DATA'], posf, outf, '1'], cwd=os.path.join(ROOT, 'pssim'), env=env, check=True, capture_output=True)
    return {r['name']: r['static'] for r in map(json.loads, open(outf)) if 'error' not in r}
def replacement(request, log, side, team=None, threads=2, seeds=32):
    """forceSwitch: every way to fill the slots the request marks from the living bench, each scored by the one-turn search at the next
    turn's start with those replacements in (champ evalpos, as a turn is decided; the Eval bar's bot_replacement builds the positions:
    the opponent's own replacement, if it must make one, averaged over its likely ones); the best is chosen. Since 2026-10-12 (the user):
    the static value the planner uses for this in self-play picked another replacement than the search in 53 of 144 of the bot's
    replacements, 1.7 points each on average (bot/decision_audit.py). Falls back to the static value, then to the type rule."""
    text = '\n'.join(log) if isinstance(log, list) else log
    need = request.get('forceSwitch') or []; mons = request['side']['pokemon']
    # Revival Blessing (the outside review, 2026-10-14): a slot whose active Pokemon is marked reviving is filled by naming a fainted
    # Pokemon (Showdown refuses a living one); no position is built for a revival, so the type rule picks among the fainted
    if any(p.get('reviving') for p in mons if p.get('active')): return replacement_by_type(request, text, side)
    slots = [k for k, must in enumerate(need) if must]
    bench = [p['details'].split(',')[0] for p in mons if not p.get('active') and not p['condition'].endswith(' fnt') and p['condition'] != '0 fnt']
    import itertools
    cands = list(itertools.permutations(bench, min(len(slots), len(bench))))
    if not slots or not cands: return 'pass'
    if len(cands) == 1: return ', '.join(f'switch {team_index(request, sp)}' for sp in cands[0]) + (', pass' * (len(slots) - len(cands[0])))
    tag = f"r{request.get('rqid', 0)}_{random.randrange(1 << 20):05x}"; exp = export(team) if team else None
    groups = []
    try:   # every candidate's positions (one per likely replacement of the opponent's), named apart, in one engine run
        for ci, cand in enumerate(cands):
            rep = {'ab'[slots[j]]: sp for j, sp in enumerate(cand)}
            specs, info = BP.bot_replacement(text, request, side, rep, topk=1, team=exp)
            if not specs: raise RuntimeError('no replacement position: ' + str(info.get('skip')))
            groups.append((cand, [(w, {**sp, 'name': f"c{ci} b{k} {sp['name']}"}) for k, (w, sp) in enumerate(specs)]))
    except Exception as e:
        sys.stderr.write('replacement positions failed, type rule instead: ' + repr(e) + '\n')
        return replacement_by_type(request, text, side)
    def pick(vals, how):
        best = None
        for cand, specs in groups:
            ws = [(w, vals[sp['name'] + ' p1']) for w, sp in specs if sp['name'] + ' p1' in vals]
            if not ws: continue
            tot = sum(w * v for w, v in ws) / max(1e-9, sum(w for w, _ in ws))
            if best is None or tot > best[0]: best = (tot, cand)
        if best is None: raise RuntimeError('no candidate evaluated')
        sys.stderr.write(f"replacement by {how}: {best[1]} ({100 * best[0]:.0f}%)\n")
        return ', '.join(f'switch {team_index(request, sp)}' for sp in best[1]) + (', pass' * (len(slots) - len(best[1])))
    allspecs = [x for _, specs in groups for x in specs]
    try:
        posf = os.path.join(OUT, tag + '.pos.jsonl'); outf = os.path.join(OUT, tag + '.eval.jsonl')
        LV.positions(allspecs, posf); run_eval(posf, outf, threads, seeds)
        return pick({r['name']: r['value'] for r in map(json.loads, open(outf)) if 'error' not in r}, 'search')
    except Exception as e:
        sys.stderr.write('replacement by search failed, static value instead: ' + repr(e) + '\n')
    try: return pick(static_values(allspecs, tag), 'static value')
    except Exception as e:
        sys.stderr.write('replacement by value failed, type rule instead: ' + repr(e) + '\n')
        return replacement_by_type(request, text, side)
def replacement_by_type(request, log, side):
    """forceSwitch: for each slot that must be filled, the bench Pokemon that takes the opponent's actives' attacking types best
    (sum over their STAB types of the type chart's multiplier against it; lower is better; ties by HP). v1 until positions can be
    built mid-turn."""
    opp = 'p2' if side == 'p1' else 'p1'; text = '\n'.join(log) if isinstance(log, list) else log
    foes = {}
    for l in text.split('\n'):   # once, in order: a faint empties the slot, a later switch-in fills it again (the third review pass)
        p = l.split('|')
        if len(p) > 3 and p[1] in ('switch', 'drag', 'detailschange', 'replace') and p[2].startswith(opp): foes[p[2][:3]] = p[3].split(',')[0]
        elif len(p) > 2 and p[1] == 'faint' and p[2].startswith(opp): foes.pop(p[2][:3], None)
    atk_types = []
    for sp in foes.values():
        s = SPECIES.get(sp) or SPECIES.get(sp.split('-')[0])
        if s: atk_types += s['types']
    def score(p):
        sp = p['details'].split(',')[0]; s = SPECIES.get(sp) or SPECIES.get(sp.split('-')[0])
        if not s: return 9.0
        tot = 0.0
        for at in atk_types:
            m = 1.0
            for dt in s['types']:
                e = TYPES.get(dt, {}).get(at, 0); m *= {0: 1.0, 1: 2.0, 2: 0.5, 3: 0.0}[e]
            tot += m
        hp = p['condition'].split('/')[0]; frac = int(hp.split()[0]) / max(1, int(p['condition'].split('/')[1].split()[0])) if '/' in p['condition'] else 0
        return tot - 0.01 * frac
    need = request.get('forceSwitch') or []; mons = request['side']['pokemon']
    fnt = lambda p: p['condition'].endswith(' fnt') or p['condition'] == '0 fnt'
    bench = [i for i, p in enumerate(mons) if not p.get('active') and not fnt(p)]
    dead = [i for i, p in enumerate(mons) if fnt(p)]   # a reviving slot names one of these (any team slot)
    bench.sort(key=lambda i: score(mons[i])); dead.sort(key=lambda i: score(mons[i]))
    active = [p for p in mons if p.get('active')]
    cmds = []
    for k, must in enumerate(need):
        if not must: cmds.append('pass'); continue
        pool = dead if k < len(active) and active[k].get('reviving') else bench
        if not pool: cmds.append('pass'); continue
        cmds.append('switch ' + str(pool.pop(0) + 1))
    return ', '.join(cmds)
