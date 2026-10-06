"""The eval bar over the user's recorded ladder games (evalbar/games/*.json, see games/README.md), in two views:
  hindsight      everything the game ever showed: the opponent's four and what each revealed are known from turn 1
  as you saw it  only what you knew at the start of the turn: your team preview of their six, the Pokemon that had come in (as they
                 looked: Illusion fools this view until it breaks) and what they had shown; the rest is averaged over every set of
                 Pokemon from their preview they could still have brought, weighted by how often each is brought
  python3 evalbar/recorded.py commonsets                       the most common Reg M-C set and bring rate per species, from the Bo3 team
                                                               sheets in the replay cache (results/common_sets.json)
  python3 evalbar/recorded.py positions <out.jsonl>            engine positions for every turn, hypothesis and view (you are side 0)
  python3 evalbar/recorded.py page <evalpos output .jsonl> <positions .jsonl> [cal=0.7538] [acc=evalbar/results/accuracy_engine.json]
                                                               writes evalbar/out/recorded.html, all games and both views on one page
Sets: yours from pssim/myteam_c_incin.json (with each game's overrides); the opponent's from the common set of each species (or the
Smogon M-C set of `from`) with what the game revealed laid on top."""
import os, sys, json, math, glob, itertools, subprocess, collections
import common as C, replay as R, procs as P
from build import options
toid = R.toid
MY = json.load(open(os.path.join(C.PSSIM, 'myteam_c_incin.json')))
SM = json.load(open(os.path.join(C.REPO, 'regionals', 'smogon_mc_sets.json')))
SPS = json.load(open(os.path.join(C.PSSIM, 'species_stats.json')))
E = json.load(open(os.path.join(C.MAIN, 'native', 'engine_data_spot.json')))
GAMES = sorted(glob.glob(os.path.join(C.HERE, 'games', '*.json')))
COMMON = os.path.join(C.HERE, 'results', 'common_sets.json'); PAIRS = os.path.join(C.HERE, 'results', 'back_pairs.json')
NICE = {'Indeedee-F': 'Indeedee', 'Floette-Eternal': 'Floette'}
PRIOR, PRIOR_N = 0.6, 20             # bring rate shrunk towards 0.6 as if from 20 more games; Illusion hides Zoroark in the logs: 0.6
def build_common():
    back = collections.defaultdict(lambda: [0, 0]); pairs = collections.defaultdict(lambda: [0, 0])     # [times possible, times in the back]
    stats = collections.defaultdict(lambda: {'n': 0, 'item': collections.Counter(), 'ability': collections.Counter(), 'nature': collections.Counter(),
                                             'moves': collections.Counter(), 'preview': 0, 'brought': 0})
    for rid, log in C.games():
        L = log.split('\n')
        for l in L:
            if l.startswith('|showteam|'):
                for st in R.parse_sheet('|'.join(l.split('|')[3:])).values():
                    s = stats[st['species']]; s['n'] += 1; s['item'][st['item']] += 1; s['ability'][st['ability']] += 1; s['nature'][st['nature']] += 1
                    for m in st['moves']: s['moves'][m] += 1
        for sd in ('p1', 'p2'):
            team = [l.split('|')[3].split(',')[0] for l in L if l.startswith(f'|poke|{sd}|')]
            order = list(dict.fromkeys(l.split('|')[3].split(',')[0].split('-Mega')[0] for l in L if l.startswith((f'|switch|{sd}', f'|drag|{sd}'))))
            seen = set(order)
            for sp in team: stats[sp]['preview'] += 1; stats[sp]['brought'] += sp in seen
            # back rates given the leads (games where all four came in and no Illusion): how often a non-lead was in the back
            if len(team) == 6 and len(order) == 4 and seen <= set(team) and not any(x.startswith('Zoroark') for x in team):
                leads, bk = order[:2], set(order[2:])
                for sp in team:
                    if sp in leads: continue
                    b = sp in bk; back[sp][0] += 1; back[sp][1] += b
                    for l in leads: pairs[f'{l}|{sp}'][0] += 1; pairs[f'{l}|{sp}'][1] += b
    out = {}
    for sp, s in stats.items():
        if not s['n'] and not s['preview']: continue
        out[sp] = {'n': s['n'], 'item': s['item'].most_common(1)[0][0] if s['n'] else '', 'ability': s['ability'].most_common(1)[0][0] if s['n'] else '',
                   'nature': s['nature'].most_common(1)[0][0] if s['n'] else '', 'moves': [m for m, _ in s['moves'].most_common(4)],
                   'preview': s['preview'], 'brought': s['brought'], 'back': back[sp]}
    json.dump(out, open(COMMON, 'w'), indent=0, sort_keys=True); print(f'{len(out)} species -> {os.path.relpath(COMMON, C.REPO)}')
    json.dump({k: v for k, v in pairs.items() if v[0] >= 3}, open(PAIRS, 'w'), separators=(',', ':'), sort_keys=True)
CS = json.load(open(COMMON)) if os.path.exists(COMMON) else {}
PR = json.load(open(PAIRS)) if os.path.exists(PAIRS) else {}
def bring(sp):
    if sp.startswith('Zoroark'): return PRIOR
    c = CS.get(sp, {}); return (c.get('brought', 0) + PRIOR * PRIOR_N) / (c.get('preview', 0) + PRIOR_N)
def back_weight(sp, leads):
    """how likely sp is in the back given the two leads: its back rate when not leading (shrunk to 0.5), times how much more or less
    often it sits behind each of these leads (shrunk to 1). On the replay cache this predicts the back pair with log loss 1.56 against
    1.73 for plain bring rates and 1.79 for a uniform guess (5-fold, 7,211 player-games)."""
    n, b = CS.get(sp, {}).get('back', [0, 0]); base = (b + 0.5 * 20) / (n + 20)
    w = base
    for l in leads:
        pn, pb = PR.get(f'{l}|{sp}', [0, 0]); w *= ((pb + base * 10) / (pn + 10)) / base
    return w
def mega_of(sp, item): return (E['items'].get(toid(item), {}).get('megaStone') or {}).get(sp)
def common_set(sp):
    """the species' most common Reg M-C set: item, ability, nature and moves from the Bo3 team sheets (at least 20 sheets), stat points from
    the Smogon M-C set of the form it plays as (the Mega form when the item is its stone); else the Smogon M-C set"""
    c = CS.get(sp)
    if c and c['n'] >= 20:
        mg = mega_of(sp, c['item']); base = SM.get(mg or sp) or SM.get(sp) or {}
        evs = base.get('evs')
        if not evs:
            import spots; evs = spots.evs_for(sp, c['item'], c['nature'], c['moves'])
        return {'species': sp, 'item': c['item'], 'ability': c['ability'], 'nature': c['nature'], 'evs': evs, 'moves': list(c['moves'])}
    base = SM.get(sp) or next(v for k, v in SM.items() if k.startswith(sp + '-Mega'))
    ab = base['ability'] if base['species'] == sp else E['species'][toid(sp)]['abilities']['0']
    return {'species': sp, 'item': base['item'], 'ability': ab, 'nature': base['nature'], 'evs': base['evs'], 'moves': list(base['moves'])}
def their_set(x, moves=None, item_known=True):
    """x: the game file's entry. moves: the moves revealed so far (hindsight: every move the file lists)."""
    base = SM[x['from']] if x.get('from') else common_set(x['species'])
    shown = x.get('moves', []) if moves is None else moves
    return {'species': x['species'], 'item': x['item'] if 'item' in x and item_known else base['item'], 'ability': x.get('ability', base['ability']),
            'nature': base['nature'], 'evs': base['evs'], 'moves': list(dict.fromkeys(shown + base['moves']))[:4]}
def my_set(k, ov):
    s = dict(MY[k]); s.update(ov.get(k, {})); return s
def maxhp(species, evs): return SPS[species]['bs']['hp'] + 75 + evs[0]
def disp(sp, mega): return 'Mega ' + sp.split('-')[0] if mega else NICE.get(sp, sp)
def turns(g):
    """the position at the start of every turn, with carry-over: [(turn, {p1: [row...], p2: [...]}, field, acts, events)]"""
    sets = {'p1': [my_set(k, g.get('my_overrides', {})) for k in g['mine']], 'p2': [their_set(x) for x in g['theirs']]}
    names = {'p1': g['mine'], 'p2': [x['species'] for x in g['theirs']]}
    st = {sd: {n: {'slot': '', 'hp': None, 'pct': 100, 'b': {}, 'mega': False, 'gone': False, 'st': '', 'f': False} for n in names[sd]} for sd in ('p1', 'p2')}
    prev_on = {'p1': {}, 'p2': {}}; prev_out = set(); out = []
    for t in g['turns']:
        for sd in ('p1', 'p2'):
            for n, ch in t.get(sd, {}).items():
                m = st[sd][n]
                if 'slot' in ch and ch['slot'] == '' and m['slot']: m['b'] = {}
                m.update(ch)
                if m['f']: m['slot'] = ''; m['b'] = {}
        on = {sd: {n: m['slot'] for n, m in st[sd].items() if m['slot']} for sd in ('p1', 'p2')}
        # turn-start view per side: Pokemon in order slot a, slot b, then the rest in brought order. Fake Out works again for a Pokemon
        # that is new on the field: it was not out at the last turn's start, changed slot, or switched out
        view = {}
        for sd in ('p1', 'p2'):
            rows = []
            for n, s in zip(names[sd], sets[sd]):
                m = st[sd][n]
                hpmax = maxhp(s['species'], s['evs']) if sd == 'p1' else None
                pct = 0 if m['f'] else (100 * m['hp'] / hpmax if sd == 'p1' and m['hp'] is not None else m['pct'])
                rows.append({'name': n, 'set': s, 'slot': m['slot'], 'pct': pct, 'hp': m['hp'], 'max': hpmax, 'b': dict(m['b']), 'mega': m['mega'],
                             'gone': m['gone'], 'st': m['st'], 'f': m['f'], 'stall': n in t.get('stall', []),
                             'moved': n in on[sd] and prev_on[sd].get(n) == on[sd][n] and (sd, n) not in prev_out})
            rows.sort(key=lambda r: 0 if r['slot'] == 'a' else 1 if r['slot'] == 'b' else 2)
            view[sd] = rows
        out.append((t['turn'], view, t.get('field', {}), t.get('acts', {}), t.get('events', [])))
        prev_out = {(sd, n) for sd in ('p1', 'p2') for n, sl in on[sd].items() if 'switch' in (t.get('acts', {}).get(sd, {}).get(sl) or {})}
        prev_on = on
    return out
def stand_in(sp):
    return {'name': sp, 'set': common_set(sp), 'slot': '', 'pct': 100, 'hp': None, 'max': None, 'b': {}, 'mega': False, 'gone': False, 'st': '',
            'f': False, 'stall': False, 'moved': False, 'standIn': True}
def hypotheses(g, mode):
    """per turn: [(weight, p2 rows)] that sum to 1, and for the page the unseen pool. hind: the real four (an unseen fourth averaged over
    the game's candidates); seen: what you knew then"""
    T = turns(g); X = {x['species']: x for x in g['theirs']}; out = []
    if mode == 'hind':
        cands = g.get('candidates') or [None]
        leads = [r['name'] for r in T[0][1]['p2'] if r['slot']]
        ws = [back_weight(c['species'], leads) if c else 1 for c in cands]; tot = sum(ws)
        for turn, view, *_ in T:
            hy = [(w / tot, view['p2'] + ([stand_in(c['species'])] if c else [])) for w, c in zip(ws, cands)]
            out.append((turn, hy, [c['species'] for c in cands] if cands[0] else [], 1 if cands[0] else 0))
        return out
    been = set(); used = collections.defaultdict(list); leads = []
    for turn, view, field, acts, events in T:
        looks = lambda n: X[n]['appears_as']['species'] if 'appears_as' in X[n] and turn < X[n]['appears_as']['until'] else n
        been |= {r['name'] for r in view['p2'] if r['slot']}
        known = []
        for r in view['p2']:
            if r['name'] not in been: continue
            n = looks(r['name']); x = X[r['name']] if n == r['name'] else {'species': n}
            s = their_set(x, moves=used[r['name']] if n == r['name'] else [], item_known=x.get('item_from', 99) <= turn and not x.get('guess'))
            known.append({**r, 'set': s, 'shown_as': n})
        seen_sp = {r['shown_as'] for r in known}
        pool = [sp for sp in g['preview'] if sp not in seen_sp]; u = 4 - len(known)
        ok = [sp for sp in pool if toid(sp) in E['species']]
        if turn == T[0][0]: leads = [r['shown_as'] for r in known if r['slot']]
        hy = []
        for combo in itertools.combinations(ok, u):
            w = math.prod(back_weight(sp, leads) for sp in combo); hy.append((w, known + [stand_in(sp) for sp in combo]))
        tot = sum(w for w, _ in hy); hy = [(w / tot, rows) for w, rows in hy]
        out.append((turn, hy, pool, u))
        for sl, a in acts.get('p2', {}).items():                       # moves used this turn are known from the next turn on
            r = next((r for r in view['p2'] if r['slot'] == sl), None)
            if r and a and 'move' in a and a['move'] not in used[r['name']]: used[r['name']].append(a['move'])
    return out
def spec_mon(r):
    s = r['set']
    return {**s, 'mega': r['mega'], 'hpPct': r['pct'], 'fainted': r['f'], 'status': r['st'], 'slept': 0, 'boosts': r['b'],
            'itemNow': '' if r['gone'] else s['item'], 'moved': r['moved'], 'stall': r['stall'], 'lock': '', 'vol': [], 'onField': bool(r['slot']),
            'last': '', 'volarg': {}, 'standIn': r.get('standIn', False)}
def specs(g, mode):
    out = []
    for (turn, view, field, acts, _), (_, hy, _, _) in zip(turns(g), hypotheses(g, mode)):
        # the engine puts the Pokemon on the field in its slots 0 and 1 in view order: slot letters and targets follow that
        eng = {sd: {r['slot']: 'ab'[i] for i, r in enumerate(view[sd][:2]) if r['slot']} for sd in ('p1', 'p2')}
        def act(sd, i):
            r = view[sd][i] if i < len(view[sd]) else None
            a = acts.get(sd, {}).get(r['slot']) if r and r['slot'] else None
            if not a: return None
            a = {**a, 'unsure': False}
            if 'switch' not in a:
                a.setdefault('mega', False); tg = a.get('target', '')
                a['target'] = tg[:2] + eng[tg[:2]].get(tg[2], tg[2]) if tg else ''
            return a
        ac = [[act(sd, i) for i in (0, 1)] for sd in ('p1', 'p2')]
        for k, (w, rows) in enumerate(hy):
            sides = [{'mons': [spec_mon(r) for r in v], 'tailwind': 0, 'screens': {}, 'hazards': []} for v in (view['p1'], rows)]
            out.append({'name': f"{g['id']} t{turn} {mode}{k}", 'turn': turn, 'sides': sides, 'acts': ac, 'perish': False,
                        'standIns': sum(r.get('standIn', False) for r in rows), 'dropped': [],
                        'field': {'weather': field.get('weather'), 'terrain': field.get('terrain'), 'trickroom': field.get('tr', 0)}})
    return out
def board(view, p2rows, field, shown, pool, u):
    """the page's position, like replay.py's snapshot. The opponent's items show only when the game revealed them; their unseen Pokemon
    are one line"""
    S = {}
    for sd, rows in (('p1', view['p1']), ('p2', p2rows)):
        S[sd] = {'mons': [{'n': disp(r.get('shown_as', r['set']['species']), r['mega']), 'hp': 0 if r['f'] else max(1, round(r['pct'])), 'st': r['st'],
                           'f': r['f'], 'b': r['b'], 'item': r['set']['item'] if sd == 'p1' or (r['name'] in shown and r.get('shown_as', r['name']) == r['name']) or r['mega'] else '',
                           'gone': r['gone'], 'slot': r['slot'], 'seen': True} for r in rows if not r.get('standIn')],
                 'tailwind': 0, 'screens': {}, 'hazards': []}
    if u:
        names = ', '.join(NICE.get(p, p) for p in pool[:-1]) + (' or ' if len(pool) > 1 else '') + NICE.get(pool[-1], pool[-1])
        S['p2']['mons'].append({'n': f"{'one' if u == 1 else u} of {names}", 'hp': 100, 'st': '', 'f': False, 'b': {}, 'item': '', 'gone': False, 'slot': '',
                                'seen': False, 'pool': True})
    w = field.get('weather'); te = field.get('terrain')
    S['field'] = {'weather': w[0] if w else '', 'wturns': w[1] if w else 0, 'terrain': te[0] if te else '', 'tturns': te[1] if te else 0, 'tr': field.get('tr', 0)}
    return S
def page(evf, posf, cal, accf):
    ev = {x['name']: x for x in map(json.loads, open(evf)) if 'error' not in x}; ps = {x['name']: x for x in map(json.loads, open(posf))}
    logit = lambda v: math.log(min(1 - 1e-4, max(1e-4, v)) / (1 - min(1 - 1e-4, max(1e-4, v))))
    scale = lambda v: C.sig(cal * logit(v))
    acc = json.load(open(accf)); A = {**acc['engine value'], 'v0': acc['version 0 (same positions)']}
    views = {}
    for mode in ('seen', 'hind'):
        games = []
        for f in GAMES:
            g = json.load(open(f)); steps = []; missing = 0
            for (turn, view, field, acts, events), (_, hy, pool, u) in zip(turns(g), hypotheses(g, mode)):
                shown = {x['species'] for x in g['theirs'] if 'item' in x and not x.get('guess') and (mode == 'hind' or x.get('item_from', 99) <= turn)}
                names = [f"{g['id']} t{turn} {mode}{k} p1" for k in range(len(hy))]
                if not all(n in ev for n in names): missing += 1; continue
                ws = [w for w, _ in hy]
                wp = sum(w * scale(ev[n]['value']) for w, n in zip(ws, names))
                opts = [options(ev[n], ps[n], scale) for n in names]
                # merge the hypotheses' options: picks and values weighted by each hypothesis's probability
                opt = {}
                for sd in ('p1', 'p2'):
                    opt[sd] = []
                    for i, sl in enumerate(opts[0][sd]):
                        acc_o = {}
                        for w, o in zip(ws, opts):
                            for x in o[sd][i]['options']:
                                a = acc_o.setdefault(x['l'], {'l': x['l'], 'w': 0, 'vw': 0, 'n': 0, 'played': x['played'], 'rough': x['rough']})
                                a['w'] += w * x['w']; a['vw'] += w * x['v']; a['n'] += w; a['rough'] = a['rough'] and x['rough']
                        merged = [{'l': a['l'], 'w': round(a['w'], 3), 'v': round(a['vw'] / a['n'], 3), 'played': a['played'], 'rough': a['rough']} for a in acc_o.values()]
                        opt[sd].append({'mon': NICE.get(sl['mon'], sl['mon']), 'played': sl['played'], 'options': merged})
                        for x in merged:
                            for a, b in NICE.items(): x['l'] = x['l'].replace(a, b)
                ev_text = [{'side': s, 'head': [h], 'notes': [[n] for n in notes]} for s, h, notes in events]
                p2rows = hy[0][1] if mode == 'seen' else view['p2']
                steps.append({'turn': turn, 'wp': wp, 'ev': wp, 'state': board(view, p2rows, field, shown, pool, u), 'events': ev_text, 'opt': opt,
                              'hyp': len(hy)})
            if missing: print(f"{g['id']} {mode}: {missing} turn(s) without engine results left out")
            last = steps[-1]['state'] if steps else None
            games.append({'id': g['id'], 'title': g['title'], 'recorded': g['recorded'], 'result': g['result'], 'how': g['how'], 'view': mode,
                          'winner': 'p1' if g['result'] == 'win' else 'p2', 'forfeit': 'forfeit' in g['how'], 'perish': False, 'rating': None,
                          'steps': steps, 'final': {'wp': 1.0 if g['result'] == 'win' else 0.0, 'state': last}, 'acc': A,
                          'engine': {'turns': len(steps), 'seeds': max(x.get('seeds', 0) for x in ev.values()), 'staged': True, 'bar': True, 'cal': cal}})
        views[mode] = games
    blob = json.dumps({'views': views, 'names': {'p1': 'You', 'p2': 'Opponent'}, 'recorded': True}, ensure_ascii=False, separators=(',', ':'))
    html = open(os.path.join(C.HERE, 'page.html')).read().replace('<title>Eval Bar</title>', '<title>Ladder Games Eval Bar</title>', 1)
    html = html.replace('/*DATA*/null', blob.replace('</', '<\\/'))
    outf = os.path.join(C.HERE, 'out', 'recorded.html'); open(outf, 'w').write(html)
    for mode, games in views.items():
        for g in games: print(f"{mode} {g['id']} ({g['result']}): you " + ' '.join(f"{100 * s['wp']:.0f}" for s in g['steps']))
    print(os.path.relpath(outf, C.REPO))
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'commonsets': build_common()
    elif a[0] == 'positions':
        allspecs = [s for f in GAMES for mode in ('hind', 'seen') for s in specs(json.load(open(f)), mode)]
        tmp = a[1] + '.specs.json'; json.dump(allspecs, open(tmp, 'w'))
        subprocess.run([P.exe('node'), os.path.join(C.HERE, 'positions.js'), os.path.abspath(tmp), os.path.abspath(a[1]), 'p1'], cwd=os.path.join(C.MAIN, 'pssim'), check=True)
        os.remove(tmp)
    elif a[0] == 'page':
        kw = dict(x.split('=', 1) for x in a[3:])
        page(a[1], a[2], float(kw.get('cal', 0.7538)), kw.get('acc', os.path.join(C.HERE, 'results', 'accuracy_engine.json')))
