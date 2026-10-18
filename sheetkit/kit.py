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
  python3 sheetkit/kit.py <team> t1 redo --only Garchomp,Golisopod   results with those Pokemon in a lead set aside for the next run
  python3 sheetkit/kit.py <team> optimal run [--threads N] [--only screen|matrix|more] | report  both sides pick their four -> optimal.json
                                                           (OPTIMAL_SIXES=pool: against real sixes -> optimal_pool.json)
  python3 sheetkit/kit.py <team> guide run [--games 64] [--g0 7000] [--threads N] | report   game plans and team-preview tells -> guide.json
  python3 sheetkit/kit.py <team> page [--compare other.html]   -> sheets/<team>/sheet.html
  python3 sheetkit/kit.py <team> mix [write|check] [--threads N]   mixed brings per card -> picks.json "mix" (check: play the mixes' answers first)
  python3 sheetkit/kit.py <team> flagged [--write]         battle results with a game flagged unsupported; --write moves them out to replay
                                                           (--moves healingwish,memento: also results where either four carries one)
                                                           (--stones 2: also results where either four holds two Mega Stones)
                                                           (--moves-only: only those, not the unsupported-mechanic results)

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
    if sheet.cfg.get('setup'): print(f"  this sheet plays on: {sheet.cfg['setup']} (sheet.json 'setup')")
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

def stone_holders(sheet, d, r, cache={}):
    """(ours, theirs): how many Pokemon in each four of result r (in folder d) hold their Mega Stone"""
    import page as PG
    D = cache.get('dex') or cache.setdefault('dex', PG.dex()); idf = PG.idf
    stone = lambda item, sp: bool((D['items'].get(idf(item), {}).get('megaStone') or {}))
    ours = sum(stone(sheet.team.get(n, {}).get('item', ''), n) for n in r.get('lead', []) + r.get('back', []))
    if os.path.exists(d + '.json'):
        if d not in cache: cache[d] = rj(d + '.json')
        theirs = sum(stone(x.get('item', ''), x.get('species')) for x in cache[d][r['job']]['theirs'])
    else:
        sets = opp_model().get(r.get('arch'), {}).get('sets', {})
        theirs = sum(stone(sets.get(sp, '').split('|')[0], sp) for sp in r.get('theirs', []))
    return ours, theirs

def has_moves(sheet, d, r, moves, cache={}):
    """does result r (in folder d) have a Pokemon with one of `moves` (ids) on either side of its four?"""
    idm = lambda m: m.lower().replace(' ', '').replace('-', '')
    mine = any(idm(m) in moves for n in r.get('lead', []) + r.get('back', []) for m in sheet.team.get(n, {}).get('moves', []))
    if mine: return True
    if 'six' in r and r.get('arch'):                              # an optimal result: their sets are the real six's (by species, so a
        if 'sixes' not in cache: cache['sixes'] = rj(sheet.w('optimal', 'sixes.json'))      # set-aside result with an old job number works too)
        six = {x['species']: x for x in cache['sixes'][r['arch']][r['six']]['six']}
        return any(idm(m) in moves for sp in r.get('theirs', []) for m in six.get(sp, {}).get('moves', []))
    if os.path.exists(d + '.json'):                               # an optimal queue: the opposing sets are in the job
        if d not in cache: cache[d] = rj(d + '.json')
        return any(idm(m) in moves for s in cache[d][r['job']]['theirs'] for m in s.get('moves', []))
    sets = opp_model().get(r.get('arch'), {}).get('sets', {})        # the card model's set for each of their four
    return any(any(m in sets.get(sp, '').split('|')[-1].split(' (')[0].split('/') for m in moves) for sp in r.get('theirs', []))

def flagged(sheet, move=False, moves=(), stones=0, only_moves=False, tag=None):
    """Battle results with a game the simulator flagged unsupported (a mechanic it had not ported), per result folder; with --write
    they move to <folder>.flagged/ (.flagged_<tag> with --tag), so the next run of that step plays just those jobs again (on a setup
    that ports the mechanic and shares the folders, e.g. SHEET_SETUP=v22-dp2-race-eg9-full). The folder's set-aside results (.stale)
    are checked too and matches moved out as stale_<n>.json: otherwise a run would reuse them by content, or matrix_cells read them"""
    import collections, glob
    dirs = sorted(d for d in glob.glob(sheet.w('*', 'res*')) + glob.glob(sheet.w('optimal*', 'screen_*')) + glob.glob(sheet.w('optimal*', 'matrix*'))
                  if os.path.isdir(d) and '.' not in os.path.basename(d) and os.path.basename(os.path.dirname(d)) != 't1')
    mech = collections.Counter(); total = 0
    for d in dirs:
        bad = []
        for f in glob.glob(os.path.join(d, '*.json')) + glob.glob(os.path.join(d + '.stale', '*.json')):
            try: rows = json.load(open(f)).get('rows', [])
            except Exception: continue
            u = [] if only_moves else [m for g in rows for m in (g.get('unsupported') or [])]      # --moves-only: just the moves / stones
            if not u and moves and has_moves(sheet, d, json.load(open(f)), moves): u = ['move ' + '/'.join(sorted(moves))]
            if not u and stones and max(stone_holders(sheet, d, json.load(open(f)))) >= stones: u = [f'{stones}+ stone holders in a four']
            if u: bad.append(f); mech.update(set(u))
        if not bad: continue
        ns = sum(f.startswith(d + '.stale' + os.sep) for f in bad)
        total += len(bad); print(f"{os.path.relpath(d, sheet.w())}: {len(bad)} results with a flagged game" + (f" ({ns} of them set aside in .stale)" if ns else ''))
        if move:
            out = d + ('.flagged_' + tag if tag else '.flagged'); os.makedirs(out, exist_ok=True)
            for f in bad: os.replace(f, os.path.join(out, ('stale_' if f.startswith(d + '.stale' + os.sep) else '') + os.path.basename(f)))
    print(f"{total} results" + (f"; mechanics (results they appear in): {', '.join(f'{m} {n}' for m, n in mech.most_common(12))}" if total else ''))
    if total: print('moved to <folder>.flagged/: run the same steps again (e.g. SHEET_SETUP=... sheetkit/cloud/all.sh, then more.sh) to replay them'
                    if move else '(nothing moved: add --write to move them out for a replay)')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('team'); ap.add_argument('step'); ap.add_argument('sub', nargs='?')
    ap.add_argument('--games', type=int); ap.add_argument('--g0', type=int); ap.add_argument('--threads', '--workers', type=int, dest='threads')
    ap.add_argument('--only'); ap.add_argument('--setup'); ap.add_argument('--top', type=int, default=5); ap.add_argument('--samples', type=int, default=12)
    ap.add_argument('--write', action='store_true'); ap.add_argument('--force', action='store_true'); ap.add_argument('--compare'); ap.add_argument('--out'); ap.add_argument('--moves'); ap.add_argument('--stones', type=int)
    ap.add_argument('--moves-only', action='store_true'); ap.add_argument('--tag')
    a = ap.parse_args()
    if a.step == 'init': return init(a.team)
    sheet = Sheet(a.team); step = (a.step, a.sub); G = sheet.cfg.get('games', {})      # sheet.json "games": default game counts per step
    import procs; procs.own(sheet)                               # show as <prefix>-py in top
    if a.step == 'status': status(sheet)
    elif a.step == 'smoke': smoke(sheet)
    elif a.step == 'flagged': flagged(sheet, a.write, tuple(x.strip() for x in (a.moves or '').split(',') if x.strip()), a.stones or 0, a.moves_only, a.tag)
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
    elif step == ('t1', 'redo'): T1.redo(sheet, [x.strip() for x in (a.only or '').split(',') if x.strip()])
    elif step == ('t1', 'run'): T1.run_all(sheet, a.samples, a.threads, a.force)
    elif step == ('t1', 'solve'): d = T1.solve(sheet); print(f"t1.json: {len(d['plans'])} plans")
    elif step == ('optimal', 'run'):
        import optimal; optimal.run(sheet, a.threads, a.force, a.only or 'all')
    elif a.step == 'mix':                                          # mixed brings (needs scipy: the venv python)
        sys.exit(subprocess.run([VENV_PY, os.path.join(KIT, 'mix.py'), a.team, a.sub or 'write'] + (['--threads', str(a.threads)] if a.threads else [])
                                + (['--force'] if a.force else [])).returncode)
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
