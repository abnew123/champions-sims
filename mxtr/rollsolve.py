"""Roll odds with both sides playing their best: sample per-turn roll sequences, solve each."""
import random, json, sys, spgame as S
S.FULL = True
EXTRA = {"Volcarona": (S.STATUS,), "Whimsicott": (S.STATUS,)}
PARA = False       # set True for threats that paralyse (keeps the old rows' random streams unchanged)
def p_solver(mine, foe, n=40, seed=7, T=6):
    rng = random.Random(seed); tot = 0.0
    for _ in range(n):
        rm = [rng.randint(85, 100) / 100 for _ in range(T + 2)]; rt = [rng.randint(85, 100) / 100 for _ in range(T + 2)]
        ties = [rng.random() < 0.5 for _ in range(T + 2)]
        paras = [rng.random() < 0.125 for _ in range(T + 2)] if PARA else None     # Champions: 1 in 8
        tot += min(S.Game(foe, sp, EXTRA.get(foe, ()), T=T, cutoff=0.0, mine=mine, trade=1.0, bullet=False, rm=rm, rt=rt, ties=ties, paras=paras).start("field")[0][0]
                   for sp in S.F[foe][3])
    return tot / n
if __name__ == "__main__":
    rows = json.load(open("matchup2.json")); SIX = ["Rillaboom","Incineroar","Sneasler","Gholdengo","Kingambit","Salamence"]; out = {}
    for f, u, cs in rows:
        for j, c in enumerate(cs):
            if c["v"] in ("roll", "wall"):
                p = p_solver(SIX[j], f); out[f"{f}|{SIX[j]}"] = p
                print(f"{f:14s} {SIX[j]:10s} {c['v']:5s} MC {c.get('roll')!s:4s}%  solver-sampled {100*p:5.1f}%", flush=True)
    json.dump(out, open("rollsolve.json", "w"))
