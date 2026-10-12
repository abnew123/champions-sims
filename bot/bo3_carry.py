"""What carries over from game 1 of a best-of-3? (2026-10-12, the user: the bot starts every game from nothing.)
  brings   on the cached Showdown Bo3 games (pssim/replays_protect, each log names its match and game number) and the bot's own matches:
           for each player from one game to the next, whether the four it brought and the two it led with repeat, and how well the back
           row is guessed at the next game's turn 1 by the population rates (the bot's guess: live.hyps top 1) and by the previous
           game's four (when its four contain the new leads). Players are matched across games by name; names are never printed or kept.
  spreads  on the bot's own matches (the inference needs the bot's exact Speed): the opponent's spreads read from the whole first game
           (spreads.refine) against the spread the bot starts the next game with (the most used Smogon spread for the sheet's nature);
           how many differ, and how many differ in Speed.
  .venv/bin/python3 bot/bo3_carry.py"""
import os, sys, json, re, glob, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'evalbar')); sys.path.insert(0, os.path.join(ROOT, 'bot'))
os.environ.setdefault('CHAMP_MAIN', ROOT)
import replay as R, live as LV
MATCH = re.compile(r'Game (\d)</strong> of <a href="/game-bestof3-[a-z0-9]+-(\d+)')
def info(log):
    """match id, game number, per side: name, the Pokemon it brought that appeared (in order), its leads"""
    m = MATCH.search(log)
    if not m: return None
    out = {'match': m.group(2), 'game': int(m.group(1)), 'sides': {}}
    for sd in ('p1', 'p2'):
        nm = next((l.split('|')[3] for l in log.split('\n') if l.startswith(f'|player|{sd}|') and len(l.split('|')) > 3 and l.split('|')[3]), None)
        seen = []
        for l in log.split('\n'):
            if l.startswith(f'|switch|{sd}') or l.startswith(f'|drag|{sd}'):
                sp = l.split('|')[3].split(',')[0]; sp = re.sub(r'-Mega(-[XYZ])?$', '', sp)
                if sp not in seen: seen.append(sp)
        out['sides'][sd] = {'name': nm, 'seen': seen, 'leads': seen[:2]}
    return out
def back_guess(log, sd):
    """the bot's population guess at sd's back row once the leads are out (turn 1)"""
    i = log.find('\n|turn|1\n')
    if i < 0: return None
    pre = log[:i + 9]
    g = R.parse(pre); st = g['steps'][-1]['state']
    six, sets, _ = LV.sets_for(g, pre, True)
    H, pool, need = LV.hyps(sd, st, six, sets, LV.Live.leads(None, pre), 1)
    return sorted(re.sub(r'-Mega(-[XYZ])?$', '', x) for x in H[0][1]) if H and need == 2 else None
def brings(logs, label):
    G = collections.defaultdict(dict)
    for lg in logs:
        x = info(lg)
        if x: G[x['match']][x['game']] = (x, lg)
    t = collections.Counter()
    for mid, games in G.items():
        for n in (2, 3):
            if n not in games or n - 1 not in games: continue
            (a, _), (b, lb) = games[n - 1], games[n]
            for sd in ('p1', 'p2'):
                nm = a['sides'][sd]['name']
                sb = next((s for s, v in b['sides'].items() if v['name'] == nm), None)
                if not nm or not sb: continue
                A, B = a['sides'][sd], b['sides'][sb]
                if len(A['seen']) == 4 and len(B['seen']) == 4:
                    t['pairs with both fours shown'] += 1; t['same four'] += sorted(A['seen']) == sorted(B['seen'])
                    t['three or more the same'] += len(set(A['seen']) & set(B['seen'])) >= 3
                if len(A['leads']) == 2 and len(B['leads']) == 2: t['pairs with leads'] += 1; t['same leads'] += sorted(A['leads']) == sorted(B['leads'])
                if len(B['seen']) == 4:
                    truth = sorted(B['seen'][2:])
                    try: pg = back_guess(lb, sb)
                    except Exception: pg = None
                    if pg is None: continue
                    t['back rows scored'] += 1; t['population guess right'] += pg == truth
                    carry = sorted(sp for sp in A['seen'] if sp not in B['leads']) if len(A['seen']) == 4 and set(B['leads']) <= set(A['seen']) else None
                    t['previous four contain the new leads'] += carry is not None
                    t['guess from the previous four right'] += (carry or pg) == truth
    print(f"{label}: {len(G)} matches")
    print(f"  same four in the next game: {t['same four']} of {t['pairs with both fours shown']} ({100 * t['same four'] / max(1, t['pairs with both fours shown']):.0f}%); three or more the same: {100 * t['three or more the same'] / max(1, t['pairs with both fours shown']):.0f}%")
    print(f"  same two leads: {t['same leads']} of {t['pairs with leads']} ({100 * t['same leads'] / max(1, t['pairs with leads']):.0f}%)")
    n = max(1, t['back rows scored'])
    print(f"  back row at the next game's turn 1 ({t['back rows scored']} scored): population guess right {100 * t['population guess right'] / n:.0f}%; "
          f"the previous game's four (when they contain the new leads, {100 * t['previous four contain the new leads'] / n:.0f}% of the time; else the population guess) right {100 * t['guess from the previous four right'] / n:.0f}%")
def spreads_carry():
    import botpos as BP, spreads as SP, position as POS
    teams = {t['name']: t for t in json.load(open(os.path.join(ROOT, 'bot', 'teams.json')))}
    pf = os.path.join(ROOT, 'bot', 'out', 'regional_pool.json'); pool = {t['name']: t for t in json.load(open(pf))}
    G = [json.loads(l) for l in open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl'))]
    t = collections.Counter(); spe = []
    for g in G:
        f = os.path.join(ROOT, 'bot', 'out', g['room'] + '.log'); team = teams.get(g.get('team')) or pool.get(g.get('team'))
        if not os.path.exists(f) or not team: continue
        log = open(f, errors='ignore').read(); x = info(log)
        if not x or x['game'] == 3: continue                          # game 1 and 2 teach the next game
        me = g['side']; op = 'p2' if me == 'p1' else 'p1'
        gp = R.parse(log); six, sets, _ = LV.sets_for(gp, log, True)
        default = {sp: list(st['evs']) for sp, st in sets[op].items() if st}
        known = {}
        for s in team['sets']:
            known[R.toid(s['species'].split('-')[0])] = (list(s['evs']), s['nature'])
        try: SP.refine(log, gp, sets, me, known)
        except Exception as e: t['failed'] += 1; continue
        seen = {m['sp'] for m in gp['final'][op]['mons'] if m.get('seen', True)}
        for sp in seen:
            st = sets[op].get(sp)
            if not st or sp not in default: continue
            t['opposing Pokemon seen'] += 1
            if list(st['evs']) != default[sp]: t['spread differs from the start-of-game guess'] += 1
            if st['evs'][5] != default[sp][5]:
                t['Speed points differ'] += 1
                n = st['nature']
                spe.append(abs(SP.raw_speed(sp, st['evs'], n) - SP.raw_speed(sp, default[sp], n)))
    n = max(1, t['opposing Pokemon seen'])
    print(f"bot's matches, games 1 and 2 read in full: {t['opposing Pokemon seen']} opposing Pokemon seen; spread off the start-of-game guess "
          f"{100 * t['spread differs from the start-of-game guess'] / n:.0f}%, Speed off {100 * t['Speed points differ'] / n:.0f}%"
          + (f" (by {sorted(spe)[len(spe) // 2]} Speed at the median)" if spe else '') + (f"; {t['failed']} games failed" if t['failed'] else ''))
if __name__ == '__main__':
    logs = [open(f, errors='ignore').read() for f in glob.glob(os.path.join(ROOT, 'pssim', 'replays_protect', '*.log'))]
    brings(logs, 'cached Showdown Bo3 games')
    G = [json.loads(l) for l in open(os.path.join(ROOT, 'bot', 'out', 'games.jsonl'))]
    bl = []
    for g in G:
        f = os.path.join(ROOT, 'bot', 'out', g['room'] + '.log')
        if os.path.exists(f): bl.append(open(f, errors='ignore').read())
    brings(bl, "the bot's matches (both sides; the bot's own brings come from its sheet or the bring model)")
    spreads_carry()
