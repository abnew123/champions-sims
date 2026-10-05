"""1v1 matchup simulator: each of the player's six against each threat.

Pessimistic by construction: his damage uses the MIN roll, theirs the MAX roll,
and each threat is simulated at each of its three most-used spreads, keeping the
worst result for him. Same-type bonus is computed from typing, never hand-entered.
"""
import math, json, copy, os
TR = os.environ.get('TR') == '1'          # Trick Room up for the whole one-on-one
exec(open('chart.py').read().split('TEAM=[')[0])          # eff(type, [types])

NAT = {"Adamant":(1.1,1,.9,1,1),"Modest":(.9,1,1.1,1,1),"Jolly":(1,1,.9,1,1.1),"Timid":(.9,1,1,1,1.1),
       "Careful":(1,1,.9,1.1,1),"Naive":(1,1,1,.9,1.1),"Relaxed":(1,1.1,1,1,.9),"Bold":(.9,1.1,1,1,1),
       "Impish":(1,1.1,.9,1,1),"Hasty":(1,.9,1,1,1.1),"Calm":(.9,1,1,1.1,1),
       "Quiet":(1,1,1.1,1,.9),"Brave":(1.1,1,1,1,.9),"Sassy":(1,1,1,1.1,.9)}
def stats(b, nat, sp):
    if len(sp) > 6: nat = sp[6]                     # a spread can carry its own nature
    m = NAT[nat]
    return [b[0]+75+sp[0]] + [math.floor((b[i]+20+sp[i])*m[i-1]) for i in range(1,6)]
def stage(n): return (2+n)/2 if n >= 0 else 2/(2-n)
def stage_stat(x, n): return x * (2 + n) // 2 if n >= 0 else x * 2 // (2 - n)     # exact integer stat stage
def js_round(x): return int(math.floor(x + 0.5))                                   # JavaScript Math.round (x >= 0)
def _mod(v, m4096): return int(math.floor((math.floor(v * m4096) + 2047) / 4096))   # Showdown modify(): 4096-based, rounds half down
def _chain(mods):
    m = 4096
    for x in mods: m = (m * x + 2048) >> 12
    return m

def M(n, t, bp, c, f=1.0, **k):
    """move: name, type, power, 'p'/'s', non-STAB factor (spread 0.75, -ate 1.2, Tough Claws 1.3)"""
    d = dict(n=n, t=t, bp=bp, c=c, f=f, pr=0, rc=0, dr=0, drop={}, charge=False, first=False,
             needs_terrain=False, kills_terrain=False, glaive=False, sucker=False, eq=False, expforce=False,
             contact=False, bodypress=False, terrainpulse=False, recharge=False, knockoff=False, heal=0, ignore_def=False, status=False,
             flinch=False)
    d.update(k); return d
def FAKE_OUT(): return M("Fake Out","Normal",40,"p",pr=3,first=True,contact=True,flinch=True)

# ---------------- the player's six ----------------
T = json.load(open('final_team.json'))
MINE = {
 "Blastoise": dict(types=["Water"], st=[186,123,140,205,137,88], item="Blastoisinite", ab={"mega_launcher"},
    entry_st=[186,103,120,150,127,88],                     # switching in, it is still base Blastoise (Torrent)
    moves=[FAKE_OUT(), M("Water Spout","Water",150,"s",0.75,spout=True), M("Aura Sphere","Fighting",80,"s",pulse=True),
           M("Dark Pulse","Dark",80,"s",pulse=True)]),
 "Torkoal": dict(types=["Fire"], st=[177,105,160,150,92,36], item="Charcoal", ab={"drought"},
    moves=[M("Eruption","Fire",150,"s",0.75,spout=True), M("Weather Ball","Fire",100,"s"), M("Earth Power","Ground",90,"s")]),
 "Farigiraf": dict(types=["Normal","Psychic"], st=[225,110,122,130,105,72], item="Sitrus", ab={"armor_tail"},
    moves=[M("Psychic","Psychic",90,"s"), M("Thunderbolt","Electric",90,"s")]),
 "Kingambit": dict(types=["Dark","Steel"], st=[207,205,140,72,107,70], item="Chople", ab={"defiant"},
    moves=[M("Kowtow Cleave","Dark",85,"p",contact=True), M("Sucker Punch","Dark",70,"p",pr=1,sucker=True,contact=True),
           M("Iron Head","Steel",80,"p",contact=True), M("Low Kick","Fighting",0,"p",lowkick=True,contact=True)]),
 "Hatterene": dict(types=["Psychic","Fairy"], st=[164,110,117,206,123,44], item="Life Orb", ab={"magic_bounce"},
    moves=[M("Expanding Force","Psychic",80,"s",expforce=True), M("Dazzling Gleam","Fairy",80,"s",0.75)]),
}

# ---------------- threats ----------------
F = json.load(open('foes.json'))
F["M-Charizard Y"] = [["Fire","Flying"],[78,104,78,159,115,100],"Modest",[[2,0,0,32,0,32],[2,0,0,32,0,32],[2,0,0,32,0,32]],"Charizardite Y",0]
# op.gg doubles, 23 Sep 2026: top spreads; natures paired where the spread only fits one
F["M-Raichu Y"]  = [["Electric"],[60,100,55,160,80,130],"Timid",[[2,0,0,32,0,32],[26,0,17,0,0,23],[32,0,11,0,0,23]],"Raichunite Y",0]
F["Milotic"]     = [["Water"],[95,60,79,100,125,81],"Bold",[[32,0,32,0,2,0,"Bold"],[20,0,20,4,8,14,"Calm"],[32,0,2,32,0,0,"Modest"]],"Leftovers",0]
F["M-Staraptor"] = [["Fighting","Flying"],[85,140,100,60,90,110],"Jolly",[[2,32,0,0,0,32],[32,2,0,0,0,32],[32,17,0,0,0,17]],"Staraptite",0]
F["Torkoal"]   = [["Fire"],[70,85,140,85,70,20],"Quiet",[[32,0,0,32,2,0],[32,0,1,32,1,0],[32,0,0,32,2,0,"Modest"]],"Charcoal",0]
F["Hatterene"] = [["Psychic","Fairy"],[57,90,95,136,103,29],"Quiet",[[32,0,2,32,0,0],[27,0,7,32,0,0],[32,0,0,32,2,0]],"Life Orb",0]
F["Indeedee"]  = [["Psychic","Normal"],[60,65,55,105,95,95],"Modest",[[32,0,0,32,2,0],[32,0,2,32,0,0],[2,0,0,32,0,32,"Timid"]],"Choice Scarf",0]
F["Armarouge"] = [["Fire","Psychic"],[85,60,100,125,80,75],"Modest",[[7,0,21,32,0,6],[32,0,12,20,2,0,"Quiet"],[32,0,0,32,2,0]],"Life Orb",0]
F["M-Gengar"]  = [["Ghost","Poison"],[60,65,80,170,95,130],"Modest",[[20,0,4,10,0,32],[30,0,1,1,28,6],[2,0,0,32,0,32,"Timid"]],"Gengarite",0]
F["Sinistcha"] = [["Grass","Ghost"],[71,60,106,121,80,70],"Bold",[[32,0,32,0,2,0],[32,0,0,0,32,2,"Calm"],[32,0,32,0,2,0,"Relaxed"]],"Kasib",0]
WEIGHT = {"Rillaboom":78.2,"Sneasler":43.0,"M-Salamence":112.6,"Incineroar":83.0,"Kingambit":120.0,"Basculegion":110.0,
 "Garchomp":95.0,"M-Garchomp Z":95.0,"Arcanine-H":168.0,"M-Golisopod":108.0,"Farigiraf":160.0,"Gholdengo":30.0,
 "Pelipper":28.0,"Indeedee-F":28.0,"Sylveon":23.5,"Whimsicott":6.6,"Archaludon":60.0,"M-Tyranitar":255.0,
 "M-Baxcalibur":210.0,"Corviknight":75.0,"M-Metagross":550.0,"Dragapult":50.0,"M-Floette":0.9,"Volcarona":46.0,
 "M-Gardevoir":48.4,"M-Charizard Y":100.5,"Salamence":112.6,"M-Raichu Y":30.0,"Milotic":162.0,"M-Staraptor":24.9,
 "Torkoal":80.4,"Hatterene":5.1,"Indeedee":28.0,"Armarouge":85.0,"M-Gengar":40.5,"Sinistcha":2.2,"Blastoise":101.1,"Farigiraf":160.0}
def lowkick_bp(w): return 20 if w<10 else 40 if w<25 else 60 if w<50 else 80 if w<100 else 100 if w<200 else 120

TM = {   # audited against Pikalytics Reg M-C (ladder + tournaments), op.gg and Pokemon Zone, Sep 2026
 "Rillaboom":[M("Wood Hammer","Grass",120,"p",rc=1/3),M("Grassy Glide","Grass",55,"p",pr=1,grassy_prio=True),
              M("High Horsepower","Ground",95,"p"),M("U-turn","Bug",70,"p"),FAKE_OUT()],
 "Sneasler":[M("Close Combat","Fighting",120,"p",drop={"def":-1,"spd":-1}),M("Dire Claw","Poison",80,"p"),
             M("Rock Slide","Rock",75,"p",0.75),FAKE_OUT()],
 "M-Salamence":[M("Hyper Voice","Flying",90,"s",1.2*0.75),M("Draco Meteor","Dragon",130,"s",drop={"spa":-2}),
                M("Double-Edge","Flying",120,"p",1.2,rc=1/3)],
 "Incineroar":[M("Flare Blitz","Fire",120,"p",rc=1/3),M("Throat Chop","Dark",80,"p"),M("Darkest Lariat","Dark",85,"p",ignore_def=True),FAKE_OUT()],
 "Kingambit":[M("Kowtow Cleave","Dark",85,"p"),M("Iron Head","Steel",80,"p"),M("Low Kick","Fighting",0,"p",lowkick=True),
              M("Sucker Punch","Dark",70,"p",pr=1,sucker=True),M("Swords Dance","Normal",0,"s",setup={"atk":2})],
 "Basculegion":[M("Last Respects","Ghost",100,"p"),M("Wave Crash","Water",120,"p",rc=1/3),M("Aqua Jet","Water",40,"p",pr=1),
                M("Flip Turn","Water",60,"p")],
 "Garchomp":[M("Earthquake","Ground",100,"p",0.75,eq=True),M("Stomping Tantrum","Ground",75,"p"),
             M("Dragon Claw","Dragon",80,"p"),M("Rock Slide","Rock",75,"p",0.75)],
 "M-Garchomp Z":[M("Draco Meteor","Dragon",130,"s",drop={"spa":-2}),M("Power Gem","Rock",80,"s"),
                 M("Flamethrower","Fire",90,"s"),M("Earth Power","Ground",90,"s"),M("Dragon Pulse","Dragon",85,"s")],
 "Arcanine-H":[M("Head Smash","Rock",150,"p"),M("Flare Blitz","Fire",120,"p",rc=1/3),M("Extreme Speed","Normal",80,"p",pr=2)],
 "M-Golisopod":[M("First Impression","Bug",100,"p",1.3,pr=2,first=True),M("Leech Life","Bug",80,"p",1.3,dr=0.5),   # Tough Claws
                M("Iron Head","Steel",80,"p",1.3),M("Liquidation","Water",85,"p",1.3),
                M("Swords Dance","Normal",0,"s",setup={"atk":2})],
 "M-Floette":[M("Moonblast","Fairy",95,"s"),M("Dazzling Gleam","Fairy",80,"s",0.75),M("Light of Ruin","Fairy",140,"s",rc=0.5),
              M("Calm Mind","Psychic",0,"s",setup={"spa":1,"spd":1})],                          # Fairy Aura via ability
 "Farigiraf":[M("Hyper Voice","Normal",90,"s",0.75),M("Psychic","Psychic",90,"s"),M("Thunderbolt","Electric",90,"s")],
 "Pelipper":[M("Hurricane","Flying",110,"s"),M("Weather Ball","Water",100,"s")],
 "Indeedee-F":[M("Psychic","Psychic",90,"s"),M("Terrain Pulse","Normal",50,"s",terrainpulse=True)],     # can't learn Expanding Force
 "Gholdengo":[M("Make It Rain","Steel",120,"s",0.75,drop={"spa":-2}),M("Shadow Ball","Ghost",80,"s"),
              M("Nasty Plot","Dark",0,"s",setup={"spa":2})],
 "Sylveon":[M("Hyper Voice","Fairy",90,"s",1.2*0.75),M("Hyper Beam","Fairy",150,"s",1.2,recharge=True),
            M("Quick Attack","Fairy",40,"p",1.2,pr=1)],
 "Whimsicott":[M("Moonblast","Fairy",95,"s")],
 "Archaludon":[M("Electro Shot","Electric",130,"s",charge=True),M("Flash Cannon","Steel",80,"s"),
               M("Dragon Pulse","Dragon",85,"s")],
 "M-Tyranitar":[M("Rock Slide","Rock",75,"p",0.75),M("Knock Off","Dark",65,"p",knockoff=True),M("Low Kick","Fighting",0,"p",lowkick=True),
                M("Dragon Dance","Dragon",0,"s",setup={"atk":1,"spe":1})],
 "M-Baxcalibur":[M("Glaive Rush","Dragon",120,"p",glaive=True),M("Icicle Crash","Ice",85,"p"),M("Ice Shard","Ice",40,"p",pr=1),
                 M("Dragon Dance","Dragon",0,"s",setup={"atk":1,"spe":1}),M("Swords Dance","Normal",0,"s",setup={"atk":2})],
 "Corviknight":[M("Brave Bird","Flying",120,"p",rc=1/3),M("Iron Head","Steel",80,"p"),M("Body Press","Fighting",80,"p",bodypress=True),
                M("Bulk Up","Fighting",0,"s",setup={"atk":1,"def":1}),M("Roost","Flying",0,"s",status=True,heal=0.5)],
 "M-Metagross":[M("Psychic Fangs","Psychic",85,"p",1.3),M("Iron Head","Steel",80,"p",1.3),M("Body Press","Fighting",80,"p",1.3,bodypress=True),
                M("Ice Punch","Ice",75,"p",1.3),M("Steel Roller","Steel",130,"p",1.3,needs_terrain=True,kills_terrain=True)],
 "Dragapult":[M("Draco Meteor","Dragon",130,"s",drop={"spa":-2}),M("Shadow Ball","Ghost",80,"s"),M("Flamethrower","Fire",90,"s")],
 "M-Gardevoir":[M("Hyper Voice","Fairy",90,"s",1.2*0.75),M("Expanding Force","Psychic",80,"s",expforce=True)],
 "Volcarona":[M("Heat Wave","Fire",95,"s",0.75),M("Bug Buzz","Bug",90,"s"),M("Fiery Dance","Fire",80,"s"),
              M("Giga Drain","Grass",75,"s",dr=0.5),M("Quiver Dance","Bug",0,"s",setup={"spa":1,"spd":1,"spe":1})],
 "M-Charizard Y":[M("Heat Wave","Fire",95,"s",0.75),M("Weather Ball","Fire",100,"s"),M("Solar Beam","Grass",120,"s"),
                  M("Ancient Power","Rock",60,"s")],
 "M-Raichu Y":[M("Zap Cannon","Electric",120,"s",para=True),M("Focus Blast","Fighting",120,"s"),FAKE_OUT()],   # No Guard: both always hit
 "Milotic":[M("Scald","Water",80,"s"),M("Ice Beam","Ice",90,"s"),M("Recover","Normal",0,"s",status=True,heal=0.5)],
 "M-Staraptor":[M("Close Combat","Fighting",120,"p",drop={"def":-1,"spd":-1},contact=True),M("Brave Bird","Flying",120,"p",rc=1/3,contact=True),
                M("Roost","Flying",0,"s",status=True,heal=0.5)],
 "Torkoal":[M("Eruption","Fire",150,"s",0.75,spout=True),M("Heat Wave","Fire",95,"s",0.75),M("Weather Ball","Fire",100,"s"),M("Earth Power","Ground",90,"s")],
 "Hatterene":[M("Expanding Force","Psychic",80,"s",expforce=True),M("Dazzling Gleam","Fairy",80,"s",0.75)],
 "Indeedee":[M("Expanding Force","Psychic",80,"s",expforce=True),M("Mystical Fire","Fire",75,"s",tdrop={"spa":-1})],
 "Armarouge":[M("Armor Cannon","Fire",120,"s",drop={"def":-1,"spd":-1}),M("Expanding Force","Psychic",80,"s",expforce=True)],
 "M-Gengar":[M("Shadow Ball","Ghost",80,"s"),M("Sludge Bomb","Poison",90,"s")],
 "Sinistcha":[M("Matcha Gotcha","Grass",80,"s",0.75,dr=0.5)],
}
TABIL = {"Incineroar":{"intimidate"},"M-Salamence":{"intimidate"},"Kingambit":{"defiant"},"Sneasler":{"unburden"},
         "Basculegion":{"adaptability"},"Farigiraf":{"armor_tail"},"M-Garchomp Z":{"levitate"},"Arcanine-H":{"rock_head"},
         "Rillaboom":{"grassy_surge"},"Indeedee-F":{"psychic_surge"},"Garchomp":{"rough_skin"},"M-Floette":{"fairy_aura"},
         "Archaludon":{"stamina"},"M-Baxcalibur":{"thermal_exchange"},"Corviknight":{"mirror_armor"},
         "M-Raichu Y":{"no_guard"},"Milotic":{"competitive"},"M-Staraptor":{"intimidate","contrary"},
         "M-Metagross":{"clear_body_lead"},"M-Gardevoir":{"trace_lead"},
         "Torkoal":{"drought"},"Indeedee":{"psychic_surge"},"Armarouge":{"flash_fire"},"Hatterene":{"magic_bounce"}}   # base abilities, live until it Mega Evolves
WEATHER = {"Pelipper":"rain","M-Charizard Y":"sun","M-Tyranitar":"sand","Torkoal":"sun"}
SPEED_EST = {"Dragapult":194,"M-Metagross":178,"Volcarona":167,"M-Gardevoir":167,"M-Charizard Y":167,"M-Tyranitar":135}
RESIST_BERRY = {"Chople":"Fighting","Colbur":"Dark"}
TYPE_ITEM = {"Miracle Seed":"Grass","Fairy Feather":"Fairy","Black Glasses":"Dark","Charcoal":"Fire"}

def make(name, types, st, item, ab, moves, weight):
    return dict(name=name, types=list(types), hp=st[0], maxhp=st[0], st=list(st), item=item, item_used=False,
                ab=set(ab), moves=copy.deepcopy(moves), stg={"atk":0,"def":0,"spa":0,"spd":0,"spe":0}, charged=False,
                glaive_vuln=False, weight=weight, seeded=False, fainted=False, out_turns=0)

def init_field(mine, foe, mode):
    w = "sun" if mine == "Torkoal" else WEATHER.get(foe)
    t = "grassy" if foe in ("Rillaboom", "Sneasler") else "psychic" if foe in ("Indeedee-F", "Indeedee") else None
    return {"terrain": t, "weather": w, "mode": mode, "tr": TR}
def goes_first(me, them, pa, pd, tie):
    """priority first; within a bracket the faster moves first, or the slower under Trick Room"""
    if pa != pd: return pa > pd
    a, b = speed(me), speed(them)
    if TR: a, b = -a, -b
    return a > b or (a == b and tie)
def grounded(p): return "Flying" not in p["types"] and "levitate" not in p["ab"]

MEGA_STONE = ("ite", "ite X", "ite Y", "ite Z")
def removable(p):
    it = p["item"]
    if it in (None, "consumed", "knocked") or str(it).endswith(MEGA_STONE): return False
    return not (p["item_used"] and it in ("Sitrus", "Chople", "Colbur", "Focus Sash"))

def mtype(att, mv, field):
    if mv.get("terrainpulse") and grounded(att):
        return {"psychic": "Psychic", "grassy": "Grass"}.get(field["terrain"], mv["t"])
    return mv["t"]

def damage(att, dfn, mv, field, roll):
    """exact in-game damage: base-power modifiers, floors, spread, weather, random roll, STAB, type, final modifiers
    (Showdown's getDamage/modifyDamage order; checked against the Smogon calculator)"""
    if mv.get("setup") or mv.get("status") or (mv["bp"] == 0 and not mv.get("lowkick")): return 0
    bp = mv["bp"]; t = mtype(att, mv, field)
    if mv.get("spout"): bp = max(1, mv["bp"] * att["hp"] // att["maxhp"])
    if mv.get("lowkick"): bp = lowkick_bp(dfn["weight"])
    if mv.get("acro") and att["item"] in (None, "consumed"): bp = 110
    ef = mv["expforce"] and field["terrain"] == "psychic" and grounded(att)
    if ef: bp = 120
    if mv.get("terrainpulse") and t != mv["t"]: bp = 100
    phys = mv["c"] == "p"
    if mv.get("bodypress"): A = stage_stat(att["st"][2], att["stg"]["def"])        # Body Press uses Defense
    else: A = stage_stat(att["st"][1] if phys else att["st"][3], att["stg"]["atk" if phys else "spa"])
    D = dfn["st"][2] if phys else dfn["st"][4]
    if not mv.get("ignore_def"): D = stage_stat(D, dfn["stg"]["def" if phys else "spd"])
    if not phys and field["weather"] == "sand" and "Rock" in dfn["types"]: D = _mod(D, 6144)
    e = eff(t, dfn["types"])
    if t == "Ground" and "levitate" in dfn["ab"]: e = 0
    if t == "Fire" and "flash_fire" in dfn["ab"]: e = 0
    if e == 0: return 0
    f = mv["f"]; spread = False                 # the move's factor = spread (a damage modifier) x -ate / Tough Claws (power)
    for sf, bpm in ((0.75, 1.0), (0.9, 1.2)):
        if abs(f - sf) < 1e-9: spread, f = True, bpm
    bpmods = []
    if abs(f - 1.2) < 1e-9: bpmods.append(4915)
    elif abs(f - 1.3) < 1e-9: bpmods.append(5325)
    elif abs(f - 1.0) > 1e-9: raise ValueError(f"unknown move factor {mv['n']} {mv['f']}")
    if TYPE_ITEM.get(att["item"]) == t: bpmods.append(4915)
    if mv.get("pulse") and "mega_launcher" in att["ab"]: bpmods.append(6144)
    if field["terrain"] == "grassy" and grounded(att) and t == "Grass": bpmods.append(5325)
    if field["terrain"] == "psychic" and grounded(att) and t == "Psychic": bpmods.append(5325)
    if mv["eq"] and field["terrain"] == "grassy" and grounded(dfn): bpmods.append(2048)
    if t == "Fairy" and ("fairy_aura" in att["ab"] or "fairy_aura" in dfn["ab"]): bpmods.append(5448)
    if mv.get("knockoff") and removable(dfn): bpmods.append(6144)
    if bpmods: bp = max(1, _mod(bp, _chain(bpmods)))
    base = (22 * bp * A) // D // 50 + 2
    if spread or ef: base = _mod(base, 3072)
    if field["weather"] == "rain" and t in ("Water", "Fire"): base = _mod(base, 6144 if t == "Water" else 2048)
    if field["weather"] == "sun" and t in ("Fire", "Water"): base = _mod(base, 6144 if t == "Fire" else 2048)
    r = 85 if roll == "min" else 100 if roll == "max" else int(round(roll * 100))     # a float = one specific roll
    base = base * r // 100
    if t in att["types"]: base = _mod(base, 8192 if "adaptability" in att["ab"] else 6144)   # STAB, from typing
    if e >= 1: base = int(base * e)
    else:
        x = e
        while x < 1 - 1e-9: base //= 2; x *= 2
    fin = []
    if RESIST_BERRY.get(dfn["item"]) == t and e > 1 and not dfn["item_used"]: fin.append(2048)
    if att["item"] == "Life Orb": fin.append(5324)
    if dfn["glaive_vuln"]: fin.append(8192)
    if fin: base = _mod(base, _chain(fin))
    return max(1, base)

def usable(att, dfn, mv, field, turn, is_mine):
    if mv["first"] and att["out_turns"] > 0: return False
    if mv["needs_terrain"] and field["terrain"] is None: return False
    prio = effective_prio(att, mv, field)
    if prio > 0 and ("armor_tail" in dfn["ab"] or (field["terrain"] == "psychic" and grounded(dfn))): return False
    return True

def effective_prio(att, mv, field):
    if mv.get("grassy_prio"): return 1 if (field["terrain"] == "grassy" and grounded(att)) else 0
    return mv["pr"]

def choose(att, dfn, field, turn, is_mine):
    if att.get("recharging", 0) > 0: return None
    roll = "min" if is_mine else "max"
    if not is_mine and att.get("policy") == "setup" and not att.get("did_setup"):
        su = next((m for m in att["moves"] if m.get("setup")), None)
        if su: return su
    opts = [mv for mv in att["moves"] if usable(att, dfn, mv, field, turn, is_mine) and not mv.get("setup")]
    if att.get("policy") == "norecoil":
        clean = [o for o in opts if not o["rc"] or "rock_head" in att["ab"]]
        if any(damage(att, dfn, o, field, roll) > 0 for o in clean): opts = clean
    if att.get("policy") == "nodrop":          # no recoil or self-drop unless it knocks out now
        clean = [o for o in opts if not o["drop"] and (not o["rc"] or "rock_head" in att["ab"])]
        kills = any(damage(att, dfn, o, field, roll) >= dfn["hp"] for o in opts)
        if not kills and any(damage(att, dfn, o, field, roll) > 0 for o in clean): opts = clean
    if not opts: return None
    def hit(mv):
        if mv["charge"] and not att["charged"]: return 0
        return damage(att, dfn, mv, field, roll)
    # a priority move that finishes now ('prio' policy: that can finish on a good roll)
    prio_roll = "max" if (is_mine and att.get("policy") == "prio") else roll
    for mv in sorted(opts, key=lambda x: -effective_prio(att, x, field)):
        fin = (damage(att, dfn, mv, field, prio_roll) if not (mv["charge"] and not att["charged"]) else 0) >= dfn["hp"]
        if effective_prio(att, mv, field) > 0 and fin and not (dfn["item"] == "Focus Sash" and not dfn["item_used"] and dfn["hp"] == dfn["maxhp"]):
            return mv
    # first turn out: Fake Out (free chip, and they lose the turn) unless a faster knockout is already there
    fo = next((o for o in opts if o.get("flinch")), None)
    if fo and hit(fo) > 0:
        sash_up = dfn["item"] == "Focus Sash" and not dfn["item_used"] and dfn["hp"] == dfn["maxhp"]
        ko_now = any(hit(o) >= dfn["hp"] for o in opts if not o.get("flinch") and not o["charge"]) and ((speed(att) < speed(dfn)) if TR else (speed(att) > speed(dfn))) and not sash_up
        if not ko_now: return fo
    if att.get("policy") == "nocharge":
        opts = [o for o in opts if not o["charge"] or att["charged"]] or opts
    if att.get("policy") == "noglaive":
        opts = [o for o in opts if not o["glaive"]] or opts
    # charge move: fire if charged; otherwise charge unless something kills now
    for mv in opts:
        if mv["charge"]:
            if att["charged"]: return mv
            if not any(hit(o) >= dfn["hp"] for o in opts if not o["charge"]): return mv
    best = max((o for o in opts if not o["charge"] and not o["sucker"]), key=hit, default=None)
    sucker = next((o for o in opts if o["sucker"]), None)
    if best is None: return sucker
    return best

def apply_hit(att, dfn, mv, field, roll, log):
    if mv.get("setup"):
        for k, v in mv["setup"].items(): att["stg"][k] = min(6, att["stg"][k] + v)
        att["did_setup"] = True; log.append(f"{att['name']} {mv['n']}"); return
    if mv["charge"] and not att["charged"]:
        att["charged"] = True; att["stg"]["spa"] = min(6, att["stg"]["spa"] + 1)
        log.append(f"{att['name']} charges"); return
    if mv["charge"]: att["charged"] = False
    dmg = damage(att, dfn, mv, field, roll)
    was_full = dfn["hp"] == dfn["maxhp"]
    if RESIST_BERRY.get(dfn["item"]) == mv["t"] and eff(mv["t"], dfn["types"]) > 1 and not dfn["item_used"]:
        dfn["item_used"] = True
    if dfn["item"] == "Focus Sash" and not dfn["item_used"] and was_full and dmg >= dfn["hp"]:
        dmg = dfn["hp"] - 1; dfn["item_used"] = True
    dealt = min(dmg, dfn["hp"]); dfn["hp"] -= dealt
    if mv.get("para") and dealt > 0 and dfn["hp"] > 0 and not dfn.get("par") and "Electric" not in dfn["types"]:
        dfn["par"] = True; log.append(f"{dfn['name']} is paralysed")
    log.append(f"{att['name']} {mv['n']} -> {dealt} ({100*dealt/dfn['maxhp']:.0f}%)")
    if mv["dr"] and dealt > 0: att["hp"] = min(att["maxhp"], att["hp"] + js_round(dealt * mv["dr"]))   # drain rounds
    if mv["rc"] and dealt > 0 and "rock_head" not in att["ab"]:
        num, den = (33, 100) if abs(mv["rc"] - 1/3) < 1e-9 else (1, 2) if abs(mv["rc"] - 0.5) < 1e-9 else (None, None)
        assert num, mv["n"]
        att["hp"] -= max(1, js_round(dealt * num / den))                    # recoil: 33% (or 1/2), rounded
    if att["item"] == "Life Orb" and dealt > 0: att["hp"] -= math.floor(att["maxhp"] / 10)
    if dealt > 0 and mv.get("contact") and "rough_skin" in dfn["ab"]: att["hp"] -= att["maxhp"] // 8
    if dealt > 0 and dfn["hp"] > 0 and "stamina" in dfn["ab"]: dfn["stg"]["def"] = min(6, dfn["stg"]["def"] + 1)
    if dealt > 0 and dfn["hp"] > 0 and "thermal_exchange" in dfn["ab"] and mtype(att, mv, field) == "Fire":
        dfn["stg"]["atk"] = min(6, dfn["stg"]["atk"] + 1)
    if mv.get("tdrop") and dealt > 0 and dfn["hp"] > 0:
        for s2, v2 in mv["tdrop"].items():
            if "competitive" in dfn["ab"]: dfn["stg"]["spa"] = min(6, dfn["stg"]["spa"] + 2)
            dfn["stg"][s2] = max(-6, dfn["stg"][s2] + v2)
    for s, v in mv["drop"].items():
        if "contrary" in att["ab"]: v = -v
        att["stg"][s] = max(-6, min(6, att["stg"][s] + v))
    if mv["glaive"]: att["glaive_vuln"] = True
    if mv.get("recharge"): att["recharging"] = 2
    if mv["kills_terrain"]: field["terrain"] = None
    for p in (dfn, att): sitrus(p)
    if mv.get("knockoff") and dealt > 0 and dfn["hp"] > 0 and removable(dfn): dfn["item"] = "knocked"

def sitrus(p):
    if p["item"] == "Sitrus" and not p["item_used"] and 0 < p["hp"] <= p["maxhp"] // 2:
        p["hp"] += p["maxhp"] // 4; p["item_used"] = True

def end_of_turn(ps, field):
    for p in ps:
        if p["hp"] <= 0: continue
        if field["weather"] == "sand" and not set(p["types"]) & {"Rock","Ground","Steel"}: p["hp"] -= p["maxhp"] // 16
        if p["hp"] > 0 and field["terrain"] == "grassy" and grounded(p): p["hp"] = min(p["maxhp"], p["hp"] + p["maxhp"] // 16)
        if p["hp"] > 0 and p["item"] == "Leftovers": p["hp"] = min(p["maxhp"], p["hp"] + p["maxhp"] // 16)
        sitrus(p)

def entry(p, foe, field, mode_mine_first=False):
    lead = field.get("mode") != "switch"            # both already out: the Intimidates met before any Mega Evolution
    if "trace_lead" in p["ab"] and lead and "intimidate" in foe["ab"]:          # Trace copies your Intimidate and fires it back
        foe["stg"]["atk"] = max(-6, foe["stg"]["atk"] - 1) if "defiant" not in foe["ab"] else min(6, foe["stg"]["atk"] + 1)
    if "intimidate" in p["ab"]:
        if "clear_body_lead" in foe["ab"] and lead: pass                       # Clear Body: the drop never lands
        elif "mirror_armor" in foe["ab"]: p["stg"]["atk"] = max(-6, p["stg"]["atk"] - 1)   # bounced back
        elif "defiant" in foe["ab"]: foe["stg"]["atk"] = min(6, foe["stg"]["atk"] + 1)   # -1 then +2
        elif "contrary" in foe["ab"] and field.get("mode") == "switch": foe["stg"]["atk"] = min(6, foe["stg"]["atk"] + 1)   # already Mega
        elif "competitive" in foe["ab"]:
            foe["stg"]["atk"] = max(-6, foe["stg"]["atk"] - 1); foe["stg"]["spa"] = min(6, foe["stg"]["spa"] + 2)
        else: foe["stg"]["atk"] = max(-6, foe["stg"]["atk"] - 1)
    if p["item"] == "Grassy Seed" and field["terrain"] == "grassy" and not p["item_used"]:
        p["stg"]["def"] += 1; p["item_used"] = True; p["seeded"] = True; p["item"] = "consumed"

def speed(p):
    s = stage_stat(p["st"][5], p["stg"]["spe"])
    if "unburden" in p["ab"] and p["seeded"]: s *= 2
    if p["item"] == "Choice Scarf": s = s * 3 // 2
    if p.get("par"): s //= 2
    return s

def duel(mine_name, foe_name, spread, mode, roll_me="min", roll_them="max", policy="greedy", mpolicy="greedy"):
    md = MINE[mine_name]
    me = make(mine_name, md["types"], md["st"], md["item"], md["ab"], md["moves"], WEIGHT.get(mine_name, 50))
    me["policy"] = mpolicy
    t, b, nat, sps, item, u = F[foe_name]
    st = stats(b, nat, spread)
    if foe_name in SPEED_EST: st[5] = max(st[5], SPEED_EST[foe_name])
    them = make(foe_name, t, st, item, TABIL.get(foe_name, set()), TM[foe_name], WEIGHT.get(foe_name, 50))
    them["policy"] = policy
    field = init_field(mine_name, foe_name, mode)
    log = []
    if mode == "switch":
        entry(them, me, field)                         # their Intimidate hit your partner, not you
        me["stg"]["atk"] = 0
        entry(me, them, field)
        them["out_turns"] = 1
        if md.get("entry_st"): me["st"] = list(md["entry_st"])      # a Mega switches in unevolved
        mv = choose(them, me, field, 0, False)
        if mv: apply_hit(them, me, mv, field, roll_them, log)
        me["st"] = list(md["st"])
        if me["hp"] <= 0: return ("loss", 0, log)
        end_of_turn([me, them], field)
    else:
        entry(me, them, field); entry(them, me, field)
    for turn in range(1, 9):
        a = choose(me, them, field, turn, True); d = choose(them, me, field, turn, False)
        pa = effective_prio(me, a, field) if a else -9
        pd = effective_prio(them, d, field) if d else -9
        me_first = goes_first(me, them, pa, pd, roll_me == "max")
        order = [(me, them, a, roll_me), (them, me, d, roll_them)]
        if not me_first: order.reverse()
        flinched = False
        for i, (x, y, mv, roll) in enumerate(order):
            if x["hp"] <= 0 or y["hp"] <= 0 or mv is None: continue
            if i == 1 and flinched: log.append(f"{x['name']} flinches"); continue
            if x.get("par") and roll == "min": log.append(f"{x['name']} is fully paralysed"); continue
            if mv["sucker"]:
                other = order[1 - i][2]
                if i == 1 or other is None or other.get("setup") or other.get("status") or (other["charge"] and not order[1 - i][0]["charged"]):
                    log.append(f"{x['name']} Sucker Punch fails"); continue
            x["glaive_vuln"] = False
            hp0 = y["hp"]
            apply_hit(x, y, mv, field, roll, log)
            if mv.get("flinch") and i == 0 and y["hp"] < hp0: flinched = True
            if y["hp"] <= 0 or x["hp"] <= 0: break
        for p in (me, them):
            p["out_turns"] += 1
            if p.get("recharging", 0) > 0: p["recharging"] -= 1
        if them["hp"] <= 0 and me["hp"] <= 0:
            return ("trade", turn, log)
        if them["hp"] <= 0: return ("win", turn, log)
        if me["hp"] <= 0: return ("loss", turn, log)
        end_of_turn([me, them], field)
        if them["hp"] <= 0: return ("win", turn, log)
        if me["hp"] <= 0: return ("loss", turn, log)
    return ("stall", 8, log)

RANK = {"loss": 0, "stall": 1, "trade": 2, "win": 3}
def goodness(r): return (RANK[r[0]], -r[1] if r[0] in ("win", "trade") else r[1])
def worst(mine, foe, mode, roll_me="min", roll_them="max"):
    """their best line (spread x policy) against your best reply"""
    tp = ["greedy", "norecoil"] + (["setup"] if any(m.get("setup") for m in TM[foe]) else [])
    res = []
    for sp in F[foe][3]:
        for p in tp:
            res.append(max((duel(mine, foe, sp, mode, roll_me, roll_them, p, mp) for mp in ("greedy", "norecoil")), key=goodness))
    return min(res, key=goodness)

def first_hits(mine, foe):
    """their best hit on you as you switch in (max roll), and your best hit on them (range), at their worst spread"""
    t, b, nat, sps, item, u = F[foe]
    md = MINE[mine]
    worst_in = (0, "", 0); worst_out = None
    for sp in sps:
        st = stats(b, nat, sp)
        me = make(mine, md["types"], md["st"], md["item"], md["ab"], md["moves"], WEIGHT.get(mine, 50))
        them = make(foe, t, st, item, TABIL.get(foe, set()), TM[foe], WEIGHT.get(foe, 50))
        field = init_field(mine, foe, "switch")
        entry(them, me, field); me["stg"]["atk"] = 0; entry(me, them, field)
        if md.get("entry_st"): me["st"] = list(md["entry_st"])      # their hit lands before your Mega Evolution
        for mv in them["moves"]:
            if mv.get("setup") or mv["first"] or (mv["needs_terrain"] and not field["terrain"]): continue
            if mv["charge"]: them["stg"]["spa"] += 1          # show what it does when it fires
            d = damage(them, me, mv, field, "max"); p = 100 * d / me["maxhp"]
            if mv["charge"]: them["stg"]["spa"] -= 1
            if p > worst_in[0]: worst_in = (p, mv["n"], eff(mv["t"], me["types"]))
        me["st"] = list(md["st"]); best = None
        for mv in me["moves"]:
            lo = damage(me, them, mv, field, "min"); hi = damage(me, them, mv, field, "max")
            if best is None or hi > best[2]: best = (mv["n"], lo, hi, them["maxhp"])
        if worst_out is None or best[2] / best[3] < worst_out[2] / worst_out[3]: worst_out = best
    return worst_in, worst_out

def classify(mine, foe):
    sw = worst(mine, foe, "switch"); fd = worst(mine, foe, "field")
    fd_best = worst(mine, foe, "field", "max", "min")
    win = lambda r: r[0] in ("win", "trade")
    wi, wo = first_hits(mine, foe)
    if win(sw): v = "counter"
    elif win(fd): v = "check"
    elif wi[0] <= 34 or sw[0] == "stall": v = "wall"
    else: v = "loses"
    return dict(v=v, sw=sw[:2], fd=fd[:2], fd_best=fd_best[0], inn=wi, out=wo)

if __name__ == "__main__":
    import sys
    pairs = [("Kingambit","M-Metagross"),("Salamence","Rillaboom"),("Gholdengo","Sneasler"),
             ("Salamence","Volcarona"),("Gholdengo","Volcarona"),("Sneasler","Gholdengo")]
    for m, f in pairs:
        c = classify(m, f)
        print(f"{m:11s} vs {f:12s} -> {c['v']:8s} switch:{c['sw']} field:{c['fd']}  takes {c['inn'][0]:.0f}% ({c['inn'][1]})  deals {c['out'][0]} {100*c['out'][1]/c['out'][3]:.0f}-{100*c['out'][2]/c['out'][3]:.0f}%")
