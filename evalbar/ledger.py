"""Where does the value go in the bot's games? (the user, 2026-10-20: if the gauge were right, the bot's rated chance would rise through a
game as its opponent errs, like an engine's against a person; how much do the opponents' mistakes come to over a game, and where is the
value lost?) The bar's luck pass gives every turn as a payoff table in hindsight (botstudy.py), cells rescaled with the engine's CAL. For
a turn t, with x and y the two sides' equilibrium mixes and M the table (the bot's chance after the turn):
  V_t        x'My, the turn's value with both sides on their mixes
  opponent   x'M[:, played] - V_t: the opponent's play against the bot's mix (the engine's charge for its departure; 0 or more)
  bot        M[played, :]y - V_t: the bot's own play against the opponent's mix (0 or less)
  together   M[played, played] - V_t - opponent - bot: how the two plays met (a read, or a guess that paid)
  dice       S_t+1 - M[played, played]: the value function at the next turn's start (S, no lookahead) against what the two plays were
             expected to give: rolls, crits, accuracy, speed ties. At the last turn the result stands in for S
  drift      V_t - S_t: the lookahead's value against the value function at the same position. If the value function were right,
             about 0 on average
  forfeit    a game that ended by a forfeit (or a timer): the result less the value at the start of the turn it ended in
Over a game these add up exactly to the result less V at turn 1, so a gap between the opponents' mistakes and the bot's gain has to show
up in one of the others. Bo1 and Bo3 apart, and Bo3 by game of the match.
  replays    the same drift in people's games (diverge.py's data: Showdown Bo3, depth at 4x), from a side's view, by what it and its
             opponent played the turn before, and by whether it played the engine's top option (a winner's curse would show there)
usage (numpy: the main folder's .venv): python3 evalbar/ledger.py [replays]   writes evalbar/results/ledger.json (ledger_replays.json)"""
import os, sys, json, re, math, collections
import numpy as np
import common as C, procs as P, botstudy as BS, diverge as D
sig = lambda x: 1 / (1 + math.exp(-x))
logit = lambda v: math.log(min(1 - 1e-4, max(1e-4, v)) / (1 - min(1 - 1e-4, max(1e-4, v))))
PARTS = ('opponent', 'bot', 'together', 'dice', 'drift', 'forfeit')
def endings():
    """{room: 'forfeit' or None}: a game decided by a forfeit or the timer, from its log (chat and HTML lines skipped)"""
    out = {}
    for f in os.listdir(BS.BOT):
        if not f.startswith('battle-') or not f.endswith('.log'): continue
        how = None
        for line in open(os.path.join(BS.BOT, f), errors='replace'):
            if line.startswith(('|c|', '|c:|', '|chat|', '|raw|', '|html|', '|uhtml|')): continue
            if line.startswith('|-message|') and (line.rstrip().endswith(' forfeited.') or 'lost due to inactivity' in line): how = 'forfeit'
        out[f[:-4]] = how
    return out
def matched(entries, side_acts):
    """indices of the joint actions that agree with each slot's played option(s) (a slot whose play the log does not show: any)"""
    key = lambda c: json.dumps(c)
    return [i for i, e in enumerate(entries)
            if all(not pl or e[s_] is None or any(key(e[s_]) == key(o['c']) for o in pl) for s_, (_, pl) in side_acts.items())]
def turn(d, cal):
    """one luck line -> (V, S, opponent, bot, together, expected cell)"""
    m = d['matrix']; R = lambda v: sig(cal * logit(v))
    raw = np.array([[x if x is not None else np.nan for x in row] for row in m['v1']], float)
    M = np.where(np.isnan(raw), R(d['value']), np.vectorize(R)(np.nan_to_num(raw, nan=0.5)))
    x = np.array(m['x'], float); x /= x.sum() or 1; y = np.array(m['y'], float); y /= y.sum() or 1
    V = float(x @ M @ y); S = R(d['static'])
    rows = matched(m['rows'], BS.acts(d['sides'][0])) or list(range(len(m['rows'])))
    cols = matched(m['cols'], BS.acts(d['sides'][1])) or list(range(len(m['cols'])))
    opp = float((x @ M[:, cols]).mean()) - V; bot = float((M[rows, :] @ y).mean()) - V
    cell = float(M[np.ix_(rows, cols)].mean())
    return V, S, opp, bot, cell - V - opp - bot, cell
def game(num, won, ended):
    """the game's ledger, or None when a turn is missing"""
    T = BS.records(num)
    if not T: return None
    turns = sorted(T)
    if turns != list(range(turns[0], turns[0] + len(turns))) or turns[0] != 1: return None
    per = {}
    for t in turns:
        vals = [turn(d, cal) for d, cal in T[t]]
        per[t] = [float(np.mean([v[i] for v in vals])) for i in range(6)]   # the turn's back-row guesses, equally
    led = dict.fromkeys(PARTS, 0.0); y = 1.0 if won else 0.0
    last = turns[-1] if ended != 'forfeit' else turns[-1] - 1             # a forfeited game: its last turn is the forfeit
    for t in turns:
        V, S, opp, bot, tog, cell = per[t]
        if t > 1: led['drift'] += V - S
        if t > last: led['forfeit'] += y - V; break
        led['opponent'] += opp; led['bot'] += bot; led['together'] += tog
        led['dice'] += (per[t + 1][1] if t + 1 in per and t + 1 <= turns[-1] else y) - cell
    led['start'] = per[1][0]; led['result'] = y; led['turns'] = len(turns); led['forfeited'] = ended == 'forfeit'
    return led
def replays():
    """drift (search less value function at a position, from a side's view) in people's games, by what that side and its opponent
    played the turn before, and whether the side played the engine's top option in every slot"""
    Mv = json.load(open(os.path.join(C.MAIN, 'native', 'engine_data_full.json')))['moves']; pos = {}
    for part in ('hold', 'val', 'fit_sub'):
        for l in open(os.path.join(D.V2, 'box', f'real_{part}_d4.eval.jsonl')):
            e = json.loads(l)
            if 'sides' not in e or e.get('static') is None: continue
            info = []
            for s_ in (0, 1):
                top, kinds, known = True, set(), True
                for sl in e['sides'][s_]['slots']:
                    o = sl['options']
                    if len(o) < 2: continue
                    pl = [x for x in o if x.get('actual')]
                    if not pl: known = False; continue
                    kinds.add(D.kind(pl[0]['label'], pl[0]['c'], Mv)); top = top and bool(max(o, key=lambda x: x['w']).get('actual'))
                info.append({'top': top and known, 'kinds': kinds, 'known': known})
            pos[(e['name'].split(' ')[0], e['turn'])] = {'d': D.R(e['value']) - D.R(e['static']), 'info': info}
    rows = []
    for (g, t), p_ in pos.items():
        q = pos.get((g, t + 1))
        if not q: continue
        for s_ in (0, 1):
            if p_['info'][s_]['known'] and p_['info'][1 - s_]['known']:
                rows.append({'g': g, 'd': q['d'] if s_ == 0 else -q['d'], 'top': p_['info'][s_]['top'], 'own': p_['info'][s_]['kinds'], 'opp_top': p_['info'][1 - s_]['top']})
    def ms(xs):
        by = collections.defaultdict(lambda: [0.0, 0])
        for r in xs: by[r['g']][0] += r['d']; by[r['g']][1] += 1
        S = np.array([v[0] for v in by.values()]); N = np.array([v[1] for v in by.values()])
        pick = np.random.default_rng(1).integers(0, len(S), (400, len(S)))
        return {'mean': float(S.sum() / N.sum()), 'se': float(np.std(S[pick].sum(1) / N[pick].sum(1))), 'n': len(xs)}
    out = {'steps': len(rows), 'games': len({r['g'] for r in rows}), 'top': {}, 'after_own': {}}
    print(f"{len(rows)} side-steps in {out['games']} people's games; drift for the side, points")
    for lab, f in (('played the top option in every slot, the opponent did not', lambda r: r['top'] and not r['opp_top']), ('did not, the opponent did', lambda r: r['opp_top'] and not r['top']),
                   ('both did', lambda r: r['top'] and r['opp_top']), ('neither did', lambda r: not r['top'] and not r['opp_top'])):
        x = out['top'][lab] = ms([r for r in rows if f(r)]); print(f"  {lab:60s} {100 * x['mean']:+.2f} ± {100 * x['se']:.2f} ({x['n']})")
    print('  by what the side itself played the turn before:')
    for k, n in collections.Counter(k for r in rows for k in r['own']).most_common():
        if n < 300: continue
        x = out['after_own'][k] = ms([r for r in rows if k in r['own']]); print(f"    {k[:44]:44s} {100 * x['mean']:+.2f} ± {100 * x['se']:.2f} ({x['n']})")
    json.dump(out, open(os.path.join(C.HERE, 'results', 'ledger_replays.json'), 'w'), indent=1)
if __name__ == '__main__':
    P.own()
    if sys.argv[1:] == ['replays']: replays(); sys.exit()
    G = BS.games(); E = endings(); gn = BS.game_numbers(); rows = []
    for num, (room, won, fmt, _) in G.items():
        try: L = game(num, won, E.get(room))
        except Exception: L = None
        if L: rows.append({**L, 'g': num, 'fmt': fmt, 'game_no': gn.get(num) if fmt == 'bo3' else None})
    out = {}
    def show(label, rs):
        if not rs: return
        n = len(rs); res = {'games': n}
        print(f"\n{label}: {n} games with every turn read (points of win chance a game; ± one standard error)")
        for k in ('start', 'result') + PARTS:
            a = np.array([r[k] for r in rs], float); res[k] = {'mean': float(a.mean()), 'se': float(a.std() / math.sqrt(n))}
            print(f"  {k:10s} {100 * a.mean():+7.2f} ± {100 * a.std() / math.sqrt(n):.2f}")
        chk = np.mean([r['result'] - r['start'] - sum(r[k] for k in PARTS) for r in rs])
        print(f"  (result - start - parts: {100 * chk:+.3f}; turns a game {np.mean([r['turns'] for r in rs]):.1f}; forfeited {100 * np.mean([r['forfeited'] for r in rs]):.0f}%)")
        out[label] = res
    for fmt in ('bo1', 'bo3'):
        show(fmt.upper(), [r for r in rows if r['fmt'] == fmt])
    for k in (1, 2, 3):
        show(f'BO3 game {k}', [r for r in rows if r['fmt'] == 'bo3' and r['game_no'] == k])
    json.dump(out, open(os.path.join(C.HERE, 'results', 'ledger.json'), 'w'), indent=1)
