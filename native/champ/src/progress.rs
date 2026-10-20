//! VNET_PROGRESS: the long game the learned value cannot see (planner_issues 21, 2026-10-20; the user: "we played 47 turns horribly
//! while our opponent was probably waiting for a forfeit by turn 15"). Bo1 …2699800290: Simple Beam let a lone Overqwil reach +6
//! evasion and +6 Def / SpD; our hits landed about one in three for a few percent against its Leftovers, Spite drained our PP and
//! Toxapex ended on Struggle. The value read 95-100% from turn 6 to 45 ("3 more Pokemon") and still 68% in the last 1-v-1 on Struggle,
//! so every option looked alike: 8 Toxics into the Poison type, 8 Baneful Bunkers, and no forfeit.
//!
//! In an endgame (5 or fewer Pokemon left in all) each side's damage is played forward to the end, two attackers a turn on the foes
//! one at a time: every living Pokemon's damaging moves with PP (calc.rs mid roll x hit chance with accuracy and evasion stages x
//! hits, PP spent as it goes), against the target's recovery (Leftovers, Black Sludge, Grassy Terrain, Aqua Ring, Ingrain, Poison Heal)
//! and with its chip (poison, burn, Leech Seed, Struggle recoil once it has no PP). Switching, speed, protection and the foe's own
//! turns are left out: it asks whether a side can get through at all, and how long that takes.
//!   - a side that cannot KO the other's team (its damage does not beat their recovery, or runs out of PP first) while the other can
//!     KO its own: lost (z -6, about 0.25%, so the bot forfeits);
//!   - a side that can and the other cannot: won, the sooner the better (z = 5 - 0.8 ln(1 + turns): 2 turns 98.8%, 17 turns 93.6%),
//!     so a won endgame prefers the moves that shorten it;
//!   - both can, and both need 4 turns or more: the net's log-odds kept within 1.5 of the race's (1.5 (their turns - ours) /
//!     sqrt(sum)).
//! Off under Perish Song (VNET_PERISH has that). VNET_PROGRESS=1 for both sides' evaluations, s0 / s1 for one (self-play A/B).
use crate::battle::Battle;
use crate::plan::{alive, hit_chance, race_damage_pub};
use crate::state::{find, MonRef};

pub(crate) fn on() -> [bool; 2] {
    static F: std::sync::OnceLock<[bool; 2]> = std::sync::OnceLock::new();
    *F.get_or_init(|| match std::env::var("VNET_PROGRESS").as_deref() {
        Err(_) | Ok("") | Ok("0") => [false, false], Ok("s0") => [true, false], Ok("s1") => [false, true], _ => [true, true] })
}

fn grounded(b: &Battle, m: MonRef) -> bool {
    let p = b.p(m);
    !(p.types.iter().any(|t| *t == "Flying") || p.ability == "levitate" || p.item == "airballoon" || find(&p.volatiles, "magnetrise").is_some())
}
/// the share of max HP a Pokemon gets back each turn it is on the field, and what it loses (status, Leech Seed, Struggle recoil)
fn upkeep(b: &Battle, m: MonRef) -> (f64, f64) {
    let p = b.p(m); let guard = p.ability == "magicguard";
    let mut rec = 0.0; let mut chip = 0.0;
    if p.item == "leftovers" { rec += 1.0 / 16.0; }
    if p.item == "blacksludge" { if p.types.iter().any(|t| *t == "Poison") { rec += 1.0 / 16.0; } else if !guard { chip += 1.0 / 8.0; } }
    if b.field.terrain == "grassyterrain" && grounded(b, m) { rec += 1.0 / 16.0; }
    if find(&p.volatiles, "aquaring").is_some() { rec += 1.0 / 16.0; }
    if find(&p.volatiles, "ingrain").is_some() { rec += 1.0 / 16.0; }
    let poisoned = p.status == "psn" || p.status == "tox";
    if poisoned && p.ability == "poisonheal" { rec += 1.0 / 8.0; }
    else if !guard {
        if poisoned { chip += 1.0 / 8.0; }
        if p.status == "brn" { chip += 1.0 / 16.0; }
        if find(&p.volatiles, "leechseed").is_some() { chip += 1.0 / 8.0; }
        if p.move_slots.iter().all(|x| x.pp <= 0 || x.disabled) { chip += 1.0 / 4.0; }   // nothing left but Struggle
    }
    (rec, chip)
}

/// turns for side s to KO every living Pokemon of the other side by damage, or None when it cannot
fn turns_to_win(b: &Battle, cd: &crate::data::Data, s: u8) -> Option<f64> {
    let o = 1 - s;
    let mut foes = alive(b, o);
    foes.sort_by_key(|m| !b.p(*m).is_active);   // the ones on the field first
    let atk = alive(b, s);
    if foes.is_empty() { return Some(0.0); }
    if atk.is_empty() { return None; }
    // per attacker, per move slot: PP left and expected share of each foe's HP a use takes
    let scr = ["reflect", "lightscreen", "auroraveil"].iter().enumerate()
        .fold(0u8, |m, (k, x)| if find(&b.sides[o as usize].side_conditions, x).is_some() { m | (1 << k) } else { m });
    let mut pp: Vec<Vec<i64>> = vec![]; let mut dmg: Vec<Vec<Vec<f64>>> = vec![];
    for &a in &atk {
        let (mut pa, mut da) = (vec![], vec![]);
        for sl in &b.p(a).move_slots {
            let mid = sl.id; let tm = &b.dex.mv(mid).tmpl;
            if sl.pp <= 0 || sl.disabled || tm.category == "Status" || mid == "fakeout" || !cd.moves.contains_key(mid) || crate::plan::imprisoned(b, s, mid) { continue; }
            let nh = match tm.multihit { Some((lo, hi)) if lo == hi => lo as f64, Some((_, hi)) => if b.p(a).ability == "skilllink" { hi as f64 } else { 3.1 }, None => 1.0 };
            let row: Vec<f64> = foes.iter().map(|&f| race_damage_pub(b, cd, a, f, mid, false, scr)
                .map(|x| x as f64 / b.p(f).maxhp.max(1) as f64 * hit_chance(b, a, Some(f), mid) * nh).unwrap_or(0.0)).collect();
            pa.push(sl.pp); da.push(row);
        }
        pp.push(pa); dmg.push(da);
    }
    let mut t = 0.0;
    for (j, &f) in foes.iter().enumerate() {
        let (rec, chip) = upkeep(b, f);
        let mut hp = b.p(f).hp as f64 / b.p(f).maxhp.max(1) as f64;
        while hp > 1e-9 {
            // each attacker's best move on f with PP left; the two best attackers act
            let mut best: Vec<(f64, usize, usize)> = (0..atk.len()).filter_map(|i| (0..pp[i].len()).filter(|&k| pp[i][k] > 0)
                .map(|k| (dmg[i][k][j], i, k)).max_by(|x, y| x.0.partial_cmp(&y.0).unwrap())).collect();
            best.sort_by(|x, y| y.0.partial_cmp(&x.0).unwrap()); best.truncate(2);
            let r = best.iter().map(|x| x.0).sum::<f64>() + chip - rec;
            if r <= 1e-4 { return None; }
            // turns until f is down or one of the moves in use runs dry
            let need = (hp / r).ceil().max(1.0);
            let k = best.iter().map(|x| pp[x.1][x.2] as f64).fold(need, f64::min).max(1.0);
            hp -= r * k; t += k;
            for x in &best { pp[x.1][x.2] -= k as i64; }
            if t > 300.0 { return None; }
        }
    }
    Some(t)
}

/// the correction to side 0's log-odds z (None: leave it)
pub(crate) fn adjust(b: &Battle, cd: &crate::data::Data, z: f64) -> f64 {
    let n = alive(b, 0).len() + alive(b, 1).len();
    if n > 5 || n == 0 { return z; }
    let perish = (0..2u8).any(|s| alive(b, s).iter().any(|m| b.p(*m).is_active && find(&b.p(*m).volatiles, "perishsong").is_some()));
    if perish { return z; }
    let cap = |t: f64| 5.0 - 0.8 * (1.0 + t).ln();
    let (t0, t1) = (turns_to_win(b, cd, 0), turns_to_win(b, cd, 1));
    if std::env::var("PROGRESS_DEBUG").is_ok() { eprintln!("progress: side 0 {:?} turns, side 1 {:?}, net z {:.2}", t0, t1, z); }
    match (t0, t1) {
        (None, Some(_)) => -6.0,
        (Some(a), None) => cap(a),
        (Some(a), Some(c)) if a.min(c) >= 4.0 => { let zr = 1.5 * (c - a) / (a + c).sqrt(); z.clamp(zr - 1.5, zr + 1.5) }
        _ => z,
    }
}
