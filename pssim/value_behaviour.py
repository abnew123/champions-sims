"""Compare how two value functions play (2026-10-04): the same games (BATTLE_TURNS state logs) in two result folders, e.g.
results/dp_test_base (egvalue5) vs results/ev6_test (egvalue6). Per side: key move clicks per 100 actions, turn-one clicks per game,
Protect habits (protect_sim.py), and my win share per archetype on the same seeds.
usage: python3 value_behaviour.py <dir A> <dir B> [label A] [label B]"""
import json, glob, sys, math, collections, protect_sim
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
GROUPS = {'sleep': {'Sleep Powder', 'Spore', 'Hypnosis', 'Yawn', 'Dark Void', 'Sing', 'Lovely Kiss'},
          'other status': {'Will-O-Wisp', 'Thunder Wave', 'Nuzzle', 'Toxic', 'Glare', 'Stun Spore'},
          'Tailwind': {'Tailwind'}, 'Trick Room': {'Trick Room'}, 'setup': {'Calm Mind', 'Nasty Plot', 'Swords Dance', 'Dragon Dance', 'Belly Drum', 'Quiver Dance', 'Bulk Up', 'Shell Smash'},
          'screens': {'Reflect', 'Light Screen', 'Aurora Veil'}, 'redirection': {'Follow Me', 'Rage Powder'}, 'Fake Out': {'Fake Out'},
          'Protect': protect_sim.PROTECT, 'switch': {'switch'}}
A, B = sys.argv[1], sys.argv[2]; la = sys.argv[3] if len(sys.argv) > 3 else A; lb = sys.argv[4] if len(sys.argv) > 4 else B
def load(d):
    R = {}; share = {}; acts = {s: collections.Counter() for s in 'ab'}; t1 = {s: collections.Counter() for s in 'ab'}; n = {s: 0 for s in 'ab'}; games = 0
    for f in glob.glob(d + '/*.json'):
        try: r = json.load(open(f))
        except Exception: continue
        R[(r['arch'], r['pair'])] = {g['g']: g['v'] for g in r['rows'] if g.get('v') is not None}; share[(r['arch'], r['pair'])] = r['share']
        for g in r['rows']:
            S = g.get('states') or []; games += 1
            for t, s in enumerate(S):
                for side in 'ab':
                    for mon, a in protect_sim.parse(s[side]).items():
                        n[side] += 1
                        for gname, mv in GROUPS.items():
                            if a in mv:
                                acts[side][gname] += 1
                                if t == 0: t1[side][gname] += 1
    return R, share, acts, t1, n, games
RA, sh, aA, tA, nA, gA = load(A); RB, _, aB, tB, nB, gB = load(B)
print(f"{la}: {gA} games | {lb}: {gB} games")
for side, nm in (('a', 'mine'), ('b', 'theirs')):
    print(f"\n{nm}: clicks per 100 actions ({la} -> {lb}) and on turn one per game")
    for gname in GROUPS:
        print(f"   {gname:13s} {100*aA[side][gname]/max(1,nA[side]):5.1f} -> {100*aB[side][gname]/max(1,nB[side]):5.1f}    turn one {tA[side][gname]/max(1,gA):.2f} -> {tB[side][gname]/max(1,gB):.2f}")
for lab, d in ((la, A), (lb, B)):
    C = protect_sim.count([d])
    print(f"\n{lab}: " + ' | '.join(f"{'mine' if s == 'a' else 'theirs'}: Protect again after a fresh one {100*c['double']/max(1,c['opps']):.1f}% of {c['opps']}, switch out {100*c['switch_after']/max(1,c['opps']):.1f}%" for s, c in C.items()))
print(f"\nmy win share, {la} -> {lb} (paired):")
tot = var_t = W_t = 0.0
for a in SH:
    teams = [t for t in RB if t[0] == a and t in RA]
    if not teams: continue
    W = sum(sh[t] for t in teams); m = var = ma = mb = 0.0
    for t in teams:
        gs = [g for g in RB[t] if g in RA[t]]
        if len(gs) < 2: continue
        d = [RB[t][g] - RA[t][g] for g in gs]; w = sh[t] / W; mu = sum(d) / len(d)
        m += w * mu; var += w * w * sum((x - mu) ** 2 for x in d) / (len(d) - 1) / len(d)
        ma += w * sum(RA[t][g] for g in gs) / len(gs); mb += w * sum(RB[t][g] for g in gs) / len(gs)
    print(f"   {a:30s} {100*ma:5.1f}% -> {100*mb:5.1f}%   {100*m:+5.1f} ± {100*math.sqrt(var):.1f}")
    tot += SH[a] * m; var_t += SH[a] ** 2 * var; W_t += SH[a]
if W_t: print(f"   ladder-weighted: {100*tot/W_t:+.2f} ± {100*math.sqrt(var_t)/W_t:.2f}")
