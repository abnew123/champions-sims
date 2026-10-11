"""Engine positions for a Showdown bot's own decisions (the planner playing its own bot account; Battle sim's bot/, asked 2026-10-10). Not
for a game a person is playing.
  bot_position(log, request, side, topk=1, team=None, tag='bot') -> ([(weight, spec)], info)
    log      the bot's battle room log as text (the room shows the bot's own side with exact HP), up to the |turn| line of this decision.
             Showdown sends the |request| just before the turn's battle lines: call this once the |turn| line is in
    request  the |request| JSON this decision answers (a dict or its text): a turn start (not team preview, not a replacement after a faint)
    side     the bot's side, 'p1' or 'p2'
    topk     how many of the opponent's most likely back rows to return (live.py's TOPK is 3)
    team     the bot's team as a Showdown export, for its exact spreads (the open team sheets have none; without it they are guessed)
  The specs come most likely first, the bot as side 0. live.positions(specs, outf) writes the engine positions (line '<name> p1' is the
  bot's view), engine.run(posf, outf) evaluates them, and in each result sides[0] is the bot.
The opponent's side is what a spectator knows (live.py): team preview, the open team sheets, what the game has shown, and the Pokémon it
has not sent in yet as its topk most likely back rows (back rates given its leads). The bot's side comes from the request: the four it
brought, each one's HP, status, fainting and held item; the log adds what the request leaves out (boosts, volatiles, the choice lock).
PP is not modelled.
info: {'turn', 'hyp': [(weight, the opponent's back row)], 'need', 'dropped'}, or {'skip': why} with no specs."""
import re, json
import live as LV, replay as R, spots as S
toid = R.toid
STATK = {'hp': 'hp', 'atk': 'atk', 'def': 'def', 'spa': 'spa', 'spd': 'spd', 'spe': 'spe'}
def export(text):
    """a Showdown team export -> {base species id: set with its spread}"""
    out = {}
    for block in re.split(r'\n\s*\n', text.strip()):
        L = [l.strip() for l in block.splitlines() if l.strip()]
        if not L: continue
        head = L[0].split(' @ '); name = re.sub(r' \([MF]\)$', '', head[0].strip())
        m = re.search(r'\(([^()]+)\)$', name); sp = m.group(1) if m else name          # "Nickname (Species)"
        st = {'species': sp, 'item': head[1].strip() if len(head) > 1 else '', 'ability': '', 'nature': 'Serious', 'moves': [], 'evs': [0] * 6}
        for l in L[1:]:
            if l.startswith('Ability:'): st['ability'] = l.split(':', 1)[1].strip()
            elif re.match(r'(EVs|SPs):', l):
                for part in l.split(':', 1)[1].split('/'):
                    v, k = part.split(); st['evs'][S.ORDER.index(STATK[toid(k)])] = int(v)
            elif l.endswith(' Nature'): st['nature'] = l[:-len(' Nature')].strip()
            elif l.startswith('- '): st['moves'].append(l[2:].strip())
        out[toid(sp.split('-')[0])] = st
    return out
def condition(c):
    """'150/202 par' -> (HP percent, exact; status; fainted)"""
    if 'fnt' in c: return 0, '', True
    hp, mx = map(int, c.split()[0].split('/')); st = c.split()[1] if len(c.split()) > 1 else ''
    return 100 * hp / mx, st, False
def fresh(st):
    return {**st, 'mega': False, 'hpPct': 100, 'fainted': False, 'status': '', 'slept': 0, 'boosts': {}, 'itemNow': st['item'], 'moved': False,
            'stall': False, 'lock': '', 'vol': [], 'onField': False, 'last': '', 'volarg': {}}
def own_side(state, sets, req, mine, dropped):
    """the bot's side from its request, with what the log tracks laid under it; None if the log and the request disagree"""
    out = []
    for k, p in enumerate(req['side']['pokemon']):
        sp = p['details'].split(',')[0]; base = toid(sp.split('-')[0])
        m = next((x for x in state['mons'] if toid(x['sp'].split('-')[0]) == base), None)
        if p.get('active') and not m: return None, f'{sp} is active in the request but not on the field in the log'
        if mine.get(base):
            st, bad = S.fit_set(mine[base], dropped)
            if st: st = {**st, 'evs': list(mine[base]['evs'])}
        else: st = next((v for key, v in sets.items() if toid(key.split('-')[0]) == base), None)
        if not st: return None, f'no set for {sp}'
        hp, status, fnt = condition(p['condition']); item = (S.E['items'].get(p.get('item') or '') or {}).get('name', '')
        d = LV.spec_mon(m, st) if m else fresh(st)
        d.update(hpPct=hp, status=status, fainted=fnt, itemNow=item, onField=bool(p.get('active')) and not fnt)
        if fnt: d['boosts'] = {}
        out.append((0 if k == 0 and d['onField'] else 1 if k == 1 and d['onField'] else 2 if not fnt else 3, k, d))
    return [d for _, _, d in sorted(out, key=lambda x: x[:2])], None
def bot_position(log, request, side, topk=1, team=None, tag='bot'):
    req = json.loads(request) if isinstance(request, str) else request
    if req.get('teamPreview') or req.get('wait'): return [], {'skip': 'no move to choose'}
    if req.get('forceSwitch'): return [], {'skip': 'a replacement after a faint, not a turn start'}
    i = log.rfind('\n|turn|')
    if i < 0: return [], {'skip': 'the battle has not started'}
    j = log.find('\n', i + 1); pre = log[:j + 1] if j >= 0 else log + '\n'
    gp = R.parse(pre); step = gp['steps'][-1]; st = step['state']; opp = 'p2' if side == 'p1' else 'p1'
    six, sets, dropped = LV.sets_for(gp, pre, True)
    mine, why = own_side(st[side], sets[side], req, export(team) if team else {}, dropped)
    if mine is None: return [], {'skip': why}
    H, pool, need = LV.hyps(opp, st, six, sets, LV.Live.leads(None, pre), topk)
    order = sorted(st[opp]['mons'], key=lambda m: (0 if m['pos'] == 'a' else 1 if m['pos'] == 'b' else 2 if not m['f'] else 3))
    bad = [m['sp'] for m in order if not sets[opp].get(m['sp'])]
    if bad: return [], {'skip': 'no set for ' + ', '.join(bad)}
    seen = [LV.spec_mon(m, sets[opp][m['sp']]) for m in order]; f = st['field']; out = []
    for h, (w, back) in enumerate(H):
        theirs = seen + [{**fresh(sets[opp][sp]), 'standIn': True} for sp in back]
        sides = [{'mons': ms, 'tailwind': st[sd]['tailwind'], 'screens': st[sd]['screens'], 'hazards': st[sd]['hazards']} for sd, ms in ((side, mine), (opp, theirs))]
        out.append((w, {'name': f"{tag} t{step['turn']} h{h}", 'turn': step['turn'], 'sides': sides, 'acts': [[None, None], [None, None]],
                        'perish': st['perish'], 'standIns': len(back), 'dropped': [],
                        'field': {'weather': [f['weather'], f['wturns']] if f['weather'] else None,
                                  'terrain': [f['terrain'], f['tturns']] if f['terrain'] else None, 'trickroom': f['tr']}}))
    return out, {'turn': step['turn'], 'hyp': H, 'need': need, 'dropped': dropped}
