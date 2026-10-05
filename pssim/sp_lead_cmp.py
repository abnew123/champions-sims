"""Spread study, turn-one part: lead values with one Pokemon's spread changed (2026-10-02).
For each variant, the leads containing MON come from that variant's refinement run (results/<dir>, refined on the same rows for every
variant) and all other leads from the v11 refinement (results/v11*); both get that variant's Speed file (it moves the Trick Room credit
of every lead that brings MON). Then tr_final.py solves each, and this prints per archetype the best lead and every MON lead's score.
usage: python3 sp_lead_cmp.py <MON> <name>:<refined dir>:<speeds json>[:<EXCLUDE_MOVES>] [...]      (first variant = the reference)
  EXCLUDE_MOVES (optional, per variant): drop plan rows like ': switch -> Indeedee-F' that the variant's team can't play"""
import json, glob, os, sys, subprocess
MON = sys.argv[1]; V = [a.split(':') for a in sys.argv[2:]]
SH = {'Tailwind goodstuffs': 26.2, 'Sun': 12.0, 'Indeedee TR / Psychic Terrain': 11.9, 'Rain': 10.5, 'Balance, no speed control': 9.3,
      'Sand': 9.0, 'Snow': 7.8, 'Trick Room without Indeedee': 6.7, 'Rain + sun': 3.3, 'Perish trap': 3.3}
has = lambda f: MON in json.load(open(f))['myLead']
out = {}
for name, rdir, spd, *ex in V:
    for suf in ('', '_colburberry', '_psychicseed'):
        dst = f'results/m_{name}{suf}'; subprocess.run(['rm', '-rf', dst]); os.makedirs(dst)
        for f in glob.glob(f'results/v11{suf}/*.json'):
            if not has(f): os.symlink(os.path.realpath(f), f'{dst}/a_{os.path.basename(f)}')
        for f in glob.glob(f'{rdir}{suf}/*.json'):
            # a lead refined only on rows another variant picked can have no rows this team has: not a contender for this team
            if not json.load(open(f))['F']: continue
            os.symlink(os.path.abspath(f), f'{dst}/b_{os.path.basename(f)}')
    env = dict(os.environ, TR_SPEEDS=spd, READER_W='0.75', TRMULT_FILE='trmult_final.json', EXCLUDE_MOVES=ex[0] if ex else '')
    subprocess.run(['../.venv/bin/python3', 'tr_final.py', f'results/m_{name}', f'tr_final_m_{name}.json'], env=env, check=True, stdout=subprocess.DEVNULL)
    D = json.load(open(f'tr_final_m_{name}.json'))
    out[name] = {a: {v[0]: v[3] for v in D['leads'][a]['all']['vals']} for a in SH}
ref = V[0][0]
print(f'lead score (0.25 ladder + 0.75 reader), x100; {MON} leads per variant; best = best lead overall in that archetype')
tot = {v[0]: 0.0 for v in V}
for a in SH:
    print(f'\n{a}  (share {SH[a]})')
    leads = sorted({l for n in out for l in out[n][a] if MON in l.split('+')}, key=lambda l: -out[ref][a].get(l, 0))
    for n, *_ in V:
        best = max(out[n][a].items(), key=lambda x: x[1]); tot[n] += SH[a] * best[1]
        print(f'  {n:8s} best {best[0]:24s} {100*best[1]:5.1f} | ' + ', '.join(f'{l} {100*out[n][a][l]:5.1f}' for l in leads[:4] if l in out[n][a]))
print('\narchetype-weighted best-lead score: ' + ', '.join(f'{n} {tot[n]/sum(SH.values())*100:.2f}' for n in tot))
