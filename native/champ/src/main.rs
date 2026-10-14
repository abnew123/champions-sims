//! Differential tests against Showdown.
//!   champ damage <champions_data.json> <damage_cases.jsonl>     native damage calc vs Showdown rolls
//!   champ turn <engine_data.json> <turn_cases.jsonl> [modes]     one full turn vs Showdown (modes: lo,hi,mid,real)
//!   champ battle / spot / plan / evalpos ...                      see battle4.rs, spot.rs, plan.rs, evalpos.rs
mod calc; mod data; mod prng; mod dex; mod state; mod battle; mod sim; mod handlers; mod turntest; mod plan; mod spreads; mod spot; mod battle4; mod human; mod evalpos; mod vfeats; mod deep;
use calc::*; use serde_json::Value; use std::collections::BTreeMap;

// The planner allocates heavily (cloned battle states, small vectors in the event system); mimalloc is much faster than the
// system allocator for that. Results do not depend on the allocator.
#[cfg(feature = "fast-alloc")]
#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

fn mon(v: &Value) -> Mon {
    let sp = &v["sp"]; let b = &v["boosts"];
    Mon { species: v["species"].as_str().unwrap().into(), item: v["item"].as_str().unwrap_or("").into(), ability: v["ability"].as_str().unwrap_or("").into(),
          nature: v["nature"].as_str().unwrap().into(), sp: std::array::from_fn(|i| sp[STATS[i]].as_i64().unwrap_or(0)),
          boosts: std::array::from_fn(|i| b[["atk", "def", "spa", "spd", "spe"][i]].as_i64().unwrap_or(0)),
          hp: v["hp"].as_i64().unwrap(), maxhp: v["maxhp"].as_i64().unwrap(), status: v["status"].as_str().unwrap_or("").into(), fallen: 0 }
}
fn main() {
    let a: Vec<String> = std::env::args().collect();
    match a.get(1).map(|s| s.as_str()) { Some("turn") => turntest::main(&a[2..]), Some("bench") => turntest::bench(&a[2..]), Some("plan") => plan::main(&a[2..]), Some("spot") => spot::main(&a[2..]), Some("battle") => battle4::main(&a[2..]), Some("play") => battle4::play_main(&a[2..]), Some("evalpos") => evalpos::main(&a[2..]), Some("feats") => evalpos::feats_main(&a[2..]), Some("vfeats") => evalpos::vfeats_main(&a[2..]), Some("spreads") => spreads::main(&a[2..]), Some("damage") => damage_main(&a[1..]), _ => damage_main(&a) }
}
fn damage_main(args: &[String]) {
    let d = data::Data::load(&args[1]);
    let t0 = std::time::Instant::now();
    let (mut n, mut exact, mut stat_ok, mut calls) = (0, 0, 0, 0u64);
    let mut bad: BTreeMap<String, (i64, i64)> = BTreeMap::new(); let mut examples: Vec<String> = vec![];
    for line in std::fs::read_to_string(&args[2]).unwrap().lines() {
        let c: Value = serde_json::from_str(line).unwrap();
        let (a, def) = (mon(&c["attacker"]), mon(&c["defender"]));
        if !d.species.contains_key(&a.species) || !d.species.contains_key(&def.species) || !d.moves.contains_key(c["move"].as_str().unwrap()) { continue; }
        n += 1;
        let st = |m: &Mon| -> [i64; 6] { std::array::from_fn(|i| stat(&d, &m.species, &m.sp, &m.nature, i)) };
        let (sa, sd) = (st(&a), st(&def));
        let sv = |v: &Value, s: &[i64; 6], m: &Mon| (1..6).all(|i| v["stats"][STATS[i]].as_i64() == Some(s[i])) && s[0] == m.maxhp;
        if sv(&c["attacker"], &sa, &a) && sv(&c["defender"], &sd, &def) { stat_ok += 1; }
        let f = Field { weather: c["field"]["weather"].as_str().unwrap().into(), terrain: c["field"]["terrain"].as_str().unwrap().into(),
                        screens: c["field"]["screens"].as_array().unwrap().iter().map(|x| x.as_str().unwrap().into()).collect(),
                        spread: c["field"]["spread"].as_bool().unwrap(), helping: c["field"]["helping"].as_bool().unwrap() };
        let mv = c["move"].as_str().unwrap();
        let mut ok = true;
        for (key, crit) in [("rolls", false), ("critRolls", true)] {
            for r in 0..16 {
                let want = c[key][r].as_i64(); let got = damage(&d, &a, &def, mv, &f, r as i64, crit, &sa, &sd); calls += 1;
                if want != got { ok = false; }
            }
        }
        if ok { exact += 1; } else {
            for k in [format!("move {}", mv), format!("atk-ability {}", a.ability), format!("atk-item {}", a.item), format!("def-ability {}", def.ability), format!("def-item {}", def.item)] {
                let e = bad.entry(k).or_insert((0, 0)); e.0 += 1;
            }
            if examples.len() < 12 {
                let got: Vec<Option<i64>> = (0..16).map(|r| damage(&d, &a, &def, mv, &f, r, false, &sa, &sd)).collect();
                examples.push(format!("#{} {} ({} {} {}) -> {} ({} {}) field {:?}\n     showdown {:?}\n     native   {:?}", c["id"], mv, a.species, a.ability, a.item, def.species, def.ability, def.item, f,
                                      c["rolls"].as_array().unwrap().iter().map(|x| x.as_i64()).collect::<Vec<_>>(), got));
            }
        }
        for (k, v) in bad.iter_mut() { let _ = (k, v); }
    }
    let el = t0.elapsed();
    println!("{} cases: stats exact {} ({:.1}%), all 32 rolls exact {} ({:.1}%)  |  {} damage calls in {:?} ({:.2} us each)",
             n, stat_ok, 100.0 * stat_ok as f64 / n as f64, exact, 100.0 * exact as f64 / n as f64, calls, el, el.as_secs_f64() * 1e6 / calls as f64);
    // most frequent ingredients among the mismatches
    let mut v: Vec<_> = bad.into_iter().collect(); v.sort_by(|a, b| b.1.0.cmp(&a.1.0));
    println!("most common in mismatching cases:"); for (k, (c, _)) in v.iter().take(25) { println!("   {:4}  {}", c, k); }
    println!("examples:"); for e in examples { println!("  {}", e); }
}
