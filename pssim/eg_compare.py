"""Compare two 2v2 result folders game by game (e.g. the JS planner vs the native one on the same jobs).
usage: python3 eg_compare.py results/eg_auto results/eg_auto_native"""
import json, glob, os, sys
A, B = sys.argv[1], sys.argv[2]
same = diff = only = 0; ex = []
for f in sorted(glob.glob(A + '/*.json'), key=lambda x: int(os.path.basename(x)[:-5])):
    g = os.path.join(B, os.path.basename(f))
    if not os.path.exists(g): only += 1; continue
    a, b = json.load(open(f)), json.load(open(g))
    if a.get('fails') or b.get('fails'): only += 1; continue
    if [round(float(x), 3) for x in a['vs']] == [round(float(x), 3) for x in b['vs']] and a['turns'] == b['turns']: same += 1   # JS rounds values to 3 decimals
    else: diff += 1; ex.append((os.path.basename(f), a['vs'], b['vs'], a['turns'], b['turns']))
print(f'{same} jobs identical, {diff} differ, {only} skipped (missing or with failed games)')
for e in ex[:10]: print('  ', *e)
