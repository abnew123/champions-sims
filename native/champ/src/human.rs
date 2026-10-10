//! `champ play` (2026-10-10, the user: "set up a simple ui so that you could play me directly"): a human on side 0 against the planner
//! on side 1, over JSON lines on stdin / stdout. Each prompt is one line {"type": "turn" | "switch", "turn", "state", "options", "log"}
//! and the reply one line {"choice": <option index>}; the game ends with {"type": "end", ...}. The state carries both sides in full
//! (species, HP, status, boosts, items, abilities, moves with PP, volatiles, field and side conditions): the same information the
//! planner has in self-play, so the test is piloting alone. Protocol lines the engine logged since the last prompt come along as `log`.
use crate::battle::Battle;
use crate::sim::PChoice;
use crate::state::{EState, Pokemon};
type Id = &'static str;
use serde_json::{json, Value};
use std::io::{BufRead, Write};

pub struct Human { log_pos: usize }
impl Human {
    pub fn new() -> Human { Human { log_pos: 0 } }
    fn mon_json(b: &Battle, p: &Pokemon, slot: Option<usize>) -> Value {
        let name = b.dex.species.get(p.species).map(|x| x.name).unwrap_or(p.species);
        let base = b.dex.species.get(p.base_species).map(|x| x.name).unwrap_or(p.base_species);
        let eff = |v: &[(Id, EState)]| v.iter().map(|(id, st)| json!({"id": id, "turns": st.duration})).collect::<Vec<Value>>();
        json!({"name": name, "base": base, "slot": slot, "hp": p.hp, "maxhp": p.maxhp, "status": p.status, "boosts": p.boosts, "item": p.item,
               "ability": p.ability, "types": p.types, "fainted": p.fainted, "active": p.is_active, "mega": p.species != p.base_species,
               "volatiles": eff(&p.volatiles),
               "moves": p.move_slots.iter().map(|m| json!({"id": m.id, "name": b.dex.mv(m.id).tmpl.name, "pp": m.pp, "maxpp": m.maxpp, "disabled": m.disabled})).collect::<Vec<Value>>()})
    }
    pub fn state_json(b: &Battle) -> Value {
        let eff = |v: &[(Id, EState)]| v.iter().map(|(id, st)| json!({"id": id, "turns": st.duration})).collect::<Vec<Value>>();
        let side = |s: usize| {
            let sd = &b.sides[s];
            let active: Vec<Value> = (0..2).map(|k| match sd.active[k] { Some(pi) if !sd.pokemon[pi as usize].fainted => Self::mon_json(b, &sd.pokemon[pi as usize], Some(k)), _ => Value::Null }).collect();
            let bench: Vec<Value> = sd.pokemon.iter().filter(|p| !p.is_active && !p.fainted).map(|p| Self::mon_json(b, p, None)).collect();
            let fainted: Vec<Value> = sd.pokemon.iter().filter(|p| p.fainted).map(|p| Self::mon_json(b, p, None)).collect();
            json!({"active": active, "bench": bench, "fainted": fainted, "conditions": eff(&sd.side_conditions)}) };
        json!({"turn": b.turn, "field": {"weather": b.field.weather, "weather_turns": b.field.weather_state.duration, "terrain": b.field.terrain,
               "terrain_turns": b.field.terrain_state.duration, "pseudo": eff(&b.field.pseudo)}, "sides": [side(0), side(1)]})
    }
    /// one slot's part of a joint choice, as the player reads it
    pub fn slot_label(b: &Battle, s: u8, k: usize, c: &PChoice) -> String {
        let name = |m: crate::state::MonRef| b.dex.species.get(b.p(m).species).map(|x| x.name).unwrap_or("?").to_string();
        let Some(pi) = b.sides[s as usize].active[k] else { return "-".into() }; let m = (s, pi);
        if b.p(m).fainted { return "-".into(); }
        match *c {
            PChoice::Move(sl, t, mega) => {
                let p = b.p(m);
                let locked: Option<&str> = if crate::state::find(&p.volatiles, "mustrecharge").is_some() { Some("Recharge") }
                    else { ["twoturnmove", "lockedmove"].iter().find_map(|v| crate::state::find(&p.volatiles, v).and_then(|st| st.get("move").and_then(|x| x.s()))).map(|mid| b.dex.mv(mid).tmpl.name) };
                let mv = match locked { Some(n) => n, None => p.move_slots.get(sl).map(|x| b.dex.mv(x.id).tmpl.name).unwrap_or("?") };
                let tgt = if t > 0 { b.sides[1 - s as usize].active[t as usize - 1].map(|x| format!(" -> {}", name((1 - s, x)))).unwrap_or_default() }
                          else if t < 0 { b.sides[s as usize].active[(-t) as usize - 1].map(|x| format!(" -> {} (ally)", name((s, x)))).unwrap_or(" -> ally".into()) } else { String::new() };
                format!("{}{}{}", mv, tgt, if mega { " (Mega)" } else { "" })
            }
            PChoice::Switch(pos) => format!("switch to {}", name((s, pos))),
            PChoice::Pass => "pass".into(),
        }
    }
    fn prompt(&mut self, b: &Battle, kind: &str, turn: usize, opts: &[[PChoice; 2]]) -> usize {
        let options: Vec<Value> = opts.iter().enumerate().map(|(i, c)| json!({"i": i, "slots": [Self::slot_label(b, 0, 0, &c[0]), Self::slot_label(b, 0, 1, &c[1])]})).collect();
        let log: Vec<&String> = b.log[self.log_pos.min(b.log.len())..].iter().collect(); self.log_pos = b.log.len();
        let out = json!({"type": kind, "turn": turn, "state": Self::state_json(b), "options": options, "log": log});
        let so = std::io::stdout(); let mut h = so.lock(); writeln!(h, "{}", out).unwrap(); h.flush().unwrap();
        let mut line = String::new();
        loop {
            line.clear();
            if std::io::stdin().lock().read_line(&mut line).unwrap_or(0) == 0 { std::process::exit(0); }
            if let Ok(v) = serde_json::from_str::<Value>(&line) { if let Some(i) = v["choice"].as_u64() { if (i as usize) < opts.len() { return i as usize; } } }
            eprintln!("play: bad reply {:?}", line.trim());
        }
    }
    pub fn choose_turn(&mut self, b: &Battle, turn: usize, opts: &[[PChoice; 2]]) -> usize { self.prompt(b, "turn", turn, opts) }
    pub fn choose_switch(&mut self, b: &Battle, turn: usize, opts: &[[PChoice; 2]]) -> usize { if opts.len() <= 1 { return 0; } self.prompt(b, "switch", turn, opts) }
    pub fn end(&mut self, b: &Battle, turn: usize, v: f64) {
        let log: Vec<&String> = b.log[self.log_pos.min(b.log.len())..].iter().collect(); self.log_pos = b.log.len();
        let winner = match b.winner { Some(Some(0)) => "you", Some(Some(1)) => "the planner", Some(_) => "draw", None => "unfinished" };
        let out = json!({"type": "end", "turn": turn, "state": Self::state_json(b), "winner": winner, "ended": b.ended, "value": v, "log": log});
        let so = std::io::stdout(); let mut h = so.lock(); writeln!(h, "{}", out).unwrap(); h.flush().unwrap();
    }
}
