"""Per-team GRID_DIRs for the planner (native/champ plan.rs / pssim/endgame2.js) from the per-set cells in out/.

The planner keys my side by base species ("foe|Salamence", "foe|Indeedee"), so a GRID_DIR holds one team's sets.
  python3 merge.py <team.json | team name in teams/start>...      -> griddirs/<team>/gx_cells_{tr,notr}_inc.json
  python3 merge.py --all                                          -> every start team
A team file is MYTEAM format; members are matched to grid ids by their exact set.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, ROOT)
import sets_lib as L
GRID = json.load(open(os.path.join(ROOT, 'grid_sets.json')))
BYKEY = {L.set_key(s): g for g, s in GRID.items()}

def base_key(species):
    sp = L.DEX['species'][L.idf(species)]
    return sp['base'].split('-Mega')[0]

def merge(team_path):
    name = os.path.splitext(os.path.basename(team_path))[0]
    team = json.load(open(team_path))
    outd = os.path.join(HERE, 'griddirs', name); os.makedirs(outd, exist_ok=True)
    missing = []
    for tag in ('tr', 'notr'):
        cells = {}
        for s in team.values():
            g = BYKEY.get(L.set_key(dict(species=s['species'], item=s.get('item') or '', ability=s['ability'], nature=s['nature'],
                                         evs=s['evs'], moves=s['moves'])))
            p = g and os.path.join(HERE, 'out', tag, g.replace('/', '_') + '.json')
            if not p or not os.path.exists(p): missing.append((tag, s['species'], g)); continue
            for foe, c in json.load(open(p))['cells'].items():
                cells[f"{foe}|{base_key(s['species'])}"] = {k: c[k] for k in ('v', 'pct', 'roll', 'det') if k in c}
        json.dump(cells, open(os.path.join(outd, f'gx_cells_{tag}_inc.json'), 'w'))
    return name, missing

def merge_gids(outd, gids):
    """GRID_DIR for a team given by grid ids -> list of (tag, gid) with no cells yet"""
    os.makedirs(outd, exist_ok=True); missing = []
    for tag in ('tr', 'notr'):
        cells = {}
        for g in gids:
            p = os.path.join(HERE, 'out', tag, g.replace('/', '_') + '.json')
            if not os.path.exists(p): missing.append((tag, g)); continue
            for foe, c in json.load(open(p))['cells'].items():
                cells[f"{foe}|{base_key(GRID[g]['species'])}"] = {k: c[k] for k in ('v', 'pct', 'roll') if k in c}
        json.dump(cells, open(os.path.join(outd, f'gx_cells_{tag}_inc.json'), 'w'))
    return missing

if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['--all']:
        d = os.path.join(ROOT, 'teams', 'start'); args = [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith('.json') and f != 'index.json']
    for a in args:
        if not a.endswith('.json'): a = os.path.join(ROOT, 'teams', 'start', a + '.json')
        n, miss = merge(a)
        print(n, 'ok' if not miss else f'missing {miss}')
