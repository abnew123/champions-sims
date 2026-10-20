"""Where do human players part from the engine, and who is right? (the user, 2026-10-20: "help us find places where humans underperform ...
or uncover more deficiencies in the current bot")
Every human choice in Battle sim's rebuilt replay positions (pssim/results/value2: the Showdown Bo3 games with open sheets, both sides,
rebuilt by spots.specs) scored by the bots' search, depth at 4x (box/real_<part>_d4.eval.jsonl), against who won.
For each kind of choice (Protect, a switch, setup, Fake Out, a spread attack, Mega Evolving now, ...):
  share        how often humans chose it, against how often the engine's mix would (the same slots)
  claimed      what the engine says each such choice cost, in points of win chance: its mix's value less the choice's, both rescaled
               (live.py's CAL for this search, 0.765)
  realized     what it cost in real results: the engine's rating of the position (rescaled) less how often the side won, over the
               positions where it was chosen. The other choices in the position (the partner's, the opponent's) are noise, not bias
  residual     realized less what the engine's claimed cost predicts (residuals(): realized = a + b x claimed over every choice). Near 0:
               the engine is right about the kind (a cost it claims is a human error, a place humans underperform); below 0: the kind does
               better against humans than the engine expects (the engine undervalues it, a bot deficiency); above 0: worse (it overvalues it).
               Standard errors by bootstrapping games
The engine knows in hindsight the Pokemon each player brought but had not shown yet (players do not), so choices that depend on the back
row can look worse to it than they were: --min-turn 4 keeps positions from turn 4 on, where most back rows are out.
usage (numpy: the main folder's .venv): python3 evalbar/diverge.py [--parts hold,val,fit_sub] [--min-turn N] [--rating hi|lo (above / below the median rating)]
       writes evalbar/results/diverge.json"""
import os, sys, json, re, math, collections, argparse
import numpy as np
import common as C, procs as P
V2 = os.path.join(C.MAIN, 'pssim', 'results', 'value2'); CAL = 0.765
sig = lambda x: 1 / (1 + math.exp(-x))
logit = lambda v: math.log(min(1 - 1e-4, max(1e-4, v)) / (1 - min(1 - 1e-4, max(1e-4, v))))
R = lambda v: sig(CAL * logit(v))
toid = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
PROTECT = {'protect', 'detect', 'spikyshield', 'kingsshield', 'banefulbunker', 'silktrap', 'burningbulwark', 'obstruct'}
PIVOT = {'uturn', 'voltswitch', 'partingshot', 'flipturn', 'teleport', 'chillyreception', 'shedtail', 'batonpass'}
FIELD = {'trickroom': 'Trick Room', 'tailwind': 'Tailwind', 'followme': 'redirection', 'ragepowder': 'redirection', 'wideguard': 'Wide / Quick Guard',
         'quickguard': 'Wide / Quick Guard', 'helpinghand': 'Helping Hand', 'fakeout': 'Fake Out', 'reflect': 'screens', 'lightscreen': 'screens',
         'auroraveil': 'screens'}
def kind(label, c, M):
    if label.startswith('switch to'): return 'switch'
    mid = toid(re.sub(r' \(Mega\)$', '', label).split(' -> ')[0]); m = M.get(mid, {})
    if mid in PROTECT: return 'Protect'
    if mid in FIELD: return FIELD[mid]
    if mid in PIVOT: return 'pivot (U-turn, Parting Shot...)'
    if m.get('category') == 'Status':
        if m.get('weather') or m.get('terrain'): return 'weather / terrain'
        if m.get('target') in ('self', 'adjacentAllyOrSelf') and (m.get('boosts') or mid in ('bellydrum', 'stockpile', 'focusenergy', 'substitute')): return 'setup / self-boost'
        if len(c) > 1 and isinstance(c[1], int) and c[1] < 0: return 'status move on the partner'
        return 'status move on a foe (Taunt, Spore, Will-O-Wisp...)'
    if len(c) > 1 and isinstance(c[1], int) and c[1] < 0: return 'attack on the partner'
    sec = m.get('secondaries') or ([m['secondary']] if m.get('secondary') else [])
    if any(s and s.get('chance', 0) >= 100 and (s.get('boosts') or {}).get('spe', 0) < 0 for s in sec): return 'speed-control attack (Icy Wind...)'
    if m.get('priority', 0) > 0: return 'priority attack'
    if m.get('target') in ('allAdjacentFoes', 'allAdjacent'): return 'spread attack'
    return 'single-target attack'
def rows(parts, min_turn=0, rating=None):
    """one row a marked human choice: (game, kind, mega, claimed, engine share of its kind, side's rated chance, side won, turn, rating)"""
    M = json.load(open(os.path.join(C.MAIN, 'native', 'engine_data_full.json')))['moves']
    out = []; ratings = []
    for part in parts:
        meta = {}
        for l in open(os.path.join(V2, f'real_{part}.meta.jsonl')):
            d = json.loads(l); meta[d['name']] = d
        for l in open(os.path.join(V2, 'box', f'real_{part}_d4.eval.jsonl')):
            e = json.loads(l); m = meta.get(e['name'])
            if not m or 'sides' not in e or e.get('turn', 0) < min_turn: continue
            if m.get('rating'): ratings.append(m['rating'])
            for s, sd in enumerate(e['sides']):
                V = R(e['value'] if s == 0 else 1 - e['value']); y = m['y'] if s == 0 else 1 - m['y']
                for sl in sd['slots']:
                    o = sl['options']; ch = next((x for x in o if x.get('actual')), None)
                    if ch is None or len(o) < 2: continue
                    tot = sum(x['w'] for x in o) or 1
                    mix = sum(x['w'] * R(x['v']) for x in o) / tot
                    k = kind(ch['label'], ch['c'], M); kw = collections.Counter()
                    for x in o: kw[kind(x['label'], x['c'], M)] += x['w'] / tot
                    mega_avail = any(x['label'].endswith('(Mega)') for x in o)
                    mega_share = sum(x['w'] for x in o if x['label'].endswith('(Mega)')) / tot
                    top = max(o, key=lambda x: x['w'])
                    out.append({'g': m['game'], 'k': k, 'mega': ch['label'].endswith('(Mega)') if mega_avail else None, 'mega_share': mega_share,
                                'claimed': mix - R(ch['v']), 'kw': dict(kw), 'V': V, 'y': y, 't': e['turn'], 'r': m.get('rating'),
                                'top_k': kind(top['label'], top['c'], M), 'top_w': top['w'] / tot, 'ch_w': ch['w'] / tot})
    if rating:
        med = float(np.median(ratings)); out = [r for r in out if r['r'] and ((r['r'] >= med) == (rating == 'hi'))]
    return out
def engine_shares(rs):
    """the engine's mix over kinds across the same slots: each kind's weight, summed over every slot, over the number of slots"""
    s = collections.Counter()
    for r in rs:
        for k, w in r['kw'].items(): s[k] += w
    return {k: v / len(rs) for k, v in s.items()}
def residuals(rs, B=500, seed=1):
    """realized = a + b x claimed over every choice (the engine's costs show up in results at rate b; a: the offset of choosing sides,
    which win a little more often than rated); per kind, the mean of realized less that line: below 0, the kind does better than the
    engine expects (it undervalues it), above 0 worse (it overvalues it, or the human errs more than it says). SEs by bootstrapping games"""
    rng = np.random.default_rng(seed); games = sorted({r['g'] for r in rs}); gi = {g: i for i, g in enumerate(games)}
    y = np.array([r['V'] - r['y'] for r in rs]); c = np.array([r['claimed'] for r in rs]); G = np.array([gi[r['g']] for r in rs])
    X = np.c_[np.ones(len(rs)), c]; a, b = np.linalg.lstsq(X, y, rcond=None)[0]; res = y - (a + b * c)
    by = collections.defaultdict(list)
    for i, r in enumerate(rs):
        by[r['k']].append(i)
        if r['mega'] is not None: by['Mega Evolves now' if r['mega'] else 'holds the Mega'].append(i)
    ES = engine_shares(rs); mega = [r for r in rs if r['mega'] is not None]
    if mega: ms = float(np.mean([r['mega_share'] for r in mega])); ES['Mega Evolves now'] = ms; ES['holds the Mega'] = 1 - ms
    out = []
    for k, ix in by.items():
        ix = np.array(ix); gg, inv = np.unique(G[ix], return_inverse=True)
        S = np.bincount(inv, res[ix]); N = np.bincount(inv); pick = rng.integers(0, len(gg), (B, len(gg)))
        base = len(mega) if k in ('Mega Evolves now', 'holds the Mega') else len(rs)
        out.append({'kind': k, 'n': len(ix), 'games': len(gg), 'human_share': len(ix) / base, 'engine_share': ES.get(k, 0.0),
                    'claimed': float(c[ix].mean()), 'realized': float(y[ix].mean()), 'residual': float(res[ix].mean()),
                    'residual_se': float(np.std(S[pick].sum(1) / N[pick].sum(1)))})
    return {'a': float(a), 'b': float(b)}, sorted(out, key=lambda x: -x['n'])
if __name__ == '__main__':
    P.own()
    ap = argparse.ArgumentParser(); ap.add_argument('--parts', default='hold,val,fit_sub'); ap.add_argument('--min-turn', type=int, default=0)
    ap.add_argument('--rating', choices=('hi', 'lo')); ap.add_argument('--out', default=os.path.join(C.HERE, 'results', 'diverge.json'))
    a = ap.parse_args()
    rs = rows(a.parts.split(','), a.min_turn, a.rating)
    fit, T = residuals(rs)
    print(f"{len(rs)} human choices in {len({r['g'] for r in rs})} games (depth at 4x, CAL {CAL}); points of win chance")
    print(f"realized = {100 * fit['a']:.2f} + {fit['b']:.2f} x claimed, over every choice")
    print(f"{'kind':44s} {'n':>7s} {'human':>6s} {'engine':>7s} {'claimed':>8s}   better (-) / worse (+) than the engine expects")
    for x in T:
        print(f"{x['kind'][:44]:44s} {x['n']:7d} {100 * x['human_share']:5.1f}% {100 * x['engine_share']:6.1f}% {100 * x['claimed']:8.2f}"
              f"   {100 * x['residual']:+6.2f} ± {100 * x['residual_se']:.2f}")
    json.dump({'choices': len(rs), 'games': len({r['g'] for r in rs}), 'cal': CAL, 'parts': a.parts, 'min_turn': a.min_turn, 'rating': a.rating,
               'fit': fit, 'kinds': T}, open(a.out, 'w'), indent=1)
