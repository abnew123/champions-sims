"""The bot's brain: one long-lived process; JSON lines in (from bot/client.js), JSON lines out.
  {"type": "pack", "sets": [...]}                       -> {"packed": "<Showdown packed team>"}
  {"type": "preview", "log": [...], "request": {...}, "side": "p1"|"p2", "team": {...}} -> {"order": [1,2,3,4]}  (4 of 6, leads first)
  {"type": "turn", "log": [...], "request": {...}, "side": ...}                          -> {"choice": "move 1 2, switch 3"}
Team preview: Team search's bring heuristic against the opponent's open team sheet (|showteam| in the log). Turns: the position is built
from the room log plus our own |request| (bot/position.py; the Eval bar thread's live builder for the opponent's side), evaluated by
champ evalpos with the kit's setup, and a joint action is sampled from the planner's mix. Never prints anything else to stdout."""
import json, os, sys, subprocess, random, re, traceback, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PS = os.path.join(ROOT, 'pssim')
sys.path.insert(0, PS); sys.path.insert(0, os.path.join(ROOT, 'bot'))
sys.path.insert(0, os.path.join(ROOT, 'evalbar'))
import replay; replay.BATON_PASS = True; replay.MEGA_ABIL = True   # the log reading: Baton Pass / Shed Tail pass boosts and volatiles; Mega Evolution clears a gained ability (the user, 2026-10-12 evening)
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
def sheet_pick(sheet, team, theirs):
    """the team sheet's bring for this opponent (sheets/<team>/picks.json: lead + back per opposing group, the sheet kit's both-sides
    pick): the opponent's six classified as the pool does (cluster_opps rules, pssim/opp_pool.json), then 'Other <archetype>', then the
    group whose likely sixes share the most species with it; None when the sheet has nothing usable"""
    from cluster_opps import tag, norm
    from pro_replays import arch
    picks = json.load(open(os.path.join(ROOT, sheet)))['picks']
    rules = json.load(open(os.path.join(PS, 'opp_pool.json')))['rules']
    six = [x['species'] for x in theirs]; g = tag(six, rules); how = 'group'
    if g not in picks: g = 'Other ' + arch([norm(x) for x in six]); how = 'archetype'
    if g not in picks:
        S = set(norm(x) for x in six)
        def overlap(k): return max((len(S & set(norm(y) for y in a['six'].split(', '))) for a in picks[k].get('answers', [])), default=0)
        g = max(picks, key=overlap); how = 'nearest group'
    pk = picks[g]; names = [x['species'] for x in team]
    mix = pk.get('mix') or []   # the sheet's mixed bring when it has one ([{lead, back, p}]), sampled; else its single pick
    if mix:
        c = random.choices(mix, weights=[m['p'] for m in mix])[0]; lead, back = c['lead'], c['back']
        tag_ = f" (mix {100 * c['p']:.0f}% of {len(mix)})" if len(mix) > 1 else ''
    else: lead, back, tag_ = pk['lead'], pk['back'], ''
    try: four = [team[names.index(sp)] for sp in lead + back]
    except ValueError: return None, None
    return four, f'sheet pick for {g} ({how}){tag_}'
def preview(msg):
    team = msg['team']['sets']; opp_side = 'p2' if msg['side'] == 'p1' else 'p1'
    theirs = showteam(msg['log'], opp_side)
    four = None
    if theirs and msg['team'].get('sheet'):
        four, why = sheet_pick(msg['team']['sheet'], team, theirs)
        if four: return {'order': [team.index(x) + 1 for x in four], 'note': 'bring ' + '/'.join(x['species'] for x in four) + f' ({why})'}
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
    fmt = (msg.get('room') or '').split('-')[1] if (msg.get('room') or '').count('-') >= 2 else None   # battle-<format>-<id>
    # the Eval bar's fitted default spreads for the opponent (spreads.FITTED), per format from limits.json fitted_spreads, read every
    # decision. On the bot's own 376 games, the bot's side at its real sets (2026-10-13): Bo3 hits dealt observed / predicted 0.985 -> 0.995,
    # in the predicted range 72.0% -> 77.3% (z +3.9), hits taken 0.975 -> 0.991 (z +0.5): on. Bo1 both a little worse (z -0.8, -1.2): off
    import spreads; spreads.FITTED = bool((json.load(open(os.path.join(ROOT, 'bot', 'limits.json'))).get('fitted_spreads') or {}).get(fmt or '', False))
    if req.get('forceSwitch'): return {'choice': POS.replacement(req, msg['log'], msg['side'], team=(msg.get('team') or {}).get('sets')), 'note': 'replacement'}
    specs, info = POS.build(msg['log'], req, msg['side'], topk=POS.back_row_k(fmt), team=(msg.get('team') or {}).get('sets'))
    cap = json.load(open(os.path.join(ROOT, 'bot', 'limits.json'))).get('protect_chain_cap')
    choice, note, value = POS.decide(specs, req, msg['side'], log=msg['log'], cap=cap, fmt=fmt)
    # a lost game is forfeited rather than played out (the user: Protect-stalling a lost position is what would annoy people most):
    # the planner's value rescaled to a real win chance as the eval bar does (log-odds x CAL), under limits.json's forfeit_below. CAL is
    # the Eval bar's, fitted for the engine and net the bot runs (live.CAL: 0.676 for v31 + the h64 net); until the outside review
    # (2026-10-14) it was v25's 0.7538 with egvalue9_sym2, which forfeited a little early (raw 0.4%: 1.5% instead of 2.3%)
    real = 1 / (1 + math.exp(-POS.LV.CAL * math.log(max(1e-6, value) / max(1e-6, 1 - value))))
    below = json.load(open(os.path.join(ROOT, 'bot', 'limits.json'))).get('forfeit_below', 0.0)
    if real < below: return {'forfeit': True, 'note': f'forfeit: win chance {100 * real:.1f}% (value {100 * value:.1f}%)'}
    return {'choice': choice, 'note': note + (f" hyp {info.get('hyp', [])[:1]}" if info.get('need') else '')}
def main():
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try:
            msg = json.loads(line)
            if msg['type'] in ('preview', 'turn') and msg.get('log') and msg.get('side'):
                # no open team sheets (Bo1): the opponent's sets guessed from the commonest real sheets and what the game has shown,
                # written into the log as a sheet (bot/bo1.py); our own sheet from our team. Logs that have sheets are left as they are.
                import bo1
                opp = 'p2' if msg['side'] == 'p1' else 'p1'
                msg['log'] = bo1.inject(list(msg['log']), opp, (msg.get('team') or {}).get('sets'), msg['side'])
            if msg['type'] == 'pack': out({'packed': pack(msg['sets'])})
            elif msg['type'] == 'preview': out(preview(msg))
            elif msg['type'] == 'turn': out(turn(msg))
            else: out({'error': 'unknown type'})
        except Exception as e:
            err(traceback.format_exc()); out({'error': repr(e)})
if __name__ == '__main__': main()
