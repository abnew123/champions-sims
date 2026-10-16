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
//! env: EG_VALUE (and RACE / CALC_DATA, TRSYM, GRID_DIR as for battles), EVAL_SEEDS, EVAL_TOP (joint actions listed, default 8),
//!      EVAL_ADAPT=1 (staged seeds: see eval_one; adds stages, sims, cells_full to the output), EVAL_STAGES, EVAL_MARGINS
//!      EVAL_BUDGET / EVAL_BUDGET_MS (the anytime search: see eval_one) and EVAL_DEPTH (with a budget: the search as a tree, deep.rs)
//!      EVAL_HORIZON=2 (two-turn values for the options in contention: see eval_one; adds horizon, cells_h2, sims_h2), EVAL_H2_SEEDS,
//!      EVAL_H2_MARGIN, EVAL_H2_HITS
//!      EVAL_MATRIX=1 | full: adds "matrix" to each line: rows / cols (both sides' joint actions as [slot 0 c, slot 1 c]), rl / cl (their
//!      labels), x / y (the final mixes), v1 (rows x cols one-turn values, side 0's win chance, at each cell's precision) with n1 (seeds per
//!      cell), and under EVAL_HORIZON=2 v2 / n2 (two-turn values where computed, else null / 0). With "1", the rows and columns holding a
//!      slot's actual or most-weighted option are first raised to EVAL_SEEDS seeds and the turn solved again (so x, y and the report agree
//!      with the matrix); with "full", every cell is.
use crate::battle::*;
use crate::plan::*;
use crate::prng::{Mode, Prng};
use crate::sim::PChoice;
use crate::spot::{joint, label, resolve_switches, seed4};
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::io::Write;

fn env_usize(name: &str, default: usize) -> usize { std::env::var(name).ok().and_then(|x| x.parse().ok()).unwrap_or(default) }

struct Cells<'a> { b: &'a Battle, cfg: &'a Cfg, msw: &'a [[PChoice; 2]], tsw: &'a [[PChoice; 2]], cs: Vec<[u16; 4]>, base: usize,
                   acc: HashMap<(usize, usize), (f64, usize)>, sims: usize, uns: Vec<String>,
                   /// each cell's sum of squared values (the budgeted search's per-cell spread)
                   sq: HashMap<(usize, usize), f64>,
                   /// EVAL_HORIZON=2: two-turn values (the next turn solved as a small matrix game after this one) and their seeds; a cell
                   /// that has one is read from here by get()
                   cs2: Vec<[u16; 4]>, acc2: HashMap<(usize, usize), (f64, usize)>, sims2: usize }
impl<'a> Cells<'a> {
    /// side 0's value after the turn (i, j) and one more turn (battle4::next_value: both sides' reduced options, one seed), averaged over n seeds
    fn ensure2(&mut self, i: usize, j: usize, n: usize) -> f64 {
        let (mut s, mut c) = self.acc2.get(&(i, j)).copied().unwrap_or((0.0, 0));
        if c >= n { return s / c as f64; }
        while c < n {
            let mut x = self.b.clone(); x.prng = Prng::gen5(self.cs[c]); x.run_turn([self.msw[i], self.tsw[j]]); resolve_switches(&mut x, self.cfg, None);
            s += crate::battle4::next_value(&x, self.cfg, self.cs2[c], 0);
            for u in &x.unsupported { if !self.uns.contains(u) { self.uns.push(u.clone()); } }
            c += 1; self.sims2 += 1;
        }
        self.acc2.insert((i, j), (s, c)); s / c as f64
    }
    /// side 0's value after the turn (i, j), averaged over at least n seeds (always the first seeds of the list, so more seeds only add)
    fn ensure(&mut self, i: usize, j: usize, n: usize) -> f64 {
        let (mut s, mut c) = self.acc.get(&(i, j)).copied().unwrap_or((0.0, 0));
        if c >= n { return s / c as f64; }
        while c < n {
            let mut x = self.b.clone(); x.prng = Prng::gen5(self.cs[c]); x.run_turn([self.msw[i], self.tsw[j]]); resolve_switches(&mut x, self.cfg, None);
            let v = value(&mut x, self.cfg); s += v; *self.sq.entry((i, j)).or_insert(0.0) += v * v;
            for u in &x.unsupported { if !self.uns.contains(u) { self.uns.push(u.clone()); } }
            c += 1; self.sims += 1;
        }
        self.acc.insert((i, j), (s, c)); s / c as f64
    }
    /// the cell at its current precision (at least the base number of seeds); its two-turn value once that has been computed
    fn get(&mut self, i: usize, j: usize) -> f64 {
        if let Some(&(s, c)) = self.acc2.get(&(i, j)) { if c > 0 { return s / c as f64; } }
        let n = self.base; self.ensure(i, j, n)
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
/// EVAL_MATRIX=1's rows / cols: the joint options holding a living slot's actual choice or its most-weighted option
fn matrix_pick(b: &Battle, s: u8, opts: &[[PChoice; 2]], w: &[f64], actual: &Value) -> Vec<usize> {
    let mut keep: Vec<usize> = vec![];
    for i in 0..2 {
        let alive = b.sides[s as usize].active[i].map(|p| !b.p((s, p)).fainted).unwrap_or(false); if !alive { continue; }
        let mut agg: Vec<(PChoice, f64)> = vec![];
        for k in 0..opts.len() { if let Some(e) = agg.iter_mut().find(|e| e.0 == opts[k][i]) { e.1 += w[k]; } else { agg.push((opts[k][i], w[k])); } }
        let mut want: Vec<PChoice> = vec![];
        if let Some(t) = agg.iter().max_by(|a, c| a.1.partial_cmp(&c.1).unwrap()) { want.push(t.0); }
        if let Some(a) = parse_actual(b, s, &actual[i]) { want.push(a); }
        for k in 0..opts.len() { if want.iter().any(|c| same(&opts[k][i], c)) && !keep.contains(&k) { keep.push(k); } }
    }
    keep
}
thread_local! { static LAST_MIX: std::cell::RefCell<Option<Mix>> = const { std::cell::RefCell::new(None) }; }
type Mix = (Vec<[PChoice; 2]>, Vec<[PChoice; 2]>, Vec<f64>, Vec<f64>);
/// the bot's search as a player (2026-10-16, battle4.rs BATTLE_ADAPT_SIDE: the bot's exact search against another in self-play): eval_one
/// on b with no recorded plays, returning both sides' joint options and solved mixes; None when it ended early (no choices to make, or
/// EVAL_DEPTH's tree search, which battle4 runs itself). Reads the same env as evalpos (EVAL_ADAPT, EVAL_SEEDS's count is nseeds here).
pub fn mix(b: &Battle, cfg: &Cfg, key: u64, nseeds: usize) -> Option<Mix> {
    LAST_MIX.with(|c| *c.borrow_mut() = None);
    eval_one(b, cfg, &json!({}), key, nseeds, 0);
    LAST_MIX.with(|c| c.borrow_mut().take())
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
    // EVAL_BUDGET (leaf evaluations) / EVAL_BUDGET_MS: the anytime search below; its cells may take up to EVAL_SEEDS_MAX rolls (default 256)
    // EVAL_BUDGET=spec: the position's own "budget" field (comparisons at matched compute), times EVAL_BUDGET_MULT (default 1)
    let mult: f64 = std::env::var("EVAL_BUDGET_MULT").ok().and_then(|x| x.parse().ok()).unwrap_or(1.0);
    let mut budget = match std::env::var("EVAL_BUDGET").as_deref() {
        Ok("spec") => (sp["budget"].as_f64().unwrap_or(0.0) * mult).round() as usize,
        Ok(x) => (x.parse::<f64>().unwrap_or(0.0) * mult).round() as usize, _ => 0 };
    // EVAL_PERISH_DEPTH=<d> (2026-10-16): with a Perish fight on (plan::perish_on), the tree search with at least d turns beyond this one
    // at EVAL_PERISH_BUDGET (default 80000) leaf evaluations at least
    let mut depth_env: Option<usize> = std::env::var("EVAL_DEPTH").ok().and_then(|x| x.parse::<usize>().ok());
    if let Some(pd) = std::env::var("EVAL_PERISH_DEPTH").ok().and_then(|x| x.parse::<usize>().ok()) { if crate::plan::perish_on(&b) {
        depth_env = Some(depth_env.unwrap_or(0).max(pd)); budget = budget.max(env_usize("EVAL_PERISH_BUDGET", 80000));
    } }
    let budget_ms = env_usize("EVAL_BUDGET_MS", 0) as u128;
    let budgeted = budget > 0 || budget_ms > 0;
    let seeds_max = if budgeted { env_usize("EVAL_SEEDS_MAX", 256).max(nseeds) } else { nseeds };
    let cs: Vec<[u16; 4]> = (0..seeds_max).map(|k| seed4(key ^ ((k as u64) << 52))).collect();
    // EVAL_ADAPT=1: luck samples go where they matter. Every cell gets the first stage's seeds; then, stage by stage, only the options
    // still in contention (in a side's mix, or within the stage's margin of that side's best option) get their cells against the other
    // side's contenders raised to the next stage's seeds, and the turn is solved again. Default stages 2, 8, EVAL_SEEDS with margins
    // 0.15, 0.06 (EVAL_STAGES / EVAL_MARGINS override). Without it every cell gets EVAL_SEEDS seeds, as before.
    let adapt = std::env::var("EVAL_ADAPT").is_ok();
    let list = |name: &str| -> Option<Vec<f64>> { std::env::var(name).ok().map(|v| v.split(',').filter_map(|x| x.trim().parse().ok()).collect()) };
    let mut stages: Vec<usize> = if adapt { list("EVAL_STAGES").map(|v| v.iter().map(|x| *x as usize).collect()).unwrap_or(vec![2, 8, nseeds]) } else { vec![nseeds] };
    stages.retain(|n| *n >= 1 && *n <= nseeds); stages.sort(); stages.dedup(); if stages.last() != Some(&nseeds) { stages.push(nseeds); }
    let margins: Vec<f64> = list("EVAL_MARGINS").unwrap_or(vec![0.15, 0.06]);
    let cs2: Vec<[u16; 4]> = (0..seeds_max).map(|k| seed4(key ^ ((k as u64) << 52) ^ (0xD3u64 << 44))).collect();
    let base0 = if budgeted { env_usize("EVAL_BUDGET_BASE", 2).clamp(1, seeds_max) } else { stages[0] };
    let mut cells = Cells { b: &b, cfg, msw: &msw, tsw: &tsw, cs, base: base0, acc: HashMap::new(), sims: 0, uns: vec![], sq: HashMap::new(), cs2, acc2: HashMap::new(), sims2: 0 };
    // one solve at the cells' current precision: each side's own matrix (all its options against the other side staying in, as
    // battle4.rs), the anticipation pass, then every option's value against the other side's mix (its support above 0.01%)
    let solve = |cells: &mut Cells| -> (Vec<f64>, Vec<f64>, Vec<f64>, Vec<f64>) {
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
        let ysup: Vec<usize> = (0..tsw.len()).filter(|j| y[*j] > 1e-4).collect(); let ytot: f64 = ysup.iter().map(|&j| y[j]).sum();
        let xsup: Vec<usize> = (0..msw.len()).filter(|i| x[*i] > 1e-4).collect(); let xtot: f64 = xsup.iter().map(|&i| x[i]).sum();
        let rv: Vec<f64> = (0..msw.len()).map(|i| ysup.iter().map(|&j| y[j] * cells.get(i, j)).sum::<f64>() / ytot).collect();
        let cv: Vec<f64> = (0..tsw.len()).map(|j| xsup.iter().map(|&i| x[i] * cells.get(i, j)).sum::<f64>() / xtot).collect();
        (x, y, rv, cv)
    };
    // the joint actions actually made (when every living slot's choice is known) always count as in contention, so what a played
    // move cost is measured at full precision even when it is far from the best options
    let actual_joint = |s: u8, opts: &[[PChoice; 2]], actual: &Value| -> Option<usize> {
        let alive: Vec<bool> = (0..2).map(|i| b.sides[s as usize].active[i].map(|p| !b.p((s, p)).fainted).unwrap_or(false)).collect();
        let act: Vec<Option<PChoice>> = (0..2).map(|i| if alive[i] { parse_actual(&b, s, &actual[i]) } else { None }).collect();
        if !(0..2).all(|i| !alive[i] || act[i].is_some()) { return None; }
        opts.iter().position(|c| (0..2).all(|i| !alive[i] || same(&c[i], act[i].as_ref().unwrap()))) };
    let (act_i, act_j) = (actual_joint(0, &msw, &sp["actual"]), actual_joint(1, &tsw, &sp["their_actual"]));
    // EVAL_DEPTH=<d> with a budget (2026-10-14, the user: the budgeted search was meant to look past the next turn): the anytime search
    // as a tree (deep.rs), d turns beyond this one; EVAL_DEPTH=0 is the same allocation without depth (for comparisons at matched
    // compute). The fixed stages, EVAL_HORIZON, EVAL_MATRIX and actual_replace below are not part of it. Before the first solve, so the
    // search's count covers every leaf evaluation (the review, 2026-10-14).
    if let Some(depth) = depth_env { if budgeted {
        let p = crate::deep::Params::from_env(base0, seeds_max);
        if let Some((mut root, mut st)) = crate::deep::search(&b, cfg, key, depth, &p, budget, budget_ms, (act_i, act_j), t0) {
            // EVAL_MATRIX with depth (2026-10-16, the Bo3 bot's contempt): as the staged search's matrix pass, the rows / cols that hold a
            // living slot's actual choice or most-weighted option (every one with "full") get all their cells to EVAL_SEEDS static rolls,
            // the tree is solved again, and the root's table goes out as "matrix" (v1: each cell's estimate with its deep correction)
            let matrix_mode = std::env::var("EVAL_MATRIX").ok().filter(|m| !m.is_empty() && m != "0");
            if let Some(mode) = &matrix_mode {
                let (nm, nt) = (root.msw.len(), root.tsw.len());
                let (rows, cols): (Vec<usize>, Vec<usize>) = if mode == "full" { ((0..nm).collect(), (0..nt).collect()) } else {
                    (matrix_pick(&b, 0, &root.msw, &root.x, &sp["actual"]), matrix_pick(&b, 1, &root.tsw, &root.y, &sp["their_actual"])) };
                // EVAL_MATRIX_MS (2026-10-16, the Bo3 bot: the pass took up to 33 s): no more cells raised once the position has run that
                // long (the rest keep the rolls the search gave them)
                let cap_ms = env_usize("EVAL_MATRIX_MS", 0) as u128;
                let over = |t: &std::time::Instant| cap_ms > 0 && t.elapsed().as_millis() >= cap_ms;
                'rows: for &i in &rows { for j in 0..nt { if over(&t0) { break 'rows; } root.ensure(cfg, i, j, nseeds, &mut st); } }
                'cols: for &j in &cols { for i in 0..nm { if over(&t0) { break 'cols; } root.ensure(cfg, i, j, nseeds, &mut st); } }
                root.resolve(cfg, &mut st);
            }
            let own1: Vec<f64> = root.cv.iter().map(|z| 1.0 - z).collect();
            let s0 = side_report(&b, 0, &root.msw, &root.x, &root.rv, &sp["actual"], top); let s1 = side_report(&b, 1, &root.tsw, &root.y, &own1, &sp["their_actual"], top);
            let mut out = json!({"value": root.v, "static": stat, "feats": f, "seeds": nseeds, "options": [root.msw.len(), root.tsw.len()], "ms": t0.elapsed().as_millis() as u64,
                "unsupported": st.uns, "sides": [s0, s1], "sims": st.sims, "budget": budget, "depth": depth, "nodes": st.nodes, "deep_rolls": st.deep_rolls,
                "levels": root.levels(), "rms_correction": st.rms_correction()});
            if matrix_mode.is_some() {
                let jc = |s: u8, c: &[PChoice; 2]| json!([choice_json(&b, s, &c[0]), choice_json(&b, s, &c[1])]);
                let (v1, n1) = root.table();
                out.as_object_mut().unwrap().insert("matrix".into(), json!({"rows": root.msw.iter().map(|c| jc(0, c)).collect::<Vec<Value>>(),
                    "rl": root.msw.iter().map(|c| label(&b, 0, c)).collect::<Vec<String>>(), "cols": root.tsw.iter().map(|c| jc(1, c)).collect::<Vec<Value>>(),
                    "cl": root.tsw.iter().map(|c| label(&b, 1, c)).collect::<Vec<String>>(), "x": root.x, "y": root.y, "v1": v1, "n1": n1}));
            }
            return out;
        }
    } }
    let (mut x, mut y, mut rv, mut cv) = solve(&mut cells);
    // the anytime search (2026-10-14, the user: think as long as the budget allows): every cell starts at the base rolls; then, round
    // after round, the cells whose next rolls shrink the position value's uncertainty most get one more roll each, and the turn is solved
    // again. A cell's priority is (x_i + f/rows)^2 (y_j + f/cols)^2 sd_ij^2 / (n (n + 1)) (the drop in the variance of x.A.y that one
    // more roll buys), sd floored at EVAL_SD_FLOOR (0.03: two equal rolls are not certainty), f = EVAL_FLOOR (0.05): every cell keeps
    // some attention, since the mixes move as cells sharpen; the actual plays' rows and columns get the floor's attention again. Rounds
    // refine EVAL_BATCH of the cells (0.05). Stops at EVAL_BUDGET leaf evaluations or EVAL_BUDGET_MS milliseconds. The fixed stages
    // below are skipped.
    if budgeted {
        let floor = std::env::var("EVAL_FLOOR").ok().and_then(|x| x.parse().ok()).unwrap_or(0.05f64);
        let sd_floor = std::env::var("EVAL_SD_FLOOR").ok().and_then(|x| x.parse().ok()).unwrap_or(0.03f64);
        let frac = std::env::var("EVAL_BATCH").ok().and_then(|x| x.parse().ok()).unwrap_or(0.05f64);
        let (nr, nc) = (msw.len() as f64, tsw.len() as f64);
        loop {
            if budget > 0 && cells.sims >= budget { break; }
            if budget_ms > 0 && t0.elapsed().as_millis() >= budget_ms { break; }
            let (xt, yt) = (x.iter().sum::<f64>().max(1e-9), y.iter().sum::<f64>().max(1e-9));
            let mut pr: Vec<(f64, usize, usize, usize)> = cells.acc.iter().filter(|(_, &(_, c))| c < seeds_max).map(|(&(i, j), &(sm, c))| {
                let n = c as f64; let m = sm / n; let q = cells.sq.get(&(i, j)).copied().unwrap_or(0.0);
                let var = if c > 1 { ((q - n * m * m) / (n - 1.0)).max(0.0) } else { 0.0 };
                let sd = var.sqrt().max(sd_floor);
                let wx = x[i] / xt + floor / nr + if Some(i) == act_i { floor } else { 0.0 };
                let wy = y[j] / yt + floor / nc + if Some(j) == act_j { floor } else { 0.0 };
                ((wx * wy * sd).powi(2) / (n * (n + 1.0)), i, j, c) }).collect();
            if pr.is_empty() { break; }
            pr.sort_by(|a, c| c.0.partial_cmp(&a.0).unwrap().then((a.1, a.2).cmp(&(c.1, c.2))));
            let k = ((pr.len() as f64 * frac).ceil() as usize).max(1);
            for &(_, i, j, c) in pr.iter().take(k) {
                cells.ensure(i, j, c + 1);
                if budget > 0 && cells.sims >= budget { break; }
            }
            (x, y, rv, cv) = solve(&mut cells);
        }
    }
    for (r, &n) in stages.iter().enumerate().skip(1) {
        if budgeted { break; }
        let margin = margins.get(r - 1).or(margins.last()).copied().unwrap_or(0.06);
        for _ in 0..3 {
            let best_r = rv.iter().cloned().fold(f64::MIN, f64::max); let best_c = cv.iter().cloned().fold(f64::MAX, f64::min);
            let rows: Vec<usize> = (0..msw.len()).filter(|&i| x[i] > 1e-3 || rv[i] >= best_r - margin).collect();
            let cols: Vec<usize> = (0..tsw.len()).filter(|&j| y[j] > 1e-3 || cv[j] <= best_c + margin || Some(j) == act_j).collect();
            let rows: Vec<usize> = if let Some(a) = act_i { if rows.contains(&a) { rows } else { let mut r = rows; r.push(a); r } } else { rows };
            let before = cells.sims;
            for &i in &rows { for &j in &cols { cells.ensure(i, j, n); } }
            if cells.sims == before { break; }
            (x, y, rv, cv) = solve(&mut cells);
        }
    }
    // EVAL_HORIZON=2: a two-turn horizon for the options that matter. Every option in contention by the one-turn solve (in a side's mix,
    // within EVAL_H2_MARGIN (default 0.15) of that side's best, or actually played) gets its cells against the other side's contenders
    // valued after one more turn (battle4::next_value: each side's Protect and strongest hits, no switches, one seed per sample;
    // EVAL_H2_SEEDS samples, default 2), the turn is solved again, and the contention set is widened to what the new solve brings in
    // (up to 3 rounds). Cells outside the set keep their one-turn values. Tests whether the one-turn horizon is what makes the planner
    // Protect and switch less than players do.
    let h2 = env_usize("EVAL_HORIZON", 1) >= 2;
    if h2 {
        let n2 = env_usize("EVAL_H2_SEEDS", 2).clamp(1, nseeds);
        let margin = std::env::var("EVAL_H2_MARGIN").ok().and_then(|x| x.parse().ok()).unwrap_or(0.15);
        for _ in 0..3 {
            let best_r = rv.iter().cloned().fold(f64::MIN, f64::max); let best_c = cv.iter().cloned().fold(f64::MAX, f64::min);
            let mut rows: Vec<usize> = (0..msw.len()).filter(|&i| x[i] > 1e-3 || rv[i] >= best_r - margin).collect();
            let mut cols: Vec<usize> = (0..tsw.len()).filter(|&j| y[j] > 1e-3 || cv[j] <= best_c + margin).collect();
            if let Some(a) = act_i { if !rows.contains(&a) { rows.push(a); } }
            if let Some(a) = act_j { if !cols.contains(&a) { cols.push(a); } }
            let before = cells.sims2;
            for &i in &rows { for &j in &cols { cells.ensure2(i, j, n2); } }
            if cells.sims2 == before { break; }
            (x, y, rv, cv) = solve(&mut cells);
        }
    }
    // EVAL_MATRIX: the payoff matrix for reading departures from the equilibrium (what a play earns against the opponent's actual move)
    let matrix_mode = std::env::var("EVAL_MATRIX").ok().filter(|m| !m.is_empty() && m != "0");
    if let Some(mode) = &matrix_mode {
        let (rows, cols): (Vec<usize>, Vec<usize>) = if mode == "full" { ((0..msw.len()).collect(), (0..tsw.len()).collect()) } else {
            (matrix_pick(&b, 0, &msw, &x, &sp["actual"]), matrix_pick(&b, 1, &tsw, &y, &sp["their_actual"])) };
        for &i in &rows { for j in 0..tsw.len() { cells.ensure(i, j, nseeds); } }
        for &j in &cols { for i in 0..msw.len() { cells.ensure(i, j, nseeds); } }
        (x, y, rv, cv) = solve(&mut cells);
    }
    LAST_MIX.with(|c| *c.borrow_mut() = Some((msw.clone(), tsw.clone(), x.clone(), y.clone())));   // for mix()
    let xsup: Vec<usize> = (0..msw.len()).filter(|i| x[*i] > 1e-4).collect(); let xtot: f64 = xsup.iter().map(|&i| x[i]).sum();
    let v = xsup.iter().map(|&i| x[i] * rv[i]).sum::<f64>() / xtot;
    let own1: Vec<f64> = cv.iter().map(|z| 1.0 - z).collect();
    let s0 = side_report(&b, 0, &msw, &x, &rv, &sp["actual"], top); let s1 = side_report(&b, 1, &tsw, &y, &own1, &sp["their_actual"], top);
    let full = cells.acc.values().filter(|c| c.1 >= nseeds).count();
    let mut out = json!({"value": v, "static": stat, "feats": f, "seeds": nseeds, "options": [msw.len(), tsw.len()], "cells": cells.acc.len(),
           "ms": t0.elapsed().as_millis() as u64, "unsupported": cells.uns, "sides": [s0, s1]});
    if adapt { let o = out.as_object_mut().unwrap(); o.insert("stages".into(), json!(stages)); o.insert("sims".into(), json!(cells.sims)); o.insert("cells_full".into(), json!(full)); }
    {   // value_se: the standard error of x.A.y from the cells' sample spreads (cells independent; a cell with one roll counts at the floor)
        let (xt, yt) = (x.iter().sum::<f64>().max(1e-9), y.iter().sum::<f64>().max(1e-9));
        let sdf = std::env::var("EVAL_SD_FLOOR").ok().and_then(|x| x.parse().ok()).unwrap_or(0.03f64);
        let mut var = 0.0;
        for (&(i, j), &(sm, c)) in cells.acc.iter() {
            let w = x[i] / xt * y[j] / yt; if w <= 0.0 { continue; }
            let n = c as f64; let m = sm / n; let q = cells.sq.get(&(i, j)).copied().unwrap_or(0.0);
            let v = if c > 1 { ((q - n * m * m) / (n - 1.0)).max(0.0) } else { sdf * sdf };
            var += w * w * v / n;
        }
        let o = out.as_object_mut().unwrap(); o.insert("value_se".into(), json!(var.sqrt()));
        if budgeted { o.insert("sims".into(), json!(cells.sims)); o.insert("budget".into(), json!(if budget > 0 { budget } else { 0 })); }
    }
    if h2 { let o = out.as_object_mut().unwrap(); o.insert("horizon".into(), json!(2)); o.insert("cells_h2".into(), json!(cells.acc2.len())); o.insert("sims_h2".into(), json!(cells.sims2)); }
    // the actual cell with the actual replacements (position field "actual_replace": {"0": [species...], "1": [...]}, the Eval bar's luck
    // measure): the same seeds as the matrix cells, pending switches settled by resolve_switches_forced; the matrix itself is unchanged.
    // A slot whose choice the log shows only in part ({none: fainted, by: priority}: not a switch, no move of higher priority; {none:
    // cant}: not a switch; {move: k}: move slot k, any target; mega: true / false) is averaged over that side's mix restricted to the
    // choices it allows (renormalised; uniform over them, at most 24, when the mix gives them nothing)
    if let Some(ar) = sp.get("actual_replace").filter(|v| v.is_object()) {
        let lst = |k: &str| -> std::collections::VecDeque<String> { ar[k].as_array().map(|a| a.iter().filter_map(|x| x.as_str().map(|s| s.to_string())).collect()).unwrap_or_default() };
        let mut bb = b.clone();
        let mut slot_ok = |s: u8, i: usize, c: &PChoice, a: &Value| -> bool {
            if a.is_null() { return true; }
            if let Some(m) = a.get("mega").and_then(|v| v.as_bool()) { if let PChoice::Move(_, _, mg) = c { if *mg != m { return false; } } }
            if a.get("choice").map(|v| !v.is_null()).unwrap_or(false) { return parse_actual(&bb, s, a).map(|x| same(c, &x)).unwrap_or(true); }
            if let Some(k) = a.get("move").and_then(|v| v.as_u64()) { return matches!(c, PChoice::Move(k2, _, _) if *k2 as u64 == k); }
            match a.get("none").and_then(|v| v.as_str()) {
                Some("cant") => !matches!(c, PChoice::Switch(_)),
                Some("fainted") => match c {
                    PChoice::Switch(_) => false,
                    PChoice::Move(k, _, _) => {
                        let Some(by) = a.get("by").and_then(|v| v.as_f64()) else { return true };
                        let Some(pi) = bb.sides[s as usize].active[i] else { return true };
                        let req = bb.request_moves((s, pi));
                        req.get(*k).map(|(mid, _, _)| bb.dex.mv(mid).tmpl.priority <= by).unwrap_or(true)
                    }
                    _ => true },
                _ => true,
            }
        };
        let mut allowed = |s: u8, opts: &[[PChoice; 2]], w: &[f64], actual: &Value| -> Vec<(usize, f64)> {
            let mut v: Vec<(usize, f64)> = (0..opts.len()).filter(|&k| (0..2).all(|i| slot_ok(s, i, &opts[k][i], &actual[i]))).map(|k| (k, w[k])).collect();
            let tot: f64 = v.iter().map(|x| x.1).sum();
            if tot > 1e-9 { v.retain(|x| x.1 / tot >= 1e-3); let t2: f64 = v.iter().map(|x| x.1).sum(); for x in v.iter_mut() { x.1 /= t2; } }
            else { v.truncate(24); let n = v.len().max(1) as f64; for x in v.iter_mut() { x.1 = 1.0 / n; } }
            v };
        let a0 = allowed(0, &msw, &x, &sp["actual"]); let a1 = allowed(1, &tsw, &y, &sp["their_actual"]);
        if !a0.is_empty() && !a1.is_empty() {
            let (mut tot, mut nf, mut sims) = (0.0, 0usize, 0usize);
            for &(i, wi) in &a0 { for &(j, wj) in &a1 {
                let mut sum = 0.0;
                for c in 0..nseeds {
                    let mut xb = b.clone(); xb.prng = Prng::gen5(cells.cs[c]); xb.run_turn([msw[i], tsw[j]]);
                    let mut fq = [lst("0"), lst("1")]; nf += crate::spot::resolve_switches_forced(&mut xb, cfg, &mut fq);
                    sum += value(&mut xb, cfg); sims += 1;
                }
                tot += wi * wj * sum / nseeds as f64;
            } }
            let exact = a0.len() == 1 && a1.len() == 1;
            out.as_object_mut().unwrap().insert("actual_cell".into(), json!({"v": tot, "n": nseeds, "forced": nf as f64 / sims.max(1) as f64,
                "pairs": a0.len() * a1.len(), "exact": exact}));
        }
    }
    if matrix_mode.is_some() {
        let jc = |s: u8, c: &[PChoice; 2]| json!([choice_json(&b, s, &c[0]), choice_json(&b, s, &c[1])]);
        let cell1 = |i: usize, j: usize| cells.acc.get(&(i, j)).copied().map(|(sum, c)| (if c > 0 { json!(sum / c as f64) } else { Value::Null }, c)).unwrap_or((Value::Null, 0));
        let v1: Vec<Vec<Value>> = (0..msw.len()).map(|i| (0..tsw.len()).map(|j| cell1(i, j).0).collect()).collect();
        let n1: Vec<Vec<usize>> = (0..msw.len()).map(|i| (0..tsw.len()).map(|j| cell1(i, j).1).collect()).collect();
        let mut m = json!({"rows": msw.iter().map(|c| jc(0, c)).collect::<Vec<Value>>(), "rl": msw.iter().map(|c| label(&b, 0, c)).collect::<Vec<String>>(),
                           "cols": tsw.iter().map(|c| jc(1, c)).collect::<Vec<Value>>(), "cl": tsw.iter().map(|c| label(&b, 1, c)).collect::<Vec<String>>(),
                           "x": x, "y": y, "v1": v1, "n1": n1});
        if h2 {
            let cell2 = |i: usize, j: usize| cells.acc2.get(&(i, j)).copied().map(|(sum, c)| (if c > 0 { json!(sum / c as f64) } else { Value::Null }, c)).unwrap_or((Value::Null, 0));
            let v2: Vec<Vec<Value>> = (0..msw.len()).map(|i| (0..tsw.len()).map(|j| cell2(i, j).0).collect()).collect();
            let n2: Vec<Vec<usize>> = (0..msw.len()).map(|i| (0..tsw.len()).map(|j| cell2(i, j).1).collect()).collect();
            let o = m.as_object_mut().unwrap(); o.insert("v2".into(), json!(v2)); o.insert("n2".into(), json!(n2));
        }
        out.as_object_mut().unwrap().insert("matrix".into(), m);
    }
    out
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
            let mut b = crate::turntest::new_battle(dex, reg, &sp["state"], Mode::Real);
            if std::env::var("EVAL_REFRESH_DISABLES").map(|v| v != "0").unwrap_or(true) { b.refresh_disables(); }   // see Battle::refresh_disables
            let b = b;
            // EVAL_KEY_SALT (2026-10-14): another draw of every seed, for measuring how much a search's answer moves with its luck alone
            let salt: u64 = std::env::var("EVAL_KEY_SALT").ok().and_then(|x| x.parse().ok()).unwrap_or(0);
            eval_one(&b, cfg, &sp, h ^ 0xE7A1 ^ salt.wrapping_mul(0x9E3779B97F4A7C15), nseeds, top) }));
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


/// champ feats <engine_data.json> <positions.jsonl> <out.jsonl> [threads=1] (champ-battle-v21): the value function's feature vector and
/// static value at each position, no lookahead (for fitting a value on real positions); same env as evalpos (EG_VALUE, RACE, ...).
/// Output per line: name, turn, side, feats, static; positions already in the output are skipped.
pub fn feats_main(args: &[String]) {
    let (dex, reg) = crate::turntest::load_all(&args[0]);
    let cfg: &'static Cfg = Box::leak(Box::new(load_cfg(&std::env::var("GRID_DIR").unwrap_or("../../mxtr".into()))));
    let threads: usize = args.get(3).and_then(|x| x.parse().ok()).unwrap_or(1);
    let lines: Vec<String> = std::fs::read_to_string(&args[1]).unwrap().lines().filter(|l| !l.trim().is_empty()).map(|s| s.to_string()).collect();
    let done: HashSet<String> = std::fs::read_to_string(&args[2]).map(|t| t.lines().filter_map(|l| serde_json::from_str::<Value>(l).ok())
        .filter_map(|v| v["name"].as_str().map(|s| s.to_string())).collect()).unwrap_or_default();
    let out = std::sync::Mutex::new(std::fs::OpenOptions::new().create(true).append(true).open(&args[2]).unwrap());
    let next = std::sync::atomic::AtomicUsize::new(0); let t0 = std::time::Instant::now(); let nd = std::sync::atomic::AtomicUsize::new(0);
    std::thread::scope(|sc| { for _ in 0..threads { sc.spawn(|| { let mut buf: Vec<String> = vec![]; loop {
        let k = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
        if k >= lines.len() || buf.len() >= 200 { let mut f = out.lock().unwrap(); for l in buf.drain(..) { writeln!(f, "{}", l).unwrap(); } if k >= lines.len() { break; } }
        let Ok(sp) = serde_json::from_str::<Value>(&lines[k]) else { continue };
        let name = sp["name"].as_str().map(|s| s.to_string()).unwrap_or(format!("line {}", k + 1));
        if done.contains(&name) { continue; }
        let r = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let mut b = crate::turntest::new_battle(dex, reg, &sp["state"], Mode::Real);
            let f = feats(&mut b, cfg); let v = value(&mut b, cfg); (f, v) }));
        let row = match r {
            Ok((f, v)) => json!({"name": name, "turn": sp["turn"], "side": sp["side"], "feats": f, "static": v}),
            Err(e) => json!({"name": name, "error": e.downcast_ref::<String>().cloned().or(e.downcast_ref::<&str>().map(|s| s.to_string())).unwrap_or("panic".into())}),
        };
        buf.push(row.to_string()); nd.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
    } }); } });
    eprintln!("{} positions in {:?}", nd.load(std::sync::atomic::Ordering::SeqCst), t0.elapsed());
}
/// champ vfeats: vfeats.rs matchup features per position (for fitting a learned value), with plan.rs feats and the static value
pub fn vfeats_main(args: &[String]) {
    let (dex, reg) = crate::turntest::load_all(&args[0]);
    let cfg: &'static Cfg = Box::leak(Box::new(load_cfg(&std::env::var("GRID_DIR").unwrap_or("../../mxtr".into()))));
    let threads: usize = args.get(3).and_then(|x| x.parse().ok()).unwrap_or(1);
    let lines: Vec<String> = std::fs::read_to_string(&args[1]).unwrap().lines().filter(|l| !l.trim().is_empty()).map(|s| s.to_string()).collect();
    let done: HashSet<String> = std::fs::read_to_string(&args[2]).map(|t| t.lines().filter_map(|l| serde_json::from_str::<Value>(l).ok())
        .filter_map(|v| v["name"].as_str().map(|s| s.to_string())).collect()).unwrap_or_default();
    let out = std::sync::Mutex::new(std::fs::OpenOptions::new().create(true).append(true).open(&args[2]).unwrap());
    let next = std::sync::atomic::AtomicUsize::new(0); let t0 = std::time::Instant::now(); let nd = std::sync::atomic::AtomicUsize::new(0);
    std::thread::scope(|sc| { for _ in 0..threads { sc.spawn(|| { let mut buf: Vec<String> = vec![]; loop {
        let k = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
        if k >= lines.len() || buf.len() >= 200 { let mut f = out.lock().unwrap(); for l in buf.drain(..) { writeln!(f, "{}", l).unwrap(); } if k >= lines.len() { break; } }
        let Ok(sp) = serde_json::from_str::<Value>(&lines[k]) else { continue };
        let name = sp["name"].as_str().map(|s| s.to_string()).unwrap_or(format!("line {}", k + 1));
        if done.contains(&name) { continue; }
        let r = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            let mut b = crate::turntest::new_battle(dex, reg, &sp["state"], Mode::Real);
            crate::vfeats::vfeats(&mut b, cfg) }));
        let row = match r {
            Ok(mut o) => { o["name"] = json!(name); o["turn"] = sp["turn"].clone(); o }
            Err(e) => json!({"name": name, "error": e.downcast_ref::<String>().cloned().or(e.downcast_ref::<&str>().map(|s| s.to_string())).unwrap_or("panic".into())}),
        };
        buf.push(row.to_string()); nd.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
    } }); } });
    eprintln!("{} positions in {:?}", nd.load(std::sync::atomic::Ordering::SeqCst), t0.elapsed());
}
