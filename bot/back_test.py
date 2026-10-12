"""What does a wrong guess at the opponent's unseen back row cost? (2026-10-12, the user.) The bot plans each turn against the single
most likely pair (or one) of the opponent's brought Pokemon not yet seen (botpos topk=1: back rates given the leads). For every decision
in the saved games where the opponent still had unseen Pokemon and the game later showed all four it brought, the position is built
twice: with the bot's guess and with the true back row. How often the guess is right, and, where it is wrong, what the bot's mix loses
read off the true position (belief_test.score: the mix planned on the guess against the mix planned on the truth, both valued in the
true position).
  .venv/bin/python3 bot/back_test.py <out prefix>"""
import os, sys, json, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'evalbar')); sys.path.insert(0, os.path.join(ROOT, 'bot'))
os.environ.setdefault('CHAMP_MAIN', ROOT)
import belief_test as BT
def main(prefix):
    import botpos as BP, live as LV, position as POS, replay as R
    guess, truth = [], []; tally = collections.Counter(); per_turn = collections.defaultdict(collections.Counter); meta = []
    full_cache = {}
    for g, team, log, req, turn in BT.decisions():
        op = 'p2' if g['side'] == 'p1' else 'p1'
        if g['room'] not in full_cache:
            full_cache[g['room']] = R.parse(open(os.path.join(ROOT, 'bot', 'out', g['room'] + '.log'), errors='ignore').read())['final']
        fin = full_cache[g['room']]
        brought = [m['sp'] for m in fin[op]['mons'] if m.get('seen', True)]
        try: specs, info = BP.bot_position(log, req, g['side'], topk=20, team=POS.export(team['sets']), tag='bk')
        except Exception: continue
        if not specs or not info.get('need'): continue
        H = info['hyp']; seen_now = {m['sp'] for m in R.parse(log)['steps'][-1]['state'][op]['mons']}
        if len(brought) < 4: tally['back row never fully shown'] += 1; continue
        true_back = sorted(sp for sp in brought if sp not in seen_now)
        if len(true_back) != info['need']: tally['inconsistent'] += 1; continue
        k = next((i for i, (w, c) in enumerate(H) if sorted(c) == true_back), None)
        if k is None: tally['true back row not among the candidates'] += 1; continue
        right = len(set(H[0][1]) & set(true_back))
        tally[f'{right} of {len(true_back)} right'] += 1; per_turn[turn][f'{right}/{len(true_back)}'] += 1
        if k == 0: continue
        name = f"{g['room'][-14:]} t{turn}"
        for lst, (w, sp) in ((guess, specs[0]), (truth, specs[k])):
            sp = json.loads(json.dumps(sp)); sp['name'] = name; lst.append((1.0, sp))
        meta.append({'name': name + ' p1', 'room': g['room'], 'turn': turn, 'guess': H[0][1], 'truth': true_back, 'p_guess': H[0][0], 'p_truth': H[k][0]})
    print('decisions with unseen opposing Pokemon:', dict(tally))
    print('by turn:', {t: dict(c) for t, c in sorted(per_turn.items())})
    for tag, S in (('guess', guess), ('truth', truth)):
        f = f'{prefix}_{tag}.pos.jsonl'
        if os.path.exists(f): os.remove(f)
        if S: LV.positions(S, f)
    json.dump(meta, open(prefix + '_back.meta.json', 'w'))
    print(f'{len(meta)} decisions with a wrong guess -> {prefix}_guess / _truth')
    if meta: BT.score(os.path.abspath(prefix) + '_guess', os.path.abspath(prefix) + '_truth')   # absolute: the engine runs from pssim/
if __name__ == '__main__':
    main(sys.argv[1])
