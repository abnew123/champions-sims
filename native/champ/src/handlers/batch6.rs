//! Handlers ported 2026-10-12, batch 6: further effects met in the mid-battle differential cases and the Eval bar's audit (Stockpile and
//! its moves, Minimize, Power Trick, Speed Swap, Smack Down, Octolock, Rapid Spin, Red Card, Leppa Berry, the Metronome item, Role
//! Play, Raging Bull, Trick-or-Treat / Forest's Curse, Steely Spirit, Focus Band and several power callbacks). Each follows the
//! champions mod's resolved source and was checked on focused Showdown cases.
use super::Reg;
use crate::battle::*;
use crate::dex::*;
use crate::h;
use crate::state::*;

fn vol_n(b: &Battle, m: MonRef, v: &str, k: &str) -> Option<f64> { find(&b.p(m).volatiles, v).and_then(|s| s.n(k)) }
/// Stockpile's boost: +1 Def / SpD, remembering each stat that moved so the end can take it back
fn stockpile_layer(b: &mut Battle, t: MonRef) {
    let n = b.mon_name(t); let l = b.es().n("layers").unwrap_or(1.0) as i64; b.add(&["-start", &n, &format!("stockpile{}", l)]);
    let (d0, s0) = (b.p(t).boosts[1], b.p(t).boosts[3]);
    b.boost(vec![(1, 1), (3, 1)], Some(t), Some(t), None, false, false);
    if d0 != b.p(t).boosts[1] { let x = b.es().n("def").unwrap_or(0.0); b.es().set("def", SV::N(x - 1.0)); }
    if s0 != b.p(t).boosts[3] { let x = b.es().n("spd").unwrap_or(0.0); b.es().set("spd", SV::N(x - 1.0)); }
}
fn swap_atk_def(b: &mut Battle, m: MonRef) { let p = b.pm(m); p.stored.swap(1, 2); }
/// Trick-or-Treat / Forest's Curse
fn add_type_move(b: &mut Battle, a: &mut HArgs, ty: Id, name: &str) -> RV {
    let t = a.t();
    if b.has_type(t, ty) { return RV::B(false); }
    b.pm(t).added_type = ty;
    let n = b.mon_name(t); b.add(&["-start", &n, "typeadd", ty, &format!("[from] move: {}", name)]);
    RV::Undef
}
fn rapid_spin(b: &mut Battle, s: MonRef, need_hp: bool) {
    if (!need_hp || b.p(s).hp > 0) && b.remove_volatile(s, "leechseed") { let n = b.mon_name(s); b.add(&["-end", &n, "Leech Seed", "[from] move: Rapid Spin"]); }
    for c in ["spikes", "toxicspikes", "stealthrock", "stickyweb", "gmaxsteelsurge"] {
        if (!need_hp || b.p(s).hp > 0) && b.remove_side_condition(s.0, c) { b.add(&["-sideend", &format!("p{}", s.0 + 1), c, "[from] move: Rapid Spin"]); }
    }
    if (!need_hp || b.p(s).hp > 0) && b.has_vol(s, "partiallytrapped") { b.remove_volatile(s, "partiallytrapped"); }
}

pub fn register(r: &mut Reg) {
    h!(r, Ability, "steelyspirit", "onAllyBasePower", |b, a| { if b.am(a.am()).mtype == "Steel" { return b.cm(1.5, 1.0); } RV::Undef });
    h!(r, Item, "focusband", "onDamage", |b, a| {
        let t = a.t();
        if b.rchance(1, 10) && a.n() >= b.p(t).hp as f64 && a.src_eff.map(|e| b.etype_of(&e) == EType::Move).unwrap_or(false) {
            let n = b.mon_name(t); b.add(&["-activate", &n, "item: Focus Band"]); return RV::N((b.p(t).hp - 1) as f64);
        }
        RV::Undef });
    h!(r, Item, "redcard", "onAfterMoveSecondary", |b, a| {
        let t = a.t(); let Some(s) = a.source else { return RV::Undef }; let am = a.am();
        if s == t || b.p(s).hp == 0 || b.p(t).hp == 0 || b.am(am).category == "Status" { return RV::Undef; }
        if !b.p(s).is_active || b.can_switch(s.0) == 0 || b.p(s).force_switch_flag || b.p(t).force_switch_flag { return RV::Undef; }
        if b.use_item(t, Some(s), None) {
            let e = a.src_eff;
            if b.run_event("DragOut", Tgt::Mon(s), Some(t), e, RV::Undef, false, false).truthy() { b.pm(s).force_switch_flag = true; }
        }
        RV::Undef });
    h!(r, Item, "leppaberry", "onUpdate", |b, a| { let m = a.t(); if b.p(m).hp == 0 { return RV::Undef; } if b.p(m).move_slots.iter().any(|s| s.pp == 0) { b.eat_item(m, false, None, None); } RV::Undef });
    h!(r, Item, "leppaberry", "onEat", |b, a| {
        let m = a.t(); let add = if b.has_ability(m, "ripen") { 20 } else { 10 };
        let p = b.pm(m);
        let k = p.move_slots.iter().position(|s| s.pp == 0).or_else(|| p.move_slots.iter().position(|s| s.pp < s.maxpp));
        let Some(k) = k else { return RV::Undef };
        let s = &mut p.move_slots[k]; s.pp = (s.pp + add).min(s.maxpp); let mv = s.id;
        let n = b.mon_name(m); let name = b.dex.mv(mv).eff.name; b.add(&["-activate", &n, "item: Leppa Berry", name, "[consumed]"]); RV::Undef });
    h!(r, Item, "metronome", "onStart", |b, a| { let m = a.t(); b.add_volatile(m, "metronome", None, None); RV::Undef });
    h!(r, Cond, "metronome", "onStart", |b, a| { b.es().set("lastMove", SV::S("")); b.es().set("numConsecutive", SV::N(0.0)); RV::Undef });
    h!(r, Cond, "metronome", "onTryMove", |b, a| {
        let m = a.t();
        if !b.has_item(m, "metronome") { b.remove_volatile(m, "metronome"); return RV::Undef; }
        let mid = b.am(a.am()).id;
        if b.dex.mv(mid).eff.raw.get("callsMove").map(|x| x.as_bool().unwrap_or(false)).unwrap_or(false) { return RV::Undef; }
        let last = b.es().get("lastMove").and_then(|x| x.s()).unwrap_or(""); let n = b.es().n("numConsecutive").unwrap_or(0.0);
        let n = if last == mid && b.p(m).move_last_turn_result == Tri::B(true) { n + 1.0 }
                else if b.has_vol(m, "twoturnmove") { if last != mid { 1.0 } else { n + 1.0 } } else { 0.0 };
        b.es().set("numConsecutive", SV::N(n)); b.es().set("lastMove", SV::S(mid)); RV::Undef });
    h!(r, Cond, "metronome", "onModifyDamage", |b, a| {
        let k = (b.es().n("numConsecutive").unwrap_or(0.0) as usize).min(5); let m = [4096.0, 4915.0, 5734.0, 6553.0, 7372.0, 8192.0][k];
        b.cm(m, 4096.0) });
    // moves
    h!(r, Move, "storedpower", "basePowerCallback", |b, a| { let (s, am) = (a.s(), a.am()); RV::N(b.am(am).base_power + 20.0 * b.positive_boosts(s) as f64) });
    h!(r, Move, "electroball", "basePowerCallback", |b, a| {
        let (t, s) = (a.t(), a.s());
        let mut ratio = (b.get_stat(s, 5, false, false) as f64 / b.get_stat(t, 5, false, false) as f64).floor(); if !ratio.is_finite() { ratio = 0.0; }
        RV::N([40.0, 60.0, 80.0, 120.0, 150.0][(ratio as usize).min(4)]) });
    h!(r, Move, "avalanche", "basePowerCallback", |b, a| {
        let (t, s, am) = (a.t(), a.s(), a.am()); let bp = b.am(am).base_power;
        let hit = b.p(s).attacked_by.iter().any(|x| x.source == t && x.damage > 0 && x.this_turn);
        RV::N(if hit { bp * 2.0 } else { bp }) });
    h!(r, Move, "burningjealousy", "secondaries.0.onHit", |b, a| {
        let (t, s) = (a.t(), a.s()); if b.p(t).stats_raised_this_turn { let e = a.src_eff; b.try_set_status(t, id("brn"), Some(s), e); } RV::Undef });
    h!(r, Move, "alluringvoice", "secondaries.0.onHit", |b, a| {
        let (t, s) = (a.t(), a.s()); if b.p(t).stats_raised_this_turn { let e = a.src_eff; b.add_volatile(t, "confusion", Some(s), e); } RV::Undef });
    h!(r, Move, "trickortreat", "onHit", |b, a| {
        let r_ = add_type_move(b, a, "Ghost", "Trick-or-Treat"); if r_ == RV::B(false) { return r_; }
        let t = a.t();
        if b.p(t).position == 1 { if let Some(i) = b.will_move(t) { if b.queue[i].am.map(|x| b.am(x).id == "curse").unwrap_or(false) { b.queue[i].target_loc = -1; } } }
        RV::Undef });
    h!(r, Move, "forestscurse", "onHit", |b, a| { add_type_move(b, a, "Grass", "Forest's Curse") });
    h!(r, Move, "ragingbull", "onModifyType", |b, a| {
        let m = a.t(); let ty = match b.p(m).species { "taurospaldeacombat" => Some("Fighting"), "taurospaldeablaze" => Some("Fire"), "taurospaldeaaqua" => Some("Water"), _ => None };
        if let Some(ty) = ty { let am = a.am(); b.amm(am).mtype = ty; } RV::Undef });
    h!(r, Move, "rapidspin", "onAfterHit", |b, a| { let s = a.s(); if !b.am(a.am()).has_sheer_force { rapid_spin(b, s, false); } RV::Undef });
    h!(r, Move, "rapidspin", "onAfterSubDamage", |b, a| { let s = a.s(); if !b.am(a.am()).has_sheer_force { rapid_spin(b, s, true); } RV::Undef });
    h!(r, Move, "speedswap", "onHit", |b, a| {
        let (t, s) = (a.t(), a.s()); let ts = b.p(t).stored[5]; let ss = b.p(s).stored[5]; b.pm(t).stored[5] = ss; b.pm(s).stored[5] = ts;
        let (sn, tn) = (b.mon_name(s), b.mon_name(t)); b.add(&["-activate", &sn, "move: Speed Swap", &format!("[of] {}", tn)]); RV::Undef });
    h!(r, Cond, "powertrick", "onStart", |b, a| { let m = a.t(); let n = b.mon_name(m); b.add(&["-start", &n, "Power Trick"]); swap_atk_def(b, m); RV::Undef });
    h!(r, Cond, "powertrick", "onCopy", |b, a| { let m = a.t(); swap_atk_def(b, m); RV::Undef });
    h!(r, Cond, "powertrick", "onEnd", |b, a| { let m = a.t(); let n = b.mon_name(m); b.add(&["-end", &n, "Power Trick"]); swap_atk_def(b, m); RV::Undef });
    h!(r, Cond, "powertrick", "onRestart", |b, a| { let m = a.t(); b.remove_volatile(m, "powertrick"); RV::Undef });
    h!(r, Cond, "minimize", "onRestart", |b, a| { RV::Null });
    h!(r, Cond, "minimize", "onSourceModifyDamage", |b, a| { if b.am(a.am()).flag("minimize") { return b.cm(2.0, 1.0); } RV::Undef });
    h!(r, Cond, "minimize", "onAccuracy", |b, a| { if b.am(a.am()).flag("minimize") { return RV::B(true); } a.relay.clone() });
    h!(r, Move, "stockpile", "onTry", |b, a| { let m = a.t(); if vol_n(b, m, "stockpile", "layers").unwrap_or(0.0) >= 3.0 { return RV::B(false); } RV::Undef });
    h!(r, Cond, "stockpile", "onStart", |b, a| {
        let t = a.t(); b.es().set("layers", SV::N(1.0)); b.es().set("def", SV::N(0.0)); b.es().set("spd", SV::N(0.0)); stockpile_layer(b, t); RV::Undef });
    h!(r, Cond, "stockpile", "onRestart", |b, a| {
        let t = a.t(); let l = b.es().n("layers").unwrap_or(1.0); if l >= 3.0 { return RV::B(false); }
        b.es().set("layers", SV::N(l + 1.0)); stockpile_layer(b, t); RV::Undef });
    h!(r, Cond, "stockpile", "onEnd", |b, a| {
        let t = a.t(); let (d, s) = (b.es().n("def").unwrap_or(0.0) as i64, b.es().n("spd").unwrap_or(0.0) as i64);
        if d != 0 || s != 0 { let mut bo = vec![]; if d != 0 { bo.push((1, d)); } if s != 0 { bo.push((3, s)); } b.boost(bo, Some(t), Some(t), None, false, false); }
        let n = b.mon_name(t); b.add(&["-end", &n, "Stockpile"]); RV::Undef });
    h!(r, Move, "spitup", "basePowerCallback", |b, a| { let s = a.s(); match vol_n(b, s, "stockpile", "layers") { Some(l) if l > 0.0 => RV::N(l * 100.0), _ => RV::B(false) } });
    h!(r, Move, "spitup", "onTry", |b, a| { RV::B(b.has_vol(a.t(), "stockpile")) });
    h!(r, Move, "spitup", "onAfterMove", |b, a| { let m = a.t(); b.remove_volatile(m, "stockpile"); RV::Undef });
    h!(r, Move, "swallow", "onTry", |b, a| { RV::B(b.has_vol(a.t(), "stockpile")) });
    h!(r, Move, "swallow", "onHit", |b, a| {
        let m = a.t(); let l = vol_n(b, m, "stockpile", "layers").filter(|x| *x > 0.0).unwrap_or(1.0) as usize;
        let hp = b.modify(b.p(m).maxhp as f64, [0.25, 0.5, 1.0][(l - 1).min(2)]) as f64;
        let ok = b.heal(hp, Some(m), None, None).truthy();
        if !ok { let n = b.mon_name(m); b.add(&["-fail", &n, "heal"]); }
        b.remove_volatile(m, "stockpile");
        if ok { RV::B(true) } else { RV::NotFail } });
    h!(r, Move, "roleplay", "onTryHit", |b, a| {
        let (t, s) = (a.t(), a.s());
        if b.p(t).ability == b.p(s).ability { return RV::B(false); }
        let fr = b.ab_data(t).raw.get("flags").and_then(|f| f.get("failroleplay")).is_some();
        if fr || b.ab_data(s).cantsuppress { return RV::B(false); } RV::Undef });
    h!(r, Move, "roleplay", "onHit", |b, a| { let (t, s) = (a.t(), a.s()); let ab = b.p(t).ability; if !b.set_ability(s, ab, Some(t), None, false) { return RV::B(false); } RV::Undef });
    h!(r, Cond, "smackdown", "onStart", |b, a| {
        let m = a.t();
        let mut applies = b.has_type(m, "Flying") || b.has_ability(m, "levitate") || b.has_ability(m, "eelevate");
        if b.has_item(m, "ironball") || b.has_vol(m, "ingrain") || find(&b.field.pseudo, "gravity").is_some() { applies = false; }
        if b.remove_volatile(m, "fly") || b.remove_volatile(m, "bounce") {
            applies = true; if let Some(i) = b.will_move(m) { b.queue.remove(i); } b.remove_volatile(m, "twoturnmove");
        }
        if b.has_vol(m, "magnetrise") { applies = true; b.pm(m).volatiles.retain(|(k, _)| *k != "magnetrise"); }
        if b.has_vol(m, "telekinesis") { applies = true; b.pm(m).volatiles.retain(|(k, _)| *k != "telekinesis"); }
        if !applies { return RV::B(false); }
        let n = b.mon_name(m); b.add(&["-start", &n, "Smack Down"]); RV::Undef });
    h!(r, Cond, "smackdown", "onRestart", |b, a| {
        let m = a.t();
        if b.remove_volatile(m, "fly") || b.remove_volatile(m, "bounce") {
            if let Some(i) = b.will_move(m) { b.queue.remove(i); } b.remove_volatile(m, "twoturnmove");
            let n = b.mon_name(m); b.add(&["-start", &n, "Smack Down"]);
        }
        RV::Undef });
    h!(r, Move, "octolock", "onTryImmunity", |b, a| { let t = a.t(); RV::B(!b.has_type(t, "Ghost")) });
    h!(r, Cond, "octolock", "onStart", |b, a| { let n = b.mon_name(a.t()); b.add(&["-start", &n, "move: Octolock"]); RV::Undef });
    h!(r, Cond, "octolock", "onResidual", |b, a| {
        let m = a.t(); let src = b.es().source;
        if let Some(s) = src { if !b.p(s).is_active || b.p(s).hp <= 0 || b.p(s).active_turns == 0 {
            b.pm(m).volatiles.retain(|(k, _)| *k != "octolock"); let n = b.mon_name(m); b.add(&["-end", &n, "Octolock", "[partiallytrapped]", "[silent]"]); return RV::Undef; } }
        let am = b.new_am(b.dex.active_move("octolock"));
        b.boost(vec![(1, -1), (3, -1)], Some(m), src, Some(Eff::mv("octolock", am)), false, false); RV::Undef });
    h!(r, Cond, "octolock", "onTrapPokemon", |b, a| { let m = a.t(); if b.es().source.map(|s| b.p(s).is_active).unwrap_or(false) { b.try_trap(m, false); } RV::Undef });
}
