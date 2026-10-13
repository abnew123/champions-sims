//! Decision review for recorded games. From a position rebuilt by native/spot_starts.js, every joint action of mine (switches included)
//! meets the opponent's likely replies (the one-turn equilibrium's support plus each candidate's best reply); every cell is played out
//! to the end of the game by the 2v2 planner on both sides (bench Pokemon come in when something faints; no voluntary switches after
//! the first turn), N times with different seeds. The cell matrix is then solved: each of my actions is scored against the opponent's
//! equilibrium reply mix and against its worst case.
//!   champ spot <engine_data.json> <spots.jsonl> <out.json> [threads=3] [playouts=8]
use crate::battle::*;
use crate::plan::*;
use crate::prng::{Mode, Prng};
use crate::sim::PChoice;
use crate::state::*;
use serde_json::{json, Value};

const MAXTURN: usize = 15;
const NS: usize = 2;          // planning seeds per cell, as in the 2v2 runs (EG_SEEDS=2)

/// splitmix64 -> a Gen5 seed (four u16 words)
pub(crate) fn seed4(x: u64) -> [u16; 4] {
    let mut z = x.wrapping_add(0x9E3779B97F4A7C15); z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9); z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB); z ^= z >> 31;
    [z as u16, (z >> 16) as u16, (z >> 32) as u16, (z >> 48) as u16]
}
/// one switch request's options for side s: every assignment of candidates to its open slots, a slot's candidates being the bench, or
/// the fainted Pokemon for a slot with Revival Blessing's condition (2026-10-13)
pub(crate) fn switch_opts(b: &Battle, s: u8, req_s: &[bool; 2]) -> Vec<[PChoice; 2]> {
    let slots: Vec<usize> = (0..2).filter(|i| req_s[*i]).collect();
    let cands = |k: usize| if b.revive_slot(s, k) { b.fainted_positions(s) } else { bench(b, s) };
    let mut o: Vec<[PChoice; 2]> = vec![];
    match slots.len() {
        0 => o.push([PChoice::Pass; 2]),
        1 => { for p in cands(slots[0]) { let mut c = [PChoice::Pass; 2]; c[slots[0]] = PChoice::Switch(p); o.push(c); } }
        _ => { let (c0, c1) = (cands(slots[0]), cands(slots[1]));
               for &p in &c0 { for &q in &c1 { if p != q { let mut c = [PChoice::Pass; 2]; c[slots[0]] = PChoice::Switch(p); c[slots[1]] = PChoice::Switch(q); o.push(c); } } }
               if !b.revive_slot(s, slots[0]) && !b.revive_slot(s, slots[1]) && c0.len() == 1 { for &k in &slots { let mut c = [PChoice::Pass; 2]; c[k] = PChoice::Switch(c0[0]); o.push(c); } } }
    }
    if o.is_empty() { o.push([PChoice::Pass; 2]); }
    o
}
pub(crate) fn bench(b: &Battle, s: u8) -> Vec<u8> {
    let mut v: Vec<u8> = b.sides[s as usize].pokemon.iter().filter(|p| !p.fainted && p.position >= 2).map(|p| p.position).collect(); v.sort(); v
}
/// joint actions for side s; with `sw`, each active Pokemon may also switch to a bench Pokemon (not both to the same one)
pub(crate) fn joint(b: &mut Battle, s: u8, sw: bool) -> Vec<[PChoice; 2]> {
    let bn = bench(b, s);
    let opts: Vec<Vec<PChoice>> = (0..2).map(|i| {
        let mut o = slot_options(b, s, i);
        if sw { if let Some(pi) = b.sides[s as usize].active[i] { let p = b.p((s, pi)); if !p.fainted && !p.trapped { for &pos in &bn { o.push(PChoice::Switch(pos)); } } } }
        o }).collect();
    let mut out = vec![];
    for x in &opts[0] { for y in &opts[1] {
        if let (PChoice::Switch(a), PChoice::Switch(c)) = (x, y) { if a == c { continue; } }
        // one Mega Evolution per side, as joint_options
        let y2 = match (x, y) { (PChoice::Move(_, _, true), PChoice::Move(k, t, true)) => PChoice::Move(*k, *t, false), _ => *y };
        let c = [*x, y2];
        if !out.contains(&c) && valid(b, s, &c) { out.push(c); }
    } }
    out
}
/// answer pending switch requests (faint replacements, U-turn): both sides' assignments of bench Pokemon to the open slots form a
/// small matrix game on the position value; `rng` None takes each side's most likely equilibrium choice, else samples it
pub(crate) fn resolve_switches(b: &mut Battle, cfg: &Cfg, rng: Option<&mut f64>) { resolve_switches_h(b, cfg, rng, None, 0) }
/// with a human on side 0 (champ play): the human picks side 0's replacements, the planner answers with its best replacement against them
pub(crate) fn resolve_switches_h(b: &mut Battle, cfg: &Cfg, mut rng: Option<&mut f64>, mut human: Option<&mut crate::human::Human>, turn: usize) {
    let mut guard = 0;
    while b.request_switch && !b.ended && guard < 8 {
        guard += 1;
        let req = b.switch_request();
        let opts: Vec<Vec<[PChoice; 2]>> = (0..2u8).map(|s| switch_opts(b, s, &req[s as usize])).collect();
        let (i, j) = if let Some(h) = human.as_deref_mut() {
            let i = h.choose_switch(b, turn, &opts[0]);
            let j = if opts[1].len() <= 1 { 0 } else {
                let vals: Vec<f64> = opts[1].iter().map(|y| { let mut c = b.clone(); c.choose_switches([opts[0][i], *y]); let v = value2(&mut c, cfg); if crate::plan::two_values(cfg) { v.1 } else { v.0 } }).collect();
                (0..vals.len()).min_by(|&a, &c| vals[a].partial_cmp(&vals[c]).unwrap()).unwrap() };
            (i, j)
        } else if opts[0].len() * opts[1].len() == 1 { (0, 0) } else {
            let a2: Vec<Vec<(f64, f64)>> = opts[0].iter().map(|x| opts[1].iter().map(|y| { let mut c = b.clone(); c.choose_switches([*x, *y]); value2(&mut c, cfg) }).collect()).collect();
            let a: Vec<Vec<f64>> = a2.iter().map(|r| r.iter().map(|v| v.0).collect()).collect();
            let (x, mut y) = nash(&a, 200);
            if crate::plan::two_values(cfg) { let ab: Vec<Vec<f64>> = a2.iter().map(|r| r.iter().map(|v| v.1).collect()).collect(); y = nash(&ab, 200).1; }   // each side by its own value
            let am = |p: &[f64]| p.iter().enumerate().fold((0, -1.0), |m, (k, v)| if *v > m.1 { (k, *v) } else { m }).0;
            match rng.as_deref_mut() { Some(r) => (sample(&x, r), sample(&y, r)), None => (am(&x), am(&y)) }
        };
        b.choose_switches([opts[0][i], opts[1][j]]);
    }
}
/// one switch request's replacement equilibrium, as resolve_switches_h settles it without rng: both sides' options (every assignment of
/// bench Pokemon to the open slots), the matrix game on the position value, each side's most likely choice
fn eq_switch_pick(b: &mut Battle, cfg: &Cfg, req: &[[bool; 2]; 2]) -> [[PChoice; 2]; 2] {
    let opts: Vec<Vec<[PChoice; 2]>> = (0..2u8).map(|s| switch_opts(b, s, &req[s as usize])).collect();
    if opts[0].len() * opts[1].len() == 1 { return [opts[0][0], opts[1][0]]; }
    let a2: Vec<Vec<(f64, f64)>> = opts[0].iter().map(|x| opts[1].iter().map(|y| { let mut c = b.clone(); c.choose_switches([*x, *y]); value2(&mut c, cfg) }).collect()).collect();
    let a: Vec<Vec<f64>> = a2.iter().map(|r| r.iter().map(|v| v.0).collect()).collect();
    let (x, mut y) = nash(&a, 200);
    if crate::plan::two_values(cfg) { let ab: Vec<Vec<f64>> = a2.iter().map(|r| r.iter().map(|v| v.1).collect()).collect(); y = nash(&ab, 200).1; }
    let am = |p: &[f64]| p.iter().enumerate().fold((0, -1.0), |m, (k, v)| if *v > m.1 { (k, *v) } else { m }).0;
    [opts[0][am(&x)], opts[1][am(&y)]]
}
/// pending switches settled with the replacements a side actually made (2026-10-12, the Eval bar's luck measure: the actual cell's
/// samples used the replacement equilibrium, so a player's own choice of replacement read as luck). `forced[s]` lists side s's
/// replacements in the order the log showed them (base species ids); each switch request takes the next ones that are legal for that
/// side, and a side with none left (or none legal) falls back to its equilibrium choice. Returns how many replacements were forced.
pub(crate) fn resolve_switches_forced(b: &mut Battle, cfg: &Cfg, forced: &mut [std::collections::VecDeque<String>; 2]) -> usize {
    let base = |x: &str| -> String { let t = crate::dex::to_id(x); match t.find("mega") { Some(k) if k > 0 => t[..k].to_string(), _ => t } };
    let mut n = 0; let mut guard = 0;
    while b.request_switch && !b.ended && guard < 8 {
        guard += 1;
        let req = b.switch_request();
        let mut pick: [Option<[PChoice; 2]>; 2] = [None, None];
        for s in 0..2u8 {
            let slots: Vec<usize> = (0..2).filter(|i| req[s as usize][*i]).collect();
            if slots.is_empty() { pick[s as usize] = Some([PChoice::Pass; 2]); continue; }
            let bn = bench(b, s); let mut c = [PChoice::Pass; 2]; let mut used: Vec<u8> = vec![]; let mut took = 0;
            for &k in &slots {
                let Some(want) = forced[s as usize].front().cloned() else { break };
                let Some(&p) = bn.iter().find(|&&p| !used.contains(&p) && base(b.p((s, p)).species) == base(&want)) else { break };
                c[k] = PChoice::Switch(p); used.push(p); forced[s as usize].pop_front(); took += 1;
            }
            if took == slots.len() || (took > 0 && bn.len() == took) { pick[s as usize] = Some(c); n += took; }
        }
        if pick[0].is_none() || pick[1].is_none() {
            // a side without a forced choice takes its choice in this request's replacement equilibrium (as resolve_switches_h with no
            // rng: each side's most likely option), the other side's forced one kept
            let eq = eq_switch_pick(b, cfg, &req);
            for s in 0..2 { if pick[s].is_none() { pick[s] = Some(eq[s]); } }
        }
        b.choose_switches([pick[0].unwrap(), pick[1].unwrap()]);
    }
    n
}
/// one-turn matrix (each cell: the turn played with NS planning seeds, switches resolved greedily, position value)
fn one_turn(b: &Battle, cfg: &Cfg, mine: &[[PChoice; 2]], theirs: &[[PChoice; 2]], cseeds: &[[u16; 4]]) -> Vec<Vec<f64>> {
    mine.iter().map(|r| theirs.iter().map(|c| {
        let mut s = 0.0;
        for cs in cseeds { let mut x = b.clone(); x.prng = Prng::gen5(*cs); x.run_turn([*r, *c]); resolve_switches(&mut x, cfg, None); s += value(&mut x, cfg); }
        s / cseeds.len() as f64 }).collect()).collect()
}
/// the planner's game from here on (both sides on the one-turn equilibrium, as play_game) with forced replacements resolved
fn playout(start: &Battle, cfg: &Cfg, mut rng: f64, key: u64) -> f64 {
    let mut b = start.clone(); let mut turn = 1;
    while !b.ended && turn <= MAXTURN {
        let mine = joint(&mut b, 0, false); let theirs = joint(&mut b, 1, false);
        if mine.is_empty() || theirs.is_empty() { break; }
        let cs: Vec<[u16; 4]> = (0..NS).map(|k| seed4(key ^ ((turn as u64) << 40) ^ ((k as u64) << 52))).collect();
        let m = one_turn(&b, cfg, &mine, &theirs, &cs);
        let (x, y) = nash(&m, 400);
        let i = sample(&x, &mut rng); let j = sample(&y, &mut rng);
        b.prng = Prng::gen5(seed4(key.wrapping_mul(31) ^ turn as u64));
        b.run_turn([mine[i], theirs[j]]);
        resolve_switches(&mut b, cfg, Some(&mut rng));
        turn += 1;
    }
    value(&mut b, cfg)
}
/// PLAY_CLOCK_TURNS (default 100): the turn after which a human's game, and the concede check's playouts, are decided as the game's
/// timer decides them (clock_winner)
pub(crate) fn clock_turns() -> usize { static F: std::sync::OnceLock<usize> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("PLAY_CLOCK_TURNS").ok().and_then(|x| x.parse().ok()).unwrap_or(100)) }
/// the timer's tiebreak: more Pokemon left, then the higher share of HP left (sum of hp / maxhp over the living), then more HP; None = tied
pub(crate) fn clock_winner(b: &Battle) -> Option<u8> {
    let stat = |s: usize| { let alive: Vec<&crate::state::Pokemon> = b.sides[s].pokemon.iter().filter(|p| !p.fainted && p.hp > 0).collect();
        (alive.len(), alive.iter().map(|p| p.hp as f64 / p.maxhp.max(1) as f64).sum::<f64>(), alive.iter().map(|p| p.hp).sum::<i64>()) };
    let (a, b2) = (stat(0), stat(1));
    if a.0 != b2.0 { return Some(if a.0 > b2.0 { 0 } else { 1 }); }
    if (a.1 - b2.1).abs() > 1e-9 { return Some(if a.1 > b2.1 { 0 } else { 1 }); }
    if a.2 != b2.2 { return Some(if a.2 > b2.2 { 0 } else { 1 }); }
    None
}
/// the planner against itself from here to the end of the game (switches allowed, up to `max_turns` turns, then the clock decides):
/// 1 = side 0 won, 0 = lost, 0.5 = tied; for the play page's concede check (an endgame the one-turn value cannot see: PP, Struggle, a slow bleed)
pub(crate) fn playout_long(start: &Battle, cfg: &Cfg, mut rng: f64, key: u64, max_turns: usize) -> f64 {
    let mut b = start.clone(); let mut turn = 1;
    while !b.ended && turn <= max_turns {
        let mine = joint(&mut b, 0, true); let theirs = joint(&mut b, 1, true);
        if mine.is_empty() || theirs.is_empty() { break; }
        let cs: Vec<[u16; 4]> = (0..NS).map(|k| seed4(key ^ ((turn as u64) << 40) ^ ((k as u64) << 52))).collect();
        let m = one_turn(&b, cfg, &mine, &theirs, &cs);
        let (x, y) = nash(&m, 400);
        let i = sample(&x, &mut rng); let j = sample(&y, &mut rng);
        b.prng = Prng::gen5(seed4(key.wrapping_mul(31) ^ turn as u64));
        b.run_turn([mine[i], theirs[j]]);
        resolve_switches(&mut b, cfg, Some(&mut rng));
        turn += 1;
    }
    if b.ended { match b.winner { Some(Some(0)) => 1.0, Some(Some(_)) => 0.0, _ => 0.5 } } else { match clock_winner(&b) { Some(0) => 1.0, Some(_) => 0.0, None => 0.5 } }
}
pub(crate) fn label(b: &Battle, s: u8, c: &[PChoice; 2]) -> String {
    let name = |m: MonRef| b.dex.species.get(b.p(m).species).map(|x| x.name).unwrap_or("?").to_string();
    (0..2).filter_map(|i| {
        let pi = b.sides[s as usize].active[i]?; let m = (s, pi); if b.p(m).fainted { return None; }
        let what = match c[i] {
            PChoice::Move(k, t, mega) => {
                // a locked turn's request has one entry (the locked move, or the recharge pseudo-move), so k does not index the move slots
                let p = b.p(m);
                let locked: Option<&str> = if crate::state::find(&p.volatiles, "mustrecharge").is_some() { Some("Recharge") }
                    else { ["twoturnmove", "lockedmove"].iter().find_map(|v| crate::state::find(&p.volatiles, v).and_then(|st| st.get("move").and_then(|x| x.s()))).map(|mid| b.dex.mv(mid).tmpl.name) };
                let mv = match locked { Some(n) => n, None => { let mid = p.move_slots.get(k).map(|x| x.id).unwrap_or("?"); if mid == "?" { "?" } else { b.dex.mv(mid).tmpl.name } } };
                let tgt = if t > 0 { b.sides[1 - s as usize].active[t as usize - 1].map(|x| format!(" -> {}", name((1 - s, x)))).unwrap_or_default() }
                          else if t < 0 { " -> ally".to_string() } else { String::new() };
                format!("{}{}{}", mv, tgt, if mega { " (Mega)" } else { "" })
            }
            PChoice::Switch(p) => format!("switch to {}", b.mon_at_position(s, p).map(name).unwrap_or("?".into())),
            PChoice::Pass => "pass".into(),
        };
        Some(format!("{}: {}", name(m), what)) }).collect::<Vec<_>>().join(" | ")
}

pub fn main(args: &[String]) {
    let (dex, reg) = crate::turntest::load_all(&args[0]);
    let cfg: &'static Cfg = Box::leak(Box::new(load_cfg(&std::env::var("GRID_DIR").unwrap_or("../../mxtr".into()))));
    let threads: usize = args.get(3).and_then(|x| x.parse().ok()).unwrap_or(3);
    let n: usize = args.get(4).and_then(|x| x.parse().ok()).unwrap_or(8);
    let rmax: usize = std::env::var("SPOT_ROWS").ok().and_then(|x| x.parse().ok()).unwrap_or(14);
    let mut report = vec![];
    for (si, line) in std::fs::read_to_string(&args[1]).unwrap().lines().enumerate() {
        let sp: Value = serde_json::from_str(line).unwrap();
        let t0 = std::time::Instant::now();
        let mut b = crate::turntest::new_battle(dex, reg, &sp["state"], Mode::Real);
        let mine = joint(&mut b, 0, true); let theirs = joint(&mut b, 1, true);
        let actual: [PChoice; 2] = std::array::from_fn(|i| { let a = &sp["actual"][i];
            if a[0].as_str() == Some("switch") { PChoice::Switch(b.p((0, a[1].as_u64().unwrap() as u8)).position) }
            else { PChoice::Move(a[0].as_u64().unwrap() as usize, a[1].as_i64().unwrap(), a[2].as_bool().unwrap()) } });
        let ai = mine.iter().position(|c| *c == actual).unwrap_or_else(|| panic!("{}: actual choice {:?} not among my options", sp["name"], actual));
        let parse = |a: &Value, s: u8, b: &Battle| -> PChoice { if a[0].as_str() == Some("switch") { PChoice::Switch(b.p((s, a[1].as_u64().unwrap() as u8)).position) }
            else { PChoice::Move(a[0].as_u64().unwrap() as usize, a[1].as_i64().unwrap(), a[2].as_bool().unwrap()) } };
        let their_actual: Option<usize> = sp["their_actual"].as_array().map(|a| { let c: [PChoice; 2] = std::array::from_fn(|i| parse(&a[i], 1, &b));
            theirs.iter().position(|x| *x == c).unwrap_or_else(|| panic!("{}: their actual choice {:?} not among their options", sp["name"], c)) });
        // stage 1: the one-turn game picks the cells worth playing out
        let cs: Vec<[u16; 4]> = (0..NS).map(|k| seed4(0xABC0 + k as u64)).collect();
        let a1 = one_turn(&b, cfg, &mine, &theirs, &cs);
        let (x0, y0) = nash(&a1, 400);
        let vs_y0: Vec<f64> = a1.iter().map(|r| r.iter().zip(&y0).map(|(v, p)| v * p).sum()).collect();
        let mut order: Vec<usize> = (0..mine.len()).collect(); order.sort_by(|i, j| vs_y0[*j].partial_cmp(&vs_y0[*i]).unwrap());
        let mut rows: Vec<usize> = order.iter().take(rmax).copied().collect();
        for (i, p) in x0.iter().enumerate() { if *p > 0.01 && !rows.contains(&i) { rows.push(i); } }
        if !rows.contains(&ai) { rows.push(ai); }
        let mut cols: Vec<usize> = (0..theirs.len()).filter(|j| y0[*j] > 0.01).collect();
        for &i in &rows { let br = (0..theirs.len()).min_by(|j, k| a1[i][*j].partial_cmp(&a1[i][*k]).unwrap()).unwrap(); if !cols.contains(&br) { cols.push(br); } }
        if let Some(j) = their_actual { if !cols.contains(&j) { cols.push(j); } }
        eprintln!("{}: {} x {} options; playing out {} x {} cells x {} games", sp["name"], mine.len(), theirs.len(), rows.len(), cols.len(), n);
        // stage 2: play every kept cell out to the end, n games each
        let tasks: Vec<(usize, usize, usize)> = rows.iter().enumerate().flat_map(|(ri, _)| cols.iter().enumerate().flat_map(move |(ci, _)| (0..n).map(move |g| (ri, ci, g)))).collect();
        let next = std::sync::atomic::AtomicUsize::new(0);
        let res = std::sync::Mutex::new(vec![vec![vec![0.0; n]; cols.len()]; rows.len()]);
        std::thread::scope(|sc| { for _ in 0..threads { sc.spawn(|| loop {
            let k = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst); if k >= tasks.len() { break; }
            let (ri, ci, g) = tasks[k];
            let key = ((si as u64) << 56) ^ ((g as u64) << 20) ^ 0x5EED;   // same seeds for every cell's g-th game
            let mut c = b.clone(); c.prng = Prng::gen5(seed4(key));
            let mut rng = (seed4(key ^ 1)[0] as f64) * 32768.0 + 12345.0;
            c.run_turn([mine[rows[ri]], theirs[cols[ci]]]);
            resolve_switches(&mut c, cfg, Some(&mut rng));
            let v = if c.ended { value(&mut c, cfg) } else { playout(&c, cfg, rng, key ^ 0xF00D) };
            res.lock().unwrap()[ri][ci][g] = v;
        }); } });
        let res = res.into_inner().unwrap();
        let m: Vec<Vec<f64>> = res.iter().map(|r| r.iter().map(|c| c.iter().sum::<f64>() / n as f64).collect()).collect();
        let (x, y) = nash(&m, 2000);
        let game_value: f64 = (0..rows.len()).map(|i| x[i] * (0..cols.len()).map(|j| m[i][j] * y[j]).sum::<f64>()).sum();
        // how each of my options did against what they actually clicked (when the spot says)
        let vs_actual: Option<usize> = their_actual.and_then(|j| cols.iter().position(|&c| c == j));
        let mut out_rows: Vec<Value> = rows.iter().enumerate().map(|(ri, &i)| {
            let v: f64 = (0..cols.len()).map(|j| m[ri][j] * y[j]).sum();
            let worst = (0..cols.len()).map(|j| m[ri][j]).fold(1.0f64, f64::min);
            // standard error of v from the n games per cell (games ~ Bernoulli-ish)
            let se = (0..cols.len()).map(|j| { let g = &res[ri][j]; let mu = m[ri][j]; let s2 = g.iter().map(|z| (z - mu).powi(2)).sum::<f64>() / (n.max(2) - 1) as f64; y[j] * y[j] * s2 / n as f64 }).sum::<f64>().sqrt();
            json!({"choice": label(&b, 0, &mine[i]), "v": v, "se": se, "worst": worst, "eq_weight": x[ri], "one_turn": vs_y0[i], "actual": i == ai,
                   "vs_their_actual": vs_actual.map(|cj| m[ri][cj])})
        }).collect();
        out_rows.sort_by(|p, q| q["v"].as_f64().unwrap().partial_cmp(&p["v"].as_f64().unwrap()).unwrap());
        let replies: Vec<Value> = cols.iter().enumerate().filter(|(cj, &j)| y[*cj] > 0.01 || Some(j) == their_actual)
            .map(|(cj, &j)| json!({"choice": label(&b, 1, &theirs[j]), "p": y[cj], "actual": Some(j) == their_actual})).collect();
        eprintln!("{}: done in {:.0?}", sp["name"], t0.elapsed());
        report.push(json!({"name": sp["name"], "note": sp["note"], "options": [mine.len(), theirs.len()], "cells": [rows.len(), cols.len()], "games_per_cell": n,
                           "value": game_value, "rows": out_rows, "their_replies": replies}));
        std::fs::write(&args[2], serde_json::to_string_pretty(&report).unwrap()).unwrap();
    }
}
