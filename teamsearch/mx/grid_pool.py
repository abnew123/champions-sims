"""One-on-one matchup cells for teamsearch sets: same method as mxtr/tr_grid.py (greedy duel, game solver, roll odds), but one
job = one set against all 46 threats, written to out/<tr|notr>/<grid id>.json, so runs resume and grow with the set list.
The note/line stage is skipped (the planner only reads v / roll).

  cd teamsearch/mx && TR=0 NPROC=3 python3 grid_pool.py [grid ids...]      (default: start teams + swap pool)
Then merge.py builds per-team GRID_DIRs in the planner's format.
"""
import json, os, sys, time, signal
import multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__))
TRM = os.environ.get("TR") == "1"
TAG = "tr" if TRM else "notr"
OUT = os.path.join(HERE, "out", TAG)
FOES = ["Rillaboom", "Sneasler", "M-Salamence", "Incineroar", "Kingambit", "Basculegion", "M-Floette", "Farigiraf", "M-Golisopod",
        "Pelipper", "Indeedee-F", "Gholdengo", "Arcanine-H", "Sylveon", "Whimsicott", "Archaludon", "M-Tyranitar", "M-Baxcalibur",
        "Garchomp", "M-Garchomp Z", "Milotic", "M-Charizard Y", "M-Gardevoir", "M-Raichu Y", "M-Staraptor", "M-Metagross", "Volcarona",
        "Corviknight", "Dragapult", "Torkoal", "Hatterene", "Indeedee", "Armarouge", "M-Gengar", "Sinistcha",
        "M-Swampert", "Grimmsnarl", "Politoed", "Venusaur", "Excadrill", "M-Froslass", "M-Camerupt", "M-Delphox", "M-Aerodactyl",
        "M-Mawile", "M-Dragonite"]                                  # mxtr's 35 + the 11 'ext' threats

def word(r): return {"win": f"wins T{r[1]}", "trade": f"trades T{r[1]}", "loss": ("loses on entry" if r[1] == 0 else f"loses T{r[1]}"), "stall": "stalemate"}[r[0]]

def cell(mine, foe):
    import matchup as M, classify3 as C, spgame as S, rolls as R
    c = M.classify(mine, foe)
    wi, wo = c["inn"], c["out"]
    deals = f"deals {wo[1]*100//wo[3]}–{wo[2]*100//wo[3]}% ({wo[0]})" if wo else "no attacks"          # (a pure support set)
    det = f"takes {wi[0]:.0f}% ({wi[1]}) · {deals} · switching in {word(c['sw'])}, already out {word(c['fd'])}"
    x = None
    for T, lim in ((8, 60), (6, 60), (5, 90)):                     # the solver, with tr_grid's time limits
        signal.alarm(lim)
        try: x = C.cellcalc(mine, foe, T); signal.alarm(0); break
        except C.TO: pass
    signal.alarm(0)
    if x is None:
        return dict(v="lost" if c["v"] == "loses" else c["v"], pct=None, det=det + " (solver timed out; greedy result)", greedy=c["v"])
    sw, fd = x["sw"], x["fd"]; p = None
    if sw > 1 - 1e-9 and x.get("sw_t0", 1) > 1 - 1e-9: v = "counter"
    elif fd > 1 - 1e-9: v = "check"
    elif fd > 1e-9: v, p = "guess", int(round(100 * fd))
    elif x.get("fd_c1", 0) > 1e-9: v = "wall"
    else: v = "loses"
    out = dict(v=v, pct=p, det=det, greedy=c["v"], solver={k: (round(b, 4) if isinstance(b, float) else b) for k, b in x.items()})
    if v in ("loses", "wall"):                                      # roll odds (tr_grid stage D)
        S.FULL = True
        EXTRA = {"Volcarona": (S.STATUS,), "Whimsicott": (S.STATUS,)}
        best = min(S.Game(foe, sp, EXTRA.get(foe, ()), T=6, cutoff=0.0, mine=mine, trade=1.0, bullet=False, rm="max", rt="min").start("field")[0][0]
                   for sp in S.F[foe][3])
        mc = R.p_win(mine, foe, n=200) if best > 1e-9 else 0.0
        r5 = min(99, int(5 * round(100 * mc / 5)))
        out["roll"] = r5
        if v == "loses": out["v"], out["pct"] = ("roll", r5) if r5 >= 1 else ("lost", None)
        elif r5 >= 1: out["v"], out["pct"] = "roll", r5
        elif x.get("fd_c1", 0) <= 1e-9: out["v"] = "lost"
    return out

def job(gid):
    path = os.path.join(OUT, gid.replace("/", "_") + ".json")
    if os.path.exists(path): return gid, None
    t = time.time(); res = {}
    for foe in FOES: res[foe] = cell(gid, foe)
    json.dump(dict(gid=gid, tr=TRM, secs=round(time.time() - t, 1), cells=res), open(path + ".tmp", "w"))
    os.replace(path + ".tmp", path)
    return gid, time.time() - t

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    ids = sys.argv[1:]
    if not ids:
        root = os.path.join(HERE, "..")
        idx = json.load(open(os.path.join(root, "teams", "start", "index.json")))
        pool = json.load(open(os.path.join(root, "swap_pool.json")))
        extra = os.path.join(HERE, "extra_ids.txt")                 # e.g. canonical sets for the bring heuristic's replay fit
        ex = [l.strip() for l in open(extra) if l.strip()] if os.path.exists(extra) else []
        ids = list(dict.fromkeys([p["gid"] for p in pool] + [g for v in idx.values() for g in v["gids"]] + ex))
    todo = [g for g in ids if not os.path.exists(os.path.join(OUT, g.replace("/", "_") + ".json"))]
    print(time.strftime("%I:%M %p"), f"{TAG}: {len(todo)} of {len(ids)} sets to do", flush=True)
    t0 = time.time(); n = 0
    with mp.get_context("spawn").Pool(int(os.environ.get("NPROC", "1")), maxtasksperchild=4) as pool:
        for gid, dt in pool.imap_unordered(job, todo):
            n += 1
            print(time.strftime("%I:%M %p"), f"{TAG} {n}/{len(todo)} {gid} {dt:.0f}s", flush=True)
    print(time.strftime("%I:%M %p"), f"{TAG} done in {(time.time()-t0)/60:.1f} min", flush=True)
