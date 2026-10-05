//! Full 4v4 battles (2026-10-03, first version). Starting positions come from native/battle_starts.js: team preview resolved (my lead +
//! back two from a plan, their lead + back two from the replay model), turn 1 not yet played. Every turn both sides choose by the
//! one-turn matrix game of the 2v2 planner, with mid-game switching at one layer: each side's own matrix offers its own voluntary
//! switches but assumes the opponent stays in (my matrix = my moves+switches x their moves; theirs = my moves x their moves+switches).
//! The two matrices share the no-switch block, so each cell is computed once. Faint replacements: the replacement matrix game
//! (spot.rs resolve_switches). Value: the planner's position value (EG_VALUE; fitted on 2v2 endgames, so not calibrated for 4v4).
//!   champ battle <engine_data.json> <starts.jsonl> <outdir> [threads=3]
use crate::battle::*;
use crate::plan::*;
use crate::prng::{Mode, Prng};
use crate::sim::PChoice;
use crate::spot::{joint, label, resolve_switches, seed4};
use crate::state::*;
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap};

const MAXTURN: usize = 25;
const STALL_MAXTURN: usize = 250;   // a game where neither side can deal damage (e.g. attack-less Indeedee-F vs Indeedee-F) plays on to PP exhaustion

/// can side s still deal damage: some living Pokemon has a damaging move with PP left, or has no PP left at all (Struggle)
fn can_damage(b: &Battle, s: u8) -> bool {
    b.sides[s as usize].pokemon.iter().filter(|p| !p.fainted).any(|p|
        p.move_slots.iter().any(|sl| sl.pp > 0 && b.dex.mv(sl.id).tmpl.category != "Status") || p.move_slots.iter().all(|sl| sl.pp <= 0))
}
fn dp2_log() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("DP2_LOG").is_ok()) }
/// DP2_SIDE=0|1 (champ-battle-v12): run the two-turn Protect check for that side only
fn dp2_side() -> Option<u8> { static F: std::sync::OnceLock<Option<u8>> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("DP2_SIDE").ok().and_then(|x| x.parse().ok())) }
fn dp2() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("DP2").is_ok()) }
/// DP2: side 0's value of a position after one more turn played as a small matrix game (reduced_options for both sides, one seed)
fn next_value(b: &Battle, cfg: &Cfg, seed: [u16; 4], s: u8) -> f64 {
    let value = |x: &mut Battle, cfg: &Cfg| { let v = value2(x, cfg); if s == 0 { v.0 } else { v.1 } };
    let mut z = b.clone();
    if z.ended { return value(&mut z, cfg); }
    let o: Vec<Vec<[PChoice; 2]>> = (0..2u8).map(|s| rjoint(&mut z, s)).collect();
    if o[0].is_empty() || o[1].is_empty() { return value(&mut z, cfg); }
    let a: Vec<Vec<f64>> = o[0].iter().map(|p| o[1].iter().map(|q| {
        let mut w = b.clone(); w.prng = Prng::gen5(seed); w.run_turn([*p, *q]); resolve_switches(&mut w, cfg, None); value(&mut w, cfg) }).collect()).collect();
    let (p, q) = nash(&a, 200);
    let mut v = 0.0; for i in 0..a.len() { for j in 0..a[0].len() { v += p[i] * q[j] * a[i][j]; } } v
}
fn dp2_sw() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("DP2_SW").is_ok()) }
/// the second turn's options per side: reduced_options for each active Pokemon, plus (DP2_SW=1, champ-battle-v9) its switches to the bench
fn rjoint(b: &mut Battle, s: u8) -> Vec<[PChoice; 2]> {
    let bn = crate::spot::bench(b, s);
    let o: Vec<Vec<PChoice>> = (0..2).map(|i| {
        let mut v = reduced_options(b, s, i);
        if dp2_sw() { if let Some(pi) = b.sides[s as usize].active[i] { let p = b.p((s, pi)); if !p.fainted && !p.trapped { for &pos in &bn { v.push(PChoice::Switch(pos)); } } } }
        v }).collect();
    let mut out = vec![];
    for x in &o[0] { for y in &o[1] {
        let y2 = match (x, y) { (PChoice::Move(_, _, true), PChoice::Move(k, t, true)) => PChoice::Move(*k, *t, false), _ => *y };
        if let (PChoice::Switch(a), PChoice::Switch(c)) = (x, &y2) { if a == c { continue; } }
        let c = [*x, y2]; if !out.contains(&c) && valid(b, s, &c) { out.push(c); }
    } }
    out
}
fn ns() -> usize { std::env::var("BATTLE_NS").ok().and_then(|x| x.parse().ok()).unwrap_or(2) }

/// switch_slots / slot_decisions: active Pokemon that switched voluntarily / active Pokemon that could have (bench available, not trapped)
struct Out { v: f64, unsupported: Vec<String>, feats: Vec<Vec<f64>>, turns: usize, tr_turns: usize, tr_by: [bool; 3], switches: [usize; 2], slot_decisions: [usize; 2], switch_slots: [usize; 2], log: Vec<String>, states: Vec<Value>, dp2: [usize; 4], dplog: Vec<Value> }

fn play(start: &Battle, cfg: &Cfg, mut rng: f64, key: u64, keep_log: bool) -> Out {
    let mut b = start.clone(); let mut turn = 1;
    let (mut tr_turns, mut tr_by, mut switches, mut log) = (0, [false; 3], [0usize; 2], vec![]);
    let (mut slot_decisions, mut switch_slots) = ([0usize; 2], [0usize; 2]);
    let mut uns: Vec<String> = vec![]; let mut dp2s = [0usize; 4]; let mut dplog: Vec<Value> = vec![];
    let want_states = std::env::var("BATTLE_TURNS").is_ok(); let mut states: Vec<Value> = vec![];
    let want_feats = std::env::var("BATTLE_FEATS").is_ok(); let mut fx: Vec<Vec<f64>> = vec![];
    while !b.ended && (turn <= MAXTURN || (turn <= STALL_MAXTURN && !can_damage(&b, 0) && !can_damage(&b, 1))) {
        let sw = std::env::var("BATTLE_NOSWITCH").is_err();   // BATTLE_NOSWITCH=1: control run, Pokemon only come in when something faints
        let msw = joint(&mut b, 0, sw); let tsw = joint(&mut b, 1, sw);
        if msw.is_empty() || tsw.is_empty() { break; }
        if want_feats { fx.push(feats(&mut b, cfg)); }   // position at the start of the turn, for refitting the value on 4v4 games
        let no_sw = |c: &[PChoice; 2]| !c.iter().any(|x| matches!(x, PChoice::Switch(_)));
        let mns: Vec<usize> = (0..msw.len()).filter(|i| no_sw(&msw[*i])).collect();
        let tns: Vec<usize> = (0..tsw.len()).filter(|j| no_sw(&tsw[*j])).collect();
        let cs: Vec<[u16; 4]> = (0..ns()).map(|k| seed4(key ^ ((turn as u64) << 40) ^ ((k as u64) << 52))).collect();
        let mut cache: HashMap<(usize, usize), (f64, f64)> = HashMap::new();
        // each cell as (side 0's value, side 1's value); the two differ only with EG_VALUE_B
        let mut cell2 = |i: usize, j: usize, b: &Battle| -> (f64, f64) {
            *cache.entry((i, j)).or_insert_with(|| {
                let mut s = (0.0, 0.0);
                for c in &cs { let mut x = b.clone(); x.prng = Prng::gen5(*c); x.run_turn([msw[i], tsw[j]]); resolve_switches(&mut x, cfg, None); let v = value2(&mut x, cfg); s.0 += v.0; s.1 += v.1; }
                (s.0 / cs.len() as f64, s.1 / cs.len() as f64) })
        };
        // my matrix: all my options (moves + switches) vs their non-switch options
        let am: Vec<Vec<f64>> = (0..msw.len()).map(|i| tns.iter().map(|&j| cell2(i, j, &b).0).collect()).collect();
        // their matrix: my non-switch options vs all their options
        let at: Vec<Vec<f64>> = mns.iter().map(|&i| (0..tsw.len()).map(|j| cell2(i, j, &b).1).collect()).collect();
        let (mut x, _) = if tns.is_empty() { (vec![1.0 / msw.len() as f64; msw.len()], vec![]) } else { nash(&am, 400) };
        let (_, mut y) = if mns.is_empty() { (vec![], vec![1.0 / tsw.len() as f64; tsw.len()]) } else { nash(&at, 400) };
        let (mut xcols, mut yrows) = (tns.clone(), mns.clone());
        // BATTLE_ANTICIPATE=1 (second pass): each side's matrix also gets the switches the other side actually plays (weight > 2% in its
        // one-layer mix), so a side plans against the opponent's real switches without searching every switch pair
        if std::env::var("BATTLE_ANTICIPATE").is_ok() {
            let isw: Vec<usize> = (0..msw.len()).filter(|i| !no_sw(&msw[*i]) && x[*i] > 0.02).collect();
            let jsw: Vec<usize> = (0..tsw.len()).filter(|j| !no_sw(&tsw[*j]) && y[*j] > 0.02).collect();
            if !jsw.is_empty() {
                let cols: Vec<usize> = tns.iter().copied().chain(jsw.iter().copied()).collect();
                let am2: Vec<Vec<f64>> = (0..msw.len()).map(|i| cols.iter().map(|&j| cell2(i, j, &b).0).collect()).collect();
                x = nash(&am2, 400).0; xcols = cols;
            }
            if !isw.is_empty() {
                let rows: Vec<usize> = mns.iter().copied().chain(isw.iter().copied()).collect();
                let at2: Vec<Vec<f64>> = rows.iter().map(|&i| (0..tsw.len()).map(|j| cell2(i, j, &b).1).collect()).collect();
                y = nash(&at2, 400).1; yrows = rows;
            }
        }
        // DP2=1 (champ-battle-v8, 2026-10-04): two-turn check of a second Protect in a row. For each active Pokemon that Protected
        // successfully last turn (stall counter up) and still has Protect weight in its side's mix: that side's best option (one-turn value
        // against the other side's mix) that Protects again, the best that uses another move, and the best that switches it out are each
        // played against the other side's likeliest replies (up to 4, >= 90% of its mix) and scored after one more turn, a small matrix
        // game (reduced_options: three strongest hits + Protect per Pokemon, one seed). If Protecting again comes out worse than the best
        // alternative, that Pokemon's Protect-again options are dropped and the side's mix is re-solved on the same rows / columns.
        if dp2() && !xcols.is_empty() && !yrows.is_empty() {
            let mut pruned: [Vec<usize>; 2] = [vec![], vec![]];
            for s in 0..2u8 { if dp2_side().map(|x| x != s).unwrap_or(false) { continue; } for k in 0..2usize {
                let Some(pi) = b.sides[s as usize].active[k] else { continue }; let m = (s, pi);
                if b.p(m).fainted || find(&b.p(m).volatiles, "stall").is_none() { continue; }
                let opts: Vec<[PChoice; 2]> = if s == 0 { msw.clone() } else { tsw.clone() };
                let stall_mv = |c: &PChoice| -> bool { if let PChoice::Move(sl, _, _) = c { b.dex.mv(b.p(m).move_slots[*sl].id).tmpl.stalling_move } else { false } };
                let prot: Vec<usize> = (0..opts.len()).filter(|&i| stall_mv(&opts[i][k]) && !pruned[s as usize].contains(&i)).collect();
                let pmass: f64 = prot.iter().map(|&i| if s == 0 { x[i] } else { y[i] }).sum();
                if prot.is_empty() || pmass < 0.01 { continue; }
                dp2s[2 * s as usize] += 1;
                let opp: Vec<f64> = if s == 0 { y.clone() } else { x.clone() };
                let mut ord: Vec<usize> = (0..opp.len()).collect(); ord.sort_by(|a, c| opp[*c].partial_cmp(&opp[*a]).unwrap());
                let mut resp: Vec<(usize, f64)> = vec![]; let mut acc = 0.0;
                for &j in &ord { if resp.len() >= 4 || acc >= 0.9 || opp[j] <= 0.0 { break; } resp.push((j, opp[j])); acc += opp[j]; }
                let tot: f64 = resp.iter().map(|r| r.1).sum(); if tot <= 0.0 { continue; } for r in resp.iter_mut() { r.1 /= tot; }
                let is_sw = |c: &PChoice| matches!(c, PChoice::Switch(_));
                let others: Vec<usize> = (0..opts.len()).filter(|&i| !stall_mv(&opts[i][k]) && !is_sw(&opts[i][k]) && !pruned[s as usize].contains(&i)).collect();
                let sws: Vec<usize> = (0..opts.len()).filter(|&i| is_sw(&opts[i][k]) && !pruned[s as usize].contains(&i)).collect();
                let mut best = [None::<usize>; 3]; let mut best1 = [None::<f64>; 3];
                for (gi, g) in [&prot, &others, &sws].iter().enumerate() {
                    let mut bv: Option<(usize, f64)> = None;
                    for &i in g.iter() {
                        let mut v = 0.0; for &(j, w) in &resp { v += w * if s == 0 { cell2(i, j, &b).0 } else { cell2(j, i, &b).1 }; }
                        let v = if s == 0 { v } else { -v };
                        if bv.map(|z| v > z.1).unwrap_or(true) { bv = Some((i, v)); }
                    }
                    best[gi] = bv.map(|z| z.0); best1[gi] = bv.map(|z| if s == 0 { z.1 } else { 1.0 + z.1 });
                }
                let Some(bp) = best[0] else { continue };
                let alts: Vec<usize> = best[1..].iter().flatten().copied().collect();
                if alts.is_empty() { continue; }
                let sa = seed4(key ^ ((turn as u64) << 40) ^ (0xD2u64 << 52) ^ ((s as u64) << 36) ^ ((k as u64) << 32));
                let sb = seed4(key ^ ((turn as u64) << 40) ^ (0xD3u64 << 52) ^ ((s as u64) << 36) ^ ((k as u64) << 32));
                let v2 = |i: usize| -> f64 { resp.iter().map(|&(j, w)| {
                    let mut z = b.clone(); z.prng = Prng::gen5(sa); z.run_turn(if s == 0 { [msw[i], tsw[j]] } else { [msw[j], tsw[i]] });
                    resolve_switches(&mut z, cfg, None); w * next_value(&z, cfg, sb, s) }).sum() };
                let vp = v2(bp); let va: Vec<f64> = alts.iter().map(|&i| v2(i)).collect();
                let worse = if s == 0 { vp < va.iter().cloned().fold(f64::MIN, f64::max) } else { vp > va.iter().cloned().fold(f64::MAX, f64::min) };
                // DP2_LOG=1 (champ-battle-v10): one record per check, values from the acting side's view: for the best Protect-again / other
                // move / switch option its one-turn and two-turn value, and (one playout against the other side's likeliest reply) the HP %
                // before and after of the Pokemon that holds the slot that turn (the switch-in for a switch)
                if dp2_log() {
                    let own = |v: f64| if s == 0 { v } else { 1.0 - v };
                    let hpp = |z: &Battle, mm: MonRef| if z.p(mm).fainted { 0 } else { (100 * z.p(mm).hp / z.p(mm).maxhp.max(1)) as i64 };
                    let mut ai = 0; let mut groups: Vec<Value> = vec![];
                    for (gi, nm) in ["protect", "other", "switch"].iter().enumerate() {
                        let Some(i) = best[gi] else { continue };
                        let v2v = if gi == 0 { vp } else { ai += 1; va[ai - 1] };
                        let holder: MonRef = match opts[i][k] { PChoice::Switch(pos) => (s, pos), _ => m };
                        let mut z = b.clone(); z.prng = Prng::gen5(sa); let j0 = resp[0].0;
                        z.run_turn(if s == 0 { [msw[i], tsw[j0]] } else { [msw[j0], tsw[i]] });
                        groups.push(json!({"k": nm, "opt": label(&b, s, &opts[i]), "v1": best1[gi], "v2": own(v2v), "hp0": hpp(&b, holder), "hp1": hpp(&z, holder)}));
                    }
                    let on: &Vec<[PChoice; 2]> = if s == 0 { &tsw } else { &msw };
                    dplog.push(json!({"t": turn, "s": s, "mon": b.dex.species.get(b.p(m).species).map(|x| x.name).unwrap_or("?"), "hp": hpp(&b, m),
                        "tr": find(&b.field.pseudo, "trickroom").and_then(|x| x.duration).unwrap_or(0), "pmass": pmass, "bench": crate::spot::bench(&b, s).len(),
                        "resp": resp.iter().map(|&(j, w)| json!([label(&b, 1 - s, &on[j]), w])).collect::<Vec<Value>>(), "g": groups, "dropped": worse}));
                }
                if !worse { continue; }
                dp2s[2 * s as usize + 1] += 1; pruned[s as usize].extend(prot.iter().copied());
                if s == 0 {
                    let rows: Vec<usize> = (0..msw.len()).filter(|i| !pruned[0].contains(i)).collect(); if rows.is_empty() { continue; }
                    let a: Vec<Vec<f64>> = rows.iter().map(|&i| xcols.iter().map(|&j| cell2(i, j, &b).0).collect()).collect();
                    let (xr, _) = nash(&a, 400); let mut xn = vec![0.0; msw.len()]; for (r, &i) in rows.iter().enumerate() { xn[i] = xr[r]; } x = xn;
                } else {
                    let cols: Vec<usize> = (0..tsw.len()).filter(|j| !pruned[1].contains(j)).collect(); if cols.is_empty() { continue; }
                    let a: Vec<Vec<f64>> = yrows.iter().map(|&i| cols.iter().map(|&j| cell2(i, j, &b).1).collect()).collect();
                    let (_, yc) = nash(&a, 400); let mut yn = vec![0.0; tsw.len()]; for (c, &j) in cols.iter().enumerate() { yn[j] = yc[c]; } y = yn;
                }
            } }
        }
        let i = sample(&x, &mut rng); let j = sample(&y, &mut rng);
        if !no_sw(&msw[i]) { switches[0] += 1; } if !no_sw(&tsw[j]) { switches[1] += 1; }
        for (s, ch) in [(0u8, &msw[i]), (1u8, &tsw[j])] {
            let can = !crate::spot::bench(&b, s).is_empty();
            for k in 0..2 { if let Some(pi) = b.sides[s as usize].active[k] { let p = b.p((s, pi)); if !p.fainted && !p.trapped && can {
                slot_decisions[s as usize] += 1; if matches!(ch[k], PChoice::Switch(_)) { switch_slots[s as usize] += 1; } } } }
        }
        // BATTLE_TURNS=1: the state at the start of each turn and both choices, for strategy summaries (Trick Room turns left, weather,
        // terrain; each side's active Pokemon with HP %, and the healthy bench)
        if want_states {
            let mons = |b: &Battle, s: u8, active: bool| -> Vec<Value> {
                b.sides[s as usize].pokemon.iter().filter(|p| !p.fainted && p.is_active == active)
                    .map(|p| json!([b.dex.species.get(p.species).map(|x| x.name).unwrap_or("?"), (100 * p.hp / p.maxhp.max(1)) as i64])).collect() };
            states.push(json!({"t": turn, "tr": find(&b.field.pseudo, "trickroom").and_then(|x| x.duration).unwrap_or(0),
                "w": b.field.weather, "ter": b.field.terrain, "me": mons(&b, 0, true), "them": mons(&b, 1, true),
                "mb": mons(&b, 0, false), "tb": mons(&b, 1, false), "a": label(&b, 0, &msw[i]), "b": label(&b, 1, &tsw[j])}));
        }
        if keep_log { log.push(format!("T{} {} || {}  [{}+{} x {}+{}]", turn, label(&b, 0, &msw[i]), label(&b, 1, &tsw[j]), mns.len(), msw.len() - mns.len(), tns.len(), tsw.len() - tns.len())); }
        b.prng = Prng::gen5(seed4(key.wrapping_mul(31) ^ turn as u64));
        b.run_turn([msw[i], tsw[j]]);
        resolve_switches(&mut b, cfg, Some(&mut rng));
        for u in &b.unsupported { if !uns.contains(u) { uns.push(u.clone()); } }
        if find(&b.field.pseudo, "trickroom").is_some() { tr_turns += 1; if turn <= 3 { for k in (turn - 1)..3 { tr_by[k] = true; } } }
        turn += 1;
    }
    Out { v: value(&mut b, cfg), unsupported: uns, feats: fx, turns: turn - 1, tr_turns, tr_by, switches, slot_decisions, switch_slots, log, states, dp2: dp2s, dplog }
}

pub fn main(args: &[String]) {
    let (dex, reg) = crate::turntest::load_all(&args[0]);
    let cfg: &'static Cfg = Box::leak(Box::new(load_cfg(&std::env::var("GRID_DIR").unwrap_or("../../mxtr".into()))));
    let threads: usize = args.get(3).and_then(|x| x.parse().ok()).unwrap_or(3);
    let keep_log = std::env::var("BATTLE_LOG").is_ok();
    let lines: Vec<String> = std::fs::read_to_string(&args[1]).unwrap().lines().map(|s| s.to_string()).collect();
    let dir = args[2].clone(); std::fs::create_dir_all(&dir).unwrap();
    let mut expect: BTreeMap<i64, usize> = BTreeMap::new();
    for l in &lines { let v: Value = serde_json::from_str(l).unwrap(); *expect.entry(v["job"].as_i64().unwrap()).or_default() += 1; }
    let next = std::sync::atomic::AtomicUsize::new(0);
    let pending: std::sync::Mutex<BTreeMap<i64, Vec<Value>>> = std::sync::Mutex::new(BTreeMap::new());
    let t0 = std::time::Instant::now();
    std::thread::scope(|sc| { for _ in 0..threads { sc.spawn(|| loop {
        let k = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst); if k >= lines.len() { break; }
        let st: Value = serde_json::from_str(&lines[k]).unwrap();
        let job = st["job"].as_i64().unwrap();
        if std::path::Path::new(&format!("{}/{}.json", dir, job)).exists() { continue; }   // resume
        let b = crate::turntest::new_battle(dex, reg, &st["state"], Mode::Real);
        let g = st["g"].as_u64().unwrap();
        // v3: seeds from the line's seedKey (battle_starts.js: archetype + their lead pair, or their four), so every team/bring facing the
        // same opponent shares turn and planning seeds for game g (common random numbers); lines without one keep the v2 job-index key
        let key = match st["seedKey"].as_str() {
            Some(sk) => { let mut h: u64 = 0xcbf29ce484222325; for c in sk.bytes() { h ^= c as u64; h = h.wrapping_mul(0x100000001b3); }   // FNV-1a
                          h ^ g.wrapping_mul(0x9E3779B97F4A7C15) ^ 0xBA77 }
            None => ((job as u64) << 24) ^ (g << 4) ^ 0xBA77,
        };
        let tg = std::time::Instant::now();
        let r = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| play(&b, cfg, st["rng"].as_f64().unwrap(), key, keep_log)));
        let row = match r {
            Ok(o) => json!({"g": g, "v": o.v, "turns": o.turns, "trTurns": o.tr_turns, "trBy": o.tr_by, "switches": o.switches, "slotDecisions": o.slot_decisions, "switchSlots": o.switch_slots, "dp2": o.dp2, "dp2log": if o.dplog.is_empty() { Value::Null } else { json!(o.dplog) }, "unsupported": o.unsupported, "F": if o.feats.is_empty() { Value::Null } else { json!(o.feats) }, "ms": tg.elapsed().as_millis() as u64,
                            "log": if keep_log { json!(o.log) } else { Value::Null }, "states": if o.states.is_empty() { Value::Null } else { json!(o.states) }}),
            Err(e) => json!({"g": g, "v": Value::Null, "error": e.downcast_ref::<String>().cloned().or(e.downcast_ref::<&str>().map(|s| s.to_string())).unwrap_or_default()}),
        };
        eprintln!("job {} game {}: {} ({} ms)", job, g, row["v"], tg.elapsed().as_millis());
        let done = { let mut pd = pending.lock().unwrap(); let e = pd.entry(job).or_default(); e.push(row); (e.len() == expect[&job]).then(|| pd.remove(&job).unwrap()) };
        if let Some(mut gs) = done {
            gs.sort_by_key(|x| x["g"].as_u64().unwrap());
            let vs: Vec<f64> = gs.iter().filter_map(|x| x["v"].as_f64()).collect();
            let feats: Vec<Value> = gs.iter().filter(|x| !x["F"].is_null()).map(|x| json!({"v": x["v"], "F": x["F"]})).collect();
            for x in gs.iter_mut() { x.as_object_mut().unwrap().remove("F"); }
            let mut out = json!({"job": job, "games": vs.len(), "v": if vs.is_empty() { Value::Null } else { json!(vs.iter().sum::<f64>() / vs.len() as f64) }, "vs": vs, "rows": gs});
            if !feats.is_empty() { out["feats"] = json!(feats); }
            if let Some(m) = st["meta"].as_object() { for (k, v) in m { out[k] = v.clone(); } }
            std::fs::write(format!("{}/{}.json", dir, job), out.to_string()).unwrap();
        }
    }); } });
    eprintln!("{} games in {:?}", lines.len(), t0.elapsed());
}
