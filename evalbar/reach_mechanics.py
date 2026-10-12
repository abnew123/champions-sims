"""Which mechanics turn up in the turns the reachability check (reach.py) cannot reproduce, over the cached replays: for each move, ability,
item or effect named in a turn's log, how many checked turns name it and how many of those had a feature no run reached, against the
overall rate. A mechanic handled wrong, by the log reading, the rebuild or Showdown's data, should stand out.
  python3 evalbar/reach_mechanics.py          reads evalbar/out/reach/replays_*of*.jsonl, writes evalbar/out/reach/mechanics.json"""
import os, re, glob, json, collections
import common as C
OUT = os.path.join(C.HERE, 'out', 'reach')
TOK = [(re.compile(r'^\|move\|[^|]*\|([^|]+)'), 'move'), (re.compile(r'\[from\] (?:ability|item|move): ([^|]+)'), None),
       (re.compile(r'^\|-(?:activate|start|end|enditem|item|ability|sidestart|fieldstart)\|[^|]*\|(?:(?:move|ability|item): )?([^|]+)'), None)]
def tokens(lines):
    out = set()
    for l in lines:
        for rx, kind in TOK:
            for m in rx.finditer(l):
                name = m.group(1).strip()
                if name and not name.startswith('[') and not re.fullmatch(r'[0-9/ a-z]+', name): out.add(name)
    return out
def turn_lines(log, t):
    i = log.find(f'\n|turn|{t}\n')
    if i < 0: return []
    j = log.find('\n|turn|', i + 1); return log[i + 1:j if j > 0 else len(log)].split('\n')
if __name__ == '__main__':
    rows = [json.loads(l) for f in glob.glob(os.path.join(OUT, 'replays_*of*.jsonl')) for l in open(f)]
    rows = [r for r in rows if 'unreached' in r and not r.get('partial')]
    NEEDS = {k for k, v in __import__('spreads').E['moves'].items() if v.get('target') in ('normal', 'any', 'adjacentFoe', 'adjacentAlly', 'adjacentAllyOrSelf')}
    toid = lambda x: re.sub(r'[^a-z0-9]', '', x.lower())
    def guessed(lines):                                                        # a move the log shows without its target (rows from before reach.py
        return any(len(p) > 4 and p[1] == 'move' and not p[4] and toid(p[3]) in NEEDS for p in (l.split('|') for l in lines))   # marked these partial)
    rid = {r.split('-')[-1]: r for r, _ in C.games()}; logs = {}
    seen, bad = collections.Counter(), collections.Counter(); nbad = 0
    for r in rows:
        k = rid.get(r['game'])
        if not k: continue
        if k not in logs: logs = {k: open(os.path.join(C.LOGS, k + '.log')).read()}
        lines = turn_lines(logs[k], r['turn'])
        if guessed(lines): continue
        tk = tokens(lines); seen.update(tk)
        if r['unreached']: bad.update(tk); nbad += 1
    base = nbad / max(1, len(rows))
    rank = sorted(((bad[t] / seen[t], seen[t], bad[t], t) for t in seen if seen[t] >= 30), reverse=True)
    json.dump({'turns': len(rows), 'unreached': nbad, 'rate': base, 'rank': [{'name': t, 'turns': n, 'unreached': b, 'rate': round(p, 3)} for p, n, b, t in rank]},
              open(os.path.join(OUT, 'mechanics.json'), 'w'), indent=0)
    print(f'{len(rows)} turns with every choice known, {nbad} with a feature no run reached ({100 * base:.1f}%)')
    for p, n, b, t in rank[:30]: print(f'  {t:24s} {b:5d} / {n:6d}  {100 * p:5.1f}%  ({p / base if base else 0:.1f}x)')
