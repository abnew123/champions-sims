"""Value features from real games (2026-10-04): replays the Bo3 logs in replays_protect/ (open team sheets: items, abilities, natures, moves)
event by event and writes, at the start of every turn, the planner's position features (plan.rs feats) that have a replay equivalent,
labelled with the game's winner and the players' mean rating (r), from each player's side (the second copy has the features negated and the outcome flipped).
Features (mine minus theirs): hp (HP share of living brought Pokemon; brought but unseen count as full), n (Pokemon left of 4), bst (active
Pokemon's primary attack stage +-3 plus 0.3 x Speed stage +-2), tr (Trick Room turns left x tanh((their mean Speed - mine) / 15)), stall
(active Pokemon that Protected successfully last turn), te (type edge, as plan.rs type_edge), slp (asleep/frozen), par, brn (burned/poisoned),
tw (Tailwind turns left, 0 under Trick Room), scr (Reflect + Light Screen + Aurora Veil turns left).
Speed: (base + 20 + points) x nature; points are hidden, so +Speed natures count 32, -Speed 0, neutral 16.
usage: python3 replay_feats.py <out.json>"""
import json, glob, os, sys, re, math, collections
D = json.load(open('dex_moves_types.json')); SP = json.load(open('species_stats.json'))
MV, TY = D['moves'], D['types']
NATP = {'Timid': 1.1, 'Jolly': 1.1, 'Hasty': 1.1, 'Naive': 1.1, 'Brave': 0.9, 'Quiet': 0.9, 'Relaxed': 0.9, 'Sassy': 0.9}
PROTECT = {'Protect', 'Detect', 'Spiky Shield', "King's Shield", 'Baneful Bunker', 'Silk Trap', 'Burning Bulwark', 'Obstruct'}
ATE = {'pixilate': 'Fairy', 'aerilate': 'Flying', 'refrigerate': 'Ice', 'galvanize': 'Electric'}
toid = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
NAMES = ['hp', 'n', 'bst', 'tr', 'stall', 'te', 'slp', 'par', 'brn', 'tw', 'scr']
def eff(mtype, dtypes):
    e = 0
    for t in dtypes:
        x = TY.get(t, {}).get(mtype, 0)
        if x == 3: return None
        e += 1 if x == 1 else -1 if x == 2 else 0
    return e
def parse_team(s):
    out = {}
    for blob in s.split(']'):
        f = blob.split('|')
        if len(f) < 6: continue
        species = f[1] or f[0]
        out[toid(species)] = {'item': toid(f[2]), 'ability': toid(f[3]), 'moves': [toid(m) for m in f[4].split(',') if m], 'nature': f[5]}
    return out
class Mon:
    def __init__(s, species, sets): s.species = species; s.hp = 1.0; s.status = ''; s.fainted = False; s.boosts = collections.Counter(); s.set = sets.get(toid(species.split('-Mega')[0]), sets.get(toid(species), {})); s.stall = False
    def stats(s): return SP.get(s.species, SP.get(s.species.split('-Mega')[0], {'bs': {}, 'types': []}))
    def speed(s):
        bs = s.stats()['bs'].get('spe', 80); nat = NATP.get(s.set.get('nature', ''), 1.0)
        pts = 32 if nat > 1 else 0 if nat < 1 else 16
        return math.floor((bs + 20 + pts) * nat)
    def prim(s):
        ph = sum(MV.get(m, {}).get('cat') == 'Physical' for m in s.set.get('moves', [])); sp = sum(MV.get(m, {}).get('cat') == 'Special' for m in s.set.get('moves', []))
        return 'atk' if ph >= sp else 'spa'
def hpval(tok):
    tok = tok.split()[0] if tok else ''
    if tok == '0' or 'fnt' in tok: return 0.0
    m = re.match(r'(\d+)/(\d+)', tok)                      # '48/100', or with an HP-bar colour suffix ('48/100y')
    return int(m.group(1)) / int(m.group(2)) if m else None
def game(log):
    L = log.split('\n'); sets = {'p1': {}, 'p2': {}}; mons = {'p1': {}, 'p2': {}}; active = {}; field = {'tr': 0, 'w': '', 'ter': ''}
    tw = {'p1': 0, 'p2': 0}; scr = {'p1': collections.Counter(), 'p2': collections.Counter()}; rows = []; winner = None; names = {}
    protected_now = set(); last_user = None; turn = 0; ratings = {}
    def mon(ident):
        side = ident[:2]; nick = ident.split(': ', 1)[1] if ': ' in ident else ident
        return mons[side].get(nick)
    def feats(side):
        o = 'p2' if side == 'p1' else 'p1'
        def S(sd):
            alive = [m for m in mons[sd].values() if not m.fainted]; nf = sum(m.fainted for m in mons[sd].values())
            hp = sum(m.hp for m in alive) + max(0, 4 - len(mons[sd]))
            act = [mons[sd][active[p]] for p in (sd + 'a', sd + 'b') if p in active and active[p] in mons[sd] and not mons[sd][active[p]].fainted]
            bst = sum(max(-3, min(3, m.boosts[m.prim()])) + 0.3 * max(-2, min(2, m.boosts['spe'])) for m in act)
            spe = sum(m.speed() for m in alive) / max(1, len(alive))
            return dict(alive=alive, act=act, hp=hp, n=4 - nf, bst=bst, spe=spe, stall=sum(m.stall for m in act),
                        slp=sum(m.status in ('slp', 'frz') for m in alive), par=sum(m.status == 'par' for m in alive),
                        brn=sum(m.status in ('brn', 'psn', 'tox') for m in alive))
        a, b = S(side), S(o)
        def te(x, y):
            if not x['alive'] or not y['alive']: return 0.0
            t = 0.0
            for dm in y['alive']:
                dt = dm.stats()['types']; lev = dm.set.get('ability') == 'levitate'; best = -2
                for am in x['alive']:
                    for mid in am.set.get('moves', []):
                        mv = MV.get(mid)
                        if not mv or mv['cat'] == 'Status' or mid == 'fakeout': continue
                        ty = mv['type']
                        if mid == 'weatherball': ty = {'SunnyDay': 'Fire', 'RainDance': 'Water', 'Sandstorm': 'Rock', 'Snowscape': 'Ice', 'Snow': 'Ice'}.get(field['w'], 'Normal')
                        if mid == 'terrainpulse': ty = {'Psychic Terrain': 'Psychic', 'Grassy Terrain': 'Grass', 'Electric Terrain': 'Electric', 'Misty Terrain': 'Fairy'}.get(field['ter'], 'Normal')
                        if ty == 'Normal' and am.set.get('ability') in ATE: ty = ATE[am.set['ability']]
                        e = eff(ty, dt)
                        if e is None or (ty == 'Ground' and lev): continue
                        best = max(best, max(-2, min(2, e)))
                t += best
            return t / len(y['alive'])
        trf = field['tr'] * math.tanh((b['spe'] - a['spe']) / 15.0) if field['tr'] else 0.0
        return [a['hp'] - b['hp'], a['n'] - b['n'], a['bst'] - b['bst'], trf, a['stall'] - b['stall'], te(a, b) - te(b, a),
                a['slp'] - b['slp'], a['par'] - b['par'], a['brn'] - b['brn'],
                0.0 if field['tr'] else tw[side] - tw[o], sum(scr[side].values()) - sum(scr[o].values())]
    for l in L:
        p = l.split('|')
        if len(p) < 2: continue
        k = p[1]
        if k == 'player' and len(p) > 3:
            names[p[3]] = p[2]
            if len(p) > 5 and p[5].strip().isdigit(): ratings[p[2]] = int(p[5])
        elif k == 'showteam': sets[p[2]] = parse_team('|'.join(p[3:]))
        elif k in ('switch', 'drag', 'replace'):
            pos = p[2][:3]; side = pos[:2]; nick = p[2].split(': ', 1)[1]; species = p[3].split(',')[0]
            if pos in active and active[pos] in mons[side] and k != 'replace': mons[side][active[pos]].boosts.clear(); mons[side][active[pos]].stall = False
            if nick not in mons[side]: mons[side][nick] = Mon(species, sets[side])
            m = mons[side][nick]; active[pos] = nick
            if len(p) > 4: v = hpval(p[4]); m.hp = v if v is not None else m.hp; st = p[4].split(); m.status = st[1] if len(st) > 1 and st[1] != 'fnt' else m.status
        elif k == 'detailschange' or k == '-formechange':
            m = mon(p[2])
            if m: m.species = p[3].split(',')[0]
        elif k in ('-damage', '-heal', '-sethp'):
            m = mon(p[2]); v = hpval(p[3]) if len(p) > 3 else None
            if m and v is not None: m.hp = v
        elif k == 'faint':
            m = mon(p[2])
            if m: m.fainted = True; m.hp = 0.0
        elif k == '-status':
            m = mon(p[2])
            if m: m.status = p[3]
        elif k == '-curestatus':
            m = mon(p[2])
            if m: m.status = ''
        elif k in ('-boost', '-unboost'):
            m = mon(p[2])
            if m: m.boosts[p[3]] += int(p[4]) * (1 if k == '-boost' else -1); m.boosts[p[3]] = max(-6, min(6, m.boosts[p[3]]))
        elif k == '-setboost':
            m = mon(p[2])
            if m: m.boosts[p[3]] = int(p[4])
        elif k in ('-clearboost', '-clearallboost'):
            for side in mons:
                for m in mons[side].values():
                    if k == '-clearallboost' or (m is mon(p[2])): m.boosts.clear()
        elif k == '-clearnegativeboost':
            m = mon(p[2])
            if m: m.boosts = collections.Counter({s: v for s, v in m.boosts.items() if v > 0})
        elif k == 'move':
            last_user = mon(p[2])
        elif k == '-singleturn' and len(p) > 3 and any(x in p[3] for x in PROTECT):
            m = mon(p[2])
            if m: protected_now.add(id(m))
        elif k == '-fieldstart':
            if 'Trick Room' in p[2]: field['tr'] = 5
            elif 'Terrain' in p[2]: field['ter'] = p[2].replace('move: ', '')
        elif k == '-fieldend':
            if 'Trick Room' in p[2]: field['tr'] = 0
            elif 'Terrain' in p[2]: field['ter'] = ''
        elif k == '-weather': field['w'] = '' if p[2] == 'none' else p[2]
        elif k == '-sidestart':
            side = p[2][:2]; what = p[3].replace('move: ', '')
            if what == 'Tailwind': tw[side] = 4
            elif what in ('Reflect', 'Light Screen', 'Aurora Veil'): scr[side][what] = 8 if last_user is not None and last_user.set.get('item') == 'lightclay' else 5
        elif k == '-sideend':
            side = p[2][:2]; what = p[3].replace('move: ', '')
            if what == 'Tailwind': tw[side] = 0
            elif what in scr[side]: scr[side][what] = 0
        elif k == 'turn':
            turn = int(p[2])
            if turn > 1:                                     # durations tick at the end of each turn
                if field['tr']: field['tr'] -= 1
                for s in tw: tw[s] = max(0, tw[s] - 1)
                for s in scr:
                    for w in scr[s]: scr[s][w] = max(0, scr[s][w] - 1)
            for side in mons:
                for m in mons[side].values(): m.stall = id(m) in protected_now
            protected_now = set()
            rows.append((turn, feats('p1')))
        elif k == 'win': winner = names.get(p[2])
    return rows, winner, (sum(ratings.values()) / len(ratings) if len(ratings) == 2 else None)
if __name__ == '__main__':
    idx = json.load(open('replays_protect/index.json')); X = []; ng = 0; skipped = collections.Counter()
    for f in sorted(glob.glob('replays_protect/*.log')):
        rid = os.path.basename(f)[:-4]
        if not idx.get(rid, {}).get('fmt', '').endswith('bo3'): skipped['not Bo3'] += 1; continue
        log = open(f).read()
        if '|showteam|' not in log: skipped['no team sheet'] += 1; continue
        try: rows, w, rating = game(log)
        except Exception as e: skipped['parse error'] += 1; continue
        if w is None or not rows: skipped['no winner'] += 1; continue
        ng += 1; y = 1 if w == 'p1' else 0
        for t, fx in rows: X.append({'g': rid, 't': t, 'r': rating, 'f': fx, 'y': y}); X.append({'g': rid, 't': t, 'r': rating, 'f': [-v for v in fx], 'y': 1 - y})
    json.dump({'names': NAMES, 'rows': X}, open(sys.argv[1], 'w'))
    print(f"{ng} games, {len(X) // 2} positions (x2 mirrored); skipped {dict(skipped)}")
