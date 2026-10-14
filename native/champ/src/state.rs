//! Battle state: pokemon, sides, field, effect states. Loaded from / exported to the JSON form of native/gen_turn_cases.js (exportState).
use crate::dex::*;
use crate::prng::Prng;
use serde_json::{json, Map, Value};

/// a pokemon: (side, index in side.pokemon)
pub type MonRef = (u8, u8);

/// a value stored in an effect state (effectState.foo)
#[derive(Clone, Debug, PartialEq)]
pub enum SV { Null, B(bool), N(f64), S(Id), M(MonRef), E(EType, Id), L(Vec<MonRef>) }
impl SV {
    pub fn truthy(&self) -> bool { match self { SV::Null => false, SV::B(b) => *b, SV::N(n) => *n != 0.0 && !n.is_nan(), SV::S(s) => !s.is_empty(), _ => true } }
    pub fn num(&self) -> Option<f64> { if let SV::N(n) = self { Some(*n) } else { None } }
    pub fn mon(&self) -> Option<MonRef> { if let SV::M(m) = self { Some(*m) } else { None } }
    pub fn s(&self) -> Option<Id> { if let SV::S(s) = self { Some(s) } else { None } }
}

#[derive(Clone, Debug, Default)]
pub struct EState {
    pub id: Id, pub effect_order: i64, pub duration: Option<i64>, pub source: Option<MonRef>, pub source_slot: Option<Id>,
    pub source_effect: Option<(EType, Id)>, pub is_slot_condition: bool, pub misc: Vec<(Id, SV)>,
}
impl EState {
    pub fn new(i: Id) -> EState { EState { id: i, ..Default::default() } }
    pub fn get(&self, k: &str) -> Option<&SV> { self.misc.iter().find(|(x, _)| *x == k).map(|(_, v)| v) }
    pub fn n(&self, k: &str) -> Option<f64> { self.get(k).and_then(|v| v.num()) }
    pub fn has(&self, k: &str) -> bool { self.get(k).map(|v| v.truthy()).unwrap_or(false) }
    pub fn set(&mut self, k: &str, v: SV) { if let Some(e) = self.misc.iter_mut().find(|(x, _)| *x == k) { e.1 = v; } else { self.misc.push((id(k), v)); } }
    pub fn del(&mut self, k: &str) { self.misc.retain(|(x, _)| *x != k); }
}

#[derive(Clone, Debug)]
pub struct MoveSlot { pub id: Id, pub pp: i64, pub maxpp: i64, pub disabled: bool, pub disabled_hidden: bool, pub disabled_source: Id, pub used: bool }

#[derive(Clone, Debug)]
pub struct Attack { pub source: MonRef, pub damage: i64, pub mv: Id, pub this_turn: bool, pub slot: Id }

/// tri-state result (moveThisTurnResult): undefined / null / bool
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Tri { Undef, Null, B(bool) }

#[derive(Clone, Debug)]
pub struct Pokemon {
    pub side: u8, pub species: Id, pub base_species: Id, pub set_species: Id, pub set_item: Id, pub nature: Id, pub evs: [i64; 6], pub set_ability: Id, pub level: i64,
    pub types: Vec<Id>, pub added_type: Id, pub stored: [i64; 6], pub base_stored: [i64; 6], pub hp: i64, pub maxhp: i64, pub base_maxhp: i64,
    pub boosts: [i64; 7], pub status: Id, pub status_state: EState, pub volatiles: Vec<(Id, EState)>,
    pub ability: Id, pub base_ability: Id, pub ability_state: EState, pub item: Id, pub item_state: EState, pub last_item: Id,
    pub used_item_this_turn: bool, pub ate_berry: bool, pub item_knocked_off: bool,
    pub move_slots: Vec<MoveSlot>, pub base_move_slots: Vec<MoveSlot>, pub position: u8, pub is_active: bool, pub fainted: bool, pub faint_queued: bool,
    pub active_turns: i64, pub active_move_actions: i64, pub weighthg: i64, pub speed: f64,
    pub last_move: Option<Id>, pub last_move_target_loc: Option<i64>, pub last_move_used: Option<Id>, pub move_this_turn: Id,
    pub move_this_turn_result: Tri, pub move_last_turn_result: Tri, pub last_damage: i64, pub hurt_this_turn: Option<i64>, pub times_attacked: i64,
    pub attacked_by: Vec<Attack>, pub stats_raised_this_turn: bool, pub stats_lowered_this_turn: bool, pub switch_flag: Option<Id>, pub force_switch_flag: bool,
    pub newly_switched: bool, pub syrup_triggered: bool, pub being_called_back: bool, pub can_mega_evo: Option<Id>, pub transformed: bool,
    pub trapped: bool, pub maybe_trapped: bool, pub maybe_disabled: bool, pub maybe_locked: bool, pub skip_before_switch_out: bool,
    /// cached effect data of the current ability / item / status (Battle::ab_data etc.): each entry is checked against the current id
    /// before use, so it can never go stale
    pub ab_d: DCache, pub it_d: DCache, pub st_d: DCache,
}

/// a refillable pointer to effect data, readable and writable through a shared reference (so lookups through &Battle can store it)
/// and safe to share between the planner's threads, which only read and clone the start position
#[derive(Default)]
pub struct DCache(std::sync::atomic::AtomicPtr<EffData>);
impl DCache {
    #[inline] pub fn get(&self) -> Option<&'static EffData> { let p = self.0.load(std::sync::atomic::Ordering::Relaxed); if p.is_null() { None } else { Some(unsafe { &*p }) } }
    #[inline] pub fn set(&self, d: &'static EffData) { self.0.store(d as *const EffData as *mut EffData, std::sync::atomic::Ordering::Relaxed); }
}
impl Clone for DCache { fn clone(&self) -> DCache { DCache(std::sync::atomic::AtomicPtr::new(self.0.load(std::sync::atomic::Ordering::Relaxed))) } }
impl std::fmt::Debug for DCache { fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result { write!(f, "DCache({})", self.get().map(|d| d.id).unwrap_or("-")) } }

#[derive(Clone, Debug)]
pub struct Side {
    pub n: u8, pub pokemon: Vec<Pokemon>, pub active: [Option<u8>; 2], pub pokemon_left: i64, pub total_fainted: i64,
    pub fainted_this_turn: Option<MonRef>, pub fainted_last_turn: Option<MonRef>,
    pub side_conditions: Vec<(Id, EState)>, pub slot_conditions: [Vec<(Id, EState)>; 2],
}

#[derive(Clone, Debug, Default)]
pub struct Field { pub weather: Id, pub weather_state: EState, pub terrain: Id, pub terrain_state: EState, pub pseudo: Vec<(Id, EState)> }

pub fn find<'a>(v: &'a [(Id, EState)], k: &str) -> Option<&'a EState> { v.iter().find(|(x, _)| *x == k).map(|(_, s)| s) }
pub fn find_mut<'a>(v: &'a mut [(Id, EState)], k: &str) -> Option<&'a mut EState> { v.iter_mut().find(|(x, _)| *x == k).map(|(_, s)| s) }

// ---------- JSON import ----------
fn sv(v: &Value) -> SV {
    match v {
        Value::Null => SV::Null, Value::Bool(b) => SV::B(*b), Value::Number(n) => SV::N(n.as_f64().unwrap()), Value::String(s) => SV::S(id(s)),
        Value::Object(o) => {
            if let Some(p) = o.get("$p") { SV::M((p[0].as_u64().unwrap() as u8, p[1].as_u64().unwrap() as u8)) }
            else if let Some(e) = o.get("$e") { SV::E(etype_of(e.as_str().unwrap()), id(o["id"].as_str().unwrap_or(""))) }
            else { SV::Null }
        }
        Value::Array(a) => SV::L(a.iter().filter_map(|x| sv(x).mon()).collect()),
    }
}
pub fn etype_of(s: &str) -> EType {
    match s { "Move" => EType::Move, "Ability" => EType::Ability, "Item" => EType::Item, "Status" => EType::Status, "Weather" => EType::Weather,
              "Terrain" => EType::Terrain, "Pokemon" => EType::Pokemon, _ => EType::Condition }
}
pub fn estate(v: &Value) -> EState {
    let mut s = EState::new(id(v.get("id").and_then(|x| x.as_str()).unwrap_or("")));
    if let Some(o) = v.as_object() { for (k, x) in o {
        match k.as_str() {
            "id" => {}
            "effectOrder" => s.effect_order = x.as_i64().unwrap_or(0),
            "duration" => s.duration = x.as_i64(),
            "source" => s.source = sv(x).mon(),
            "sourceSlot" => s.source_slot = x.as_str().map(id),
            "sourceEffect" => if let SV::E(t, i) = sv(x) { s.source_effect = Some((t, i)); },
            "isSlotCondition" => s.is_slot_condition = x.as_bool().unwrap_or(false),
            _ => s.misc.push((id(k), sv(x))),
        }
    } }
    s
}
fn states(v: &Value) -> Vec<(Id, EState)> { v.as_object().map(|o| o.iter().map(|(k, x)| (id(k), estate(x))).collect()).unwrap_or_default() }
fn tri(v: &Value) -> Tri { match v { Value::Bool(b) => Tri::B(*b), Value::Null => Tri::Null, _ => Tri::Undef } }
const ST: [&str; 6] = ["hp", "atk", "def", "spa", "spd", "spe"];

fn mon(v: &Value, side: u8) -> Pokemon {
    let s = |k: &str| id(v[k].as_str().unwrap_or(""));
    let stats = |x: &Value| -> [i64; 6] { std::array::from_fn(|i| x.get(ST[i]).and_then(|y| y.as_i64()).unwrap_or(0)) };
    let set = &v["set"];
    let parse = |a: &Value| -> Vec<MoveSlot> { a.as_array().unwrap().iter().map(|m| MoveSlot {
        id: id(m["id"].as_str().unwrap()), pp: m["pp"].as_i64().unwrap(), maxpp: m["maxpp"].as_i64().unwrap(),
        disabled: truthy_json(&m["disabled"]), disabled_hidden: m["disabled"].as_str() == Some("hidden"), disabled_source: "", used: m["used"].as_bool().unwrap_or(false) }).collect() };
    let slots = parse(&v["moveSlots"]);
    // a transformed Pokemon's own moves (export_state.js exports them since 2026-10-12; older states: the current ones)
    let base_slots = if v["baseMoveSlots"].is_array() { parse(&v["baseMoveSlots"]) } else { slots.clone() };
    Pokemon {
        ab_d: DCache::default(), it_d: DCache::default(), st_d: DCache::default(),
        side, species: s("species"), base_species: s("baseSpecies"), set_species: id(&to_id(set["species"].as_str().unwrap())), set_item: id(&to_id(set["item"].as_str().unwrap_or(""))), nature: id(&to_id(set["nature"].as_str().unwrap_or(""))),
        evs: stats(&set["evs"]), set_ability: id(&to_id(set["ability"].as_str().unwrap_or(""))), level: v["level"].as_i64().unwrap_or(50),
        types: v["types"].as_array().unwrap().iter().map(|x| id(x.as_str().unwrap())).collect(), added_type: s("addedType"),
        stored: stats(&v["storedStats"]), base_stored: stats(&v["baseStoredStats"]), hp: v["hp"].as_i64().unwrap(), maxhp: v["maxhp"].as_i64().unwrap(),
        base_maxhp: v["baseMaxhp"].as_i64().unwrap(), boosts: std::array::from_fn(|i| v["boosts"][BOOST_NAMES[i]].as_i64().unwrap_or(0)),
        status: s("status"), status_state: estate(&v["statusState"]), volatiles: states(&v["volatiles"]),
        ability: s("ability"), base_ability: s("baseAbility"), ability_state: estate(&v["abilityState"]), item: s("item"), item_state: estate(&v["itemState"]),
        last_item: s("lastItem"), used_item_this_turn: v["usedItemThisTurn"].as_bool().unwrap_or(false), ate_berry: v["ateBerry"].as_bool().unwrap_or(false),
        item_knocked_off: v["itemKnockedOff"].as_bool().unwrap_or(false), base_move_slots: base_slots, move_slots: slots,
        position: v["position"].as_u64().unwrap() as u8, is_active: v["isActive"].as_bool().unwrap(), fainted: v["fainted"].as_bool().unwrap(),
        faint_queued: v["faintQueued"].as_bool().unwrap_or(false), active_turns: v["activeTurns"].as_i64().unwrap_or(0),
        active_move_actions: v["activeMoveActions"].as_i64().unwrap_or(0), weighthg: v["weighthg"].as_i64().unwrap_or(1), speed: v["speed"].as_f64().unwrap_or(0.0),
        last_move: v["lastMove"].as_str().filter(|x| !x.is_empty()).map(id), last_move_target_loc: v["lastMoveTargetLoc"].as_i64(), last_move_used: None,
        move_this_turn: s("moveThisTurn"), move_this_turn_result: tri(&v["moveThisTurnResult"]), move_last_turn_result: tri(&v["moveLastTurnResult"]),
        last_damage: v["lastDamage"].as_i64().unwrap_or(0), hurt_this_turn: v["hurtThisTurn"].as_i64(), times_attacked: v["timesAttacked"].as_i64().unwrap_or(0),
        attacked_by: v["attackedBy"].as_array().map(|a| a.iter().map(|x| Attack { source: sv(&x["source"]).mon().unwrap_or((0, 0)), damage: x["damage"].as_i64().unwrap_or(0),
            mv: id(x["move"].as_str().unwrap_or("")), this_turn: x["thisTurn"].as_bool().unwrap_or(false), slot: id(x["slot"].as_str().unwrap_or("")) }).collect()).unwrap_or_default(),
        stats_raised_this_turn: v["statsRaisedThisTurn"].as_bool().unwrap_or(false), stats_lowered_this_turn: v["statsLoweredThisTurn"].as_bool().unwrap_or(false),
        switch_flag: match &v["switchFlag"] { Value::String(x) => Some(id(x)), Value::Bool(true) => Some(id("true")), _ => None },
        force_switch_flag: v["forceSwitchFlag"].as_bool().unwrap_or(false), newly_switched: v["newlySwitched"].as_bool().unwrap_or(false), syrup_triggered: v["syrupTriggered"].as_bool().unwrap_or(false),
        being_called_back: v["beingCalledBack"].as_bool().unwrap_or(false), can_mega_evo: v["canMegaEvo"].as_str().map(|x| id(&to_id(x))),
        transformed: v["transformed"].as_bool().unwrap_or(false), trapped: truthy_json(&v["trapped"]), maybe_trapped: v["maybeTrapped"].as_bool().unwrap_or(false),
        maybe_disabled: v["maybeDisabled"].as_bool().unwrap_or(false), maybe_locked: v["maybeLocked"].as_bool().unwrap_or(false), skip_before_switch_out: false,
    }
}

pub struct Loaded { pub turn: i64, pub effect_order: i64, pub prng: Option<Prng>, pub field: Field, pub sides: [Side; 2] }
pub fn load_state(v: &Value) -> Loaded {
    let f = &v["field"];
    let field = Field { weather: id(f["weather"].as_str().unwrap_or("")), weather_state: estate(&f["weatherState"]), terrain: id(f["terrain"].as_str().unwrap_or("")),
                        terrain_state: estate(&f["terrainState"]), pseudo: states(&f["pseudoWeather"]) };
    let side = |i: usize| -> Side {
        let s = &v["sides"][i];
        let sc = s["slotConditions"].as_array().unwrap();
        Side { n: i as u8, pokemon: s["pokemon"].as_array().unwrap().iter().map(|p| mon(p, i as u8)).collect(),
               active: [s["active"][0].as_u64().map(|x| x as u8), s["active"][1].as_u64().map(|x| x as u8)],
               pokemon_left: s["pokemonLeft"].as_i64().unwrap(), total_fainted: s["totalFainted"].as_i64().unwrap(),
               fainted_this_turn: sv(&s["faintedThisTurn"]).mon(), fainted_last_turn: sv(&s["faintedLastTurn"]).mon(),
               side_conditions: states(&s["sideConditions"]), slot_conditions: [states(&sc[0]), states(&sc[1])] }
    };
    let prng = v["prng"].as_array().map(|a| Prng::gen5(std::array::from_fn(|i| a[i].as_u64().unwrap() as u16)));
    Loaded { turn: v["turn"].as_i64().unwrap(), effect_order: v["effectOrder"].as_i64().unwrap_or(0), prng, field, sides: [side(0), side(1)] }
}

// ---------- comparable export (the fields the differential test checks) ----------
fn sv_json(v: &SV) -> Value {
    match v { SV::Null => Value::Null, SV::B(b) => json!(b), SV::N(n) => json!(n), SV::S(s) => json!(s), SV::M(m) => json!({"$p": [m.0, m.1]}),
              SV::E(_, i) => json!({"$e": i}), SV::L(l) => json!(l.iter().map(|m| json!([m.0, m.1])).collect::<Vec<_>>()) }
}
pub fn estate_json(s: &EState) -> Value {
    let mut o = Map::new();
    if let Some(d) = s.duration { o.insert("duration".into(), json!(d)); }
    for (k, x) in &s.misc { o.insert(k.to_string(), sv_json(x)); }
    Value::Object(o)
}
