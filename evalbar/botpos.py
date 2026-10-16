"""Engine positions for a Showdown bot's own decisions (the planner playing its own bot account; Battle sim's bot/, asked 2026-10-10). Not
for a game a person is playing.
  bot_position(log, request, side, topk=1, team=None, tag='bot') -> ([(weight, spec)], info)
    log      the bot's battle room log as text (the room shows the bot's own side with exact HP), up to the |turn| line of this decision.
             Showdown sends the |request| just before the turn's battle lines: call this once the |turn| line is in
    request  the |request| JSON this decision answers (a dict or its text): a turn start (not team preview, not a replacement after a faint)
    side     the bot's side, 'p1' or 'p2'
    topk     how many of the opponent's most likely back rows to return (live.py's TOPK is 3)
    team     the bot's team as a Showdown export or a list of sets with 'evs' (bot/teams.json), for its exact spreads (the open team sheets have none; without it they are guessed)
  The specs come most likely first, the bot as side 0. live.positions(specs, outf) writes the engine positions (line '<name> p1' is the
  bot's view), engine.run(posf, outf) evaluates them, and in each result sides[0] is the bot.
The opponent's side is what a spectator knows (live.py): team preview, the open team sheets, what the game has shown, and the Pokémon it
has not sent in yet as its topk most likely back rows (back rates given its leads). The bot's side comes from the request: the four it
brought, each one's HP, status, fainting and held item; the log adds what the request leaves out (boosts, volatiles, the choice lock).
PP is not modelled.
info: {'turn', 'hyp': [(weight, the opponent's back row)], 'need', 'dropped'}, or {'skip': why} with no specs.
  bot_replacement(log, request, side, replacements, topk=1, team=None, tag='bot') -> ([(weight, spec)], info)
    a forceSwitch request (a replacement after a faint, or a pivot's switch): the next turn's start with the bot's replacements in
    (replacements {'a': species, 'b': species}, the slots the request asks for), and the switch-in abilities that follow (Intimidate,
    weather, terrain; rules.py; info['tail'] shows the lines added for the most likely branch). When the opponent replaces at the same time, each of its possible replacements is a spec, weighted by how
    likely that Pokemon is in its back row (each Pokemon on its bench equally likely to come in). A pivot's switch comes mid-turn: the rest
    of that turn is left out (info['midturn']).
  decisions(log, side) -> [{'kind': 'preview' | 'turn' | 'switch', 'log', 'request', 'actual'}]
    for testing on saved games: each decision the player on that side made, the log as it stood then and a request built from what the
    game showed by its end (the four brought; HP in percent, as a spectator sees it), and what the player chose.
  python3 evalbar/botpos.py [games=50]   every decision of that many saved Bo3 games (C.games()), both sides, built; counts what failed"""
import re, json, math, itertools, collections
import live as LV, replay as R, spots as S, rules as RU, battlestate as BS
toid = R.toid
# the positions.js fixes the bot's positions ask for (battlestate.FLAGS has the eval bar's). Battle sim switches each on for the bot: yawnDue
# and volDue (a Yawn at the turn start puts its target to sleep at this turn's end; Taunt, Encore, Disable, Throat Chop and Heal Block keep
# their remaining turns) the user, 2026-10-12; pctDue, abilDue, chipDue (Toxic's stage, binding moves), fallenDue (Supreme Overlord's count)
# and typeDue (types changed in battle) the user, 2026-10-12 evening; then syrupDue and srcDue
BOT_FLAGS = dict.fromkeys(('yawnDue', 'volDue', 'fieldDue', 'pctDue', 'abilDue', 'chipDue', 'fallenDue', 'typeDue', 'syrupDue', 'srcDue',
                           'rechargeDue', 'itemDue', 'chargeDue'), True)   # rechargeDue / itemDue: on for the bot 2026-10-14 (Battle sim, the standing rule)
# chargeDue: on 2026-10-16 (Battle sim, the standing rule): a charged move stopped before it fired is no longer charging; of the bot's
# 1,933 decisions in its 243 games with a charged move, only …2698578723's turn 7 changes (their Archaludon, flinched mid Electro Shot,
# was read as locked into the charge; it used Protect)
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
def team_sets(team):
    """the bot's team, as a Showdown export or a list of sets with 'evs' (bot/teams.json) -> {base species id: set}"""
    if not team: return {}
    return export(team) if isinstance(team, str) else {toid(t['species'].split('-')[0]): t for t in team}
def condition(c):
    """'150/202 par' -> (HP percent, exact; status; fainted)"""
    if 'fnt' in c: return 0, '', True
    hp, mx = map(int, c.split()[0].split('/')); st = c.split()[1] if len(c.split()) > 1 else ''
    return 100 * hp / mx, st, False
def spread(p, st):
    """the bot's exact stat points from its request (its stats, and its max HP from the condition), with the set's nature: [hp, atk, def,
    spa, spd, spe], or the set's own where a stat cannot be matched (Champions: stat = (2 base + 31 + 2 points) / 2 + 5, times the nature)"""
    E = S.E; sp = E['species'].get(toid(p['details'].split(',')[0])) or E['species'].get(toid(st['species']))
    nat = E['natures'].get(toid(st.get('nature', '')), {}); stats = p.get('stats') or {}
    if not sp or not stats: return st['evs']
    out = list(st['evs'])
    for i, k in enumerate(S.ORDER):
        B = sp['stats'][k]
        if k == 'hp':
            if 'fnt' in p['condition']: continue
            want = int(p['condition'].split()[0].split('/')[1]); calc = lambda x: (2 * B + 31 + 2 * x) * 50 // 100 + 60
        else:
            want = stats.get(k); m = 1.1 if nat.get('plus') == k else 0.9 if nat.get('minus') == k else 1.0
            calc = lambda x: int(((2 * B + 31 + 2 * x) * 50 // 100 + 5) * m)
        hit = next((x for x in range(33) if calc(x) == want), None)
        if hit is not None: out[i] = hit
    return out
def refine_opponent(pre, gp, sets, side, req, strict=False):
    """the opponent's spreads (in sets) picked against the turn order the log shows, the bot's own Speed being exact (spreads.py)"""
    import spreads
    known = {}
    for p in req['side']['pokemon']:
        sp = p['details'].split(',')[0]; st = next((v for k, v in sets[side].items() if v and toid(k.split('-')[0]) == toid(sp.split('-')[0])), None)
        if st: known[toid(sp.split('-')[0])] = (spread(p, st), st['nature'])
    return spreads.refine(pre, gp, sets, side, known, strict)
def own_side(state, sets, req, mine, dropped, slots=False):
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
        st = {**st, 'evs': spread(p, st)}                                    # the exact spread, from the stats the request shows
        hp, status, fnt = condition(p['condition']); item = (S.E['items'].get(p.get('item') or '') or {}).get('name', '')
        d = BS.mon(m, st, BOT_FLAGS) if m else BS.fresh(st)
        d.update(hpPct=hp, status=status, fainted=fnt, itemNow=item, onField=bool(p.get('active')) and not fnt)
        if fnt: d['boosts'] = {}
        # slots (the eval bar's): a fainted Pokemon still in slot a keeps it, as the log's positions (and so the turn's choices) have it;
        # without, the one left standing moves up to slot a (the bot's positions; it maps its choices by species)
        on = p.get('active') if slots else d['onField']
        out.append((0 if k == 0 and on else 1 if k == 1 and on else 2 if not fnt else 3, k, d))
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
    mine, why = own_side(st[side], sets[side], req, team_sets(team), dropped)
    refine_opponent(pre, gp, sets, side, req, strict=3)                      # the opponent's spreads against the turn order seen so far (strict: the user, 2026-10-12; level 3, exact action Speed: the user, 2026-10-12 evening)
    if mine is None: return [], {'skip': why}
    H, pool, need = LV.hyps(opp, st, six, sets, LV.Live.leads(None, pre), topk)
    order = BS.order(st[opp])
    bad = [m['sp'] for m in order if not sets[opp].get(m['sp'])]
    if bad: return [], {'skip': 'no set for ' + ', '.join(bad)}
    seen = [BS.mon(m, sets[opp][m['sp']], BOT_FLAGS) for m in order]; out = []
    for h, (w, back) in enumerate(H):
        theirs = seen + [BS.fresh(sets[opp][sp], True) for sp in back]
        sides = [BS.side(st[sd], ms) for sd, ms in ((side, mine), (opp, theirs))]
        out.append((w, BS.spec(f"{tag} t{step['turn']} h{h}", step, sides, [[None, None], [None, None]], len(back), BOT_FLAGS)))
    return out, {'turn': step['turn'], 'hyp': H, 'need': need, 'dropped': dropped}
def nicks(log, sd):
    """{species: the nickname the log calls it by}"""
    out = {}
    for l in log.split('\n'):
        p = l.split('|')
        if len(p) > 3 and p[1] in ('switch', 'drag') and p[2].startswith(sd): out.setdefault(p[3].split(',')[0], p[2].split(': ', 1)[1])
    return out
def back_odds(sd, state, six, sets, leads):
    """the Pokemon on this side's bench, for a replacement: [(weight, species)], each bench Pokemon equally likely to come in"""
    H, pool, need = LV.hyps(sd, state, six, sets, leads, topk=10 ** 6)
    bench = [m['sp'] for m in state[sd]['mons'] if not m['pos'] and not m['f']]
    return H, bench
def bot_replacement(log, request, side, replacements, topk=1, team=None, tag='bot'):
    req = json.loads(request) if isinstance(request, str) else request
    need = req.get('forceSwitch') or []; rows = req['side']['pokemon']; slots = [x for i, x in enumerate('ab') if i < len(need) and need[i]]
    if not slots: return [], {'skip': 'not a forceSwitch request'}
    if set(replacements) != set(slots): return [], {'skip': f"replacements for slots {', '.join(slots)} are needed"}
    t = log.rfind('\n|turn|')
    if t < 0: return [], {'skip': 'the battle has not started'}
    N = int(log[t + 7:].split('\n')[0]); body = log[t:]; midturn = '\n|upkeep' not in body; pre = log.rstrip('\n') + '\n'
    new = [dict(r) for r in rows]; mine = []
    for sl, sp in replacements.items():
        k = 'ab'.index(sl); j = next((i for i, r in enumerate(new) if toid(r['details'].split(',')[0].split('-')[0]) == toid(sp.split('-')[0])), None)
        if j is None or new[j].get('active') or 'fnt' in new[j]['condition']: return [], {'skip': f'{sp} cannot come in'}
        new[k], new[j] = new[j], new[k]; new[k]['active'] = True; new[j]['active'] = False
        mine.append(f"|switch|{side}{sl}: {new[k]['ident'].split(': ', 1)[1]}|{new[k]['details']}|{new[k]['condition']}")
    synth = {**{k: v for k, v in req.items() if k != 'forceSwitch'}, 'side': {**req['side'], 'pokemon': new}}
    opp = 'p2' if side == 'p1' else 'p1'; branches = [(1.0, [])]
    if not midturn:                                                      # the opponent replaces its own fainted Pokemon at the same time
        g = R.parse(pre); st = g['final']; turn_part = body.split('\n|upkeep')[0]
        empty = sorted({l.split('|')[2][2] for l in turn_part.split('\n') if l.startswith(f'|faint|{opp}')})
        if empty:
            six, sets, _ = LV.sets_for(g, pre, True); H, bench = back_odds(opp, st, six, sets, LV.Live.leads(None, pre))
            acc = collections.defaultdict(float); nk = nicks(pre, opp); hp = {m['sp']: m['hp'] for m in st[opp]['mons']}
            for w, back in H:
                full = bench + list(back); k = min(len(empty), len(full))
                for sub in itertools.combinations(sorted(full), k): acc[sub] += w / math.comb(len(full), k)
            branches = [(w, [f"|switch|{opp}{sl}: {nk.get(sp, sp)}|{sp}, L50|{hp.get(sp, 100)}/100" for sl, sp in zip(empty, sub)]) for sub, w in acc.items()]
    out = []; derived = True; first = None
    for b, (wb, theirs) in enumerate(sorted(branches, key=lambda x: -x[0])):
        tail = mine + theirs + ['|', f'|turn|{N + 1}']; text = pre + '\n'.join(tail) + '\n'
        try:                                                             # the switch-ins' abilities, as the rules have them
            d = RU.derive(text); i = d.rfind('\n' + tail[0] + '\n')
            if i >= 0: text = pre + d[i + 1:].rstrip('\n') + '\n'
            else: derived = False
        except Exception: derived = False
        if first is None: first = text[len(pre):].rstrip('\n').split('\n')
        specs, info = bot_position(text, synth, side, topk, team, f'{tag} b{b}')
        if not specs: return [], info
        out += [(wb * w, sp) for w, sp in specs]
    return sorted(out, key=lambda x: -x[0]), {'turn': N + 1, 'midturn': midturn, 'their': [(w, [l.split('|')[3].split(',')[0] for l in th]) for w, th in branches],
                                              'derived': derived, 'tail': first}
def fake_request(state, side, sheets, brought, nk, force=None):
    """a |request| as Showdown would send it, from what a spectator saw (HP in percent)"""
    rows = []; E = S.E
    def row(sp, forme, cond, active, item):
        sh = sheets.get(toid(sp)) or sheets.get(toid(sp.split('-')[0])) or {}
        return {'ident': f"{side}: {nk.get(sp, sp)}", 'details': f'{forme or sp}, L50', 'condition': cond, 'active': active, 'stats': {},
                'moves': [toid(m) for m in sh.get('moves', [])], 'baseAbility': toid(sh.get('ability', '')), 'ability': toid(sh.get('ability', '')),
                'item': toid(item), 'pokeball': 'pokeball'}
    for m in sorted(state['mons'], key=lambda m: (0 if m['pos'] == 'a' else 1 if m['pos'] == 'b' else 2)):
        sh = sheets.get(toid(m['sp'])) or sheets.get(toid(m['sp'].split('-')[0])) or {}
        rows.append(row(m['sp'], m['forme'], '0 fnt' if m['f'] else f"{m['hp']}/100" + (f" {m['st']}" if m['st'] else ''), bool(m['pos']) and not m['f'],
                        '' if m['gone'] else (m['item'] or sh.get('item', ''))))
    for sp in brought:
        if not any(toid(r['details'].split(',')[0].split('-')[0]) == toid(sp.split('-')[0]) for r in rows):
            rows.append(row(sp, '', '100/100', False, (sheets.get(toid(sp)) or {}).get('item', '')))
    act = [{'moves': [{'move': E['moves'][i]['name'], 'id': i, 'pp': 8, 'maxpp': 8, 'target': E['moves'][i]['target'], 'disabled': False}
                      for i in r['moves'] if i in E['moves']]} for r in rows[:2] if r['active']]
    return {'forceSwitch': force, 'side': {'id': side, 'pokemon': rows}, 'rqid': 0} if force else {'active': act, 'side': {'id': side, 'pokemon': rows}, 'rqid': 0}
def decisions(log, side):
    g = R.parse(log); sheets = g['sheets'][side]; brought = [m['sp'] for m in g['final'][side]['mons']]; nk = nicks(log, side)
    L = log.split('\n'); out = []; acts = {s['turn']: s['acts'] for s in g['steps']}
    six = [l.split('|')[3].split(',')[0] for l in L if l.startswith(f'|poke|{side}|')]
    leads = [l.split('|')[3].split(',')[0] for l in L if l.startswith(f'|switch|{side}')][:2]
    for i, l in enumerate(L):
        upto = '\n'.join(L[:i]) + '\n'
        if l.startswith('|teampreview'):
            j = i + 1
            while j < len(L) and (L[j].startswith('|showteam|') or L[j].startswith('|t:|')): j += 1   # the open sheets come during preview
            out.append({'kind': 'preview', 'log': '\n'.join(L[:j]) + '\n', 'request': {'teamPreview': True, 'maxChosenTeamSize': 4, 'side': {'id': side, 'pokemon': [
                {'ident': f'{side}: {sp}', 'details': f'{sp}, L50', 'condition': '100/100', 'active': False, 'item': toid((sheets.get(toid(sp)) or {}).get('item', '')),
                 'moves': [toid(m) for m in (sheets.get(toid(sp)) or {}).get('moves', [])]} for sp in six]}}, 'actual': {'brought': brought, 'leads': leads}})
        elif l.startswith('|turn|'):
            t = int(l[6:]); st = R.parse(upto + l)['steps'][-1]['state']
            out.append({'kind': 'turn', 'log': upto + l + '\n', 'request': fake_request(st[side], side, sheets, brought, nk),
                        'actual': {k[2]: v for k, v in (acts.get(t) or {}).items() if k.startswith(side)}})
        elif l.startswith(f'|switch|{side}'):
            p = l.split('|'); pivot = '[from]' in l
            after_upkeep = not pivot and any(x == '|upkeep' for x in L[max(0, i - 4):i])
            if not (pivot or after_upkeep): continue
            first = i
            while not pivot and L[first - 1].startswith('|switch|'): first -= 1  # the first replacement of this batch (either side)
            if not pivot and any(x['kind'] == 'switch' and x.get('at') == first for x in out):
                x = next(x for x in out if x.get('at') == first); x['request']['forceSwitch']['ab'.index(p[2][2])] = True; x['actual'][p[2][2]] = p[3].split(',')[0]
                continue
            cut = '\n'.join(L[:first]) + '\n'; st = R.parse(cut)['final']
            force = [False, False]; force['ab'.index(p[2][2])] = True
            out.append({'kind': 'switch', 'at': first, 'log': cut, 'request': fake_request(st[side], side, sheets, brought, nk, force),
                        'actual': {p[2][2]: p[3].split(',')[0]}, 'pivot': pivot})
    for x in out: x.pop('at', None)
    return out
if __name__ == '__main__':
    import sys, common as C, procs as P
    P.own()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50; done = collections.Counter(); bad = collections.Counter(); k = 0
    for rid, log in C.games():
        if '|showteam|' not in log or '|teampreview' not in log: continue
        k += 1
        if k > n: break
        for sd in ('p1', 'p2'):
            for d in decisions(log, sd):
                if d['kind'] == 'preview': done['preview'] += 1; continue
                specs, info = (bot_position(d['log'], d['request'], sd) if d['kind'] == 'turn' else bot_replacement(d['log'], d['request'], sd, d['actual']))
                if specs: done[d['kind']] += 1
                else: bad[(d['kind'], info.get('skip'))] += 1
    print(f"{min(k, n)} games: built {dict(done)}; not built {sum(bad.values())}", *(f"\n  {c} {kd}: {w}" for (kd, w), c in bad.most_common(10)))
