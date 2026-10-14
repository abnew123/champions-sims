"""The reachability check (the user asked for a bug hunt beyond luck, 2026-10-12): for each turn of the Showdown bot's Bo3 games, the
position as the eval bar rebuilds it in hindsight (live.py), the choices and replacements the log shows played in Showdown over many seeds
(reach.js), and the next turn's start as the log has it compared with every seed's. A turn no seed reproduces points at the log reading
(replay.py), the rebuild (positions.js) or a guessed spread; one that only HP rules out is likely a spread, so the two are kept apart.
  python3 evalbar/reach.py [games] [seeds=32]          writes evalbar/out/reach/report.json and prints the turns no seed reproduces"""
import os, re, sys, json, glob, time, collections, subprocess
import common as C, live as L, replay as R, procs as P, spreads as SPR
OUT = os.path.join(C.HERE, 'out', 'reach'); E = SPR.E
toid = R.toid
WEATHER = {'raindance': 'Rain', 'sunnyday': 'Sun', 'sandstorm': 'Sandstorm', 'snowscape': 'Snow', 'hail': 'Hail', 'desolateland': 'Harsh sun', 'primordialsea': 'Heavy rain',
           'deltastream': 'Strong winds'}
NEEDS = {'normal', 'any', 'adjacentFoe', 'adjacentAlly', 'adjacentAllyOrSelf'}
def choose(spec, si):
    """the Showdown choice for side si from the spec's acts (engine slot order, targets remapped); partial: a slot whose choice the log
    does not show in full, played as its first move"""
    sd = spec['sides'][si]; acts = spec['acts'][si]; foe = 'p2' if si == 0 else 'p1'; own = 'p1' if si == 0 else 'p2'; parts = []; partial = False
    for i in range(2):
        m = sd['mons'][i] if i < len(sd['mons']) else None
        if not m or not m.get('onField') or m.get('fainted'): parts.append('pass'); continue
        a = acts[i] or {}
        if a.get('switch'):
            k = next((j for j, x in enumerate(sd['mons']) if j > 1 and not x.get('fainted') and toid(x['species'].split('-')[0]) == toid(a['switch'].split('-')[0])), None)
            parts.append(f'switch {k + 1}' if k is not None else 'default'); continue
        if 'charging' in (m.get('vol') or []): parts.append('move 1'); continue    # locked into its charged move: no target to give
        mv = a.get('move'); moves = [toid(x) for x in m.get('moves', [])]
        if not mv or toid(mv) not in moves: partial = True; mv = m['moves'][0]
        k = moves.index(toid(mv)); md = E['moves'].get(toid(mv)) or {}; tgt_type = md.get('target', 'normal')
        if md.get('nonGhostTarget') and 'Ghost' not in ((E['species'].get(toid(m['species'])) or {}).get('types') or []): tgt_type = md['nonGhostTarget']   # Curse
        s = f'move {k + 1}'
        if tgt_type in NEEDS and a.get('target') == own + 'ab'[i]: tgt_type = 'self'   # the log names the user itself: no target to give
        if tgt_type in NEEDS:
            t = a.get('target') or a.get('spreadTarget') or ''
            if not t: partial = True; t = foe + 'a'                            # no target in the log (a failed Sucker Punch): a guess
            n = (1 if t[2] == 'a' else 2) if t[:2] == foe else -(1 if t[2] == 'a' else 2)
            s += f' {n}'
        if a.get('mega'): s += ' mega'
        parts.append(s)
    return ', '.join(parts), partial
def observed(st, field_src):
    f = field_src['field']; out = {'field': {'weather': f.get('weather') or '', 'terrain': (f.get('terrain') or ''), 'tr': (f.get('tr') or 0) > 0}, 'sides': {}}
    for sd in ('p1', 'p2'):
        s = st[sd]; out['sides'][sd] = {'tailwind': (s.get('tailwind') or 0) > 0, 'screens': sorted(toid(k) for k, v in (s.get('screens') or {}).items() if v),
                                        'mons': {toid(m['sp'].split('-')[0]): m for m in s['mons'] if not m.get('pool')}}
    return out
def compare(obs, smp):
    """the features a seed's state gets wrong: discrete ones, and HP (kept apart)"""
    bad, hp = [], []
    sf = smp['field']
    if (WEATHER.get(sf['weather'], sf['weather']) or '') != obs['field']['weather']: bad.append(f"weather {sf['weather'] or '-'} vs {obs['field']['weather'] or '-'}")
    if (sf['terrain'].replace('terrain', '').capitalize() if sf['terrain'] else '') != obs['field']['terrain']: bad.append(f"terrain {sf['terrain'] or '-'} vs {obs['field']['terrain'] or '-'}")
    if sf['tr'] != obs['field']['tr']: bad.append(f"trick room {sf['tr']} vs {obs['field']['tr']}")
    for sd in ('p1', 'p2'):
        o, s = obs['sides'][sd], smp['sides'][sd]
        if s['tailwind'] != o['tailwind']: bad.append(f'{sd} tailwind {s["tailwind"]} vs {o["tailwind"]}')
        if s['screens'] != o['screens']: bad.append(f'{sd} screens {s["screens"]} vs {o["screens"]}')
        for x in s['mons']:
            m = o['mons'].get(toid(x['sp']))
            if not m: continue
            if x['fnt'] != bool(m['f']): bad.append(f"{sd} {x['sp']} fainted {x['fnt']} vs {bool(m['f'])}"); continue
            if x['fnt']: continue
            if x['active'] != bool(m['pos']): bad.append(f"{sd} {x['sp']} active {x['active']} vs {bool(m['pos'])}")
            if (x['status'] or '') != (m['st'] or ''): bad.append(f"{sd} {x['sp']} status {x['status'] or '-'} vs {m['st'] or '-'}")
            if x['active'] and m['pos'] and {k: v for k, v in x['boosts'].items() if k in ('atk', 'def', 'spa', 'spd', 'spe')} != {k: v for k, v in (m['b'] or {}).items() if v and k in ('atk', 'def', 'spa', 'spd', 'spe')}:
                bad.append(f"{sd} {x['sp']} boosts {x['boosts']} vs {m['b']}")
            pct = 100 * x['hp'] / x['maxhp']; shown = SPR.shown(x['hp'], x['maxhp'])
            if (abs(pct - m['hp']) > 0.6) if sd == 'p1' else (shown != round(m['hp'])): hp.append(f"{sd} {x['sp']} hp {pct:.0f} vs {m['hp']:.0f}")
    return bad, hp
def reach(obs, states, exact='p1'):
    """each observed feature against every state the runs reached, one feature at a time: [discrete features no run reached], [HP outside
    every run's range]"""
    bad, hp = [], []
    def need(name, want, got):
        if want not in got: bad.append(f'{name}: {want} (runs: {sorted(map(str, got))[:4]})')
    need('weather', obs['field']['weather'], {WEATHER.get(s['field']['weather'], s['field']['weather']) or '' for s in states})
    need('terrain', obs['field']['terrain'], {(s['field']['terrain'].replace('terrain', '').capitalize() if s['field']['terrain'] else '') for s in states})
    need('trick room', obs['field']['tr'], {s['field']['tr'] for s in states})
    for sd in ('p1', 'p2'):
        o = obs['sides'][sd]
        need(f'{sd} tailwind', o['tailwind'], {s['sides'][sd]['tailwind'] for s in states})
        need(f'{sd} screens', tuple(o['screens']), {tuple(s['sides'][sd]['screens']) for s in states})
        for k, m in o['mons'].items():
            xs = [x for s in states for x in s['sides'][sd]['mons'] if toid(x['sp']) == k]
            if not xs: continue
            need(f'{sd} {k} fainted', bool(m['f']), {x['fnt'] for x in xs})
            if m['f']: continue
            alive = [x for x in xs if not x['fnt']]
            if not alive: continue
            need(f'{sd} {k} active', bool(m['pos']), {x['active'] for x in alive})
            need(f'{sd} {k} status', m['st'] or '', {x['status'] or '' for x in alive})
            if m['pos']:
                for stat in ('atk', 'def', 'spa', 'spd', 'spe'):
                    need(f'{sd} {k} {stat}', (m['b'] or {}).get(stat, 0), {x['boosts'].get(stat, 0) for x in alive if x['active']} or {0})
            pc = [100 * x['hp'] / x['maxhp'] for x in alive] if sd == exact else [SPR.shown(x['hp'], x['maxhp']) for x in alive]
            tol = 0.6 if sd == exact else 0
            if not (min(pc) - tol <= m['hp'] <= max(pc) + tol): hp.append(f"{sd} {k} hp {m['hp']:.0f} (runs {min(pc):.0f}-{max(pc):.0f})")
    return bad, hp
def revived(log, t):
    """{side: [species]} brought back by Revival Blessing in turn t, in order (the log heals them; no switch line)"""
    i = log.find(f'\n|turn|{t}\n'); out = {'p1': [], 'p2': []}
    if i < 0: return out
    j = log.find('\n|turn|', i + 1); nick = {}
    for l in log[:j if j > 0 else len(log)].split('\n'):
        p = l.split('|')
        if len(p) > 3 and p[1] in ('switch', 'drag', 'replace', 'poke') and ': ' in p[2]: nick[(p[2][:2], p[2].split(': ', 1)[1])] = p[3].split(',')[0]
    for l in log[i:j if j > 0 else len(log)].split('\n'):
        p = l.split('|')
        if len(p) > 3 and p[1] == '-heal' and 'Revival Blessing' in l and ': ' in p[2]: out[p[2][:2]].append(nick.get((p[2][:2], p[2].split(': ', 1)[1]), p[2].split(': ', 1)[1]))
    return out
def cases(f, seeds, bot=True):
    """bot: one of the bot's own logs (its side exact from its requests, Player 1); else a cached replay (both sides from the team sheets
    and the guessed spreads)"""
    room = os.path.basename(f)[:-4]; num = re.search(r'-(\d{6,})(?:-[a-z0-9]+)?$', room).group(1)
    lv = L.Live(room, 1, 0, logfile=f, tag='reach_' + num, fmt=''); lv.exact = bot
    log = L.bot_first(open(f).read()) if bot else open(f).read(); full = R.parse(log); steps = {s['turn']: s for s in full['steps']}
    out = []
    for t in sorted(steps):
        if t < 1 or t + 1 not in steps: continue                                  # the next turn's start is what is compared
        try: sp, H = lv.at(log, t, hindsight=True)
        except Exception as e: out.append({'game': num, 'turn': t, 'error': f'build: {e}'[:120]}); continue
        if not sp: continue
        cs, part = [], False                                                        # every hypothesis (sleep cases, an unseen back row), seeds shared out
        for w, spec in sorted(sp, key=lambda x: -x[0])[:6]:
            c1, p1 = choose(spec, 0); c2, p2 = choose(spec, 1); part = part or p1 or p2
            cs.append({'spec': spec, 'choose': {'p1': c1, 'p2': c2}, 'replace': spec.get('replace') or L.replacements(log, t), 'revive': revived(log, t), 'seeds': max(8, round(seeds * w))})
        out.append({'game': num, 'turn': t, 'cases': cs, 'partial': part, 'obs': observed(steps[t + 1]['state'], steps[t + 1]['state']), 'exact': 'p1' if bot else None})
    return out
def stamp(path, title, total, done0):
    """a progress card on the shared status page (localhost:8766, status.py): <path>.run.json, path counted in lines (one per game)"""
    json.dump({'title': title, 'out': os.path.relpath(path, os.path.join(C.HERE, 'out')), 'total': total, 'done0': done0, 'started': time.time(),
               'threads': 2, 'seeds': 0, 'staged': False}, open(path + '.run.json', 'w'))
def run(files, seeds, bot=True, out=None, title=None):
    """out: a .jsonl the rows are appended to as each game finishes (games already in it are skipped, so a run resumes); with title, a
    progress card (each worker is about 2 cores: this process and its Showdown child)"""
    os.makedirs(OUT, exist_ok=True); rows = []
    done = {json.loads(l)['game'] for l in open(out)} if out and os.path.exists(out) else set()
    prog = out[:-6] + '.games' if out else None
    if prog and title:
        open(prog, 'w').writelines(g + '\n' for g in sorted(done)); stamp(prog, title, len(files), len(done))
    for f in files:
        if re.search(r'-(\d{6,})', os.path.basename(f)).group(1) in done: continue
        try: cs = cases(f, seeds, bot)
        except Exception as e: cs = [{'game': re.search(r'-(\d{6,})', os.path.basename(f)).group(1), 'turn': 0, 'error': f'game: {e}'[:120]}]
        todo = [c for c in cs if 'cases' in c]; new = [c for c in cs if 'error' in c]
        if not todo: rows += new; continue
        tag = f'{os.getpid()}'; qf, of = os.path.join(OUT, f'q{tag}.json'), os.path.join(OUT, f'r{tag}.json'); json.dump([x for c in todo for x in c['cases']], open(qf, 'w'))
        subprocess.run([P.exe('node'), os.path.join(C.HERE, 'reach.js'), qf, of], cwd=os.path.join(C.MAIN, 'pssim'), check=True)
        res = iter(json.load(open(of)))
        for c in todo:
            rs = [next(res) for _ in c['cases']]
            row = {'game': c['game'], 'turn': c['turn'], 'partial': c['partial'], 'choose': c['cases'][0]['choose'], 'replace': c['cases'][0]['replace']}
            if all(r.get('error') for r in rs): row['error'] = rs[0]['error']; new.append(row); continue
            st = [s for r in rs for s in r.get('states', []) if s.get('turnDone')]
            if not st: row['error'] = 'the turn did not finish'; rows.append(row); continue
            bad, hp = reach(c['obs'], st, c['exact']); row['n'] = len(st); row['unreached'] = bad; row['hp'] = hp
            new.append(row)
        rows += new
        if out:
            with open(out, 'a') as fh: fh.writelines(json.dumps(r) + '\n' for r in (new or [{'game': todo[0]['game'], 'turn': 0, 'empty': True}]))
            if prog:
                with open(prog, 'a') as fh: fh.write(todo[0]['game'] + '\n')
    return rows
if __name__ == '__main__':
    P.own(); L.evalbar_mode()
    a = sys.argv[1:]; seeds = next((int(x[6:]) for x in a if x.startswith('seeds=')), 32); n = next((int(x) for x in a if x.isdigit()), None)
    if a and a[0] == 'recheck':                                                 # recheck <file.jsonl>: its unreached turns again
        f = a[1]; rows = [json.loads(l) for l in open(f)]
        bad = collections.defaultdict(set)
        for r in rows:
            if r.get('unreached'): bad[r['game']].add(r['turn'])
        rid = {x.split('-')[-1]: x for x, _ in C.games()}; fixed = {}
        prog = f[:-6] + '.recheck'; open(prog, 'w').close(); stamp(prog, f'Reachability check: recheck of {os.path.basename(f)} (games)', len(bad), 0)
        for g, ts in bad.items():
            with open(prog, 'a') as fh: fh.write(g + '\n')
            cs = [c for c in cases(os.path.join(C.LOGS, rid[g] + '.log'), seeds, bot=False) if c['turn'] in ts and 'cases' in c]
            if not cs: continue
            qf, of = os.path.join(OUT, f'q{os.getpid()}.json'), os.path.join(OUT, f'r{os.getpid()}.json'); json.dump([x for c in cs for x in c['cases']], open(qf, 'w'))
            subprocess.run([P.exe('node'), os.path.join(C.HERE, 'reach.js'), qf, of], cwd=os.path.join(C.MAIN, 'pssim'), check=True)
            res = iter(json.load(open(of)))
            for c in cs:
                st = [s for r in [next(res) for _ in c['cases']] for s in r.get('states', []) if s.get('turnDone')]
                if st: b_, h_ = reach(c['obs'], st, c['exact']); fixed[(g, c['turn'])] = (b_, h_, c['partial'])
        out = []
        for r in rows:
            if (r['game'], r['turn']) in fixed: r['unreached'], r['hp'], r['partial'] = fixed[(r['game'], r['turn'])]
            out.append(r)
        open(f, 'w').writelines(json.dumps(r) + '\n' for r in out)
        sys.exit(print(f'{f}: {len(fixed)} turns rechecked, {sum(1 for v in fixed.values() if v[0])} still unreached'))
    if a and a[0] == 'replays':                                                 # replays k/n: the k-th of n shares of the cached Bo3 replays
        k, m = map(int, a[1].split('/'))
        files = sorted(os.path.join(C.LOGS, rid + '.log') for rid, _ in C.games() if 'regmcbo3' in rid)[k::m]
        rows = run(files, seeds, bot=False, out=os.path.join(OUT, f'replays_{k}of{m}.jsonl'), title=f'Reachability check: replays, share {k + 1} of {m} (games)')
        sys.exit(print(f'share {k}/{m}: {len(rows)} new rows'))
    files = sorted((f for f in glob.glob(os.path.join(C.MAIN, 'bot', 'out', 'battle-*bo3-*.log')) if re.search(r'-\d{6,}(-[a-z0-9]+)?\.log$', f)), key=os.path.getmtime)
    rows = run(files[:n] if n else files, seeds)
    json.dump(rows, open(os.path.join(OUT, 'report.json'), 'w'), indent=0)
    ok = [r for r in rows if 'unreached' in r]; bad = [r for r in ok if r['unreached']]; hp = [r for r in ok if not r['unreached'] and r['hp']]
    print(f"{len(rows)} turns: {len(ok) - len(bad) - len(hp)} reached, {len(hp)} only HP out of range, {len(bad)} with a feature no run reached, {len(rows) - len(ok)} errors")
    why = collections.Counter(re.sub(r'^(p[12]) \S+ ', r'\1 X ', x.split(':')[0]) for r in bad for x in r['unreached'])
    print('features no run reached:', why.most_common(15))
