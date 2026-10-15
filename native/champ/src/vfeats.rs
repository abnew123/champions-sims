//! Matchup features for a learned position value (2026-10-12, the user: work towards a better position score). The static value
//! (plan.rs `feats` / `value`) misses most of what the one-turn search sees (held-out real games: static log loss 0.557, one-turn search
//! 0.523): who knocks out whom this turn and who moves first, focus fire, priority, Fake Out / Protect / redirection on hand, the bench's
//! threats and switch-ins. `side_feats(b, s)` describes side s's actives against the other side's actives this turn, its bench and what
//! it has on hand; `field_feats(b, s)` the field as side s sees it. A learned value scores a position as h(e) - h(e_swapped) with
//! e = [side 0, side 1, field for 0, plan.rs feats] and e_swapped = [side 1, side 0, field for 1, -feats], so it is symmetric by
//! construction. Nothing here is used in play; `champ vfeats` dumps the vectors.
//!   champ vfeats <engine_data.json> <positions.jsonl> <out.jsonl> [threads]   (env as for battles: RACE=1 CALC_DATA=... for feats)
use crate::battle::*;
use crate::dex::*;
use crate::plan::{alive, hit_chance, race_damage_pub, Cfg};
use crate::state::*;

pub const SIDE_NAMES: [&str; 32] = ["alive", "hp", "actives", "bench alive", "bench hp", "damage potential", "focus potential",
    "foes KO-able alone", "foes KO-able first", "foes KO-able by focus", "outspeeds", "priority potential", "spread potential",
    "Protect on hand", "Fake Out on hand", "redirection on hand", "speed control on hand", "Intimidate on the bench", "bench threat",
    "bench switch-in", "actives in danger", "primary boosts", "Speed boosts", "defence boosts", "asleep/frozen", "paralysed",
    "burned/poisoned", "Mega available", "choice-locked", "Taunted/Encored", "Substitute", "setup on hand"];
pub const FIELD_NAMES: [&str; 12] = ["Trick Room turns", "Trick Room favours me", "my Tailwind", "their Tailwind", "my screens",
    "their screens", "grassy", "psychic", "electric", "misty", "weather turns", "turn"];

fn active(b: &Battle, s: u8) -> Vec<MonRef> {
    (0..2).filter_map(|i| b.sides[s as usize].active[i].map(|x| (s, x))).filter(|m| !b.p(*m).fainted).collect()
}
fn bench(b: &Battle, s: u8) -> Vec<MonRef> { crate::spot::bench(b, s).into_iter().map(|p| (s, p)).collect() }
fn dur(e: Option<&EState>, dflt: i64) -> f64 { e.map(|x| x.duration.filter(|d| *d > 0).unwrap_or(dflt)).unwrap_or(0) as f64 }
fn screens_bits(b: &Battle, s: u8) -> u8 {
    ["reflect", "lightscreen", "auroraveil"].iter().enumerate().fold(0u8, |m, (k, x)| if find(&b.sides[s as usize].side_conditions, x).is_some() { m | (1 << k) } else { m })
}
/// one attacker's damaging options against the foes on the field: per option, (expected damage on each foe, priority usable, spread)
struct Hit { dmg: Vec<f64>, prio: bool, spread: bool }
fn hits(b: &mut Battle, cd: &crate::data::Data, a: MonRef, foes: &[MonRef]) -> Vec<Hit> {
    let mut out = vec![];
    if foes.is_empty() || !cd.species.contains_key(b.p(a).species) { return out; }
    let s = a.0; let o = 1 - s;
    let psy = b.field.terrain == "psychicterrain"; let grassy = b.field.terrain == "grassyterrain";
    // what needs &mut Battle, once per call: grounded foes, a priority-blocking ability on their side
    let grounded: Vec<bool> = if psy { foes.iter().map(|f| b.is_grounded(*f, false) == Some(true)).collect() } else { vec![false; foes.len()] };
    let blocks = active(b, o).iter().any(|m| ["armortail", "dazzling", "queenlymajesty"].contains(&b.p(*m).ability));
    let b: &Battle = b;
    let lock = find(&b.p(a).volatiles, "choicelock").and_then(|cl| cl.get("move").and_then(|v| v.s()));
    let scr = screens_bits(b, o); let skill = b.p(a).ability == "skilllink";
    for sl in &b.p(a).move_slots {
        let mid = sl.id;
        if sl.pp <= 0 || sl.disabled || mid == "fakeout" || lock.map(|l| l != mid).unwrap_or(false) || !cd.moves.contains_key(mid) { continue; }
        let tm = &b.dex.mv(mid).tmpl;
        if tm.category == "Status" { continue; }
        let pr = if mid == "grassyglide" { if grassy { 1 } else { 0 } } else { tm.priority as i64 };
        let spread = (tm.target == "allAdjacentFoes" || tm.target == "allAdjacent") && foes.len() == 2;
        let nh = match tm.multihit { Some((lo, hi)) if lo == hi => lo as f64, Some((_, hi)) => if skill { hi as f64 } else { 3.1 }, None => 1.0 };
        let row = |tg: &[usize]| -> Vec<f64> {
            let mut d = vec![0.0; foes.len()];
            for &j in tg { if let Some(x) = race_damage_pub(b, cd, a, foes[j], mid, spread, scr) { d[j] = x as f64 * hit_chance(b, a, Some(foes[j]), mid) * nh; } }
            d };
        let prio_ok = |j: usize| pr > 0 && !(psy && grounded[j]) && !blocks;
        if spread { let all: Vec<usize> = (0..foes.len()).collect(); out.push(Hit { dmg: row(&all), prio: pr > 0 && (0..foes.len()).all(|j| prio_ok(j)), spread: true }); }
        else { for j in 0..foes.len() { out.push(Hit { dmg: row(&[j]), prio: prio_ok(j), spread: false }); } }
    }
    out
}
fn has_move(b: &Battle, m: MonRef, ids: &[&str]) -> bool { b.p(m).move_slots.iter().any(|x| x.pp > 0 && !x.disabled && ids.contains(&x.id) && !crate::plan::imprisoned(b, m.0, x.id)) }   // an Imprisoned move does not count (2026-10-14)
fn spe(b: &mut Battle, m: MonRef) -> f64 { crate::plan::memo_spe(b, m) }   // get_stat's Speed, once per leaf evaluation (plan.rs EvalMemo)
/// side s's features (SIDE_NAMES)
pub fn side_feats(b: &mut Battle, cd: &crate::data::Data, s: u8) -> Vec<f64> {
    let o = 1 - s;
    let me = active(b, s); let foes = active(b, o); let bn = bench(b, s);
    let al = alive(b, s);
    let frac = |b: &Battle, m: MonRef| b.p(m).hp as f64 / b.p(m).maxhp.max(1) as f64;
    let tr = find(&b.field.pseudo, "trickroom").is_some();
    let mut v = vec![0.0; SIDE_NAMES.len()];
    v[0] = al.len() as f64 / 4.0;
    v[1] = al.iter().map(|m| frac(b, *m)).sum::<f64>() / 4.0;
    v[2] = me.len() as f64 / 2.0;
    v[3] = bn.len() as f64 / 2.0;
    v[4] = bn.iter().map(|m| frac(b, *m)).sum::<f64>() / 2.0;
    // this turn: my actives on their actives (share of each foe's current HP), who moves first
    let fhp: Vec<f64> = foes.iter().map(|f| b.p(*f).hp.max(1) as f64).collect();
    let mut best = vec![vec![0.0f64; foes.len()]; me.len()]; let mut bestp = vec![vec![0.0f64; foes.len()]; me.len()];
    let mut spread_pot = 0.0f64;
    for (i, &a) in me.iter().enumerate() {
        for h in hits(b, cd, a, &foes) {
            for j in 0..foes.len() {
                let x = h.dmg[j] / fhp[j]; best[i][j] = best[i][j].max(x);
                if h.prio { bestp[i][j] = bestp[i][j].max(x); }
            }
            if h.spread { spread_pot = spread_pot.max(h.dmg.iter().zip(&fhp).map(|(d, hp)| (d / hp).min(1.0)).sum::<f64>()); }
        }
    }
    let sp_me: Vec<f64> = me.iter().map(|m| spe(b, *m)).collect(); let sp_foe: Vec<f64> = foes.iter().map(|m| spe(b, *m)).collect();
    let faster = |i: usize, j: usize| -> f64 { let (x, y) = (sp_me[i], sp_foe[j]); if x == y { 0.5 } else if (x > y) != tr { 1.0 } else { 0.0 } };
    if !foes.is_empty() && !me.is_empty() {
        let nf = 2.0;
        v[5] = (0..foes.len()).map(|j| (0..me.len()).map(|i| best[i][j]).fold(0.0, f64::max).min(1.0)).sum::<f64>() / nf;
        v[6] = (0..foes.len()).map(|j| (0..me.len()).map(|i| best[i][j]).sum::<f64>().min(1.0)).sum::<f64>() / nf;
        v[7] = (0..foes.len()).filter(|&j| (0..me.len()).any(|i| best[i][j] >= 1.0)).count() as f64 / nf;
        v[8] = (0..foes.len()).filter(|&j| (0..me.len()).any(|i| bestp[i][j] >= 1.0 || (best[i][j] >= 1.0 && faster(i, j) == 1.0))).count() as f64 / nf;
        v[9] = (0..foes.len()).filter(|&j| (0..me.len()).map(|i| best[i][j]).sum::<f64>() >= 1.0).count() as f64 / nf;
        v[10] = (0..me.len()).flat_map(|i| (0..foes.len()).map(move |j| (i, j))).map(|(i, j)| faster(i, j)).sum::<f64>() / (me.len() * foes.len()) as f64;
        v[11] = bestp.iter().flatten().fold(0.0f64, |m, x| m.max(*x)).min(1.0);
        v[12] = spread_pot / 2.0;
    }
    v[13] = me.iter().filter(|m| b.p(**m).move_slots.iter().any(|x| x.pp > 0 && !x.disabled && b.dex.mv(x.id).tmpl.stalling_move) && find(&b.p(**m).volatiles, "stall").is_none()).count() as f64 / 2.0;
    v[14] = me.iter().filter(|m| b.p(**m).active_move_actions == 0 && has_move(b, **m, &["fakeout"])).count() as f64 / 2.0;
    v[15] = me.iter().filter(|m| has_move(b, **m, &["followme", "ragepowder"])).count() as f64 / 2.0;
    v[16] = al.iter().filter(|m| has_move(b, **m, &["tailwind", "trickroom", "icywind", "electroweb"])).count() as f64 / 2.0;
    v[17] = bn.iter().filter(|m| b.p(**m).ability == "intimidate").count() as f64 / 2.0;
    // the bench: its best hit on their actives, and how safely its sturdiest member comes in (1 - the most a foe active takes off it)
    if !foes.is_empty() {
        let mut bt = 0.0f64; let mut safe = 0.0f64;
        for &m in &bn {
            for h in hits(b, cd, m, &foes) { for j in 0..foes.len() { bt = bt.max((h.dmg[j] / fhp[j]).min(1.0)); } }
            let mhp = b.p(m).hp.max(1) as f64; let mut taken = 0.0f64;
            for &f in &foes { for h in hits(b, cd, f, &[m]) { taken = taken.max(h.dmg[0] / mhp); } }
            safe = safe.max(1.0 - taken.min(1.0));
        }
        v[18] = bt; v[19] = safe;
    }
    // my actives in danger: per active, their two actives' best hits on it summed (focus), capped, averaged
    if !foes.is_empty() {
        let mut d = 0.0;
        for &a in &me { let hp = b.p(a).hp.max(1) as f64; let mut tot = 0.0; for &f in &foes { tot += hits(b, cd, f, &[a]).iter().map(|h| h.dmg[0] / hp).fold(0.0, f64::max); } d += tot.min(1.0); }
        v[20] = d / 2.0;
    }
    for &m in &me {
        let p = b.p(m); let pa = if p.stored[1] >= p.stored[3] { 0 } else { 2 };
        v[21] += p.boosts[pa].clamp(-3, 3) as f64 / 6.0; v[22] += p.boosts[4].clamp(-3, 3) as f64 / 6.0; v[23] += (p.boosts[1] + p.boosts[3]).clamp(-4, 4) as f64 / 8.0;
    }
    for m in &al {
        match b.p(*m).status { "slp" | "frz" => v[24] += 0.25, "par" => v[25] += 0.25, "brn" | "psn" | "tox" => v[26] += 0.25, _ => {} }
    }
    v[27] = if al.iter().any(|m| b.p(*m).can_mega_evo.is_some()) { 1.0 } else { 0.0 };
    v[28] = me.iter().filter(|m| find(&b.p(**m).volatiles, "choicelock").is_some()).count() as f64 / 2.0;
    v[29] = me.iter().filter(|m| find(&b.p(**m).volatiles, "taunt").is_some() || find(&b.p(**m).volatiles, "encore").is_some()).count() as f64 / 2.0;
    v[30] = me.iter().filter(|m| find(&b.p(**m).volatiles, "substitute").is_some()).count() as f64 / 2.0;
    v[31] = me.iter().filter(|m| b.p(**m).move_slots.iter().any(|x| x.pp > 0 && !x.disabled && { let t = &b.dex.mv(x.id).tmpl; t.category == "Status" && t.target == "self" && t.base.boosts.as_ref().map(|bs| bs.iter().any(|(_, k)| *k > 0)).unwrap_or(false) })).count() as f64 / 2.0;
    v
}
/// the field as side s sees it (FIELD_NAMES)
pub fn field_feats(b: &mut Battle, s: u8) -> Vec<f64> {
    let o = 1 - s;
    let trl = dur(find(&b.field.pseudo, "trickroom"), 5);
    let mean = |b: &mut Battle, s: u8| { let a = active(b, s); if a.is_empty() { 0.0 } else { a.iter().map(|m| spe(b, *m)).sum::<f64>() / a.len() as f64 } };
    let (ms, os) = (mean(b, s), mean(b, o));
    let scr = |b: &Battle, s: u8| ["reflect", "lightscreen", "auroraveil"].iter().map(|k| dur(find(&b.sides[s as usize].side_conditions, k), 5)).sum::<f64>();
    let t = b.field.terrain; let tl = dur(Some(&b.field.terrain_state), 5) / 5.0;
    let wl = if b.field.weather.is_empty() { 0.0 } else { dur(Some(&b.field.weather_state), 5) / 5.0 };
    vec![trl / 5.0, if trl > 0.0 { (os - ms).signum() * trl / 5.0 } else { 0.0 },
         dur(find(&b.sides[s as usize].side_conditions, "tailwind"), 4) / 4.0, dur(find(&b.sides[o as usize].side_conditions, "tailwind"), 4) / 4.0,
         scr(b, s) / 10.0, scr(b, o) / 10.0,
         if t == "grassyterrain" { tl } else { 0.0 }, if t == "psychicterrain" { tl } else { 0.0 }, if t == "electricterrain" { tl } else { 0.0 }, if t == "mistyterrain" { tl } else { 0.0 },
         wl, (b.turn as f64).min(20.0) / 10.0]
}
pub fn vfeats(b: &mut Battle, cfg: &Cfg) -> serde_json::Value {
    let cd = cfg.cdata.expect("vfeats needs CALC_DATA (the damage calc)");
    let f0 = side_feats(b, cd, 0); let f1 = side_feats(b, cd, 1);
    let g0 = field_feats(b, 0); let g1 = field_feats(b, 1);
    let x = crate::plan::feats(b, cfg); let v = crate::plan::value(b, cfg);
    serde_json::json!({"f0": f0, "f1": f1, "g0": g0, "g1": g1, "x": x, "static": v})
}
