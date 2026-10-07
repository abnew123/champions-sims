"""Which human lines does the sim misjudge? (2026-10-07) For every slot decision in Eval bar's accuracy set (560 cached Bo3 games,
one-turn planner at 32 seeds, sym2 value; evalpos rows + the positions with the choices actually made), the human's play is classed by kind
of line (attack, Protect, switch, setup, redirection, Trick Room, Tailwind, pivot, speed control, ...) and by situation (double Protect,
Protect under the foe's Trick Room / Tailwind, turn-1 Protect, switch into Intimidate, ...). Per class: how often humans and the planner
play it, the planner's weight on the human's play, its regret, and the real test: the game's actual outcome against the planner's own
rating of the chosen line (both sides' values rescaled as the eval bar's are, log-odds x CAL). A class where the actual win rate beats
the planner's rating of the line is a line the sim thinks is worse than it is; one where it matches is the sim being right.
  ../.venv/bin/python3 human_lines.py <eval.jsonl> <pos.jsonl> [min rating] [CAL=0.7538]  -> results/human_lines.txt + .json
Outcomes come from the cached logs (replays_protect/<id>.log, git-ignored). No names are read beyond mapping the winner to p1/p2."""
import json, os, sys, math, collections, random
HERE = os.path.dirname(os.path.abspath(__file__))
MOVES = json.load(open(os.path.join(HERE, '..', 'native', 'engine_data_full.json')))['moves']
BYNAME = {m['name']: k for k, m in MOVES.items()}
SETUP = {'swordsdance', 'dragondance', 'nastyplot', 'calmmind', 'bulkup', 'irondefense', 'coil', 'agility', 'shellsmash', 'quiverdance', 'curse',
         'bellydrum', 'tidyup', 'shiftgear', 'victorydance', 'honeclaws', 'workup', 'growth', 'stockpile', 'amnesia', 'acidarmor', 'cosmicpower',
         'clangoroussoul', 'noretreat', 'filletaway', 'geomancy', 'rockpolish', 'autotomize', 'howl', 'meditate', 'sharpen', 'defendorder', 'cottonguard'}
def kind(label):
    """the human's option label -> (kind, move id or None)"""
    if label.startswith('switch to'): return 'switch', None
    name = label.split(' -> ')[0].replace(' (Mega)', '').strip()
    mid = BYNAME.get(name)
    if mid is None: return 'other', None
    m = MOVES[mid]
    if mid == 'fakeout': return 'Fake Out', mid
    if m.get('stallingMove'): return 'Protect', mid
    if mid in ('wideguard', 'quickguard'): return 'Wide/Quick Guard', mid
    if mid in ('followme', 'ragepowder'): return 'redirection', mid
    if mid == 'allyswitch': return 'Ally Switch', mid
    if mid == 'trickroom': return 'Trick Room', mid
    if mid == 'tailwind': return 'Tailwind', mid
    if m.get('sideCondition') in ('reflect', 'lightscreen', 'auroraveil'): return 'screen', mid
    if mid in ('helpinghand', 'coaching', 'decorate'): return 'Helping Hand', mid
    if m.get('selfSwitch'): return 'pivot', mid
    if m['category'] == 'Status':
        if mid in SETUP or (m.get('boosts') and m['target'] == 'self' and any(v > 0 for v in m['boosts'].values())): return 'setup', mid
        if m.get('status') or mid in ('yawn', 'spore', 'sleeppowder', 'hypnosis', 'darkvoid'): return 'status move', mid
        if mid in ('taunt', 'encore', 'disable', 'imprison', 'haze', 'trick', 'switcheroo', 'perishsong', 'skillswap', 'roar', 'whirlwind'): return 'disruption', mid
        if m.get('weather') or m.get('terrain'): return 'weather/terrain', mid
        if m.get('heal') or mid in ('healpulse', 'lifedew', 'wish', 'pollenpuff', 'junglehealing'): return 'heal', mid
        if mid == 'substitute': return 'Substitute', mid
        return 'other status', mid
    sec = m.get('secondary') or {}
    if sec.get('chance') == 100 and sec.get('boosts') and all(v < 0 for v in sec['boosts'].values()) and m['target'] in ('allAdjacentFoes', 'allAdjacent'):
        return 'speed/stat control', mid
    if m.get('priority', 0) > 0: return 'priority attack', mid
    if m['target'] in ('allAdjacentFoes', 'allAdjacent'): return 'spread attack', mid
    return 'attack', mid
def logit(v): v = min(1 - 1e-4, max(1e-4, v)); return math.log(v / (1 - v))
def resc(v, cal): return 1 / (1 + math.exp(-cal * logit(v)))
def winner(gid):
    """p1 / p2 / None from the cached log (names only compared, never kept)"""
    p = os.path.join(HERE, 'replays_protect', gid + '.log')
    if not os.path.exists(p): return None
    players, win = {}, None
    for l in open(p, errors='replace'):
        if l.startswith('|player|'):
            f = l.rstrip('\n').split('|')
            if len(f) > 3 and f[3]: players[f[3]] = f[2]
        elif l.startswith('|win|'): win = l.rstrip('\n').split('|')[2]
    return players.get(win) if win else None
def situations(st, s, slot, kd, mid, pos, label, turn):
    """extra tags for the human's play from the position"""
    tags = []
    side = st['sides'][s]; foe = st['sides'][1 - s]
    act = side['pokemon'][side['active'][slot]] if side['active'][slot] is not None else None
    pw = st['field'].get('pseudoWeather') or {}
    tr = pw.get('trickroom', {}).get('duration') if 'trickroom' in pw else 0
    my_spe = [p['storedStats']['spe'] for p in side['pokemon'] if not p['fainted']]; foe_spe = [p['storedStats']['spe'] for p in foe['pokemon'] if not p['fainted']]
    slower = sum(my_spe) / max(1, len(my_spe)) < sum(foe_spe) / max(1, len(foe_spe))
    foe_tw = 'tailwind' in (foe.get('sideConditions') or {}); my_tw = 'tailwind' in (side.get('sideConditions') or {})
    hpf = act['hp'] / max(1, act['maxhp']) if act else 1.0
    if kd == 'Protect':
        if act and 'stall' in (act.get('volatiles') or {}): tags.append('Protect: again (double)')
        if tr and not slower: tags.append("Protect: under foe's Trick Room")
        if foe_tw and not my_tw: tags.append("Protect: under foe's Tailwind")
        if turn == 1: tags.append('Protect: turn 1')
        if hpf < 0.35: tags.append('Protect: low HP (<35%)')
        # the partner's actual play this turn, if known: Protect to cover a setup / Trick Room / Tailwind turn
        pa = pos['actual'][1 - slot] if pos.get('actual') and len(pos['actual']) > 1 else None
        if pa and pa.get('choice') and pa['choice'][0] != 'switch':
            pm = side['pokemon'][side['active'][1 - slot]] if side['active'][1 - slot] is not None else None
            if pm:
                k = pa['choice'][0]
                if isinstance(k, int) and k < len(pm['moveSlots']):
                    pmid = pm['moveSlots'][k]['id']; pk, _ = kind(MOVES[pmid]['name']) if pmid in MOVES else ('other', None)
                    if pk in ('setup', 'Trick Room', 'Tailwind'): tags.append(f'Protect: partner {pk}')
    if kd == 'switch':
        tgt = label.replace('switch to ', '').strip()
        tp = next((p for p in side['pokemon'] if not p['fainted'] and (p['set']['species'] == tgt or p['species'] == tgt.lower().replace(' ', '').replace('-', ''))), None)
        if tp and tp.get('ability', '').lower().replace(' ', '') == 'intimidate': tags.append('switch: into Intimidate')
        if hpf < 0.35: tags.append('switch: out at low HP (<35%)')
        elif hpf > 0.8: tags.append('switch: out of a healthy Pokemon')
        if tr and not slower: tags.append("switch: under foe's Trick Room")
        if act and any(v > 0 for v in act['boosts'].values()): tags.append('switch: giving up boosts')
        if act and any(v < 0 for v in act['boosts'].values()): tags.append('switch: resetting drops')
    if kd == 'setup':
        if turn == 1: tags.append('setup: turn 1')
        if tr and slower: tags.append('setup: under own Trick Room')
    if kd == 'Trick Room':
        if tr: tags.append('Trick Room: reversing')
        else: tags.append('Trick Room: setting')
    if kd in ('attack', 'spread attack', 'priority attack'):
        # attacking into a foe that Protected last turn / a foe at low HP
        pass
    return tags
def summarize(rows, cal, by, label_of):
    """rows: dicts with w, v, vtop, won(0/1/None), top(bool), game. Per class: counts and outcome tests, with game-resampled SE."""
    groups = collections.defaultdict(list)
    for r in rows:
        for k in by(r): groups[k].append(r)
    out = []
    for k, g in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        n = len(g); dis = [r for r in g if r['w'] < 0.05]; agree = [r for r in g if r['w'] >= 0.3]
        def outcome(sub):
            sub = [r for r in sub if r['won'] is not None]
            if len(sub) < 8: return None
            act = sum(r['won'] for r in sub) / len(sub); pv = sum(resc(r['v'], cal) for r in sub) / len(sub); pt = sum(resc(r['vtop'], cal) for r in sub) / len(sub)
            # SE of (actual - predicted) by game resampling
            byg = collections.defaultdict(list)
            for r in sub: byg[r['game']].append(r['won'] - resc(r['v'], cal))
            keys = list(byg); rnd = random.Random(7); diffs = []
            for _ in range(300):
                pick = [byg[rnd.choice(keys)] for _ in keys]; flat = [x for l in pick for x in l]; diffs.append(sum(flat) / len(flat))
            mu = sum(diffs) / len(diffs); se = (sum((d - mu) ** 2 for d in diffs) / len(diffs)) ** 0.5
            return {'n': len(sub), 'actual': act, 'sim_line': pv, 'sim_top': pt, 'edge': act - pv, 'se': se}
        out.append({'class': k, 'n': n, 'share': n / len(rows), 'w_mean': sum(r['w'] for r in g) / n, 'top_pick': sum(r['top'] for r in g) / n,
                    'regret_mean': sum(r['vtop'] - r['v'] for r in g) / n, 'disliked': len(dis) / n,
                    'all': outcome(g), 'disliked_outcome': outcome(dis), 'agreed_outcome': outcome(agree)})
    return out
def main(evalf, posf, min_rating, cal):
    idx = json.load(open(os.path.join(HERE, 'replays_protect', 'index.json')))
    pos = {}
    for l in open(posf): p = json.loads(l); pos[p['name']] = p
    rows = []; planned = collections.Counter(); wins = {}
    nrows = 0
    for l in open(evalf):
        r = json.loads(l); p = pos.get(r['name'])
        if not p: continue
        gid = r['name'].split(' ')[0]
        rating = (idx.get(gid) or {}).get('rating')
        if min_rating and (rating is None or rating < min_rating): continue
        if gid not in wins: wins[gid] = winner(gid)
        nrows += 1
        st = p['state']
        for si, s in enumerate(r['sides']):
            side_name = 'p1' if si == 0 else 'p2'
            won = None if wins[gid] is None else int(wins[gid] == side_name)
            for sl in s['slots']:
                opts = sl['options']
                if not opts: continue
                for o in opts: planned[kind(o['label'])[0]] += o['w']
                act = next((o for o in opts if o['actual']), None)
                if act is None: continue
                top = max(opts, key=lambda o: o['w'])
                kd, mid = kind(act['label'])
                tags = situations(st, si, sl['slot'], kd, mid, p if si == 0 else {'actual': p.get('their_actual')}, act['label'], p['turn'])
                rows.append({'game': gid, 'name': r['name'], 'turn': r['turn'], 'side': side_name, 'mon': sl['mon'], 'label': act['label'], 'kind': kd, 'tags': tags,
                             'w': act['w'], 'v': act['v'], 'vtop': top['v'], 'top': act is top, 'top_label': top['label'], 'won': won, 'rating': rating})
    tot_w = sum(planned.values())
    kinds = summarize(rows, cal, lambda r: [r['kind']], None)
    base_rows = [r for r in rows if r['w'] >= 0.5 and r['won'] is not None]
    baseline = sum(r['won'] - resc(r['v'], cal) for r in base_rows) / len(base_rows)
    for k in kinds:
        k['planner_share'] = planned[k['class']] / tot_w
        a = k['agreed_outcome']; d = k['disliked_outcome']
        k['net'] = None if not d else d['edge'] - (a['edge'] if a and a['n'] >= 50 else baseline)
    sits = summarize(rows, cal, lambda r: r['tags'], None)
    # weight buckets over all kinds: when humans deviate from the sim, do they do better than the sim says?
    def bucket(r): w = r['w']; return ['w < 1%' if w < 0.01 else 'w 1-5%' if w < 0.05 else 'w 5-20%' if w < 0.2 else 'w 20-50%' if w < 0.5 else 'w >= 50%']
    buckets = summarize(rows, cal, bucket, None)
    lines = [f"{nrows} positions, {len(rows)} decisions with a known human play, {len(wins)} games ({sum(1 for v in wins.values() if v)} with a winner), min rating {min_rating or 'none'}, CAL {cal}",
             f"selection baseline: on plays the planner gives >= 50% the side's actual win rate exceeds the planner's rating by {100 * baseline:+.1f} points (a Pokemon's play is",
             "only known when it got to act, and sides whose Pokemon act win more); 'net' = the disliked plays' edge less the kind's agreed edge (or this baseline)",
             "", "per kind of line: share of human plays / of the planner's mix; planner's weight on the human play; top-pick rate; regret (points); 'disliked' = weight < 5%",
             "   outcome test: actual win rate of the side vs the planner's rescaled rating of the chosen line (sim_line) and of its own top pick (sim_top); edge = actual - sim_line (SE by game)",
             f"{'kind':20s} {'n':>5s} {'human%':>6s} {'plan%':>6s} {'w':>5s} {'top%':>5s} {'regret':>6s} {'dis%':>5s} | {'disliked plays: n':>17s} {'actual':>6s} {'sim_line':>8s} {'sim_top':>7s} {'edge':>12s} | {'agreed: n':>9s} {'edge':>12s} | {'net':>5s}"]
    def fo(o, with_top=True):
        if not o: return f"{'-':>17s}" + ' ' * (6 + 1 + 8 + 1 + 7 + 1 + 12 + 1 if with_top else 0)
        s = f"{o['n']:17d} {100 * o['actual']:6.1f} {100 * o['sim_line']:8.1f} {100 * o['sim_top']:7.1f} {100 * o['edge']:+6.1f} ± {100 * o['se']:4.1f}"
        return s
    for k in kinds:
        d = k['disliked_outcome']; a = k['agreed_outcome']
        lines.append(f"{k['class']:20s} {k['n']:5d} {100 * k['share']:6.1f} {100 * k['planner_share']:6.1f} {k['w_mean']:5.2f} {100 * k['top_pick']:5.0f} {100 * k['regret_mean']:6.1f} {100 * k['disliked']:5.0f} | "
                     + (f"{d['n']:17d} {100 * d['actual']:6.1f} {100 * d['sim_line']:8.1f} {100 * d['sim_top']:7.1f} {100 * d['edge']:+6.1f} ± {100 * d['se']:4.1f}" if d else f"{'-':>17s}" + ' ' * 38)
                     + " | " + (f"{a['n']:9d} {100 * a['edge']:+6.1f} ± {100 * a['se']:4.1f}" if a else f"{'-':>9s}" + ' ' * 13)
                     + " | " + (f"{100 * k['net']:+5.1f}" if k['net'] is not None else '    -'))
    lines += ["", "by the planner's weight on the human play (all kinds): actual outcome vs the planner's rating of the line",
              f"{'bucket':20s} {'n':>5s} {'actual':>6s} {'sim_line':>8s} {'sim_top':>7s} {'edge':>12s} {'regret':>6s}"]
    for b in sorted(buckets, key=lambda x: x['class']):
        o = b['all']
        if o: lines.append(f"{b['class']:20s} {o['n']:5d} {100 * o['actual']:6.1f} {100 * o['sim_line']:8.1f} {100 * o['sim_top']:7.1f} {100 * o['edge']:+6.1f} ± {100 * o['se']:4.1f} {100 * b['regret_mean']:6.1f}")
    lines += ["", "situations (a play can carry several tags)",
              f"{'situation':36s} {'n':>5s} {'w':>5s} {'top%':>5s} {'regret':>6s} {'dis%':>5s} | {'all: actual':>11s} {'sim_line':>8s} {'edge':>12s} | {'disliked: n':>11s} {'actual':>6s} {'sim_line':>8s} {'edge':>12s}"]
    for s in sits:
        o = s['all']; d = s['disliked_outcome']
        lines.append(f"{s['class']:36s} {s['n']:5d} {s['w_mean']:5.2f} {100 * s['top_pick']:5.0f} {100 * s['regret_mean']:6.1f} {100 * s['disliked']:5.0f} | "
                     + (f"{100 * o['actual']:11.1f} {100 * o['sim_line']:8.1f} {100 * o['edge']:+6.1f} ± {100 * o['se']:4.1f}" if o else f"{'-':>11s}" + ' ' * 22) + " | "
                     + (f"{d['n']:11d} {100 * d['actual']:6.1f} {100 * d['sim_line']:8.1f} {100 * d['edge']:+6.1f} ± {100 * d['se']:4.1f}" if d else f"{'-':>11s}"))
    # the most disliked human plays per kind, for reading: highest regret with weight < 5%, in won games (the lines that worked)
    lines += ["", "examples: disliked plays (weight < 5%) in games that side went on to win, highest regret first (replay id, turn, side)"]
    for k in kinds[:12]:
        ex = sorted([r for r in rows if r['kind'] == k['class'] and r['w'] < 0.05 and r['won'] == 1], key=lambda r: r['v'] - r['vtop'])[:4]
        if not ex: continue
        lines.append(f"  {k['class']}:")
        for r in ex: lines.append(f"    {r['game']:42s} t{r['turn']:<3d}{r['side']} {r['mon']:14s} {r['label']:36s} w {100 * r['w']:4.1f}% regret {100 * (r['vtop'] - r['v']):5.1f}  (planner: {r['top_label']})")
    # rating bias by the side's team archetype / core group (opp_pool.json carries both per replay side): actual outcome of the position
    # against the planner's rescaled root value, from each side's view, so a team style the planner rates too high reads negative
    arch = {}
    pp = os.path.join(HERE, 'opp_pool.json')
    if os.path.exists(pp):
        ent = {(e['id'], e['side']): e for e in json.load(open(pp))['entries']}
        prow = {}
        for l in open(evalf):
            r = json.loads(l); gid = r['name'].split(' ')[0]
            if gid not in wins or wins[gid] is None: continue
            a, b = ent.get((gid, 'p1')), ent.get((gid, 'p2'))
            if not a or not b: continue
            v = resc(r['value'], cal); won = wins[gid] == 'p1'
            for e, d in ((a, won - v), (b, (1 - won) - (1 - v))):
                for key in (('arch', e.get('arch')), ('group', e.get('group'))):
                    prow.setdefault(key, collections.defaultdict(list))[gid].append(d)
        for (kindk, name), byg in prow.items():
            l = [x for g in byg.values() for x in g]
            if len(byg) < 6: continue
            keys = list(byg); rnd = random.Random(3); ms = []
            for _ in range(300): flat = [x for kk in [rnd.choice(keys) for _ in keys] for x in byg[kk]]; ms.append(sum(flat) / len(flat))
            mu = sum(l) / len(l); se = (sum((m - sum(ms) / len(ms)) ** 2 for m in ms) / len(ms)) ** 0.5
            arch.setdefault(kindk, []).append({'team': name, 'positions': len(l), 'games': len(byg), 'bias': mu, 'se': se})
        for kindk, title in (('arch', 'archetype (pro_replays.arch)'), ('group', 'core group')):
            lines += ["", f"planner rating bias by the side's team, {title}: actual - planner's root rating (points; positions, games; SE by game). Negative = the planner rates that style too high"]
            for a in sorted(arch.get(kindk, []), key=lambda x: -x['positions']):
                lines.append(f"  {a['team'][:60]:60s} {a['positions']:5d} {a['games']:4d} {100 * a['bias']:+6.1f} ± {100 * a['se']:4.1f}")
    txt = '\n'.join(lines) + '\n'; print(txt)
    os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
    open(os.path.join(HERE, 'results', 'human_lines.txt'), 'w').write(txt)
    json.dump({'eval': os.path.basename(evalf), 'positions': nrows, 'decisions': len(rows), 'min_rating': min_rating, 'cal': cal, 'baseline': baseline, 'kinds': kinds, 'situations': sits, 'buckets': buckets, 'team_bias': arch},
              open(os.path.join(HERE, 'results', 'human_lines.json'), 'w'), indent=1)
if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1], int(a[2]) if len(a) > 2 and a[2] not in ('0', 'none') else 0, float(a[3]) if len(a) > 3 else 0.7538)
