//! Conditions: statuses, volatiles, side conditions, weather, terrain, pseudo-weather (data/conditions.ts + move conditions).
use super::Reg;
use crate::battle::*;
use crate::dex::*;
use crate::h;
use crate::state::*;

/// Showdown's protect-family onTryHit core: returns Some(NOT_FAIL) when the hit is blocked
fn protect_block(b: &mut Battle, a: &HArgs, block_status: bool) -> bool {
    let (t, s, am) = (a.t(), a.s(), a.am());
    if b.bypasses_protect(am, s, t, block_status) { return false; }
    if b.am(am).smart_target.unwrap_or(false) { b.amm(am).smart_target = Some(false); } else { let n = b.mon_name(t); b.add(&["-activate", &n, "move: Protect"]); }
    if let Some(l) = find(&b.p(s).volatiles, "lockedmove") { if l.duration == Some(2) { b.pm(s).volatiles.retain(|(k, _)| *k != "lockedmove"); } }
    true
}
fn status_start(b: &mut Battle, a: &HArgs, st: &str) { let n = b.mon_name(a.t()); b.add(&["-status", &n, st]); }
impl Battle {
    pub fn es_side(&self) -> u8 { match self.effect_state { SLoc::SideC(s, _) | SLoc::Slot(s, _, _) => s, _ => panic!("effect state is not a side condition") } }
    pub fn get_at_slot(&self, slot: &str) -> Option<MonRef> {
        let s = slot.as_bytes(); if s.len() < 3 { return None; }
        let side = (s[1] - b'1') as usize; let pos = (s[2] - b'a') as usize;
        self.sides.get(side).and_then(|x| x.active.get(pos).copied().flatten()).map(|i| (side as u8, i))
    }
    pub fn will_move(&self, m: MonRef) -> Option<usize> {
        if self.p(m).fainted { return None; }
        self.queue.iter().position(|q| q.choice == Choice::Move && q.pokemon == Some(m))
    }
    /// screens: the defender is on the screen's side, not hit by itself, not a crit, not infiltrating
    fn screen_applies(&mut self, a: &HArgs, cat: &str) -> bool {
        let (atk, def) = (a.t(), a.s()); let am = a.am();
        if atk == def || def.0 != self.es_side() || self.dex.mv(self.am(am).id).tmpl.category != cat { return false; }
        let slot = self.slot_name(def);
        !self.amm(am).hd(slot).crit && !self.am(am).infiltrates
    }
}

pub fn register(r: &mut Reg) {
    // ---------- statuses ----------
    h!(r, Cond, "brn", "onStart", |b, a| { status_start(b, a, "brn"); RV::Undef });
    h!(r, Cond, "brn", "onResidual", |b, a| { let m = a.t(); let d = b.p(m).base_maxhp as f64 / 16.0; b.damage(d, None, None, None, false); RV::Undef });
    h!(r, Cond, "psn", "onStart", |b, a| { status_start(b, a, "psn"); RV::Undef });
    h!(r, Cond, "psn", "onResidual", |b, a| { let m = a.t(); let d = b.p(m).base_maxhp as f64 / 8.0; b.damage(d, None, None, None, false); RV::Undef });
    h!(r, Cond, "tox", "onStart", |b, a| { b.es().set("stage", SV::N(0.0)); status_start(b, a, "tox"); RV::Undef });
    h!(r, Cond, "tox", "onSwitchIn", |b, a| { b.es().set("stage", SV::N(0.0)); RV::Undef });
    h!(r, Cond, "tox", "onResidual", |b, a| {
        let m = a.t();
        let st = b.es().n("stage").unwrap_or(0.0); if st < 15.0 { b.es().set("stage", SV::N(st + 1.0)); }
        let stage = b.es().n("stage").unwrap_or(0.0);
        let per = (b.p(m).base_maxhp as f64 / 16.0).floor().max(1.0);   // clampIntRange(baseMaxhp / 16, 1)
        b.damage(per * stage, None, None, None, false); RV::Undef });
    h!(r, Cond, "par", "onStart", |b, a| { status_start(b, a, "par"); RV::Undef });
    h!(r, Cond, "par", "onModifySpe", |b, a| {
        let m = a.t(); let mut spe = b.modify(a.n(), b.event.as_ref().unwrap().modifier);
        b.event.as_mut().unwrap().modifier = 1.0;
        if !b.has_ability(m, "quickfeet") { spe = (spe as f64 * 50.0 / 100.0).floor() as i64; }
        RV::N(spe as f64) });
    h!(r, Cond, "par", "onBeforeMove", |b, a| { if b.rchance(1, 8) { let n = b.mon_name(a.t()); b.add(&["cant", &n, "par"]); return RV::B(false); } RV::Undef });
    h!(r, Cond, "slp", "onStart", |b, a| {
        status_start(b, a, "slp");
        let tbl = [2.0, 3.0, 3.0]; let i = b.prng.sample_idx(3);
        b.es().set("startTime", SV::N(tbl[i])); b.es().set("time", SV::N(tbl[i]));
        let m = a.t(); b.remove_volatile(m, "nightmare"); RV::Undef });
    h!(r, Cond, "slp", "onBeforeMove", |b, a| {
        let m = a.t(); let am = a.am();
        if b.has_ability(m, "earlybird") { let t = b.pm(m).status_state.n("time").unwrap_or(0.0); b.pm(m).status_state.set("time", SV::N(t - 1.0)); }
        let t = b.pm(m).status_state.n("time").unwrap_or(0.0) - 1.0; b.pm(m).status_state.set("time", SV::N(t));
        if t <= 0.0 { b.cure_status(m); return RV::Undef; }
        let n = b.mon_name(m); b.add(&["cant", &n, "slp"]);
        if b.am(am).sleep_usable { return RV::Undef; }
        RV::B(false) });
    h!(r, Cond, "frz", "onStart", |b, a| { status_start(b, a, "frz"); b.es().set("startTime", SV::N(3.0)); b.es().set("time", SV::N(3.0)); RV::Undef });
    h!(r, Cond, "frz", "onBeforeMove", |b, a| {
        let m = a.t(); let am = a.am();
        if b.am(am).flag("defrost") { return RV::Undef; }
        let t = b.pm(m).status_state.n("time").unwrap_or(0.0) - 1.0; b.pm(m).status_state.set("time", SV::N(t));
        if t <= 0.0 || b.rchance(1, 4) { b.cure_status(m); return RV::Undef; }
        let n = b.mon_name(m); b.add(&["cant", &n, "frz"]); RV::B(false) });
    h!(r, Cond, "frz", "onModifyMove", |b, a| { let m = a.t(); let am = a.am(); if b.am(am).flag("defrost") { b.set_status(m, "", None, None, false); } RV::Undef });
    h!(r, Cond, "frz", "onAfterMoveSecondary", |b, a| { let am = a.am(); if b.am(am).thaws_target { let m = a.t(); b.cure_status(m); } RV::Undef });
    h!(r, Cond, "frz", "onDamagingHit", |b, a| { let am = a.am(); let mv = b.am(am); if mv.mtype == "Fire" && mv.category != "Status" && mv.id != "polarflare" { let m = a.t(); b.cure_status(m); } RV::Undef });

    // ---------- volatiles ----------
    h!(r, Cond, "confusion", "onStart", |b, a| {
        let min = if a.src_eff.map(|e| e.id) == Some("axekick") { 3 } else { 2 };
        let t = b.prng.range(min, 6); b.es().set("time", SV::N(t as f64)); RV::Undef });
    h!(r, Cond, "confusion", "onEnd", |b, a| { RV::Undef });
    h!(r, Cond, "confusion", "onBeforeMove", |b, a| {
        let m = a.t();
        let t = find(&b.p(m).volatiles, "confusion").and_then(|s| s.n("time")).unwrap_or(0.0) - 1.0;
        if let Some(s) = find_mut(&mut b.pm(m).volatiles, "confusion") { s.set("time", SV::N(t)); }
        if t == 0.0 { b.remove_volatile(m, "confusion"); return RV::Undef; }
        if !b.rchance(33, 100) { return RV::Undef; }
        b.active_target = Some(m);
        let d = b.confusion_damage(m, 40);
        b.damage(d as f64, Some(m), Some(m), Some(Eff::cond(id("confused"))), false); RV::B(false) });
    h!(r, Cond, "flinch", "onBeforeMove", |b, a| { let m = a.t(); let n = b.mon_name(m); b.add(&["cant", &n, "flinch"]); b.run_event("Flinch", Tgt::Mon(m), None, None, RV::Undef, false, false); RV::B(false) });
    h!(r, Cond, "choicelock", "onStart", |b, a| {
        let Some(am) = b.active_move else { return RV::B(false) };
        let mv = b.am(am); if mv.id.is_empty() || mv.has_bounced || mv.source_effect == Some("snatch") { return RV::B(false); }
        let i = mv.id; b.es().set("move", SV::S(i)); RV::Undef });
    h!(r, Cond, "choicelock", "onBeforeMove", |b, a| {
        let m = a.t(); let am = a.am();
        if !b.item_data(m).b("isChoice") { b.remove_volatile(m, "choicelock"); return RV::Undef; }
        let lock = b.es().get("move").and_then(|v| v.s());
        if !b.ignoring_item(m) && Some(b.am(am).id) != lock && b.am(am).id != "struggle" { let n = b.mon_name(m); b.add(&["-fail", &n]); return RV::B(false); }
        RV::Undef });
    h!(r, Cond, "choicelock", "onDisableMove", |b, a| {
        let m = a.t(); let lock = b.es().get("move").and_then(|v| v.s());
        if !b.item_data(m).b("isChoice") || !lock.map(|l| b.p(m).move_slots.iter().any(|s| s.id == l)).unwrap_or(false) { b.remove_volatile(m, "choicelock"); return RV::Undef; }
        if b.ignoring_item(m) { return RV::Undef; }
        let ids: Vec<Id> = b.p(m).move_slots.iter().map(|s| s.id).collect();
        for i in ids { if Some(i) != lock { b.disable_move(m, i, false, "choicelock"); } }
        RV::Undef });
    h!(r, Cond, "stall", "onStart", |b, a| { b.es().set("counter", SV::N(3.0)); RV::Undef });
    h!(r, Cond, "stall", "onStallMove", |b, a| {
        let m = a.t(); let c = b.es().n("counter").filter(|x| *x != 0.0).unwrap_or(1.0);
        let ok = b.rchance(1, c as i64);
        if !ok { b.pm(m).volatiles.retain(|(k, _)| *k != "stall"); }
        RV::B(ok) });
    h!(r, Cond, "stall", "onRestart", |b, a| {
        let cmax = b.dex.conds["stall"].n("counterMax").unwrap_or(729.0);
        let c = b.es().n("counter").unwrap_or(1.0); if c < cmax { b.es().set("counter", SV::N(c * 3.0)); }
        b.es().duration = Some(2); RV::Undef });
    h!(r, Cond, "protect", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "protect", "onTryHit", |b, a| { if protect_block(b, a, true) { RV::NotFail } else { RV::Undef } });
    h!(r, Cond, "spikyshield", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "spikyshield", "onTryHit", |b, a| {
        if !protect_block(b, a, true) { return RV::Undef; }
        let (t, s) = (a.t(), a.s()); if b.makes_contact(a.am(), s) { let d = b.p(s).base_maxhp as f64 / 8.0; b.damage(d, Some(s), Some(t), None, false); }
        RV::NotFail });
    h!(r, Cond, "spikyshield", "onHit", |b, a| { RV::Undef });
    h!(r, Cond, "banefulbunker", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "banefulbunker", "onTryHit", |b, a| {
        if !protect_block(b, a, true) { return RV::Undef; }
        let (t, s) = (a.t(), a.s()); if b.makes_contact(a.am(), s) { b.try_set_status(s, "psn", Some(t), None); }
        RV::NotFail });
    h!(r, Cond, "banefulbunker", "onHit", |b, a| { RV::Undef });
    h!(r, Cond, "kingsshield", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "kingsshield", "onTryHit", |b, a| {
        if !protect_block(b, a, false) { return RV::Undef; }
        let (t, s) = (a.t(), a.s());
        if b.makes_contact(a.am(), s) { let ks = b.new_am(b.dex.active_move("kingsshield")); b.boost(vec![(0, -1)], Some(s), Some(t), Some(Eff::mv(id("kingsshield"), ks)), false, false); }
        RV::NotFail });
    h!(r, Cond, "kingsshield", "onHit", |b, a| { RV::Undef });
    h!(r, Cond, "helpinghand", "onStart", |b, a| { b.es().set("multiplier", SV::N(1.5)); RV::Undef });
    h!(r, Cond, "helpinghand", "onRestart", |b, a| { let m = b.es().n("multiplier").unwrap_or(1.5); b.es().set("multiplier", SV::N(m * 1.5)); RV::Undef });
    h!(r, Cond, "helpinghand", "onBasePower", |b, a| { let m = b.es().n("multiplier").unwrap_or(1.5); b.cm(m, 1.0) });
    h!(r, Cond, "followme", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "followme", "onFoeRedirectTarget", |b, a| {
        let user = b.holder(); let src = a.s(); let am = a.am();
        if !b.is_sky_dropped(user) && b.valid_target(user, src, b.am(am).target) {
            if b.am(am).smart_target.unwrap_or(false) { b.amm(am).smart_target = Some(false); }
            return RV::M(user);
        }
        RV::Undef });
    h!(r, Cond, "ragepowder", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "ragepowder", "onFoeRedirectTarget", |b, a| {
        let user = b.holder(); let src = a.s(); let am = a.am();
        if b.is_sky_dropped(user) { return RV::Undef; }
        if b.run_status_immunity(src, "powder", false) && b.valid_target(user, src, b.am(am).target) {
            if b.am(am).smart_target.unwrap_or(false) { b.amm(am).smart_target = Some(false); }
            return RV::M(user);
        }
        RV::Undef });
    h!(r, Cond, "lockedmove", "onStart", |b, a| { let t = b.prng.range(2, 4); b.es().set("trueDuration", SV::N(t as f64)); let mv = a.src_eff.unwrap().id; b.es().set("move", SV::S(mv)); RV::Undef });
    h!(r, Cond, "lockedmove", "onRestart", |b, a| { if b.es().n("trueDuration").unwrap_or(0.0) >= 2.0 { b.es().duration = Some(2); } RV::Undef });
    h!(r, Cond, "lockedmove", "onResidual", |b, a| {
        let m = a.t(); if b.p(m).status == "slp" { b.pm(m).volatiles.retain(|(k, _)| *k != "lockedmove"); }
        if let Some(s) = b.state_mut(b.effect_state) { let t = s.n("trueDuration").unwrap_or(0.0); s.set("trueDuration", SV::N(t - 1.0)); }
        RV::Undef });
    h!(r, Cond, "lockedmove", "onAfterMove", |b, a| { if b.es().duration == Some(1) { let m = a.t(); b.remove_volatile(m, "lockedmove"); } RV::Undef });
    h!(r, Cond, "lockedmove", "onEnd", |b, a| { if b.es().n("trueDuration").unwrap_or(0.0) > 1.0 { return RV::Undef; } let m = a.t(); b.add_volatile(m, "confusion", None, None); RV::Undef });
    h!(r, Cond, "lockedmove", "onLockMove", |b, a| { match b.es().get("move").and_then(|v| v.s()) { Some(s) => RV::S(s), None => RV::Undef } });
    h!(r, Cond, "mustrecharge", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "mustrecharge", "onBeforeMove", |b, a| { let m = a.t(); b.remove_volatile(m, "mustrecharge"); b.remove_volatile(m, "truant"); RV::Null });
    h!(r, Cond, "twoturnmove", "onStart", |b, a| {
        let att = a.t(); let def = a.s(); let e = a.src_eff.unwrap();
        b.es().set("move", SV::S(e.id));
        b.add_volatile(att, e.id, None, None);
        let mut tloc = b.p(att).last_move_target_loc.unwrap_or(0);
        if let Some(am) = e.am { if b.am(am).source_effect.is_some() && b.dex.mv(e.id).tmpl.target != "self" {
            let mut d = def;
            if b.p(d).fainted { let foes = b.foes_all(att); let i = b.prng.sample_idx(foes.len()); d = foes[i]; }
            tloc = b.get_loc_of(att, d);
        } }
        if let Some(s) = find_mut(&mut b.pm(att).volatiles, e.id) { s.set("targetLoc", SV::N(tloc as f64)); }
        b.run_event("PrepareHit", Tgt::Mon(att), Some(def), Some(e), RV::Undef, false, false);
        RV::Undef });
    h!(r, Cond, "twoturnmove", "onEnd", |b, a| { let mv = b.es().get("move").and_then(|v| v.s()); if let Some(mv) = mv { let m = a.t(); b.remove_volatile(m, mv); } RV::Undef });
    h!(r, Cond, "twoturnmove", "onLockMove", |b, a| { match b.es().get("move").and_then(|v| v.s()) { Some(s) => RV::S(s), None => RV::Undef } });
    h!(r, Cond, "twoturnmove", "onMoveAborted", |b, a| { let m = a.t(); b.remove_volatile(m, "twoturnmove"); RV::Undef });
    h!(r, Cond, "throatchop", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "throatchop", "onEnd", |b, a| { RV::Undef });
    h!(r, Cond, "throatchop", "onDisableMove", |b, a| {
        let m = a.t(); let ids: Vec<Id> = b.p(m).move_slots.iter().map(|s| s.id).collect();
        for i in ids { if b.dex.mv(i).tmpl.flag("sound") { b.disable_move(m, i, false, "throatchop"); } }
        RV::Undef });
    h!(r, Cond, "throatchop", "onBeforeMove", |b, a| { if b.am(a.am()).flag("sound") { return RV::B(false); } RV::Undef });
    h!(r, Cond, "throatchop", "onModifyMove", |b, a| { if b.am(a.am()).flag("sound") { return RV::B(false); } RV::Undef });
    h!(r, Cond, "taunt", "onStart", |b, a| {
        let m = a.t(); if b.p(m).active_turns != 0 && b.will_move(m).is_none() { let d = b.es().duration.unwrap_or(0); b.es().duration = Some(d + 1); }
        RV::Undef });
    h!(r, Cond, "taunt", "onEnd", |b, a| { RV::Undef });
    h!(r, Cond, "taunt", "onDisableMove", |b, a| {
        let m = a.t(); let ids: Vec<Id> = b.p(m).move_slots.iter().map(|s| s.id).collect();
        for i in ids { if b.dex.mv(i).tmpl.category == "Status" && i != "mefirst" { b.disable_move(m, i, false, "taunt"); } }
        RV::Undef });
    h!(r, Cond, "taunt", "onBeforeMove", |b, a| { let mv = b.am(a.am()); if mv.category == "Status" && mv.id != "mefirst" { return RV::B(false); } RV::Undef });
    h!(r, Cond, "encore", "onStart", |b, a| {
        let m = a.t();
        let Some(lm) = b.p(m).last_move else { return RV::B(false) };
        let slot_ok = b.p(m).move_slots.iter().any(|s| s.id == lm && s.pp > 0);
        let md = &b.dex.mv(lm).tmpl;
        if md.is_z || md.is_max || md.flag("failencore") || !slot_ok { return RV::B(false); }
        b.es().set("move", SV::S(lm));
        match b.will_move(m) {
            None => { let d = b.es().duration.unwrap_or(0); b.es().duration = Some(d + 1); }
            Some(qi) => {
                let cur = b.am(b.queue[qi].am.unwrap()).id;
                if cur != lm && !b.has_item(m, "mentalherb") {
                    let pr = b.queue[qi].priority - b.dex.mv(cur).tmpl.priority + b.dex.mv(lm).tmpl.priority;
                    let order = b.queue[qi].order;
                    b.queue.retain(|q| q.pokemon != Some(m));
                    let am = b.new_am(b.dex.active_move(lm));
                    let mut act = crate::sim::simple_action(Choice::Move, order); act.pokemon = Some(m); act.am = Some(am);
                    let acts = b.resolve_action(act, false);
                    b.insert_actions(acts);
                    if let Some(qi) = b.will_move(m) { b.queue[qi].priority = pr; }
                }
            }
        }
        RV::Undef });
    h!(r, Cond, "encore", "onOverrideAction", |b, a| { let mv = b.es().get("move").and_then(|v| v.s()); if let Some(mv) = mv { if mv != b.am(a.am()).id { return RV::S(mv); } } RV::Undef });
    h!(r, Cond, "encore", "onResidual", |b, a| {
        let m = a.t(); let mv = b.es().get("move").and_then(|v| v.s());
        if !mv.map(|x| b.p(m).move_slots.iter().any(|s| s.id == x && s.pp > 0)).unwrap_or(false) { b.remove_volatile(m, "encore"); }
        RV::Undef });
    h!(r, Cond, "encore", "onEnd", |b, a| { RV::Undef });
    h!(r, Cond, "encore", "onDisableMove", |b, a| {
        let m = a.t(); let Some(mv) = b.es().get("move").and_then(|v| v.s()) else { return RV::Undef };
        if !b.p(m).move_slots.iter().any(|s| s.id == mv) { return RV::Undef; }
        let ids: Vec<Id> = b.p(m).move_slots.iter().map(|s| s.id).collect();
        for i in ids { if i != mv { b.disable_move(m, i, false, "encore"); } }
        RV::Undef });
    h!(r, Cond, "disable", "onStart", |b, a| {
        let m = a.t();
        if b.will_move(m).is_some() || (b.active_pokemon == Some(m) && b.active_move.map(|x| !b.am(x).is_external).unwrap_or(false)) { let d = b.es().duration.unwrap_or(0); b.es().duration = Some(d - 1); }
        let Some(lm) = b.p(m).last_move else { return RV::B(false) };
        if b.p(m).move_slots.iter().any(|s| s.id == lm && s.pp == 0) { return RV::B(false); }
        b.es().set("move", SV::S(lm)); RV::Undef });
    h!(r, Cond, "disable", "onEnd", |b, a| { RV::Undef });
    h!(r, Cond, "disable", "onBeforeMove", |b, a| { let mv = b.am(a.am()); if Some(mv.id) == b.es_ref().and_then(|s| s.get("move")).and_then(|v| v.s()) && !mv.flag("cantusetwice") { return RV::B(false); } RV::Undef });
    h!(r, Cond, "disable", "onDisableMove", |b, a| { let m = a.t(); if let Some(mv) = b.es().get("move").and_then(|v| v.s()) { b.disable_move(m, mv, false, "disable"); } RV::Undef });
    h!(r, Cond, "imprison", "onStart", |b, a| { RV::Undef });
    // the source is always the Imprison user, which holds the volatile (target self), so the holder is used: a position rebuilt from a
    // log gave it the opposing active as its source (2026-10-13: the bot planned on an Imprisoned Protect and Trick Room)
    h!(r, Cond, "imprison", "onFoeDisableMove", |b, a| {
        let m = a.t(); let src = b.holder();
        let ids: Vec<Id> = b.p(src).move_slots.iter().map(|s| s.id).collect();
        for i in ids { if i != "struggle" { b.disable_move(m, i, true, "imprison"); } }
        b.pm(m).maybe_disabled = true; RV::Undef });
    h!(r, Cond, "imprison", "onFoeBeforeMove", |b, a| {
        let mv = b.am(a.am()).id; let src = b.holder();
        if mv != "struggle" && b.p(src).move_slots.iter().any(|s| s.id == mv) { return RV::B(false); } RV::Undef });
    // 2026-10-09: slot conditions (sim.rs add_slot_condition): Wish heals whoever is in the user's slot at the end of the next turn,
    // Healing Wish the next Pokemon to come into the slot
    h!(r, Cond, "wish", "onStart", |b, a| { let Some(src) = a.source else { return RV::Undef }; let hp = b.p(src).maxhp as f64 / 2.0; let t0 = b.turn - 1; b.es().set("hp", SV::N(hp)); b.es().set("startingTurn", SV::N(t0.min(255) as f64)); RV::Undef });
    h!(r, Cond, "wish", "onResidual", |b, a| {
        let t0 = b.es().n("startingTurn").unwrap_or(0.0); if ((b.turn - 1).min(255) as f64) <= t0 { return RV::Undef; }
        let Some(slot) = b.es().source_slot else { return RV::Undef };
        let bs = slot.as_bytes(); let s = (bs[1] - b'1') as u8; let pos = (bs[2] - b'a') as u8;
        b.remove_slot_condition(s, pos, "wish"); RV::Undef });
    h!(r, Cond, "wish", "onEnd", |b, a| { let Some(t) = a.target.mon() else { return RV::Undef }; if !b.p(t).fainted { let hp = b.es().n("hp").unwrap_or(0.0); b.heal(hp, Some(t), Some(t), None); } RV::Undef });
    h!(r, Cond, "healingwish", "onSwitchIn", |b, a| { let t = a.t(); let pos = b.p(t).position; b.single_event("Swap", Eff::cond("healingwish"), Some(SLoc::Slot(t.0, pos, "healingwish")), Tgt::Mon(t), None, None, RV::Undef); RV::Undef });
    h!(r, Cond, "healingwish", "onSwap", |b, a| { let t = a.t();
        if !b.p(t).fainted && (b.p(t).hp < b.p(t).maxhp || !b.p(t).status.is_empty()) {
            let mx = b.p(t).maxhp as f64; b.pokemon_heal(t, mx); let p = b.pm(t); p.status = ""; p.status_state = EState::default();
            if b.logging { let n = b.mon_name(t); let p = b.p(t); let hp = format!("{}/{}", p.hp, p.maxhp); b.add(&["-heal", &n, &hp, "[from] move: Healing Wish"]); }
            let pos = b.p(t).position; b.remove_slot_condition(t.0, pos, "healingwish");
        } RV::Undef });
    h!(r, Cond, "saltcure", "onStart", |b, a| { RV::Undef });
    // Champions halves Salt Cure's residual: 1/8 for Water / Steel types, 1/16 otherwise (the base game's 1/4 and 1/8)
    h!(r, Cond, "saltcure", "onResidual", |b, a| { let m = a.t(); let div = if b.has_type(m, "Water") || b.has_type(m, "Steel") { 8.0 } else { 16.0 }; let d = b.p(m).base_maxhp as f64 / div; b.damage(d, None, None, None, false); RV::Undef });
    h!(r, Cond, "saltcure", "onEnd", |b, a| { RV::Undef });
    // 2026-10-09, batch 3: Gravity, Charge, Curse, Ally Switch's counter
    h!(r, Cond, "gravity", "durationCallback", |b, a| { RV::N(5.0) });
    h!(r, Cond, "gravity", "onFieldStart", |b, a| {
        let all: Vec<MonRef> = (0..2u8).flat_map(|s| b.side_active(s)).collect();
        for p in all {
            let fly = b.remove_volatile(p, "bounce") | b.remove_volatile(p, "fly");
            if fly { b.queue.retain(|q| !(q.pokemon == Some(p) && q.choice == Choice::Move)); b.remove_volatile(p, "twoturnmove"); }
            if b.has_vol(p, "skydrop") { b.queue.retain(|q| !(q.pokemon == Some(p) && q.choice == Choice::Move)); b.remove_volatile(p, "skydrop"); b.remove_volatile(p, "twoturnmove"); }
            b.pm(p).volatiles.retain(|(k, _)| *k != "magnetrise" && *k != "telekinesis");
        } RV::Undef });
    h!(r, Cond, "gravity", "onModifyAccuracy", |b, a| { if let RV::N(_) = a.relay { return b.cm(6840.0, 4096.0); } RV::Undef });
    h!(r, Cond, "gravity", "onDisableMove", |b, a| { let m = a.t(); let ids: Vec<Id> = b.p(m).move_slots.iter().map(|s| s.id).collect(); for mid in ids { if b.dex.mv(mid).tmpl.flag("gravity") { b.disable_move(m, mid, false, ""); } } RV::Undef });
    h!(r, Cond, "gravity", "onBeforeMove", |b, a| { let m = a.t(); if b.am(a.am()).flag("gravity") { let n = b.mon_name(m); b.add(&["cant", &n, "move: Gravity"]); return RV::B(false); } RV::Undef });
    h!(r, Cond, "gravity", "onModifyMove", |b, a| { let m = a.t(); if b.am(a.am()).flag("gravity") { let n = b.mon_name(m); b.add(&["cant", &n, "move: Gravity"]); return RV::B(false); } RV::Undef });
    h!(r, Cond, "gravity", "onFieldEnd", |b, a| { RV::Undef });
    h!(r, Cond, "charge", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "charge", "onRestart", |b, a| { RV::Undef });
    h!(r, Cond, "charge", "onBasePower", |b, a| { if b.am(a.am()).mtype == "Electric" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Cond, "charge", "onMoveAborted", |b, a| { let m = a.t(); let am = a.am(); if b.am(am).mtype == "Electric" && b.am(am).id != "charge" { b.remove_volatile(m, "charge"); } RV::Undef });
    h!(r, Cond, "charge", "onAfterMove", |b, a| { let m = a.t(); let am = a.am(); if b.am(am).mtype == "Electric" && b.am(am).id != "charge" { b.remove_volatile(m, "charge"); } RV::Undef });
    h!(r, Cond, "charge", "onEnd", |b, a| { RV::Undef });
    h!(r, Cond, "curse", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "curse", "onResidual", |b, a| { let m = a.t(); let d = b.p(m).base_maxhp as f64 / 4.0; b.damage(d, None, None, None, false); RV::Undef });
    h!(r, Cond, "allyswitch", "onStart", |b, a| { b.es().set("counter", SV::N(3.0)); RV::Undef });
    h!(r, Cond, "allyswitch", "onRestart", |b, a| { let m = a.t(); let c = b.es().n("counter").filter(|x| *x != 0.0).unwrap_or(1.0);
        if !b.rchance(1, c as i64) { b.pm(m).volatiles.retain(|(k, _)| *k != "allyswitch"); return RV::B(false); }
        if c < 729.0 { b.es().set("counter", SV::N(c * 3.0)); } b.es().duration = Some(2); RV::Undef });
    h!(r, Cond, "yawn", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "yawn", "onEnd", |b, a| { let m = a.t(); let src = b.es().source; b.try_set_status(m, "slp", src, Some(Eff::cond(id("yawn")))); RV::Undef });
    h!(r, Cond, "perishsong", "onResidual", |b, a| { RV::Undef });
    h!(r, Cond, "perishsong", "onEnd", |b, a| { let m = a.t(); b.faint(m, None, None); RV::Undef });
    h!(r, Cond, "roost", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "roost", "onType", |b, a| { if let RV::Types(t) = &a.relay { let t2: Vec<Id> = t.iter().copied().filter(|x| *x != "Flying").collect(); return RV::Types(t2); } RV::Undef });
    h!(r, Cond, "glaiverush", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "glaiverush", "onAccuracy", |b, a| { RV::B(true) });
    h!(r, Cond, "glaiverush", "onSourceModifyDamage", |b, a| { b.cm(2.0, 1.0) });
    h!(r, Cond, "glaiverush", "onBeforeMove", |b, a| { let m = a.t(); b.remove_volatile(m, "glaiverush"); RV::Undef });
    h!(r, Cond, "flashfire", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "flashfire", "onEnd", |b, a| { RV::Undef });
    h!(r, Cond, "flashfire", "onModifyAtk", |b, a| { let m = a.t(); if b.am(a.am()).mtype == "Fire" && b.has_ability(m, "flashfire") { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Cond, "flashfire", "onModifySpA", |b, a| { let m = a.t(); if b.am(a.am()).mtype == "Fire" && b.has_ability(m, "flashfire") { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Cond, "unburden", "onModifySpe", |b, a| { let m = a.t(); if b.p(m).item.is_empty() && !b.ignoring_ability(m) { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Cond, "substitute", "onStart", |b, a| {
        let m = a.t(); let hp = (b.p(m).maxhp as f64 / 4.0).floor(); b.es().set("hp", SV::N(hp));
        b.pm(m).volatiles.retain(|(k, _)| *k != "partiallytrapped"); RV::Undef });
    h!(r, Cond, "substitute", "onEnd", |b, a| { RV::Undef });
    h!(r, Cond, "substitute", "onTryPrimaryHit", |b, a| {
        let (t, s, am) = (a.t(), a.s(), a.am());
        if t == s || b.am(am).flag("bypasssub") || b.am(am).infiltrates { return RV::Undef; }
        let d = b.get_damage(s, t, am);
        if !d.truthy() && d != RV::N(0.0) { let n = b.mon_name(s); b.add(&["-fail", &n]); return RV::Null; }
        let sub = find(&b.p(t).volatiles, "substitute").and_then(|x| x.n("hp")).unwrap_or(0.0);
        let dmg = d.num().min(sub);
        if let Some(x) = find_mut(&mut b.pm(t).volatiles, "substitute") { x.set("hp", SV::N(sub - dmg)); }
        b.pm(s).last_damage = dmg as i64;
        if sub - dmg <= 0.0 { b.remove_volatile(t, "substitute"); }
        if dmg != 0.0 { b.apply_recoil_damage(dmg as i64, am, s); }
        if let Some((x, y)) = b.am(am).drain { b.heal((dmg * x as f64 / y as f64).ceil(), Some(s), Some(t), Some(Eff::cond(id("drain")))); }
        let e = Eff::mv(b.am(am).id, am);
        b.single_event("AfterSubDamage", e, None, Tgt::Mon(t), Some(s), Some(e), RV::N(dmg));
        b.run_event("AfterSubDamage", Tgt::Mon(t), Some(s), Some(e), RV::N(dmg), false, false);
        RV::N(0.0) });
    h!(r, Cond, "leechseed", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "leechseed", "onResidual", |b, a| {
        let m = a.t(); let slot = find(&b.p(m).volatiles, "leechseed").and_then(|s| s.source_slot);
        let Some(t) = slot.and_then(|s| b.get_at_slot(s)) else { return RV::Undef };
        if b.p(t).fainted || b.p(t).hp <= 0 { return RV::Undef; }
        let d = b.damage(b.p(m).base_maxhp as f64 / 8.0, Some(m), Some(t), None, false);
        if d.truthy() { b.heal(d.num(), Some(t), Some(m), None); }
        RV::Undef });
    h!(r, Cond, "partiallytrapped", "durationCallback", |b, a| { if a.source.map(|s| b.has_item(s, "gripclaw")).unwrap_or(false) { return RV::N(8.0); } RV::N(b.prng.range(5, 7) as f64) });
    h!(r, Cond, "partiallytrapped", "onStart", |b, a| { let s = a.s(); let d = if b.has_item(s, "bindingband") { 6.0 } else { 8.0 }; b.es().set("boundDivisor", SV::N(d)); RV::Undef });
    h!(r, Cond, "partiallytrapped", "onResidual", |b, a| {
        let m = a.t(); let src = b.es().source;
        if let Some(s) = src { if !b.p(s).is_active || b.p(s).hp <= 0 || b.p(s).active_turns == 0 { b.pm(m).volatiles.retain(|(k, _)| *k != "partiallytrapped"); return RV::Undef; } }
        let div = b.es().n("boundDivisor").unwrap_or(8.0);
        b.damage(b.p(m).base_maxhp as f64 / div, None, None, None, false); RV::Undef });
    h!(r, Cond, "partiallytrapped", "onEnd", |b, a| { RV::Undef });
    h!(r, Cond, "partiallytrapped", "onTrapPokemon", |b, a| { let m = a.t(); if b.es().source.map(|s| b.p(s).is_active).unwrap_or(false) { b.try_trap(m, false); } RV::Undef });   // tryTrap: a Ghost is not trapped (2026-10-12)
    h!(r, Cond, "destinybond", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "destinybond", "onFaint", |b, a| {
        let t = a.t(); let (Some(s), Some(e)) = (a.source, a.src_eff) else { return RV::Undef };
        if b.is_ally(t, s) { return RV::Undef; }
        if b.etype_of(&e) == EType::Move && !e.am.map(|x| b.am(x).flag("futuremove")).unwrap_or(false) { b.faint(s, None, None); }
        RV::Undef });
    h!(r, Cond, "destinybond", "onBeforeMove", |b, a| { if b.am(a.am()).id == "destinybond" { return RV::Undef; } let m = a.t(); b.remove_volatile(m, "destinybond"); RV::Undef });
    h!(r, Cond, "destinybond", "onMoveAborted", |b, a| { let m = a.t(); b.remove_volatile(m, "destinybond"); RV::Undef });
    h!(r, Cond, "curse", "onStart", |b, a| { RV::Undef });
    h!(r, Cond, "curse", "onResidual", |b, a| { let m = a.t(); b.damage(b.p(m).base_maxhp as f64 / 4.0, None, None, None, false); RV::Undef });

    h!(r, Cond, "healblock", "durationCallback", |b, a| {
        if a.src_eff.map(|e| e.id) == Some("psychicnoise") { return RV::N(2.0); }
        if a.source.map(|s| b.has_ability(s, "persistent")).unwrap_or(false) { return RV::N(7.0); } RV::N(5.0) });
    h!(r, Cond, "healblock", "onStart", |b, a| { if let Some(s) = a.source { b.pm(s).move_this_turn_result = Tri::B(true); } RV::Undef });
    h!(r, Cond, "healblock", "onEnd", |b, a| { RV::Undef });
    h!(r, Cond, "healblock", "onDisableMove", |b, a| {
        let m = a.t(); let ids: Vec<Id> = b.p(m).move_slots.iter().map(|s| s.id).collect();
        for i in ids { if b.dex.mv(i).tmpl.flag("heal") { b.disable_move(m, i, false, "healblock"); } } RV::Undef });
    h!(r, Cond, "healblock", "onBeforeMove", |b, a| { let mv = b.am(a.am()); if mv.flag("heal") && !mv.is_z && !mv.is_max { return RV::B(false); } RV::Undef });
    h!(r, Cond, "healblock", "onModifyMove", |b, a| { let mv = b.am(a.am()); if mv.flag("heal") && !mv.is_z && !mv.is_max { return RV::B(false); } RV::Undef });
    h!(r, Cond, "healblock", "onTryHeal", |b, a| {
        let t = a.t(); let e = a.src_eff;
        if let (Some(s), Some(e)) = (a.source, e) { if t != s && b.p(t).hp != b.p(t).maxhp && e.id == "pollenpuff" { return RV::Null; } }
        RV::B(false) });
    h!(r, Cond, "healblock", "onRestart", |b, a| {
        if a.src_eff.map(|e| e.id) == Some("psychicnoise") { return RV::Undef; }
        if let Some(s) = a.source { if !matches!(b.p(s).move_this_turn_result, Tri::B(true)) { b.pm(s).move_this_turn_result = Tri::B(false); } } RV::Undef });
    h!(r, Cond, "toxicspikes", "onSideStart", |b, a| { b.es().set("layers", SV::N(1.0)); RV::Undef });
    h!(r, Cond, "toxicspikes", "onSideRestart", |b, a| { let l = b.es().n("layers").unwrap_or(0.0); if l >= 2.0 { return RV::B(false); } b.es().set("layers", SV::N(l + 1.0)); RV::Undef });
    h!(r, Cond, "toxicspikes", "onSwitchIn", |b, a| {
        let m = a.t(); if b.is_grounded(m, false) != Some(true) { return RV::Undef; }
        let foe0 = b.sides[1 - m.0 as usize].active[0].map(|i| (1 - m.0, i));
        if b.has_type(m, "Poison") { b.remove_side_condition(m.0, "toxicspikes"); }
        else if b.has_type(m, "Steel") || b.has_item(m, "heavydutyboots") {}
        else if b.es().n("layers").unwrap_or(0.0) >= 2.0 { b.try_set_status(m, "tox", foe0, None); }
        else { b.try_set_status(m, "psn", foe0, None); }
        RV::Undef });
    h!(r, Cond, "stealthrock", "onSideStart", |b, a| { RV::Undef });
    h!(r, Cond, "stealthrock", "onSwitchIn", |b, a| {
        let m = a.t(); if b.has_item(m, "heavydutyboots") { return RV::Undef; }
        let am = b.new_am(b.dex.active_move("stealthrock"));
        let tm = Battle::clamp(b.run_effectiveness(m, am), -6, 6);
        let d = b.p(m).maxhp as f64 * 2f64.powi(tm as i32) / 8.0;
        b.damage(d, None, None, None, false); RV::Undef });
    h!(r, Cond, "gem", "onBasePower", |b, a| { b.cm(5325.0, 4096.0) });

    // ---------- side conditions ----------
    h!(r, Cond, "tailwind", "durationCallback", |b, a| { if a.source.map(|s| b.has_ability(s, "persistent")).unwrap_or(false) { RV::N(6.0) } else { RV::N(4.0) } });
    h!(r, Cond, "tailwind", "onSideStart", |b, a| { RV::Undef });
    h!(r, Cond, "tailwind", "onSideEnd", |b, a| { RV::Undef });
    h!(r, Cond, "tailwind", "onModifySpe", |b, a| { b.cm(2.0, 1.0) });
    for c in ["reflect", "lightscreen", "auroraveil"] { let _ = c; }
    h!(r, Cond, "reflect", "durationCallback", |b, a| { if a.source.map(|s| b.has_item(s, "lightclay")).unwrap_or(false) { RV::N(8.0) } else { RV::N(5.0) } });
    h!(r, Cond, "lightscreen", "durationCallback", |b, a| { if a.source.map(|s| b.has_item(s, "lightclay")).unwrap_or(false) { RV::N(8.0) } else { RV::N(5.0) } });
    h!(r, Cond, "auroraveil", "durationCallback", |b, a| { if a.source.map(|s| b.has_item(s, "lightclay")).unwrap_or(false) { RV::N(8.0) } else { RV::N(5.0) } });
    h!(r, Cond, "reflect", "onSideStart", |b, a| { RV::Undef });
    h!(r, Cond, "reflect", "onSideEnd", |b, a| { RV::Undef });
    h!(r, Cond, "lightscreen", "onSideStart", |b, a| { RV::Undef });
    h!(r, Cond, "lightscreen", "onSideEnd", |b, a| { RV::Undef });
    h!(r, Cond, "auroraveil", "onSideStart", |b, a| { RV::Undef });
    h!(r, Cond, "auroraveil", "onSideEnd", |b, a| { RV::Undef });
    h!(r, Cond, "reflect", "onAnyModifyDamage", |b, a| { if b.screen_applies(a, "Physical") { return b.cm(2732.0, 4096.0); } RV::Undef });
    h!(r, Cond, "lightscreen", "onAnyModifyDamage", |b, a| { if b.screen_applies(a, "Special") { return b.cm(2732.0, 4096.0); } RV::Undef });
    h!(r, Cond, "auroraveil", "onAnyModifyDamage", |b, a| {
        let (atk, def) = (a.t(), a.s()); let am = a.am();
        if atk != def && def.0 == b.es_side() {
            let cat = b.dex.mv(b.am(am).id).tmpl.category;
            let side = &b.sides[def.0 as usize].side_conditions;
            if (find(side, "reflect").is_some() && cat == "Physical") || (find(side, "lightscreen").is_some() && cat == "Special") { return RV::Undef; }
            let slot = b.slot_name(def);
            if !b.amm(am).hd(slot).crit && !b.am(am).infiltrates { return b.cm(2732.0, 4096.0); }
        }
        RV::Undef });
    h!(r, Cond, "wideguard", "onSideStart", |b, a| { RV::Undef });
    h!(r, Cond, "wideguard", "onTryHit", |b, a| {
        let am = a.am(); let tt = b.am(am).target;
        if tt != "allAdjacent" && tt != "allAdjacentFoes" { return RV::Undef; }
        let (t, s) = (a.t(), a.s());
        if b.bypasses_protect(am, s, t, true) { return RV::Undef; }
        if let Some(l) = find(&b.p(s).volatiles, "lockedmove") { if l.duration == Some(2) { b.pm(s).volatiles.retain(|(k, _)| *k != "lockedmove"); } }
        RV::NotFail });
    h!(r, Cond, "quickguard", "onSideStart", |b, a| { RV::Undef });
    h!(r, Cond, "quickguard", "onTryHit", |b, a| {
        let am = a.am(); if b.am(am).priority <= 0.1 { return RV::Undef; }
        let (t, s) = (a.t(), a.s());
        if b.bypasses_protect(am, s, t, true) { return RV::Undef; }
        if let Some(l) = find(&b.p(s).volatiles, "lockedmove") { if l.duration == Some(2) { b.pm(s).volatiles.retain(|(k, _)| *k != "lockedmove"); } }
        RV::NotFail });
    h!(r, Cond, "safeguard", "durationCallback", |b, a| { if a.source.map(|s| b.has_ability(s, "persistent")).unwrap_or(false) { RV::N(7.0) } else { RV::N(5.0) } });
    h!(r, Cond, "safeguard", "onSideStart", |b, a| { RV::Undef });
    h!(r, Cond, "safeguard", "onSideEnd", |b, a| { RV::Undef });
    h!(r, Cond, "safeguard", "onSetStatus", |b, a| {
        let (Some(e), Some(s)) = (a.src_eff, a.source) else { return RV::Undef }; let t = a.t();
        if e.id == "yawn" { return RV::Undef; }
        if b.etype_of(&e) == EType::Move && e.am.map(|x| b.am(x).infiltrates).unwrap_or(false) && !b.is_ally(t, s) { return RV::Undef; }
        if t != s { return RV::Null; }
        RV::Undef });
    h!(r, Cond, "safeguard", "onTryAddVolatile", |b, a| {
        let (Some(e), Some(s)) = (a.src_eff, a.source) else { return RV::Undef }; let t = a.t();
        if b.etype_of(&e) == EType::Move && e.am.map(|x| b.am(x).infiltrates).unwrap_or(false) && !b.is_ally(t, s) { return RV::Undef; }
        let st = if let RV::S(x) = a.relay { x } else { "" };
        if (st == "confusion" || st == "yawn") && t != s { return RV::Null; }
        RV::Undef });

    // ---------- pseudo-weather ----------
    h!(r, Cond, "trickroom", "durationCallback", |b, a| { if a.target.mon().map(|s| b.has_ability(s, "persistent")).unwrap_or(false) { RV::N(7.0) } else { RV::N(5.0) } });
    h!(r, Cond, "trickroom", "onFieldStart", |b, a| { RV::Undef });
    h!(r, Cond, "trickroom", "onFieldRestart", |b, a| { b.remove_pseudo_weather("trickroom"); RV::Undef });
    h!(r, Cond, "trickroom", "onFieldEnd", |b, a| { RV::Undef });

    // ---------- weather ----------
    h!(r, Cond, "sunnyday", "durationCallback", |b, a| { if a.target.mon().map(|s| b.has_item(s, "heatrock")).unwrap_or(false) { RV::N(8.0) } else { RV::N(5.0) } });
    h!(r, Cond, "raindance", "durationCallback", |b, a| { if a.target.mon().map(|s| b.has_item(s, "damprock")).unwrap_or(false) { RV::N(8.0) } else { RV::N(5.0) } });
    h!(r, Cond, "sandstorm", "durationCallback", |b, a| { if a.target.mon().map(|s| b.has_item(s, "smoothrock")).unwrap_or(false) { RV::N(8.0) } else { RV::N(5.0) } });
    h!(r, Cond, "snowscape", "durationCallback", |b, a| { if a.target.mon().map(|s| b.has_item(s, "icyrock")).unwrap_or(false) { RV::N(8.0) } else { RV::N(5.0) } });
    for w in ["sunnyday", "raindance", "sandstorm", "snowscape"] { let _ = w; }
    h!(r, Cond, "sunnyday", "onFieldStart", |b, a| { RV::Undef });
    h!(r, Cond, "raindance", "onFieldStart", |b, a| { RV::Undef });
    h!(r, Cond, "sandstorm", "onFieldStart", |b, a| { RV::Undef });
    h!(r, Cond, "snowscape", "onFieldStart", |b, a| { RV::Undef });
    h!(r, Cond, "sunnyday", "onFieldEnd", |b, a| { RV::Undef });
    h!(r, Cond, "raindance", "onFieldEnd", |b, a| { RV::Undef });
    h!(r, Cond, "sandstorm", "onFieldEnd", |b, a| { RV::Undef });
    h!(r, Cond, "snowscape", "onFieldEnd", |b, a| { RV::Undef });
    h!(r, Cond, "sunnyday", "onFieldResidual", |b, a| { b.each_event("Weather", None); RV::Undef });
    h!(r, Cond, "raindance", "onFieldResidual", |b, a| { b.each_event("Weather", None); RV::Undef });
    h!(r, Cond, "sandstorm", "onFieldResidual", |b, a| { if b.effective_weather() == "sandstorm" { b.each_event("Weather", None); } RV::Undef });
    h!(r, Cond, "snowscape", "onFieldResidual", |b, a| { if b.effective_weather() == "snowscape" { b.each_event("Weather", None); } RV::Undef });
    h!(r, Cond, "sandstorm", "onWeather", |b, a| { let m = a.t(); b.damage(b.p(m).base_maxhp as f64 / 16.0, None, None, None, false); RV::Undef });
    h!(r, Cond, "sunnyday", "onWeatherModifyDamage", |b, a| {
        let (att, def, am) = (a.t(), a.s(), a.am()); let mv = b.am(am).clone();
        if mv.id == "hydrosteam" && b.pokemon_effective_weather(att, None) == "sunnyday" { return b.cm(1.5, 1.0); }
        if b.pokemon_effective_weather(def, None) != "sunnyday" { return RV::Undef; }
        if mv.mtype == "Fire" { return b.cm(1.5, 1.0); }
        if mv.mtype == "Water" { return b.cm(0.5, 1.0); }
        RV::Undef });
    h!(r, Cond, "raindance", "onWeatherModifyDamage", |b, a| {
        let (def, am) = (a.s(), a.am()); let mt = b.am(am).mtype;
        if b.pokemon_effective_weather(def, None) != "raindance" { return RV::Undef; }
        if mt == "Water" { return b.cm(1.5, 1.0); }
        if mt == "Fire" { return b.cm(0.5, 1.0); }
        RV::Undef });
    h!(r, Cond, "sunnyday", "onImmunity", |b, a| { let m = a.t(); if b.pokemon_effective_weather(m, None) != "sunnyday" { return RV::Undef; } if a.relay == RV::S(id("frz")) { return RV::B(false); } RV::Undef });
    h!(r, Cond, "sandstorm", "onModifySpD", |b, a| { let m = a.t(); if b.has_type(m, "Rock") && b.pokemon_effective_weather(m, None) == "sandstorm" { return RV::N(b.modify(a.n(), 1.5) as f64); } RV::Undef });
    h!(r, Cond, "snowscape", "onModifyDef", |b, a| { let m = a.t(); if b.has_type(m, "Ice") && b.pokemon_effective_weather(m, None) == "snowscape" { return RV::N(b.modify(a.n(), 1.5) as f64); } RV::Undef });

    // ---------- terrain ----------
    h!(r, Cond, "psychicterrain", "durationCallback", |b, a| { if a.target.mon().map(|s| b.has_item(s, "terrainextender")).unwrap_or(false) { RV::N(8.0) } else { RV::N(5.0) } });
    h!(r, Cond, "grassyterrain", "durationCallback", |b, a| { if a.target.mon().map(|s| b.has_item(s, "terrainextender")).unwrap_or(false) { RV::N(8.0) } else { RV::N(5.0) } });
    h!(r, Cond, "electricterrain", "durationCallback", |b, a| { if a.target.mon().map(|s| b.has_item(s, "terrainextender")).unwrap_or(false) { RV::N(8.0) } else { RV::N(5.0) } });
    h!(r, Cond, "mistyterrain", "durationCallback", |b, a| { if a.target.mon().map(|s| b.has_item(s, "terrainextender")).unwrap_or(false) { RV::N(8.0) } else { RV::N(5.0) } });
    h!(r, Cond, "psychicterrain", "onFieldStart", |b, a| { RV::Undef });
    h!(r, Cond, "grassyterrain", "onFieldStart", |b, a| { RV::Undef });
    h!(r, Cond, "electricterrain", "onFieldStart", |b, a| { RV::Undef });
    h!(r, Cond, "mistyterrain", "onFieldStart", |b, a| { RV::Undef });
    h!(r, Cond, "psychicterrain", "onFieldEnd", |b, a| { RV::Undef });
    h!(r, Cond, "grassyterrain", "onFieldEnd", |b, a| { RV::Undef });
    h!(r, Cond, "electricterrain", "onFieldEnd", |b, a| { RV::Undef });
    h!(r, Cond, "mistyterrain", "onFieldEnd", |b, a| { RV::Undef });
    h!(r, Cond, "psychicterrain", "onTryHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        let Some(am) = a.am_opt() else { return RV::Undef };
        if b.am(am).priority <= 0.1 || b.am(am).target == "self" { return RV::Undef; }
        if b.is_semi_invulnerable(t) || b.is_ally(t, s) { return RV::Undef; }
        if b.is_grounded(t, false) != Some(true) { return RV::Undef; }
        let n = b.mon_name(t); b.add(&["-activate", &n, "move: Psychic Terrain"]);
        RV::Null });
    h!(r, Cond, "psychicterrain", "onBasePower", |b, a| {
        let (att, am) = (a.t(), a.am());
        if b.am(am).mtype == "Psychic" && b.is_grounded(att, false) == Some(true) && !b.is_semi_invulnerable(att) { return b.cm(5325.0, 4096.0); }
        RV::Undef });
    h!(r, Cond, "grassyterrain", "onBasePower", |b, a| {
        let (att, def, am) = (a.t(), a.s(), a.am()); let mv = b.am(am).clone();
        if ["earthquake", "bulldoze", "magnitude"].contains(&mv.id) && b.is_grounded(def, false) == Some(true) && !b.is_semi_invulnerable(def) { return b.cm(0.5, 1.0); }
        if mv.mtype == "Grass" && b.is_grounded(att, false) == Some(true) { return b.cm(5325.0, 4096.0); }
        RV::Undef });
    h!(r, Cond, "grassyterrain", "onResidual", |b, a| {
        let m = a.t();
        if b.is_grounded(m, false) == Some(true) && !b.is_semi_invulnerable(m) { b.heal(b.p(m).base_maxhp as f64 / 16.0, Some(m), Some(m), None); }
        RV::Undef });
    h!(r, Cond, "electricterrain", "onBasePower", |b, a| {
        let (att, am) = (a.t(), a.am());
        if b.am(am).mtype == "Electric" && b.is_grounded(att, false) == Some(true) && !b.is_semi_invulnerable(att) { return b.cm(5325.0, 4096.0); }
        RV::Undef });
    h!(r, Cond, "electricterrain", "onSetStatus", |b, a| {
        let t = a.t();
        if a.relay == RV::S(id("slp")) && b.is_grounded(t, false) == Some(true) && !b.is_semi_invulnerable(t) { return RV::B(false); }
        RV::Undef });
    h!(r, Cond, "electricterrain", "onTryAddVolatile", |b, a| {
        let t = a.t(); if b.is_grounded(t, false) != Some(true) || b.is_semi_invulnerable(t) { return RV::Undef; }
        if a.relay == RV::S(id("yawn")) { return RV::Null; } RV::Undef });
    h!(r, Cond, "mistyterrain", "onBasePower", |b, a| {
        let (def, am) = (a.s(), a.am());
        if b.am(am).mtype == "Dragon" && b.is_grounded(def, false) == Some(true) && !b.is_semi_invulnerable(def) { return b.cm(0.5, 1.0); }
        RV::Undef });
    h!(r, Cond, "mistyterrain", "onSetStatus", |b, a| {
        let t = a.t(); if b.is_grounded(t, false) != Some(true) || b.is_semi_invulnerable(t) { return RV::Undef; }
        RV::B(false) });
    h!(r, Cond, "mistyterrain", "onTryAddVolatile", |b, a| {
        let t = a.t(); if b.is_grounded(t, false) != Some(true) || b.is_semi_invulnerable(t) { return RV::Undef; }
        if a.relay == RV::S(id("confusion")) { return RV::Null; } RV::Undef });
}
