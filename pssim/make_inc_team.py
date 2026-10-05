# Incineroar-for-Hatterene team, assembled from existing runs (no new sims):
#   - the current team's refined leads without Hatterene (results/v7*); six of them had Hatterene in the back row. Their back row
#     becomes Farigiraf (the other setter), their Trick Room credit is recomputed with Farigiraf's 72 Speed in place of Hatterene's 44,
#     and turn-one switches into Hatterene are dropped at solve time (EXCLUDE_MOVES='switch -> Hatterene');
#   - Incineroar's refined leads (results/r_incin*).
# Writes results/inc, results/inc_colburberry, results/inc_psychicseed and tr_speeds_inc.json.
import json, glob, os, shutil
S = json.load(open('tr_speeds.json')); S2 = dict(S); nfix = 0
for k, v in S.items():
    arch, lead, pair = k.split('|')
    if 'Hatterene' in lead or 44 not in v['mine']: continue
    mine = [72 if x == 44 else x for x in v['mine']]; S2[k] = dict(v, mine=mine, m=sum(mine) / 4); nfix += 1
json.dump(S2, open('tr_speeds_inc.json', 'w'))
def newback(lead, back):
    if 'Hatterene' not in back: return back
    b = ['Farigiraf' if x == 'Hatterene' else x for x in back]
    return ['Indeedee-F', 'Farigiraf'] if set(b) == {'Indeedee-F', 'Farigiraf'} else b
for suf in ('', '_colburberry', '_psychicseed'):
    out = f'results/inc{suf}'; shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    nv = nc = ni = 0
    for fn in sorted(glob.glob(f'results/v7{suf}/*.json')):
        r = json.load(open(fn))
        if 'Hatterene' in r['myLead']: continue
        dst = f"{out}/v7_{os.path.basename(fn)}"
        if 'Hatterene' in r['myBack']:
            r['myBack'] = newback(r['myLead'], r['myBack']); json.dump(r, open(dst, 'w')); nc += 1
        else: os.symlink(os.path.abspath(fn), dst)
        nv += 1
    for fn in sorted(glob.glob(f'results/r_incin{suf}/*.json')):
        os.symlink(os.path.abspath(fn), f"{out}/inc_{os.path.basename(fn)}"); ni += 1
    print(out, 'current-team leads', nv, '(back row changed', nc, ') + Incineroar', ni)
print('tr speed entries recomputed:', nfix)
