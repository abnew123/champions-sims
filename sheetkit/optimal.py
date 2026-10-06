"""Both sides pick their four: the tab's number when the opponent also brings its best four against ours, and the four of ours that holds
up best when it does.

  A  screen   our tab pick against every four each opposing six allows (16 games per four where the archetype is one six, 8 where it
              is a mix of six teams); fresh game indices from 9000
  B  matrix   our candidate fours (the ones the confirmation tested for that tab) against each opposing six's three strongest fours from
              the screen, 32 games each, from index 9100
  report      per tab and candidate: the share-weighted win share when every opposing six brings its strongest four against it (the
              minimum over its three); the best candidate is the tab's robust pick and its number the tab's value with both sides picking.
              Writes optimal.json.

The opposing sixes come from opp_sixes.js (OPTIMAL_SIXES=model, the default) or, with OPTIMAL_SIXES=pool, from the most common real sixes
in Battle sim's pool of Showdown Bo3 sides (pssim/opp_pool.py); a pool run keeps its battles in work/optimal_pool and writes optimal_pool.json. Games are explicit-team battles, seeded by their four, so our candidates meet the same games."""
import collections, glob, itertools, json
from common import *
import picks as P

SCREEN_G0, MATRIX_G0, MATRIX_GAMES = 9000, 9100, 32

SOURCE = os.environ.get('OPTIMAL_SIXES', 'model')                # model: sixes reconstructed from the archetype models; pool: real sixes
OUT = 'optimal' if SOURCE == 'model' else 'optimal_' + SOURCE     # where a run's battles go (work/<OUT>) and its result (<OUT>.json)
TOP_SIXES = 6                                                    # pool: the most common sixes per tab

def _w(sheet, *p): return sheet.w(OUT, *p)

def pool_sixes(sheet):
    """per tab, the TOP_SIXES most common real sixes in Battle sim's pool (pssim/opp_pool.py: Showdown Bo3 sides with open team sheets),
    each placed on a tab by the archetype classifier the sheet's "Which tab" guide follows, weighted by how often it was seen"""
    py = VENV_PY if os.path.exists(VENV_PY) else sys.executable
    if not os.path.exists(os.path.join(PSSIM, 'opp_pool.json')): subprocess.run([py, 'opp_pool.py', 'build'], cwd=PSSIM, stdout=subprocess.DEVNULL, check=True)
    tmp = _w(sheet, 'pool_all.json'); os.makedirs(os.path.dirname(tmp), exist_ok=True)
    subprocess.run([py, 'opp_pool.py', 'sixes', 'all', '100000', tmp], cwd=PSSIM, stdout=subprocess.DEVNULL, check=True)      # (run() here is this module's)
    sys.path.insert(0, PSSIM); from pro_replays import arch
    SM = rj(os.path.join(ROOT, 'regionals', 'smogon_mc_sets.json'))
    def spread(species, nature):                                   # as opp_pool.spread (importing that module needs numpy)
        x = SM.get(species) or SM.get(species.split('-')[0])
        if x and x.get('evs'): return x['evs']
        return [32, 32, 0, 0, 2, 0] if nature in ('Adamant', 'Jolly', 'Brave', 'Careful', 'Impish') else [32, 0, 0, 32, 2, 0]
    name = {'Tailwind': 'Tailwind goodstuffs', 'Sun': 'Sun', 'Indeedee TR': 'Indeedee TR / Psychic Terrain', 'Rain': 'Rain', 'Balance': 'Balance, no speed control',
            'Sand': 'Sand', 'Snow': 'Snow', 'Trick Room': 'Trick Room without Indeedee', 'Rain + Sun': 'Rain + sun', 'Perish': 'Perish trap'}
    by = collections.defaultdict(list)
    for x in rj(tmp)['sixes']:
        if len(x['six']) == 6: by[name[arch([m['species'] for m in x['six']])]].append(x)
    out = {}
    for a, xs in by.items():
        top = sorted(xs, key=lambda x: -x['count'])[:TOP_SIXES]; W = sum(x['count'] for x in top)
        out[a] = [{'label': ', '.join(m['species'] for m in x['six']), 'weight': x['count'] / W, 'count': x['count'],
                   'six': [{**m, 'evs': spread(m['species'], m['nature'])} for m in x['six']]} for x in top]
    return out

def sixes(sheet):
    p = _w(sheet, 'sixes.json')
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if SOURCE == 'pool': wj(pool_sixes(sheet), p)
        else:
            r = subprocess.run(['node', '../sheetkit/opp_sixes.js'], env=dict(os.environ, MYTEAM=sheet.team_path), cwd=PSSIM, capture_output=True, text=True, check=True)
            open(p, 'w').write(r.stdout)
    return rj(p)

def fours_of(six):
    n = len(six)
    for lead in itertools.combinations(range(n), 2):
        for back in itertools.combinations([i for i in range(n) if i not in lead], 2):
            yield [six[i] for i in lead + back]

def candidates(sheet, a):
    """our fours for tab a: those the confirmation played (its top fours plus the pick), else the pick alone"""
    V, share, names, _, _ = P.load(sheet.w('confirm', 'res*', '*.json'))
    fours = {c for t in V if t[0] == a for c in V[t]}
    out = [names[c] for c in fours]
    pick = rj(sheet.p('picks.json'))['picks'][a]
    if not any(set(l) == set(pick['lead']) and set(b) == set(pick['back']) for l, b in out): out.append((pick['lead'], pick['back']))
    return [(list(l), list(b)) for l, b in out]

def job(sheet, a, si, lead, back, theirs):
    return {'mine': [sheet.team[n] for n in lead + back], 'theirs': theirs,
            'meta': {'arch': a, 'six': si, 'our_lead': lead, 'our_back': back, 'their_lead': [s['species'] for s in theirs[:2]], 'their_back': [s['species'] for s in theirs[2:]]}}

def run_screen(sheet, threads, log):
    S6 = sixes(sheet); picks = rj(sheet.p('picks.json'))['picks']; d = _w(sheet)
    for games in (16, 8):                                         # one queue per game count (a result folder holds one kind of run)
        jobs = [job(sheet, a, si, picks[a]['lead'], picks[a]['back'], f)
                for a in ARCHS if a in picks for si, t in enumerate(S6[a]) if (len(S6[a]) == 1) == (games == 16) for f in fours_of(t['six'])]
        wj(jobs, f'{d}/screen_{games}.json')
        P.battle_run(sheet, 'optimal', f'{d}/screen_{games}.json', f'{d}/screen_{games}', games, SCREEN_G0, threads, None, log)

def screen_results(sheet):
    """(arch, six) -> [(our win share, their four as species names, their four's sets)], lowest first"""
    out = collections.defaultdict(list)
    for games in (16, 8):
        p = _w(sheet, f'screen_{games}.json')
        if not os.path.exists(p): continue
        jobs = rj(p)
        for f in glob.glob(_w(sheet, f'screen_{games}', '*.json')):
            r = rj(f); vs = [g['v'] for g in r['rows'] if g.get('v') is not None]
            if vs: out[(r['arch'], r['six'])].append((mean(vs), r['their_lead'] + r['their_back'], jobs[r['job']]['theirs']))
    for k in out: out[k].sort(key=lambda x: x[0])
    return out

def run_matrix(sheet, threads, log, top=3):
    scr = screen_results(sheet); d = _w(sheet); jobs = []
    for a in ARCHS:
        cands = candidates(sheet, a) if any(k[0] == a for k in scr) else []
        for (arch, si), rows in sorted(scr.items()):
            if arch != a: continue
            for _, _, theirs in rows[:top]:
                for lead, back in cands: jobs.append(job(sheet, a, si, lead, back, theirs))
    wj(jobs, f'{d}/matrix.json')
    P.battle_run(sheet, 'optimal', f'{d}/matrix.json', f'{d}/matrix', MATRIX_GAMES, MATRIX_G0, threads, None, log)

def run(sheet, threads=None, force=False, stage='all'):
    threads = threads_arg(threads, force); log = RunLog(sheet, OUT)
    if stage in ('all', 'screen'): run_screen(sheet, threads, log)
    if stage in ('all', 'matrix'): run_matrix(sheet, threads, log)

def report(sheet, out=print):
    S6 = sixes(sheet); picks = rj(sheet.p('picks.json'))['picks']; scr = screen_results(sheet)
    M = collections.defaultdict(dict)                             # (arch, our four) -> (six, their four) -> win share
    for f in glob.glob(_w(sheet, 'matrix', '*.json')):
        r = rj(f); vs = [g['v'] for g in r['rows'] if g.get('v') is not None]
        if vs: M[(r['arch'], ('+'.join(r['our_lead']), '+'.join(r['our_back'])))][(r['six'], '+'.join(r['their_lead'] + r['their_back']))] = (mean(vs), len(vs))
    res = {}; mine = lambda n: sheet.my_names.get(n, n); four = lambda l, b: f"{'+'.join(map(mine, l))} / {'+'.join(map(mine, b))}"
    for a in ARCHS:
        if a not in picks: continue
        ts = S6[a]; W = sum(t['weight'] for t in ts); rows = []
        for (arch, ours), cells in M.items():
            if arch != a: continue
            per = []
            for si, t in enumerate(ts):
                c = [(v, n, k[1]) for k, (v, n) in cells.items() if k[0] == si]
                if c: per.append((t['weight'] / W, min(c)))
            if len(per) == len(ts): rows.append((sum(w * m[0] for w, m in per), ours, per))
        rows.sort(key=lambda x: -x[0])
        pk = ('+'.join(picks[a]['lead']), '+'.join(picks[a]['back']))
        out(f"\n=== {a}: sheet {100*picks[a]['v']:.0f}% against the replay-average fours")
        for v, ours, per in rows:
            out(f"   {four(ours[0].split('+'), ours[1].split('+')):42s} {100*v:5.1f}% when each opposing six brings its best four" + ('   <- sheet pick' if set(ours[0].split('+')) == set(pk[0].split('+')) and set(ours[1].split('+')) == set(pk[1].split('+')) else ''))
        if rows:
            v, ours, per = rows[0]
            res[a] = {'lead': ours[0].split('+'), 'back': ours[1].split('+'), 'v': round(v, 3), 'replay_v': picks[a]['v'],
                      'answers': [{'six': ts[i]['label'], 'weight': round(w, 3), 'their_four': m[2], 'v': round(m[0], 3)} for i, (w, m) in enumerate(per)]}
            for i, (w, m) in enumerate(per): out(f"      their best answer{' (' + ts[i]['label'] + ')' if len(ts) > 1 else ''}: {m[2].replace('+', ', ', 1) if False else m[2]} -> {100*m[0]:.0f}%")
    wj(res, sheet.p(OUT + '.json'), indent=1, ensure_ascii=False)
    return res
