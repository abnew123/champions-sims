//! Handlers ported 2026-11-27, batch 10: more Regulation M-D candidates (Team search's check of an unofficial M-D prediction list against
//! v43: every effect those species use that `champ missing` still listed). Doodle (Grafaiai), Well-Baked Body (Dachsbun), Costar
//! (Flamigo), Thick Club (Marowak), Water Compaction (the ability reported for Mega Heatran; the data's Heatran-Mega keeps its abilities
//! until M-D says otherwise), Download (Porygon-Z), Toxic Boost (Zangoose), Color Change (Kecleon, with the Curse glitch), Present
//! (Delibird), Conversion (Porygon line), Ability Shield's onSetAbility (Past in Champions; Doodle's blocked case). As Showdown's data/
//! *.ts, which the Champions mod leaves alone (it marks the moves and Ability Shield Past). Inert in M-C: no M-C set carries any of them.
use super::Reg;
use crate::battle::*;
use crate::dex::*;
use crate::h;
use crate::state::*;

impl Battle {
    /// pokemon.setAbility as Showdown returns it: false (fainted, cantsuppress, or a SetAbility handler said false), null (a SetAbility
    /// handler said null: Ability Shield), else the old ability's id (S). Otherwise the same as set_ability, which callers that only need
    /// a yes / no keep using
    pub fn set_ability_rv(&mut self, m: MonRef, ab: Id, source: Option<MonRef>, src_eff: Option<Eff>) -> RV {
        if self.p(m).hp == 0 { return RV::B(false); }
        if self.dex.eff(Kind::Ability, ab).flag("cantsuppress") || self.dex.eff(Kind::Ability, self.p(m).ability).flag("cantsuppress") { return RV::B(false); }
        let r = self.run_event("SetAbility", Tgt::Mon(m), source, src_eff, RV::S(ab), false, false);
        if !r.truthy() { return if r == RV::Null { RV::Null } else { RV::B(false) }; }
        let old = self.p(m).ability;
        self.single_event("End", Eff::new(Kind::Ability, old), Some(SLoc::Ability(m)), Tgt::Mon(m), source, None, RV::Undef);
        let st = self.init_state(ab, Some(self.p(m).is_active));
        let p = self.pm(m); p.ability = ab; p.ability_state = st;
        if !ab.is_empty() { self.single_event("Start", Eff::new(Kind::Ability, ab), Some(SLoc::Ability(m)), Tgt::Mon(m), source, None, RV::Undef); }
        RV::S(old)
    }
    /// pokemon.setType(type) (not enforced): Arceus and Silvally keep theirs (as batch9's set_type)
    fn set_type_one(&mut self, m: MonRef, t: Id) -> bool {
        let num = self.dex.species.get(self.p(m).species).map(|s| s.num).unwrap_or(0);
        if num == 493 || num == 773 || t == "Stellar" { return false; }
        let p = self.pm(m); p.types = vec![t]; p.added_type = ""; true
    }
}

pub fn register(r: &mut Reg) {
    // Doodle: the user and its ally take the target's ability
    h!(r, Move, "doodle", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s()); let am = a.am();
        let tab = b.p(t).ability;
        let mut success = RV::B(false);
        if !b.dex.eff(Kind::Ability, tab).flag("failroleplay") {
            for m in b.allies_and_self(s) {
                if b.p(m).ability == tab || b.ab_data(m).cantsuppress { continue; }
                let e = Eff::mv(b.am(am).id, am);
                let old = b.set_ability_rv(m, tab, Some(t), Some(e));
                if old.truthy() { success = RV::B(true); } else if !success.truthy() && old == RV::Null { success = RV::Null; }
            }
        }
        if !success.truthy() {
            if success == RV::B(false) { let n = b.mon_name(s); b.add(&["-fail", &n]); }
            return RV::NotFail;
        }
        RV::Undef });
    // Well-Baked Body: Fire moves fail and raise Def by 2 (immune message if Def can't rise)
    h!(r, Ability, "wellbakedbody", "onTryHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if t != s && b.am(a.am()).mtype == "Fire" {
            if !b.boost(vec![(1, 2)], None, None, None, false, false).truthy() { let n = b.mon_name(t); b.add(&["-immune", &n, "[from] ability: Well-Baked Body"]); }
            return RV::Null;
        }
        RV::Undef });
    // Costar: on entry, copy the ally's stat stages and its crit-rate volatiles
    h!(r, Ability, "costar", "onStart", |b, a| {
        let m = a.t();
        let Some(ally) = b.allies(m).into_iter().next() else { return RV::Undef };
        let bo = b.p(ally).boosts; b.pm(m).boosts = bo;
        let vols = ["dragoncheer", "focusenergy", "gmaxchistrike", "laserfocus"];
        for v in vols { b.remove_volatile(m, v); }
        for v in vols {
            if !b.has_vol(ally, v) { continue; }
            b.add_volatile(m, v, None, None);
            for key in ["layers", "hasDragonType"] {
                let val = find(&b.p(ally).volatiles, v).and_then(|s| s.get(key)).cloned();
                if let Some(val) = val { if let Some(s) = b.pm(m).volatiles.iter_mut().find(|(k, _)| *k == v) { s.1.set(key, val); } }
            }
        }
        let (n, o) = (b.mon_name(m), b.mon_name(ally)); b.add(&["-copyboost", &n, &o, "[from] ability: Costar"]);
        RV::Undef });
    // Thick Club: Cubone's and Marowak's (every forme's) Attack x2
    h!(r, Item, "thickclub", "onModifyAtk", |b, a| {
        let m = a.t(); let bb = to_id(b.base_base(m));
        if bb == "cubone" || bb == "marowak" { return b.cm(2.0, 1.0); }
        RV::Undef });
    // Water Compaction: +2 Def when hit by a Water move
    h!(r, Ability, "watercompaction", "onDamagingHit", |b, a| {
        if b.am(a.am()).mtype == "Water" { b.boost(vec![(1, 2)], None, None, None, false, false); }
        RV::Undef });
    // Download: +1 SpA if the foes' total Def >= their total SpD, else +1 Atk (unboosted stats, unmodified)
    h!(r, Ability, "download", "onStart", |b, a| {
        let m = a.t(); let (mut def, mut spd) = (0i64, 0i64);
        for t in b.foes(m) { def += b.get_stat(t, 2, false, true); spd += b.get_stat(t, 4, false, true); }
        if def != 0 && def >= spd { b.boost(vec![(2, 1)], None, None, None, false, false); }
        else if spd != 0 { b.boost(vec![(0, 1)], None, None, None, false, false); }
        RV::Undef });
    // Toxic Boost: physical moves x1.5 while poisoned
    h!(r, Ability, "toxicboost", "onBasePower", |b, a| {
        let m = a.t(); let st = b.p(m).status;
        if (st == "psn" || st == "tox") && b.am(a.am()).category == "Physical" { return b.cm(1.5, 1.0); }
        RV::Undef });
    // Color Change: after a damaging move, the holder becomes the move's type
    h!(r, Ability, "colorchange", "onAfterMoveSecondary", |b, a| {
        let t = a.t(); if b.p(t).hp == 0 { return RV::Undef; }
        let am = a.am(); let (ty, cat) = (b.am(am).mtype, b.am(am).category);
        if b.p(t).is_active && cat != "Status" && ty != "???" && !b.has_type(t, ty) {
            if !b.set_type_one(t, ty) { return RV::B(false); }
            let n = b.mon_name(t); b.add(&["-start", &n, "typechange", ty, "[from] ability: Color Change"]);
            // the Curse glitch: a Ghost-turned holder in the right slot that will still use Curse aims it at no one
            if b.p(t).position == 1 {
                if let Some(qi) = b.will_move(t) { if let Some(qam) = b.queue[qi].am { if b.am(qam).id == "curse" { b.queue[qi].target_loc = -1; } } }
            }
        }
        RV::Undef });
    // Present: 20% heals the target by 1/4 (infiltrating), 40% 40 power, 30% 80, 10% 120
    h!(r, Move, "present", "onModifyMove", |b, a| {
        let am = a.am(); let rand = b.prng.below(10);
        if rand < 2 { let mv = b.amm(am); mv.base.heal = Some((1, 4)); mv.infiltrates = true; }
        else if rand < 6 { b.amm(am).base_power = 40.0; }
        else if rand < 9 { b.amm(am).base_power = 80.0; }
        else { b.amm(am).base_power = 120.0; }
        RV::Undef });
    // Ability Shield (Past in Champions; ported so Doodle's null branch is checked): ability changes are blocked, and say nothing
    h!(r, Item, "abilityshield", "onSetAbility", |b, a| {
        if let Some(e) = a.src_eff { if e.kind == Kind::Ability && e.id != "trace" {
            if let Some(s) = a.source { let (n, f) = (b.mon_name(s), format!("ability: {}", b.dex.eff(Kind::Ability, e.id).name)); b.add(&["-ability", &n, &f]); }
        } }
        let n = b.mon_name(a.t()); b.add(&["-block", &n, "item: Ability Shield"]);
        RV::Null });
    // Conversion: the user becomes the type of its first move
    h!(r, Move, "conversion", "onHit", |b, a| {
        let t = a.t();
        let Some(first) = b.p(t).move_slots.first().map(|s| s.id) else { return RV::B(false) };
        let ty = b.dex.mv(first).tmpl.mtype;
        if b.has_type(t, ty) || !b.set_type_one(t, ty) { return RV::B(false); }
        let n = b.mon_name(t); b.add(&["-start", &n, "typechange", ty]);
        RV::Undef });
}
