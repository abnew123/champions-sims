"""Mega data check (the user asked, 2026-10-12, after Mega Lucario Z turned out to have Aura Guard, not Adaptability): every hit in the
cached Reg M-C replays that a Mega gave or took, its observed damage against what our data predicts (damage.js, the most used spreads),
split by the Mega's own-type moves, its other moves and the hits it took (contact or not, physical or special). Hits between non-Megas
(a sample) give the baseline, since guessed spreads skew every ratio a little. A Mega whose ratio in one class stands apart from the
baseline has suspect data (an ability, a stat, a type).
  python3 evalbar/mega_check.py run k/n        share k of n of the replays -> out/megacheck/part_k_of_n.jsonl (resumable, a progress card)
  python3 evalbar/mega_check.py report         -> evalbar/mega_check.json and a table"""
import os, re, sys, json, time, glob, random, statistics, subprocess, collections
import common as C, live as L, replay as R, spreads as SPR, procs as P
OUT = os.path.join(C.HERE, 'out', 'megacheck'); E = SPR.E
toid = R.toid
def hits(rid, log, sample=0.1):
    """this game's clean hits with a Mega in them (and about one in ten without, for the baseline): [(query, meta)]"""
    full = R.parse(log); steps = {s['turn']: s for s in full['steps'] if s.get('state')}
    six, sets, dropped = L.sets_for(full, log, True); leads = L.Live.leads(None, log)
    obs = []
    for ks in ('p1', 'p2'):                                                   # each side in turn as the 'known' one: hits on the other in percent
        for o in SPR.damage_observations(log, ks, 2):
            if o['def'][:2] == ks or o['crit'] or o['atleast'] or 'pct' not in o or o['pct'][1] == 0: continue
            if o['hp'].get('att') and o['hp']['att'][0] == 'abs': o['hp']['att'] = ['pct', o['hp']['att'][1]]
            obs.append(o)
    out = []; rng = random.Random(rid)
    for t in sorted({o['turn'] for o in obs}):
        if t not in steps: continue
        st = steps[t]['state']
        try: sp, H = L.specs_for('mc', full, {**steps[t], 'acts': {}}, six, sets, leads)
        except Exception: continue
        if not sp: continue
        spec = max(sp, key=lambda x: x[0])[1]
        order = {sd: sorted(st[sd]['mons'], key=lambda m: (0 if m['pos'] == 'a' else 1 if m['pos'] == 'b' else 2 if not m['f'] else 3)) for sd in ('p1', 'p2')}
        def slot(pos):
            sd = pos[:2]; return next(([0 if sd == 'p1' else 1, i] for i, m in enumerate(order[sd]) if m['pos'] == pos[2] and not m['f']), None)
        for o in (o for o in obs if o['turn'] == t):
            a, d = slot(o['att']), slot(o['def'])
            if not a or not d: continue
            s2 = json.loads(json.dumps(spec)); am, dm = s2['sides'][a[0]]['mons'][a[1]], s2['sides'][d[0]]['mons'][d[1]]
            for pos, m in ((o['att'], am), (o['def'], dm)):
                if pos in o['megas']: m['mega'] = True
                for k_, v_ in ((o.get('boosts') or {}).get(pos) or {}).items(): m.setdefault('boosts', {}); m['boosts'][k_] = max(-6, min(6, m['boosts'].get(k_, 0) + v_))
            if o.get('weather'): s2['field']['weather'] = [SPR.SD_WEATHER[o['weather']], 5] if SPR.SD_WEATHER[o['weather']] else None
            mega = lambda m: (SPR.mega_of(m['species'], m.get('item', '')) if m.get('mega') else None)
            amega, dmega = mega(am), mega(dm)
            if not amega and not dmega and rng.random() > sample: continue
            mv = E['moves'].get(toid(o['move'])) or {}
            if mv.get('category') not in ('Physical', 'Special'): continue
            aform = amega or am['species']; atypes = (E['species'].get(toid(aform)) or {}).get('types') or []
            q = {'spec': s2, 'att': a, 'def': d, 'move': o['move'], 'crit': False, 'spread': o['spread'], 'helping': o['helping'], 'hp': o['hp'], 'strict': 2}
            out.append((q, {'game': rid.split('-')[-1], 'turn': t, 'att': aform, 'amega': bool(amega), 'def': dmega or dm['species'], 'dmega': bool(dmega),
                            'abase': am['species'], 'anat': am.get('nature'), 'dbase': dm['species'], 'dnat': dm.get('nature'),
                            'move': o['move'], 'cat': mv['category'], 'type': mv.get('type'), 'stab': mv.get('type') in atypes,
                            'contact': bool((mv.get('flags') or {}).get('contact')), 'pct': o['pct']}))
    return out
def run(k, n):
    os.makedirs(OUT, exist_ok=True); part = os.path.join(OUT, f'part_{k}_of_{n}.jsonl'); prog = part[:-6] + '.games'
    games = sorted(rid for rid, _ in C.games() if 'regmcbo3' in rid)[k::n]
    done = {l.strip() for l in open(prog)} if os.path.exists(prog) else set()
    json.dump({'title': f'Mega data check: replays, share {k + 1} of {n} (games)', 'out': os.path.relpath(prog, os.path.join(C.HERE, 'out')), 'total': len(games),
               'done0': len(done), 'started': time.time(), 'threads': 2, 'seeds': 0, 'staged': False}, open(prog + '.run.json', 'w'))
    qf, of = os.path.join(OUT, f'q{os.getpid()}.json'), os.path.join(OUT, f'r{os.getpid()}.json')
    for rid in games:
        if rid in done: continue
        rows = []
        try:
            hs = hits(rid, open(os.path.join(C.LOGS, rid + '.log')).read())
            if hs:
                json.dump([q for q, _ in hs], open(qf, 'w'))
                subprocess.run([P.exe('node'), os.path.join(C.HERE, 'damage.js'), qf, of], cwd=os.path.join(C.MAIN, 'pssim'), check=True, capture_output=True)
                for (_, m), r in zip(hs, json.load(open(of))):
                    if r and r.get('lo') is not None and r.get('maxhp'): rows.append({**m, 'lo': r['lo'], 'hi': r['hi'], 'maxhp': r['maxhp']})
        except Exception as e: rows = [{'game': rid.split('-')[-1], 'error': str(e)[:120]}]
        with open(part, 'a') as fh: fh.writelines(json.dumps(r) + '\n' for r in rows)
        with open(prog, 'a') as fh: fh.write(rid + '\n')
def ratio(r):
    lo, hi = 100 * r['lo'] / r['maxhp'], 100 * r['hi'] / r['maxhp']
    return (r['pct'][0] - r['pct'][1]) / ((lo + hi) / 2) if hi > 0 else None
def report():
    rows = [json.loads(l) for f in glob.glob(os.path.join(OUT, 'part_*.jsonl')) for l in open(f)]
    rows = [r for r in rows if 'lo' in r and ratio(r) is not None and r['pct'][0] - r['pct'][1] > 3]
    groups = collections.defaultdict(list)
    for r in rows:
        x = ratio(r)
        if not r['amega'] and not r['dmega']: groups[('baseline', 'gives', r['cat'], 'STAB' if r['stab'] else 'other')].append(x); groups[('baseline', 'takes', r['cat'], 'contact' if r['contact'] else 'no contact')].append(x)
        if r['amega']: groups[(r['att'], 'gives', r['cat'], 'STAB' if r['stab'] else 'other')].append(x)
        if r['dmega']: groups[(r['def'], 'takes', r['cat'], 'contact' if r['contact'] else 'no contact')].append(x)
    base = {k[1:]: statistics.median(v) for k, v in groups.items() if k[0] == 'baseline' and len(v) >= 20}
    out = []
    for k, v in groups.items():
        if k[0] == 'baseline' or len(v) < 12: continue
        med = statistics.median(v); b = base.get(k[1:])
        out.append({'mega': k[0], 'side': k[1], 'cat': k[2], 'kind': k[3], 'n': len(v), 'median': round(med, 3), 'baseline': round(b, 3) if b else None,
                    'rel': round(med / b, 3) if b else None, 'q1': round(statistics.quantiles(v, n=4)[0], 3), 'q3': round(statistics.quantiles(v, n=4)[2], 3)})
    out.sort(key=lambda x: -abs(math_log(x['rel'] or 1)))
    json.dump({'rows': len(rows), 'baseline': {' '.join(k): round(v, 3) for k, v in base.items()}, 'groups': out}, open(os.path.join(C.HERE, 'mega_check.json'), 'w'), indent=0)
    print(len(rows), 'hits; baseline medians:', {' '.join(k): round(v, 3) for k, v in base.items()})
    for x in out[:40]: print(f"  {x['mega']:22s} {x['side']:5s} {x['cat']:8s} {x['kind']:10s} n={x['n']:4d}  median {x['median']:.2f}  vs baseline {x['baseline']}  -> {x['rel']}")
def math_log(x):
    import math; return math.log(max(1e-3, x))
if __name__ == '__main__':
    P.own(); R.BATON_PASS = True
    a = sys.argv[1:]
    if a and a[0] == 'run': k, n = map(int, a[1].split('/')); run(k, n)
    elif a and a[0] == 'report': report()
    else: sys.exit(__doc__)
