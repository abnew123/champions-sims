"""Mixed brings (the user's request, 2026-10-10, for the ladder bot in Bo3: a fixed four is readable from game 1).
Per card, a probability over our screened fours (those whose own strongest answers were searched) that maximises the share-weighted
win share when each of the card's opposing sixes best-responds to the mix with the answers we know: a small LP on the both-sides-pick
matrix (optimal.matrix_cells). Needs scipy, so kit.py runs it with the project's venv python.

  write    -> picks.json: per card "mix": [{lead, back, p}], "mix_v" (the mix's value), "mix_pure_v" (the best single four on the same
              answers); the pick itself ("lead", "back", "v") is unchanged, so the page stays one pick per card
  check    -> rounds of: find each six's two strongest fours against the mix from the components' screens (every component was screened
              against every opposing four, so no new screen is needed), play every component against the new ones (32 games, queue
              work/optimal/matrix_mix<n>), re-solve; until no new answer or --rounds; then write
  usage: <venv python> sheetkit/mix.py <team> write | check [--threads N] [--rounds 3]"""
import sys, os, re, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import optimal as O, picks as P
import numpy as np
from scipy.optimize import linprog

def components(sheet, a, M, done):
    """our screened fours for card a that have cells (they meet the answers)"""
    return [k for (arch, k) in M if arch == a and O.four_key(k[0].split('+'), k[1].split('+')) in done[a]]

def solve(sheet, a, S6, M, done):
    """-> (mix [(p, ours)], value, best single four's value, {six: answers used}) or None"""
    fours = components(sheet, a, M, done); ts = S6[a]
    if not fours: return None
    W = sum(t['weight'] for t in ts)
    A = {si: set.intersection(*[{x[1] for x in M[(a, f)] if x[0] == si} for f in fours]) for si in range(len(ts))}
    if any(not A[si] for si in A): return None
    n = len(fours); nv = n + len(ts); c = np.zeros(nv); c[n:] = -np.array([t['weight'] / W for t in ts])
    Aub, bub = [], []
    for si in range(len(ts)):
        for ans in A[si]:
            row = np.zeros(nv); row[n + si] = 1
            for j, f in enumerate(fours): row[j] = -M[(a, f)][(si, ans)][0]
            Aub.append(row); bub.append(0.0)
    r = linprog(c, A_ub=Aub, b_ub=bub, A_eq=[[1.0] * n + [0.0] * len(ts)], b_eq=[1.0], bounds=[(0, 1)] * n + [(None, None)] * len(ts))
    if not r.success: return None
    x = [max(0.0, v) for v in r.x[:n]]; s = sum(x); x = [v / s for v in x]
    pure = max(sum(t['weight'] / W * min(M[(a, f)][(si, ans)][0] for ans in A[si]) for si, t in enumerate(ts)) for f in fours)
    return sorted(zip(x, fours), reverse=True), -r.fun, pure, A

def write(sheet, out=print):
    S6 = O.sixes(sheet); M = O.matrix_cells(sheet); done = O.screened(sheet); d = rj(sheet.p('picks.json')); n = 0; tot = vm = vp = 0.0
    share = {k: c['share'] for k, c in CARDS.items()} if CARDS else SHARE
    for a, pk in d['picks'].items():
        r = solve(sheet, a, S6, M, done)
        if r is None:
            pk['mix'] = [{'lead': pk['lead'], 'back': pk['back'], 'p': 1.0}]; pk.pop('mix_v', None); pk.pop('mix_pure_v', None); continue
        mix, v, pure, _ = r
        pk['mix'] = [{'lead': sheet.lead(f[0].split('+')), 'back': sheet.back(f[1].split('+')), 'p': round(p, 3)} for p, f in mix if p >= 0.01]
        t = sum(m['p'] for m in pk['mix']); [m.update(p=round(m['p'] / t, 3)) for m in pk['mix']]
        pk['mix_v'] = round(v, 3); pk['mix_pure_v'] = round(pure, 3); n += len(pk['mix']) > 1
        tot += share.get(a, 0); vm += share.get(a, 0) * v; vp += share.get(a, 0) * pure
        out(f"{a[:46]:46s} pure {100*pure:5.1f}  mix {100*v:5.1f}  " + '; '.join(f"{100*m['p']:.0f}% {'+'.join(m['lead'])} / {'+'.join(m['back'])}" for m in pk['mix']))
    d['mix_note'] = ("per card a probability over screened fours (sheetkit/mix.py): the LP optimum when each opposing six best-responds "
                     "with the answers known; sample one per game")
    wj(d, sheet.p('picks.json'), indent=1)
    if tot: out(f"picks.json: mixes written, {n} cards mix more than one four; ladder-weighted pure {100*vp/tot:.1f}% -> mixed {100*vm/tot:.1f}%")

def check(sheet, threads, rounds, out=print):
    """answers to the mix from the components' screens, played against every component; repeat"""
    S6 = O.sixes(sheet); d = O._w(sheet); log = RunLog(sheet, 'mix')
    for rnd in range(rounds):
        M = O.matrix_cells(sheet); done = O.screened(sheet); scr = O.screen_results(sheet); jobs = []
        for a in O.ARCHS:
            r = solve(sheet, a, S6, M, done)
            if r is None: continue
            mix, _, _, _ = r
            comps = components(sheet, a, M, done)
            for si in range(len(S6[a])):                          # 1. every component against every answer any of them has met
                sets_of = {'+'.join(names): sets for f in comps for _, names, sets in scr.get((a, si, O.four_key(f[0].split('+'), f[1].split('+'))), [])}
                union = {k for f in comps for (s, k) in M[(a, f)] if s == si}
                for k in union:
                    for f in comps:
                        if (si, k) not in M[(a, f)] and k in sets_of: jobs.append(O.job(sheet, a, si, f[0].split('+'), f[1].split('+'), sets_of[k]))
            for si in range(len(S6[a])):                          # 2. the mix's own strongest answers, from the components' screens
                val = {}                                          # opposing four (names) -> (mix value from screens, their sets)
                for p, f in mix:
                    for v, names, sets in scr.get((a, si, O.four_key(f[0].split('+'), f[1].split('+'))), []):
                        k = '+'.join(names); val.setdefault(k, [0.0, sets, 0.0]); val[k][0] += p * v; val[k][2] += p
                full = [(v, k, sets) for k, (v, sets, w) in val.items() if w > 0.999]           # met by every component
                for v, k, sets in sorted(full, key=lambda x: x[0])[:2]:
                    for p, f in mix:
                        if (si, k) not in M.get((a, f), {}): jobs.append(O.job(sheet, a, si, f[0].split('+'), f[1].split('+'), sets))
        seen = set(); jobs = [j for j in jobs if not (P.job_key(j) in seen or seen.add(P.job_key(j)))]      # a cell asked for twice
        if not jobs: out(f"round {rnd + 1}: the mixes' strongest answers are all played; done"); break
        n = 1 + max([int(m.group(1)) for p in O.queues(sheet, 'matrix') for m in [re.search(r'_mix(\d+)\.json$', p)] if m] + [0])
        q = f'{d}/matrix_mix{n}.json'; wj(jobs, q); out(f"round {rnd + 1}: {len(jobs)} new cells -> {os.path.basename(q)}")
        P.battle_run(sheet, 'optimal', q, q[:-5], O.MATRIX_GAMES, O.MATRIX_G0, threads, None, log)
    write(sheet, out)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('team'); ap.add_argument('cmd', choices=['write', 'check'])
    ap.add_argument('--threads', type=int); ap.add_argument('--rounds', type=int, default=3); ap.add_argument('--force', action='store_true')
    a = ap.parse_args(); sheet = Sheet(a.team)
    import procs; procs.own(sheet)
    if a.cmd == 'write': write(sheet)
    else: check(sheet, threads_arg(a.threads, a.force), a.rounds)
