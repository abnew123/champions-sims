//! Native port of pssim/endgame2.js: the 2v2 planner. Each turn both sides play the equilibrium mix of a one-turn matrix game
//! (every joint action, each cell played out by the engine and scored by the position value), then the real turn is sampled.
//! Starting positions and all seeds come from native/eg_starts.js, so a game can be compared move for move with the JS planner.
//!   champ plan <engine_data.json> <starts.jsonl> <out.jsonl> [threads]
//! env: EG_VALUE (value weights json, else the hand-set score), EG_AUTOPILOT, GRID_DIR (default ../../mxtr), EG_GAMES_LOG
use crate::battle::*;
use crate::dex::*;
use crate::prng::{Mode, Prng};
use crate::sim::PChoice;
use crate::state::*;
use serde_json::{json, Value};
use std::collections::BTreeMap;

const MAXTURN: usize = 15;
const FOE_TARGETS: [&str; 3] = ["normal", "any", "adjacentFoe"];
const CHOOSABLE: [&str; 5] = ["normal", "any", "adjacentAlly", "adjacentAllyOrSelf", "adjacentFoe"];

pub struct Cfg {
    /// matchup grid cells ("foe|mine" -> value), with and without Trick Room
    pub grid_tr: FxMap<String, f64>, pub grid_notr: FxMap<String, f64>, pub gfoes: Vec<String>,
    pub vw: Option<(f64, Vec<f64>)>, pub autopilot: bool,
    /// EG_VALUE_B (champ-battle-v12): value weights side 1 plans with (head-to-head tests of two values); None = the same as side 0
    pub vw_b: Option<(f64, Vec<f64>)>,
    /// RACE=1 + CALC_DATA=<champions_data.json>: the damage-race features (race_feats) are appended to the position features
    pub cdata: Option<&'static crate::data::Data>,
    /// EG_VNET=<json> (2026-10-12, the learned value; pssim/value_fit.py export): both sides' positions are scored by the net instead of
    /// EG_VALUE. Needs RACE=1 RACE_PRIO=1 FEATS22=1 CALC_DATA (the inputs it was fitted on).
    pub vnet: Option<VNet>,
}
/// a learned value: sigmoid(h(e) - h(e_swapped)), h linear or one tanh layer over vfeats.rs's side / field features and plan.rs feats
pub struct VNet { pub sd: Vec<f64>, pub w: Option<Vec<Vec<f64>>>, pub v: Vec<f64> }
impl VNet {
    fn h(&self, e: &[f64]) -> f64 {
        match &self.w {
            None => self.v.iter().zip(e).zip(&self.sd).map(|((v, x), s)| v * x / s).sum(),
            // only the non-zero inputs (2026-10-14, the review's speed item): a zero input adds +-0.0 to a sum that starts at +0.0, which
            // never changes it, so each row's sum is bit for bit the one over every input, without a multiply and a divide per zero
            Some(w) => {
                let n = e.len().min(self.sd.len()).min(w.first().map(|r| r.len()).unwrap_or(0));
                let nz: Vec<usize> = (0..n).filter(|&k| e[k] != 0.0).collect();
                w.iter().zip(&self.v).map(|(row, vv)| vv * nz.iter().map(|&k| row[k] * e[k] / self.sd[k]).sum::<f64>().tanh()).sum()
            }
        }
    }
    pub fn value(&self, b: &mut Battle, cfg: &Cfg) -> f64 {
        let cd = cfg.cdata.expect("EG_VNET needs RACE=1 and CALC_DATA");
        let _memo = MemoScope::open();   // speeds, hit chances, damage and weather read once for this position
        let f0 = crate::vfeats::side_feats(b, cd, 0); let f1 = crate::vfeats::side_feats(b, cd, 1);
        let g0 = crate::vfeats::field_feats(b, 0); let g1 = crate::vfeats::field_feats(b, 1);
        let mut x = feats(b, cfg); x.resize(28, 0.0);
        let e: Vec<f64> = f0.iter().chain(&f1).chain(&g0).chain(&x).copied().collect();
        let es: Vec<f64> = f1.iter().chain(&f0).chain(&g1).copied().chain(x.iter().map(|v| -v)).collect();
        let z = (self.h(&e) - self.h(&es)).clamp(-30.0, 30.0);
        1.0 / (1.0 + (-z).exp())
    }
}

pub fn load_cfg(grid_dir: &str) -> Cfg {
    let gval = |v: &Value| -> f64 {
        match v["v"].as_str().unwrap_or("") { "roll" => v["roll"].as_f64().unwrap_or(f64::NAN) / 100.0, "counter" => 1.0, "check" => 0.75, "wall" => 0.5, "guess" => 0.5, "lost" => 0.0, _ => 0.5 }
    };
    let mut grids = [FxMap::default(), FxMap::default()]; let mut gfoes: Vec<String> = vec![];
    for (gi, f) in ["gx_cells_tr_inc", "gx_cells_notr_inc"].iter().enumerate() {
        for suf in ["", "_ext"] {
            let p = format!("{}/{}{}.json", grid_dir, f, suf);
            let Ok(t) = std::fs::read_to_string(&p) else { continue };
            let v: Value = serde_json::from_str(&t).unwrap();
            for (k, c) in v.as_object().unwrap() {
                grids[gi].insert(k.clone(), gval(c));
                if gi == 0 { let foe = k.split('|').next().unwrap().to_string(); if !gfoes.contains(&foe) { gfoes.push(foe); } }
            }
        }
    }
    let load_vw = |name: &str| std::env::var(name).ok().map(|p| {
        let v: Value = serde_json::from_str(&std::fs::read_to_string(&p).expect("value file")).unwrap();
        (v["b0"].as_f64().unwrap(), v["w"].as_array().unwrap().iter().map(|x| x.as_f64().unwrap()).collect::<Vec<f64>>())
    });
    let vw = load_vw("EG_VALUE"); let vw_b = load_vw("EG_VALUE_B");
    let [grid_tr, grid_notr] = grids;
    let cdata: Option<&'static crate::data::Data> = std::env::var("RACE").ok().map(|_| {
        let p = std::env::var("CALC_DATA").expect("RACE=1 needs CALC_DATA=<champions_data.json>");
        &*Box::leak(Box::new(crate::data::Data::load(&p))) });
    let vnet = std::env::var("EG_VNET").ok().map(|p| {
        let v: Value = serde_json::from_str(&std::fs::read_to_string(&p).expect("EG_VNET file")).unwrap();
        let fl = |a: &Value| a.as_array().unwrap().iter().map(|x| x.as_f64().unwrap()).collect::<Vec<f64>>();
        VNet { sd: fl(&v["sd"]), w: if v["W"].is_null() { None } else { Some(v["W"].as_array().unwrap().iter().map(fl).collect()) }, v: fl(&v["v"]) } });
    Cfg { grid_tr, grid_notr, gfoes, vw, autopilot: std::env::var("EG_AUTOPILOT").is_ok(), vw_b, cdata, vnet }
}

/// a move's chance to hit as Showdown works it out, for the analytic features (2026-10-13, the user: a Bo1 game's Mega Raichu-Y Zap
/// Cannon; the features took the listed accuracy, so No Guard's 120-power hit counted at 50% and Hurricane / Thunder in rain at 70%):
/// always-hit moves, No Guard on either side, Thunder / Hurricane in rain (sure) and sun (50), Blizzard in snow, accuracy and evasion
/// stages (Keen Eye, Mind's Eye and Unaware ignore evasion; an Unaware target ignores accuracy), Compound Eyes, Hustle (physical),
/// Victory Star, Wide Lens, the target's Bright Powder, Sand Veil and Snow Cloak (not against Mold Breaker and its kin), Gravity. Capped
/// at 1. d None: no particular target (the target's side of it left out).
/// the move is blocked for side s by an active foe holding Imprison that knows it (planner_issues 19, 2026-10-14: lyph88's Imprison
/// Indeedee; the Trick Room potential still credited our Farigiraf, so the Imprisoned position read as a live Trick Room plan). Bench
/// Pokemon count too: Imprison stops them as soon as they come in, for as long as the Imprisoner stays.
pub(crate) fn imprisoned(b: &Battle, s: u8, mv: &str) -> bool {
    b.sides[1 - s as usize].active.iter().flatten().any(|&i| { let p = &b.sides[1 - s as usize].pokemon[i as usize];
        !p.fainted && find(&p.volatiles, "imprison").is_some() && p.move_slots.iter().any(|x| x.id == mv) })
}
/// one leaf evaluation's memo (2026-10-14, the outside review's speed item: the learned value's features recomputed speeds, hit chances,
/// mid-roll damage and the effective weather many times over the same position). VNet::value opens it for the length of one call; while
/// it is open those reads are made once. The position does not change inside an evaluation, so each read returns what the uncached call
/// would (games identical; EVAL_NOMEMO=1 turns it off for that check).
#[derive(Default)]
pub(crate) struct EvalMemo { spe: FxMap<MonRef, f64>, hit: FxMap<(MonRef, Option<MonRef>, PId), f64>, dmg: FxMap<(MonRef, MonRef, PId, bool, u8), Option<i64>>, wx: Option<Id> }
thread_local! { static MEMO: std::cell::RefCell<Option<EvalMemo>> = const { std::cell::RefCell::new(None) }; }
fn nomemo() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("EVAL_NOMEMO").is_ok()) }
pub(crate) struct MemoScope(bool);
impl MemoScope { pub(crate) fn open() -> MemoScope { if nomemo() { return MemoScope(false); } MEMO.with(|m| *m.borrow_mut() = Some(EvalMemo::default())); MemoScope(true) } }
impl Drop for MemoScope { fn drop(&mut self) { if self.0 { MEMO.with(|m| *m.borrow_mut() = None); } } }
/// a Pokemon's Speed (get_stat), once per open memo
pub(crate) fn memo_spe(b: &mut Battle, m: MonRef) -> f64 {
    if let Some(v) = MEMO.with(|c| c.borrow().as_ref().and_then(|e| e.spe.get(&m).copied())) { return v; }
    let v = b.get_stat(m, 5, false, false) as f64;
    MEMO.with(|c| if let Some(e) = c.borrow_mut().as_mut() { e.spe.insert(m, v); }); v
}
fn memo_weather(b: &Battle) -> Id {
    if let Some(w) = MEMO.with(|c| c.borrow().as_ref().and_then(|e| e.wx)) { return w; }
    let w = b.effective_weather();
    MEMO.with(|c| if let Some(e) = c.borrow_mut().as_mut() { e.wx = Some(w); }); w
}
pub(crate) fn hit_chance(b: &Battle, a: MonRef, d: Option<MonRef>, mid: Id) -> f64 {
    let k = (a, d, PId(mid));
    if let Some(v) = MEMO.with(|c| c.borrow().as_ref().and_then(|e| e.hit.get(&k).copied())) { return v; }
    let v = hit_chance_raw(b, a, d, mid);
    MEMO.with(|c| if let Some(e) = c.borrow_mut().as_mut() { e.hit.insert(k, v); }); v
}
fn hit_chance_raw(b: &Battle, a: MonRef, d: Option<MonRef>, mid: Id) -> f64 {
    let tm = &b.dex.mv(mid).tmpl;
    let Some(base) = tm.accuracy else { return 1.0 };
    let pa = b.p(a); let pd = d.map(|x| b.p(x));
    if pa.ability == "noguard" || pd.map(|x| x.ability == "noguard").unwrap_or(false) { return 1.0; }
    let wx = if pa.item == "utilityumbrella" { "" } else { memo_weather(b) };
    let mut acc = base;
    if mid == "thunder" || mid == "hurricane" {
        match wx { "raindance" | "primordialsea" => return 1.0, "sunnyday" | "desolateland" => acc = 50.0, _ => {} }
    }
    if mid == "blizzard" && (b.field.weather == "snowscape" || b.field.weather == "snow" || b.field.weather == "hail") { return 1.0; }
    let breaker = ["moldbreaker", "teravolt", "turboblaze"].contains(&pa.ability);
    let ign_eva = ["keeneye", "mindseye", "unaware"].contains(&pa.ability);
    let acc_st = if pd.map(|x| x.ability == "unaware").unwrap_or(false) { 0 } else { pa.boosts[5] };
    let eva_st = if ign_eva { 0 } else { pd.map(|x| x.boosts[6]).unwrap_or(0) };
    let st = (acc_st - eva_st).clamp(-6, 6);
    acc *= if st >= 0 { (3 + st) as f64 / 3.0 } else { 3.0 / (3 - st) as f64 };
    if pa.ability == "compoundeyes" { acc *= 1.3; }
    if pa.ability == "hustle" && tm.category == "Physical" { acc *= 0.8; }
    if pa.ability == "victorystar" { acc *= 1.1; }
    if pa.item == "widelens" { acc *= 1.1; }
    if let Some(x) = pd {
        if x.item == "brightpowder" { acc *= 0.9; }
        if !breaker && x.ability == "sandveil" && b.field.weather == "sandstorm" { acc *= 0.8; }
        if !breaker && x.ability == "snowcloak" && (b.field.weather == "snowscape" || b.field.weather == "snow" || b.field.weather == "hail") { acc *= 0.8; }
    }
    if find(&b.field.pseudo, "gravity").is_some() { acc *= 5.0 / 3.0; }
    (acc / 100.0).clamp(0.0, 1.0)
}
/// BATTLE_POLICY_n=greedy (2026-10-10, the user: an opponent who always clicks the highest damage): a joint option's expected damage this
/// turn, both slots' moves on their targets (calc damage x accuracy x hits, capped at the target's HP, as a share of its max HP;
/// spread moves on both foes); status moves, Fake Out, switches and locked turns score 0
pub fn greedy_damage(b: &Battle, cfg: &Cfg, s: u8, c: &[PChoice; 2]) -> f64 {
    let Some(cd) = cfg.cdata else { return 0.0 };
    let foes: Vec<MonRef> = active_alive(b, 1 - s).into_iter().map(|x| x.1).collect();
    let scr: u8 = screens_of(b, 1 - s).iter().fold(0u8, |m, x| m | match x.as_str() { "reflect" => 1, "lightscreen" => 2, _ => 4 });
    let mut tot = 0.0;
    for k in 0..2usize {
        let PChoice::Move(sl, t, _) = c[k] else { continue };
        let Some(pi) = b.sides[s as usize].active[k] else { continue }; let m = (s, pi); let p = b.p(m);
        if p.fainted || find(&p.volatiles, "mustrecharge").is_some() || find(&p.volatiles, "twoturnmove").is_some() { continue; }
        let Some(slot) = p.move_slots.get(sl) else { continue }; let mid = slot.id;
        if !cd.moves.contains_key(mid) || !cd.species.contains_key(p.species) { continue; }
        let tm = &b.dex.mv(mid).tmpl;
        if tm.category == "Status" { continue; }
        let spread = (tm.target == "allAdjacentFoes" || tm.target == "allAdjacent") && foes.len() == 2;
        let hits = match tm.multihit { Some((lo, hi)) if lo == hi => lo as f64, Some((_, hi)) => if p.ability == "skilllink" { hi as f64 } else { 3.1 }, None => 1.0 };
        let tgts: Vec<MonRef> = if spread { foes.clone() } else if t > 0 { b.sides[1 - s as usize].active[t as usize - 1].map(|x| (1 - s, x)).into_iter().filter(|f| !b.p(*f).fainted).collect() } else { vec![] };
        for f in tgts {
            if !cd.species.contains_key(b.p(f).species) { continue; }
            if let Some(d) = race_damage(b, cd, m, f, mid, spread, scr) { tot += (d as f64 * hit_chance(b, m, Some(f), mid) * hits).min(b.p(f).hp as f64) / b.p(f).maxhp.max(1) as f64; }
        }
    }
    tot
}
fn sp_name(b: &Battle, m: MonRef) -> Id { b.dex.species.get(b.p(m).species).map(|s| s.name).unwrap_or("") }
fn base_name(b: &Battle, m: MonRef) -> Id { b.dex.species.get(b.p(m).species).map(|s| s.base_name).unwrap_or("") }
pub(crate) fn alive(b: &Battle, s: u8) -> Vec<MonRef> { (0..b.sides[s as usize].pokemon.len() as u8).map(|i| (s, i)).filter(|m| !b.p(*m).fainted).collect() }
fn active_alive(b: &Battle, s: u8) -> Vec<(usize, MonRef)> {
    (0..2).filter_map(|i| b.sides[s as usize].active[i].map(|x| (i, (s, x)))).filter(|(_, m)| !b.p(*m).fainted).collect()
}
/// dex.getImmunity(type, types) && getEffectiveness: multiplier of a move type on a pokemon (0 = immune)
fn type_mult(b: &mut Battle, ty: &str, m: MonRef) -> f64 {
    let types = b.get_types(m);
    let mut x = 1.0;
    for t in &types { if b.dex.immune_type(ty, &[*t]) { return 0.0; } x *= 2f64.powi(b.dex.effectiveness(ty, t) as i32); }
    x
}

/// the planner's immune-target filter: does the move, as it would be used, do nothing to this foe by type? Showdown's ModifyType and
/// runImmunity for what our teams meet: Weather Ball / Terrain Pulse never count (their types move); the -ate abilities (Dragonize too)
/// turn Normal moves, Normalize turns every move Normal, Liquid Voice turns sound moves Water; the move's own ignoreImmunity (Thousand
/// Arrows) and Ring Target ignore it; Scrappy / Mind's Eye and a Foresight / Odor Sleuth mark let Normal and Fighting hit Ghosts,
/// Miracle Eye Psychic hit Darks; Ground follows isGrounded (Gravity, Smack Down, Iron Ball, Air Balloon, Magnet Rise; Levitate is an
/// ability's immunity and stays offered, as before). The outside review (2026-10-14): the data type alone dropped Scrappy Kangaskhan's
/// Fake Out into a Ghost and Pixilate Sylveon's Quick Attack into Dragapult, which land. mega_ab: the attacker's ability after this turn's
/// Mega Evolution (an id), for the Mega copy of an option (the second review: Mega Altaria's Pixilate Double-Edge into Dragapult was
/// judged with base Altaria's Natural Cure); None: its ability now.
fn immune_to(b: &mut Battle, a: MonRef, mid: Id, f: MonRef, mega_ab: Option<&str>) -> bool {
    if mid == "weatherball" || mid == "terrainpulse" { return false; }
    // the Mega's ability is suppressed as the current one would be (Neutralizing Gas, Gastro Acid: the third review pass)
    let has = |b: &Battle, ab: &str| match mega_ab { Some(x) => x == ab && !b.ignoring_ability(a), None => b.has_ability(a, ab) };
    let mv = b.dex.mv(mid).tmpl.clone();
    let no_mod = ["judgment", "multiattack", "naturalgift", "revelationdance", "technoblast"];
    let mut ty: Id = mv.mtype;
    if has(b, "normalize") && !no_mod.contains(&mid) { ty = "Normal"; }
    else if ty == "Normal" && !no_mod.contains(&mid) {
        for (ab, t) in [("pixilate", "Fairy"), ("aerilate", "Flying"), ("refrigerate", "Ice"), ("galvanize", "Electric"), ("dragonize", "Dragon")] { if has(b, ab) { ty = t; } }
    }
    if has(b, "liquidvoice") && mv.flags.contains(&"sound") { ty = "Water"; }
    match &mv.ignore_immunity { Some(IgnImm::All(true)) => return false, Some(IgnImm::Types(v)) if v.contains(&ty) => return false, _ => {} }
    if b.p(f).item == "ringtarget" && !b.ignoring_item(f) { return false; }
    if ty == "Ground" { return b.is_grounded(f, false) == Some(false); }
    let scrappy = (ty == "Normal" || ty == "Fighting") && (has(b, "scrappy") || has(b, "mindseye") || find(&b.p(f).volatiles, "foresight").is_some());
    let eye = ty == "Psychic" && find(&b.p(f).volatiles, "miracleeye").is_some();
    let types = b.get_types(f);
    types.iter().any(|t| b.dex.immune_type(ty, &[*t]) && !(scrappy && *t == "Ghost") && !(eye && *t == "Dark"))
}

// ---------------- position value ----------------
fn prim(b: &Battle, m: MonRef) -> usize {
    let (mut ph, mut sp) = (0, 0);
    for s in &b.p(m).move_slots { match b.dex.mv(s.id).tmpl.category { "Physical" => ph += 1, "Special" => sp += 1, _ => {} } }
    if ph >= sp { 0 } else { 2 }
}
fn move_type(b: &Battle, m: MonRef, mid: Id) -> Id {
    let mv = &b.dex.mv(mid).tmpl;
    if mid == "weatherball" { return match b.field.weather { "sunnyday" | "desolateland" => "Fire", "raindance" | "primordialsea" => "Water", "sandstorm" => "Rock", "snowscape" | "hail" => "Ice", _ => "Normal" }; }
    if mid == "terrainpulse" { return match b.field.terrain { "psychicterrain" => "Psychic", "grassyterrain" => "Grass", "electricterrain" => "Electric", "mistyterrain" => "Fairy", _ => "Normal" }; }
    if mv.mtype == "Normal" { match b.p(m).ability { "pixilate" => return "Fairy", "aerilate" => return "Flying", "refrigerate" => return "Ice", "galvanize" => return "Electric", _ => {} } }
    mv.mtype
}
thread_local! {
    /// (attacking type, defender's types) -> None if immune, else the clamped effectiveness exponent (speed only: same numbers as before)
    static TEFF: std::cell::RefCell<FxMap<(PId, PId, PId, PId), Option<i64>>> = std::cell::RefCell::new(FxMap::default());
    /// grid name of a foe (base species, is Mega, item) and grid cells ((Trick Room grid?, foe key, my base species) -> cell)
    static GFOE: std::cell::RefCell<FxMap<(PId, bool, PId), Option<String>>> = std::cell::RefCell::new(FxMap::default());
    static GCELL: std::cell::RefCell<FxMap<(bool, PId, bool, PId, PId), Option<f64>>> = std::cell::RefCell::new(FxMap::default());
}
fn type_edge(b: &mut Battle, att: u8, def: u8) -> f64 {
    let (a, d) = (alive(b, att), alive(b, def));
    if a.is_empty() || d.is_empty() { return 0.0; }
    // every attacker's damaging move types, once per call (the old loop redid this for every defender; the set of types is the same)
    let mut atk: Vec<Id> = Vec::with_capacity(16);
    for &am in &a {
        for k in 0..b.p(am).move_slots.len() {
            let mid = b.p(am).move_slots[k].id;
            let mv = &b.dex.mv(mid).tmpl; if mv.category == "Status" || mid == "fakeout" { continue; }
            let ty = move_type(b, am, mid); if !atk.contains(&ty) { atk.push(ty); }
        }
    }
    let mut t = 0.0;
    for &dm in &d {
        let dtypes = b.get_types(dm); let lev = b.has_ability(dm, "levitate");
        let mut best = -2i64;
        if dtypes.len() <= 3 {
            let key3 = (dtypes[0], if dtypes.len() > 1 { dtypes[1] } else { "" }, if dtypes.len() > 2 { dtypes[2] } else { "" });
            for &ty in &atk {
                if ty == "Ground" && lev { continue; }
                let e = TEFF.with(|c| {
                    let k = (PId(ty), PId(key3.0), PId(key3.1), PId(key3.2));
                    if let Some(v) = c.borrow().get(&k) { return *v; }
                    let v = if dtypes.iter().any(|t| b.dex.immune_type(ty, &[*t])) { None } else { Some(dtypes.iter().map(|t| b.dex.effectiveness(ty, t)).sum::<i64>().clamp(-2, 2)) };
                    c.borrow_mut().insert(k, v); v });
                if let Some(e) = e { best = best.max(e); }
            }
        } else {
            for &ty in &atk {
                if dtypes.iter().any(|t| b.dex.immune_type(ty, &[*t])) || (ty == "Ground" && lev) { continue; }
                let e: i64 = dtypes.iter().map(|t| b.dex.effectiveness(ty, t)).sum();
                best = best.max(e.clamp(-2, 2));
            }
        }
        t += best as f64;
    }
    t / d.len() as f64
}
fn gname(b: &Battle, cfg: &Cfg, m: MonRef) -> Option<String> {
    let base = base_name(b, m);
    let alias = match base { "Arcanine-Hisui" => Some("Arcanine-H"), "Floette-Eternal" | "Floette" => Some("M-Floette"), _ => None };
    if let Some(a) = alias { return Some(a.to_string()); }
    let has = |x: &str| cfg.gfoes.iter().any(|g| g == x);
    let mega = cfg.gfoes.iter().find(|g| **g == format!("M-{}", base) || g.starts_with(&format!("M-{} ", base)));
    if let Some(mg) = mega {
        let is_mega = b.dex.species.get(b.p(m).species).map(|s| s.is_mega).unwrap_or(false);
        let iname = b.dex.items.get(b.p(m).item).map(|e| e.name).unwrap_or("").to_lowercase();
        let stone = iname.ends_with("ite") || iname.ends_with("ite x") || iname.ends_with("ite y") || iname.ends_with("ite z");
        // an un-evolved holder reads as its base entry when the grid has one, now that the planner may keep it un-evolved; with
        // EG_MEGA_ALWAYS for its side it still reads as the Mega it will become on its first move (v23 behaviour)
        if is_mega || (stone && mega_always()[m.0 as usize]) || !has(base) { return Some(mg.clone()); }
    }
    if has(base) { Some(base.to_string()) } else { None }
}
fn grid_feats(b: &Battle, cfg: &Cfg) -> [f64; 2] {
    let tr = find(&b.field.pseudo, "trickroom").is_some();
    let g = if tr { &cfg.grid_tr } else { &cfg.grid_notr };
    if g.is_empty() { return [0.0, 0.0]; }
    // names and cells are memoised per thread (the grid is fixed for the run), so no strings are built after the first lookup
    let mine: Vec<Id> = alive(b, 0).iter().map(|m| base_name(b, *m)).collect();
    let foes: Vec<(PId, bool, PId)> = alive(b, 1).iter().filter_map(|m| {
        let key = (PId(base_name(b, *m)), b.dex.species.get(b.p(*m).species).map(|s| s.is_mega).unwrap_or(false), PId(b.p(*m).item));
        let ok = GFOE.with(|c| { if let Some(v) = c.borrow().get(&key) { return v.is_some(); }
            let v = gname(b, cfg, *m); let r = v.is_some(); c.borrow_mut().insert(key, v); r });
        if ok { Some(key) } else { None } }).collect();
    if mine.is_empty() || foes.is_empty() { return [0.0, 0.0]; }
    let cell = |f: &(PId, bool, PId), mi: Id| -> Option<f64> {
        let key = (tr, f.0, f.1, f.2, PId(mi));
        GCELL.with(|c| { if let Some(v) = c.borrow().get(&key) { return *v; }
            let fname = GFOE.with(|x| x.borrow().get(f).cloned().flatten()).unwrap_or_default();
            let v = g.get(&format!("{}|{}", fname, mi.split("-Mega").next().unwrap())).copied();
            c.borrow_mut().insert(key, v); v }) };
    let cov = foes.iter().map(|f| mine.iter().map(|mi| cell(f, mi).unwrap_or(0.0)).fold(0.0f64, f64::max)).sum::<f64>() / foes.len() as f64;
    let exp = mine.iter().map(|mi| foes.iter().map(|f| cell(f, mi).unwrap_or(0.5)).fold(1.0f64, f64::min)).sum::<f64>() / mine.len() as f64;
    [cov - 0.5, exp - 0.5]
}
pub fn feats(b: &mut Battle, cfg: &Cfg) -> Vec<f64> {
    struct S { hp: f64, n: f64, bst: f64, lock_s: f64, lock_a: f64, spe: f64 }
    let side = |b: &Battle, s: u8| -> S {
        let al = alive(b, s);
        let hp = al.iter().map(|m| b.p(*m).hp as f64 / b.p(*m).maxhp as f64).sum();
        let mut bst = 0.0; let (mut ls, mut la) = (0.0, 0.0);
        for (_, m) in active_alive(b, s) {
            let p = b.p(m);
            bst += (p.boosts[prim(b, m)].clamp(-3, 3)) as f64 + 0.3 * (p.boosts[4].clamp(-2, 2)) as f64;
            if let Some(cl) = find(&p.volatiles, "choicelock") { if let Some(mv) = cl.get("move").and_then(|v| v.s()) {
                if b.dex.moves.get(mv).map(|x| x.tmpl.category == "Status").unwrap_or(false) { ls += 1.0; } else { la += 1.0; } } }
        }
        let spe = al.iter().map(|m| b.p(*m).stored[5] as f64).sum::<f64>() / (al.len().max(1)) as f64;
        S { hp, n: al.len() as f64, bst, lock_s: ls, lock_a: la, spe }
    };
    let (a, o) = (side(b, 0), side(b, 1));
    let tr = find(&b.field.pseudo, "trickroom").and_then(|s| s.duration);
    let cnt = |b: &Battle, s: u8, v: &str| active_alive(b, s).iter().filter(|(_, m)| find(&b.p(*m).volatiles, v).is_some()).count() as f64;
    let st = |b: &Battle, s: u8, l: &[&str]| alive(b, s).iter().filter(|m| l.contains(&b.p(**m).status)).count() as f64;
    let sc = |b: &Battle, s: u8, k: &str| find(&b.sides[s as usize].side_conditions, k).map(|x| x.duration.filter(|d| *d != 0).unwrap_or(1) as f64).unwrap_or(0.0);
    let tricked = |b: &Battle, s: u8| active_alive(b, s).iter().filter(|(_, m)| b.p(*m).item.starts_with("choice") && !b.p(*m).set_item.starts_with("choice")).count() as f64;
    let g = grid_feats(b, cfg);
    let te = type_edge(b, 0, 1) - type_edge(b, 1, 0);
    let d = |f: &dyn Fn(&Battle, u8) -> f64| f(b, 0) - f(b, 1);
    let mut v = vec![a.hp - o.hp, a.n - o.n, a.bst - o.bst, tr.map(|t| t as f64 * ((o.spe - a.spe) / 15.0).tanh()).unwrap_or(0.0),
         a.lock_s - o.lock_s, a.lock_a - o.lock_a, g[0], g[1],
         d(&|b, s| cnt(b, s, "mustrecharge")), d(&|b, s| cnt(b, s, "stall")), te,
         d(&|b, s| st(b, s, &["slp", "frz"])), d(&|b, s| st(b, s, &["par"])), d(&|b, s| st(b, s, &["brn", "psn", "tox"])),
         if tr.is_some() { 0.0 } else { d(&|b, s| sc(b, s, "tailwind")) },
         d(&|b, s| sc(b, s, "reflect") + sc(b, s, "lightscreen") + sc(b, s, "auroraveil")),
         d(&|b, s| cnt(b, s, "encore")), d(&|b, s| tricked(b, s))];
    let taunt = d(&|b, s| cnt(b, s, "taunt"));
    if let Some(cd) = cfg.cdata {
        let r = race_feats(b, cd); v.extend_from_slice(&r[..2]);
        if feats21() {
            // champ-battle-v21 features (after the two race edges; a value file with 20 weights ignores them):
            // 20 priority edge (RACE_PRIO; the best priority hit each side has on the field, HP share, summed over its actives)
            // 21 Speed stages of the actives, 22 stat drops of the actives (the part of the boost feature that is negative: a drop
            // is switched off for free, so the fit can charge it less), 23 weather turns left x who benefits (per active: +1 with a
            // damaging move of the boosted type or a weather Speed / power ability, -1 with a move of the weakened type and no benefit;
            // sand: +1 Rock type or sand ability, -0.5 taking the chip; snow: +1 Ice type or snow ability), 24 Taunted actives
            let spe_st = |b: &Battle, s: u8| active_alive(b, s).iter().map(|(_, m)| b.p(*m).boosts[4].clamp(-3, 3) as f64).sum::<f64>();
            let drops = |b: &Battle, s: u8| active_alive(b, s).iter().map(|(_, m)| { let p = b.p(*m); (p.boosts[prim(b, *m)].clamp(-3, 0)) as f64 + 0.3 * (p.boosts[4].clamp(-2, 0)) as f64 }).sum::<f64>();
            let wx = b.field.weather; let wleft = if wx.is_empty() { 0.0 } else { b.field.weather_state.duration.filter(|d| *d > 0).unwrap_or(5) as f64 };
            let wben = |b: &mut Battle, s: u8| -> f64 { if wleft == 0.0 { return 0.0; } let mut t = 0.0;
                for (_, m) in active_alive(b, s) {
                    let ab = b.p(m).ability; let types = b.get_types(m);
                    let has_ty = |b: &Battle, ty: &str| b.p(m).move_slots.iter().any(|sl| { let mv = &b.dex.mv(sl.id).tmpl; mv.category != "Status" && move_type(b, m, sl.id) == ty });
                    t += match wx {
                        "raindance" | "primordialsea" => if has_ty(b, "Water") || ["swiftswim", "raindish", "drydish", "hydration"].contains(&ab) { 1.0 } else if has_ty(b, "Fire") { -1.0 } else { 0.0 },
                        "sunnyday" | "desolateland" => if has_ty(b, "Fire") || ["chlorophyll", "protosynthesis", "solarpower", "orichalcumpulse", "flowergift", "harvest", "leafguard"].contains(&ab) || b.p(m).move_slots.iter().any(|sl| sl.id == "solarbeam" || sl.id == "solarblade") { 1.0 } else if has_ty(b, "Water") { -1.0 } else { 0.0 },
                        "sandstorm" => if types.contains(&"Rock") || ["sandrush", "sandforce", "sandveil"].contains(&ab) { 1.0 } else if !(types.contains(&"Ground") || types.contains(&"Steel") || ["overcoat", "magicguard"].contains(&ab)) { -0.5 } else { 0.0 },
                        "snowscape" | "hail" => if types.contains(&"Ice") || ["slushrush", "iceface", "snowcloak", "icebody"].contains(&ab) { 1.0 } else { 0.0 },
                        _ => 0.0 };
                }
                t };
            let wb = (wben(b, 0) - wben(b, 1)) * wleft / 5.0;
            v.extend_from_slice(&[r[2], spe_st(b, 0) - spe_st(b, 1), drops(b, 0) - drops(b, 1), wb, taunt]);
            if feats22() {
                // FEATS22 (champ-battle-v21): plan potential and the bench. 25 Trick Room potential: with Trick Room down (or on its last
                // turn), a side with a living Trick Room user (not Taunted if active) gets tanh(speed edge in its favour) x the user's HP
                // share, so the slower side's unset Trick Room is worth something before it is clicked; 26 Tailwind potential: a side
                // without its own Tailwind up and a living Tailwind user gets tanh((2 x its mean Speed - the foe's) / 15) x HP share;
                // 27 bench edge (bench_edge): the best hit each side's bench has on the other's actives, HP share, side 0 minus side 1.
                let has_move = |b: &Battle, s: u8, mv: &str| -> f64 {
                    let mut best = 0.0f64;
                    for m in alive(b, s) {
                        let p = b.p(m);
                        if p.is_active && find(&p.volatiles, "taunt").is_some() { continue; }
                        if p.move_slots.iter().any(|x| x.id == mv && x.pp > 0 && !x.disabled) && !imprisoned(b, s, mv) { best = best.max(p.hp as f64 / p.maxhp.max(1) as f64); }
                    }
                    best };
                let tr_phase = tr.map(|t| t <= 1).unwrap_or(true);
                let trp = |b: &Battle, s: u8, edge: f64| if tr_phase { has_move(b, s, "trickroom") * (edge / 15.0).tanh().max(0.0) } else { 0.0 };
                let tr_pot = trp(b, 0, o.spe - a.spe) - trp(b, 1, a.spe - o.spe);
                let twp = |b: &Battle, s: u8, mine: f64, theirs: f64| if find(&b.sides[s as usize].side_conditions, "tailwind").is_some() { 0.0 } else { has_move(b, s, "tailwind") * ((2.0 * mine - theirs) / 15.0).tanh().max(0.0) };
                let tw_pot = twp(b, 0, a.spe, o.spe) - twp(b, 1, o.spe, a.spe);
                let be = bench_edge(b, cd);
                v.extend_from_slice(&[tr_pot, tw_pot, be]);
            }
        }
    }
    v
}
/// FEATS22=1 (champ-battle-v21, implies FEATS21): three more features, 28 in all
fn feats22() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("FEATS22").is_ok()) }
/// FEATS21=1 (champ-battle-v21): the five extra features above are appended to the feature vector (needs RACE=1)
fn feats21() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("FEATS21").is_ok() || std::env::var("FEATS22").is_ok()) }
/// RACE=1 (champ-battle-v6, 2026-10-04): a short damage race between the Pokemon on the field, so a one-turn search sees what the next
/// turns hold (a Protect that only delays a KO, a boost or Tailwind that wins the race). Each active Pokemon's options are its usable
/// damaging moves (Choice lock respected; Fake Out left out) with expected damage from calc.rs at the mid roll x accuracy x expected hits,
/// spread moves at 3/4 on both foes. For up to RACE_T turns everyone attacks in Speed order (Trick Room and each Tailwind only for the
/// turns they have left; paralysis already halves Speed and costs 1/8 of the damage; sleep skips turns until it wears off, freeze two),
/// each picking the option that removes the most foe HP share plus 1 per KO; then burn 1/16, poison 1/8, Leftovers +1/16.
/// Returns [KO edge, HP edge] for side 0: foe actives KO'd minus mine (a KO on race turn k counts 1/k), and the share of foe active HP
/// removed minus the share of mine. Bench Pokemon, switching, Protect and priority are left out.
const RACE_T: usize = 3;
/// race damage memo (per thread): everything calc.rs reads that can differ between calls in our battles; HP only where it matters
/// (Eruption / Water Spout for the attacker; Super Fang family / Hard Press, else full-HP Multiscale, for the target). Exact, so games
/// are identical with and without it (RACE_NOCACHE=1 turns it off for that check).
#[derive(Hash, PartialEq, Eq)]
struct DKey { mv: PId, a: (PId, PId, PId, PId), d: (PId, PId, PId, PId), ab: [i64; 5], db: [i64; 5], ast: [i64; 6], dst: [i64; 6], hp_a: (i64, i64), hp_d: (i64, i64),
              wx: PId, ter: PId, scr: u8, spread: bool, fallen: i64 }
fn nocache() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("RACE_NOCACHE").is_ok()) }
thread_local! { static DCACHE: std::cell::RefCell<FxMap<DKey, Option<i64>>> = std::cell::RefCell::new(FxMap::default()); }
fn cmon(b: &Battle, m: MonRef) -> crate::calc::Mon {
    let p = b.p(m);
    crate::calc::Mon { species: p.species.to_string(), item: p.item.to_string(), ability: p.ability.to_string(), nature: p.nature.to_string(), sp: [0; 6],
        boosts: [p.boosts[0], p.boosts[1], p.boosts[2], p.boosts[3], p.boosts[4]], hp: p.hp, maxhp: p.maxhp, status: p.status.to_string(),
        fallen: if race_prio() && p.ability == "supremeoverlord" { p.ability_state.n("fallen").unwrap_or(0.0) as i64 } else { 0 } }
}
fn screens_of(b: &Battle, s: u8) -> Vec<String> { ["reflect", "lightscreen", "auroraveil"].iter().filter(|k| find(&b.sides[s as usize].side_conditions, k).is_some()).map(|k| k.to_string()).collect() }
/// calc.rs mid-roll damage of `mid` by `a` on `d` in the current field, memoised per thread (DKey); None = immune / no damage
fn race_damage(b: &Battle, cd: &crate::data::Data, a: MonRef, d: MonRef, mid: Id, spread: bool, scr: u8) -> Option<i64> {
    let k = (a, d, PId(mid), spread, scr);
    if let Some(v) = MEMO.with(|c| c.borrow().as_ref().and_then(|e| e.dmg.get(&k).copied())) { return v; }
    let v = race_damage_raw(b, cd, a, d, mid, spread, scr);
    MEMO.with(|c| if let Some(e) = c.borrow_mut().as_mut() { e.dmg.insert(k, v); }); v
}
fn race_damage_raw(b: &Battle, cd: &crate::data::Data, a: MonRef, d: MonRef, mid: Id, spread: bool, scr: u8) -> Option<i64> {
    let (pa, pd) = (b.p(a), b.p(d));
    if !cd.species.contains_key(pa.species) || !cd.species.contains_key(pd.species) || !cd.moves.contains_key(mid) { return None; }
    // the attacker's HP matters to Eruption / Water Spout and to the pinch abilities (Blaze, Torrent, Overgrow, Swarm at 1/3 HP or less;
    // calc.rs `pinch`): without the flag a low-HP attacker could read a full-HP hit from the memo, or the reverse (2026-10-12)
    let hp_a = if mid == "eruption" || mid == "waterspout" { (pa.hp, pa.maxhp) } else { ((pa.hp * 3 <= pa.maxhp) as i64, 0) };
    let hp_d = if ["hardpress", "superfang", "ruination"].contains(&mid) { (pd.hp, pd.maxhp) } else { ((pd.hp >= pd.maxhp) as i64, 0) };
    let key = DKey { mv: PId(mid), a: (PId(pa.species), PId(pa.item), PId(pa.ability), PId(pa.status)), d: (PId(pd.species), PId(pd.item), PId(pd.ability), PId(pd.status)),
        ab: [pa.boosts[0], pa.boosts[1], pa.boosts[2], pa.boosts[3], pa.boosts[4]], db: [pd.boosts[0], pd.boosts[1], pd.boosts[2], pd.boosts[3], pd.boosts[4]],
        ast: pa.stored, dst: pd.stored, hp_a, hp_d, wx: PId(b.field.weather), ter: PId(b.field.terrain),
        scr, spread, fallen: if race_prio() && pa.ability == "supremeoverlord" { pa.ability_state.n("fallen").unwrap_or(0.0) as i64 } else { 0 } };
    DCACHE.with(|c| {
        if nocache() { c.borrow_mut().clear(); }
        if let Some(v) = c.borrow().get(&key) { return *v; }
        let f = crate::calc::Field { weather: b.field.weather.to_string(), terrain: b.field.terrain.to_string(), screens: screens_of(b, d.0), spread, helping: false };
        let v = crate::calc::damage(cd, &cmon(b, a), &cmon(b, d), mid, &f, 7, false, &pa.stored, &pd.stored);
        let mut m = c.borrow_mut(); if m.len() > 2_000_000 { m.clear(); } m.insert(key, v); v })
}
/// race_damage for vfeats.rs (the learned-value features), same memo
pub(crate) fn race_damage_pub(b: &Battle, cd: &crate::data::Data, a: MonRef, d: MonRef, mid: Id, spread: bool, scr: u8) -> Option<i64> { race_damage(b, cd, a, d, mid, spread, scr) }
/// FEATS22 bench edge: what each side has in the back against the other side's actives: for each living bench Pokemon its best damaging
/// move's mid-roll hit on each foe active as a share of that foe's HP (accuracy x expected hits), the best over bench and foes, capped at 1;
/// side 0's minus side 1's. A position where the answer is on the bench reads better than one where it is not.
fn bench_edge(b: &mut Battle, cd: &crate::data::Data) -> f64 {
    let mut out = [0.0f64; 2];
    for s in 0..2u8 {
        let foes: Vec<MonRef> = active_alive(b, 1 - s).into_iter().map(|x| x.1).collect(); if foes.is_empty() { continue; }
        let scr = ["reflect", "lightscreen", "auroraveil"].iter().enumerate().fold(0u8, |m, (k, x)| if find(&b.sides[1 - s as usize].side_conditions, x).is_some() { m | (1 << k) } else { m });
        let mut best = 0.0f64;
        for pos in crate::spot::bench(b, s) {
            let m = (s, pos);
            let slots: Vec<Id> = b.p(m).move_slots.iter().filter(|x| x.pp > 0 && !x.disabled).map(|x| x.id).collect();
            for mid in slots {
                let tm = &b.dex.mv(mid).tmpl; if tm.category == "Status" || mid == "fakeout" { continue; }
                let hits = match tm.multihit { Some((lo, hi)) if lo == hi => lo as f64, Some(_) => 3.1, None => 1.0 };
                let spread = (tm.target == "allAdjacentFoes" || tm.target == "allAdjacent") && foes.len() == 2;
                for &f in &foes {
                    if let Some(d) = race_damage(b, cd, m, f, mid, spread, scr) { best = best.max((d as f64 * hit_chance(b, m, Some(f), mid) * hits / b.p(f).maxhp.max(1) as f64).min(1.0)); }
                }
            }
        }
        out[s as usize] = best;
    }
    out[0] - out[1]
}
fn race_feats(b: &mut Battle, cd: &crate::data::Data) -> [f64; 3] {
    let act: [Vec<MonRef>; 2] = [active_alive(b, 0).into_iter().map(|x| x.1).collect(), active_alive(b, 1).into_iter().map(|x| x.1).collect()];
    if act[0].is_empty() || act[1].is_empty() { return [0.0, 0.0, 0.0]; }
    let units: Vec<MonRef> = act[0].iter().chain(act[1].iter()).copied().collect();
    let screens = |b: &Battle, s: u8| -> Vec<String> { ["reflect", "lightscreen", "auroraveil"].iter().filter(|k| find(&b.sides[s as usize].side_conditions, k).is_some()).map(|k| k.to_string()).collect() };
    // each side's screens once, as the memo's bitmask (the string list is only built on a memo miss)
    let scr_bits: [u8; 2] = std::array::from_fn(|s| screens(b, s as u8).iter().fold(0u8, |m, x| m | match x.as_str() { "reflect" => 1, "lightscreen" => 2, _ => 4 }));
    let dur = |e: Option<&EState>| e.map(|x| x.duration.unwrap_or(5)).unwrap_or(0) as usize;
    let tr_left = dur(find(&b.field.pseudo, "trickroom"));
    let tw_left = [dur(find(&b.sides[0].side_conditions, "tailwind")), dur(find(&b.sides[1].side_conditions, "tailwind"))];
    let n = units.len(); let sides: Vec<u8> = units.iter().map(|m| m.0).collect(); let side = |i: usize| sides[i];
    // RACE_PRIO (champ-battle-v21): priority moves act first in each race turn. A move with priority > 0 (Grassy Glide only in Grassy
    // Terrain) is left out against a grounded target under Psychic Terrain and against a side with Armor Tail / Dazzling / Queenly
    // Majesty on the field (it would fail); each option carries its priority, and the units act in order of their best option's
    // priority at the start of the race turn, then Speed. Without the flag the race is the old one (no priority anywhere).
    let prio_on = race_prio();
    let psy = b.field.terrain == "psychicterrain"; let grassy = b.field.terrain == "grassyterrain";
    let grounded: Vec<bool> = (0..n).map(|i| b.is_grounded(units[i], false) == Some(true)).collect();
    let blocks: [bool; 2] = std::array::from_fn(|s| (0..n).any(|i| side(i) == s as u8 && ["armortail", "dazzling", "queenlymajesty"].contains(&b.p(units[i]).ability)));
    // options: per unit, a list of expected damage to each unit index (0 for non-targets), with each option's priority
    let mut opts: Vec<Vec<Vec<f64>>> = vec![vec![]; n]; let mut oprio: Vec<Vec<i64>> = vec![vec![]; n];
    for i in 0..n {
        let m = units[i]; let s = b.p(m).side; let foes: Vec<usize> = (0..n).filter(|&j| side(j) != s).collect();
        if !cd.species.contains_key(b.p(m).species) { continue; }
        let lock = find(&b.p(m).volatiles, "choicelock").and_then(|cl| cl.get("move").and_then(|v| v.s()));
        let slots: Vec<(Id, i64, bool)> = b.p(m).move_slots.iter().map(|x| (x.id, x.pp, x.disabled)).collect();
        for (mid, pp, disabled) in slots {
            if pp <= 0 || disabled || mid == "fakeout" || lock.map(|l| l != mid).unwrap_or(false) || !cd.moves.contains_key(mid) { continue; }
            let tm = &b.dex.mv(mid).tmpl;
            if tm.category == "Status" { continue; }
            let prio = if !prio_on { 0 } else if mid == "grassyglide" { if grassy { 1 } else { 0 } } else { tm.priority as i64 };
            let prio_ok = |j: usize| prio <= 0 || (!(psy && grounded[j]) && !blocks[side(j) as usize]);
            let spread = (tm.target == "allAdjacentFoes" || tm.target == "allAdjacent") && foes.len() == 2;
            let md = crate::battle::Battle::miss_double() == Some(s);   // MISS_DOUBLE: that side's analytic accuracy too
            let acc_of = |j: usize| { let a = hit_chance(b, m, Some(units[j]), mid); if md { (2.0 * a - 1.0).max(0.0) } else { a } };
            let hits = match tm.multihit { Some((lo, hi)) if lo == hi => lo as f64, Some((_, hi)) => if b.p(m).ability == "skilllink" { hi as f64 } else { 3.1 }, None => 1.0 };
            let mut row = |tgts: &[usize]| -> Vec<f64> {
                let mut out = vec![0.0; n];
                for &j in tgts {
                    if let Some(dmg) = race_damage(b, cd, units[i], units[j], mid, spread, scr_bits[side(j) as usize]) { out[j] = dmg as f64 * acc_of(j) * hits; }
                }
                out };
            if spread { if foes.iter().all(|&j| prio_ok(j)) { let r = row(&foes); opts[i].push(r); oprio[i].push(prio); } }
            else { for &j in &foes { if prio_ok(j) { let r = row(&[j]); opts[i].push(r); oprio[i].push(prio); } } }
        }
    }
    // priority edge (feature): per side, the sum over its units of the best priority-move hit on any foe as a share of that foe's HP (capped at 1)
    let prio_edge: f64 = if !prio_on { 0.0 } else { (0..n).map(|i| {
        let best = (0..opts[i].len()).filter(|&k| oprio[i][k] > 0).map(|k| (0..n).map(|j| if b.p(units[j]).maxhp > 0 { opts[i][k][j] / b.p(units[j]).maxhp as f64 } else { 0.0 }).fold(0.0, f64::max)).fold(0.0, f64::max).min(1.0);
        if side(i) == 0 { best } else { -best } }).sum() };
    let spe: Vec<f64> = (0..n).map(|i| memo_spe(b, units[i])).collect();
    let hp0: Vec<f64> = (0..n).map(|i| b.p(units[i]).hp as f64).collect();
    let maxhp: Vec<f64> = (0..n).map(|i| b.p(units[i]).maxhp.max(1) as f64).collect();
    let status: Vec<Id> = (0..n).map(|i| b.p(units[i]).status).collect();
    let wake: Vec<usize> = (0..n).map(|i| match status[i] { "slp" => b.p(units[i]).status_state.n("time").map(|t| t.max(1.0) as usize).unwrap_or(2), "frz" => 3, _ => 1 }).collect();
    let lefties: Vec<bool> = (0..n).map(|i| b.p(units[i]).item == "leftovers").collect();
    // one race; `first` = the side that moves first when opposing Pokemon tie on Speed (0 reproduces the original order)
    let run = |first: u8| -> ([f64; 2], Vec<f64>) {
        let mut hp = hp0.clone(); let mut ko = [0.0f64; 2];
        for k in 1..=RACE_T {
            let tr_on = k <= tr_left;
            let eff_spe = |i: usize| { let s = side(i) as usize; let x = if tw_left[s] > 0 && k > tw_left[s] { spe[i] / 2.0 } else { spe[i] }; if tr_on { -x } else { x } };
            // each unit's priority this turn: that of its best option against the HP at the start of the turn (0 without RACE_PRIO)
            let pr: Vec<i64> = (0..n).map(|i| { if !prio_on || hp[i] <= 0.0 || opts[i].is_empty() { return 0; }
                let pf = if status[i] == "par" { 0.875 } else { 1.0 };
                let score = |o: &Vec<f64>| (0..n).filter(|&j| hp[j] > 0.0 && o[j] > 0.0).map(|j| (o[j] * pf).min(hp[j]) / maxhp[j] + if o[j] * pf >= hp[j] { 1.0 } else { 0.0 }).sum::<f64>();
                let kb = (0..opts[i].len()).max_by(|&x, &y| score(&opts[i][x]).partial_cmp(&score(&opts[i][y])).unwrap()).unwrap(); oprio[i][kb] }).collect();
            let mut order: Vec<usize> = (0..n).filter(|&i| hp[i] > 0.0).collect();
            order.sort_by(|&x, &y| pr[y].cmp(&pr[x]).then_with(|| eff_spe(y).partial_cmp(&eff_spe(x)).unwrap()).then_with(|| if side(x) == side(y) { std::cmp::Ordering::Equal }
                else if side(x) == first { std::cmp::Ordering::Less } else { std::cmp::Ordering::Greater }));
            for &i in &order {
                if hp[i] <= 0.0 || k < wake[i] || opts[i].is_empty() { continue; }
                let pf = if status[i] == "par" { 0.875 } else { 1.0 };
                let score = |o: &Vec<f64>| (0..n).filter(|&j| hp[j] > 0.0 && o[j] > 0.0).map(|j| (o[j] * pf).min(hp[j]) / maxhp[j] + if o[j] * pf >= hp[j] { 1.0 } else { 0.0 }).sum::<f64>();
                let best = opts[i].iter().max_by(|x, y| score(x).partial_cmp(&score(y)).unwrap()).unwrap().clone();
                for j in 0..n {
                    if hp[j] > 0.0 && best[j] > 0.0 { hp[j] -= best[j] * pf; if hp[j] <= 0.0 { ko[side(j) as usize] += 1.0 / k as f64; } }
                }
            }
            for i in 0..n {
                if hp[i] <= 0.0 { continue; }
                let chip = match status[i] { "brn" => maxhp[i] / 16.0, "psn" | "tox" => maxhp[i] / 8.0, _ => 0.0 };
                hp[i] = (hp[i] - chip + if lefties[i] { maxhp[i] / 16.0 } else { 0.0 }).min(maxhp[i]);
                if hp[i] <= 0.0 { ko[side(i) as usize] += 1.0 / k as f64; }
            }
            if (0..n).filter(|&i| side(i) == 0).all(|i| hp[i] <= 0.0) || (0..n).filter(|&i| side(i) == 1).all(|i| hp[i] <= 0.0) { break; }
        }
        (ko, hp)
    };
    let edges = |ko: &[f64; 2], hp: &Vec<f64>| -> [f64; 2] {
        let lost = |s: u8| (0..n).filter(|&i| side(i) == s).map(|i| (hp0[i] - hp[i].max(0.0)) / maxhp[i]).sum::<f64>();
        [ko[1] - ko[0], lost(1) - lost(0)] };
    let (ko, hp) = run(0); let mut out = edges(&ko, &hp);
    // RACE_TIES=avg (champ-battle-v13): a Speed tie between opposing Pokemon is a coin flip in the game, so the race is run with each
    // side winning the ties and the two results are averaged. Without it side 0 always moves first on a tie (the original behaviour).
    if race_ties_avg() && (0..n).any(|i| (0..n).any(|j| side(i) != side(j) && spe[i] == spe[j])) {
        let (ko1, hp1) = run(1); let o1 = edges(&ko1, &hp1); out = [(out[0] + o1[0]) / 2.0, (out[1] + o1[1]) / 2.0];
    }
    if std::env::var("RACE_DEBUG").is_ok() {                   // first few calls only: units, best hit % on each foe, Speed, outcome
        static CNT: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
        if CNT.fetch_add(1, std::sync::atomic::Ordering::Relaxed) < 6 {
            let mut lines = vec![format!("race: TR {} turns, Tailwind {:?}", tr_left, tw_left)];
            for i in 0..n {
                let best: Vec<String> = (0..n).filter(|&j| side(j) != side(i)).map(|j| format!("{} {:.0}%", b.p(units[j]).species,
                    100.0 * opts[i].iter().map(|o| o[j]).fold(0.0, f64::max) / maxhp[j])).collect();
                lines.push(format!("  s{} {} hp {:.0}% spe {} -> {} | end hp {:.0}% (side 0 first on ties)", side(i), b.p(units[i]).species, 100.0 * hp0[i] / maxhp[i], spe[i], best.join(", "), 100.0 * hp[i].max(0.0) / maxhp[i]));
            }
            lines.push(format!("  KO edge {:+.2}, HP edge {:+.2}, priority edge {:+.2}", out[0], out[1], prio_edge));
            eprintln!("{}", lines.join("\n"));
        }
    }
    [out[0], out[1], prio_edge]
}
/// PLAN_KEEP_IMMUNE=0|1|both: that side's options keep damaging moves aimed at an immune target (see slot_options)
fn keep_immune() -> [bool; 2] { static F: std::sync::OnceLock<[bool; 2]> = std::sync::OnceLock::new(); *F.get_or_init(|| match std::env::var("PLAN_KEEP_IMMUNE").as_deref() { Ok("0") => [true, false], Ok("1") => [false, true], Ok(_) => [true, true], Err(_) => [false, false] }) }
fn race_prio() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("RACE_PRIO").is_ok()) }
fn race_ties_avg() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("RACE_TIES").map(|v| v == "avg").unwrap_or(false)) }
fn perish_adj(b: &Battle, w: &[f64]) -> f64 {
    let al = [alive(b, 0), alive(b, 1)];
    let t = |m: &MonRef| find(&b.p(*m).volatiles, "perishsong").and_then(|s| s.duration);
    if al[0].is_empty() || al[1].is_empty() { return 0.0; }
    if al.iter().all(|l| l.iter().all(|m| t(m).is_some())) {
        let tmax: Vec<i64> = al.iter().map(|l| l.iter().map(|m| t(m).unwrap()).max().unwrap()).collect();
        if tmax[0] != tmax[1] { return if tmax[0] > tmax[1] { 3.0 } else { -3.0 }; }
        let tr_then = find(&b.field.pseudo, "trickroom").and_then(|s| s.duration).map(|d| d >= tmax[0]).unwrap_or(false);
        let mut last: Vec<(u8, i64)> = vec![];
        for k in 0..2 { for m in &al[k] { if t(m) == Some(tmax[k]) { last.push((k as u8, b.p(*m).stored[5])); } } }
        last.sort_by(|a, c| if tr_then { a.1.cmp(&c.1) } else { c.1.cmp(&a.1) });   // stable, like JS sort
        return if last.last().unwrap().0 == 0 { 3.0 } else { -3.0 };
    }
    if perish2() {
        // PERISH2=1 (champ-battle-v11): a Perish count only dooms a Pokemon that cannot leave. Per side, the counted Pokemon that are not
        // trapped take the bench slots (healthiest first) and are charged a small tempo cost; the rest (trapped by Shadow Tag / Arena Trap /
        // Magnet Pull / a trapping move, or no bench left) are charged most of their worth, more the fewer turns remain, and for trapped
        // ones scaled by how healthy the foe's trapper is (KOing or forcing out the trapper is the way out).
        let hpf = |m: &MonRef| b.p(*m).hp as f64 / b.p(*m).maxhp.max(1) as f64;
        let mut z = 0.0;
        for k in 0..2usize {
            let mut counted: Vec<(MonRef, i64)> = al[k].iter().filter_map(|m| t(m).map(|tt| (*m, tt))).collect();
            if counted.is_empty() { continue; }
            let trap_hp = active_alive(b, 1 - k as u8).iter().filter(|(_, f)| ["shadowtag", "arenatrap", "magnetpull"].contains(&b.p(*f).ability))
                .map(|(_, f)| hpf(f)).fold(f64::NAN, f64::max);
            let hold = if trap_hp.is_nan() { 1.0 } else { 0.6 + 0.4 * trap_hp };
            let mut free = crate::spot::bench(b, k as u8).len();
            counted.sort_by(|a, c| hpf(&c.0).partial_cmp(&hpf(&a.0)).unwrap());
            for (m, tt) in counted {
                let worth = w[0] * hpf(&m) + w[1];
                let f = if !b.p(m).trapped && free > 0 { free -= 1; 0.15 }
                        else { (if tt <= 1 { 0.95 } else if tt == 2 { 0.8 } else { 0.65 }) * if b.p(m).trapped { hold } else { 1.0 } };
                z += (if k == 0 { -1.0 } else { 1.0 }) * f * worth;
            }
        }
        return z;
    }
    let mut z = 0.0;
    for (k, l) in al.iter().enumerate() { for m in l { if let Some(tt) = t(m) {
        z += (if k == 0 { -1.0 } else { 1.0 }) * 0.8 * (w[0] * b.p(*m).hp as f64 / b.p(*m).maxhp as f64 + w[1]) / (tt.max(1) as f64);
    } } }
    z
}
fn perish2() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("PERISH2").is_ok()) }
fn trsym() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("TRSYM").is_ok()) }
/// who refuses to click Trick Room while it is up: side 0 only (the original rule, written for the slow Trick Room six), or with TRSYM=1
/// (champ-battle-v11) whichever side is slower on average, so a faster side 0 with a Trick Room move can reverse the opponent's
fn tr_keep(b: &Battle, s: u8) -> bool {
    if !trsym() { return s == 0; }
    let ms = |x: u8| { let a = alive(b, x); a.iter().map(|m| b.p(*m).stored[5] as f64).sum::<f64>() / a.len().max(1) as f64 };
    ms(s) < ms(1 - s)
}
/// side 0's win chance as each side sees it: (with side 0's weights, with side 1's weights); equal unless EG_VALUE_B is set
pub fn value2(b: &mut Battle, cfg: &Cfg) -> (f64, f64) {
    if let Some(n) = &cfg.vnet {
        // EG_VNET_SIDE=0|1 (head-to-heads): only that side plans with the net, the other with EG_VALUE
        if let Some(side) = vnet_side() {
            if b.ended { let v = match b.winner { Some(Some(0)) => 1.0, Some(Some(_)) => 0.0, _ => 0.5 }; return (v, v); }
            let vn = n.value(b, cfg); let vo = value_sym(b, cfg);
            return if side == 0 { (vn, vo) } else { (vo, vn) };
        }
        let v = value(b, cfg); return (v, v);
    }
    let Some((b1, w1)) = &cfg.vw_b else { let v = value(b, cfg); return (v, v); };
    if b.ended { let v = match b.winner { Some(Some(0)) => 1.0, Some(Some(_)) => 0.0, _ => 0.5 }; return (v, v); }
    let f = feats(b, cfg);
    let ev = |b0: f64, w: &Vec<f64>| { let mut z = b0; for k in 0..w.len().min(f.len()) { z += w[k] * f[k]; } z += perish_adj(b, w); 1.0 / (1.0 + (-z).exp()) };
    let va = match &cfg.vw { Some((b0, w)) => ev(*b0, w), None => ev(*b1, w1) };
    (va, ev(*b1, w1))
}
/// each side plans with its own value (EG_VALUE_B, or EG_VNET_SIDE)
pub(crate) fn two_values(cfg: &Cfg) -> bool { cfg.vw_b.is_some() || (cfg.vnet.is_some() && vnet_side().is_some()) }
fn vnet_side() -> Option<u8> { static F: std::sync::OnceLock<Option<u8>> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("EG_VNET_SIDE").ok().and_then(|x| x.parse().ok())) }
pub fn value(b: &mut Battle, cfg: &Cfg) -> f64 {
    if b.ended { return match b.winner { Some(Some(0)) => 1.0, Some(Some(_)) => 0.0, _ => 0.5 }; }
    if let Some(n) = &cfg.vnet { if vnet_side().is_none() { return n.value(b, cfg); } }
    value_sym(b, cfg)
}
/// the EG_VALUE score (the logistic value over plan.rs feats), whatever EG_VNET says
fn value_sym(b: &mut Battle, cfg: &Cfg) -> f64 {
    let f = feats(b, cfg);
    match &cfg.vw {
        Some((b0, w)) => { let mut z = *b0; for k in 0..w.len().min(f.len()) { z += w[k] * f[k]; } z += perish_adj(b, w); 1.0 / (1.0 + (-z).exp()) }
        None => { let x = f[0] + 0.3 * f[2] + 0.08 * f[3] - 0.5 * f[4] - 0.1 * f[5]; (0.5 + 0.25 * x).clamp(0.0, 1.0) }
    }
}

// ---------------- options ----------------
/// EG_NO_DOUBLE_PROTECT=0 | 1 | both (experiment, 2026-10-04): that side never clicks a Protect-family move while the stall counter from
/// last turn's successful Protect is up (no second Protect in a row). Unset: no change.
/// EG_LAST_PROTECT=0|1|both (2026-10-11, the user): that side's last Pokemon may not Protect when protecting changes nothing (see
/// pointless_protect); a Protect that only stalls is what makes a lost endgame drag on
fn last_protect_rule() -> [bool; 2] { static F: std::sync::OnceLock<[bool; 2]> = std::sync::OnceLock::new(); *F.get_or_init(|| match std::env::var("EG_LAST_PROTECT").as_deref() { Ok("0") => [true, false], Ok("1") => [false, true], Ok(_) => [true, true], Err(_) => [false, false] }) }
/// side s is down to one Pokemon (m) and a Protect this turn would change nothing: no timed field or side effect is running (weather,
/// terrain, Trick Room / Gravity / rooms, Tailwind, screens, Safeguard, Mist, Wish / Future Sight / Healing Wish slots), no Pokemon on
/// the field is asleep, frozen, charging, locked, confused, Taunted, Encored, Disabled, Throat Chopped, Heal Blocked, drowsy or under
/// Perish Song, no end-of-turn HP change (residual damage on anyone; healing for m when it is below full: Leftovers, Black Sludge, Grassy
/// Terrain, Aqua Ring, Ingrain), no foe has a fresh Fake Out, m cannot still Mega Evolve and has no Speed Boost / Moody
pub(crate) fn pointless_protect(b: &mut Battle, s: u8, m: MonRef) -> bool {
    if alive(b, s).len() != 1 { return false; }
    if !b.field.weather.is_empty() || !b.field.terrain.is_empty() || !b.field.pseudo.is_empty() { return false; }
    for sd in 0..2usize {
        if !b.sides[sd].side_conditions.is_empty() || b.sides[sd].slot_conditions.iter().any(|v| !v.is_empty()) { return false; }
    }
    const TIMED: [&str; 14] = ["yawn", "perishsong", "taunt", "encore", "disable", "throatchop", "healblock", "confusion", "twoturnmove",
        "lockedmove", "mustrecharge", "partiallytrapped", "leechseed", "saltcure"];
    let field: Vec<MonRef> = (0..2u8).flat_map(|sd| crate::plan::active_alive(b, sd).into_iter().map(|x| x.1).collect::<Vec<_>>()).collect();
    for &q in &field {
        let p = b.p(q);
        if ["slp", "frz", "brn", "psn", "tox"].contains(&p.status) { return false; }
        if TIMED.iter().any(|v| find(&p.volatiles, v).is_some()) || find(&p.volatiles, "curse").is_some() || find(&p.volatiles, "nightmare").is_some() { return false; }
        if q.0 != s && p.active_move_actions == 0 && p.move_slots.iter().any(|x| x.id == "fakeout" && x.pp > 0) { return false; }
    }
    let p = b.p(m);
    if p.can_mega_evo.is_some() || ["speedboost", "moody"].contains(&p.ability) { return false; }
    if p.hp < p.maxhp {
        let heal = p.item == "leftovers" || find(&p.volatiles, "aquaring").is_some() || find(&p.volatiles, "ingrain").is_some();
        let sludge = p.item == "blacksludge";
        if heal || (sludge && b.has_type(m, "Poison")) { return false; }
    }
    true
}
fn no_double_protect(s: u8) -> bool {
    static F: std::sync::OnceLock<[bool; 2]> = std::sync::OnceLock::new();
    F.get_or_init(|| match std::env::var("EG_NO_DOUBLE_PROTECT").as_deref() {
        Ok("0") => [true, false], Ok("1") => [false, true], Ok("both") => [true, true], _ => [false, false] })[s as usize]
}
fn selfko_rule() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("EG_SELFKO_RULE").is_ok()) }
pub(crate) fn slot_options(b: &mut Battle, s: u8, i: usize) -> Vec<PChoice> {
    let Some(pi) = b.sides[s as usize].active[i] else { return vec![PChoice::Pass] };
    let m = (s, pi);
    if b.p(m).fainted { return vec![PChoice::Pass]; }
    let req = b.request_moves(m);
    let locked = b.get_locked_move(m).is_some();
    // a locked move (a charged two-turn move, Outrage...) fires at the target Showdown stored for it (side.chooseMove: volatiles[move]
    // .targetLoc, else lastMoveTargetLoc), whatever is chosen; make_move_action does the same, so per-target options were duplicates
    // (2026-10-12, the Eval bar: Electro Shot shown as 50/50 over two targets). One option, at the stored target.
    if let Some(l) = b.get_locked_move(m) {
        let p = b.p(m); let mut tl = p.last_move_target_loc.unwrap_or(0);
        if let Some(t) = find(&p.volatiles, l).and_then(|x| x.n("targetLoc")) { if t != 0.0 { tl = t as i64; } }
        if !req.is_empty() && FOE_TARGETS.contains(&req[0].1) { return vec![PChoice::Move(0, tl, false)]; }
    }
    let mega = !locked && b.p(m).can_mega_evo.is_some();
    // the Mega's ability (an id), for judging the Mega copies of options; with and without it the immune-target filter can differ
    let mega_ab: Option<String> = if mega { b.p(m).can_mega_evo.and_then(|sp| b.dex.species.get(sp)).and_then(|x| x.abilities.iter().find(|(k, _)| *k == "0").map(|x| x.1))
        .map(|n| n.chars().filter(|c| c.is_ascii_alphanumeric()).collect::<String>().to_lowercase()) } else { None };
    let (mut mega_only, mut base_only): (Vec<(usize, i64)>, Vec<PChoice>) = (vec![], vec![]);
    let mut out = vec![];
    let foes: Vec<Option<MonRef>> = (0..2).map(|t| b.sides[1 - s as usize].active[t].map(|x| (1 - s, x))).collect();
    for (k, (mid, rtarget, disabled)) in req.iter().enumerate() {
        if *disabled { continue; }
        // Healing Wish / Memento are offered since 2026-10-09 (their self-KO and the slot condition started working then). The planner
        // clicks Healing Wish at full HP in about a fifth of its uses (320 matrix games with the Trick Room six: 65 games with a use,
        // v20 43.1% -> 46.6% with the move free); the user's read is that this is often a real line (the setter leaves for free once
        // Trick Room is up, the replacement comes in without taking a hit), and the free version also scores higher than a restricted
        // one (45.3%), so it stays free. EG_SELFKO_RULE=1 restricts it to a hurt user / hurt bench (Memento: hurt user) for comparisons.
        if (*mid == "healingwish" || *mid == "memento") && selfko_rule() {
            let p = b.p(m); let hurt = |q: &Pokemon| q.hp * 2 <= q.maxhp || !q.status.is_empty();
            let bench_hurt = b.sides[s as usize].pokemon.iter().any(|q| !q.fainted && !q.is_active && (q.hp * 5 <= q.maxhp * 3 || !q.status.is_empty()));
            if *mid == "healingwish" && !(hurt(p) || bench_hurt) { continue; }
            if *mid == "memento" && !hurt(p) { continue; }
        }
        if *mid == "fakeout" && b.p(m).active_move_actions > 0 { continue; }
        if b.p(m).item.starts_with("choice") && (*mid == "protect" || *mid == "detect") { continue; }
        if *mid == "trickroom" && find(&b.field.pseudo, "trickroom").is_some() && tr_keep(b, s) { continue; }
        let mv = b.dex.mv(mid).tmpl.clone();
        if mv.stalling_move && no_double_protect(s) && find(&b.p(m).volatiles, "stall").is_some() { continue; }
        if mv.stalling_move && last_protect_rule()[s as usize] && pointless_protect(b, s, m) { continue; }
        // the request's target class, as Showdown's chooseMove checks it: for a real move it is the move's own; for the recharge
        // pseudo-move (a stub with no target in the data, which used to read as "normal" and left a recharging Pokemon with no legal
        // option, ending the game early) it is "self"
        let target: Id = *rtarget;
        if FOE_TARGETS.contains(&target) {
            for (t, f) in foes.iter().enumerate() {
                let Some(f) = f else { continue }; if b.p(*f).fainted { continue; }
                // an immune target is dropped (the move can do nothing to it) unless PLAN_KEEP_IMMUNE names this side: a human (champ
                // play) attacks into an immune Pokemon on purpose when predicting a switch, and the move then hits the switch-in
                let check = mv.category != "Status" && !keep_immune()[s as usize];
                let im_now = check && immune_to(b, m, mid, *f, None);
                let im_mega = if mega && check { immune_to(b, m, mid, *f, mega_ab.as_deref()) } else { im_now };
                if im_now && im_mega { continue; }
                if mega && im_mega { base_only.push(PChoice::Move(k, t as i64 + 1, false)); continue; }   // it lands only without the Mega
                if mega && im_now { mega_only.push((k, t as i64 + 1)); }                                // only with it: no plain copy
                out.push(PChoice::Move(k, t as i64 + 1, mega));
            }
            // the partner as the target (planner_issues 17, the user's scope, 2026-10-13): the moves players aim at their partner over
            // 10% of the time, where they do something to it (Instruct and Beat Up wait for their ports)
            if let Some(a) = b.sides[s as usize].active[1 - i] { if !b.p((s, a)).fainted && partner_target(b, s, mid, (s, a)) { out.push(PChoice::Move(k, if i == 0 { -2 } else { -1 }, mega)); } }
        } else if target == "adjacentAlly" {
            if let Some(a) = b.sides[s as usize].active[1 - i] { if !b.p((s, a)).fainted { out.push(PChoice::Move(k, if i == 0 { -2 } else { -1 }, mega)); } }
        } else { out.push(PChoice::Move(k, 0, mega)); }
    }
    // Mega choice (the user, 2026-10-10, through TR sheet: "always mega evolving feels wrong in general"): a stone holder's moves are
    // offered with and without the Mega Evolution, so it can keep its base ability or typing (Lightning Rod Raichu, Intimidate
    // Staraptor) or leave the Mega to its partner. EG_MEGA_ALWAYS=1 restores the old rule (the first move always Mega Evolves).
    if mega && !mega_always()[s as usize] {
        let n = out.len(); for j in 0..n { if let PChoice::Move(k, t, true) = out[j] { if !mega_only.contains(&(k, t)) { out.push(PChoice::Move(k, t, false)); } } }
        out.extend(base_only);
    }
    if out.is_empty() { vec![PChoice::Move(0, 0, false)] } else { out }
}
/// a normal / any move worth aiming at the partner (planner_issues 17; PARTNER_TARGETS=0 turns it off for head-to-heads): always for the
/// moves played at the partner nearly always or whose effect suits it (Decorate, After You, Speed Swap, Heal Pulse, Soak, Skill Swap,
/// Entrainment, Roar); a stat drop into Contrary (Charm, Fake Tears, Parting Shot: Defiant and Competitive ignore an ally's drop);
/// Psych Up onto a boosted partner; Simple Beam onto a boosted partner or one held back by its ability; U-turn and Grassy Glide into
/// Weak Armor or Stamina. PARTNER_TARGETS=0 off, s0 / s1 for one side only (head-to-heads), on otherwise
fn partner_target(b: &Battle, s: u8, mid: Id, a: MonRef) -> bool {
    static ON: std::sync::OnceLock<[bool; 2]> = std::sync::OnceLock::new();
    let on = *ON.get_or_init(|| match std::env::var("PARTNER_TARGETS").as_deref() { Ok("0") => [false, false], Ok("s0") => [true, false], Ok("s1") => [false, true], _ => [true, true] });
    if !on[s as usize] { return false; }
    let p = b.p(a); let ab = p.ability; let boosted = p.boosts.iter().any(|x| *x > 0);
    match mid {
        "decorate" | "afteryou" | "speedswap" | "healpulse" | "soak" | "skillswap" | "entrainment" | "roar" => true,
        "charm" | "faketears" | "partingshot" => ab == "contrary",
        "psychup" => boosted,
        "simplebeam" => boosted || ["truant", "slowstart", "defeatist", "klutz"].contains(&ab),
        "uturn" | "grassyglide" => ab == "weakarmor" || ab == "stamina",
        _ => false,
    }
}
/// EG_MEGA_ALWAYS=1 (or both): both sides keep the old rule; =0 / =1 as a side number: only that side does (head-to-head tests)
fn mega_always() -> [bool; 2] { static F: std::sync::OnceLock<[bool; 2]> = std::sync::OnceLock::new(); *F.get_or_init(|| match std::env::var("EG_MEGA_ALWAYS").as_deref() { Ok("s0") => [true, false], Ok("s1") => [false, true], Ok(_) => [true, true], Err(_) => [false, false] }) }
/// DP2 (champ-battle-v8): the small option set for the second turn of the two-turn Protect check: the Pokemon's Protect (if it has one)
/// and its three strongest damaging options by base power x STAB x type effectiveness x accuracy (spread moves x 0.75 on each foe);
/// Mega Evolution taken whenever it is available. No switches or status moves.
pub(crate) fn reduced_options(b: &mut Battle, s: u8, i: usize) -> Vec<PChoice> { reduced_options_n(b, s, i, 3) }
pub(crate) fn reduced_options_n(b: &mut Battle, s: u8, i: usize, nhits: usize) -> Vec<PChoice> {
    let all = slot_options(b, s, i);
    let Some(pi) = b.sides[s as usize].active[i] else { return all };
    let m = (s, pi);
    if b.p(m).fainted { return all; }
    let has_mega = all.iter().any(|c| matches!(c, PChoice::Move(_, _, true)));
    let foes: Vec<Option<MonRef>> = (0..2).map(|t| b.sides[1 - s as usize].active[t].map(|x| (1 - s, x))).collect();
    let types = b.get_types(m);
    let (mut prot, mut dmg): (Option<PChoice>, Vec<(f64, PChoice)>) = (None, vec![]);
    for c in &all {
        let PChoice::Move(k, t, mega) = *c else { continue };
        if has_mega && !mega { continue; }
        let mid = b.p(m).move_slots[k].id; let mv = b.dex.mv(mid).tmpl.clone();
        if mv.stalling_move { if prot.is_none() { prot = Some(*c); } continue; }
        if mv.category == "Status" || mv.base_power <= 0.0 { continue; }
        let ty = move_type(b, m, mid); let stab = if types.contains(&ty) { 1.5 } else { 1.0 };
        let md = crate::battle::Battle::miss_double() == Some(s);
        let accs: Vec<f64> = foes.iter().map(|f| f.map(|f| { let a = hit_chance(b, m, Some(f), mid); if md { (2.0 * a - 1.0).max(0.0) } else { a } }).unwrap_or(0.0)).collect();
        let eff = if t >= 1 { match foes[(t - 1) as usize] { Some(f) if !b.p(f).fainted => type_mult(b, ty, f) * accs[(t - 1) as usize], _ => 0.0 } }
                  else { let fs: Vec<(MonRef, f64)> = foes.iter().zip(&accs).filter_map(|(f, a)| f.map(|f| (f, *a))).filter(|(f, _)| !b.p(*f).fainted).collect();
                         fs.iter().map(|(f, a)| 0.75 * type_mult(b, ty, *f) * a).sum() };
        dmg.push((mv.base_power * stab * eff, *c));
    }
    dmg.sort_by(|a, c| c.0.partial_cmp(&a.0).unwrap());
    let mut out: Vec<PChoice> = dmg.into_iter().take(nhits).map(|x| x.1).collect();
    if let Some(p) = prot { out.push(p); }
    if out.is_empty() { all } else { out }
}
fn joint_options(b: &mut Battle, s: u8) -> Vec<[PChoice; 2]> {
    let (a, c) = (slot_options(b, s, 0), slot_options(b, s, 1));
    let mut out = vec![];
    for x in &a { for y in &c {
        let y2 = match (x, y) { (PChoice::Move(_, _, true), PChoice::Move(k, t, true)) => PChoice::Move(*k, *t, false), _ => *y };
        let j = [*x, y2]; if !out.contains(&j) { out.push(j); }
    } }
    out
}
/// would Showdown's side.choose accept this? (chooseMove's checks for the parts our options can get wrong)
pub(crate) fn valid(b: &mut Battle, s: u8, ch: &[PChoice; 2]) -> bool {
    for i in 0..2 {
        let Some(pi) = b.sides[s as usize].active[i] else { continue };
        let m = (s, pi);
        match ch[i] {
            PChoice::Pass => { if !b.p(m).fainted { return false; } }
            // a voluntary switch (only spot.rs offers these): to a living Pokemon on the bench
            PChoice::Switch(pos) => { if b.p(m).fainted || b.mon_at_position(s, pos).map(|t| b.p(t).fainted || b.p(t).position < 2).unwrap_or(true) { return false; } }
            PChoice::Move(k, t, mega) => {
                if b.p(m).fainted { continue; }
                let req = b.request_moves(m);
                if k >= req.len() { return false; }
                let tt = req[k].1;
                if CHOOSABLE.contains(&tt) { if t == 0 || !b.valid_target_loc(t, m, tt) { return false; } } else if t != 0 { return false; }
                let locked = b.get_locked_move(m).is_some();
                let any_valid = b.p(m).move_slots.iter().any(|s| !(s.disabled || s.pp <= 0));
                if !locked && any_valid && b.p(m).move_slots.iter().find(|s| s.id == req[k].0).map(|s| s.disabled || s.pp <= 0).unwrap_or(true) { return false; }
                if mega && (b.p(m).can_mega_evo.is_none() || locked) { return false; }
            }
        }
    }
    true
}

// ---------------- matrix game ----------------
pub fn nash(a: &[Vec<f64>], iters: usize) -> (Vec<f64>, Vec<f64>) {
    let (m, n) = (a.len(), a[0].len());
    let (mut rr, mut rc, mut sr, mut sc) = (vec![0.0; m], vec![0.0; n], vec![0.0; m], vec![0.0; n]);
    let norm = |r: &[f64]| -> Vec<f64> { let mut p: Vec<f64> = r.iter().map(|x| x.max(0.0)).collect(); let t: f64 = { let mut t = 0.0; for x in &p { t += x; } t };
        if t <= 0.0 { p.iter_mut().for_each(|x| *x = 1.0 / r.len() as f64); } else { p.iter_mut().for_each(|x| *x /= t); } p };
    for _ in 0..iters {
        let (x, y) = (norm(&rr), norm(&rc));
        let mut ur = vec![0.0; m]; let mut uc = vec![0.0; n]; let mut v = 0.0;
        for i in 0..m { let mut s = 0.0; for j in 0..n { s += a[i][j] * y[j]; } ur[i] = s; v += x[i] * s; }
        for j in 0..n { let mut s = 0.0; for i in 0..m { s += a[i][j] * x[i]; } uc[j] = -s; }
        for i in 0..m { rr[i] = (rr[i] + ur[i] - v).max(0.0); sr[i] += x[i]; }
        for j in 0..n { rc[j] = (rc[j] + uc[j] + v).max(0.0); sc[j] += y[j]; }
    }
    let ts: f64 = sr.iter().fold(0.0, |a, b| a + b); let tc: f64 = sc.iter().fold(0.0, |a, b| a + b);
    (sr.iter().map(|v| v / ts).collect(), sc.iter().map(|v| v / tc).collect())
}
pub(crate) fn sample(p: &[f64], rng: &mut f64) -> usize {
    *rng = (*rng * 1103515245.0 + 12345.0) % 2147483648.0;
    let mut r = *rng / 2147483648.0; let mut k = 0;
    while k < p.len() - 1 { r -= p[k]; if r <= 0.0 { break; } k += 1; }
    k
}

// ---------------- autopilot (my side) ----------------
fn auto_choice(b: &mut Battle, s: u8) -> [PChoice; 2] {
    let mut parts = [PChoice::Pass; 2]; let mut mega_used = false;
    for i in 0..2 {
        let Some(pi) = b.sides[s as usize].active[i] else { continue };
        let m = (s, pi); if b.p(m).fainted { continue; }
        let locked = b.get_locked_move(m).is_some();
        let mega = !locked && b.p(m).can_mega_evo.is_some() && !mega_used; if mega { mega_used = true; }
        let moves: Vec<(usize, Id)> = b.request_moves(m).into_iter().enumerate().filter(|(_, x)| !x.2).map(|(k, x)| (k, x.0)).collect();
        let foes: Vec<(i64, MonRef)> = (0..2).filter_map(|t| b.sides[1 - s as usize].active[t].map(|x| (t as i64 + 1, (1 - s, x)))).filter(|(_, f)| !b.p(*f).fainted).collect();
        let ally = b.sides[s as usize].active[1 - i].map(|x| (s, x));
        let ally_up = ally.map(|a| !b.p(a).fainted && b.p(a).move_slots.iter().any(|sl| b.dex.mv(sl.id).tmpl.category != "Status")).unwrap_or(false);
        let has = |id_: &str| moves.iter().find(|x| x.1 == id_).map(|x| x.0);
        let eff = |b: &mut Battle, ty: &str, f: MonRef| -> f64 { if ty == "Ground" && b.has_ability(f, "levitate") { return 0.0; } type_mult(b, ty, f) };
        let tr_down = find(&b.field.pseudo, "trickroom").is_none();
        let mut c: Option<PChoice> = None;
        if tr_down && has("trickroom").is_some() { c = Some(PChoice::Move(has("trickroom").unwrap(), 0, mega)); }
        else if has("fakeout").is_some() && b.p(m).active_move_actions == 0 && { let mut any = false; for (_, f) in &foes { if eff(b, "Normal", *f) > 0.0 { any = true; } } any } {
            let mut cands: Vec<(i64, MonRef, i64)> = vec![];
            for (t, f) in &foes { if eff(b, "Normal", *f) > 0.0 {
                // getStat(stat, false, true): stages, no modifiers. EG_FAKEOUT_FULLSTAT=1 reproduces the old JS (full getStat; crashes vs Torrent/Blaze)
                let st = if std::env::var("EG_FAKEOUT_FULLSTAT").is_ok() { b.get_stat(*f, 1, false, false).max(b.get_stat(*f, 3, false, false)) }
                         else { b.get_stat_simple(*f, 1, false, true).max(b.get_stat_simple(*f, 3, false, true)) };
                cands.push((*t, *f, st)); } }
            cands.sort_by(|a, d| d.2.cmp(&a.2));   // stable
            c = Some(PChoice::Move(has("fakeout").unwrap(), cands[0].0, mega));
        } else if has("helpinghand").is_some() && ally_up { c = Some(PChoice::Move(has("helpinghand").unwrap(), if i == 0 { -2 } else { -1 }, mega)); }
        else {
            let mut best: Option<(f64, PChoice)> = None;
            let wx_tbl = |w: &str, ty: &str| -> f64 { match (w, ty) { ("sunnyday", "Fire") | ("desolateland", "Fire") | ("raindance", "Water") | ("primordialsea", "Water") => 1.5,
                ("sunnyday", "Water") | ("raindance", "Fire") => 0.5, ("desolateland", "Water") | ("primordialsea", "Fire") => 0.0, _ => 1.0 } };
            for (k, mid) in moves.clone() {
                let mv = b.dex.mv(mid).tmpl.clone();
                if mv.category == "Status" || mid == "fakeout" || mid == "suckerpunch" { continue; }
                let mut bp = if mv.base_power != 0.0 { mv.base_power } else { 60.0 };
                let ty = move_type(b, m, mid);
                let p = b.p(m); let frac = p.hp as f64 / p.maxhp as f64;
                if mid == "eruption" || mid == "waterspout" { if frac < 0.5 { continue; } bp = 150.0 * p.hp as f64 / p.maxhp as f64; }
                if mid == "weatherball" && ["sunnyday", "desolateland", "raindance", "primordialsea", "sandstorm", "snowscape", "hail"].contains(&b.field.weather) { bp = 100.0; }
                let stab = if b.get_types(m).contains(&ty) { 1.5 } else { 1.0 };
                let wx = wx_tbl(b.field.weather, ty);
                if mv.target == "allAdjacentFoes" || mv.target == "allAdjacent" {
                    let mut v = 0.0; let nf = foes.len();
                    for (_, f) in &foes { v += bp * stab * wx * eff(b, ty, *f) * (if nf > 1 { 0.75 } else { 1.0 }); }
                    if v > 0.0 && best.as_ref().map(|x| v > x.0).unwrap_or(true) { best = Some((v, PChoice::Move(k, 0, mega))); }
                } else if FOE_TARGETS.contains(&mv.target) {
                    for (t, f) in &foes {
                        let fp = b.p(*f); let hpf = fp.hp as f64 / fp.maxhp as f64;
                        let v = bp * stab * wx * eff(b, ty, *f) * (1.2 - 0.2 * hpf);
                        if v > 0.0 && best.as_ref().map(|x| v > x.0).unwrap_or(true) { best = Some((v, PChoice::Move(k, *t, mega))); }
                    }
                }
            }
            c = Some(best.map(|x| x.1).unwrap_or(PChoice::Move(moves.first().map(|x| x.0).unwrap_or(0), 0, mega)));
        }
        parts[i] = c.unwrap();
    }
    parts
}

// ---------------- games ----------------
pub struct GameOut { pub v: f64, pub turns: usize, pub auto_miss: usize, pub unsupported: Vec<String>, pub log: Vec<String> }

fn solve_turn(b: &Battle, cfg: &Cfg, cseeds: &[[u16; 4]]) -> (Vec<[PChoice; 2]>, Vec<[PChoice; 2]>, Vec<Vec<f64>>, Vec<String>) {
    let mut b0 = b.clone();
    let mine: Vec<[PChoice; 2]> = joint_options(&mut b0, 0).into_iter().filter(|c| valid(&mut b0, 0, c)).collect();
    let theirs: Vec<[PChoice; 2]> = joint_options(&mut b0, 1).into_iter().filter(|c| valid(&mut b0, 1, c)).collect();
    let mut a = vec![vec![0.0; theirs.len()]; mine.len()]; let mut uns = vec![];
    for i in 0..mine.len() { for j in 0..theirs.len() {
        let mut s = 0.0;
        for cs in cseeds {
            let mut c = b.clone(); c.prng = Prng::gen5(*cs);
            c.run_turn([mine[i], theirs[j]]);
            for u in &c.unsupported { if !uns.contains(u) { uns.push(u.clone()); } }
            s += value(&mut c, cfg);
        }
        a[i][j] = s / cseeds.len() as f64;
    } }
    (mine, theirs, a, uns)
}
pub fn play_game(start: &Battle, cfg: &Cfg, rng0: f64, cseeds: &[Vec<[u16; 4]>]) -> GameOut {
    let mut b = start.clone();
    let mut rng = rng0; let mut turn = 1; let mut auto_miss = 0; let mut uns: Vec<String> = vec![]; let mut log = vec![];
    while !b.ended && turn <= MAXTURN {
        let (r, c, m, u) = solve_turn(&b, cfg, &cseeds[turn - 1]);
        for x in u { if !uns.contains(&x) { uns.push(x); } }
        if r.is_empty() || c.is_empty() {
            // nothing the engine accepts on one side: Showdown's autoChoose for both sides (first usable move, default target)
            let auto = |b: &mut Battle, s: u8| -> [PChoice; 2] { std::array::from_fn(|i| {
                let Some(pi) = b.sides[s as usize].active[i] else { return PChoice::Pass };
                if b.p((s, pi)).fainted { return PChoice::Pass; }
                let req = b.request_moves((s, pi));
                PChoice::Move(req.iter().position(|x| !x.2).unwrap_or(0), 0, false) }) };
            let ch = [auto(&mut b, 0), auto(&mut b, 1)];
            log.push(format!("T{} (engine default choices)", turn));
            b.run_turn(ch);
            for x in &b.unsupported { if !uns.contains(x) { uns.push(x.clone()); } }
            turn += 1; continue;
        }
        let (x, y) = nash(&m, 400);
        let mut i = sample(&x, &mut rng); let j = sample(&y, &mut rng);
        if cfg.autopilot { let ac = auto_choice(&mut b, 0); match r.iter().position(|o| *o == ac) { Some(a) => i = a, None => auto_miss += 1 } }
        log.push(format!("T{} {:?} || {:?}  [{}x{}]", turn, r[i], c[j], r.len(), c.len()));
        b.run_turn([r[i], c[j]]);
        for x in &b.unsupported { if !uns.contains(x) { uns.push(x.clone()); } }
        turn += 1;
    }
    GameOut { v: value(&mut b, cfg), turns: turn - 1, auto_miss, unsupported: uns, log }
}

/// one job's games -> the JS workers' result shape ({arch, mine, theirs, w, K, games, fails, v, vs, turns, autoMiss, ms, job})
fn job_row(job: i64, mut gs: Vec<Value>) -> Value {
    gs.sort_by_key(|g| g["g"].as_i64().unwrap());
    let ok: Vec<&Value> = gs.iter().filter(|g| !g["v"].is_null()).collect();
    let vs: Vec<f64> = ok.iter().map(|g| g["v"].as_f64().unwrap()).collect();
    let mean = if vs.is_empty() { Value::Null } else { json!(vs.iter().sum::<f64>() / vs.len() as f64) };
    let mut uns: Vec<String> = gs.iter().flat_map(|g| g["unsupported"].as_array().cloned().unwrap_or_default()).filter_map(|x| x.as_str().map(|s| s.to_string())).collect();
    uns.sort(); uns.dedup();
    let mut row = json!({"job": job, "K": gs[0]["K"], "games": vs.len(), "fails": gs.len() - vs.len(), "v": mean, "vs": vs,
        "turns": ok.iter().map(|g| g["turns"].clone()).collect::<Vec<_>>(), "autoMiss": ok.iter().map(|g| g["autoMiss"].as_i64().unwrap_or(0)).sum::<i64>(),
        "unsupported": uns, "ms": gs.iter().map(|g| g["ms"].as_i64().unwrap_or(0)).sum::<i64>(), "engine": "native"});
    if let Some(m) = gs[0]["meta"].as_object() { for (k, v) in m { row[k] = v.clone(); } }
    if gs.iter().any(|g| !g["log"].is_null()) { row["logs"] = json!(gs.iter().map(|g| g["log"].clone()).collect::<Vec<_>>()); }
    let errs: Vec<Value> = gs.iter().filter_map(|g| g.get("error").cloned()).collect();
    if !errs.is_empty() { row["errors"] = json!(errs); }
    row
}
pub fn main(args: &[String]) {
    let (dex, reg) = crate::turntest::load_all(&args[0]);
    let cfg: &'static Cfg = Box::leak(Box::new(load_cfg(&std::env::var("GRID_DIR").unwrap_or("../../mxtr".into()))));
    let threads: usize = args.get(3).and_then(|x| x.parse().ok()).unwrap_or(1);
    let lines: Vec<String> = std::fs::read_to_string(&args[1]).unwrap().lines().map(|s| s.to_string()).collect();
    let next = std::sync::atomic::AtomicUsize::new(0);
    let results = std::sync::Mutex::new(vec![]);
    let outdir = std::path::Path::new(&args[2]).is_dir().then(|| args[2].clone());
    let mut expect: BTreeMap<i64, usize> = BTreeMap::new();
    for l in &lines { let v: Value = serde_json::from_str(l).unwrap(); *expect.entry(v["job"].as_i64().unwrap()).or_default() += 1; }
    let pending: std::sync::Mutex<BTreeMap<i64, Vec<Value>>> = std::sync::Mutex::new(BTreeMap::new());
    let t0 = std::time::Instant::now();
    std::thread::scope(|sc| {
        for _ in 0..threads { sc.spawn(|| loop {
            let k = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst); if k >= lines.len() { break; }
            let st: Value = serde_json::from_str(&lines[k]).unwrap();
            let b = crate::turntest::new_battle(dex, reg, &st["state"], Mode::Real);
            let cseeds: Vec<Vec<[u16; 4]>> = st["cseeds"].as_array().unwrap().iter().map(|t| t.as_array().unwrap().iter().map(|s| std::array::from_fn(|i| s[i].as_u64().unwrap() as u16)).collect()).collect();
            let tg = std::time::Instant::now();
            let r = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| play_game(&b, cfg, st["rng"].as_f64().unwrap(), &cseeds)));
            let ms = tg.elapsed().as_millis();
            let row = match r {
                Ok(g) => json!({"job": st["job"], "g": st["g"], "K": st["K"], "meta": st["meta"], "v": g.v, "turns": g.turns, "autoMiss": g.auto_miss, "unsupported": g.unsupported, "ms": ms,
                                "log": if std::env::var("EG_GAMES_LOG").is_ok() { json!(g.log) } else { Value::Null }}),
                Err(e) => { let msg = e.downcast_ref::<String>().cloned().or(e.downcast_ref::<&str>().map(|s| s.to_string())).unwrap_or_default();
                    json!({"job": st["job"], "g": st["g"], "K": st["K"], "meta": st["meta"], "v": Value::Null, "fail": true, "error": msg, "ms": ms}) }
            };
            eprintln!("job {} game {}: {} ({} ms)", st["job"], st["g"], row["v"], ms);
            if let Some(dir) = &outdir {
                let job = row["job"].as_i64().unwrap();
                let done = { let mut pd = pending.lock().unwrap(); let e = pd.entry(job).or_default(); e.push(row.clone()); (e.len() == expect[&job]).then(|| pd.remove(&job).unwrap()) };
                if let Some(gs) = done { std::fs::write(format!("{}/{}.json", dir, job), job_row(job, gs).to_string()).unwrap(); }
            }
            results.lock().unwrap().push(row);
        }); }
    });
    // one row per job: a directory gets <job>.json files (written as each job completes, see below); otherwise one JSONL file
    let rows = results.into_inner().unwrap();
    if !std::path::Path::new(&args[2]).is_dir() {
        let mut by: BTreeMap<i64, Vec<Value>> = BTreeMap::new();
        for r in rows { by.entry(r["job"].as_i64().unwrap()).or_default().push(r); }
        let out: String = by.into_iter().map(|(job, gs)| format!("{}\n", job_row(job, gs))).collect();
        std::fs::write(&args[2], out).unwrap();
    }
    eprintln!("{} games in {:?}", lines.len(), t0.elapsed());
}
