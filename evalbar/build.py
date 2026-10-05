"""Eval bar page for one cached replay (version 0: the bar only, from the real-game win-chance model; no engine).
  python3 evalbar/build.py pick                 lists cached games that make a good demo (high rated, played out, the lead changes hands)
  python3 evalbar/build.py <replay id> [acc.json]   writes evalbar/out/<replay id>.html (acc.json: accuracy.py's output, quoted on the page)
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
        rid = sys.argv[1]; log = open(os.path.join(C.LOGS, rid + '.log')).read()
        d, hidden = game_data(rid, log, w)
        d['acc'] = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
        blob = json.dumps(d, ensure_ascii=False, separators=(',', ':')); leak_check(blob, hidden)
        page = open(os.path.join(C.HERE, 'page.html')).read().replace('/*DATA*/null', blob.replace('</', '<\\/'))
        os.makedirs(os.path.join(C.HERE, 'out'), exist_ok=True); outf = os.path.join(C.HERE, 'out', rid + '.html'); open(outf, 'w').write(page)
        print(f"{os.path.relpath(outf, C.REPO)}: {len(d['steps'])} turns, winner {d['winner']}, bar " + ' '.join(f"{100 * s['wp']:.0f}" for s in d['steps']))
