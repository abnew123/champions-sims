//! Position evaluation for the eval bar (2026-10-05, champ-battle-v13). Each input line is a position: a state exported like the battle
//! starts and spots (any turn, both sides' sets explicit) with optional actual choices. For each one the turn is solved as the battle
//! planner solves it (each side's own options, switches included, against the other side staying in, plus the other side's actually-played
//! switches: battle4.rs with BATTLE_ANTICIPATE), every cell averaged over EVAL_SEEDS seeds (default 8) of the turn's luck, and one output
//! line is written:
//!   name, turn, side, perish, approx   copied from the input
//!   value        side 0's win chance: both sides on their equilibrium mixes
//!   static       the value function at the position itself (no lookahead); feats = the planner's feature vector there
//!   sides[s]     slots: per living active Pokemon {mon, options: [{label, c, w, v, actual}]}: every legal option with its engine choice
//!                (c: [move slot, target, mega] or ["switch", team index]), its weight in that side's mix (w), the value of the best joint
//!                action containing it against the other side's mix (v), and whether it was the choice made (true / false / null = unknown);
//!                joint: the side's top joint actions {label, w, v}; actual_v: the value of the joint action actually made (null if a
//!                slot's choice is unknown), actual_found: false if a given choice is not among the legal options.
//!                Every v inside sides[s] is side s's OWN win chance (side 1's = 1 - side 0's).
//!   options, cells, ms, unsupported (engine mechanics hit while simulating), seeds
//! A position that cannot be handled gives {name, error}; the run goes on. Output is appended as positions finish (any order, keyed by
//! name); names already in the output file are skipped, so a run resumes.
//!   champ evalpos <engine_data.json> <positions.jsonl> <out.jsonl> [threads=1]
//! env: EG_VALUE (and RACE / CALC_DATA, TRSYM, GRID_DIR as for battles), EVAL_SEEDS, EVAL_TOP (joint actions listed, default 8)
use crate::battle::*;
use crate::plan::*;
use crate::prng::{Mode, Prng};
use crate::sim::PChoice;
use crate::spot::{joint, label, resolve_switches, seed4};
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::io::Write;

fn env_usize(name: &str, default: usize) -> usize { std::env::var(name).ok().and_then(|x| x.parse().ok()).unwrap_or(default) }

struct Cells<'a> { b: &'a Battle, cfg: &'a Cfg, msw: &'a [[PChoice; 2]], tsw: &'a [[PChoice; 2]], cs: Vec<[u16; 4]>, cache: HashMap<(usize, usize), f64>, uns: Vec<String> }
impl<'a> Cells<'a> {
    /// side 0's value after the turn (i, j), averaged over the seeds
    fn get(&mut self, i: usize, j: usize) -> f64 {
        if let Some(v) = self.cache.get(&(i, j)) { return *v; }
        let mut s = 0.0;
        for c in &self.cs {
            let mut x = self.b.clone(); x.prng = Prng::gen5(*c); x.run_turn([self.msw[i], self.tsw[j]]); resolve_switches(&mut x, self.cfg, None);
            s += value(&mut x, self.cfg);
            for u in &x.unsupported { if !self.uns.contains(u) { self.uns.push(u.clone()); } }
        }
        let v = s / self.cs.len() as f64; self.cache.insert((i, j), v); v
    }
}
fn choice_json(b: &Battle, s: u8, c: &PChoice) -> Value {
    match c { PChoice::Move(k, t, mega) => json!([k, t, mega]), PChoice::Switch(p) => json!(["switch", b.mon_at_position(s, *p).map(|m| m.1)]), PChoice::Pass => Value::Null }
}
/// one slot's part of spot::label ("Move -> Target (Mega)" / "switch to X")
fn slot_label(b: &Battle, s: u8, i: usize, c: &PChoice) -> String {
    let mut j = [PChoice::Pass; 2]; j[i] = *c;
    let l = label(b, s, &j);
    // label() joins the living slots as "Mon: what | Mon: what"; the other slot shows "pass"
    let parts: Vec<&str> = l.split(" | ").collect();
    let alive0 = b.sides[s as usize].active[0].map(|p| !b.p((s, p)).fainted).unwrap_or(false);
    let part = if i == 0 || !alive0 { parts.first() } else { parts.get(1) };
    part.and_then(|p| p.split_once(": ")).map(|x| x.1.to_string()).unwrap_or_default()
}
/// the input's actual choice for one slot: None = unknown
fn parse_actual(b: &Battle, s: u8, a: &Value) -> Option<PChoice> {
    let c = a.get("choice")?;
    if c[0].as_str() == Some("switch") { let i = c[1].as_u64()? as usize; let p = b.sides[s as usize].pokemon.get(i)?; Some(PChoice::Switch(p.position)) }
    else { Some(PChoice::Move(c[0].as_u64()? as usize, c[1].as_i64()?, c[2].as_bool().unwrap_or(false))) }
}
/// same move slot and target (the Mega flag is ignored: options always Mega Evolve when they can), or the same switch
fn same(c: &PChoice, a: &PChoice) -> bool {
    match (c, a) { (PChoice::Move(k, t, _), PChoice::Move(k2, t2, _)) => k == k2 && t == t2, (PChoice::Switch(p), PChoice::Switch(q)) => p == q, _ => false }
}
fn side_report(b: &Battle, s: u8, opts: &[[PChoice; 2]], w: &[f64], own: &[f64], actual: &Value, top: usize) -> Value {
    let alive: Vec<bool> = (0..2).map(|i| b.sides[s as usize].active[i].map(|p| !b.p((s, p)).fainted).unwrap_or(false)).collect();
    let act: Vec<Option<PChoice>> = (0..2).map(|i| if alive[i] { parse_actual(b, s, &actual[i]) } else { None }).collect();
    let mut found = true; let mut slots = vec![];
    for i in 0..2 {
        if !alive[i] { continue; }
        let p = b.sides[s as usize].active[i].unwrap(); let name = b.dex.species.get(b.p((s, p)).species).map(|x| x.name).unwrap_or("?");
        let mut seen: Vec<PChoice> = vec![]; let mut list = vec![];
        for k in 0..opts.len() {
            let c = opts[k][i];
            if seen.iter().any(|x| *x == c) { continue; }
            seen.push(c);
            let idx: Vec<usize> = (0..opts.len()).filter(|&q| opts[q][i] == c).collect();
            let ww: f64 = idx.iter().map(|&q| w[q]).sum(); let vv = idx.iter().map(|&q| own[q]).fold(f64::MIN, f64::max);
            let a = act[i].as_ref().map(|x| json!(same(&c, x))).unwrap_or(Value::Null);
            list.push(json!({"label": slot_label(b, s, i, &c), "c": choice_json(b, s, &c), "w": ww, "v": vv, "actual": a}));
        }
        if let Some(x) = &act[i] { if !seen.iter().any(|c| same(c, x)) { found = false; } }
        list.sort_by(|a, c| c["w"].as_f64().partial_cmp(&a["w"].as_f64()).unwrap().then(c["v"].as_f64().partial_cmp(&a["v"].as_f64()).unwrap()));
        slots.push(json!({"slot": i, "mon": name, "options": list}));
    }
    let mut order: Vec<usize> = (0..opts.len()).collect();
    order.sort_by(|a, c| w[*c].partial_cmp(&w[*a]).unwrap().then(own[*c].partial_cmp(&own[*a]).unwrap()));
    let jn: Vec<Value> = order.iter().take(top).map(|&q| json!({"label": label(b, s, &opts[q]), "w": w[q], "v": own[q]})).collect();
    let known = (0..2).all(|i| !alive[i] || act[i].is_some());
    let actual_v = if known && found { opts.iter().position(|c| (0..2).all(|i| !alive[i] || same(&c[i], act[i].as_ref().unwrap()))).map(|q| json!(own[q])).unwrap_or(Value::Null) } else { Value::Null };
    json!({"slots": slots, "joint": jn, "actual_v": actual_v, "actual_found": found})
}
fn eval_one(b0: &Battle, cfg: &Cfg, sp: &Value, key: u64, nseeds: usize, top: usize) -> Value {
    let t0 = std::time::Instant::now();
    let mut b = b0.clone();
    let stat = value(&mut b.clone(), cfg); let f = feats(&mut b.clone(), cfg);
    let msw = joint(&mut b, 0, true); let tsw = joint(&mut b, 1, true);
    if b.ended || msw.is_empty() || tsw.is_empty() { return json!({"value": stat, "static": stat, "feats": f, "note": "no choices to make"}); }
    let no_sw = |c: &[PChoice; 2]| !c.iter().any(|x| matches!(x, PChoice::Switch(_)));
    let mns: Vec<usize> = (0..msw.len()).filter(|i| no_sw(&msw[*i])).collect();
    let tns: Vec<usize> = (0..tsw.len()).filter(|j| no_sw(&tsw[*j])).collect();
    let cs: Vec<[u16; 4]> = (0..nseeds).map(|k| seed4(key ^ ((k as u64) << 52))).collect();
    let mut cells = Cells { b: &b, cfg, msw: &msw, tsw: &tsw, cs, cache: HashMap::new(), uns: vec![] };
    // each side's own matrix: all its options against the other side staying in (as battle4.rs), then the anticipation pass
    let am: Vec<Vec<f64>> = (0..msw.len()).map(|i| tns.iter().map(|&j| cells.get(i, j)).collect()).collect();
    let at: Vec<Vec<f64>> = mns.iter().map(|&i| (0..tsw.len()).map(|j| cells.get(i, j)).collect()).collect();
    let mut x = if tns.is_empty() { vec![1.0 / msw.len() as f64; msw.len()] } else { nash(&am, 400).0 };
    let mut y = if mns.is_empty() { vec![1.0 / tsw.len() as f64; tsw.len()] } else { nash(&at, 400).1 };
    let isw: Vec<usize> = (0..msw.len()).filter(|i| !no_sw(&msw[*i]) && x[*i] > 0.02).collect();
    let jsw: Vec<usize> = (0..tsw.len()).filter(|j| !no_sw(&tsw[*j]) && y[*j] > 0.02).collect();
    if !jsw.is_empty() {
        let cols: Vec<usize> = tns.iter().copied().chain(jsw.iter().copied()).collect();
        let am2: Vec<Vec<f64>> = (0..msw.len()).map(|i| cols.iter().map(|&j| cells.get(i, j)).collect()).collect();
        x = nash(&am2, 400).0;
    }
    if !isw.is_empty() {
        let rows: Vec<usize> = mns.iter().copied().chain(isw.iter().copied()).collect();
        let at2: Vec<Vec<f64>> = rows.iter().map(|&i| (0..tsw.len()).map(|j| cells.get(i, j)).collect()).collect();
        y = nash(&at2, 400).1;
    }
    // every option's value against the other side's mix (the support above 0.01%)
    let ysup: Vec<usize> = (0..tsw.len()).filter(|j| y[*j] > 1e-4).collect(); let ytot: f64 = ysup.iter().map(|&j| y[j]).sum();
    let xsup: Vec<usize> = (0..msw.len()).filter(|i| x[*i] > 1e-4).collect(); let xtot: f64 = xsup.iter().map(|&i| x[i]).sum();
    let rv: Vec<f64> = (0..msw.len()).map(|i| ysup.iter().map(|&j| y[j] * cells.get(i, j)).sum::<f64>() / ytot).collect();
    let cv: Vec<f64> = (0..tsw.len()).map(|j| xsup.iter().map(|&i| x[i] * cells.get(i, j)).sum::<f64>() / xtot).collect();
    let v = xsup.iter().map(|&i| x[i] * rv[i]).sum::<f64>() / xtot;
    let own1: Vec<f64> = cv.iter().map(|z| 1.0 - z).collect();
    let s0 = side_report(&b, 0, &msw, &x, &rv, &sp["actual"], top); let s1 = side_report(&b, 1, &tsw, &y, &own1, &sp["their_actual"], top);
    json!({"value": v, "static": stat, "feats": f, "seeds": nseeds, "options": [msw.len(), tsw.len()], "cells": cells.cache.len(),
           "ms": t0.elapsed().as_millis() as u64, "unsupported": cells.uns, "sides": [s0, s1]})
}

pub fn main(args: &[String]) {
    let (dex, reg) = crate::turntest::load_all(&args[0]);
    let cfg: &'static Cfg = Box::leak(Box::new(load_cfg(&std::env::var("GRID_DIR").unwrap_or("../../mxtr".into()))));
    let threads: usize = args.get(3).and_then(|x| x.parse().ok()).unwrap_or(1);
    let nseeds = env_usize("EVAL_SEEDS", 8).max(1); let top = env_usize("EVAL_TOP", 8);
    let lines: Vec<String> = std::fs::read_to_string(&args[1]).unwrap().lines().filter(|l| !l.trim().is_empty()).map(|s| s.to_string()).collect();
    let done: HashSet<String> = std::fs::read_to_string(&args[2]).map(|t| t.lines().filter_map(|l| serde_json::from_str::<Value>(l).ok())
        .filter_map(|v| v["name"].as_str().map(|s| s.to_string())).collect()).unwrap_or_default();
    let out = std::sync::Mutex::new(std::fs::OpenOptions::new().create(true).append(true).open(&args[2]).unwrap());
    let next = std::sync::atomic::AtomicUsize::new(0); let t0 = std::time::Instant::now();
    let nd = std::sync::atomic::AtomicUsize::new(0);
    std::thread::scope(|sc| { for _ in 0..threads { sc.spawn(|| loop {
        let k = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst); if k >= lines.len() { break; }
        let Ok(sp) = serde_json::from_str::<Value>(&lines[k]) else { continue };
        let name = sp["name"].as_str().map(|s| s.to_string()).unwrap_or(format!("line {}", k + 1));
        if done.contains(&name) { continue; }
        let mut h: u64 = 0xcbf29ce484222325; for c in name.bytes() { h ^= c as u64; h = h.wrapping_mul(0x100000001b3); }      // FNV-1a of the name
        let r = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let b = crate::turntest::new_battle(dex, reg, &sp["state"], Mode::Real);
            eval_one(&b, cfg, &sp, h ^ 0xE7A1, nseeds, top) }));
        let mut row = match r {
            Ok(v) => v,
            Err(e) => json!({"error": e.downcast_ref::<String>().cloned().or(e.downcast_ref::<&str>().map(|s| s.to_string())).unwrap_or("panic".into())}),
        };
        let o = row.as_object_mut().unwrap(); o.insert("name".into(), json!(name));
        for key in ["turn", "side", "perish", "approx"] { if let Some(v) = sp.get(key) { o.insert(key.into(), v.clone()); } }
        { let mut f = out.lock().unwrap(); writeln!(f, "{}", row).unwrap(); f.flush().unwrap(); }
        let n = nd.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
        eprintln!("{} / {}: {} {}", n, lines.len() - done.len().min(lines.len()), name, if row.get("error").is_some() { "ERROR" } else { "" });
    }); } });
    eprintln!("{} positions in {:?}", nd.load(std::sync::atomic::Ordering::SeqCst), t0.elapsed());
}
