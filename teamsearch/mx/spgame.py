"""Sucker Punch as a guessing game.

Each turn both sides pick a move at the same time. Kingambit chooses between its
best normal attack and Sucker Punch; the threat chooses between its best attack,
any priority move that goes before Sucker Punch, its setup move, and (if it
carries one) a status move other than Protect. Protect is left out on purpose:
it stops every move, not just Sucker Punch.

Payoff = Kingambit's chance to win (trade = 0.5). Each node is a zero-sum
matrix game solved by linear programming, so the value is what Kingambit gets
when both sides guess as well as possible. Rolls stay pessimistic: Kingambit
min, threat max, worst of the threat's spreads.
"""
import copy, json, sys
exec(open('matchup.py').read().split('if __name__')[0])
import numpy as np
from scipy.optimize import linprog

STATUS = M("status move", "Normal", 0, "s", status=True)          # Tailwind, Encore, Rage Powder ...
BULLET_PUNCH = M("Bullet Punch", "Steel", 40, "p", 1.3, pr=1)      # Tough Claws: contact

def solve(A):
    """value and both mixed strategies of a zero-sum game, row player maximises"""
    A = np.asarray(A, float); m, n = A.shape
    def lp(B):
        k, l = B.shape
        c = np.zeros(k + 1); c[-1] = -1
        res = linprog(c, A_ub=np.hstack([-B.T, np.ones((l, 1))]), b_ub=np.zeros(l),
                      A_eq=np.r_[np.ones(k), 0].reshape(1, -1), b_eq=[1],
                      bounds=[(0, 1)] * k + [(None, None)], method="highs")
        return res.x[-1], res.x[:k]
    v, x = lp(A)
    _, y = lp(1 - A.T)          # column player maximises (1 - payoff)
    return v, x, y

def attacks(mv): return mv is not None and not mv.get("setup") and not mv.get("status")

def cp(p):
    q = dict(p); q["stg"] = dict(p["stg"]); return q

def plain(mv):
    """an attack with no side effect, so a stronger plain attack of the same priority dominates it"""
    return not (mv["rc"] or mv["dr"] or mv["drop"] or mv["charge"] or mv["first"] or mv["glaive"] or mv["sucker"] or mv.get("recharge") or mv.get("flinch")
                or mv.get("knockoff") or mv.get("bodypress") or mv.get("ignore_def") or mv.get("terrainpulse")
                or mv["kills_terrain"] or mv["needs_terrain"] or mv.get("setup") or mv.get("status") or mv["pr"] or mv.get("grassy_prio"))

def prune(opts, att, dfn, field, roll):
    """drop plain attacks beaten by a stronger plain attack (same priority bracket)"""
    pl = [o for o in opts if attacks(o) and plain(o)]
    if len(pl) <= 1: return opts
    best = max(pl, key=lambda o: damage(att, dfn, o, field, roll))
    return [o for o in opts if not (attacks(o) and plain(o)) or o is best]

def play_turn(me, them, field, a, d, log, rm="min", rt="max", tie=None, par=None):
    """par: whether a paralysed Pokemon of yours is fully paralysed this turn (None = your worst luck when rm is min)"""
    pa = effective_prio(me, a, field); pd = effective_prio(them, d, field)
    if tie is None: tie = (rm == "max")                    # best case: ties to you
    me_first = goes_first(me, them, pa, pd, tie)
    order = [(me, them, a, rm), (them, me, d, rt)]
    if not me_first: order.reverse()
    flinched = False
    for i, (x, y, mv, roll) in enumerate(order):
        if x["hp"] <= 0 or y["hp"] <= 0: continue
        if i == 1 and flinched: log.append(f"{x['name']} flinches"); continue
        if x.get("par"):
            full = (par if par is not None else rm == "min") if x is me else (rt == "min")
            if full: log.append(f"{x['name']} is fully paralysed"); continue
        if mv.get("status"):
            if mv.get("heal"): x["hp"] = min(x["maxhp"], x["hp"] + js_round(x["maxhp"] * mv["heal"]))
            log.append(f"{x['name']} {mv['n']}"); continue
        if mv["sucker"]:
            other = order[1 - i][2]
            if i == 1 or not attacks(other):
                log.append(f"{x['name']} Sucker Punch fails"); continue
        x["glaive_vuln"] = False
        hp0 = y["hp"]
        apply_hit(x, y, mv, field, roll, log)
        if mv.get("flinch") and i == 0 and y["hp"] < hp0: flinched = True
        if y["hp"] <= 0 or x["hp"] <= 0: break
    for p in (me, them):
        p["out_turns"] += 1
        if p.get("recharging", 0) > 0: p["recharging"] -= 1
    if me["hp"] <= 0 and them["hp"] <= 0: return 0.5
    if them["hp"] <= 0: return 1.0
    if me["hp"] <= 0: return 0.0
    end_of_turn([me, them], field)
    if them["hp"] <= 0: return 1.0
    if me["hp"] <= 0: return 0.0
    return None

def my_options(me, them, field, t):
    if me.get("recharging", 0) > 0: return [STATUS]
    opts = [mv for mv in me["moves"] if usable(me, them, mv, field, t, True) and attacks(mv)]
    if me["name"] == "Kingambit" and not FULL:   # original two-button game: best attack vs Sucker Punch
        normal = [o for o in opts if not o["sucker"] and effective_prio(me, o, field) <= 0]
        best = max(normal, key=lambda o: damage(me, them, o, field, "min"))
        return [best] + [o for o in opts if o["sucker"]]
    out = [o for o in opts if damage(me, them, o, field, "min") > 0 or o["charge"]]
    return prune(out, me, them, field, "min") or [STATUS]

FULL = True          # every usable move for both sides (False = the original Kingambit-only game)
def their_options(them, me, field, t, extra):
    if them.get("recharging", 0) > 0: return [STATUS]
    opts = [mv for mv in them["moves"] if usable(them, me, mv, field, t, False)]
    if FULL:
        out = prune([o for o in opts if attacks(o) and (damage(them, me, o, field, "max") > 0 or o["charge"])], them, me, field, "max")
    else:
        atk = [o for o in opts if attacks(o) and effective_prio(them, o, field) <= 0]
        out = []
        if atk:
            out.append(max(atk, key=lambda o: damage(them, me, o, field, "max")))
            clean = [o for o in atk if not o["rc"] or "rock_head" in them["ab"]]
            if clean and clean[0] is not out[0]:
                alt = max(clean, key=lambda o: damage(them, me, o, field, "max"))
                if alt is not out[0]: out.append(alt)
        out += [o for o in opts if attacks(o) and effective_prio(them, o, field) > 0]      # priority
    out += [o for o in opts if o.get("setup") or o.get("heal")]
    out += extra
    return out or [STATUS]

def key(me, them, field, t):
    f = lambda p: (p["hp"], tuple(sorted(p["stg"].items())), p["item_used"], p["item"], p["charged"], p["glaive_vuln"], p["out_turns"] > 0,
                   p["seeded"], p.get("recharging", 0), bool(p.get("par")))
    return (t, f(me), f(them), field["terrain"])

class Game:
    def __init__(self, foe, spread, extra=(), T=7, cutoff=0.5, mine="Kingambit", trade=0.5, noitem=False, bullet=True, rm="min", rt="max", ties=None, paras=None):
        self.paras = paras
        self.foe, self.spread, self.extra, self.T, self.cutoff, self.mine = foe, spread, list(extra), T, cutoff, mine
        self.rm, self.rt, self.ties = rm, rt, ties
        self.trade, self.noitem, self.bullet = trade, noitem, bullet
        self.memo = {}
    def fresh(self):
        md = MINE[self.mine]
        me = make(self.mine, md["types"], md["st"], None if self.noitem else md["item"], md["ab"], md["moves"], WEIGHT.get(self.mine, 50))
        t, b, nat, sps, item, u = F[self.foe]
        st = stats(b, nat, self.spread)
        if self.foe in SPEED_EST: st[5] = max(st[5], SPEED_EST[self.foe])
        moves = TM[self.foe] + ([BULLET_PUNCH] if self.foe == "M-Metagross" and self.mine == "Kingambit" and self.bullet else [])
        them = make(self.foe, t, st, item, TABIL.get(self.foe, set()), moves, WEIGHT.get(self.foe, 50))
        field = init_field(self.mine, self.foe, None)
        return me, them, field
    def V(self, me, them, field, t):
        if t > self.T: return self.cutoff, None
        k = key(me, them, field, t)
        if k in self.memo: return self.memo[k]
        mo = my_options(me, them, field, t); to = their_options(them, me, field, t, self.extra)
        cache = {}
        def cell(i, j):
            if (i, j) not in cache:
                m2, t2, f2 = cp(me), cp(them), dict(field)
                rm = self.rm[t] if isinstance(self.rm, list) else self.rm
                rt = self.rt[t] if isinstance(self.rt, list) else self.rt
                tie = self.ties[t] if self.ties else None
                par = self.paras[t] if self.paras else None
                r = play_turn(m2, t2, f2, mo[i], to[j], [], rm, rt, tie, par)
                if r == 0.5: r = self.trade
                cache[(i, j)] = r if r is not None else self.V(m2, t2, f2, t + 1)[0]
            return cache[(i, j)]
        def early(v, x, y):
            out = (v, dict(me=[o["n"] for o in mo], them=[o["n"] for o in to],
                           A=[[cache.get((a, b), np.nan) for b in range(len(to))] for a in range(len(mo))], x=x, y=y))
            self.memo[k] = out; return out
        for i in range(len(mo)):                       # a move that wins against every reply
            if all(cell(i, j) >= 1 - 1e-9 for j in range(len(to))):
                x = np.zeros(len(mo)); x[i] = 1; return early(1.0, x, np.ones(len(to)) / len(to))
        for j in range(len(to)):                       # a reply of theirs that beats every move
            if all(cell(i, j) <= 1e-9 for i in range(len(mo))):
                y = np.zeros(len(to)); y[j] = 1; return early(0.0, np.ones(len(mo)) / len(mo), y)
        A = [[cell(i, j) for j in range(len(to))] for i in range(len(mo))]
        v, x, y = solve(A)
        out = (v, dict(me=[o["n"] for o in mo], them=[o["n"] for o in to], A=A, x=x, y=y))
        self.memo[k] = out
        return out
    def start(self, mode):
        me, them, field = self.fresh()
        field["mode"] = mode
        if mode == "switch":                     # they pick the entry action that hurts most
            entry(them, me, field); me["stg"]["atk"] = 0; entry(me, them, field); them["out_turns"] = 1
            if "grassy_surge" in me["ab"]: field["terrain"] = "grassy"      # your Rillaboom's terrain replaces theirs as it lands
            md = MINE[self.mine]
            if md.get("entry_st"): me["st"] = list(md["entry_st"])          # a Mega switches in unevolved
            best = None
            for d in their_options(them, me, field, 0, self.extra):
                m2, t2, f2 = cp(me), cp(them), dict(field)
                if not d.get("status"):
                    if d["sucker"]: continue
                    apply_hit(t2, m2, d, f2, self.rt[0] if isinstance(self.rt, list) else self.rt, [])
                m2["st"] = list(md["st"])                                    # Mega Evolves before it moves
                if m2["hp"] <= 0: r = (0.0, None)
                else:
                    end_of_turn([m2, t2], f2)
                    r = self.V(m2, t2, f2, 1)
                if best is None or r[0] < best[0][0]: best = (r, d["n"], (m2["hp"], t2["hp"]))
            return best
        entry(me, them, field); entry(them, me, field)
        return (self.V(me, them, field, 1), None, (me["hp"], them["hp"]))

def report(foe, mode, extra=(), label=""):
    res = []
    for sp in F[foe][3]:
        g = Game(foe, sp, extra)
        (v, info), entry_mv, hp = g.start(mode)
        res.append((v, sp, info, entry_mv, hp))
    v, sp, info, entry_mv, hp = min(res, key=lambda r: r[0])
    print(f"{foe:12s} {mode:6s} {label:28s} Kingambit wins {100*v:5.1f}%   worst spread {sp}" + (f"  entry: {entry_mv}" if entry_mv else ""))
    return v, info

if __name__ == "__main__":
    cases = [("Basculegion", "switch", (), "Aqua Jet"), ("Basculegion", "field", (), "Aqua Jet"),
             ("Arcanine-H", "field", (), "Extreme Speed"),
             ("Volcarona", "field", (STATUS,), "Quiver Dance + status"), ("Volcarona", "field", (), "Quiver Dance only"),
             ("Whimsicott", "switch", (STATUS,), "status move"), ("Whimsicott", "field", (STATUS,), "status move"),
             ("M-Metagross", "field", (), "Bullet Punch"),
             ("M-Tyranitar", "field", (), "Dragon Dance"), ("M-Tyranitar", "switch", (), "Dragon Dance"),
             ("M-Baxcalibur", "field", (), "Dragon Dance"), ("M-Baxcalibur", "switch", (), "Dragon Dance")]
    for foe, mode, extra, lab in cases:
        report(foe, mode, extra, lab)
