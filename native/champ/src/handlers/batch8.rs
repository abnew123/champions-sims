//! Handlers ported 2026-11-06, batch 8: the Regulation M-D candidates, so the engine is ready for species and abilities that may arrive
//! with the next regulation before it is announced. Commander (Tatsugiri + Dondozo: the ability, the commanding / commanded conditions
//! and Order Up), Power Construct (Zygarde -> Zygarde-Complete, which may then Mega Evolve with Zygardite), Soul-Heart, Storm Drain,
//! Water Veil, Bad Dreams, Dark Aura and Aura Break (Fairy Aura now honours Aura Break too: abilities::aura_bp), Thousand Arrows,
//! Thousand Waves (the trapped / trapper link: sim.rs add_volatile_ex and the linked-volatile removal), Core Enforcer (Gastro Acid's
//! condition), Dark Void, and Ion Deluge (Plasma Fists' pseudo-weather). Each follows data/abilities.js, moves.js and conditions.js of the
//! pinned Showdown; message-only code is reduced to log lines.
use super::Reg;
use crate::battle::*;
use crate::dex::*;
use crate::h;
use crate::state::*;

impl Battle {
    /// the base species (Showdown's pokemon.baseSpecies.baseSpecies) of this Pokemon's permanent forme, as an id
    pub fn base_base(&self, m: MonRef) -> Id { self.dex.species.get(self.p(m).base_species).map(|s| s.base_species).unwrap_or("") }
    /// Showdown's pokemon.canMegaEvo === false: its side has Mega Evolved (every Pokemon of the side gets false then). The flag comes
    /// from the state; a position built without it still shows the Mega in a Pokemon's permanent forme (a Champions Mega never reverts,
    /// except a Zygarde-Mega fainting back to its set's forme, whose side's flags are already set)
    pub fn mega_spent(&self, m: MonRef) -> bool {
        self.p(m).mega_spent || self.sides[m.0 as usize].pokemon.iter().any(|p| self.dex.species.get(p.base_species).map(|x| x.is_mega).unwrap_or(false))
    }
    /// the Champions mod's actions.canMegaEvo: the held item's megaStone entry for the permanent forme's name (the requiredMove branch is
    /// Rayquaza's alone)
    pub fn can_mega_evo_of(&self, m: MonRef) -> Option<Id> {
        let name = self.dex.species.get(self.p(m).base_species)?.name;
        self.dex.items.get(self.p(m).item)?.raw.get("megaStone")?.get(name)?.as_str().map(|x| id(&to_id(x)))
    }
}

/// Commander's onUpdate (onStart and onAnySwitchIn call it too): a Tatsugiri next to a Dondozo goes into it (its queued action is
/// cancelled, it gets the commanding volatile, the Dondozo commanded with +2 in every stat); it comes out when the Dondozo faints
fn commander_update(b: &mut Battle, m: MonRef) {
    // gameType is always doubles here
    if b.queue.first().map(|q| q.choice == Choice::RunSwitch).unwrap_or(false) { return; }
    let ally = b.allies(m).first().copied();
    if b.p(m).switch_flag.is_some() || ally.map(|x| b.p(x).switch_flag.is_some()).unwrap_or(false) { return; }
    let Some(al) = ally.filter(|x| b.base_base(m) == "tatsugiri" && b.base_base(*x) == "dondozo") else {
        if b.has_vol(m, "commanding") { b.remove_volatile(m, "commanding"); }
        return;
    };
    if !b.has_vol(m, "commanding") {
        if b.has_vol(al, "commanded") { return; }
        b.queue.retain(|q| q.pokemon != Some(m));   // queue.cancelAction(pokemon)
        if b.logging { let (n, o) = (b.mon_name(m), b.mon_name(al)); b.add(&["-activate", &n, "ability: Commander", &format!("[of] {}", o)]); }
        b.add_volatile(m, "commanding", None, None);
        b.add_volatile(al, "commanded", Some(m), None);
    } else {
        if !b.p(al).fainted { return; }
        b.remove_volatile(m, "commanding");
    }
}
/// Core Enforcer's onHit / onAfterSubDamage: Gastro Acid on a target that has already moved this turn (not one that just came in)
fn core_enforcer(b: &mut Battle, t: MonRef) {
    if b.ab_data(t).cantsuppress { return; }
    if b.p(t).newly_switched || b.will_move(t).is_some() { return; }
    b.add_volatile(t, "gastroacid", None, None);
}

pub fn register(r: &mut Reg) {
    // ---------- Commander ----------
    h!(r, Ability, "commander", "onAnySwitchIn", |b, a| { let m = b.holder(); commander_update(b, m); RV::Undef });
    h!(r, Ability, "commander", "onStart", |b, a| { let m = a.t(); commander_update(b, m); RV::Undef });
    h!(r, Ability, "commander", "onUpdate", |b, a| { let m = a.t(); commander_update(b, m); RV::Undef });
    // Tatsugiri: can't be hit (hitStepInvulnerabilityEvent checks the volatile; its constant onInvulnerability: false answers the moves
    // that run the event themselves, e.g. Perish Song), can't act (onBeforeTurn), switch or be dragged out
    h!(r, Cond, "commanding", "onBeforeTurn", |b, a| { let m = a.t(); b.queue.retain(|q| q.pokemon != Some(m)); RV::Undef });
    h!(r, Cond, "commanding", "onTrapPokemon", |b, a| { let m = a.t(); b.pm(m).trapped = true; RV::Undef });
    h!(r, Cond, "commanding", "onDragOut", |b, a| { RV::B(false) });
    // Dondozo
    h!(r, Cond, "commanded", "onStart", |b, a| {
        let m = a.t(); b.boost(vec![(0, 2), (2, 2), (4, 2), (1, 2), (3, 2)], Some(m), None, None, false, false); RV::Undef });   // {atk, spa, spe, def, spd}
    h!(r, Cond, "commanded", "onTrapPokemon", |b, a| { let m = a.t(); b.pm(m).trapped = true; RV::Undef });
    h!(r, Cond, "commanded", "onDragOut", |b, a| { RV::B(false) });
    // Order Up: +1 by the commanding Tatsugiri's forme (Showdown switches on tatsugiri.baseSpecies.forme: "Droopy" Def, "Stretchy" Spe,
    // anything else Atk). A Mega counts as its plain forme here (Droopy-Mega Def, Stretchy-Mega Spe; the rule asked for 2026-11-06); in
    // Showdown the Megas' formes read "Droopy-Mega" / "Stretchy-Mega" / "Curly-Mega", so all three fall to the default and give Atk
    h!(r, Move, "orderup", "onAfterMoveSecondarySelf", |b, a| {
        let m = a.t();
        let Some(t) = find(&b.p(m).volatiles, "commanded").and_then(|s| s.source) else { return RV::Undef };
        if b.base_base(t) != "tatsugiri" { return RV::Undef; }
        let bs = b.p(t).base_species;
        let stat = if bs.starts_with("tatsugiridroopy") { 1 } else if bs.starts_with("tatsugiristretchy") { 4 } else { 0 };
        b.boost(vec![(stat, 1)], Some(m), Some(m), None, false, false); RV::Undef });

    // ---------- abilities ----------
    h!(r, Ability, "soulheart", "onAnyFaint", |b, a| { let m = b.holder(); b.boost(vec![(2, 1)], Some(m), None, None, false, false); RV::Undef });
    h!(r, Ability, "stormdrain", "onTryHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if t != s && b.am(a.am()).mtype == "Water" {
            if !b.boost(vec![(2, 1)], None, None, None, false, false).truthy() { let n = b.mon_name(t); b.add(&["-immune", &n, "[from] ability: Storm Drain"]); }
            return RV::Null;
        }
        RV::Undef });
    h!(r, Ability, "stormdrain", "onAnyRedirectTarget", |b, a| {
        let src = a.t(); let am = a.am(); let mv = b.am(am);
        if mv.mtype != "Water" || mv.flag("pledgecombo") { return RV::Undef; }
        let rt = if ["randomNormal", "adjacentFoe"].contains(&mv.target) { "normal" } else { mv.target };
        let h_ = b.holder();
        if b.valid_target(h_, src, rt) {
            if b.am(am).smart_target.unwrap_or(false) { b.amm(am).smart_target = Some(false); }
            if a.relay != RV::M(h_) { let n = b.mon_name(h_); b.add(&["-activate", &n, "ability: Storm Drain"]); }
            return RV::M(h_);
        }
        RV::Undef });
    h!(r, Ability, "waterveil", "onUpdate", |b, a| {
        let m = a.t();
        if b.p(m).status == "brn" { let n = b.mon_name(m); b.add(&["-activate", &n, "ability: Water Veil"]); b.cure_status(m); }
        RV::Undef });
    h!(r, Ability, "waterveil", "onSetStatus", |b, a| {
        if a.relay != RV::S(id("brn")) { return RV::Undef; }
        let from_status = a.src_eff.map(|e| match e.kind { Kind::Move => e.am.map(|x| b.am(x).base.status.is_some()).unwrap_or(false), _ => b.dex.eff(e.kind, e.id).s("status").is_some() }).unwrap_or(false);
        if from_status { let n = b.mon_name(a.t()); b.add(&["-immune", &n, "[from] ability: Water Veil"]); }
        RV::B(false) });
    h!(r, Ability, "baddreams", "onResidual", |b, a| {
        let m = a.t(); if b.p(m).hp == 0 { return RV::Undef; }
        for t in b.foes(m) {
            if b.p(t).status == "slp" || b.has_ability(t, "comatose") { let d = b.p(t).base_maxhp as f64 / 8.0; b.damage(d, Some(t), Some(m), None, false); }
        }
        RV::Undef });
    h!(r, Ability, "aurabreak", "onStart", |b, a| { RV::Undef });
    h!(r, Ability, "aurabreak", "onAnyTryPrimaryHit", |b, a| {
        let t = a.t(); let am = a.am();
        if a.source == Some(t) || b.am(am).category == "Status" { return RV::Undef; }
        b.amm(am).set_misc("hasAuraBreak", 1.0); RV::Undef });
    h!(r, Ability, "darkaura", "onStart", |b, a| { RV::Undef });
    h!(r, Ability, "darkaura", "onAnyBasePower", |b, a| { super::abilities::aura_bp(b, a, "Dark", "darkaura") });
    h!(r, Ability, "powerconstruct", "onResidual", |b, a| {
        let m = a.t();
        if b.base_base(m) != "zygarde" || b.p(m).transformed || b.p(m).hp == 0 { return RV::Undef; }
        if b.p(m).species == "zygardecomplete" || b.p(m).hp as f64 > b.p(m).maxhp as f64 / 2.0 { return RV::Undef; }
        let n = b.mon_name(m); b.add(&["-activate", &n, "ability: Power Construct"]);
        // formeChange('Zygarde-Complete', this.effect, true): HP rises with the new max HP (updateMaxHp), the ability is set again
        b.forme_change_permanent(m, id("zygardecomplete"), Some(Eff::new(Kind::Ability, id("powerconstruct"))));
        // canMegaEvo = canMegaEvo === false ? false : actions.canMegaEvo(pokemon): Zygardite's stone is for Zygarde-Complete
        if !b.mega_spent(m) { let c = b.can_mega_evo_of(m); b.pm(m).can_mega_evo = c; }
        RV::Undef });

    // ---------- moves ----------
    // Thousand Arrows (ignoreImmunity Ground and the smackdown volatile are data): neutral on a Flying type that isn't grounded
    h!(r, Move, "thousandarrows", "onEffectiveness", |b, a| {
        let am = a.am(); if b.am(am).mtype != "Ground" { return RV::Undef; }
        let Some(t) = a.target.mon() else { return RV::Undef };
        let ty = b.eff_type;
        let immune = !b.run_immunity_type(t, "Ground", false);
        b.eff_type = ty;
        if immune && b.has_type(t, "Flying") { return RV::N(0.0); }
        RV::Undef });
    h!(r, Move, "thousandwaves", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if b.p(s).is_active { let e = a.src_eff; b.add_volatile_ex(t, "trapped", Some(s), e, Some("trapper")); }
        RV::Undef });
    h!(r, Cond, "trapped", "onTrapPokemon", |b, a| { let m = a.t(); b.try_trap(m, false); RV::Undef });
    h!(r, Cond, "trapped", "onStart", |b, a| { let n = b.mon_name(a.t()); b.add(&["-activate", &n, "trapped"]); RV::Undef });
    h!(r, Move, "coreenforcer", "onHit", |b, a| { let t = a.t(); core_enforcer(b, t); RV::Undef });
    h!(r, Move, "coreenforcer", "onAfterSubDamage", |b, a| { let t = a.t(); core_enforcer(b, t); RV::Undef });
    h!(r, Cond, "gastroacid", "onStart", |b, a| {
        let m = a.t();
        if b.has_item(m, "abilityshield") { return RV::B(false); }
        let n = b.mon_name(m); b.add(&["-endability", &n]);
        let ab = b.p(m).ability;
        b.single_event("End", Eff::new(Kind::Ability, ab), Some(SLoc::Ability(m)), Tgt::Mon(m), Some(m), Some(Eff::cond(id("gastroacid"))), RV::Undef);
        RV::Undef });
    h!(r, Cond, "gastroacid", "onCopy", |b, a| { let m = a.t(); if b.ab_data(m).cantsuppress { b.remove_volatile(m, "gastroacid"); } RV::Undef });
    h!(r, Move, "darkvoid", "onTry", |b, a| {
        let s = a.t(); let am = a.am();
        if b.dex.species.get(b.p(s).species).map(|x| x.base_species) == Some("darkrai") || b.am(am).has_bounced { return RV::Undef; }
        let n = b.mon_name(s); b.add(&["-fail", &n, "move: Dark Void"]);
        RV::Null });
    // Ion Deluge (Plasma Fists' pseudoWeather; duration 1: it ends at this turn's residual): Normal moves become Electric
    h!(r, Cond, "iondeluge", "onFieldStart", |b, a| { RV::Undef });
    h!(r, Cond, "iondeluge", "onModifyType", |b, a| { let am = a.am(); if b.am(am).mtype == "Normal" { b.amm(am).mtype = "Electric"; } RV::Undef });
}
