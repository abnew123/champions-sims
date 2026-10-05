"""One-on-one cells for a team's six against the 46 grid threats, with Trick Room up and without: the full-battle planner's GRID_DIR
(its value function reads how each of my Pokemon fares one-on-one), written to sheets/<team>/work/grid/gx_cells_{tr,notr}_inc.json.

The cells come from the Team search thread's generic one-on-one code (teamsearch/mx, used read-only). What it models and what it leaves
out is listed in sheetkit/README.md ("The one-on-one grid"). About a minute of CPU for a six. Finished sets are kept (delete
work/grid/cells/ to rebuild after changing a set)."""
import concurrent.futures, hashlib
from common import *
from page import dex, idf

def pool_of(sheet): return {n: {k: s[k] for k in ('species', 'item', 'ability', 'nature', 'evs', 'moves')} for n, s in sheet.team.items()}
def cell_path(sheet, n, tr):
    """where one set's cells for one mode are kept; the name carries a hash of the set, so a changed set gets new cells"""
    tag = hashlib.sha1(json.dumps(pool_of(sheet)[n], sort_keys=True).encode()).hexdigest()[:8]
    return sheet.w('grid', 'cells', f"{'tr' if tr else 'notr'}_{idf(n)}_{tag}.json")

def build(sheet, workers=1, quiet=False):
    d = sheet.w('grid'); os.makedirs(os.path.join(d, 'cells'), exist_ok=True)
    pool = pool_of(sheet)
    wj(pool, os.path.join(d, 'pool.json'), indent=1)
    py = VENV_PY if os.path.exists(VENV_PY) else sys.executable
    def one(job):
        n, tr = job; out = cell_path(sheet, n, tr)
        if not os.path.exists(out):
            r = subprocess.run(['nice', '-n', '10', py, os.path.join(KIT, 'grid_worker.py'), n, out + '.tmp'], capture_output=True, text=True,
                               env=dict(os.environ, TR='1' if tr else '0', POOL_FILE=os.path.join(d, 'pool.json')))
            if r.returncode: return n, tr, None, (r.stderr or r.stdout).strip().split('\n')[-1]
            os.replace(out + '.tmp', out)
        return n, tr, rj(out), None
    res = {1: {}, 0: {}}; failed = []
    with concurrent.futures.ThreadPoolExecutor(workers) as ex:
        for n, tr, r, err in ex.map(one, [(n, tr) for n in sheet.names for tr in (1, 0)]):
            if err: failed.append(f"{n} ({'Trick Room' if tr else 'no Trick Room'}): {err}"); continue
            if not quiet: print(f"{now()} {n:14s} {'Trick Room up' if tr else 'no Trick Room'}: {len(r['cells'])} cells, {r['secs']} s", flush=True)
            base = dex()['species'][idf(sheet.team[n]['species'])]['base'].split('-Mega')[0]       # the planner keys my side by base species
            for foe, c in r['cells'].items(): res[tr][f"{foe}|{base}"] = {k: c[k] for k in ('v', 'pct', 'roll', 'det') if k in c}
    if failed: sys.exit('grid not written:\n  ' + '\n  '.join(failed))
    for tr, name in ((1, 'gx_cells_tr_inc.json'), (0, 'gx_cells_notr_inc.json')): wj(res[tr], os.path.join(d, name))
    if not quiet: print(f"grid written: {os.path.relpath(d, ROOT)} ({len(res[1])} cells per mode)")
