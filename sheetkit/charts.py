"""Coverage and Matchups for a team's page, from the one-on-one grid: writes charts.json.

  Matchups  one row per threat, one column per attacker (a Pokemon with no attacking move has no column), Trick Room up and not:
            the grid step's verdict for each cell plus its detail line, "needs its item" mark and move line
  Coverage  each attacker's hardest hit on each threat, worst gaps first

Threats: sheet.json "threats" (names from the grid's 46), default the 29 with usage numbers (team-sheet.html.usage.json at the repo
root: op.gg doubles usage, or a ladder rank as "#13"). Runs the grid step first if a set has no cells yet."""
import concurrent.futures
from common import *
import grid as G
import procs

USAGE = rj(os.path.join(ROOT, 'team-sheet.html.usage.json'))
ITEMNOTE = {"Focus Sash": "Sash", "Chople": "Chople", "Colbur": "Colbur", "Sitrus": "Sitrus"}      # threat items a Coverage row names

def build(sheet, workers=1, out=None):
    G.build(sheet, workers, quiet=True)
    threats = sheet.cfg.get('threats') or list(USAGE); d = sheet.w('charts'); os.makedirs(d, exist_ok=True)
    py, penv = procs.python(sheet, venv=True)
    def one(tr):
        tag = 'tr' if tr else 'notr'; job = os.path.join(d, f'job_{tag}.json'); res = os.path.join(d, f'res_{tag}.json')
        wj({'names': sheet.names, 'threats': threats, 'cells': {n: G.cell_path(sheet, n, tr) for n in sheet.names}}, job)
        r = subprocess.run(['nice', '-n', '10', py, os.path.join(KIT, 'charts_worker.py'), job, res], capture_output=True, text=True,
                           env=dict(os.environ, **penv, TR='1' if tr else '0', POOL_FILE=sheet.w('grid', 'pool.json')))
        if r.returncode: sys.exit(f"charts ({tag}) failed:\n{(r.stderr or r.stdout).strip()[-1500:]}")
        return tr, rj(res)
    with concurrent.futures.ThreadPoolExecutor(min(2, workers)) as ex: R = dict(ex.map(one, (1, 0)))
    cov, item = R[0]['cov'], R[0]['item']
    their = lambda f: THEIR_NAMES.get(f, f); mine = lambda n: sheet.my_names.get(n, n)
    usage = lambda f: USAGE[f] if isinstance(USAGE.get(f), str) else (round(USAGE[f], 1) if USAGE.get(f) else 0)
    attackers = [n for n in sheet.names if any(n in cov[f] for f in threats)]
    rows = []
    for f in threats:
        rank = sorted(((n, cov[f][n]) for n in attackers if n in cov[f]), key=lambda kv: -kv[1][0])       # ties: team order
        if not rank: continue
        name = their(f) + (f" ({ITEMNOTE[item[f]]})" if item[f] in ITEMNOTE else '')
        rows.append((sum(1 for _, v in rank if v[3] == 16), round(rank[0][1][0], 1),
                     [name, usage(f), 1 if item[f] == 'Focus Sash' else 0, [[mine(n), v[1], v[2], round(v[0], 1), v[3]] for n, v in rank]]))
    rows.sort(key=lambda r: (r[0], r[1]))                            # fewest guaranteed knockouts first, then the weakest best hit
    def cell(c):
        o = {'v': c['v'], 't': c['det']}
        if c.get('pct') is not None: o['p'] = c['pct']
        if c.get('dep'): o['d'] = c['dep']
        if c.get('note'): o['n'] = c['note']
        return o
    X = [[their(f), usage(f)] + [[cell(R[tr]['cells'][f'{f}|{n}']) for n in attackers] for tr in (1, 0)] for f in threats]
    out = out or sheet.p('charts.json')
    wj({'attackers': attackers, 'coverage': [r[2] for r in rows], 'matchups': X}, out, indent=1, ensure_ascii=False)
    n = lambda tr, v: sum(c['v'] == v for r in X for c in r[2 if tr else 3])
    print(f"{os.path.relpath(out, ROOT)}: {len(X)} threats x {len(attackers)} attackers; Trick Room up {n(1, 'counter')} counters / {n(1, 'check')} checks, "
          f"without {n(0, 'counter')} / {n(0, 'check')}; {sum(r[0] == 0 for r in rows)} threats with no guaranteed one-hit KO")
