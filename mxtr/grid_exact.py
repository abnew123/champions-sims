"""The whole Matchups grid again, on the exact-damage simulator (patch_exact_sim.py) with Champions'
1-in-8 full paralysis. Same method as before, in one pass:
  A  greedy duel -> the detail line (takes / deals / speed / switching in / already out)   [matrix.py, newrows.py]
  B  game solver -> sw, fd and the tie-break values                                       [classify3.cellcalc]
  C  verdicts, item dependence, solver wording, principal lines                           [matrix2.build]
  D  roll odds for losing squares: min(Monte Carlo n=250, solver-sampled n=40), to 5, cap 99 [build_new.py]
  E  the wall rule                                                                         [finalize.py]
Row order, usage figures and ranks are kept from matchup2.json. Hand notes are carried over and re-checked by hand."""
import json, time, sys, signal
import multiprocessing as mp

SIX = ["Rillaboom", "Incineroar", "Sneasler", "Gholdengo", "Kingambit", "Salamence"]
ITEM = {"Gholdengo": "Sash", "Kingambit": "Chople", "Incineroar": "Sitrus"}

def stage_a(job):
    foe, mine = job
    import matchup as M
    c = M.classify(mine, foe)
    def my_speed():
        s = M.MINE[mine]["st"][5]
        if mine == "Sneasler" and foe != "Indeedee-F": s *= 2
        return s
    def their_speed():
        t, b, nat, sps, item, u = M.F[foe]
        v = max(M.stats(b, nat, sp)[5] for sp in sps)
        if foe in M.SPEED_EST: v = max(v, M.SPEED_EST[foe])
        if foe == "Sneasler": v *= 2
        return v
    ms, ts = my_speed(), their_speed()
    spd = "faster" if ms > ts else ("tie" if ms == ts else "slower")
    wi, wo, sw, fd = c["inn"], c["out"], c["sw"], c["fd"]
    def word(r): return {"win": f"wins T{r[1]}", "trade": f"trades T{r[1]}",
                         "loss": ("loses on entry" if r[1] == 0 else f"loses T{r[1]}"), "stall": "stalemate"}[r[0]]
    sash = " — Sash holds from full" if mine == "Gholdengo" and wi[0] >= 100 else ""
    det = (f"takes {wi[0]:.0f}% ({wi[1]}){sash} · deals {wo[1]*100//wo[3]}–{wo[2]*100//wo[3]}% ({wo[0]}) · {spd} · "
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
    import spgame as S, rolls as R, rollsolve as RS
    S.FULL = True
    RS.PARA = (foe == "M-Raichu Y")
    EXTRA = {"Volcarona": (S.STATUS,), "Whimsicott": (S.STATUS,)}
    best = min(S.Game(foe, sp, EXTRA.get(foe, ()), T=6, cutoff=0.0, mine=mine, trade=1.0, bullet=False, rm="max", rt="min").start("field")[0][0]
               for sp in S.F[foe][3])
    mc = R.p_win(mine, foe, n=250) if best > 1e-9 else 0.0
    rs = RS.p_solver(mine, foe) if best > 1e-9 else 0.0
    return job, dict(best=best, mc=mc, rs=rs, r5=min(99, int(5 * round(100 * min(mc, rs) / 5))))

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
    return "is " + p if nw == "guess" else p          # the sheet reads "switching in is a coin flip"

if __name__ == "__main__":
    old = json.load(open("matchup2.json"))
    keys = [(f, m) for f, u, cs in old for m in SIX]
    A = pmap(stage_a, keys, "greedy"); json.dump({"|".join(k): v for k, v in A.items()}, open("gx_A.json", "w"))
    B = pmap(stage_b, keys, "solver"); json.dump({"|".join(k): v for k, v in B.items()}, open("gx_B.json", "w"))
    assert not any(x.get("timeout") for x in B.values()), [k for k, x in B.items() if x.get("timeout")]
    # C: verdicts
    cells = {}
    better = {"loses": 0, "wall": 1, "guess": 2, "check": 3, "counter": 4}
    need_line = []
    for k in keys:
        f, mine = k; x = B[k]; a = A[k]
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
        import re
        mo = re.search(r"switching in (.*?), already out (.*)$", a["det"])
        det = f"{prefix} · switching in {keep(mo.group(1), sw, x.get('sw_t0'))}, already out {keep(mo.group(2), fd, x.get('fd_t0'))}"
        had_line = any(r[0] == f and r[2][SIX.index(mine)].get("note", "").startswith("line:") for r in old)
        if (better.get(v, 0) > better.get(a["v"], 0) or had_line) and v in ("counter", "check"):
            need_line.append((f, mine, "switch" if v == "counter" else "field"))
        cells[k] = dict(v=v, pct=p, dep=dep, note="", det=det, greedy=a["v"])
    L = pmap(stage_line, need_line, "lines")
    for (f, mine, mode), seq in L.items():
        comp = []
        for mvn in seq:
            if comp and comp[-1][0] == mvn: comp[-1][1] += 1
            else: comp.append([mvn, 1])
        cells[(f, mine)]["note"] = "line: " + " → ".join(m if n == 1 else f"{m} ×{n}" for m, n in comp)
    # D: rolls
    lose = [k for k in keys if cells[k]["v"] in ("loses", "wall")]
    D = pmap(stage_d, lose, "rolls"); json.dump({"|".join(k): v for k, v in D.items()}, open("gx_D.json", "w"))
    for k in lose:
        c = cells[k]; r5 = D[k]["r5"]; c["roll"] = r5
        if c["v"] == "loses": c["v"], c["pct"] = ("roll", r5) if r5 >= 1 else ("lost", None)
    # E: wall rule
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
            elif fd_p.startswith("loses"): print(f"WARNING {k}: survives only on a guess (fd_c1={x['fd_c1']:.2f})")
            if x.get("sw_c1", 0) > 1 - 1e-9 and (sw_p.startswith("loses") or sw_p.startswith("stalemate")): sw_p = "stalls"
            c["det"] = f"{pre} · switching in {sw_p}, already out {fd_p}"
    json.dump({"|".join(k): v for k, v in cells.items()}, open("gx_cells.json", "w"), ensure_ascii=True)
    print("done", flush=True)
