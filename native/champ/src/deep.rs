//! The anytime search with depth (2026-10-14, the user: the budgeted search was meant to look past the next turn; its first cut only
//! spread rolls over the one-turn table). A tree of one-turn tables. A node is a position's table, solved as evalpos solves it (each
//! side's options against the other staying in, plus the anticipation pass); a cell's rolls are the turn played with roll k's luck and
//! valued by the static value (the net). A cell can also be deepened roll by roll: roll k's position after the turn becomes a node of
//! its own (its table at EVAL_CHILD_BASE rolls a cell, solved), and the cell's estimate becomes
//!     mean of its static rolls + mean over its deep rolls of (child value - that roll's static value)
//! so the static rolls keep averaging the luck while the deep rolls correct the static value's error (a control variate). Every round
//! takes the actions that remove the most variance from the root's value per leaf evaluation, anywhere in the tree:
//!     one more static roll of a cell:  W (x_i y_j)^2 sd^2 / (n (n + 1))                       per 1 evaluation
//!     one more deep roll of a cell:    W (x_i y_j)^2 e^2 / (K (K + 1)), K = 0: W (x_i y_j)^2 e^2   per a child's cost
//!     anything inside a child:         its own priority, with W (x_i y_j)^2 / K^2 as the child's W
//! W is the node's weight (1 at the root), x_i / y_j the mixes' weights plus EVAL_FLOOR / options (the actual plays' rows and columns at
//! the root get the floor again), sd a cell's roll spread (at least EVAL_SD_FLOOR), e^2 the spread of the cell's corrections (with fewer
//! than two deep rolls: the mean square correction over the tree so far, starting from EVAL_DEEP_SD0 = 0.05). A node deepens while it
//! has depth left (EVAL_DEPTH at the root: turns beyond the root's turn). Rounds spend about EVAL_ROUND (2%) of the budget; only the
//! nodes whose cells changed are solved again. Every value is side 0's win chance.
use crate::battle::*;
use crate::plan::*;
use crate::prng::Prng;
use crate::sim::PChoice;
use crate::spot::{joint, resolve_switches, seed4};
use std::collections::HashMap;

fn envf(name: &str, d: f64) -> f64 { std::env::var(name).ok().and_then(|x| x.parse().ok()).unwrap_or(d) }

pub struct Params { pub base: usize, pub child_base: usize, pub seeds_max: usize, pub floor: f64, pub sd_floor: f64, pub sd0: f64, pub round: f64 }
impl Params {
    pub fn from_env(base: usize, seeds_max: usize) -> Params {
        Params { base: base.max(1), child_base: envf("EVAL_CHILD_BASE", 1.0).max(1.0) as usize, seeds_max, floor: envf("EVAL_FLOOR", 0.05),
                 sd_floor: envf("EVAL_SD_FLOOR", 0.03), sd0: envf("EVAL_DEEP_SD0", 0.05), round: envf("EVAL_ROUND", 0.02) }
    }
}
#[derive(Default)]
pub struct Stats { pub sims: usize, pub nodes: usize, pub deep_rolls: usize, pub uns: Vec<String>, err_n: usize, err_sq: f64, cost_n: usize, cost_sum: f64 }
impl Stats {
    /// the mean square correction so far, shrunk toward EVAL_DEEP_SD0^2 by five pseudo-observations
    fn err_ms(&self, p: &Params) -> f64 { (self.err_sq + 5.0 * p.sd0 * p.sd0) / (self.err_n as f64 + 5.0) }
    pub fn rms_correction(&self) -> f64 { if self.err_n == 0 { 0.0 } else { (self.err_sq / self.err_n as f64).sqrt() } }
}
struct Cell { st: Vec<f64>, sum: f64, sq: f64, deep: Vec<Deep> }
/// a deep roll: the child's value; node None when the child position is over or has no choices (its static value is then exact)
struct Deep { v: f64, node: Option<Box<Node>> }
impl Cell {
    fn est(&self) -> f64 {
        let ms = self.sum / self.st.len().max(1) as f64;
        if self.deep.is_empty() { return ms; }
        ms + self.deep.iter().enumerate().map(|(q, d)| d.v - self.st[q]).sum::<f64>() / self.deep.len() as f64
    }
    fn var_st(&self) -> f64 { let n = self.st.len() as f64; if n < 2.0 { 0.0 } else { ((self.sq - self.sum * self.sum / n) / (n - 1.0)).max(0.0) } }
    fn var_err(&self) -> Option<f64> {
        let k = self.deep.len(); if k < 2 { return None; }
        let e: Vec<f64> = self.deep.iter().enumerate().map(|(q, d)| d.v - self.st[q]).collect();
        let m = e.iter().sum::<f64>() / k as f64; Some(e.iter().map(|x| (x - m) * (x - m)).sum::<f64>() / (k - 1) as f64)
    }
}
pub struct Node { b: Battle, pub msw: Vec<[PChoice; 2]>, pub tsw: Vec<[PChoice; 2]>, mns: Vec<usize>, tns: Vec<usize>,
    cells: HashMap<(usize, usize), Cell>, pub x: Vec<f64>, pub y: Vec<f64>, pub rv: Vec<f64>, pub cv: Vec<f64>, pub v: f64,
    depth: usize, key: u64, base: usize, dirty: bool, act: (Option<usize>, Option<usize>) }
#[derive(Clone, Copy)]
enum Act { Roll(usize, usize), Deep(usize, usize) }
struct Cand { pri: f64, path: Vec<(usize, usize, usize)>, act: Act }

fn no_sw(c: &[PChoice; 2]) -> bool { !c.iter().any(|x| matches!(x, PChoice::Switch(_))) }
fn mix64(k: u64) -> u64 { let mut z = k.wrapping_add(0x9E3779B97F4A7C15); z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9); z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB); z ^ (z >> 31) }

impl Node {
    /// a node for b with its table at `base` rolls a cell, solved; None when the game is over or a side has no choices
    fn new(mut b: Battle, cfg: &Cfg, depth: usize, key: u64, base: usize, st: &mut Stats) -> Option<Node> {
        if b.ended { return None; }
        let msw = joint(&mut b, 0, true); let tsw = joint(&mut b, 1, true);
        if msw.is_empty() || tsw.is_empty() { return None; }
        let mns: Vec<usize> = (0..msw.len()).filter(|&i| no_sw(&msw[i])).collect();
        let tns: Vec<usize> = (0..tsw.len()).filter(|&j| no_sw(&tsw[j])).collect();
        let mut n = Node { b, msw, tsw, mns, tns, cells: HashMap::new(), x: vec![], y: vec![], rv: vec![], cv: vec![], v: 0.5, depth, key, base, dirty: true, act: (None, None) };
        st.nodes += 1; n.solve(cfg, st);
        Some(n)
    }
    /// roll k's luck: the same seeds as evalpos's cells at the root (key ^ k << 52)
    fn after(&self, cfg: &Cfg, i: usize, j: usize, k: usize, st: &mut Stats) -> Battle {
        let mut x = self.b.clone(); x.prng = Prng::gen5(seed4(self.key ^ ((k as u64) << 52))); x.run_turn([self.msw[i], self.tsw[j]]); resolve_switches(&mut x, cfg, None);
        for u in &x.unsupported { if !st.uns.contains(u) { st.uns.push(u.clone()); } }
        x
    }
    fn roll(&mut self, cfg: &Cfg, i: usize, j: usize, st: &mut Stats) {
        let k = self.cells.get(&(i, j)).map(|c| c.st.len()).unwrap_or(0);
        let mut x = self.after(cfg, i, j, k, st); let v = value(&mut x, cfg); st.sims += 1;
        let c = self.cells.entry((i, j)).or_insert(Cell { st: vec![], sum: 0.0, sq: 0.0, deep: vec![] });
        c.st.push(v); c.sum += v; c.sq += v * v;
    }
    fn get(&mut self, cfg: &Cfg, i: usize, j: usize, st: &mut Stats) -> f64 {
        while self.cells.get(&(i, j)).map(|c| c.st.len()).unwrap_or(0) < self.base { self.roll(cfg, i, j, st); }
        self.cells[&(i, j)].est()
    }
    /// the cell's next deep roll: roll K's position after the turn searched as a node one turn shallower
    fn deepen(&mut self, cfg: &Cfg, i: usize, j: usize, p: &Params, st: &mut Stats) {
        let k = self.cells.get(&(i, j)).map(|c| c.deep.len()).unwrap_or(0);
        while self.cells.get(&(i, j)).map(|c| c.st.len()).unwrap_or(0) <= k { self.roll(cfg, i, j, st); }
        let s_k = self.cells[&(i, j)].st[k];
        let child = self.after(cfg, i, j, k, st);
        let before = st.sims;
        let ck = mix64(self.key ^ ((i as u64) << 44) ^ ((j as u64) << 24) ^ (k as u64) ^ 0xDEE9);
        let node = Node::new(child, cfg, self.depth.saturating_sub(1), ck, p.child_base, st);
        if node.is_some() { st.cost_n += 1; st.cost_sum += (st.sims - before) as f64; }
        let v = node.as_ref().map(|n| n.v).unwrap_or(s_k);
        st.deep_rolls += 1; st.err_n += 1; st.err_sq += (v - s_k) * (v - s_k);
        self.cells.get_mut(&(i, j)).unwrap().deep.push(Deep { v, node: node.map(Box::new) });
    }
    /// solve the table at the cells' current estimates (as evalpos's solve), and the node's value from it
    fn solve(&mut self, cfg: &Cfg, st: &mut Stats) {
        let (nm, nt) = (self.msw.len(), self.tsw.len());
        let (mns, tns) = (self.mns.clone(), self.tns.clone());
        let mut table = |me: &mut Node, rows: &[usize], cols: &[usize]| -> Vec<Vec<f64>> {
            rows.iter().map(|&i| cols.iter().map(|&j| me.get(cfg, i, j, st)).collect()).collect() };
        let all_m: Vec<usize> = (0..nm).collect(); let all_t: Vec<usize> = (0..nt).collect();
        let mut x = if tns.is_empty() { vec![1.0 / nm as f64; nm] } else { nash(&table(self, &all_m, &tns), 400).0 };
        let mut y = if mns.is_empty() { vec![1.0 / nt as f64; nt] } else { nash(&table(self, &mns, &all_t), 400).1 };
        let isw: Vec<usize> = (0..nm).filter(|&i| !no_sw(&self.msw[i]) && x[i] > 0.02).collect();
        let jsw: Vec<usize> = (0..nt).filter(|&j| !no_sw(&self.tsw[j]) && y[j] > 0.02).collect();
        if !jsw.is_empty() { let cols: Vec<usize> = tns.iter().chain(jsw.iter()).copied().collect(); x = nash(&table(self, &all_m, &cols), 400).0; }
        if !isw.is_empty() { let rows: Vec<usize> = mns.iter().chain(isw.iter()).copied().collect(); y = nash(&table(self, &rows, &all_t), 400).1; }
        let ysup: Vec<usize> = (0..nt).filter(|&j| y[j] > 1e-4).collect(); let ytot: f64 = ysup.iter().map(|&j| y[j]).sum();
        let xsup: Vec<usize> = (0..nm).filter(|&i| x[i] > 1e-4).collect(); let xtot: f64 = xsup.iter().map(|&i| x[i]).sum();
        let rv: Vec<f64> = (0..nm).map(|i| ysup.iter().map(|&j| y[j] * self.get(cfg, i, j, st)).sum::<f64>() / ytot).collect();
        let cv: Vec<f64> = (0..nt).map(|j| xsup.iter().map(|&i| x[i] * self.get(cfg, i, j, st)).sum::<f64>() / xtot).collect();
        self.v = xsup.iter().map(|&i| x[i] * rv[i]).sum::<f64>() / xtot;
        self.x = x; self.y = y; self.rv = rv; self.cv = cv; self.dirty = false;
    }
    /// solve again every node whose cells changed, deepest first, carrying the children's values up
    fn refresh(&mut self, cfg: &Cfg, st: &mut Stats) {
        if !self.dirty { return; }
        for c in self.cells.values_mut() { for d in c.deep.iter_mut() { if let Some(n) = d.node.as_mut() { if n.dirty { n.refresh(cfg, st); d.v = n.v; } } } }
        self.solve(cfg, st);
    }
    fn collect(&self, w: f64, path: &mut Vec<(usize, usize, usize)>, p: &Params, e2: f64, child_cost: f64, out: &mut Vec<Cand>) {
        let xt = self.x.iter().sum::<f64>().max(1e-9); let yt = self.y.iter().sum::<f64>().max(1e-9);
        let (nr, nc) = (self.msw.len() as f64, self.tsw.len() as f64); let sdf2 = p.sd_floor * p.sd_floor;
        for (&(i, j), c) in &self.cells {
            let wx = self.x[i] / xt + p.floor / nr + if Some(i) == self.act.0 { p.floor } else { 0.0 };
            let wy = self.y[j] / yt + p.floor / nc + if Some(j) == self.act.1 { p.floor } else { 0.0 };
            let ww = w * (wx * wy) * (wx * wy);
            let n = c.st.len() as f64;
            if c.st.len() < p.seeds_max { out.push(Cand { pri: ww * c.var_st().max(sdf2) / (n * (n + 1.0)), path: path.clone(), act: Act::Roll(i, j) }); }
            let k = c.deep.len() as f64;
            if self.depth >= 1 && c.deep.len() < p.seeds_max {
                let g = if c.deep.is_empty() { e2 } else { c.var_err().unwrap_or(e2) / (k * (k + 1.0)) };
                out.push(Cand { pri: ww * g / child_cost, path: path.clone(), act: Act::Deep(i, j) });
            }
            for (q, d) in c.deep.iter().enumerate() { if let Some(nd) = &d.node { path.push((i, j, q)); nd.collect(ww / (k * k), path, p, e2, child_cost, out); path.pop(); } }
        }
    }
    /// the node at a path, marking every node on the way as changed
    fn at_mut(&mut self, path: &[(usize, usize, usize)]) -> &mut Node {
        self.dirty = true;
        if path.is_empty() { return self; }
        let (i, j, q) = path[0];
        self.cells.get_mut(&(i, j)).unwrap().deep[q].node.as_mut().unwrap().at_mut(&path[1..])
    }
    /// turns searched below this node at the deepest
    pub fn levels(&self) -> usize { self.cells.values().flat_map(|c| c.deep.iter()).filter_map(|d| d.node.as_ref()).map(|n| 1 + n.levels()).max().unwrap_or(0) }
}

/// the anytime search from b: `depth` turns beyond b's may be searched; stops at `budget` leaf evaluations or `budget_ms` milliseconds
/// (since t0). act: the actual plays' row and column at the root, if known (they keep some attention). None when b has no choices.
pub fn search(b: &Battle, cfg: &Cfg, key: u64, depth: usize, p: &Params, budget: usize, budget_ms: u128, act: (Option<usize>, Option<usize>), t0: std::time::Instant) -> Option<(Node, Stats)> {
    let mut st = Stats::default();
    let mut root = Node::new(b.clone(), cfg, depth, key, p.base, &mut st)?;
    root.act = act; root.dirty = true; root.refresh(cfg, &mut st);
    loop {
        if budget > 0 && st.sims >= budget { break; }
        if budget_ms > 0 && t0.elapsed().as_millis() >= budget_ms { break; }
        let cc = if st.cost_n > 0 { st.cost_sum / st.cost_n as f64 } else { (root.cells.len() * p.child_base) as f64 }.max(1.0);
        let mut cands = vec![]; root.collect(1.0, &mut vec![], p, st.err_ms(p), cc, &mut cands);
        if cands.is_empty() { break; }
        cands.sort_by(|a, c| c.pri.partial_cmp(&a.pri).unwrap_or(std::cmp::Ordering::Equal));
        let quota = if budget > 0 { budget as f64 * p.round } else { st.sims as f64 * 0.05 }.max(32.0);
        let start = st.sims;
        for c in &cands {
            if (st.sims - start) as f64 >= quota || (budget > 0 && st.sims >= budget) { break; }
            // no deep roll the budget left cannot pay for (a child's table is spent whole): compute stays matched to depth 0's
            if matches!(c.act, Act::Deep(..)) && budget > 0 && ((budget - st.sims) as f64) < cc { continue; }
            let nd = root.at_mut(&c.path);
            match c.act { Act::Roll(i, j) => nd.roll(cfg, i, j, &mut st), Act::Deep(i, j) => nd.deepen(cfg, i, j, p, &mut st) }
        }
        if st.sims == start { break; }
        root.refresh(cfg, &mut st);
    }
    Some((root, st))
}

/// BATTLE_EVAL=1 (champ battle): both sides choose each turn by this search, BATTLE_EVAL_BUDGET leaf evaluations (default 20000) a
/// decision (BATTLE_EVAL_BUDGET_0 / _1: one side's own), BATTLE_EVAL_DEPTH_0 / BATTLE_EVAL_DEPTH_1 the turns each may look beyond the
/// current one (default 0). Returns ([budget, depth] for side 0, for side 1).
pub fn battle_eval() -> Option<[[usize; 2]; 2]> {
    static F: std::sync::OnceLock<Option<[[usize; 2]; 2]>> = std::sync::OnceLock::new();
    *F.get_or_init(|| {
        if std::env::var("BATTLE_EVAL").map(|v| v == "0").unwrap_or(true) { return None; }
        let u = |k: &str, d: usize| std::env::var(k).ok().and_then(|x| x.parse().ok()).unwrap_or(d);
        let b = u("BATTLE_EVAL_BUDGET", 20000);
        Some(std::array::from_fn(|s| [u(&format!("BATTLE_EVAL_BUDGET_{}", s), b), u(&format!("BATTLE_EVAL_DEPTH_{}", s), 0)])) })
}
