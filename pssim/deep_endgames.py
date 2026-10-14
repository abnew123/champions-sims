"""Does the anytime search's depth (deep.rs, EVAL_DEPTH / BATTLE_EVAL) play endgames better? (2026-10-14, the user: a sanity check
where depth must help, since it can search them through and the one-turn search cannot; if it does not, the testing is broken.)
Starts are real endgames from the value data (results/value/real_fit / real_hold positions, both sides with at most two living Pokemon
and none on the bench), stratified by size; each is played out twice by champ battle with BATTLE_EVAL=1 on the same luck: arm B with
depth on side 0, arm C with depth on side 1, the other side the same search without depth at the same budget. The deep side's gain over
an even split is (v_B - v_C) / 2 per start (v = side 0's result), standard errors over starts.
  ../.venv/bin/python3 deep_endgames.py starts <prefix> [per kind=150]   -> <prefix>.jsonl (starts) and <prefix>.jobs.json
  ../.venv/bin/python3 deep_endgames.py report <prefix> <dir B> <dir C>"""
import json, os, sys, glob, random, collections
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(HERE, 'results', 'value')
def kind(st):
    alive = [[p for p in sd['pokemon'] if not p.get('fainted') and p.get('hp', 1) > 0] for sd in st['sides']]
    if any(len(a) > 2 for a in alive) or any(not p.get('isActive', False) for a in alive for p in a): return None
    if not alive[0] or not alive[1]: return None
    return f'{len(alive[0])}v{len(alive[1])}'
def starts(prefix, per=150):
    by = collections.defaultdict(list)
    for part in ('hold', 'fit'):
        for l in open(os.path.join(R, f'real_{part}.pos.jsonl')):
            r = json.loads(l); k = kind(r['state'])
            if k: by[k].append(r)
    rnd = random.Random(31); out = []
    for k in sorted(by):
        rs = by[k][:]; rnd.shuffle(rs)
        for r in rs[:per]: out.append({'job': len(out), 'g': 0, 'rng': float(rnd.randrange(1, 2 ** 31)), 'state': r['state'], 'meta': {'kind': k, 'name': r['name']}})
    with open(prefix + '.jsonl', 'w') as f:
        for s in out: f.write(json.dumps(s) + '\n')
    json.dump([s['job'] for s in out], open(prefix + '.jobs.json', 'w'))
    print(len(out), 'starts:', {k: min(per, len(v)) for k, v in sorted(by.items())}, 'of', {k: len(v) for k, v in sorted(by.items())})
def load(d):
    out = {}
    for f in glob.glob(os.path.join(d, '*.json')):
        j = json.load(open(f)); out[j['job']] = j
    return out
def report(prefix, db, dc):
    B, C = load(db), load(dc); gains = collections.defaultdict(list); turns = collections.defaultdict(list); ms = [0, 0]
    for k in sorted(set(B) & set(C)):
        vb, vc = B[k]['v'], C[k]['v']
        if vb is None or vc is None: continue
        g = (vb - vc) / 2; gains[B[k]['kind']].append(g); gains['all'].append(g)
        turns['all'].append((B[k]['rows'][0]['turns'], C[k]['rows'][0]['turns'])); ms[0] += B[k]['rows'][0]['ms']; ms[1] += C[k]['rows'][0]['ms']
        turns['deep'].append(B[k]['rows'][0].get('h2', 0) + C[k]['rows'][0].get('h2', 0))
    def line(name, d):
        n = len(d); mu = sum(d) / n; se = (sum((x - mu) ** 2 for x in d) / max(n - 1, 1)) ** 0.5 / n ** 0.5
        print(f"  {name:4s} {n:4d} starts  the deep side's gain {100 * mu:+5.1f} ± {100 * se:3.1f} points  (results differ in {sum(1 for x in d if abs(x) > 1e-9)})")
    n = len(gains['all'])
    if not n: print('nothing to compare yet'); return
    print(f"{n} endgames played both ways; {ms[0] / n / 1000:.1f} / {ms[1] / n / 1000:.1f} s a game; deep rolls a game {sum(turns['deep']) / (2 * n):.0f} (games with none: {sum(1 for x in turns['deep'] if x == 0)} of {n} pairs)")
    for k in sorted(gains, key=lambda x: (x != 'all', x)): line(k, gains[k])
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'starts': starts(a[1], int(a[2]) if len(a) > 2 else 150)
    elif a[0] == 'report': report(a[1], a[2], a[3])
