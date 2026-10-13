//! Champions data exported from Showdown's Champions mod (native/export_data.js).
use serde::Deserialize;
use serde_json::Value;
// the calc data maps use the engine's Fx hasher (2026-10-13): race_damage looks species and moves up before its memo, and SipHash was
// about a tenth of a game with the learned value; only lookups, never iterated in an order that matters (games identical)
type HashMap<K, V> = std::collections::HashMap<K, V, crate::dex::FxBuild>;

#[derive(Deserialize, Clone, Debug)]
pub struct Stats { pub hp: i64, pub atk: i64, pub def: i64, pub spa: i64, pub spd: i64, pub spe: i64 }
impl Stats {
    pub fn get(&self, s: &str) -> i64 { match s { "hp" => self.hp, "atk" => self.atk, "def" => self.def, "spa" => self.spa, "spd" => self.spd, _ => self.spe } }
}

#[derive(Deserialize, Clone, Debug)]
pub struct Species {
    pub name: String,
    pub base: String,
    pub types: Vec<String>,
    pub stats: Stats,
    pub abilities: HashMap<String, String>,
    pub weightkg: f64,
    #[serde(rename = "isMega")] pub is_mega: bool,
}

#[derive(Deserialize, Clone, Debug, Default)]
pub struct Move {
    pub id: String,
    #[serde(rename = "type")] pub mtype: String,
    pub category: String,
    #[serde(rename = "basePower", default)] pub base_power: i64,
    #[serde(default)] pub priority: i64,
    #[serde(default)] pub target: String,
    #[serde(default)] pub flags: HashMap<String, i64>,
    #[serde(default)] pub secondary: Option<Value>,
    #[serde(default)] pub secondaries: Option<Value>,
    #[serde(default)] pub recoil: Option<Value>,
    #[serde(rename = "hasCrashDamage", default)] pub has_crash: bool,
    #[serde(rename = "overrideOffensiveStat", default)] pub override_off: Option<String>,
    #[serde(rename = "overrideDefensiveStat", default)] pub override_def: Option<String>,
    #[serde(rename = "ignoreDefensive", default)] pub ignore_defensive: bool,
    #[serde(default)] pub multihit: Option<Value>,
}

#[derive(Deserialize, Clone, Debug, Default)]
pub struct Effect { #[serde(default)] pub prio: HashMap<String, f64> }

#[derive(Deserialize)]
pub struct Data {
    pub species: HashMap<String, Species>,
    pub moves: HashMap<String, Move>,
    pub items: HashMap<String, Effect>,
    pub abilities: HashMap<String, Effect>,
    pub natures: HashMap<String, Nature>,
    /// type -> {attacking type -> 0 neutral, 1 weak, 2 resist, 3 immune}
    pub types: HashMap<String, HashMap<String, i64>>,
}

#[derive(Deserialize, Clone, Debug)]
pub struct Nature { pub plus: Option<String>, pub minus: Option<String> }

impl Data {
    pub fn load(path: &str) -> Data { serde_json::from_str(&std::fs::read_to_string(path).expect("data file")).expect("parse data") }
    pub fn nature(&self, n: &str) -> Nature { self.natures.get(&n.to_lowercase()).cloned().unwrap_or(Nature { plus: None, minus: None }) }
    /// type effectiveness exponent of one attacking type on one defending type: Some(+1/-1/0), None = immune
    pub fn eff1(&self, atk: &str, def: &str) -> Option<i64> {
        match self.types.get(def).and_then(|t| t.get(atk)).copied().unwrap_or(0) { 1 => Some(1), 2 => Some(-1), 3 => None, _ => Some(0) }
    }
    pub fn prio(&self, kind: &str, id: &str, hook: &str) -> f64 {
        let key = format!("{}Priority", hook);
        let e = match kind { "item" => self.items.get(id), _ => self.abilities.get(id) };
        e.and_then(|e| e.prio.get(&key)).copied().unwrap_or(0.0)
    }
}
