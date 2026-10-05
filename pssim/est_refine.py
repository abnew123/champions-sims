# Estimate refinement worker-time from stage-1 logs: time scales with rows kept and samples.
import json, re, sys
tag = sys.argv[1]; NS = int(sys.argv[2]) if len(sys.argv) > 2 else 12
L = {}
for w in (0, 1):
    for line in open(f'results/c_{tag}_w{w}.log'):
        m = re.match(r'\S+ \d+ (.*?) \| (.*?) \| (.*?) (\d+)x(\d+) (\d+)s', line)
        if m: L[(m.group(1), m.group(3), m.group(2))] = (int(m.group(4)), int(m.group(5)), float(m.group(6)))
tot1 = sum(v[2] for v in L.values())
r = json.load(open(f'jobs_r_{tag}.json')); it = json.load(open(f'jobs_r_{tag}_items.json'))
def est(js):
    e = 0
    for j in js:
        my, th, sec = L[(j['arch'], '+'.join(j['lead']), j['pair'])]; e += sec * len(j['rows']) / my * NS
    return e
e1, e2 = est(r), est(it) * 2
print(f'{tag}: stage-1 {len(L)} jobs {tot1/60:.0f} worker-min | refine {len(r)} jobs {e1/60:.0f} worker-min + items {len(it)}x2 {e2/60:.0f} worker-min '
      f'-> {(e1+e2)/2/60:.0f} min on 2 workers at {NS} samples')
