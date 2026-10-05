"""The Speed table for a team's page: the six among the common opposing spreads. Writes speed.json (rows: [speed, yours, theirs, tie]).

Opposing tiers come from Smogon's Reg M-C moveset stats (regionals/smogon_mc_2026-09_moveset.txt): for each of the most-used
Pokemon (and every threat on the team's Matchups list), each of its listed top spreads gives one Speed, labelled by nature and
Speed points. Champions stats: floor((base + 20 + SP) x nature). A Mega is listed at its Mega forme's Speed.

sheet.json "speed" options (all optional):
  order   "fastest-first" (default) or "slowest-first" (default for a team scored with the slower-four Trick Room credit)
  top     how many of the most-used Pokemon to list (default 30)
  tiers   at most this many Speeds per Pokemon, its most common first (default 2; 0 = every listed spread)
  range   [low, high]: Speeds outside it are folded into one "everything else" row at each end
          (default: from 15 below the six's slowest to 15 above its fastest)
A speed.json with "hand": true was written by hand and is not overwritten (--force does)."""
import re
from common import *
from page import dex, idf, stats

STATS = os.path.join(ROOT, 'regionals', 'smogon_mc_2026-09_moveset.txt')
SECTIONS = ('Abilities', 'Items', 'Spreads', 'Moves', 'Teammates', 'Checks and Counters')

def moveset(path=STATS):
    """{species as Smogon names it: {count, spreads: [(nature, [6 SP], %)]}}, most used first"""
    out, cur, sec = {}, None, None; lines = open(path).read().splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r'^\| (.+?) +\|$', ln)
        if not m: continue
        txt = m.group(1).strip()
        if lines[i - 1].startswith('+') and i + 1 < len(lines) and lines[i + 1].startswith('+') and txt not in SECTIONS \
                and not txt.startswith(('Raw count', 'Avg', 'Viability')):
            cur = txt; out[cur] = {'count': 0, 'spreads': []}; sec = None; continue
        if cur is None: continue
        if txt in SECTIONS: sec = txt
        elif txt.startswith('Raw count'): out[cur]['count'] = int(txt.split(':')[1])
        elif sec == 'Spreads':
            mm = re.match(r'^(\w+):([\d/]+) ([\d.]+)%$', txt)
            if mm: out[cur]['spreads'].append((mm.group(1), [int(x) for x in mm.group(2).split('/')], float(mm.group(3))))
    return dict(sorted(out.items(), key=lambda kv: -kv[1]['count']))

def shown(name):
    """Smogon / engine forme name -> how the page writes it"""
    m = re.match(r'^(.*)-Mega(-[XYZ])?$', name)
    if m: return 'Mega ' + m.group(1) + (' ' + m.group(2)[1:] if m.group(2) else '')
    return {'Indeedee-F': 'Indeedee F', 'Indeedee': 'Indeedee M', 'Arcanine-Hisui': 'Arcanine-H', 'Floette-Eternal': 'Floette'}.get(name, name)

GRID_NAMES = {'Arcanine-H': 'Arcanine-Hisui', 'M-Floette': 'Floette-Mega', 'M-Garchomp Z': 'Garchomp-Mega-Z', 'M-Charizard Y': 'Charizard-Mega-Y',
              'M-Raichu Y': 'Raichu-Mega-Y'}
def smogon_name(threat):
    """a Matchups threat name ('M-Salamence') -> its name in the stats ('Salamence-Mega')"""
    return GRID_NAMES.get(threat) or (threat[2:] + '-Mega' if threat.startswith('M-') else threat)

def tiers(species, spreads, keep=0):
    """[(Speed, label)] for one Pokemon: one entry per distinct Speed among its listed spreads (the `keep` most common, 0 = all)"""
    sp = dex()['species'].get(idf(species))
    if not sp: return []
    by = {}
    for nat, pts, pct in spreads:
        by.setdefault(stats(sp['stats'], nat, pts)[5], []).append((nat, pts[5], pct))
    if keep: by = dict(sorted(by.items(), key=lambda kv: -sum(x[2] for x in kv[1]))[:keep])
    out = []
    for v, xs in sorted(by.items()):
        if len(by) == 1: out.append((v, shown(species))); continue
        nats = list(dict.fromkeys(n for n, _, _ in sorted(xs, key=lambda x: -x[2]))); pts = sorted({p for _, p, _ in xs})
        pt = ('no Speed points' if pts == [0] else 'max Speed' if pts == [32] else f"{pts[0]} Speed point{'s' if pts[0] != 1 else ''}" if len(pts) == 1
              else f"{pts[0]}-{pts[-1]} Speed points")
        # the nature is enough when no other tier of this Pokemon shares it; otherwise say the Speed points too
        shared = any(n in {m for m, _, _ in ys} for w, ys in by.items() if w != v for n in nats)
        out.append((v, f"{shown(species)} ({', '.join(nats)}{', ' + pt if shared else ''})"))
    return out

def build(sheet, out=None, force=False):
    out = out or sheet.p('speed.json')
    if os.path.exists(out) and rj(out).get('hand') and not force: sys.exit(f"{os.path.relpath(out, ROOT)} is hand-written (\"hand\": true); --force overwrites it")
    c = sheet.cfg.get('speed', {}); MS = moveset(); D = dex()
    slow_first = c.get('order', 'slowest-first' if sheet.cfg.get('t1', {}).get('tr_credit') == 'slower-four' else 'fastest-first') == 'slowest-first'
    # mine
    mine = {}
    for n, s in sheet.team.items():
        sp = D['species'][idf(s['species'])]; name = sheet.my_names.get(n, n)
        mega = (D['items'].get(idf(s['item']), {}).get('megaStone') or {}).get(sp['name'])
        if mega: sp = D['species'][idf(mega)]; name = 'Mega ' + name
        mine.setdefault(stats(sp['stats'], s['nature'], s['evs'])[5], []).append(name)
    # theirs: the most-used Pokemon plus the team's Matchups threats, most used first within a row
    want = list(MS)[:c.get('top', 30)] + [smogon_name(t) for t in sheet.cfg.get('threats', []) if smogon_name(t) in MS]
    theirs = {}
    for species in sorted(dict.fromkeys(want), key=lambda s: -MS[s]['count']):
        for v, label in tiers(species, MS[species]['spreads'], c.get('tiers', 2)): theirs.setdefault(v, []).append((species, label))
    lo, hi = c.get('range', [min(mine) - 15, max(mine) + 15])
    rows = [[v, ', '.join(mine.get(v, [])), ', '.join(l for _, l in theirs.get(v, [])), 'Tie' if v in mine and v in theirs else '']
            for v in sorted(set(mine) | set(theirs)) if lo <= v <= hi]
    def rest(vals, word):                                        # the most-used Pokemon with a spread out there
        names = sorted({sp for v in vals for sp, _ in theirs[v]}, key=lambda sp: -MS[sp]['count'])
        return f"Everything {word}, including {', '.join(shown(sp) for sp in names[:8])}"
    below = sorted(v for v in theirs if v < lo); above = sorted(v for v in theirs if v > hi)
    if below: rows.insert(0, [f"{below[-1]} or less", '', rest(below, 'slower'), ''])
    if above: rows.append([f"{above[0]}+", '', rest(above, 'faster'), ''])
    if not slow_first: rows.reverse()
    wj({'made': f"kit speed step from {os.path.basename(STATS)}", 'order': 'slowest-first' if slow_first else 'fastest-first', 'rows': rows}, out,
       indent=1, ensure_ascii=False)
    print(f"{os.path.relpath(out, ROOT)}: {len(rows)} rows ({'slowest' if slow_first else 'fastest'} first), your six at {sorted(mine)}")
