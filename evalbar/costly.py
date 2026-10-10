"""The costly plays page: every play the day-1 study found costly (study.py publish), each with the full board as the players knew it at
the start of the turn (the live mode's state: field, both sides' Pokemon with HP, boosts and sets, the unseen back Pokemon as pools),
every active Pokemon's options, what happened, the game's win chance by turn and, when reads.py has run, whether the play was a read.
  python3 evalbar/costly.py <out.html> [name=day1] [video=05UxX2Rd9u8] [title=...] [event=...] [where=...]   the page (template costly.tpl)
The page carries no names: the logs say Player 1 and Player 2, and the build stops if anything else from the log would show."""
import os, sys, json, collections
import common as C, procs as P, replay as R, live as LV, study as ST
def build(name='day1', video='05UxX2Rd9u8'):
    res = json.load(open(os.path.join(C.HERE, 'results', f'broadcast_study_{name}.json'))); costly = res['costly_plays']
    D = json.load(open(os.path.join(ST.OUT, f'{name}.json'))); win = {g['game'].replace(name + '_', ''): g['winner'] for g in D['games']}
    X = collections.defaultdict(dict)
    for d in D['decisions']: X[(d['game'].replace(name + '_', ''), d['turn'])][d['side'] + '|' + d['mon']] = d
    games = {}
    for gid in sorted({c['game'] for c in costly}):
        tag = f'{name}_{gid}'; f = os.path.join(ST.OUT, tag + '.log'); log = open(f).read(); g = R.parse(log)
        L = LV.Live(None, 1, 0, logfile=f, tag=tag, fmt='Champions broadcast')
        if '|showteam|' not in log: L.bo3 = False                            # no sheets on stream: common sets, as the live page
        for st in g['steps']:
            if st['turn'] >= 1:
                sp, H = L.at(log, st['turn']); L.weights[st['turn']] = {x['name']: w for w, x in sp} if sp else {}; L.hyp[st['turn']] = H
        L.build(log, g); acts = {st['turn']: st['acts'] for st in g['steps']}
        steps = []
        for s in L.data['games'][0]['steps']:
            t = s['turn']; at = {m['sd'] + m['pos']: m['n'] for m in [{**m, 'sd': sd} for sd in ('p1', 'p2') for m in s['state'][sd]['mons'] if m.get('pos') and not m['f']]}
            tables = {}
            for k, d in X[(gid, t)].items():
                sd, mon = k.split('|'); pos = next((p for p, n in at.items() if p[:2] == sd and R.toid(mon.split('-')[0]) in R.toid(n)), None)
                a = acts.get(t, {}).get(pos) or {}; tg = a.get('target') or ''
                tables[k] = {'played': d['played'], 'top': d['top'], 'table': d['table'], 'target': at.get(tg[:3]) if tg else None}
            steps.append({'turn': t, 'wp': round(s['wp'], 4), 'state': s['state'], 'events': s['events'], 'opt': s['opt'], 'hyp': s['hyp'], 'tables': tables,
                          'vt': next((d['vt'] for d in X[(gid, t)].values() if d.get('vt') is not None), None)})
        games[gid] = {'winner': win.get(gid), 'sheets': g['sheets'], 'steps': steps}
    scen = [{**c, 'protect': ST.kind(c['played']) == 'Protect', **{k: round(X[(c['game'], c['turn'])][c['side'] + '|' + c['mon']][k], 4) for k in ('v_top', 'v_played')}}
            for c in costly]
    rf = os.path.join(C.HERE, 'out', 'reads', 'reads.json' if name == 'day1' else f'{name}_reads.json'); reads = {}
    if os.path.exists(rf):
        for r in json.load(open(rf)):
            if r.get('measured'): reads[f"{r['game']}-t{r['turn']}-{r['side']}-{R.toid(r['mon'])}"] = {k: r[k] for k in (
                'ante_played', 'ante_top', 'post_played', 'post_top', 'post_best', 'post_best_action', 'mass_better', 'shift', 'lines', 'opp', 'hypotheses', 'exact')}
    return {'video': video, 'scenarios': scen, 'games': games, 'reads': reads}
if __name__ == '__main__':
    P.own()
    if len(sys.argv) < 2: sys.exit(__doc__)
    kw = dict(x.split('=', 1) for x in sys.argv[2:] if '=' in x); d = build(kw.get('name', 'day1'), kw.get('video', '05UxX2Rd9u8')); blob = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
    import re
    other = set(re.findall(r'Player [A-Za-z0-9]+', blob)) - {'Player 1', 'Player 2'}
    if other: sys.exit(f'refusing to write the page: {len(other)} other player label(s) would appear on it')
    title, event, where = kw.get('title', 'Day 1 Costly Plays'), kw.get('event', 'Regional broadcast · Day 1'), kw.get('where', 'day 1 regional broadcast')
    html = open(os.path.join(C.HERE, 'costly.tpl')).read().replace('__TITLE__', title).replace('__EVENT__', event).replace('__WHERE__', where)
    html = html.replace('/*DATA*/null', blob.replace('</', '<\\/'), 1)
    open(sys.argv[1], 'w').write(html); print(f"{sys.argv[1]}: {len(d['scenarios'])} plays, {len(d['reads'])} with reads, {len(html)} bytes")
