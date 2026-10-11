"""How often does the opponent's real Speed contradict the spread the bot assumed? (2026-10-11, the user: the position builder never
updates its guess of an opponent's spread from what the game shows.) For every turn of the bot's saved games, each pair of moves (ours,
theirs) at the same priority, with no Trick Room, Tailwind, weather, terrain, Speed change, paralysis, Quick Claw / Custap / Quick Draw
or Unburden in play that turn, says which of the two was faster. Our Speed is exact (the request); theirs is assumed the way the
builder assumes it (evalbar/spots.py evs_for: the species' usual spread for its sheet nature), Champions' stat formula
(base + stat points + 20, x nature). A pair contradicts the assumption when the observed order disagrees with the assumed Speeds and
they are not tied; it is impossible when no spread (0-32 Speed points) explains it.
  .venv/bin/python3 bot/speed_check.py"""
import json, os, sys, glob, re, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'evalbar'))
import spots as SPOTS
CD = json.load(open(os.path.join(ROOT, 'native', 'champions_data.json')))
MOVES = {m['name']: m for m in json.load(open(os.path.join(ROOT, 'native', 'engine_data_full.json')))['moves'].values()}
NAT = CD['natures']; toid = lambda s: re.sub(r'[^a-z0-9]', '', (s or '').lower())
SPEC = {toid(v['name']): v for v in CD['species'].values()}
def spe(species, sp, nature):
    s = SPEC.get(toid(species))
    if not s: return None
    x = s['stats']['spe'] + sp + 20; n = NAT.get(toid(nature), {})
    return int(x * 1.1) if n.get('plus') == 'spe' else int(x * 0.9) if n.get('minus') == 'spe' else x
def unpack(packed):
    out = {}
    for x in packed.split(']'):
        f = x.split('|')
        if len(f) < 10: continue
        sp = f[1] or f[0]; out[sp] = {'species': sp, 'item': f[2], 'ability': f[3], 'moves': [MOVES.get(m, {}).get('name', m) for m in f[4].split(',')], 'nature': f[5] or 'Serious'}
    return out
G = {json.loads(l)['room']: json.loads(l) for l in open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl'))}
pairs = contra = impossible = 0; by = collections.Counter(); ex = []
for room, g in G.items():
    f = os.path.join(ROOT, 'bot', 'out', room + '.log')
    if not os.path.exists(f): continue
    me = g['side']; op = 'p2' if me == 'p1' else 'p1'
    L = open(f, errors='ignore').read().split('\n')
    sheet = {}
    for l in L:
        if l.startswith(f'|showteam|{op}|'): sheet = {k: v for k, v in unpack(l.split('|', 3)[3]).items()}
    def norm_sheet(name):
        for k in sheet:
            if toid(k) == toid(name) or toid(name).startswith(toid(k)): return sheet[k]
    nick = {}; form = {}; req = None; field_ok = True; tr = tw = weather = terrain = False; boosts = collections.Counter(); par = set(); used = set()
    turn_lines = []
    def flush():
        global pairs, contra, impossible
        if not turn_lines or req is None: return
        if tr or tw or weather or terrain: return
        text = '\n'.join(turn_lines)
        if re.search(r'\|-(boost|unboost)\|[^|]*\|spe', text) or 'Quick Claw' in text or 'Custap' in text or 'Quick Draw' in text or '|-sidestart|' in text or 'trickroom' in text.lower() or '|-status|' in text: return
        mv = []
        for l in turn_lines:
            p = l.split('|')
            if len(p) > 3 and p[1] == 'move' and not any(x.startswith('[from]') for x in p[4:]):
                m = MOVES.get(p[3]); ident = p[2]
                if not m or m.get('priority', 0) != 0: continue
                if m['category'] == 'Status' and ident.startswith(op): continue          # Prankster could have raised it
                mv.append(ident)
        ours = {}
        for p in req['side']['pokemon']:
            if p.get('active'): ours[p['ident'].split(': ', 1)[1]] = (p['stats']['spe'], p['details'].split(',')[0])
        for i in range(len(mv)):
            for j in range(i + 1, len(mv)):
                a, b = mv[i], mv[j]
                if a[:2] == b[:2]: continue
                o, t = (a, b) if a.startswith(me) else (b, a); ours_first = a.startswith(me)
                on = o.split(': ', 1)[1]; tn = t.split(': ', 1)[1]
                if on not in ours or on in par or tn in par or boosts[o[:2] + on] or boosts[t[:2] + tn]: continue
                ospe = ours[on][0]; sh = norm_sheet(nick.get(t[:3] + tn, tn))
                if not sh or toid(sh['item']) in ('choicescarf', 'quickclaw') or toid(sh['ability']) in ('unburden', 'speedboost'): continue
                cur = form.get(t[:3] + tn, sh['species'])
                ev = SPOTS.evs_for(sh['species'], sh['item'], sh['nature'], sh['moves'])
                ts = spe(cur, ev[5], sh['nature']); lo = spe(cur, 0, sh['nature']); hi = spe(cur, 32, sh['nature'])
                if ts is None: continue
                pairs += 1
                if ts == ospe: continue
                assumed_ours_first = ospe > ts
                if assumed_ours_first != ours_first:
                    contra += 1; by[cur] += 1
                    imp = (not ours_first and hi < ospe) or (ours_first and lo > ospe)
                    impossible += imp
                    if len(ex) < 12: ex.append(f"{cur} (sheet {sh['nature']}, assumed {ev[5]} Speed points = {ts}, possible {lo}-{hi}) vs our {ours[on][1]} at {ospe}: {'they' if not ours_first else 'we'} moved first{' (no spread explains it)' if imp else ''}")
    for l in L:
        p = l.split('|')
        if len(p) < 2: continue
        if p[1] == 'request' and len(p) > 2 and p[2].startswith('{'):
            try: r = json.loads(p[2])
            except Exception: r = None
            if r and r.get('active'): req = r
        elif p[1] == 'turn': flush(); turn_lines = []; continue
        elif p[1] in ('switch', 'drag') and len(p) > 3:
            ident = p[2][:2] + ':' + p[2].split(': ', 1)[1]; boosts[p[2][:2] + p[2].split(': ', 1)[1]] = 0
            nick[p[2][:3] + p[2].split(': ', 1)[1]] = p[3].split(',')[0]; form[p[2][:3] + p[2].split(': ', 1)[1]] = p[3].split(',')[0]
        elif p[1] in ('detailschange', '-formechange') and len(p) > 3: form[p[2][:3] + p[2].split(': ', 1)[1]] = p[3].split(',')[0]
        elif p[1] in ('-boost', '-unboost') and len(p) > 3 and p[3] == 'spe': boosts[p[2][:2] + p[2].split(': ', 1)[1]] += 1
        elif p[1] == '-status' and len(p) > 3 and p[3] == 'par': par.add(p[2].split(': ', 1)[1])
        elif p[1] == '-fieldstart' and 'Trick Room' in l: tr = True
        elif p[1] == '-fieldend' and 'Trick Room' in l: tr = False
        elif p[1] == '-fieldstart' and 'Terrain' in l: terrain = True
        elif p[1] == '-fieldend' and 'Terrain' in l: terrain = False
        elif p[1] == '-sidestart' and 'Tailwind' in l: tw = True
        elif p[1] == '-sideend' and 'Tailwind' in l: tw = False
        elif p[1] == '-weather' and len(p) > 2: weather = p[2] not in ('none', '')
        turn_lines.append(l)
print(f"{len(G)} games; informative speed comparisons {pairs}; the assumed spread got the order wrong in {contra} ({100 * contra / max(1, pairs):.0f}%); no spread at all explains {impossible} of those")
print('wrong most often for:', by.most_common(8))
for e in ex: print('  ', e)
