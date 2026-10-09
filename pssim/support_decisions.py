"""Do the support credits make the planner agree with players? (2026-10-10, TR sheet relaying the user: fit the credits to human decisions
as a check.) On Eval bar's accuracy set (560 cached ladder Bo3 games, 3,968 positions, both sides' plays known where the Pokemon acted),
the one-turn planner's slot policies under several support settings (evalpos output files, one per setting, same positions and seeds) are
compared with the players' choices on the decisions the credits touch:
  Fake Out (a fresh Pokemon with Fake Out usable: used it or not), Tailwind (usable, own Tailwind down), Trick Room (usable, down),
  redirection (Follow Me / Rage Powder usable), and finishing: a foe on the field at <= 25% HP, split by whether that foe still has a
  support move (Fake Out, Follow Me, Tailwind, Trick Room, screens, Parting Shot, Helping Hand, Wide Guard, sleep, Will-O-Wisp /
  Thunder Wave, Taunt / Encore) usable: did the player's attack target it (or a spread move hit it), and how much weight the planner put on hitting it.
Per decision type and setting: decisions, the players' rate, the planner's rate (its total weight on the yes option), p(human) = the
planner's weight on what the player did, and match = how often the planner's majority agrees; the differences between settings are
paired on the same decisions (SE from a bootstrap by game).
  ../.venv/bin/python3 support_decisions.py <pos.jsonl> <label>=<eval.jsonl> [<label>=<eval.jsonl> ...] [--min-rating N]"""
import json, os, sys, collections, random, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from human_lines import MOVES, BYNAME, kind
SUPPORT = {'fakeout', 'followme', 'ragepowder', 'tailwind', 'trickroom', 'reflect', 'lightscreen', 'auroraveil', 'partingshot', 'helpinghand', 'wideguard',
           'spore', 'sleeppowder', 'hypnosis', 'darkvoid', 'willowisp', 'thunderwave', 'taunt', 'encore'}
def to_id(s): return re.sub(r'[^a-z0-9]', '', s.lower())
def usable(p, mid):
    return any(sl['id'] == mid and sl['pp'] > 0 and not sl['disabled'] for sl in p['moveSlots'])
def label_parts(label):
    """option label -> (move id or None, target id or None, is spread damaging)"""
    if label.startswith('switch to'): return None, None, False
    name, _, tgt = label.partition(' -> ')
    name = name.replace(' (Mega)', '').strip(); mid = BYNAME.get(name)
    if mid is None: return None, None, False
    m = MOVES[mid]; spread = m['category'] != 'Status' and m['target'] in ('allAdjacentFoes', 'allAdjacent')
    return mid, (to_id(tgt.replace(' (Mega)', '')) if tgt else None), spread
def decisions(pos, r):
    """(type, key, human yes/no, planner weight on yes) for every known slot play in eval row r"""
    out = []; st = pos['state']
    for si, s in enumerate(r['sides']):
        side = st['sides'][si]; foe = st['sides'][1 - si]
        pw = st['field'].get('pseudoWeather') or {}
        for sl in s['slots']:
            opts = sl['options']
            if not opts or side['active'][sl['slot']] is None: continue
            act = next((o for o in opts if o['actual']), None)
            if act is None: continue
            p = side['pokemon'][side['active'][sl['slot']]]
            amid, atgt, aspread = label_parts(act['label'])
            key = (r['name'], si, sl['slot'])
            def binary(typ, yes):
                wy = sum(o['w'] for o in opts if yes(o)); out.append((typ, key, yes(act), wy))
            if usable(p, 'fakeout') and p.get('activeMoveActions', 0) == 0:
                binary('Fake Out (fresh)', lambda o: label_parts(o['label'])[0] == 'fakeout')
            if usable(p, 'tailwind') and 'tailwind' not in (side.get('sideConditions') or {}):
                binary('Tailwind (down)', lambda o: label_parts(o['label'])[0] == 'tailwind')
            if usable(p, 'trickroom') and 'trickroom' not in pw:
                binary('Trick Room (down)', lambda o: label_parts(o['label'])[0] == 'trickroom')
            if usable(p, 'followme') or usable(p, 'ragepowder'):
                binary('redirection', lambda o: label_parts(o['label'])[0] in ('followme', 'ragepowder'))
            for fi in foe['active']:
                if fi is None: continue
                f = foe['pokemon'][fi]
                if f['fainted'] or f['hp'] <= 0 or f['hp'] * 4 > f['maxhp']: continue
                fid = to_id(f['species']); sup = any(usable(f, m) for m in SUPPORT)
                hits = lambda o: (lambda mid, tgt, spread: mid is not None and MOVES[mid]['category'] != 'Status' and (tgt == fid or spread))(*label_parts(o['label']))
                if not any(hits(o) for o in opts): continue
                binary('finish a foe <= 25% HP: ' + ('support' if sup else 'attacker'), hits)
    return out
def main(posf, evals, min_rating):
    idx = json.load(open(os.path.join(HERE, 'replays_protect', 'index.json')))
    pos = {}
    for l in open(posf): p = json.loads(l); pos[p['name']] = p
    D = {}
    for label, f in evals:
        d = {}
        for l in open(f):
            r = json.loads(l); p = pos.get(r['name'])
            if not p: continue
            gid = r['name'].split(' ')[0]
            if min_rating and ((idx.get(gid) or {}).get('rating') or 0) < min_rating: continue
            for typ, key, hy, wy in decisions(p, r): d[(typ, key)] = (hy, wy)
        D[label] = d
    labels = [l for l, _ in evals]; common = set.intersection(*(set(D[l]) for l in labels))
    types = sorted(set(t for t, _ in common), key=lambda t: -sum(1 for x in common if x[0] == t))
    print(f"{len(common)} decisions in common across {len(labels)} settings (min rating {min_rating})")
    for typ in types:
        keys = sorted(k for k in common if k[0] == typ); n = len(keys)
        hy = sum(1 for k in keys if D[labels[0]][k][0]) / n
        print(f"\n{typ}: {n} decisions, players yes {100 * hy:.1f}%")
        print(f"  {'setting':10s} {'planner yes':>11s} {'p(human)':>9s} {'match':>6s} | vs {labels[0]}: {'d p(human)':>11s} {'d match':>9s}")
        base = labels[0]; rnd = random.Random(7); games = collections.defaultdict(list)
        for k in keys: games[k[1][0].split(' ')[0]].append(k)
        gk = list(games)
        for lab in labels:
            ph = lambda k, l: D[l][k][1] if D[l][k][0] else 1 - D[l][k][1]
            mt = lambda k, l: (D[l][k][1] >= 0.5) == D[l][k][0]
            py = sum(D[lab][k][1] for k in keys) / n; p_h = sum(ph(k, lab) for k in keys) / n; m = sum(mt(k, lab) for k in keys) / n
            if lab == base: print(f"  {lab:10s} {100 * py:10.1f}% {100 * p_h:8.1f}% {100 * m:5.1f}%"); continue
            dp = [ph(k, lab) - ph(k, base) for k in keys]; dm = [float(mt(k, lab)) - float(mt(k, base)) for k in keys]
            bp, bm = [], []
            for _ in range(200):
                ks = [k for g in [rnd.choice(gk) for _ in gk] for k in games[g]]
                bp.append(sum(ph(k, lab) - ph(k, base) for k in ks) / len(ks)); bm.append(sum(float(mt(k, lab)) - float(mt(k, base)) for k in ks) / len(ks))
            sd = lambda b: (sum((x - sum(b) / len(b)) ** 2 for x in b) / (len(b) - 1)) ** 0.5
            print(f"  {lab:10s} {100 * py:10.1f}% {100 * p_h:8.1f}% {100 * m:5.1f}% | {100 * sum(dp) / n:+8.1f} ± {100 * sd(bp):3.1f} {100 * sum(dm) / n:+6.1f} ± {100 * sd(bm):3.1f}")
if __name__ == '__main__':
    a = sys.argv[1:]; mr = 0
    if '--min-rating' in a: i = a.index('--min-rating'); mr = int(a[i + 1]); a = a[:i] + a[i + 2:]
    main(a[0], [tuple(x.split('=', 1)) for x in a[1:]], mr)
