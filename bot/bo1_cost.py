"""What does playing without open sheets cost the bot? (2026-10-12, for the Bo1 bot.) Every decision in the bot's saved Bo3 games is
built twice: as it was (both open sheets) and with the opponent's sheet replaced by bot/bo1.py's guess from the commonest real sheets and
what the game had shown by then. Both are solved by the engine; the mix planned on the guess is valued in the true position against the
mix planned on the truth (belief_test.score), so the gain reads as the cost of not seeing the sheet.
  .venv/bin/python3 bot/bo1_cost.py build <prefix>      then   .venv/bin/python3 bot/belief_test.py score <prefix>_guess <prefix>_true"""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'evalbar')); sys.path.insert(0, os.path.join(ROOT, 'bot'))
os.environ.setdefault('CHAMP_MAIN', ROOT)
import belief_test as BT, bo1
def build(prefix):
    import botpos as BP, live as LV, position as POS
    out = {'guess': [], 'true': []}; n = 0
    for g, team, log, req, turn in BT.decisions():
        opp = 'p2' if g['side'] == 'p1' else 'p1'
        L = log.split('\n')
        hidden = bo1.inject([l for l in L if not l.startswith(f'|showteam|{opp}|')], opp)
        name = f"{g['room'][-14:]} t{turn}"
        built = {}
        for tag, text in (('true', log), ('guess', '\n'.join(hidden))):
            try: specs, info = BP.bot_position(text, req, g['side'], topk=1, team=POS.export(team['sets']), tag='b1')
            except Exception: specs = []
            if not specs: break
            sp = json.loads(json.dumps(specs[0][1])); sp['name'] = name; built[tag] = sp
        if len(built) == 2:
            for tag in built: out[tag].append((1.0, built[tag]))
            n += 1
    for tag, S in out.items():
        f = f'{prefix}_{tag}.pos.jsonl'
        if os.path.exists(f): os.remove(f)
        LV.positions(S, f)
    print(f'{n} decisions built both ways -> {prefix}_guess / _true')
if __name__ == '__main__':
    build(os.path.abspath(sys.argv[2]))
