"""Stock win rates against Perish trap, from real regional results instead of battles (user, 2026-10-05: Perish lines are long and
specific, so the sim plays them badly; Perish is a small part of the meta, so use real data for it). With TS_PERISH=real, evaluate.py
skips the 6 Perish jobs and scores that archetype at the rate real teams of our team's archetype had against Perish.

Rates: every Reg M-C regional match (Baltimore, Brisbane, Frankfurt; regmatch/) between a team of archetype A and a Perish team,
match win rate shrunk toward the pooled rate with a prior worth K matches, then converted to the per-game rate whose best-of-3
match rate is that (the sims are single games). Writes perish_stock.json (aggregates only; regmatch/ with player names stays local).
  python3 perish_stock.py
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, 'bring'))
K = 30

if __name__ == '__main__':
    sys.argv = sys.argv[:1]
    import archmatch as AM
    rw, rn = AM.real_regionals()
    w0 = sum(rw[(a, 'Perish')] for a in AM.NAMES if a != 'Perish'); n0 = sum(rn[(a, 'Perish')] for a in AM.NAMES if a != 'Perish')
    p0 = w0 / n0
    rates = {a: round(AM.game_rate((rw[(a, 'Perish')] + K * p0) / (rn[(a, 'Perish')] + K)), 4) for a in AM.NAMES}
    out = dict(source='Reg M-C regionals (Baltimore, Brisbane, Frankfurt), pokedata.ovh standings', prior_matches=K,
               pooled=round(AM.game_rate(p0), 4), matches={a: rn[(a, 'Perish')] for a in AM.NAMES}, rate=rates)
    json.dump(out, open(os.path.join(HERE, 'perish_stock.json'), 'w'), indent=1)
    for a in AM.NAMES: print(f"{a:12s} {rn[(a, 'Perish')]:4d} matches  per-game {100 * rates[a]:.1f}%")
    print(f"pooled (non-Perish teams vs Perish) {100 * out['pooled']:.1f}% per game")
