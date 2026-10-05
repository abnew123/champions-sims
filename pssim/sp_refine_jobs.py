# Refinement jobs for the Incineroar Speed test (Brave 72 vs Adamant 81, spread study 2026-10-02).
# Leads: every Incineroar lead refined in v11, plus any Incineroar lead either stage one puts in contention (tr_select picks).
# Rows: union of v11's refined rows and both stage ones' keep rows, so both teams are refined on the same actions.
#   usage: python3 sp_refine_jobs.py <sel72 prefix> <sel81 prefix> <out prefix>
import json, glob, os, sys
sel72, sel81, out = sys.argv[1:4]
key = lambda j: (j['arch'], '+'.join(j['lead']), j['pair'])
rkey = lambda r: (r['arch'], '+'.join(r['myLead']), r['pair'])
src = {}                                    # v11 refined jobs, by key
for jf, d in (('jobs_inc2.json', 'inc2'), ('jobs_inc3.json', 'inc3')):
    J = json.load(open(jf))
    for f in glob.glob(f'results/v11/{d}_*.json'):
        i = int(os.path.basename(f)[len(d) + 1:-5]); src[key(J[i])] = J[i]
assert all(rkey(json.load(open(f))) in src for f in glob.glob('results/v11/*.json'))
rows, jobs = {}, {}
for k, j in src.items():
    if 'Incineroar' in k[1]: rows.setdefault(k, set()).update(j['rows']); jobs[k] = j
for p in (sel72, sel81):
    for j in json.load(open(p + '.json')):
        if 'Incineroar' in j['lead']: rows.setdefault(key(j), set()).update(j['rows']); jobs.setdefault(key(j), j)
sel = [dict(jobs[k], rows=sorted(rows[k])) for k in sorted(jobs)]
items = [j for j in sel if 'Indeedee-F' in j['pair'].split(' + ')]
json.dump(sel, open(out + '.json', 'w')); json.dump(items, open(out + '_items.json', 'w'))
new = sorted({k[:2] for k in jobs} - {k[:2] for k in src})
print(f'{len(sel)} jobs ({sum(len(j["rows"]) for j in sel)} rows; v11 had {sum(len(j["rows"]) for k, j in src.items() if "Incineroar" in k[1])}), '
      f'{len(items)} item jobs; leads not refined in v11: {new or "none"}')
