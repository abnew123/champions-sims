"""Position building and the decision for one turn (bot/brain.py calls these).
  build(log_lines, request, side) -> (specs, info) from the Eval bar thread's evalbar/botpos.py: the opponent's side as a spectator knows
       it (open sheets, reveals, its most likely back row), our side exactly from the |request|; we are side 0
  decide(specs, request, side) -> ("move 1 2, move 2 1", note): live.positions writes the engine position, engine.run evaluates it
       (champ evalpos, 32 seeds, staged, the kit's value), a joint action is sampled from side 0's mix and mapped to /choose syntax
  replacement(request, log, side) -> "switch 3[, switch 4]" for a forceSwitch request (v1: a type-chart rule, see below)"""
import os, sys, json, random, re, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); EB = os.path.join(ROOT, 'evalbar')
sys.path.insert(0, EB); sys.path.insert(0, os.path.join(ROOT, 'pssim'))
os.environ.setdefault('CHAMP_BIN', os.path.join(ROOT, 'native', 'champ', 'bin', 'battlesim-champ'))   # the current build (the kit's v25 setup)
os.environ.setdefault('CHAMP_DATA', 'engine_data_full.json')
os.environ.setdefault('EG_MEGA_TIE', '0')
os.environ.setdefault('EG_LAST_PROTECT', '0')   # our last Pokemon never Protects when it changes nothing (side 0 is the bot); the user, 2026-10-11
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
def decide(specs, request, side, threads=2, seeds=32):
    tag = f"t{request.get('rqid', 0)}_{random.randrange(1 << 20):05x}"
    posf = os.path.join(OUT, tag + '.pos.jsonl'); outf = os.path.join(OUT, tag + '.eval.jsonl')
    ps = LV.positions(specs, posf)
    EN.run(posf, outf, threads, seeds, 1)
    rows = {r['name']: r for r in map(json.loads, open(outf)) if 'error' not in r}
    w0, spec0 = specs[0]; name = spec0['name'] + ' p1'
    r = rows.get(name) or next(iter(rows.values()))
    s0 = r['sides'][0]; joint = [j for j in s0['joint'] if j['w'] > 0]
    pick = random.choices(joint, weights=[j['w'] for j in joint])[0]
    parts = [p.strip() for p in pick['label'].split(' | ')]
    cmds = []
    for k, sl in enumerate(s0['slots']):
        lab = next((p.split(': ', 1)[1] for p in parts if p.startswith(sl['mon'] + ': ')), None)
        opt = next((o for o in sl['options'] if o['label'] == lab), None) if lab else None
        if not opt: cmds.append('default'); continue
        c = opt['c']
        if c[0] == 'switch': cmds.append('switch ' + str(team_index(request, lab.replace('switch to ', ''))))
        else:
            mv, t, mega = c
            rmoves = (request.get('active') or [{}] * 2)[k].get('moves') or []
            if len(rmoves) == 1: cmds.append('move 1'); continue          # a locked turn (charging, recharging, locked move): no target
            rm = rmoves[mv] if mv < len(rmoves) else {}
            s = f'move {mv + 1}'
            if t and rm.get('target') in (None, 'normal', 'any', 'adjacentFoe', 'adjacentAlly', 'adjacentAllyOrSelf'): s += f' {t}'
            if mega and (request.get('active') or [{}] * 2)[k].get('canMegaEvo'): s += ' mega'
            cmds.append(s)
    note = f"{pick['label']} ({100 * pick['w']:.0f}%, value {100 * r['value']:.0f}%)"
    return ', '.join(cmds), note, r['value']
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
    env = dict(os.environ, RACE_TIES='avg', EG_VALUE=os.environ.get('EG_VALUE', 'egvalue9_sym2.json'), RACE='1', TRSYM='1', CALC_DATA='../native/champions_data.json', GRID_DIR=grid)
    import subprocess
    subprocess.run([os.environ['CHAMP_BIN'], 'feats', '../native/' + os.environ['CHAMP_DATA'], posf, outf, '1'], cwd=os.path.join(ROOT, 'pssim'), env=env, check=True, capture_output=True)
    return {r['name']: r['static'] for r in map(json.loads, open(outf)) if 'error' not in r}
def replacement(request, log, side):
    """forceSwitch: every way to fill the slots the request marks from the living bench, each scored by the engine's static value of
    the next turn's start with those replacements in (the Eval bar's bot_replacement: the opponent's own replacement, if it must make
    one, averaged over its likely ones); the best is chosen, as the planner chooses for itself in self-play. Falls back to the type rule."""
    text = '\n'.join(log) if isinstance(log, list) else log
    need = request.get('forceSwitch') or []; mons = request['side']['pokemon']
    slots = [k for k, must in enumerate(need) if must]
    bench = [p['details'].split(',')[0] for p in mons if not p.get('active') and not p['condition'].endswith(' fnt') and p['condition'] != '0 fnt']
    import itertools
    cands = list(itertools.permutations(bench, min(len(slots), len(bench))))
    if not slots or not cands: return 'pass'
    if len(cands) == 1: return ', '.join(f'switch {team_index(request, sp)}' for sp in cands[0]) + (', pass' * (len(slots) - len(cands[0])))
    best = None; tag = f"r{request.get('rqid', 0)}_{random.randrange(1 << 20):05x}"
    try:
        for ci, cand in enumerate(cands):
            rep = {'ab'[slots[j]]: sp for j, sp in enumerate(cand)}
            specs, info = BP.bot_replacement(text, request, side, rep, topk=1)
            if not specs: raise RuntimeError('no replacement position: ' + str(info.get('skip')))
            vals = static_values(specs, f'{tag}_{ci}')
            tot = sum(w * vals.get(sp['name'] + ' p1', 0.5) for w, sp in specs) / max(1e-9, sum(w for w, _ in specs))
            if best is None or tot > best[0]: best = (tot, cand)
    except Exception as e:
        sys.stderr.write('replacement by value failed, type rule instead: ' + repr(e) + '\n')
        return replacement_by_type(request, text, side)
    cand = best[1]
    sys.stderr.write(f"replacement by value: {cand} ({100 * best[0]:.0f}%)\n")
    return ', '.join(f'switch {team_index(request, sp)}' for sp in cand) + (', pass' * (len(slots) - len(cand)))
def replacement_by_type(request, log, side):
    """forceSwitch: for each slot that must be filled, the bench Pokemon that takes the opponent's actives' attacking types best
    (sum over their STAB types of the type chart's multiplier against it; lower is better; ties by HP). v1 until positions can be
    built mid-turn."""
    opp = 'p2' if side == 'p1' else 'p1'; text = '\n'.join(log) if isinstance(log, list) else log
    foes = {}
    for l in text.split('\n'):
        p = l.split('|')
        if len(p) > 3 and p[1] in ('switch', 'drag', 'detailschange', 'replace') and p[2].startswith(opp): foes[p[2][:3]] = p[3].split(',')[0]
    for l in text.split('\n'):
        p = l.split('|')
        if len(p) > 2 and p[1] == 'faint' and p[2][:3] in foes: foes.pop(p[2][:3], None)
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
    bench = [i for i, p in enumerate(mons) if not p.get('active') and not p['condition'].endswith(' fnt') and p['condition'] != '0 fnt']
    bench.sort(key=lambda i: score(mons[i]))
    cmds = []
    for k, must in enumerate(need):
        if not must: cmds.append('pass'); continue
        if not bench: cmds.append('pass'); continue
        cmds.append('switch ' + str(bench.pop(0) + 1))
    return ', '.join(cmds)
