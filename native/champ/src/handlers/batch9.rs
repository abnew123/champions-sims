//! Handlers ported 2026-11-07, batch 9 (champ-battle-v43): what Team search's M-B calibration sims reported unsupported (Bug Bite, Cute
//! Charm with Attract, Forecast, Solar Blade, Shed Tail, Gluttony, Poison Heal, Hunger Switch with Aura Wheel, Cud Chew, Merciless,
//! Spirit Shackle, Copycat, Fling, Heat Crash, Instruct), Assault Vest (the user, 2026-11-07: it may come to the game), and everything
//! else the v43 audit's sweep (`champ missing` crossed with pssim/results/v43_audit/effects_used.json) found on real M-B or M-C sets.
//! Each follows data/moves.js, abilities.js, items.js and conditions.js of the pinned Showdown (champions mod where it overrides);
//! message-only code is reduced to log lines. Genders come from the state (export_state.js with {v43: true}); battle.lastMove from
//! Battle::last_move_id; Fling's move.onHit from ActiveMove::fling_item (sim.rs run_move_effects calls fling_hit).
use super::Reg;
use crate::battle::*;
use crate::dex::*;
use crate::h;
use crate::sim::simple_action;
use crate::state::*;

fn boosts_of(rv: &RV) -> Boosts { if let RV::Boosts(b) = rv { b.clone() } else { vec![] } }
fn is_berry(b: &Battle, it: Id) -> bool { b.dex.items.get(it).map(|i| i.b("isBerry")).unwrap_or(false) }
/// `if (item.onEat)`: the item has an onEat callback (a function or a truthy constant)
fn has_on_eat(b: &Battle, it: Id) -> bool {
    b.dex.items.get(it).and_then(|i| i.cbs.get("onEat")).map(|c| !c.absent && c.cval != Some(CVal::Bool(false))).unwrap_or(false)
}
fn item_name(b: &Battle, it: Id) -> Id { b.dex.items.get(it).map(|x| x.name).unwrap_or(it) }
/// pokemon.deductPP(move, amount): the PP actually taken (0 when the move isn't known or has none left)
fn deduct_pp_amount(b: &mut Battle, m: MonRef, mid: Id, amount: i64) -> i64 {
    let p = b.pm(m);
    let Some(s) = p.move_slots.iter_mut().find(|s| s.id == mid) else { return 0 };
    s.used = true;
    if s.pp == 0 { return 0; }
    let mut amount = if amount == 0 { 1 } else { amount };
    s.pp -= amount;
    if s.pp < 0 { amount += s.pp; s.pp = 0; }
    amount
}
/// pokemon.getTypes(true): the types after the Type event, without the added type
fn types_ex(b: &mut Battle, m: MonRef) -> Vec<Id> {
    let base = b.p(m).types.clone();
    let mut t = match b.run_event("Type", Tgt::Mon(m), None, None, RV::Types(base.clone()), false, false) { RV::Types(t) => t, _ => base };
    if t.is_empty() { t.push("Normal"); }
    t
}
/// pokemon.setType(types) (not enforced): Arceus and Silvally keep theirs
fn set_type(b: &mut Battle, m: MonRef, types: Vec<Id>) -> bool {
    let num = b.dex.species.get(b.p(m).species).map(|s| s.num).unwrap_or(0);
    if num == 493 || num == 773 { return false; }
    let p = b.pm(m); p.types = types; p.added_type = ""; true
}
/// formeChange(species, source) that isn't permanent (Champions mod): setSpecies (ModifySpecies, types, stats, weight, speed) and the log
fn forme_change_temp(b: &mut Battle, m: MonRef, sp: Id, source: Option<Eff>) {
    let src = source.or(b.effect);
    let r = b.run_event("ModifySpecies", Tgt::Mon(m), None, src, RV::S(sp), false, false);
    let sp = match r { RV::S(s) if !s.is_empty() => s, _ => sp };
    b.set_species(m, sp);
    if b.logging {
        let n = b.mon_name(m); let name = b.dex.species.get(sp).map(|s| s.name).unwrap_or(sp);
        match source.filter(|e| e.kind == Kind::Ability) { Some(e) => { let f = format!("[from] ability: {}", b.dex.eff(Kind::Ability, e.id).name); b.add(&["-formechange", &n, name, "[msg]", &f]); }
                                                            None => b.add(&["-formechange", &n, name]) }
    }
}
/// pokemon.ignoringItem(true) (Fling): inactive, Embargo, Magic Room, or Klutz whatever the item
fn ignoring_item_fling(b: &Battle, m: MonRef) -> bool {
    let p = b.p(m);
    if !p.is_active { return true; }
    if find(&p.volatiles, "embargo").is_some() || find(&b.field.pseudo, "magicroom").is_some() { return true; }
    b.has_ability(m, "klutz")
}
/// Bug Bite / Pluck onHit: the user takes and eats the target's berry
fn steal_eat(b: &mut Battle, a: &HArgs, name: &str) -> RV {
    let (t, s) = (a.t(), a.s()); let e = a.src_eff;
    let item = b.p(t).item;
    if b.p(s).hp > 0 && is_berry(b, item) && b.take_item(t, Some(s)).is_some() {
        if b.logging { let (tn, sn) = (b.mon_name(t), b.mon_name(s)); let nm = item_name(b, item);
                       b.add(&["-enditem", &tn, nm, "[from] stealeat", &format!("[move] {}", name), &format!("[of] {}", sn)]); }
        if b.single_event("Eat", Eff::new(Kind::Item, item), Some(SLoc::Item(t)), Tgt::Mon(s), Some(s), e, RV::Undef).truthy() {
            b.run_event("EatItem", Tgt::Mon(s), Some(s), e, RV::S(item), false, false);
        }
        if has_on_eat(b, item) { b.pm(s).ate_berry = true; }
    }
    RV::Undef
}
/// Fling's move.onHit (sim.rs run_move_effects): the flung berry is eaten by the target, or the item's fling.effect runs on it
pub fn fling_hit(b: &mut Battle, t: MonRef, s: MonRef, am: usize) -> RV {
    let Some(item) = b.am(am).fling_item else { return RV::Undef };
    let e = Eff::mv(b.am(am).id, am);
    if is_berry(b, item) {
        if b.single_event("Eat", Eff::new(Kind::Item, item), Some(SLoc::Item(s)), Tgt::Mon(t), Some(s), Some(e), RV::Undef).truthy() {
            b.run_event("EatItem", Tgt::Mon(t), Some(s), Some(e), RV::S(item), false, false);
        }
        if has_on_eat(b, item) { b.pm(t).ate_berry = true; }
    } else {
        // the item's fling.effect(target), registered as Item:<id>.fling.effect
        match b.reg.get(&(Kind::Item, item, id("fling.effect"))).copied() {
            Some(f) => { let mut x = HArgs { relay: RV::Undef, has_relay: false, target: Tgt::Mon(t), source: Some(s), src_eff: Some(e) }; f(b, &mut x); }
            None => b.unsupported(format!("Item:{}.fling.effect", item)),
        }
    }
    RV::B(true)
}
/// two-turn moves without a weather or item shortcut (Fly, Bounce, Dig, Dive, Sky Attack): onTryMove
fn two_turn(b: &mut Battle, a: &HArgs) -> RV {
    let att = a.t(); let def = a.source; let e = a.src_eff.unwrap();
    if b.remove_volatile(att, e.id) { return RV::Undef; }
    if b.logging { let n = b.mon_name(att); let mn = b.dex.mv(e.id).eff.name; b.add(&["-prepare", &n, mn]); }
    if !b.run_event("ChargeMove", Tgt::Mon(att), def, Some(e), RV::Undef, false, false).truthy() { return RV::Undef; }
    b.add_volatile_src_eff(att, "twoturnmove", def, Some(e)); RV::Null
}
/// the semi-invulnerable states' onInvulnerability: only the listed moves hit
fn invuln(b: &Battle, a: &HArgs, hits: &[&str]) -> RV {
    let Some(am) = a.am_opt() else { return RV::B(false) };
    if hits.contains(&b.am(am).id) { RV::Undef } else { RV::B(false) }
}
/// Mean Look / Block / Spirit Shackle: the target is trapped while the user stays in (Showdown's linked trapped / trapper volatiles)
fn trap(b: &mut Battle, t: MonRef, s: MonRef, e: Option<Eff>) -> RV { b.add_volatile_ex(t, "trapped", Some(s), e, Some("trapper")) }
/// getLastDamagedBy(true): the last damaging attack (damageValue a number: status moves don't count) on m from the other side. (Metal
/// Burst's port in moves.rs leaves the status-move filter out; unchanged in v43, so its games stay as v42 played them)
fn last_damaged_by(b: &Battle, m: MonRef) -> Option<Attack> { b.p(m).attacked_by.iter().filter(|x| x.numeric && !b.is_ally(m, x.source)).last().cloned() }
/// Mimicry's onTerrainChange
fn mimicry(b: &mut Battle, m: MonRef) {
    let types: Vec<Id> = match b.field.terrain {
        "electricterrain" => vec!["Electric"], "grassyterrain" => vec!["Grass"], "mistyterrain" => vec!["Fairy"], "psychicterrain" => vec!["Psychic"],
        _ => b.dex.species.get(b.p(m).base_species).map(|s| s.types.clone()).unwrap_or_default(),
    };
    let old = b.get_types(m);
    if old.join(",") == types.join(",") || !set_type(b, m, types.clone()) { return; }
    if b.logging {
        let n = b.mon_name(m);
        if !b.field.terrain.is_empty() || b.p(m).transformed { let ts = types.join("/"); b.add(&["-start", &n, "typechange", &ts, "[from] ability: Mimicry"]); }
        else { b.add(&["-activate", &n, "ability: Mimicry"]); b.add(&["-end", &n, "typechange", "[silent]"]); }
    }
}
/// Forecast's onWeatherChange
fn forecast(b: &mut Battle, m: MonRef) {
    if b.base_base(m) != "castform" || b.p(m).transformed { return; }
    let w = b.pokemon_effective_weather(m, None); let sp = b.p(m).species;
    let want = match w { "sunnyday" | "desolateland" => "castformsunny", "raindance" | "primordialsea" => "castformrainy", "hail" | "snowscape" => "castformsnowy", _ => "castform" };
    if b.p(m).is_active && sp != want { forme_change_temp(b, m, id(want), Some(Eff::new(Kind::Ability, id("forecast")))); }
}
/// Opportunist's copied boosts, kept in its ability state as "atk:1,spe:2" ("-" for the empty object Showdown keeps when none were
/// raised); applying them clears it
fn opp_boosts(b: &Battle) -> Option<Boosts> {
    let s = b.es_ref()?.get("boosts")?.s()?;
    Some(s.split(',').filter(|x| x.contains(':')).filter_map(|x| { let (k, v) = x.split_once(':')?; Some((boost_idx(k) as u8, v.parse().ok()?)) }).collect())
}
fn opp_apply(b: &mut Battle) -> RV {
    let Some(bo) = opp_boosts(b) else { return RV::Undef };
    let h_ = b.holder();
    b.boost(bo, Some(h_), None, None, false, false);
    b.es().del("boosts"); RV::Undef
}
/// Sticky Web's onSwitchIn
fn sticky_web(b: &mut Battle, m: MonRef) {
    if b.is_grounded(m, false) != Some(true) || b.has_item(m, "heavydutyboots") { return; }
    let n = b.mon_name(m); b.add(&["-activate", &n, "move: Sticky Web"]);
    let foe0 = b.sides[1 - m.0 as usize].active[0].map(|i| (1 - m.0, i));
    let am = b.new_am(b.dex.active_move("stickyweb"));
    b.boost(vec![(4, -1)], Some(m), foe0, Some(Eff::mv(id("stickyweb"), am)), false, false);
}
/// Future Sight's delayed hit (futuremove onEnd): the stored move data hits whoever is in the slot, then Life Orb, then checkWin
fn future_hit(b: &mut Battle, t: MonRef) {
    let Some(st) = b.es_ref().cloned() else { return };
    let mv = st.get("move").and_then(|v| v.s()).unwrap_or(id("futuresight"));
    let Some(src) = st.source else { return };
    if b.p(t).fainted || t == src { return; }
    if b.logging { let n = b.mon_name(t); let x = format!("move: {}", b.dex.mv(mv).eff.name); b.add(&["-end", &n, &x]); }
    b.remove_volatile(t, "protect"); b.remove_volatile(t, "endure");
    // new Dex.Move(moveData): Future Sight's data with ignoreImmunity false; Infiltrator / Normalize of the user apply
    let am = b.new_am(b.dex.active_move(mv));
    { let x = b.amm(am); x.ignore_immunity = Some(IgnImm::All(false)); x.set_misc("futureHit", 1.0); }
    if b.has_ability(src, "infiltrator") { b.amm(am).infiltrates = true; }
    if b.has_ability(src, "normalize") { b.amm(am).mtype = "Normal"; }
    b.set_active_move(Some(am), Some(src), Some(t));
    b.try_spread_move_hit(vec![t], src, am);
    // Life Orb's handler runs with the item as the move: its category is not 'Status', so the user takes the recoil
    if b.p(src).is_active && b.has_item(src, "lifeorb") && src != t && !b.p(src).force_switch_flag {
        let d = b.p(src).base_maxhp as f64 / 10.0; b.damage(d, Some(src), Some(src), Some(Eff::new(Kind::Item, id("lifeorb"))), false);
    }
    b.active_move = None;
    b.check_win(None);
}

/// battle.skillSwap(source, target) (Wandering Spirit; the Skill Swap move's port in moves.rs is the same steps)
fn skill_swap(b: &mut Battle, s: MonRef, t: MonRef) -> RV {
    if b.p(s).fainted || b.p(t).fainted { return RV::B(false); }
    if b.has_vol(s, "dynamax") || b.has_vol(t, "dynamax") { return RV::B(false); }
    let (sa, ta) = (b.p(s).ability, b.p(t).ability);
    if b.dex.eff(Kind::Ability, sa).flag("failskillswap") || b.dex.eff(Kind::Ability, ta).flag("failskillswap") { return RV::B(false); }
    let se = Some(Eff::cond(id("skillswap")));
    let r1 = b.run_event("SetAbility", Tgt::Mon(t), Some(s), se, RV::S(sa), false, false); if !r1.truthy() { return r1; }
    let r2 = b.run_event("SetAbility", Tgt::Mon(s), Some(s), se, RV::S(ta), false, false); if !r2.truthy() { return r2; }
    if b.logging { let (n, o) = (b.mon_name(s), b.mon_name(t)); let (tn, sn) = (b.dex.eff(Kind::Ability, ta).name, b.dex.eff(Kind::Ability, sa).name);
                   if b.is_ally(s, t) { b.add(&["-activate", &n, "Skill Swap", "", "", &format!("[of] {}", o)]); } else { b.add(&["-activate", &n, "Skill Swap", tn, sn, &format!("[of] {}", o)]); } }
    b.single_event("End", Eff::new(Kind::Ability, sa), Some(SLoc::Ability(s)), Tgt::Mon(s), None, None, RV::Undef);
    b.single_event("End", Eff::new(Kind::Ability, ta), Some(SLoc::Ability(t)), Tgt::Mon(t), None, None, RV::Undef);
    b.pm(s).ability = ta; b.pm(t).ability = sa;
    let st1 = b.init_state(ta, Some(true)); b.pm(s).ability_state = st1;
    let st2 = b.init_state(sa, Some(true)); b.pm(t).ability_state = st2;
    b.single_event("Start", Eff::new(Kind::Ability, sa), Some(SLoc::Ability(t)), Tgt::Mon(t), None, None, RV::Undef);
    b.single_event("Start", Eff::new(Kind::Ability, ta), Some(SLoc::Ability(s)), Tgt::Mon(s), None, None, RV::Undef);
    RV::Undef
}

pub fn register(r: &mut Reg) {
    // ---------- reported unsupported by name in earlier ports (abilities.rs) ----------
    h!(r, Ability, "wanderingspirit", "onDamagingHit", |b, a| { let (t, s) = (a.t(), a.s()); if b.makes_contact(a.am(), s) { skill_swap(b, s, t); } RV::Undef });
    h!(r, Ability, "magician", "onAfterMoveSecondarySelf", |b, a| {
        let s = a.t(); let Some(am) = a.am_opt() else { return RV::Undef };
        let (mid, cat) = (b.am(am).id, b.am(am).category);
        if b.p(s).switch_flag == Some("true") || !b.p(s).item.is_empty() || b.has_vol(s, "gem") || mid == "fling" || cat == "Status" { return RV::Undef; }
        let mut ht: Vec<(MonRef, f64)> = b.am(am).hit_targets.iter().map(|m| (*m, b.p(*m).speed)).collect();
        b.speed_sort(&mut ht, |x| (None, 0.0, x.1, 0.0, 0.0));
        for (pk, _) in ht {
            if pk == s { continue; }
            let Some(it) = b.take_item(pk, Some(s)) else { continue };
            if !b.set_item(s, it, None, None) { b.pm(pk).item = it; continue; }
            if b.logging { let (n, o) = (b.mon_name(s), b.mon_name(pk)); let nm = item_name(b, it); b.add(&["-item", &n, nm, "[from] ability: Magician", &format!("[of] {}", o)]); }
            return RV::Undef;
        }
        RV::Undef });

    // ---------- requested by Team search (the M-B calibration sims' unsupported list) ----------
    h!(r, Move, "bugbite", "onHit", |b, a| { steal_eat(b, a, "Bug Bite") });
    h!(r, Move, "pluck", "onHit", |b, a| { steal_eat(b, a, "Pluck") });
    // Cute Charm and Attract (genders from the state)
    h!(r, Ability, "cutecharm", "onDamagingHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if b.makes_contact(a.am(), s) && b.rchance(3, 10) { let h_ = b.holder(); let _ = t; b.add_volatile(s, "attract", Some(h_), None); }
        RV::Undef });
    h!(r, Move, "attract", "onTryImmunity", |b, a| {
        let (t, s) = (a.t(), a.s()); let (g1, g2) = (b.p(t).gender, b.p(s).gender);
        RV::B((g1 == "M" && g2 == "F") || (g1 == "F" && g2 == "M")) });
    h!(r, Cond, "attract", "onStart", |b, a| {
        let m = a.t(); let Some(s) = a.source else { return RV::B(false) };
        let (g1, g2) = (b.p(m).gender, b.p(s).gender);
        if !((g1 == "M" && g2 == "F") || (g1 == "F" && g2 == "M")) { return RV::B(false); }
        if !b.run_event("Attract", Tgt::Mon(m), Some(s), None, RV::Undef, false, false).truthy() { return RV::B(false); }
        if b.logging {
            let (n, o) = (b.mon_name(m), b.mon_name(s));
            match a.src_eff.map(|e| e.id) { Some("cutecharm") => b.add(&["-start", &n, "Attract", "[from] ability: Cute Charm", &format!("[of] {}", o)]),
                                            Some("destinyknot") => b.add(&["-start", &n, "Attract", "[from] item: Destiny Knot", &format!("[of] {}", o)]),
                                            _ => b.add(&["-start", &n, "Attract"]) }
        }
        RV::Undef });
    h!(r, Cond, "attract", "onUpdate", |b, a| {
        let m = a.t(); let src = b.es_ref().and_then(|s| s.source);
        if let Some(src) = src { if !b.p(src).is_active && b.has_vol(m, "attract") { b.remove_volatile(m, "attract"); } }
        RV::Undef });
    h!(r, Cond, "attract", "onBeforeMove", |b, a| {
        let m = a.t();
        if b.logging { let n = b.mon_name(m); let o = b.es_ref().and_then(|s| s.source).map(|x| b.mon_name(x)).unwrap_or_default(); b.add(&["-activate", &n, "move: Attract", &format!("[of] {}", o)]); }
        if b.rchance(1, 2) { let n = b.mon_name(m); b.add(&["cant", &n, "Attract"]); return RV::B(false); }
        RV::Undef });
    h!(r, Cond, "attract", "onEnd", |b, a| { let n = b.mon_name(a.t()); b.add(&["-end", &n, "Attract", "[silent]"]); RV::Undef });
    // Castform
    h!(r, Ability, "forecast", "onStart", |b, a| {
        let m = a.t(); b.single_event("WeatherChange", Eff::new(Kind::Ability, id("forecast")), Some(SLoc::Ability(m)), Tgt::Mon(m), None, None, RV::Undef); RV::Undef });
    h!(r, Ability, "forecast", "onWeatherChange", |b, a| { let m = a.t(); forecast(b, m); RV::Undef });
    // Solar Blade: Solar Beam's code
    h!(r, Move, "solarblade", "onTryMove", |b, a| {
        let att = a.t(); let def = a.source; let e = a.src_eff.unwrap();
        if b.remove_volatile(att, e.id) { return RV::Undef; }
        if b.logging { let n = b.mon_name(att); b.add(&["-prepare", &n, "Solar Blade"]); }
        let w = b.pokemon_effective_weather(att, None);
        if w == "sunnyday" || w == "desolateland" { return RV::Undef; }
        if !b.run_event("ChargeMove", Tgt::Mon(att), def, Some(e), RV::Undef, false, false).truthy() { return RV::Undef; }
        b.add_volatile_src_eff(att, "twoturnmove", def, Some(e)); RV::Null });
    h!(r, Move, "solarblade", "onBasePower", |b, a| {
        let m = a.t(); let w = b.pokemon_effective_weather(m, None);
        if ["raindance", "primordialsea", "sandstorm", "hail", "snowscape"].contains(&w) { return b.cm(0.5, 1.0); } RV::Undef });
    // Shed Tail (the Substitute passes to the switch-in: sim.rs copy_volatile_from with 'shedtail')
    h!(r, Move, "shedtail", "onTryHit", |b, a| {
        let s = a.t();
        if b.can_switch(s.0) == 0 || b.has_vol(s, "commanded") { let n = b.mon_name(s); b.add(&["-fail", &n]); return RV::NotFail; }
        if b.has_vol(s, "substitute") { let n = b.mon_name(s); b.add(&["-fail", &n, "move: Shed Tail"]); return RV::NotFail; }
        if b.p(s).hp as f64 <= (b.p(s).maxhp as f64 / 2.0).ceil() { let n = b.mon_name(s); b.add(&["-fail", &n, "move: Shed Tail", "[weak]"]); return RV::NotFail; }
        RV::Undef });
    h!(r, Move, "shedtail", "onHit", |b, a| {
        let t = a.t(); let d = (b.p(t).maxhp as f64 / 2.0).ceil() as i64; let (src, eff) = (a.source, b.effect);
        b.direct_damage(d, t, src, eff); RV::Undef });
    h!(r, Move, "shedtail", "self.onHit", |b, a| { let s = a.t(); b.pm(s).skip_before_switch_out = true; RV::Undef });
    // Gluttony (only the flag: no pinch berry is in M-B or M-C), Poison Heal
    h!(r, Ability, "gluttony", "onStart", |b, a| { let m = a.t(); b.pm(m).ability_state.set("gluttony", SV::B(true)); RV::Undef });
    h!(r, Ability, "gluttony", "onDamage", |b, a| { let m = a.t(); b.pm(m).ability_state.set("gluttony", SV::B(true)); RV::Undef });
    h!(r, Ability, "poisonheal", "onDamage", |b, a| {
        let t = a.t(); let eid = a.src_eff.map(|e| e.id);
        if eid == Some("psn") || eid == Some("tox") { let d = b.p(t).base_maxhp as f64 / 8.0; b.heal(d, None, None, None); return RV::B(false); }
        RV::Undef });
    // Morpeko
    h!(r, Ability, "hungerswitch", "onResidual", |b, a| {
        let m = a.t(); let sp = b.p(m).species;
        if b.dex.species.get(sp).map(|s| s.base_species) != Some("morpeko") { return RV::Undef; }
        let want = if sp == "morpeko" { "morpekohangry" } else { "morpeko" };
        forme_change_temp(b, m, id(want), None); RV::Undef });
    h!(r, Move, "aurawheel", "onTry", |b, a| {
        let s = a.t();
        if b.dex.species.get(b.p(s).species).map(|x| x.base_species) == Some("morpeko") { return RV::Undef; }
        let n = b.mon_name(s); b.add(&["-fail", &n, "move: Aura Wheel"]); RV::Null });
    h!(r, Move, "aurawheel", "onModifyType", |b, a| {
        let m = a.t(); let am = a.am(); let ty = if b.p(m).species == "morpekohangry" { "Dark" } else { "Electric" }; b.amm(am).mtype = ty; RV::Undef });
    // Cud Chew: the berry comes back for one more bite at the end of the next turn (this turn's when eaten during the residual)
    h!(r, Ability, "cudchew", "onEatItem", |b, a| {
        let RV::S(item) = a.relay else { return RV::Undef };
        if is_berry(b, item) && !a.src_eff.map(|e| e.id == "bugbite" || e.id == "pluck").unwrap_or(false) {
            let empty = b.queue.is_empty();
            let es = b.es(); es.set("berry", SV::E(EType::Item, item)); es.set("counter", SV::N(if empty { 1.0 } else { 2.0 }));
        }
        RV::Undef });
    h!(r, Ability, "cudchew", "onResidual", |b, a| {
        let m = a.t();
        let berry = match b.es_ref().and_then(|s| s.get("berry")) { Some(SV::E(_, x)) => *x, Some(SV::S(x)) => *x, _ => return RV::Undef };
        if berry.is_empty() || b.p(m).hp == 0 { return RV::Undef; }
        let c = b.es().n("counter").unwrap_or(0.0) - 1.0; b.es().set("counter", SV::N(c));
        if c <= 0.0 {
            if b.logging { let n = b.mon_name(m); let nm = item_name(b, berry); b.add(&["-activate", &n, "ability: Cud Chew"]); b.add(&["-enditem", &n, nm, "[eat]"]); }
            if b.single_event("Eat", Eff::new(Kind::Item, berry), None, Tgt::Mon(m), None, None, RV::Undef).truthy() {
                b.run_event("EatItem", Tgt::Mon(m), None, None, RV::S(berry), false, false);
            }
            if has_on_eat(b, berry) { b.pm(m).ate_berry = true; }
            let es = b.es(); es.del("berry"); es.del("counter");
        }
        RV::Undef });
    h!(r, Ability, "merciless", "onModifyCritRatio", |b, a| {
        if let Some(t) = a.source { let st = b.p(t).status; if st == "psn" || st == "tox" { return RV::N(5.0); } } RV::Undef });
    h!(r, Move, "spiritshackle", "secondaries.0.onHit", |b, a| {
        let (t, s) = (a.t(), a.s()); if b.p(s).is_active { let e = a.src_eff; trap(b, t, s, e); } RV::Undef });
    h!(r, Move, "copycat", "onHit", |b, a| {
        let m = a.t(); let am = a.am();
        let Some(lm) = b.last_move_id else { return RV::Undef };
        let tm = &b.dex.mv(lm).tmpl;
        if tm.flag("failcopycat") || tm.is_z || tm.is_max { return RV::B(false); }
        let ni = b.new_am(b.dex.active_move(lm)); b.use_move(ni, m, None, Some(Eff::mv(id("copycat"), am)));
        RV::Undef });
    // Fling (move.onHit: ActiveMove::fling_item, run by fling_hit; the item leaves at the next Update: the fling volatile)
    h!(r, Move, "fling", "onPrepareHit", |b, a| {
        let s = a.s(); let am = a.am(); let e = Eff::mv(b.am(am).id, am);
        if ignoring_item_fling(b, s) { return RV::B(false); }
        let item = b.p(s).item;
        if item.is_empty() { return RV::B(false); }   // no item: no fling data
        if !b.single_event("TakeItem", Eff::new(Kind::Item, item), Some(SLoc::Item(s)), Tgt::Mon(s), Some(s), Some(e), RV::S(item)).truthy() { return RV::B(false); }
        let Some(fl) = b.dex.items.get(item).and_then(|d| d.raw.get("fling")).filter(|x| x.is_object()).cloned() else { return RV::B(false) };
        b.amm(am).base_power = fl["basePower"].as_f64().unwrap_or(0.0);
        if is_berry(b, item) {
            if b.has_ability(s, "cudchew") { let ab = b.p(s).ability; b.single_event("EatItem", Eff::new(Kind::Ability, ab), Some(SLoc::Ability(s)), Tgt::Mon(s), Some(s), Some(e), RV::S(item)); }
            b.amm(am).fling_item = Some(item);
        } else if fl.get("effect").map(|x| x == "__fn").unwrap_or(false) {
            b.amm(am).fling_item = Some(item);
        } else {
            let mut secs = b.am(am).secondaries.clone().unwrap_or_default();
            let part = id(&format!("secondaries.{}", secs.len()));
            if let Some(st) = fl.get("status").and_then(|x| x.as_str()) { secs.push(HitEff { part, status: Some(id(&to_id(st))), ..Default::default() }); }
            else if let Some(v) = fl.get("volatileStatus").and_then(|x| x.as_str()) { secs.push(HitEff { part, volatile_status: Some(id(&to_id(v))), ..Default::default() }); }
            b.amm(am).secondaries = Some(secs);
        }
        b.add_volatile(s, "fling", None, None);
        RV::Undef });
    h!(r, Item, "whiteherb", "fling.effect", |b, a| {
        let t = a.t(); let mut any = false;
        for k in 0..7 { if b.p(t).boosts[k] < 0 { b.pm(t).boosts[k] = 0; any = true; } }
        if any { let n = b.mon_name(t); b.add(&["-clearnegativeboost", &n, "[silent]"]); }
        RV::Undef });
    h!(r, Item, "mentalherb", "fling.effect", |b, a| {
        let t = a.t(); let conds = ["attract", "taunt", "encore", "torment", "disable", "healblock"];
        if conds.iter().any(|c| b.has_vol(t, c)) { for c in conds { b.remove_volatile(t, c); } }
        RV::Undef });
    h!(r, Cond, "fling", "onUpdate", |b, a| {
        let m = a.t(); let item = b.p(m).item;
        b.set_item(m, "", None, None);
        { let p = b.pm(m); p.last_item = item; p.used_item_this_turn = true; }
        if b.logging { let n = b.mon_name(m); let nm = item_name(b, item); b.add(&["-enditem", &n, nm, "[from] move: Fling"]); }
        b.run_event("AfterUseItem", Tgt::Mon(m), None, None, RV::S(item), false, false);
        b.remove_volatile(m, "fling"); RV::Undef });
    // Heat Crash: Heavy Slam's code (the weight ratio)
    h!(r, Move, "heatcrash", "onTryHit", |b, a| { RV::Undef });   // Dynamax only
    h!(r, Move, "heatcrash", "basePowerCallback", |b, a| {
        let (t, s) = (a.t(), a.s()); let tw = b.get_weight(t); let sw = b.get_weight(s);
        RV::N(if sw >= tw * 5 { 120.0 } else if sw >= tw * 4 { 100.0 } else if sw >= tw * 3 { 80.0 } else if sw >= tw * 2 { 60.0 } else { 40.0 }) });
    h!(r, Move, "instruct", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        let Some(lm) = b.p(t).last_move else { return RV::B(false) };
        if b.has_vol(t, "dynamax") { return RV::B(false); }
        let tm = &b.dex.mv(lm).tmpl;
        let pp_out = b.p(t).move_slots.iter().find(|x| x.id == lm).map(|x| x.pp <= 0).unwrap_or(false);
        if tm.flag("failinstruct") || tm.is_z || tm.is_max || tm.flag("charge") || tm.flag("recharge") || b.has_vol(t, "beakblast") || b.has_vol(t, "focuspunch")
           || b.has_vol(t, "shelltrap") || pp_out { return RV::B(false); }
        if b.logging { let (n, o) = (b.mon_name(t), b.mon_name(s)); b.add(&["-singleturn", &n, "move: Instruct", &format!("[of] {}", o)]); }
        // queue.prioritizeAction(queue.resolveAction({choice: 'move', pokemon: target, moveid, targetLoc})[0]): order 3, no source effect
        let am2 = b.new_am(b.dex.active_move(lm));
        let mut act = simple_action(Choice::Move, 200.0); act.pokemon = Some(t); act.am = Some(am2); act.target_loc = b.p(t).last_move_target_loc.unwrap_or(0);
        let acts = b.resolve_action(act, false);
        if let Some(mut x) = acts.into_iter().next() { x.source_effect = None; x.order = 3.0; b.queue.insert(0, x); }
        RV::Undef });
    // Assault Vest (the user, 2026-11-07: may come to the game)
    h!(r, Item, "assaultvest", "onModifySpD", |b, a| { b.cm(1.5, 1.0) });
    h!(r, Item, "assaultvest", "onDisableMove", |b, a| {
        let m = a.t(); let ids: Vec<Id> = b.p(m).move_slots.iter().map(|s| s.id).collect();
        for mid in ids { if b.dex.mv(mid).tmpl.category == "Status" && mid != "mefirst" { b.disable_move(m, mid, false, ""); } }
        RV::Undef });

    // ---------- the sweep: other effects real M-B / M-C sets use ----------
    // Endure (Protect's stall rules)
    h!(r, Move, "endure", "onPrepareHit", |b, a| {
        if !b.will_act() { return RV::B(false); }
        let m = a.t(); RV::B(b.run_event("StallMove", Tgt::Mon(m), None, None, RV::Undef, false, false).truthy()) });
    h!(r, Move, "endure", "onHit", |b, a| { let m = a.t(); b.add_volatile(m, "stall", None, None); RV::Undef });
    h!(r, Cond, "endure", "onStart", |b, a| { let n = b.mon_name(a.t()); b.add(&["-singleturn", &n, "move: Endure"]); RV::Undef });
    h!(r, Cond, "endure", "onDamage", |b, a| {
        let t = a.t();
        if b.eff_is(a.src_eff, EType::Move) && a.n() >= b.p(t).hp as f64 { let n = b.mon_name(t); b.add(&["-activate", &n, "move: Endure"]); return RV::N((b.p(t).hp - 1) as f64); }
        RV::Undef });
    // Piercing Drill: the champions mod's Unseen Fist (contact moves hit through Protect for a quarter)
    h!(r, Ability, "piercingdrill", "onHitProtect", |b, a| {
        let am = a.am(); let Some(d) = a.source else { return RV::Undef };
        if b.am(am).flag("contact") { let slot = b.slot_name(d); b.amm(am).hd(slot).bypass_protect = true; return RV::B(false); }
        RV::Undef });
    h!(r, Ability, "sapsipper", "onAllyTryHitSide", |b, a| {
        let t = a.t(); let Some(s) = a.source else { return RV::Undef }; let h_ = b.holder();
        if s == h_ || !b.is_ally(t, s) { return RV::Undef; }
        if b.am(a.am()).mtype == "Grass" { b.boost(vec![(0, 1)], Some(h_), None, None, false, false); }
        RV::Undef });
    h!(r, Move, "tidyup", "onHit", |b, a| {
        let m = a.t(); let mut success = false;
        for x in b.all_active() { if b.remove_volatile(x, "substitute") { success = true; } }
        for side in [m.0, 1 - m.0] { for c in ["spikes", "toxicspikes", "stealthrock", "stickyweb", "gmaxsteelsurge"] { if b.remove_side_condition(side, c) { success = true; } } }
        if success { let n = b.mon_name(m); b.add(&["-activate", &n, "move: Tidy Up"]); }
        let r = b.boost(vec![(0, 1), (4, 1)], Some(m), Some(m), None, false, true);
        RV::B(r.truthy() || success) });
    h!(r, Move, "watershuriken", "basePowerCallback", |b, a| {
        let s = a.s(); let bp = b.am(a.am()).base_power;
        if b.p(s).species == "greninjaash" && b.has_ability(s, "battlebond") && !b.p(s).transformed { return RV::N(bp + 5.0); }
        RV::N(bp) });
    h!(r, Ability, "rivalry", "onBasePower", |b, a| {
        let (at, de) = (a.t(), a.s()); let (g1, g2) = (b.p(at).gender, b.p(de).gender);
        if !g1.is_empty() && !g2.is_empty() { return if g1 == g2 { b.cm(1.25, 1.0) } else { b.cm(0.75, 1.0) }; }
        RV::Undef });
    h!(r, Move, "fellstinger", "onAfterMoveSecondarySelf", |b, a| {
        let m = a.t();
        if a.source.map(|t| b.p(t).fainted || b.p(t).hp <= 0).unwrap_or(true) { let e = a.src_eff; b.boost(vec![(0, 3)], Some(m), Some(m), e, false, false); }
        RV::Undef });
    h!(r, Ability, "symbiosis", "onAllyAfterUseItem", |b, a| {
        let pk = a.t(); if b.p(pk).switch_flag.is_some() { return RV::Undef; }
        let src = b.holder();
        let Some(my) = b.take_item(src, None) else { return RV::Undef };
        let eff = b.effect;
        let ok = b.single_event("TakeItem", Eff::new(Kind::Item, my), Some(SLoc::Item(src)), Tgt::Mon(pk), Some(src), eff, RV::S(my)).truthy() && b.set_item(pk, my, None, None);
        if !ok { b.pm(src).item = my; return RV::Undef; }
        if b.logging { let (n, o) = (b.mon_name(src), b.mon_name(pk)); let nm = item_name(b, my); b.add(&["-activate", &n, "ability: Symbiosis", nm, &format!("[of] {}", o)]); }
        RV::Undef });
    h!(r, Cond, "stickyweb", "onSideStart", |b, a| { RV::Undef });
    h!(r, Cond, "stickyweb", "onSwitchIn", |b, a| { let m = a.t(); sticky_web(b, m); RV::Undef });
    // Future Sight: a slot condition that hits at the end of the turn after next
    h!(r, Move, "futuresight", "onTry", |b, a| {
        let s = a.t(); let am = a.am();
        if b.am(am).misc("futureHit").is_some() { return RV::Undef; }   // the delayed hit's own move (new Dex.Move(moveData) has no onTry)
        let Some(t) = a.source else { return RV::B(false) };
        if !b.add_slot_condition(t, id("futuremove"), Some(s), None).truthy() { return RV::B(false); }
        let pos = b.p(t).position;
        if let Some(st) = find_mut(&mut b.sides[t.0 as usize].slot_conditions[pos as usize], "futuremove") { st.set("move", SV::S(id("futuresight"))); st.source = Some(s); }
        let n = b.mon_name(s); b.add(&["-start", &n, "move: Future Sight"]);
        RV::NotFail });
    h!(r, Cond, "futuremove", "onStart", |b, a| {
        let Some(t) = a.target.mon() else { return RV::Undef };
        let slot = b.slot_name(t); let turn = b.turn;
        let es = b.es(); es.set("targetSlot", SV::S(slot)); es.set("endingTurn", SV::N((turn - 1 + 2) as f64)); RV::Undef });
    h!(r, Cond, "futuremove", "onResidual", |b, a| {
        let ending = b.es_ref().and_then(|s| s.n("endingTurn")).unwrap_or(0.0);
        if (((b.turn - 1) % 255) as f64) < ending { return RV::Undef; }
        let slot = b.es_ref().and_then(|s| s.get("targetSlot")).and_then(|v| v.s()).unwrap_or("");
        let sb = slot.as_bytes(); if sb.len() < 3 { return RV::Undef; }
        let (side, pos) = (sb[1] - b'1', sb[2] - b'a');
        b.remove_slot_condition(side, pos, id("futuremove")); RV::Undef });
    h!(r, Cond, "futuremove", "onEnd", |b, a| { if let Some(t) = a.target.mon() { future_hit(b, t); } RV::Undef });
    h!(r, Item, "bigroot", "onTryHeal", |b, a| {
        if a.src_eff.map(|e| ["drain", "leechseed", "ingrain", "aquaring", "strengthsap"].contains(&e.id)).unwrap_or(false) { return b.cm(5324.0, 4096.0); } RV::Undef });
    h!(r, Ability, "slushrush", "onModifySpe", |b, a| { let w = b.effective_weather(); if w == "hail" || w == "snowscape" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Ability, "heavymetal", "onModifyWeight", |b, a| { RV::N(a.n() * 2.0) });
    h!(r, Ability, "lightmetal", "onModifyWeight", |b, a| { RV::N(Battle::trunc(a.n() / 2.0) as f64) });
    h!(r, Ability, "innardsout", "onDamagingHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if b.p(t).hp == 0 {
            let am = a.am(); let mut d = a.n();
            if !b.am(am).smart_target.unwrap_or(false) { d += b.am(am).total_damage as f64; }
            b.damage(d, Some(s), Some(t), None, false);
        }
        RV::Undef });
    h!(r, Ability, "bigpecks", "onTryBoost", |b, a| {
        let t = a.t(); if a.source == Some(t) { return RV::Undef; }
        let bo = boosts_of(&a.relay);
        if bo.iter().any(|(k, v)| *k == 1 && *v < 0) {
            let secondary = a.src_eff.map(|e| e.kind == Kind::Move && !e.part.is_empty()).unwrap_or(false);
            if !secondary && a.src_eff.map(|e| e.id) != Some("octolock") { let n = b.mon_name(t); b.add(&["-fail", &n, "unboost", "Defense", "[from] ability: Big Pecks"]); }
            return RV::Boosts(bo.into_iter().filter(|(k, _)| *k != 1).collect());
        }
        RV::Undef });
    h!(r, Ability, "whitesmoke", "onTryBoost", |b, a| {
        let t = a.t(); if a.source == Some(t) { return RV::Undef; }
        let bo = boosts_of(&a.relay);
        if bo.iter().any(|(_, v)| *v < 0) { return RV::Boosts(bo.into_iter().filter(|(_, v)| *v >= 0).collect()); }
        RV::Undef });
    h!(r, Move, "gravapple", "onBasePower", |b, a| { if find(&b.field.pseudo, "gravity").is_some() { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Move, "growth", "onModifyMove", |b, a| {
        let m = a.t(); let am = a.am();
        if b.has_ability(m, "megasol") && b.effective_weather() != "sunnyday" { b.amm(am).base.boosts = None; }
        else { let w = b.pokemon_effective_weather(m, None); if w == "sunnyday" || w == "desolateland" { b.amm(am).base.boosts = Some(vec![(0, 2), (2, 2)]); } }
        RV::Undef });
    h!(r, Move, "topsyturvy", "onHit", |b, a| {
        let t = a.t(); let mut any = false;
        for k in 0..7 { let v = b.p(t).boosts[k]; if v != 0 { b.pm(t).boosts[k] = -v; any = true; } }
        if !any { return RV::B(false); }
        let n = b.mon_name(t); b.add(&["-invertboost", &n, "[from] move: Topsy-Turvy"]); RV::Undef });
    h!(r, Ability, "hustle", "onModifyAtk", |b, a| { RV::N(b.modify(a.n(), 1.5) as f64) });
    h!(r, Ability, "hustle", "onSourceModifyAccuracy", |b, a| {
        if let RV::N(_) = a.relay { if b.am(a.am()).category == "Physical" { return b.cm(3277.0, 4096.0); } } RV::Undef });
    h!(r, Move, "triattack", "secondaries.0.onHit", |b, a| {
        let (t, s) = (a.t(), a.s()); let st = ["brn", "par", "frz"][b.prng.sample_idx(3)]; b.try_set_status(t, st, Some(s), None); RV::Undef });
    h!(r, Ability, "fluffy", "onSourceModifyDamage", |b, a| {
        let mv = b.am(a.am()); let mut m = 1.0; if mv.mtype == "Fire" { m *= 2.0; } if mv.flag("contact") { m /= 2.0; } b.cm(m, 1.0) });
    h!(r, Cond, "aquaring", "onStart", |b, a| { let n = b.mon_name(a.t()); b.add(&["-start", &n, "Aqua Ring"]); RV::Undef });
    h!(r, Cond, "aquaring", "onResidual", |b, a| { let d = b.p(a.t()).base_maxhp as f64 / 16.0; b.heal(d, None, None, None); RV::Undef });
    h!(r, Move, "eeriespell", "secondaries.0.onHit", |b, a| {
        let t = a.t(); if b.p(t).hp == 0 { return RV::Undef; }
        let Some(lm) = b.p(t).last_move else { return RV::Undef };
        if b.dex.mv(lm).tmpl.is_z { return RV::Undef; }
        let d = deduct_pp_amount(b, t, lm, 3); if d == 0 { return RV::Undef; }
        let n = b.mon_name(t); let mn = b.dex.mv(lm).eff.name; b.add(&["-activate", &n, "move: Eerie Spell", mn, &d.to_string()]); RV::Undef });
    h!(r, Move, "spite", "onHit", |b, a| {
        let t = a.t();
        let Some(lm) = b.p(t).last_move else { return RV::B(false) };
        if b.dex.mv(lm).tmpl.is_z { return RV::B(false); }
        let d = deduct_pp_amount(b, t, lm, 4); if d == 0 { return RV::B(false); }
        let n = b.mon_name(t); let mn = b.dex.mv(lm).eff.name; b.add(&["-activate", &n, "move: Spite", mn, &d.to_string()]); RV::Undef });
    // Electrify
    h!(r, Move, "electrify", "onTryHit", |b, a| { let t = a.t(); if b.will_move(t).is_none() && b.p(t).active_turns != 0 { return RV::B(false); } RV::Undef });
    h!(r, Cond, "electrify", "onStart", |b, a| { let n = b.mon_name(a.t()); b.add(&["-singleturn", &n, "move: Electrify"]); RV::Undef });
    h!(r, Cond, "electrify", "onModifyType", |b, a| { let am = a.am(); if b.am(am).id != "struggle" { b.amm(am).mtype = "Electric"; } RV::Undef });
    h!(r, Ability, "cheekpouch", "onEatItem", |b, a| { let d = b.p(a.t()).base_maxhp as f64 / 3.0; b.heal(d, None, None, None); RV::Undef });
    // semi-invulnerable two-turn moves
    h!(r, Move, "fly", "onTryMove", |b, a| { two_turn(b, a) });
    h!(r, Move, "bounce", "onTryMove", |b, a| { two_turn(b, a) });
    h!(r, Move, "dig", "onTryMove", |b, a| { two_turn(b, a) });
    h!(r, Move, "skyattack", "onTryMove", |b, a| { two_turn(b, a) });
    h!(r, Move, "dive", "onTryMove", |b, a| {
        let att = a.t();
        if b.has_ability(att, "gulpmissile") && b.p(att).species == "cramorant" && !b.p(att).transformed { b.unsupported("Move:dive gulpmissile".into()); }
        two_turn(b, a) });
    h!(r, Cond, "fly", "onInvulnerability", |b, a| { invuln(b, a, &["gust", "twister", "skyuppercut", "thunder", "hurricane", "smackdown", "thousandarrows"]) });
    h!(r, Cond, "fly", "onSourceModifyDamage", |b, a| { let mid = b.am(a.am()).id; if mid == "gust" || mid == "twister" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Cond, "bounce", "onInvulnerability", |b, a| { invuln(b, a, &["gust", "twister", "skyuppercut", "thunder", "hurricane", "smackdown", "thousandarrows"]) });
    h!(r, Cond, "bounce", "onSourceBasePower", |b, a| { let mid = b.am(a.am()).id; if mid == "gust" || mid == "twister" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Cond, "dig", "onImmunity", |b, a| { if a.relay == RV::S(id("sandstorm")) || a.relay == RV::S(id("hail")) { return RV::B(false); } RV::Undef });
    h!(r, Cond, "dig", "onInvulnerability", |b, a| { invuln(b, a, &["earthquake", "magnitude"]) });
    h!(r, Cond, "dig", "onSourceModifyDamage", |b, a| { let mid = b.am(a.am()).id; if mid == "earthquake" || mid == "magnitude" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Cond, "dive", "onImmunity", |b, a| { if a.relay == RV::S(id("sandstorm")) || a.relay == RV::S(id("hail")) { return RV::B(false); } RV::Undef });
    h!(r, Cond, "dive", "onInvulnerability", |b, a| { invuln(b, a, &["surf", "whirlpool"]) });
    h!(r, Cond, "dive", "onSourceModifyDamage", |b, a| { let mid = b.am(a.am()).id; if mid == "surf" || mid == "whirlpool" { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Move, "recycle", "onHit", |b, a| {
        let m = a.t(); let am = a.am();
        if !b.p(m).item.is_empty() || b.p(m).last_item.is_empty() { return RV::B(false); }
        let it = b.p(m).last_item; b.pm(m).last_item = "";
        let n = b.mon_name(m); let nm = item_name(b, it); b.add(&["-item", &n, nm, "[from] move: Recycle"]);
        let s = a.source; b.set_item(m, it, s, Some(Eff::mv(id("recycle"), am))); RV::Undef });
    h!(r, Ability, "quickfeet", "onModifySpe", |b, a| { if !b.p(a.t()).status.is_empty() { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Ability, "stakeout", "onModifyAtk", |b, a| { if let Some(d) = a.source { if b.p(d).active_turns == 0 { return b.cm(2.0, 1.0); } } RV::Undef });
    h!(r, Ability, "stakeout", "onModifySpA", |b, a| { if let Some(d) = a.source { if b.p(d).active_turns == 0 { return b.cm(2.0, 1.0); } } RV::Undef });
    h!(r, Move, "acupressure", "onHit", |b, a| {
        let t = a.t(); let stats: Vec<u8> = (0..7u8).filter(|k| b.p(t).boosts[*k as usize] < 6).collect();
        if stats.is_empty() { return RV::B(false); }
        let k = stats[b.prng.sample_idx(stats.len())]; b.boost(vec![(k, 2)], None, None, None, false, false); RV::Undef });
    // Klutz's onStart ends the item's effects: Showdown's singleEvent skips End for an item the holder ignores, so it does nothing
    h!(r, Ability, "klutz", "onStart", |b, a| {
        let m = a.t(); let it = b.p(m).item; b.single_event("End", Eff::new(Kind::Item, it), Some(SLoc::Item(m)), Tgt::Mon(m), None, None, RV::Undef); RV::Undef });
    h!(r, Ability, "anticipation", "onStart", |b, a| { RV::Undef });   // a message only
    h!(r, Ability, "mimicry", "onStart", |b, a| {
        let m = a.t(); b.single_event("TerrainChange", Eff::new(Kind::Ability, id("mimicry")), Some(SLoc::Ability(m)), Tgt::Mon(m), None, None, RV::Undef); RV::Undef });
    h!(r, Ability, "mimicry", "onTerrainChange", |b, a| { let m = a.t(); mimicry(b, m); RV::Undef });
    h!(r, Move, "jawlock", "onHit", |b, a| { let (t, s) = (a.t(), a.s()); let e = a.src_eff; trap(b, s, t, e); trap(b, t, s, e); RV::Undef });
    h!(r, Move, "meanlook", "onHit", |b, a| { let (t, s) = (a.t(), a.s()); let e = a.src_eff; trap(b, t, s, e) });
    h!(r, Move, "block", "onHit", |b, a| { let (t, s) = (a.t(), a.s()); let e = a.src_eff; trap(b, t, s, e) });
    h!(r, Move, "magicpowder", "onHit", |b, a| {
        let t = a.t();
        if b.get_types(t).join(",") == "Psychic" || !set_type(b, t, vec!["Psychic"]) { return RV::B(false); }
        let n = b.mon_name(t); b.add(&["-start", &n, "typechange", "Psychic"]); RV::Undef });
    h!(r, Ability, "pickup", "onResidual", |b, a| {
        let m = a.t(); if !b.p(m).item.is_empty() { return RV::Undef; }
        let ts: Vec<MonRef> = b.all_active().iter().copied().filter(|&x| !b.p(x).last_item.is_empty() && b.p(x).used_item_this_turn && b.is_adjacent(m, x)).collect();
        if ts.is_empty() { return RV::Undef; }
        let rt = ts[b.prng.sample_idx(ts.len())];
        let it = b.p(rt).last_item; b.pm(rt).last_item = "";
        let n = b.mon_name(m); let nm = item_name(b, it); b.add(&["-item", &n, nm, "[from] ability: Pickup"]);
        b.set_item(m, it, None, None); RV::Undef });
    h!(r, Ability, "shedskin", "onResidual", |b, a| {
        let m = a.t(); if b.p(m).hp > 0 && !b.p(m).status.is_empty() && b.rchance(33, 100) { let n = b.mon_name(m); b.add(&["-activate", &n, "ability: Shed Skin"]); b.cure_status(m); } RV::Undef });
    h!(r, Ability, "hydration", "onResidual", |b, a| {
        let m = a.t(); let w = b.pokemon_effective_weather(m, None);
        if !b.p(m).status.is_empty() && (w == "raindance" || w == "primordialsea") { let n = b.mon_name(m); b.add(&["-activate", &n, "ability: Hydration"]); b.cure_status(m); } RV::Undef });
    h!(r, Move, "healbell", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s()); let n = b.mon_name(s); b.add(&["-activate", &n, "move: Heal Bell"]);
        let mut success = false;
        for i in 0..b.sides[t.0 as usize].pokemon.len() {
            let x = (t.0, i as u8);
            if x != s && !b.suppressing_ability(Some(x)) {
                if b.has_ability(x, "soundproof") { let n = b.mon_name(x); b.add(&["-immune", &n, "[from] ability: Soundproof"]); continue; }
                if b.has_ability(x, "goodasgold") { let n = b.mon_name(x); b.add(&["-immune", &n, "[from] ability: Good as Gold"]); continue; }
            }
            if b.cure_status(x) { success = true; }
        }
        RV::B(success) });
    // Wonder Room (the defence swap itself: sim.rs calculate_stat, battle.rs get_stat) and Magic Room (battle.rs ignoring_item)
    h!(r, Cond, "wonderroom", "durationCallback", |b, a| { if a.source.map(|s| b.has_ability(s, "persistent")).unwrap_or(false) { return RV::N(7.0); } RV::N(5.0) });
    h!(r, Cond, "wonderroom", "onFieldStart", |b, a| { RV::Undef });
    h!(r, Cond, "wonderroom", "onFieldRestart", |b, a| { b.remove_pseudo_weather("wonderroom"); RV::Undef });
    h!(r, Cond, "wonderroom", "onFieldEnd", |b, a| { RV::Undef });
    h!(r, Cond, "wonderroom", "onModifyMove", |b, a| {
        let am = a.am(); match b.am(am).override_offensive_stat { Some("def") => b.amm(am).override_offensive_stat = Some("spd"), Some("spd") => b.amm(am).override_offensive_stat = Some("def"), _ => {} }
        RV::Undef });
    h!(r, Cond, "magicroom", "durationCallback", |b, a| { if a.source.map(|s| b.has_ability(s, "persistent")).unwrap_or(false) { return RV::N(7.0); } RV::N(5.0) });
    h!(r, Cond, "magicroom", "onFieldStart", |b, a| {
        for m in b.all_active() { let it = b.p(m).item; b.single_event("End", Eff::new(Kind::Item, it), Some(SLoc::Item(m)), Tgt::Mon(m), None, None, RV::Undef); }
        RV::Undef });
    h!(r, Cond, "magicroom", "onFieldRestart", |b, a| { b.remove_pseudo_weather("magicroom"); RV::Undef });
    h!(r, Cond, "magicroom", "onFieldEnd", |b, a| { RV::Undef });
    h!(r, Move, "guardswap", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        for k in [1usize, 3] { let (x, y) = (b.p(t).boosts[k], b.p(s).boosts[k]); b.pm(s).boosts[k] = x; b.pm(t).boosts[k] = y; }
        let (n, o) = (b.mon_name(s), b.mon_name(t)); b.add(&["-swapboost", &n, &o, "def, spd", "[from] move: Guard Swap"]); RV::Undef });
    h!(r, Move, "sparklingaria", "onAfterMove", |b, a| {
        let s = a.t(); let am = a.am();
        let ht: Vec<MonRef> = b.am(am).hit_targets.clone();
        if b.p(s).fainted || ht.is_empty() || b.am(am).has_sheer_force {
            for m in b.all_active() { b.pm(m).volatiles.retain(|(k, _)| *k != "sparklingaria"); }
            return RV::Undef;
        }
        let nt = ht.len();
        for m in ht { if m != s && b.p(m).is_active && (b.remove_volatile(m, "sparklingaria") || nt > 1) && b.p(m).status == "brn" { b.cure_status(m); } }
        RV::Undef });
    h!(r, Ability, "effectspore", "onDamagingHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if b.makes_contact(a.am(), s) && b.run_status_immunity(s, "powder", false) {
            let r = b.prng.below(100);
            if r < 11 { b.try_set_status(s, "slp", Some(t), None); } else if r < 21 { b.try_set_status(s, "par", Some(t), None); } else if r < 30 { b.try_set_status(s, "psn", Some(t), None); }
        }
        RV::Undef });
    // Opportunist: the foes' raised stats, copied once the current action ends
    h!(r, Ability, "opportunist", "onFoeAfterBoost", |b, a| {
        if a.src_eff.map(|e| e.id == "opportunist" || e.id == "mirrorherb").unwrap_or(false) { return RV::Undef; }
        let mut cur = opp_boosts(b).unwrap_or_default();
        for (k, v) in boosts_of(&a.relay) { if v > 0 { match cur.iter_mut().find(|(x, _)| *x == k) { Some(e) => e.1 += v, None => cur.push((k, v)) } } }
        let s = if cur.is_empty() { "-".to_string() } else { cur.iter().map(|(k, v)| format!("{}:{}", BOOST_NAMES[*k as usize], v)).collect::<Vec<_>>().join(",") };
        b.es().set("boosts", SV::S(id(&s))); RV::Undef });
    h!(r, Ability, "opportunist", "onAnyAfterMega", |b, a| { opp_apply(b) });
    h!(r, Ability, "opportunist", "onAnyAfterMove", |b, a| { opp_apply(b) });
    h!(r, Ability, "opportunist", "onAnyAfterTerastallization", |b, a| { opp_apply(b) });
    h!(r, Ability, "opportunist", "onAnySwitchIn", |b, a| { opp_apply(b) });
    h!(r, Ability, "opportunist", "onResidual", |b, a| { opp_apply(b) });
    h!(r, Ability, "opportunist", "onEnd", |b, a| { if let Some(s) = b.es_ref() { if s.get("boosts").is_some() { b.es().del("boosts"); } } RV::Undef });
    // Ingrain, Syrup Bomb, Torment, Uproar, Magnet Rise
    h!(r, Cond, "ingrain", "onStart", |b, a| { let n = b.mon_name(a.t()); b.add(&["-start", &n, "move: Ingrain"]); RV::Undef });
    h!(r, Cond, "ingrain", "onResidual", |b, a| { let d = b.p(a.t()).base_maxhp as f64 / 16.0; b.heal(d, None, None, None); RV::Undef });
    h!(r, Cond, "ingrain", "onTrapPokemon", |b, a| { let m = a.t(); b.try_trap(m, false); RV::Undef });
    h!(r, Cond, "ingrain", "onDragOut", |b, a| { let n = b.mon_name(a.t()); b.add(&["-activate", &n, "move: Ingrain"]); RV::Null });
    h!(r, Cond, "syrupbomb", "onStart", |b, a| { let n = b.mon_name(a.t()); b.add(&["-start", &n, "Syrup Bomb"]); RV::Undef });
    h!(r, Cond, "syrupbomb", "onUpdate", |b, a| {
        let m = a.t(); if let Some(s) = b.es_ref().and_then(|x| x.source) { if !b.p(s).is_active { b.remove_volatile(m, "syrupbomb"); } } RV::Undef });
    h!(r, Cond, "syrupbomb", "onResidual", |b, a| { let m = a.t(); let s = b.es_ref().and_then(|x| x.source); b.boost(vec![(4, -1)], Some(m), s, None, false, false); RV::Undef });
    h!(r, Cond, "syrupbomb", "onEnd", |b, a| { RV::Undef });
    h!(r, Cond, "torment", "onStart", |b, a| {
        let m = a.t();
        if b.has_vol(m, "dynamax") { b.pm(m).volatiles.retain(|(k, _)| *k != "torment"); return RV::B(false); }
        let n = b.mon_name(m); b.add(&["-start", &n, "Torment"]); RV::Undef });
    h!(r, Cond, "torment", "onEnd", |b, a| { let n = b.mon_name(a.t()); b.add(&["-end", &n, "Torment"]); RV::Undef });
    h!(r, Cond, "torment", "onDisableMove", |b, a| { let m = a.t(); if let Some(lm) = b.p(m).last_move { if lm != "struggle" { b.disable_move(m, lm, false, ""); } } RV::Undef });
    h!(r, Move, "uproar", "onTryHit", |b, a| {
        let t = a.t();
        for i in 0..2 { for side in [t.0, 1 - t.0] {
            if let Some(x) = b.sides[side as usize].active[i] { let m = (side, x); if b.p(m).status == "slp" { b.cure_status(m); } }
        } }
        RV::Undef });
    h!(r, Cond, "uproar", "onStart", |b, a| { let n = b.mon_name(a.t()); b.add(&["-start", &n, "Uproar"]); RV::Undef });
    h!(r, Cond, "uproar", "onResidual", |b, a| {
        let m = a.t();
        if b.has_vol(m, "throatchop") { b.remove_volatile(m, "uproar"); return RV::Undef; }
        if b.p(m).last_move == Some("struggle") { b.pm(m).volatiles.retain(|(k, _)| *k != "uproar"); }
        let n = b.mon_name(m); b.add(&["-start", &n, "Uproar", "[upkeep]"]); RV::Undef });
    h!(r, Cond, "uproar", "onEnd", |b, a| { let n = b.mon_name(a.t()); b.add(&["-end", &n, "Uproar"]); RV::Undef });
    h!(r, Cond, "uproar", "onAnySetStatus", |b, a| {
        if a.relay == RV::S(id("slp")) { let n = b.mon_name(a.t()); b.add(&["-fail", &n, "slp", "[from] Uproar"]); return RV::Null; } RV::Undef });
    h!(r, Move, "magnetrise", "onTry", |b, a| {
        let s = a.t(); let t = a.source.unwrap_or(s);
        if b.has_vol(t, "smackdown") || b.has_vol(t, "ingrain") { return RV::B(false); }
        if find(&b.field.pseudo, "gravity").is_some() { let n = b.mon_name(s); b.add(&["cant", &n, "move: Gravity", "Magnet Rise"]); return RV::Null; }
        RV::Undef });
    h!(r, Cond, "magnetrise", "onStart", |b, a| { let n = b.mon_name(a.t()); b.add(&["-start", &n, "Magnet Rise"]); RV::Undef });
    h!(r, Cond, "magnetrise", "onImmunity", |b, a| { if a.relay == RV::S(id("Ground")) { return RV::B(false); } RV::Undef });
    h!(r, Cond, "magnetrise", "onEnd", |b, a| { let n = b.mon_name(a.t()); b.add(&["-end", &n, "Magnet Rise"]); RV::Undef });
    // Comeuppance: the last damage taken from a foe this turn, x1.5, back at that foe's slot
    h!(r, Move, "comeuppance", "onTry", |b, a| { let s = a.t(); if !last_damaged_by(b, s).map(|x| x.this_turn).unwrap_or(false) { return RV::B(false); } RV::Undef });
    h!(r, Move, "comeuppance", "onModifyTarget", |b, a| {
        let s = a.t(); if let Some(x) = last_damaged_by(b, s) { return RV::Target(b.get_at_slot(x.slot)); } RV::Undef });
    h!(r, Move, "comeuppance", "damageCallback", |b, a| {
        let s = a.s(); match last_damaged_by(b, s) { Some(x) => { let d = x.damage as f64 * 1.5; RV::N(if d == 0.0 { 1.0 } else { d }) } None => RV::N(0.0) } });
    h!(r, Move, "courtchange", "onHitField", |b, a| {
        const SC: [&str; 19] = ["mist", "lightscreen", "reflect", "spikes", "safeguard", "tailwind", "toxicspikes", "stealthrock", "waterpledge", "firepledge",
                                "grasspledge", "stickyweb", "auroraveil", "luckychant", "gmaxsteelsurge", "gmaxcannonade", "gmaxvinelash", "gmaxwildfire", "gmaxvolcalith"];
        let s = a.s(); let (me, foe) = (s.0 as usize, 1 - s.0 as usize);
        fn take(v: &mut Vec<(Id, EState)>) -> Vec<(Id, EState)> {
            let (x, keep): (Vec<_>, Vec<_>) = std::mem::take(v).into_iter().partition(|(k, _)| SC.contains(k)); *v = keep; x }
        let mine = take(&mut b.sides[me].side_conditions); let theirs = take(&mut b.sides[foe].side_conditions);
        let success = !mine.is_empty() || !theirs.is_empty();
        b.sides[foe].side_conditions.extend(mine); b.sides[me].side_conditions.extend(theirs);
        if !success { return RV::B(false); }
        let n = b.mon_name(s); b.add(&["-swapsideconditions"]); b.add(&["-activate", &n, "move: Court Change"]); RV::Undef });
    h!(r, Move, "mistyexplosion", "onBasePower", |b, a| {
        let s = a.t(); if b.is_terrain("mistyterrain") && b.is_grounded(s, false) == Some(true) { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Move, "thief", "onAfterHit", |b, a| {
        let (t, s) = (a.t(), a.s()); let e = a.src_eff;
        if !b.p(s).item.is_empty() || b.has_vol(s, "gem") { return RV::Undef; }
        let Some(it) = b.take_item(t, Some(s)) else { return RV::Undef };
        let ok = b.single_event("TakeItem", Eff::new(Kind::Item, it), Some(SLoc::Item(t)), Tgt::Mon(s), Some(t), e, RV::S(it)).truthy() && b.set_item(s, it, None, None);
        if !ok { b.pm(t).item = it; return RV::Undef; }
        if b.logging { let (n, o) = (b.mon_name(s), b.mon_name(t)); let nm = item_name(b, it); b.add(&["-item", &n, nm, "[from] move: Thief", &format!("[of] {}", o)]); }
        RV::Undef });
    h!(r, Ability, "receiver", "onAllyFaint", |b, a| {
        let t = a.t(); let h_ = b.holder(); if b.p(h_).hp == 0 { return RV::Undef; }
        let ab = b.p(t).ability;
        if b.dex.eff(Kind::Ability, ab).flag("noreceiver") || ab == "noability" { return RV::Undef; }
        b.set_ability(h_, ab, Some(t), None, false); RV::Undef });
    h!(r, Ability, "sandspit", "onDamagingHit", |b, a| { b.set_weather("sandstorm", None, None); RV::Undef });
    // Sticky Hold: Showdown throws when no move is active (an item taken outside a move); here it then lets the item go
    h!(r, Ability, "stickyhold", "onTakeItem", |b, a| {
        let m = a.t(); let Some(am) = b.active_move else { return RV::Undef };
        if b.p(m).hp == 0 || b.p(m).item == "stickybarb" { return RV::Undef; }
        if (a.source.is_some() && a.source != Some(m)) || b.am(am).id == "knockoff" { let n = b.mon_name(m); b.add(&["-activate", &n, "ability: Sticky Hold"]); return RV::B(false); }
        RV::Undef });
    h!(r, Ability, "suctioncups", "onDragOut", |b, a| { let n = b.mon_name(a.t()); b.add(&["-activate", &n, "ability: Suction Cups"]); RV::Null });
    h!(r, Ability, "guarddog", "onDragOut", |b, a| { let n = b.mon_name(a.t()); b.add(&["-activate", &n, "ability: Guard Dog"]); RV::Null });
    h!(r, Ability, "guarddog", "onTryBoost", |b, a| {
        let t = a.t(); let mut bo = boosts_of(&a.relay);
        if a.src_eff.map(|e| e.id) == Some("intimidate") && bo.iter().any(|(k, v)| *k == 0 && *v != 0) {
            bo.retain(|(k, _)| *k != 0); b.boost(vec![(0, 1)], Some(t), Some(t), None, false, true); return RV::Boosts(bo);
        }
        RV::Undef });
    h!(r, Move, "gastroacid", "onTryHit", |b, a| {
        let t = a.t(); if b.ab_data(t).cantsuppress { return RV::B(false); }
        if b.has_item(t, "abilityshield") { let n = b.mon_name(t); b.add(&["-block", &n, "item: Ability Shield"]); return RV::Null; }
        RV::Undef });
    h!(r, Move, "belch", "onTry", |b, a| { let s = a.t(); RV::B(b.p(s).ate_berry) });
    h!(r, Move, "reflecttype", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        let num = b.dex.species.get(b.p(s).species).map(|x| x.num).unwrap_or(0); if num == 493 || num == 773 { return RV::B(false); }
        let mut nt: Vec<Id> = types_ex(b, t).into_iter().filter(|x| *x != "???").collect();
        if nt.is_empty() { if !b.p(t).added_type.is_empty() { nt = vec!["Normal"]; } else { return RV::B(false); } }
        let (n, o) = (b.mon_name(s), b.mon_name(t)); b.add(&["-start", &n, "typechange", "[from] move: Reflect Type", &format!("[of] {}", o)]);
        set_type(b, s, nt); let at = b.p(t).added_type; b.pm(s).added_type = at; RV::Undef });
    // items
    h!(r, Item, "mistyseed", "onStart", |b, a| { let m = a.t(); if !b.ignoring_item(m) && b.is_terrain("mistyterrain") { b.use_item(m, None, None); } RV::Undef });
    h!(r, Item, "mistyseed", "onTerrainChange", |b, a| { let m = a.t(); if b.is_terrain("mistyterrain") { b.use_item(m, None, None); } RV::Undef });
    h!(r, Item, "oranberry", "onUpdate", |b, a| { let m = a.t(); if b.p(m).hp as f64 <= b.p(m).maxhp as f64 / 2.0 { b.eat_item(m, false, None, None); } RV::Undef });
    h!(r, Item, "oranberry", "onTryEatItem", |b, a| {
        let m = a.t(); let e = b.effect; if !b.run_event("TryHeal", Tgt::Mon(m), None, e, RV::N(10.0), false, false).truthy() { return RV::B(false); } RV::Undef });
    h!(r, Item, "oranberry", "onEat", |b, a| { b.heal(10.0, None, None, None); RV::Undef });
    h!(r, Item, "persimberry", "onUpdate", |b, a| { let m = a.t(); if b.has_vol(m, "confusion") { b.eat_item(m, false, None, None); } RV::Undef });
    h!(r, Item, "persimberry", "onEat", |b, a| { let m = a.t(); b.remove_volatile(m, "confusion"); RV::Undef });
    h!(r, Item, "shedshell", "onTrapPokemon", |b, a| { let m = a.t(); b.pm(m).trapped = false; RV::Undef });
    h!(r, Item, "shedshell", "onMaybeTrapPokemon", |b, a| { let m = a.t(); b.pm(m).maybe_trapped = false; RV::Undef });
}
