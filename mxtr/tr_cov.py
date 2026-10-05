"""Best hit on each threat for the Trick Room six (the old sheet's Coverage gaps table), on the same exact-damage engine
as the Matchups grid. Pessimistic: each threat at the bulkiest of its three spreads for the side hit, items that stop a
knockout applied (Focus Sash from full, resist berries), Sitrus never counted. Your Torkoal is in its own sun; other
weather and terrain come from the threat (Pelipper rain, Charizard sun, Tyranitar sand, Rillaboom or seeded Sneasler
Grassy Terrain, Indeedee Psychic Terrain). Water Spout and Eruption from full HP, spread moves at spread damage."""
import json, os
os.environ["TR"] = "0"
import matchup as M
from tr_grid import FOES, SIX
old = json.load(open("../team-sheet.html.usage.json")) if os.path.exists("../team-sheet.html.usage.json") else {}
ITEMNOTE = {"Focus Sash": "Sash", "Chople": "Chople", "Colbur": "Colbur", "Sitrus": "Sitrus"}
rows = []
for f in FOES:
    t, b, nat, sps, item, u = M.F[f]
    per = {}
    for mine in SIX:
        md = M.MINE[mine]
        for mv in md["moves"]:
            if mv.get("flinch") or mv.get("setup") or mv.get("status"): continue      # Fake Out left out, as before
            phys = mv["c"] == "p"
            best = None
            for sp in sps:                                    # bulkiest spread for this side
                st = M.stats(b, nat, sp); sc = st[0] * (st[2] if phys else st[4])
                if best is None or sc > best[0]: best = (sc, st)
            st = best[1]
            me = M.make(mine, md["types"], md["st"], md["item"], md["ab"], md["moves"], M.WEIGHT.get(mine, 50))
            them = M.make(f, t, st, item, M.TABIL.get(f, set()), M.TM[f], M.WEIGHT.get(f, 50))
            field = M.init_field(mine, f, "field")
            M.entry(them, me, field); me["stg"] = {k: 0 for k in me["stg"]}               # full Attack (no Intimidate, no Defiant)
            dm = [M.damage(me, them, mv, field, r / 100) for r in range(85, 101)]
            if max(dm) == 0: continue
            hp = them["maxhp"]
            ko = sum(1 for d in dm if d >= hp)
            if item == "Focus Sash": ko = 0
            e = M.eff(M.mtype(me, mv, field), t)
            pct = 100 * dm[-1] / hp
            if mine not in per or pct > per[mine][0]: per[mine] = (pct, mv["n"], e, ko, dm[0], dm[-1], hp)
    rank = sorted(per.items(), key=lambda kv: -kv[1][0])
    nk = sum(1 for m, v in rank if v[3] == 16)
    top = rank[0]; nxt = rank[1] if len(rank) > 1 else None
    note = f" ({ITEMNOTE[item]})" if item in ITEMNOTE else ""
    usage = old.get(f, 0)
    rows.append([f + note, usage, top[0], top[1][1], top[1][2], round(top[1][0], 1), nk,
                 (f"{nxt[0]} {nxt[1][1]} {nxt[1][0]:.0f}%" if nxt else "—"), "sash" if item == "Focus Sash" else "",
                 [[m, v[1], round(v[0], 1), v[3]] for m, v in rank]])
rows.sort(key=lambda r: (r[6], r[5]))
json.dump(rows, open("tr_cov.json", "w"), ensure_ascii=False)
for r in rows: print(f"{r[0]:22s} {r[1]:6} best {r[2]:10s} {r[3]:16s} {r[4]:g}x {r[5]:6.1f}%  KO by {r[6]}  next {r[7]}")
