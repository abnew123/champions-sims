"""The bot's brain: one long-lived process; JSON lines in (from bot/client.js), JSON lines out.
  {"type": "pack", "sets": [...]}                       -> {"packed": "<Showdown packed team>"}
  {"type": "preview", "log": [...], "request": {...}, "side": "p1"|"p2", "team": {...}} -> {"order": [1,2,3,4]}  (4 of 6, leads first)
  {"type": "turn", "log": [...], "request": {...}, "side": ...}                          -> {"choice": "move 1 2, switch 3"}
Team preview: Team search's bring heuristic against the opponent's open team sheet (|showteam| in the log). Turns: the position is built
from the room log plus our own |request| (bot/position.py; the Eval bar thread's live builder for the opponent's side), evaluated by
champ evalpos with the kit's setup, and a joint action is sampled from the planner's mix. Never prints anything else to stdout."""
import json, os, sys, subprocess, random, re, traceback, math
CAL = 0.7538   # the rescale of the planner's value to real outcomes (the eval bar's, fitted for egvalue9_sym2)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PS = os.path.join(ROOT, 'pssim')
sys.path.insert(0, PS); sys.path.insert(0, os.path.join(ROOT, 'bot'))
def out(o): sys.stdout.write(json.dumps(o) + '\n'); sys.stdout.flush()
def err(e): sys.stderr.write(e + '\n'); sys.stderr.flush()
def pack(sets):
    js = "const {Teams}=require('pokemon-showdown'); const s=JSON.parse(require('fs').readFileSync(0)); console.log(Teams.pack(s.map(x=>({name:x.species,species:x.species,item:x.item,ability:x.ability,moves:x.moves,nature:x.nature,level:50,evs:{hp:x.evs[0],atk:x.evs[1],def:x.evs[2],spa:x.evs[3],spd:x.evs[4],spe:x.evs[5]}}))))"
    r = subprocess.run(['node', '-e', js], input=json.dumps(sets), capture_output=True, text=True, cwd=PS)
    return r.stdout.strip()
def showteam(log, side):
    """the opponent's open sheet from the room log: |showteam|p2|<packed>  -> list of sets"""
    for l in log:
        p = l.split('|', 3)   # the packed team itself uses '|' as its field separator
        if len(p) > 3 and p[1] == 'showteam' and p[2] == side: return unpack(p[3])
    return None
def unpack(packed):
    js = "const {Teams}=require('pokemon-showdown'); console.log(JSON.stringify(Teams.unpack(require('fs').readFileSync(0,'utf8').trim())))"
    r = subprocess.run(['node', '-e', js], input=packed, capture_output=True, text=True, cwd=PS)
    try: team = json.loads(r.stdout)
    except Exception: return None
    return [{'species': t['species'] or t['name'], 'item': t.get('item', ''), 'ability': t.get('ability', ''), 'moves': t.get('moves', []), 'nature': t.get('nature', 'Serious'),
             'evs': [t.get('evs', {}).get(k, 0) for k in ('hp', 'atk', 'def', 'spa', 'spd', 'spe')]} for t in team]
def preview(msg):
    team = msg['team']['sets']; opp_side = 'p2' if msg['side'] == 'p1' else 'p1'
    theirs = showteam(msg['log'], opp_side)
    import play_server as P
    rnd = random.Random()
    four = P.planner_bring(team, theirs, rnd) if theirs else None
    if not four:   # no sheet seen: the first four
        four = team[:4]
    order = [team.index(x) + 1 for x in four]
    return {'order': order, 'note': 'bring ' + '/'.join(x['species'] for x in four) + ('' if theirs else ' (no sheet seen)')}
def turn(msg):
    import position as POS
    req = msg['request']
    if req.get('forceSwitch'): return {'choice': POS.replacement(req, msg['log'], msg['side']), 'note': 'replacement'}
    specs, info = POS.build(msg['log'], req, msg['side'], team=(msg.get('team') or {}).get('sets'))
    choice, note, value = POS.decide(specs, req, msg['side'])
    # a lost game is forfeited rather than played out (the user: Protect-stalling a lost position is what would annoy people most):
    # the planner's value rescaled to a real win chance as the eval bar does (log-odds x 0.7538), under limits.json's forfeit_below
    real = 1 / (1 + math.exp(-CAL * math.log(max(1e-6, value) / max(1e-6, 1 - value))))
    below = json.load(open(os.path.join(ROOT, 'bot', 'limits.json'))).get('forfeit_below', 0.0)
    if real < below: return {'forfeit': True, 'note': f'forfeit: win chance {100 * real:.1f}% (value {100 * value:.1f}%)'}
    return {'choice': choice, 'note': note + (f" hyp {info.get('hyp', [])[:1]}" if info.get('need') else '')}
def main():
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try:
            msg = json.loads(line)
            if msg['type'] == 'pack': out({'packed': pack(msg['sets'])})
            elif msg['type'] == 'preview': out(preview(msg))
            elif msg['type'] == 'turn': out(turn(msg))
            else: out({'error': 'unknown type'})
        except Exception as e:
            err(traceback.format_exc()); out({'error': repr(e)})
if __name__ == '__main__': main()
