//! Rust ports of Showdown's event handlers, keyed by (effect kind, effect id, callback name). Each port follows the JS in
//! native/handlers_all.js line by line; message-only code is reduced to log lines.
use crate::battle::*;
use crate::dex::*;
pub type Reg = FxMap<(Kind, Id, Id), HFn>;

/// h!(reg, Kind, "effect", "callback", |b, a| { ...body returning RV... })
#[macro_export]
macro_rules! h {
    ($r:expr, $k:ident, $e:expr, $cb:expr, |$b:ident, $a:ident| $body:block) => {{
        #[allow(unused_variables, unused_mut, unreachable_code)]
        fn f($b: &mut $crate::battle::Battle, $a: &mut $crate::battle::HArgs) -> $crate::battle::RV { $body }
        $r.insert(($crate::dex::Kind::$k, $crate::dex::id($e), $crate::dex::id($cb)), f as $crate::battle::HFn);
    }};
}

pub mod conditions;
pub mod moves;
pub mod abilities;
pub mod items;
pub mod batch4;

pub fn build() -> Reg {
    let mut r: Reg = FxMap::default();
    conditions::register(&mut r);
    moves::register(&mut r);
    abilities::register(&mut r);
    items::register(&mut r);
    batch4::register(&mut r);
    r
}

// ---------- helpers for handler bodies ----------
impl HArgs {
    /// the event target as a pokemon
    pub fn t(&self) -> crate::state::MonRef { self.target.mon().expect("handler target is not a pokemon") }
    pub fn s(&self) -> crate::state::MonRef { self.source.expect("handler has no source") }
    /// the ActiveMove slot of the event's effect
    pub fn am(&self) -> usize { self.src_eff.and_then(|e| e.am).expect("handler effect is not an active move") }
    pub fn am_opt(&self) -> Option<usize> { self.src_eff.and_then(|e| e.am) }
    pub fn n(&self) -> f64 { self.relay.num() }
}
impl Battle {
    /// this.effectState.target for pokemon-held states
    pub fn holder(&self) -> crate::state::MonRef { self.es_mon().expect("effect state is not on a pokemon") }
    /// return this.chainModify(num/den)
    pub fn cm(&mut self, num: f64, den: f64) -> RV { self.chain_modify(num, den); RV::Undef }
    pub fn rchance(&mut self, n: i64, d: i64) -> bool { self.prng.chance(n, d) }
    pub fn eff_is(&self, e: Option<Eff>, t: EType) -> bool { e.map(|e| self.etype_of(&e) == t).unwrap_or(false) }
    /// validTarget(target, source, targetType)
    pub fn valid_target(&self, t: crate::state::MonRef, src: crate::state::MonRef, ttype: &str) -> bool { let l = self.get_loc_of(src, t); self.valid_target_loc(l, src, ttype) }
    pub fn is_semi_invulnerable(&self, m: crate::state::MonRef) -> bool {
        let v = &self.p(m).volatiles;
        ["fly", "bounce", "dive", "dig", "phantomforce", "shadowforce", "skydrop"].iter().any(|x| crate::state::find(v, x).is_some())
    }
    pub fn has_vol(&self, m: crate::state::MonRef, v: &str) -> bool { crate::state::find(&self.p(m).volatiles, v).is_some() }
    pub fn item_data(&self, m: crate::state::MonRef) -> &'static EffData { self.dex.eff(Kind::Item, self.p(m).item) }
    /// checkMoveMakesContact
    pub fn makes_contact(&self, am: usize, attacker: crate::state::MonRef) -> bool { self.am(am).flag("contact") && !self.has_item(attacker, "protectivepads") }
    /// checkMoveBypassesProtect(move, attacker, defender, blockStatus)
    pub fn bypasses_protect(&mut self, am: usize, attacker: crate::state::MonRef, defender: crate::state::MonRef, block_status: bool) -> bool {
        let mv = self.am(am);
        if (mv.category != "Status" || block_status) && mv.flag("protect") {
            let e = Eff::mv(mv.id, am);
            if self.run_event("HitProtect", Tgt::Mon(attacker), Some(defender), Some(e), RV::Undef, false, false).truthy() { return false; }
        }
        true
    }
    pub fn is_sky_dropped(&self, m: crate::state::MonRef) -> bool {
        if self.has_vol(m, "skydrop") { return true; }
        self.foes_all(m).iter().any(|f| crate::state::find(&self.p(*f).volatiles, "skydrop").map(|s| s.source == Some(m)).unwrap_or(false))
    }
}
