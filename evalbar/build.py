"""Eval bar page for one cached replay.
  python3 evalbar/build.py pick                 lists cached games that make a good demo (high rated, played out, the lead changes hands)
  python3 evalbar/build.py <replay id> [acc=<accuracy json>] [engine=<evalpos output .jsonl> pos=<the positions .jsonl it was run on>]
writes evalbar/out/<replay id>.html. Without engine results the page is version 0 (the bar from the real-game win-chance model). With
them every turn also gets each active Pokemon's options: how often the planner picks each, what each is worth, and which was played.
The page shows no usernames or nicknames (players are Player 1 / Player 2); build fails if one would get through."""
import os, re, sys, json
import common as C, replay as R
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
def options(e, pos):
    """evalpos line + the position line it came from -> {'p1': [slot...], 'p2': [...]}, slot = {mon, played (True, or None if unknown), options: [{l, w, v, played}]}"""
    out = {}
    for s, sd, acts in ((0, 'p1', pos['actual']), (1, 'p2', pos['their_actual'])):
        out[sd] = []
        for sl in e['sides'][s]['slots']:
            a = acts[sl['slot']]; a = a['choice'] if a else None
            opts = [{'l': label(o['label']), 'w': round(o['w'], 3), 'v': round(o['v'], 3), 'played': bool(a) and same(o['c'], a)} for o in sl['options']]
            out[sd].append({'mon': R.disp(sl['mon']), 'played': True if any(o['played'] for o in opts) else None, 'options': opts})
    return out
def leak_check(text, hidden):
    low = text.lower()
    bad = [h for h in hidden if re.search(r'(?<![a-z0-9])' + re.escape(h.lower()) + r'(?![a-z0-9])', low)]
    if bad: sys.exit(f'refusing to write the page: {len(bad)} username(s) or nickname(s) would appear on it')
if __name__ == '__main__':
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
        d['acc'] = json.load(open(arg['acc'])) if 'acc' in arg else None
        if 'engine' in arg:
            ev = {x['name']: x for x in map(json.loads, open(arg['engine'])) if 'error' not in x}; ps = {x['name']: x for x in map(json.loads, open(arg['pos']))}
            for s in d['steps']:
                nm = f"{rid} t{s['turn']} p1"
                if nm in ev: s['opt'] = options(ev[nm], ps[nm]); s['ev'] = ev[nm]['value']
            d['engine'] = {'turns': sum('opt' in s for s in d['steps']), 'seeds': max((x.get('seeds', 0) for x in ev.values()), default=0)}
        blob = json.dumps(d, ensure_ascii=False, separators=(',', ':')); leak_check(blob, hidden)
        page = open(os.path.join(C.HERE, 'page.html')).read().replace('/*DATA*/null', blob.replace('</', '<\\/'))
        os.makedirs(os.path.join(C.HERE, 'out'), exist_ok=True); outf = os.path.join(C.HERE, 'out', rid + '.html'); open(outf, 'w').write(page)
        print(f"{os.path.relpath(outf, C.REPO)}: {len(d['steps'])} turns, winner {d['winner']}, bar " + ' '.join(f"{100 * s['wp']:.0f}" for s in d['steps']))
