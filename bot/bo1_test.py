"""How good are the Bo1 guesses? (2026-10-12) On cached Bo3 games, where both open sheets are known, one side's sheet is hidden and its
sets guessed at the start of every turn from what the log has shown so far (bot/bo1.py), for each of its Pokemon that has appeared;
scored against the real sheet: item, ability, nature right, moves right out of four, the whole set right. Also the guess that never
updates (the commonest whole set) for comparison. The prior includes these games' sheets, so this flatters the prior slightly.
  .venv/bin/python3 bot/bo1_test.py [games=1500]"""
import os, sys, re, json, glob, random, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'bot'))
import bo1 as B, set_prior as SP
def main(n=1500):
    files = sorted(glob.glob(os.path.join(ROOT, 'pssim', 'replays_protect', '*.log'))); random.Random(4).shuffle(files)
    acc = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0]))
    done = 0
    for f in files:
        if done >= n: break
        L = open(f, errors='replace').read().split('\n')
        truth = {side: {B.toid(sp): (item, ab, nat, set(B.toid(m) for m in moves)) for sp, item, ab, nat, moves in team} for side, team in SP.sheets('\n'.join(L))}
        if len(truth) < 2: continue
        done += 1
        for side in ('p1', 'p2'):
            hidden = [l for l in L if not l.startswith(f'|showteam|{side}|')]
            turn = 0; seen = set()
            for i, l in enumerate(hidden):
                if l.startswith('|switch|' + side) or l.startswith('|drag|' + side): seen.add(B.toid(B.base(l.split('|')[3].split(',')[0])))
                if not l.startswith('|turn|'): continue
                turn = int(l.split('|')[2]); bucket = 'turn 1' if turn == 1 else 'turns 2-3' if turn <= 3 else 'turns 4-6' if turn <= 6 else 'turn 7+'
                rv = B.reveals(hidden[:i], side)
                for sp in seen:
                    t = truth[side].get(sp)
                    if not t: continue
                    for tag, g in (('updated', B.guess(sp, rv.get(sp))), ('never updated', B.guess(sp, None))):
                        if not g: continue
                        _, item, ab, nat, moves = g; gm = {B.toid(m) for m in moves}
                        for k, ok in (('item', B.toid(item) == B.toid(t[0])), ('ability', B.toid(ab) == B.toid(t[1])), ('nature', nat == t[2]),
                                      ('moves (of 4)', len(gm & t[3]) / 4), ('whole set', B.toid(item) == B.toid(t[0]) and B.toid(ab) == B.toid(t[1]) and nat == t[2] and gm == t[3])):
                            for b in (bucket, 'all'):
                                a = acc[(tag, b)][k]; a[0] += ok; a[1] += 1
    print(f"{done} games, each side's sheet hidden in turn; Pokemon that have appeared, at the start of each turn")
    keys = ['item', 'ability', 'nature', 'moves (of 4)', 'whole set']
    print(f"  {'':26s}" + ''.join(f"{k:>14s}" for k in keys))
    for tag in ('never updated', 'updated'):
        for b in ('turn 1', 'turns 2-3', 'turns 4-6', 'turn 7+', 'all'):
            r = acc[(tag, b)]
            if r['item'][1]: print(f"  {tag + ', ' + b:26s}" + ''.join(f"{100 * r[k][0] / r[k][1]:13.0f}%" for k in keys))
if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1500)
