//! Showdown's PRNG (sim/prng.ts, Gen5RNG: 64-bit LCG, top 32 bits per draw) plus the deterministic test modes used by
//! native/gen_turn_cases.js: "lo" (every draw its lowest value), "hi" (highest), "mid" (middle).

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Mode { Real, Lo, Hi, Mid }

#[derive(Clone, Debug)]
pub struct Prng { pub mode: Mode, pub seed: u64, pub draws: u64 }

impl Prng {
    pub fn gen5(words: [u16; 4]) -> Prng {
        let seed = ((words[0] as u64) << 48) | ((words[1] as u64) << 32) | ((words[2] as u64) << 16) | words[3] as u64;
        Prng { mode: Mode::Real, seed, draws: 0 }
    }
    pub fn fake(mode: Mode) -> Prng { Prng { mode, seed: 0, draws: 0 } }
    pub fn words(&self) -> [u16; 4] { [(self.seed >> 48) as u16, (self.seed >> 32) as u16, (self.seed >> 16) as u16, self.seed as u16] }
    fn next(&mut self) -> u64 {
        self.draws += 1;
        self.seed = self.seed.wrapping_mul(0x5D588B656C078965).wrapping_add(0x269EC3);
        self.seed >> 32
    }
    /// random() in [0, 1)
    pub fn frac(&mut self) -> f64 {
        match self.mode { Mode::Real => self.next() as f64 / 4294967296.0, Mode::Lo => { self.draws += 1; 0.0 } Mode::Hi => { self.draws += 1; 0.999999 } Mode::Mid => { self.draws += 1; 0.5 } }
    }
    /// random(n): integer in [0, n)
    pub fn below(&mut self, n: i64) -> i64 {
        match self.mode {
            Mode::Real => ((self.next() * n as u64) >> 32) as i64,
            Mode::Lo => { self.draws += 1; 0 } Mode::Hi => { self.draws += 1; n - 1 } Mode::Mid => { self.draws += 1; n / 2 }
        }
    }
    /// random(from, to): integer in [from, to)
    pub fn range(&mut self, from: i64, to: i64) -> i64 {
        match self.mode {
            Mode::Real => ((self.next() * (to - from) as u64) >> 32) as i64 + from,
            Mode::Lo => { self.draws += 1; from } Mode::Hi => { self.draws += 1; to - 1 } Mode::Mid => { self.draws += 1; from + (to - from) / 2 }
        }
    }
    pub fn chance(&mut self, num: i64, den: i64) -> bool { self.below(den) < num }
    pub fn sample_idx(&mut self, len: usize) -> usize { self.below(len as i64) as usize }
    /// Fisher-Yates over [start, end), as Showdown's PRNG.shuffle
    pub fn shuffle<T>(&mut self, items: &mut [T], mut start: usize, end: usize) {
        while start + 1 < end {
            let ni = self.range(start as i64, end as i64) as usize;
            if ni != start { items.swap(start, ni); }
            start += 1;
        }
    }
}
