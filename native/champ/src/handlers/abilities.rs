//! Ability handlers (data/abilities.ts). runEvent handler arguments are (relay, event target, event source, effect):
//!   ModifyAtk/SpA/BasePower/ModifyDamage/ModifySTAB (+Source/Any variants): target = attacker, source = defender
//!   TryHit / DamagingHit / Invulnerability / Accuracy: target = the hit pokemon, source = the user
//!   TryMove / PrepareHit / ModifyMove / ModifyType / ModifyPriority: target = the user, source = its target
//!   RedirectTarget: relay = current target, target = source = the user
use super::Reg;
use crate::battle::*;
use crate::dex::*;
use crate::h;
use crate::state::*;

impl Battle {
    pub fn try_trap(&mut self, m: MonRef, _hidden: bool) -> bool { if !self.run_status_immunity(m, "trapped", false) { return false; } self.pm(m).trapped = true; true }
}
fn mon_code(m: MonRef) -> f64 { (m.0 as f64) * 16.0 + m.1 as f64 + 1.0 }
fn code_mon(x: f64) -> MonRef { let c = x as i64 - 1; ((c / 16) as u8, (c % 16) as u8) }
fn boosts_of(rv: &RV) -> Boosts { if let RV::Boosts(b) = rv { b.clone() } else { vec![] } }
fn ate(b: &mut Battle, a: &HArgs, ty: Id) -> RV {
    let am = a.am(); let mv = b.am(am);
    let no = ["judgment", "multiattack", "naturalgift", "revelationdance", "technoblast", "terrainpulse", "weatherball"];
    if mv.mtype == "Normal" && !no.contains(&mv.id) && !(mv.is_z && mv.category != "Status") {
        let ab = b.effect.unwrap().id; let x = b.amm(am); x.mtype = ty; x.type_changer_boosted = Some(ab);
    }
    RV::Undef
}
fn ate_bp(b: &mut Battle, a: &HArgs) -> RV { let am = a.am(); if b.am(am).type_changer_boosted == b.effect.map(|e| e.id) { return b.cm(4915.0, 4096.0); } RV::Undef }
/// Intimidate-style "delete boost.atk" for Inner Focus / Oblivious / Scrappy / Own Tempo
fn block_intimidate(a: &HArgs) -> RV {
    let mut bo = boosts_of(&a.relay);
    if a.src_eff.map(|e| e.id) == Some("intimidate") && bo.iter().any(|(k, v)| *k == 0 && *v != 0) { bo.retain(|(k, _)| *k != 0); return RV::Boosts(bo); }
    RV::Undef
}
/// Defiant / Competitive
fn on_lowered(b: &mut Battle, a: &HArgs, stat: u8) -> RV {
    let t = a.t(); let Some(s) = a.source else { return RV::Undef };
    if b.is_ally(t, s) { return RV::Undef; }
    if boosts_of(&a.relay).iter().any(|(_, v)| *v < 0) { b.boost(vec![(stat, 2)], Some(t), Some(t), None, false, true); }
    RV::Undef
}
fn priority_block(b: &mut Battle, a: &HArgs) -> RV {
    // Armor Tail / Queenly Majesty onFoeTryMove(target=user, source=move target, move)
    let am = a.am(); let mv = b.am(am);
    if mv.target == "foeSide" || (mv.target == "all" && !["perishsong", "flowershield", "rototiller"].contains(&mv.id)) { return RV::Undef; }
    let holder = b.holder();
    let tgt_ally = a.source.map(|s| b.is_ally(s, holder)).unwrap_or(false);
    if (tgt_ally || mv.target == "all") && mv.priority > 0.1 {
        if b.logging {   // as Showdown: |cant|USER|ability: Armor Tail|MOVE|[of] HOLDER
            let ab = match b.p(holder).ability { "armortail" => "Armor Tail", "queenlymajesty" => "Queenly Majesty", "dazzling" => "Dazzling", x => x };
            let (u, h, mn) = (b.mon_name(a.t()), b.mon_name(holder), b.am(am).name); let abs = format!("ability: {}", ab); let of = format!("[of] {}", h);
            b.add(&["cant", &u, &abs, mn, &of]);
        }
        return RV::B(false);
    }
    RV::Undef
}
fn weather_spe(b: &mut Battle, a: &HArgs, ws: &[&str]) -> RV { let m = a.t(); let w = b.pokemon_effective_weather(m, None); if ws.contains(&w) { return b.cm(2.0, 1.0); } RV::Undef }
fn pinch(b: &mut Battle, a: &HArgs, ty: &str) -> RV {
    let att = a.t(); let am = a.am(); let p = b.p(att);
    if b.am(am).mtype == ty && p.hp as f64 <= p.maxhp as f64 / 3.0 { return b.cm(1.5, 1.0); } RV::Undef
}
fn set_type_once(b: &mut Battle, a: &HArgs, key: &str) -> RV {
    if b.es().has(key) { return RV::Undef; }
    let src = a.t(); let am = a.am(); let mv = b.am(am).clone();
    if mv.has_bounced || mv.flag("futuremove") || mv.source_effect == Some("snatch") { return RV::Undef; }
    let ty = mv.mtype;
    if !ty.is_empty() && ty != "???" && b.get_types(src).join(",") != ty {
        let p = b.pm(src); p.types = vec![ty]; p.added_type = "";
        b.es().set(key, SV::B(true));
    }
    RV::Undef
}
fn sun_weather_mod(b: &mut Battle, a: &HArgs) {
    let (att, def, am) = (a.t(), a.s(), a.am()); let mv = b.am(am).clone();
    if mv.id == "hydrosteam" && b.pokemon_effective_weather(att, None) == "sunnyday" { b.chain_modify(1.5, 1.0); return; }
    if b.pokemon_effective_weather(def, None) != "sunnyday" { return; }
    if mv.mtype == "Fire" { b.chain_modify(1.5, 1.0); } else if mv.mtype == "Water" { b.chain_modify(0.5, 1.0); }
}

pub fn register(r: &mut Reg) {
    // ---------- switch-in effects ----------
    h!(r, Ability, "intimidate", "onStart", |b, a| {
        let m = a.t();
        for t in b.adjacent_foes(m) { if !b.has_vol(t, "substitute") { b.boost(vec![(0, -1)], Some(t), Some(m), None, true, false); } }
        RV::Undef });
    h!(r, Ability, "grassysurge", "onStart", |b, a| { let m = a.t(); b.set_terrain("grassyterrain", Some(m), None); RV::Undef });
    h!(r, Ability, "psychicsurge", "onStart", |b, a| { let m = a.t(); b.set_terrain("psychicterrain", Some(m), None); RV::Undef });
    h!(r, Ability, "electricsurge", "onStart", |b, a| { let m = a.t(); b.set_terrain("electricterrain", Some(m), None); RV::Undef });
    h!(r, Ability, "drizzle", "onStart", |b, a| { let m = a.t(); b.set_weather("raindance", Some(m), None); RV::Undef });
    h!(r, Ability, "drought", "onStart", |b, a| { let m = a.t(); b.set_weather("sunnyday", Some(m), None); RV::Undef });
    h!(r, Ability, "sandstream", "onStart", |b, a| { let m = a.t(); b.set_weather("sandstorm", Some(m), None); RV::Undef });
    h!(r, Ability, "snowwarning", "onStart", |b, a| { let m = a.t(); b.set_weather("snowscape", Some(m), None); RV::Undef });
    h!(r, Ability, "hospitality", "onStart", |b, a| { let m = a.t(); for al in b.adjacent_allies(m) { let d = b.p(al).base_maxhp as f64 / 4.0; b.heal(d, Some(al), Some(m), None); } RV::Undef });
    h!(r, Ability, "fairyaura", "onStart", |b, a| { RV::Undef });
    h!(r, Ability, "moldbreaker", "onStart", |b, a| { RV::Undef });
    h!(r, Ability, "pressure", "onStart", |b, a| { RV::Undef });
    h!(r, Ability, "unnerve", "onStart", |b, a| { if b.es().has("unnerved") { return RV::Undef; } b.es().set("unnerved", SV::B(true)); RV::Undef });
    h!(r, Ability, "unnerve", "onEnd", |b, a| { b.es().set("unnerved", SV::B(false)); RV::Undef });
    h!(r, Ability, "unnerve", "onFoeTryEatItem", |b, a| { RV::B(!b.es().has("unnerved")) });
    h!(r, Ability, "cloudnine", "onStart", |b, a| { b.es().set("ending", SV::B(false)); let e = b.effect; b.each_event("WeatherChange", e); RV::Undef });
    h!(r, Ability, "cloudnine", "onSwitchIn", |b, a| { b.es().set("ending", SV::B(false)); let e = b.effect; b.each_event("WeatherChange", e); RV::Undef });
    h!(r, Ability, "cloudnine", "onEnd", |b, a| { b.es().set("ending", SV::B(true)); let e = b.effect; b.each_event("WeatherChange", e); RV::Undef });
    h!(r, Ability, "trace", "onStart", |b, a| {
        let m = a.t();
        let seek = !b.has_item(m, "abilityshield");
        b.es().set("seek", SV::B(seek));
        if seek { let e = b.effect.unwrap(); let st = b.effect_state; b.single_event("Update", e, Some(st), Tgt::Mon(m), None, None, RV::Undef); }
        RV::Undef });
    h!(r, Ability, "trace", "onUpdate", |b, a| {
        if !b.es().has("seek") { return RV::Undef; }
        let m = a.t();
        let poss: Vec<MonRef> = b.adjacent_foes(m).into_iter().filter(|t| !b.dex.eff(Kind::Ability, b.p(*t).ability).flag("notrace") && b.p(*t).ability != "noability").collect();
        if poss.is_empty() { return RV::Undef; }
        let t = poss[b.prng.sample_idx(poss.len())]; let ab = b.p(t).ability;
        b.set_ability(m, ab, Some(t), None, false); RV::Undef });
    // ---------- stat stages ----------
    h!(r, Ability, "defiant", "onAfterEachBoost", |b, a| { on_lowered(b, a, 0) });
    h!(r, Ability, "competitive", "onAfterEachBoost", |b, a| { on_lowered(b, a, 2) });
    h!(r, Ability, "contrary", "onChangeBoost", |b, a| { if a.src_eff.map(|e| e.id) == Some("zpower") { return RV::Undef; } RV::Boosts(boosts_of(&a.relay).into_iter().map(|(k, v)| (k, -v)).collect()) });
    h!(r, Ability, "clearbody", "onTryBoost", |b, a| {
        let t = a.t(); if a.source == Some(t) { return RV::Undef; }
        RV::Boosts(boosts_of(&a.relay).into_iter().filter(|(_, v)| *v >= 0).collect()) });
    h!(r, Ability, "hypercutter", "onTryBoost", |b, a| {
        let t = a.t(); if a.source == Some(t) { return RV::Undef; }
        RV::Boosts(boosts_of(&a.relay).into_iter().filter(|(k, v)| !(*k == 0 && *v < 0)).collect()) });
    h!(r, Ability, "innerfocus", "onTryBoost", |b, a| { block_intimidate(a) });
    h!(r, Ability, "oblivious", "onTryBoost", |b, a| { block_intimidate(a) });
    h!(r, Ability, "scrappy", "onTryBoost", |b, a| { block_intimidate(a) });
    h!(r, Ability, "mirrorarmor", "onTryBoost", |b, a| {
        let t = a.t(); let Some(s) = a.source else { return RV::Undef };
        if t == s || a.src_eff.map(|e| e.id) == Some("mirrorarmor") { return RV::Undef; }
        let mut bo = boosts_of(&a.relay); let mut keep = vec![];
        for (k, v) in bo.drain(..) {
            if v < 0 { if b.p(t).boosts[k as usize] == -6 { keep.push((k, v)); continue; }
                       if b.p(s).hp > 0 { b.boost(vec![(k, v)], Some(s), Some(t), None, true, false); } }
            else { keep.push((k, v)); }
        }
        RV::Boosts(keep) });
    h!(r, Ability, "unaware", "onAnyModifyBoost", |b, a| {
        let user = b.holder(); let pk = a.t(); if user == pk { return RV::Undef; }
        let mut bo = boosts_of(&a.relay);
        let mut zero = |bo: &mut Boosts, k: u8| { if let Some(e) = bo.iter_mut().find(|(x, _)| *x == k) { e.1 = 0; } else { bo.push((k, 0)); } };
        if Some(user) == b.active_pokemon && Some(pk) == b.active_target { zero(&mut bo, 1); zero(&mut bo, 3); zero(&mut bo, 6); }
        if Some(pk) == b.active_pokemon && Some(user) == b.active_target { zero(&mut bo, 0); zero(&mut bo, 1); zero(&mut bo, 2); zero(&mut bo, 5); }
        RV::Boosts(bo) });
    h!(r, Ability, "stamina", "onDamagingHit", |b, a| { b.boost(vec![(1, 1)], None, None, None, false, false); RV::Undef });
    h!(r, Ability, "weakarmor", "onDamagingHit", |b, a| { let t = a.t(); if b.am(a.am()).category == "Physical" { b.boost(vec![(1, -1), (4, 2)], Some(t), Some(t), None, false, false); } RV::Undef });
    h!(r, Ability, "thermalexchange", "onDamagingHit", |b, a| { if b.am(a.am()).mtype == "Fire" { b.boost(vec![(0, 1)], None, None, None, false, false); } RV::Undef });
    h!(r, Ability, "speedboost", "onResidual", |b, a| { let m = a.t(); if b.p(m).active_turns != 0 { b.boost(vec![(4, 1)], None, None, None, false, false); } RV::Undef });
    // ---------- type changes ----------
    h!(r, Ability, "aerilate", "onModifyType", |b, a| { ate(b, a, "Flying") });
    h!(r, Ability, "pixilate", "onModifyType", |b, a| { ate(b, a, "Fairy") });
    h!(r, Ability, "aerilate", "onBasePower", |b, a| { ate_bp(b, a) });
    h!(r, Ability, "pixilate", "onBasePower", |b, a| { ate_bp(b, a) });
    h!(r, Ability, "liquidvoice", "onModifyType", |b, a| { let am = a.am(); if b.am(am).flag("sound") { b.amm(am).mtype = "Water"; } RV::Undef });
    h!(r, Ability, "protean", "onPrepareHit", |b, a| { set_type_once(b, a, "protean") });
    h!(r, Ability, "libero", "onPrepareHit", |b, a| { set_type_once(b, a, "libero") });
    // ---------- power ----------
    h!(r, Ability, "toughclaws", "onBasePower", |b, a| { if b.am(a.am()).flag("contact") { return b.cm(5325.0, 4096.0); } RV::Undef });
    h!(r, Ability, "ironfist", "onBasePower", |b, a| { if b.am(a.am()).flag("punch") { return b.cm(4915.0, 4096.0); } RV::Undef });
    h!(r, Ability, "sharpness", "onBasePower", |b, a| { if b.am(a.am()).flag("slicing") { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Ability, "megalauncher", "onBasePower", |b, a| { if b.am(a.am()).flag("pulse") { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Ability, "punkrock", "onBasePower", |b, a| { if b.am(a.am()).flag("sound") { return b.cm(5325.0, 4096.0); } RV::Undef });
    h!(r, Ability, "punkrock", "onSourceModifyDamage", |b, a| { if b.am(a.am()).flag("sound") { return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Ability, "technician", "onBasePower", |b, a| { let m = b.event.as_ref().unwrap().modifier; if b.modify(a.n(), m) <= 60 { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Ability, "sheerforce", "onModifyMove", |b, a| {
        let am = a.am(); let id_ = b.am(am).id;
        if b.am(am).secondaries.is_some() && !b.dex.mv(id_).eff.b("hasSheerForceBoost") { let x = b.amm(am); x.secondaries = None; x.base.self_eff = None; x.has_sheer_force = true; }
        RV::Undef });
    h!(r, Ability, "sheerforce", "onBasePower", |b, a| { let am = a.am(); let id_ = b.am(am).id; if b.am(am).has_sheer_force || b.dex.mv(id_).eff.b("hasSheerForceBoost") { return b.cm(5325.0, 4096.0); } RV::Undef });
    h!(r, Ability, "sandforce", "onBasePower", |b, a| { if b.effective_weather() == "sandstorm" && ["Rock", "Ground", "Steel"].contains(&b.am(a.am()).mtype) { return b.cm(5325.0, 4096.0); } RV::Undef });
    h!(r, Ability, "sandforce", "onImmunity", |b, a| { if a.relay == RV::S(id("sandstorm")) { return RV::B(false); } RV::Undef });
    h!(r, Ability, "fairyaura", "onAnyBasePower", |b, a| {
        let (src, tgt, am) = (a.t(), a.s(), a.am()); let mv = b.am(am);
        if tgt == src || mv.category == "Status" || mv.mtype != "Fairy" { return RV::Undef; }
        let holder = b.holder();
        let cur = b.am(am).misc("auraBooster").map(code_mon);
        if !cur.map(|c| b.has_ability(c, "fairyaura")).unwrap_or(false) { b.amm(am).set_misc("auraBooster", mon_code(holder)); }
        if b.am(am).misc("auraBooster").map(code_mon) != Some(holder) { return RV::Undef; }
        b.cm(5448.0, 4096.0) });
    h!(r, Ability, "hugepower", "onModifyAtk", |b, a| { b.cm(2.0, 1.0) });
    h!(r, Ability, "adaptability", "onModifySTAB", |b, a| {
        let s = a.t(); let am = a.am(); let mt = b.am(am).mtype;
        if b.am(am).force_stab || b.has_type(s, mt) { return RV::N(if a.n() == 2.0 { 2.25 } else { 2.0 }); } RV::Undef });
    h!(r, Ability, "blaze", "onModifyAtk", |b, a| { pinch(b, a, "Fire") });
    h!(r, Ability, "blaze", "onModifySpA", |b, a| { pinch(b, a, "Fire") });
    h!(r, Ability, "torrent", "onModifyAtk", |b, a| { pinch(b, a, "Water") });
    h!(r, Ability, "torrent", "onModifySpA", |b, a| { pinch(b, a, "Water") });
    h!(r, Ability, "overgrow", "onModifyAtk", |b, a| { pinch(b, a, "Grass") });
    h!(r, Ability, "overgrow", "onModifySpA", |b, a| { pinch(b, a, "Grass") });
    h!(r, Ability, "firemane", "onModifyAtk", |b, a| { if b.am(a.am()).mtype == "Fire" { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Ability, "firemane", "onModifySpA", |b, a| { if b.am(a.am()).mtype == "Fire" { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Ability, "waterbubble", "onModifyAtk", |b, a| { if b.am(a.am()).mtype == "Water" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Ability, "waterbubble", "onModifySpA", |b, a| { if b.am(a.am()).mtype == "Water" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Ability, "waterbubble", "onSourceModifyAtk", |b, a| { if b.am(a.am()).mtype == "Fire" { return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Ability, "waterbubble", "onSourceModifySpA", |b, a| { if b.am(a.am()).mtype == "Fire" { return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Ability, "waterbubble", "onUpdate", |b, a| { let m = a.t(); if b.p(m).status == "brn" { b.cure_status(m); } RV::Undef });
    h!(r, Ability, "waterbubble", "onSetStatus", |b, a| { if a.relay != RV::S(id("brn")) { return RV::Undef; } RV::B(false) });
    h!(r, Ability, "thermalexchange", "onUpdate", |b, a| { let m = a.t(); if b.p(m).status == "brn" { b.cure_status(m); } RV::Undef });
    h!(r, Ability, "thermalexchange", "onSetStatus", |b, a| { if a.relay != RV::S(id("brn")) { return RV::Undef; } RV::B(false) });
    h!(r, Ability, "thickfat", "onSourceModifyAtk", |b, a| { let t = b.am(a.am()).mtype; if t == "Ice" || t == "Fire" { return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Ability, "thickfat", "onSourceModifySpA", |b, a| { let t = b.am(a.am()).mtype; if t == "Ice" || t == "Fire" { return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Ability, "sniper", "onModifyDamage", |b, a| { let (t, am) = (a.s(), a.am()); let sl = b.slot_name(t); if b.amm(am).hd(sl).crit { return b.cm(1.5, 1.0); } RV::Undef });
    // ---------- damage taken ----------
    h!(r, Ability, "multiscale", "onSourceModifyDamage", |b, a| { let t = a.s(); if b.p(t).hp >= b.p(t).maxhp { return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Ability, "filter", "onSourceModifyDamage", |b, a| { let (t, am) = (a.s(), a.am()); let sl = b.slot_name(t); if b.amm(am).hd(sl).type_mod > 0 { return b.cm(0.75, 1.0); } RV::Undef });
    h!(r, Ability, "friendguard", "onAnyModifyDamage", |b, a| { let t = a.s(); let h_ = b.holder(); if t != h_ && b.is_ally(t, h_) { return b.cm(0.75, 1.0); } RV::Undef });
    h!(r, Ability, "rockhead", "onDamage", |b, a| { if a.src_eff.map(|e| e.id) == Some("recoil") { if b.active_move.map(|x| b.am(x).id) != Some("struggle") { return RV::Null; } } RV::Undef });
    h!(r, Ability, "magicguard", "onDamage", |b, a| { if !b.eff_is(a.src_eff, EType::Move) { return RV::B(false); } RV::Undef });
    h!(r, Ability, "disguise", "onDamage", |b, a| { let t = a.t(); if b.eff_is(a.src_eff, EType::Move) && b.p(t).species == "mimikyu" { b.es().set("busted", SV::B(true)); return RV::N(0.0); } RV::Undef });
    h!(r, Ability, "disguise", "onCriticalHit", |b, a| {
        let t = a.t(); let am = a.am(); if b.p(t).species != "mimikyu" { return RV::Undef; }
        if b.has_vol(t, "substitute") && !b.am(am).flag("bypasssub") && !b.am(am).infiltrates { return RV::Undef; }
        if !b.run_immunity_move(t, am, false) { return RV::Undef; } RV::B(false) });
    // Unseen Fist, Champions (mods/champions: onHitProtect, 2026-10-13, v29): a contact move goes through Protect and its kin for a
    // quarter of the damage (the hit's bypassProtect, the same 0.25 as a Z-move through Protect)
    h!(r, Ability, "unseenfist", "onHitProtect", |b, a| {
        let am = a.am(); let Some(d) = a.source else { return RV::Undef };
        if b.am(am).flag("contact") { let slot = b.slot_name(d); b.amm(am).hd(slot).bypass_protect = true; return RV::B(false); }
        RV::Undef });
    h!(r, Ability, "disguise", "onEffectiveness", |b, a| {
        let t = a.t(); let am = a.am(); if b.am(am).category == "Status" || b.p(t).species != "mimikyu" { return RV::Undef; }
        if b.has_vol(t, "substitute") && !b.am(am).flag("bypasssub") && !b.am(am).infiltrates { return RV::Undef; }
        if !b.run_immunity_move(t, am, false) { return RV::Undef; } RV::N(0.0) });
    h!(r, Ability, "disguise", "onUpdate", |b, a| {
        let m = a.t(); if b.p(m).species == "mimikyu" && b.es().has("busted") {
            b.forme_change_permanent(m, id("mimikyubusted"), b.effect);
            // the effect is the species, as in Showdown (no onDamage): with none, the running Disguise was added to the Damage handlers
            // a second time and its tie with itself drew a shuffle (2026-10-12)
            b.damage(b.p(m).base_maxhp as f64 / 8.0, Some(m), Some(m), Some(Eff::new(Kind::Species, id("mimikyubusted"))), false);
        } RV::Undef });
    // ---------- immunities / absorbs ----------
    h!(r, Ability, "goodasgold", "onTryHit", |b, a| { let (t, s) = (a.t(), a.s()); if b.am(a.am()).category == "Status" && t != s { return RV::Null; } RV::Undef });
    h!(r, Ability, "soundproof", "onTryHit", |b, a| { let (t, s) = (a.t(), a.s()); if t != s && b.am(a.am()).flag("sound") { return RV::Null; } RV::Undef });
    h!(r, Ability, "soundproof", "onAllyTryHitSide", |b, a| { RV::Undef });
    h!(r, Ability, "bulletproof", "onTryHit", |b, a| { if b.am(a.am()).flag("bullet") { return RV::Null; } RV::Undef });
    h!(r, Ability, "flashfire", "onTryHit", |b, a| {
        let (t, s, am) = (a.t(), a.s(), a.am());
        if t != s && b.am(am).mtype == "Fire" { b.amm(am).accuracy = None; b.add_volatile(t, "flashfire", None, None); return RV::Null; } RV::Undef });
    h!(r, Ability, "flashfire", "onEnd", |b, a| { let m = a.t(); b.remove_volatile(m, "flashfire"); RV::Undef });
    h!(r, Ability, "voltabsorb", "onTryHit", |b, a| { let (t, s) = (a.t(), a.s()); if t != s && b.am(a.am()).mtype == "Electric" { let d = b.p(t).base_maxhp as f64 / 4.0; b.heal(d, None, None, None); return RV::Null; } RV::Undef });
    h!(r, Ability, "lightningrod", "onTryHit", |b, a| { let (t, s) = (a.t(), a.s()); if t != s && b.am(a.am()).mtype == "Electric" { b.boost(vec![(2, 1)], None, None, None, false, false); return RV::Null; } RV::Undef });
    h!(r, Ability, "lightningrod", "onAnyRedirectTarget", |b, a| {
        let src = a.t(); let am = a.am(); let mv = b.am(am);
        if mv.mtype != "Electric" || mv.flag("pledgecombo") { return RV::Undef; }
        let rt = if ["randomNormal", "adjacentFoe"].contains(&mv.target) { "normal" } else { mv.target };
        let h_ = b.holder();
        if b.valid_target(h_, src, rt) { if b.am(am).smart_target.unwrap_or(false) { b.amm(am).smart_target = Some(false); } return RV::M(h_); }
        RV::Undef });
    h!(r, Ability, "magicbounce", "onTryHit", |b, a| {
        let (t, s, am) = (a.t(), a.s(), a.am()); let mv = b.am(am);
        if t == s || mv.has_bounced || !mv.flag("reflectable") || b.is_semi_invulnerable(t) { return RV::Undef; }
        let mut nm = b.dex.active_move(mv.id); nm.has_bounced = true; nm.prankster_boosted = false; let ni = b.new_am(nm);
        b.use_move(ni, t, Some(s), None); RV::Null });
    h!(r, Ability, "magicbounce", "onAllyTryHitSide", |b, a| {
        let (t, s, am) = (a.t(), a.s(), a.am()); let mv = b.am(am);
        if b.is_ally(t, s) || mv.has_bounced || !mv.flag("reflectable") || b.is_semi_invulnerable(t) { return RV::Undef; }
        let mut nm = b.dex.active_move(mv.id); nm.has_bounced = true; nm.prankster_boosted = false; let ni = b.new_am(nm);
        let h_ = b.holder(); b.use_move(ni, h_, Some(s), None); b.amm(am).has_bounced = true; RV::Null });
    h!(r, Ability, "sandrush", "onImmunity", |b, a| { if a.relay == RV::S(id("sandstorm")) { return RV::B(false); } RV::Undef });
    h!(r, Ability, "oblivious", "onUpdate", |b, a| { let m = a.t(); if b.has_vol(m, "attract") { b.remove_volatile(m, "attract"); } if b.has_vol(m, "taunt") { b.remove_volatile(m, "taunt"); } RV::Undef });
    h!(r, Ability, "oblivious", "onImmunity", |b, a| { if a.relay == RV::S(id("attract")) { return RV::B(false); } RV::Undef });
    h!(r, Ability, "oblivious", "onTryHit", |b, a| { let mv = b.am(a.am()).id; if ["attract", "captivate", "taunt"].contains(&mv) { return RV::Null; } RV::Undef });
    h!(r, Ability, "innerfocus", "onTryAddVolatile", |b, a| { if a.relay == RV::S(id("flinch")) { return RV::Null; } RV::Undef });
    // ---------- priority / accuracy / targeting ----------
    h!(r, Ability, "prankster", "onModifyPriority", |b, a| { let am = a.am(); if b.am(am).category == "Status" { b.amm(am).prankster_boosted = true; return RV::N(a.n() + 1.0); } RV::Undef });
    h!(r, Ability, "galewings", "onModifyPriority", |b, a| { let m = a.t(); let am = a.am(); if b.am(am).mtype == "Flying" && b.p(m).hp == b.p(m).maxhp { return RV::N(a.n() + 1.0); } RV::Undef });
    h!(r, Ability, "armortail", "onFoeTryMove", |b, a| { priority_block(b, a) });
    h!(r, Ability, "queenlymajesty", "onFoeTryMove", |b, a| { priority_block(b, a) });
    h!(r, Ability, "noguard", "onAnyInvulnerability", |b, a| { let h_ = b.holder(); if a.src_eff.is_some() && (a.source == Some(h_) || a.target.mon() == Some(h_)) { return RV::N(0.0); } RV::Undef });
    h!(r, Ability, "noguard", "onAnyAccuracy", |b, a| { let h_ = b.holder(); if a.src_eff.is_some() && (a.source == Some(h_) || a.target.mon() == Some(h_)) { return RV::B(true); } a.relay.clone() });
    h!(r, Ability, "compoundeyes", "onSourceModifyAccuracy", |b, a| { if let RV::N(_) = a.relay { return b.cm(5325.0, 4096.0); } RV::Undef });
    h!(r, Ability, "moldbreaker", "onModifyMove", |b, a| { let am = a.am(); b.amm(am).ignore_ability = true; RV::Undef });
    h!(r, Ability, "infiltrator", "onModifyMove", |b, a| { let am = a.am(); b.amm(am).infiltrates = true; RV::Undef });
    h!(r, Ability, "stalwart", "onModifyMove", |b, a| { let am = a.am(); let t = b.am(am).target != "scripted"; b.amm(am).tracks_target = t; RV::Undef });
    h!(r, Ability, "scrappy", "onModifyMove", |b, a| {
        let am = a.am();
        match b.am(am).ignore_immunity.clone() {
            Some(IgnImm::All(true)) => {}
            Some(IgnImm::Types(mut v)) => { for t in ["Fighting", "Normal"] { if !v.contains(&t) { v.push(t); } } b.amm(am).ignore_immunity = Some(IgnImm::Types(v)); }
            _ => { b.amm(am).ignore_immunity = Some(IgnImm::Types(vec!["Fighting", "Normal"])); }
        }
        RV::Undef });
    h!(r, Ability, "parentalbond", "onPrepareHit", |b, a| {
        let am = a.am(); let mv = b.am(am);
        if mv.category == "Status" || mv.multihit.is_some() || mv.flag("noparentalbond") || mv.flag("charge") || mv.flag("futuremove") || mv.spread_hit || mv.is_z || mv.is_max { return RV::Undef; }
        let x = b.amm(am); x.multihit = Some((2, 2)); x.multihit_type = Some("parentalbond"); RV::Undef });
    h!(r, Ability, "parentalbond", "onSourceModifySecondaries", |b, a| { RV::Undef });
    h!(r, Ability, "stancechange", "onModifyMove", |b, a| {
        let m = a.t(); let am = a.am();
        if b.dex.species[b.p(m).species].base_species != "aegislash" || b.p(m).transformed { return RV::Undef; }
        let mv = b.am(am); if mv.category == "Status" && mv.id != "kingsshield" { return RV::Undef; }
        let tf = if mv.id == "kingsshield" { "aegislash" } else { "aegislashblade" };
        if b.p(m).species != tf { b.set_species(m, id(tf)); }
        RV::Undef });
    h!(r, Ability, "pressure", "onDeductPP", |b, a| { let (t, s) = (a.t(), a.s()); if b.is_ally(t, s) { return RV::Undef; } RV::N(1.0) });
    // ---------- contact / after-hit ----------
    h!(r, Ability, "roughskin", "onDamagingHit", |b, a| { let (t, s) = (a.t(), a.s()); if b.makes_contact(a.am(), s) { let d = b.p(s).base_maxhp as f64 / 8.0; b.damage(d, Some(s), Some(t), None, false); } RV::Undef });
    // 2026-10-09: ported for the sheet threads' card opponents (Garganacl, Cofagrigus, Pincurchin / Raichu Static, Froslass Snow Cloak)
    h!(r, Ability, "purifyingsalt", "onSetStatus", |b, a| { RV::B(false) });
    h!(r, Ability, "purifyingsalt", "onTryAddVolatile", |b, a| { if a.relay == RV::S(id("yawn")) { return RV::Null; } RV::Undef });
    h!(r, Ability, "purifyingsalt", "onSourceModifyAtk", |b, a| { if b.am(a.am()).mtype == "Ghost" { return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Ability, "purifyingsalt", "onSourceModifySpA", |b, a| { if b.am(a.am()).mtype == "Ghost" { return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Ability, "mummy", "onDamagingHit", |b, a| { let (t, s) = (a.t(), a.s()); let sab = b.p(s).ability;
        if b.dex.eff(Kind::Ability, sab).cantsuppress || sab == "mummy" { return RV::Undef; }
        if b.makes_contact(a.am(), s) { b.set_ability(s, "mummy", Some(t), None, false); } RV::Undef });
    h!(r, Ability, "static", "onDamagingHit", |b, a| { let (t, s) = (a.t(), a.s()); if b.makes_contact(a.am(), s) && b.rchance(3, 10) { b.try_set_status(s, "par", Some(t), None); } RV::Undef });
    h!(r, Ability, "snowcloak", "onImmunity", |b, a| { if a.relay == RV::S(id("hail")) { return RV::B(false); } RV::Undef });
    h!(r, Ability, "snowcloak", "onModifyAccuracy", |b, a| { if let RV::N(_) = a.relay { let w = b.effective_weather(); if w == "hail" || w == "snowscape" { return b.cm(3277.0, 4096.0); } } RV::Undef });
    h!(r, Ability, "owntempo", "onUpdate", |b, a| { let m = a.t(); if b.has_vol(m, "confusion") { b.remove_volatile(m, "confusion"); } RV::Undef });
    h!(r, Ability, "owntempo", "onTryAddVolatile", |b, a| { if a.relay == RV::S(id("confusion")) { return RV::Null; } RV::Undef });
    h!(r, Ability, "owntempo", "onHit", |b, a| { RV::Undef });
    h!(r, Ability, "owntempo", "onTryBoost", |b, a| { block_intimidate(a) });
    h!(r, Ability, "quickdraw", "onFractionalPriority", |b, a| { let m = a.t(); if b.am(a.am()).category != "Status" && b.rchance(3, 10) { let n = b.mon_name(m); b.add(&["-activate", &n, "ability: Quick Draw"]); return RV::N(0.1); } RV::Undef });
    h!(r, Ability, "surgesurfer", "onModifySpe", |b, a| { if b.is_terrain("electricterrain") { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Ability, "dryskin", "onTryHit", |b, a| { let t = a.t(); if a.source != Some(t) && b.am(a.am()).mtype == "Water" { let d = b.p(t).base_maxhp as f64 / 4.0; b.heal(d, None, None, None); return RV::Null; } RV::Undef });
    h!(r, Ability, "dryskin", "onSourceBasePower", |b, a| { if b.am(a.am()).mtype == "Fire" { return b.cm(1.25, 1.0); } RV::Undef });
    h!(r, Ability, "dryskin", "onWeather", |b, a| { let t = a.t(); let w = a.src_eff.map(|e| e.id).unwrap_or("");
        if b.pokemon_effective_weather(t, None) != w { return RV::Undef; }
        if w == "raindance" || w == "primordialsea" { let d = b.p(t).base_maxhp as f64 / 8.0; b.heal(d, None, None, None); }
        else if w == "sunnyday" || w == "desolateland" { let d = b.p(t).base_maxhp as f64 / 8.0; b.damage(d, Some(t), Some(t), None, false); } RV::Undef });
    h!(r, Ability, "zerotohero", "onSwitchOut", |b, a| { let m = a.t(); let bs = b.p(m).base_species; let base = b.dex.species.get(bs).map(|x| x.base_species).unwrap_or(bs);
        if to_id(base) != "palafin" || b.p(m).transformed { return RV::Undef; }
        if b.p(m).species != "palafinhero" { b.forme_change_permanent(m, "palafinhero", Some(Eff::new(Kind::Ability, id("zerotohero")))); } RV::Undef });
    h!(r, Ability, "zerotohero", "onSwitchIn", |b, a| { RV::Undef });
    // 2026-10-09, batch 3 (Eval bar's and TR sheet's lists)
    for ab in ["insomnia", "vitalspirit"] {
        h!(r, Ability, ab, "onUpdate", |b, a| { let m = a.t(); if b.p(m).status == "slp" { b.cure_status(m); } RV::Undef });
        h!(r, Ability, ab, "onSetStatus", |b, a| { if a.relay != RV::S(id("slp")) { return RV::Undef; } RV::B(false) });
        h!(r, Ability, ab, "onTryAddVolatile", |b, a| { if a.relay == RV::S(id("yawn")) { return RV::Null; } RV::Undef });
    }
    h!(r, Ability, "healer", "onResidual", |b, a| { let m = a.t(); let allies: Vec<MonRef> = b.adjacent_allies(m).into_iter().collect();
        for al in allies { if !b.p(al).status.is_empty() && b.rchance(1, 2) { let n = b.mon_name(m); b.add(&["-activate", &n, "ability: Healer"]); b.cure_status(al); } } RV::Undef });   // Champions: 1/2 (base game 3/10) (2026-10-12)
    h!(r, Ability, "gooey", "onDamagingHit", |b, a| { let (t, s) = (a.t(), a.s()); if b.makes_contact(a.am(), s) { b.boost(vec![(4, -1)], Some(s), Some(t), None, true, false); } RV::Undef });
    h!(r, Ability, "curiousmedicine", "onStart", |b, a| { let m = a.t(); let allies: Vec<MonRef> = b.adjacent_allies(m).into_iter().collect(); for al in allies { b.pm(al).boosts = [0; 7]; } RV::Undef });
    h!(r, Ability, "seedsower", "onDamagingHit", |b, a| { b.set_terrain("grassyterrain", None, None); RV::Undef });
    h!(r, Ability, "swarm", "onModifyAtk", |b, a| { pinch(b, a, "Bug") });
    h!(r, Ability, "swarm", "onModifySpA", |b, a| { pinch(b, a, "Bug") });
    h!(r, Ability, "electromorphosis", "onDamagingHit", |b, a| { let t = a.t(); b.add_volatile(t, "charge", None, None); RV::Undef });
    h!(r, Ability, "ripen", "onTryHeal", |b, a| { let Some(e) = a.src_eff else { return RV::Undef }; if e.kind == Kind::Item && b.dex.items.get(e.id).map(|i| i.raw.get("isBerry").and_then(|x| x.as_bool()).unwrap_or(false)).unwrap_or(false) { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Ability, "ripen", "onChangeBoost", |b, a| { let Some(e) = a.src_eff else { return RV::Undef };
        if e.kind == Kind::Item && b.dex.items.get(e.id).map(|i| i.raw.get("isBerry").and_then(|x| x.as_bool()).unwrap_or(false)).unwrap_or(false) {
            if let RV::Boosts(bs) = &a.relay { return RV::Boosts(bs.iter().map(|(k, v)| (*k, v * 2)).collect()); } } RV::Undef });
    h!(r, Ability, "ripen", "onSourceModifyDamage", |b, a| { let t = a.s(); if b.p(t).ability_state.has("berryWeaken") { b.pm(t).ability_state.set("berryWeaken", SV::B(false)); return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Ability, "ripen", "onTryEatItem", |b, a| { RV::Undef });
    h!(r, Ability, "ripen", "onEatItem", |b, a| { let m = a.t(); let item = match &a.relay { RV::S(i) => *i, _ => "" };
        let weaken = ["babiriberry", "chartiberry", "chilanberry", "chopleberry", "cobaberry", "colburberry", "habanberry", "kasibberry", "kebiaberry", "occaberry", "passhoberry", "payapaberry", "rindoberry", "roseliberry", "shucaberry", "tangaberry", "wacanberry", "yacheberry"].contains(&item);
        b.pm(m).ability_state.set("berryWeaken", SV::B(weaken)); RV::Undef });
    h!(r, Ability, "flamebody", "onDamagingHit", |b, a| { let (t, s) = (a.t(), a.s()); if b.makes_contact(a.am(), s) && b.rchance(3, 10) { b.try_set_status(s, "brn", Some(t), None); } RV::Undef });
    h!(r, Ability, "poisontouch", "onSourceDamagingHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if b.has_ability(t, "shielddust") || b.has_item(t, "covertcloak") { return RV::Undef; }
        if b.makes_contact(a.am(), t) && b.rchance(3, 10) { b.try_set_status(t, "psn", Some(s), None); }
        RV::Undef });
    h!(r, Ability, "spicyspray", "onDamagingHit", |b, a| { let (t, s) = (a.t(), a.s()); b.try_set_status(s, "brn", Some(t), None); RV::Undef });
    h!(r, Ability, "toxicdebris", "onDamagingHit", |b, a| {
        let (t, s) = (a.t(), a.s()); let side = if b.is_ally(s, t) { 1 - s.0 } else { s.0 };
        let layers = find(&b.sides[side as usize].side_conditions, "toxicspikes").map(|x| x.n("layers").unwrap_or(0.0));
        if b.am(a.am()).category == "Physical" && layers.map(|l| l < 2.0).unwrap_or(true) { b.add_side_condition(side, "toxicspikes", Some(t), None); }
        RV::Undef });
    h!(r, Ability, "solidrock", "onSourceModifyDamage", |b, a| { let (t, am) = (a.s(), a.am()); let sl = b.slot_name(t); if b.amm(am).hd(sl).type_mod > 0 { return b.cm(0.75, 1.0); } RV::Undef });
    h!(r, Ability, "sturdy", "onTryHit", |b, a| { if b.am(a.am()).ohko.is_some() { return RV::Null; } RV::Undef });
    h!(r, Ability, "sturdy", "onDamage", |b, a| { let t = a.t(); let p = b.p(t); if p.hp == p.maxhp && a.n() >= p.hp as f64 && b.eff_is(a.src_eff, EType::Move) { return RV::N((p.hp - 1) as f64); } RV::Undef });
    h!(r, Ability, "raindish", "onWeather", |b, a| { let t = a.t(); let Some(e) = a.src_eff else { return RV::Undef };
        if b.pokemon_effective_weather(t, None) != e.id { return RV::Undef; }
        if e.id == "raindance" || e.id == "primordialsea" { let d = b.p(t).base_maxhp as f64 / 16.0; b.heal(d, None, None, None); } RV::Undef });
    h!(r, Ability, "icebody", "onWeather", |b, a| { let t = a.t(); if let Some(e) = a.src_eff { if e.id == "hail" || e.id == "snowscape" { let d = b.p(t).base_maxhp as f64 / 16.0; b.heal(d, None, None, None); } } RV::Undef });
    h!(r, Ability, "icebody", "onImmunity", |b, a| { if a.relay == RV::S(id("hail")) { return RV::B(false); } RV::Undef });
    h!(r, Ability, "telepathy", "onTryHit", |b, a| { let (t, s) = (a.t(), a.s()); if t != s && b.is_ally(t, s) && b.am(a.am()).category != "Status" { return RV::Null; } RV::Undef });
    h!(r, Ability, "keeneye", "onTryBoost", |b, a| { let t = a.t(); if a.source == Some(t) { return RV::Undef; } RV::Boosts(boosts_of(&a.relay).into_iter().filter(|(k, v)| !(*k == 5 && *v < 0)).collect()) });
    h!(r, Ability, "keeneye", "onModifyMove", |b, a| { let am = a.am(); b.amm(am).ignore_evasion = true; RV::Undef });
    h!(r, Ability, "leafguard", "onSetStatus", |b, a| { let t = a.t(); let w = b.pokemon_effective_weather(t, None); if w == "sunnyday" || w == "desolateland" { return RV::B(false); } RV::Undef });
    h!(r, Ability, "leafguard", "onTryAddVolatile", |b, a| { let t = a.t(); let w = b.pokemon_effective_weather(t, None); if a.relay == RV::S(id("yawn")) && (w == "sunnyday" || w == "desolateland") { return RV::Null; } RV::Undef });
    h!(r, Ability, "guts", "onModifyAtk", |b, a| { let m = a.t(); if !b.p(m).status.is_empty() { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Ability, "furcoat", "onModifyDef", |b, a| { b.cm(2.0, 1.0) });
    h!(r, Ability, "heatproof", "onSourceModifyAtk", |b, a| { if b.am(a.am()).mtype == "Fire" { return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Ability, "heatproof", "onSourceModifySpA", |b, a| { if b.am(a.am()).mtype == "Fire" { return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Ability, "heatproof", "onDamage", |b, a| { if a.src_eff.map(|e| e.id) == Some("brn") { return RV::N(a.n() / 2.0); } RV::Undef });
    h!(r, Ability, "supremeoverlord", "onStart", |b, a| { let m = a.t(); let tf = b.sides[m.0 as usize].total_fainted; if tf != 0 { b.es().set("fallen", SV::N(tf.min(5) as f64)); } RV::Undef });
    h!(r, Ability, "supremeoverlord", "onEnd", |b, a| { RV::Undef });
    h!(r, Ability, "supremeoverlord", "onBasePower", |b, a| { let f = b.es().n("fallen").unwrap_or(0.0); if f != 0.0 { let pm = [4096.0, 4506.0, 4915.0, 5325.0, 5734.0, 6144.0]; return b.cm(pm[f as usize], 4096.0); } RV::Undef });
    h!(r, Ability, "wanderingspirit", "onDamagingHit", |b, a| { let (t, s) = (a.t(), a.s()); if b.makes_contact(a.am(), s) { b.unsupported("wanderingspirit skill swap".into()); } RV::Undef });
    h!(r, Ability, "synchronize", "onAfterSetStatus", |b, a| {
        let t = a.t(); let Some(s) = a.source else { return RV::Undef }; if s == t { return RV::Undef; }
        if a.src_eff.map(|e| e.id) == Some("toxicspikes") { return RV::Undef; }
        let st = if let RV::S(x) = a.relay { x } else { return RV::Undef }; if st == "slp" || st == "frz" { return RV::Undef; }
        b.try_set_status(s, st, Some(t), Some(Eff::new(Kind::Ability, id("synchronize")))); RV::Undef });
    h!(r, Ability, "moody", "onResidual", |b, a| {
        let m = a.t(); let mut bo: Boosts = vec![];
        let up: Vec<u8> = (0..5u8).filter(|k| b.p(m).boosts[*k as usize] < 6).collect();
        let r1 = if up.is_empty() { None } else { Some(up[b.prng.sample_idx(up.len())]) };
        if let Some(k) = r1 { bo.push((k, 2)); }
        let dn: Vec<u8> = (0..5u8).filter(|k| b.p(m).boosts[*k as usize] > -6 && Some(*k) != r1).collect();
        if !dn.is_empty() { let k = dn[b.prng.sample_idx(dn.len())]; bo.push((k, -1)); }
        bo.sort_by_key(|x| x.0);   // JS object keys keep insertion order of the boost table (atk..spe)
        b.boost(bo, Some(m), Some(m), None, false, false); RV::Undef });
    h!(r, Ability, "magician", "onAfterMoveSecondarySelf", |b, a| { b.unsupported("magician".into()); RV::Undef });
    h!(r, Ability, "pickpocket", "onAfterMoveSecondary", |b, a| {
        let t = a.t(); let Some(s) = a.source else { return RV::Undef }; let am = a.am();
        if s != t && b.am(am).flag("contact") {
            if !b.p(t).item.is_empty() || b.p(t).switch_flag.is_some() || b.p(t).force_switch_flag || b.p(s).switch_flag == Some("true") { return RV::Undef; }
            let Some(it) = b.take_item(s, Some(t)) else { return RV::Undef };
            if !b.set_item(t, it, None, None) { b.pm(s).item = it; }
        }
        RV::Undef });
    h!(r, Ability, "illusion", "onBeforeSwitchIn", |b, a| { RV::Undef });
    h!(r, Ability, "illusion", "onDamagingHit", |b, a| { RV::Undef });
    h!(r, Ability, "illusion", "onEnd", |b, a| { RV::Undef });
    h!(r, Ability, "illusion", "onFaint", |b, a| { RV::Undef });
    h!(r, Ability, "unburden", "onAfterUseItem", |b, a| { let m = a.t(); if Some(m) != b.es_mon() { return RV::Undef; } b.add_volatile(m, "unburden", None, None); RV::Undef });
    h!(r, Ability, "unburden", "onTakeItem", |b, a| { let m = a.t(); b.add_volatile(m, "unburden", None, None); RV::Undef });
    h!(r, Ability, "unburden", "onEnd", |b, a| { let m = a.t(); b.remove_volatile(m, "unburden"); RV::Undef });
    h!(r, Ability, "superluck", "onModifyCritRatio", |b, a| { RV::N(a.n() + 1.0) });
    h!(r, Ability, "naturalcure", "onSwitchOut", |b, a| { let m = a.t(); let st = b.p(m).status; if st.is_empty() || st == "fnt" { return RV::Undef; } if b.p(m).hp > 0 { b.set_status(m, "", None, None, false); } RV::Undef });
    h!(r, Ability, "regenerator", "onSwitchOut", |b, a| { let m = a.t(); let d = b.p(m).base_maxhp as f64 / 3.0; b.pokemon_heal(m, d); RV::Undef });
    // ---------- speed ----------
    h!(r, Ability, "swiftswim", "onModifySpe", |b, a| { weather_spe(b, a, &["raindance", "primordialsea"]) });
    h!(r, Ability, "chlorophyll", "onModifySpe", |b, a| { weather_spe(b, a, &["sunnyday", "desolateland"]) });
    h!(r, Ability, "sandrush", "onModifySpe", |b, a| { if b.effective_weather() == "sandstorm" { return b.cm(2.0, 1.0); } RV::Undef });
    // ---------- weather ----------
    h!(r, Ability, "shadowtag", "onFoeTrapPokemon", |b, a| { let m = a.t(); let h_ = b.holder(); if !b.has_ability(m, "shadowtag") && b.is_adjacent(m, h_) { b.try_trap(m, true); } RV::Undef });
    h!(r, Ability, "shadowtag", "onFoeMaybeTrapPokemon", |b, a| { let m = a.t(); let src = a.source.or(b.es_mon()); let Some(src) = src else { return RV::Undef };
        if !b.is_adjacent(m, src) { return RV::Undef; } if !b.has_ability(m, "shadowtag") { b.pm(m).maybe_trapped = true; } RV::Undef });
    h!(r, Ability, "damp", "onAnyTryMove", |b, a| { if a.src_eff.map(|e| ["explosion", "mindblown", "mistyexplosion", "selfdestruct"].contains(&e.id)).unwrap_or(false) { return RV::B(false); } RV::Undef });
    h!(r, Ability, "damp", "onAnyDamage", |b, a| { if a.src_eff.map(|e| e.id) == Some("aftermath") { return RV::B(false); } RV::Undef });
    h!(r, Ability, "emergencyexit", "onEmergencyExit", |b, a| { let t = a.t(); if b.can_switch(t.0) == 0 || b.p(t).force_switch_flag || b.p(t).switch_flag.is_some() { return RV::Undef; } b.pm(t).switch_flag = Some(id("true")); RV::Undef });
    h!(r, Ability, "flowerveil", "onAllyTryBoost", |b, a| {
        let t = a.t(); if (a.source.is_some() && a.source == Some(t)) || !b.has_type(t, "Grass") { return RV::Undef; }
        RV::Boosts(boosts_of(&a.relay).into_iter().filter(|(_, v)| *v >= 0).collect()) });
    h!(r, Ability, "flowerveil", "onAllySetStatus", |b, a| {
        let t = a.t(); if b.has_type(t, "Grass") && a.source.is_some() && a.source != Some(t) && a.src_eff.map(|e| e.id != "yawn").unwrap_or(false) { return RV::Null; } RV::Undef });
    h!(r, Ability, "flowerveil", "onAllyTryAddVolatile", |b, a| { let t = a.t(); if b.has_type(t, "Grass") && a.relay == RV::S(id("yawn")) { return RV::Null; } RV::Undef });
    h!(r, Ability, "cursedbody", "onDamagingHit", |b, a| {
        let (s, am) = (a.s(), a.am()); if b.has_vol(s, "disable") { return RV::Undef; }
        let mv = b.am(am); if !mv.is_max && !mv.flag("futuremove") && mv.id != "struggle" && b.rchance(3, 10) { let h_ = b.holder(); b.add_volatile(s, "disable", Some(h_), None); }
        RV::Undef });
    h!(r, Ability, "limber", "onUpdate", |b, a| { let m = a.t(); if b.p(m).status == "par" { b.cure_status(m); } RV::Undef });
    h!(r, Ability, "limber", "onSetStatus", |b, a| { if a.relay != RV::S(id("par")) { return RV::Undef; } RV::B(false) });
    h!(r, Ability, "magmaarmor", "onUpdate", |b, a| { let m = a.t(); if b.p(m).status == "frz" { b.cure_status(m); } RV::Undef });
    h!(r, Ability, "magmaarmor", "onImmunity", |b, a| { if a.relay == RV::S(id("frz")) { return RV::B(false); } RV::Undef });
    h!(r, Ability, "solarpower", "onModifySpA", |b, a| { let m = a.t(); let w = b.pokemon_effective_weather(m, None); if w == "sunnyday" || w == "desolateland" { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Ability, "solarpower", "onWeather", |b, a| {
        let t = a.t(); let Some(e) = a.src_eff else { return RV::Undef };
        if b.pokemon_effective_weather(t, None) != e.id { return RV::Undef; }
        if e.id == "sunnyday" || e.id == "desolateland" { let d = b.p(t).base_maxhp as f64 / 8.0; b.damage(d, Some(t), Some(t), None, false); }
        RV::Undef });
    h!(r, Ability, "sandveil", "onImmunity", |b, a| { if a.relay == RV::S(id("sandstorm")) { return RV::B(false); } RV::Undef });
    h!(r, Ability, "sandveil", "onModifyAccuracy", |b, a| { if let RV::N(_) = a.relay { if b.effective_weather() == "sandstorm" { return b.cm(3277.0, 4096.0); } } RV::Undef });
    h!(r, Ability, "justified", "onDamagingHit", |b, a| { if b.am(a.am()).mtype == "Dark" { b.boost(vec![(0, 1)], None, None, None, false, false); } RV::Undef });
    h!(r, Ability, "megasol", "onWeatherModifyDamage", |b, a| { sun_weather_mod(b, a); a.relay.clone() });
}
