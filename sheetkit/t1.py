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
import os, shutil
from common import *

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

def sim_env(sheet):
    c = t1cfg(sheet); env = {'MYTEAM': sheet.team_path}
    if c.get('tw_under_tr'): env['TW_UNDER_TR'] = c['tw_under_tr']
    return env

def run_all(sheet, samples=12, workers=None, force=False):
    workers = threads_arg(workers, force); log = RunLog(sheet, 't1'); d = sheet.w('t1'); env = sim_env(sheet)
    for jobs, out, extra in [('jobs.json', 'res', {})] + [('jobs_items.json', f'res_{it}', {'ITEM_OVERRIDE': f'Indeedee-F={it}'}) for it in ITEM_VARIANTS]:
        os.makedirs(os.path.join(d, out), exist_ok=True)
        if not rj(os.path.join(d, jobs)): continue
        log.start(os.path.join(d, jobs), os.path.join(d, out), f"{samples} samples per cell, {workers} workers")
        run(['nice', '-n', '10', './run_jobs.sh', os.path.join(d, jobs), os.path.join(d, out), str(samples), str(workers)], env={**env, **extra}, cwd=PSSIM)
        log.done(os.path.join(d, out))
    speeds(sheet)

def speeds(sheet, jobs=None, out=None):
    run(['node', 'tr_speeds.js', jobs or sheet.w('t1', 'jobs.json'), out or sheet.w('t1', 'speeds.json')], env={'MYTEAM': sheet.team_path}, cwd=PSSIM,
        stdout=subprocess.DEVNULL)

def solve(sheet, res=None, speeds_path=None, out=None):
    c = t1cfg(sheet); res = res or sheet.w('t1', 'res'); out = out or sheet.p('t1.json')
    env = {'READER_W': str(c['reader_w']), 'TR_SPEEDS': speeds_path or sheet.w('t1', 'speeds.json'), 'TR_CREDIT': c['tr_credit'],
           'EXCLUDE_MOVES': ','.join(c.get('exclude_moves', []))}
    if c.get('trmult_file'): env['TRMULT_FILE'] = os.path.normpath(sheet.p(c['trmult_file']))
    for it in ITEM_VARIANTS: os.makedirs(f'{res}_{it}', exist_ok=True)
    os.makedirs(sheet.w('t1'), exist_ok=True)
    with open(sheet.w('t1', 'solve.log'), 'w') as lg:
        run([VENV_PY if os.path.exists(VENV_PY) else sys.executable, 'tr_final.py', res, out], env=env, cwd=PSSIM, stdout=lg)
    return rj(out)
