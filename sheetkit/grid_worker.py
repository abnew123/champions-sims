"""One set against every threat in the one-on-one grid, one Trick Room mode: called by grid.py as its own process.
  TR=1|0 POOL_FILE=<pool.json> python3 grid_worker.py <set id> <out.json>
Uses the Team search thread's generic one-on-one code (teamsearch/mx) read-only: it builds my side from any set, and its cell() needs
the process's main thread (solver time limits by signal) and POOL_FILE / TR in the environment before the first import."""
import sys, os, json, time
gid, out = sys.argv[1], os.path.abspath(sys.argv[2])
MX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'teamsearch', 'mx')
os.chdir(MX); sys.path.insert(0, MX)                       # the mx modules open their data files by relative path
import grid_pool, matchup
if gid not in matchup.MINE:
    sys.exit(f"{gid}: the one-on-one code could not build this set (species, a move or the item is missing from native/champions_data.json)")
t = time.time(); cells = {foe: grid_pool.cell(gid, foe) for foe in grid_pool.FOES}
json.dump({'gid': gid, 'tr': os.environ.get('TR') == '1', 'secs': round(time.time() - t, 1), 'cells': cells}, open(out, 'w'))
