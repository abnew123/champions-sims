"""Turn-one lines for each pick: the lead with its real back row against the archetype's six most common opposing leads, every joint
action in Showdown's engine (pssim/t1sim.js), solved for the mix to click (pssim/tr_final.py).

  jobs   one job per (archetype, opposing lead pair) for the pick's lead + back, and the subset whose opposing lead has an Indeedee-F
         (its item is mixed at replay rates: the base run holds Rocky Helmet, two variant runs hold Colbur Berry and Psychic Seed)
  run    12 RNG samples per cell, base + the two item variants; then each job's mean Speeds (for the Trick Room credit)
  solve  -> t1.json: per (archetype, lead, opposing pair) the simplified mix rounded to 5%, with its two win numbers
         (against ladder click rates / against a player who reads the mix)

sheet.json "t1" options: reader_w (weight on the reader number, default 0.75), tr_credit ("slower-four": Trick Room up after turn one
counts for whichever side brought the slower four, the right model for a Trick Room team; "fitted": for whoever set it, as fitted on
replays), tw_under_tr ("zero": a Tailwind set the same turn as Trick Room scores nothing), trmult_file (per-archetype multipliers on
the Trick Room credit), exclude_moves (my turn-one actions never to click, as ": <text>" fragments)."""
import os, re, shutil, hashlib
from common import *
import procs

ITEM_VARIANTS = ('colburberry', 'psychicseed')                   # tr_final.py's ITEMW: Rocky Helmet 47 / Colbur 31 / Psychic Seed 20

def t1cfg(sheet): return {'reader_w': 0.75, 'tr_credit': 'fitted', **sheet.cfg.get('t1', {})}

def make_jobs(sheet, picks):
    """-> (jobs, the jobs that need the opposing Indeedee-F item variants)"""
    opp = opp_model(); jobs = []
    for a in ARCHS:
        if a not in picks: continue
        for k, pr in enumerate(opp[a]['pairs']):
            jobs.append({'arch': a, 'k': k, 'lead': sheet.lead(picks[a]['lead']), 'back': sheet.back(picks[a]['back']), 'pair': pr['pair']})
    return jobs, [j for j in jobs if 'Indeedee-F' in j['pair'].split(' + ')]

def redo(sheet, species):
    """move aside the turn-one results of every job with one of `species` in either lead (ours, or the opposing pair), so the next
    `t1 run` plays them again: for a fix to the turn-one simulator that only touches some Pokemon (e.g. the three Mega abilities,
    2026-10-11)"""
    d = sheet.w('t1'); base = lambda n: n.split('-Mega')[0]; want = {base(x) for x in species}; moved = 0
    k = 1
    while os.path.exists(os.path.join(d, f'archive_{k}')): k += 1
    arch = os.path.join(d, f'archive_{k}')
    for name, res in (('jobs.json', 'res'), ('jobs_items.json', 'res_colburberry'), ('jobs_items.json', 'res_psychicseed')):
        jp, rd = os.path.join(d, name), os.path.join(d, res)
        if not (os.path.exists(jp) and os.path.isdir(rd)): continue
        for i, j in enumerate(rj(jp)):
            names = {base(x) for x in j['lead']} | {base(x) for x in j['pair'].split(' + ')}
            f = os.path.join(rd, f'{i}.json')
            if names & want and os.path.exists(f):
                os.makedirs(os.path.join(arch, res), exist_ok=True); shutil.move(f, os.path.join(arch, res, f'{i}.json')); moved += 1
    print(f"{moved} turn-one results with {', '.join(sorted(want))} in a lead moved to {os.path.relpath(arch, sheet.dir)}/" if moved else "no turn-one result has them in a lead")
    return moved

def write_jobs(sheet, picks):
    """Write work/t1/jobs.json. Results are named by job number, so a result is kept only when the job with that number is the same
    job as before (same archetype, opposing lead, lead and back row) and the six and the scoring options are unchanged; every other
    result is moved to work/t1/archive_<n>/, so changed picks are re-run and unchanged ones are not."""
    jobs, items = make_jobs(sheet, picks); d = sheet.w('t1'); os.makedirs(d, exist_ok=True)
    h = lambda o: hashlib.sha1(json.dumps(o, sort_keys=True).encode()).hexdigest()[:10]
    st = {'team': h(sheet.team), 'env': h(sim_env(sheet) | {'MYTEAM': ''}), 'opponents': OPPONENTS['kind']}
    old = rj(os.path.join(d, 'stamp.json')) if os.path.exists(os.path.join(d, 'stamp.json')) else {}
    same_six = {k: old.get(k) for k in st} == st
    moved = 0; arch = None
    for name, res, new_jobs in (('jobs.json', 'res', jobs), ('jobs_items.json', 'res_colburberry', items), ('jobs_items.json', 'res_psychicseed', items)):
        prev = rj(os.path.join(d, name)) if os.path.exists(os.path.join(d, name)) else []
        rd = os.path.join(d, res)
        if not os.path.isdir(rd): continue
        for f in os.listdir(rd):
            m = re.match(r'^(\d+)\.json$', f)
            if m and same_six and int(m.group(1)) < len(prev) and int(m.group(1)) < len(new_jobs) and prev[int(m.group(1))] == new_jobs[int(m.group(1))]: continue
            if arch is None:
                k = 1
                while os.path.exists(os.path.join(d, f'archive_{k}')): k += 1
                arch = os.path.join(d, f'archive_{k}')
            os.makedirs(os.path.join(arch, res), exist_ok=True); shutil.move(os.path.join(rd, f), os.path.join(arch, res, f)); moved += 1
    if arch:
        for f in ('jobs.json', 'jobs_items.json', 'stamp.json'):
            if os.path.exists(os.path.join(d, f)): shutil.copy(os.path.join(d, f), os.path.join(arch, f))
        print(f"{moved} turn-one results no longer match their job (changed picks, or a changed six): moved to {os.path.relpath(arch, sheet.dir)}/")
    wj(jobs, os.path.join(d, 'jobs.json')); wj(items, os.path.join(d, 'jobs_items.json')); wj(st, os.path.join(d, 'stamp.json'))
    return jobs, items

def sim_env(sheet):
    c = t1cfg(sheet); env = {'MYTEAM': sheet.team_path}
    if c.get('tw_under_tr'): env['TW_UNDER_TR'] = c['tw_under_tr']
    if c.get('mega_choice'): env['MEGA_CHOICE'] = '1'                 # a stone holder may also attack without Mega Evolving (as champ-battle-v24)
    return env

def run_all(sheet, samples=12, workers=None, force=False):
    workers = threads_arg(workers, force); log = RunLog(sheet, 't1'); d = sheet.w('t1'); env = sim_env(sheet)
    for jobs, out, extra in [('jobs.json', 'res', {})] + [('jobs_items.json', f'res_{it}', {'ITEM_OVERRIDE': f'Indeedee-F={it}'}) for it in ITEM_VARIANTS]:
        os.makedirs(os.path.join(d, out), exist_ok=True)
        if not rj(os.path.join(d, jobs)): continue
        log.start(os.path.join(d, jobs), os.path.join(d, out), f"{samples} samples per cell, {workers} workers")
        run(['nice', '-n', '10', procs.exe(sheet, 'bash', name='sh'), './run_jobs.sh', os.path.join(d, jobs), os.path.join(d, out), str(samples), str(workers)],
            env={**env, **extra, 'NODE_BIN': procs.exe(sheet, 'node')}, cwd=PSSIM)
        log.done(os.path.join(d, out))
    speeds(sheet)

def speeds(sheet, jobs=None, out=None):
    run([procs.exe(sheet, 'node'), 'tr_speeds.js', jobs or sheet.w('t1', 'jobs.json'), out or sheet.w('t1', 'speeds.json')], env={'MYTEAM': sheet.team_path}, cwd=PSSIM,
        stdout=subprocess.DEVNULL)

def solve(sheet, res=None, speeds_path=None, out=None):
    c = t1cfg(sheet); res = res or sheet.w('t1', 'res'); out = out or sheet.p('t1.json')
    env = {'READER_W': str(c['reader_w']), 'TR_SPEEDS': speeds_path or sheet.w('t1', 'speeds.json'), 'TR_CREDIT': c['tr_credit'],
           'EXCLUDE_MOVES': ','.join(c.get('exclude_moves', []))}
    if c.get('trmult_file'):
        tm = rj(os.path.normpath(sheet.p(c['trmult_file'])))
        if CARDS:                                                 # keyed by archetype: each card takes its tab's archetype's multiplier
            arch_of = {a['key']: a['model'] for a in rj(os.path.join(KIT, 'archetypes.json'))['archetypes']}
            tm = {m: tm.get(arch_of[c_['tab']], 1.0) for m, c_ in CARDS.items()}
            wj(tm, sheet.w('t1', 'trmult_cards.json')); env['TRMULT_FILE'] = sheet.w('t1', 'trmult_cards.json')
        else: env['TRMULT_FILE'] = os.path.normpath(sheet.p(c['trmult_file']))
    for it in ITEM_VARIANTS: os.makedirs(f'{res}_{it}', exist_ok=True)
    os.makedirs(sheet.w('t1'), exist_ok=True)
    with open(sheet.w('t1', 'solve.log'), 'w') as lg:
        py, penv = procs.python(sheet, venv=True)
        run([py, 'tr_final.py', res, out], env={**env, **penv}, cwd=PSSIM, stdout=lg)
    return rj(out)
