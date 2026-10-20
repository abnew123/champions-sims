"""The bot's own games against people (the user, 2026-10-20: "is the bot consistently missing certain lines, or overestimating how often
its human opponent will do certain things"), Bo1 and Bo3 apart. Read from the bot page's luck pass: every turn of every bot game as a
payoff table in hindsight (both sides' Pokemon as the game showed them; the table's rows are the bot's joint actions, its columns the
opponent's, each cell the bot's win chance after the turn), with the engine's equilibrium mixes and what each side played. Values are
rescaled with each engine's CAL (live.CALS); the bot is Player 1 in these files (live.bot_first).
  predicted    how often the opponent chose each kind of play (diverge.kind), against the engine's mix for the same slots: a kind the
               engine expects more often than people choose it is one the bot overestimates
  missed       for each kind of play the bot had, its best option of that kind by the engine's own reckoning (chosen without knowing what
               the opponent did), scored against the opponent's actual choice, less the bot's own choice scored the same way, and the same
               two against the engine's predicted mix. excess = actual - expected: what people's real choices add to that kind beyond the
               engine's model. Above 0, consistently: a line the bot misses against people
  turn 1       the bot's rated chance at its first turn (in hindsight: both sides' brought Pokemon known) against how often it won; in Bo3
               by game of the match too
  results      the bot's own choices by kind: its rated chance less how often it won, against what the engine says each choice cost
               (diverge.residuals). Every game counts, its forfeits too: the bot resigns positions it judges lost (about 4 games in 10),
               so leaving them out would keep only the games it went on to win more often. The bot's choices follow the engine, so the
               claimed costs are small and a kind's residual mostly says whether the engine rates the positions where the bot makes that
               choice right
usage (numpy: the main folder's .venv): python3 evalbar/botstudy.py [--fmt bo1|bo3]   writes evalbar/results/botstudy.json"""
import os, sys, json, re, math, glob, bisect, collections, argparse
import numpy as np
import common as C, procs as P, diverge as D
OUT = os.path.join(C.HERE, 'out', 'live'); BOT = os.path.join(C.MAIN, 'bot', 'out')
sys.path.insert(0, os.path.join(C.MAIN, 'bot'))
HM = json.load(open(os.path.join(BOT, 'contempt', 'human_model.json')))   # the Bo3 bot's model of people (position.CONTEMPT_MODEL)
CALS = {'': 0.7538, '_v31': 0.782, '_v34': 0.785}                        # live.CALS by file suffix (v25, v31, v34)
sig = lambda x: 1 / (1 + math.exp(-x))
logit = lambda v: math.log(min(1 - 1e-4, max(1e-4, v)) / (1 - min(1 - 1e-4, max(1e-4, v))))
def games():
    """{battle number: (room, bot won, format, the bot forfeited)} for the bot's ladder games; the forfeit read from the log's -message
    line by comparing the name in it with the bot's own player name (names are compared, never kept)"""
    out = {}
    for l in open(os.path.join(BOT, 'games.jsonl')):
        try: g = json.loads(l)
        except ValueError: continue
        m = re.search(r'-(\d+)(?:-[a-z0-9]+)?$', g.get('room', ''))
        if not m or 'won' not in g: continue
        f = os.path.join(BOT, g['room'] + '.log'); ff = False
        if os.path.exists(f):
            me = None
            for line in open(f, errors='replace'):
                if line.startswith(('|c|', '|c:|', '|chat|', '|raw|', '|html|', '|uhtml|')): continue
                p = line.rstrip('\n').split('|')
                if len(p) > 3 and p[1] == 'player' and p[2] == g['side'] and p[3]: me = p[3]
                elif len(p) > 2 and p[1] == '-message' and p[2].endswith(' forfeited.') and me and p[2][:-len(' forfeited.')] == me: ff = True
        out[m.group(1)] = (g['room'], bool(g['won']), 'bo3' if 'bo3' in g['room'] else 'bo1', ff)
    return out
def game_numbers():
    """{battle number: its game number in its Bo3 match}: each game goes to the first match that ended after it (bot/out/matches.jsonl),
    in order of ending (a match's game rooms are not numbered in a row)"""
    ends = []
    for l in open(os.path.join(BOT, 'matches.jsonl')):
        try: m = json.loads(l)
        except ValueError: continue
        if 'bo3' in m.get('room', ''): ends.append(m['when'])
    ends.sort(); by = collections.defaultdict(list)
    for l in open(os.path.join(BOT, 'games.jsonl')):
        try: g = json.loads(l)
        except ValueError: continue
        mm = re.search(r'-(\d+)(?:-[a-z0-9]+)?$', g.get('room', ''))
        if mm and 'bo3' in g['room']:
            i = bisect.bisect_left(ends, g['when'])
            if i < len(ends): by[i].append((g['when'], mm.group(1)))
    return {num: k + 1 for xs in by.values() for k, (_, num) in enumerate(sorted(xs))}
def records(num):
    """the luck pass's lines of one game: {turn: [(line, CAL)]}, each turn from the newest engine that read all of it"""
    by = {}
    for suf in ('', '_v31', '_v34'):                                    # oldest first: a newer engine's turn replaces an older one's
        f = os.path.join(OUT, f'bot_{num}_luck{suf}.jsonl')
        if not os.path.exists(f): continue
        t_lines = collections.defaultdict(list)
        for l in open(f):
            try: d = json.loads(l)
            except ValueError: continue
            if d.get('matrix') and 'sides' in d: t_lines[d['turn']].append((d, CALS[suf]))
        by.update(t_lines)
    return by
def acts(side):
    """{engine slot: (options, the options marked as played)} for a side of a luck line"""
    return {sl['slot']: (sl['options'], [o for o in sl['options'] if o.get('actual')]) for sl in side['slots']}
def turn_rows(d, cal, M):
    """the measures of one luck line: predicted (opponent), missed and results rows (bot)"""
    R = lambda v: sig(cal * logit(v)); m = d['matrix']; key = lambda c: json.dumps(c)
    V = np.vectorize(R)(np.array([[x if x is not None else np.nan for x in row] for row in m['v1']], float))
    y = np.array(m['y'], float); y = y / (y.sum() or 1)
    bot, opp = acts(d['sides'][0]), acts(d['sides'][1])
    pred = []
    for s_, (opts, played) in opp.items():                              # the opponent's choices against the engine's mix
        if not played or len(opts) < 2: continue
        tot = sum(o['w'] for o in opts) or 1; kw = collections.Counter()
        for o in opts: kw[D.kind(o['label'], o['c'], M)] += o['w'] / tot
        import exploit_test as XT                                       # the bot's human model: its chance of each option
        hk = collections.Counter()
        for o, q in zip(opts, XT.probs([(o['label'], o['w'] / tot, o['v']) for o in opts], HM)): hk[D.kind(o['label'], o['c'], M)] += q
        pred.append({'k': D.kind(played[0]['label'], played[0]['c'], M), 'kw': dict(kw), 'hk': dict(hk), 'mega': played[0]['label'].endswith('(Mega)') if any(o['label'].endswith('(Mega)') for o in opts) else None,
                     'mega_w': sum(o['w'] for o in opts if o['label'].endswith('(Mega)')) / tot})
    # the opponent's actual columns: every column that agrees with each opponent slot's played option(s) (a slot not shown: any)
    def match(entries, side_acts):
        ok = []
        for i, e in enumerate(entries):
            if all(not pl or e[s_] is None or any(key(e[s_]) == key(o['c']) for o in pl) for s_, (_, pl) in side_acts.items()): ok.append(i)
        return ok
    cols = match(m['cols'], opp)
    if not cols or any(not pl for s_, (opts, pl) in opp.items() if len(opts) > 1): cols = None   # an opponent slot's choice unknown: no actual
    rix = collections.defaultdict(list)
    for i, r in enumerate(m['rows']): rix[(key(r[0]), key(r[1]))].append(i)
    missed = []; res = []; own = []
    for s_, (opts, played) in bot.items():
        if not played or len(opts) < 2: continue
        j = 1 - s_; partner = bot.get(j, (None, []))[1]
        pk = [key(o['c']) for o in partner] or [key(None)]
        def val(o):
            rs = [i for p in pk for i in rix.get((key(o['c']), p) if s_ == 0 else (p, key(o['c'])), [])]
            if not rs: return None, None
            sub = V[rs]
            vy = float(np.nanmean(sub @ y)) if not np.isnan(sub).any() else float(np.nanmean(np.nansum(sub * y, 1)))
            va = float(np.nanmean(sub[:, cols])) if cols else None
            return va, vy
        a = played[0]; va_a, vy_a = val(a)
        if vy_a is None: continue
        if cols and va_a is not None: own.append(va_a - vy_a)            # the bot's own line against people's actual play, less the model's
        best = {}
        for o in opts:
            va, vy = val(o)
            if vy is None: continue
            k = D.kind(o['label'], o['c'], M)
            for kk in [k] + (['Mega Evolves now' if o['label'].endswith('(Mega)') else 'holds the Mega'] if any(x['label'].endswith('(Mega)') for x in opts) else []):
                if kk not in best or vy > best[kk][1]: best[kk] = (va, vy, o['label'])
        ka = D.kind(a['label'], a['c'], M)
        for kk, (va, vy, lab) in best.items():
            missed.append({'k': kk, 'played_kind': ka, 'same': lab == a['label'], 'model': vy - vy_a,
                           'actual': (va - va_a) if cols and va is not None and va_a is not None else None})
        tot = sum(o['w'] for o in opts) or 1; kw = collections.Counter()
        for o in opts: kw[D.kind(o['label'], o['c'], M)] += o['w'] / tot
        res.append({'k': ka, 'claimed': sum(o['w'] * R(o['v']) for o in opts) / tot - R(a['v']), 'mega': a['label'].endswith('(Mega)') if any(o['label'].endswith('(Mega)') for o in opts) else None,
                    'mega_share': sum(o['w'] for o in opts if o['label'].endswith('(Mega)')) / tot,
                    'kw': dict(kw)})
    return pred, missed, res, own
def collect(fmt=None):
    M = json.load(open(os.path.join(C.MAIN, 'native', 'engine_data_full.json')))['moves']
    G = games(); P_, MI, RS, OW = [], [], [], []
    for num, (room, won, f, ff) in G.items():
        if fmt and f != fmt: continue
        for t, lines in records(num).items():
            w = 1 / len(lines)                                          # the turn's back-row guesses, equally
            for d, cal in lines:
                try: pred, missed, res, own = turn_rows(d, cal, M)
                except Exception: continue
                Vbot = sig(cal * logit(d['value']))
                for r in pred: P_.append({**r, 'g': num, 'f': f, 'w': w})
                for r in missed: MI.append({**r, 'g': num, 'f': f, 'w': w})
                for r in res: RS.append({**r, 'g': num, 'f': f, 'w': w, 'V': Vbot, 'y': 1.0 if won else 0.0, 'forfeit': ff, 't': t})
                for x in own: OW.append({'g': num, 'f': f, 'w': w, 'x': x})
    return G, P_, MI, RS, OW
def boot_mean(vals, gs, ws, B=500, seed=1):
    vals, ws = np.asarray(vals, float), np.asarray(ws, float)
    if not len(vals): return float('nan'), float('nan')
    gg, inv = np.unique(np.asarray(gs), return_inverse=True); S = np.bincount(inv, vals * ws); W = np.bincount(inv, ws)
    pick = np.random.default_rng(seed).integers(0, len(gg), (B, len(gg)))
    return float(S.sum() / W.sum()), float(np.std(S[pick].sum(1) / W[pick].sum(1)))
def report(G, P_, MI, RS, OW, fmt_label):
    out = {'format': fmt_label, 'games': len({r['g'] for r in P_ + MI + RS})}
    print(f"\n== {fmt_label}: {out['games']} games read")
    # predicted: per kind, the opponent's share against the engine's
    N = sum(r['w'] for r in P_); act = collections.Counter(); eng = collections.Counter(); hm = collections.Counter()
    for r in P_:
        act[r['k']] += r['w']
        for k, x in r['kw'].items(): eng[k] += r['w'] * x
        for k, x in r['hk'].items(): hm[k] += r['w'] * x
    rows = []
    for k in sorted(set(act) | set(eng), key=lambda k: -(act[k] + eng[k])):
        if act[k] + eng[k] < 0.004 * N: continue
        diff = [(r['k'] == k) - r['kw'].get(k, 0) for r in P_]
        m, se = boot_mean(diff, [r['g'] for r in P_], [r['w'] for r in P_])
        rows.append({'kind': k, 'people': act[k] / N, 'engine': eng[k] / N, 'human_model': hm[k] / N, 'diff': m, 'se': se})
    mg = [r for r in P_ if r['mega'] is not None]
    if mg:
        m, se = boot_mean([(1.0 if r['mega'] else 0.0) - r['mega_w'] for r in mg], [r['g'] for r in mg], [r['w'] for r in mg])
        sw = sum(r['w'] for r in mg)
        rows.append({'kind': 'Mega Evolves now (of slots that can)', 'people': sum(r['w'] for r in mg if r['mega']) / sw, 'engine': sum(r['w'] * r['mega_w'] for r in mg) / sw, 'diff': m, 'se': se})
    out['predicted'] = rows
    print(f"the opponent's choices: {N:.0f} slot decisions | kind, people, engine, people - engine, the bot's human model (Bo3 contempt)")
    for x in rows: print(f"  {x['kind'][:44]:44s} {100 * x['people']:5.1f}% {100 * x['engine']:5.1f}%   {100 * x['diff']:+5.1f} ± {100 * x['se']:.1f}"
                         + (f"   {100 * x['human_model']:5.1f}%" if 'human_model' in x else ''))
    # missed: per kind the bot had, model and actual gaps of its best option of that kind, against its own choice
    rows = []
    by = collections.defaultdict(list)
    for r in MI:
        if r['actual'] is not None and not r['same']: by[r['k']].append(r)
    for k, xs in by.items():
        if len(xs) < 30: continue
        gs, ws = [r['g'] for r in xs], [r['w'] for r in xs]
        mm, mse = boot_mean([r['model'] for r in xs], gs, ws); am, ase = boot_mean([r['actual'] for r in xs], gs, ws)
        em, ese = boot_mean([r['actual'] - r['model'] for r in xs], gs, ws)
        rows.append({'kind': k, 'n': len(xs), 'model': mm, 'actual': am, 'excess': em, 'excess_se': ese})
    rows.sort(key=lambda x: -x['excess']); out['missed'] = rows
    if OW:
        m, se = boot_mean([r['x'] for r in OW], [r['g'] for r in OW], [r['w'] for r in OW]); out['own_line'] = {'mean': m, 'se': se, 'n': len(OW)}
        print(f"the bot's own choice against people's actual play, less against the engine's predicted mix: {100 * m:+.2f} ± {100 * se:.2f} points ({len(OW)} decisions)")
    print("lines the bot did not play: its best option of each kind (when it played something else), against the opponent's actual choice\n"
          "  and against the engine's predicted mix, less its own choice; points | kind, n, expected, actual, excess")
    for x in rows: print(f"  {x['kind'][:44]:44s} {x['n']:6d} {100 * x['model']:+6.2f} {100 * x['actual']:+6.2f}   {100 * x['excess']:+5.2f} ± {100 * x['excess_se']:.2f}")
    # results: the bot's own choices against who won, without its forfeits
    rs = RS
    if len(rs) > 200:
        rr = [{'g': r['g'], 'k': r['k'], 'mega': r['mega'], 'mega_share': r['mega_share'], 'claimed': r['claimed'], 'V': r['V'], 'y': r['y'], 'kw': r['kw']} for r in rs]
        fit, T = D.residuals(rr)
        T = [x for x in T if x['n'] >= 100]
        out['results'] = {'fit': fit, 'kinds': T, 'forfeited': len({r['g'] for r in RS if r['forfeit']})}
        print(f"the bot's own choices against results ({len({r['g'] for r in rs})} games, {out['results']['forfeited']} of them forfeited by the bot): "
              f"realized = {100 * fit['a']:.2f} + {fit['b']:.2f} x claimed | kind, n, claimed, better (-) / worse (+) than expected")
        for x in T: print(f"  {x['kind'][:44]:44s} {x['n']:6d} {100 * x['claimed']:6.2f}   {100 * x['residual']:+6.2f} ± {100 * x['residual_se']:.2f}")
        t1 = {}
        for r in rs:
            if r['t'] == 1: t1.setdefault(r['g'], (r['V'], r['y']))
        if t1:
            v, yv = np.array([x[0] for x in t1.values()]), np.array([x[1] for x in t1.values()])
            out['turn1'] = {'games': len(t1), 'rated': float(v.mean()), 'won': float(yv.mean()), 'se': float(yv.std() / math.sqrt(len(yv)))}
            print(f"turn 1, before anything is forfeited: rated {100 * v.mean():.1f}%, won {100 * yv.mean():.1f}% ± {100 * out['turn1']['se']:.1f} ({len(t1)} games)")
            if fmt_label == 'BO3':                                     # by game of the match: people adapt after game 1, the bot does not
                gn = game_numbers(); out['turn1_by_game'] = {}
                for k in (1, 2, 3):
                    xs = [t1[g] for g in t1 if gn.get(g) == k]
                    if not xs: continue
                    a = np.array(xs); out['turn1_by_game'][k] = {'games': len(a), 'rated': float(a[:, 0].mean()), 'won': float(a[:, 1].mean()), 'se': float(a[:, 1].std() / math.sqrt(len(a)))}
                    print(f"  game {k} of the match: rated {100 * a[:, 0].mean():.1f}%, won {100 * a[:, 1].mean():.1f}% ± {100 * a[:, 1].std() / math.sqrt(len(a)):.1f} ({len(a)} games)")
    return out
if __name__ == '__main__':
    P.own()
    ap = argparse.ArgumentParser(); ap.add_argument('--fmt', choices=('bo1', 'bo3')); ap.add_argument('--out', default=os.path.join(C.HERE, 'results', 'botstudy.json'))
    a = ap.parse_args()
    G, P_, MI, RS, OW = collect()
    print(f"{len(G)} bot ladder games in games.jsonl; luck pass read for {len({r['g'] for r in P_})}")
    res = []
    for f in ([a.fmt] if a.fmt else ['bo1', 'bo3']):
        res.append(report(G, *[[r for r in X if r['f'] == f] for X in (P_, MI, RS, OW)], f.upper()))
    json.dump(res, open(a.out, 'w'), indent=1)
