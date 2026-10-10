"""The page's Matchups cells and Coverage hits for a team, one Trick Room mode: called by charts.py as its own process.
  TR=1|0 POOL_FILE=<pool.json> python3 charts_worker.py <job.json> <out.json>
  job: {names: [my set ids], threats: [...], cells: {name: path of that set's cached grid cells for this mode}}

Starts from the grid step's cells (verdict, roll odds, solver values) and adds what only the page shows, the way mxtr/tr_grid.py did
for the first sheet: who moves first, the wording of each cell's detail line, whether a win needs the item intact, and the move
line for wins the simple greedy play misses. With TR=0 it also finds each attacker's hardest hit on every threat (mxtr/tr_cov.py)."""
import sys, os, json, re
job, out = json.load(open(sys.argv[1])), os.path.abspath(sys.argv[2])
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MX = os.path.join(ROOT, 'teamsearch', 'mx')
os.chdir(MX); sys.path.insert(0, MX); sys.path.append(os.path.join(ROOT, 'mxtr'))     # matrix2 (the move-line finder) lives in mxtr/
import matchup as M
TRM = os.environ.get('TR') == '1'
missing = [n for n in job['names'] if n not in M.MINE]
if missing: sys.exit(f"{missing}: the one-on-one code could not build these sets")

def speed_word(mine, foe):
    def theirs():
        t, b, nat, sps, item, u = M.F[foe]
        spd = [M.stats(b, nat, sp)[5] for sp in sps]
        if item == "Choice Scarf": spd = [x * 3 // 2 for x in spd]
        if foe == "Sneasler": spd = [x * 2 for x in spd]                     # seeded in their Rillaboom's terrain
        wx = M.init_field(mine, foe, None)["weather"]                        # Swift Swim / Sand Rush / Chlorophyll in their weather
        if any(k in M.TABIL.get(foe, ()) and wx == w for k, w in M.WX_SPEED.items()): spd = [x * 2 for x in spd]
        if TRM: return min(spd)                                              # worst case under Trick Room: their slowest spread
        v = max(spd)
        return max(v, M.SPEED_EST[foe]) if foe in M.SPEED_EST else v
    ms, ts = M.MINE[mine]["st"][5], theirs()
    if ms == ts: return "speed tie"
    if TRM: return "moves first" if ms < ts else "moves second"
    return "faster" if ms > ts else "slower"

def pct(v): return int(round(100 * v))
def phrase(v, t0=None):
    if v is None: return "not re-checked"
    if v > 1 - 1e-9: return "trades" if (t0 is not None and t0 < 1 - 1e-9) else "wins"
    if v < 1e-9: return "loses"
    return "a coin flip" if abs(v - 0.5) < 0.04 else f"{pct(v)}% with best play"
def keep(oldp, v, t0):
    """the greedy wording, unless the solver's value says otherwise"""
    ow = "win" if oldp.startswith(("wins", "trades")) else "loss" if oldp.startswith("loses") else "stall"
    nw = "win" if v > 1 - 1e-9 else "loss" if v < 1e-9 else "guess"
    if ow == nw and not (ow == "win" and (oldp.startswith("wins") != (t0 is None or t0 > 1 - 1e-9))): return oldp
    p = phrase(v, t0)
    return "is " + p if nw == "guess" else p

BETTER = {"loses": 0, "wall": 1, "guess": 2, "check": 3, "counter": 4}
def page_cell(mine, foe, c):
    """c: the grid step's cell {v, pct, det, greedy, solver?, roll?} -> {v, pct, dep, note, det}"""
    pre, tail = c["det"].split(" · switching in ", 1)
    pre += " · " + speed_word(mine, foe); x = c.get("solver")
    if x is None: return dict(v=c["v"], pct=None, dep="", note="", det=f"{pre} · switching in {tail}")       # solver timed out: greedy result
    sw_p, fd_p = re.match(r"^(.*?), already out (.*)$", tail).groups(); sw, fd = x["sw"], x["fd"]
    sw_p, fd_p = keep(sw_p, sw, x.get("sw_t0")), keep(fd_p, fd, x.get("fd_t0"))
    v0 = ("counter" if sw > 1 - 1e-9 and x.get("sw_t0", 1) > 1 - 1e-9 else "check" if fd > 1 - 1e-9 else "guess" if fd > 1e-9
          else "wall" if x.get("fd_c1", 0) > 1e-9 else "loses")                                              # before roll odds
    dep = ""
    if v0 == "counter" and x.get("sw_noitem", 1) < 1 - 1e-9: dep = M.MINE[mine]["item"]
    if v0 == "check" and x.get("fd_noitem", 1) < 1 - 1e-9: dep = M.MINE[mine]["item"]
    note = ""
    if BETTER.get(v0, 0) > BETTER.get(c["greedy"], 0) and v0 in ("counter", "check"):                        # a win greedy play misses: show the line
        import matrix2 as MX
        comp = []
        for mvn in MX.principal(mine, foe, "switch" if v0 == "counter" else "field"):
            if comp and comp[-1][0] == mvn: comp[-1][1] += 1
            else: comp.append([mvn, 1])
        note = "line: " + " → ".join(m if n == 1 else f"{m} ×{n}" for m, n in comp)
    if c["v"] == "wall":                                                                                     # a true wall: it stalls, it does not lose
        if x.get("fd_c1", 0) > 1 - 1e-9 and fd_p.startswith(("loses", "stalemate")): fd_p = "stalls"
        if x.get("sw_c1", 0) > 1 - 1e-9 and sw_p.startswith(("loses", "stalemate")): sw_p = "stalls"
    return dict(v=c["v"], pct=c.get("pct"), dep=dep or "", note=note, det=f"{pre} · switching in {sw_p}, already out {fd_p}")

def best_hits(foe):
    """each of my attackers' hardest hit on the threat: {mine: [max %, move, effectiveness, KO rolls of 16]}; pessimistic (bulkiest spread
    for the side hit, Focus Sash and resist berries applied, their weather and terrain up, my full Attack, Fake Out left out)"""
    t, b, nat, sps, item, u = M.F[foe]; per = {}
    for mine in job["names"]:
        md = M.MINE[mine]
        for mv in md["moves"]:
            if mv.get("flinch") or mv.get("setup") or mv.get("status"): continue
            phys = mv["c"] == "p"; best = None
            for sp in sps:
                st = M.stats(b, nat, sp); sc = st[0] * (st[2] if phys else st[4])
                if best is None or sc > best[0]: best = (sc, st)
            me = M.make(mine, md["types"], md["st"], md["item"], md["ab"], md["moves"], M.WEIGHT.get(mine, 50))
            them = M.make(foe, t, best[1], item, M.TABIL.get(foe, set()), M.TM[foe], M.WEIGHT.get(foe, 50))
            field = M.init_field(mine, foe, "field")
            M.entry(them, me, field); me["stg"] = {k: 0 for k in me["stg"]}
            if mv.get("charge"): me["stg"]["spa"] = 1                  # Electro Shot, Meteor Beam: +1 Sp. Atk before the hit
            dm = [M.damage(me, them, mv, field, r / 100) for r in range(85, 101)]
            if max(dm) == 0: continue
            hp = them["maxhp"]; ko = 0 if item == "Focus Sash" else sum(1 for d in dm if d >= hp); p = 100 * dm[-1] / hp
            if mine not in per or p > per[mine][0]: per[mine] = [p, mv["n"], M.eff(mv["t"], t), ko]
    return per

res = {"cells": {}, "cov": {}, "item": {f: M.F[f][4] for f in job["threats"]}}
for n in job["names"]:
    cells = json.load(open(job["cells"][n]))["cells"]
    for f in job["threats"]: res["cells"][f"{f}|{n}"] = page_cell(n, f, cells[f])
if not TRM: res["cov"] = {f: best_hits(f) for f in job["threats"]}
json.dump(res, open(out, "w"))
