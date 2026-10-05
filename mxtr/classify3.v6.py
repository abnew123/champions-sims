import json, time, sys, signal, spgame as S
S.FULL = True
EXTRA = {"Volcarona": (S.STATUS,), "Whimsicott": (S.STATUS,)}
SIX = ["Rillaboom","Incineroar","Sneasler","Gholdengo","Kingambit","Salamence"]
class TO(Exception): pass
def _alarm(*a): raise TO()
signal.signal(signal.SIGALRM, _alarm)
def V(mine, foe, mode, T, trade=1.0, cutoff=0.0, noitem=False):
    return min(S.Game(foe, sp, EXTRA.get(foe, ()), T=T, cutoff=cutoff, mine=mine, trade=trade, noitem=noitem, bullet=False).start(mode)[0][0]
               for sp in S.F[foe][3])
def cellcalc(mine, foe, T):
    r = dict(T=T, sw=V(mine, foe, "switch", T), fd=V(mine, foe, "field", T))
    if r["fd"] < 1e-9: r["fd_c1"] = V(mine, foe, "field", T, cutoff=1.0)
    if r.get("fd_c1", 0) > 1e-9 and r["sw"] < 1e-9: r["sw_c1"] = V(mine, foe, "switch", T, cutoff=1.0)   # does a wall also survive switching in?
    if r["fd"] > 1 - 1e-9: r["fd_t0"] = V(mine, foe, "field", T, trade=0.0)
    if r["sw"] > 1 - 1e-9: r["sw_t0"] = V(mine, foe, "switch", T, trade=0.0)
    if mine in ("Kingambit", "Farigiraf"):
        if r["sw"] > 1 - 1e-9: r["sw_noitem"] = V(mine, foe, "switch", T, noitem=True)
        elif r["fd"] > 1 - 1e-9: r["fd_noitem"] = V(mine, foe, "field", T, noitem=True)
    return r
if __name__ == "__main__":
    part, nparts, outf = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    rows = json.load(open("matchup.json")); done = json.load(open("solver.json"))
    todo = [(f, j, c) for f, u, cs in rows for j, c in enumerate(cs) if f"{f}|{SIX[j]}" not in done]
    todo = todo[part::nparts]; out = {}
    for f, j, c in todo:
        k = f"{f}|{SIX[j]}"; t1 = time.time(); r = None
        for T, lim in ((8, 60), (6, 60), (5, 90)):
            S_memo_reset = None
            signal.alarm(lim)
            try:
                r = cellcalc(SIX[j], f, T); signal.alarm(0); break
            except TO:
                print(f"  {k}: T={T} timed out", flush=True)
        signal.alarm(0)
        if r is None: r = dict(timeout=True)
        r["old"] = c["v"]; out[k] = r; json.dump(out, open(outf, "w"))
        print(f"{k:28s} old {c['v']:7s} {json.dumps({a: (round(b, 2) if isinstance(b, float) else b) for a, b in r.items() if a != 'old'})}  {time.time()-t1:5.1f}s", flush=True)
    print("done", flush=True)
