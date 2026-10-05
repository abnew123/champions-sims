#!/usr/bin/env python3
"""Proof that the kit reproduces the Trick Room Six sheet as published in Version 16 from the raw sim results that built it, step by
step, against the files the old hand-run pipeline left in pssim/ and the published page (kept in the fixture folder). No sims are run; the turn-one solve takes a minute or two.

  python3 sheetkit/selftest_tr.py            every check
  python3 sheetkit/selftest_tr.py --link     also (re)create sheets/trick-room-six/work/{matrix,confirm} as links to the old results,
                                             so the kit's matrix report and confirm decide run on the Trick Room Six

The inputs are frozen in sheetkit/fixtures/tr-v16/ (the six, config, text and charts as published), so the test keeps its meaning
while sheets/trick-room-six/ moves on.

Run it after any change to the kit: a failure means the change altered what an existing sheet would say."""
import sys, os, glob, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import picks as P, t1 as T1, page as PG

R = os.path.join(PSSIM, 'results')
sheet = Sheet(os.path.join(KIT, 'fixtures', 'tr-v16')); ok = True      # the six, text and charts as published in Version 16 (frozen)
def check(name, cond, detail=''):
    global ok; ok &= bool(cond); print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}", flush=True)
def jkey(j): return (j['arch'], j['k'], tuple(j['lead']), tuple(j['back']))

def link(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.islink(dst): os.remove(dst)
    os.symlink(os.path.realpath(src), dst)

def t1_results(jobs, dest, suffix=''):
    """link the old turn-one result of every kit job into dest/<job index>.json (old runs: results/v15 and results/v14_itr)"""
    old = {}
    for d in ('v15', 'v14_itr'):
        for f in glob.glob(f'{R}/{d}{suffix}/*.json'):
            r = rj(f); old[(r['arch'], '+'.join(r['myLead']), r['pair'])] = f
    os.makedirs(dest, exist_ok=True); n = 0
    for i, j in enumerate(jobs):
        f = old.get((j['arch'], '+'.join(j['lead']), j['pair']))
        if f: link(f, f'{dest}/{i}.json'); n += 1
    return n

# 1. bring-matrix jobs
same = all(P.matrix_jobs(sheet, a) == rj(f'{PSSIM}/bringmx_{i}.json') for i, a in enumerate(ARCHS))
check('matrix jobs: the 5,400 jobs equal pssim/bringmx_0..9.json, in order', same)

# 2. confirmation jobs (the old run was split in two; part a's job file survives)
old = rj(f'{PSSIM}/bringcf_jobs_a.json'); archs = list(dict.fromkeys(j['arch'] for j in old))
new = P.confirm_jobs(sheet, 5, pattern=f'{R}/bringmx_*/*.json', picks_path=f'{PSSIM}/battle_picks_final.json', only=[ARCHS.index(a) for a in archs], out=lambda s: None)
check(f'confirm jobs: same fours as pssim/bringcf_jobs_a.json ({len(old)} jobs, {len(archs)} archetypes)', sorted(map(jkey, new)) == sorted(map(jkey, old)))

# 3. the decision
final = P.decide(sheet, pattern=f'{R}/bringcf_*/*.json', matrix_pattern=f'{R}/bringmx_*/*.json', picks_path=f'{PSSIM}/battle_picks_final.json', out=lambda s: None)
legacy = rj(f'{PSSIM}/bringcf_picks.json')
check('confirm decide: picks equal pssim/bringcf_picks.json (fours, win shares, game counts)', final == legacy,
      f"ladder-weighted {100 * P.weighted(final):.1f}%")

# 4. turn-one jobs
jobs, items = T1.make_jobs(sheet, final)
oldj = rj(f'{PSSIM}/jobs_v15.json') + rj(f'{PSSIM}/jobs_v14_itr.json'); oldi = rj(f'{PSSIM}/jobs_v15_items.json') + rj(f'{PSSIM}/jobs_v14_itr_items.json')
k5 = lambda j: jkey(j) + (j['pair'],)
check(f'turn-one jobs: the {len(jobs)} jobs (+{len(items)} item-variant jobs) equal jobs_v15 + jobs_v14_itr',
      sorted(map(k5, jobs)) == sorted(map(k5, oldj)) and sorted(map(k5, items)) == sorted(map(k5, oldi)))

tmp = tempfile.mkdtemp(prefix='kit_selftest_')
try:
    # 5. speeds for the Trick Room credit
    wj(jobs, f'{tmp}/jobs.json'); T1.speeds(sheet, f'{tmp}/jobs.json', f'{tmp}/speeds.json')
    sp, osp = rj(f'{tmp}/speeds.json'), rj(f'{PSSIM}/tr_speeds_v15.json')
    check(f'turn-one speeds: {len(sp)} entries equal pssim/tr_speeds_v15.json', all(osp.get(k) == v for k, v in sp.items()))

    # 6. the solve, from the raw turn-one results
    n = t1_results(jobs, f'{tmp}/res'); ni = [t1_results(items, f'{tmp}/res_{it}', f'_{it}') for it in T1.ITEM_VARIANTS]
    check('turn-one results: every job has its old result', n == len(jobs) and all(x == len(items) for x in ni), f'{n} + {ni}')
    t1 = T1.solve(sheet, res=f'{tmp}/res', speeds_path=f'{tmp}/speeds.json', out=f'{tmp}/t1.json')
    old = rj(f'{PSSIM}/tr_final_v15plus.json')['plans']
    check(f"turn-one solve: all {len(t1['plans'])} plans (mix, both win numbers) equal pssim/tr_final_v15plus.json",
          all(old.get(k) == v for k, v in t1['plans'].items()) and len(t1['plans']) == len(jobs))

    # 7. the page
    s, L = PG.render(sheet, PG.leads_data(sheet, final, t1, rj(sheet.p('notes.json')))); open(f'{tmp}/sheet.html', 'w').write(s)
    d, notes = PG.compare(f'{tmp}/sheet.html', sheet.p('published.html'))
    check('page: equals the published Version 16 page (six data blocks by value; markup, styles and scripts byte for byte)', not d, '; '.join(d + notes))
    bad = PG.check_leads(sheet, L); check('page: every turn-one switch goes to the card\'s back row; lines sum to 100%', not bad, '; '.join(bad))

    # 8. Coverage and Matchups from the generic one-on-one grid (the first run builds the fixture's grid cells: about a CPU-minute)
    import charts as CH
    CH.build.__globals__['print'] = lambda *a, **k: None
    CH.build(sheet, 1, f'{tmp}/charts.json'); gen, old = rj(f'{tmp}/charts.json'), rj(sheet.p('charts.json'))
    cells = [(r[0], gen['attackers'][j], x, y) for r, q in zip(gen['matchups'], old['matchups']) for m in (2, 3) for j, (x, y) in enumerate(zip(r[m], q[m]))]
    diff = [c for c in cells if c[2] != c[3]]; verdicts = [c for c in diff if (c[2]['v'], c[2].get('p')) != (c[3]['v'], c[3].get('p'))]
    check('charts: Coverage equals the published table (35 threats, 5 attackers)', gen['coverage'] == old['coverage'] and gen['attackers'] == old['attackers'])
    check(f'charts: Matchups equal the published grid in {len(cells) - len(diff)} of {len(cells)} cells; the rest are Incineroar cells (White Herb is now modelled)',
          [r[:2] for r in gen['matchups']] == [r[:2] for r in old['matchups']] and {c[1] for c in diff} <= {'Incineroar'} and len(diff) == 10 and len(verdicts) == 4,
          f'{len(diff)} differ, {len(verdicts)} of them in the verdict')

    if '--link' in sys.argv:                                     # the live folder's matrix and confirmation results (the basis of its picks)
        live = Sheet('trick-room-six')
        for i in range(len(ARCHS)):
            for suf in ('', 'r'):
                if os.path.isdir(f'{R}/bringmx_{i}{suf}'): link(f'{R}/bringmx_{i}{suf}', live.w('matrix', f'res_{i}{suf}'))
            wj(P.matrix_jobs(live, ARCHS[i]), live.w('matrix', f'jobs_{i}.json'))
        for x in ('a', 'b'): link(f'{R}/bringcf_{x}', live.w('confirm', f'res_{x}'))
        print('linked: sheets/trick-room-six/work/{matrix,confirm} now point at the old results')
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print('\nALL PASS' if ok else '\nFAILED')
sys.exit(0 if ok else 1)
