#!/usr/bin/env python3
"""Sheet kit: one command per step of a team's ladder sheet. Run from anywhere:

  python3 sheetkit/kit.py <team> init                      start sheets/<team>/ from sheetkit/starter/ (then put the six in team.json)
  python3 sheetkit/kit.py <team> status                    what exists in sheets/<team>/ and what the next step is
  python3 sheetkit/kit.py <team> smoke                     2 whole games, 1 turn-one job and a page in work/smoke/: about a minute, 1 core
  python3 sheetkit/kit.py <team> grid [--workers N]        one-on-one cells for the six (the full-battle planner needs them)
  python3 sheetkit/kit.py <team> charts [--workers N]      Coverage and Matchups for the page, from the grid -> charts.json
  python3 sheetkit/kit.py <team> speed                     the Speed table: the six among the common opposing spreads -> speed.json
  python3 sheetkit/kit.py <team> matrix jobs               all 90 fours x each archetype's opposing leads
  python3 sheetkit/kit.py <team> matrix run [--games 16] [--g0 600] [--threads N] [--only 0,3] [--setup NAME]
  python3 sheetkit/kit.py <team> matrix report             best fours, worth of bringing each Pokemon, species tells
  python3 sheetkit/kit.py <team> confirm jobs [--top 5] [--only 0,3]
  python3 sheetkit/kit.py <team> confirm run [--games 48] [--g0 1000] [--threads N] [--setup NAME]
  python3 sheetkit/kit.py <team> confirm decide [--write]  paired on fresh games; --write updates picks.json
  python3 sheetkit/kit.py <team> t1 jobs | run [--samples 12] [--workers N] | solve
  python3 sheetkit/kit.py <team> optimal run [--threads N] [--only screen|matrix] | report   both sides pick their four -> optimal.json
                                                           (OPTIMAL_SIXES=pool: against real sixes -> optimal_pool.json)
  python3 sheetkit/kit.py <team> guide run [--games 64] [--g0 7000] [--threads N] | report   game plans and team-preview tells -> guide.json
  python3 sheetkit/kit.py <team> page [--compare other.html]   -> sheets/<team>/sheet.html

Long runs: start them in the background (nohup ... &); every run resumes where it stopped and shows on the progress page (port 8766).
On the Mac the default is 3 workers and more than 10 is refused (--force); ask before any multi-core run. See sheetkit/README.md."""
import argparse, sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import picks as P, t1 as T1, page as PG

# a built page opened straight from disk needs the charset and viewport lines a published Artifact gets
PREVIEW_HEAD = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n'

def ints(s): return [int(x) for x in s.split(',')] if s else None

def status(sheet):
    ex = lambda *p: os.path.exists(sheet.p(*p)); n = lambda *p: len(glob_json(sheet.w(*p)))
    S = rj(os.path.join(KIT, 'sim.json'))
    print(f"{sheet.cfg.get('name', sheet.slug)}  ({sheet.dir})")
    print(f"  six: {', '.join(sheet.names)}")
    print(f"  current sim setup: {S['current']}  ({S['setups'][S['current']]['status']})")
    g = os.path.normpath(sheet.p(sheet.cfg.get('grid_dir', 'work/grid')))
    print(f"  grid      {'ok' if os.path.exists(os.path.join(g, 'gx_cells_tr_inc.json')) else 'MISSING (run: grid)'}  {os.path.relpath(g, ROOT)}")
    mj = len(rj(sheet.w('matrix', 'jobs.json'))) if os.path.exists(sheet.w('matrix', 'jobs.json')) else 0; mr = n('matrix', 'res')
    ran = lambda d: (lambda r: f"  ({r['setup']}, {r['games']} games from index {r['g0']})")(rj(d + '.run.json')) if os.path.exists(d + '.run.json') else ''
    print(f"  matrix    {mr} of {mj} jobs done{ran(sheet.w('matrix', 'res'))}" if mj else "  matrix    no jobs yet (run: matrix jobs)")
    cj_ = len(rj(sheet.w('confirm', 'jobs.json'))) if os.path.exists(sheet.w('confirm', 'jobs.json')) else 0
    print(f"  confirm   {n('confirm', 'res')} of {cj_} jobs done{ran(sheet.w('confirm', 'res'))}" if cj_ else "  confirm   no jobs yet")
    if ex('picks.json'):
        d = rj(sheet.p('picks.json')); print(f"  picks     {len(d['picks'])} archetypes, ladder-weighted {100 * P.weighted(d['picks']):.1f}%  ({d.get('setup', '?')}, {d.get('made', '?')})")
    else: print("  picks     none yet (run: confirm decide --write)")
    tj = len(rj(sheet.w('t1', 'jobs.json'))) if os.path.exists(sheet.w('t1', 'jobs.json')) else 0
    print(f"  t1        {n('t1', 'res')} of {tj} jobs done; t1.json {'ok' if ex('t1.json') else 'missing'}" if tj else "  t1        no jobs yet")
    ch = rj(sheet.p('charts.json')) if ex('charts.json') else None; sp = rj(sheet.p('speed.json')) if ex('speed.json') else None
    print(f"  charts    {len(ch['matchups'])} threats x {len(ch['attackers'])} attackers" if ch else "  charts    none (run: charts)")
    print(f"  speed     {len(sp['rows'])} rows{' (hand-written)' if sp.get('hand') else ''}" if sp else "  speed     none (run: speed)")
    print(f"  page      {'sheet.html built' if ex('sheet.html') else 'not built'}; published: {sheet.cfg.get('published', 'never')}  {sheet.cfg.get('artifact', '')}")

def init(slug):
    d = slug if os.sep in slug else os.path.join(ROOT, 'sheets', slug)
    if os.path.exists(os.path.join(d, 'sheet.json')): sys.exit(f"{d} already has a sheet.json")
    os.makedirs(os.path.join(d, 'work'), exist_ok=True)
    for f in os.listdir(os.path.join(KIT, 'starter')):
        if not os.path.exists(os.path.join(d, f)): shutil.copy(os.path.join(KIT, 'starter', f), os.path.join(d, f))
    print(f"{d} created. Next: write team.json (the six, MYTEAM format, see sheetkit/README.md), edit sheet.json and text.json, then: grid, smoke")

def smoke(sheet):
    """A dry run of every step on one core: two fours x one whole game, one turn-one job x one sample, and the page built from them.
    The numbers mean nothing; it only shows that this team's sets run through the whole toolchain. Everything stays in work/smoke/."""
    d = sheet.w('smoke'); shutil.rmtree(d, ignore_errors=True); os.makedirs(d); a = ARCHS[0]; log = RunLog(sheet, 'smoke')
    mj = P.matrix_jobs(sheet, a); jobs = [mj[0], mj[len(mj) // 2]]; wj(jobs, os.path.join(d, 'jobs.json'))
    P.battle_run(sheet, 'smoke', os.path.join(d, 'jobs.json'), os.path.join(d, 'res'), 1, 0, 1, None, log)
    V, share, names, _, _ = P.load(os.path.join(d, 'res', '*.json'))
    for t in V:
        for c, g in V[t].items(): print(f"  whole game: {P.four_name(sheet, names, c)} vs {t[1]}: {list(g.values())}")
    if not V: sys.exit('no battle result: see ' + os.path.join(d, 'res.err'))
    picks = {a: {'lead': jobs[0]['lead'], 'back': jobs[0]['back'], 'v': 0.5, 'n': 1}}
    tj, _ = T1.make_jobs(sheet, picks); wj(tj[:1], os.path.join(d, 't1_jobs.json'))
    log.start(os.path.join(d, 't1_jobs.json'), os.path.join(d, 't1res'), '1 sample per cell, 1 worker')
    import procs
    run(['nice', '-n', '10', procs.exe(sheet, 'bash', name='sh'), './run_jobs.sh', os.path.join(d, 't1_jobs.json'), os.path.join(d, 't1res'), '1', '1'],
        env={**T1.sim_env(sheet), 'NODE_BIN': procs.exe(sheet, 'node')}, cwd=PSSIM,
        stdout=subprocess.DEVNULL)
    log.done(os.path.join(d, 't1res'))
    T1.speeds(sheet, os.path.join(d, 't1_jobs.json'), os.path.join(d, 'speeds.json'))
    t1 = T1.solve(sheet, res=os.path.join(d, 't1res'), speeds_path=os.path.join(d, 'speeds.json'), out=os.path.join(d, 't1.json'))
    for k, p in t1['plans'].items(): print(f"  turn one: {k.replace('||', ' | ')}: {p['mix']}")
    s, L = PG.render(sheet, PG.leads_data(sheet, picks, t1, {})); open(os.path.join(d, 'preview.html'), 'w').write(PREVIEW_HEAD + s)
    print(f"  page: {os.path.relpath(os.path.join(d, 'preview.html'), ROOT)} ({len(s)} bytes; one Leads tab from this dry run, the other sections as they will be)\nsmoke run ok")

def glob_json(d, pat='*.json'):
    import glob
    return glob.glob(os.path.join(d, pat))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('team'); ap.add_argument('step'); ap.add_argument('sub', nargs='?')
    ap.add_argument('--games', type=int); ap.add_argument('--g0', type=int); ap.add_argument('--threads', '--workers', type=int, dest='threads')
    ap.add_argument('--only'); ap.add_argument('--setup'); ap.add_argument('--top', type=int, default=5); ap.add_argument('--samples', type=int, default=12)
    ap.add_argument('--write', action='store_true'); ap.add_argument('--force', action='store_true'); ap.add_argument('--compare'); ap.add_argument('--out')
    a = ap.parse_args()
    if a.step == 'init': return init(a.team)
    sheet = Sheet(a.team); step = (a.step, a.sub); G = sheet.cfg.get('games', {})      # sheet.json "games": default game counts per step
    import procs; procs.own(sheet)                               # show as <prefix>-py in top
    if a.step == 'status': status(sheet)
    elif a.step == 'smoke': smoke(sheet)
    elif a.step == 'grid':
        import grid; grid.build(sheet, threads_arg(a.threads, a.force))
    elif a.step == 'charts':
        import charts; charts.build(sheet, threads_arg(a.threads, a.force), a.out)
    elif a.step == 'speed':
        import speed; speed.build(sheet, a.out, a.force)
    elif step == ('matrix', 'jobs'): P.write_matrix_jobs(sheet)
    elif step == ('matrix', 'run'): P.run_matrix(sheet, a.games or G.get('matrix', 16), 600 if a.g0 is None else a.g0, a.threads, a.setup, ints(a.only), a.force)
    elif step == ('matrix', 'report'):
        lines = []; P.matrix_report(sheet, out=lambda s: (print(s), lines.append(s)))
        open(sheet.w('matrix', 'report.txt'), 'w').write('\n'.join(lines) + '\n')
    elif step == ('confirm', 'jobs'):
        jobs = P.confirm_jobs(sheet, a.top, only=ints(a.only)); wj(jobs, sheet.w('confirm', 'jobs.json')); print(f"{len(jobs)} jobs -> work/confirm/jobs.json")
    elif step == ('confirm', 'run'): P.run_confirm(sheet, a.games or G.get('confirm', 48), 1000 if a.g0 is None else a.g0, a.threads, a.setup, a.force)
    elif step == ('confirm', 'decide'):
        lines = []; final = P.decide(sheet, out=lambda s: (print(s), lines.append(s)))
        open(sheet.w('confirm', 'report.txt'), 'w').write('\n'.join(lines) + '\n')
        if a.write:
            meta = rj(sheet.w('confirm', 'res.run.json')) if os.path.exists(sheet.w('confirm', 'res.run.json')) else {}
            wj({'made': meta.get('date', datetime.date.today().isoformat()), 'setup': meta.get('setup'), 'picks': final}, sheet.p('picks.json'), indent=1)
            print('picks.json written; next: t1 jobs, t1 run, t1 solve, page')
        else: print('\n(not written: add --write to update picks.json)')
    elif step == ('t1', 'jobs'):
        jobs, items = T1.write_jobs(sheet, rj(sheet.p('picks.json'))['picks']); print(f"{len(jobs)} jobs, {len(items)} with item variants -> work/t1/")
    elif step == ('t1', 'run'): T1.run_all(sheet, a.samples, a.threads, a.force)
    elif step == ('t1', 'solve'): d = T1.solve(sheet); print(f"t1.json: {len(d['plans'])} plans")
    elif step == ('optimal', 'run'):
        import optimal; optimal.run(sheet, a.threads, a.force, a.only or 'all')
    elif step == ('optimal', 'adopt'):
        import optimal; optimal.adopt(sheet)
    elif step == ('optimal', 'report'):
        import optimal; lines = []; optimal.report(sheet, out=lambda s: (print(s), lines.append(s)))
        open(sheet.w('optimal', 'report.txt'), 'w').write('\n'.join(lines) + '\n')
    elif step == ('guide', 'run'):
        import guide; guide.run(sheet, a.games or G.get('guide', guide.GAMES), guide.G0 if a.g0 is None else a.g0, a.threads, a.setup, a.force)
    elif step == ('guide', 'report'):
        import guide; lines = []; guide.report(sheet, out=lambda s: (print(s), lines.append(s)))
        open(sheet.w('guide', 'report.txt'), 'w').write('\n'.join(lines) + '\n')
    elif a.step == 'page':
        out = a.out or sheet.p('sheet.html'); s, L = PG.render(sheet); open(out, 'w').write(s)
        os.makedirs(sheet.w(), exist_ok=True); open(sheet.w('preview.html'), 'w').write(PREVIEW_HEAD + s)
        bad = PG.check_leads(sheet, L)
        print(f"{os.path.relpath(out, ROOT)} written ({len(s)} bytes, {len(L)} tabs)" + ('' if not bad else '\nPROBLEMS:\n  ' + '\n  '.join(bad)))
        if a.compare:
            d, notes = PG.compare(out, a.compare)
            print(f"vs {a.compare}: " + ('same (data blocks by value, the rest byte for byte)' if not d else 'DIFFERENT: ' + '; '.join(d)) + ''.join('\n  note: ' + x for x in notes))
        if bad: sys.exit(1)
    else: sys.exit(__doc__)

if __name__ == '__main__': main()
