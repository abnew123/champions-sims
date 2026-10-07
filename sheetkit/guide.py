"""Strategy guide: what the four on each tab do after turn one, and team-preview tells, for the page.

  run      each pick against its archetype's six opposing leads, 64 games each, with the per-turn log (BATTLE_TURNS=1), fresh game
           indices (default from 7000); writes work/guide/res
  report   -> guide.json: per archetype a short game plan (turn-two habits, Trick Room timing and resets, when the back comes in, Mega
           timing, what decides games, their hardest Pokemon) from those battles, and the strongest team-preview tells from the bring
           matrix (how much bringing each of the six is worth when they have Pokemon X, against that archetype's average)

Everything is weighted by the replay share of their lead pair, as on the Leads tab. Numbers describe how the planner plays the pick
against the modelled opponents: a picture of the usual game, not a rule."""
import collections, glob
from common import *
import picks as P

GAMES, G0 = 64, 7000

def jobs(sheet, picks):
    opp = opp_model()
    return [{'arch': a, 'k': k, 'lead': sheet.back(picks[a]['lead']), 'back': sheet.back(picks[a]['back'])}
            for a in ARCHS if a in picks for k in range(len(opp[a]['pairs']))]

def run(sheet, games=GAMES, g0=G0, threads=None, setup=None, force=False):
    threads = threads_arg(threads, force); js = jobs(sheet, rj(sheet.p('picks.json'))['picks'])
    wj(js, sheet.w('guide', 'jobs.json')); log = RunLog(sheet, 'guide')
    os.environ['BATTLE_TURNS'] = '1'                              # the per-turn state log the report reads
    P.battle_run(sheet, 'guide', sheet.w('guide', 'jobs.json'), sheet.w('guide', 'res'), games, g0, threads, setup, log)

# ---------------------------------------------------------------- reading the battles
def base(n): return n.split('-Mega')[0]

def acts(label):
    """'Mon: Move -> Target (Mega) | Mon2: switch to X' -> [(mon, kind, move, target, mega)]"""
    out = []
    for part in (label or '').split(' | '):
        if ': ' not in part: continue
        mon, a = part.split(': ', 1); mega = a.endswith(' (Mega)'); a = a.replace(' (Mega)', '')
        if a.startswith('switch to '): out.append((base(mon), 'switch', 'switch', base(a[10:]), mega))
        else:
            mv, _, tgt = a.partition(' -> '); out.append((base(mon), 'move', mv, base(tgt) if tgt else '', mega))
    return out

def load_games(sheet):
    G = collections.defaultdict(list)                             # arch -> [(weight, game, job result)]
    for f in glob.glob(sheet.w('guide', 'res', '*.json')):
        r = rj(f); rows = [g for g in r['rows'] if g.get('v') is not None and g.get('states')]
        for g in rows: G[r['arch']].append((r['share'] / len(rows), g, r))
    return G

def wmean(pairs):
    W = sum(w for w, _ in pairs); return sum(w * v for w, v in pairs) / W if W else float('nan')

def pct(x): return f"{round(100 * x)}%"

# ---------------------------------------------------------------- game plan per archetype
SET_TR = 'Trick Room'

def turn_kind(state):
    """what my side did on a turn, as one of a few plain kinds"""
    a = acts(state['a']); sw = [x for x in a if x[1] == 'switch']
    if len(sw) == 2: return 'double switch'
    if any(x[2] == SET_TR for x in a): return 'click Trick Room'
    if len(sw) == 1: return 'one switch'
    if any(x[2] in ('Protect', 'Detect') for x in a): return 'a Protect'
    return 'attack with both'

def plan(sheet, arch, L):
    mine = lambda n: sheet.my_names.get(n, n); W = sum(w for w, _, _ in L)
    st = lambda g, t: g['states'][t - 1] if len(g['states']) >= t else None
    lines, facts = [], {}
    # turn two: the usual kinds of turn, and the usual switch
    k2 = collections.Counter(); sw2 = collections.Counter()
    for w, g, _ in L:
        s = st(g, 2)
        if not s: continue
        k = turn_kind(s); k2[k] += w
        if k == 'one switch': sw2[next((x[0], x[3]) for x in acts(s['a']) if x[1] == 'switch')] += w
    if k2:
        tot = sum(k2.values()); top = [(k, v / tot) for k, v in k2.most_common(3) if v / tot >= 0.1]
        txt = []
        for k, v in top:
            if k == 'one switch' and sw2:
                (out_, in_), n = sw2.most_common(1)[0]
                txt.append(f"one switch {pct(v)}" + (f" (mostly {mine(out_)} out for {mine(in_)})" if n / sum(sw2.values()) >= 0.4 else ''))
            else: txt.append(f"{k} {pct(v)}")
        lines.append('Turn two: ' + ', '.join(txt) + '.')
        facts['turn2'] = {k: round(v / tot, 3) for k, v in k2.items()}
    # Trick Room: set on turn one or later, set again when it runs out, by whom
    t1_set = wmean([(w, 1.0 if any(x[2] == SET_TR for x in acts(g['states'][0]['a'])) else 0.0) for w, g, _ in L])
    up2 = wmean([(w, 1.0 if st(g, 2) and st(g, 2)['tr'] > 0 else 0.0) for w, g, _ in L])
    later = []; later_t = []; setter = collections.Counter(); theirs = 0.0
    for w, g, _ in L:
        sets = [(s['t'], x[0]) for s in g['states'] for x in acts(s['a']) if x[2] == SET_TR and s['t'] > 1]
        theirs += w * sum(1 for s in g['states'] for x in acts(s['b']) if x[2] == SET_TR)
        later.append((w, 1.0 if sets else 0.0))
        if sets: later_t.append((w, sets[0][0])); setter[sets[0][1]] += w
    lt = wmean(later); facts.update(tr_turn1=round(t1_set, 3), tr_up_turn2=round(up2, 3), tr_set_later=round(lt, 3), their_tr_per_game=round(theirs / W, 2))
    who = mine(setter.most_common(1)[0][0]) if setter else None
    if t1_set >= 0.3:
        s = f"Trick Room is up on turn two in {pct(up2)} of games"
        if lt >= 0.1: s += f"; when it runs out, {who} sets it again in {pct(lt)} (around turn {round(wmean(later_t))})"
        lines.append(s + '.')
    elif lt >= 0.1:
        lines.append(f"No Trick Room on turn one; {who} sets it later in {pct(lt)} of games, around turn {round(wmean(later_t))}.")
    # the back row: how often and when each comes in
    first_in = collections.defaultdict(list)
    for w, g, r in L:
        seen = {}
        for s in g['states']:
            for m, hp in s['me']:
                m = base(m)
                if m in map(base, r['back']) and m not in seen: seen[m] = s['t']
        for m in map(base, r['back']): first_in[m].append((w, seen.get(m)))
    parts = []
    for m, xs in first_in.items():
        inn = [(w, t) for w, t in xs if t is not None]; share = sum(w for w, _ in inn) / W
        if inn: parts.append((share, f"{mine(m)} comes in around turn {round(wmean(inn))}" + ('' if share >= 0.9 else f" ({pct(share)} of games)")))
    if parts: lines.append('; '.join(p for _, p in sorted(parts, key=lambda x: -x[0])) + '.')
    # Mega timing (whichever of mine carries a stone)
    mega = [(w, s['t']) for w, g, _ in L for s in g['states'] for x in acts(s['a']) if x[4]]
    if mega:
        who_m = next((x[0] for w, g, _ in L for s in g['states'] for x in acts(s['a']) if x[4]), None)
        share = min(1.0, sum(w for w, _ in mega) / W); tt = sorted(t for _, t in mega); med = tt[len(tt) // 2]
        lines.append(f"{mine(who_m)} Mega Evolves on turn {med}" + ('' if share >= 0.9 else f" or later ({pct(share)} of games)") + '.' if med == 1 else
                     f"{mine(who_m)} Mega Evolves around turn {med}" + ('' if share >= 0.9 else f" ({pct(share)} of games)") + '.')
    # what decides games
    win = wmean([(w, g['v']) for w, g, _ in L]); facts['win'] = round(win, 3)
    def cond(f):
        a = [(w, g['v']) for w, g, _ in L if f(g)]; b = [(w, g['v']) for w, g, _ in L if not f(g)]
        return (wmean(a), wmean(b), len(a), len(b)) if len(a) >= 30 and len(b) >= 30 else None
    c = cond(lambda g: bool(st(g, 2)) and st(g, 2)['tr'] > 0)
    if c and abs(c[0] - c[1]) >= 0.1:
        lines.append(f"With Trick Room up on turn two you win {pct(c[0])}; without it {pct(c[1])}.")
    # first of mine to faint by turn three, when it costs the most
    lost = collections.defaultdict(list)
    for w, g, r in L:
        prev = {base(m) for m, _ in g['states'][0]['me'] + g['states'][0]['mb']}
        for s in g['states'][1:3]:
            now = {base(m) for m, _ in s['me'] + s['mb']}
            for m in prev - now: lost[m].append(w)
            prev = now
    worst = None
    for m, ws in lost.items():
        a = [(w, g['v']) for w, g, r in L if any(base(x) == m for x, _ in g['states'][0]['me'] + g['states'][0]['mb'])
             and m not in {base(x) for x, _ in (g['states'][2]['me'] + g['states'][2]['mb'] if len(g['states']) > 2 else [])}]
        if len(a) >= 30 and (worst is None or wmean(a) < worst[1]): worst = (m, wmean(a), sum(ws) / W)
    if worst and worst[1] <= win - 0.15:
        lines.append(f"Losing {mine(worst[0])} by turn three ({pct(worst[2])} of games) drops you to {pct(worst[1])}: keep it safe early.")
    # their hardest Pokemon
    opp = collections.defaultdict(list)
    for w, g, r in L:
        for m in set(map(base, r['theirs'])): opp[m].append((w, g['v']))
    hard = sorted(((wmean(v), m, sum(w for w, _ in v) / W) for m, v in opp.items() if sum(w for w, _ in v) / W >= 0.15 and len(v) >= 64))
    if hard and hard[0][0] <= win - 0.1:
        lines.append(f"Hardest when they bring {THEIR_NAMES.get(hard[0][1], hard[0][1])} ({pct(hard[0][0])} won)" +
                     (f", then {THEIR_NAMES.get(hard[1][1], hard[1][1])} ({pct(hard[1][0])})" if len(hard) > 1 and hard[1][0] <= win - 0.1 else '') + '.')
    facts['games'] = len(L)
    return lines, facts

# ---------------------------------------------------------------- team-preview tells
def tells(sheet, min_teams=3, min_points=4.0):
    """[(their Pokemon, [(mine, change in points)], teams)]: how much more or less bringing each of the six is worth when they have X,
    against the same archetype's average, from the bring matrix; only changes over 2 standard errors and min_points"""
    V, share, names, theirs, _ = P.load(sheet.w('matrix', 'res*', '*.json')); mine = lambda n: sheet.my_names.get(n, n)
    def bring_value(t, m):
        cs = list(V[t]); gs = set.intersection(*(set(V[t][c]) for c in cs))
        d = [mean([V[t][c][g] for c in cs if m in c[0] | c[1]]) - mean([V[t][c][g] for c in cs if m not in c[0] | c[1]]) for g in gs]
        mu = mean(d); return mu, math.sqrt(sum((x - mu) ** 2 for x in d) / max(1, len(d) - 1) / max(1, len(d)))
    full = max(len(v) for v in V.values()); teams = [t for t in V if len(V[t]) >= 0.85 * full]     # leads with (nearly) every four run
    BV = {(t, m): bring_value(t, m) for t in teams for m in sheet.names}
    arch_bv = {(a, m): sum(share[t] * BV[(t, m)][0] for t in teams if t[0] == a) / sum(share[t] for t in teams if t[0] == a)
               for a in {t[0] for t in teams} for m in sheet.names}
    spec = collections.defaultdict(list)
    for t in teams:
        for x in {base(n) for n in theirs[t]}: spec[x].append(t)
    wt = lambda t: SHARE[t[0]] * share[t]; out = []
    for x, ts in spec.items():
        if len(ts) < min_teams or len({t[0] for t in ts}) < 2: continue            # one archetype only: that is the tab, not a tell
        W = sum(wt(t) for t in ts); row = []
        for m in sheet.names:
            d = sum(wt(t) * (BV[(t, m)][0] - arch_bv[(t[0], m)]) for t in ts) / W
            se = math.sqrt(sum((wt(t) / W) ** 2 * BV[(t, m)][1] ** 2 for t in ts))
            if abs(d) > 2 * se and abs(100 * d) >= min_points: row.append((mine(m), round(100 * d)))
        if row: out.append((THEIR_NAMES.get(x, x), sorted(row, key=lambda r: -r[1]), len(ts), W))
    return sorted(out, key=lambda r: -r[3])

def report(sheet, out=print):
    G = load_games(sheet); picks = rj(sheet.p('picks.json'))['picks']; res = {'plans': {}, 'tells': []}
    for a in ARCHS:
        if a not in G: continue
        lines, facts = plan(sheet, a, G[a]); res['plans'][a] = {'lines': lines, 'facts': facts}
        out(f"\n=== {a}: {'+'.join(picks[a]['lead'])} / {'+'.join(picks[a]['back'])}, {facts['games']} games, won {pct(facts['win'])}")
        for l in lines: out('   ' + l)
    if glob.glob(sheet.w('matrix', 'res*', '*.json')):
        res['tells'] = [{'them': x, 'mine': row, 'teams': n} for x, row, n, _ in tells(sheet)]
        out('\n=== team-preview tells (change in what bringing each of yours is worth when they have X, win-% points)')
        for t in res['tells']: out(f"   {t['them']:16s} " + ', '.join(f"{m} {d:+d}" for m, d in t['mine']) + f"   ({t['teams']} opposing teams)")
    meta = rj(sheet.w('guide', 'res.run.json')) if os.path.exists(sheet.w('guide', 'res.run.json')) else {}
    res['made'] = {'setup': meta.get('setup'), 'games': meta.get('games'), 'g0': meta.get('g0')}
    wj(res, sheet.p('guide.json'), indent=1, ensure_ascii=False)
    return res
