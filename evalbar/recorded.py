"""The eval bar over the user's recorded ladder games (evalbar/games/*.json, see games/README.md).
  python3 evalbar/recorded.py positions <out.jsonl>          engine positions for every turn of every game (one per candidate for an
                                                             unseen fourth Pokemon), your side as the engine's side 0
  python3 evalbar/recorded.py page <evalpos output .jsonl> <positions .jsonl> [cal=0.7438] [acc=evalbar/results/accuracy_engine.json]
                                                             writes evalbar/out/recorded.html, all games on one page
Sets: yours from pssim/myteam_c_incin.json (with each game's overrides); the opponent's from Smogon M-C sets with what the game revealed."""
import os, sys, json, math, glob, subprocess
import common as C, replay as R
from build import options, label
toid = R.toid
MY = json.load(open(os.path.join(C.PSSIM, 'myteam_c_incin.json')))
SM = json.load(open(os.path.join(C.REPO, 'regionals', 'smogon_mc_sets.json')))
SPS = json.load(open(os.path.join(C.PSSIM, 'species_stats.json')))
GAMES = sorted(glob.glob(os.path.join(C.HERE, 'games', '*.json')))
def their_set(x):
    base = SM.get(x.get('from') or x['species']) or SM[x['species']]
    moves = list(dict.fromkeys(x.get('moves', []) + base['moves']))[:4]
    return {'species': x['species'], 'item': x.get('item', base['item']), 'ability': x.get('ability', base['ability']),
            'nature': x.get('nature', base['nature']), 'evs': x.get('evs', base['evs']), 'moves': moves}
def my_set(k, ov):
    s = dict(MY[k]); s.update(ov.get(k, {})); return s
def maxhp(species, evs): return SPS[species]['bs']['hp'] + 75 + evs[0]
NICE = {'Indeedee-F': 'Indeedee', 'Floette-Eternal': 'Floette'}
def disp(sp, mega): return 'Mega ' + sp.split('-')[0] if mega else NICE.get(sp, sp)
def turns(g):
    """the position at the start of every turn, with carry-over: [(turn, {p1: [mon...], p2: [...]}, field, acts, events)]"""
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
        # Fake Out works again for a Pokemon that is new on the field: it was not out at the last turn's start, changed slot, or switched out
        # turn-start view per side: Pokemon in order slot a, slot b, then the rest in brought order
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
def spec_mon(r):
    s = r['set']
    return {**s, 'mega': r['mega'], 'hpPct': r['pct'], 'fainted': r['f'], 'status': r['st'], 'slept': 0, 'boosts': r['b'],
            'itemNow': '' if r['gone'] else s['item'], 'moved': r['moved'], 'stall': r['stall'], 'lock': '', 'vol': [], 'onField': bool(r['slot']),
            'last': '', 'volarg': {}}
def specs(g):
    cands = g.get('candidates') or [None]
    out = []
    for turn, view, field, acts, _ in turns(g):
        for k, c in enumerate(cands):
            sides = []
            for sd in ('p1', 'p2'):
                mons = [spec_mon(r) for r in view[sd]]
                if sd == 'p2' and c:
                    s = their_set({'species': c['species']})
                    mons.append({**spec_mon({'set': s, 'mega': False, 'pct': 100, 'f': False, 'st': '', 'b': {}, 'gone': False, 'moved': False,
                                             'stall': False, 'slot': ''}), 'standIn': True})
                sides.append({'mons': mons, 'tailwind': 0, 'screens': {}, 'hazards': []})
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
            out.append({'name': f"{g['id']} t{turn}" + (f" c{k}" if c else ''), 'turn': turn, 'sides': sides, 'acts': ac, 'perish': False,
                        'standIns': 1 if c else 0, 'dropped': [],
                        'field': {'weather': field.get('weather'), 'terrain': field.get('terrain'), 'trickroom': field.get('tr', 0)}})
    return out
def board(view, field, shown):
    """the page's position: like replay.py's snapshot. The opponent's items are shown only when the game revealed them (shown: names)"""
    S = {}
    for sd in ('p1', 'p2'):
        S[sd] = {'mons': [{'n': disp(r['set']['species'], r['mega']), 'hp': 0 if r['f'] else max(1, round(r['pct'])), 'st': r['st'], 'f': r['f'], 'b': r['b'],
                           'item': r['set']['item'] if sd == 'p1' or r['name'] in shown or r['mega'] else '', 'gone': r['gone'], 'slot': r['slot'], 'seen': True}
                          for r in view[sd]],
                 'tailwind': 0, 'screens': {}, 'hazards': []}
    w = field.get('weather'); te = field.get('terrain')
    S['field'] = {'weather': w[0] if w else '', 'wturns': w[1] if w else 0, 'terrain': te[0] if te else '', 'tturns': te[1] if te else 0, 'tr': field.get('tr', 0)}
    return S
def page(evf, posf, cal, accf):
    ev = {x['name']: x for x in map(json.loads, open(evf)) if 'error' not in x}; ps = {x['name']: x for x in map(json.loads, open(posf))}
    logit = lambda v: math.log(min(1 - 1e-4, max(1e-4, v)) / (1 - min(1 - 1e-4, max(1e-4, v))))
    scale = lambda v: C.sig(cal * logit(v))
    acc = json.load(open(accf)); A = {**acc['engine value'], 'v0': acc['version 0 (same positions)']}
    games = []
    for f in GAMES:
        g = json.load(open(f)); cands = g.get('candidates') or [None]
        wsum = sum(c['w'] for c in cands) if cands[0] else 1
        steps = []; missing = 0
        for turn, view, field, acts, events in turns(g):
            names = [f"{g['id']} t{turn}" + (f" c{k}" if c else '') + ' p1' for k, c in enumerate(cands)]
            if not all(n in ev for n in names): missing += 1; continue
            ws = [c['w'] / wsum if c else 1 for c in cands]
            wp = sum(w * scale(ev[n]['value']) for w, n in zip(ws, names))
            opts = [options(ev[n], ps[n], scale) for n in names]
            # merge the candidates' options: picks and values weighted by each candidate's probability
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
                    opt[sd].append({'mon': sl['mon'], 'played': sl['played'], 'options': merged})
            ev_text = [{'side': s, 'head': [h], 'notes': [[n] for n in notes]} for s, h, notes in events]
            for sd in opt:
                for sl in opt[sd]:
                    sl['mon'] = NICE.get(sl['mon'], sl['mon'])
                    for x in sl['options']:
                        for a, b in NICE.items(): x['l'] = x['l'].replace(a, b)
            shown = {x['species'] for x in g['theirs'] if 'item' in x and not x.get('guess')}
            steps.append({'turn': turn, 'wp': wp, 'ev': wp, 'state': board(view, field, shown), 'events': ev_text, 'opt': opt})
        if missing: print(f"{g['id']}: {missing} turn(s) without engine results left out")
        last = steps[-1]['state'] if steps else None
        unseen = ' or '.join(c['species'] for c in cands) if cands[0] else ''
        if unseen:
            for s in steps + ([{'state': last}] if last else []):
                s['state']['p2']['mons'].append({'n': f'one of {unseen}', 'hp': 100, 'st': '', 'f': False, 'b': {}, 'item': '', 'gone': False, 'slot': '', 'seen': False})
        games.append({'id': g['id'], 'title': g['title'], 'recorded': g['recorded'], 'result': g['result'], 'how': g['how'],
                      'winner': 'p1' if g['result'] == 'win' else 'p2', 'forfeit': 'forfeit' in g['how'], 'perish': False, 'rating': None,
                      'steps': steps, 'final': {'wp': 1.0 if g['result'] == 'win' else 0.0, 'state': last}, 'acc': A,
                      'engine': {'turns': len(steps), 'seeds': max(x.get('seeds', 0) for x in ev.values()), 'staged': True, 'bar': True, 'cal': cal}})
    blob = json.dumps({'games': games, 'names': {'p1': 'You', 'p2': 'Opponent'}, 'recorded': True}, ensure_ascii=False, separators=(',', ':'))
    html = open(os.path.join(C.HERE, 'page.html')).read().replace('<title>Eval Bar</title>', '<title>Ladder Games Eval Bar</title>', 1)
    html = html.replace('/*DATA*/null', blob.replace('</', '<\\/'))
    outf = os.path.join(C.HERE, 'out', 'recorded.html'); open(outf, 'w').write(html)
    for g in games: print(f"{g['id']} ({g['result']}): you " + ' '.join(f"{100 * s['wp']:.0f}" for s in g['steps']))
    print(os.path.relpath(outf, C.REPO))
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'positions':
        allspecs = [s for f in GAMES for s in specs(json.load(open(f)))]
        tmp = a[1] + '.specs.json'; json.dump(allspecs, open(tmp, 'w'))
        subprocess.run(['node', os.path.join(C.HERE, 'positions.js'), os.path.abspath(tmp), os.path.abspath(a[1]), 'p1'], cwd=os.path.join(C.MAIN, 'pssim'), check=True)
        os.remove(tmp)
    elif a[0] == 'page':
        kw = dict(x.split('=', 1) for x in a[3:])
        page(a[1], a[2], float(kw.get('cal', 0.7438)), kw.get('acc', os.path.join(C.HERE, 'results', 'accuracy_engine.json')))
