"""Static audit (the user asked for a bug hunt beyond luck, 2026-10-12): Showdown's hooks (engine_data_full.json cbs, from the champions mod) for every effect on real Reg M-C sheets, against the
hooks the native engine registers (h!(r, Kind, id, event), loops expanded) and whether its source names the effect at all"""
import os, re, json, glob, collections, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
MAIN = C.MAIN; SP = os.path.join(C.HERE, 'out', 'audit'); os.makedirs(SP, exist_ok=True)
E = json.load(open(os.path.join(MAIN, 'native', 'engine_data_full.json')))
def build_pool():
    """moves, abilities, items and species on the cached Reg M-C Bo3 team sheets, with a Mega's own ability counted for its stone"""
    toid = lambda x: re.sub(r'[^a-z0-9]', '', (x or '').lower())
    use = {k: collections.Counter() for k in ('move', 'ability', 'item', 'species')}
    for rid, log in C.games():
        seen = set()
        for l in log.split('\n'):
            p = l.split('|')
            if len(p) > 3 and p[1] == 'showteam' and p[2] not in seen:
                seen.add(p[2])
                for m in '|'.join(p[3:]).split(']'):
                    f = m.split('|')
                    if len(f) < 5: continue
                    use['species'][toid(f[1] or f[0])] += 1; use['item'][toid(f[2])] += 1; use['ability'][toid(f[3])] += 1
                    for mv in f[4].split(','): use['move'][toid(mv)] += 1
    for it, n in list(use['item'].items()):
        for k, v in E['species'].items():
            if v.get('requiredItem') and toid(v['requiredItem']) == it and v.get('isMega'): use['ability'][toid((v.get('abilities') or {}).get('0'))] += n
    return {k: dict(v.most_common()) for k, v in use.items()}
pool = build_pool()
src = {f: open(f).read() for f in glob.glob(os.path.join(MAIN, 'native', 'champ', 'src', '**', '*.rs'), recursive=True)}
reg = collections.defaultdict(set); lits = set()
for f, s in src.items():
    lits |= set(re.findall(r'"([a-z0-9]+)"', s))
    pats = [r'h!\(\s*r\s*,\s*(\w+)\s*,\s*("([a-z0-9]+)"|(\w+))\s*,\s*"(\w+)"',
            r'r\.insert\(\(\s*Kind::(\w+)\s*,\s*id\(\s*("([a-z0-9]+)"|(\w+))\s*\)\s*,\s*id\(\s*"(\w+)"\s*\)']
    for m in (m for pat in pats for m in re.finditer(pat, s)):
        kind, lit, var, ev = m.group(1), m.group(3), m.group(4), m.group(5)
        if lit: reg[(kind, lit)].add(ev); continue
        # a loop variable: the list in the nearest `for <var> in [...]` / `for (<var>, ..) in [...]` before it
        head = s[:m.start()]; fm = None
        for fm_ in re.finditer(r'for\s+\(?\s*' + re.escape(var) + r'\b[^\n]*?\bin\s*\[', head): fm = fm_
        if not fm: continue
        i = fm.end(); depth = 1; j = i
        while j < len(s) and depth: depth += {'[': 1, ']': -1}.get(s[j], 0); j += 1
        for x in re.findall(r'"([a-z0-9]+)"', s[i:j]): reg[(kind, x)].add(ev)
KIND = {'move': 'Move', 'ability': 'Ability', 'item': 'Item'}
rows = []
def check(kind, i, uses, data, label=None):
    cb = {k for k, v in (data.get('cbs') or {}).items() if not (isinstance(v, dict) and v.get('absent'))}   # 'absent': sort keys only
    if not cb: return
    have = reg.get((KIND.get(kind, 'Cond'), i), set()) | (reg.get(('Cond', i), set()) if kind == 'move' else set())
    if 'onStart' in have: have = have | {'onSwitchIn'}                    # the engine's getCallback: no onSwitchIn falls back to onStart
    miss = sorted(cb - have)
    if not miss: return
    rows.append({'kind': label or kind, 'id': i, 'uses': uses, 'showdown': sorted(cb), 'engine': sorted(have), 'missing': miss, 'named': i in lits})
for kind, key in (('move', 'moves'), ('ability', 'abilities'), ('item', 'items')):
    for i, n in pool[kind].items():
        if i in E[key]: check(kind, i, n, E[key][i])
        elif i: rows.append({'kind': kind, 'id': i, 'uses': n, 'showdown': [], 'engine': [], 'missing': ['NOT IN ENGINE DATA'], 'named': i in lits})
# conditions the pool's moves start (volatiles, side and field effects, statuses, weather, terrain)
cond_use = collections.Counter()
for i, n in pool['move'].items():
    mv = E['moves'].get(i) or {}
    for k in ('volatileStatus', 'sideCondition', 'slotCondition', 'pseudoWeather', 'weather', 'terrain', 'status'):
        if mv.get(k): cond_use[mv[k]] += n
    for sec in (mv.get('secondaries') or []) + ([mv['secondary']] if mv.get('secondary') else []):
        for k in ('volatileStatus', 'status'):
            if sec and sec.get(k): cond_use[sec[k]] += n
for c in ('par', 'slp', 'frz', 'brn', 'psn', 'tox', 'confusion', 'flinch', 'trapped', 'partiallytrapped', 'lockedmove', 'twoturnmove', 'choicelock', 'mustrecharge', 'stall',
          'raindance', 'sunnyday', 'sandstorm', 'snowscape', 'electricterrain', 'grassyterrain', 'mistyterrain', 'psychicterrain', 'trickroom', 'tailwind', 'reflect', 'lightscreen', 'auroraveil'):
    cond_use[c] += 0
for c, n in cond_use.items():
    d = E['conditions'].get(c) or (E['moves'].get(c) or {}).get('condition')
    if d: check('condition', c, n, d)
rows.sort(key=lambda r: (r['named'], -r['uses']))
json.dump(rows, open(os.path.join(C.HERE, 'hook_audit.json'), 'w'), indent=0)
A = [r for r in rows if not r['named']]; B = [r for r in rows if r['named']]
print(f"{len(A)} effects with Showdown hooks the engine never names; {len(B)} named but with hooks missing")
for r in A[:30]: print(f"  A {r['kind']:9s} {r['id']:18s} uses {r['uses']:6d}  showdown {r['showdown']}")
