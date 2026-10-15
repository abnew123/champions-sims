"""Rebuild the cross-team game cache (gamecache.py) from run folders copied home, after a box is lost (2026-10-15: the v33 climb's
Spain box was reclaimed mid round 1; its SQLite cache never left the box, but every finished game was in the pulled runs/). Every run
folder with a jobs.json and out_<setup>_<seed0>_<per_job>/<j>.json files gives each finished, seed-keyed job's result under the key
run_jobs would look up (setup, engine data, seed0, per_job, job). Pool runs only (engine_data_full.json); jobs without a seed key are
skipped, and so are half-written files.
  python3 rebuild_gamecache.py <runs dir> <out games.sqlite>      then copy the file to the new box as the climb's TS_GAME_CACHE
"""
import json, os, sys, glob, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import gamecache as GC
ED = 'engine_data_full.json'

if __name__ == '__main__':
    runs, out = sys.argv[1], sys.argv[2]; n = bad = 0; batch = []
    for d in sorted(glob.glob(os.path.join(runs, '*'))):
        jp = os.path.join(d, 'jobs.json')
        if not os.path.exists(jp): continue
        jobs = json.load(open(jp))
        for o in glob.glob(os.path.join(d, 'out_*')):
            m = re.match(r'out_(.+)_(\d+)_(\d+)$', os.path.basename(o))
            if not m: continue
            setup, seed0, per_job = m.group(1), int(m.group(2)), int(m.group(3))
            for j, job in enumerate(jobs):
                f = os.path.join(o, f'{j}.json')
                if not os.path.exists(f) or 'seed_index' not in (job.get('meta') or {}): continue
                try: r = json.load(open(f))
                except Exception: bad += 1; continue
                batch.append((GC.key(setup, ED, seed0, per_job, job), r)); n += 1
                if len(batch) >= 5000: GC.put_many(out, batch); batch = []
    if batch: GC.put_many(out, batch)
    print(f"{n} games from {runs} ({bad} half-written files skipped); {GC.stats(out)} distinct games in {out}")
