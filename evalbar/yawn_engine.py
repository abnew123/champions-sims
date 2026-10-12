"""The engine on the human Yawn decisions (yawn_study.py): at the start of the turn after each Yawn the drowsy Pokemon could switch out of,
how much of the engine's mix takes it off the field (a switch, or its own U-turn, Parting Shot and the like), against what the player did.
The position is the deciding player's view: their own four exact (the Pokemon they brought, from the whole game), the opponent's back row
as a spectator would guess it, each sleeping Pokemon split by its sleep counter (live.py). The user's idea (2026-10-12): the engine in the
humans' own positions, rather than self-play.
  python3 evalbar/yawn_engine.py build              positions -> evalbar/out/yawn/pos.jsonl
  python3 evalbar/yawn_engine.py run [threads=1]     the engine (resumes) -> evalbar/out/yawn/eval.jsonl
  python3 evalbar/yawn_engine.py report             -> evalbar/yawn_engine.json"""
import os, re, sys, json, math, collections
import common as C, replay as R, live as L, yawn_study as Y, engine as EN, procs as P
OUT = os.path.join(C.HERE, 'out', 'yawn'); POS = os.path.join(OUT, 'pos.jsonl'); EV = os.path.join(OUT, 'eval.jsonl'); W = os.path.join(OUT, 'weights.json')
toid = R.toid
def decisions():
    """[(replay id, turn, side, species, what the player did)] for each Yawn the player could have switched out of"""
    out = []
    for rid, log in C.games():
        if 'Yawn' not in log: continue
        for sd, kind, res, rt, t, sp in Y.study(log):
            if res in ('no bench', 'trapped', 'forced'): continue
            out.append((rid, t, sd, sp, res, rt))
    return out
def specs(rid, log, t, sd):
    """engine position specs for turn t from side sd's view: [(weight, spec)]"""
    lv = L.Live(None, 1, 0, logfile=os.path.join(C.LOGS, rid + '.log'), tag='yawn', fmt='')
    pre = lv.upto(log, t); gp = R.parse(pre); step = next(x for x in gp['steps'] if x['turn'] == t)
    full = next(x for x in R.parse(log)['steps'] if x['turn'] == t)
    st = json.loads(json.dumps(step['state'])); st[sd] = full['state'][sd]           # their own side with hindsight: all four they brought
    step = {**step, 'state': st, 'acts': full['acts']}
    six, sets, dropped = L.sets_for(gp, pre, True)
    sp, H = L.specs_for(f"y{rid.split('-')[-1]}{sd}", gp, step, six, sets, lv.leads(pre))
    return L.sleep_cases(sp)
def build():
    os.makedirs(OUT, exist_ok=True); allsp = []; weights = {}; logs = dict(C.games()); skipped = collections.Counter()
    for rid, t, sd, sp, res, rt in decisions():
        try: ss = specs(rid, logs[rid], t, sd)
        except Exception as e: skipped[type(e).__name__] += 1; continue
        if not ss: skipped['no positions'] += 1; continue
        key = f'{rid} {t} {sd}'
        if key in weights: continue                                         # two drowsy Pokemon on one side: one position
        weights[key] = {x['name'] + ' p1': w for w, x in ss}; allsp += ss
    json.dump(weights, open(W, 'w'))
    L.positions(allsp, POS)
    print(f'{len(weights)} decisions, {len(allsp)} positions; skipped {dict(skipped) or "none"}')
def run(threads):
    os.environ['EVAL_TITLE'] = 'Yawn decisions: the engine in the human positions'
    EN.run(POS, EV, threads, 32, 1, extra={'CALC_DATA': '../native/champions_data_full.json'}, nice=10)
PIVOT = Y.PIVOT
def share(e, s, sp):
    """the engine's mix on side s for the slot holding species sp: (share that leaves the field, best value leaving, best value staying)"""
    sl = next((x for x in e['sides'][s]['slots'] if toid(x['mon']) == toid(sp)), None) or \
         next((x for x in e['sides'][s]['slots'] if toid(x['mon']).startswith(toid(sp.split('-')[0]))), None)
    if not sl: return None
    leave = lambda o: o['c'][0] == 'switch' or toid(o['label'].split(' -> ')[0].replace(' (Mega)', '')) in PIVOT
    lv = [o for o in sl['options'] if leave(o)]; st = [o for o in sl['options'] if not leave(o)]
    if not lv: return None                                                  # no way out in the engine's position
    return sum(o['w'] for o in lv), max(o['v'] for o in lv), max((o['v'] for o in st), default=None)
def report():
    ev = L.records(EV); weights = json.load(open(W)); dec = decisions(); rows = []
    sc = lambda v: C.sig(L.CAL * math.log(min(1 - 1e-4, max(1e-4, v)) / (1 - min(1 - 1e-4, max(1e-4, v)))))
    for rid, t, sd, sp, res, rt in dec:
        ws = weights.get(f'{rid} {t} {sd}')
        if not ws or not all(n in ev for n in ws): continue
        s = 0 if sd == 'p1' else 1; got = [(w, share(ev[n], s, sp)) for n, w in ws.items()]
        if any(g is None for _, g in got): continue
        rows.append({'id': rid, 'turn': t, 'side': sd, 'species': sp, 'rating': rt, 'human_left': res in ('switched', 'pivot'), 'human': res,
                     'engine_left': sum(w * g[0] for w, g in got),
                     'gain': sum(w * (sc(g[1]) - sc(g[2])) for w, g in got if g[2] is not None)})
    n = len(rows)
    if not n: return print('nothing evaluated yet')
    hl = sum(r['human_left'] for r in rows) / n; el = sum(r['engine_left'] for r in rows) / n
    agree = sum((r['engine_left'] >= 0.5) == r['human_left'] for r in rows) / n
    by = collections.defaultdict(list)
    for r in rows: by[r['species']].append(r)
    out = {'decisions': n, 'human_left': round(hl, 3), 'engine_left': round(el, 3), 'agree': round(agree, 3),
           'engine_left_when_human_left': round(sum(r['engine_left'] for r in rows if r['human_left']) / max(1, sum(r['human_left'] for r in rows)), 3),
           'engine_left_when_human_stayed': round(sum(r['engine_left'] for r in rows if not r['human_left']) / max(1, sum(not r['human_left'] for r in rows)), 3),
           'by_species': {k: {'n': len(v), 'human_left': round(sum(r['human_left'] for r in v) / len(v), 2), 'engine_left': round(sum(r['engine_left'] for r in v) / len(v), 2)}
                          for k, v in sorted(by.items(), key=lambda kv: -len(kv[1])) if len(v) >= 8},
           'rows': rows}
    json.dump(out, open(os.path.join(C.HERE, 'yawn_engine.json'), 'w'), indent=1)
    print({k: v for k, v in out.items() if k != 'rows'})
if __name__ == '__main__':
    P.own()
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == 'build': build()
    elif a[0] == 'run': run(int(a[1]) if len(a) > 1 else 1)
    elif a[0] == 'report': report()
