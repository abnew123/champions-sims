# Sixth-slot candidate vs Hatterene, by archetype, on refined (12-sample, item-mixed) lead values.
# Current team: best of the refined leads in tr_final_v7(.x2). Candidate team: best of (current leads without Hatterene, refined candidate leads).
import json, sys, os
tags = sys.argv[1:]; RW = os.environ.get('RW', '')
BASE = os.environ.get('BASE_FINAL', 'tr_final_v7'); DROP = os.environ.get('DROP', 'Hatterene')   # team compared against, and the member being replaced
W = {'Tailwind goodstuffs': 26.2, 'Indeedee TR / Psychic Terrain': 11.9, 'Sun': 12.0, 'Rain': 10.5, 'Balance, no speed control': 9.3, 'Sand': 9.0,
     'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
NAME = {'incin': 'Incineroar', 'arma': 'Armarouge', 'sylv': 'Sylveon'}
for suf, lab in (('', 'Trick Room at fitted weight'), ('_x2', 'Trick Room counted double')):
    if not os.path.exists(f'{BASE}{RW}{suf}.json'): continue
    A = json.load(open(f'{BASE}{RW}{suf}.json'))
    C = {t: json.load(open(f'tr_final_c_{t}{RW}{suf}.json')) for t in tags}
    print(f'\n== {lab} {RW}')
    tot = {t: 0 for t in tags}; totH = 0
    for arch in sorted(W, key=lambda a: -W[a]):
        v = A['leads'][arch]['all']['vals']; top = v[0]; noH = next(x for x in v if DROP not in x[0])
        totH += W[arch] * (noH[3] - top[3])
        line = f"{arch[:27]:27s} {W[arch]:4.1f}%  now {top[0]:21s} {100*top[3]:5.1f} | no {DROP} {100*(noH[3]-top[3]):+5.1f}"
        for t in tags:
            cv = C[t]['leads'].get(arch, {}).get('all', {}).get('vals', [])
            best = max([noH] + cv, key=lambda x: x[3]); d = best[3] - top[3]; tot[t] += W[arch] * d
            cb = cv[0] if cv else None
            line += f" | {NAME.get(t, t)}: {(cb[0] + ' ' + format(100*cb[3], '.1f')) if cb else 'none refined':26s} best {100*d:+5.1f}"
        print(line)
    print(f"archetype-weighted change in best-lead value: without {DROP} {100*totH/sum(W.values()):+.2f}" +
          ''.join(f" | {NAME.get(t, t)} {100*tot[t]/sum(W.values()):+.2f}" for t in tags))
