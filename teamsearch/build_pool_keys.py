"""Opponent group weights for the pool climbs (pool_keys*.json, read by poolmode.keys()): each core group's count among the
regional team sheets (regionals/regional_teams.json, every event in it) and its number of real pool entries (pssim/opp_pool.json).
The original pool_keys.json (2026-10-06, 2,531 sheets from Baltimore, Brisbane and Frankfurt, aggregate counts only) stays as it
was so the earlier climbs reproduce; this writes a new file for a new climb (user, 2026-10-12: add Louisville and Recife).
  python3 build_pool_keys.py [out = pool_keys_2026-10-12.json]       then TS_POOL_KEYS=<out> for the climb
"""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import poolmode as PM
OUT = sys.argv[1] if len(sys.argv) > 1 else 'pool_keys_2026-10-12.json'
T = json.load(open(os.path.join(HERE, '..', 'regionals', 'regional_teams.json')))
reg = collections.Counter(PM.group_of(t['six']) for t in T)
pool = {k: len(v) for k, v in PM.entries().items()}
keys = {k: dict(regional=reg.get(k, 0), share=reg.get(k, 0) / len(T), pool=pool.get(k, 0)) for k in sorted(set(reg) | set(pool), key=lambda k: -reg.get(k, 0))}
ev = collections.Counter(t['event'] for t in T)
json.dump(dict(source='regional team sheets (regionals/regional_teams.json: ' + ', '.join(f"{e} {n}" for e, n in ev.items()) +
               ') tagged with pssim core rules (results/core_rules_both_100.json); other split by pro_replays.arch; pool = pssim/opp_pool.json entries',
               regional_teams=len(T), keys=keys), open(os.path.join(HERE, OUT), 'w'), indent=1)
print(f"{OUT}: {len(T)} regional sheets, {len(keys)} groups")
