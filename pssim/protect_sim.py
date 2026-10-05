"""Double-Protect check, sim side (2026-10-04): the same measure as protect_replays.py on full battles with the per-turn state log
(champ-battle-v4, BATTLE_TURNS=1): after a fresh Protect (the Pokemon did not Protect the turn before), how often its next action is
Protect again, out of the times it acts again; plus the overall Protect share of actions. My side and their side separately.
usage: python3 protect_sim.py <results dir> [...]"""
import json, glob, sys, collections
PROTECT = {'Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Baneful Bunker', 'Silk Trap', 'Burning Bulwark', 'Obstruct'}
base = lambda n: n.split('-Mega')[0]
def parse(label):
    out = {}
    for part in (label or '').split(' | '):
        if ': ' not in part: continue
        mon, a = part.split(': ', 1); a = a.replace(' (Mega)', '')
        out[base(mon)] = 'switch' if a.startswith('switch to ') else a.partition(' -> ')[0]
    return out
def count(dirs):
    C = {s: collections.Counter() for s in 'ab'}
    for d in dirs:
        for f in glob.glob(d + '/*.json'):
            try: r = json.load(open(f))
            except Exception: continue
            for g in r['rows']:
                S = g.get('states')
                if not S: continue
                for side in 'ab':
                    A = [parse(s[side]) for s in S]; C[side]['games'] += 1
                    for t, acts in enumerate(A):
                        for mon, a in acts.items():
                            C[side]['actions'] += 1; C[side]['protects'] += a in PROTECT
                            if a not in PROTECT or (t > 0 and A[t - 1].get(mon) in PROTECT) or t + 1 >= len(A): continue
                            nxt = A[t + 1].get(mon)
                            if nxt is None: continue
                            k = '_tr' if S[t + 1].get('tr', 0) > 0 else '_notr'
                            for sfx in ('', k):
                                C[side]['opps' + sfx] += 1; C[side]['double' + sfx] += nxt in PROTECT; C[side]['switch_after' + sfx] += nxt == 'switch'
    return C
if __name__ == '__main__':
    for side, c in count(sys.argv[1:]).items():
        print(f"{'mine' if side == 'a' else 'theirs'}: {c['games']} games, Protect {100*c['protects']/max(1,c['actions']):.1f}% of actions; after a fresh Protect, "
              f"next action is Protect again {c['double']}/{c['opps']} = {100*c['double']/max(1,c['opps']):.1f}%, switch out {100*c['switch_after']/max(1,c['opps']):.1f}%"
              f" | Trick Room up: {100*c['double_tr']/max(1,c['opps_tr']):.1f}% of {c['opps_tr']} | down: {100*c['double_notr']/max(1,c['opps_notr']):.1f}% of {c['opps_notr']}")
