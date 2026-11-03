"""What do the bot's ladder opponents show us? (2026-11-03, the user: since Showdown's bot opt-in most opponents are other bots, several
stronger than ours, "maybe we can learn things from them that we can't learn vs humans".) On bot/decision_audit.py's rebuilt and solved
decisions (built with AUDIT_SINCE / AUDIT_UNTIL, solved with AUDIT_LIVE: the bot's engine, net and calc data), by opponent (names from the
logs' |player| lines; chat is never read). Per decision with both plays known, the bot's win chance (real: log-odds x live.CAL) moves to the
next decision's estimate, or the result after the last one; the move splits into
  their play   the opponent's actual joint valued against the bot's mix, minus the game value. Against an equilibrium mix it cannot be
               negative, so it is what the opponent gave away by the engine's reckoning (near 0: they play what the engine would)
  our play     the bot's actual joint against the opponent's equilibrium, minus the game value (what the bot gave away)
  rest         what happened minus both: luck (rolls, crits, accuracy) plus the engine's error. Luck averages out; a steady negative rest
               against one opponent says their plays work better than the engine rates them, which is what we can learn from
Then each loss to the opponents named on the command line (default: those who beat the bot twice or more): turn by turn, with the biggest
drop's plays (each slot play's weight in the engine's equilibrium mix for that side, and its rating against the slot's best).
  .venv/bin/python3 bot/opp_ledger.py <audit prefix, e.g. bot/out/pos/botopp_1103> [opponent ...]"""
import os, sys, json, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'pssim')); sys.path.insert(0, os.path.join(ROOT, 'evalbar')); sys.path.insert(0, os.path.join(ROOT, 'bot'))
import human_lines as HL, live as LV, opp_report as OR
from ladder_lines import cse
real = lambda v: HL.resc(v, LV.CAL)


def main(prefix, names):
    meta = json.load(open(prefix + '.meta.json'))['turns']
    rows = {r['name']: r for r in map(json.loads, open(prefix + '_turns.eval.jsonl')) if 'error' not in r and 'sides' in r}
    G = {g['room']: g for g in map(json.loads, open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl')))}
    seq = collections.defaultdict(list)
    for name, m in meta.items():
        r = rows.get(name + ' h0 p1')
        if r and G[m['room']]['won'] is not None: seq[m['room']].append((m['turn'], r))
    opp = {room: OR.log_info(room, G[room]['side'])[0] or '?' for room in seq}
    D = collections.defaultdict(list)          # room -> [(turn, win chance, their play, our play, rest, row)]
    for room, S in seq.items():
        S.sort(key=lambda x: x[0]); won = 1.0 if G[room]['won'] else 0.0
        for i, (t, r) in enumerate(S):
            s0, s1 = r['sides'][0], r['sides'][1]; v = real(r['value'])
            nxt = real(S[i + 1][1]['value']) if i + 1 < len(S) and S[i + 1][0] == t + 1 else (won if i + 1 == len(S) else None)
            if s0.get('actual_v') is None or s1.get('actual_v') is None or nxt is None: continue
            th, ou = real(1 - s1['actual_v']) - v, real(s0['actual_v']) - v
            D[room].append((t, v, th, ou, nxt - v - th - ou, r))
    fmt = lambda room: 'Bo1' if G[room].get('format') == 'gen9championsvgc2026regmc' else 'Bo3'
    print(f"{sum(len(x) for x in D.values())} decisions with both plays known, in {len(D)} games; the bot's win chance, points per decision (± SE by game)")
    print(f"  {'opponent':20s} {'games':>9s} {'decisions':>9s} {'their play':>13s} {'our play':>13s} {'rest':>13s}")
    by = collections.defaultdict(list)
    for room, xs in D.items(): by[opp[room]].append(room)
    for o, rooms in sorted(by.items(), key=lambda kv: -sum(len(D[r]) for r in kv[1])) + [('(all)', list(D))]:
        P = [(room, x) for room in rooms for x in D[room]]
        w = sum(1 for room in rooms if G[room]['won'])
        cells = [cse([(room, x[k]) for room, x in P]) for k in (2, 3, 4)]
        print(f"  {o:20s} {f'{w}-{len(rooms) - w}':>9s} {len(P):9d} " + ' '.join(f"{100 * mu:+6.2f} ± {100 * se:4.2f}" for mu, se, _ in cells))
    want = set(names) or {o for o, rooms in by.items() if sum(1 for r in rooms if not G[r]['won']) >= 2}
    for room in sorted((r for r in D if not G[r]['won'] and opp[r] in want), key=lambda r: G[r]['when']):
        xs = D[room]
        print(f"\n{G[room]['when'][:16]} UTC  {fmt(room)} loss to {opp[room]} ({G[room].get('team')}), {room}")
        for t, v, th, ou, rs, r in xs:
            print(f"    t{t:<3d} win chance {100 * v:5.1f}   their play {100 * th:+6.1f}   our play {100 * ou:+6.1f}   rest {100 * rs:+6.1f}")
        t, v, th, ou, rs, r = min(xs, key=lambda x: x[2] + x[3] + x[4])
        print(f"  biggest drop t{t}: {100 * (th + ou + rs):+.1f}")
        for sd, who in ((1, 'they'), (0, 'we')):
            for sl in r['sides'][sd]['slots']:
                o = next((x for x in sl['options'] if x.get('actual')), None)
                if not o: continue
                best = max(x['v'] for x in sl['options'])
                top = max(sl['options'], key=lambda x: x['w'])
                print(f"    {who:4s} {sl['mon']}: {o['label']}  (mix {100 * o['w']:.0f}%, rated {100 * (real(o['v']) - real(best)):+.1f} vs the slot's best;"
                      f" the mix's top: {top['label']} {100 * top['w']:.0f}%)")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
