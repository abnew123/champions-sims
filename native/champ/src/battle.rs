//! The battle object and Showdown's event system (sim/battle.ts runEvent / singleEvent / fieldEvent / eachEvent, findEventHandlers,
//! resolvePriority, speedSort). Handlers are found from the exported callback lists and sorted exactly as Showdown sorts them
//! (including the random shuffle of tied handlers), then run through the Rust ports registered in handlers/.
use crate::dex::*;
use crate::prng::Prng;
use crate::state::*;

/// an effect as a handler or event source: (kind, id), plus the ActiveMove slot when it's a move in use, and the move part
/// ("" the move, "secondaries.N", "self") for moveData effects
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Eff { pub kind: Kind, pub id: Id, pub am: Option<usize>, pub part: Id }
impl Eff {
    pub fn new(kind: Kind, id: Id) -> Eff { Eff { kind, id, am: None, part: "" } }
    pub fn mv(id: Id, am: usize) -> Eff { Eff { kind: Kind::Move, id, am: Some(am), part: "" } }
    pub fn cond(id: Id) -> Eff { Eff::new(Kind::Cond, id) }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Holder { Mon(MonRef), Side(u8), Field, Battle }

/// where an effect's state lives (this.effectState)
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum SLoc { Status(MonRef), Vol(MonRef, Id), Ability(MonRef), Item(MonRef), Species(MonRef), Slot(u8, u8, Id), SideC(u8, Id), Weather, Terrain, Pseudo(Id), Temp(usize), Nil }

#[derive(Clone, Debug, PartialEq)]
pub enum Tgt { Mon(MonRef), Side(u8), Field, Battle, Mons(Vec<Option<MonRef>>), None }
impl Tgt { pub fn mon(&self) -> Option<MonRef> { if let Tgt::Mon(m) = self { Some(*m) } else { None } } }

/// relay variable
#[derive(Clone, Debug, PartialEq)]
pub enum RV { Undef, Null, NotFail, B(bool), N(f64), M(MonRef), S(Id), Boosts(Boosts), Types(Vec<Id>), Secs(Vec<HitEff>), Target(Option<MonRef>) }
impl RV {
    pub fn truthy(&self) -> bool {
        match self { RV::Undef | RV::Null | RV::NotFail => false, RV::B(b) => *b, RV::N(n) => *n != 0.0 && !n.is_nan(), RV::S(s) => !s.is_empty(), _ => true }
    }
    pub fn num(&self) -> f64 { match self { RV::N(n) => *n, RV::B(true) => 1.0, _ => 0.0 } }
    pub fn is_undef(&self) -> bool { matches!(self, RV::Undef) }
    pub fn from_bool(b: bool) -> RV { RV::B(b) }
}

pub struct HArgs { pub relay: RV, pub has_relay: bool, pub target: Tgt, pub source: Option<MonRef>, pub src_eff: Option<Eff> }
pub type HFn = fn(&mut Battle, &mut HArgs) -> RV;

#[derive(Clone, Debug)]
pub struct EventCtx { pub id: Id, pub target: Tgt, pub source: Option<MonRef>, pub effect: Option<Eff>, pub modifier: f64 }

#[derive(Clone, Debug)]
pub struct Handler {
    pub eff: Eff, pub d: &'static EffData, pub etype: EType, pub cb: Id, pub holder: Holder, pub state: SLoc, pub absent: bool, pub cval: Option<CVal>, pub f: Option<HFn>,
    pub order: Option<f64>, pub priority: f64, pub speed: f64, pub sub_order: f64, pub effect_order: f64, pub index: Option<usize>, pub target: Option<MonRef>,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Choice { Move, MegaEvo, BeforeTurn, Residual, BeforeTurnMove, PriorityChargeMove, Pass, Switch, InstaSwitch, RunSwitch, RevivalBlessing }
#[derive(Clone, Debug)]
pub struct Action {
    pub choice: Choice, pub order: f64, pub priority: f64, pub fractional_priority: f64, pub speed: f64, pub sub_order: f64, pub effect_order: f64,
    pub pokemon: Option<MonRef>, pub target_loc: i64, pub original_target: Option<MonRef>, pub am: Option<usize>, pub mega: bool, pub source_effect: Option<Eff>,
    /// the pokemon switching in (switch / instaswitch)
    pub target: Option<MonRef>,
}

#[derive(Clone)]
pub struct FaintData { pub target: MonRef, pub source: Option<MonRef>, pub effect: Option<Eff> }

#[derive(Clone)]
pub struct Battle {
    pub dex: &'static Dex, pub reg: &'static FxMap<(Kind, Id, Id), HFn>, pub prng: Prng,
    pub field: Field, pub sides: [Side; 2], pub queue: Vec<Action>, pub turn: i64, pub effect_order: i64, pub ended: bool, pub winner: Option<Option<u8>>,
    pub faint_queue: Vec<FaintData>, pub amoves: Vec<ActiveMove>, pub active_move: Option<usize>, pub active_pokemon: Option<MonRef>, pub active_target: Option<MonRef>,
    pub effect: Option<Eff>, pub effect_state: SLoc, pub event: Option<EventCtx>, pub event_depth: i32, pub temp: Vec<EState>,
    pub log: Vec<String>, pub logging: bool, pub mid_turn: bool, pub request_switch: bool, pub last_successful_move_this_turn: Option<Id>, pub last_move: Option<usize>,
    pub unsupported: Vec<String>, pub quick_claw_roll: bool, pub eff_type: Id, pub nevents: u64, pub nfind: u64, pub speed_order: Vec<i64>,
}

/// up to four pokemon refs without allocating (derefs to a slice)
#[derive(Clone, Copy, Debug, Default)]
pub struct MonList { n: u8, v: [MonRef; 4] }
impl MonList {
    #[inline] pub fn push(&mut self, m: MonRef) { self.v[self.n as usize] = m; self.n += 1; }
    #[inline] pub fn filter(self, f: impl Fn(&MonRef) -> bool) -> MonList { let mut o = MonList::default(); for m in self { if f(&m) { o.push(m); } } o }
}
impl std::ops::Deref for MonList { type Target = [MonRef]; #[inline] fn deref(&self) -> &[MonRef] { &self.v[..self.n as usize] } }
impl IntoIterator for MonList { type Item = MonRef; type IntoIter = std::iter::Take<std::array::IntoIter<MonRef, 4>>; fn into_iter(self) -> Self::IntoIter { self.v.into_iter().take(self.n as usize) } }

pub const PREFIXLESS: [&str; 5] = ["BeforeTurn", "Update", "Weather", "WeatherChange", "TerrainChange"];

impl Battle {
    // ---------- accessors ----------
    pub fn p(&self, m: MonRef) -> &Pokemon { &self.sides[m.0 as usize].pokemon[m.1 as usize] }
    pub fn pm(&mut self, m: MonRef) -> &mut Pokemon { &mut self.sides[m.0 as usize].pokemon[m.1 as usize] }
    pub fn am(&self, i: usize) -> &ActiveMove { &self.amoves[i] }
    pub fn amm(&mut self, i: usize) -> &mut ActiveMove { &mut self.amoves[i] }
    pub fn new_am(&mut self, m: ActiveMove) -> usize { self.amoves.push(m); self.amoves.len() - 1 }
    /// active (slot occupant) refs on a side, including fainted ones (side.active)
    pub fn side_active(&self, s: u8) -> MonList { let mut o = MonList::default(); for x in self.sides[s as usize].active { if let Some(i) = x { o.push((s, i)); } } o }
    /// side.allies(): active with hp
    pub fn allies_of_side(&self, s: u8) -> MonList { self.side_active(s).filter(|m| self.p(*m).hp > 0) }
    pub fn allies_and_self(&self, m: MonRef) -> MonList { self.allies_of_side(m.0) }
    pub fn allies(&self, m: MonRef) -> MonList { self.allies_of_side(m.0).filter(|x| *x != m) }
    pub fn foes(&self, m: MonRef) -> MonList { self.allies_of_side(1 - m.0) }
    pub fn foes_all(&self, m: MonRef) -> MonList { self.side_active(1 - m.0) }
    pub fn adjacent_allies(&self, m: MonRef) -> MonList { self.allies_of_side(m.0).filter(|x| self.is_adjacent(m, *x)) }
    pub fn adjacent_foes(&self, m: MonRef) -> MonList { self.foes(m) }
    pub fn is_adjacent(&self, a: MonRef, b: MonRef) -> bool { if self.p(a).fainted || self.p(b).fainted { return false; } a != b }
    pub fn is_ally(&self, a: MonRef, b: MonRef) -> bool { a.0 == b.0 }
    /// all active non-fainted pokemon, side 0 first
    pub fn all_active(&self) -> MonList { let mut o = MonList::default(); for s in 0..2u8 { for m in self.side_active(s) { if !self.p(m).fainted { o.push(m); } } } o }
    pub fn slot_name(&self, m: MonRef) -> Id { ["p1a", "p1b", "p2a", "p2b"][m.0 as usize * 2 + (self.p(m).position as usize).min(1)] }
    pub fn mon_name(&self, m: MonRef) -> String { let p = self.p(m); format!("p{}{}: {}", m.0 + 1, if p.position == 0 { 'a' } else { 'b' }, self.dex.species.get(p.set_species).map(|s| s.name).unwrap_or(p.set_species)) }
    pub fn get_at_loc(&self, m: MonRef, loc: i64) -> Option<MonRef> {
        let side = if loc < 0 { m.0 } else { 1 - m.0 }; let l = loc.unsigned_abs() as usize;
        if l == 0 || l > 2 { return None; }
        self.sides[side as usize].active[l - 1].map(|i| (side, i))
    }
    pub fn get_loc_of(&self, src: MonRef, t: MonRef) -> i64 { let pos = self.p(t).position as i64 + 1; if src.0 == t.0 { -pos } else { pos } }
    pub fn add(&mut self, parts: &[&str]) { if self.logging { let l = format!("|{}", parts.join("|")); self.addl(l); } }
    /// DRAWTRACE=1: each log line ends in " #<random draws so far>", to find where the engine's draws part from Showdown's
    pub fn addl(&mut self, s: String) { if self.logging {
        static T: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
        if *T.get_or_init(|| std::env::var("DRAWTRACE").is_ok()) { self.log.push(format!("{} #{}", s, self.prng.draws)); } else { self.log.push(s); } } }
    pub fn unsupported(&mut self, what: String) { if !self.unsupported.contains(&what) { self.unsupported.push(what); } }

    pub fn state_mut(&mut self, loc: SLoc) -> Option<&mut EState> {
        match loc {
            SLoc::Status(m) => Some(&mut self.pm(m).status_state),
            SLoc::Vol(m, i) => find_mut(&mut self.pm(m).volatiles, i),
            SLoc::Ability(m) => Some(&mut self.pm(m).ability_state),
            SLoc::Item(m) => Some(&mut self.pm(m).item_state),
            SLoc::Species(_) | SLoc::Nil => None,
            SLoc::Slot(s, pos, i) => find_mut(&mut self.sides[s as usize].slot_conditions[pos as usize], i),
            SLoc::SideC(s, i) => find_mut(&mut self.sides[s as usize].side_conditions, i),
            SLoc::Weather => Some(&mut self.field.weather_state),
            SLoc::Terrain => Some(&mut self.field.terrain_state),
            SLoc::Pseudo(i) => find_mut(&mut self.field.pseudo, i),
            SLoc::Temp(i) => self.temp.get_mut(i),
        }
    }
    pub fn state(&self, loc: SLoc) -> Option<&EState> {
        match loc {
            SLoc::Status(m) => Some(&self.p(m).status_state),
            SLoc::Vol(m, i) => find(&self.p(m).volatiles, i),
            SLoc::Ability(m) => Some(&self.p(m).ability_state),
            SLoc::Item(m) => Some(&self.p(m).item_state),
            SLoc::Species(_) | SLoc::Nil => None,
            SLoc::Slot(s, pos, i) => find(&self.sides[s as usize].slot_conditions[pos as usize], i),
            SLoc::SideC(s, i) => find(&self.sides[s as usize].side_conditions, i),
            SLoc::Weather => Some(&self.field.weather_state),
            SLoc::Terrain => Some(&self.field.terrain_state),
            SLoc::Pseudo(i) => find(&self.field.pseudo, i),
            SLoc::Temp(i) => self.temp.get(i),
        }
    }
    /// this.effectState of the running handler
    pub fn es(&mut self) -> &mut EState { let l = self.effect_state; self.state_mut(l).expect("effect state") }
    pub fn es_ref(&self) -> Option<&EState> { self.state(self.effect_state) }
    /// the holder (effectState.target) of the running handler's state, when it is a pokemon
    pub fn es_mon(&self) -> Option<MonRef> {
        match self.effect_state { SLoc::Status(m) | SLoc::Vol(m, _) | SLoc::Ability(m) | SLoc::Item(m) | SLoc::Species(m) => Some(m), _ => None }
    }
    pub fn init_state(&mut self, i: Id, target_active: Option<bool>) -> EState {
        // initEffectState: effectOrder++ when the state has an id and a target that is active (or a side/field target)
        let mut s = EState::new(i);
        if !i.is_empty() && target_active.unwrap_or(false) { s.effect_order = self.effect_order; self.effect_order += 1; }
        s
    }

    /// effect data of a pokemon's current ability / item / status through its per-pokemon cache (valid only while the cached
    /// entry's id is the pokemon's current id; otherwise looked up again and stored)
    #[inline] fn cached_eff(&self, c: &DCache, kind: Kind, want: Id) -> &'static EffData {
        if let Some(d) = c.get() { if (d.id.as_ptr() == want.as_ptr() && d.id.len() == want.len()) || d.id == want { return d; } }
        let d = self.dex.eff(kind, want); c.set(d); d
    }
    #[inline] pub fn ab_data(&self, m: MonRef) -> &'static EffData { let p = self.p(m); self.cached_eff(&p.ab_d, Kind::Ability, p.ability) }
    #[inline] pub fn it_data(&self, m: MonRef) -> &'static EffData { let p = self.p(m); self.cached_eff(&p.it_d, Kind::Item, p.item) }
    #[inline] pub fn st_data(&self, m: MonRef) -> &'static EffData { let p = self.p(m); self.cached_eff(&p.st_d, Kind::Cond, p.status) }
    pub fn etype_of(&self, e: &Eff) -> EType {
        match e.kind { Kind::Move => EType::Move, Kind::Ability => EType::Ability, Kind::Item => EType::Item, Kind::Species => EType::Pokemon,
                       Kind::Cond => self.dex.conds.get(e.id).map(|c| c.etype).unwrap_or(EType::Condition) }
    }
    pub fn effdata(&self, e: &Eff) -> &'static EffData { self.dex.eff(e.kind, e.id) }

    // ---------- suppression checks ----------
    pub fn ignoring_ability(&self, m: MonRef) -> bool {
        let p = self.p(m);
        if !p.is_active { return true; }
        let ab = self.ab_data(m);
        if ab.notransform && p.transformed { return true; }
        if ab.cantsuppress { return false; }
        if find(&p.volatiles, "gastroacid").is_some() { return true; }
        if p.item == "abilityshield" && !self.ignoring_item(m) || p.ability == "neutralizinggas" { return false; }
        for o in self.all_active() {
            let q = self.p(o);
            if q.ability == "neutralizinggas" && find(&q.volatiles, "gastroacid").is_none() && !q.transformed && !q.ability_state.has("ending") && find(&p.volatiles, "commanding").is_none() { return true; }
        }
        false
    }
    pub fn ignoring_item(&self, m: MonRef) -> bool {
        let p = self.p(m);
        if !p.is_active { return true; }
        if find(&p.volatiles, "embargo").is_some() || find(&self.field.pseudo, "magicroom").is_some() { return true; }
        p.ability == "klutz" && !self.it_data(m).ignore_klutz && !self.ignoring_ability(m)
    }
    pub fn has_ability(&self, m: MonRef, a: &str) -> bool { self.p(m).ability == a && !self.ignoring_ability(m) }
    pub fn has_item(&self, m: MonRef, i: &str) -> bool { self.p(m).item == i && !self.ignoring_item(m) }
    pub fn suppressing_ability(&self, target: Option<MonRef>) -> bool {
        match (self.active_pokemon, self.active_move) {
            (Some(ap), Some(am)) => self.p(ap).is_active && Some(ap) != target && self.am(am).ignore_ability && !target.map(|t| self.has_item(t, "abilityshield")).unwrap_or(false),
            _ => false,
        }
    }
    pub fn suppressing_weather(&self) -> bool {
        for m in (0..2u8).flat_map(|s| self.side_active(s)) {
            let p = self.p(m);
            if !p.fainted && self.ab_data(m).suppress_weather && !self.ignoring_ability(m) && !p.ability_state.has("ending") { return true; }
        }
        false
    }
    pub fn effective_weather(&self) -> Id { if self.suppressing_weather() { "" } else { self.field.weather } }

    // ---------- handler discovery ----------
    /// getCallback: the effect's on<Event> callback; for abilities/items an absent onSwitchIn falls back to onStart (with the sort keys
    /// still taken from onSwitchIn*, e.g. the seeds' onSwitchInPriority). Absent entries (sort keys only) are returned for getKey use.
    fn get_callback(&self, holder_is_mon: bool, eff: &EffData, kind: Kind, cb: Cb) -> Option<(Id, CbInfo)> {
        let direct = eff.cbi(cb.i);
        if let Some(c) = direct { if !c.absent || c.cval.is_some() { return Some((cb.name, c.clone())); } }
        if holder_is_mon && cb.switch_in && eff.cbi(self.dex.i_on_any_switch_in).is_none() &&
           (matches!(kind, Kind::Ability | Kind::Item) || (eff.etype == EType::Status && (eff.id.starts_with("ability:") || eff.id.starts_with("item:")))) {
            if let Some(st) = eff.cbi(self.dex.i_on_start) { if !st.absent {
                let mut c = st.clone();
                let keys = direct.cloned().unwrap_or_default(); c.order = keys.order; c.priority = keys.priority; c.sub_order = keys.sub_order;
                return Some((self.dex.on_start, c));
            } }
        }
        direct.map(|c| (cb.name, c.clone()))
    }
    fn mk_handler(&self, eff: Eff, d: &'static EffData, cb: Id, called: Id, info: Option<&CbInfo>, holder: Holder, state: SLoc) -> Handler {
        let etype = self.etype_of(&eff);
        let (absent, cval, order, priority, mut sub, f) = match info { Some(c) => (c.absent, c.cval.clone(), c.order, c.priority, c.sub_order, c.f), None => (true, None, None, 0.0, 0.0, None) };
        // resolvePriority: default subOrder by effect type
        if sub == 0.0 {
            sub = match etype { EType::Condition => 2.0, EType::Weather => 5.0, EType::Ability => 7.0, EType::Item => 8.0, _ => 0.0 };
            if etype == EType::Condition { match state { SLoc::Slot(..) => sub = 3.0, SLoc::SideC(..) => sub = 4.0, SLoc::Pseudo(_) | SLoc::Weather | SLoc::Terrain => sub = 5.0, _ => {} } }
            else if etype == EType::Ability { if d.name == "Poison Touch" || d.name == "Perish Body" { sub = 6.0 } else if d.name == "Stall" { sub = 9.0 } }
        }
        let mut effect_order = 0.0;
        if cb.ends_with("SwitchIn") || cb.ends_with("RedirectTarget") { effect_order = self.state(state).map(|s| s.effect_order as f64).unwrap_or(0.0); }
        let mut speed = 0.0;
        if let Holder::Mon(m) = holder {
            speed = self.p(m).speed;
            if d.name == "Magic Bounce" && cb == "onAllyTryHitSide" { speed = self.get_stat_simple(m, 4, true, true) as f64; }
            if cb.ends_with("SwitchIn") {
                let fpv = m.0 as i64 + 2 * self.p(m).position as i64;
                let idx = self.speed_order.iter().position(|x| *x == fpv).map(|x| x as f64).unwrap_or(-1.0);
                speed -= idx / 4.0;
            }
        }
        Handler { eff, d, etype, cb: called, holder, state, absent, cval, f, order: order.filter(|o| *o != 0.0), priority, speed, sub_order: sub, effect_order, index: None, target: None }
    }
    pub fn find_pokemon_handlers(&self, m: MonRef, cb: Cb, get_key: bool, out: &mut Vec<Handler>) {
        if !get_key && !cb.switch_in && cb.i == NO_CB { return; }
        let p = self.p(m);
        let hm = Holder::Mon(m);
        let skip = |d: &EffData| !get_key && !cb.switch_in && !d.has(cb.i);   // no callback, no sort keys wanted, no onStart stand-in
        if !p.status.is_empty() {
            let d = self.st_data(m);
            if skip(d) { } else {
            let c = self.get_callback(true, d, Kind::Cond, cb);
            if c.is_some() || (get_key && p.status_state.duration.unwrap_or(0) != 0) {
                out.push(self.mk_handler(Eff::cond(p.status), d, cb.name, c.as_ref().map(|x| x.0).unwrap_or(cb.name), c.as_ref().map(|x| &x.1), hm, SLoc::Status(m)));
            } }
        }
        for (vid, st) in &p.volatiles {
            let d = self.dex.eff(Kind::Cond, vid);
            if skip(d) { continue; }
            let c = self.get_callback(true, d, Kind::Cond, cb);
            if c.is_some() || (get_key && st.duration.unwrap_or(0) != 0) {
                out.push(self.mk_handler(Eff::cond(vid), d, cb.name, c.as_ref().map(|x| x.0).unwrap_or(cb.name), c.as_ref().map(|x| &x.1), hm, SLoc::Vol(m, vid)));
            }
        }
        if !p.ability.is_empty() {
            let d = self.ab_data(m);
            if skip(d) { } else {
            let c = self.get_callback(true, d, Kind::Ability, cb);
            if c.is_some() || (get_key && p.ability_state.duration.unwrap_or(0) != 0) {
                out.push(self.mk_handler(Eff::new(Kind::Ability, p.ability), d, cb.name, c.as_ref().map(|x| x.0).unwrap_or(cb.name), c.as_ref().map(|x| &x.1), hm, SLoc::Ability(m)));
            } }
        }
        if !p.item.is_empty() {
            let d = self.it_data(m);
            if skip(d) { } else {
            let c = self.get_callback(true, d, Kind::Item, cb);
            if c.is_some() || (get_key && p.item_state.duration.unwrap_or(0) != 0) {
                out.push(self.mk_handler(Eff::new(Kind::Item, p.item), d, cb.name, c.as_ref().map(|x| x.0).unwrap_or(cb.name), c.as_ref().map(|x| &x.1), hm, SLoc::Item(m)));
            } }
        }
        // species callbacks: none in Champions scope
        let side = &self.sides[m.0 as usize];
        if (p.position as usize) < 2 {
            for (cid, st) in &side.slot_conditions[p.position as usize] {
                let d = self.dex.eff(Kind::Cond, cid);
                if skip(d) { continue; }
                let c = self.get_callback(true, d, Kind::Cond, cb);
                if c.is_some() || (get_key && st.duration.unwrap_or(0) != 0) {
                    out.push(self.mk_handler(Eff::cond(cid), d, cb.name, c.as_ref().map(|x| x.0).unwrap_or(cb.name), c.as_ref().map(|x| &x.1), hm, SLoc::Slot(m.0, p.position, cid)));
                }
            }
        }
    }
    pub fn find_side_handlers(&self, s: u8, cb: Cb, get_key: bool, custom: Option<MonRef>, out: &mut Vec<Handler>) {
        if !get_key && cb.i == NO_CB { return; }
        for (cid, st) in &self.sides[s as usize].side_conditions {
            let d = self.dex.eff(Kind::Cond, cid);
            if !get_key && !d.has(cb.i) { continue; }   // holder is a side: no onStart stand-in
            let c = self.get_callback(false, d, Kind::Cond, cb);
            if c.is_some() || (get_key && st.duration.unwrap_or(0) != 0) {
                let holder = custom.map(Holder::Mon).unwrap_or(Holder::Side(s));
                out.push(self.mk_handler(Eff::cond(cid), d, cb.name, c.as_ref().map(|x| x.0).unwrap_or(cb.name), c.as_ref().map(|x| &x.1), holder, SLoc::SideC(s, cid)));
            }
        }
    }
    pub fn find_field_handlers(&self, cb: Cb, get_key: bool, custom: Option<MonRef>, out: &mut Vec<Handler>) {
        if !get_key && cb.i == NO_CB { return; }
        let holder = custom.map(Holder::Mon).unwrap_or(Holder::Field);
        for (cid, st) in &self.field.pseudo {
            let d = self.dex.eff(Kind::Cond, cid);
            if !get_key && !d.has(cb.i) { continue; }
            let c = self.get_callback(false, d, Kind::Cond, cb);
            if c.is_some() || (get_key && st.duration.unwrap_or(0) != 0) {
                out.push(self.mk_handler(Eff::cond(cid), d, cb.name, c.as_ref().map(|x| x.0).unwrap_or(cb.name), c.as_ref().map(|x| &x.1), holder, SLoc::Pseudo(cid)));
            }
        }
        if !self.field.weather.is_empty() {
            let d = self.dex.eff(Kind::Cond, self.field.weather);
            let c = self.get_callback(false, d, Kind::Cond, cb);
            if c.is_some() || (get_key && self.field.weather_state.duration.unwrap_or(0) != 0) {
                out.push(self.mk_handler(Eff::cond(self.field.weather), d, cb.name, c.as_ref().map(|x| x.0).unwrap_or(cb.name), c.as_ref().map(|x| &x.1), holder, SLoc::Weather));
            }
        }
        if !self.field.terrain.is_empty() {
            let d = self.dex.eff(Kind::Cond, self.field.terrain);
            let c = self.get_callback(false, d, Kind::Cond, cb);
            if c.is_some() || (get_key && self.field.terrain_state.duration.unwrap_or(0) != 0) {
                out.push(self.mk_handler(Eff::cond(self.field.terrain), d, cb.name, c.as_ref().map(|x| x.0).unwrap_or(cb.name), c.as_ref().map(|x| &x.1), holder, SLoc::Terrain));
            }
        }
    }
    pub fn find_event_handlers(&self, target: &Tgt, n: &EvNames, source: Option<MonRef>) -> Vec<Handler> {
        let mut hs = Vec::new();   // most events find nothing: allocate only on the first push
        if let Tgt::Mons(list) = target {
            for (i, t) in list.iter().enumerate() {
                if let Some(m) = t {
                    let mut cur = self.find_event_handlers(&Tgt::Mon(*m), n, source);
                    for h in cur.iter_mut() { h.target = Some(*m); h.index = Some(i); }
                    hs.extend(cur);
                }
            }
            return hs;
        }
        let prefixed = n.prefixed;
        let on = n.on_c;
        let mut tside: Option<u8> = match target { Tgt::Side(s) => Some(*s), _ => None };
        let bubble = tside.is_some();
        if let Tgt::Mon(m) = target {
            if self.p(*m).is_active || source.map(|s| self.p(s).is_active).unwrap_or(false) {
                self.find_pokemon_handlers(*m, on, false, &mut hs);
                if prefixed {
                    let (ally, any, foe) = (n.ally_c, n.any_c, n.foe_c);
                    // a scan for a name no effect defines returns at once, so skip the loops when both names are such
                    if ally.i != NO_CB || any.i != NO_CB { for a in self.allies_and_self(*m) { self.find_pokemon_handlers(a, ally, false, &mut hs); self.find_pokemon_handlers(a, any, false, &mut hs); } }
                    if foe.i != NO_CB || any.i != NO_CB { for f in self.foes(*m) { self.find_pokemon_handlers(f, foe, false, &mut hs); self.find_pokemon_handlers(f, any, false, &mut hs); } }
                }
                tside = Some(m.0);
            }
        }
        if let (Some(s), true) = (source, prefixed) { self.find_pokemon_handlers(s, n.source_c, false, &mut hs); }
        if let Some(ts) = tside {
            let (foe, any) = (n.foe_c, n.any_c);
            for s in 0..2u8 {
                if bubble {
                    for a in self.side_active(s) {
                        if s == ts { self.find_pokemon_handlers(a, on, false, &mut hs); } else if prefixed { self.find_pokemon_handlers(a, foe, false, &mut hs); }
                        if prefixed { self.find_pokemon_handlers(a, any, false, &mut hs); }
                    }
                }
                if s == ts { self.find_side_handlers(s, on, false, None, &mut hs); } else if prefixed { self.find_side_handlers(s, foe, false, None, &mut hs); }
                if prefixed { self.find_side_handlers(s, any, false, None, &mut hs); }
            }
        }
        self.find_field_handlers(on, false, None, &mut hs);
        hs
    }

    // ---------- sorting ----------
    pub fn cmp_priority(a: (Option<f64>, f64, f64, f64, f64), b: (Option<f64>, f64, f64, f64, f64)) -> f64 {
        let big = 4294967296.0;
        let d = -(b.0.unwrap_or(big) - a.0.unwrap_or(big)); if d != 0.0 { return d; }
        let d = b.1 - a.1; if d != 0.0 { return d; }
        let d = b.2 - a.2; if d != 0.0 { return d; }
        let d = -(b.3 - a.3); if d != 0.0 { return d; }
        -(b.4 - a.4)
    }
    fn hkey(h: &Handler) -> (Option<f64>, f64, f64, f64, f64) { (h.order, h.priority, h.speed, h.sub_order, h.effect_order) }
    /// speedSort: selection sort by comparator; ties are shuffled with the PRNG
    pub fn speed_sort<T>(&mut self, list: &mut Vec<T>, key: impl Fn(&T) -> (Option<f64>, f64, f64, f64, f64)) {
        if list.len() < 2 { return; }
        let mut sorted = 0;
        while sorted + 1 < list.len() {
            let mut next = vec![sorted];
            for i in sorted + 1..list.len() {
                let delta = Self::cmp_priority(key(&list[next[0]]), key(&list[i]));
                if delta < 0.0 { continue; }
                if delta > 0.0 { next = vec![i]; } else { next.push(i); }
            }
            for (k, &idx) in next.iter().enumerate() { if idx != sorted + k { list.swap(sorted + k, idx); } }
            if next.len() > 1 { let n = next.len(); if self.logging && std::env::var("DRAWTRACE").is_ok() { let k = key(&list[sorted]); self.addl(format!("|~tie|{}|{:?}", n, k)); } self.prng.shuffle(list, sorted, sorted + n); }
            sorted += next.len();
        }
    }

    // ---------- running handlers ----------
    fn call_handler(&mut self, h: &Handler, args: &mut HArgs) -> RV {
        if let Some(c) = &h.cval {
            return match c { CVal::Bool(b) => RV::B(*b), CVal::Num(n) => RV::N(*n), CVal::Str(s) => RV::S(s) };
        }
        if let Some(f) = h.f { return f(self, args); }
        let key = (h.eff.kind, h.eff.id, h.cb);
        match self.reg.get(&key) {
            Some(f) => { let f = *f; f(self, args) }
            None => { self.unsupported(format!("{:?}:{}.{}", h.eff.kind, h.eff.id, h.cb)); RV::Undef }
        }
    }
    /// runEvent
    pub fn run_event(&mut self, ev: &str, target: Tgt, source: Option<MonRef>, src_eff: Option<Eff>, relay: RV, on_effect: bool, fast_exit: bool) -> RV {
        self.run_event_full(ev, target, source, src_eff, relay, on_effect, fast_exit).0
    }
    pub fn run_event_spread(&mut self, ev: &str, targets: Vec<Option<MonRef>>, source: Option<MonRef>, src_eff: Option<Eff>, relay: Option<Vec<RV>>) -> Vec<RV> {
        let n = targets.len();
        let r = self.run_event_full_spread(ev, targets, source, src_eff, relay.unwrap_or_else(|| vec![RV::B(true); n]));
        r
    }
    fn run_event_full_spread(&mut self, ev: &str, targets: Vec<Option<MonRef>>, source: Option<MonRef>, src_eff: Option<Eff>, mut trv: Vec<RV>) -> Vec<RV> {
        let n = self.dex.evn(ev);
        let tgt = Tgt::Mons(targets);
        let mut hs = self.find_event_handlers(&tgt, n, source);
        if n.left_to_right {
            hs.sort_by(|a, b| {
                let big = 4294967296.0;
                let d = -(b.order.unwrap_or(big) - a.order.unwrap_or(big)); let d = if d != 0.0 { d } else { b.priority - a.priority };
                let d = if d != 0.0 { d } else { -((b.index.unwrap_or(0) as f64) - (a.index.unwrap_or(0) as f64)) };
                d.partial_cmp(&0.0).unwrap()
            });
        } else { self.speed_sort(&mut hs, Self::hkey); }
        let has_relay = true;
        let parent = self.event.take();
        self.event = Some(EventCtx { id: n.ev, target: tgt.clone(), source, effect: src_eff, modifier: 1.0 });
        self.event_depth += 1;
        for h in hs {
            let idx = h.index.unwrap();
            if !trv[idx].truthy() && !(trv[idx] == RV::N(0.0) && n.damaging_hit) { continue; }
            if let Some(t) = h.target { if let Some(e) = self.event.as_mut() { e.target = Tgt::Mon(t); } }
            if !self.handler_allowed(&h, n) { continue; }
            let mut args = HArgs { relay: trv[idx].clone(), has_relay, target: h.target.map(Tgt::Mon).unwrap_or(Tgt::None), source, src_eff };
            let rv = self.invoke(&h, &mut args);
            if !rv.is_undef() {
                if !rv.truthy() { trv[idx] = rv; if trv.iter().all(|v| !v.truthy()) { break; } }
            }
        }
        self.event_depth -= 1;
        self.event = parent;
        trv
    }
    fn handler_allowed(&self, h: &Handler, n: &EvNames) -> bool {
        if h.etype == EType::Status { if let Holder::Mon(m) = h.holder { if self.p(m).status != h.eff.id { return false; } } }
        if h.etype == EType::Ability && self.active_move.is_some() && h.d.breakable { if let Holder::Mon(m) = h.holder { if self.suppressing_ability(Some(m)) { return false; } } }
        if let Holder::Mon(m) = h.holder {
            if !n.start && !n.switch_in && !n.take_item && h.etype == EType::Item && self.ignoring_item(m) { return false; }
            else if !n.end && h.etype == EType::Ability && self.ignoring_ability(m) { return false; }
        }
        if (h.etype == EType::Weather || n.weather) && !n.residual && !n.end && self.suppressing_weather() { return false; }
        true
    }
    fn invoke(&mut self, h: &Handler, args: &mut HArgs) -> RV {
        if h.absent { return RV::Undef; }
        let (pe, ps) = (self.effect, self.effect_state);
        self.effect = Some(h.eff); self.effect_state = h.state;
        let rv = self.call_handler(h, args);
        self.effect = pe; self.effect_state = ps;
        rv
    }
    fn run_event_full(&mut self, ev: &str, target: Tgt, source: Option<MonRef>, src_eff: Option<Eff>, relay: RV, on_effect: bool, fast_exit: bool) -> (RV, ()) {
        if self.event_depth >= 8 { panic!("event stack overflow at {}", ev); }
        self.nevents += 1;
        let n = self.dex.evn(ev);
        // fast path: no effect anywhere defines any handler for this event (onX / onAllyX / onFoeX / onAnyX / onSourceX), so nothing can run
        if !on_effect && !n.possible {
            return (match relay { RV::Undef | RV::Null => RV::B(true), r => r }, ());
        }
        let mut hs = self.find_event_handlers(&target, n, source);
        // nothing to run: the loop below would leave relay as it is (an integer relay through modify(n, 1) is unchanged), so return now
        if hs.is_empty() && !on_effect {
            return (match relay { RV::Undef | RV::Null => RV::B(true), r => r }, ());
        }
        let mut temp_pushed = false;
        if on_effect {
            let se = src_eff.expect("onEffect without effect");
            let d = self.effdata(&se);
            let cbname = n.on;
            if let Some(c) = d.cbi(n.on_c.i).filter(|c| !c.absent || c.cval.is_some()) {
                let holder = match &target { Tgt::Mon(m) => Holder::Mon(*m), Tgt::Side(s) => Holder::Side(*s), Tgt::Field => Holder::Field, _ => Holder::Battle };
                self.temp.push(EState::default()); temp_pushed = true;
                let mut h = self.mk_handler(se, d, cbname, cbname, Some(c), holder, SLoc::Temp(self.temp.len() - 1));
                h.absent = false;
                hs.insert(0, h);
            }
        }
        if n.left_to_right {
            hs.sort_by(|a, b| { let big = 4294967296.0;
                let d = -(b.order.unwrap_or(big) - a.order.unwrap_or(big)); let d = if d != 0.0 { d } else { b.priority - a.priority };
                d.partial_cmp(&0.0).unwrap() });
        } else if fast_exit {
            hs.sort_by(|a, b| { let d = b.priority - a.priority; let d = if d != 0.0 { d } else { b.speed - a.speed };
                let d = if d != 0.0 { d } else if matches!(a.state, SLoc::Ability(_)) && matches!(b.state, SLoc::Ability(_)) { -(b.effect_order - a.effect_order) } else { 0.0 };
                d.partial_cmp(&0.0).unwrap() });
        } else {
            if hs.len() > 1 && self.logging && std::env::var("DRAWTRACE").is_ok() {
                let l = format!("|~ev|{}|{}", ev, hs.iter().map(|h| format!("{}.{}:{}:{}:{}:{:?}:{:?}", h.eff.id, h.cb, h.priority, h.speed, h.sub_order, h.holder, h.state)).collect::<Vec<_>>().join(" ")); self.addl(l); }
            self.speed_sort(&mut hs, Self::hkey);
        }
        let has_relay = !matches!(relay, RV::Undef | RV::Null);
        let mut relay = if has_relay { relay } else { RV::B(true) };
        let parent = self.event.take();
        self.event = Some(EventCtx { id: n.ev, target: target.clone(), source, effect: src_eff, modifier: 1.0 });
        self.event_depth += 1;
        for h in hs.iter() {
            if !self.handler_allowed(h, n) { continue; }
            let mut args = HArgs { relay: relay.clone(), has_relay, target: target.clone(), source, src_eff };
            let rv = self.invoke(h, &mut args);
            if !rv.is_undef() {
                relay = rv;
                if !relay.truthy() || fast_exit { break; }
            }
        }
        self.event_depth -= 1;
        if let RV::N(n) = relay { if n >= 0.0 && n == n.floor() {
            let m = self.event.as_ref().unwrap().modifier;
            relay = RV::N(self.modify(n, m) as f64);
        } }
        self.event = parent;
        if temp_pushed { self.temp.pop(); }
        (relay, ())
    }
    pub fn priority_event(&mut self, ev: &str, target: Tgt, source: Option<MonRef>, src_eff: Option<Eff>, relay: RV, on_effect: bool) -> RV {
        self.run_event(ev, target, source, src_eff, relay, on_effect, true)
    }
    /// singleEvent
    pub fn single_event(&mut self, ev: &str, eff: Eff, state: Option<SLoc>, target: Tgt, source: Option<MonRef>, src_eff: Option<Eff>, relay: RV) -> RV {
        let has_relay = !relay.is_undef();
        let relay = if has_relay { relay } else { RV::B(true) };
        let n = self.dex.evn(ev);
        let d = self.effdata(&eff);
        // no callback: nothing to check or run
        let cbname = if eff.part.is_empty() { n.on } else { cbp(eff.part, ev) };
        let (cval, f) = if eff.part.is_empty() {
            match d.cbi(n.on_c.i) { Some(i) if !i.absent || i.cval.is_some() => (i.cval.clone(), i.f), _ => return relay }
        } else { (None, None) };
        let etype = self.etype_of(&eff);
        if let Tgt::Mon(m) = target {
            if etype == EType::Status && self.p(m).status != eff.id { return relay; }
            if n.switch_in && etype == EType::Ability && d.breakable && self.suppressing_ability(Some(m)) { return relay; }
            if !n.start && !n.take_item && !n.set_ability && etype == EType::Item && self.ignoring_item(m) { return relay; }
            if !n.end && etype == EType::Ability && self.ignoring_ability(m) { return relay; }
        }
        if etype == EType::Weather && !n.field_srs && self.suppressing_weather() { return relay; }
        let mut temp_pushed = false;
        let loc = match state { Some(l) => l, None => { self.temp.push(EState::default()); temp_pushed = true; SLoc::Temp(self.temp.len() - 1) } };
        let h = Handler { eff, d, etype, cb: cbname, holder: Holder::Battle, state: loc, absent: false, cval, f, order: None, priority: 0.0, speed: 0.0,
                          sub_order: 0.0, effect_order: 0.0, index: None, target: None };
        let parent = self.event.take();
        self.event = Some(EventCtx { id: n.ev, target: target.clone(), source, effect: src_eff, modifier: f64::NAN });
        self.event_depth += 1;
        let mut args = HArgs { relay: relay.clone(), has_relay, target, source, src_eff };
        let rv = self.invoke(&h, &mut args);
        self.event_depth -= 1;
        self.event = parent;
        if temp_pushed { self.temp.pop(); }
        if rv.is_undef() { relay } else { rv }
    }
    /// eachEvent: run an event on every active pokemon in speed order
    pub fn each_event(&mut self, ev: &str, eff: Option<Eff>) {
        let actives = self.all_active();
        let eff = eff.or(self.effect);
        let speeds: Vec<f64> = actives.iter().map(|m| self.p(*m).speed).collect();
        let mut pairs: Vec<(MonRef, f64)> = actives.iter().copied().zip(speeds).collect();
        self.speed_sort(&mut pairs, |x| (None, 0.0, x.1, 0.0, 0.0));
        for (m, _) in pairs { self.run_event(ev, Tgt::Mon(m), None, eff, RV::Undef, false, false); }
        if ev == "Weather" { self.each_event("Update", None); }
    }

    // ---------- arithmetic ----------
    pub fn trunc(x: f64) -> i64 { if x >= 0.0 && x < 4294967296.0 { x.trunc() as i64 } else { (x.trunc() as i64).rem_euclid(4294967296) } }
    pub fn modify(&self, value: f64, m: f64) -> i64 {
        let modifier = Self::trunc(m * 4096.0);
        Self::trunc((Self::trunc(value * modifier as f64) + 2048 - 1) as f64 / 4096.0)
    }
    pub fn modify_frac(&self, value: f64, num: f64, den: f64) -> i64 {
        let modifier = Self::trunc(num * 4096.0 / den);
        Self::trunc((Self::trunc(value * modifier as f64) + 2048 - 1) as f64 / 4096.0)
    }
    pub fn chain_modify(&mut self, num: f64, den: f64) {
        let e = self.event.as_mut().expect("chainModify outside event");
        let prev = Self::trunc(e.modifier * 4096.0);
        let next = Self::trunc(num * 4096.0 / den);
        e.modifier = ((prev * next + 2048) >> 12) as f64 / 4096.0;
    }
    pub fn clamp(x: i64, lo: i64, hi: i64) -> i64 { x.max(lo).min(hi) }

    // ---------- stats ----------
    /// pokemon.getStat(stat, unboosted, unmodified); i in 1..=5 (atk..spe)
    pub fn get_stat(&mut self, m: MonRef, i: usize, unboosted: bool, unmodified: bool) -> i64 {
        let mut stat = self.p(m).stored[i];
        if !unboosted {
            let mut boosts: Boosts = (0..7).map(|k| (k as u8, self.p(m).boosts[k])).collect();
            if !unmodified {
                if let RV::Boosts(b) = self.run_event("ModifyBoost", Tgt::Mon(m), None, None, RV::Boosts(boosts.clone()), false, false) { boosts = b; }
            }
            let b = boosts.iter().find(|(k, _)| *k as usize == i - 1).map(|x| x.1).unwrap_or(0).clamp(-6, 6);
            stat = boost_stat(stat, b);
        }
        if !unmodified {
            let ev = ["", "ModifyAtk", "ModifyDef", "ModifySpA", "ModifySpD", "ModifySpe"][i];
            stat = self.run_event(ev, Tgt::Mon(m), None, None, RV::N(stat as f64), false, false).num() as i64;
        }
        if i == 5 && stat > 10000 { stat = 10000; }
        stat
    }
    /// getStat without events (used where Showdown reads raw values)
    pub fn get_stat_simple(&self, m: MonRef, i: usize, unboosted: bool, _unmodified: bool) -> i64 {
        let p = self.p(m); let s = p.stored[i];
        if unboosted { s } else { boost_stat(s, p.boosts[i - 1]) }
    }
    /// Champions getActionSpeed: getStat('spe'), negated under Trick Room
    pub fn action_speed_of(&mut self, m: MonRef) -> f64 {
        let s = self.get_stat(m, 5, false, false) as f64;
        if find(&self.field.pseudo, "trickroom").is_some() { -s } else { s }
    }
    pub fn update_speed(&mut self) { for m in self.all_active() { let s = self.action_speed_of(m); self.pm(m).speed = s; } }
    pub fn get_types(&mut self, m: MonRef) -> Vec<Id> {
        let base = self.p(m).types.clone();
        let mut t = match self.run_event("Type", Tgt::Mon(m), None, None, RV::Types(base.clone()), false, false) { RV::Types(t) => t, _ => base };
        if t.is_empty() { t.push("Normal"); }
        let added = self.p(m).added_type;
        if !added.is_empty() { t.push(added); }
        t
    }
    pub fn has_type(&mut self, m: MonRef, t: &str) -> bool { self.get_types(m).iter().any(|x| *x == t) }
}

pub fn boost_stat(stat: i64, b: i64) -> i64 {
    let t = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]; let b = b.clamp(-6, 6);
    if b >= 0 { (stat as f64 * t[b as usize]).floor() as i64 } else { (stat as f64 / t[(-b) as usize]).floor() as i64 }
}
