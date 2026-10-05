"""Which four to bring against each archetype, from whole-game sims.

  matrix   every (lead, back) four of the six (90) against the archetype's six most common opposing leads, the same games for all 90
  confirm  each archetype's top fours from the matrix plus the current pick, replayed on fresh games; a pick changes only when the
           fresh-game leader beats it by a clear paired margin (picking the best of 90 on the same games flatters the winner)

Seeds depend on the opponent and the game index only, so every four meets the same games: all comparisons are paired, game by game.
Result files are the battle binary's: {arch, pair, share, lead, back, theirs, rows: [{g, v, ms, ...}]}."""
import glob, itertools, json, os, collections, datetime, hashlib, re, shutil
from common import *

MIN_SE = 1.5        # a pick changes when the fresh-game leader beats it by at least this many paired standard errors

# ---------------------------------------------------------------- jobs and runs
def matrix_jobs(sheet, arch, npairs=6):
    jobs = []
    for lead in itertools.combinations(sheet.names, 2):
        for back in itertools.combinations([n for n in sheet.names if n not in lead], 2):
            for k in range(npairs): jobs.append({'arch': arch, 'k': k, 'lead': list(lead), 'back': list(back)})
    return jobs

def all_matrix_jobs(sheet):
    opp = opp_model(); return [j for a in ARCHS for j in matrix_jobs(sheet, a, len(opp[a]['pairs']))]

def write_matrix_jobs(sheet):
    jobs = all_matrix_jobs(sheet); wj(jobs, sheet.w('matrix', 'jobs.json'))
    print(f"{len(jobs)} jobs ({len(jobs) // len(ARCHS)} per archetype) -> work/matrix/jobs.json")

def team_hash(sheet): return hashlib.sha1(json.dumps(sheet.team, sort_keys=True).encode()).hexdigest()[:10]

def stamp(outdir, want):
    """One result folder holds one kind of run: refuse to add games played with other sets, another sim setup or other game indices."""
    p = outdir + '.run.json'; n = len(glob.glob(os.path.join(outdir, '*.json')))
    have = rj(p) if os.path.exists(p) else None
    if n and (have is None or any(have.get(k) != v for k, v in want.items())):
        sys.exit(f"{os.path.relpath(outdir, ROOT)} already holds {n} results from a different run ({have or 'unrecorded'}); this run is {want}. "
                 "Move that folder aside (do not mix runs) and start again.")
    wj(dict(want, date=datetime.date.today().isoformat()), p)

def make_starts(sheet, jobs, todo, starts, games, g0, procs):
    """Starting positions for jobs[i], i in todo, written to `starts` with each line's job number = i. battle_starts.js numbers the jobs of
    the file it is given from 0, so the list is cut into slices built in parallel and the numbers are put back while merging.
    Seeds depend on the opponent and the game index, not on the job number, so this plays the same games as one job file would."""
    k = max(1, min(procs, 16, math.ceil(len(todo) / 40))); parts = [todo[c::k] for c in range(k)]; d = starts + '.parts'; os.makedirs(d, exist_ok=True)
    ps = []
    for c, part in enumerate(parts):
        wj([jobs[i] for i in part], f'{d}/{c}.json')
        ps.append(subprocess.Popen(['node', '../native/battle_starts.js', f'{d}/{c}.json', f'{d}/{c}.jsonl', str(games), str(g0)],
                                   env=dict(os.environ, MYTEAM=sheet.team_path), cwd=PSSIM, stdout=subprocess.DEVNULL))
    if any(p.wait() for p in ps): sys.exit('building the starting positions failed (node ../native/battle_starts.js)')
    n = 0
    with open(starts, 'w') as out:
        for c, part in enumerate(parts):
            for line in open(f'{d}/{c}.jsonl'):
                m = re.match(r'\{"job":(\d+),', line); assert m, 'unexpected line from battle_starts.js'
                out.write('{"job":%d,' % part[int(m.group(1))] + line[m.end():]); n += 1
    shutil.rmtree(d); assert n == len(todo) * games, (n, len(todo), games)
    return n

def battle_run(sheet, step, jobs_path, outdir, games, g0, threads, setup, log, only=None):
    """Play jobs_path's jobs (all, or the job numbers in `only`) for games g0 .. g0+games-1 with the full-battle sim, one work queue for
    all of them. Resumes: jobs with a result file are skipped."""
    S = sim_setup(setup); jobs = rj(jobs_path); starts = outdir + '.starts.jsonl'; os.makedirs(outdir, exist_ok=True)
    stamp(outdir, {'setup': S['name'], 'games': games, 'g0': g0, 'team': team_hash(sheet)})
    todo = [i for i in (only if only is not None else range(len(jobs))) if not os.path.exists(os.path.join(outdir, f'{i}.json'))]
    log.start(jobs_path, outdir, f"{games} games, {threads} threads ({S['name']}, first game {g0}; {len(todo)} of {len(jobs)} jobs to play)")
    if todo:
        n = make_starts(sheet, jobs, todo, starts, games, g0, threads); log.line(f"{now()} {n} starting positions")
        env = dict(S['env'], GRID_DIR=sheet.grid_dir())
        with open(outdir + '.err', 'a') as err:
            run(['nice', '-n', '10', S['binary'], 'battle', S['engine_data'], starts, outdir, str(threads)], env=env, cwd=PSSIM, stderr=err)
        os.remove(starts)
    log.done(outdir)

def run_matrix(sheet, games=16, g0=600, threads=None, setup=None, only=None, force=False):
    threads = threads_arg(threads, force); log = RunLog(sheet, 'matrix'); jobs = rj(sheet.w('matrix', 'jobs.json'))
    idx = [i for i, j in enumerate(jobs) if ARCHS.index(j['arch']) in only] if only is not None else None      # --only: archetype numbers
    battle_run(sheet, 'matrix', sheet.w('matrix', 'jobs.json'), sheet.w('matrix', 'res'), games, g0, threads, setup, log, idx)

def run_confirm(sheet, games=48, g0=1000, threads=None, setup=None, force=False):
    threads = threads_arg(threads, force); log = RunLog(sheet, 'confirm')
    battle_run(sheet, 'confirm', sheet.w('confirm', 'jobs.json'), sheet.w('confirm', 'res'), games, g0, threads, setup, log)

# ---------------------------------------------------------------- reading results
def load(pattern):
    """(arch, opposing lead pair) -> four (lead frozenset, back frozenset) -> {game: value}; plus share, the four's names, their four, ms"""
    V = collections.defaultdict(dict); share = {}; names = {}; theirs = {}; ms = collections.defaultdict(list)
    for f in glob.glob(pattern):
        try: r = rj(f)
        except Exception: continue                                # a file still being written
        key = (frozenset(r['lead']), frozenset(r['back'])); names[key] = (r['lead'], r['back']); t = (r['arch'], r['pair'])
        V[t][key] = {g['g']: g['v'] for g in r['rows'] if g.get('v') is not None}
        share[t] = r['share']; theirs[t] = r['theirs']; ms[r['arch']] += [g.get('ms', 0) for g in r['rows']]
    return V, share, names, theirs, ms

def ranked(V, share, a):
    """the archetype's opposing teams, the fours played against all of them (best first), and each four's share-weighted win share"""
    teams = [t for t in V if t[0] == a]
    if not teams: return [], [], {}
    fours = set.intersection(*(set(V[t]) for t in teams)); W = sum(share[t] for t in teams)
    win = {c: sum(share[t] * mean(list(V[t][c].values())) for t in teams) / W for c in fours}
    return teams, sorted(fours, key=lambda c: -win[c]), win

def gap(V, share, teams, c, best):
    """paired difference c - best over the games both played, opposing teams weighted by replay share"""
    return paired_gap([(share[t], [V[t][c][g] - V[t][best][g] for g in V[t][c] if g in V[t][best]]) for t in teams])

def four_name(sheet, names, c):
    l, b = names[c]; s = lambda m: sheet.my_names.get(m, m)
    return f"{'+'.join(map(s, l))} / {'+'.join(map(s, b))}"

def read_picks(path):
    """picks.json -> {archetype: {lead, back, ...}} (or {} when there is none yet)"""
    if not path or not os.path.exists(path): return {}
    d = rj(path); return d.get('picks', d)
def four_of(p): return (frozenset(p['lead']), frozenset(p['back']))

# ---------------------------------------------------------------- matrix report
def matrix_report(sheet, pattern=None, picks_path=None, out=print):
    """A. per archetype: the best fours, where the current pick ranks and its paired gap to the best
    B. per archetype: what bringing / leading each of the six is worth
    C. species tells: how the worth of bringing each of mine changes when X is in their four, against the same archetype's average"""
    V, share, names, theirs, _ = load(pattern or sheet.w('matrix', 'res*', '*.json')); picks = read_picks(picks_path or sheet.p('picks.json'))
    short = lambda m: sheet.my_names.get(m, m); MINE = sheet.names
    out(f"{sum(len(d) for d in V.values())} (opposing team, four) jobs read, {sum(len(g) for d in V.values() for g in d.values())} games")
    pick_tot = best_tot = Wtot = 0.0
    for a in ARCHS:
        teams, rows, win = ranked(V, share, a)
        if not rows: continue
        best = rows[0]; pk = four_of(picks[a]) if a in picks else None; W = sum(share[t] for t in teams)
        out(f"\n=== {a} ({SHARE[a]}%): {len(rows)} fours, {len(teams)} opposing teams, {min(len(V[t][best]) for t in teams)} games each")
        for i, c in enumerate(rows[:6]):
            g = '' if c == best else '  %+.1f ± %.1f' % tuple(100 * x for x in gap(V, share, teams, c, best))
            out(f"  {i+1:2d}. {four_name(sheet, names, c):40s} {100*win[c]:5.1f}%{g}{'   <- sheet' if c == pk else ''}")
        if pk in win and pk not in rows[:6]:
            m, se = gap(V, share, teams, pk, best)
            out(f"  {rows.index(pk)+1:2d}. {four_name(sheet, names, pk):40s} {100*win[pk]:5.1f}%  {100*m:+.1f} ± {100*se:.1f}   <- sheet")
        if pk in win: pick_tot += SHARE[a] * win[pk]; best_tot += SHARE[a] * win[best]; Wtot += SHARE[a]
        parts = []
        tm = lambda t, cs: mean([mean(list(V[t][c].values())) for c in cs])
        for m in MINE:
            bring = sum(share[t] * (tm(t, [c for c in rows if m in c[0] | c[1]]) - tm(t, [c for c in rows if m not in c[0] | c[1]])) for t in teams) / W
            lead = sum(share[t] * (tm(t, [c for c in rows if m in c[0]]) - tm(t, [c for c in rows if m in c[1]])) for t in teams) / W
            parts.append(f"{short(m)} {100*bring:+.0f} (lead vs back {100*lead:+.0f})")
        out('  worth of bringing: ' + ', '.join(parts))
    if Wtot: out(f"\nladder-weighted (archetypes with a current pick): current picks {100*pick_tot/Wtot:.1f}% | best four here {100*best_tot/Wtot:.1f}%"
                 " (the best-four number is optimistic: it is picked on the same games)")
    # C. species tells
    def bring_value(t, m):
        cs = list(V[t]); gs = set.intersection(*(set(V[t][c]) for c in cs))
        d = [mean([V[t][c][g] for c in cs if m in c[0] | c[1]]) - mean([V[t][c][g] for c in cs if m not in c[0] | c[1]]) for g in gs]
        mu = mean(d); return mu, math.sqrt(sum((x - mu) ** 2 for x in d) / max(1, len(d) - 1) / max(1, len(d)))
    BV = {(t, m): bring_value(t, m) for t in V if len(V[t]) >= 80 for m in MINE}
    teams = sorted({t for t, _ in BV})
    if not teams: return
    arch_bv = {}
    for a in ARCHS:
        ts = [t for t in teams if t[0] == a]
        for m in MINE:
            if ts: arch_bv[(a, m)] = sum(share[t] * BV[(t, m)][0] for t in ts) / sum(share[t] for t in ts)
    spec = collections.defaultdict(list)
    for t in teams:
        for x in {n.split('-Mega')[0] for n in theirs[t]}: spec[x].append(t)
    wt = lambda t: SHARE[t[0]] * share[t]; Wall = sum(wt(t) for t in teams)
    out(f"\n=== species tells ({len(teams)} opposing teams): change in what bringing each of mine is worth when X is in their four, vs the same "
        "archetype's average (win-% points; * = more than 2 standard errors)")
    out('  ' + ' ' * 22 + ''.join(f"{short(m):>11s}" for m in MINE) + '   teams (archetypes)')
    for x, ts in sorted(spec.items(), key=lambda kv: -sum(wt(t) for t in kv[1])):
        if len(ts) < 2: continue
        W = sum(wt(t) for t in ts); cells = []
        for m in MINE:
            d = sum(wt(t) * (BV[(t, m)][0] - arch_bv[(t[0], m)]) for t in ts) / W
            se = math.sqrt(sum((wt(t) / W) ** 2 * BV[(t, m)][1] ** 2 for t in ts))
            cells.append(f"{100*d:+6.0f}{'*' if abs(d) > 2 * se else ' '}   ")
        archs = collections.Counter(t[0].split(' ')[0].split('/')[0].rstrip(',') for t in ts)
        out(f"  {x:22s}" + ''.join(cells) + f"  {len(ts)} ({', '.join(f'{k} {v}' for k, v in archs.most_common(3))}); {100*W/Wall:.0f}% of weight")

# ---------------------------------------------------------------- confirmation
def confirm_jobs(sheet, N=5, pattern=None, picks_path=None, only=None, out=print):
    """Each archetype's top N fours in the matrix plus the current pick, against all its opposing leads; slow archetypes first."""
    V, share, names, _, ms = load(pattern or sheet.w('matrix', 'res*', '*.json')); picks = read_picks(picks_path or sheet.p('picks.json'))
    opp = opp_model(); jobs = []
    for a in sorted([ARCHS[i] for i in only] if only else ARCHS, key=lambda a: -mean(ms[a])):
        teams, rows, win = ranked(V, share, a)
        pk = four_of(picks[a]) if a in picks else None
        cand = rows[:N] + ([pk] if pk is not None and pk not in rows[:N] else [])
        out(f"{a} ({mean(ms[a])/1000:.1f} s/game): " + ' | '.join(f"{four_name(sheet, names, c)} {100*win[c]:.0f}%{' (sheet)' if c == pk else ''}" for c in cand))
        for c in cand:
            lead, back = names.get(c) or (sheet.back(c[0]), sheet.back(c[1]))
            for k in range(len(opp[a]['pairs'])): jobs.append({'arch': a, 'k': k, 'lead': lead, 'back': back})
    return jobs

def decide(sheet, pattern=None, matrix_pattern=None, picks_path=None, out=print):
    """Paired on the fresh games only. Returns the new picks {archetype: {lead, back, v, n, ...}}."""
    V, share, names, _, _ = load(pattern or sheet.w('confirm', 'res*', '*.json'))
    M, mshare, mnames, _, _ = load(matrix_pattern or sheet.w('matrix', 'res*', '*.json')); names.update(mnames)
    picks = read_picks(picks_path or sheet.p('picks.json')); final = {}; tot = tot_sheet = 0.0
    for a in ARCHS:
        teams, rows, win = ranked(V, share, a)
        if not rows: continue
        best = rows[0]; pk = four_of(picks[a]) if a in picks else None
        _, _, mwin = ranked(M, mshare, a)
        n = sum(len(V[t][best]) for t in teams)
        out(f"\n=== {a} ({SHARE[a]}%), {n} fresh games per four")
        for c in rows:
            g = '' if c == best else '  %+.1f ± %.1f vs the best' % tuple(100 * x for x in gap(V, share, teams, c, best))
            out(f"   {four_name(sheet, names, c):40s} fresh {100*win[c]:5.1f}%  (bring matrix {100*mwin.get(c, float('nan')):.0f}%){g}{'   <- sheet' if c == pk else ''}")
        # keep the current pick unless the fresh-game leader beats it by at least MIN_SE standard errors (paired)
        sg, sse = gap(V, share, teams, pk, best) if pk in win and pk != best else (0.0, 1.0)
        ch = best if pk not in win or -sg >= MIN_SE * sse else pk
        lead, back = names[ch]
        final[a] = {'lead': lead, 'back': back, 'v': round(win[ch], 3), 'n': n, 'source': 'bring matrix + fresh confirmation',
                    'changed': ch != pk, 'best': four_name(sheet, names, best), 'best_v': round(win[best], 3), 'sheet_v': round(win[pk], 3) if pk in win else None}
        out(f"   -> {'NEW PICK ' if ch != pk else 'keep '}{four_name(sheet, names, ch)} ({100*win[ch]:.1f}%)")
        tot += SHARE[a] * win[ch]; tot_sheet += SHARE[a] * win.get(pk, float('nan'))
    W = sum(SHARE[a] for a in final)
    if W: out(f"\nladder-weighted on fresh games: new picks {100*tot/W:.1f}% | current picks {100*tot_sheet/W:.1f}%")
    return final

def weighted(picks): return sum(SHARE[a] * p['v'] for a, p in picks.items()) / sum(SHARE[a] for a in picks)
