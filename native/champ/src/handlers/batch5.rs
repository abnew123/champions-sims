//! Handlers ported 2026-10-12, batch 5: the most used effects still missing in the Eval bar's audit (evalbar/hook_audit.json) and in the
//! mid-battle differential cases (native/gen_battle_cases.js). Each follows the champions mod's resolved source and was checked on
//! focused Showdown cases.
use super::Reg;
use crate::battle::*;
use crate::dex::*;
use crate::h;
use crate::state::*;

impl Battle {
    /// pokemon.sethp(d): clamped to 1..maxhp, returns the change
    pub fn set_hp(&mut self, m: MonRef, d: f64) -> i64 {
        if self.p(m).hp == 0 { return 0; }
        let mut d = Battle::trunc(d); if d < 1 { d = 1; }
        let p = self.pm(m); let mut ch = d - p.hp; p.hp += ch;
        if p.hp > p.maxhp { ch -= p.hp - p.maxhp; p.hp = p.maxhp; }
        ch
    }
    fn is_berry(&self, it: Id) -> bool { self.dex.items.get(it).map(|i| i.raw.get("isBerry").and_then(|x| x.as_bool()).unwrap_or(false)).unwrap_or(false) }
}
/// Synthesis / Moonlight / Morning Sun: half, two thirds in sun, a quarter in other weather
fn weather_heal(b: &mut Battle, a: &mut HArgs) -> RV {
    let m = a.t();
    let factor = match b.pokemon_effective_weather(m, None) { "sunnyday" | "desolateland" => 0.667, "raindance" | "primordialsea" | "sandstorm" | "hail" | "snowscape" => 0.25, _ => 0.5 };
    let hp = b.modify(b.p(m).maxhp as f64, factor) as f64;
    let ok = b.heal(hp, Some(m), None, None).truthy();
    if !ok { let n = b.mon_name(m); b.add(&["-fail", &n, "heal"]); return RV::NotFail; }
    RV::B(true)
}
/// Water Absorb / Earth Eater: a move of that type heals a quarter instead
fn absorb_heal(b: &mut Battle, a: &mut HArgs, ty: &str, ab: &str) -> RV {
    let (t, s) = (a.t(), a.s());
    if t != s && b.am(a.am()).mtype == ty {
        let d = b.p(t).base_maxhp as f64 / 4.0;
        if !b.heal(d, Some(t), None, None).truthy() { let n = b.mon_name(t); b.add(&["-immune", &n, &format!("[from] ability: {}", ab)]); }
        return RV::Null;
    }
    RV::Undef
}
fn plus_minus(b: &mut Battle, a: &mut HArgs) -> RV {
    let m = a.t();
    for x in b.allies_and_self(m) { if x != m && (b.has_ability(x, "minus") || b.has_ability(x, "plus")) { return b.cm(1.5, 1.0); } }
    RV::Undef
}
fn ate2(b: &mut Battle, a: &mut HArgs, ty: Id) -> RV {
    let am = a.am(); let mv = b.am(am);
    let no = ["judgment", "multiattack", "naturalgift", "revelationdance", "technoblast", "terrainpulse", "weatherball"];
    if mv.mtype == "Normal" && !no.contains(&mv.id) && !(mv.is_z && mv.category != "Status") {
        let ab = b.effect.unwrap().id; let x = b.amm(am); x.mtype = ty; x.type_changer_boosted = Some(ab);
    }
    RV::Undef
}
fn ate2_bp(b: &mut Battle, a: &mut HArgs) -> RV { let am = a.am(); if b.am(am).type_changer_boosted == b.effect.map(|e| e.id) { return b.cm(4915.0, 4096.0); } RV::Undef }

pub fn register(r: &mut Reg) {
    // abilities
    h!(r, Ability, "reckless", "onBasePower", |b, a| { let am = b.am(a.am()); if am.recoil.is_some() || am.has_crash_damage { return b.cm(4915.0, 4096.0); } RV::Undef });
    h!(r, Ability, "dragonize", "onModifyType", |b, a| { ate2(b, a, "Dragon") });
    h!(r, Ability, "dragonize", "onBasePower", |b, a| { ate2_bp(b, a) });
    h!(r, Ability, "refrigerate", "onModifyType", |b, a| { ate2(b, a, "Ice") });
    h!(r, Ability, "refrigerate", "onBasePower", |b, a| { ate2_bp(b, a) });
    h!(r, Ability, "purepower", "onModifyAtk", |b, a| { b.cm(2.0, 1.0) });
    h!(r, Ability, "marvelscale", "onModifyDef", |b, a| { if !b.p(a.t()).status.is_empty() { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Ability, "shielddust", "onModifySecondaries", |b, a| {
        if let RV::Secs(s) = &a.relay { return RV::Secs(s.iter().filter(|e| e.self_eff.is_some()).cloned().collect()); } RV::Undef });
    h!(r, Ability, "skilllink", "onModifyMove", |b, a| {
        let am = a.am(); let x = b.amm(am);
        if let Some((_, hi)) = x.multihit { x.multihit = Some((hi, hi)); }
        x.multiaccuracy = false; RV::Undef });
    h!(r, Ability, "eartheater", "onTryHit", |b, a| { absorb_heal(b, a, "Ground", "Earth Eater") });
    h!(r, Ability, "waterabsorb", "onTryHit", |b, a| { absorb_heal(b, a, "Water", "Water Absorb") });
    h!(r, Ability, "motordrive", "onTryHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if t != s && b.am(a.am()).mtype == "Electric" {
            if !b.boost(vec![(4, 1)], None, None, None, false, false).truthy() { let n = b.mon_name(t); b.add(&["-immune", &n, "[from] ability: Motor Drive"]); }
            return RV::Null;
        }
        RV::Undef });
    h!(r, Ability, "overcoat", "onImmunity", |b, a| { if a.relay == RV::S(id("sandstorm")) || a.relay == RV::S(id("hail")) || a.relay == RV::S(id("powder")) { return RV::B(false); } RV::Undef });
    h!(r, Ability, "overcoat", "onTryHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if b.am(a.am()).flag("powder") && t != s && !b.has_type(t, "Grass") {
            let n = b.mon_name(t); b.add(&["-immune", &n, "[from] ability: Overcoat"]); return RV::Null;
        }
        RV::Undef });
    h!(r, Ability, "minus", "onModifySpA", |b, a| { plus_minus(b, a) });
    h!(r, Ability, "plus", "onModifySpA", |b, a| { plus_minus(b, a) });
    h!(r, Ability, "longreach", "onModifyMove", |b, a| { let am = a.am(); b.amm(am).flags.retain(|f| *f != "contact"); RV::Undef });
    h!(r, Ability, "tangledfeet", "onModifyAccuracy", |b, a| {
        if let RV::N(_) = a.relay { if b.has_vol(a.t(), "confusion") { return b.cm(0.5, 1.0); } } RV::Undef });
    h!(r, Ability, "immunity", "onUpdate", |b, a| {
        let m = a.t(); if b.p(m).status == "psn" || b.p(m).status == "tox" { let n = b.mon_name(m); b.add(&["-activate", &n, "ability: Immunity"]); b.cure_status(m); }
        RV::Undef });
    h!(r, Ability, "immunity", "onSetStatus", |b, a| {
        if a.relay != RV::S(id("psn")) && a.relay != RV::S(id("tox")) { return RV::Undef; }
        let from_status = a.src_eff.map(|e| e.am.map(|i| b.am(i).base.status.is_some()).unwrap_or(false)).unwrap_or(false);
        if from_status { let n = b.mon_name(a.t()); b.add(&["-immune", &n, "[from] ability: Immunity"]); }
        RV::B(false) });
    h!(r, Ability, "angerpoint", "onHit", |b, a| {
        let t = a.t(); if b.p(t).hp == 0 { return RV::Undef; }
        let Some(e) = a.src_eff else { return RV::Undef }; let Some(am) = e.am else { return RV::Undef };
        let sl = b.slot_name(t); if b.amm(am).hd(sl).crit { b.boost(vec![(0, 12)], Some(t), Some(t), None, false, false); }
        RV::Undef });
    h!(r, Ability, "berserk", "onDamage", |b, a| {
        let multi = a.src_eff.and_then(|e| e.am).map(|i| b.am(i).multihit.is_some()).unwrap_or(false);
        let is_move = a.src_eff.map(|e| b.etype_of(&e) == EType::Move).unwrap_or(false);
        b.es().set("checkedBerserk", SV::B(!(is_move && !multi))); RV::Undef });
    h!(r, Ability, "berserk", "onTryEatItem", |b, a| {
        let heal = ["aguavberry", "enigmaberry", "figyberry", "iapapaberry", "magoberry", "sitrusberry", "wikiberry", "oranberry", "berryjuice"];
        if let RV::S(it) = a.relay { if heal.contains(&it) { return match b.es().get("checkedBerserk") { Some(v) => RV::B(v.truthy()), None => RV::Undef }; } }   // unset: no objection
        RV::B(true) });
    h!(r, Ability, "berserk", "onAfterMoveSecondary", |b, a| {
        b.es().set("checkedBerserk", SV::B(true));
        let t = a.t(); let Some(s) = a.source else { return RV::Undef }; let am = a.am();
        if s == t || b.p(t).hp == 0 || b.am(am).total_damage == 0 { return RV::Undef; }
        let Some(last) = b.p(t).attacked_by.last().map(|x| x.damage) else { return RV::Undef };
        let mv = b.am(am); let dmg = if mv.multihit.is_some() && !mv.smart_target.unwrap_or(false) { mv.total_damage } else { last };
        let p = b.p(t);
        if p.hp as f64 <= p.maxhp as f64 / 2.0 && (p.hp + dmg) as f64 > p.maxhp as f64 / 2.0 { b.boost(vec![(2, 1)], Some(t), Some(t), None, false, false); }
        RV::Undef });
    h!(r, Ability, "harvest", "onResidual", |b, a| {
        let m = a.t();
        let w = b.effective_weather();
        if w == "sunnyday" || w == "desolateland" || b.rchance(1, 2) {
            let li = b.p(m).last_item;
            if b.p(m).hp > 0 && b.p(m).item.is_empty() && b.is_berry(li) {
                b.set_item(m, li, None, None); b.pm(m).last_item = "";
                let n = b.mon_name(m); let name = b.dex.items.get(li).map(|x| x.name).unwrap_or(li); b.add(&["-item", &n, name, "[from] ability: Harvest"]);
            }
        }
        RV::Undef });
    // items
    h!(r, Item, "ironball", "onModifySpe", |b, a| { b.cm(0.5, 1.0) });
    h!(r, Item, "ironball", "onEffectiveness", |b, a| {
        let Some(t) = a.target.mon() else { return RV::Undef };
        if b.has_vol(t, "ingrain") || b.has_vol(t, "smackdown") || find(&b.field.pseudo, "gravity").is_some() { return RV::Undef; }
        if b.am(a.am()).mtype == "Ground" && b.has_type(t, "Flying") { return RV::N(0.0); }
        RV::Undef });
    h!(r, Item, "wiseglasses", "onBasePower", |b, a| { if b.am(a.am()).category == "Special" { return b.cm(4505.0, 4096.0); } RV::Undef });
    h!(r, Item, "zoomlens", "onSourceModifyAccuracy", |b, a| {
        if let RV::N(_) = a.relay { if b.will_move(a.t()).is_none() { return b.cm(4915.0, 4096.0); } } RV::Undef });
    h!(r, Item, "flameorb", "onResidual", |b, a| { let m = a.t(); b.try_set_status(m, id("brn"), Some(m), None); RV::Undef });
    h!(r, Item, "toxicorb", "onResidual", |b, a| { let m = a.t(); b.try_set_status(m, id("tox"), Some(m), None); RV::Undef });
    // moves
    h!(r, Move, "gyroball", "basePowerCallback", |b, a| {
        let (t, s) = (a.t(), a.s());
        let (ts, ss) = (b.get_stat(t, 5, false, false) as f64, b.get_stat(s, 5, false, false) as f64);
        let mut p = (25.0 * ts / ss).floor() + 1.0; if !p.is_finite() { p = 1.0; } if p > 150.0 { p = 150.0; }
        RV::N(p) });
    h!(r, Move, "infernalparade", "basePowerCallback", |b, a| {
        let (t, am) = (a.t(), a.am()); let bp = b.am(am).base_power;
        RV::N(if !b.p(t).status.is_empty() || b.has_ability(t, "comatose") { bp * 2.0 } else { bp }) });
    h!(r, Move, "lashout", "onBasePower", |b, a| { if b.p(a.t()).stats_lowered_this_turn { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Move, "synthesis", "onHit", |b, a| { weather_heal(b, a) });
    h!(r, Move, "moonlight", "onHit", |b, a| { weather_heal(b, a) });
    h!(r, Move, "morningsun", "onHit", |b, a| { weather_heal(b, a) });
    h!(r, Move, "strengthsap", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if b.p(t).boosts[0] == -6 { return RV::B(false); }
        let atk = b.get_stat(t, 1, false, true) as f64;
        let ok = b.boost(vec![(0, -1)], Some(t), Some(s), None, false, true).truthy();
        let healed = b.heal(atk, Some(s), Some(t), None).truthy();
        RV::B(healed || ok) });
    h!(r, Move, "painsplit", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        let th = b.p(t).hp; let avg = { let x = (th + b.p(s).hp) / 2; if x == 0 { 1 } else { x } };
        let change = th - avg; let nh = b.p(t).hp - change; b.set_hp(t, nh as f64);
        let tn = b.mon_name(t); let hp = format!("{}/{}", b.p(t).hp, b.p(t).maxhp); b.add(&["-sethp", &tn, &hp, "[from] move: Pain Split", "[silent]"]);
        b.set_hp(s, avg as f64);
        let sn = b.mon_name(s); let hp = format!("{}/{}", b.p(s).hp, b.p(s).maxhp); b.add(&["-sethp", &sn, &hp, "[from] move: Pain Split"]);
        RV::Undef });
    h!(r, Move, "endeavor", "damageCallback", |b, a| { let (t, s) = (a.t(), a.source.unwrap()); RV::N((b.p(t).hp - b.p(s).hp) as f64) });
    h!(r, Move, "endeavor", "onTryImmunity", |b, a| { let (t, s) = (a.t(), a.source.unwrap()); RV::B(b.p(s).hp < b.p(t).hp) });
    h!(r, Move, "quash", "onHit", |b, a| {
        let t = a.t(); let Some(i) = b.will_move(t) else { return RV::B(false) };
        b.queue[i].order = 201.0; let n = b.mon_name(t); b.add(&["-activate", &n, "move: Quash"]); RV::Undef });
    h!(r, Move, "highjumpkick", "onMoveFail", |b, a| {
        let s = a.source.unwrap(); let d = b.p(s).base_maxhp as f64 / 2.0;
        b.damage(d, Some(s), Some(s), Some(Eff::cond(id("highjumpkick"))), false); RV::Undef });
    h!(r, Move, "worryseed", "onTryImmunity", |b, a| { let t = a.t(); let ab = b.p(t).ability; RV::B(!(ab == "truant" || ab == "insomnia")) });
    h!(r, Move, "worryseed", "onTryHit", |b, a| { if b.ab_data(a.t()).cantsuppress { return RV::B(false); } RV::Undef });
    h!(r, Move, "worryseed", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if !b.set_ability(t, id("insomnia"), Some(s), None, false) { return RV::B(false); }
        if b.p(t).status == "slp" { b.cure_status(t); }
        RV::Undef });
    // Ceaseless Edge lays Spikes; Spikes as a side condition
    h!(r, Move, "ceaselessedge", "onAfterHit", |b, a| { let s = a.s(); let am = a.am(); if !b.am(am).has_sheer_force && b.p(s).hp > 0 { b.add_side_condition(1 - s.0, "spikes", None, None); } RV::Undef });
    h!(r, Move, "ceaselessedge", "onAfterSubDamage", |b, a| { let s = a.s(); let am = a.am(); if !b.am(am).has_sheer_force && b.p(s).hp > 0 { b.add_side_condition(1 - s.0, "spikes", None, None); } RV::Undef });
    h!(r, Cond, "spikes", "onSideStart", |b, a| { b.es().set("layers", SV::N(1.0)); RV::Undef });
    h!(r, Cond, "spikes", "onSideRestart", |b, a| { let l = b.es().n("layers").unwrap_or(0.0); if l >= 3.0 { return RV::B(false); } b.es().set("layers", SV::N(l + 1.0)); RV::Undef });
    h!(r, Cond, "spikes", "onSwitchIn", |b, a| {
        let m = a.t(); if b.is_grounded(m, false) != Some(true) || b.has_item(m, "heavydutyboots") { return RV::Undef; }
        let l = b.es().n("layers").unwrap_or(0.0) as usize; let amt = [0.0, 3.0, 4.0, 6.0][l.min(3)];
        let d = amt * b.p(m).maxhp as f64 / 24.0; b.damage(d, None, None, None, false); RV::Undef });
}
