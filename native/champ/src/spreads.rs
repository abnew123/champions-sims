//! Spread search tables: for each of my Pokemon, how every Stat Point allocation fares against the threat list (spreads/threats.json).
//! Offense: per nature and SP in the attacking stat, against each threat at its common bulk, how many of the 16 rolls OHKO and how many
//! of the 256 roll pairs 2HKO. Defense: per nature, HP SP and Def (or SpD) SP, against each threat's attacks, how many rolls (and roll
//! pairs) I survive. Scoring and reporting is done in spreads/score.py.
//!   champ spreads <champions_data.json> <mine.json> <threats.json> <out.json>
use crate::calc::*;
use crate::data::Data;
use serde_json::{json, Value};

const SPREAD: [&str; 2] = ["allAdjacentFoes", "allAdjacent"];

fn mon(species: &str, item: &str, ability: &str, nature: &str, sp: [i64; 6], d: &Data) -> (Mon, [i64; 6]) {
    let st: [i64; 6] = std::array::from_fn(|i| stat(d, species, &sp, nature, i));
    (Mon { species: species.into(), item: item.into(), ability: ability.into(), nature: nature.into(), sp, boosts: [0; 5], hp: st[0], maxhp: st[0], status: String::new() }, st)
}
fn rolls(d: &Data, a: &Mon, ast: &[i64; 6], t: &Mon, tst: &[i64; 6], mv: &str, f: &Field) -> Vec<i64> {
    (0..16).map(|r| damage(d, a, t, mv, f, r, false, ast, tst).unwrap_or(0)).collect()
}
/// (rolls that KO from full, roll pairs that KO in two hits)
fn ko_counts(r: &[i64], hp: i64) -> (i64, i64) {
    let one = r.iter().filter(|x| **x >= hp).count() as i64;
    let mut two = 0; for a in r { for b in r { if a + b >= hp { two += 1; } } }
    (one, two)
}

pub fn main(args: &[String]) {
    let d = Data::load(&args[0]);
    let mine: Value = serde_json::from_str(&std::fs::read_to_string(&args[1]).unwrap()).unwrap();
    let threats: Value = serde_json::from_str(&std::fs::read_to_string(&args[2]).unwrap()).unwrap();
    let ths = threats.as_array().unwrap();
    let mut out = vec![];
    for m in mine.as_array().unwrap() {
        let (sp_id, item, ab) = (m["species"].as_str().unwrap(), m["item"].as_str().unwrap(), m["ability"].as_str().unwrap());
        let my_moves: Vec<String> = m["moves"].as_array().unwrap().iter().map(|x| x.as_str().unwrap().to_string())
            .filter(|x| d.moves.get(x.as_str()).map(|mv| mv.category != "Status").unwrap_or(false) && x != "fakeout").collect();
        let my_weather = m["weather"].as_str().unwrap_or("");
        // a nature matters to offense only through the attacking stat and to defense only through Def/SpD, so the tables are built for
        // representative natures: offense Serious / Brave (+Atk) / Quiet (+SpA); defense Serious / Relaxed (+Def) / Sassy (+SpD)
        let off_natures = ["Serious", "Brave", "Quiet"]; let def_natures = ["Serious", "Relaxed", "Sassy"];
        // offense: my attacks vs each threat at its common bulk; attacking stat swept 0..32 (other stats irrelevant at full HP)
        let mut offense = vec![];
        for nat in off_natures {
            let mut by_sp = vec![];
            for sp in 0..=32i64 {
                let mut per_t = vec![];
                for t in ths {
                    let tsp: [i64; 6] = std::array::from_fn(|i| t["bulk_sp"][i].as_i64().unwrap());
                    let (tm, tst) = mon(t["species"].as_str().unwrap(), t["item"].as_str().unwrap(), t["ability"].as_str().unwrap(), t["bulk_nature"].as_str().unwrap(), tsp, &d);
                    let mut per_m = vec![];
                    for mv in &my_moves {
                        let cat = d.moves[mv.as_str()].category.clone();
                        let msp = [0, if cat == "Physical" { sp } else { 0 }, 0, if cat == "Special" { sp } else { 0 }, 0, 0];
                        let (am, ast) = mon(sp_id, item, ab, nat, msp, &d);
                        let spread = SPREAD.contains(&d.moves[mv.as_str()].target.as_str());
                        let f = Field { weather: if my_weather.is_empty() { t["weather"].as_str().unwrap().into() } else { my_weather.into() }, terrain: t["terrain"].as_str().unwrap().into(),
                                        screens: vec![], spread, helping: false };
                        let r = rolls(&d, &am, &ast, &tm, &tst, mv, &f);
                        let (one, two) = ko_counts(&r, tst[0]);
                        per_m.push(json!([one, two, r[15], r[0]]));
                    }
                    per_t.push(Value::Array(per_m));
                }
                by_sp.push(Value::Array(per_t));
            }
            offense.push(json!({"nature": nat, "by_sp": by_sp}));
        }
        // defense: each threat's attacks (its common nature, 32 SP in the attacking stat) vs me at HP x Def (physical) / HP x SpD (special)
        let mut defense = vec![];
        for nat in def_natures {
            let mut tabs = json!({"nature": nat, "phys": [], "spec": []});
            for (key, di) in [("phys", 2usize), ("spec", 4usize)] {
                let mut grid = vec![];
                for hp in 0..=32i64 { for dv in 0..=32i64 {
                    let mut sp = [0i64; 6]; sp[0] = hp; sp[di] = dv;
                    let (me, mst) = mon(sp_id, item, ab, nat, sp, &d);
                    let mut cell = vec![];
                    for t in ths {
                        let tsp: [i64; 6] = std::array::from_fn(|i| t["atk_sp"][i].as_i64().unwrap());
                        let (tm, tst) = mon(t["species"].as_str().unwrap(), t["item"].as_str().unwrap(), t["ability"].as_str().unwrap(), t["atk_nature"].as_str().unwrap(), tsp, &d);
                        for mvw in t["moves"].as_array().unwrap() {
                            let mv = mvw[0].as_str().unwrap();
                            let Some(md) = d.moves.get(mv) else { continue };
                            let phys = md.override_def.as_deref() == Some("def") || (md.category == "Physical" && md.override_def.is_none());
                            if (key == "phys") != phys { continue; }
                            let spread = SPREAD.contains(&md.target.as_str());
                            let f = Field { weather: if my_weather.is_empty() { t["weather"].as_str().unwrap().into() } else { my_weather.into() }, terrain: t["terrain"].as_str().unwrap().into(),
                                            screens: vec![], spread, helping: false };
                            let r = rolls(&d, &tm, &tst, &me, &mst, mv, &f);
                            let (one, two) = ko_counts(&r, mst[0]);
                            cell.push(json!([16 - one, 256 - two]));
                        }
                    }
                    grid.push(Value::Array(cell));
                } }
                tabs[key] = Value::Array(grid);
            }
            defense.push(tabs);
        }
        // the move lists in table order, so the scorer can label cells
        let mut dmoves = json!({"phys": [], "spec": []});
        for t in ths { for mvw in t["moves"].as_array().unwrap() {
            let mv = mvw[0].as_str().unwrap(); let Some(md) = d.moves.get(mv) else { continue };
            let phys = md.override_def.as_deref() == Some("def") || (md.category == "Physical" && md.override_def.is_none());
            dmoves[if phys { "phys" } else { "spec" }].as_array_mut().unwrap().push(json!([t["name"], mv, mvw[1], t["weight"]]));
        } }
        eprintln!("{} done", m["name"]);
        out.push(json!({"name": m["name"], "moves": my_moves, "offense": offense, "defense": defense, "dmoves": dmoves}));
    }
    std::fs::write(&args[3], serde_json::to_string(&out).unwrap()).unwrap();
}
