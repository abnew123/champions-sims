"""End-to-end test of the brain on saved Bo3 games (the Eval bar's botpos.decisions): every decision of one side is answered as the
bot would, the command and the time taken are printed, nothing is compared to the player (the point is that nothing fails).
  .venv/bin/python3 bot/test_cached.py [games=1] [max turns per game=6]      (outputs under bot/out/, git-ignored: logs carry names)"""
import os, sys, json, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'evalbar')); sys.path.insert(0, os.path.join(ROOT, 'bot'))
import common as C, botpos as BP, brain as BR, position as POS
n = int(sys.argv[1]) if len(sys.argv) > 1 else 1; maxt = int(sys.argv[2]) if len(sys.argv) > 2 else 6
mine = json.load(open(os.path.join(ROOT, 'native', 'focus_sets_team.json')))
done = 0
for rid, log in C.games():
    if '|showteam|' not in log: continue
    print('game', done + 1)
    turns = 0
    for d in BP.decisions(log, 'p1'):
        t0 = time.time()
        try:
            if d['kind'] == 'preview':
                six = d['request']['side']['pokemon']
                sets = BR.showteam(d['log'].split('\n'), 'p1') or mine
                r = BR.preview({'type': 'preview', 'side': 'p1', 'log': d['log'].split('\n'), 'request': d['request'], 'team': {'name': 'own sheet', 'sets': sets}})
            elif d['kind'] == 'turn':
                if turns >= maxt: continue
                turns += 1
                specs, info = POS.build(d["log"], d["request"], "p1"); choice, note, value = POS.decide(specs, d["request"], "p1", log=d["log"], cap=4); r = {"choice": choice, "note": note}
            else:
                r = {'choice': POS.replacement(d['request'], d['log'], 'p1'), 'note': 'replacement; player chose ' + json.dumps(d['actual'])}
        except Exception as e:
            import traceback; r = {'error': repr(e)}; traceback.print_exc()
        print(f"  {d['kind']:8s} {time.time() - t0:5.1f}s  {json.dumps(r)[:160]}")
    done += 1
    if done >= n: break
