"""The Bo1 net A/B (bot/brain.py net_arm, limits.json "net_ab"; 2026-10-21): the Bo1 games since the A/B's start by arm (the battle
number's parity: odd d4, even acc), W-L and wins above the Elo expectation per game, the difference with its standard error. The Eval bar's
luck-adjusted measure (result - turn-1 rating - dice, evalbar/ledger.py) needs about a third fewer games; this is the raw-wins check that
goes beside it.
  .venv/bin/python3 bot/ab_report.py"""
import os, json, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def main():
    L = json.load(open(os.path.join(ROOT, 'bot', 'limits.json'))); out = []
    for fmt, ab in (L.get('net_ab') or {}).items():
        G = [json.loads(l) for l in open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl')) if '"arm"' in l]
        G = [g for g in G if g.get('format') == fmt and g['when'][:10] >= ab.get('start', '')]
        by = {}
        for g in G:
            num = g['room'].split('-')[2]
            if not num.isdigit(): continue
            arm = ab['odd' if int(num) % 2 else 'even']['name']
            ex = (g['won'] - 1 / (1 + 10 ** ((g['oppRating'] - g['myRating']) / 400))) if g.get('oppRating') and g.get('myRating') else None
            by.setdefault(arm, []).append((g['won'], ex))
        out.append(f"net A/B ({fmt}, since {ab.get('start')}):")
        stats = {}
        for arm, rs in sorted(by.items()):
            w = sum(r[0] for r in rs); ex = [r[1] for r in rs if r[1] is not None]
            m = sum(ex) / len(ex) if ex else 0.0; se = 0.5 / math.sqrt(len(ex)) if ex else 0.0; stats[arm] = (m, se)
            out.append(f"  {arm:4s} {len(rs):4d} games {w}-{len(rs) - w}  wins above Elo expectation {100 * m:+.1f} ± {100 * se:.1f} per 100 games")
        if len(stats) == 2:
            (a, (ma, sa)), (b, (mb, sb)) = sorted(stats.items())
            out.append(f"  {b} - {a}: {100 * (mb - ma):+.1f} ± {100 * math.sqrt(sa ** 2 + sb ** 2):.1f} per 100 games")
    print('\n'.join(out))
if __name__ == '__main__': main()
