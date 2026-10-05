"""Bring heuristic features: for a six, the four it brings (S) and the two it leads (L), against an opposing six (weighted species).

Every Pokémon is represented by a set: mine by its grid id; a replay player's Pokémon by the most common regional set of that
species (canon_gid.json); the opponent likewise. One-on-one matrix cells (teamsearch/mx/out) are looked up against the opponent's
threat name (mxtr's 46 threats); typing, speed and roles come from the sets and Showdown's Champions data.
"""
import json, os, re, math, functools, itertools
HERE = os.path.dirname(os.path.abspath(__file__))
TS = os.path.join(HERE, '..')
import sys; sys.path.insert(0, TS)
import sets_lib as L
DEX = L.DEX
G = json.load(open(os.path.join(TS, 'grid_sets.json')))
CANON = json.load(open(os.path.join(HERE, 'canon_gid.json')))
for _sp, _s in json.load(open(os.path.join(L.ROOT, 'regionals', 'smogon_mc_sets.json'))).items():   # species with no regional set:
    _base = DEX['species'].get(L.idf(_sp), {}).get('base', _sp)                                    # Smogon's set (neutral cells)
    for _name in {_sp, _base}:
        if _name not in CANON and L.idf(_sp) in DEX['species']:
            G['smogon:' + _sp] = dict(_s, species=_base if DEX['species'][L.idf(_sp)]['isMega'] else _sp); CANON[_name] = 'smogon:' + _sp
THREATS = ["Rillaboom", "Sneasler", "M-Salamence", "Incineroar", "Kingambit", "Basculegion", "M-Floette", "Farigiraf", "M-Golisopod",
           "Pelipper", "Indeedee-F", "Gholdengo", "Arcanine-H", "Sylveon", "Whimsicott", "Archaludon", "M-Tyranitar", "M-Baxcalibur",
           "Garchomp", "M-Garchomp Z", "Milotic", "M-Charizard Y", "M-Gardevoir", "M-Raichu Y", "M-Staraptor", "M-Metagross", "Volcarona",
           "Corviknight", "Dragapult", "Torkoal", "Hatterene", "Indeedee", "Armarouge", "M-Gengar", "Sinistcha",
           "M-Swampert", "Grimmsnarl", "Politoed", "Venusaur", "Excadrill", "M-Froslass", "M-Camerupt", "M-Delphox", "M-Aerodactyl",
           "M-Mawile", "M-Dragonite"]
TSET = set(THREATS)
GVAL = {"counter": 1.0, "check": 0.75, "wall": 0.5, "lost": 0.0}

def threat_of(species):
    """the matrix threat name for a team-sheet / preview species (as plan.rs gname: forme aliases, then Mega by base)"""
    if species in TSET: return species
    al = {'Arcanine-Hisui': 'Arcanine-H', 'Floette-Eternal': 'M-Floette', 'Floette': 'M-Floette'}
    if species in al: return al[species]
    base = re.sub(r'-Mega.*$', '', species)
    mega = next((t for t in THREATS if t == 'M-' + base or t.startswith('M-' + base + ' ')), None)
    if mega: return mega
    return base if base in TSET else None

@functools.lru_cache(maxsize=None)
def cells(gid, tr):
    p = os.path.join(TS, 'mx', 'out', 'tr' if tr else 'notr', gid.replace('/', '_') + '.json')
    if not os.path.exists(p): return None
    out = {}
    for foe, c in json.load(open(p))['cells'].items():
        v = c['v']
        out[foe] = c['pct'] / 100 if v == 'roll' else min(0.75, (c.get('pct') or 50) / 100) if v == 'guess' else GVAL.get(v, 0.5)
    return out

def eff(atk, types):
    x = 1.0
    for t in types:
        d = DEX['types'][t].get(atk, 0)
        if d == 3: return 0.0
        x *= {0: 1, 1: 2, 2: 0.5}[d]
    return x

ATE = {"Pixilate": "Fairy", "Aerilate": "Flying", "Refrigerate": "Ice", "Galvanize": "Electric"}
WX_SET = {"Drought": "sun", "Drizzle": "rain", "Sand Stream": "sand", "Snow Warning": "snow"}
TERR_SET = {"Grassy Surge": "grassy", "Psychic Surge": "psychic", "Electric Surge": "electric", "Misty Surge": "misty"}

@functools.lru_cache(maxsize=None)
def info(gid):
    """battle forme, types, Speed, attack types, roles"""
    s = G[gid]
    forme = L.battle_forme(s['species'], s['item'])
    sp = DEX['species'].get(L.idf(forme)) or DEX['species'][L.idf(s['species'])]
    ab = sp['abilities']['0'] if sp['isMega'] else s['ability']
    n = DEX['natures'].get(L.idf(s['nature']), {})
    spe = math.floor((sp['stats']['spe'] + 20 + s['evs'][5]) * (1.1 if n.get('plus') == 'spe' else 0.9 if n.get('minus') == 'spe' else 1))
    if s['item'] == 'Choice Scarf': spe = spe * 3 // 2
    mv = [DEX['moves'][L.idf(m)] for m in s['moves'] if L.idf(m) in DEX['moves']]
    names = {m['name'] for m in mv}
    atk = []
    for m in mv:
        if m['category'] == 'Status': continue
        t = m['type']
        if t == 'Normal' and ab in ATE: t = ATE[ab]
        atk.append(t)
    wx = WX_SET.get(ab) or WX_SET.get(s['ability'] if not sp['isMega'] else '')
    terr = TERR_SET.get(ab)
    types = sp['types']
    abuse = {
        'sun': bool({'Chlorophyll', 'Solar Power', 'Protosynthesis'} & {ab}) or 'Fire' in atk or bool({'Solar Beam', 'Weather Ball'} & names),
        'rain': ab in ('Swift Swim',) or 'Water' in atk or bool({'Hurricane', 'Thunder', 'Weather Ball'} & names),
        'sand': ab in ('Sand Rush', 'Sand Force') or bool({'Rock', 'Ground', 'Steel'} & set(types)),
        'snow': ab in ('Slush Rush',) or bool({'Blizzard', 'Aurora Veil'} & names),
        'grassy': 'Grassy Glide' in names or s['item'] == 'Grassy Seed' or 'Grass' in atk,
        'psychic': 'Expanding Force' in names or s['item'] == 'Psychic Seed' or 'Psychic' in atk,
        'electric': 'Electric' in atk or s['item'] == 'Electric Seed',
        'misty': 'Fairy' in atk or s['item'] == 'Misty Seed',
    }
    return dict(species=s['species'], forme=sp['name'], types=types, spe=spe, atk=atk, ab=ab,
                mega=bool((DEX['items'].get(L.idf(s['item'] or ''), {}) or {}).get('megaStone')),
                fake=('Fake Out' in names), tw=('Tailwind' in names), tr=('Trick Room' in names),
                redir=bool({'Follow Me', 'Rage Powder'} & names), intim=(s['ability'] == 'Intimidate' or ab == 'Intimidate'),
                sctrl=bool({'Icy Wind', 'Electroweb', 'Thunder Wave', 'Bulldoze', 'Rock Tomb'} & names),
                perish=('Perish Song' in names), wx=wx, terr=terr, abuse=abuse, slow=spe <= 75)

def canon(species):
    """a set for a preview species: its own, else its base forme's (cosmetic formes like Sinistcha-Masterpiece, Maushold-Four)"""
    for name in (species, DEX['species'].get(L.idf(species), {}).get('base'), species.split('-')[0]):
        g = CANON.get(name)
        if g in G and L.idf(G[g]['species']) in DEX['species']: return g
    return None

class Matchup:
    """precomputed per (my six, opposing six with weights); feature vectors for every bring and lead"""
    def __init__(self, mine, opp):
        self.mine = mine                                            # 6 grid ids
        self.opp = [(o, threat_of(G[o]['species']) if o in G else None, w) for o, w in opp]   # (gid, threat, weight)
        I = [info(g) for g in mine]; O = [info(o) if o in G else None for o, _, _ in self.opp]
        self.I = I; W = [w for _, _, w in self.opp]; self.W = W
        n = len(self.opp)
        def cell(g, t, tr):
            c = cells(g, tr)
            return None if (c is None or t is None) else c.get(t)
        self.cn = [[cell(g, t, False) for _, t, _ in self.opp] for g in mine]
        self.ct = [[cell(g, t, True) for _, t, _ in self.opp] for g in mine]
        lg = lambda x: -2.0 if x == 0 else max(-2.0, min(2.0, math.log2(x)))
        self.off = [[(max((lg(eff(a, O[j]['types'])) for a in I[i]['atk']), default=-1.0) if O[j] else 0.0) for j in range(n)] for i in range(6)]
        self.dfn = [[(-max((lg(eff(a, I[i]['types'])) for a in set(O[j]['atk']) | set(O[j]['types'])), default=0.0) if O[j] else 0.0) for j in range(n)] for i in range(6)]
        self.osp = [[(1.0 if I[i]['spe'] > O[j]['spe'] else 0.5 if I[i]['spe'] == O[j]['spe'] else 0.0) if O[j] else 0.5 for j in range(n)] for i in range(6)]

    def _cov(self, S, M):
        num = den = 0.0
        for j, w in enumerate(self.W):
            vals = [M[i][j] for i in S if M[i][j] is not None]
            if vals: num += w * max(vals); den += w
        return num / den if den else 0.5
    def _exp(self, S, M):
        out = []
        for i in S:
            vals = [M[i][j] for j in range(len(self.W)) if M[i][j] is not None and self.W[j] >= 0.25]
            out.append(min(vals) if vals else 0.5)
        return sum(out) / len(out)
    def _wavg(self, S, M, agg):
        tw = sum(self.W) or 1
        return sum(w * agg(M[i][j] for i in S) for j, w in enumerate(self.W)) / tw

    def bring_feats(self, S):
        I = self.I; X = [I[i] for i in S]
        wx = {x['wx'] for x in X if x['wx']}; terr = {x['terr'] for x in X if x['terr']}
        wsyn = max((sum(1 for i in S if I[i]['abuse'][w] and I[i]['wx'] != w) for w in wx), default=0)
        tsyn = max((sum(1 for i in S if I[i]['abuse'][t] and I[i]['terr'] != t) for t in terr), default=0)
        tr = any(x['tr'] for x in X)
        return [
            self._cov(S, self.cn), self._cov(S, self.ct) if tr else 0.0, self._exp(S, self.cn),
            self._wavg(S, self.off, max), sum(self._wavg([i], self.dfn, lambda g: sum(g)) for i in S) / 4,
            sum(self._wavg([i], self.osp, lambda g: sum(g)) for i in S) / 4,
            float(any(x['tw'] for x in X)), float(tr), (sum(x['slow'] for x in X) / 4) if tr else 0.0,
            min(wsyn, 2) / 2, min(tsyn, 2) / 2, float(sum(x['mega'] for x in X) >= 2), float(any(x['mega'] for x in X)),
            sum(x['intim'] for x in X) / 4, sum(x['fake'] for x in X) / 4, sum(x['redir'] for x in X) / 4,
            float(any(x['perish'] for x in X)), sum(x['sctrl'] for x in X) / 4,
        ]
    BRING_NAMES = ['cov', 'cov_tr', 'exposure', 'offense', 'defense', 'speed', 'tailwind', 'trick_room', 'tr_slow', 'weather_syn',
                   'terrain_syn', 'two_megas', 'mega', 'intimidate', 'fake_out', 'redirect', 'perish', 'speed_ctrl']

    def lead_feats(self, Lp, S):
        I = self.I; X = [I[i] for i in Lp]; back = [I[i] for i in S if i not in Lp]
        tr_lead = any(x['tr'] for x in X)
        wx_ok = any(x['wx'] and any(I[i]['abuse'][x['wx']] and I[i] is not x for i in S) for x in X)   # setter leads, an abuser is brought
        return [
            self._cov(Lp, self.cn), self._cov(Lp, self.ct) if tr_lead else 0.0,
            sum(self._wavg([i], self.osp, lambda g: sum(g)) for i in Lp) / 2, self._wavg(Lp, self.off, max),
            float(any(x['fake'] for x in X)), float(any(x['tw'] for x in X)), float(tr_lead),
            (sum(y['slow'] for y in back) / 2) if tr_lead else 0.0, float(any(x['redir'] for x in X)),
            float(any(x['intim'] for x in X)), float(wx_ok), float(any(x['terr'] for x in X)), float(any(x['mega'] for x in X)),
            float(any(x['sctrl'] for x in X)), float(any(x['perish'] for x in X)),
        ]
    LEAD_NAMES = ['lead_cov', 'lead_cov_tr', 'lead_speed', 'lead_offense', 'lead_fake_out', 'lead_tailwind', 'lead_trick_room',
                  'tr_slow_back', 'lead_redirect', 'lead_intimidate', 'lead_weather', 'lead_terrain', 'lead_mega', 'lead_speed_ctrl', 'lead_perish']

BRINGS = list(itertools.combinations(range(6), 4))
def leads(S): return list(itertools.combinations(S, 2))
