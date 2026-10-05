"""Logic test for the sequential rule and the sharpening pass, with a fake evaluator (no battles; seconds of CPU).
Fake teams: win probability 0.55 + a small per-set effect, +0.04 for Garchomp#1; games share random numbers across teams for the
same (seed, job, game), like the paired battle seeds. Runs one 'thorough' round on two starts in a sandbox, then sharpen_pass().
  python3 test_sharpen.py
"""
import os, sys, json, hashlib, random, tempfile
SB = tempfile.mkdtemp(prefix='sharpen_test_')
os.environ.update(TS_STATE=os.path.join(SB, 'state.json'), TS_LOG=os.path.join(SB, 'log.jsonl'), TS_PROGRESS=os.path.join(SB, 'progress.json'),
                  TS_STARTS='trick_room_six,Baltimore-01', TS_SEQ_MAX='6')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import climb as C
import evaluate as E
P = E.P
calls = []

def h01(*a): return int(hashlib.md5('|'.join(map(str, a)).encode()).hexdigest()[:8], 16) / 0xffffffff
def strength(team): return 0.55 + sum(0.04 if g == 'Garchomp#1' else 0.02 * (h01('set', g) - 0.5) for g in team)
def fake_result(team, per_job, seed):
    per = {}
    for j in range(60):
        w = sum(1 for g in range(per_job) if h01(seed, j, g) * 0.7 + h01(seed, j, g, C.key_s(team)) * 0.3 < strength(team))
        per[j] = (float(w), per_job)
    by = {a: sum(per[i * 6 + k][0] / per_job * P.pair_shares(a)[k] for k in range(6)) for i, a in enumerate(E.ARCHS)}
    score = sum(P.ARCH_SHARE[a] * by[a] for a in by) / sum(P.ARCH_SHARE.values())
    return dict(score=score, per_job=per, by_arch=by, games=60 * per_job)
def fake_search_many(teams, seed):
    calls.append(('search', len(teams), seed))
    return [dict(fake_result(t, 1, seed), chosen={a: (t[:2], t[2:4]) for a in E.ARCHS}, rank={}) for t in teams]
def fake_evaluate_fixed(teams, brings, per_job, seed):
    calls.append(('fixed', len(teams), per_job, seed))
    return [fake_result(t, per_job, seed) for t in teams]
E.search_many, E.evaluate_fixed = fake_search_many, fake_evaluate_fixed

C.run_round('thorough')
print('\n--- sharpen pass ---')
C.sharpen_pass()
print('\nevaluator calls:', [c for c in calls if c[0] == 'fixed'])
st = json.load(open(os.environ['TS_STATE']))
for n, t in st['teams'].items(): print(n, 'done' if t['done'] else 'climbing', [p['out'] + '->' + p['into'] for p in t['path']])
print('sandbox:', SB)
