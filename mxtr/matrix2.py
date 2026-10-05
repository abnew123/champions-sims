"""Build the Matchups grid from the game solver (solver*.json) plus the roll simulator.

Verdicts (pessimistic rolls, both sides free to pick any move, Protect left out):
  counter  switches in and wins (a trade counts, as before)
  check    wins if already out
  guess    a guessing game: your chance with best play from both sides
  wall     can't win, but survives the whole window at your worst rolls
  roll     loses at worst rolls, wins some of the time on real rolls
  lost     loses on any rolls
Run finalize.py after the rollsolve min-adjustment: it turns a wall that wins on
real rolls into a Roll and words a true wall's detail as "stalls".
"""
import json, re, sys
import numpy as np
import spgame as S
import rolls as R

SIX = ["Rillaboom", "Incineroar", "Sneasler", "Gholdengo", "Kingambit", "Salamence"]
ITEM = {"Gholdengo": "Sash", "Kingambit": "Chople", "Incineroar": "Sitrus"}
EXTRA = {"Volcarona": (S.STATUS,), "Whimsicott": (S.STATUS,)}
S.FULL = True

NOTES = {   # hand-written explanations for guesses and special cases, keyed foe|mine
 "Basculegion|Kingambit": "switching in is a coin flip: Aqua Jet goes first and dodges Sucker Punch",
 "Arcanine-H|Kingambit": "Extreme Speed dodges Sucker Punch but only chips 9%: mostly keep clicking Sucker Punch",
 "M-Metagross|Kingambit": "Bullet Punch (1 in 4 carry it) goes first and dodges Sucker Punch: a coin flip",
}

def load():
    d = {}
    for f in ("solv5_0.json", "solv5_1.json"):
        try: d.update(json.load(open(f)))
        except FileNotFoundError: pass
    return d

def pct(v): return int(round(100 * v))

def principal(mine, foe, mode):
    """my move sequence on the solver's line at the worst spread (for squares that changed to a win)"""
    worst = None
    for sp in S.F[foe][3]:
        g = S.Game(foe, sp, EXTRA.get(foe, ()), T=8, cutoff=0.0, mine=mine, trade=1.0, bullet=False)
        r = g.start(mode)
        if worst is None or r[0][0] < worst[1][0][0]: worst = (g, r)
    g, ((v, info), entry_mv, hp) = worst
    me, them, field = g.fresh()
    field["mode"] = mode
    if mode == "switch":
        S.entry(them, me, field); me["stg"]["atk"] = 0; S.entry(me, them, field); them["out_turns"] = 1
        d = next(o for o in S.their_options(them, me, field, 0, g.extra) if o["n"] == entry_mv)
        if not d.get("status"): S.apply_hit(them, me, d, field, "max", [])
        S.end_of_turn([me, them], field)
    else:
        S.entry(me, them, field); S.entry(them, me, field)
    seq = []
    for t in range(1, 9):
        v, info = g.V(me, them, field, t)
        mo = S.my_options(me, them, field, t); to = S.their_options(them, me, field, t, g.extra)
        i = int(np.argmax(info["x"]))
        # their reply: the one that keeps my value lowest for my chosen move
        best_j, best_v = 0, 2
        for j in range(len(to)):
            m2, t2, f2 = S.cp(me), S.cp(them), dict(field)
            r = S.play_turn(m2, t2, f2, mo[i], to[j], [])
            val = r if r is not None else g.V(m2, t2, f2, t + 1)[0]
            if val < best_v: best_v, best_j = val, j
        seq.append(mo[i]["n"])
        r = S.play_turn(me, them, field, mo[i], to[best_j], [])
        if r is not None: break
    return seq

def phrase(v, t0=None):
    if v is None: return "not re-checked"
    if v > 1 - 1e-9: return "trades" if (t0 is not None and t0 < 1 - 1e-9) else "wins"
    if v < 1e-9: return "loses"
    return "a coin flip" if abs(v - 0.5) < 0.04 else f"{pct(v)}% with best play"

def build():
    sol = load(); rows = json.load(open("matchup.json")); out = []; changes = []
    for f, u, cs in rows:
        cells = []
        for j, c in enumerate(cs):
            mine = SIX[j]; k = f"{f}|{mine}"; x = sol.get(k, {})
            prefix = c["det"].split(" · switching in")[0]
            dep, note, v, p = "", NOTES.get(k, ""), None, None
            if not x or x.get("timeout"):
                v = c["v"] if c["v"] in ("counter", "check", "wall") else "lost"
                det = c["det"] + " (not re-checked)"
                cells.append(dict(v=v, pct=None, dep=c.get("dep", "").replace("Sucker Punch", "").strip(" +"), note="", det=det)); continue
            sw, fd = x["sw"], x["fd"]
            if sw > 1 - 1e-9 and x.get("sw_t0", 1) > 1 - 1e-9: v = "counter"        # a switch-in that only trades is not a counter
            elif fd > 1 - 1e-9: v = "check"
            elif fd > 1e-9: v, p = "guess", pct(fd)
            elif x.get("fd_c1", 0) > 1e-9: v = "wall"                              # survives the window at worst rolls
            else: v = "loses"
            if mine in ITEM:
                if v == "counter" and x.get("sw_noitem", 1) < 1 - 1e-9: dep = ITEM[mine]
                if v == "check" and x.get("fd_noitem", 1) < 1 - 1e-9: dep = ITEM[mine]
            mo = re.search(r"switching in (.*?), already out (.*)$", c["det"])
            def keep(oldp, v, t0):
                ow = "win" if oldp.startswith(("wins", "trades")) else "loss" if oldp.startswith("loses") else "stall"
                nw = "win" if v > 1 - 1e-9 else "loss" if v < 1e-9 else "guess"
                if ow == nw and not (ow == "win" and (oldp.startswith("wins") != (t0 is None or t0 > 1 - 1e-9))): return oldp
                return phrase(v, t0)
            det = f"{prefix} · switching in {keep(mo.group(1), sw, x.get('sw_t0'))}, already out {keep(mo.group(2), fd, x.get('fd_t0'))}"
            old = c["v"]
            better = {"loses": 0, "wall": 1, "guess": 2, "check": 3, "counter": 4}
            if better.get(v, 0) > better.get(old, 0) and v in ("counter", "check"):
                seq = principal(mine, f, "switch" if v == "counter" else "field")
                comp = []
                for mvn in seq:
                    if comp and comp[-1][0] == mvn: comp[-1][1] += 1
                    else: comp.append([mvn, 1])
                note = (note + "; " if note else "") + "line: " + " → ".join(m if n == 1 else f"{m} ×{n}" for m, n in comp)
            if v != old: changes.append((k, old, v, p))
            cells.append(dict(v=v, pct=p, dep=dep, note=note, det=det))
        out.append([f, u, cells])
    # the losing side: how often real rolls rescue it
    for f, u, cells in out:
        for j, c in enumerate(cells):
            if c["v"] in ("loses", "wall"):
                best = min(S.Game(f, sp, EXTRA.get(f, ()), T=6, cutoff=0.0, mine=SIX[j], trade=1.0, bullet=False, rm="max", rt="min").start("field")[0][0]
                           for sp in S.F[f][3])
                pr = R.p_win(SIX[j], f, n=250) if best > 1e-9 else 0.0     # if even the best rolls lose, nothing rescues it
                c["roll"] = pct(pr)
                if c["v"] == "loses":
                    c["v"], c["pct"] = ("roll", pct(pr)) if pr >= 0.01 else ("lost", None)
    return out, changes

if __name__ == "__main__":
    out, changes = build()
    json.dump(out, open("matchup2.json", "w"), separators=(",", ":"), ensure_ascii=True)
    for ch in changes: print("changed:", ch)
    from collections import Counter
    print(Counter(c["v"] for f, u, cs in out for c in cs))
