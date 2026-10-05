"""Version 15 merge: results/v15plus{,_colburberry,_psychicseed} = v14plus with every (arch, lead, opposing pair) re-run in results/v15
(real sets, each tab's planned back row) replaced by the new result; tr_speeds_v15.json = tr_speeds_v14.json + the new jobs' speeds."""
import json, glob, os, shutil
def key(r): return (r['arch'], '+'.join(r['myLead']), r['pair'])
new = {key(json.load(open(f))) for f in glob.glob('results/v15/*.json')}
for s in ('', '_colburberry', '_psychicseed'):
    d = f'results/v15plus{s}'; shutil.rmtree(d, ignore_errors=True); os.makedirs(d); kept = 0
    for f in glob.glob(f'results/v14plus{s}/*.json'):
        if key(json.load(open(f))) in new: continue
        os.symlink(os.path.realpath(f), f'{d}/{os.path.basename(f)}'); kept += 1
    added = 0
    for f in glob.glob(f'results/v15{s}/*.json'):
        os.symlink(os.path.realpath(f), f'{d}/v15_{os.path.basename(f)}'); added += 1
    print(d, 'kept', kept, 'added', added)
sp = json.load(open('tr_speeds_v14.json')); sp.update(json.load(open('tr_speeds_v15new.json'))); json.dump(sp, open('tr_speeds_v15.json', 'w'))
