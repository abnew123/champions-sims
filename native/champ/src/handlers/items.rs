//! Item handlers (data/items.ts). Same argument conventions as abilities.rs.
use super::Reg;
use crate::battle::*;
use crate::dex::*;
use crate::h;
use crate::state::*;

fn item_type(i: &str) -> &'static str {
    match i {
        "miracleseed" => "Grass", "mysticwater" => "Water", "blackglasses" => "Dark", "charcoal" => "Fire", "fairyfeather" => "Fairy", "sharpbeak" => "Flying",
        "twistedspoon" => "Psychic", "nevermeltice" => "Ice", "magnet" => "Electric", "blackbelt" => "Fighting", "dragonfang" => "Dragon", "spelltag" => "Ghost",
        "silkscarf" => "Normal", "softsand" => "Ground", "hardstone" => "Rock", "metalcoat" => "Steel", "poisonbarb" => "Poison", "silverpowder" => "Bug",
        _ => "",
    }
}
fn berry_type(i: &str) -> &'static str {
    match i {
        "chopleberry" => "Fighting", "colburberry" => "Dark", "occaberry" => "Fire", "passhoberry" => "Water", "cobaberry" => "Flying", "kasibberry" => "Ghost",
        "roseliberry" => "Fairy", "habanberry" => "Dragon", "kebiaberry" => "Poison", "tangaberry" => "Bug", "babiriberry" => "Steel", "chartiberry" => "Rock",
        "rindoberry" => "Grass", "wacanberry" => "Electric", "yacheberry" => "Ice", "shucaberry" => "Ground", "payapaberry" => "Psychic", "chilanberry" => "Normal",
        _ => "",
    }
}
fn type_boost(b: &mut Battle, a: &mut HArgs) -> RV { let ty = item_type(b.effect.unwrap().id); if b.am(a.am()).mtype == ty { return b.cm(4915.0, 4096.0); } RV::Undef }
fn resist_berry(b: &mut Battle, a: &mut HArgs) -> RV {
    let ty = berry_type(b.effect.unwrap().id); let (t, am) = (a.s(), a.am());
    let sl = b.slot_name(t);
    if b.am(am).mtype == ty && b.amm(am).hd(sl).type_mod > 0 {
        if b.has_vol(t, "substitute") && !b.am(am).flag("bypasssub") && !b.am(am).infiltrates { return RV::Undef; }
        if b.eat_item(t, false, None, None) { return b.cm(0.5, 1.0); }
    }
    RV::Undef
}
fn noop(_b: &mut Battle, _a: &mut HArgs) -> RV { RV::Undef }
/// mega stones: can't be removed from a pokemon that can use them
fn mega_take(b: &mut Battle, a: &mut HArgs) -> RV {
    let holder = a.t(); let item = b.effect.unwrap().id;
    let ms = b.dex.items[item].raw.get("megaStone").cloned().unwrap_or(serde_json::Value::Null);
    let Some(o) = ms.as_object() else { return RV::B(true) };
    let bs = b.p(holder).base_species; let bsd = &b.dex.species[bs];
    let base_name = b.dex.species.get(bsd.base_species).map(|s| s.name).unwrap_or(bsd.name);
    let blocked = o.contains_key(base_name) || o.contains_key(bsd.name) || o.values().any(|v| v.as_str() == Some(bsd.name));
    RV::B(!blocked)
}
fn seed(b: &mut Battle, a: &mut HArgs, terrain: &str, start: bool) -> RV {
    let m = a.t();
    if (!start || !b.ignoring_item(m)) && b.is_terrain(terrain) { b.use_item(m, None, None); }
    RV::Undef
}
fn white_herb(b: &mut Battle, m: MonRef) { if b.p(m).boosts.iter().any(|x| *x < 0) { b.use_item(m, None, None); } }

pub fn register(r: &mut Reg) {
    for (i, _) in [("miracleseed", 0), ("mysticwater", 0), ("blackglasses", 0), ("charcoal", 0), ("fairyfeather", 0), ("sharpbeak", 0), ("twistedspoon", 0),
                   ("nevermeltice", 0), ("magnet", 0), ("blackbelt", 0), ("dragonfang", 0), ("spelltag", 0), ("silkscarf", 0), ("softsand", 0)] {
        r.insert((Kind::Item, id(i), id("onBasePower")), type_boost as HFn);
    }
    for i in ["chopleberry", "colburberry", "occaberry", "passhoberry", "cobaberry", "kasibberry", "roseliberry", "habanberry", "kebiaberry", "tangaberry", "babiriberry", "chartiberry"] {
        r.insert((Kind::Item, id(i), id("onSourceModifyDamage")), resist_berry as HFn);
        r.insert((Kind::Item, id(i), id("onEat")), noop as HFn);
    }
    // every item with a megaStone table gets the same onTakeItem
    let megas = ["salamencite", "raichunitey", "raichunitex", "floettite", "golisopite", "charizarditey", "charizarditex", "garchompitez", "garchompite", "staraptite",
                 "gardevoirite", "tyranitarite", "gengarite", "froslassite", "metagrossite", "delphoxite", "lucarionitez", "lucarionite", "swampertite", "dragoninite",
                 "baxcalibrite", "glimmoranite", "aerodactylite", "cameruptite", "blastoisinite", "absolitez", "absolite", "blazikenite", "mawilite", "scovillainite",
                 "lopunnite", "pyroarite", "alakazite", "meganiumite", "meowsticite", "venusaurite", "scraftinite", "kangaskhanite", "crabominite", "starminite",
                 "gyaradosite", "sceptilite", "manectite", "aggronite", "dragalgite", "scizorite", "steelixite", "excadrite", "chandelurite", "feraligite", "greninjite",
                 "hawluchanite", "drampanite", "chesnaughtite", "slowbronite", "banettite", "ampharosite", "skarmorite", "victreebelite", "clefablite", "emboarite",
                 "chimechite", "falinksite", "malamarite", "barbaracite", "dragalgite", "eelektrossite", "beedrillite", "pidgeotite", "audinite", "houndoominite",
                 "heracronite", "pinsirite", "sablenite", "altarianite", "medichamite", "abomasite", "glalitite", "latiasite", "latiosite", "galladite", "diancite"];
    for i in megas { r.insert((Kind::Item, id(i), id("onTakeItem")), mega_take as HFn); }

    h!(r, Item, "normalgem", "onSourceTryPrimaryHit", |b, a| {
        let (t, s, am) = (a.t(), a.s(), a.am());
        if t == s || b.am(am).category == "Status" || b.am(am).flag("pledgecombo") { return RV::Undef; }
        if b.am(am).mtype == "Normal" && b.use_item(s, None, None) { b.add_volatile(s, "gem", None, None); }
        RV::Undef });
    h!(r, Item, "focussash", "onDamage", |b, a| {
        let t = a.t(); let p = b.p(t);
        if p.hp == p.maxhp && a.n() >= p.hp as f64 && b.eff_is(a.src_eff, EType::Move) { if b.use_item(t, None, None) { return RV::N((b.p(t).hp - 1) as f64); } }
        RV::Undef });
    h!(r, Item, "sitrusberry", "onUpdate", |b, a| { let m = a.t(); if b.p(m).hp as f64 <= b.p(m).maxhp as f64 / 2.0 { b.eat_item(m, false, None, None); } RV::Undef });
    h!(r, Item, "sitrusberry", "onTryEatItem", |b, a| {
        let m = a.t(); let e = b.effect; let d = b.p(m).base_maxhp as f64 / 4.0;
        if !b.run_event("TryHeal", Tgt::Mon(m), None, e, RV::N(d), false, false).truthy() { return RV::B(false); } RV::Undef });
    h!(r, Item, "sitrusberry", "onEat", |b, a| { let m = a.t(); let d = b.p(m).base_maxhp as f64 / 4.0; b.heal(d, None, None, None); RV::Undef });
    h!(r, Item, "lumberry", "onAfterSetStatus", |b, a| { let m = a.t(); b.eat_item(m, false, None, None); RV::Undef });
    h!(r, Item, "lumberry", "onUpdate", |b, a| { let m = a.t(); if !b.p(m).status.is_empty() || b.has_vol(m, "confusion") { b.eat_item(m, false, None, None); } RV::Undef });
    h!(r, Item, "lumberry", "onEat", |b, a| { let m = a.t(); b.cure_status(m); b.remove_volatile(m, "confusion"); RV::Undef });
    h!(r, Item, "lifeorb", "onModifyDamage", |b, a| { b.cm(5324.0, 4096.0) });
    h!(r, Item, "lifeorb", "onAfterMoveSecondarySelf", |b, a| {
        let s = a.t(); let am = a.am();
        if Some(s) != a.source && b.am(am).category != "Status" && !b.p(s).force_switch_flag {
            let d = b.p(s).base_maxhp as f64 / 10.0; b.damage(d, Some(s), Some(s), Some(Eff::new(Kind::Item, id("lifeorb"))), false);
        }
        RV::Undef });
    h!(r, Item, "expertbelt", "onModifyDamage", |b, a| { let (t, am) = (a.s(), a.am()); let sl = b.slot_name(t); if b.amm(am).hd(sl).type_mod > 0 { return b.cm(4915.0, 4096.0); } RV::Undef });
    h!(r, Item, "leftovers", "onResidual", |b, a| { let m = a.t(); let d = b.p(m).base_maxhp as f64 / 16.0; b.heal(d, None, None, None); RV::Undef });
    h!(r, Item, "choicescarf", "onStart", |b, a| { let m = a.t(); b.remove_volatile(m, "choicelock"); RV::Undef });
    h!(r, Item, "choicescarf", "onModifyMove", |b, a| { let m = a.t(); b.add_volatile(m, "choicelock", None, None); RV::Undef });
    h!(r, Item, "choicescarf", "onModifySpe", |b, a| { b.cm(1.5, 1.0) });
    h!(r, Item, "grassyseed", "onStart", |b, a| { seed(b, a, "grassyterrain", true) });
    h!(r, Item, "grassyseed", "onTerrainChange", |b, a| { seed(b, a, "grassyterrain", false) });
    h!(r, Item, "psychicseed", "onStart", |b, a| { seed(b, a, "psychicterrain", true) });
    h!(r, Item, "psychicseed", "onTerrainChange", |b, a| { seed(b, a, "psychicterrain", false) });
    h!(r, Item, "electricseed", "onStart", |b, a| { seed(b, a, "electricterrain", true) });
    h!(r, Item, "electricseed", "onTerrainChange", |b, a| { seed(b, a, "electricterrain", false) });
    h!(r, Item, "whiteherb", "onStart", |b, a| { let m = b.holder(); white_herb(b, m); RV::Undef });
    h!(r, Item, "whiteherb", "onAnySwitchIn", |b, a| { let m = b.holder(); white_herb(b, m); RV::Undef });
    h!(r, Item, "whiteherb", "onAnyAfterMega", |b, a| { let m = b.holder(); white_herb(b, m); RV::Undef });
    h!(r, Item, "whiteherb", "onAnyAfterMove", |b, a| { let m = b.holder(); white_herb(b, m); RV::Undef });
    h!(r, Item, "whiteherb", "onResidual", |b, a| { let m = a.t(); white_herb(b, m); RV::Undef });
    h!(r, Item, "whiteherb", "onUse", |b, a| { let m = a.t(); for k in 0..7 { if b.p(m).boosts[k] < 0 { b.pm(m).boosts[k] = 0; } } RV::Undef });
    h!(r, Item, "mentalherb", "onUpdate", |b, a| {
        let m = a.t(); let conds = ["attract", "taunt", "encore", "torment", "disable", "healblock"];
        for c in conds { if b.has_vol(m, c) { if !b.use_item(m, None, None) { return RV::Undef; } for c2 in conds { b.remove_volatile(m, c2); } return RV::Undef; } }
        RV::Undef });
    h!(r, Item, "rockyhelmet", "onDamagingHit", |b, a| { let (t, s) = (a.t(), a.s()); if b.makes_contact(a.am(), s) { let d = b.p(s).base_maxhp as f64 / 6.0; b.damage(d, Some(s), Some(t), None, false); } RV::Undef });
    h!(r, Item, "ejectbutton", "onAfterMoveSecondary", |b, a| {
        let t = a.t(); let Some(s) = a.source else { return RV::Undef }; let am = a.am();
        if s != t && b.p(t).hp > 0 && b.am(am).category != "Status" && !b.am(am).flag("futuremove") {
            if b.can_switch(t.0) == 0 || b.p(t).force_switch_flag || b.p(t).being_called_back || b.is_sky_dropped(t) { return RV::Undef; }
            if b.p(t).volatiles.iter().any(|(k, _)| *k == "commanding" || *k == "commanded") { return RV::Undef; }
            if b.all_active().iter().any(|x| b.p(*x).switch_flag == Some("true")) { return RV::Undef; }
            b.pm(t).switch_flag = Some(id("true"));
            if !b.use_item(t, None, None) { b.pm(t).switch_flag = None; }
        }
        RV::Undef });
    h!(r, Item, "widelens", "onSourceModifyAccuracy", |b, a| { if let RV::N(_) = a.relay { return b.cm(4505.0, 4096.0); } RV::Undef });
    h!(r, Item, "brightpowder", "onModifyAccuracy", |b, a| { if let RV::N(_) = a.relay { return b.cm(3686.0, 4096.0); } RV::Undef });
    h!(r, Item, "scopelens", "onModifyCritRatio", |b, a| { RV::N(a.n() + 1.0) });
    h!(r, Item, "leek", "onModifyCritRatio", |b, a| {
        let m = a.t(); let bs = b.dex.species[b.p(m).base_species].base_species;
        if bs == "farfetchd" || bs == "sirfetchd" { return RV::N(a.n() + 2.0); } RV::Undef });
    h!(r, Item, "kingsrock", "onModifyMove", |b, a| {
        let am = a.am(); if b.am(am).category == "Status" { return RV::Undef; }
        let mut secs = b.am(am).secondaries.clone().unwrap_or_default();
        if secs.iter().any(|s| s.volatile_status == Some("flinch")) { return RV::Undef; }
        secs.push(HitEff { part: id(&format!("secondaries.{}", secs.len())), chance: Some(10), volatile_status: Some("flinch"), ..Default::default() });
        b.amm(am).secondaries = Some(secs); RV::Undef });
}
