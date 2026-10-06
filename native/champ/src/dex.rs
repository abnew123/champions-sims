//! Engine data (native/export_engine.js): moves, items, abilities, conditions, species, with every effect's event callbacks and the
//! order/priority/subOrder Showdown sorts their handlers by.
use serde_json::Value;
use std::collections::{HashMap, HashSet};
use std::hash::{BuildHasherDefault, Hasher};
use std::sync::{Mutex, OnceLock};

/// FxHash (rustc's hasher): far cheaper than SipHash for the short string keys used everywhere here
#[derive(Default, Clone, Copy)]
pub struct Fx(u64);
impl Fx { #[inline] fn add(&mut self, w: u64) { self.0 = (self.0.rotate_left(5) ^ w).wrapping_mul(0x517cc1b727220a95); } }
impl Hasher for Fx {
    #[inline] fn write(&mut self, bytes: &[u8]) {
        let mut c = bytes.chunks_exact(8);
        for x in &mut c { self.add(u64::from_le_bytes(x.try_into().unwrap())); }
        let r = c.remainder(); if !r.is_empty() { let mut b = [0u8; 8]; b[..r.len()].copy_from_slice(r); self.add(u64::from_le_bytes(b) ^ ((r.len() as u64) << 56)); }
    }
    #[inline] fn write_u8(&mut self, i: u8) { self.add(i as u64); }
    #[inline] fn write_usize(&mut self, i: usize) { self.add(i as u64); }
    #[inline] fn write_u64(&mut self, i: u64) { self.add(i); }
    #[inline] fn finish(&self) -> u64 { self.0 }
}
pub type FxBuild = BuildHasherDefault<Fx>;
pub type FxMap<K, V> = HashMap<K, V, FxBuild>;

pub type Id = &'static str;

/// an Id hashed and compared by address and length instead of by contents, for memo keys: equal addresses mean equal strings, and a
/// string that arrives under a different address merely misses the memo and is recomputed (never a wrong hit)
#[derive(Clone, Copy, Debug)]
pub struct PId(pub Id);
impl PartialEq for PId { #[inline] fn eq(&self, o: &PId) -> bool { self.0.as_ptr() == o.0.as_ptr() && self.0.len() == o.0.len() } }
impl Eq for PId {}
impl std::hash::Hash for PId { #[inline] fn hash<H: Hasher>(&self, h: &mut H) { h.write_usize(self.0.as_ptr() as usize); h.write_usize(self.0.len()); } }

static INTERN: OnceLock<Mutex<HashSet<&'static str, FxBuild>>> = OnceLock::new();
thread_local! { static IDTL: std::cell::RefCell<HashSet<&'static str, FxBuild>> = std::cell::RefCell::new(HashSet::default()); }
/// Interned string (lives for the program; compare with == on &str). Each thread keeps its own copy of the strings it has seen, so
/// the shared table and its lock are touched only for a string new to the thread: with many threads in one process the lock was the
/// bottleneck (champ-battle-v19; one 90-thread process ran six times slower per game than 30 processes of 3).
pub fn id(s: &str) -> Id {
    if let Some(x) = IDTL.with(|c| c.borrow().get(s).copied()) { return x; }
    let m = INTERN.get_or_init(|| Mutex::new(HashSet::default()));
    let x = { let mut g = m.lock().unwrap(); match g.get(s) { Some(x) => *x, None => { let x: &'static str = Box::leak(s.to_string().into_boxed_str()); g.insert(x); x } } };
    IDTL.with(|c| c.borrow_mut().insert(x)); x
}
thread_local! { static CBP: std::cell::RefCell<FxMap<(usize, usize, usize, usize), Id>> = std::cell::RefCell::new(FxMap::default()); }
/// "<part>.on<Event>" for a move part's callback (secondaries.0.onHit), cached by the strings' addresses: no format! on the hot path
#[inline]
pub fn cbp(part: Id, ev: &str) -> Id {
    let key = (part.as_ptr() as usize, part.len(), ev.as_ptr() as usize, ev.len());
    CBP.with(|c| { if let Some(x) = c.borrow().get(&key) { return *x; }
        let v = id(&format!("{}.on{}", part, ev)); c.borrow_mut().insert(key, v); v })
}
/// an event's callback names and properties, computed once per event name
#[derive(Debug)]
pub struct EvNames {
    pub ev: Id, pub on: Id, pub ally: Id, pub foe: Id, pub any: Id, pub source: Id, pub on_field: Id, pub on_side: Id,
    /// the same callback names with their dense indices (NO_CB when no effect defines the name), for handler discovery
    pub on_c: Cb, pub ally_c: Cb, pub foe_c: Cb, pub any_c: Cb, pub source_c: Cb,
    /// some effect defines a handler under one of the runEvent prefixes
    pub possible: bool, pub prefixed: bool, pub left_to_right: bool,
    pub start: bool, pub switch_in: bool, pub take_item: bool, pub end: bool, pub weather: bool, pub residual: bool, pub set_ability: bool,
    pub field_srs: bool, pub damaging_hit: bool,
}
thread_local! {
    static EFFC: std::cell::RefCell<FxMap<(usize, u8, usize, usize), &'static EffData>> = std::cell::RefCell::new(FxMap::default());
    static MVC: std::cell::RefCell<FxMap<(usize, usize, usize), &'static MoveData>> = std::cell::RefCell::new(FxMap::default());
    static EVN: std::cell::RefCell<FxMap<(usize, usize), &'static EvNames>> = std::cell::RefCell::new(FxMap::default());
    static EVP: std::cell::RefCell<FxMap<(usize, usize), bool>> = std::cell::RefCell::new(FxMap::default());
    static CBN: std::cell::RefCell<FxMap<(usize, usize, usize), Id>> = std::cell::RefCell::new(FxMap::default());
}
/// interned prefix + event name ("onFoe" + "RedirectTarget"), cached by the strings' addresses so hot paths skip format! and the intern lock
#[inline]
pub fn cbn(prefix: &'static str, ev: &str) -> Id {
    let key = (prefix.as_ptr() as usize, ev.as_ptr() as usize, ev.len());
    CBN.with(|c| { if let Some(x) = c.borrow().get(&key) { return *x; }
        let v = id(&format!("{}{}", prefix, ev)); c.borrow_mut().insert(key, v); v })
}
/// a callback name with its dense index into every effect's `slots` table (NO_CB: no effect defines it, so discovery can stop at once)
#[derive(Clone, Copy, Debug)]
pub struct Cb { pub name: Id, pub i: u16, pub switch_in: bool }
pub const NO_CB: u16 = u16::MAX;
thread_local! { static CBI: std::cell::RefCell<FxMap<(usize, usize, usize, usize), Cb>> = std::cell::RefCell::new(FxMap::default()); }
/// cbn() plus the index lookup, cached by the strings' addresses
#[inline]
pub fn cbi(dex: &Dex, prefix: &'static str, ev: &str) -> Cb {
    let key = (dex as *const Dex as usize, prefix.as_ptr() as usize, ev.as_ptr() as usize, ev.len());
    CBI.with(|c| { if let Some(x) = c.borrow().get(&key) { return *x; }
        let v = dex.cb(cbn(prefix, ev)); c.borrow_mut().insert(key, v); v })
}
pub fn to_id(s: &str) -> String { s.to_lowercase().chars().filter(|c| c.is_ascii_alphanumeric()).collect() }

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Kind { Move, Ability, Item, Cond, Species }
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EType { Move, Ability, Item, Condition, Status, Weather, Terrain, Pokemon }

/// constant (non-function) handler value, e.g. Shell Armor's onCriticalHit: false
#[derive(Clone, Debug, PartialEq)]
pub enum CVal { Bool(bool), Num(f64), Str(Id) }

#[derive(Clone, Debug, Default)]
pub struct CbInfo { pub absent: bool, pub cval: Option<CVal>, pub order: Option<f64>, pub priority: f64, pub sub_order: f64, pub f: Option<crate::battle::HFn> }

#[derive(Clone, Debug)]
pub struct EffData {
    pub id: Id, pub name: Id, pub etype: EType, pub cbs: FxMap<Id, CbInfo>, pub fns: Vec<Id>, pub duration: Option<i64>, pub raw: Value,
    /// the callbacks again, indexed: `slots[cb index]` is the position in `cbl` or NO_CB (built by Dex::index_callbacks); `cbmask`
    /// has bit i set when callback index i is defined (256 bits: the full Showdown data has 162 callback names)
    pub slots: Box<[u16]>, pub cbl: Vec<(Id, CbInfo)>, pub cbmask: [u64; 4],
    /// flags read on hot paths, precomputed from `raw`
    pub breakable: bool, pub notransform: bool, pub cantsuppress: bool, pub ignore_klutz: bool, pub suppress_weather: bool,
}
impl EffData {
    pub fn cb(&self, name: &str) -> Option<&CbInfo> { self.cbs.get(name) }
    /// the callback at a dense index (same contents as `cbs.get(name)`)
    #[inline] pub fn cbi(&self, i: u16) -> Option<&CbInfo> {
        if !self.has(i) { return None; }
        match self.slots.get(i as usize) { Some(&p) if p != NO_CB => Some(&self.cbl[p as usize].1), _ => None }
    }
    /// does this effect define the callback with index i? (one bit test)
    #[inline] pub fn has(&self, i: u16) -> bool { i < 256 && (self.cbmask[(i >> 6) as usize] >> (i & 63)) & 1 == 1 }
    pub fn has_fn(&self, name: &str) -> bool { self.fns.iter().any(|f| *f == name) }
    pub fn flag(&self, f: &str) -> bool { self.raw.get("flags").and_then(|x| x.get(f)).map(|v| !v.is_null() && v != &Value::Bool(false) && v != &Value::from(0)).unwrap_or(false) }
    pub fn s(&self, k: &str) -> Option<Id> { self.raw.get(k).and_then(|v| v.as_str()).map(id) }
    pub fn b(&self, k: &str) -> bool { self.raw.get(k).map(truthy_json).unwrap_or(false) }
    pub fn n(&self, k: &str) -> Option<f64> { self.raw.get(k).and_then(|v| v.as_f64()) }
}
pub fn truthy_json(v: &Value) -> bool {
    match v { Value::Null => false, Value::Bool(b) => *b, Value::Number(n) => n.as_f64().map(|x| x != 0.0).unwrap_or(false), Value::String(s) => !s.is_empty(), _ => true }
}

pub const BOOST_NAMES: [&str; 7] = ["atk", "def", "spa", "spd", "spe", "accuracy", "evasion"];
pub fn boost_idx(s: &str) -> usize { BOOST_NAMES.iter().position(|x| *x == s).unwrap_or_else(|| panic!("boost {}", s)) }
/// boost table in insertion order (order matters for messages and AfterEachBoost)
pub type Boosts = Vec<(u8, i64)>;
pub fn parse_boosts(v: &Value) -> Option<Boosts> {
    v.as_object().map(|o| o.iter().map(|(k, x)| (boost_idx(k) as u8, x.as_i64().unwrap_or(0))).collect())
}

/// a "moveData"-like hit effect: the move's own effects, one of its secondaries, or its self effect
#[derive(Clone, Debug, Default, PartialEq)]
pub struct HitEff {
    pub part: Id,                 // "" (the move), "secondaries.N", "self", "selfBoost"
    pub chance: Option<i64>,
    pub boosts: Option<Boosts>,
    pub status: Option<Id>, pub volatile_status: Option<Id>, pub side_condition: Option<Id>, pub slot_condition: Option<Id>,
    pub pseudo_weather: Option<Id>, pub weather: Option<Id>, pub terrain: Option<Id>,
    pub heal: Option<(i64, i64)>, pub force_switch: bool, pub self_switch: Option<Id>, pub selfdestruct: Option<Id>,
    pub self_eff: Option<Box<HitEff>>, pub on_hit: bool, pub ability: Option<Id>,
}
fn opt_id(v: &Value, k: &str) -> Option<Id> { v.get(k).and_then(|x| x.as_str()).map(|s| id(&to_id(s))) }   // e.g. weather: "RainDance" -> raindance
fn pair(v: &Value, k: &str) -> Option<(i64, i64)> { v.get(k).and_then(|x| x.as_array()).map(|a| (a[0].as_i64().unwrap(), a[1].as_i64().unwrap())) }
pub fn parse_hiteff(v: &Value, part: &str) -> HitEff {
    HitEff {
        part: id(part), chance: v.get("chance").and_then(|x| x.as_i64()), boosts: v.get("boosts").and_then(parse_boosts),
        status: opt_id(v, "status"), volatile_status: opt_id(v, "volatileStatus"), side_condition: opt_id(v, "sideCondition"), slot_condition: opt_id(v, "slotCondition"),
        pseudo_weather: opt_id(v, "pseudoWeather"), weather: opt_id(v, "weather"), terrain: opt_id(v, "terrain"), heal: pair(v, "heal"),
        force_switch: v.get("forceSwitch").map(truthy_json).unwrap_or(false),
        self_switch: v.get("selfSwitch").and_then(|x| if x.as_bool() == Some(true) { Some(id("true")) } else { x.as_str().map(id) }),
        selfdestruct: opt_id(v, "selfdestruct"),
        self_eff: v.get("self").filter(|x| x.is_object()).map(|x| Box::new(parse_hiteff(x, &format!("{}{}self", part, if part.is_empty() { "" } else { "." })))),
        on_hit: v.get("onHit").map(|x| x == "__fn").unwrap_or(false), ability: opt_id(v, "ability"),
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum IgnImm { All(bool), Types(Vec<Id>) }

#[derive(Clone, Debug, Default)]
pub struct HitData { pub crit: bool, pub type_mod: i64, pub bypass_protect: bool }

/// Showdown's ActiveMove: a mutable copy of the move for one use
#[derive(Clone, Debug)]
pub struct ActiveMove {
    pub id: Id, pub name: Id, pub num: i64, pub mtype: Id, pub category: Id, pub base_power: f64, pub accuracy: Option<f64>,
    pub priority: f64, pub target: Id, pub flags: Vec<Id>, pub pp: i64,
    pub base: HitEff, pub secondaries: Option<Vec<HitEff>>, pub self_boost: Option<HitEff>,
    pub drain: Option<(i64, i64)>, pub recoil: Option<(i64, i64)>, pub crit_ratio: i64, pub will_crit: Option<bool>,
    pub multihit: Option<(i64, i64)>, pub multihit_type: Option<Id>, pub ignore_immunity: Option<IgnImm>,
    pub ignore_ability: bool, pub ignore_accuracy: bool, pub ignore_evasion: bool, pub ignore_defensive: bool, pub ignore_offensive: bool,
    pub ignore_negative_offensive: bool, pub ignore_positive_defensive: bool, pub breaks_protect: bool, pub stalling_move: bool,
    pub smart_target: Option<bool>, pub tracks_target: bool, pub sleep_usable: bool, pub has_sheer_force: bool, pub has_crash_damage: bool,
    pub struggle_recoil: bool, pub mind_blown_recoil: bool, pub override_offensive_stat: Option<Id>, pub override_defensive_stat: Option<Id>,
    pub override_offensive_pokemon: Option<Id>, pub override_defensive_pokemon: Option<Id>, pub ohko: Option<Id>, pub always_hit: bool,
    pub infiltrates: bool, pub force_stab: bool, pub multiaccuracy: bool, pub fixed_damage: Option<f64>, pub level_damage: bool,
    pub is_z: bool, pub is_max: bool, pub crit_modifier: Option<f64>, pub thaws_target: bool,
    // per-use state
    pub hit: i64, pub total_damage: i64, pub spread_hit: bool, pub last_hit: bool, pub has_bounced: bool, pub prankster_boosted: bool,
    pub self_dropped: bool, pub source_effect: Option<Id>, pub is_external: bool, pub type_changer_boosted: Option<Id>,
    pub hit_data: Vec<(Id, HitData)>, pub hit_targets: Vec<(u8, u8)>, pub misc: Vec<(Id, f64)>, pub stab_override: Option<f64>,
}
impl ActiveMove {
    pub fn flag(&self, f: &str) -> bool { self.flags.iter().any(|x| *x == f) }
    pub fn hd(&mut self, slot: Id) -> &mut HitData {
        if let Some(i) = self.hit_data.iter().position(|(s, _)| *s == slot) { return &mut self.hit_data[i].1; }
        self.hit_data.push((slot, HitData::default())); &mut self.hit_data.last_mut().unwrap().1
    }
    pub fn misc(&self, k: &str) -> Option<f64> { self.misc.iter().find(|(x, _)| *x == k).map(|(_, v)| *v) }
    pub fn set_misc(&mut self, k: &str, v: f64) { if let Some(e) = self.misc.iter_mut().find(|(x, _)| *x == k) { e.1 = v; } else { self.misc.push((id(k), v)); } }
}

#[derive(Clone, Debug)]
pub struct MoveData { pub eff: EffData, pub tmpl: ActiveMove }

fn parse_move(v: &Value) -> ActiveMove {
    let b = |k: &str| v.get(k).map(truthy_json).unwrap_or(false);
    let s = |k: &str| opt_id(v, k);
    let secondaries = v.get("secondaries").and_then(|x| x.as_array()).map(|a| a.iter().enumerate().map(|(i, x)| parse_hiteff(x, &format!("secondaries.{}", i))).collect());
    ActiveMove {
        id: id(v["id"].as_str().unwrap()), name: id(v["name"].as_str().unwrap()), num: v["num"].as_i64().unwrap_or(0),
        mtype: id(v["type"].as_str().unwrap()), category: id(v["category"].as_str().unwrap_or("Physical")),
        base_power: v["basePower"].as_f64().unwrap_or(0.0), accuracy: v["accuracy"].as_f64(),
        priority: v["priority"].as_f64().unwrap_or(0.0), target: id(v["target"].as_str().unwrap_or("normal")),
        flags: v["flags"].as_object().map(|o| o.iter().filter(|(_, x)| truthy_json(x)).map(|(k, _)| id(k)).collect()).unwrap_or_default(),
        pp: v["pp"].as_i64().unwrap_or(0),
        base: parse_hiteff(v, ""), secondaries, self_boost: v.get("selfBoost").filter(|x| x.is_object()).map(|x| parse_hiteff(x, "selfBoost")),
        drain: pair(v, "drain"), recoil: pair(v, "recoil"), crit_ratio: v["critRatio"].as_i64().unwrap_or(1),
        will_crit: v.get("willCrit").and_then(|x| x.as_bool()),
        multihit: v.get("multihit").and_then(|x| if let Some(n) = x.as_i64() { Some((n, n)) } else { x.as_array().map(|a| (a[0].as_i64().unwrap(), a[1].as_i64().unwrap())) }),
        multihit_type: s("multihitType"),
        ignore_immunity: v.get("ignoreImmunity").and_then(|x| if let Some(bb) = x.as_bool() { Some(IgnImm::All(bb)) } else { x.as_object().map(|o| IgnImm::Types(o.keys().map(|k| id(k)).collect())) }),
        ignore_ability: b("ignoreAbility"), ignore_accuracy: b("ignoreAccuracy"), ignore_evasion: b("ignoreEvasion"), ignore_defensive: b("ignoreDefensive"),
        ignore_offensive: b("ignoreOffensive"), ignore_negative_offensive: b("ignoreNegativeOffensive"), ignore_positive_defensive: b("ignorePositiveDefensive"),
        breaks_protect: b("breaksProtect"), stalling_move: b("stallingMove"), smart_target: v.get("smartTarget").and_then(|x| x.as_bool()),
        tracks_target: b("tracksTarget"), sleep_usable: b("sleepUsable"), has_sheer_force: b("hasSheerForce"), has_crash_damage: b("hasCrashDamage"),
        struggle_recoil: b("struggleRecoil"), mind_blown_recoil: b("mindBlownRecoil"), override_offensive_stat: s("overrideOffensiveStat"),
        override_defensive_stat: s("overrideDefensiveStat"), override_offensive_pokemon: s("overrideOffensivePokemon"), override_defensive_pokemon: s("overrideDefensivePokemon"),
        ohko: v.get("ohko").and_then(|x| if x.as_bool() == Some(true) { Some(id("true")) } else { x.as_str().map(id) }), always_hit: b("alwaysHit"),
        infiltrates: b("infiltrates"), force_stab: b("forceSTAB"), multiaccuracy: b("multiaccuracy"),
        fixed_damage: v.get("damage").and_then(|x| x.as_f64()), level_damage: v.get("damage").and_then(|x| x.as_str()) == Some("level"),
        is_z: b("isZ"), is_max: b("isMax"), crit_modifier: v.get("critModifier").and_then(|x| x.as_f64()), thaws_target: b("thawsTarget"),
        hit: 0, total_damage: 0, spread_hit: false, last_hit: false, has_bounced: false, prankster_boosted: false, self_dropped: false,
        source_effect: None, is_external: false, type_changer_boosted: None, hit_data: vec![], hit_targets: vec![], misc: vec![], stab_override: None,
    }
}

#[derive(Clone, Debug)]
pub struct SpeciesData {
    pub id: Id, pub name: Id, pub num: i64, pub base_species: Id, pub base_name: Id, pub types: Vec<Id>, pub stats: [i64; 6], pub abilities: Vec<(Id, Id)>,
    pub weighthg: i64, pub is_mega: bool, pub required_item: Option<Id>, pub other_formes: Vec<Id>,
}

pub struct Dex {
    pub moves: FxMap<Id, MoveData>, pub items: FxMap<Id, EffData>, pub abilities: FxMap<Id, EffData>, pub conds: FxMap<Id, EffData>,
    pub species: FxMap<Id, SpeciesData>, pub species_by_name: FxMap<Id, Id>,
    /// defending type -> attacking type -> 0 neutral / 1 weak / 2 resist / 3 immune
    pub types: FxMap<Id, FxMap<Id, i64>>, pub natures: FxMap<Id, (Option<Id>, Option<Id>)>,
    pub empty: EffData,
    /// every callback name defined by any effect (most prefixed variants like onAllyModifyAtk exist nowhere, so lookups can stop early)
    pub cb_names: std::collections::HashSet<Id, FxBuild>,
    /// dense index of every callback name in cb_names; the indices of the names handler discovery needs by itself
    pub cb_index: FxMap<Id, u16>, pub i_on_start: u16, pub i_on_any_switch_in: u16, pub on_start: Id,
}

fn etype(s: &str) -> EType {
    match s { "Move" => EType::Move, "Ability" => EType::Ability, "Item" => EType::Item, "Status" => EType::Status, "Weather" => EType::Weather,
              "Terrain" => EType::Terrain, "Pokemon" => EType::Pokemon, _ => EType::Condition }
}
fn parse_cbs(v: &Value) -> FxMap<Id, CbInfo> {
    let mut m = FxMap::default();
    if let Some(o) = v.as_object() { for (k, e) in o {
        let cval = e.get("val").map(|x| match x { Value::Bool(b) => CVal::Bool(*b), Value::Number(n) => CVal::Num(n.as_f64().unwrap()), Value::String(s) => CVal::Str(id(s)), _ => CVal::Bool(true) });
        m.insert(id(k), CbInfo { absent: e.get("absent").is_some(), cval, order: e.get("order").and_then(|x| x.as_f64()),
                                 priority: e.get("priority").and_then(|x| x.as_f64()).unwrap_or(0.0), sub_order: e.get("subOrder").and_then(|x| x.as_f64()).unwrap_or(0.0), f: None });
    } }
    m
}
fn parse_eff(v: &Value, default_type: EType) -> EffData {
    EffData {
        id: id(v["id"].as_str().unwrap_or("")), name: id(v.get("name").and_then(|x| x.as_str()).unwrap_or(v["id"].as_str().unwrap_or(""))),
        etype: v.get("effectType").and_then(|x| x.as_str()).map(etype).unwrap_or(default_type), cbs: parse_cbs(&v["cbs"]),
        fns: v.get("fns").and_then(|x| x.as_array()).map(|a| a.iter().map(|x| id(x.as_str().unwrap())).collect()).unwrap_or_default(),
        duration: v.get("duration").and_then(|x| x.as_i64()), raw: v.clone(),
        slots: Box::new([]), cbl: vec![], cbmask: [0; 4],
        breakable: flag_of(v, "breakable"), notransform: flag_of(v, "notransform"), cantsuppress: flag_of(v, "cantsuppress"),
        ignore_klutz: v.get("ignoreKlutz").map(truthy_json).unwrap_or(false), suppress_weather: v.get("suppressWeather").map(truthy_json).unwrap_or(false),
    }
}
fn flag_of(v: &Value, f: &str) -> bool { v.get("flags").and_then(|x| x.get(f)).map(|x| !x.is_null() && x != &Value::Bool(false) && x != &Value::from(0)).unwrap_or(false) }

impl Dex {
    pub fn load(path: &str) -> Dex {
        let v: Value = serde_json::from_str(&std::fs::read_to_string(path).expect("engine data")).expect("parse engine data");
        let mut moves = FxMap::default();
        for (k, m) in v["moves"].as_object().unwrap() { moves.insert(id(k), MoveData { eff: parse_eff(m, EType::Move), tmpl: parse_move(m) }); }
        let items: FxMap<Id, EffData> = v["items"].as_object().unwrap().iter().map(|(k, x)| (id(k), parse_eff(x, EType::Item))).collect();
        let abilities: FxMap<Id, EffData> = v["abilities"].as_object().unwrap().iter().map(|(k, x)| (id(k), parse_eff(x, EType::Ability))).collect();
        let conds: FxMap<Id, EffData> = v["conditions"].as_object().unwrap().iter().map(|(k, x)| (id(k), parse_eff(x, EType::Condition))).collect();
        let mut species = FxMap::default(); let mut species_by_name = FxMap::default();
        for (k, s) in v["species"].as_object().unwrap() {
            let st = &s["stats"];
            let sd = SpeciesData {
                id: id(k), name: id(s["name"].as_str().unwrap()), num: s["num"].as_i64().unwrap_or(0), base_species: id(s["baseSpeciesId"].as_str().unwrap()),
                base_name: id(s["base"].as_str().unwrap_or("")),
                types: s["types"].as_array().unwrap().iter().map(|x| id(x.as_str().unwrap())).collect(),
                stats: [st["hp"].as_i64().unwrap(), st["atk"].as_i64().unwrap(), st["def"].as_i64().unwrap(), st["spa"].as_i64().unwrap(), st["spd"].as_i64().unwrap(), st["spe"].as_i64().unwrap()],
                abilities: s["abilities"].as_object().unwrap().iter().map(|(a, b)| (id(a), id(&to_id(b.as_str().unwrap())))).collect(),
                weighthg: s["weighthg"].as_i64().unwrap_or(1), is_mega: s["isMega"].as_bool().unwrap_or(false),
                required_item: s.get("requiredItem").and_then(|x| x.as_str()).map(|x| id(&to_id(x))),
                other_formes: s.get("otherFormes").and_then(|x| x.as_array()).map(|a| a.iter().map(|x| id(&to_id(x.as_str().unwrap()))).collect()).unwrap_or_default(),
            };
            species_by_name.insert(sd.name, sd.id); species.insert(sd.id, sd);
        }
        let types = v["types"].as_object().unwrap().iter().map(|(t, m)| (id(t), m.as_object().unwrap().iter().map(|(a, x)| (id(a), x.as_i64().unwrap_or(0))).collect())).collect();
        let natures = v["natures"].as_object().unwrap().iter().map(|(n, x)| (id(n), (x["plus"].as_str().map(id), x["minus"].as_str().map(id)))).collect();
        let empty = EffData { id: "", name: "", etype: EType::Condition, cbs: FxMap::default(), fns: vec![], duration: None, raw: Value::Null,
                              slots: Box::new([]), cbl: vec![], cbmask: [0; 4], breakable: false, notransform: false, cantsuppress: false, ignore_klutz: false, suppress_weather: false };
        let mut cb_names = std::collections::HashSet::default();
        for m in moves.values() { for k in m.eff.cbs.keys() { cb_names.insert(*k); } }
        for e in items.values().chain(abilities.values()).chain(conds.values()) { for k in e.cbs.keys() { cb_names.insert(*k); } }
        cb_names.insert(id("onStart"));
        let mut names: Vec<Id> = cb_names.iter().copied().collect(); names.sort();
        assert!(names.len() < 256, "too many callback names for the 256-bit callback mask");
        let cb_index: FxMap<Id, u16> = names.iter().enumerate().map(|(i, n)| (*n, i as u16)).collect();
        let (i_on_start, i_on_any_switch_in) = (cb_index[&id("onStart")], cb_index.get(&id("onAnySwitchIn")).copied().unwrap_or(NO_CB));
        let mut d = Dex { moves, items, abilities, conds, species, species_by_name, types, natures, empty, cb_names, cb_index, i_on_start, i_on_any_switch_in, on_start: id("onStart") };
        d.index_callbacks(); d
    }
    /// (re)build every effect's indexed callback table from its `cbs` map
    fn index_callbacks(&mut self) {
        let n = self.cb_index.len(); let idx = &self.cb_index;
        let build = |e: &mut EffData| {
            let mut slots = vec![NO_CB; n]; let mut cbl: Vec<(Id, CbInfo)> = e.cbs.iter().map(|(k, c)| (*k, c.clone())).collect();
            cbl.sort_by_key(|(k, _)| idx[k]);
            let mut mask = [0u64; 4];
            for (p, (k, _)) in cbl.iter().enumerate() { let i = idx[k]; slots[i as usize] = p as u16; mask[(i >> 6) as usize] |= 1u64 << (i & 63); }
            e.slots = slots.into_boxed_slice(); e.cbl = cbl; e.cbmask = mask;
        };
        for m in self.moves.values_mut() { build(&mut m.eff); }
        for e in self.items.values_mut().chain(self.abilities.values_mut()).chain(self.conds.values_mut()) { build(e); }
    }
    /// a callback name with its dense index
    pub fn cb(&self, name: Id) -> Cb { Cb { name, i: self.cb_index.get(name).copied().unwrap_or(NO_CB), switch_in: name == "onSwitchIn" } }
    /// attach the Rust handler ports to the callbacks they implement, so dispatch needs no registry lookup
    pub fn attach(&mut self, reg: &FxMap<(Kind, Id, Id), crate::battle::HFn>) {
        for (k, m) in self.moves.iter_mut() { for (cb, c) in m.eff.cbs.iter_mut() { c.f = reg.get(&(Kind::Move, *k, *cb)).copied(); } }
        for (kind, map) in [(Kind::Item, &mut self.items), (Kind::Ability, &mut self.abilities), (Kind::Cond, &mut self.conds)] {
            for (k, e) in map.iter_mut() { for (cb, c) in e.cbs.iter_mut() { c.f = reg.get(&(kind, *k, *cb)).copied(); } }
        }
        self.index_callbacks();
    }
    pub fn evn(&self, ev: &str) -> &'static EvNames {
        let key = (ev.as_ptr() as usize, ev.len());
        if let Some(x) = EVN.with(|c| c.borrow().get(&key).copied()) { return x; }
        let on = id(&format!("on{}", ev));
        let (ally, foe, any, source) = (id(&format!("onAlly{}", ev)), id(&format!("onFoe{}", ev)), id(&format!("onAny{}", ev)), id(&format!("onSource{}", ev)));
        let n: &'static EvNames = Box::leak(Box::new(EvNames {
            ev: id(ev), on, ally, foe, any, source,
            on_field: id(&format!("onField{}", ev)), on_side: id(&format!("onSide{}", ev)),
            on_c: self.cb(on), ally_c: self.cb(ally), foe_c: self.cb(foe), any_c: self.cb(any), source_c: self.cb(source),
            possible: ["on", "onAlly", "onFoe", "onAny", "onSource"].iter().any(|p| self.cb_names.contains(format!("{}{}", p, ev).as_str())),
            prefixed: !["BeforeTurn", "Update", "Weather", "WeatherChange", "TerrainChange"].contains(&ev),
            left_to_right: ["Invulnerability", "TryHit", "DamagingHit", "EntryHazard"].contains(&ev),
            start: ev == "Start", switch_in: ev == "SwitchIn", take_item: ev == "TakeItem", end: ev == "End", weather: ev == "Weather", residual: ev == "Residual",
            set_ability: ev == "SetAbility", field_srs: ev == "FieldStart" || ev == "FieldResidual" || ev == "FieldEnd", damaging_hit: ev == "DamagingHit",
        }));
        EVN.with(|c| c.borrow_mut().insert(key, n)); n
    }
    /// can any effect handle event `ev` under any prefix? (cached by the event string's address)
    pub fn event_possible(&self, ev: &str) -> bool {
        let key = (ev.as_ptr() as usize, ev.len());
        EVP.with(|c| { if let Some(x) = c.borrow().get(&key) { return *x; }
            let v = ["on", "onAlly", "onFoe", "onAny", "onSource"].iter().any(|p| self.cb_names.contains(format!("{}{}", p, ev).as_str()));
            c.borrow_mut().insert(key, v); v })
    }
    pub fn mv(&'static self, m: Id) -> &'static MoveData {
        let key = (self as *const Dex as usize, m.as_ptr() as usize, m.len());
        if let Some(x) = MVC.with(|c| c.borrow().get(&key).copied()) { return x; }
        let r = self.moves.get(m).unwrap_or_else(|| panic!("move {}", m));
        MVC.with(|c| c.borrow_mut().insert(key, r)); r
    }
    pub fn active_move(&self, m: &str) -> ActiveMove { self.moves.get(m).unwrap_or_else(|| panic!("move {}", m)).tmpl.clone() }
    /// effect data by kind and id. Ids are interned (or literals), so the result is cached per thread by the string's address and
    /// length (a &'static str never changes), which skips hashing and comparing the bytes on the hot discovery path.
    pub fn eff(&'static self, kind: Kind, i: Id) -> &'static EffData {
        let key = (self as *const Dex as usize, kind as u8, i.as_ptr() as usize, i.len());
        if let Some(x) = EFFC.with(|c| c.borrow().get(&key).copied()) { return x; }
        let r = self.eff_slow(kind, i);
        EFFC.with(|c| c.borrow_mut().insert(key, r)); r
    }
    pub fn eff_slow(&self, kind: Kind, i: &str) -> &EffData {
        let r = match kind { Kind::Move => self.moves.get(i).map(|m| &m.eff), Kind::Ability => self.abilities.get(i), Kind::Item => self.items.get(i),
                             Kind::Cond => self.conds.get(i), Kind::Species => None };
        r.unwrap_or(&self.empty)
    }
    /// dex.getImmunity(type or status, target types): false if any of the target's types is immune
    pub fn immune_type(&self, source: &str, types: &[Id]) -> bool {
        types.iter().any(|t| self.types.get(t).and_then(|m| m.get(source)).copied() == Some(3))
    }
    /// dex.getEffectiveness(type, defending type): +1 / -1 / 0
    pub fn effectiveness(&self, atk: &str, def: &str) -> i64 {
        match self.types.get(def).and_then(|m| m.get(atk)).copied().unwrap_or(0) { 1 => 1, 2 => -1, _ => 0 }
    }
}
