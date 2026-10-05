"""Training battles for the outcome-fitted bring heuristic (user's choice, 2026-10-03: fit bring weights to battle results).

12 start teams (each archetype's best placed, plus a second Tailwind and Perish team; the Trick Room six is held out for the
check against the sheet). For every team x archetype, 8 distinct (four, leads) choices: the human-fitted model's top 3, the
features-only model's top 2, then random ones; each plays that archetype's 6 modelled lead pairs PER_JOB times.
Battles: evaluate.run_jobs (champ-battle-v2, egvalue5, anticipation). Resumes: finished jobs are skipped.
  TS_THREADS=3 python3 train_battles.py        -> train_labels.json (one row per team x archetype x choice)
"""
import json, os, sys, random, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import evaluate as E
P = E.P; Fx = P.Fx
TEAMS = ['Baltimore-03', 'Brisbane-05', 'Brisbane-02', 'Baltimore-05', 'Frankfurt-01', 'Frankfurt-02', 'Baltimore-04', 'Brisbane-04',
         'Baltimore-01', 'Brisbane-01', 'Baltimore-06', 'Brisbane-10']
N_CHOICES, PER_JOB = 8, int(os.environ.get('PER_JOB', 2))
HUMAN = os.path.join(HERE, 'bring_model.json'); NOPRIOR = os.path.join(HERE, 'bring_model_noprior.json')

def ranked(team, arch, path):
    """every (lead idx, back idx) of the 90, best first, by a fitted choice model"""
    import numpy as np
    wB, wL, pb, pl = P.model(path)
    m = Fx.Matchup(list(team), list(P.opp_six(arch))); sp = [Fx.G[g]['species'] for g in team]
    out = []
    for S in Fx.BRINGS:
        ub = np.dot(wB, m.bring_feats(S) + [sum(pb.get(sp[i], 0.0) for i in S)])
        for Lp in Fx.leads(S):
            ul = np.dot(wL, m.lead_feats(Lp, S) + [sum(pl.get(sp[i], 0.0) for i in Lp)])
            out.append((ub + ul, Lp, tuple(i for i in S if i not in Lp)))
    return [(Lp, B) for _, Lp, B in sorted(out, key=lambda t: -t[0])]

def choices(team, arch, seed):
    rng = random.Random(seed); out = []
    for c in ranked(team, arch, HUMAN)[:3] + ranked(team, arch, NOPRIOR)[:2]:
        if c not in out: out.append(c)
    allc = [(Lp, tuple(i for i in S if i not in Lp)) for S in Fx.BRINGS for Lp in Fx.leads(S)]
    while len(out) < N_CHOICES:
        c = rng.choice(allc)
        if c not in out: out.append(c)
    return out

if __name__ == '__main__':
    idx = json.load(open(os.path.join(HERE, '..', 'teams', 'start', 'index.json')))
    thr = int(os.environ.get('TS_THREADS', 3)); labels = []
    for n, name in enumerate(TEAMS):
        team = idx[name]['gids']; sp = [Fx.G[g]['species'] for g in team]
        jobs, meta = [], []
        for arch in P.ARCH_SHARE:
            for ci, (Lp, B) in enumerate(choices(team, arch, f'{name}|{arch}')):
                for k in range(P.K):
                    jobs.append(dict(arch=arch, k=k, lead=[sp[i] for i in Lp], back=[sp[i] for i in B]))
                    meta.append((arch, ci, Lp, B, k))
        t0 = time.time()
        res = E.run_jobs(team, jobs, PER_JOB, 0, thr, 'train')
        acc = {}
        for (arch, ci, Lp, B, k), r in zip(meta, res):
            vs = [row['v'] for row in r['rows'] if not row.get('unsupported')]
            a = acc.setdefault((arch, ci), dict(team=name, gids=team, arch=arch, choice=ci, lead=list(Lp), back=list(B), num=0.0, den=0.0, games=0))
            if vs:
                w = P.pair_shares(arch)[k]; a['num'] += w * sum(vs) / len(vs); a['den'] += w; a['games'] += len(vs)
        for a in acc.values():
            a['win'] = a['num'] / a['den'] if a['den'] else None; labels.append(a)
        json.dump(labels, open(os.path.join(HERE, 'train_labels.json'), 'w'))
        print(time.strftime('%I:%M %p'), f'{n + 1}/{len(TEAMS)} {name}: {len(jobs) * PER_JOB} games in {(time.time() - t0) / 60:.1f} min', flush=True)
    print('done', flush=True)
