//! Handlers ported 2026-10-12, batch 7: Transform and Imposter (Ditto, 86 sheets in the cached Bo3 replays), following
//! pokemon.transformInto (the engine restores a transformed Pokemon on leaving the field from base_move_slots, exported since
//! 2026-10-12); and the unported effects the 300-battle mid-battle run met most (Sap Sipper, Simple, Reversal / Flail, Venoshock,
//! Burn Up, Meteor Beam, Shell Bell, Simple Beam, Illuminate, Supercell Slam's crash, Liquid Ooze, Aroma Veil, Screen Cleaner).
use super::Reg;
use crate::battle::*;
use crate::dex::*;
use crate::h;
use crate::state::*;

impl Battle {
    /// pokemon.transformInto(target, effect)
    pub fn transform_into(&mut self, m: MonRef, t: MonRef, effect: Option<&str>) -> bool {
        // the engine does not model Illusion: a holder not hit since it came in counts as still disguised (Showdown refuses
        // pokemon.illusion; a damaging hit ends it)
        let disguised = self.p(t).ability == "illusion" && self.p(t).times_attacked == 0;
        if self.p(t).fainted || self.has_vol(t, "substitute") || self.p(t).transformed || self.p(m).transformed || disguised { return false; }
        // Showdown's baseMoveSlots are the same objects as moveSlots until now (PP spent so far, Transform's own included, stays)
        { let p = self.pm(m); p.base_move_slots = p.move_slots.clone(); }
        let sp = self.p(t).species;
        self.set_species(m, sp);                     // own set's stats for that species; cached speed from them, as setSpecies does
        // the target's types without its added type (getTypes(true, true): after the Type event)
        let base = self.p(t).types.clone();
        let mut types = match self.run_event("Type", Tgt::Mon(t), None, None, RV::Types(base.clone()), false, false) { RV::Types(x) => x, _ => base };
        if types.is_empty() { types.push("Normal"); }
        let (added, wt, ta) = (self.p(t).added_type, self.p(t).weighthg, self.p(t).times_attacked);
        let stored = self.p(t).stored; let boosts = self.p(t).boosts;
        let slots: Vec<MoveSlot> = self.p(t).move_slots.iter().map(|s| {
            let pp = self.dex.mv(s.id).tmpl.pp.min(5);
            MoveSlot { id: s.id, pp, maxpp: pp, disabled: false, disabled_hidden: false, disabled_source: "", used: false } }).collect();
        {
            let p = self.pm(m);
            p.transformed = true; p.weighthg = wt; p.types = types; p.added_type = added;
            for i in 1..6 { p.stored[i] = stored[i]; }
            p.move_slots = slots; p.times_attacked = ta; p.boosts = boosts;
        }
        for v in ["dragoncheer", "focusenergy", "laserfocus"] { self.remove_volatile(m, v); }
        for v in ["dragoncheer", "focusenergy", "laserfocus"] {
            if self.has_vol(t, v) {
                self.add_volatile(m, v, None, None);
                if v == "dragoncheer" {
                    let d = find(&self.p(t).volatiles, "dragoncheer").map(|s| s.has("hasDragonType")).unwrap_or(false);
                    if let Some(s) = self.pm(m).volatiles.iter_mut().find(|(k, _)| *k == "dragoncheer") { s.1.set("hasDragonType", SV::B(d)); }
                }
            }
        }
        let (mn, tn) = (self.mon_name(m), self.mon_name(t));
        match effect { Some(e) => self.add(&["-transform", &mn, &tn, &format!("[from] {}", e)]), None => self.add(&["-transform", &mn, &tn]) }
        // setAbility(target's, isFromFormeChange, isTransform): no SetAbility event, Start only when the ability changes
        let ab = self.p(t).ability;
        if ab != self.p(m).ability { self.set_ability(m, ab, Some(m), None, true); }
        true
    }
}

pub fn register(r: &mut Reg) {
    h!(r, Ability, "imposter", "onSwitchIn", |b, a| {
        let m = a.t(); let foe = 1 - m.0 as usize;
        let n = b.sides[foe].active.len(); let pos = b.p(m).position as usize;
        if pos < n { if let Some(i) = b.sides[foe].active[n - 1 - pos] { b.transform_into(m, (foe as u8, i), Some("ability: Imposter")); } }
        RV::Undef });
    h!(r, Move, "transform", "onHit", |b, a| { let (t, s) = (a.t(), a.s()); RV::B(b.transform_into(s, t, None)) });

    h!(r, Ability, "sapsipper", "onTryHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if t != s && b.am(a.am()).mtype == "Grass" {
            if !b.boost(vec![(0, 1)], None, None, None, false, false).truthy() { let n = b.mon_name(t); b.add(&["-immune", &n, "[from] ability: Sap Sipper"]); }
            return RV::Null;
        }
        RV::Undef });
    h!(r, Ability, "simple", "onChangeBoost", |b, a| {
        if a.src_eff.map(|e| e.id == "zpower").unwrap_or(false) { return RV::Undef; }
        if let RV::Boosts(bo) = &a.relay { return RV::Boosts(bo.iter().map(|(k, v)| (*k, v * 2)).collect()); } RV::Undef });
    h!(r, Ability, "illuminate", "onModifyMove", |b, a| { let am = a.am(); b.amm(am).ignore_evasion = true; RV::Undef });
    h!(r, Ability, "illuminate", "onTryBoost", |b, a| {
        let t = a.t(); if a.source == Some(t) { return RV::Undef; }
        if let RV::Boosts(bo) = &a.relay { if bo.iter().any(|(k, v)| *k == 5 && *v < 0) {
            let nb: Boosts = bo.iter().filter(|(k, _)| *k != 5).cloned().collect();
            let from_sec = a.src_eff.and_then(|e| e.am).map(|i| b.am(i).secondaries.is_some()).unwrap_or(false);
            if !from_sec { let n = b.mon_name(t); b.add(&["-fail", &n, "unboost", "accuracy", "[from] ability: Illuminate", &format!("[of] {}", n)]); }
            return RV::Boosts(nb);
        } }
        RV::Undef });
    h!(r, Ability, "liquidooze", "onSourceTryHeal", |b, a| {
        let Some(e) = a.src_eff else { return RV::Undef };
        if ["drain", "leechseed", "strengthsap"].contains(&e.id) { let t = a.t(); let d = a.n(); b.damage(d, Some(t), a.source, None, false); return RV::N(0.0); }
        RV::Undef });
    h!(r, Ability, "aromaveil", "onAllyTryAddVolatile", |b, a| {
        let RV::S(v) = a.relay else { return RV::Undef };
        if ["attract", "disable", "encore", "healblock", "taunt", "torment"].contains(&v) {
            if a.src_eff.map(|e| b.etype_of(&e) == EType::Move).unwrap_or(false) {
                let (tn, hn) = (b.mon_name(a.t()), b.mon_name(b.holder())); b.add(&["-block", &tn, "ability: Aroma Veil", &format!("[of] {}", hn)]);
            }
            return RV::Null;
        }
        RV::Undef });
    h!(r, Ability, "screencleaner", "onStart", |b, a| {
        let m = a.t(); let mut act = false;
        for c in ["reflect", "lightscreen", "auroraveil"] { for s in [m.0, 1 - m.0] {
            if find(&b.sides[s as usize].side_conditions, c).is_some() {
                if !act { let n = b.mon_name(m); b.add(&["-activate", &n, "ability: Screen Cleaner"]); act = true; }
                b.remove_side_condition(s, c);
            } } }
        RV::Undef });
    h!(r, Item, "shellbell", "onAfterMoveSecondarySelf", |b, a| {
        let m = a.t(); let td = b.am(a.am()).total_damage;
        if td != 0 && !b.p(m).force_switch_flag { b.heal(td as f64 / 8.0, Some(m), None, None); } RV::Undef });
    for mv in ["reversal", "flail"] {
        r.insert((Kind::Move, id(mv), id("basePowerCallback")), reversal_bp as HFn);
    }
    h!(r, Move, "venoshock", "onBasePower", |b, a| { let t = a.s(); let st = b.p(t).status; if st == "psn" || st == "tox" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Move, "burnup", "onTryMove", |b, a| {
        let m = a.t(); if b.has_type(m, "Fire") { return RV::Undef; }
        let n = b.mon_name(m); b.add(&["-fail", &n, "move: Burn Up"]); RV::Null });
    h!(r, Move, "burnup", "self.onHit", |b, a| {
        let m = a.t();
        let base = b.p(m).types.clone();
        let ty = match b.run_event("Type", Tgt::Mon(m), None, None, RV::Types(base.clone()), false, false) { RV::Types(x) => x, _ => base };
        let nt: Vec<Id> = ty.iter().map(|t| if *t == "Fire" { "???" } else { *t }).collect();
        { let p = b.pm(m); p.types = nt; p.added_type = ""; }
        let n = b.mon_name(m); let tj = b.get_types(m).join("/"); b.add(&["-start", &n, "typechange", &tj, "[from] move: Burn Up"]); RV::Undef });
    h!(r, Move, "meteorbeam", "onTryMove", |b, a| {
        let att = a.t(); let def = a.source; let e = a.src_eff.unwrap();
        if b.remove_volatile(att, e.id) { return RV::Undef; }
        b.boost(vec![(2, 1)], Some(att), Some(att), Some(e), false, false);
        if !b.run_event("ChargeMove", Tgt::Mon(att), def, Some(e), RV::Undef, false, false).truthy() { return RV::Undef; }
        b.add_volatile_src_eff(att, "twoturnmove", def, Some(e)); RV::Null });
    h!(r, Move, "simplebeam", "onTryHit", |b, a| { let t = a.t(); let ab = b.p(t).ability; if b.ab_data(t).cantsuppress || ab == "simple" || ab == "truant" { return RV::B(false); } RV::Undef });
    h!(r, Move, "simplebeam", "onHit", |b, a| { let (t, s) = (a.t(), a.s()); if !b.set_ability(t, id("simple"), Some(s), None, false) { return RV::B(false); } RV::Undef });
    h!(r, Move, "supercellslam", "onMoveFail", |b, a| {
        let s = a.source.unwrap(); let d = b.p(s).base_maxhp as f64 / 2.0;
        b.damage(d, Some(s), Some(s), Some(Eff::cond(id("supercellslam"))), false); RV::Undef });
}
fn reversal_bp(b: &mut Battle, a: &mut HArgs) -> RV {
    let s = a.s(); let p = b.p(s);
    let ratio = ((p.hp * 48) as f64 / p.maxhp as f64).floor().max(1.0);
    RV::N(if ratio < 2.0 { 200.0 } else if ratio < 5.0 { 150.0 } else if ratio < 10.0 { 100.0 } else if ratio < 17.0 { 80.0 } else if ratio < 33.0 { 40.0 } else { 20.0 })
}
