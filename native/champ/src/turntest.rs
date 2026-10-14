//! Turn differential test: load the state before a turn, play both sides' choices natively, compare with Showdown's state after the turn.
use crate::battle::*;
use crate::dex::*;
use crate::prng::{Mode, Prng};
use crate::state::*;
use crate::sim::PChoice;
use serde_json::Value;
use std::collections::BTreeMap;

/// engine data + handler registry, with the handlers attached to the data (leaked: they live for the whole run)
pub fn load_all(path: &str) -> (&'static Dex, &'static crate::handlers::Reg) {
    let reg = crate::handlers::build(); let mut dex = Dex::load(path); dex.attach(&reg);
    (Box::leak(Box::new(dex)), Box::leak(Box::new(reg)))
}
pub fn new_battle(dex: &'static Dex, reg: &'static crate::handlers::Reg, pre: &Value, mode: Mode) -> Battle {
    let l = load_state(pre);
    let prng = if mode == Mode::Real { l.prng.clone().expect("real mode needs the seed") } else { Prng::fake(mode) };
    Battle { dex, reg, prng, field: l.field, sides: l.sides, queue: vec![], turn: l.turn, effect_order: l.effect_order, ended: false, winner: None,
             faint_queue: vec![], amoves: vec![], active_move: None, active_pokemon: None, active_target: None, effect: None, effect_state: SLoc::Nil,
             event: None, event_depth: 0, temp: vec![], log: vec![], logging: std::env::var("LOG").is_ok(), mid_turn: false, request_switch: false,
             last_successful_move_this_turn: None, last_move: None, unsupported: vec![], quick_claw_roll: false, eff_type: "", nevents: 0, nfind: 0, speed_order: vec![] }
}
/// "move 2 1 mega, switch 3" -> per active slot: move (request index, target loc, mega) / switch (team position) / pass
pub fn parse_choice(s: &str) -> [PChoice; 2] {
    let mut out = [PChoice::Pass, PChoice::Pass];
    for (i, part) in s.split(',').map(|x| x.trim()).enumerate().take(2) {
        let w: Vec<&str> = part.split_whitespace().collect();
        match w.first() {
            Some(&"move") => {
                let idx = w[1].parse::<usize>().unwrap() - 1;
                let mut tloc = 0; let mut mega = false;
                for x in &w[2..] { if *x == "mega" { mega = true; } else if let Ok(n) = x.parse::<i64>() { tloc = n; } }
                out[i] = PChoice::Move(idx, tloc, mega);
            }
            Some(&"switch") => { out[i] = PChoice::Switch((w[1].parse::<u8>().unwrap() - 1) as u8); }
            _ => {}
        }
    }
    out
}
/// play the turn, answering switch requests with the switches Showdown was given (in order)
pub fn play(b: &mut Battle, ch: [[PChoice; 2]; 2], switches: &[(usize, String)]) {
    b.run_turn(ch);
    let mut k = 0; let mut guard = 0;
    while b.request_switch && !b.ended && guard < 10 {
        guard += 1;
        let req = b.switch_request();
        let mut c = [[PChoice::Pass; 2]; 2];
        for s in 0..2 { if req[s].iter().any(|x| *x) { if let Some((ss, txt)) = switches.get(k) { if *ss == s { c[s] = parse_choice(txt); k += 1; } } } }
        b.choose_switches(c);
    }
}
fn dur(v: &Value) -> Option<i64> { v.get("duration").and_then(|x| x.as_i64()) }
/// differences between the native battle and Showdown's exported post-turn state
pub fn diff(b: &Battle, post: &Value) -> Vec<String> {
    let mut d = vec![];
    let mut chk = |what: String, mine: String, theirs: String| { if mine != theirs { d.push(format!("{}: native {} vs showdown {}", what, mine, theirs)); } };
    let f = &post["field"];
    chk("weather".into(), format!("{}/{:?}", b.field.weather, b.field.weather_state.duration.filter(|_| !b.field.weather.is_empty())),
        format!("{}/{:?}", f["weather"].as_str().unwrap_or(""), dur(&f["weatherState"]).filter(|_| !f["weather"].as_str().unwrap_or("").is_empty())));
    chk("terrain".into(), format!("{}/{:?}", b.field.terrain, b.field.terrain_state.duration.filter(|_| !b.field.terrain.is_empty())),
        format!("{}/{:?}", f["terrain"].as_str().unwrap_or(""), dur(&f["terrainState"]).filter(|_| !f["terrain"].as_str().unwrap_or("").is_empty())));
    let mut pw: Vec<String> = b.field.pseudo.iter().map(|(k, s)| format!("{}:{:?}", k, s.duration)).collect(); pw.sort();
    let mut pw2: Vec<String> = f["pseudoWeather"].as_object().unwrap().iter().map(|(k, s)| format!("{}:{:?}", k, dur(s))).collect(); pw2.sort();
    chk("pseudoWeather".into(), pw.join(","), pw2.join(","));
    chk("turn".into(), b.turn.to_string(), post["turn"].to_string());
    chk("ended".into(), b.ended.to_string(), post["ended"].to_string());
    for s in 0..2 {
        let ps = &post["sides"][s]; let side = &b.sides[s];
        chk(format!("p{} pokemonLeft", s + 1), side.pokemon_left.to_string(), ps["pokemonLeft"].to_string());
        let mut sc: Vec<String> = side.side_conditions.iter().map(|(k, x)| format!("{}:{:?}", k, x.duration)).collect(); sc.sort();
        let mut sc2: Vec<String> = ps["sideConditions"].as_object().unwrap().iter().map(|(k, x)| format!("{}:{:?}", k, dur(x))).collect(); sc2.sort();
        chk(format!("p{} sideConditions", s + 1), sc.join(","), sc2.join(","));
        for (i, pp) in ps["pokemon"].as_array().unwrap().iter().enumerate() {
            // Showdown reorders side.pokemon on switches; match by species
            let sp = to_id(pp["set"]["species"].as_str().unwrap());
            let pos = pp["position"].as_u64().unwrap_or(99) as u8;
            let Some(p) = side.pokemon.iter().find(|q| q.set_species == sp && q.position == pos).or_else(|| side.pokemon.iter().find(|q| q.set_species == sp)) else { chk(format!("p{}[{}]", s + 1, i), "missing".into(), sp.clone()); continue };
            let w = format!("p{}[{}] {}", s + 1, i, p.set_species);
            chk(format!("{} position", w), p.position.to_string(), pp["position"].to_string());
            chk(format!("{} active", w), p.is_active.to_string(), pp["isActive"].to_string());
            chk(format!("{} species", w), p.species.to_string(), pp["species"].as_str().unwrap().to_string());
            chk(format!("{} hp", w), p.hp.to_string(), pp["hp"].to_string());
            chk(format!("{} status", w), p.status.to_string(), pp["status"].as_str().unwrap().to_string());
            let ss = &pp["statusState"];
            for k in ["time", "stage"] { if let Some(x) = ss.get(k) { chk(format!("{} status.{}", w, k), format!("{:?}", p.status_state.n(k)), format!("{:?}", x.as_f64())); } }
            chk(format!("{} boosts", w), format!("{:?}", p.boosts), format!("{:?}", BOOST_NAMES.iter().map(|k| pp["boosts"][k].as_i64().unwrap_or(0)).collect::<Vec<_>>()));
            let mut v: Vec<String> = p.volatiles.iter().map(|(k, x)| format!("{}:{:?}", k, x.duration)).collect(); v.sort();
            let mut v2: Vec<String> = pp["volatiles"].as_object().unwrap().iter().map(|(k, x)| format!("{}:{:?}", k, dur(x))).collect(); v2.sort();
            chk(format!("{} volatiles", w), v.join(","), v2.join(","));
            chk(format!("{} item", w), p.item.to_string(), pp["item"].as_str().unwrap().to_string());
            chk(format!("{} ability", w), p.ability.to_string(), pp["ability"].as_str().unwrap().to_string());
            chk(format!("{} fainted", w), p.fainted.to_string(), pp["fainted"].to_string());
            chk(format!("{} pp", w), format!("{:?}", p.move_slots.iter().map(|m| m.pp).collect::<Vec<_>>()),
                format!("{:?}", pp["moveSlots"].as_array().unwrap().iter().map(|m| m["pp"].as_i64().unwrap()).collect::<Vec<_>>()));
            chk(format!("{} lastMove", w), p.last_move.unwrap_or("").to_string(), pp["lastMove"].as_str().unwrap_or("").to_string());
        }
    }
    d
}

/// effect-state values in one comparable form: false / null / "" / missing are the same; Pokemon by species (the two sides order
/// side.pokemon differently after switches); effects by id; numbers as f64
fn canon_sd(v: &Value, mon: &dyn Fn(usize, usize) -> String) -> Option<String> {
    match v {
        Value::Null | Value::Bool(false) => None, Value::Bool(true) => Some("true".into()),
        Value::Number(n) => Some(format!("{}", n.as_f64().unwrap_or(0.0))),
        Value::String(x) => if x.is_empty() { None } else { Some(x.clone()) },
        Value::Object(o) => if let Some(p) = o.get("$p") { Some(format!("mon:{}", mon(p[0].as_u64().unwrap_or(0) as usize, p[1].as_u64().unwrap_or(0) as usize))) }
                            else if o.contains_key("$e") { Some(format!("e:{}", o.get("id").and_then(|x| x.as_str()).unwrap_or(""))) } else { Some("obj".into()) },
        Value::Array(a) => { let v: Vec<String> = a.iter().filter(|x| x.get("$p").is_some()).filter_map(|x| canon_sd(x, mon)).collect();
                             if v.is_empty() { None } else { Some(format!("[{}]", v.join(","))) } }
    }
}
fn canon_en(v: &SV, mon: &dyn Fn(MonRef) -> String) -> Option<String> {
    match v {
        SV::Null | SV::B(false) => None, SV::B(true) => Some("true".into()), SV::N(n) => Some(format!("{}", n)),
        SV::S(x) => if x.is_empty() { None } else { Some(x.to_string()) }, SV::M(m) => Some(format!("mon:{}", mon(*m))), SV::E(_, i) => Some(format!("e:{}", i)),
        SV::L(l) => if l.is_empty() { None } else { Some(format!("[{}]", l.iter().map(|m| format!("mon:{}", mon(*m))).collect::<Vec<_>>().join(","))) },
    }
}
const SKIP: [&str; 5] = ["id", "effectOrder", "duration", "target", "name"];
fn est_sd(v: &Value, mon: &dyn Fn(usize, usize) -> String) -> String {
    let mut m: BTreeMap<String, String> = BTreeMap::new();
    if let Some(o) = v.as_object() { for (k, x) in o { if SKIP.contains(&k.as_str()) { continue; } if let Some(c) = canon_sd(x, mon) { m.insert(k.clone(), c); } } }
    m.iter().map(|(k, v)| format!("{}={}", k, v)).collect::<Vec<_>>().join(" ")
}
fn est_en(s: &EState, mon: &dyn Fn(MonRef) -> String) -> String {
    let mut m: BTreeMap<String, String> = BTreeMap::new();
    for (k, x) in &s.misc { if SKIP.contains(k) { continue; } if let Some(c) = canon_en(x, mon) { m.insert(k.to_string(), c); } }
    if let Some(x) = s.source { m.insert("source".into(), format!("mon:{}", mon(x))); }
    if let Some(x) = s.source_slot { if !x.is_empty() { m.insert("sourceSlot".into(), x.to_string()); } }
    if let Some((_, i)) = s.source_effect { m.insert("sourceEffect".into(), format!("e:{}", i)); }
    if s.is_slot_condition { m.insert("isSlotCondition".into(), "true".into()); }
    m.iter().map(|(k, v)| format!("{}={}", k, v)).collect::<Vec<_>>().join(" ")
}
/// what `diff` leaves out (DIFF_FULL=1; 2026-10-12, for the mid-battle cases of gen_battle_cases.js): the contents of every effect state
/// (volatiles, side and slot conditions, status, ability, item, weather, terrain, pseudo-weathers: layers, counters, sources, stored
/// moves), stats, types, move slots, item history and counters, and for the active Pokemon the disabled moves and trapping the next
/// request is built from; with the post-turn request exported (`req`), the engine's request moves against Showdown's
pub fn diff_full(b: &Battle, post: &Value, req: Option<&Value>) -> Vec<String> {
    let mut d = vec![]; let mut bb = b.clone();
    // a secondary effect's volatile has a plain object as Showdown's sourceEffect (not an effect); the engine keeps the move
    let strip = |x: String| -> String { x.split(' ').filter(|f| !f.starts_with("sourceEffect=")).collect::<Vec<_>>().join(" ") };
    let mut chk = |what: String, mine: String, theirs: String| {
        let (mine, theirs) = if theirs.contains("sourceEffect=obj") { (strip(mine), strip(theirs)) } else { (mine, theirs) };
        if mine != theirs { d.push(format!("{}: native {} vs showdown {}", what, mine, theirs)); } };
    let sdm = |s: usize, i: usize| -> String { post["sides"][s]["pokemon"][i]["set"]["species"].as_str().map(to_id).unwrap_or_default() };
    let enm = |m: MonRef| -> String { b.sides[m.0 as usize].pokemon.get(m.1 as usize).map(|p| p.set_species.to_string()).unwrap_or_default() };
    let f = &post["field"];
    chk("weatherState".into(), est_en(&b.field.weather_state, &enm), est_sd(&f["weatherState"], &sdm));
    chk("terrainState".into(), est_en(&b.field.terrain_state, &enm), est_sd(&f["terrainState"], &sdm));
    for (k, st) in &b.field.pseudo { chk(format!("pseudoWeather {}", k), est_en(st, &enm), est_sd(&f["pseudoWeather"][*k], &sdm)); }
    for s in 0..2 {
        let ps = &post["sides"][s]; let side = &b.sides[s];
        chk(format!("p{} totalFainted", s + 1), side.total_fainted.to_string(), ps["totalFainted"].to_string());
        for (k, st) in &side.side_conditions { chk(format!("p{} sideCondition {}", s + 1, k), est_en(st, &enm), est_sd(&ps["sideConditions"][*k], &sdm)); }
        for slot in 0..2 {
            let mut a: Vec<String> = side.slot_conditions[slot].iter().map(|(k, st)| format!("{}:{:?}[{}]", k, st.duration, est_en(st, &enm))).collect(); a.sort();
            let empty = serde_json::Map::new();
            let mut c: Vec<String> = ps["slotConditions"][slot].as_object().unwrap_or(&empty).iter().map(|(k, x)| format!("{}:{:?}[{}]", k, dur(x), est_sd(x, &sdm))).collect(); c.sort();
            chk(format!("p{} slotConditions[{}]", s + 1, slot), a.join(","), c.join(","));
        }
        for pp in ps["pokemon"].as_array().unwrap() {
            let sp = to_id(pp["set"]["species"].as_str().unwrap());
            let pos = pp["position"].as_u64().unwrap_or(99) as u8;
            let Some(p) = side.pokemon.iter().find(|q| q.set_species == sp && q.position == pos).or_else(|| side.pokemon.iter().find(|q| q.set_species == sp)) else { continue };
            let w = format!("p{} {}", s + 1, p.set_species);
            chk(format!("{} stats", w), format!("{:?}", &p.stored[1..]), format!("{:?}", ["atk", "def", "spa", "spd", "spe"].iter().map(|k| pp["storedStats"][k].as_i64().unwrap_or(0)).collect::<Vec<_>>()));
            chk(format!("{} types", w), format!("{:?}/{}", p.types, p.added_type), format!("{:?}/{}", pp["types"].as_array().unwrap().iter().map(|x| x.as_str().unwrap_or("")).collect::<Vec<_>>(), pp["addedType"].as_str().unwrap_or("")));
            chk(format!("{} moves", w), format!("{:?}", p.move_slots.iter().map(|m| (m.id, m.maxpp)).collect::<Vec<_>>()),
                format!("{:?}", pp["moveSlots"].as_array().unwrap().iter().map(|m| (m["id"].as_str().unwrap_or(""), m["maxpp"].as_i64().unwrap_or(0))).collect::<Vec<_>>()));
            chk(format!("{} lastItem", w), p.last_item.to_string(), pp["lastItem"].as_str().unwrap_or("").to_string());
            chk(format!("{} itemKnockedOff", w), p.item_knocked_off.to_string(), pp["itemKnockedOff"].to_string());
            chk(format!("{} timesAttacked", w), p.times_attacked.to_string(), pp["timesAttacked"].to_string());
            chk(format!("{} canMegaEvo", w), p.can_mega_evo.map(|x| x.to_string()).unwrap_or_default(), pp["canMegaEvo"].as_str().map(to_id).unwrap_or_default());
            chk(format!("{} transformed", w), p.transformed.to_string(), pp["transformed"].to_string());
            chk(format!("{} statusState", w), est_en(&p.status_state, &enm), est_sd(&pp["statusState"], &sdm));
            chk(format!("{} abilityState", w), est_en(&p.ability_state, &enm), est_sd(&pp["abilityState"], &sdm));
            chk(format!("{} itemState", w), est_en(&p.item_state, &enm), est_sd(&pp["itemState"], &sdm));
            for (k, st) in &p.volatiles { chk(format!("{} volatile {}", w, k), est_en(st, &enm), est_sd(&pp["volatiles"][*k], &sdm)); }
            if p.is_active && !p.fainted && !b.ended {
                chk(format!("{} disabled", w), format!("{:?}", p.move_slots.iter().map(|m| m.disabled).collect::<Vec<_>>()),
                    format!("{:?}", pp["moveSlots"].as_array().unwrap().iter().map(|m| truthy_json(&m["disabled"])).collect::<Vec<_>>()));
                // Showdown's request (getMoveRequestData) traps a Pokemon locked into a move and clears maybeTrapped except on the
                // side's last active Pokemon (information hiding); the exported state is taken after the request
                let mi = side.pokemon.iter().position(|q| std::ptr::eq(q, p)).unwrap() as u8;
                let locked = bb.get_locked_move((s as u8, mi)).is_some();
                let last = side.active.iter().skip(p.position as usize + 1).all(|a| a.map(|i| side.pokemon[i as usize].fainted).unwrap_or(true));
                chk(format!("{} trapped", w), format!("{}/{}", p.trapped || locked, p.maybe_trapped && last && !locked),
                    format!("{}/{}", truthy_json(&pp["trapped"]), pp["maybeTrapped"].as_bool().unwrap_or(false)));
            }
        }
        // the next request (gen_battle_cases.js `req`): each active slot's moves as Showdown lists them, against request_moves
        if let Some(r) = req.and_then(|r| r.get(s)).and_then(|r| r.get("active")).and_then(|a| a.as_array()) {
            for (i, ra) in r.iter().enumerate() {
                let Some(pi) = b.sides[s].active.get(i).copied().flatten() else { continue };
                if b.sides[s].pokemon[pi as usize].fainted { continue; }
                // a hidden disable (Imprison) shows as usable in the last active Pokemon's request (Showdown's restrictData)
                let last = b.sides[s].active.iter().skip(i + 1).all(|a| a.map(|j| b.sides[s].pokemon[j as usize].fainted).unwrap_or(true));
                let slots = &b.sides[s].pokemon[pi as usize].move_slots;
                let mine: Vec<String> = bb.request_moves_shown((s as u8, pi)).iter().map(|(m, _, dis)| {
                    let hidden = last && slots.iter().any(|x| x.id == *m && x.disabled_hidden && x.pp > 0);
                    format!("{}{}", m, if *dis && !hidden { "(x)" } else { "" }) }).collect();
                let theirs: Vec<String> = ra["moves"].as_array().map(|a| a.iter().map(|m| format!("{}{}", m["id"].as_str().unwrap_or(""), if truthy_json(&m["disabled"]) { "(x)" } else { "" })).collect()).unwrap_or_default();
                chk(format!("p{} request slot {}", s + 1, i), mine.join(","), theirs.join(","));
            }
        }
    }
    d
}
/// the order of |move| lines (user and move) in the engine's log and Showdown's (ORDER=1)
pub fn diff_order(b: &Battle, log: &Value) -> Vec<String> {
    // the user by its position (Showdown's log names some formes by their base species: "Indeedee" for Indeedee-F)
    let pick = |l: &str| -> Option<String> { if l.starts_with("|move|") { let f: Vec<&str> = l.split('|').collect(); Some(format!("{} {}", f.get(2).unwrap_or(&"").split(':').next().unwrap_or(""), f.get(3).unwrap_or(&""))) } else { None } };
    let mine: Vec<String> = b.log.iter().filter_map(|l| pick(l)).collect();
    let theirs: Vec<String> = log.as_array().map(|a| a.iter().filter_map(|l| l.as_str().and_then(pick)).collect()).unwrap_or_default();
    if mine == theirs { vec![] } else { vec![format!("move order: native {:?} vs showdown {:?}", mine, theirs)] }
}
/// time run_turn alone: each case's starting position is built once, then cloned and played with real RNG (different seeds)
pub fn bench(args: &[String]) {
    let (dex, reg) = crate::turntest::load_all(&args[0]);
    let reps: usize = args.get(2).and_then(|x| x.parse().ok()).unwrap_or(20);
    let mut starts = vec![];
    for line in std::fs::read_to_string(&args[1]).unwrap().lines() {
        let c: Value = serde_json::from_str(line).unwrap();
        let ch = [parse_choice(c["choices"][0].as_str().unwrap()), parse_choice(c["choices"][1].as_str().unwrap())];
        let sw: Vec<(usize, String)> = c["real"].get("switches").and_then(|x| x.as_array()).map(|a| a.iter().map(|e| (e[0].as_u64().unwrap() as usize, e[1].as_str().unwrap().to_string())).collect()).unwrap_or_default();
        starts.push((new_battle(dex, reg, &c["pre"], Mode::Real), ch, sw));
    }
    let t0 = std::time::Instant::now(); let mut n = 0u64; let mut sink = 0i64; let (mut ev, mut fi) = (0u64, 0u64);
    for r in 0..reps { for (b0, ch, sw) in &starts {
        let mut b = b0.clone(); b.prng = Prng::gen5([1, 2, 3, r as u16]);
        play(&mut b, *ch, sw); n += 1; sink += b.sides[0].pokemon[0].hp; ev += b.nevents; fi += b.nfind;
    } }
    let el = t0.elapsed();
    println!("{} turns in {:?}: {:.1} us/turn (clone + run_turn)  [{}]  runEvents/turn {:.0}, pokemon handler scans/turn {:.0}", n, el, el.as_secs_f64() * 1e6 / n as f64, sink % 7, ev as f64 / n as f64, fi as f64 / n as f64);
}
pub fn main(args: &[String]) {
    let (dex, reg) = crate::turntest::load_all(&args[0]);
    let modes: Vec<&str> = args.get(2).map(|s| s.split(',').collect()).unwrap_or(vec!["lo", "hi", "mid"]);
    let only: Option<i64> = std::env::var("CASE").ok().and_then(|x| x.parse().ok());
    let full = std::env::var("DIFF_FULL").is_ok(); let order = std::env::var("ORDER").is_ok();
    let maxex: usize = std::env::var("MAXEX").ok().and_then(|x| x.parse().ok()).unwrap_or(15);
    let text = std::fs::read_to_string(&args[1]).unwrap();
    let mut tot: BTreeMap<String, (usize, usize, usize)> = BTreeMap::new();   // mode -> (exact, mismatch, unsupported)
    let mut unsup: BTreeMap<String, usize> = BTreeMap::new();
    let mut bad: BTreeMap<String, usize> = BTreeMap::new();
    let mut examples = vec![];
    let t0 = std::time::Instant::now(); let mut turns = 0;
    for line in text.lines() {
        let c: Value = serde_json::from_str(line).unwrap();
        if let Some(o) = only { if c["id"].as_i64() != Some(o) { continue; } }
        let ch = [parse_choice(c["choices"][0].as_str().unwrap()), parse_choice(c["choices"][1].as_str().unwrap())];
        for mode in &modes {
            let Some(exp) = c.get(*mode) else { continue };
            let m = match *mode { "lo" => Mode::Lo, "hi" => Mode::Hi, "mid" => Mode::Mid, q if q.starts_with('q') => Mode::Frac(q[1..].parse().unwrap()), _ => Mode::Real };
            let mut b = new_battle(dex, reg, &c["pre"], m);
            if order { b.logging = true; }
            let sw: Vec<(usize, String)> = exp.get("switches").and_then(|x| x.as_array()).map(|a| a.iter().map(|e| (e[0].as_u64().unwrap() as usize, e[1].as_str().unwrap().to_string())).collect()).unwrap_or_default();
            let r = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| { play(&mut b, ch, &sw); b }));
            turns += 1;
            let e = tot.entry(mode.to_string()).or_insert((0, 0, 0));
            let b = match r { Ok(b) => b, Err(p) => {
                e.2 += 1; let msg = p.downcast_ref::<String>().cloned().or(p.downcast_ref::<&str>().map(|s| s.to_string())).unwrap_or_default();
                *unsup.entry(format!("PANIC {}", msg.chars().take(80).collect::<String>())).or_insert(0) += 1; continue; } };
            if !b.unsupported.is_empty() { e.2 += 1; for u in &b.unsupported { *unsup.entry(u.clone()).or_insert(0) += 1; } continue; }
            let mut d = diff(&b, &exp["post"]);
            if full { d.extend(diff_full(&b, &exp["post"], exp.get("req"))); }
            if order { d.extend(diff_order(&b, &exp["log"])); }
            if d.is_empty() { e.0 += 1; } else {
                e.1 += 1;
                for x in &d { let k: String = x.split(": native").next().unwrap().split_whitespace().last().unwrap_or("").to_string(); *bad.entry(k).or_insert(0) += 1; }
                if examples.len() < maxex || only.is_some() {
                    examples.push(format!("case {} [{}] choices {:?}\n    {}\n    showdown log: {}", c["id"], mode, c["choices"], d.join("\n    "),
                        exp["log"].as_array().map(|l| l.iter().map(|x| x.as_str().unwrap_or("")).collect::<Vec<_>>().join(" ")).unwrap_or_default()));
                    if b.logging { examples.push(format!("    native log: {}", b.log.join(" "))); }
                }
            }
        }
    }
    let el = t0.elapsed();
    for (m, (ok, bad_, un)) in &tot { println!("{:4}: exact {:5}  mismatch {:5}  unsupported {:5}   ({:.1}% exact of supported)", m, ok, bad_, un, 100.0 * *ok as f64 / (*ok + *bad_).max(1) as f64); }
    println!("{} native turns in {:?} ({:.1} us/turn)", turns, el, el.as_secs_f64() * 1e6 / turns.max(1) as f64);
    let mut v: Vec<_> = unsup.into_iter().collect(); v.sort_by(|a, b| b.1.cmp(&a.1));
    println!("unsupported (cases):"); for (k, n) in v.iter().take(40) { println!("  {:5} {}", n, k); }
    let mut v: Vec<_> = bad.into_iter().collect(); v.sort_by(|a, b| b.1.cmp(&a.1));
    println!("mismatching fields:"); for (k, n) in v.iter().take(20) { println!("  {:5} {}", n, k); }
    for e in examples { println!("{}", e); }
}
