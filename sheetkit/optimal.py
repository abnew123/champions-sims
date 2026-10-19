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
import collections, glob, itertools, json, re
from common import *
import picks as P

SCREEN_G0, MATRIX_G0, MATRIX_GAMES = 9000, 9100, 32

SOURCE = os.environ.get('OPTIMAL_SIXES', 'model')                # model: sixes reconstructed from the archetype models; pool: real sixes
                                                                 # (with cards the sixes are always the card's own real sixes: see sixes())
OUT = 'optimal' if SOURCE == 'model' else 'optimal_' + SOURCE     # where a run's battles go (work/<OUT>) and its result (<OUT>.json)
TOP_SIXES = 6                                                    # pool: the most common sixes per tab

def _w(sheet, *p): return sheet.w(OUT, *p)

def opt(sheet, k, default):
    """sheet.json "optimal" settings, for a run that has to be cheaper: sixes (per card, most common first), screen_games (per four
    where a card has several sixes), answers (their strongest fours per six that the candidates meet), candidates (ours, best first)"""
    return sheet.cfg.get('optimal', {}).get(k, default)

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

def card_sixes(sheet):
    """per card, its group's TOP_SIXES most common real sixes (pssim/opp_pool.py sixes), weighted by how often each was seen"""
    py = VENV_PY if os.path.exists(VENV_PY) else sys.executable; tmp = _w(sheet, 'pool_card.json'); out = {}
    SM = rj(os.path.join(ROOT, 'regionals', 'smogon_mc_sets.json'))
    def spread(species, nature):                                   # as opp_pool.spread (importing that module needs numpy)
        x = SM.get(species) or SM.get(species.split('-')[0])
        if x and x.get('evs'): return x['evs']
        return [32, 32, 0, 0, 2, 0] if nature in ('Adamant', 'Jolly', 'Brave', 'Careful', 'Impish') else [32, 0, 0, 32, 2, 0]
    for m, c in CARDS.items():
        group = m if c['rule'] else 'other:' + m[len('Other '):]
        subprocess.run([py, 'opp_pool.py', 'sixes', group, str(TOP_SIXES), tmp], cwd=PSSIM, stdout=subprocess.DEVNULL, check=True)
        xs = [x for x in rj(tmp)['sixes'] if len(x['six']) == 6]; W = sum(x['count'] for x in xs)
        out[m] = [{'label': ', '.join(s['species'] for s in x['six']), 'weight': x['count'] / W, 'count': x['count'],
                   'six': [{**s, 'evs': spread(s['species'], s['nature'])} for s in x['six']]} for x in xs]
    os.remove(tmp); return out

def sixes(sheet):
    """the opposing sixes per tab or card, cut to the "sixes" most common (weights renormalised)"""
    S = _sixes(sheet); n = opt(sheet, 'sixes', 99); out = {}
    for a, ts in S.items():
        ts = ts[:n]; W = sum(t['weight'] for t in ts); out[a] = [dict(t, weight=t['weight'] / W) for t in ts]
    return out

def _sixes(sheet):
    p = _w(sheet, 'sixes.json')
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if CARDS: wj(card_sixes(sheet), p)
        elif SOURCE == 'pool': wj(pool_sixes(sheet), p)
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
    """our fours for tab a: those the confirmation played (its top fours plus the pick), best on fresh games first; else the pick alone"""
    V, share, names, _, _ = P.load(sheet.w('confirm', 'res*', '*.json'))
    _, rows, _ = P.ranked(V, share, a)
    out = [names[c] for c in rows]
    pick = rj(sheet.p('picks.json'))['picks'][a]
    if not any(set(l) == set(pick['lead']) and set(b) == set(pick['back']) for l, b in out): out.append((pick['lead'], pick['back']))
    return [(list(l), list(b)) for l, b in out]

def job(sheet, a, si, lead, back, theirs):
    return {'mine': [sheet.team[n] for n in lead + back], 'theirs': theirs,
            'meta': {'arch': a, 'six': si, 'our_lead': lead, 'our_back': back, 'their_lead': [s['species'] for s in theirs[:2]], 'their_back': [s['species'] for s in theirs[2:]]}}

def run_screen(sheet, threads, log):
    S6 = sixes(sheet); picks = rj(sheet.p('picks.json'))['picks']; d = _w(sheet)
    g8 = opt(sheet, 'screen_games', 8)
    for games in (16, g8):                                        # one queue per game count (a result folder holds one kind of run)
        jobs = [job(sheet, a, si, picks[a]['lead'], picks[a]['back'], f)
                for a in ARCHS if a in picks for si, t in enumerate(S6[a]) if (len(S6[a]) == 1) == (games == 16) for f in fours_of(t['six'])]
        if not jobs: continue
        wj(jobs, f'{d}/screen_{games}.json')
        P.battle_run(sheet, 'optimal', f'{d}/screen_{games}.json', f'{d}/screen_{games}', games, SCREEN_G0, threads, None, log)

def queues(sheet, kind):
    """the job files of every round so far: round 1 is screen_<games>.json / matrix.json, later rounds screen_r<n>_<games>.json / matrix_r<n>.json;
    each one's results are in the folder of the same name"""
    pat = re.compile(r'screen(_r\d+)?_\d+\.json$' if kind == 'screen' else r'matrix(_r\d+|_mix\d+)?\.json$')      # _mix<n>: mix.py check
    return sorted(p for p in glob.glob(_w(sheet, '*.json')) if pat.search(os.path.basename(p)))

def four_key(lead, back): return (frozenset(lead), frozenset(back))

def screen_results(sheet):
    """(arch, six, our four) -> [(our win share, their four as species names, their four's sets)], lowest first"""
    out = collections.defaultdict(list); S6 = sixes(sheet)
    for p in queues(sheet, 'screen'):
        jobs = rj(p)
        for f in glob.glob(os.path.join(p[:-5], '*.json')):
            r = rj(f); vs = [g['v'] for g in r['rows'] if g.get('v') is not None]
            if vs and r['six'] < len(S6.get(r['arch'], [])):
                out[(r['arch'], r['six'], four_key(r['our_lead'], r['our_back']))].append((mean(vs), r['their_lead'] + r['their_back'], jobs[r['job']]['theirs']))
    for k in out: out[k].sort(key=lambda x: x[0])
    return out

def screened(sheet):
    """arch -> the fours of ours whose strongest answers have been searched (a screen played them against every opposing four)"""
    out = collections.defaultdict(set)
    for a, _, k in screen_results(sheet): out[a].add(k)
    return out

def matrix_cells(sheet):
    """(arch, our four as 'lead', 'back' strings) -> (six, their four) -> (win share, games), over every round's matrix"""
    M = collections.defaultdict(dict)
    for p in queues(sheet, 'matrix'):                             # (.stale: cells no longer in a queue are still games played on this setup)
        for f in glob.glob(os.path.join(p[:-5], '*.json')) + glob.glob(os.path.join(p[:-5] + '.stale', '*.json')):
            r = rj(f); vs = [g['v'] for g in r['rows'] if g.get('v') is not None]
            if vs: M[(r['arch'], ('+'.join(r['our_lead']), '+'.join(r['our_back'])))][(r['six'], '+'.join(r['their_lead'] + r['their_back']))] = (mean(vs), len(vs))
    return M

def matrix_jobs(sheet, scr, archs, top, have=None):
    """every candidate of each tab in archs against the top strongest answers per six in scr (one screen's results), skipping cells in have"""
    jobs = []; have = have or {}
    for a in ARCHS:
        if a not in archs: continue
        cands = candidates(sheet, a)[:opt(sheet, 'candidates', 99)]
        for (arch, si), rows in sorted(scr.items()):
            if arch != a: continue
            for _, names, theirs in rows[:top]:
                for lead, back in cands:
                    if (si, '+'.join(names)) not in have.get((a, ('+'.join(lead), '+'.join(back))), {}): jobs.append(job(sheet, a, si, lead, back, theirs))
    return jobs

def run_matrix(sheet, threads, log, top=None):
    scr = {(a, si): rows for (a, si, _), rows in screen_results(sheet).items()}; d = _w(sheet)
    jobs = matrix_jobs(sheet, scr, {a for a, _ in scr}, top or opt(sheet, 'answers', 3))
    wj(jobs, f'{d}/matrix.json')
    P.battle_run(sheet, 'optimal', f'{d}/matrix.json', f'{d}/matrix', MATRIX_GAMES, MATRIX_G0, threads, None, log)

def ranking(sheet, a, S6=None, M=None):
    """[(win share when each opposing six brings its strongest four we have met, our four as ('lead', 'back') strings, per six
    [(weight, (win share, games, their four))])] for tab a, best first"""
    S6 = S6 or sixes(sheet); M = M if M is not None else matrix_cells(sheet); ts = S6[a]; W = sum(t['weight'] for t in ts); rows = []
    for (arch, ours), cells in M.items():
        if arch != a: continue
        per = []
        for si, t in enumerate(ts):
            c = [(v, n, k[1]) for k, (v, n) in cells.items() if k[0] == si]
            if c: per.append((t['weight'] / W, min(c)))
        if len(per) == len(ts): rows.append((sum(w * m[0] for w, m in per), ours, per))
    return sorted(rows, key=lambda x: -x[0])

def run_more(sheet, threads, log):
    """one more round: for each tab whose best four on the numbers so far is one nobody searched answers for (after a first round, every
    candidate but the screened pick), screen it against every opposing four, then play every candidate against its new strongest
    answers. An unsearched four only met answers found against another four, which flatters it; repeat until the best four of every
    tab has been searched."""
    picks = rj(sheet.p('picks.json'))['picks']; S6 = sixes(sheet); done = screened(sheet); d = _w(sheet); M = matrix_cells(sheet)
    target = {}
    for a in ARCHS:
        if a not in picks: continue
        rows = ranking(sheet, a, S6, M)
        top = rows[0][1] if rows else ('+'.join(picks[a]['lead']), '+'.join(picks[a]['back']))
        lead, back = top[0].split('+'), top[1].split('+')
        if four_key(lead, back) not in done[a]: target[a] = (lead, back)
    todo = list(target)
    if not todo: print("every tab's best four has been searched; nothing to do"); return
    print(f"{len(todo)} tabs: their best four's answers not searched yet")
    n = 1 + max([int(m.group(1)) for p in queues(sheet, 'screen') for m in [re.search(r'_r(\d+)_', p)] if m] + [1])    # round 2, 3, ...
                                                                  # (the first extra round of the Trick Room Six run of 2026-10-06 is named r1)
    g8 = opt(sheet, 'screen_games', 8)
    for games in (16, g8):
        jobs = [job(sheet, a, si, *target[a], f)
                for a in todo for si, t in enumerate(S6[a]) if (len(S6[a]) == 1) == (games == 16) for f in fours_of(t['six'])]
        if not jobs: continue
        wj(jobs, f'{d}/screen_r{n}_{games}.json')
        P.battle_run(sheet, 'optimal', f'{d}/screen_r{n}_{games}.json', f'{d}/screen_r{n}_{games}', games, SCREEN_G0, threads, None, log)
    scr = {(a, si): rows for (a, si, k), rows in screen_results(sheet).items() if a in todo and k == four_key(*target[a])}
    jobs = matrix_jobs(sheet, scr, set(todo), opt(sheet, 'answers', 3), matrix_cells(sheet))
    wj(jobs, f'{d}/matrix_r{n}.json')
    P.battle_run(sheet, 'optimal', f'{d}/matrix_r{n}.json', f'{d}/matrix_r{n}', MATRIX_GAMES, MATRIX_G0, threads, None, log)

def run(sheet, threads=None, force=False, stage='all'):
    threads = threads_arg(threads, force); log = RunLog(sheet, OUT)
    if stage == 'more': return run_more(sheet, threads, log)
    if stage in ('all', 'screen'): run_screen(sheet, threads, log)
    if stage in ('all', 'matrix'): run_matrix(sheet, threads, log)
    if stage == 'all':                                            # later rounds' queues: play whatever is missing (e.g. moved out by
        for p in queues(sheet, 'screen') + queues(sheet, 'matrix'):  # `kit.py <team> flagged --write` for a replay)
            m = re.search(r'screen_r\d+_(\d+)\.json$', p) or re.search(r'matrix_(r|mix)\d+\.json$', p)
            if not m: continue
            games = int(m.group(1)) if 'screen' in os.path.basename(p) else MATRIX_GAMES; g0 = SCREEN_G0 if 'screen' in os.path.basename(p) else MATRIX_G0
            if len(glob.glob(os.path.join(p[:-5], '*.json'))) < len(rj(p)): P.battle_run(sheet, 'optimal', p, p[:-5], games, g0, threads, None, log)

def adopt(sheet, out=print):
    """picks.json from the report: each tab's (card's) pick becomes its best candidate when both sides pick, and its number that
    candidate's win share against each opposing six's strongest answer (the user's choice, 2026-10-06: the sheet's percentages assume
    both players pick their four well). The fresh-game number against the usual brings is kept as replay_v."""
    R = rj(sheet.p(OUT + '.json')); d = rj(sheet.p('picks.json')); P_ = d['picks']; n = 0
    V, share, names, _, _ = P.load(sheet.w('confirm', 'res*', '*.json'))
    for a, r in R.items():
        old = P_.get(a, {}); key = (frozenset(r['lead']), frozenset(r['back']))
        teams = [t for t in V if t[0] == a and key in V[t]]
        rv = sum(share[t] * mean(list(V[t][key].values())) for t in teams) / sum(share[t] for t in teams) if teams else None
        changed = not old or key != (frozenset(old['lead']), frozenset(old['back']))
        P_[a] = {'lead': r['lead'], 'back': r['back'], 'v': r['v'], 'basis': 'both sides pick', 'replay_v': round(rv, 3) if rv is not None else None,
                 'answers': r['answers'], 'changed': changed, **{k: old[k] for k in ('mix', 'mix_v', 'mix_pure_v') if k in old}}   # mixes (mix.py) stay until rewritten
        n += changed; out(f"{a}: {'NEW ' if changed else ''}{'+'.join(r['lead'])} / {'+'.join(r['back'])}  {100*r['v']:.0f}% when they pick too")
    d.update(picks=P_, basis='both sides pick their four (optimal step, ' + OUT + ')'); wj(d, sheet.p('picks.json'), indent=1)
    out(f"picks.json: {n} fours changed")

def report(sheet, out=print):
    """only a four whose own strongest answers were searched can be the pick (the others met answers found against another four, so
    their numbers are flattering); they are listed, marked, so a later round ("optimal run --only more") can search theirs"""
    S6 = sixes(sheet); picks = rj(sheet.p('picks.json'))['picks']; M = matrix_cells(sheet); done = screened(sheet)
    res = {}; mine = lambda n: sheet.my_names.get(n, n); four = lambda l, b: f"{'+'.join(map(mine, l))} / {'+'.join(map(mine, b))}"
    for a in ARCHS:
        if a not in picks: continue
        ts = S6[a]; rows = ranking(sheet, a, S6, M)
        pk = four_key(picks[a]['lead'], picks[a]['back']); ok = lambda ours: four_key(ours[0].split('+'), ours[1].split('+')) in done[a]
        rv = picks[a].get('replay_v')                             # None when the confirmation never played the pick
        out(f"\n=== {a}: " + (f"sheet {100*rv:.0f}% against the replay-average fours" if rv is not None else "the sheet pick has no fresh-game number"))
        for v, ours, per in rows:
            out(f"   {four(ours[0].split('+'), ours[1].split('+')):42s} {100*v:5.1f}% when each opposing six brings its best four"
                + ('' if ok(ours) else '   (its own answers not searched)') + ('   <- sheet pick' if four_key(ours[0].split('+'), ours[1].split('+')) == pk else ''))
        rows = [r for r in rows if ok(r[1])]
        if rows:
            v, ours, per = rows[0]
            res[a] = {'lead': ours[0].split('+'), 'back': ours[1].split('+'), 'v': round(v, 3), 'replay_v': picks[a]['v'],
                      'answers': [{'six': ts[i]['label'], 'weight': round(w, 3), 'their_four': m[2], 'v': round(m[0], 3)} for i, (w, m) in enumerate(per)]}
            for i, (w, m) in enumerate(per): out(f"      their best answer{' (' + ts[i]['label'] + ')' if len(ts) > 1 else ''}: {m[2].replace('+', ', ', 1) if False else m[2]} -> {100*m[0]:.0f}%")
    wj(res, sheet.p(OUT + '.json'), indent=1, ensure_ascii=False)
    return res
