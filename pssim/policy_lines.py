"""What rises and falls when a side exploits (or is exploited)? Per run and side: share of slot decisions by kind of line, focus fire,
game length, Trick Room / Tailwind set per game, Protect and switches per game; differences vs the same side in the baseline run on
the same games (SE by game)."""
import json, glob, sys, os, collections, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from human_lines import kind, MOVES, BYNAME
S = os.environ.get('POLICY_RUNS', '.')   # the directory holding the run folders (L_base, L_pureRead, ...)
KINDS = ['attack', 'spread attack', 'priority attack', 'Protect', 'switch', 'Fake Out', 'setup', 'pivot', 'redirection', 'Helping Hand', 'Tailwind', 'Trick Room', 'status move', 'disruption', 'weather/terrain', 'heal', 'Wide/Quick Guard', 'other']
def load(d):
    out = {}
    for f in glob.glob(f'{S}/{d}/*.json'):
        j = json.load(open(f))
        if j['v'] is None or not j.get('rows'): continue
        out[j['job']] = j
    return out
def acts(s):
    """'Mon: Move -> Target | Mon2: switch to X' -> [(mon, label)]"""
    out = []
    for seg in s.split(' | '):
        if ': ' not in seg: continue
        mon, lab = seg.split(': ', 1); out.append((mon.strip(), lab.strip()))
    return out
def game_stats(row, side):
    """per game, one side: counts by kind, decisions, focus-fire turns (both slots attack the same target), attack turns with 2 attackers"""
    c = collections.Counter(); dec = 0; ff = 0; two = 0; t1prot = 0
    for st in row['states']:
        a = acts(st['a'] if side == 0 else st['b'])
        kinds = []
        for mon, lab in a:
            kd, mid = kind(lab)
            if kd == 'attack' and mid and MOVES[mid].get('priority', 0) > 0: kd = 'priority attack'
            if kd not in KINDS: kd = 'other'
            c[kd] += 1; dec += 1; kinds.append((kd, lab))
            if st['t'] == 1 and kd == 'Protect': t1prot += 1
        tg = [lab.split(' -> ')[1] for kd, lab in kinds if kd in ('attack', 'priority attack') and ' -> ' in lab]
        if len(tg) == 2: two += 1; ff += tg[0] == tg[1]
    return c, dec, ff, two, t1prot
def side_table(R, side, B=None):
    ks = sorted(R)
    if B is not None: ks = sorted(set(R) & set(B))
    def collect(X):
        per = []
        for k in ks:
            row = X[k]['rows'][0]; c, dec, ff, two, t1p = game_stats(row, side)
            d = {kd: c[kd] / max(1, dec) for kd in KINDS}
            d['decisions'] = dec; d['turns'] = row['turns']; d['focus fire'] = ff / two if two else None
            d['Protects / game'] = c['Protect']; d['switches / game'] = c['switch']; d['Trick Room / game'] = c['Trick Room']; d['Tailwind / game'] = c['Tailwind']
            d['turn-1 Protect'] = t1p; d['won'] = X[k]['v'] if side == 0 else 1 - X[k]['v']
            per.append(d)
        return per
    A = collect(R); Bp = collect(B) if B is not None else None
    lines = []
    for key in ['won', 'turns', 'decisions'] + KINDS + ['focus fire', 'Protects / game', 'switches / game', 'Trick Room / game', 'Tailwind / game', 'turn-1 Protect']:
        xs = [d[key] for d in A if d[key] is not None]
        if not xs: continue
        mu = sum(xs) / len(xs); s = f"{key:18s} {fmt(key, mu)}"
        if Bp is not None:
            pairs = [(a[key], b[key]) for a, b in zip(A, Bp) if a[key] is not None and b[key] is not None]
            dd = [a - b for a, b in pairs]; m = sum(dd) / len(dd); se = math.sqrt(sum((x - m) ** 2 for x in dd) / max(1, len(dd) - 1) / len(dd))
            mb = sum(b for _, b in pairs) / len(pairs)
            s += f"   base {fmt(key, mb)}   diff {fmt(key, m, True)} ± {fmt(key, se)}"
        lines.append(s)
    return lines
def fmt(key, v, sign=False):
    if key in KINDS or key in ('focus fire', 'won'): return f"{100 * v:{'+' if sign else ''}6.1f}%"
    return f"{v:{'+' if sign else ''}6.2f}"
if __name__ == '__main__':
    B = load('L_base')
    for d, side, lab in [(x.split(':')[0], int(x.split(':')[1]), x.split(':')[2]) for x in sys.argv[1:]]:
        R = load(d); print(f"\n== {lab}: {d} side {side} vs L_base side {side}, {len(set(R) & set(B))} games")
        print('\n'.join(side_table(R, side, B)))
