//! Stats and damage, ported from Showdown's Champions mod (sim/battle-actions.js getDamage + mods/champions modifyDamage).
//! Integer arithmetic follows Showdown exactly: trunc, modify() = trunc((trunc(v*m) + 2047) / 4096), chainModify rounding.
use crate::data::{Data, Move};

pub fn tr(x: f64) -> i64 { x.trunc() as i64 }
/// Showdown modify(value, numerator/denominator): 4096-based, rounds half down
pub fn modify(value: i64, num: i64, den: i64) -> i64 {
    let m = tr(num as f64 * 4096.0 / den as f64);
    tr((tr(value as f64 * m as f64) + 2048 - 1) as f64 / 4096.0)
}
/// chainModify: previous (4096-based) x next, rounded
pub fn chain(prev: i64, num: i64, den: i64) -> i64 { let next = tr(num as f64 * 4096.0 / den as f64); (prev * next + 2048) >> 12 }
fn apply_chain(value: i64, m4096: i64) -> i64 { if m4096 == 4096 { value } else { tr((tr(value as f64 * m4096 as f64) + 2047) as f64 / 4096.0) } }

#[derive(Clone, Debug, Default)]
pub struct Mon {
    pub species: String, pub item: String, pub ability: String, pub nature: String,
    pub sp: [i64; 6], pub boosts: [i64; 5], pub hp: i64, pub maxhp: i64, pub status: String,
}
pub const STATS: [&str; 6] = ["hp", "atk", "def", "spa", "spd", "spe"];

pub fn stat(d: &Data, species: &str, sp: &[i64; 6], nature: &str, i: usize) -> i64 {
    let s = &d.species[species]; let name = STATS[i]; let base = s.stats.get(name);
    if i == 0 { return base + sp[0] + 75; }
    let mut v = base + sp[i] + 20; let n = d.nature(nature);
    if n.plus.as_deref() == Some(name) { v = tr(((v * 110) % 65536) as f64 / 100.0); }
    else if n.minus.as_deref() == Some(name) { v = tr(((v * 90) % 65536) as f64 / 100.0); }
    v
}

#[derive(Clone, Debug, Default)]
pub struct Field { pub weather: String, pub terrain: String, pub screens: Vec<String>, pub spread: bool, pub helping: bool }

fn types<'a>(d: &'a Data, m: &Mon) -> &'a Vec<String> { &d.species[&m.species].types }
fn has_type(d: &Data, m: &Mon, t: &str) -> bool { types(d, m).iter().any(|x| x == t) }
pub fn grounded(d: &Data, m: &Mon) -> bool { !has_type(d, m, "Flying") && m.ability != "levitate" && m.item != "airballoon" }
fn weight_hg(d: &Data, m: &Mon) -> i64 { (d.species[&m.species].weightkg * 10.0).round() as i64 }

/// the move as it is after the type/move hooks run (useMoveInner): its type, base power, and flags we track
pub struct Active { pub mtype: String, pub bp: i64, pub type_changer: bool, pub sheer_force: bool, pub mv: Move }

pub fn prepare(d: &Data, a: &Mon, f: &Field, id: &str) -> Active {
    let mv = d.moves[id].clone(); let mut t = mv.mtype.clone(); let mut bp = mv.base_power;
    // the move's own ModifyType / ModifyMove
    match id {
        "weatherball" => { let w = match f.weather.as_str() { "sunnyday" => "Fire", "raindance" => "Water", "sandstorm" => "Rock", "snowscape" => "Ice", _ => "" };
                           if !w.is_empty() { t = w.into(); bp *= 2; } }
        "terrainpulse" => if grounded(d, a) { let x = match f.terrain.as_str() { "electricterrain" => "Electric", "grassyterrain" => "Grass", "mistyterrain" => "Fairy", "psychicterrain" => "Psychic", _ => "" };
                           if !x.is_empty() { t = x.into(); bp *= 2; } },
        _ => {}
    }
    // ability ModifyType (-ate abilities; Liquid Voice)
    let mut type_changer = false;
    let ate = match a.ability.as_str() { "aerilate" => "Flying", "pixilate" => "Fairy", "refrigerate" => "Ice", "galvanize" => "Electric", "dragonize" => "Dragon", _ => "" };
    let no_mod = ["judgment", "multiattack", "naturalgift", "revelationdance", "technoblast", "terrainpulse", "weatherball"];
    if !ate.is_empty() && t == "Normal" && !no_mod.contains(&id) { t = ate.into(); type_changer = true; }
    if a.ability == "liquidvoice" && mv.flags.contains_key("sound") { t = "Water".into(); }
    let sheer_force = a.ability == "sheerforce" && (mv.secondary.is_some() || mv.secondaries.is_some());
    Active { mtype: t, bp, type_changer, sheer_force, mv }
}

/// type effectiveness exponent; None = immune
pub fn effectiveness(d: &Data, act: &Active, def: &Mon, atk_ability: &str) -> Option<i64> {
    if act.mtype == "Ground" && !grounded(d, def) { return None; }
    let scrappy = ["scrappy", "mindseye"].contains(&atk_ability) && (act.mtype == "Normal" || act.mtype == "Fighting"); let mut e = 0;
    for ty in types(d, def) {
        match d.eff1(&act.mtype, ty) { None => { if !(scrappy && ty == "Ghost") { return None; } } Some(x) => { e += x; } }
        if act.mv.id == "freezedry" && ty == "Water" { e += 1 - d.eff1(&act.mtype, ty).unwrap_or(0); }
    }
    Some(e)
}

fn boosted(stat: i64, boost: i64) -> i64 {
    let t = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]; let b = boost.clamp(-6, 6);
    if b >= 0 { (stat as f64 * t[b as usize]).floor() as i64 } else { (stat as f64 / t[(-b) as usize]).floor() as i64 }
}
fn bi(s: &str) -> usize { match s { "atk" => 0, "def" => 1, "spa" => 2, "spd" => 3, _ => 4 } }

/// one handler in an event: (priority, effect-order tiebreak, multiplier num/den); `direct` = returns this.modify(...) right away
struct H { prio: f64, sub: i64, num: i64, den: i64, direct: bool }
fn run(value: i64, mut hs: Vec<H>) -> i64 {
    hs.sort_by(|a, b| b.prio.partial_cmp(&a.prio).unwrap().then(a.sub.cmp(&b.sub)));
    let mut v = value; let mut m = 4096;
    for h in hs { if h.direct { v = modify(v, h.num, h.den); } else { m = chain(m, h.num, h.den); } }
    apply_chain(v, m)
}

/// damage for one random roll (0..15) without/with a critical hit; None = immune
pub fn damage(d: &Data, a: &Mon, def: &Mon, id: &str, f: &Field, roll: i64, crit: bool, astats: &[i64; 6], dstats: &[i64; 6]) -> Option<i64> {
    let act = prepare(d, a, f, id); let mv = &act.mv;
    let crit = crit && !["shellarmor", "battlearmor"].contains(&def.ability.as_str());
    let eff = effectiveness(d, &act, def, &a.ability)?;
    // fixed damage (damageCallback / damage: 'level'), after the immunity check
    match id { "superfang" | "ruination" => return Some((def.hp / 2).max(1)), "nightshade" | "seismictoss" => return Some(50), _ => {} }
    // Cloud Nine / Air Lock: weather has no effect
    let f = &{ let mut g = f.clone(); if ["cloudnine", "airlock"].contains(&a.ability.as_str()) || ["cloudnine", "airlock"].contains(&def.ability.as_str()) { g.weather = String::new(); } g };
    let phys = mv.category == "Physical";
    // base power (callbacks, then the BasePower event)
    let mut bp = act.bp;
    match id {
        "eruption" | "waterspout" => bp = (mv.base_power as f64 * a.hp as f64 / a.maxhp as f64) as i64,
        "lowkick" | "grassknot" => { let w = weight_hg(d, def); bp = if w >= 2000 { 120 } else if w >= 1000 { 100 } else if w >= 500 { 80 } else if w >= 250 { 60 } else if w >= 100 { 40 } else { 20 }; }
        "heavyslam" | "heatcrash" => { let (w, u) = (weight_hg(d, def), weight_hg(d, a)); bp = if u >= w * 5 { 120 } else if u >= w * 4 { 100 } else if u >= w * 3 { 80 } else if u >= w * 2 { 60 } else { 40 }; }
        "acrobatics" => if a.item.is_empty() { bp *= 2 },
        "lastrespects" => bp = 50,
        "payback" => bp = 50,
        "powertrip" | "storedpower" => bp = mv.base_power + 20 * a.boosts.iter().filter(|&&b| b > 0).sum::<i64>(),
        "ragefist" => bp = 50,
        "hardpress" => { let h = tr(def.hp as f64 * 4096.0 / def.maxhp as f64); let x = tr(tr(((100 * (100 * h)) + 2048 - 1) as f64 / 4096.0) as f64 / 100.0); bp = if x == 0 { 1 } else { x }; }
        _ => {}
    }
    if bp <= 0 { return None; }
    let mut hs = vec![];
    let ap = |hook: &str| d.prio("ability", &a.ability, hook); let ip = |hook: &str| d.prio("item", &a.item, hook);
    match a.ability.as_str() {
        "technician" => if bp <= 60 { hs.push(H { prio: 30.0, sub: 1, num: 3, den: 2, direct: false }) },
        "aerilate" | "pixilate" | "refrigerate" | "galvanize" | "dragonize" => if act.type_changer { hs.push(H { prio: 23.0, sub: 1, num: 4915, den: 4096, direct: false }) },
        "toughclaws" => if mv.flags.contains_key("contact") { hs.push(H { prio: 21.0, sub: 1, num: 5325, den: 4096, direct: false }) },
        "sheerforce" => if act.sheer_force { hs.push(H { prio: 21.0, sub: 1, num: 5325, den: 4096, direct: false }) },
        "ironfist" => if mv.flags.contains_key("punch") { hs.push(H { prio: 23.0, sub: 1, num: 4915, den: 4096, direct: false }) },
        "sharpness" => if mv.flags.contains_key("slicing") { hs.push(H { prio: 19.0, sub: 1, num: 3, den: 2, direct: false }) },
        "megalauncher" => if mv.flags.contains_key("pulse") { hs.push(H { prio: 19.0, sub: 1, num: 3, den: 2, direct: false }) },
        "strongjaw" => if mv.flags.contains_key("bite") { hs.push(H { prio: ap("onBasePower"), sub: 1, num: 3, den: 2, direct: false }) },
        "reckless" => if mv.recoil.is_some() || mv.has_crash { hs.push(H { prio: 23.0, sub: 1, num: 4915, den: 4096, direct: false }) },
        "sandforce" => if f.weather == "sandstorm" && ["Rock", "Ground", "Steel"].contains(&act.mtype.as_str()) { hs.push(H { prio: 21.0, sub: 1, num: 5325, den: 4096, direct: false }) },
        "punkrock" => if mv.flags.contains_key("sound") { hs.push(H { prio: 7.0, sub: 1, num: 5325, den: 4096, direct: false }) },
        _ => {}
    }
    if act.mtype == "Fairy" && (a.ability == "fairyaura" || def.ability == "fairyaura") { hs.push(H { prio: 20.0, sub: 1, num: 5448, den: 4096, direct: false }); }
    let type_item = match a.item.as_str() { "miracleseed" => "Grass", "fairyfeather" => "Fairy", "mysticwater" => "Water", "blackglasses" => "Dark", "charcoal" => "Fire",
        "sharpbeak" => "Flying", "twistedspoon" => "Psychic", "nevermeltice" => "Ice", "magnet" => "Electric", "blackbelt" => "Fighting", "dragonfang" => "Dragon",
        "spelltag" => "Ghost", "silkscarf" => "Normal", "softsand" => "Ground", "hardstone" => "Rock", "metalcoat" => "Steel", "poisonbarb" => "Poison", "silverpowder" => "Bug", _ => "" };
    if !type_item.is_empty() && act.mtype == type_item { hs.push(H { prio: ip("onBasePower").max(15.0), sub: 2, num: 4915, den: 4096, direct: false }); }
    if f.helping { hs.push(H { prio: 10.0, sub: 3, num: 3, den: 2, direct: false }); }
    match f.terrain.as_str() {
        "psychicterrain" if act.mtype == "Psychic" && grounded(d, a) => hs.push(H { prio: 6.0, sub: 4, num: 5325, den: 4096, direct: false }),
        "electricterrain" if act.mtype == "Electric" && grounded(d, a) => hs.push(H { prio: 6.0, sub: 4, num: 5325, den: 4096, direct: false }),
        "grassyterrain" => {
            if ["earthquake", "bulldoze", "magnitude"].contains(&id) && grounded(d, def) { hs.push(H { prio: 6.0, sub: 4, num: 1, den: 2, direct: false }); }
            else if act.mtype == "Grass" && grounded(d, a) { hs.push(H { prio: 6.0, sub: 4, num: 5325, den: 4096, direct: false }); }
        }
        "mistyterrain" if act.mtype == "Dragon" && grounded(d, def) => hs.push(H { prio: 6.0, sub: 4, num: 1, den: 2, direct: false }),
        _ => {}
    }
    match id {
        "expandingforce" if f.terrain == "psychicterrain" && grounded(d, a) => hs.push(H { prio: 0.0, sub: 0, num: 3, den: 2, direct: false }),
        "knockoff" => { let mega_stone = d.items.contains_key(&def.item) && def.item.ends_with("ite") || def.item.ends_with("itex") || def.item.ends_with("itey") || def.item.ends_with("itez");
                        if !def.item.is_empty() && !mega_stone { hs.push(H { prio: 0.0, sub: 0, num: 3, den: 2, direct: false }); } }
        "facade" if !a.status.is_empty() && a.status != "slp" => hs.push(H { prio: 0.0, sub: 0, num: 2, den: 1, direct: false }),
        "solarbeam" | "solarblade" if ["raindance", "sandstorm", "snowscape"].contains(&f.weather.as_str()) => hs.push(H { prio: 0.0, sub: 0, num: 1, den: 2, direct: false }),
        "barbbarrage" if def.status == "psn" || def.status == "tox" => hs.push(H { prio: 0.0, sub: 0, num: 2, den: 1, direct: false }),
        _ => {}
    }
    bp = run(bp, hs).max(1);
    // attack and defence
    let (mut ast, dst) = (mv.override_off.clone().unwrap_or(if phys { "atk".into() } else { "spa".into() }), mv.override_def.clone().unwrap_or(if phys { "def".into() } else { "spd".into() }));
    let attacker_is_target = id == "foulplay";
    let src = if attacker_is_target { def } else { a };
    let srcstats = if attacker_is_target { dstats } else { astats };
    let mut ab = src.boosts[bi(&ast)]; let mut db = def.boosts[bi(&dst)];
    if crit { if ab < 0 { ab = 0; } if db > 0 { db = 0; } }
    if mv.ignore_defensive { db = 0; }
    let mut atk = boosted(srcstats[1 + bi(&ast)], ab); let mut dfn = boosted(dstats[1 + bi(&dst)], db);
    ast = if phys { "atk".into() } else { "spa".into() };
    // ModifyAtk / ModifySpA
    let mut hs = vec![];
    let hook = if ast == "atk" { "onModifyAtk" } else { "onModifySpA" };
    let pinch = |t: &str| act.mtype == t && a.hp * 3 <= a.maxhp;
    match a.ability.as_str() {
        "hugepower" | "purepower" if ast == "atk" => hs.push(H { prio: 5.0, sub: 1, num: 2, den: 1, direct: false }),
        "blaze" if pinch("Fire") => hs.push(H { prio: 5.0, sub: 1, num: 3, den: 2, direct: false }),
        "torrent" if pinch("Water") => hs.push(H { prio: 5.0, sub: 1, num: 3, den: 2, direct: false }),
        "overgrow" if pinch("Grass") => hs.push(H { prio: 5.0, sub: 1, num: 3, den: 2, direct: false }),
        "swarm" if pinch("Bug") => hs.push(H { prio: 5.0, sub: 1, num: 3, den: 2, direct: false }),
        "guts" if ast == "atk" && !a.status.is_empty() => hs.push(H { prio: 5.0, sub: 1, num: 3, den: 2, direct: false }),
        "solarpower" if ast == "spa" && f.weather == "sunnyday" => hs.push(H { prio: 5.0, sub: 1, num: 3, den: 2, direct: false }),
        "firemane" if act.mtype == "Fire" => hs.push(H { prio: 5.0, sub: 1, num: 3, den: 2, direct: false }),
        "waterbubble" if act.mtype == "Water" => hs.push(H { prio: 0.0, sub: 1, num: 2, den: 1, direct: false }),
        _ => {}
    }
    match a.item.as_str() {
        "choiceband" if ast == "atk" => hs.push(H { prio: d.prio("item", "choiceband", hook), sub: 2, num: 3, den: 2, direct: false }),
        "choicespecs" if ast == "spa" => hs.push(H { prio: d.prio("item", "choicespecs", hook), sub: 2, num: 3, den: 2, direct: false }),
        _ => {}
    }
    match def.ability.as_str() {
        "thickfat" if act.mtype == "Ice" || act.mtype == "Fire" => hs.push(H { prio: if ast == "atk" { 6.0 } else { 5.0 }, sub: 3, num: 1, den: 2, direct: false }),
        "heatproof" if act.mtype == "Fire" => hs.push(H { prio: if ast == "atk" { 6.0 } else { 5.0 }, sub: 3, num: 1, den: 2, direct: false }),
        "waterbubble" if act.mtype == "Fire" => hs.push(H { prio: 5.0, sub: 3, num: 1, den: 2, direct: false }),
        _ => {}
    }
    atk = run(atk, hs);
    // ModifyDef / ModifySpD
    let mut hs = vec![];
    if dst == "spd" && f.weather == "sandstorm" && has_type(d, def, "Rock") { hs.push(H { prio: 10.0, sub: 0, num: 3, den: 2, direct: true }); }
    if dst == "def" && f.weather == "snowscape" && has_type(d, def, "Ice") { hs.push(H { prio: 10.0, sub: 0, num: 3, den: 2, direct: true }); }
    match def.ability.as_str() {
        "furcoat" if dst == "def" => hs.push(H { prio: 6.0, sub: 1, num: 2, den: 1, direct: false }),
        "marvelscale" if dst == "def" && !def.status.is_empty() => hs.push(H { prio: 6.0, sub: 1, num: 3, den: 2, direct: false }),
        _ => {}
    }
    if def.item == "assaultvest" && dst == "spd" { hs.push(H { prio: d.prio("item", "assaultvest", "onModifySpD"), sub: 2, num: 3, den: 2, direct: false }); }
    if def.item == "eviolite" { hs.push(H { prio: 2.0, sub: 2, num: 3, den: 2, direct: false }); }
    dfn = run(dfn, hs);
    // base damage
    let base = tr(tr(tr(tr(2.0 * 50.0 / 5.0 + 2.0) as f64 * bp as f64 * atk as f64) as f64 / dfn as f64) as f64 / 50.0);
    // modifyDamage (Champions)
    let mut dmg = base + 2;
    if f.spread { dmg = modify(dmg, 3, 4); }
    let wx = match (f.weather.as_str(), act.mtype.as_str()) { ("sunnyday", "Fire") | ("raindance", "Water") => Some((3, 2)), ("sunnyday", "Water") | ("raindance", "Fire") => Some((1, 2)), _ => None };
    let wx = if id == "hydrosteam" && f.weather == "sunnyday" { Some((3, 2)) } else { wx };
    if let Some((n, de)) = wx { dmg = apply_chain(dmg, chain(4096, n, de)); }
    if crit { dmg = tr(dmg as f64 * 1.5); }
    dmg = tr(tr(dmg as f64 * (100 - roll) as f64) as f64 / 100.0);
    if has_type(d, a, &act.mtype) { dmg = modify(dmg, if a.ability == "adaptability" { 2 } else { 3 }, if a.ability == "adaptability" { 1 } else { 2 }); }
    if eff > 0 { for _ in 0..eff { dmg *= 2; } } else if eff < 0 { for _ in 0..(-eff) { dmg = tr(dmg as f64 / 2.0); } }
    if a.status == "brn" && phys && a.ability != "guts" { dmg = modify(dmg, 1, 2); }
    // ModifyDamage: attacker items/abilities, target abilities/berries, screens
    let mut hs = vec![];
    if a.item == "lifeorb" { hs.push(H { prio: 0.0, sub: 1, num: 5324, den: 4096, direct: false }); }
    if a.item == "expertbelt" && eff > 0 { hs.push(H { prio: 0.0, sub: 1, num: 4915, den: 4096, direct: false }); }
    if a.ability == "sniper" && crit { hs.push(H { prio: 0.0, sub: 1, num: 3, den: 2, direct: false }); }
    if a.ability == "tintedlens" && eff < 0 { hs.push(H { prio: 0.0, sub: 1, num: 2, den: 1, direct: false }); }
    match def.ability.as_str() {
        "multiscale" | "shadowshield" if def.hp >= def.maxhp => hs.push(H { prio: 0.0, sub: 2, num: 1, den: 2, direct: false }),
        "filter" | "solidrock" | "prismarmor" if eff > 0 => hs.push(H { prio: 0.0, sub: 2, num: 3, den: 4, direct: false }),
        "punkrock" if mv.flags.contains_key("sound") => hs.push(H { prio: 0.0, sub: 2, num: 1, den: 2, direct: false }),
        "fluffy" => { if mv.flags.contains_key("contact") { hs.push(H { prio: 0.0, sub: 2, num: 1, den: 2, direct: false }); } if act.mtype == "Fire" { hs.push(H { prio: 0.0, sub: 2, num: 2, den: 1, direct: false }); } }
        "icescales" if !phys => hs.push(H { prio: 0.0, sub: 2, num: 1, den: 2, direct: false }),
        _ => {}
    }
    let berry = match def.item.as_str() { "chopleberry" => "Fighting", "colburberry" => "Dark", "occaberry" => "Fire", "passhoberry" => "Water", "cobaberry" => "Flying",
        "kasibberry" => "Ghost", "roseliberry" => "Fairy", "habanberry" => "Dragon", "kebiaberry" => "Poison", "tangaberry" => "Bug", "babiriberry" => "Steel",
        "chartiberry" => "Rock", "yacheberry" => "Ice", "shucaberry" => "Ground", "wacanberry" => "Electric", "rindoberry" => "Grass", "payapaberry" => "Psychic", _ => "" };
    if !berry.is_empty() && act.mtype == berry && eff > 0 { hs.push(H { prio: 0.0, sub: 3, num: 1, den: 2, direct: false }); }
    if def.item == "chilanberry" && act.mtype == "Normal" { hs.push(H { prio: 0.0, sub: 3, num: 1, den: 2, direct: false }); }
    if !crit && a.ability != "infiltrator" {
        let has = |s: &str| f.screens.iter().any(|x| x == s);
        let screened = (phys && has("reflect")) || (!phys && has("lightscreen"));
        let veil = has("auroraveil") && !screened;
        if screened || veil { hs.push(H { prio: 0.0, sub: 4, num: 2732, den: 4096, direct: false }); }
    }
    dmg = run(dmg, hs);
    let out = dmg % 65536;
    Some(if out == 0 { 1 } else { out })
}
