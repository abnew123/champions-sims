"""Eval bar page for one cached replay.
  python3 evalbar/build.py pick                 lists cached games that make a good demo (high rated, played out, the lead changes hands)
  python3 evalbar/build.py <replay id> [acc=<accuracy json>] [engine=<evalpos output .jsonl> pos=<the positions .jsonl it was run on>] [cal=<weight>]
writes evalbar/out/<replay id>.html. Without engine results the page is version 0 (the bar from the real-game win-chance model). With
them every turn also gets each active Pokemon's options: how often the planner picks each, what each is worth, and which was played.
With cal (the weight accuracy.py fits on the engine value's log-odds) the bar itself is the engine's value rescaled to real results, and
the options' values are on the same scale; acc is then accuracy.py's engine results file.
The page shows no usernames or nicknames (players are Player 1 / Player 2); build fails if one would get through."""
import os, re, sys, json, math
import common as C, procs as P, replay as R
RF = C.replay_feats()
def game_data(rid, log, w):
    g = R.parse(log); rows, winner, _ = RF.game(log)
    wp = {t: C.v0(w, f) for t, f in rows}
    turns = [s for s in g['steps'] if s['turn'] >= 1]
    end = None if g['winner'] is None else 1.0 if g['winner'] == 'p1' else 0.0
    out = {'id': rid, 'rating': g['rating'], 'winner': g['winner'], 'forfeit': g['forfeit'], 'perish': g['perish'], 'brought': g['brought'],
           'steps': [{'turn': s['turn'], 'wp': wp[s['turn']], 'state': s['state'], 'events': s['events']} for s in turns], 'final': {'wp': end, 'state': g['final']}}
    return out, g['_hidden']
def label(l):
    """the engine's option label -> page text: 'Moonblast -> Garchomp-Mega-Z (Mega)' -> 'Moonblast → Mega Garchomp Z (and Mega Evolve)'"""
    mega = l.endswith(' (Mega)'); l = l[:-7] if mega else l
    if l.startswith('switch to '): l = 'Switch to ' + R.disp(l[10:])
    elif ' -> ' in l: mv, tg = l.split(' -> ', 1); l = f"{mv} → {tg if tg == 'ally' else R.disp(tg)}"
    return l + (' (and Mega Evolve)' if mega else '')
def same(c, a):
    """is option c the choice a that was made? (move slot and target, or the switch target; the Mega flag is ignored)"""
    return c[:2] == a[:2]
def options(e, pos, scale):
    """evalpos line + the position line it came from -> {'p1': [slot...], 'p2': [...]}, slot = {mon, played (True, or None if unknown),
    options: [{l, w, v, played, rough}]}. rough: in the staged mode an option more than 0.15 below its side's best kept a 2-sample value."""
    out = {}
    for s, sd, acts in ((0, 'p1', pos['actual']), (1, 'p2', pos['their_actual'])):
        out[sd] = []; best = max((o['v'] for sl in e['sides'][s]['slots'] for o in sl['options']), default=1)
        for sl in e['sides'][s]['slots']:
            a = acts[sl['slot']]; a = a['choice'] if a else None
            opts = [{'l': label(o['label']), 'w': round(o['w'], 3), 'v': round(scale(o['v']), 3), 'played': bool(a) and same(o['c'], a),
                     'rough': 'stages' in e and o['v'] < best - 0.15} for o in sl['options']]
            out[sd].append({'mon': R.disp(sl['mon']), 'played': True if any(o['played'] for o in opts) else None, 'options': opts})
    return out
def merge(ws, opts):
    """options() of several hypotheses with weights ws (summing to 1) -> one: each option's picks and value weighted over the hypotheses
    (a value averages over the hypotheses where the option exists). The Pokemon on the field must be the same in every hypothesis."""
    out = {}
    for sd in ('p1', 'p2'):
        out[sd] = []
        for i, sl in enumerate(opts[0][sd]):
            acc = {}
            for w, o in zip(ws, opts):
                for x in o[sd][i]['options']:
                    a = acc.setdefault(x['l'], {'l': x['l'], 'w': 0, 'vw': 0, 'n': 0, 'played': x['played'], 'rough': x['rough']})
                    a['w'] += w * x['w']; a['vw'] += w * x['v']; a['n'] += w; a['rough'] = a['rough'] and x['rough']
            out[sd].append({'mon': sl['mon'], 'played': sl['played'],
                            'options': [{'l': a['l'], 'w': round(a['w'], 3), 'v': round(a['vw'] / a['n'], 3), 'played': a['played'], 'rough': a['rough']} for a in acc.values()]})
    return out
def leak_check(text, hidden):
    low = text.lower()
    bad = [h for h in hidden if re.search(r'(?<![a-z0-9])' + re.escape(h.lower()) + r'(?![a-z0-9])', low)]
    if bad: sys.exit(f'refusing to write the page: {len(bad)} username(s) or nickname(s) would appear on it')
if __name__ == '__main__':
    P.own()
    w = C.v0_weights()
    if sys.argv[1] == 'pick':
        idx = json.load(open(os.path.join(C.LOGS, 'index.json'))); cands = []
        for rid, log in C.games():
            try: d, _ = game_data(rid, log, w)
            except Exception: continue
            v = [s['wp'] for s in d['steps']]
            if d['winner'] is None or d['perish'] or d['brought'] != {'p1': 4, 'p2': 4} or not 8 <= len(v) <= 13 or not idx[rid].get('rating'): continue
            wv = v if d['winner'] == 'p1' else [1 - x for x in v]
            cross = sum((a - .5) * (b - .5) < 0 for a, b in zip(v, v[1:]))
            if d['forfeit'] and wv[-1] < 0.9: continue
            cands.append((idx[rid]['rating'], cross, min(wv), len(v), d['forfeit'], rid))
        for c in sorted([c for c in cands if c[1] >= 2 and c[2] < 0.3], reverse=True)[:15]:
            print(f"rating {c[0]}  lead changes {c[1]}  winner's low {100 * c[2]:.0f}%  turns {c[3]}  forfeit {c[4]}  {c[5]}")
    else:
        rid = sys.argv[1]; log = open(os.path.join(C.LOGS, rid + '.log')).read(); arg = dict(a.split('=', 1) for a in sys.argv[2:])
        d, hidden = game_data(rid, log, w)
        acc = json.load(open(arg['acc'])) if 'acc' in arg else None
        d['acc'] = {**acc['engine value'], 'v0': acc['version 0 (same positions)']} if acc and 'engine value' in acc else acc
        if 'engine' in arg:
            ev = {x['name']: x for x in map(json.loads, open(arg['engine'])) if 'error' not in x}; ps = {x['name']: x for x in map(json.loads, open(arg['pos']))}
            cal = float(arg['cal']) if 'cal' in arg else None
            logit = lambda v: math.log(min(1 - 1e-4, max(1e-4, v)) / (1 - min(1 - 1e-4, max(1e-4, v))))
            scale = (lambda v: C.sig(cal * logit(v))) if cal else (lambda v: v)
            for s in d['steps']:
                nm = f"{rid} t{s['turn']} p1"
                if nm not in ev: continue
                s['opt'] = options(ev[nm], ps[nm], scale); s['ev'] = scale(ev[nm]['value'])
                if cal: s['wp0'] = s['wp']; s['wp'] = s['ev']
            d['engine'] = {'turns': sum('opt' in s for s in d['steps']), 'seeds': max((x.get('seeds', 0) for x in ev.values()), default=0),
                           'staged': any('stages' in x for x in ev.values()), 'bar': bool(cal), 'cal': cal}
        blob = json.dumps(d, ensure_ascii=False, separators=(',', ':')); leak_check(blob, hidden)
        page = open(os.path.join(C.HERE, 'page.html')).read().replace('/*DATA*/null', blob.replace('</', '<\\/'))
        os.makedirs(os.path.join(C.HERE, 'out'), exist_ok=True); outf = os.path.join(C.HERE, 'out', rid + '.html'); open(outf, 'w').write(page)
        print(f"{os.path.relpath(outf, C.REPO)}: {len(d['steps'])} turns, winner {d['winner']}, bar " + ' '.join(f"{100 * s['wp']:.0f}" for s in d['steps']))
