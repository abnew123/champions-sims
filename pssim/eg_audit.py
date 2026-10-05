"""Move audit for the 2v2 runs (EG_AUDIT output): for every move on every set that appeared, how often it was offered as an option,
its average share of the equilibrium mix when offered, and how often it was actually played. Flags moves never played / never offered.
usage: python3 eg_audit.py <resultsDir> <jobs.json>"""
import json, glob, sys, subprocess, collections
A = collections.defaultdict(lambda: [0, 0.0, 0])
for f in glob.glob(sys.argv[1] + '/*.json'):
    for k, (o, m, p) in json.load(open(f)).get('audit', {}).items():
        e = A[k]; e[0] += o; e[1] += m; e[2] += p
# every set that appeared, from the engine's own set builder
dump = subprocess.run(['node', '-e', f"""
const E = require('./endgame2.js'); const J = require('./{sys.argv[2]}'); const seen = {{}};
for (const j of J) {{ const [ms, ts] = E.sets(j.arch, j.mine, j.theirs);
  for (const s of ms) seen['p1|' + s.species] = s.moves; for (const s of ts) seen['p2|' + s.species + '|' + j.arch] = s.moves; }}
console.log(JSON.stringify(seen));"""], capture_output=True, text=True, env={'MYTEAM': 'myteam_c_incin.json', 'PATH': '/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin'})
S = json.loads(dump.stdout)
from collections import defaultdict
moves = defaultdict(set)                      # side|species -> set of move ids on any of its sets
for k, mv in S.items():
    side, sp = k.split('|')[:2]; moves[f'{side}|{sp}'] |= set(mv)
toid = lambda x: ''.join(c for c in x.lower() if c.isalnum())
REASON = {'healingwish': 'skipped by rule: no bench to bring in', 'memento': 'skipped by rule: no bench',
          'perishsong': 'useless with no bench (removes everything on the field, the user too)'}
print(f"{'side':5s} {'Pokemon':16s} {'move':18s} {'offered':>8s} {'mix share':>9s} {'played':>7s}")
never_played, never_offered = [], []
for key in sorted(moves):
    side, sp = key.split('|')
    got = {toid(k.split('|')[2]): v for k, v in A.items() if k.startswith(f'{side}|{sp}|')}
    for mv in sorted(moves[key]):
        o, m, p = got.get(toid(mv), [0, 0, 0])
        share = m / o if o else 0
        flag = '' if p else ('  <- never offered' if not o else '  <- never played')
        if not o: never_offered.append((side, sp, mv))
        elif not p: never_played.append((side, sp, mv, o, share))
        print(f"{'you' if side == 'p1' else 'them':5s} {sp:16s} {mv:18s} {o:8d} {100*share:8.1f}% {p:7d}{flag}")
print('\nNever offered:'); [print(f"  {('you' if s=='p1' else 'them')} {sp} {mv}: {REASON.get(mv, '?')}") for s, sp, mv in never_offered]
print('\nOffered but never played:'); [print(f"  {('you' if s=='p1' else 'them')} {sp} {mv}: offered {o} turns, avg share {100*sh:.1f}%") for s, sp, mv, o, sh in never_played]
