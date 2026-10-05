"""How often a losing square is won on damage rolls or a speed tie.

Same one-on-one as the grid (already on the field, their best line against your
best reply), but every hit draws one of the 16 real damage rolls at random and a
speed tie is a coin flip each turn. Their line is chosen pessimistically: for each
of their three spreads and each of their policies we take your best policy, then
keep the lowest win rate. Accuracy, crits and secondary effects stay out, as in
the rest of the sheet. A trade counts as a win, as it does for a check.
"""
import random, json, sys
import matchup as M

def duel_rand(mine, foe, spread, policy, mpolicy, rng):
    md = M.MINE[mine]
    me = M.make(mine, md["types"], md["st"], md["item"], md["ab"], md["moves"], M.WEIGHT.get(mine, 50))
    me["policy"] = mpolicy
    t, b, nat, sps, item, u = M.F[foe]
    st = M.stats(b, nat, spread)
    if foe in M.SPEED_EST: st[5] = max(st[5], M.SPEED_EST[foe])
    them = M.make(foe, t, st, item, M.TABIL.get(foe, set()), M.TM[foe], M.WEIGHT.get(foe, 50))
    them["policy"] = policy
    field = M.init_field(mine, foe, "field")
    M.entry(me, them, field); M.entry(them, me, field)
    for turn in range(1, 9):
        a = M.choose(me, them, field, turn, True); d = M.choose(them, me, field, turn, False)
        pa = M.effective_prio(me, a, field) if a else -9
        pd = M.effective_prio(them, d, field) if d else -9
        me_first = M.goes_first(me, them, pa, pd, rng.random() < 0.5)
        order = [(me, them, a), (them, me, d)]
        if not me_first: order.reverse()
        flinched = False
        for i, (x, y, mv) in enumerate(order):
            if x["hp"] <= 0 or y["hp"] <= 0 or mv is None: continue
            if i == 1 and flinched: continue
            if x.get("par") and rng.random() < 0.125: continue         # fully paralysed: 1 in 8 in Champions
            if mv["sucker"]:
                other = order[1 - i][2]
                if i == 1 or other is None or other.get("setup") or other.get("status") or (other["charge"] and not order[1 - i][0]["charged"]):
                    continue
            x["glaive_vuln"] = False
            hp0 = y["hp"]
            M.apply_hit(x, y, mv, field, rng.randint(85, 100) / 100, [])
            if mv.get("flinch") and i == 0 and y["hp"] < hp0: flinched = True
            if y["hp"] <= 0 or x["hp"] <= 0: break
        for p in (me, them):
            p["out_turns"] += 1
            if p.get("recharging", 0) > 0: p["recharging"] -= 1
        if them["hp"] <= 0: return 1          # includes a trade
        if me["hp"] <= 0: return 0
        M.end_of_turn([me, them], field)
        if them["hp"] <= 0: return 1
        if me["hp"] <= 0: return 0
    return 0                                   # stalemate is not a win

def p_win(mine, foe, n=600, seed=1):
    rng = random.Random(seed)
    tp = ["greedy", "norecoil", "nodrop"] + (["setup"] if any(m.get("setup") for m in M.TM[foe]) else []) \
         + (["nocharge"] if any(m["charge"] for m in M.TM[foe]) else []) + (["noglaive"] if any(m["glaive"] for m in M.TM[foe]) else [])
    worst = 1.0
    prio_ok = any(m["pr"] > 0 or m.get("grassy_prio") for m in M.MINE[mine]["moves"])
    for sp in M.F[foe][3]:
        for p in tp:
            st = rng.getstate()
            vals = [sum(duel_rand(mine, foe, sp, p, mp, rng) for _ in range(n)) / n for mp in ("greedy", "norecoil", "nodrop")]
            if prio_ok:              # also: click priority whenever it can finish on a good roll (same random draws as greedy)
                r2 = random.Random(); r2.setstate(st)
                vals.append(sum(duel_rand(mine, foe, sp, p, "prio", r2) for _ in range(n)) / n)
            worst = min(worst, max(vals))
    return worst

if __name__ == "__main__":
    rows = json.load(open("matchup.json"))
    SIX = ["Rillaboom", "Incineroar", "Sneasler", "Gholdengo", "Kingambit", "Salamence"]
    out = {}
    for f, u, cs in rows:
        for j, c in enumerate(cs):
            if c["v"] in ("loses", "wall"):
                p = p_win(SIX[j], f)
                out[f"{f}|{SIX[j]}"] = p
                if p > 0 or c["rolly"]: print(f"{f:14s} {SIX[j]:10s} {c['v']:5s} rolly={c['rolly']!s:5s} P(win on rolls) = {100*p:5.1f}%")
    json.dump(out, open("rolls.json", "w"))
