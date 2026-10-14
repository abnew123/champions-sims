//! Turn flow, ported from Showdown (sim/battle.ts, battle-actions.ts, battle-queue.ts, pokemon.ts, side.ts, field.ts) with the Champions
//! mod overrides (data/mods/champions/scripts.ts). Function names follow Showdown's; comments note where behaviour is intentionally narrower.
use crate::battle::*;
use crate::dex::*;
use crate::state::*;

/// a target slot in the hit pipeline: a pokemon, `false` (dropped), or `null` (hit a substitute)
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum TS { M(MonRef), F, N }
impl TS { pub fn m(&self) -> Option<MonRef> { if let TS::M(m) = self { Some(*m) } else { None } } }

#[derive(Clone, Copy, Debug)]
pub struct MoveChoice { pub slot: usize, pub target_loc: i64, pub mega: bool }

pub const MOVE_SIDE_TARGETS: [&str; 4] = ["all", "foeSide", "allySide", "allyTeam"];

/// combineResults
pub fn combine(left: &RV, right: &RV) -> RV {
    fn rank(v: &RV) -> i32 { match v { RV::Undef => 0, RV::NotFail => 1, RV::Null => 2, RV::B(_) => 3, RV::N(_) => 4, _ => 4 } }
    if rank(left) > rank(right) { return left.clone(); }
    if left.truthy() && !right.truthy() && *right != RV::N(0.0) { return left.clone(); }
    if let (RV::N(a), RV::N(b)) = (left, right) { return RV::N(a + b); }
    right.clone()
}

pub static MISS_STATS: std::sync::Mutex<Vec<((u8, Id), (u64, u64))>> = std::sync::Mutex::new(Vec::new());
fn miss_stats() -> bool { static F: std::sync::OnceLock<bool> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("MISS_STATS").is_ok()) }
trait Entry { fn entry(&mut self, k: (u8, Id)) -> &mut (u64, u64); }
impl Entry for Vec<((u8, Id), (u64, u64))> { fn entry(&mut self, k: (u8, Id)) -> &mut (u64, u64) { if let Some(i) = self.iter().position(|e| e.0 == k) { &mut self[i].1 } else { self.push((k, (0, 0))); &mut self.last_mut().unwrap().1 } } }
impl Battle {
    // ======================= choices and the queue =======================
    /// the moves a player can actually choose: (move id, target, disabled). A hidden disable (Imprison) counts as disabled: Showdown's
    /// request may show the move as usable (below), but choosing it is refused ("[Unavailable choice]") and the request re-sent with it
    /// disabled (2026-10-13: v29 planned on the shown list and the bot's mix put all its weight on an Imprisoned Protect)
    pub fn request_moves(&mut self, m: MonRef) -> Vec<(Id, Id, bool)> { self.request_moves_ex(m, false) }
    /// pokemon.getMoves(lockedMove, restrictData) as the request lists them (the differential test compares this)
    pub fn request_moves_shown(&mut self, m: MonRef) -> Vec<(Id, Id, bool)> { self.request_moves_ex(m, true) }
    fn request_moves_ex(&mut self, m: MonRef, shown: bool) -> Vec<(Id, Id, bool)> {
        let locked = self.get_locked_move(m);
        if let Some(l) = locked {
            if l == "recharge" { return vec![(id("recharge"), id("self"), false)]; }
            return vec![(l, self.dex.mv(l).tmpl.target, false)];
        }
        // a hidden disable (Imprison) shows as usable in the side's last active Pokemon's request (getMoves' restrictData = isLastActive,
        // 2026-10-13: an Imprisoned Farigiraf mirror read as Struggle); choosing it is then refused (request_moves above)
        let last = shown && { let s = m.0 as usize; let pos = self.p(m).position as usize; self.p(m).is_active && ((pos + 1)..2).all(|i| self.sides[s].active[i].map(|x| self.sides[s].pokemon[x as usize].fainted).unwrap_or(true)) };
        let p = self.p(m);
        let mut out = vec![]; let mut any = false;
        for s in &p.move_slots {
            let disabled = if s.pp <= 0 { true } else if s.disabled && s.disabled_hidden { !last } else { s.disabled };
            if !disabled { any = true; }
            out.push((s.id, self.dex.mv(s.id).tmpl.target, disabled));
        }
        if any { out } else { vec![(id("struggle"), id("randomNormal"), false)] }
    }
    pub fn get_locked_move(&mut self, m: MonRef) -> Option<Id> {
        match self.priority_event("LockMove", Tgt::Mon(m), None, None, RV::Undef, false) { RV::S(s) => Some(s), _ => None }
    }
    /// side.chooseMove + resolveAction for one pokemon. `idx` indexes request_moves.
    pub fn make_move_action(&mut self, m: MonRef, idx: usize, target_loc: i64, mega: bool) -> Action {
        let req = self.request_moves(m);
        let mut moveid = req[idx.min(req.len() - 1)].0;
        let mut tloc = target_loc;
        let locked = self.get_locked_move(m);
        if let Some(l) = locked {
            let p = self.p(m);
            tloc = p.last_move_target_loc.unwrap_or(0);
            if let Some(t) = find(&p.volatiles, l).and_then(|s| s.n("targetLoc")) { if t != 0.0 { tloc = t as i64; } }
            moveid = l;
        } else if self.p(m).move_slots.iter().all(|s| s.disabled || s.pp <= 0) {
            moveid = id("struggle");
        }
        let target = self.dex.mv(moveid).tmpl.target;
        if !["normal", "any", "adjacentAlly", "adjacentAllyOrSelf", "adjacentFoe"].contains(&target) && locked.is_none() { tloc = 0; }
        let am = self.new_am(self.dex.active_move(moveid));
        Action { choice: Choice::Move, order: 200.0, priority: 0.0, fractional_priority: 0.0, speed: 0.0, sub_order: 0.0, effect_order: 0.0,
                 pokemon: Some(m), target_loc: tloc, original_target: None, am: Some(am), mega: mega && locked.is_none(), source_effect: None, target: None }
    }
    /// queue.resolveAction (not midTurn)
    pub fn resolve_action(&mut self, mut a: Action, mid_turn: bool) -> Vec<Action> {
        let mut out = vec![];
        if a.choice == Choice::Move && !mid_turn {
            let m = a.pokemon.unwrap(); let am = a.am.unwrap();
            let mid = self.am(am).id;
            // queue.resolveAction unshifts beforeTurnMove (Counter, Mirror Coat), the Mega, then priorityChargeMove (Focus Punch, Beak
            // Blast, Chilly Reception), each resolved in that order: a move action without a target location draws a random target
            // (2026-10-12: the engine had neither action, so these moves' turn-start effects and draws were missing)
            if self.dex.mv(mid).eff.has_fn("beforeTurnCallback") {
                let mut x = simple_action(Choice::BeforeTurnMove, 5.0); x.pokemon = Some(m); x.am = Some(am); x.target_loc = a.target_loc;
                if x.target_loc == 0 { if let Some(t) = self.get_random_target(m, am) { x.target_loc = self.get_loc_of(m, t); } }
                x.original_target = self.get_at_loc(m, x.target_loc);
                self.get_action_speed(&mut x); out.insert(0, x);
            }
            if a.mega {
                let mut mega = simple_action(Choice::MegaEvo, 104.0); mega.pokemon = Some(m);
                self.get_action_speed(&mut mega);
                out.insert(0, mega);
            }
            if self.dex.mv(mid).eff.has_fn("priorityChargeCallback") {
                let mut x = simple_action(Choice::PriorityChargeMove, 107.0); x.pokemon = Some(m); x.am = Some(am);
                if let Some(t) = self.get_random_target(m, am) { x.target_loc = self.get_loc_of(m, t); }
                x.original_target = self.get_at_loc(m, x.target_loc);
                self.get_action_speed(&mut x); out.insert(0, x);
            }
            a.fractional_priority = self.run_event("FractionalPriority", Tgt::Mon(m), None, Some(Eff::mv(mid, am)), RV::N(0.0), false, false).num();
        }
        if (a.choice == Choice::Switch || a.choice == Choice::InstaSwitch) && !mid_turn {
            let m = a.pokemon.unwrap();
            if let Some(f) = self.p(m).switch_flag { if f != "true" { a.source_effect = Some(Eff::new(Kind::Move, f)); } }
            self.pm(m).switch_flag = None;
        }
        if let Some(am) = a.am {
            let m = a.pokemon.unwrap();
            if a.target_loc == 0 {
                let t = self.get_random_target(m, am);
                if let Some(t) = t { a.target_loc = self.get_loc_of(m, t); }
            }
            a.original_target = self.get_at_loc(m, a.target_loc);
        }
        self.get_action_speed(&mut a);
        out.push(a);
        out
    }
    /// battle.getActionSpeed(action)
    pub fn get_action_speed(&mut self, a: &mut Action) {
        if a.choice == Choice::Move {
            let m = a.pokemon.unwrap(); let am = a.am.unwrap(); let mid = self.am(am).id;
            let mut pr = self.dex.mv(mid).tmpl.priority;
            let target = self.get_target(m, am, a.target_loc, None);
            let e = Eff::mv(mid, am);
            pr = self.single_event("ModifyPriority", e, None, Tgt::Mon(m), target, None, RV::N(pr)).num();
            pr = self.run_event("ModifyPriority", Tgt::Mon(m), target, Some(e), RV::N(pr), false, false).num();
            a.priority = pr + a.fractional_priority;
            self.amm(am).priority = pr;
        }
        a.speed = match a.pokemon { None => 1.0, Some(m) => self.get_action_speed_mon(m) };
    }
    pub fn get_action_speed_mon(&mut self, m: MonRef) -> f64 { self.action_speed_of(m) }
    fn akey(a: &Action) -> (Option<f64>, f64, f64, f64, f64) { (Some(a.order), a.priority, a.speed, a.sub_order, a.effect_order) }
    pub fn sort_queue(&mut self) { let mut q = std::mem::take(&mut self.queue); self.speed_sort(&mut q, Self::akey); self.queue = q; }
    /// queue.insertChoice for a single resolved action list
    pub fn insert_actions(&mut self, actions: Vec<Action>) {
        let mut first: Option<usize> = None; let mut last: Option<usize> = None;
        for (i, cur) in self.queue.iter().enumerate() {
            let c = Self::cmp_priority(Self::akey(&actions[0]), Self::akey(cur));
            if c <= 0.0 && first.is_none() { first = Some(i); }
            if c < 0.0 { last = Some(i); break; }
        }
        match first {
            None => self.queue.extend(actions),
            Some(f) => {
                let l = last.unwrap_or(self.queue.len());
                let idx = if f == l { f } else { self.prng.range(f as i64, l as i64 + 1) as usize };
                for (k, a) in actions.into_iter().enumerate() { self.queue.insert(idx + k, a); }
            }
        }
    }

    /// Both sides' choices for one turn (per active slot), then run the turn (commitChoices + turnLoop). The turn may stop at a
    /// switch request (`request_switch`); answer it with `choose_switches`.
    pub fn run_turn(&mut self, choices: [[PChoice; 2]; 2]) {
        self.update_speed();
        self.queue.clear();
        let mut acts: Vec<Action> = vec![];
        for s in 0..2u8 {
            for i in 0..2 {
                let Some(pi) = self.sides[s as usize].active[i] else { continue };
                let m = (s, pi);
                if self.p(m).fainted { continue; }
                match choices[s as usize][i] {
                    PChoice::Move(idx, tloc, mega) => { let a = self.make_move_action(m, idx, tloc, mega); acts.push(a); }
                    PChoice::Switch(pos) => { if let Some(t) = self.mon_at_position(s, pos) { acts.push(switch_action(Choice::Switch, m, t)); } }
                    PChoice::Pass => {}
                }
            }
        }
        for a in acts { let r = self.resolve_action(a, false); self.queue.extend(r); }
        self.sort_queue();
        self.turn_loop();
    }
    /// which active slots must be replaced right now (Showdown's forceSwitch request), per side
    pub fn switch_request(&self) -> [[bool; 2]; 2] {
        std::array::from_fn(|s| {
            if !self.request_switch || self.sides[s].pokemon_left == 0 { return [false, false]; }
            std::array::from_fn(|i| self.sides[s].active[i].map(|x| self.sides[s].pokemon[x as usize].switch_flag.is_some()).unwrap_or(false))
        })
    }
    /// answer a switch request (commitChoices with instaswitch actions in front of the rest of the turn)
    pub fn choose_switches(&mut self, choices: [[PChoice; 2]; 2]) {
        let req = self.switch_request();
        self.update_speed();
        let old = std::mem::take(&mut self.queue);
        let mut acts = vec![];
        for s in 0..2u8 { for i in 0..2 {
            if !req[s as usize][i] { continue; }
            let Some(pi) = self.sides[s as usize].active[i] else { continue };
            if let PChoice::Switch(pos) = choices[s as usize][i] { if let Some(t) = self.mon_at_position(s, pos) {
                // Revival Blessing (2026-10-13, the Eval bar: it revived nothing): the user's slot holds the condition, the choice names a
                // fainted Pokemon, and the action revives it (side.ts chooseSwitch: order 6, the user stays in)
                if self.revive_slot(s, i) {
                    if self.p(t).fainted { self.pm((s, pi)).switch_flag = None; let mut a = simple_action(Choice::RevivalBlessing, 6.0); a.pokemon = Some((s, pi)); a.target = Some(t); acts.push(a); }
                } else { acts.push(switch_action(Choice::InstaSwitch, (s, pi), t)); }
            } }
        } }
        for a in acts { let r = self.resolve_action(a, false); self.queue.extend(r); }
        self.sort_queue();
        self.queue.extend(old);
        self.request_switch = false;
        self.turn_loop();
    }
    /// active slot i of side s holds Revival Blessing's slot condition: its switch request picks a fainted Pokemon to revive
    pub fn revive_slot(&self, s: u8, i: usize) -> bool { find(&self.sides[s as usize].slot_conditions[i], "revivalblessing").is_some() }
    /// the team positions of side s's fainted Pokemon (Revival Blessing's choices)
    pub fn fainted_positions(&self, s: u8) -> Vec<u8> { let mut v: Vec<u8> = self.sides[s as usize].pokemon.iter().filter(|p| p.fainted).map(|p| p.position).collect(); v.sort(); v }
    pub fn mon_at_position(&self, s: u8, pos: u8) -> Option<MonRef> {
        self.sides[s as usize].pokemon.iter().position(|p| p.position == pos).map(|i| (s, i as u8))
    }
    pub fn turn_loop(&mut self) {
        if !self.mid_turn {
            let mut bt = simple_action(Choice::BeforeTurn, 4.0);
            self.get_action_speed(&mut bt);
            self.insert_actions(vec![bt]);
            let mut res = simple_action(Choice::Residual, 300.0);
            self.get_action_speed(&mut res);
            self.queue.push(res);
            self.mid_turn = true;
        }
        while !self.queue.is_empty() {
            let a = self.queue.remove(0);
            self.run_action(a);
            if self.request_switch || self.ended { return; }
        }
        self.end_turn();
        self.mid_turn = false;
        self.queue.clear();
    }

    // ======================= runAction =======================
    pub fn run_action(&mut self, a: Action) {
        let mut residual_pokemon: Vec<(MonRef, i64)> = vec![];
        let orig_hp = a.pokemon.map(|m| self.p(m).hp);
        match a.choice {
            Choice::Move => {
                let m = a.pokemon.unwrap();
                if !self.p(m).is_active || self.p(m).fainted { return; }
                self.run_move(a.am.unwrap(), m, a.target_loc, a.source_effect, a.original_target, false);
            }
            Choice::MegaEvo => { self.run_mega_evo(a.pokemon.unwrap()); }
            Choice::BeforeTurnMove => {
                let m = a.pokemon.unwrap(); if !self.p(m).is_active || self.p(m).fainted { return; }
                let am = a.am.unwrap(); let mid = self.am(am).id;
                let Some(t) = self.get_target(m, am, a.target_loc, None) else { return };
                self.call_fn(Kind::Move, mid, "beforeTurnCallback", Tgt::Mon(m), Some(t), Some(Eff::mv(mid, am)));
            }
            Choice::PriorityChargeMove => {
                let m = a.pokemon.unwrap(); if !self.p(m).is_active || self.p(m).fainted { return; }
                let am = a.am.unwrap(); let mid = self.am(am).id;
                self.call_fn(Kind::Move, mid, "priorityChargeCallback", Tgt::Mon(m), None, Some(Eff::mv(mid, am)));
            }
            Choice::BeforeTurn => { self.each_event("BeforeTurn", None); }
            Choice::Residual => {
                self.clear_active_move(true);
                self.update_speed();
                residual_pokemon = self.all_active().into_iter().map(|m| (m, self.p(m).hp)).collect();
                self.field_event("Residual", None);
                if !self.ended { self.add(&["upkeep"]); }
            }
            Choice::Switch | Choice::InstaSwitch => {
                let m = a.pokemon.unwrap();
                if self.switch_in(a.target.unwrap(), self.p(m).position, a.source_effect, false) == SwitchResult::PursuitFaint { /* gen 5+: the switch just doesn't happen */ }
            }
            Choice::RunSwitch => { self.run_switch(a.pokemon.unwrap()); }
            Choice::RevivalBlessing => {
                let (m, t) = (a.pokemon.unwrap(), a.target.unwrap()); let s = m.0;
                self.sides[s as usize].pokemon_left += 1;
                if (self.p(t).position as usize) < 2 { let r = self.resolve_action(switch_action(Choice::InstaSwitch, t, t), false); self.queue.extend(r); }   // queue.addChoice: pushed, not sorted
                { let p = self.pm(t); p.fainted = false; p.faint_queued = false; p.status = id(""); p.hp = 1;   // statusState left as it was (battle.ts sets only status)
                  let half = (p.maxhp as f64 / 2.0).trunc() as i64; p.hp = half.max(1).min(p.maxhp); }
                if self.logging { let n = self.mon_name(t); let p = self.p(t); let hp = format!("{}/{}", p.hp, p.maxhp); self.add(&["-heal", &n, &hp, "[from] move: Revival Blessing"]); }
                let pos = self.p(m).position; self.remove_slot_condition(s, pos, id("revivalblessing"));
            }
            _ => {}
        }
        for s in 0..2u8 { for m in self.side_active(s) { if self.p(m).force_switch_flag {
            if self.p(m).hp > 0 { let pos = self.p(m).position; self.drag_in(s, pos); }
            self.pm(m).force_switch_flag = false;
        } } }
        self.clear_active_move(false);
        self.faint_messages(false, false, true);
        if self.ended { return; }
        if self.queue.is_empty() { self.check_fainted(); }
        else if self.queue[0].choice == Choice::InstaSwitch { return; }
        self.each_event("Update", None);
        for (m, orig) in residual_pokemon {
            let p = self.p(m);
            if p.hp > 0 && (p.hp as f64) <= p.maxhp as f64 / 2.0 && orig as f64 > p.maxhp as f64 / 2.0 { self.run_event("EmergencyExit", Tgt::Mon(m), None, None, RV::Undef, false, false); }
        }
        if a.choice == Choice::RunSwitch {
            let m = a.pokemon.unwrap(); let p = self.p(m);
            if p.hp > 0 && p.hp as f64 <= p.maxhp as f64 / 2.0 && orig_hp.unwrap_or(0) as f64 > p.maxhp as f64 / 2.0 { self.run_event("EmergencyExit", Tgt::Mon(m), None, None, RV::Undef, false, false); }
        }
        let mut switches = [false; 2];
        for s in 0..2u8 { switches[s as usize] = self.side_active(s).iter().any(|m| self.p(*m).switch_flag.is_some()); }
        for s in 0..2u8 {
            if switches[s as usize] && self.can_switch(s) == 0 {
                let mut revive = false;
                for m in self.side_active(s) { if self.revive_slot(s, self.p(m).position as usize) { revive = true; continue; } self.pm(m).switch_flag = None; }
                if !revive { switches[s as usize] = false; }
            } else if switches[s as usize] {
                for m in self.side_active(s) {
                    let p = self.p(m);
                    if p.hp > 0 && p.switch_flag.is_some() && p.switch_flag != Some("revivalblessing") && !p.skip_before_switch_out {
                        self.run_event("BeforeSwitchOut", Tgt::Mon(m), None, None, RV::Undef, false, false);
                        self.pm(m).skip_before_switch_out = true;
                        self.faint_messages(false, false, true);
                        if self.ended { return; }
                        if self.p(m).fainted { switches[s as usize] = self.side_active(s).iter().any(|x| self.p(*x).switch_flag.is_some()); }
                    }
                }
            }
        }
        if switches.iter().any(|x| *x) { self.request_switch = true; return; }
        if self.queue.first().map(|q| q.choice == Choice::Move).unwrap_or(false) {
            self.update_speed();
            let mut q = std::mem::take(&mut self.queue);
            for qa in q.iter_mut() { if qa.pokemon.is_some() { self.get_action_speed(qa); } }
            self.queue = q;
            self.sort_queue();
        }
    }

    // ======================= switching =======================
    /// switchIn(pokemon, pos, sourceEffect, isDrag)
    pub fn switch_in(&mut self, m: MonRef, pos: u8, source_effect: Option<Eff>, is_drag: bool) -> SwitchResult {
        if self.p(m).is_active { return SwitchResult::Failed; }
        let s = m.0;
        let old = self.sides[s as usize].active[pos as usize].map(|i| (s, i));
        if let Some(o) = old { if self.p(o).hp > 0 {
            self.pm(o).being_called_back = true;
            let copy = source_effect.map(|se| se.kind == Kind::Move && self.dex.mv(se.id).tmpl.base.self_switch == Some("copyvolatile")).unwrap_or(false);
            if !self.p(o).skip_before_switch_out && !is_drag {
                self.run_event("BeforeSwitchOut", Tgt::Mon(o), None, None, RV::Undef, false, false);
                self.each_event("Update", None);
            }
            self.pm(o).skip_before_switch_out = false;
            if !self.run_event("SwitchOut", Tgt::Mon(o), None, None, RV::Undef, false, false).truthy() { return SwitchResult::Failed; }
            if self.p(o).hp == 0 { return SwitchResult::PursuitFaint; }
            let (ab, it) = (self.p(o).ability, self.p(o).item);
            self.single_event("End", Eff::new(Kind::Ability, ab), Some(SLoc::Ability(o)), Tgt::Mon(o), None, None, RV::Undef);
            self.single_event("End", Eff::new(Kind::Item, it), Some(SLoc::Item(o)), Tgt::Mon(o), None, None, RV::Undef);
            self.queue.retain(|q| q.pokemon != Some(o));
            if copy { self.copy_volatile_from(m, o); }   // Baton Pass (2026-10-09)
            self.clear_volatile(o, true);
        } }
        if let Some(o) = old {
            let new_pos = self.p(m).position;
            let p = self.pm(o);
            p.is_active = false; p.used_item_this_turn = false; p.stats_raised_this_turn = false; p.stats_lowered_this_turn = false;
            p.position = new_pos;
            if p.fainted { p.status = ""; }
        }
        self.pm(m).position = pos;
        self.sides[s as usize].active[pos as usize] = Some(m.1);
        { let p = self.pm(m); p.is_active = true; p.active_turns = 0; p.active_move_actions = 0; for sl in p.move_slots.iter_mut() { sl.used = false; } }
        let (ab, it) = (self.p(m).ability, self.p(m).item);
        let st = self.init_state(ab, Some(true)); self.pm(m).ability_state = st;
        let st = self.init_state(it, Some(true)); self.pm(m).item_state = st;
        self.run_event("BeforeSwitchIn", Tgt::Mon(m), None, None, RV::Undef, false, false);
        if self.logging { let n = self.mon_name(m); self.add(&[if is_drag { "drag" } else { "switch" }, &n]); }
        if is_drag { self.run_switch(m); }
        else {
            self.update_speed_of(m);
            let mut a = simple_action(Choice::RunSwitch, 101.0); a.pokemon = Some(m);
            let r = self.resolve_action(a, false);
            self.insert_actions(r);
        }
        SwitchResult::Ok
    }
    /// pokemon.copyVolatileFrom(old, 'batonpass'): boosts and the volatiles without noCopy move to the switch-in (Baton Pass)
    pub fn copy_volatile_from(&mut self, m: MonRef, o: MonRef) {
        const NOCOPY: [&str; 30] = ["attract", "choicelock", "commanded", "commanding", "counter", "defensecurl", "destinybond", "disable", "dynamax", "encore", "flashfire",
            "foresight", "glaiverush", "gmaxchistrike", "imprison", "lockon", "minimize", "miracleeye", "mirrorcoat", "nightmare", "protosynthesis", "quarkdrive", "saltcure",
            "smackdown", "spotlight", "stockpile", "syrupbomb", "torment", "trapped", "trapper"];
        self.clear_volatile(m, true);
        self.pm(m).boosts = self.p(o).boosts;
        let vols: Vec<(Id, EState)> = self.p(o).volatiles.iter().filter(|(k, _)| !NOCOPY.contains(k) && *k != "yawn").cloned().collect();
        let ids: Vec<Id> = vols.iter().map(|(k, _)| *k).collect();
        self.pm(m).volatiles = vols;
        self.pm(o).volatiles.clear();
        for v in ids { self.single_event("Copy", Eff::cond(v), Some(SLoc::Vol(m, v)), Tgt::Mon(m), None, None, RV::Undef); }
    }
    /// battle.swapPosition (Ally Switch): the two actives of a side trade slots; Swap runs for both
    pub fn swap_position(&mut self, m: MonRef, new_pos: u8) -> bool {
        let s = m.0; let target = self.sides[s as usize].active[new_pos as usize].map(|i| (s, i));
        if new_pos != 1 && target.map(|t| self.p(t).fainted).unwrap_or(true) { return false; }
        if self.logging { let n = self.mon_name(m); let np = new_pos.to_string(); self.add(&["swap", &n, &np]); }
        let old_pos = self.p(m).position;
        self.sides[s as usize].active[old_pos as usize] = target.map(|t| t.1);
        self.sides[s as usize].active[new_pos as usize] = Some(m.1);
        if let Some(t) = target { self.pm(t).position = old_pos; }
        self.pm(m).position = new_pos;
        if let Some(t) = target { self.run_event("Swap", Tgt::Mon(t), Some(m), None, RV::Undef, false, false); }
        self.run_event("Swap", Tgt::Mon(m), target, None, RV::Undef, false, false);
        true
    }
    pub fn update_speed_of(&mut self, m: MonRef) { let s = self.action_speed_of(m); self.pm(m).speed = s; }
    /// runSwitch: switch-in effects for this and any immediately following runSwitch actions
    pub fn run_switch(&mut self, m: MonRef) {
        let mut ins = vec![m];
        while self.queue.first().map(|q| q.choice == Choice::RunSwitch).unwrap_or(false) { let q = self.queue.remove(0); ins.push(q.pokemon.unwrap()); }
        let mut all: Vec<(MonRef, f64)> = (0..2u8).flat_map(|s| self.side_active(s)).map(|x| (x, self.p(x).speed)).collect();
        self.speed_sort(&mut all, |x| (None, 0.0, x.1, 0.0, 0.0));
        self.speed_order = all.iter().map(|(x, _)| x.0 as i64 + 2 * self.p(*x).position as i64).collect();
        self.field_event("SwitchIn", Some(ins));
    }
    /// dragIn(side, pos): Roar / Dragon Tail style replacement with a random benched pokemon
    pub fn drag_in(&mut self, s: u8, pos: u8) -> bool {
        // possibleSwitches walks side.pokemon in Showdown's order, which is team position order
        let mut bench: Vec<MonRef> = self.sides[s as usize].pokemon.iter().enumerate().filter(|(_, p)| p.position >= 2 && !p.fainted).map(|(i, _)| (s, i as u8)).collect();
        bench.sort_by_key(|m| self.p(*m).position);
        if bench.is_empty() { return false; }
        let t = bench[self.prng.sample_idx(bench.len())];
        let Some(old) = self.sides[s as usize].active[pos as usize].map(|i| (s, i)) else { return false };
        if self.p(old).hp == 0 { return false; }
        if !self.run_event("DragOut", Tgt::Mon(old), None, None, RV::Undef, false, false).truthy() { return false; }
        self.switch_in(t, pos, None, true) == SwitchResult::Ok
    }
    pub fn can_switch(&self, s: u8) -> usize {
        let side = &self.sides[s as usize];
        side.pokemon.iter().enumerate().filter(|(i, p)| !p.fainted && !side.active.contains(&Some(*i as u8))).count()
    }
    pub fn clear_active_move(&mut self, failed: bool) {
        if let Some(am) = self.active_move { if !failed { self.last_move = Some(am); } self.active_move = None; self.active_pokemon = None; self.active_target = None; }
    }
    pub fn set_active_move(&mut self, am: Option<usize>, p: Option<MonRef>, t: Option<MonRef>) { self.active_move = am; self.active_pokemon = p; self.active_target = t.or(p); }
    pub fn check_fainted(&mut self) {
        for s in 0..2 { for m in self.side_active(s) { if self.p(m).fainted { let p = self.pm(m); p.status = id("fnt"); p.switch_flag = Some(id("true")); } } }
    }

    // ======================= faint / win =======================
    pub fn faint(&mut self, m: MonRef, source: Option<MonRef>, effect: Option<Eff>) {
        let p = self.pm(m);
        if p.fainted || p.faint_queued { return; }
        p.hp = 0; p.switch_flag = None; p.faint_queued = true;
        self.faint_queue.push(FaintData { target: m, source, effect });
    }
    pub fn faint_messages(&mut self, last_first: bool, force_check: bool, mut check_win: bool) -> bool {
        if self.ended { return false; }
        let length = self.faint_queue.len();
        if length == 0 { if force_check && self.check_win(None) { return true; } return false; }
        if last_first { let x = self.faint_queue.pop().unwrap(); self.faint_queue.insert(0, x); }
        let mut last: Option<(MonRef, Option<MonRef>, Option<Eff>)> = None;
        while !self.faint_queue.is_empty() {
            let left = self.faint_queue.len();
            let fd = self.faint_queue.remove(0);
            let m = fd.target;
            last = Some((m, fd.source, fd.effect));
            if !self.p(m).fainted && self.run_event("BeforeFaint", Tgt::Mon(m), fd.source, fd.effect, RV::Undef, false, false).truthy() {
                let name = self.mon_name(m); self.add(&["faint", &name]);
                let s = m.0 as usize;
                if self.sides[s].pokemon_left > 0 { self.sides[s].pokemon_left -= 1; }
                if self.sides[s].total_fainted < 100 { self.sides[s].total_fainted += 1; }
                self.run_event("Faint", Tgt::Mon(m), fd.source, fd.effect, RV::Undef, false, false);
                let ab = self.p(m).ability; let it = self.p(m).item;
                self.single_event("End", Eff::new(Kind::Ability, ab), Some(SLoc::Ability(m)), Tgt::Mon(m), None, None, RV::Undef);
                self.single_event("End", Eff::new(Kind::Item, it), Some(SLoc::Item(m)), Tgt::Mon(m), None, None, RV::Undef);
                self.clear_volatile(m, false);
                let p = self.pm(m);
                p.fainted = true; p.is_active = false;
                self.sides[s].fainted_this_turn = Some(m);
                if self.faint_queue.len() >= left { check_win = true; }
            }
        }
        if check_win && self.check_win(last.map(|x| x.0)) { return true; }
        if let Some((t, s, e)) = last { if length > 0 { self.run_event("AfterFaint", Tgt::Mon(t), s, e, RV::N(length as f64), false, false); } }
        false
    }
    pub fn check_win(&mut self, faint_target: Option<MonRef>) -> bool {
        if self.sides.iter().all(|s| s.pokemon_left == 0) { self.win(faint_target.map(|m| m.0)); return true; }
        for s in 0..2 { if self.sides[1 - s].pokemon_left == 0 { self.win(Some(s as u8)); return true; } }
        false
    }
    pub fn win(&mut self, side: Option<u8>) { if self.ended { return; } self.winner = Some(side); self.ended = true; }
    /// pokemon.clearVolatile (Champions: also resets timesAttacked)
    pub fn clear_volatile(&mut self, m: MonRef, include_switch_flags: bool) {
        let p = self.pm(m);
        p.boosts = [0; 7]; if p.transformed { p.move_slots = p.base_move_slots.clone(); }   // baseMoveSlots.slice() shares the slot objects
        p.transformed = false; p.ability = p.base_ability;
        p.volatiles.clear();
        if include_switch_flags { p.switch_flag = None; p.force_switch_flag = false; }
        p.last_move = None; p.last_move_used = None; p.move_this_turn = ""; p.move_last_turn_result = Tri::Undef; p.move_this_turn_result = Tri::Undef;
        p.last_damage = 0; p.attacked_by.clear(); p.hurt_this_turn = None; p.newly_switched = true; p.being_called_back = false; p.times_attacked = 0;
        p.ability_state.del("started"); p.item_state.del("started");
        let bs = p.base_species; self.set_species(m, bs);
    }
    pub fn set_species(&mut self, m: MonRef, sp: Id) {
        let sd = self.dex.species.get(sp).unwrap_or_else(|| panic!("species {}", sp)).clone();
        let p = self.pm(m);
        p.species = sp; p.types = sd.types.clone(); p.added_type = ""; p.weighthg = sd.weighthg;
        let stats = self.spread_modify(&sd.stats, m);
        let p = self.pm(m);
        for i in 1..6 { p.stored[i] = stats[i]; }
        p.speed = p.stored[5] as f64;
    }
    /// Champions statModify for all stats of this pokemon's set
    pub fn spread_modify(&self, base: &[i64; 6], m: MonRef) -> [i64; 6] {
        let p = self.p(m); let (plus, minus) = self.dex.natures.get(p.nature).cloned().unwrap_or((None, None));
        let names = ["hp", "atk", "def", "spa", "spd", "spe"];
        std::array::from_fn(|i| {
            if i == 0 { return base[0] + p.evs[0] + 75; }
            let mut s = base[i] + p.evs[i] + 20;
            if plus == Some(names[i]) { s = Battle::trunc(((s * 110) % 65536) as f64 / 100.0); } else if minus == Some(names[i]) { s = Battle::trunc(((s * 90) % 65536) as f64 / 100.0); }
            s
        })
    }

    // ======================= Mega Evolution =======================
    pub fn run_mega_evo(&mut self, m: MonRef) -> bool {
        let Some(sp) = self.p(m).can_mega_evo else { return false };
        let item = self.p(m).item;
        self.forme_change_permanent(m, sp, Some(Eff::new(Kind::Item, item)));
        for i in 0..self.sides[m.0 as usize].pokemon.len() { self.sides[m.0 as usize].pokemon[i].can_mega_evo = None; }
        self.run_event("AfterMega", Tgt::Mon(m), None, None, RV::Undef, false, false);
        true
    }
    /// Champions formeChange(species, source, isPermanent=true)
    pub fn forme_change_permanent(&mut self, m: MonRef, sp: Id, source: Option<Eff>) {
        let r = self.run_event("ModifySpecies", Tgt::Mon(m), None, source, RV::S(sp), false, false);
        let sp = match r { RV::S(s) => s, _ => sp };
        self.set_species(m, sp);
        self.pm(m).base_species = sp;
        // updateMaxHp: Champions HP = base + SP + 75
        let sd = self.dex.species[sp].clone();
        let new_max = sd.stats[0] + self.p(m).evs[0] + 75;
        let p = self.pm(m);
        if new_max != p.base_maxhp { p.base_maxhp = new_max; p.hp = if p.hp <= 0 { 0 } else { (new_max - (p.maxhp - p.hp)).max(1) }; p.maxhp = new_max; }
        // formeChange(.., isPermanent): only an item (Mega Stone) logs -mega and sets moveThisTurnResult; Disguise and Ice Face keep
        // the ability and its state (busted) (2026-10-12: the engine did all of it for every source)
        if source.map(|e| e.kind == Kind::Item).unwrap_or(false) {
            let name = self.mon_name(m); self.add(&["-mega", &name, sd.name]);
            self.pm(m).move_this_turn_result = Tri::B(true);
        }
        if source.map(|e| e.id == "disguise" || e.id == "iceface").unwrap_or(false) { return; }
        let ab = sd.abilities.iter().find(|(k, _)| *k == "0").map(|x| x.1).unwrap_or("");
        self.set_ability(m, ab, None, None, true);
        self.pm(m).base_ability = ab;
    }
    pub fn set_ability(&mut self, m: MonRef, ab: Id, source: Option<MonRef>, _src_eff: Option<Eff>, from_forme_change: bool) -> bool {
        if self.p(m).hp == 0 { return false; }
        if !from_forme_change {
            if self.dex.eff(Kind::Ability, ab).flag("cantsuppress") || self.dex.eff(Kind::Ability, self.p(m).ability).flag("cantsuppress") { return false; }
            let r = self.run_event("SetAbility", Tgt::Mon(m), source, None, RV::S(ab), false, false);
            if !r.truthy() { return false; }
        }
        let old = self.p(m).ability;
        self.single_event("End", Eff::new(Kind::Ability, old), Some(SLoc::Ability(m)), Tgt::Mon(m), source, None, RV::Undef);
        let st = self.init_state(ab, Some(self.p(m).is_active));
        let p = self.pm(m); p.ability = ab; p.ability_state = st;
        if !ab.is_empty() { self.single_event("Start", Eff::new(Kind::Ability, ab), Some(SLoc::Ability(m)), Tgt::Mon(m), source, None, RV::Undef); }
        true
    }

    // ======================= targeting =======================
    pub fn valid_target_loc(&self, loc: i64, src: MonRef, ttype: &str) -> bool {
        if loc == 0 { return true; }
        if loc.abs() > 2 { return false; }
        let src_loc = -(self.p(src).position as i64 + 1);
        let is_self = src_loc == loc; let is_foe = loc > 0;
        let across = -(2 + 1 - loc);
        let is_adj = if loc > 0 { (across - src_loc).abs() <= 1 } else { (loc - src_loc).abs() == 1 };
        match ttype { "randomNormal" | "scripted" | "normal" => is_adj, "adjacentAlly" => is_adj && !is_foe, "adjacentAllyOrSelf" => is_adj && !is_foe || is_self,
                      "adjacentFoe" => is_adj && is_foe, "any" => !is_self, _ => false }
    }
    pub fn get_random_target(&mut self, m: MonRef, am: usize) -> Option<MonRef> {
        let t = self.am(am).target;
        if ["self", "all", "allySide", "allyTeam", "adjacentAllyOrSelf"].contains(&t) { return Some(m); }
        if t == "adjacentAlly" { let a = self.adjacent_allies(m); return if a.is_empty() { None } else { let i = self.prng.sample_idx(a.len()); Some(a[i]) }; }
        let foes = self.foes(m);
        if !foes.is_empty() { let i = self.prng.sample_idx(foes.len()); return Some(foes[i]); }
        self.sides[1 - m.0 as usize].active[0].map(|i| (1 - m.0, i))
    }
    pub fn get_target(&mut self, m: MonRef, am: usize, loc: i64, original: Option<MonRef>) -> Option<MonRef> {
        let mv = self.am(am).clone();
        let tracks = mv.tracks_target || self.has_ability(m, "stalwart") || self.has_ability(m, "propellertail");
        if tracks { if let Some(o) = original { if self.p(o).is_active { return Some(o); } } }
        if mv.smart_target.unwrap_or(false) {
            let cur = self.get_at_loc(m, loc);
            return match cur { Some(c) if !self.p(c).fainted => Some(c), _ => self.get_random_target(m, am) };
        }
        let self_loc = self.get_loc_of(m, m);
        if ["adjacentAlly", "any", "normal"].contains(&mv.target) && loc == self_loc && find(&self.p(m).volatiles, "twoturnmove").is_none() { return None; }
        if mv.target != "randomNormal" && self.valid_target_loc(loc, m, mv.target) {
            let t = self.get_at_loc(m, loc);
            if let Some(t) = t {
                if self.p(t).fainted && self.is_ally(t, m) { return Some(if mv.target == "adjacentAllyOrSelf" { m } else { t }); }
                if !self.p(t).fainted { return Some(t); }
            }
        }
        self.get_random_target(m, am)
    }
    /// pokemon.getMoveTargets
    pub fn get_move_targets(&mut self, m: MonRef, am: usize, target: MonRef) -> (Vec<MonRef>, Vec<MonRef>) {
        let mt = self.am(am).target;
        let mut targets: Vec<MonRef> = vec![];
        match mt {
            "all" | "foeSide" | "allySide" | "allyTeam" => {
                if !mt.starts_with("foe") { targets.extend(self.allies_and_self(m)); }
                if !mt.starts_with("ally") { targets.extend(self.foes_all(m).into_iter().filter(|x| !self.p(*x).fainted || true)); }
            }
            "allAdjacent" | "allAdjacentFoes" => {
                if mt == "allAdjacent" { targets.extend(self.adjacent_allies(m)); }
                targets.extend(self.adjacent_foes(m));
            }
            "allies" => { targets = self.allies_and_self(m).to_vec(); }
            _ => {
                let mut t = target;
                if self.p(t).fainted && !self.is_ally(t, m) {
                    match self.get_random_target(m, am) { Some(x) => t = x, None => return (vec![], vec![]) }
                }
                let mid = self.am(am).id;
                let w = self.pokemon_effective_weather(m, Some(Eff::mv(mid, am)));
                let charging = self.am(am).flag("charge") && find(&self.p(m).volatiles, "twoturnmove").is_none() && !(mid.starts_with("solarb") && (w == "sunnyday" || w == "desolateland"))
                    && !(mid == "electroshot" && (w == "raindance" || w == "primordialsea")) && !self.has_item(m, "powerherb");
                if !self.am(am).tracks_target && !charging {
                    let mid = self.am(am).id;
                    if let RV::M(x) = self.priority_event("RedirectTarget", Tgt::Mon(m), Some(m), Some(Eff::mv(mid, am)), RV::M(t), false) { t = x; }
                }
                if self.am(am).smart_target.unwrap_or(false) { targets = self.get_smart_targets(m, t, am); t = targets[0]; } else { targets.push(t); }
                if self.p(t).fainted { return (vec![], vec![]); }
            }
        }
        let pressure = if mt == "foeSide" { vec![] } else if self.am(am).flag("mustpressure") { self.foes(m).to_vec() } else { targets.clone() };
        (targets, pressure)
    }
    fn get_smart_targets(&mut self, m: MonRef, t: MonRef, am: usize) -> Vec<MonRef> {
        let t2 = self.adjacent_allies(t).first().copied();
        match t2 {
            Some(t2) if t2 != m && self.p(t2).hp > 0 => { if self.p(t).hp == 0 { self.amm(am).smart_target = Some(false); vec![t2] } else { vec![t, t2] } }
            _ => { self.amm(am).smart_target = Some(false); vec![t] }
        }
    }

    // ======================= runMove / useMove =======================
    pub fn run_move(&mut self, am: usize, m: MonRef, target_loc: i64, source_effect: Option<Eff>, original: Option<MonRef>, external: bool) {
        self.pm(m).active_move_actions += 1;
        let mut source_effect = source_effect;
        let mut target = self.get_target(m, am, target_loc, original);
        let mut am = am;
        let mid0 = self.am(am).id;
        if mid0 != "struggle" && !external {
            // Encore: the OverrideAction event answers with the move to use instead (2026-10-09; it used to be reported unsupported)
            let r = self.run_event("OverrideAction", Tgt::Mon(m), target, Some(Eff::mv(mid0, am)), RV::Undef, false, false);
            if let RV::S(changed) = r { if changed != mid0 {
                let (pr, pb) = (self.am(am).priority, self.am(am).prankster_boosted);
                let new = self.new_am(self.dex.active_move(changed));
                self.amm(new).priority = pr; if pb { self.amm(new).prankster_boosted = true; }
                am = new; target = self.get_random_target(m, am);
            } }
        }
        let mid = self.am(am).id;
        self.amm(am).is_external = external;
        self.set_active_move(Some(am), Some(m), target);
        let e = Eff::mv(mid, am);
        let will = self.run_event("BeforeMove", Tgt::Mon(m), target, Some(e), RV::Undef, false, false);
        if !will.truthy() {
            self.run_event("MoveAborted", Tgt::Mon(m), target, Some(e), RV::Undef, false, false);
            self.clear_active_move(true);
            self.pm(m).move_this_turn_result = match will { RV::B(b) => Tri::B(b), RV::Null => Tri::Null, _ => Tri::B(false) };
            return;
        }
        if self.am(am).flag("cantusetwice") && self.p(m).last_move == Some(mid) { self.add_volatile(m, mid, None, None); }
        if self.dex.mv(mid).eff.has_fn("beforeMoveCallback") {
            if self.call_fn(Kind::Move, mid, "beforeMoveCallback", Tgt::Mon(m), target, Some(e)).truthy() {
                self.clear_active_move(true); self.pm(m).move_this_turn_result = Tri::B(false); return;
            }
        }
        self.pm(m).last_damage = 0;
        if !external {
            let locked = self.get_locked_move(m);
            if locked.is_none() {
                if !self.deduct_pp(m, mid, 1) && mid != "struggle" {
                    let n = self.mon_name(m); self.add(&["cant", &n, "nopp"]);
                    self.clear_active_move(true); self.pm(m).move_this_turn_result = Tri::B(false); return;
                }
            } else { source_effect = Some(Eff::cond(id("lockedmove"))); }
            let p = self.pm(m); p.last_move = Some(mid); p.last_move_target_loc = Some(target_loc); p.move_this_turn = mid;
        }
        let did = self.use_move(am, m, target, source_effect);
        self.last_successful_move_this_turn = if did { self.active_move.map(|a| self.am(a).id) } else { None };
        let mv = self.active_move.unwrap_or(am);
        let e = Eff::mv(self.am(mv).id, mv);
        self.single_event("AfterMove", e, None, Tgt::Mon(m), target, Some(e), RV::Undef);
        self.run_event("AfterMove", Tgt::Mon(m), target, Some(e), RV::Undef, false, false);
        if self.am(mv).flag("cantusetwice") { let i = self.am(mv).id; self.remove_volatile(m, i); }
        self.faint_messages(false, false, true);
        self.check_win(None);
    }
    pub fn use_move(&mut self, am: usize, m: MonRef, target: Option<MonRef>, source_effect: Option<Eff>) -> bool {
        self.pm(m).move_this_turn_result = Tri::Undef;
        let r = self.use_move_inner(am, m, target, source_effect);
        if self.p(m).move_this_turn_result == Tri::Undef { self.pm(m).move_this_turn_result = match &r { RV::B(b) => Tri::B(*b), RV::Null => Tri::Null, RV::Undef => Tri::Undef, x => Tri::B(x.truthy()) }; }
        r.truthy()
    }
    fn use_move_inner(&mut self, am: usize, m: MonRef, target: Option<MonRef>, source_effect: Option<Eff>) -> RV {
        let mut target = target;
        let source_effect = source_effect.or(self.effect.filter(|e| !e.id.is_empty()));
        self.pm(m).last_move_used = Some(self.am(am).id);
        if let Some(a) = self.active_move { let (pr, pb) = (self.am(a).priority, self.am(a).prankster_boosted); let x = self.amm(am); x.priority = pr; if !x.has_bounced { x.prankster_boosted = pb; } }
        let base_target = self.am(am).target;
        let mid = self.am(am).id; let e = Eff::mv(mid, am);
        if let RV::Target(t) = self.run_event("ModifyTarget", Tgt::Mon(m), target, Some(e), RV::Target(target), true, false) { if t.is_some() { target = t; } }
        if target.is_none() { target = self.get_random_target(m, am); }
        if base_target == "self" || base_target == "allies" { target = Some(m); }
        if let Some(se) = source_effect {
            self.amm(am).source_effect = Some(se.id);
            let ign = se.kind == Kind::Move && se.am.map(|a| self.am(a).ignore_ability).unwrap_or(false);
            self.amm(am).ignore_ability = ign;
        }
        self.set_active_move(Some(am), Some(m), target);
        self.single_event("ModifyType", e, None, Tgt::Mon(m), target, Some(e), RV::S(id("$move")));
        self.single_event("ModifyMove", e, None, Tgt::Mon(m), target, Some(e), RV::S(id("$move")));
        if base_target != self.am(am).target { target = self.get_random_target(m, am); }
        let r1 = self.run_event("ModifyType", Tgt::Mon(m), target, Some(e), RV::S(id("$move")), false, false);
        let r2 = self.run_event("ModifyMove", Tgt::Mon(m), target, Some(e), RV::S(id("$move")), false, false);
        if base_target != self.am(am).target { target = self.get_random_target(m, am); }
        if !r1.truthy() || !r2.truthy() || self.p(m).fainted { return RV::B(false); }
        if self.logging {
            let tn = target.map(|t| self.mon_name(t)).unwrap_or_default(); let n = self.mon_name(m); let mn = self.am(am).name;
            self.add(&["move", &n, mn, &tn]);
        }
        let Some(t0) = target else { let n = self.mon_name(m); self.add(&["-fail", &n]); return RV::B(false); };
        let (targets, pressure) = self.get_move_targets(m, am, t0);
        if self.logging && targets.len() > 1 {   // as Showdown's attrLastMove: the move line gets every target of a spread move
            let names: Vec<String> = targets.iter().map(|t| self.mon_name(*t)).collect();
            if let Some(l) = self.log.iter_mut().rev().find(|l| l.starts_with("|move|")) { l.push_str(&format!("|[spread] {}", names.join(","))); }
        }
        if let Some(l) = targets.last() { target = Some(*l); }
        let caller_pp = source_effect.map(|s| s.kind == Kind::Move).unwrap_or(false);
        if source_effect.is_none() || caller_pp {
            let mut extra = 0.0;
            for s in pressure { let d = self.run_event("DeductPP", Tgt::Mon(s), Some(m), Some(e), RV::Undef, false, false); if d != RV::B(true) { extra += d.num(); } }
            if extra > 0.0 { self.deduct_pp(m, mid, extra as i64); }
        }
        let mut tmr = self.single_event("TryMove", e, None, Tgt::Mon(m), target, Some(e), RV::Undef);
        if tmr.truthy() { tmr = self.run_event("TryMove", Tgt::Mon(m), target, Some(e), RV::Undef, false, false); }
        if !tmr.truthy() { return tmr; }
        self.single_event("UseMoveMessage", e, None, Tgt::Mon(m), target, Some(e), RV::Undef);
        if self.am(am).ignore_immunity.is_none() { let st = self.am(am).category == "Status"; self.amm(am).ignore_immunity = Some(IgnImm::All(st)); }
        if self.am(am).base.selfdestruct == Some("always") { self.faint(m, Some(m), Some(e)); }
        let move_result: RV;
        if MOVE_SIDE_TARGETS.contains(&self.am(am).target) {
            let d = self.try_move_hit(&targets, m, am);
            if d == RV::NotFail { self.pm(m).move_this_turn_result = Tri::Null; }
            move_result = RV::B(d.truthy() || d == RV::N(0.0) || d.is_undef());
        } else {
            if targets.is_empty() { let n = self.mon_name(m); self.add(&["-fail", &n]); return RV::B(false); }
            move_result = RV::B(self.try_spread_move_hit(targets.clone(), m, am));
        }
        if self.am(am).self_boost.is_some() && move_result.truthy() { let sb = self.am(am).self_boost.clone().unwrap(); self.move_hit(vec![TS::M(m)], m, am, Some(sb), false, true); }
        if self.p(m).hp == 0 { self.faint(m, Some(m), Some(e)); }
        if !move_result.truthy() {
            let orig = self.p(m).hp;
            self.single_event("MoveFail", e, None, target.map(Tgt::Mon).unwrap_or(Tgt::None), Some(m), Some(e), RV::Undef);
            if Some(m) != target && self.am(am).category != "Status" { let p = self.p(m); if p.hp as f64 <= p.maxhp as f64 / 2.0 && orig as f64 > p.maxhp as f64 / 2.0 { self.run_event("EmergencyExit", Tgt::Mon(m), Some(m), None, RV::Undef, false, false); } }
            return RV::B(false);
        }
        if !(self.am(am).has_sheer_force && self.has_ability(m, "sheerforce")) && !self.am(am).flag("futuremove") {
            let orig = self.p(m).hp;
            self.single_event("AfterMoveSecondarySelf", e, None, Tgt::Mon(m), target, Some(e), RV::Undef);
            self.run_event("AfterMoveSecondarySelf", Tgt::Mon(m), target, Some(e), RV::Undef, false, false);
            if Some(m) != target && self.am(am).category != "Status" { let p = self.p(m); if p.hp as f64 <= p.maxhp as f64 / 2.0 && orig as f64 > p.maxhp as f64 / 2.0 { self.run_event("EmergencyExit", Tgt::Mon(m), Some(m), None, RV::Undef, false, false); } }
        }
        RV::B(true)
    }
    /// call a non-event function of an effect (basePowerCallback, damageCallback, beforeMoveCallback, durationCallback, ...)
    pub fn call_fn(&mut self, kind: Kind, i: Id, f: &str, target: Tgt, source: Option<MonRef>, eff: Option<Eff>) -> RV {
        let key = (kind, i, id(f));
        match self.reg.get(&key) {
            Some(h) => { let h = *h; let mut a = HArgs { relay: RV::Undef, has_relay: false, target, source, src_eff: eff }; h(self, &mut a) }
            None => { self.unsupported(format!("{:?}:{}.{}", kind, i, f)); RV::Undef }
        }
    }
    pub fn deduct_pp(&mut self, m: MonRef, mid: Id, amount: i64) -> bool {
        let p = self.pm(m);
        let Some(s) = p.move_slots.iter_mut().find(|s| s.id == mid) else { return false };
        s.used = true;
        if s.pp == 0 { return false; }
        s.pp -= amount; if s.pp < 0 { s.pp = 0; }
        true
    }

    // ======================= hit pipeline =======================
    pub fn try_move_hit(&mut self, targets: &[MonRef], m: MonRef, am: usize) -> RV {
        let target = targets.first().copied();
        self.set_active_move(Some(am), Some(m), target);
        let e = Eff::mv(self.am(am).id, am);
        let mut hr = self.single_event("Try", e, None, Tgt::Mon(m), target, Some(e), RV::Undef);
        if hr.truthy() { hr = self.single_event("PrepareHit", e, None, target.map(Tgt::Mon).unwrap_or(Tgt::None), Some(m), Some(e), RV::Undef); }
        if hr.truthy() { hr = self.run_event("PrepareHit", Tgt::Mon(m), target, Some(e), RV::Undef, false, false); }
        if !hr.truthy() { if hr == RV::B(false) { let n = self.mon_name(m); self.add(&["-fail", &n]); } return RV::B(false); }
        hr = if self.am(am).target == "all" { self.run_event("TryHitField", target.map(Tgt::Mon).unwrap_or(Tgt::None), Some(m), Some(e), RV::Undef, false, false) }
             else { self.run_event("TryHitSide", target.map(Tgt::Mon).unwrap_or(Tgt::None), Some(m), Some(e), RV::Undef, false, false) };
        if !hr.truthy() { if hr == RV::B(false) { let n = self.mon_name(m); self.add(&["-fail", &n]); } return RV::B(false); }
        let r = self.move_hit(vec![target.map(TS::M).unwrap_or(TS::N)], m, am, None, false, false);
        r
    }
    pub fn try_spread_move_hit(&mut self, targets: Vec<MonRef>, m: MonRef, am: usize) -> bool {
        if targets.len() > 1 && !self.am(am).smart_target.unwrap_or(false) { self.amm(am).spread_hit = true; }
        let e = Eff::mv(self.am(am).id, am);
        let t0 = targets[0];
        let mut hr = self.single_event("Try", e, None, Tgt::Mon(m), Some(t0), Some(e), RV::Undef);
        if hr.truthy() { hr = self.single_event("PrepareHit", e, None, Tgt::Mon(t0), Some(m), Some(e), RV::Undef); }
        if hr.truthy() { hr = self.run_event("PrepareHit", Tgt::Mon(m), Some(t0), Some(e), RV::Undef, false, false); }
        if !hr.truthy() {
            if hr == RV::B(false) { let n = self.mon_name(m); self.add(&["-fail", &n]); }
            return hr == RV::NotFail;
        }
        let mut targets = targets;
        let mut at_least_one_failure = false;
        for step in 0..7 {
            let res: Option<Vec<RV>> = match step {
                0 => Some(self.hit_step_invulnerability(&targets, m, am)),
                1 => Some(self.hit_step_try_hit(&targets, m, am)),
                2 => Some(self.hit_step_type_immunity(&targets, m, am)),
                3 => Some(self.hit_step_try_immunity(&targets, m, am)),
                4 => Some(self.hit_step_accuracy(&targets, m, am)),
                5 => { self.hit_step_break_protect(&targets, m, am); None }
                _ => Some(self.hit_step_move_hit_loop(&targets, m, am)),
            };
            let Some(res) = res else { continue };
            let keep: Vec<MonRef> = targets.iter().zip(res.iter()).filter(|(_, r)| r.truthy() || **r == RV::N(0.0)).map(|(t, _)| *t).collect();
            at_least_one_failure = at_least_one_failure || res.iter().any(|r| *r == RV::B(false));
            if self.am(am).smart_target.unwrap_or(false) && at_least_one_failure { self.amm(am).smart_target = Some(false); }
            targets = keep;
            if targets.is_empty() { break; }
        }
        self.amm(am).hit_targets = targets.clone();
        let ok = !targets.is_empty();
        if !ok && !at_least_one_failure { self.pm(m).move_this_turn_result = Tri::Null; }
        ok
    }
    fn hit_step_invulnerability(&mut self, targets: &[MonRef], m: MonRef, am: usize) -> Vec<RV> {
        if self.am(am).id == "helpinghand" { return vec![RV::B(true); targets.len()]; }
        let e = Eff::mv(self.am(am).id, am);
        let mut out = vec![];
        for &t in targets {
            let r = if find(&self.p(t).volatiles, "commanding").is_some() { RV::B(false) }
                    else if self.am(am).id == "toxic" && self.has_type(m, "Poison") { RV::B(true) }
                    else { self.run_event("Invulnerability", Tgt::Mon(t), Some(m), Some(e), RV::Undef, false, false) };
            if r == RV::B(false) {
                if self.am(am).smart_target.unwrap_or(false) { self.amm(am).smart_target = Some(false); }
                else { let (a, b) = (self.mon_name(m), self.mon_name(t)); self.add(&["-miss", &a, &b]); }
            }
            out.push(r);
        }
        out
    }
    fn hit_step_try_hit(&mut self, targets: &[MonRef], m: MonRef, am: usize) -> Vec<RV> {
        let e = Eff::mv(self.am(am).id, am);
        let mut r = self.run_event_spread("TryHit", targets.iter().map(|t| Some(*t)).collect(), Some(m), Some(e), None);
        if !r.contains(&RV::B(true)) && r.contains(&RV::B(false)) { let n = self.mon_name(m); self.add(&["-fail", &n]); }
        for x in r.iter_mut() { if *x != RV::NotFail && !x.truthy() { *x = RV::B(false); } }
        r
    }
    fn hit_step_type_immunity(&mut self, targets: &[MonRef], _m: MonRef, am: usize) -> Vec<RV> {
        if self.am(am).ignore_immunity.is_none() { let st = self.am(am).category == "Status"; self.amm(am).ignore_immunity = Some(IgnImm::All(st)); }
        let msg = !self.am(am).smart_target.unwrap_or(false);
        targets.iter().map(|&t| RV::B(self.run_immunity_move(t, am, msg))).collect()
    }
    fn hit_step_try_immunity(&mut self, targets: &[MonRef], m: MonRef, am: usize) -> Vec<RV> {
        let e = Eff::mv(self.am(am).id, am);
        let mut out = vec![];
        for &t in targets {
            let r = if self.am(am).flag("powder") && t != m && { let ty = self.get_types(t); self.dex.immune_type("powder", &ty) } {
                let n = self.mon_name(t); self.add(&["-immune", &n]); false
            } else if !self.single_event("TryImmunity", e, None, Tgt::Mon(t), Some(m), Some(e), RV::Undef).truthy() {
                let n = self.mon_name(t); self.add(&["-immune", &n]); false
            } else if self.am(am).prankster_boosted && self.has_ability(m, "prankster") && !self.is_ally(t, m) && { let ty = self.get_types(t); self.dex.immune_type("prankster", &ty) } {
                let n = self.mon_name(t); self.add(&["-immune", &n]); false
            } else { true };
            out.push(RV::B(r));
        }
        out
    }
    /// MISS_DOUBLE=<side> (champ-battle-v19, 2026-10-06): that side's accuracy rolls use p' = max(0, 2p - 100) in place of the final hit
    /// chance p (base accuracy, stages, ModifyAccuracy and Accuracy events applied), so its misses are twice as likely: Hurricane 70 ->
    /// 40, Sleep Powder 75 -> 50, OHKO moves 30 -> 0. Rolls that the game has already made certain (accuracy `true`) are untouched, and
    /// a miss caused by the rule is an ordinary miss (Blunder Policy, crash damage). Secondary chances are not affected.
    pub fn miss_double() -> Option<u8> { static F: std::sync::OnceLock<Option<u8>> = std::sync::OnceLock::new(); *F.get_or_init(|| std::env::var("MISS_DOUBLE").ok().and_then(|x| x.parse().ok())) }
    /// the accuracy roll: does the move by m hit, given its final hit chance acc (true = certain)? MISS_STATS=1 counts rolls and misses
    /// per side and move (printed by `champ battle` at the end) to check the rule.
    fn roll_accuracy(&mut self, m: MonRef, am: usize, acc: &RV) -> bool {
        if *acc == RV::B(true) { return true; }
        let mut p = acc.num();
        if Self::miss_double() == Some(m.0) { p = (2.0 * p - 100.0).max(0.0); }
        let hit = self.prng.chance(p as i64, 100);
        if miss_stats() { let mid = self.am(am).id; let mut g = MISS_STATS.lock().unwrap(); let e = g.entry((m.0, mid)); e.0 += 1; if !hit { e.1 += 1; } }
        hit
    }
    fn hit_step_accuracy(&mut self, targets: &[MonRef], m: MonRef, am: usize) -> Vec<RV> {
        let e = Eff::mv(self.am(am).id, am);
        let mut out = vec![];
        for &t in targets {
            self.active_target = Some(t);
            let mut acc: RV = match self.am(am).accuracy { Some(a) => RV::N(a), None => RV::B(true) };
            if let Some(ohko) = self.am(am).ohko {
                if !self.is_semi_invulnerable(t) {
                    let mut a = 30.0;
                    if ohko == "Ice" && !self.has_type(m, "Ice") { a = 20.0; }
                    let lvl_ok = self.p(m).level >= self.p(t).level && (ohko == "true" || !self.has_type(t, ohko));
                    if lvl_ok { a += (self.p(m).level - self.p(t).level) as f64; acc = RV::N(a); }
                    else { let n = self.mon_name(t); self.add(&["-immune", &n, "[ohko]"]); out.push(RV::B(false)); continue; }
                }
            } else {
            acc = self.run_event("ModifyAccuracy", Tgt::Mon(t), Some(m), Some(e), acc, false, false);
            if acc != RV::B(true) {
                let mut boost = 0i64;
                if !self.am(am).ignore_accuracy {
                    let b = self.boost_event(m); boost = Battle::clamp(b[5], -6, 6);
                }
                if !self.am(am).ignore_evasion {
                    let b = self.boost_event(t); boost = Battle::clamp(boost - b[6], -6, 6);
                }
                let a = acc.num();
                if boost > 0 { acc = RV::N(Battle::trunc(a * (3 + boost) as f64 / 3.0) as f64); } else if boost < 0 { acc = RV::N(Battle::trunc(a * 3.0 / (3 - boost) as f64) as f64); }
            }
            }
            let mv = self.am(am);
            let self_status = mv.target == "self" && mv.category == "Status";
            if mv.always_hit || (mv.id == "toxic" && self.has_type(m, "Poison")) || self_status {
                acc = RV::B(true);
            } else {
                acc = self.run_event("Accuracy", Tgt::Mon(t), Some(m), Some(e), acc, false, false);
            }
            if !self.roll_accuracy(m, am, &acc) {
                if self.am(am).smart_target.unwrap_or(false) { self.amm(am).smart_target = Some(false); }
                else { let (a, b) = (self.mon_name(m), self.mon_name(t)); self.add(&["-miss", &a, &b]); }
                out.push(RV::B(false)); continue;
            }
            out.push(RV::B(true));
        }
        out
    }
    /// runEvent('ModifyBoost', pokemon, null, null, {...boosts}) -> boosts array
    pub fn boost_event(&mut self, m: MonRef) -> [i64; 7] {
        let b: Boosts = (0..7).map(|k| (k as u8, self.p(m).boosts[k])).collect();
        let mut out = self.p(m).boosts;
        if let RV::Boosts(r) = self.run_event("ModifyBoost", Tgt::Mon(m), None, None, RV::Boosts(b), false, false) { for (k, v) in r { out[k as usize] = v; } }
        out
    }
    fn hit_step_break_protect(&mut self, targets: &[MonRef], m: MonRef, am: usize) {
        if !self.am(am).breaks_protect { return; }
        for &t in targets {
            let mut broke = false;
            for v in ["banefulbunker", "burningbulwark", "kingsshield", "obstruct", "protect", "silktrap", "spikyshield"] { if self.remove_volatile(t, v) { broke = true; } }
            for c in ["craftyshield", "matblock", "quickguard", "wideguard"] { if self.remove_side_condition(t.0, c) { broke = true; } }
            if broke { self.pm(t).volatiles.retain(|(k, _)| *k != "stall"); let n = self.mon_name(t); self.add(&["-activate", &n, "move: Feint"]); }
        }
        let _ = m;
    }
    fn hit_step_move_hit_loop(&mut self, targets: &[MonRef], m: MonRef, am: usize) -> Vec<RV> {
        let mut damage: Vec<RV> = vec![RV::N(0.0); targets.len()];
        self.amm(am).total_damage = 0;
        self.pm(m).last_damage = 0;
        let target_hits = match self.am(am).multihit {
            None => 1,
            Some((a, b)) if a == b => a,
            Some((2, 5)) => { let tbl = [2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 5, 5, 5]; let i = self.prng.sample_idx(tbl.len()); let mut h = tbl[i];
                               if h < 4 && self.has_item(m, "loadeddice") { h = 5 - self.prng.below(2); } h }
            Some((a, b)) => self.prng.range(a, b + 1),
        };
        let mut target_hits = target_hits;
        if target_hits == 10 && self.has_item(m, "loadeddice") { target_hits -= self.prng.below(7); }
        let mut null_damage = true;
        let mut move_damage: Vec<RV> = vec![];
        let sleep_usable = self.am(am).sleep_usable;
        let mut targets_copy: Vec<TS> = targets.iter().map(|t| TS::M(*t)).collect();
        let mut hit = 1;
        while hit <= target_hits {
            if damage.contains(&RV::B(false)) { break; }
            if hit > 1 && self.p(m).status == "slp" && !sleep_usable { break; }
            if targets.iter().all(|t| self.p(*t).hp == 0) { break; }
            { let x = self.amm(am); x.hit = hit; x.last_hit = hit == target_hits; }
            let smart = self.am(am).smart_target.unwrap_or(false);
            if smart && targets.len() > 1 { targets_copy = vec![TS::M(targets[hit as usize - 1])]; damage = vec![damage.get(hit as usize - 1).cloned().unwrap_or(RV::Undef)]; }   // JS: [damage[hit - 1]] (may be undefined)
            else { targets_copy = targets.iter().map(|t| TS::M(*t)).collect(); }
            if let (Some(TS::M(t)), true) = (targets_copy.first().copied(), self.am(am).multiaccuracy && hit > 1) {
                let e = Eff::mv(self.am(am).id, am);
                let mut acc: RV = match self.am(am).accuracy { Some(a) => RV::N(a), None => RV::B(true) };
                let tbl = [1.0, 4.0 / 3.0, 5.0 / 3.0, 2.0, 7.0 / 3.0, 8.0 / 3.0, 3.0];
                if acc != RV::B(true) {
                    let mut a = acc.num();
                    if !self.am(am).ignore_accuracy { let bo = Battle::clamp(self.boost_event(m)[5], -6, 6); if bo > 0 { a *= tbl[bo as usize]; } else { a /= tbl[(-bo) as usize]; } }
                    if !self.am(am).ignore_evasion { let bo = Battle::clamp(self.boost_event(t)[6], -6, 6); if bo > 0 { a /= tbl[bo as usize]; } else if bo < 0 { a *= tbl[(-bo) as usize]; } }
                    acc = RV::N(a);
                }
                acc = self.run_event("ModifyAccuracy", Tgt::Mon(t), Some(m), Some(e), acc, false, false);
                if !self.am(am).always_hit {
                    acc = self.run_event("Accuracy", Tgt::Mon(t), Some(m), Some(e), acc, false, false);
                    if !self.roll_accuracy(m, am, &acc) { break; }
                }
            }
            let (mdh, tc) = self.spread_move_hit(targets_copy.clone(), m, am, None, false, false);
            targets_copy = tc;
            if smart { move_damage.extend(mdh); } else { move_damage = mdh; }
            if !move_damage.iter().any(|v| *v != RV::B(false)) { break; }
            null_damage = false;
            for (i, md) in move_damage.clone().iter().enumerate() {
                if smart && i as i64 != hit - 1 { continue; }
                let dv = if *md == RV::B(true) || !md.truthy() { 0.0 } else { md.num() };
                if i >= damage.len() { damage.resize(i + 1, RV::Undef); } damage[i] = RV::N(dv);
                self.amm(am).total_damage += dv as i64;
            }
            self.each_event("Update", None);
            if self.p(m).hp == 0 && targets.len() == 1 { hit += 1; break; }
            hit += 1;
        }
        if hit == 1 { return vec![RV::B(false); damage.len()]; }
        if null_damage { for d in damage.iter_mut() { *d = RV::B(false); } }
        let src_fainted = self.p(m).hp == 0;
        self.faint_messages(false, false, src_fainted);
        let td = self.am(am).total_damage;
        if td != 0 { self.apply_recoil_damage(td, am, m); }
        if self.am(am).smart_target.unwrap_or(false) { targets_copy = targets.iter().map(|t| TS::M(*t)).collect(); }
        let e = Eff::mv(self.am(am).id, am);
        for (i, t) in targets_copy.iter().enumerate() {
            if let TS::M(t) = t { if *t != m {
                let md = move_damage.get(i).cloned().unwrap_or(RV::Undef);
                let dn = if let RV::N(x) = md { x as i64 } else { 0 };
                let slot = self.slot_name(m); let mid = self.am(am).id;
                self.pm(*t).attacked_by.push(Attack { source: m, damage: dn, mv: mid, this_turn: true, slot });
                if let RV::N(_) = md { let add = if self.am(am).smart_target.unwrap_or(false) { 1 } else { hit - 1 }; self.pm(*t).times_attacked += add; }
            } }
        }
        if !damage.iter().any(|v| v.truthy() || *v == RV::N(0.0)) { return damage; }
        self.each_event("Update", None);
        let tcm: Vec<MonRef> = targets_copy.iter().filter_map(|t| t.m()).collect();
        if !(self.am(am).has_sheer_force && self.has_ability(m, "sheerforce")) {
            self.single_event("AfterMoveSecondary", e, None, tcm.first().map(|t| Tgt::Mon(*t)).unwrap_or(Tgt::None), Some(m), Some(e), RV::Undef);
            self.run_event_spread("AfterMoveSecondary", tcm.iter().map(|t| Some(*t)).collect(), Some(m), Some(e), None);
            for (i, d) in damage.iter().enumerate() {
                let cur = if targets.len() == 1 { RV::N(self.am(am).total_damage as f64) } else { d.clone() };
                if let RV::N(c) = cur { let t = targets[i]; let p = self.p(t);
                    if p.hp > 0 { let before = p.hurt_this_turn.unwrap_or(0) as f64 + c;
                        if (p.hp as f64) <= p.maxhp as f64 / 2.0 && before > p.maxhp as f64 / 2.0 { self.run_event("EmergencyExit", Tgt::Mon(t), Some(m), None, RV::Undef, false, false); } } }
            }
        }
        damage
    }
    pub fn apply_recoil_damage(&mut self, dealt: i64, am: usize, m: MonRef) {
        let mv = self.am(am).clone();
        let recoil = if mv.struggle_recoil { Battle::clamp((self.p(m).base_maxhp as f64 / 4.0).round() as i64, 1, i64::MAX) }
                     else if mv.mind_blown_recoil { (self.p(m).maxhp as f64 / 2.0).round() as i64 }
                     else if let Some((a, b)) = mv.recoil { Battle::clamp(js_round(dealt as f64 * a as f64 / b as f64), 1, i64::MAX) }
                     else { return };
        let before = self.p(m).hp;
        if mv.struggle_recoil { self.direct_damage(recoil, m, Some(m), Some(Eff::cond(id("strugglerecoil")))); }
        else { self.damage(recoil as f64, Some(m), Some(m), Some(Eff::cond(id("recoil"))), false); }
        let p = self.p(m);
        if p.hp as f64 <= p.maxhp as f64 / 2.0 && before as f64 > p.maxhp as f64 / 2.0 { self.run_event("EmergencyExit", Tgt::Mon(m), Some(m), None, RV::Undef, false, false); }
    }
    /// moveHit -> spreadMoveHit with one target
    pub fn move_hit(&mut self, targets: Vec<TS>, m: MonRef, am: usize, hit_effect: Option<HitEff>, is_secondary: bool, is_self: bool) -> RV {
        let (d, _) = self.spread_move_hit(targets, m, am, hit_effect, is_secondary, is_self);
        let r = d.into_iter().next().unwrap_or(RV::Undef);
        if r == RV::B(true) { RV::Undef } else { r }
    }
    /// spreadMoveHit (Champions version)
    pub fn spread_move_hit(&mut self, mut targets: Vec<TS>, m: MonRef, am: usize, hit_effect: Option<HitEff>, is_secondary: bool, is_self: bool) -> (Vec<RV>, Vec<TS>) {
        let target = targets.first().copied().and_then(|t| t.m());
        let mut damage: Vec<RV> = vec![RV::B(true); targets.len()];
        let md: HitEff = hit_effect.clone().unwrap_or_else(|| self.am(am).base.clone());
        let mid = self.am(am).id; let e = Eff::mv(mid, am);
        let md_eff = Eff { part: md.part, ..e };
        let mtarget = self.am(am).target;
        let hit_result: RV = if mtarget == "all" && !is_self { self.single_event("TryHitField", md_eff, None, target.map(Tgt::Mon).unwrap_or(Tgt::None), Some(m), Some(e), RV::Undef) }
            else if ["foeSide", "allySide", "allyTeam"].contains(&mtarget) && !is_self { self.single_event("TryHitSide", md_eff, None, target.map(Tgt::Mon).unwrap_or(Tgt::None), Some(m), Some(e), RV::Undef) }
            else if let Some(t) = target { if md.part.is_empty() { self.single_event("TryHit", md_eff, None, Tgt::Mon(t), Some(m), Some(e), RV::Undef) } else { RV::B(true) } }
            else { RV::B(true) };
        if !hit_result.truthy() {
            if hit_result == RV::B(false) { let n = self.mon_name(m); self.add(&["-fail", &n]); }
            return (vec![RV::B(false)], targets);
        }
        // moveData is the move object itself in Showdown, so changes made by its handlers (Clangorous Soul deletes move.boosts) show through
        let md: HitEff = if hit_effect.is_none() { self.am(am).base.clone() } else { md };
        if !is_secondary && !is_self && !MOVE_SIDE_TARGETS.contains(&mtarget) {
            for (i, t) in targets.iter().enumerate() { if let TS::M(t) = t { damage[i] = self.run_event("TryPrimaryHit", Tgt::Mon(*t), Some(m), Some(md_eff), RV::Undef, false, false); } }
        }
        for i in 0..targets.len() {
            if damage[i] == RV::N(0.0) { damage[i] = RV::B(true); targets[i] = TS::N; }   // HIT_SUBSTITUTE
            if targets[i] != TS::F && targets[i] != TS::N && is_secondary && md.self_eff.is_none() { damage[i] = RV::B(true); }
            if !damage[i].truthy() { targets[i] = TS::F; }
        }
        damage = self.get_spread_damage(damage, &targets, m, am, &md, is_secondary, is_self);
        for i in 0..targets.len() { if damage[i] == RV::B(false) { targets[i] = TS::F; } }
        damage = self.spread_damage(damage, &targets, Some(m), Some(e), false);
        for i in 0..targets.len() { if damage[i] == RV::B(false) { targets[i] = TS::F; } }
        damage = self.run_move_effects(damage, &targets, m, am, &md, is_secondary, is_self);
        for i in 0..targets.len() { if !damage[i].truthy() && damage[i] != RV::N(0.0) { targets[i] = TS::F; } }
        let active_target = self.active_target;
        if md.self_eff.is_some() && !self.am(am).self_dropped { self.self_drops(&targets, m, am, &md, is_secondary); }
        if md.part.is_empty() && self.am(am).secondaries.is_some() { self.secondaries(&targets, m, am, is_self); }
        self.active_target = active_target;
        if md.force_switch {   // forceSwitch: DragOut, then the flag makes runAction drag in a random benched pokemon
            for (i, t) in targets.clone().iter().enumerate() { let TS::M(t) = *t else { continue };
                if self.p(t).hp > 0 && self.p(m).hp > 0 && self.can_switch(t.0) > 0 {
                    let r = self.run_event("DragOut", Tgt::Mon(t), Some(m), Some(e), RV::Undef, false, false);
                    if r.truthy() { self.pm(t).force_switch_flag = true; }
                    else if r == RV::B(false) && self.am(am).category == "Status" { let n = self.mon_name(m); self.add(&["-fail", &n]); damage[i] = RV::B(false); }
                } }
        }
        for i in 0..targets.len() { if !damage[i].truthy() && damage[i] != RV::N(0.0) { targets[i] = TS::F; } }
        let mut dt = vec![]; let mut dd = vec![];
        for (i, t) in targets.iter().enumerate() { if let (RV::N(x), TS::M(t)) = (&damage[i], t) { dt.push(Some(*t)); dd.push(RV::N(*x)); } }
        let orig_hp = self.p(m).hp;
        if !dd.is_empty() && !is_secondary && !is_self {
            self.run_event_spread("DamagingHit", dt.clone(), Some(m), Some(e), Some(dd));
            if self.dex.mv(mid).eff.cbs.contains_key("onAfterHit") {
                for t in dt.iter().flatten() { self.single_event("AfterHit", e, None, Tgt::Mon(*t), Some(m), Some(e), RV::Undef); }
            }
            let p = self.p(m);
            if p.hp > 0 && p.hp as f64 <= p.maxhp as f64 / 2.0 && orig_hp as f64 > p.maxhp as f64 / 2.0 { self.run_event("EmergencyExit", Tgt::Mon(m), None, None, RV::Undef, false, false); }
        }
        (damage, targets)
    }
    fn get_spread_damage(&mut self, mut damage: Vec<RV>, targets: &[TS], m: MonRef, am: usize, md: &HitEff, is_secondary: bool, is_self: bool) -> Vec<RV> {
        for (i, t) in targets.iter().enumerate() {
            let TS::M(t) = t else { continue };
            self.active_target = Some(*t);
            damage[i] = RV::Undef;
            // getDamage runs on the moveData: a secondary or self effect has no base power, so it deals no damage
            let cur = if md.part.is_empty() { self.get_damage(m, *t, am) } else { RV::Undef };
            if cur == RV::B(false) || cur == RV::Null {
                if damage[i] == RV::B(false) && !is_secondary && !is_self { let n = self.mon_name(m); self.add(&["-fail", &n]); }
                damage[i] = RV::B(false); continue;
            }
            damage[i] = cur;
        }
        damage
    }
    fn run_move_effects(&mut self, mut damage: Vec<RV>, targets: &[TS], m: MonRef, am: usize, md: &HitEff, is_secondary: bool, is_self: bool) -> Vec<RV> {
        let mut did_anything = damage.iter().skip(1).fold(damage.first().cloned().unwrap_or(RV::Undef), |a, b| combine(&a, b));
        let mid = self.am(am).id; let e = Eff::mv(mid, am);
        let mtarget = self.am(am).target;
        for (i, t) in targets.iter().enumerate() {
            if *t == TS::F { continue; }
            let mut did: RV = RV::Undef;
            if let TS::M(t) = *t {
                if let Some(b) = &md.boosts { if !self.p(t).fainted {
                    let r = self.boost(b.clone(), Some(t), Some(m), Some(e), is_secondary, is_self); did = combine(&did, &r);
                } }
                if let Some((hn, hd)) = md.heal { if !self.p(t).fainted {
                    if self.p(t).hp >= self.p(t).maxhp {
                        let n = self.mon_name(t); self.add(&["-fail", &n, "heal"]);
                        damage[i] = combine(&damage[i], &RV::B(false)); did_anything = combine(&did_anything, &RV::Null); continue;
                    }
                    let amount = js_round(self.p(t).base_maxhp as f64 * hn as f64 / hd as f64);
                    let d = self.heal(amount as f64, Some(t), Some(m), Some(e));
                    if !d.truthy() && d != RV::N(0.0) {
                        if d != RV::Null { let n = self.mon_name(m); self.add(&["-fail", &n]); }
                        damage[i] = combine(&damage[i], &RV::B(false)); did_anything = combine(&did_anything, &RV::Null); continue;
                    }
                    did = RV::B(true);
                } }
                if let Some(st) = md.status {
                    let src_eff = if let Some(a) = md.ability { Eff::new(Kind::Ability, a) } else { e };
                    let r = self.try_set_status(t, st, Some(m), Some(src_eff));
                    if !r.truthy() && self.am(am).base.status.is_some() { damage[i] = combine(&damage[i], &RV::B(false)); did_anything = combine(&did_anything, &RV::Null); continue; }
                    did = combine(&did, &r);
                }
                if let Some(v) = md.volatile_status { let r = self.add_volatile(t, v, Some(m), Some(e)); did = combine(&did, &r); }
                if let Some(c) = md.side_condition { let r = self.add_side_condition(t.0, c, Some(m), Some(e)); did = combine(&did, &r); }
                if let Some(sc) = md.slot_condition { let r = self.add_slot_condition(t, sc, Some(m), Some(e)); did = combine(&did, &r); }
                if let Some(w) = md.weather { let r = self.set_weather(w, Some(m), Some(e)); did = combine(&did, &r); }
                if let Some(tr) = md.terrain { let r = self.set_terrain(tr, Some(m), Some(e)); did = combine(&did, &r); }
                if let Some(pw) = md.pseudo_weather { let r = self.add_pseudo_weather(pw, Some(m), Some(e)); did = combine(&did, &r); }
                if md.force_switch { let r = RV::B(self.can_switch(t.0) > 0); did = combine(&did, &r); }
                let md_eff = Eff { part: md.part, ..e };
                if mtarget == "all" && !is_self {
                    if self.has_part_fn(mid, md, "onHitField") { let r = self.single_event("HitField", md_eff, None, Tgt::Mon(t), Some(m), Some(e), RV::Undef); did = combine(&did, &r); }
                } else if (mtarget == "foeSide" || mtarget == "allySide") && !is_self {
                    if self.has_part_fn(mid, md, "onHitSide") { let r = self.single_event("HitSide", md_eff, None, Tgt::Side(t.0), Some(m), Some(e), RV::Undef); did = combine(&did, &r); }
                } else {
                    if self.has_part_fn(mid, md, "onHit") { let r = self.single_event("Hit", md_eff, None, Tgt::Mon(t), Some(m), Some(e), RV::Undef); did = combine(&did, &r); }
                    if !is_self && !is_secondary { self.run_event("Hit", Tgt::Mon(t), Some(m), Some(e), RV::Undef, false, false); }
                }
            }
            // the data holds "ifhit" (ids are lower-cased); the old "ifHit" comparison never matched, so Healing Wish and Memento users
            // never fainted (both were kept out of the planner's options for that reason until 2026-10-09)
            if md.selfdestruct == Some("ifhit") && damage[i] != RV::B(false) { self.faint(m, Some(m), Some(e)); }
            if md.self_switch.is_some() {
                if self.can_switch(m.0) > 0 && find(&self.p(m).volatiles, "commanded").is_none() { did = RV::B(true); } else { did = combine(&did, &RV::B(false)); }
            }
            if did.is_undef() { did = RV::B(true); }
            let dv = if did == RV::Null { RV::B(false) } else { did.clone() };
            damage[i] = combine(&damage[i], &dv);
            did_anything = combine(&did_anything, &did);
        }
        if !did_anything.truthy() && did_anything != RV::N(0.0) && md.self_eff.is_none() && md.selfdestruct.is_none() {
            if !is_self && !is_secondary && did_anything == RV::B(false) { let n = self.mon_name(m); self.add(&["-fail", &n]); }
        } else if self.am(am).base.self_switch.is_some() { if self.p(m).hp > 0 && find(&self.p(m).volatiles, "commanded").is_none() { let mid = self.am(am).id; self.pm(m).switch_flag = Some(mid); } }
        damage
    }
    fn has_part_fn(&self, mid: Id, md: &HitEff, cb: &str) -> bool {
        if md.part.is_empty() { self.dex.mv(mid).eff.cbs.get(cb).map(|c| !c.absent).unwrap_or(false) } else { cb == "onHit" && md.on_hit }
    }
    fn self_drops(&mut self, targets: &[TS], m: MonRef, am: usize, md: &HitEff, is_secondary: bool) {
        let Some(se) = md.self_eff.clone() else { return };
        for t in targets {
            if *t == TS::F { continue; }
            if self.am(am).self_dropped { continue; }
            if !is_secondary && se.boosts.is_some() {
                let roll = self.prng.below(100);
                if se.chance.map(|c| roll < c).unwrap_or(true) { self.move_hit(vec![TS::M(m)], m, am, Some((*se).clone()), is_secondary, true); }
                if self.am(am).multihit.is_none() { self.amm(am).self_dropped = true; }
            } else {
                self.move_hit(vec![TS::M(m)], m, am, Some((*se).clone()), is_secondary, true);
            }
        }
    }
    fn secondaries(&mut self, targets: &[TS], m: MonRef, am: usize, is_self: bool) {
        let Some(secs) = self.am(am).secondaries.clone() else { return };
        let mid = self.am(am).id;
        for t in targets {
            if *t == TS::F { continue; }
            let tt = match t { TS::M(x) => Tgt::Mon(*x), _ => Tgt::None };
            let list = match self.run_event("ModifySecondaries", tt, Some(m), Some(Eff::mv(mid, am)), RV::Secs(secs.clone()), false, false) { RV::Secs(s) => s, _ => secs.clone() };
            for s in list {
                let roll = self.prng.below(100);
                if s.chance.map(|c| roll < c).unwrap_or(true) { self.move_hit(vec![*t], m, am, Some(s), true, is_self); }
            }
        }
    }

    // ======================= damage =======================
    /// getDamage (+ Champions modifyDamage); returns N(damage), B(false) (immune/failed), Undef (no damage: status move or 0 bp)
    pub fn get_damage(&mut self, src: MonRef, t: MonRef, am: usize) -> RV {
        let mid = self.am(am).id; let e = Eff::mv(mid, am);
        if !self.run_immunity_move(t, am, true) { return RV::B(false); }
        if self.am(am).ohko.is_some() { return RV::N(self.p(t).maxhp as f64); }
        if self.dex.mv(mid).eff.has_fn("damageCallback") { return self.call_fn(Kind::Move, mid, "damageCallback", Tgt::Mon(t), Some(src), Some(e)); }
        if self.am(am).level_damage { return RV::N(self.p(src).level as f64); }
        if let Some(d) = self.am(am).fixed_damage { return RV::N(d); }
        let category = self.dex.mv(mid).tmpl.category;
        let mut bp = self.am(am).base_power;
        if self.dex.mv(mid).eff.has_fn("basePowerCallback") { bp = self.call_fn(Kind::Move, mid, "basePowerCallback", Tgt::Mon(t), Some(src), Some(e)).num(); }
        if bp == 0.0 { return RV::Undef; }
        let mut bp = Battle::clamp(bp as i64, 1, i64::MAX) as f64;
        let crit_ratio = self.am(am).crit_ratio as f64;
        let cr = self.run_event("ModifyCritRatio", Tgt::Mon(src), Some(t), Some(e), RV::N(crit_ratio), false, false).num();
        let cr = Battle::clamp(cr as i64, 0, 4);
        let crit_mult = [0, 24, 8, 2, 1];
        let slot = self.slot_name(t);
        let mut crit = self.am(am).will_crit.unwrap_or(false);
        if self.am(am).will_crit.is_none() && cr != 0 { crit = self.prng.chance(1, crit_mult[cr as usize]); }
        if crit { crit = self.run_event("CriticalHit", Tgt::Mon(t), None, Some(e), RV::Undef, false, false).truthy(); }
        self.amm(am).hd(slot).crit = crit;
        bp = self.run_event("BasePower", Tgt::Mon(src), Some(t), Some(e), RV::N(bp), true, false).num();
        if bp == 0.0 { return RV::N(0.0); }
        let bp = Battle::clamp(bp as i64, 1, i64::MAX);
        let level = self.p(src).level;
        let mv = self.am(am).clone();
        let attacker = if mv.override_offensive_pokemon == Some("target") { t } else { src };
        let defender = if mv.override_defensive_pokemon == Some("source") { src } else { t };
        let is_phys = mv.category == "Physical";
        let atk_stat = mv.override_offensive_stat.unwrap_or(if is_phys { "atk" } else { "spa" });
        let def_stat = mv.override_defensive_stat.unwrap_or(if is_phys { "def" } else { "spd" });
        let si = |s: &str| ["", "atk", "def", "spa", "spd", "spe"].iter().position(|x| *x == s).unwrap();
        let mut atk_boost = self.p(attacker).boosts[si(atk_stat) - 1];
        let mut def_boost = self.p(defender).boosts[si(def_stat) - 1];
        let (mut ign_neg_off, mut ign_pos_def) = (mv.ignore_negative_offensive, mv.ignore_positive_defensive);
        if crit { ign_neg_off = true; ign_pos_def = true; }
        if mv.ignore_offensive || (ign_neg_off && atk_boost < 0) { atk_boost = 0; }
        if mv.ignore_defensive || (ign_pos_def && def_boost > 0) { def_boost = 0; }
        let attack = self.calculate_stat(attacker, si(atk_stat), atk_boost, src);
        let defense = self.calculate_stat(defender, si(def_stat), def_boost, t);
        let ev_a = if category == "Physical" { "ModifyAtk" } else { "ModifySpA" };
        let ev_d = ["", "ModifyAtk", "ModifyDef", "ModifySpA", "ModifySpD", "ModifySpe"][si(def_stat)];
        let attack = self.run_event(ev_a, Tgt::Mon(src), Some(t), Some(e), RV::N(attack as f64), false, false).num();
        let defense = self.run_event(ev_d, Tgt::Mon(t), Some(src), Some(e), RV::N(defense as f64), false, false).num();
        let tr = |x: f64| Battle::trunc(x) as f64;
        let base = tr(tr(tr(tr(2.0 * level as f64 / 5.0 + 2.0) * bp as f64 * attack) / defense) / 50.0);
        RV::N(self.modify_damage(base as i64, src, t, am) as f64)
    }
    /// getConfusionDamage(pokemon, basePower)
    pub fn confusion_damage(&mut self, m: MonRef, bp: i64) -> i64 {
        let (ab, db) = (self.p(m).boosts[0], self.p(m).boosts[1]);
        let attack = self.calculate_stat(m, 1, ab, m) as f64;
        let defense = self.calculate_stat(m, 2, db, m) as f64;
        let level = self.p(m).level as f64;
        let tr = |x: f64| Battle::trunc(x) as f64;
        let base = tr(tr(tr(tr(2.0 * level / 5.0 + 2.0) * bp as f64 * attack) / defense) / 50.0) + 2.0;
        let d = Battle::trunc(base) % 65536;
        let d = Battle::trunc(Battle::trunc(d as f64 * (100 - self.prng.below(16)) as f64) as f64 / 100.0);
        d.max(1)
    }
    fn calculate_stat(&mut self, m: MonRef, i: usize, boost: i64, user: MonRef) -> i64 {
        let stat = self.p(m).stored[i];
        let b: Boosts = vec![((i - 1) as u8, boost)];
        let boost = match self.run_event("ModifyBoost", Tgt::Mon(user), None, None, RV::Boosts(b), false, false) {
            RV::Boosts(r) => r.iter().find(|(k, _)| *k as usize == i - 1).map(|x| x.1).unwrap_or(boost), _ => boost };
        let s = boost_stat(stat, boost.clamp(-6, 6));
        self.modify(s as f64, 1.0)
    }
    fn modify_damage(&mut self, base: i64, src: MonRef, t: MonRef, am: usize) -> i64 {
        let mid = self.am(am).id; let e = Eff::mv(mid, am);
        let mtype = self.am(am).mtype;
        let mut d = base + 2;
        if self.am(am).spread_hit { d = self.modify(d as f64, 0.75); }
        else if self.am(am).multihit_type == Some("parentalbond") && self.am(am).hit > 1 { d = self.modify(d as f64, 0.25); }
        d = self.priority_event("WeatherModifyDamage", Tgt::Mon(src), Some(t), Some(e), RV::N(d as f64), false).num() as i64;
        let slot = self.slot_name(t);
        let crit = self.amm(am).hd(slot).crit;
        if crit { d = Battle::trunc(d as f64 * self.am(am).crit_modifier.unwrap_or(1.5)); }
        d = Battle::trunc(Battle::trunc(d as f64 * (100 - self.prng.below(16)) as f64) as f64 / 100.0);
        if mtype != "???" {
            let types = self.get_types(src);
            let is_stab = self.am(am).force_stab || types.contains(&mtype);
            let mut stab = if is_stab { 1.5 } else { 1.0 };
            stab = self.run_event("ModifySTAB", Tgt::Mon(src), Some(t), Some(e), RV::N(stab), false, false).num();
            d = self.modify(d as f64, stab);
        }
        let tm = self.run_effectiveness(t, am);
        let tm = Battle::clamp(tm, -6, 6);
        self.amm(am).hd(slot).type_mod = tm;
        if tm > 0 { for _ in 0..tm { d *= 2; } }
        if tm < 0 { for _ in 0..(-tm) { d = Battle::trunc(d as f64 / 2.0); } }
        if self.p(src).status == "brn" && self.am(am).category == "Physical" && !self.has_ability(src, "guts") && mid != "facade" { d = self.modify(d as f64, 0.5); }
        d = self.run_event("ModifyDamage", Tgt::Mon(src), Some(t), Some(e), RV::N(d as f64), false, false).num() as i64;
        if self.amm(am).hd(slot).bypass_protect { d = self.modify(d as f64, 0.25); }
        if d == 0 { return 1; }
        Battle::trunc(d as f64) % 65536
    }
    pub fn run_effectiveness(&mut self, t: MonRef, am: usize) -> i64 {
        let mid = self.am(am).id; let e = Eff::mv(mid, am);
        let mtype = self.am(am).mtype;
        let mut total = 0.0;
        for ty in self.get_types(t) {
            let mut tm = RV::N(self.dex.effectiveness(mtype, ty) as f64);
            self.eff_type = ty;   // Showdown passes the defending type in the source slot; handlers read it here
            tm = self.single_event("Effectiveness", e, None, Tgt::Mon(t), None, Some(e), tm);
            self.eff_type = ty;
            total += self.run_event("Effectiveness", Tgt::Mon(t), None, Some(e), tm, false, false).num();
        }
        total as i64
    }
    /// pokemon.runImmunity(move, message)
    pub fn run_immunity_move(&mut self, t: MonRef, am: usize, message: bool) -> bool {
        let mtype = self.am(am).mtype;
        match &self.am(am).ignore_immunity { Some(IgnImm::All(true)) => return true, Some(IgnImm::Types(v)) if v.contains(&mtype) => return true, _ => {} }
        self.run_immunity_type(t, mtype, message)
    }
    pub fn run_immunity_type(&mut self, t: MonRef, ty: Id, message: bool) -> bool {
        if ty.is_empty() || ty == "???" { return true; }
        self.eff_type = ty;
        let negate = !self.run_event("NegateImmunity", Tgt::Mon(t), None, None, RV::Undef, false, false).truthy();
        let not_immune: Option<bool> = if ty == "Ground" { self.is_grounded(t, negate) } else { Some(negate || { let types = self.get_types(t); !self.dex.immune_type(ty, &types) }) };
        if not_immune == Some(true) { return true; }
        if message { let n = self.mon_name(t); self.add(&["-immune", &n]); }
        false
    }
    /// isGrounded: Some(true) grounded, Some(false) airborne, None = Levitate
    pub fn is_grounded(&mut self, m: MonRef, negate: bool) -> Option<bool> {
        if find(&self.field.pseudo, "gravity").is_some() { return Some(true); }
        let vols = &self.p(m).volatiles;
        if find(vols, "ingrain").is_some() || find(vols, "smackdown").is_some() { return Some(true); }
        let item = if self.ignoring_item(m) { "" } else { self.p(m).item };
        if item == "ironball" { return Some(true); }
        if !negate && self.has_type(m, "Flying") && !(self.has_type(m, "???") && find(&self.p(m).volatiles, "roost").is_some()) { return Some(false); }
        if (self.has_ability(m, "levitate") || self.has_ability(m, "eelevate")) && !self.suppressing_ability(Some(m)) { return None; }
        if find(&self.p(m).volatiles, "magnetrise").is_some() || find(&self.p(m).volatiles, "telekinesis").is_some() { return Some(false); }
        Some(item != "airballoon")
    }
    /// pokemon.effectiveWeather(sourceEffect): Mega Sol makes the user's moves act as in sun; Utility Umbrella hides sun/rain
    pub fn pokemon_effective_weather(&self, m: MonRef, source_effect: Option<Eff>) -> Id {
        let se = source_effect.or(self.effect);
        let w = self.effective_weather();
        if let Some(ap) = self.active_pokemon { if self.has_ability(ap, "megasol") { if let Some(se) = se {
            let et = self.etype_of(&se);
            if (se.id == "megasol" || et == EType::Move || et == EType::Weather) && se.id != "electroshot" { return id("sunnyday"); } } } }
        if ["sunnyday", "raindance", "desolateland", "primordialsea"].contains(&w) && self.has_item(m, "utilityumbrella") { return ""; }
        w
    }
    pub fn run_status_immunity(&mut self, m: MonRef, ty: &str, message: bool) -> bool {
        if self.p(m).fainted { return false; }
        if ty.is_empty() { return true; }
        let types = self.get_types(m);
        if self.dex.immune_type(ty, &types) { if message { let n = self.mon_name(m); self.add(&["-immune", &n]); } return false; }
        let r = self.run_event("Immunity", Tgt::Mon(m), None, None, RV::S(id(ty)), false, false);
        if !r.truthy() { if message && r != RV::Null { let n = self.mon_name(m); self.add(&["-immune", &n]); } return false; }
        true
    }

    /// battle.spreadDamage
    pub fn spread_damage(&mut self, damage: Vec<RV>, targets: &[TS], source: Option<MonRef>, effect: Option<Eff>, _instafaint: bool) -> Vec<RV> {
        let mut ret = vec![];
        let eff_type = effect.map(|e| self.etype_of(&e));
        for (i, cur) in damage.iter().enumerate() {
            let t = targets.get(i).copied().unwrap_or(TS::F);
            if !(cur.truthy() || *cur == RV::N(0.0)) { ret.push(cur.clone()); continue; }
            let Some(t) = t.m() else { ret.push(RV::N(0.0)); continue };
            if self.p(t).hp == 0 { ret.push(RV::N(0.0)); continue; }
            if !self.p(t).is_active { ret.push(RV::B(false)); continue; }
            let mut td = cur.num();
            if td != 0.0 { td = td.floor().max(1.0); }   // clampIntRange(damage, 1)
            if effect.map(|e| e.id) != Some("strugglerecoil") {
                if eff_type == Some(EType::Weather) && !self.run_status_immunity(t, effect.unwrap().id, false) { ret.push(RV::N(0.0)); continue; }
                let r = self.run_event("Damage", Tgt::Mon(t), source, effect, RV::N(td), true, false);
                if !(r.truthy() || r == RV::N(0.0)) { ret.push(if *cur == RV::B(true) { RV::Undef } else { r }); continue; }
                td = r.num();
            }
            if td != 0.0 { td = td.floor().max(1.0); }
            let dealt = self.pokemon_damage(t, td, source, effect);
            if dealt != 0 { let hp = self.p(t).hp; self.pm(t).hurt_this_turn = Some(hp); }
            if let (Some(s), Some(EType::Move)) = (source, eff_type) { self.pm(s).last_damage = dealt; }
            if self.logging { let n = self.mon_name(t); let p = self.p(t); let hp = format!("{}/{}", p.hp, p.maxhp);
                              let from = effect.filter(|_| eff_type != Some(EType::Move)).map(|e| format!("[from] {}", e.id)).unwrap_or_default(); self.add(&["-damage", &n, &hp, &from]);
                              if eff_type == Some(EType::Move) { if let Some(am) = effect.and_then(|e| e.am) { let slot = self.slot_name(t); let (crit, tm) = { let hd = self.amm(am).hd(slot); (hd.crit, hd.type_mod) };
                                  if crit { self.add(&["-crit", &n]); } if tm > 0 { self.add(&["-supereffective", &n]); } else if tm < 0 { self.add(&["-resisted", &n]); } } } }
            if dealt != 0 && eff_type == Some(EType::Move) {
                if let (Some(s), Some(e)) = (source, effect) { if let Some(am) = e.am { if let Some((a, b)) = self.am(am).drain {
                    let amount = js_round(dealt as f64 * a as f64 / b as f64);
                    self.heal(amount as f64, Some(s), Some(t), Some(Eff::cond(id("drain"))));
                } } }
            }
            ret.push(RV::N(dealt as f64));
        }
        ret
    }
    pub fn damage(&mut self, d: f64, target: Option<MonRef>, source: Option<MonRef>, effect: Option<Eff>, instafaint: bool) -> RV {
        let (target, source, effect) = self.event_defaults(target, source, effect);
        let Some(t) = target else { return RV::N(0.0) };
        self.spread_damage(vec![RV::N(d)], &[TS::M(t)], source, effect, instafaint).remove(0)
    }
    fn event_defaults(&self, target: Option<MonRef>, source: Option<MonRef>, effect: Option<Eff>) -> (Option<MonRef>, Option<MonRef>, Option<Eff>) {
        match &self.event { Some(ev) => (target.or(ev.target.mon()), source.or(ev.source), effect.or(self.effect)), None => (target, source, effect) }
    }
    /// pokemon.damage
    pub fn pokemon_damage(&mut self, m: MonRef, d: f64, source: Option<MonRef>, effect: Option<Eff>) -> i64 {
        if self.p(m).hp == 0 || d.is_nan() || d <= 0.0 { return 0; }
        let mut d = Battle::trunc(if d < 1.0 { 1.0 } else { d });
        self.pm(m).hp -= d;
        if self.p(m).hp <= 0 { d += self.p(m).hp; self.faint(m, source, effect); }
        d
    }
    pub fn direct_damage(&mut self, d: i64, m: MonRef, source: Option<MonRef>, effect: Option<Eff>) -> i64 {
        if self.p(m).hp == 0 || d == 0 { return 0; }
        let d = self.pokemon_damage(m, d.max(1) as f64, source, effect);
        if self.p(m).fainted { self.faint(m, source, effect); }
        d
    }
    /// battle.heal
    pub fn heal(&mut self, d: f64, target: Option<MonRef>, source: Option<MonRef>, effect: Option<Eff>) -> RV {
        let (target, source, effect) = self.event_defaults(target, source, effect);
        let mut d = d; if d != 0.0 && d <= 1.0 { d = 1.0; }
        let d = Battle::trunc(d) as f64;
        let r = self.run_event("TryHeal", target.map(Tgt::Mon).unwrap_or(Tgt::None), source, effect, RV::N(d), false, false);
        if !r.truthy() { return r; }
        let Some(t) = target else { return RV::B(false) };
        if self.p(t).hp == 0 || !self.p(t).is_active || self.p(t).hp >= self.p(t).maxhp { return RV::B(false); }
        let fin = self.pokemon_heal(t, r.num());
        if self.logging { let n = self.mon_name(t); let p = self.p(t); let hp = format!("{}/{}", p.hp, p.maxhp); self.add(&["-heal", &n, &hp]); }
        self.run_event("Heal", Tgt::Mon(t), source, effect, RV::N(fin as f64), false, false);
        RV::N(fin as f64)
    }
    pub fn pokemon_heal(&mut self, m: MonRef, d: f64) -> i64 {
        let p = self.pm(m);
        if p.hp == 0 { return 0; }
        let mut d = Battle::trunc(d);
        if d <= 0 || p.hp >= p.maxhp { return 0; }
        p.hp += d; if p.hp > p.maxhp { d -= p.hp - p.maxhp; p.hp = p.maxhp; }
        d
    }
    /// battle.boost
    pub fn boost(&mut self, boost: Boosts, target: Option<MonRef>, source: Option<MonRef>, effect: Option<Eff>, is_secondary: bool, is_self: bool) -> RV {
        let (target, source, effect) = self.event_defaults(target, source, effect);
        let Some(t) = target else { return RV::N(0.0) };
        if self.p(t).hp == 0 { return RV::N(0.0); }
        if !self.p(t).is_active { return RV::B(false); }
        if self.sides[1 - t.0 as usize].pokemon_left == 0 { return RV::B(false); }
        let b = match self.run_event("ChangeBoost", Tgt::Mon(t), source, effect, RV::Boosts(boost.clone()), false, false) { RV::Boosts(b) => b, _ => boost };
        let b = self.capped_boost(t, &b);
        let b = match self.run_event("TryBoost", Tgt::Mon(t), source, effect, RV::Boosts(b.clone()), false, false) { RV::Boosts(b) => b, _ => b };
        let mut success = RV::Null;
        let eff_type = effect.map(|e| self.etype_of(&e));
        let mut boosted = is_secondary;
        for (k, v) in b.iter() {
            let cur = self.pm(t).boosts[*k as usize];
            let capped = Battle::clamp(cur + v, -6, 6) - cur;
            self.pm(t).boosts[*k as usize] += capped;
            let mut by = capped;
            let neg = *v < 0 || self.p(t).boosts[*k as usize] == -6;
            if neg { by = -by; }
            if by != 0 {
                success = RV::B(true);
                if self.logging { let n = self.mon_name(t); let msg = if neg { "-unboost" } else { "-boost" }; self.add(&[msg, &n, BOOST_NAMES[*k as usize], &by.to_string()]); }
                if eff_type == Some(EType::Ability) && !boosted { boosted = true; }
                self.run_event("AfterEachBoost", Tgt::Mon(t), source, effect, RV::Boosts(vec![(*k, capped)]), false, false);
            } else if eff_type == Some(EType::Ability) {
                if is_secondary || is_self { /* message only */ }
            }
        }
        self.run_event("AfterBoost", Tgt::Mon(t), source, effect, RV::Boosts(b.clone()), false, false);
        if success.truthy() {
            if b.iter().any(|(_, v)| *v > 0) { self.pm(t).stats_raised_this_turn = true; }
            if b.iter().any(|(_, v)| *v < 0) { self.pm(t).stats_lowered_this_turn = true; }
        }
        success
    }
    pub fn capped_boost(&self, m: MonRef, b: &Boosts) -> Boosts {
        b.iter().filter(|(_, v)| *v != 0).map(|(k, v)| { let cur = self.p(m).boosts[*k as usize]; (*k, Battle::clamp(cur + v, -6, 6) - cur) }).collect()
    }

    // ======================= status / volatiles / conditions =======================
    pub fn try_set_status(&mut self, m: MonRef, st: Id, source: Option<MonRef>, src_eff: Option<Eff>) -> RV {
        let cur = self.p(m).status;
        self.set_status(m, if cur.is_empty() { st } else { cur }, source, src_eff, false)
    }
    pub fn set_status(&mut self, m: MonRef, st: Id, source: Option<MonRef>, src_eff: Option<Eff>, ignore_imm: bool) -> RV {
        if self.p(m).hp == 0 { return RV::B(false); }
        let (mut source, mut src_eff) = (source, src_eff);
        if let Some(ev) = &self.event { if source.is_none() { source = ev.source; } if src_eff.is_none() { src_eff = self.effect; } }
        let source = source.or(Some(m));
        let se_status = src_eff.and_then(|e| self.eff_status(e));
        if self.p(m).status == st {
            if se_status == Some(st) { let n = self.mon_name(m); self.add(&["-fail", &n, st]); }
            else if se_status.is_some() { let n = self.mon_name(source.unwrap()); self.add(&["-fail", &n]); }
            return RV::B(false);
        }
        if !ignore_imm && !st.is_empty() && !(source.map(|s| self.has_ability(s, "corrosion")).unwrap_or(false) && (st == "tox" || st == "psn")) {
            if !self.run_status_immunity(m, if st == "tox" { "psn" } else { st }, false) {
                if se_status.is_some() { let n = self.mon_name(m); self.add(&["-immune", &n]); }
                return RV::B(false);
            }
        }
        let (prev, prev_state) = (self.p(m).status, self.p(m).status_state.clone());
        if !st.is_empty() {
            let r = self.run_event("SetStatus", Tgt::Mon(m), source, src_eff, RV::S(st), false, false);
            if !r.truthy() { return r; }
        }
        let mut ns = self.init_state(st, Some(self.p(m).is_active));
        ns.source = source;
        if let Some(d) = self.dex.conds.get(st).and_then(|c| c.duration) { ns.duration = Some(d); }
        { let p = self.pm(m); p.status = st; p.status_state = ns; }
        if self.dex.conds.get(st).map(|c| c.has_fn("durationCallback")).unwrap_or(false) {
            let d = self.call_fn(Kind::Cond, st, "durationCallback", Tgt::Mon(m), source, src_eff); self.pm(m).status_state.duration = Some(d.num() as i64);
        }
        if !st.is_empty() && !self.single_event("Start", Eff::cond(st), Some(SLoc::Status(m)), Tgt::Mon(m), source, src_eff, RV::Undef).truthy() {
            let p = self.pm(m); p.status = prev; p.status_state = prev_state; return RV::B(false);
        }
        if !st.is_empty() && !self.run_event("AfterSetStatus", Tgt::Mon(m), source, src_eff, RV::S(st), false, false).truthy() { return RV::B(false); }
        RV::B(true)
    }
    fn eff_status(&self, e: Eff) -> Option<Id> {
        match e.kind { Kind::Move => e.am.map(|a| self.am(a).base.status).unwrap_or(self.dex.mv(e.id).tmpl.base.status), _ => self.dex.eff(e.kind, e.id).s("status") }
    }
    pub fn cure_status(&mut self, m: MonRef) -> bool {
        if self.p(m).hp == 0 || self.p(m).status.is_empty() { return false; }
        let n = self.mon_name(m); let s = self.p(m).status; self.add(&["-curestatus", &n, s]);
        self.set_status(m, "", None, None, false); true
    }
    pub fn add_volatile(&mut self, m: MonRef, v: &str, source: Option<MonRef>, src_eff: Option<Eff>) -> RV {
        let v = id(v);
        let cd = self.dex.conds.get(v);
        if self.p(m).hp == 0 && !cd.map(|c| c.b("affectsFainted")).unwrap_or(false) { return RV::B(false); }
        let (mut source, mut src_eff) = (source, src_eff);
        if let Some(ev) = &self.event { if source.is_none() { source = ev.source; } if src_eff.is_none() { src_eff = self.effect; } }
        let source = source.or(Some(m));
        if find(&self.p(m).volatiles, v).is_some() {
            if !cd.map(|c| c.cbs.contains_key("onRestart")).unwrap_or(false) { return RV::B(false); }
            return self.single_event("Restart", Eff::cond(v), Some(SLoc::Vol(m, v)), Tgt::Mon(m), source, src_eff, RV::Undef);
        }
        if !self.run_status_immunity(m, v, false) {
            if src_eff.and_then(|e| self.eff_status(e)).is_some() { let n = self.mon_name(m); self.add(&["-immune", &n]); }
            return RV::B(false);
        }
        let r = self.run_event("TryAddVolatile", Tgt::Mon(m), source, src_eff, RV::S(v), false, false);
        if !r.truthy() { return r; }
        let mut st = self.init_state(v, Some(self.p(m).is_active));
        st.source = source; st.source_slot = source.map(|s| self.slot_name(s));
        if let Some(se) = src_eff { st.source_effect = Some((self.etype_of(&se), se.id)); }
        if let Some(d) = cd.and_then(|c| c.duration) { st.duration = Some(d); }
        self.pm(m).volatiles.push((v, st));
        if cd.map(|c| c.has_fn("durationCallback")).unwrap_or(false) {
            let d = self.call_fn(Kind::Cond, v, "durationCallback", Tgt::Mon(m), source, src_eff);
            if let Some(s) = find_mut(&mut self.pm(m).volatiles, v) { s.duration = Some(d.num() as i64); }
        }
        let r = self.single_event("Start", Eff::cond(v), Some(SLoc::Vol(m, v)), Tgt::Mon(m), source, src_eff, RV::Undef);
        if !r.truthy() { self.pm(m).volatiles.retain(|(k, _)| *k != v); return r; }
        RV::B(true)
    }
    pub fn remove_volatile(&mut self, m: MonRef, v: &str) -> bool {
        if self.p(m).hp == 0 { return false; }
        let v = id(v);
        if find(&self.p(m).volatiles, v).is_none() { return false; }
        self.single_event("End", Eff::cond(v), Some(SLoc::Vol(m, v)), Tgt::Mon(m), None, None, RV::Undef);
        self.pm(m).volatiles.retain(|(k, _)| *k != v);
        true
    }
    pub fn add_side_condition(&mut self, s: u8, c: &str, source: Option<MonRef>, src_eff: Option<Eff>) -> RV {
        let c = id(c);
        let source = source.or_else(|| self.event.as_ref().and_then(|e| e.target.mon())).or_else(|| self.side_active(s).first().copied());
        let cd = self.dex.conds.get(c);
        if find(&self.sides[s as usize].side_conditions, c).is_some() {
            if !cd.map(|x| x.cbs.contains_key("onSideRestart")).unwrap_or(false) { return RV::B(false); }
            return self.single_event("SideRestart", Eff::cond(c), Some(SLoc::SideC(s, c)), Tgt::Side(s), source, src_eff, RV::Undef);
        }
        let mut st = self.init_state(c, Some(true));
        st.source = source; st.source_slot = source.map(|x| self.slot_name(x)); st.duration = cd.and_then(|x| x.duration);
        self.sides[s as usize].side_conditions.push((c, st));
        if cd.map(|x| x.has_fn("durationCallback")).unwrap_or(false) {
            let a0 = self.sides[s as usize].active[0].map(|i| (s, i));
            let d = self.call_fn(Kind::Cond, c, "durationCallback", a0.map(Tgt::Mon).unwrap_or(Tgt::None), source, src_eff);
            if let Some(x) = find_mut(&mut self.sides[s as usize].side_conditions, c) { x.duration = Some(d.num() as i64); }
        }
        if !self.single_event("SideStart", Eff::cond(c), Some(SLoc::SideC(s, c)), Tgt::Side(s), source, src_eff, RV::Undef).truthy() {
            self.sides[s as usize].side_conditions.retain(|(k, _)| *k != c); return RV::B(false);
        }
        self.run_event("SideConditionStart", Tgt::Side(s), source, Some(Eff::cond(c)), RV::Undef, false, false);
        if self.logging { let sd = format!("p{}", s + 1); let x = format!("move: {}", c); self.add(&["-sidestart", &sd, &x]); }
        RV::B(true)
    }
    /// side.addSlotCondition (2026-10-09): a condition on the target's slot (Wish, Healing Wish); handlers run for whoever is in the slot
    pub fn add_slot_condition(&mut self, t: MonRef, c: Id, source: Option<MonRef>, src_eff: Option<Eff>) -> RV {
        let c = id(&to_id(c)); let (s, pos) = (t.0, self.p(t).position);
        if pos > 1 { return RV::B(false); }
        let source = source.or_else(|| self.event.as_ref().and_then(|e| e.target.mon())).or_else(|| self.side_active(s).first().copied());
        let cd = self.dex.conds.get(c);
        if find(&self.sides[s as usize].slot_conditions[pos as usize], c).is_some() {
            if !cd.map(|x| x.cbs.contains_key("onRestart")).unwrap_or(false) { return RV::B(false); }
            return self.single_event("Restart", Eff::cond(c), Some(SLoc::Slot(s, pos, c)), Tgt::Mon(t), source, src_eff, RV::Undef);
        }
        let mut st = self.init_state(c, Some(true));
        st.source = source; st.source_slot = source.map(|x| self.slot_name(x)); st.duration = cd.and_then(|x| x.duration); st.is_slot_condition = true;
        self.sides[s as usize].slot_conditions[pos as usize].push((c, st));
        if cd.map(|x| x.has_fn("durationCallback")).unwrap_or(false) {
            let a0 = self.sides[s as usize].active[0].map(|i| (s, i));
            let d = self.call_fn(Kind::Cond, c, "durationCallback", a0.map(Tgt::Mon).unwrap_or(Tgt::None), source, src_eff);
            if let Some(x) = find_mut(&mut self.sides[s as usize].slot_conditions[pos as usize], c) { x.duration = Some(d.num() as i64); }
        }
        let at = self.sides[s as usize].active[pos as usize].map(|i| (s, i));
        if !self.single_event("Start", Eff::cond(c), Some(SLoc::Slot(s, pos, c)), at.map(Tgt::Mon).unwrap_or(Tgt::None), source, src_eff, RV::Undef).truthy() {
            self.sides[s as usize].slot_conditions[pos as usize].retain(|(k, _)| *k != c); return RV::B(false);
        }
        RV::B(true)
    }
    pub fn remove_slot_condition(&mut self, s: u8, pos: u8, c: Id) -> bool {
        if find(&self.sides[s as usize].slot_conditions[pos as usize], c).is_none() { return false; }
        let a = self.sides[s as usize].active[pos as usize].map(|i| (s, i));
        self.single_event("End", Eff::cond(c), Some(SLoc::Slot(s, pos, c)), a.map(Tgt::Mon).unwrap_or(Tgt::None), None, None, RV::Undef);
        self.sides[s as usize].slot_conditions[pos as usize].retain(|(k, _)| *k != c);
        true
    }
    pub fn remove_side_condition(&mut self, s: u8, c: &str) -> bool {
        let c = id(c);
        if find(&self.sides[s as usize].side_conditions, c).is_none() { return false; }
        if self.logging { let sd = format!("p{}", s + 1); let x = format!("move: {}", c); self.add(&["-sideend", &sd, &x]); }
        self.single_event("SideEnd", Eff::cond(c), Some(SLoc::SideC(s, c)), Tgt::Side(s), None, None, RV::Undef);
        self.sides[s as usize].side_conditions.retain(|(k, _)| *k != c);
        true
    }
    pub fn set_weather(&mut self, w: &str, source: Option<MonRef>, src_eff: Option<Eff>) -> RV {
        let w = id(w);
        let src_eff = src_eff.or(self.effect);
        let source = source.or_else(|| self.event.as_ref().and_then(|e| e.target.mon()));
        if self.field.weather == w {
            if src_eff.map(|e| self.etype_of(&e) == EType::Ability).unwrap_or(false) { return RV::B(false); }
            return RV::B(false);
        }
        if let Some(s) = source {
            let r = self.run_event("SetWeather", Tgt::Mon(s), Some(s), Some(Eff::cond(w)), RV::Undef, false, false);
            if !r.truthy() { return RV::Null; }
        }
        let (pw, ps) = (self.field.weather, self.field.weather_state.clone());
        let mut st = EState::new(w);   // initEffectState({id}): no target, effectOrder 0
        if let Some(s) = source { st.source = Some(s); st.source_slot = Some(self.slot_name(s)); }
        st.duration = self.dex.conds.get(w).and_then(|c| c.duration);
        self.field.weather = w; self.field.weather_state = st;
        if self.dex.conds.get(w).map(|c| c.has_fn("durationCallback")).unwrap_or(false) {
            let d = self.call_fn(Kind::Cond, w, "durationCallback", source.map(Tgt::Mon).unwrap_or(Tgt::None), source, src_eff); self.field.weather_state.duration = Some(d.num() as i64);
        }
        if !self.single_event("FieldStart", Eff::cond(w), Some(SLoc::Weather), Tgt::Field, source, src_eff, RV::Undef).truthy() {
            self.field.weather = pw; self.field.weather_state = ps; return RV::B(false);
        }
        self.each_event("WeatherChange", src_eff);
        if self.logging { self.add(&["-weather", w]); }
        RV::B(true)
    }
    pub fn clear_weather(&mut self) -> bool {
        if self.field.weather.is_empty() { return false; }
        let w = self.field.weather;
        if self.logging { self.add(&["-weather", "none"]); }
        self.single_event("FieldEnd", Eff::cond(w), Some(SLoc::Weather), Tgt::Field, None, None, RV::Undef);
        self.field.weather = ""; self.field.weather_state = EState::default();
        self.each_event("WeatherChange", None);
        true
    }
    pub fn set_terrain(&mut self, t: &str, source: Option<MonRef>, src_eff: Option<Eff>) -> RV {
        let t = id(t);
        let src_eff = src_eff.or(self.effect);
        let source = source.or_else(|| self.event.as_ref().and_then(|e| e.target.mon()));
        if self.field.terrain == t { return RV::B(false); }
        let (pt, ps) = (self.field.terrain, self.field.terrain_state.clone());
        let mut st = EState::new(t);
        if let Some(s) = source { st.source = Some(s); st.source_slot = Some(self.slot_name(s)); }
        st.duration = self.dex.conds.get(t).and_then(|c| c.duration);
        self.field.terrain = t; self.field.terrain_state = st;
        if self.dex.conds.get(t).map(|c| c.has_fn("durationCallback")).unwrap_or(false) {
            let d = self.call_fn(Kind::Cond, t, "durationCallback", source.map(Tgt::Mon).unwrap_or(Tgt::None), source, src_eff); self.field.terrain_state.duration = Some(d.num() as i64);
        }
        if !self.single_event("FieldStart", Eff::cond(t), Some(SLoc::Terrain), Tgt::Field, source, src_eff, RV::Undef).truthy() {
            self.field.terrain = pt; self.field.terrain_state = ps; return RV::B(false);
        }
        self.each_event("TerrainChange", src_eff);
        if self.logging { let x = format!("move: {}", t); self.add(&["-fieldstart", &x]); }
        RV::B(true)
    }
    pub fn clear_terrain(&mut self) -> bool {
        if self.field.terrain.is_empty() { return false; }
        let t = self.field.terrain;
        if self.logging { let x = format!("move: {}", t); self.add(&["-fieldend", &x]); }
        self.single_event("FieldEnd", Eff::cond(t), Some(SLoc::Terrain), Tgt::Field, None, None, RV::Undef);
        self.field.terrain = ""; self.field.terrain_state = EState::default();
        self.each_event("TerrainChange", None);
        true
    }
    pub fn add_pseudo_weather(&mut self, c: &str, source: Option<MonRef>, src_eff: Option<Eff>) -> RV {
        let c = id(c);
        let source = source.or_else(|| self.event.as_ref().and_then(|e| e.target.mon()));
        if find(&self.field.pseudo, c).is_some() {
            if !self.dex.conds.get(c).map(|x| x.cbs.contains_key("onFieldRestart")).unwrap_or(false) { return RV::B(false); }
            return self.single_event("FieldRestart", Eff::cond(c), Some(SLoc::Pseudo(c)), Tgt::Field, source, src_eff, RV::Undef);
        }
        let mut st = EState::new(c);
        st.source = source; st.source_slot = source.map(|s| self.slot_name(s)); st.duration = self.dex.conds.get(c).and_then(|x| x.duration);
        self.field.pseudo.push((c, st));
        if self.dex.conds.get(c).map(|x| x.has_fn("durationCallback")).unwrap_or(false) {
            let d = self.call_fn(Kind::Cond, c, "durationCallback", source.map(Tgt::Mon).unwrap_or(Tgt::None), source, src_eff);
            if let Some(x) = find_mut(&mut self.field.pseudo, c) { x.duration = Some(d.num() as i64); }
        }
        if !self.single_event("FieldStart", Eff::cond(c), Some(SLoc::Pseudo(c)), Tgt::Field, source, src_eff, RV::Undef).truthy() {
            self.field.pseudo.retain(|(k, _)| *k != c); return RV::B(false);
        }
        self.run_event("PseudoWeatherChange", source.map(Tgt::Mon).unwrap_or(Tgt::None), source, Some(Eff::cond(c)), RV::Undef, false, false);
        if self.logging { let x = format!("move: {}", c); self.add(&["-fieldstart", &x]); }
        RV::B(true)
    }
    pub fn remove_pseudo_weather(&mut self, c: &str) -> bool {
        let c = id(c);
        if find(&self.field.pseudo, c).is_none() { return false; }
        if self.logging { let x = format!("move: {}", c); self.add(&["-fieldend", &x]); }
        self.single_event("FieldEnd", Eff::cond(c), Some(SLoc::Pseudo(c)), Tgt::Field, None, None, RV::Undef);
        self.field.pseudo.retain(|(k, _)| *k != c);
        true
    }

    // ======================= items =======================
    pub fn eat_item(&mut self, m: MonRef, force: bool, source: Option<MonRef>, src_eff: Option<Eff>) -> bool {
        let item = self.p(m).item;
        if item.is_empty() { return false; }
        if (self.p(m).hp == 0 && item != "jabocaberry" && item != "rowapberry") || !self.p(m).is_active { return false; }
        let src_eff = src_eff.or(self.effect);
        let source = source.or_else(|| self.event.as_ref().and_then(|e| e.target.mon()));
        if let Some(se) = src_eff { if se.kind == Kind::Item && item != se.id && source == Some(m) { return false; } }
        let ie = Eff::new(Kind::Item, item);
        if self.run_event("UseItem", Tgt::Mon(m), None, None, RV::S(item), false, false).truthy() &&
           (force || self.run_event("TryEatItem", Tgt::Mon(m), None, None, RV::S(item), false, false).truthy()) {
            let n = self.mon_name(m); self.add(&["-enditem", &n, item, "[eat]"]);
            self.single_event("Eat", ie, Some(SLoc::Item(m)), Tgt::Mon(m), source, src_eff, RV::Undef);
            self.run_event("EatItem", Tgt::Mon(m), source, src_eff, RV::S(item), false, false);
            let p = self.pm(m); p.last_item = item; p.item = ""; p.item_state = EState::default(); p.used_item_this_turn = true; p.ate_berry = true;
            self.run_event("AfterUseItem", Tgt::Mon(m), None, None, RV::S(item), false, false);
            return true;
        }
        false
    }
    pub fn use_item(&mut self, m: MonRef, source: Option<MonRef>, src_eff: Option<Eff>) -> bool {
        let item = self.p(m).item;
        if self.p(m).hp == 0 || !self.p(m).is_active || item.is_empty() { return false; }
        let src_eff = src_eff.or(self.effect);
        let source = source.or_else(|| self.event.as_ref().and_then(|e| e.target.mon()));
        if let Some(se) = src_eff { if se.kind == Kind::Item && item != se.id && source == Some(m) { return false; } }
        if self.run_event("UseItem", Tgt::Mon(m), None, None, RV::S(item), false, false).truthy() {
            let n = self.mon_name(m); self.add(&["-enditem", &n, item]);
            if let Some(b) = self.dex.items.get(item).and_then(|d| d.raw.get("boosts")).and_then(parse_boosts) { self.boost(b, Some(m), source, Some(Eff::new(Kind::Item, item)), false, false); }
            self.single_event("Use", Eff::new(Kind::Item, item), Some(SLoc::Item(m)), Tgt::Mon(m), source, src_eff, RV::Undef);
            let p = self.pm(m); p.last_item = item; p.item = ""; p.item_state = EState::default(); p.used_item_this_turn = true;
            self.run_event("AfterUseItem", Tgt::Mon(m), None, None, RV::S(item), false, false);
            return true;
        }
        false
    }
    pub fn take_item(&mut self, m: MonRef, source: Option<MonRef>) -> Option<Id> {
        let source = source.or(Some(m));
        let item = self.p(m).item;
        if item.is_empty() { return None; }
        if self.run_event("TakeItem", Tgt::Mon(m), source, None, RV::S(item), false, false).truthy() {
            self.pm(m).item = "";
            let old = std::mem::take(&mut self.pm(m).item_state);
            self.temp.push(old);
            let tl = SLoc::Temp(self.temp.len() - 1);
            self.single_event("End", Eff::new(Kind::Item, item), Some(tl), Tgt::Mon(m), None, None, RV::Undef);
            self.temp.pop();
            self.run_event("AfterTakeItem", Tgt::Mon(m), None, None, RV::S(item), false, false);
            return Some(item);
        }
        None
    }

    // ======================= residual / end of turn =======================
    pub fn field_event(&mut self, ev: &str, targets: Option<Vec<MonRef>>) {
        let get_key = ev == "Residual";
        let mut hs: Vec<Handler> = vec![];
        self.find_field_handlers(cbi(self.dex, "onField", ev), get_key, None, &mut hs);
        for s in 0..2u8 {
            self.find_side_handlers(s, cbi(self.dex, "onSide", ev), get_key, None, &mut hs);
            for a in self.side_active(s) {
                if ev == "SwitchIn" { self.find_pokemon_handlers(a, cbi(self.dex, "onAny", ev), false, &mut hs); }
                if let Some(t) = &targets { if !t.contains(&a) { continue; } }
                let cb = cbi(self.dex, "on", ev);
                self.find_pokemon_handlers(a, cb, get_key, &mut hs);
                self.find_side_handlers(s, cb, false, Some(a), &mut hs);
                self.find_field_handlers(cb, false, Some(a), &mut hs);
            }
        }
        self.speed_sort(&mut hs, |h| (h.order, h.priority, h.speed, h.sub_order, h.effect_order));
        while !hs.is_empty() {
            let h = hs.remove(0);
            if let Holder::Mon(m) = h.holder { if self.p(m).fainted && !matches!(h.state, SLoc::Slot(..)) { continue; } }
            // only state-holding handlers that came with getKey (not customHolder) can expire
            let has_end = !matches!(h.holder, Holder::Mon(_)) || matches!(h.state, SLoc::Status(_) | SLoc::Vol(..) | SLoc::Ability(_) | SLoc::Item(_) | SLoc::Slot(..));
            let own_state = match (h.holder, h.state) { (Holder::Mon(_), SLoc::SideC(..)) | (Holder::Mon(_), SLoc::Pseudo(_)) | (Holder::Mon(_), SLoc::Weather) | (Holder::Mon(_), SLoc::Terrain) => false, _ => true };
            if ev == "Residual" && has_end && own_state {
                if let Some(st) = self.state_mut(h.state) { if let Some(d) = st.duration { if d != 0 {
                    st.duration = Some(d - 1);
                    if d - 1 == 0 { self.end_effect(&h); if self.ended { return; } continue; }
                } } }
            }
            // stale state checks: the state must still be the one in its place
            if self.state(h.state).is_none() && !matches!(h.state, SLoc::Species(_)) { continue; }
            if let SLoc::Status(m) = h.state { if self.p(m).status != h.eff.id { continue; } }
            if let SLoc::Ability(m) = h.state { if self.p(m).ability != h.eff.id { continue; } }
            if let SLoc::Item(m) = h.state { if self.p(m).item != h.eff.id { continue; } }
            if h.state == SLoc::Weather && self.field.weather != h.eff.id { continue; }
            if h.state == SLoc::Terrain && self.field.terrain != h.eff.id { continue; }
            let hev: Id = match h.holder { Holder::Side(_) => cbn("Side", ev), Holder::Field => cbn("Field", ev), _ => cbn("", ev) };
            if !h.absent {
                let tgt = match h.holder { Holder::Mon(m) => Tgt::Mon(m), Holder::Side(s) => Tgt::Side(s), Holder::Field => Tgt::Field, Holder::Battle => Tgt::Battle };
                // singleEvent(handlerEventid, effect, state, holder, null, null, undefined, callback)
                let eff = h.eff;
                let etype = h.etype;
                let skip = if let Tgt::Mon(m) = tgt { (etype == EType::Status && self.p(m).status != eff.id) || (etype == EType::Item && self.ignoring_item(m)) || (etype == EType::Ability && self.ignoring_ability(m)) } else { false }
                           || (etype == EType::Weather && hev != "FieldStart" && hev != "FieldResidual" && hev != "FieldEnd" && self.suppressing_weather());
                if !skip {
                    let parent = self.event.take();
                    self.event = Some(EventCtx { id: hev, target: tgt.clone(), source: None, effect: None, modifier: f64::NAN });
                    self.event_depth += 1;
                    let mut args = HArgs { relay: RV::B(true), has_relay: false, target: tgt, source: None, src_eff: None };
                    let (pe, ps) = (self.effect, self.effect_state);
                    self.effect = Some(eff); self.effect_state = h.state;
                    let key = (eff.kind, eff.id, h.cb);
                    match h.f.or_else(|| self.reg.get(&key).copied()) { Some(f) => { f(self, &mut args); } None => { if h.cval.is_none() { self.unsupported(format!("{:?}:{}.{}", eff.kind, eff.id, h.cb)); } } }
                    self.effect = pe; self.effect_state = ps;
                    self.event_depth -= 1; self.event = parent;
                }
            }
            self.faint_messages(false, false, true);
            if self.ended { return; }
        }
    }
    /// a residual handler's state ran out: call its end (removeVolatile / clearStatus / removeSideCondition / ...)
    fn end_effect(&mut self, h: &Handler) {
        match h.state {
            SLoc::Vol(m, v) => { self.remove_volatile(m, v); }
            SLoc::Status(m) => { if self.p(m).hp > 0 && !self.p(m).status.is_empty() { self.set_status(m, "", None, None, false); } }
            SLoc::SideC(s, c) => { self.remove_side_condition(s, c); }
            SLoc::Pseudo(c) => { self.remove_pseudo_weather(c); }
            SLoc::Weather => { self.clear_weather(); }
            SLoc::Terrain => { self.clear_terrain(); }
            SLoc::Slot(s, pos, c) => { self.remove_slot_condition(s, pos, c); }
            SLoc::Ability(_) | SLoc::Item(_) => { self.unsupported("ability/item duration end".into()); }
            _ => {}
        }
    }
    /// the request's disables recomputed for every active Pokemon (end_turn's DisableMove pass alone): a position rebuilt from a log
    /// carries the volatiles (Imprison, Taunt, ...) but not the disables Showdown derives from them for the request, so the planner offered
    /// an Imprisoned Trick Room (2026-10-13); on an exported Showdown state it reproduces the request's own disables
    pub fn refresh_disables(&mut self) {
        for s in 0..2u8 { for m in self.side_active(s) {
            if self.p(m).fainted { continue; }
            { let p = self.pm(m); p.maybe_disabled = false; for sl in p.move_slots.iter_mut() { sl.disabled = false; sl.disabled_hidden = false; sl.disabled_source = ""; } }
            self.run_event("DisableMove", Tgt::Mon(m), None, None, RV::Undef, false, false);
            let slots: Vec<Id> = self.p(m).move_slots.iter().map(|x| x.id).collect();
            for sid in slots {
                if self.dex.mv(sid).eff.cbs.contains_key("onDisableMove") {
                    let am = self.new_am(self.dex.active_move(sid));
                    self.single_event("DisableMove", Eff::mv(sid, am), None, Tgt::Mon(m), None, None, RV::Undef);
                }
                if self.dex.mv(sid).tmpl.flag("cantusetwice") && self.p(m).last_move == Some(sid) { self.disable_move(m, sid, false, ""); }
            }
        } }
    }
    pub fn end_turn(&mut self) {
        self.turn += 1;
        self.last_successful_move_this_turn = None;
        for s in 0..2u8 {
            for m in self.side_active(s) {
                {
                    let turn = self.turn;
                    let p = self.pm(m);
                    p.move_this_turn = ""; p.newly_switched = false; p.move_last_turn_result = p.move_this_turn_result; p.move_this_turn_result = Tri::Undef;
                    if turn != 1 { p.used_item_this_turn = false; p.stats_raised_this_turn = false; p.stats_lowered_this_turn = false; p.hurt_this_turn = None; }
                    p.maybe_disabled = false; p.maybe_locked = false;
                    for sl in p.move_slots.iter_mut() { sl.disabled = false; sl.disabled_hidden = false; sl.disabled_source = ""; }
                }
                self.run_event("DisableMove", Tgt::Mon(m), None, None, RV::Undef, false, false);
                let slots: Vec<Id> = self.p(m).move_slots.iter().map(|s| s.id).collect();
                for sid in slots {
                    // only moves with an onDisableMove need a fresh ActiveMove (getActiveMove has no other side effects here)
                    if self.dex.mv(sid).eff.cbs.contains_key("onDisableMove") {
                        let am = self.new_am(self.dex.active_move(sid));
                        self.single_event("DisableMove", Eff::mv(sid, am), None, Tgt::Mon(m), None, None, RV::Undef);
                    }
                    if self.dex.mv(sid).tmpl.flag("cantusetwice") && self.p(m).last_move == Some(sid) { self.disable_move(m, sid, false, ""); }
                }
                {
                    let srcs: Vec<bool> = self.p(m).attacked_by.iter().map(|a| self.p(a.source).is_active).collect();
                    let p = self.pm(m);
                    let mut i = p.attacked_by.len();
                    while i > 0 { i -= 1; if srcs[i] { p.attacked_by[i].this_turn = false; } else { p.attacked_by.remove(i); } }
                }
                self.pm(m).trapped = false; self.pm(m).maybe_trapped = false;
                self.run_event("TrapPokemon", Tgt::Mon(m), None, None, RV::Undef, false, false);
                let types = self.get_types(m);
                if !self.dex.immune_type("trapped", &types) { self.run_event("MaybeTrapPokemon", Tgt::Mon(m), None, None, RV::Undef, false, false); }
                if self.p(m).fainted { continue; }
                self.pm(m).active_turns += 1;
            }
            let side = &mut self.sides[s as usize];
            side.fainted_last_turn = side.fainted_this_turn; side.fainted_this_turn = None;
        }
        if self.logging { self.add(&["turn", &self.turn.to_string()]); }
        // the queue is empty between turns, so no ActiveMove is referenced any more (battle.lastMove isn't read by anything in scope)
        self.amoves.clear(); self.last_move = None; self.active_move = None;
    }
    pub fn disable_move(&mut self, m: MonRef, mid: &str, hidden: bool, source: &str) {
        for s in self.pm(m).move_slots.iter_mut() { if s.id == mid && !(s.disabled && !s.disabled_hidden) { s.disabled = true; s.disabled_hidden = hidden; s.disabled_source = id(source); } }
    }
}

pub fn simple_action(choice: Choice, order: f64) -> Action {
    Action { choice, order, priority: 0.0, fractional_priority: 0.0, speed: 0.0, sub_order: 0.0, effect_order: 0.0, pokemon: None, target_loc: 0,
             original_target: None, am: None, mega: false, source_effect: None, target: None }
}
pub fn switch_action(choice: Choice, out: MonRef, incoming: MonRef) -> Action {
    let mut a = simple_action(choice, if choice == Choice::Switch { 103.0 } else { 3.0 }); a.pokemon = Some(out); a.target = Some(incoming); a
}
/// a player's choice for one active slot: move (request index, target loc, mega), switch to the pokemon at this team position, or pass
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum PChoice { Move(usize, i64, bool), Switch(u8), Pass }
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum SwitchResult { Ok, Failed, PursuitFaint }
/// Math.round (half up, including negatives toward +inf)
pub fn js_round(x: f64) -> i64 { (x + 0.5).floor() as i64 }
