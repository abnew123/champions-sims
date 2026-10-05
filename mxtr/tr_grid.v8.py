"""Matchups grid for the Trick Room six, same method as grid_exact.py (stages A-E), run once without and once with
Trick Room up (env TR=1). Roll odds use the Monte Carlo duel only (n=200 per spread and policy)."""
import json, time, sys, signal, re, os
import multiprocessing as mp
SIX = ["Blastoise", "Torkoal", "Farigiraf", "Kingambit", "Hatterene"]
ITEM = {"Kingambit": os.environ.get("KG_ITEM", "Chople"), "Farigiraf": os.environ.get("FG_ITEM", "Sitrus"), "Hatterene": os.environ.get("HT_ITEM", "Life Orb"), "Torkoal": os.environ.get("TK_ITEM", "Charcoal")}
if os.environ.get("GRID_MONS"): SIX = os.environ["GRID_MONS"].split(",")
FOES = ["Rillaboom", "Sneasler", "M-Salamence", "Incineroar", "Kingambit", "Basculegion", "M-Floette", "Farigiraf", "M-Golisopod",
        "Pelipper", "Indeedee-F", "Gholdengo", "Arcanine-H", "Sylveon", "Whimsicott", "Archaludon", "M-Tyranitar", "M-Baxcalibur",
        "Garchomp", "M-Garchomp Z", "Milotic", "M-Charizard Y", "M-Gardevoir", "M-Raichu Y", "M-Staraptor", "M-Metagross", "Volcarona",
        "Corviknight", "Dragapult", "Torkoal", "Hatterene", "Indeedee", "Armarouge", "M-Gengar", "Sinistcha"]
TRM = os.environ.get("TR") == "1"
def stage_a(job):
    foe, mine = job
    import matchup as M
    c = M.classify(mine, foe)
    def spd_of(name, mineside):
        if mineside: return M.MINE[name]["st"][5]
        t, b, nat, sps, item, u = M.F[name]
        spd = [M.stats(b, nat, sp)[5] for sp in sps]
        if item == "Choice Scarf": spd = [x * 3 // 2 for x in spd]
        if name == "Sneasler": spd = [x * 2 for x in spd]      # seeded in their Rillaboom's terrain
        if TRM: return min(spd)                                  # worst case under Trick Room: their slowest spread
        v = max(spd)
        if name in M.SPEED_EST: v = max(v, M.SPEED_EST[name])
        return v
    ms, ts = spd_of(mine, True), spd_of(foe, False)
    if ms == ts: spd = "speed tie"
    elif TRM: spd = "moves first" if ms < ts else "moves second"
    else: spd = "faster" if ms > ts else "slower"
    wi, wo, sw, fd = c["inn"], c["out"], c["sw"], c["fd"]
    def word(r): return {"win": f"wins T{r[1]}", "trade": f"trades T{r[1]}",
                         "loss": ("loses on entry" if r[1] == 0 else f"loses T{r[1]}"), "stall": "stalemate"}[r[0]]
    det = (f"takes {wi[0]:.0f}% ({wi[1]}) · deals {wo[1]*100//wo[3]}–{wo[2]*100//wo[3]}% ({wo[0]}) · {spd} · "
           f"switching in {word(sw)}, already out {word(fd)}")
    return job, dict(v=c["v"], det=det, inn=list(wi), out=list(wo), sw=list(sw), fd=list(fd))
def stage_b(job):
    foe, mine = job
    import classify3 as C
    x = None
    for T, lim in ((8, 60), (6, 60), (5, 90)):
        signal.alarm(lim)
        try:
            x = C.cellcalc(mine, foe, T); signal.alarm(0); break
        except C.TO:
            pass
    signal.alarm(0)
    return job, (x or dict(timeout=True))
def stage_d(job):
    foe, mine = job
    import spgame as S, rolls as R
    S.FULL = True
    EXTRA = {"Volcarona": (S.STATUS,), "Whimsicott": (S.STATUS,)}
    best = min(S.Game(foe, sp, EXTRA.get(foe, ()), T=6, cutoff=0.0, mine=mine, trade=1.0, bullet=False, rm="max", rt="min").start("field")[0][0]
               for sp in S.F[foe][3])
    mc = R.p_win(mine, foe, n=200) if best > 1e-9 else 0.0
    return job, dict(best=best, mc=mc, r5=min(99, int(5 * round(100 * mc / 5))))
def stage_line(job):
    foe, mine, mode = job
    import matrix2 as MX
    return job, MX.principal(mine, foe, mode)
def pmap(fn, jobs, label):
    out = {}; t1 = time.time()
    with mp.get_context("spawn").Pool(2, maxtasksperchild=8) as pool:
        for i, (job, r) in enumerate(pool.imap_unordered(fn, jobs)):
            out[job] = r
            if (i + 1) % 25 == 0 or i + 1 == len(jobs): print(f"  {label}: {i+1}/{len(jobs)}  {time.time()-t1:5.0f}s", flush=True)
    return out
def pct(v): return int(round(100 * v))
def phrase(v, t0=None):
    if v is None: return "not re-checked"
    if v > 1 - 1e-9: return "trades" if (t0 is not None and t0 < 1 - 1e-9) else "wins"
    if v < 1e-9: return "loses"
    return "a coin flip" if abs(v - 0.5) < 0.04 else f"{pct(v)}% with best play"
def keep(oldp, v, t0):
    ow = "win" if oldp.startswith(("wins", "trades")) else "loss" if oldp.startswith("loses") else "stall"
    nw = "win" if v > 1 - 1e-9 else "loss" if v < 1e-9 else "guess"
    if ow == nw and not (ow == "win" and (oldp.startswith("wins") != (t0 is None or t0 > 1 - 1e-9))): return oldp
    p = phrase(v, t0)
    return "is " + p if nw == "guess" else p
if __name__ == "__main__":
    tag = ("tr" if TRM else "notr") + os.environ.get("GRID_TAG", "")
    keys = [(f, m) for f in FOES for m in SIX]
    A = pmap(stage_a, keys, "greedy"); json.dump({"|".join(k): v for k, v in A.items()}, open(f"gx_A_{tag}.json", "w"))
    B = pmap(stage_b, keys, "solver"); json.dump({"|".join(k): v for k, v in B.items()}, open(f"gx_B_{tag}.json", "w"))
    bad = [k for k, x in B.items() if x.get("timeout")]
    if bad: print("TIMEOUTS", bad, flush=True)
    cells = {}; need_line = []
    better = {"loses": 0, "wall": 1, "guess": 2, "check": 3, "counter": 4}
    for k in keys:
        f, mine = k; x = B[k]; a = A[k]
        if x.get("timeout"):
            cells[k] = dict(v="lost" if a["v"] == "loses" else a["v"], pct=None, dep="", note="", det=a["det"] + " (solver timed out; greedy result)"); continue
        sw, fd = x["sw"], x["fd"]; p = None; dep = ""
        if sw > 1 - 1e-9 and x.get("sw_t0", 1) > 1 - 1e-9: v = "counter"
        elif fd > 1 - 1e-9: v = "check"
        elif fd > 1e-9: v, p = "guess", pct(fd)
        elif x.get("fd_c1", 0) > 1e-9: v = "wall"
        else: v = "loses"
        if mine in ITEM:
            if v == "counter" and x.get("sw_noitem", 1) < 1 - 1e-9: dep = ITEM[mine]
            if v == "check" and x.get("fd_noitem", 1) < 1 - 1e-9: dep = ITEM[mine]
        prefix = a["det"].split(" · switching in")[0]
        mo = re.search(r"switching in (.*?), already out (.*)$", a["det"])
        det = f"{prefix} · switching in {keep(mo.group(1), sw, x.get('sw_t0'))}, already out {keep(mo.group(2), fd, x.get('fd_t0'))}"
        if better.get(v, 0) > better.get(a["v"], 0) and v in ("counter", "check"):
            need_line.append((f, mine, "switch" if v == "counter" else "field"))
        cells[k] = dict(v=v, pct=p, dep=dep, note="", det=det, greedy=a["v"])
    L = pmap(stage_line, need_line, "lines") if need_line else {}
    for (f, mine, mode), seq in L.items():
        comp = []
        for mvn in seq:
            if comp and comp[-1][0] == mvn: comp[-1][1] += 1
            else: comp.append([mvn, 1])
        cells[(f, mine)]["note"] = "line: " + " → ".join(m if n == 1 else f"{m} ×{n}" for m, n in comp)
    lose = [k for k in keys if cells[k]["v"] in ("loses", "wall")]
    D = pmap(stage_d, lose, "rolls") if lose else {}
    json.dump({"|".join(k): v for k, v in D.items()}, open(f"gx_D_{tag}.json", "w"))
    for k in lose:
        c = cells[k]; r5 = D[k]["r5"]; c["roll"] = r5
        if c["v"] == "loses": c["v"], c["pct"] = ("roll", r5) if r5 >= 1 else ("lost", None)
    for k in keys:
        c = cells[k]
        if c["v"] != "wall": continue
        x = B[k]; roll = c.get("roll") or 0
        survives = x.get("fd_c1", 0) > 1e-9
        if roll >= 1: c["v"], c["pct"] = "roll", roll
        elif not survives: c["v"], c["pct"] = "lost", None
        else:
            m = re.search(r"^(.*) · switching in (.*?), already out (.*)$", c["det"]); pre, sw_p, fd_p = m.groups()
            if x.get("fd_c1", 0) > 1 - 1e-9 and (fd_p.startswith("loses") or fd_p.startswith("stalemate")): fd_p = "stalls"
            if x.get("sw_c1", 0) > 1 - 1e-9 and (sw_p.startswith("loses") or sw_p.startswith("stalemate")): sw_p = "stalls"
            c["det"] = f"{pre} · switching in {sw_p}, already out {fd_p}"
    json.dump({"|".join(k): v for k, v in cells.items()}, open(f"gx_cells_{tag}.json", "w"), ensure_ascii=True)
    from collections import Counter
    print(tag, Counter(c["v"] for c in cells.values()), flush=True)
    print("done", flush=True)
