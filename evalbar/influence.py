"""How much is a good read worth? On the day-1 broadcast turns' full payoff matrices (uncertain.py's known runs: every cell at 32 samples,
values rescaled to real win chances), each side in turn is the reader:
  equilibrium   both sides play the exact equilibrium of the turn (linear programming); the reader's win chance is the game's value
  influenced    the opponent plays its equilibrium mix, except that a share eps of the time it picks one option the reader steered it to:
                one of its reasonable options (in its equilibrium mix, or within 2 points of its best answer to the reader's equilibrium),
                the one that suits the reader best
  optimal       the reader keeps its equilibrium mix against the influenced opponent (it barely gains: the opponent's reasonable options
                are all about equally good against it)
  exploit       the reader knows where the opponent leans and plays its best answer
Per turn, the reader's gain from exploiting is exploit minus optimal, in win-chance points; and what that exploiting move costs if the
opponent does not lean after all (the equilibrium value minus the move's value against the plain equilibrium mix). A turn's gain in win chance carries to the
end of the game, so the gain over a game is about the sum over its turns (a reader who gets that influence every turn).
  python3 evalbar/influence.py [eps ...=0.1 0.2 0.3 0.5]
Needs numpy and scipy: run it with the main folder's .venv python."""
import os, sys, json, glob, collections
import numpy as np
from scipy.optimize import linprog
import common as C, procs as P, study as ST
SRC = os.path.join(C.HERE, 'out', 'uncertain'); MARGIN = 0.02
def equilibrium(A):
    """the exact equilibrium of the zero-sum game A (row player maximizes): row mix, column mix, value"""
    m, n = A.shape
    r = linprog(np.r_[np.zeros(m), -1], A_ub=np.c_[-A.T, np.ones(n)], b_ub=np.zeros(n), A_eq=np.r_[np.ones(m), 0][None], b_eq=[1],
                bounds=[(0, None)] * m + [(None, None)], method='highs')
    c = linprog(np.r_[np.zeros(n), 1], A_ub=np.c_[A, -np.ones(m)], b_ub=np.zeros(m), A_eq=np.r_[np.ones(n), 0][None], b_eq=[1],
                bounds=[(0, None)] * n + [(None, None)], method='highs')
    return r.x[:m], c.x[:n], r.x[m]
def turn(A, eps):
    """one turn with the reader on the rows -> (equilibrium value, optimal vs influenced, exploit vs influenced)"""
    x, y, v = equilibrium(A); col = x @ A
    ok = [k for k in range(A.shape[1]) if y[k] > 0.01 or col[k] <= v + MARGIN]          # the opponent's reasonable options
    Ay = A @ y; best = (-1, None, None)
    for k in ok:
        w = (1 - eps) * Ay + eps * A[:, k]; i = int(w.argmax())
        if w[i] > best[0]: best = (w[i], k, i)
    val, k, i = best; optimal = (1 - eps) * v + eps * col[k]
    return v, optimal, val, v - Ay[i]                                   # the last: what the exploiting move costs if the opponent does not lean
def cases():
    for f in sorted(glob.glob(os.path.join(SRC, '*_base_eval.jsonl'))):
        game = os.path.basename(f).split('_base')[0]
        for e in map(json.loads, open(f)):
            if 'matrix' not in e: continue
            V = np.vectorize(ST.scale)(np.array(e['matrix']['v1']))
            yield game, e['turn'], 'p1', V
            yield game, e['turn'], 'p2', 1 - V.T
def main(epss):
    data = list(cases()); print(f"{len(data) // 2} turns from {len({g for g, *_ in data})} games, each side as the reader")
    for eps in epss:
        per = []; games = collections.defaultdict(float)
        for g, t, sd, A in data:
            v, opt, exp, risk = turn(A, eps); per.append((opt - v, exp - opt, risk)); games[(g, sd)] += exp - opt
        gain = np.array([b for _, b, _ in per]); free = np.array([a for a, _, _ in per]); risk = np.array([c for _, _, c in per]); G = np.array(list(games.values()))
        print(f"eps {eps:.0%}: per turn, exploiting gains {100 * gain.mean():.2f} points on average (median {100 * np.median(gain):.2f}; over 5 points "
              f"on {100 * (gain > 0.05).mean():.0f}% of turns; keeping the equilibrium mix gains {100 * free.mean():.2f}) | per game, summed over its "
              f"turns: {100 * G.mean():.1f} points on average (median {100 * np.median(G):.1f}, middle half {100 * np.percentile(G, 25):.1f} to {100 * np.percentile(G, 75):.1f})"
              f" | if the read is wrong (no lean), the exploiting move costs {100 * risk.mean():.2f} points per turn on average")
if __name__ == '__main__':
    P.own()
    main([float(a) for a in sys.argv[1:]] or [0.1, 0.2, 0.3, 0.5])
