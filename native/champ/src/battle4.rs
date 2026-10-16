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
use crate::spot::{joint, label, resolve_switches, seed4, resolve_switches_h};
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
#[derive(Clone, Copy)]
enum Policy { Eq, Random, Pure, Greedy, Exploit(f64), Noise(f64) }
/// BATTLE_POLICY_0 / BATTLE_POLICY_1 = eq | random | pure | greedy | exploit:<e> | noise:<e> (see the turn loop)
fn policy() -> [Policy; 2] {
    static F: std::sync::OnceLock<[Policy; 2]> = std::sync::OnceLock::new();
    *F.get_or_init(|| std::array::from_fn(|s| match std::env::var(format!("BATTLE_POLICY_{}", s)).as_deref() {
        Ok("random") => Policy::Random, Ok("pure") => Policy::Pure, Ok("greedy") => Policy::Greedy,
        Ok(v) if v.starts_with("exploit:") => Policy::Exploit(v[8..].parse().unwrap_or(0.1)),
        Ok(v) if v.starts_with("noise:") => Policy::Noise(v[6..].parse().unwrap_or(0.1)),
        _ => Policy::Eq }))
}
fn perish_search() -> Option<[usize; 2]> { static F: std::sync::OnceLock<Option<[usize; 2]>> = std::sync::OnceLock::new(); *F.get_or_init(|| {
    let d: usize = std::env::var("BATTLE_PERISH_DEPTH").ok()?.parse().ok()?;
    Some([std::env::var("BATTLE_PERISH_BUDGET").ok().and_then(|x| x.parse().ok()).unwrap_or(20000), d]) }) }
fn adapt_side() -> Option<u8> { static F: std::sync::OnceLock<Option<u8>> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("BATTLE_ADAPT_SIDE").ok().and_then(|x| x.parse().ok())) }
fn adapt_seeds() -> usize { static F: std::sync::OnceLock<usize> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("BATTLE_ADAPT_SEEDS").ok().and_then(|x| x.parse().ok()).unwrap_or(32)) }
fn dp2() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("DP2").is_ok()) }
/// DP2: side 0's value of a position after one more turn played as a small matrix game (reduced_options for both sides, one seed)
pub(crate) fn next_value(b: &Battle, cfg: &Cfg, seed: [u16; 4], s: u8) -> f64 {
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
/// EVAL_H2_HITS (evalpos horizon 2): damaging options per Pokemon in the second turn's reduced set (default 3, as DP2 uses)
fn h2_hits() -> usize { static F: std::sync::OnceLock<usize> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("EVAL_H2_HITS").ok().and_then(|x| x.parse().ok()).unwrap_or(3)) }
fn dp2_sw() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("DP2_SW").is_ok()) }
/// the second turn's options per side: reduced_options for each active Pokemon, plus (DP2_SW=1, champ-battle-v9) its switches to the bench
pub(crate) fn rjoint(b: &mut Battle, s: u8) -> Vec<[PChoice; 2]> {
    let bn = crate::spot::bench(b, s);
    let o: Vec<Vec<PChoice>> = (0..2).map(|i| {
        let mut v = reduced_options_n(b, s, i, h2_hits());
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
/// BATTLE_NS_0 / BATTLE_NS_1 (2026-10-14, the user: could the climb run on half the luck samples?): one side's own number of luck seeds
/// a cell (default BATTLE_NS). A cell is played on the larger number; each side averages its first n (the seeds are the same list),
/// so with both unset or equal every value is as before.
fn ns_sides() -> [usize; 2] {
    static F: std::sync::OnceLock<[usize; 2]> = std::sync::OnceLock::new();
    *F.get_or_init(|| std::array::from_fn(|s| std::env::var(format!("BATTLE_NS_{}", s)).ok().and_then(|x| x.parse().ok()).unwrap_or(ns()).max(1)))
}
/// EG_MEGA_TIE (default 0.002): margin of the Mega tie-break in play(); 0 keeps every mix as solved
fn mega_tie() -> f64 { static F: std::sync::OnceLock<f64> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("EG_MEGA_TIE").ok().and_then(|x| x.parse().ok()).unwrap_or(0.002)) }
/// BATTLE_FULLSW=0|1|both: which sides solve the full matrix game (the other side's switches included) instead of the one-layer one
fn fullsw() -> [bool; 2] { static F: std::sync::OnceLock<[bool; 2]> = std::sync::OnceLock::new(); *F.get_or_init(|| match std::env::var("BATTLE_FULLSW").as_deref() { Ok("0") => [true, false], Ok("1") => [false, true], Ok(_) => [true, true], Err(_) => [false, false] }) }
/// BATTLE_HORIZON=2 with BATTLE_HORIZON_SIDE=0|1 (default both): which sides re-solve on the two-turn values
fn horizon_sides() -> [bool; 2] {
    static F: std::sync::OnceLock<[bool; 2]> = std::sync::OnceLock::new();
    *F.get_or_init(|| { let on = std::env::var("BATTLE_HORIZON").ok().and_then(|x| x.parse::<usize>().ok()).unwrap_or(1) >= 2;
        if !on { return [false, false]; }
        match std::env::var("BATTLE_HORIZON_SIDE").as_deref() { Ok("0") => [true, false], Ok("1") => [false, true], _ => [true, true] } })
}

/// switch_slots / slot_decisions: active Pokemon that switched voluntarily / active Pokemon that could have (bench available, not trapped)
struct Out { sdlog: Vec<String>, v: f64, unsupported: Vec<String>, feats: Vec<Vec<f64>>, turns: usize, tr_turns: usize, tr_by: [bool; 3], switches: [usize; 2], slot_decisions: [usize; 2], switch_slots: [usize; 2], log: Vec<String>, states: Vec<Value>, dp2: [usize; 4], dplog: Vec<Value>, h2: usize }

fn play(start: &Battle, cfg: &Cfg, mut rng: f64, key: u64, keep_log: bool, st_job: i64, st_g: u64, mut human: Option<&mut crate::human::Human>) -> Out {
    let mut b = start.clone(); let mut turn = 1;
    if human.is_some() { b.logging = false; }   // the planner's sims must not log; the real turn is logged below
    // BATTLE_SDLOG=1 (2026-10-12, the Eval bar's Yawn study): the real turns' Showdown protocol lines, drained after each turn so the
    // planner's clones never copy them; written out as "sdlog" (pssim/selfplay_logs.py makes spectator logs of them)
    let sd_on = human.is_none() && std::env::var("BATTLE_SDLOG").is_ok(); let mut sdlog: Vec<String> = vec![];
    let (mut tr_turns, mut tr_by, mut switches, mut log) = (0, [false; 3], [0usize; 2], vec![]);
    let (mut slot_decisions, mut switch_slots) = ([0usize; 2], [0usize; 2]);
    let mut uns: Vec<String> = vec![]; let mut dp2s = [0usize; 4]; let mut dplog: Vec<Value> = vec![]; let mut h2cells = 0usize;
    let want_states = std::env::var("BATTLE_TURNS").is_ok(); let mut states: Vec<Value> = vec![];
    let want_feats = std::env::var("BATTLE_FEATS").is_ok(); let mut fx: Vec<Vec<f64>> = vec![];
    let human_game = human.is_some();   // a human's game runs until the clock (PLAY_CLOCK_TURNS, default 100), not to the self-play cap
    let clock = crate::spot::clock_turns();
    while !b.ended && (if human_game { turn <= clock } else { turn <= MAXTURN || (turn <= STALL_MAXTURN && !can_damage(&b, 0) && !can_damage(&b, 1)) }) {
        let sw = std::env::var("BATTLE_NOSWITCH").is_err();   // BATTLE_NOSWITCH=1: control run, Pokemon only come in when something faints
        let msw = joint(&mut b, 0, sw); let tsw = joint(&mut b, 1, sw);
        if msw.is_empty() || tsw.is_empty() {
            // BATTLE_BREAK_DEBUG=1: say why a game is handed to the value function before it ended (which side, its active Pokemon,
            // their locked moves and request moves, and each slot's raw options)
            if std::env::var("BATTLE_BREAK_DEBUG").is_ok() {
                for s in 0..2u8 {
                    let n = if s == 0 { msw.len() } else { tsw.len() };
                    eprintln!("turn {}: side {} has {} joint actions; bench {:?}", turn, s, n, crate::spot::bench(&b, s));
                    for i in 0..2 {
                        let Some(pi) = b.sides[s as usize].active[i] else { eprintln!("   slot {}: empty", i); continue };
                        let m = (s, pi); let lk = b.get_locked_move(m); let req = b.request_moves(m);
                        let p = b.p(m); let vol: Vec<&str> = p.volatiles.iter().map(|v| v.0).collect();
                        eprintln!("   slot {}: {} hp {} fainted {} trapped {} locked {:?} volatiles {:?} request {:?}", i, p.species, p.hp, p.fainted, p.trapped, lk, vol, req);
                        eprintln!("      options {:?}", crate::plan::slot_options(&mut b, s, i));
                    }
                }
            }
            break;
        }
        if want_feats { fx.push(feats(&mut b, cfg)); }   // position at the start of the turn, for refitting the value on 4v4 games
        let no_sw = |c: &[PChoice; 2]| !c.iter().any(|x| matches!(x, PChoice::Switch(_)));
        let mns: Vec<usize> = (0..msw.len()).filter(|i| no_sw(&msw[*i])).collect();
        let tns: Vec<usize> = (0..tsw.len()).filter(|j| no_sw(&tsw[*j])).collect();
        let nss = ns_sides();
        let cs: Vec<[u16; 4]> = (0..nss[0].max(nss[1])).map(|k| seed4(key ^ ((turn as u64) << 40) ^ ((k as u64) << 52))).collect();
        let mut cache: HashMap<(usize, usize), (f64, f64)> = HashMap::new();
        // each cell as (side 0's value, side 1's value); the two differ only with EG_VALUE_B
        let mut cell2 = |i: usize, j: usize, b: &Battle| -> (f64, f64) {
            *cache.entry((i, j)).or_insert_with(|| {
                let mut s = (0.0, 0.0);
                for (k, c) in cs.iter().enumerate() { let mut x = b.clone(); x.prng = Prng::gen5(*c); x.run_turn([msw[i], tsw[j]]); resolve_switches(&mut x, cfg, None); let v = value2(&mut x, cfg); if k < nss[0] { s.0 += v.0; } if k < nss[1] { s.1 += v.1; } }
                (s.0 / nss[0] as f64, s.1 / nss[1] as f64) })
        };
        // BATTLE_FULLSW=1 (champ-battle-v21): one full matrix game, both sides' switches in both sides' matrices (the one-layer model
        // below assumes the opponent stays in; the shared no-switch block means the full game costs only the switch x switch cells more)
        let fsw = fullsw();
        let tns0: Vec<usize> = if fsw[0] { (0..tsw.len()).collect() } else { tns.clone() };   // side 0's matrix sees all of side 1's options
        let mns0: Vec<usize> = if fsw[1] { (0..msw.len()).collect() } else { mns.clone() };   // side 1's matrix sees all of side 0's
        // my matrix: all my options (moves + switches) vs their non-switch options
        let am: Vec<Vec<f64>> = (0..msw.len()).map(|i| tns0.iter().map(|&j| cell2(i, j, &b).0).collect()).collect();
        // their matrix: my non-switch options vs all their options
        let at: Vec<Vec<f64>> = mns0.iter().map(|&i| (0..tsw.len()).map(|j| cell2(i, j, &b).1).collect()).collect();
        let (mut x, _) = if tns0.is_empty() { (vec![1.0 / msw.len() as f64; msw.len()], vec![]) } else { nash(&am, 400) };
        let (_, mut y) = if mns0.is_empty() { (vec![], vec![1.0 / tsw.len() as f64; tsw.len()]) } else { nash(&at, 400) };
        let (mut xcols, mut yrows) = (tns0.clone(), mns0.clone());
        // BATTLE_ANTICIPATE=1 (second pass): each side's matrix also gets the switches the other side actually plays (weight > 2% in its
        // one-layer mix), so a side plans against the opponent's real switches without searching every switch pair.
        // BATTLE_ANTICIPATE=2|3 (champ-battle-v21): that many passes, each adding the switches the other side's latest mix plays.
        if !(fsw[0] && fsw[1]) { if let Ok(ap) = std::env::var("BATTLE_ANTICIPATE") {
            let passes: usize = ap.parse().unwrap_or(1).max(1);
            for _ in 0..passes {
                let isw: Vec<usize> = if fsw[1] { vec![] } else { (0..msw.len()).filter(|i| !no_sw(&msw[*i]) && x[*i] > 0.02 && !yrows.contains(i)).collect() };
                let jsw: Vec<usize> = if fsw[0] { vec![] } else { (0..tsw.len()).filter(|j| !no_sw(&tsw[*j]) && y[*j] > 0.02 && !xcols.contains(j)).collect() };
                if isw.is_empty() && jsw.is_empty() { break; }
                if !jsw.is_empty() {
                    let cols: Vec<usize> = xcols.iter().copied().chain(jsw.iter().copied()).collect();
                    let am2: Vec<Vec<f64>> = (0..msw.len()).map(|i| cols.iter().map(|&j| cell2(i, j, &b).0).collect()).collect();
                    x = nash(&am2, 400).0; xcols = cols;
                }
                if !isw.is_empty() {
                    let rows: Vec<usize> = yrows.iter().copied().chain(isw.iter().copied()).collect();
                    let at2: Vec<Vec<f64>> = rows.iter().map(|&i| (0..tsw.len()).map(|j| cell2(i, j, &b).1).collect()).collect();
                    y = nash(&at2, 400).1; yrows = rows;
                }
            }
        } }
        // BATTLE_HORIZON=2 (champ-battle-v21): the evalpos two-turn horizon in real games. Every option in contention after the one-turn
        // solve (in a side's mix, or within BATTLE_H2_MARGIN (0.15) of that side's best option) gets its cells against the other side's
        // contenders valued after one more turn (next_value: both sides' Protect and strongest hits, no switches, one seed per sample,
        // BATTLE_H2_SEEDS samples, default 1), and the sides that use the horizon (BATTLE_HORIZON_SIDE=0|1, default both) re-solve their
        // mixes on those values; up to 2 rounds, widening to what the new solve brings in. Cells outside the set keep one-turn values.
        let hz = horizon_sides();
        let mut cache2: HashMap<(usize, usize), f64> = HashMap::new();
        if (hz[0] || hz[1]) && !xcols.is_empty() && !yrows.is_empty() {
            let n2 = std::env::var("BATTLE_H2_SEEDS").ok().and_then(|x| x.parse().ok()).unwrap_or(1usize).max(1);
            let margin: f64 = std::env::var("BATTLE_H2_MARGIN").ok().and_then(|x| x.parse().ok()).unwrap_or(0.05);
            // BATTLE_H2_TOP (default 6): at most this many rows and columns per round (the mix's heaviest first, then the closest
            // values), so a turn costs about 2-3x the one-turn solve instead of 30x
            let top_n = std::env::var("BATTLE_H2_TOP").ok().and_then(|x| x.parse().ok()).unwrap_or(6usize).max(1);
            for _ in 0..2 {
                let v0 = |c2: &HashMap<(usize, usize), f64>, cache: &mut dyn FnMut(usize, usize) -> (f64, f64), i: usize, j: usize, s: u8| -> f64 {
                    if hz[s as usize] { if let Some(v) = c2.get(&(i, j)) { return if s == 0 { *v } else { *v }; } }
                    let c = cache(i, j); if s == 0 { c.0 } else { c.1 } };
                let ysup: Vec<usize> = (0..tsw.len()).filter(|j| y[*j] > 1e-4).collect(); let ytot: f64 = ysup.iter().map(|&j| y[j]).sum();
                let xsup: Vec<usize> = (0..msw.len()).filter(|i| x[*i] > 1e-4).collect(); let xtot: f64 = xsup.iter().map(|&i| x[i]).sum();
                let mut cb = |i: usize, j: usize| cell2(i, j, &b);
                let rv: Vec<f64> = (0..msw.len()).map(|i| ysup.iter().map(|&j| y[j] * v0(&cache2, &mut cb, i, j, 0)).sum::<f64>() / ytot).collect();
                let cv: Vec<f64> = (0..tsw.len()).map(|j| xsup.iter().map(|&i| x[i] * v0(&cache2, &mut cb, i, j, 1)).sum::<f64>() / xtot).collect();
                let best_r = rv.iter().cloned().fold(f64::MIN, f64::max); let best_c = cv.iter().cloned().fold(f64::MAX, f64::min);
                let mut rows: Vec<usize> = (0..msw.len()).filter(|&i| x[i] > 1e-3 || rv[i] >= best_r - margin).collect();
                let mut cols: Vec<usize> = (0..tsw.len()).filter(|&j| y[j] > 1e-3 || cv[j] <= best_c + margin).collect();
                rows.sort_by(|&a, &c| x[c].partial_cmp(&x[a]).unwrap().then(rv[c].partial_cmp(&rv[a]).unwrap())); rows.truncate(top_n);
                cols.sort_by(|&a, &c| y[c].partial_cmp(&y[a]).unwrap().then(cv[a].partial_cmp(&cv[c]).unwrap())); cols.truncate(top_n);
                let before = cache2.len();
                for &i in &rows { for &j in &cols {
                    if cache2.contains_key(&(i, j)) { continue; }
                    let mut v = 0.0;
                    for k in 0..n2 {
                        let sa = seed4(key ^ ((turn as u64) << 40) ^ (0xA2u64 << 52) ^ ((k as u64) << 48)); let sb = seed4(key ^ ((turn as u64) << 40) ^ (0xA3u64 << 52) ^ ((k as u64) << 48));
                        let mut z = b.clone(); z.prng = Prng::gen5(sa); z.run_turn([msw[i], tsw[j]]); resolve_switches(&mut z, cfg, None);
                        for u in &z.unsupported { if !uns.contains(u) { uns.push(u.clone()); } }
                        v += next_value(&z, cfg, sb, 0);
                    }
                    cache2.insert((i, j), v / n2 as f64); h2cells += 1;
                } }
                if cache2.len() == before { break; }
                if hz[0] { let am2: Vec<Vec<f64>> = (0..msw.len()).map(|i| xcols.iter().map(|&j| v0(&cache2, &mut cb, i, j, 0)).collect()).collect(); x = nash(&am2, 400).0; }
                if hz[1] { let at2: Vec<Vec<f64>> = yrows.iter().map(|&i| (0..tsw.len()).map(|j| v0(&cache2, &mut cb, i, j, 1)).collect()).collect(); y = nash(&at2, 400).1; }
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
        // Mega tie-break (2026-10-10, TR sheet's read of the 17% delays): where a move is offered with and without the Mega and the Mega
        // version is worth at least as much against the other side's mix minus EG_MEGA_TIE (default 0.002), the no-Mega version's
        // weight moves to it, so a coin flip between equal options never reads as "held the Mega". EG_MEGA_TIE=0 turns it off.
        let tie = mega_tie();
        if tie >= 0.0 {
            let twin = |opts: &[[PChoice; 2]], i: usize| -> Option<usize> {
                let c = opts[i]; let mut want = c; let mut changed = false;
                for k in 0..2 { if let PChoice::Move(sl, t, false) = c[k] { if opts.iter().any(|o| o[k] == PChoice::Move(sl, t, true)) && !changed { want[k] = PChoice::Move(sl, t, true); changed = true; } } }
                if !changed { return None; } opts.iter().position(|o| *o == want) };
            let ysup: Vec<usize> = (0..tsw.len()).filter(|j| y[*j] > 1e-4).collect(); let ytot: f64 = ysup.iter().map(|&j| y[j]).sum();
            let xsup: Vec<usize> = (0..msw.len()).filter(|i| x[*i] > 1e-4).collect(); let xtot: f64 = xsup.iter().map(|&i| x[i]).sum();
            for i in 0..msw.len() { if x[i] > 1e-6 { if let Some(j) = twin(&msw, i) {
                let (mut vi, mut vj) = (0.0, 0.0); for &c in &ysup { vi += y[c] * cell2(i, c, &b).0; vj += y[c] * cell2(j, c, &b).0; }
                if ytot > 0.0 && vj / ytot >= vi / ytot - tie { x[j] += x[i]; x[i] = 0.0; } } } }
            for i in 0..tsw.len() { if y[i] > 1e-6 { if let Some(j) = twin(&tsw, i) {
                let (mut vi, mut vj) = (0.0, 0.0); for &r in &xsup { vi += x[r] * cell2(r, i, &b).1; vj += x[r] * cell2(r, j, &b).1; }
                if xtot > 0.0 && vj / xtot <= vi / xtot + tie { y[j] += y[i]; y[i] = 0.0; } } } }
        }
        // BATTLE_POLICY_0 / BATTLE_POLICY_1 (2026-10-10, the user: how strong is the equilibrium?): how a side acts on the solved turn.
        //   eq (default) samples its mix; random picks uniformly among all its options; greedy plays the joint option with the highest
        //   expected damage this turn (plan.rs greedy_damage: no Protect, no switches); pure plays its mix's heaviest option with
        //   probability 1; exploit:<e> plays the best response to a model of the other side that plays its mix 1-e of the time and a
        //   uniform non-switch option e of the time; noise:<e> plays its own mix 1-e of the time and a uniform non-switch option e of
        //   the time (the opponent the exploiter imagines). Side 0's policy is applied first, so an exploiter on side 0 models side 1's
        //   solved mix before side 1's own noise is added.
        // BATTLE_EVAL=1 (2026-10-14): each side's mix from the anytime search instead (deep.rs: BATTLE_EVAL_BUDGET leaf evaluations,
        // BATTLE_EVAL_DEPTH_0 / _1 turns beyond this one, per-side budgets BATTLE_EVAL_BUDGET_0 / _1), both sides on the same key so
        // equal settings see the same table
        // BATTLE_PERISH_DEPTH=<d> (2026-10-16, the user: a search for Perish specifically): on turns with a Perish fight on
        // (plan::perish_on) both sides choose by the tree search with at least d turns beyond this one at BATTLE_PERISH_BUDGET (default
        // 20000) leaf evaluations at least, with or without BATTLE_EVAL
        let mut eval_sides = crate::deep::battle_eval();
        if let Some([pb, pd]) = perish_search() { if crate::plan::perish_on(&b) {
            let mut sd = eval_sides.unwrap_or([[pb, pd]; 2]);
            for x in sd.iter_mut() { x[0] = x[0].max(pb); x[1] = x[1].max(pd); }
            eval_sides = Some(sd);
        } }
        if let Some(sides) = eval_sides {
            let p = crate::deep::Params::from_env(2, 256);
            for s in 0..2u8 {
                // BATTLE_ADAPT_SIDE=0|1 (2026-10-16): that side chooses by the bot's own search (evalpos eval_one: EVAL_ADAPT's staged seeds,
                // BATTLE_ADAPT_SEEDS a cell at most, default 32) instead of the anytime search, for testing a new bot search against the
                // live one
                if adapt_side() == Some(s) {
                    if let Some((m0, m1, x2, y2)) = crate::evalpos::mix(&b, cfg, key ^ ((turn as u64) << 40) ^ 0xADA7, adapt_seeds()) {
                        if s == 0 && m0 == msw { x = x2; } else if s == 1 && m1 == tsw { y = y2; }
                        else { let u = "BATTLE_ADAPT_SIDE: options differ from battle4's".to_string(); if !uns.contains(&u) { uns.push(u); } }
                    }
                    continue;
                }
                let [budget, depth] = sides[s as usize];
                // each side's leaves scored with its own net when EG_VNET_B is set (plan.rs as_side)
                let Some((root, st)) = crate::plan::as_side(s, || crate::deep::search(&b, cfg, key ^ ((turn as u64) << 40) ^ 0xE7A1, depth, &p, budget, 0, (None, None), std::time::Instant::now())) else { continue };
                for u in &st.uns { if !uns.contains(u) { uns.push(u.clone()); } }
                h2cells += st.deep_rolls;   // the row's h2 counts the deep rolls under BATTLE_EVAL
                if s == 0 && root.msw == msw { x = root.x.clone(); } else if s == 1 && root.tsw == tsw { y = root.y.clone(); }
            }
        }
        let pol = policy();
        for s in 0..2usize {
            let (n_own, own_ns, opp_ns) = if s == 0 { (msw.len(), &mns, &tns) } else { (tsw.len(), &tns, &mns) };
            let new_mix: Option<Vec<f64>> = match pol[s] {
                Policy::Eq => None,
                Policy::Random => Some(vec![1.0 / n_own as f64; n_own]),
                Policy::Greedy => { let own: &Vec<[PChoice; 2]> = if s == 0 { &msw } else { &tsw };   // highest expected damage, first on ties
                    let vals: Vec<f64> = own.iter().map(|c| greedy_damage(&b, cfg, s as u8, c)).collect();
                    let k = (0..n_own).max_by(|&a, &c| vals[a].partial_cmp(&vals[c]).unwrap().then(c.cmp(&a))).unwrap();
                    let mut u = vec![0.0; n_own]; u[k] = 1.0; Some(u) }
                Policy::Pure => { let mix = if s == 0 { &x } else { &y };
                    let k = (0..mix.len()).max_by(|&a, &c| mix[a].partial_cmp(&mix[c]).unwrap()).unwrap();
                    let mut u = vec![0.0; mix.len()]; u[k] = 1.0; Some(u) }
                Policy::Noise(e) => { let mix = if s == 0 { &x } else { &y };
                    let mut u: Vec<f64> = mix.iter().map(|v| v * (1.0 - e)).collect();
                    if !own_ns.is_empty() { for &k in own_ns.iter() { u[k] += e / own_ns.len() as f64; } }
                    Some(u) }
                Policy::Exploit(e) => { let opp = if s == 0 { &y } else { &x };
                    let mut model: Vec<f64> = opp.iter().map(|v| v * (1.0 - e)).collect();
                    if !opp_ns.is_empty() { for &k in opp_ns.iter() { model[k] += e / opp_ns.len() as f64; } }
                    let vals: Vec<f64> = (0..n_own).map(|i| (0..model.len()).filter(|&j| model[j] > 1e-6)
                        .map(|j| model[j] * if s == 0 { cell2(i, j, &b).0 } else { 1.0 - cell2(j, i, &b).1 }).sum()).collect();
                    let k = (0..n_own).max_by(|&a, &c| vals[a].partial_cmp(&vals[c]).unwrap()).unwrap();
                    let mut u = vec![0.0; n_own]; u[k] = 1.0; Some(u) }
            };
            if let Some(u) = new_mix { if s == 0 { x = u; } else { y = u; } }
        }
        let i = match human.as_deref_mut() {
            Some(h) => {   // the turn's solved value (both mixes' supports; those cells are cached), for the page's concede check
                let xs: Vec<usize> = (0..msw.len()).filter(|&i| x[i] > 1e-4).collect(); let ys: Vec<usize> = (0..tsw.len()).filter(|&j| y[j] > 1e-4).collect();
                let (mut gv, mut wt) = (0.0, 0.0);
                for &i in &xs { for &j in &ys { gv += x[i] * y[j] * cell2(i, j, &b).0; wt += x[i] * y[j]; } }
                let gv = if wt > 0.0 { gv / wt } else { 0.5 };
                // "ask the planner to concede": 8 playouts of the planner against itself from here (up to 250 turns each)
                let mut check = || { let n = 8usize; let bb = &b;
                    let rs: Vec<f64> = std::thread::scope(|sc| { let hs: Vec<_> = (0..n).map(|k| sc.spawn(move || crate::spot::playout_long(bb, cfg, (k as f64 + 1.0) * 7919.0, key ^ ((turn as u64) << 40) ^ ((k as u64 + 11) << 48), clock.saturating_sub(turn - 1).max(1)))).collect();
                        hs.into_iter().map(|h| h.join().unwrap_or(0.5)).collect() });
                    let wins = rs.iter().filter(|&&r| r < 0.25).count(); let draws = rs.iter().filter(|&&r| (0.25..0.75).contains(&r)).count();
                    json!({"type": "verdict", "n": n, "planner_wins": wins, "draws": draws, "value": gv}) };
                h.choose_turn(&b, turn, &msw, gv, &mut check) }
            None => sample(&x, &mut rng) };
        let j = sample(&y, &mut rng);
        // BATTLE_MEGA_AUDIT=<jsonl> (2026-10-10, for TR sheet's audit of un-evolved attacking turns): whenever a side's sampled action
        // uses a move without the Mega although the Mega twin was on offer, record the turn with both outcomes against the other
        // side's sampled action (8 seeds: damage range and KOs per target, who moved first), the ability / type the Mega would have had,
        // and the two options' values against the other side's mix
        if let Ok(path) = std::env::var("BATTLE_MEGA_AUDIT") {
            for s in 0..2u8 {
                let (own, their, mine_i, their_j) = if s == 0 { (&msw, &tsw, i, j) } else { (&tsw, &msw, j, i) };
                let ch = own[mine_i];
                for k in 0..2usize {
                    let PChoice::Move(sl, t, false) = ch[k] else { continue };
                    let mut twin = ch; twin[k] = PChoice::Move(sl, t, true);
                    let Some(ti) = own.iter().position(|o| *o == twin) else { continue };
                    let Some(pi) = b.sides[s as usize].active[k] else { continue }; let m = (s, pi);
                    if b.p(m).can_mega_evo.is_none() { continue; }
                    let mid = b.p(m).move_slots[sl].id; let cat = b.dex.mv(mid).tmpl.category;
                    if cat == "Status" { continue; }
                    let mega_sp = b.p(m).can_mega_evo.unwrap(); let msd = b.dex.species.get(mega_sp);
                    let mega_ab = msd.and_then(|x| x.abilities.iter().find(|(kk, _)| *kk == "0").map(|x| x.1)).unwrap_or("");
                    let mega_types: Vec<&str> = msd.map(|x| x.types.clone()).unwrap_or_default();
                    // values against the other side's mix
                    let (mix, tot): (Vec<f64>, f64) = if s == 0 { (y.clone(), y.iter().sum()) } else { (x.clone(), x.iter().sum()) };
                    let mut val = |row: usize| -> f64 { let mut v = 0.0; for (c, w) in mix.iter().enumerate() { if *w > 1e-4 { v += w * if s == 0 { cell2(row, c, &b).0 } else { 1.0 - cell2(c, row, &b).1 }; } } v / tot.max(1e-9) };
                    let (v_no, v_mega) = (val(mine_i), val(ti));
                    // outcomes against the sampled reply, 8 seeds, both ways
                    let mut actives: Vec<MonRef> = vec![]; for sd in 0..2u8 { for kk in 0..2 { if let Some(q) = b.sides[sd as usize].active[kk] { actives.push((sd, q)); } } }
                    let names: Vec<String> = actives.iter().map(|q| b.dex.species.get(b.p(*q).species).map(|x| x.name.to_string()).unwrap_or_default()).collect();
                    let hp0: Vec<i64> = actives.iter().map(|q| b.p(*q).hp).collect();
                    let run = |choice: [PChoice; 2]| -> Value {
                        let mut dmg_min = vec![i64::MAX; actives.len()]; let mut dmg_max = vec![0i64; actives.len()]; let mut ko = vec![0; actives.len()]; let mut first = std::collections::HashMap::new();
                        let mut f0: Vec<f64> = vec![]; let mut v0 = 0.0; let mut end_species: Vec<String> = vec![];
                        for sd in 0..8u64 {
                            let mut z = b.clone(); z.prng = Prng::gen5(seed4(key ^ ((turn as u64) << 40) ^ (0xAAu64 << 52) ^ (sd << 44))); z.logging = true;
                            let jc = if s == 0 { [choice, their[their_j]] } else { [their[their_j], choice] };
                            z.run_turn(jc);
                            if sd == 0 { resolve_switches(&mut z, cfg, None); f0 = feats(&mut z, cfg); v0 = value(&mut z, cfg); end_species = actives.iter().map(|q| format!("{} {}/{} spe {}", z.p(*q).species, z.p(*q).hp, z.p(*q).maxhp, z.p(*q).stored[5])).collect(); }
                            for (qi, q) in actives.iter().enumerate() { let d = (hp0[qi] - z.p(*q).hp).max(0); dmg_min[qi] = dmg_min[qi].min(d); dmg_max[qi] = dmg_max[qi].max(d); if z.p(*q).hp == 0 { ko[qi] += 1; } }
                            if let Some(l) = z.log.iter().find(|l| l.starts_with("|move|")) { *first.entry(l.split('|').nth(2).unwrap_or("").to_string()).or_insert(0) += 1; }
                        }
                        json!({"dmg": actives.iter().enumerate().map(|(qi, _)| json!([names[qi].clone(), dmg_min[qi], dmg_max[qi], ko[qi]])).collect::<Vec<_>>(), "first_mover": first, "feats_seed0": f0, "value_seed0": v0, "end_seed0": end_species})
                    };
                    let rec = json!({"job": st_job, "g": st_g, "turn": turn, "side": s, "species": names[(s as usize) * 2 + k], "move": b.dex.mv(mid).tmpl.name, "label": label(&b, s, &ch),
                        "reply": label(&b, 1 - s, &their[their_j]), "tr": find(&b.field.pseudo, "trickroom").and_then(|x| x.duration).unwrap_or(0),
                        "ability_now": b.p(m).ability, "mega_ability": mega_ab, "types_now": b.p(m).types.clone(), "mega_types": mega_types,
                        "v_no_mega": v_no, "v_mega": v_mega, "gap": v_mega - v_no, "weight_no_mega": if s == 0 { x[mine_i] } else { y[mine_i] }, "weight_mega": if s == 0 { x[ti] } else { y[ti] },
                        "outcome_no_mega": run(ch), "outcome_mega": run(twin)});
                    if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&path) { use std::io::Write; let _ = writeln!(f, "{}", rec); }
                }
            }
        }
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
        if human.is_some() || sd_on { b.logging = true; }
        b.run_turn([msw[i], tsw[j]]);
        resolve_switches_h(&mut b, cfg, Some(&mut rng), human.as_deref_mut(), turn);
        if human.is_some() || sd_on { b.logging = false; }
        if sd_on { sdlog.push(format!("|turn|{}", turn)); sdlog.extend(b.log.drain(..)); }
        for u in &b.unsupported { if !uns.contains(u) { uns.push(u.clone()); } }
        if find(&b.field.pseudo, "trickroom").is_some() { tr_turns += 1; if turn <= 3 { for k in (turn - 1)..3 { tr_by[k] = true; } } }
        turn += 1;
    }
    let v = value(&mut b, cfg);
    if let Some(h) = human.as_deref_mut() {
        let (winner, how) = if b.ended { (match b.winner { Some(Some(0)) => "you", Some(Some(1)) => "the planner", Some(_) => "draw", None => "unfinished" }, None) }
            else { let w = crate::spot::clock_winner(&b); (match w { Some(0) => "you", Some(_) => "the planner", None => "draw" }, Some(format!("the clock ran out after {} turns: {}", turn - 1,
                   match w { Some(_) => "more Pokemon left, or more HP", None => "dead even" }))) };
        h.end(&b, turn - 1, v, winner, how); }
    Out { sdlog, v, unsupported: uns, feats: fx, turns: turn - 1, tr_turns, tr_by, switches, slot_decisions, switch_slots, log, states, dp2: dp2s, dplog, h2: h2cells }
}
/// champ play <engine_data.json> <start.jsonl> : the first start line, a human on side 0 (see human.rs)
pub fn play_main(args: &[String]) {
    let (dex, reg) = crate::turntest::load_all(&args[0]);
    let cfg: &'static Cfg = Box::leak(Box::new(load_cfg(&std::env::var("GRID_DIR").unwrap_or("../../mxtr".into()))));
    let line = std::fs::read_to_string(&args[1]).unwrap().lines().find(|l| !l.trim().is_empty()).map(|s| s.to_string()).expect("no start");
    let st: Value = serde_json::from_str(&line).unwrap();
    let b = crate::turntest::new_battle(dex, reg, &st["state"], Mode::Real);
    let t = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_nanos() as u64).unwrap_or(7);
    let key = t ^ 0x9E3779B97F4A7C15; let rng = st["rng"].as_f64().unwrap_or((t % 1_000_003) as f64);
    let mut h = crate::human::Human::new();
    let _ = play(&b, cfg, rng, key, false, 0, 0, Some(&mut h));
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
        let r = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| play(&b, cfg, st["rng"].as_f64().unwrap(), key, keep_log, job, g, None)));
        let row = match r {
            Ok(o) => json!({"g": g, "v": o.v, "turns": o.turns, "trTurns": o.tr_turns, "trBy": o.tr_by, "switches": o.switches, "slotDecisions": o.slot_decisions, "switchSlots": o.switch_slots, "dp2": o.dp2, "h2": o.h2, "dp2log": if o.dplog.is_empty() { Value::Null } else { json!(o.dplog) }, "unsupported": o.unsupported, "F": if o.feats.is_empty() { Value::Null } else { json!(o.feats) }, "ms": tg.elapsed().as_millis() as u64,
                            "log": if keep_log { json!(o.log) } else { Value::Null }, "sdlog": if o.sdlog.is_empty() { Value::Null } else { json!(o.sdlog) }, "states": if o.states.is_empty() { Value::Null } else { json!(o.states) }}),
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
    if std::env::var("MISS_STATS").is_ok() {
        let g = crate::sim::MISS_STATS.lock().unwrap(); let mut v: Vec<_> = g.iter().cloned().collect(); v.sort_by(|a, b| b.1.0.cmp(&a.1.0));
        eprintln!("accuracy rolls (side, move: rolls, misses, hit rate):");
        for ((s, mid), (r, mi)) in v.iter().take(30) { eprintln!("   {} {:16} {:6} {:6} {:5.1}%", s, mid, r, mi, 100.0 * (1.0 - *mi as f64 / *r as f64)); }
    }
}
