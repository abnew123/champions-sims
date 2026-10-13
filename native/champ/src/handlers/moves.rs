//! Move handlers (data/moves.ts). Argument positions follow the singleEvent calls in battle-actions:
//!   onTry / onTryMove / onModifyMove / onModifyType / onModifyPriority: target = user, source = target
//!   onPrepareHit / onHit / onTryHit / onAfterHit / onTryImmunity / onMoveFail: target = target, source = user
//!   onBasePower: target = attacker, source = defender;  basePowerCallback / damageCallback (call_fn): target = defender, source = attacker
use super::Reg;
use crate::battle::*;
use crate::dex::*;
use crate::h;
use crate::state::*;

impl Battle {
    pub fn will_act(&self) -> bool { self.queue.iter().any(|q| q.choice == Choice::Move) }
    pub fn is_terrain(&self, t: &str) -> bool { self.field.terrain == t }
    pub fn get_weight(&mut self, m: MonRef) -> i64 {
        let w = self.p(m).weighthg as f64;
        (self.run_event("ModifyWeight", Tgt::Mon(m), None, None, RV::N(w), false, false).num() as i64).max(1)
    }
    pub fn positive_boosts(&self, m: MonRef) -> i64 { self.p(m).boosts.iter().filter(|x| **x > 0).sum() }
    pub fn clear_boosts(&mut self, m: MonRef) { self.pm(m).boosts = [0; 7]; }
    pub fn set_item(&mut self, m: MonRef, item: Id, source: Option<MonRef>, effect: Option<Eff>) -> bool {
        if self.p(m).hp == 0 || !self.p(m).is_active { return false; }
        let old = self.p(m).item;
        let st = self.init_state(item, Some(true));
        let old_state = std::mem::replace(&mut self.pm(m).item_state, st);
        self.pm(m).item = item;
        if !old.is_empty() { self.temp.push(old_state); let tl = SLoc::Temp(self.temp.len() - 1);
            self.single_event("End", Eff::new(Kind::Item, old), Some(tl), Tgt::Mon(m), None, None, RV::Undef); self.temp.pop(); }
        if !item.is_empty() { self.single_event("Start", Eff::new(Kind::Item, item), Some(SLoc::Item(m)), Tgt::Mon(m), source, effect, RV::Undef); }
        true
    }
    pub fn prioritize_action(&mut self, qi: usize, source_effect: Option<Eff>) {
        let mut a = self.queue.remove(qi); a.source_effect = source_effect; a.order = 3.0; self.queue.insert(0, a);
    }
}
/// protect-family onPrepareHit: !!queue.willAct() && runEvent('StallMove', pokemon)
fn stall_prepare(b: &mut Battle, a: &HArgs) -> RV {
    if !b.will_act() { return RV::B(false); }
    let m = a.t(); RV::B(b.run_event("StallMove", Tgt::Mon(m), None, None, RV::Undef, false, false).truthy())
}
fn weight_bp(w: i64) -> f64 { (if w >= 2000 { 120 } else if w >= 1000 { 100 } else if w >= 500 { 80 } else if w >= 250 { 60 } else if w >= 100 { 40 } else { 20 }) as f64 }
fn remove_screens(b: &mut Battle, m: MonRef) { for c in ["reflect", "lightscreen", "auroraveil"] { b.remove_side_condition(m.0, c); } }
/// Trick / Switcheroo onHit
fn swap_items(b: &mut Battle, a: &HArgs) -> RV {
    let (t, s) = (a.t(), a.s()); let e = a.src_eff;
    let your = b.take_item_ex(t, Some(s)); let my = b.take_item_ex(s, None);
    let fail = |b: &mut Battle| { if let Some(Some(y)) = your { b.pm(t).item = y; } if let Some(Some(x)) = my { b.pm(s).item = x; } RV::B(false) };
    if your.is_none() || my.is_none() || (your == Some(None) && my == Some(None)) { return fail(b); }
    if let Some(Some(x)) = my { if !b.single_event("TakeItem", Eff::new(Kind::Item, x), Some(SLoc::Item(s)), Tgt::Mon(t), Some(s), e, RV::S(x)).truthy() { return fail(b); } }
    if let Some(Some(y)) = your { if !b.single_event("TakeItem", Eff::new(Kind::Item, y), Some(SLoc::Item(t)), Tgt::Mon(s), Some(t), e, RV::S(y)).truthy() { return fail(b); } }
    if let Some(Some(x)) = my { b.set_item(t, x, None, None); }
    if let Some(Some(y)) = your { b.set_item(s, y, None, None); }
    RV::Undef
}
impl Battle {
    /// takeItem returning Some(Some(item)) taken, Some(None) nothing held (undefined), None refused (false)
    pub fn take_item_ex(&mut self, m: MonRef, source: Option<MonRef>) -> Option<Option<Id>> {
        if self.p(m).item.is_empty() { return Some(None); }
        match self.take_item(m, source) { Some(i) => Some(Some(i)), None => None }
    }
}

/// Showdown's pokemon.getLastDamagedBy(true): the last foe hit on the user's attackedBy list
fn last_damaged_by(b: &Battle, m: MonRef) -> Option<Attack> { b.p(m).attacked_by.iter().filter(|x| !b.is_ally(m, x.source)).last().cloned() }
/// the Pokemon now in a slot ("p1a" .. "p2b")
fn at_slot(b: &Battle, slot: Id) -> Option<MonRef> {
    let bs = slot.as_bytes(); if bs.len() < 3 { return None; }
    let s = (bs[1] - b'1') as u8; let pos = (bs[2] - b'a') as usize;
    if s > 1 || pos > 1 { return None; }
    b.sides[s as usize].active[pos].map(|i| (s, i))
}
fn mortal_spin_clear(b: &mut Battle, m: MonRef) {
    b.remove_volatile(m, "leechseed");
    for c in ["spikes", "toxicspikes", "stealthrock", "stickyweb", "gmaxsteelsurge"] { b.remove_side_condition(m.0, c); }
    b.remove_volatile(m, "partiallytrapped");
}
pub fn register(r: &mut Reg) {
    // ---------- protection ----------
    for _ in 0..1 {}
    h!(r, Move, "protect", "onPrepareHit", |b, a| { stall_prepare(b, a) });
    h!(r, Move, "protect", "onHit", |b, a| { let m = a.t(); b.add_volatile(m, "stall", None, None); RV::Undef });
    h!(r, Move, "detect", "onPrepareHit", |b, a| { stall_prepare(b, a) });
    h!(r, Move, "detect", "onHit", |b, a| { let m = a.t(); b.add_volatile(m, "stall", None, None); RV::Undef });
    h!(r, Move, "spikyshield", "onPrepareHit", |b, a| { stall_prepare(b, a) });
    h!(r, Move, "spikyshield", "onHit", |b, a| { let m = a.t(); b.add_volatile(m, "stall", None, None); RV::Undef });
    h!(r, Move, "banefulbunker", "onPrepareHit", |b, a| { stall_prepare(b, a) });
    h!(r, Move, "banefulbunker", "onHit", |b, a| { let m = a.t(); b.add_volatile(m, "stall", None, None); RV::Undef });
    h!(r, Move, "kingsshield", "onPrepareHit", |b, a| { stall_prepare(b, a) });
    h!(r, Move, "kingsshield", "onHit", |b, a| { let m = a.t(); b.add_volatile(m, "stall", None, None); RV::Undef });
    h!(r, Move, "wideguard", "onTry", |b, a| { RV::B(b.will_act()) });
    h!(r, Move, "wideguard", "onHitSide", |b, a| { let s = a.s(); b.add_volatile(s, "stall", None, None); RV::Undef });
    h!(r, Move, "quickguard", "onTry", |b, a| { RV::B(b.will_act()) });
    h!(r, Move, "quickguard", "onHitSide", |b, a| { let s = a.s(); b.add_volatile(s, "stall", None, None); RV::Undef });
    // ---------- first-turn / priority moves ----------
    h!(r, Move, "fakeout", "onTry", |b, a| { if b.p(a.t()).active_move_actions > 1 { return RV::B(false); } RV::Undef });
    h!(r, Move, "fakeout", "onDisableMove", |b, a| { let m = a.t(); if b.p(m).active_move_actions != 0 { b.disable_move(m, "fakeout", false, ""); } RV::Undef });
    h!(r, Move, "firstimpression", "onTry", |b, a| { if b.p(a.t()).active_move_actions > 1 { return RV::B(false); } RV::Undef });
    h!(r, Move, "firstimpression", "onDisableMove", |b, a| { let m = a.t(); if b.p(m).active_move_actions != 0 { b.disable_move(m, "firstimpression", false, ""); } RV::Undef });
    h!(r, Move, "grassyglide", "onModifyPriority", |b, a| { let m = a.t(); if b.is_terrain("grassyterrain") && b.is_grounded(m, false) == Some(true) { return RV::N(a.n() + 1.0); } RV::Undef });
    h!(r, Move, "suckerpunch", "onTry", |b, a| {
        let Some(t) = a.source else { return RV::B(false) };
        let qa = b.will_move(t).map(|i| b.queue[i].am.unwrap());
        match qa { None => RV::B(false), Some(qm) => { let mv = b.am(qm); if (mv.category == "Status" && mv.id != "mefirst") || b.has_vol(t, "mustrecharge") { RV::B(false) } else { RV::Undef } } }
    });
    h!(r, Move, "upperhand", "onTry", |b, a| {
        let Some(t) = a.source else { return RV::B(false) };
        match b.will_move(t).map(|i| b.queue[i].am.unwrap()) { None => RV::B(false), Some(qm) => { let mv = b.am(qm); if mv.priority <= 0.1 || mv.category == "Status" { RV::B(false) } else { RV::Undef } } }
    });
    // ---------- support ----------
    h!(r, Move, "followme", "onTry", |b, a| { RV::B(true) });
    h!(r, Move, "ragepowder", "onTry", |b, a| { RV::B(true) });
    h!(r, Move, "helpinghand", "onTryHit", |b, a| { let t = a.t(); if !b.p(t).newly_switched && b.will_move(t).is_none() { return RV::B(false); } RV::Undef });
    h!(r, Move, "partingshot", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        let ok = b.boost(vec![(0, -1), (2, -1)], Some(t), Some(s), None, false, false);
        if !ok.truthy() && !b.has_ability(t, "mirrorarmor") { let am = a.am(); b.amm(am).base.self_switch = None; }
        RV::Undef });
    h!(r, Move, "auroraveil", "onTry", |b, a| { let w = b.effective_weather(); RV::B(w == "hail" || w == "snowscape") });
    h!(r, Move, "yawn", "onTryHit", |b, a| { let t = a.t(); if !b.p(t).status.is_empty() || !b.run_status_immunity(t, "slp", false) { return RV::B(false); } RV::Undef });
    h!(r, Move, "disable", "onTryHit", |b, a| { let t = a.t(); if b.p(t).last_move.map(|x| x == "struggle").unwrap_or(true) { return RV::B(false); } RV::Undef });
    h!(r, Move, "leechseed", "onTryImmunity", |b, a| { let t = a.t(); RV::B(!b.has_type(t, "Grass")) });
    h!(r, Move, "trick", "onTryImmunity", |b, a| { RV::B(!b.has_ability(a.t(), "stickyhold")) });
    h!(r, Move, "switcheroo", "onTryImmunity", |b, a| { RV::B(!b.has_ability(a.t(), "stickyhold")) });
    h!(r, Move, "trick", "onHit", |b, a| { swap_items(b, a) });
    h!(r, Move, "switcheroo", "onHit", |b, a| { swap_items(b, a) });
    h!(r, Move, "perishsong", "onHitField", |b, a| {
        let s = a.s(); let e = a.src_eff; let mut result = false;
        for m in b.all_active() {
            if b.run_event("Invulnerability", Tgt::Mon(m), Some(s), e, RV::Undef, false, false) == RV::B(false) { result = true; }
            else if b.run_event("TryHit", Tgt::Mon(m), Some(s), e, RV::Undef, false, false) == RV::Null { result = true; }
            else if !b.has_vol(m, "perishsong") { b.add_volatile(m, "perishsong", None, None); result = true; }
        }
        if !result { return RV::B(false); } RV::Undef });
    h!(r, Move, "haze", "onHitField", |b, a| { for m in b.all_active() { b.clear_boosts(m); } RV::Undef });
    h!(r, Move, "clearsmog", "onHit", |b, a| { let t = a.t(); b.clear_boosts(t); RV::Undef });
    h!(r, Move, "substitute", "onTryHit", |b, a| { let s = a.t(); if b.has_vol(s, "substitute") { return RV::NotFail; } let p = b.p(s); if p.hp as f64 <= p.maxhp as f64 / 4.0 || p.maxhp == 1 { return RV::NotFail; } RV::Undef });
    h!(r, Move, "substitute", "onHit", |b, a| { let t = a.t(); b.direct_damage((b.p(t).maxhp as f64 / 4.0).floor() as i64, t, None, None); RV::Undef });
    h!(r, Move, "healpulse", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        let amt = if b.has_ability(s, "megalauncher") { b.modify(b.p(t).base_maxhp as f64, 0.75) as f64 } else { (b.p(t).base_maxhp as f64 * 0.5).ceil() };
        let ok = b.heal(amt, None, None, None).truthy();
        if !ok { return RV::NotFail; } RV::B(true) });
    h!(r, Move, "pollenpuff", "onTryHit", |b, a| { let (t, s) = (a.t(), a.s()); if b.is_ally(s, t) { let am = a.am(); b.amm(am).base_power = 0.0; b.amm(am).infiltrates = true; } RV::Undef });
    h!(r, Move, "pollenpuff", "onTryMove", |b, a| { let s = a.t(); if let Some(t) = a.source { if b.is_ally(s, t) && b.has_vol(s, "healblock") { return RV::B(false); } } RV::Undef });
    h!(r, Move, "pollenpuff", "onHit", |b, a| { let (t, s) = (a.t(), a.s()); if b.is_ally(s, t) { if !b.heal((b.p(t).base_maxhp as f64 * 0.5).floor(), None, None, None).truthy() { return RV::NotFail; } } RV::Undef });
    h!(r, Move, "psychup", "onHit", |b, a| { let (t, s) = (a.t(), a.s()); let bo = b.p(t).boosts; b.pm(s).boosts = bo; RV::Undef });
    h!(r, Move, "powerswap", "onHit", |b, a| { let (t, s) = (a.t(), a.s()); for k in [0, 2] { let x = b.p(t).boosts[k]; let y = b.p(s).boosts[k]; b.pm(s).boosts[k] = x; b.pm(t).boosts[k] = y; } RV::Undef });
    h!(r, Move, "bellydrum", "onHit", |b, a| {
        let t = a.t(); let p = b.p(t); if p.hp as f64 <= p.maxhp as f64 / 2.0 || p.boosts[0] >= 6 || p.maxhp == 1 { return RV::B(false); }
        b.direct_damage((b.p(t).maxhp as f64 / 2.0).floor() as i64, t, None, None); b.boost(vec![(0, 12)], Some(t), None, None, false, false); RV::Undef });
    h!(r, Move, "clangoroussoul", "onTry", |b, a| { let s = a.t(); let p = b.p(s); if p.hp as f64 <= p.maxhp as f64 * 33.0 / 100.0 || p.maxhp == 1 { return RV::B(false); } RV::Undef });
    h!(r, Move, "clangoroussoul", "onTryHit", |b, a| {
        let am = a.am(); let bo = b.am(am).base.boosts.clone().unwrap_or_default();
        if !b.boost(bo, None, None, None, false, false).truthy() { return RV::Null; }
        b.amm(am).base.boosts = None; RV::Undef });
    h!(r, Move, "clangoroussoul", "onHit", |b, a| { let t = a.t(); let d = (b.p(t).maxhp as f64 * 33.0 / 100.0).floor() as i64; b.direct_damage(d, t, None, None); RV::Undef });
    h!(r, Move, "destinybond", "onPrepareHit", |b, a| { let m = a.t(); RV::B(!b.remove_volatile(m, "destinybond")) });
    h!(r, Move, "afteryou", "onHit", |b, a| { let t = a.t(); match b.will_move(t) { Some(i) => { b.prioritize_action(i, None); RV::Undef } None => RV::B(false) } });
    h!(r, Move, "batonpass", "onHit", |b, a| { let t = a.t(); if b.can_switch(t.0) == 0 || b.has_vol(t, "commanded") { return RV::NotFail; } RV::Undef });
    h!(r, Move, "batonpass", "self.onHit", |b, a| { let s = a.t(); b.pm(s).skip_before_switch_out = true; RV::Undef });
    h!(r, Move, "healingwish", "onTryHit", |b, a| { if b.can_switch(a.t().0) == 0 { return RV::NotFail; } RV::Undef });
    h!(r, Move, "revivalblessing", "onTryHit", |b, a| { let s = a.t(); if !b.sides[s.0 as usize].pokemon.iter().any(|p| p.fainted) { return RV::B(false); } RV::Undef });
    h!(r, Move, "soak", "onHit", |b, a| { let t = a.t(); let ty = b.get_types(t); if ty == vec!["Water"] { return RV::Null; } let p = b.pm(t); p.types = vec![id("Water")]; p.added_type = ""; RV::Undef });
    h!(r, Move, "steelbeam", "onMoveFail", |b, a| { let am = a.am(); if b.am(am).multihit.is_some() { return RV::Undef; } let s = a.s(); let d = crate::sim::js_round(b.p(s).maxhp as f64 / 2.0); b.damage(d as f64, Some(s), Some(s), Some(Eff::cond(id("steelbeam"))), false); RV::Undef });
    h!(r, Move, "skillswap", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if b.p(s).fainted || b.p(t).fainted { return RV::B(false); }
        let (sa, ta) = (b.p(s).ability, b.p(t).ability);
        if b.dex.eff(Kind::Ability, sa).flag("failskillswap") || b.dex.eff(Kind::Ability, ta).flag("failskillswap") { return RV::B(false); }
        let se = Some(Eff::cond(id("skillswap")));
        let r1 = b.run_event("SetAbility", Tgt::Mon(t), Some(s), se, RV::S(sa), false, false); if !r1.truthy() { return r1; }
        let r2 = b.run_event("SetAbility", Tgt::Mon(s), Some(s), se, RV::S(ta), false, false); if !r2.truthy() { return r2; }
        b.single_event("End", Eff::new(Kind::Ability, sa), Some(SLoc::Ability(s)), Tgt::Mon(s), None, None, RV::Undef);
        b.single_event("End", Eff::new(Kind::Ability, ta), Some(SLoc::Ability(t)), Tgt::Mon(t), None, None, RV::Undef);
        b.pm(s).ability = ta; b.pm(t).ability = sa;
        let st1 = b.init_state(ta, Some(true)); b.pm(s).ability_state = st1;
        let st2 = b.init_state(sa, Some(true)); b.pm(t).ability_state = st2;
        b.single_event("Start", Eff::new(Kind::Ability, sa), Some(SLoc::Ability(t)), Tgt::Mon(t), None, None, RV::Undef);
        b.single_event("Start", Eff::new(Kind::Ability, ta), Some(SLoc::Ability(s)), Tgt::Mon(s), None, None, RV::Undef);
        RV::Undef });
    h!(r, Move, "round", "onTry", |b, a| {
        let e = a.src_eff;
        let qi = b.queue.iter().position(|q| q.choice == Choice::Move && q.am.map(|x| b.am(x).id == "round").unwrap_or(false));
        if let Some(qi) = qi { b.prioritize_action(qi, e); }
        RV::Undef });
    h!(r, Move, "stoneaxe", "onAfterHit", |b, a| { let s = a.s(); let am = a.am(); if !b.am(am).has_sheer_force && b.p(s).hp > 0 { b.add_side_condition(1 - s.0, "stealthrock", None, None); } RV::Undef });
    h!(r, Move, "stoneaxe", "onAfterSubDamage", |b, a| { let s = a.s(); let am = a.am(); if !b.am(am).has_sheer_force && b.p(s).hp > 0 { b.add_side_condition(1 - s.0, "stealthrock", None, None); } RV::Undef });
    h!(r, Move, "struggle", "onModifyMove", |b, a| { let am = a.am(); b.amm(am).mtype = "???"; RV::Undef });
    h!(r, Move, "lastresort", "onTry", |b, a| {
        let s = a.t(); let p = b.p(s); if p.move_slots.len() < 2 { return RV::B(false); }
        let mut has = false; for sl in &p.move_slots { if sl.id == "lastresort" { has = true; continue; } if !sl.used { return RV::B(false); } }
        RV::B(has) });
    // ---------- type / power / targeting changes ----------
    h!(r, Move, "weatherball", "onModifyType", |b, a| {
        let m = a.t(); let am = a.am(); let w = b.pokemon_effective_weather(m, None);
        let t = match w { "sunnyday" | "desolateland" => "Fire", "raindance" | "primordialsea" => "Water", "sandstorm" => "Rock", "hail" | "snowscape" => "Ice", _ => "" };
        if !t.is_empty() { b.amm(am).mtype = t; } RV::Undef });
    h!(r, Move, "weatherball", "onModifyMove", |b, a| {
        let m = a.t(); let am = a.am(); let w = b.pokemon_effective_weather(m, None);
        if ["sunnyday", "desolateland", "raindance", "primordialsea", "sandstorm", "hail", "snowscape"].contains(&w) { b.amm(am).base_power *= 2.0; } RV::Undef });
    h!(r, Move, "terrainpulse", "onModifyType", |b, a| {
        let m = a.t(); let am = a.am(); if b.is_grounded(m, false) != Some(true) { return RV::Undef; }
        let t = match b.field.terrain { "electricterrain" => "Electric", "grassyterrain" => "Grass", "mistyterrain" => "Fairy", "psychicterrain" => "Psychic", _ => "" };
        if !t.is_empty() { b.amm(am).mtype = t; } RV::Undef });
    h!(r, Move, "terrainpulse", "onModifyMove", |b, a| { let m = a.t(); let am = a.am(); if !b.field.terrain.is_empty() && b.is_grounded(m, false) == Some(true) { b.amm(am).base_power *= 2.0; } RV::Undef });
    h!(r, Move, "expandingforce", "onBasePower", |b, a| { let m = a.t(); if b.is_terrain("psychicterrain") && b.is_grounded(m, false) == Some(true) { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Move, "expandingforce", "onModifyMove", |b, a| { let m = a.t(); let am = a.am(); if b.is_terrain("psychicterrain") && b.is_grounded(m, false) == Some(true) { b.amm(am).target = "allAdjacentFoes"; } RV::Undef });
    h!(r, Move, "hurricane", "onModifyMove", |b, a| {
        let am = a.am(); let w = a.source.map(|t| b.pokemon_effective_weather(t, None)).unwrap_or("");
        match w { "raindance" | "primordialsea" => b.amm(am).accuracy = None, "sunnyday" | "desolateland" => b.amm(am).accuracy = Some(50.0), _ => {} } RV::Undef });
    h!(r, Move, "thunder", "onModifyMove", |b, a| {
        let am = a.am(); let w = a.source.map(|t| b.pokemon_effective_weather(t, None)).unwrap_or("");
        match w { "raindance" | "primordialsea" => b.amm(am).accuracy = None, "sunnyday" | "desolateland" => b.amm(am).accuracy = Some(50.0), _ => {} } RV::Undef });
    h!(r, Move, "blizzard", "onModifyMove", |b, a| { let w = b.effective_weather(); if w == "hail" || w == "snowscape" { let am = a.am(); b.amm(am).accuracy = None; } RV::Undef });
    h!(r, Move, "freezedry", "onEffectiveness", |b, a| { if b.eff_type == "Water" { return RV::N(1.0); } RV::Undef });
    h!(r, Move, "facade", "onBasePower", |b, a| { let m = a.t(); let st = b.p(m).status; if !st.is_empty() && st != "slp" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Move, "barbbarrage", "onBasePower", |b, a| { let t = a.s(); let st = b.p(t).status; if st == "psn" || st == "tox" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Move, "ficklebeam", "onBasePower", |b, a| { if b.rchance(3, 10) { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Move, "solarbeam", "onBasePower", |b, a| { let m = a.t(); let w = b.pokemon_effective_weather(m, None); if ["raindance", "primordialsea", "sandstorm", "hail", "snowscape"].contains(&w) { return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Move, "knockoff", "onBasePower", |b, a| {
        let t = a.s(); let item = b.p(t).item; let e = a.src_eff;
        if !b.single_event("TakeItem", Eff::new(Kind::Item, item), Some(SLoc::Item(t)), Tgt::Mon(t), Some(t), e, RV::S(if item.is_empty() { "$none" } else { item })).truthy() { return RV::Undef; }
        if !item.is_empty() { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Move, "knockoff", "onAfterHit", |b, a| { let t = a.t(); b.take_item(t, None); RV::Undef });
    h!(r, Move, "psychicfangs", "onTryHit", |b, a| { let t = a.t(); remove_screens(b, t); RV::Undef });
    h!(r, Move, "brickbreak", "onTryHit", |b, a| { let t = a.t(); remove_screens(b, t); RV::Undef });
    h!(r, Move, "ragingbull", "onTryHit", |b, a| { let t = a.t(); remove_screens(b, t); RV::Undef });
    h!(r, Move, "lowkick", "onTryHit", |b, a| { RV::Undef });
    h!(r, Move, "grassknot", "onTryHit", |b, a| { RV::Undef });
    h!(r, Move, "heavyslam", "onTryHit", |b, a| { RV::Undef });
    h!(r, Move, "poltergeist", "onTry", |b, a| { RV::B(a.source.map(|t| !b.p(t).item.is_empty()).unwrap_or(false)) });
    h!(r, Move, "poltergeist", "onTryHit", |b, a| { RV::Undef });
    h!(r, Move, "steelroller", "onTry", |b, a| { RV::B(!b.field.terrain.is_empty()) });
    h!(r, Move, "steelroller", "onHit", |b, a| { b.clear_terrain(); RV::Undef });
    h!(r, Move, "steelroller", "onAfterSubDamage", |b, a| { b.clear_terrain(); RV::Undef });
    h!(r, Move, "icespinner", "onAfterHit", |b, a| { b.clear_terrain(); RV::Undef });
    h!(r, Move, "icespinner", "onAfterSubDamage", |b, a| { if a.source.map(|s| b.p(s).hp > 0).unwrap_or(false) { b.clear_terrain(); } RV::Undef });
    h!(r, Move, "doubleshock", "onTryMove", |b, a| { let m = a.t(); if b.has_type(m, "Electric") { return RV::Undef; } RV::Null });
    h!(r, Move, "doubleshock", "self.onHit", |b, a| { let m = a.t(); let ty: Vec<Id> = b.p(m).types.iter().map(|t| if *t == "Electric" { "???" } else { *t }).collect(); let p = b.pm(m); p.types = ty; p.added_type = ""; RV::Undef });
    h!(r, Move, "direclaw", "secondaries.0.onHit", |b, a| { let (t, s) = (a.t(), a.s()); let st = ["psn", "par", "slp"][b.prng.sample_idx(3)]; b.try_set_status(t, st, Some(s), None); RV::Undef });
    h!(r, Move, "throatchop", "secondaries.0.onHit", |b, a| { let t = a.t(); b.add_volatile(t, "throatchop", None, None); RV::Undef });
    // Curse as Champions rewrites it (mods/champions/moves.js): no volatileStatus on the move; a non-Ghost user boosts in onHit, a Ghost
    // user pays half its HP and applies the curse volatile in onHit (a random foe when it targeted an ally)
    h!(r, Move, "curse", "onModifyMove", |b, a| { let m = a.t(); let am = a.am();
        if !b.has_type(m, "Ghost") { b.amm(am).target = "self"; } else if let Some(t) = a.source { if t != m && b.is_ally(m, t) { b.amm(am).target = "randomNormal"; } } RV::Undef });
    h!(r, Move, "curse", "onTryHit", |b, a| { let t = a.t(); let Some(s) = a.source else { return RV::Undef }; if b.has_type(s, "Ghost") && b.has_vol(t, "curse") { return RV::B(false); } RV::Undef });
    h!(r, Move, "curse", "onHit", |b, a| { let t = a.t(); let s = a.s();
        if !b.has_type(s, "Ghost") { let r = b.boost(vec![(4, -1), (0, 1), (1, 1)], Some(s), Some(s), None, false, false); return RV::B(r.truthy()); }
        let d = b.p(s).maxhp / 2; b.direct_damage(d, s, Some(s), None);
        let mut t = t;
        if b.is_ally(s, t) { let am = b.new_am(b.dex.active_move("curse")); match b.get_random_target(s, am) { Some(r) => t = r, None => return RV::B(false) } }
        b.pm(t).volatiles.retain(|(k, _)| *k != "curse");
        b.add_volatile(t, "curse", Some(s), None); RV::Undef });
    h!(r, Move, "batonpass", "onHit", |b, a| { let t = a.t(); if b.can_switch(t.0) == 0 || b.has_vol(t, "commanded") { return RV::NotFail; } RV::Undef });
    h!(r, Move, "batonpass", "self.onHit", |b, a| { let s = a.t(); b.pm(s).skip_before_switch_out = true; RV::Undef });
    h!(r, Move, "healingwish", "onTryHit", |b, a| { if b.can_switch(a.t().0) == 0 { return RV::NotFail; } RV::Undef });
    h!(r, Move, "revivalblessing", "onTryHit", |b, a| { let s = a.t(); if !b.sides[s.0 as usize].pokemon.iter().any(|p| p.fainted) { return RV::B(false); } RV::Undef });
    h!(r, Move, "soak", "onHit", |b, a| { let t = a.t(); let ty = b.get_types(t); if ty == vec!["Water"] { return RV::Null; } let p = b.pm(t); p.types = vec![id("Water")]; p.added_type = ""; RV::Undef });
    h!(r, Move, "steelbeam", "onMoveFail", |b, a| { let am = a.am(); if b.am(am).multihit.is_some() { return RV::Undef; } let s = a.s(); let d = crate::sim::js_round(b.p(s).maxhp as f64 / 2.0); b.damage(d as f64, Some(s), Some(s), Some(Eff::cond(id("steelbeam"))), false); RV::Undef });
    h!(r, Move, "skillswap", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if b.p(s).fainted || b.p(t).fainted { return RV::B(false); }
        let (sa, ta) = (b.p(s).ability, b.p(t).ability);
        if b.dex.eff(Kind::Ability, sa).flag("failskillswap") || b.dex.eff(Kind::Ability, ta).flag("failskillswap") { return RV::B(false); }
        let se = Some(Eff::cond(id("skillswap")));
        let r1 = b.run_event("SetAbility", Tgt::Mon(t), Some(s), se, RV::S(sa), false, false); if !r1.truthy() { return r1; }
        let r2 = b.run_event("SetAbility", Tgt::Mon(s), Some(s), se, RV::S(ta), false, false); if !r2.truthy() { return r2; }
        b.single_event("End", Eff::new(Kind::Ability, sa), Some(SLoc::Ability(s)), Tgt::Mon(s), None, None, RV::Undef);
        b.single_event("End", Eff::new(Kind::Ability, ta), Some(SLoc::Ability(t)), Tgt::Mon(t), None, None, RV::Undef);
        b.pm(s).ability = ta; b.pm(t).ability = sa;
        let st1 = b.init_state(ta, Some(true)); b.pm(s).ability_state = st1;
        let st2 = b.init_state(sa, Some(true)); b.pm(t).ability_state = st2;
        b.single_event("Start", Eff::new(Kind::Ability, sa), Some(SLoc::Ability(t)), Tgt::Mon(t), None, None, RV::Undef);
        b.single_event("Start", Eff::new(Kind::Ability, ta), Some(SLoc::Ability(s)), Tgt::Mon(s), None, None, RV::Undef);
        RV::Undef });
    h!(r, Move, "round", "onTry", |b, a| {
        let e = a.src_eff;
        let qi = b.queue.iter().position(|q| q.choice == Choice::Move && q.am.map(|x| b.am(x).id == "round").unwrap_or(false));
        if let Some(qi) = qi { b.prioritize_action(qi, e); }
        RV::Undef });
    h!(r, Move, "stoneaxe", "onAfterHit", |b, a| { let s = a.s(); let am = a.am(); if !b.am(am).has_sheer_force && b.p(s).hp > 0 { b.add_side_condition(1 - s.0, "stealthrock", None, None); } RV::Undef });
    h!(r, Move, "stoneaxe", "onAfterSubDamage", |b, a| { let s = a.s(); let am = a.am(); if !b.am(am).has_sheer_force && b.p(s).hp > 0 { b.add_side_condition(1 - s.0, "stealthrock", None, None); } RV::Undef });
    h!(r, Move, "struggle", "onModifyMove", |b, a| { let am = a.am(); b.amm(am).mtype = "???"; RV::Undef });
    h!(r, Move, "lastresort", "onTry", |b, a| {
        let s = a.t(); let p = b.p(s); if p.move_slots.len() < 2 { return RV::B(false); }
        let mut has = false; for sl in &p.move_slots { if sl.id == "lastresort" { has = true; continue; } if !sl.used { return RV::B(false); } }
        RV::B(has) });
    // ---------- type / power / targeting changes ----------
    h!(r, Move, "weatherball", "onModifyType", |b, a| {
        let m = a.t(); let am = a.am(); let w = b.pokemon_effective_weather(m, None);
        let t = match w { "sunnyday" | "desolateland" => "Fire", "raindance" | "primordialsea" => "Water", "sandstorm" => "Rock", "hail" | "snowscape" => "Ice", _ => "" };
        if !t.is_empty() { b.amm(am).mtype = t; } RV::Undef });
    h!(r, Move, "weatherball", "onModifyMove", |b, a| {
        let m = a.t(); let am = a.am(); let w = b.pokemon_effective_weather(m, None);
        if ["sunnyday", "desolateland", "raindance", "primordialsea", "sandstorm", "hail", "snowscape"].contains(&w) { b.amm(am).base_power *= 2.0; } RV::Undef });
    h!(r, Move, "terrainpulse", "onModifyType", |b, a| {
        let m = a.t(); let am = a.am(); if b.is_grounded(m, false) != Some(true) { return RV::Undef; }
        let t = match b.field.terrain { "electricterrain" => "Electric", "grassyterrain" => "Grass", "mistyterrain" => "Fairy", "psychicterrain" => "Psychic", _ => "" };
        if !t.is_empty() { b.amm(am).mtype = t; } RV::Undef });
    h!(r, Move, "terrainpulse", "onModifyMove", |b, a| { let m = a.t(); let am = a.am(); if !b.field.terrain.is_empty() && b.is_grounded(m, false) == Some(true) { b.amm(am).base_power *= 2.0; } RV::Undef });
    h!(r, Move, "expandingforce", "onBasePower", |b, a| { let m = a.t(); if b.is_terrain("psychicterrain") && b.is_grounded(m, false) == Some(true) { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Move, "expandingforce", "onModifyMove", |b, a| { let m = a.t(); let am = a.am(); if b.is_terrain("psychicterrain") && b.is_grounded(m, false) == Some(true) { b.amm(am).target = "allAdjacentFoes"; } RV::Undef });
    h!(r, Move, "hurricane", "onModifyMove", |b, a| {
        let am = a.am(); let w = a.source.map(|t| b.pokemon_effective_weather(t, None)).unwrap_or("");
        match w { "raindance" | "primordialsea" => b.amm(am).accuracy = None, "sunnyday" | "desolateland" => b.amm(am).accuracy = Some(50.0), _ => {} } RV::Undef });
    h!(r, Move, "thunder", "onModifyMove", |b, a| {
        let am = a.am(); let w = a.source.map(|t| b.pokemon_effective_weather(t, None)).unwrap_or("");
        match w { "raindance" | "primordialsea" => b.amm(am).accuracy = None, "sunnyday" | "desolateland" => b.amm(am).accuracy = Some(50.0), _ => {} } RV::Undef });
    h!(r, Move, "blizzard", "onModifyMove", |b, a| { let w = b.effective_weather(); if w == "hail" || w == "snowscape" { let am = a.am(); b.amm(am).accuracy = None; } RV::Undef });
    h!(r, Move, "freezedry", "onEffectiveness", |b, a| { if b.eff_type == "Water" { return RV::N(1.0); } RV::Undef });
    // Flying Press (2026-10-13, v29: the Eval bar's unsupported list): its Fighting effectiveness plus Flying's against each type
    h!(r, Move, "flyingpress", "onEffectiveness", |b, a| { RV::N(a.relay.num() + b.dex.effectiveness("Flying", b.eff_type) as f64) });
    h!(r, Move, "facade", "onBasePower", |b, a| { let m = a.t(); let st = b.p(m).status; if !st.is_empty() && st != "slp" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Move, "barbbarrage", "onBasePower", |b, a| { let t = a.s(); let st = b.p(t).status; if st == "psn" || st == "tox" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Move, "ficklebeam", "onBasePower", |b, a| { if b.rchance(3, 10) { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Move, "solarbeam", "onBasePower", |b, a| { let m = a.t(); let w = b.pokemon_effective_weather(m, None); if ["raindance", "primordialsea", "sandstorm", "hail", "snowscape"].contains(&w) { return b.cm(0.5, 1.0); } RV::Undef });
    h!(r, Move, "knockoff", "onBasePower", |b, a| {
        let t = a.s(); let item = b.p(t).item; let e = a.src_eff;
        if !b.single_event("TakeItem", Eff::new(Kind::Item, item), Some(SLoc::Item(t)), Tgt::Mon(t), Some(t), e, RV::S(if item.is_empty() { "$none" } else { item })).truthy() { return RV::Undef; }
        if !item.is_empty() { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Move, "knockoff", "onAfterHit", |b, a| { let t = a.t(); b.take_item(t, None); RV::Undef });
    h!(r, Move, "psychicfangs", "onTryHit", |b, a| { let t = a.t(); remove_screens(b, t); RV::Undef });
    h!(r, Move, "brickbreak", "onTryHit", |b, a| { let t = a.t(); remove_screens(b, t); RV::Undef });
    h!(r, Move, "ragingbull", "onTryHit", |b, a| { let t = a.t(); remove_screens(b, t); RV::Undef });
    h!(r, Move, "lowkick", "onTryHit", |b, a| { RV::Undef });
    h!(r, Move, "grassknot", "onTryHit", |b, a| { RV::Undef });
    h!(r, Move, "heavyslam", "onTryHit", |b, a| { RV::Undef });
    h!(r, Move, "poltergeist", "onTry", |b, a| { RV::B(a.source.map(|t| !b.p(t).item.is_empty()).unwrap_or(false)) });
    h!(r, Move, "poltergeist", "onTryHit", |b, a| { RV::Undef });
    h!(r, Move, "steelroller", "onTry", |b, a| { RV::B(!b.field.terrain.is_empty()) });
    h!(r, Move, "steelroller", "onHit", |b, a| { b.clear_terrain(); RV::Undef });
    h!(r, Move, "steelroller", "onAfterSubDamage", |b, a| { b.clear_terrain(); RV::Undef });
    h!(r, Move, "icespinner", "onAfterHit", |b, a| { b.clear_terrain(); RV::Undef });
    h!(r, Move, "icespinner", "onAfterSubDamage", |b, a| { if a.source.map(|s| b.p(s).hp > 0).unwrap_or(false) { b.clear_terrain(); } RV::Undef });
    h!(r, Move, "doubleshock", "onTryMove", |b, a| { let m = a.t(); if b.has_type(m, "Electric") { return RV::Undef; } RV::Null });
    h!(r, Move, "doubleshock", "self.onHit", |b, a| { let m = a.t(); let ty: Vec<Id> = b.p(m).types.iter().map(|t| if *t == "Electric" { "???" } else { *t }).collect(); let p = b.pm(m); p.types = ty; p.added_type = ""; RV::Undef });
    h!(r, Move, "direclaw", "secondaries.0.onHit", |b, a| { let (t, s) = (a.t(), a.s()); let st = ["psn", "par", "slp"][b.prng.sample_idx(3)]; b.try_set_status(t, st, Some(s), None); RV::Undef });
    h!(r, Move, "throatchop", "secondaries.0.onHit", |b, a| { let t = a.t(); b.add_volatile(t, "throatchop", None, None); RV::Undef });
    // ---------- two-turn moves ----------
    h!(r, Move, "electroshot", "onTryMove", |b, a| {
        let att = a.t(); let def = a.source; let e = a.src_eff.unwrap();
        if b.remove_volatile(att, e.id) { return RV::Undef; }
        b.boost(vec![(2, 1)], Some(att), Some(att), Some(e), false, false);
        let w = b.pokemon_effective_weather(att, None);
        if w == "raindance" || w == "primordialsea" { return RV::Undef; }
        if !b.run_event("ChargeMove", Tgt::Mon(att), def, Some(e), RV::Undef, false, false).truthy() { return RV::Undef; }
        b.add_volatile_src_eff(att, "twoturnmove", def, Some(e)); RV::Null });
    h!(r, Move, "solarbeam", "onTryMove", |b, a| {
        let att = a.t(); let def = a.source; let e = a.src_eff.unwrap();
        if b.remove_volatile(att, e.id) { return RV::Undef; }
        let w = b.pokemon_effective_weather(att, None);
        if w == "sunnyday" || w == "desolateland" { return RV::Undef; }
        if !b.run_event("ChargeMove", Tgt::Mon(att), def, Some(e), RV::Undef, false, false).truthy() { return RV::Undef; }
        b.add_volatile_src_eff(att, "twoturnmove", def, Some(e)); RV::Null });
    h!(r, Move, "phantomforce", "onTryMove", |b, a| {
        let att = a.t(); let def = a.source; let e = a.src_eff.unwrap();
        if b.remove_volatile(att, e.id) { return RV::Undef; }
        if !b.run_event("ChargeMove", Tgt::Mon(att), def, Some(e), RV::Undef, false, false).truthy() { return RV::Undef; }
        b.add_volatile_src_eff(att, "twoturnmove", def, Some(e)); RV::Null });
    // ---------- base power callbacks (target = defender, source = attacker) ----------
    h!(r, Move, "eruption", "basePowerCallback", |b, a| { let (s, am) = (a.s(), a.am()); let p = b.p(s); RV::N(b.am(am).base_power * p.hp as f64 / p.maxhp as f64) });
    h!(r, Move, "waterspout", "basePowerCallback", |b, a| { let (s, am) = (a.s(), a.am()); let p = b.p(s); RV::N(b.am(am).base_power * p.hp as f64 / p.maxhp as f64) });
    h!(r, Move, "lowkick", "basePowerCallback", |b, a| { let t = a.t(); let w = b.get_weight(t); RV::N(weight_bp(w)) });
    h!(r, Move, "grassknot", "basePowerCallback", |b, a| { let t = a.t(); let w = b.get_weight(t); RV::N(weight_bp(w)) });
    h!(r, Move, "heavyslam", "basePowerCallback", |b, a| {
        let (t, s) = (a.t(), a.s()); let tw = b.get_weight(t); let sw = b.get_weight(s);
        RV::N((if sw >= tw * 5 { 120 } else if sw >= tw * 4 { 100 } else if sw >= tw * 3 { 80 } else if sw >= tw * 2 { 60 } else { 40 }) as f64) });
    h!(r, Move, "lastrespects", "basePowerCallback", |b, a| { let s = a.s(); RV::N(50.0 + 50.0 * b.sides[s.0 as usize].total_fainted as f64) });
    h!(r, Move, "ragefist", "basePowerCallback", |b, a| { let s = a.s(); RV::N((50 + 50 * b.p(s).times_attacked).min(350) as f64) });
    h!(r, Move, "powertrip", "basePowerCallback", |b, a| { let (s, am) = (a.s(), a.am()); RV::N(b.am(am).base_power + 20.0 * b.positive_boosts(s) as f64) });
    h!(r, Move, "tripleaxel", "basePowerCallback", |b, a| { RV::N(20.0 * b.am(a.am()).hit as f64) });
    h!(r, Move, "acrobatics", "basePowerCallback", |b, a| { let (s, am) = (a.s(), a.am()); let bp = b.am(am).base_power; RV::N(if b.p(s).item.is_empty() { bp * 2.0 } else { bp }) });
    h!(r, Move, "stompingtantrum", "basePowerCallback", |b, a| { let (s, am) = (a.s(), a.am()); let bp = b.am(am).base_power; RV::N(if b.p(s).move_last_turn_result == Tri::B(false) { bp * 2.0 } else { bp }) });
    h!(r, Move, "assurance", "basePowerCallback", |b, a| { let (t, am) = (a.t(), a.am()); let bp = b.am(am).base_power; RV::N(if b.p(t).hurt_this_turn.map(|x| x != 0).unwrap_or(false) { bp * 2.0 } else { bp }) });
    h!(r, Move, "payback", "basePowerCallback", |b, a| { let (t, am) = (a.t(), a.am()); let bp = b.am(am).base_power; RV::N(if b.p(t).newly_switched || b.will_move(t).is_some() { bp } else { bp * 2.0 }) });
    h!(r, Move, "risingvoltage", "basePowerCallback", |b, a| { let (t, am) = (a.t(), a.am()); let bp = b.am(am).base_power; RV::N(if b.is_terrain("electricterrain") && b.is_grounded(t, false) == Some(true) { bp * 2.0 } else { bp }) });
    h!(r, Move, "round", "basePowerCallback", |b, a| { let am = a.am(); let bp = b.am(am).base_power; RV::N(if b.am(am).source_effect == Some("round") { bp * 2.0 } else { bp }) });
    h!(r, Move, "hardpress", "basePowerCallback", |b, a| {
        let t = a.t(); let p = b.p(t);
        let x = ((p.hp * 4096) as f64 / p.maxhp as f64).floor();
        let bp = (((100.0 * (100.0 * x) + 2048.0 - 1.0) / 4096.0).floor() / 100.0).floor();
        RV::N(if bp == 0.0 { 1.0 } else { bp }) });
    // 2026-10-09: Metal Burst (the last foe that damaged the user this turn), Mortal Spin
    h!(r, Move, "metalburst", "damageCallback", |b, a| { let s = a.s(); match last_damaged_by(b, s) { Some(x) => RV::N((x.damage as f64 * 1.5).max(1.0)), None => RV::N(0.0) } });
    h!(r, Move, "metalburst", "onTry", |b, a| { let s = a.t(); RV::B(last_damaged_by(b, s).map(|x| x.this_turn).unwrap_or(false)) });
    h!(r, Move, "metalburst", "onModifyTarget", |b, a| { let s = a.t(); if let Some(x) = last_damaged_by(b, s) { if let Some(t) = at_slot(b, x.slot) { return RV::Target(Some(t)); } } RV::Undef });
    h!(r, Move, "mortalspin", "onAfterHit", |b, a| { let s = a.s(); let am = a.am(); if !b.am(am).has_sheer_force { mortal_spin_clear(b, s); } RV::Undef });
    h!(r, Move, "mortalspin", "onAfterSubDamage", |b, a| { let s = a.s(); let am = a.am(); if !b.am(am).has_sheer_force && b.p(s).hp > 0 { mortal_spin_clear(b, s); } RV::Undef });
    h!(r, Move, "hex", "basePowerCallback", |b, a| { let t = a.t(); let bp = b.am(a.am()).base_power; if !b.p(t).status.is_empty() || b.has_ability(t, "comatose") { return RV::N(bp * 2.0); } RV::N(bp) });
    h!(r, Move, "rest", "onTry", |b, a| { let m = a.t();
        if b.p(m).status == "slp" || b.has_ability(m, "comatose") { return RV::B(false); }
        if b.p(m).hp == b.p(m).maxhp { let n = b.mon_name(m); b.add(&["-fail", &n, "heal"]); return RV::Null; }
        if b.has_ability(m, "insomnia") || b.has_ability(m, "vitalspirit") { let n = b.mon_name(m); b.add(&["-fail", &n]); return RV::Null; } RV::Undef });
    h!(r, Move, "rest", "onHit", |b, a| { let t = a.t(); let s = a.source; let e = a.src_eff;
        let r = b.set_status(t, "slp", s, e, false); if !r.truthy() { return r; }
        b.pm(t).status_state.set("time", SV::N(3.0)); b.pm(t).status_state.set("startTime", SV::N(3.0));
        let mx = b.p(t).maxhp as f64; b.heal(mx, None, None, None); RV::Undef });
    // 2026-10-09, batch 3
    h!(r, Move, "entrainment", "onTryHit", |b, a| { let t = a.t(); let Some(s) = a.source else { return RV::Undef }; if t == s { return RV::B(false); }
        let (ta, sa) = (b.p(t).ability, b.p(s).ability);
        if ta == sa || b.dex.eff(Kind::Ability, ta).cantsuppress || ta == "truant" || b.dex.eff(Kind::Ability, sa).flag("noentrain") { return RV::B(false); } RV::Undef });
    h!(r, Move, "entrainment", "onHit", |b, a| { let t = a.t(); let Some(s) = a.source else { return RV::Undef }; let sa = b.p(s).ability; if !b.set_ability(t, sa, Some(s), None, false) { return RV::B(false); } RV::Undef });
    h!(r, Move, "temperflare", "basePowerCallback", |b, a| { let s = a.s(); let bp = b.am(a.am()).base_power; if b.p(s).move_last_turn_result == Tri::B(false) { return RV::N(bp * 2.0); } RV::N(bp) });
    h!(r, Move, "shellsidearm", "onPrepareHit", |b, a| { RV::Undef });
    h!(r, Move, "shellsidearm", "onModifyMove", |b, a| { let m = a.t(); let Some(t) = a.source else { return RV::Undef }; let am = a.am();
        let (atk, spa) = (b.get_stat_simple(m, 1, false, true), b.get_stat_simple(m, 3, false, true)); let (def, spd) = (b.get_stat_simple(t, 2, false, true), b.get_stat_simple(t, 4, false, true));
        let lv = b.p(m).level; let base = 2 * lv / 5 + 2;
        let physical = ((base * 90 * atk) / def) / 50; let special = ((base * 90 * spa) / spd) / 50;
        if physical > special || (physical == special && b.rchance(1, 2)) { b.amm(am).category = "Physical"; if !b.am(am).flags.contains(&"contact") { b.amm(am).flags.push("contact"); } } RV::Undef });
    h!(r, Move, "shellsidearm", "onHit", |b, a| { RV::Undef });
    h!(r, Move, "shellsidearm", "onAfterSubDamage", |b, a| { RV::Undef });
    h!(r, Move, "batonpass", "onHit", |b, a| { let t = a.t(); if b.can_switch(t.0) == 0 || b.has_vol(t, "commanded") { let n = b.mon_name(t); b.add(&["-fail", &n]); return RV::NotFail; } RV::Undef });
    h!(r, Move, "allyswitch", "onPrepareHit", |b, a| { let m = a.t(); b.add_volatile(m, "allyswitch", None, None) });
    h!(r, Move, "allyswitch", "onHit", |b, a| { let m = a.t(); let pos = b.p(m).position; let np = if pos == 0 { 1 } else { 0 };
        let ok = b.sides[m.0 as usize].active[np as usize].map(|i| !b.p((m.0, i)).fainted).unwrap_or(false);
        if !ok { let n = b.mon_name(m); b.add(&["-fail", &n, "move: Ally Switch"]); return RV::NotFail; }
        b.swap_position(m, np); RV::Undef });
    h!(r, Move, "superfang", "damageCallback", |b, a| { let t = a.t(); RV::N((b.p(t).hp as f64 / 2.0).floor().max(1.0)) });
    h!(r, Move, "finalgambit", "damageCallback", |b, a| { let s = a.s(); let d = b.p(s).hp; b.faint(s, None, None); RV::N(d as f64) });
}

impl Battle {
    /// addVolatile(id, source, sourceEffect) where the handler passes a source explicitly (pokemon.addVolatile('twoturnmove', defender))
    pub fn add_volatile_src_eff(&mut self, m: MonRef, v: &str, source: Option<MonRef>, eff: Option<Eff>) -> RV { self.add_volatile(m, v, source, eff) }
}
