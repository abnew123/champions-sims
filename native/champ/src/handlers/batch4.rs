//! Handlers ported 2026-10-12 from the Eval bar's audit (evalbar/hook_audit.py): the unsupported effects met most in the bot's real
//! positions (No Retreat, Sweet Veil, Eelevate, Focus Energy, Strong Jaw, Frisk, Analytic), plus the faint boosters and Steadfast.
//! Each follows data/abilities.ts / data/moves.ts (the champions mod changes none of them) and was checked on focused Showdown cases.
use super::Reg;
use crate::battle::*;
use crate::dex::*;
use crate::h;
use crate::state::*;

impl Battle {
    /// pokemon.getBestStat(unboosted, unmodified): the boost index (0 atk .. 4 spe) of the highest stat, ties to the first
    pub fn best_stat(&mut self, m: MonRef, unboosted: bool, unmodified: bool) -> u8 {
        let (mut best, mut idx) = (0, 0u8);
        for i in 1..6 { let s = self.get_stat(m, i, unboosted, unmodified); if s > best { best = s; idx = (i - 1) as u8; } }
        idx
    }
    /// onSourceAfterFaint of Moxie / Beast Boost / Eelevate: a faint caused by a move boosts the holder by the number fainted
    fn faint_boost(&mut self, a: &HArgs, stat: Option<u8>) {
        let Some(e) = a.src_eff else { return };
        if self.etype_of(&e) != EType::Move { return; }
        let m = self.holder(); let n = a.n() as i64;
        let k = stat.unwrap_or_else(|| self.best_stat(m, true, true));
        self.boost(vec![(k, n)], Some(m), Some(m), None, false, false);
    }
}

pub fn register(r: &mut Reg) {
    h!(r, Ability, "strongjaw", "onBasePower", |b, a| { if b.am(a.am()).flag("bite") { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Ability, "analytic", "onBasePower", |b, a| {
        let m = a.t();
        let boosted = b.all_active().iter().filter(|&&t| t != m).all(|&t| b.will_move(t).is_none());
        if boosted { return b.cm(5325.0, 4096.0); } RV::Undef });
    h!(r, Ability, "frisk", "onStart", |b, a| {
        let m = a.t();
        for t in b.foes(m) { let it = b.p(t).item; if !it.is_empty() {
            let (tn, mn) = (b.mon_name(t), b.mon_name(m)); let name = b.dex.items[it].name;
            b.add(&["-item", &tn, name, "[from] ability: Frisk", &format!("[of] {}", mn)]); } }
        RV::Undef });
    h!(r, Ability, "sweetveil", "onAllySetStatus", |b, a| {
        if a.relay != RV::S(id("slp")) { return RV::Undef; }
        let (t, hn) = (a.t(), b.mon_name(b.holder())); let tn = b.mon_name(t);
        b.add(&["-block", &tn, "ability: Sweet Veil", &format!("[of] {}", hn)]); RV::Null });
    h!(r, Ability, "sweetveil", "onAllyTryAddVolatile", |b, a| {
        if a.relay != RV::S(id("yawn")) { return RV::Undef; }
        let (t, hn) = (a.t(), b.mon_name(b.holder())); let tn = b.mon_name(t);
        b.add(&["-block", &tn, "ability: Sweet Veil", &format!("[of] {}", hn)]); RV::Null });
    h!(r, Ability, "moxie", "onSourceAfterFaint", |b, a| { b.faint_boost(a, Some(0)); RV::Undef });
    h!(r, Ability, "beastboost", "onSourceAfterFaint", |b, a| { b.faint_boost(a, None); RV::Undef });
    h!(r, Ability, "eelevate", "onSourceAfterFaint", |b, a| { b.faint_boost(a, None); RV::Undef });   // its airborneness is in is_grounded
    h!(r, Ability, "steadfast", "onFlinch", |b, a| { b.boost(vec![(4, 1)], None, None, None, false, false); RV::Undef });

    h!(r, Move, "noretreat", "onTry", |b, a| {
        let m = a.t();
        if b.has_vol(m, "noretreat") { return RV::B(false); }
        if b.has_vol(m, "trapped") { let i = a.am(); b.amoves[i].base.volatile_status = None; }
        RV::Undef });
    h!(r, Cond, "noretreat", "onStart", |b, a| { let n = b.mon_name(a.t()); b.add(&["-start", &n, "move: No Retreat"]); RV::Undef });
    h!(r, Cond, "noretreat", "onTrapPokemon", |b, a| { let m = a.t(); b.try_trap(m, false); RV::Undef });
    h!(r, Cond, "focusenergy", "onStart", |b, a| {
        let t = a.t(); if b.has_vol(t, "dragoncheer") { return RV::B(false); }
        let n = b.mon_name(t); b.add(&["-start", &n, "move: Focus Energy"]); RV::Undef });
    h!(r, Cond, "focusenergy", "onModifyCritRatio", |b, a| { RV::N(a.n() + 2.0) });
    h!(r, Cond, "dragoncheer", "onStart", |b, a| {
        let t = a.t(); if b.has_vol(t, "focusenergy") { return RV::B(false); }
        let n = b.mon_name(t); b.add(&["-start", &n, "move: Dragon Cheer"]);
        let d = b.has_type(t, "Dragon"); b.es().set("hasDragonType", SV::B(d)); RV::Undef });
    h!(r, Cond, "dragoncheer", "onModifyCritRatio", |b, a| { let k = if b.es().has("hasDragonType") { 2.0 } else { 1.0 }; RV::N(a.n() + k) });

    // turn-start actions (sim.rs resolve_action / run_action) and the conditions they add
    h!(r, Move, "chillyreception", "priorityChargeCallback", |b, a| { let m = a.t(); b.add_volatile(m, "chillyreception", None, None); RV::Undef });
    h!(r, Cond, "chillyreception", "onBeforeMove", |b, a| {
        if b.am(a.am()).id != "chillyreception" { return RV::Undef; }
        let n = b.mon_name(a.t()); b.add(&["-prepare", &n, "Chilly Reception", "[premajor]"]); RV::Undef });
    h!(r, Move, "focuspunch", "priorityChargeCallback", |b, a| { let m = a.t(); b.add_volatile(m, "focuspunch", None, None); RV::Undef });
    h!(r, Move, "focuspunch", "beforeMoveCallback", |b, a| {
        let m = a.t();
        let lost = crate::state::find(&b.p(m).volatiles, "focuspunch").map(|s| s.has("lostFocus")).unwrap_or(false);
        if lost { let n = b.mon_name(m); b.add(&["cant", &n, "Focus Punch", "Focus Punch"]); return RV::B(true); }
        RV::Undef });
    h!(r, Cond, "focuspunch", "onStart", |b, a| { let n = b.mon_name(a.t()); b.add(&["-singleturn", &n, "move: Focus Punch"]); RV::Undef });
    h!(r, Cond, "focuspunch", "onHit", |b, a| { if b.am(a.am()).category != "Status" { b.es().set("lostFocus", SV::B(true)); } RV::Undef });
    h!(r, Cond, "focuspunch", "onTryAddVolatile", |b, a| { if a.relay == RV::S(id("flinch")) { return RV::Null; } RV::Undef });
    h!(r, Move, "beakblast", "priorityChargeCallback", |b, a| { let m = a.t(); b.add_volatile(m, "beakblast", None, None); RV::Undef });
    h!(r, Move, "beakblast", "onAfterMove", |b, a| { let m = a.t(); b.remove_volatile(m, "beakblast"); RV::Undef });
    h!(r, Cond, "beakblast", "onStart", |b, a| { let n = b.mon_name(a.t()); b.add(&["-singleturn", &n, "move: Beak Blast"]); RV::Undef });
    h!(r, Cond, "beakblast", "onHit", |b, a| {
        let (t, s, am) = (a.t(), a.s(), a.am());
        if b.makes_contact(am, s) { b.try_set_status(s, id("brn"), Some(t), None); } RV::Undef });
    for (mv, cat) in [("counter", "Physical"), ("mirrorcoat", "Special")] {
        r.insert((Kind::Move, id(mv), id("beforeTurnCallback")), if mv == "counter" { counter_btc as HFn } else { mirrorcoat_btc as HFn });
        r.insert((Kind::Move, id(mv), id("onTry")), if mv == "counter" { counter_try as HFn } else { mirrorcoat_try as HFn });
        r.insert((Kind::Move, id(mv), id("damageCallback")), if mv == "counter" { counter_dmg as HFn } else { mirrorcoat_dmg as HFn });
        r.insert((Kind::Cond, id(mv), id("onStart")), reflect_start as HFn);
        r.insert((Kind::Cond, id(mv), id("onRedirectTarget")), if mv == "counter" { counter_redirect as HFn } else { mirrorcoat_redirect as HFn });
        r.insert((Kind::Cond, id(mv), id("onDamagingHit")), if cat == "Physical" { counter_hit as HFn } else { mirrorcoat_hit as HFn });
    }
}
// Counter / Mirror Coat: the volatile records the last foe to hit with that category and twice the damage
fn reflect_btc(b: &mut Battle, a: &mut HArgs, v: &str) -> RV { let m = a.t(); b.add_volatile(m, v, None, None); RV::Undef }
fn counter_btc(b: &mut Battle, a: &mut HArgs) -> RV { reflect_btc(b, a, "counter") }
fn mirrorcoat_btc(b: &mut Battle, a: &mut HArgs) -> RV { reflect_btc(b, a, "mirrorcoat") }
fn reflect_try(b: &mut Battle, a: &mut HArgs, v: &str) -> RV {
    let m = a.t();
    match crate::state::find(&b.p(m).volatiles, v) { None => RV::B(false), Some(s) => if s.get("slot").and_then(|x| x.s()).map(|x| x.is_empty()).unwrap_or(true) { RV::B(false) } else { RV::Undef } }
}
fn counter_try(b: &mut Battle, a: &mut HArgs) -> RV { reflect_try(b, a, "counter") }
fn mirrorcoat_try(b: &mut Battle, a: &mut HArgs) -> RV { reflect_try(b, a, "mirrorcoat") }
fn reflect_dmg(b: &mut Battle, a: &mut HArgs, v: &str) -> RV {
    let m = a.source.unwrap_or(a.t());
    match crate::state::find(&b.p(m).volatiles, v) { None => RV::N(0.0), Some(s) => { let d = s.n("damage").unwrap_or(0.0); RV::N(if d != 0.0 { d } else { 1.0 }) } }
}
fn counter_dmg(b: &mut Battle, a: &mut HArgs) -> RV { reflect_dmg(b, a, "counter") }
fn mirrorcoat_dmg(b: &mut Battle, a: &mut HArgs) -> RV { reflect_dmg(b, a, "mirrorcoat") }
fn reflect_start(b: &mut Battle, _a: &mut HArgs) -> RV { b.es().set("slot", SV::Null); b.es().set("damage", SV::N(0.0)); RV::Undef }
fn reflect_redirect(b: &mut Battle, a: &mut HArgs, v: &str) -> RV {
    if b.am(a.am()).id != v { return RV::Undef; }
    let holder = b.holder();
    let slot = b.es().get("slot").and_then(|x| x.s()).unwrap_or("");
    if a.source != Some(holder) || slot.is_empty() { return RV::Undef; }
    match b.get_at_slot(slot) { Some(t) => RV::M(t), None => RV::Undef }
}
fn counter_redirect(b: &mut Battle, a: &mut HArgs) -> RV { reflect_redirect(b, a, "counter") }
fn mirrorcoat_redirect(b: &mut Battle, a: &mut HArgs) -> RV { reflect_redirect(b, a, "mirrorcoat") }
fn reflect_hit(b: &mut Battle, a: &mut HArgs, cat: &str) -> RV {
    let (t, s) = (a.t(), a.s()); let mid = b.am(a.am()).id;
    if !b.is_ally(s, t) && b.dex.mv(mid).tmpl.category == cat {
        let slot = b.slot_name(s); let d = a.n();
        b.es().set("slot", SV::S(slot)); b.es().set("damage", SV::N(2.0 * d));
    }
    RV::Undef
}
fn counter_hit(b: &mut Battle, a: &mut HArgs) -> RV { reflect_hit(b, a, "Physical") }
fn mirrorcoat_hit(b: &mut Battle, a: &mut HArgs) -> RV { reflect_hit(b, a, "Special") }
