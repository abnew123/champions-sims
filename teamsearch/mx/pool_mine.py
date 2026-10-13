"""Build matchup-style MINE entries from teamsearch/pool.json, using Showdown's Champions data (native/champions_data_full.json: a superset of champions_data.json, 2026-10-13).

Called from matchup.py (and from spgame.py, which execs matchup's source) with that namespace's M / FAKE_OUT / stats,
so the move dicts have exactly the fields the one-on-one code expects. Champions stats: HP = base + 75 + SP,
others floor((base + 20 + SP) x nature). What the one-on-one model can't see is left out, as for the threats:
status moves, accuracy, crits and secondary chances under 100%.
"""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
DEX = json.load(open(os.path.join(HERE, '..', '..', 'native', 'champions_data_full.json')))
POOL = json.load(open(os.environ.get('POOL_FILE', os.path.join(HERE, '..', 'grid_sets.json'))))
def idf(s): return re.sub(r'[^a-z0-9]', '', s.lower())

AB = {"Intimidate": "intimidate", "Defiant": "defiant", "Unburden": "unburden", "Adaptability": "adaptability", "Armor Tail": "armor_tail",
      "Levitate": "levitate", "Rock Head": "rock_head", "Grassy Surge": "grassy_surge", "Psychic Surge": "psychic_surge",
      "Rough Skin": "rough_skin", "Fairy Aura": "fairy_aura", "Stamina": "stamina", "Thermal Exchange": "thermal_exchange",
      "Mirror Armor": "mirror_armor", "Competitive": "competitive", "Contrary": "contrary", "Clear Body": "clear_body_lead",
      "Trace": "trace_lead", "Drought": "drought", "Flash Fire": "flash_fire", "Mega Launcher": "mega_launcher",
      "Huge Power": "huge_power", "Swift Swim": "swift_swim", "Sand Rush": "sand_rush", "Chlorophyll": "chlorophyll",
      "Multiscale": "multiscale", "Prankster": "prankster", "Magic Bounce": "magic_bounce", "No Guard": "no_guard"}
ENTRY_AB = {"intimidate", "trace_lead", "clear_body_lead"}          # a Mega's base ability only matters as it comes in
WEATHER_AB = {"Drought": "sun", "Drizzle": "rain", "Sand Stream": "sand", "Snow Warning": "snow"}
TERRAIN_AB = {"Grassy Surge": "grassy", "Psychic Surge": "psychic"}
ATE = {"Pixilate": "Fairy", "Aerilate": "Flying", "Refrigerate": "Ice", "Galvanize": "Electric"}
WBALL = {"sun": "Fire", "rain": "Water", "sand": "Rock", "snow": "Ice"}
ITEM = {"Sitrus Berry": "Sitrus"}                                   # the one-on-one code's short names
for b in ("Chople", "Colbur", "Occa", "Babiri", "Kasib", "Yache", "Shuca", "Passho", "Wacan", "Rindo", "Coba", "Kebia",
          "Payapa", "Tanga", "Charti", "Haban", "Roseli"):
    ITEM[b + " Berry"] = b

def species(name):
    return DEX['species'][idf(name)]
def mega_forme(s):
    """(battle forme, base forme or None): a Mega Stone holder fights as its Mega and switches in as the base forme"""
    ms = DEX['items'].get(idf(s['item']), {}).get('megaStone') or {}
    if ms:
        base_name, mega_name = next(iter(ms.items()))
        return species(mega_name), species(base_name)
    return species(s['species']), None

def build(M, FAKE_OUT, stats):
    out, weights = {}, {}
    ok = lambda s: idf(s['species']) in DEX['species'] and all(idf(m) in DEX['moves'] for m in s['moves']) \
        and (not s['item'] or idf(s['item']) in DEX['items'])
    want = set(os.environ['GRID_IDS'].split(',')) if os.environ.get('GRID_IDS') else None
    for pid, s in POOL.items():
        if not ok(s) or (want is not None and pid not in want): continue
        sp, base = mega_forme(s)
        evs = s['evs']; nat = s['nature']
        b6 = lambda x: [x['stats'][k] for k in ('hp', 'atk', 'def', 'spa', 'spd', 'spe')]
        st = stats(b6(sp), nat, evs)
        ab_name, base_ab = s['ability'], None
        if base is not None:          # a Mega fights with its Mega ability; team sheets list either the Mega's or the base's
            base_ab = s['ability'] if s['ability'] in base['abilities'].values() else s.get('base_ability')
            ab_name = sp['abilities']['0']
        ab = {AB[ab_name]} if ab_name in AB else set()
        if base_ab in AB and AB[base_ab] in ENTRY_AB: ab.add(AB[base_ab])
        weather = WEATHER_AB.get(ab_name) or WEATHER_AB.get(base_ab or '')
        terrain = TERRAIN_AB.get(ab_name)
        if weather == "sun": ab.add("drought")
        moves = []
        for mn in s['moves']:
            mv = DEX['moves'][idf(mn)]
            if mn == "Fake Out": moves.append(FAKE_OUT()); continue
            if mv['category'] == 'Status': continue
            t, bp, c = mv['type'], mv['basePower'], 'p' if mv['category'] == 'Physical' else 's'
            fl = mv.get('flags', {})
            spread = mv['target'] in ('allAdjacentFoes', 'allAdjacent')
            k = dict(pr=mv['priority'], contact=bool(fl.get('contact')))
            power = 1.0
            if t == 'Normal' and ab_name in ATE and mn not in ("Weather Ball", "Terrain Pulse"): t, power = ATE[ab_name], 1.2
            if ab_name == "Tough Claws" and fl.get('contact'): power = 1.3
            f = (0.75 if spread else 1.0) * power
            if mv.get('recoil'): k['rc'] = mv['recoil'][0] / mv['recoil'][1] if mv['recoil'] != [33, 100] else 1 / 3
            if mv.get('drain'): k['dr'] = mv['drain'][0] / mv['drain'][1]
            sb = (mv.get('self') or {}).get('boosts')
            if sb: k['drop'] = dict(sb)
            sv = (mv.get('self') or {}).get('volatileStatus')
            if sv == 'mustrecharge': k['recharge'] = True
            if sv == 'glaiverush': k['glaive'] = True
            sec = mv.get('secondary') or {}
            if sec.get('chance') == 100 and sec.get('boosts'): k['tdrop'] = dict(sec['boosts'])
            if sec.get('chance') == 100 and sec.get('status') == 'par': k['para'] = True
            if fl.get('pulse'): k['pulse'] = True
            # moves with their own rules in the one-on-one code
            if mn in ("Eruption", "Water Spout"): k['spout'] = True
            if mn == "Expanding Force": k['expforce'] = True
            if mn in ("Low Kick", "Grass Knot"): k['lowkick'] = True
            if mn == "Sucker Punch": k['sucker'] = True
            if mn == "Knock Off": k['knockoff'] = True
            if mn == "Body Press": k['bodypress'] = True
            if mn == "Terrain Pulse": k['terrainpulse'] = True
            if mn == "Grassy Glide": k['grassy_prio'] = True
            if mn in ("Earthquake", "Bulldoze"): k['eq'] = True
            if mn == "Darkest Lariat": k['ignore_def'] = True
            if mn == "Steel Roller": k.update(needs_terrain=True, kills_terrain=True)
            if mn == "First Impression": k['first'] = True
            if mn == "Last Respects": bp = 100                     # one teammate down, as for the threats
            if mn == "Weather Ball" and weather: t, bp = WBALL[weather], 100
            if mn == "Solar Beam" and weather != "sun": k['charge'] = True
            if mn in ("Electro Shot", "Meteor Beam") and weather != "rain": k['charge'] = True
            mh = mv.get('multihit')
            if isinstance(mh, int): k['hits'] = mh
            elif isinstance(mh, list): k['hits'] = 5 if ab_name == "Skill Link" else 3     # 2-5 hits: about 3 on average
            if mn == "Triple Axel": bp, k['hits'] = 40, 3                                   # 20 + 40 + 60
            if mn == "Population Bomb": k['hits'] = 7                                       # each hit rolls 90% accuracy
            if mv.get('overrideDefensiveStat') == 'def': k['psyshock'] = True
            if mv.get('ignoreDefensive'): k['ignore_def'] = True
            if mn == "Freeze-Dry": k['freezedry'] = True
            if mn == "Acrobatics": k['acro'] = True
            moves.append(M(mn, t, bp, c, f, **k))
        e = dict(types=list(sp['types']), st=st, item=ITEM.get(s['item'], s['item']) or None, ab=ab, moves=moves,
                 weather=weather, terrain=terrain, species=sp['name'], ability=ab_name, base_ability=base_ab)
        if base is not None: e['entry_st'] = stats(b6(base), nat, evs)
        out[pid] = e
        weights[pid] = sp['weightkg']
    return out, weights
