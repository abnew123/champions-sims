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
}
