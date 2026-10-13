# Planner weaknesses seen in the Showdown bot's games

The user (2026-10-11): fix planner issues after the ladder climb, not during it; during the climb only behaviour that drags games out
for opponents (a last Pokemon stalling, lost games played out) is fixed on the spot. Add to this list as games show more.

1. **Repeat Protect without the double-Protect check.** The bot decides with the eval bar's position evaluator (`champ evalpos`), which
   lacks self-play's DP2 check. Mega Swampert protected six turns running (3-8) against Rillaboom's priority Grassy Glide while its
   partners fell, never attacking with rain up (Frankfurt-239, game ..2696484953). Other chains: Archaludon (Leftovers, accepted),
   Farigiraf, Raichu, Excadrill (`bot/protect_report.py`). Worst case (11:33 am, regional team f194 #59): Volcarona and Milotic both
   protected every turn from 7 to 11 and never attacked, and an opponent vented in chat. Stopgap since 2026-10-11 noon (the user): the
   bot never Protects with the same Pokemon two turns running (`EG_NO_DOUBLE_PROTECT=0`; self-play cost -1.2 ± 0.7 against the DP2
   planner) and a hard cap of 4 Protect turns running per Pokemon (`protect_chain_cap` in limits.json). Fix after the climb: give the bot
   battle4's turn solver (DP2 + the anticipation pass) through a one-turn decide mode, then reconsider the ban.
   Measured in self-play (800 pool starts, the opponent with the check): a side without the check loses -1.3 ± 0.6 and plays 40 Protect
   chains of 3+ turns (23 with the check); banning back-to-back Protect on that side is free (+0.1 ± 0.8) and removes every chain. With
   the check, the ban costs -1.2 ± 0.7. So the ban is right for the bot as it is, and the check is worth about a point more on top.
2. **Small weights on clearly worse options.** Fictitious play (400 rounds) leaves a few percent on options several points below the
   best (Fake Out without the Mega at 2%, 5 points worse). The user is fine with these as low-probability rolls; a cleanup would drop
   options more than a point or two below the best against the opponent's mix.
3. **Static value tails.** The position value cannot see that every single-target move is redirected (Rage Powder) or that a +6/+6
   Pokemon is out of reach; lost positions read 2-4% instead of ~0. Handled for now by the forfeit rule (real win chance under 2%).
4. **Dead turns look odd.** A Pokemon about to faint before moving spreads its weight over near-equal options (Wide Guard with no
   spread move on the other side). Invisible to opponents (an unexecuted choice never shows), so left as is.
5. **Team-side, not planner:** Frankfurt-156's Archaludon loses its Electric STAB into Lightning Rod Raichu (absorbed twice, boosting
   Raichu), which is where its Leftovers Protect chains came from.
6. **Opponent spreads are never updated from what the game shows.** The position builder guesses each opposing spread once (the
   species' usual spread for its sheet nature, evalbar/spots.py `evs_for`) and keeps it, even after the opponent outspeeds or takes a
   hit in a way that rules it out. `bot/speed_check.py` (2026-10-11, 111 games): only 39 move pairs were clean speed evidence (most
   turns have Trick Room, Tailwind, weather or terrain), the assumed spread got 2 clearly wrong (Modest Archaludon assumed at 0 Speed
   points but outsped a 108-Speed Archaludon; Jolly Sneasler assumed at 32 but outsped by a 178 Gengar) plus 2 the check cannot judge
   (Prankster, Mega timing). **Partly done (Eval bar, 2026-10-11 evening, 190d732):** opponents now get the most used Smogon spread
   with their sheet nature (no more 0-Speed fallback), refined turn by turn by the turn order seen so far (botpos.refine_opponent);
   the bot is restarted onto it. Damage as evidence followed the same evening (1a286e5: each candidate spread's damage range from
   Showdown, cached per hit), with a fix for three Megas whose ability the pssim Showdown package has wrong (Mega Golisopod, Mega
   Garchomp Z, Mega Absol Z) in rebuilt positions. Measured (`bot/belief_test.py`,
   403 of the bot's decisions rebuilt with the builder before and after): the beliefs differ in 269 (67%), but the choice moves little,
   +0.26 points per such decision, about +0.9 a game, only 2 decisions by 5+ points (an upper estimate: the new beliefs taken as true).
   **Remeasured 2026-10-12:** `belief_test.decisions()` had paired each turn's log with the previous turn's request (Showdown sends a
   turn's request right after the log chunk ending in `|turn|N`), so it built a stale or inconsistent position for most turns and
   kept 403. Fixed, all 995 decisions build; beliefs differ in 768 and the gain is **+0.44 points per such decision, about +3.1 a game**
   over 109 games, 21 decisions by 5+ points. Still an upper estimate: the new beliefs are taken as true, and two decisions (+31.5,
   +26.9) carry a sixth of the total, which looks like options outside the mix being valued on few simulations (see 8). The live bot
   was not affected: it decides on the request with the log up to it.
7. **Replacements are scored by the static value.** After a faint the bot picks its replacement by the engine's static value at the
   next turn's start (position.py `replacement`, as self-play's `spot.rs resolve_switches` does), not by the one-turn search it uses
   for its turns. `bot/decision_audit.py` (2026-10-12, 144 of the bot's replacements with two or more candidates, each candidate's
   position solved by `champ evalpos` as a turn is): the search prefers another candidate in 53, by over 10 points in 10, **1.7 points
   per replacement** on average. **Done for the bot (2026-10-12, the user):** position.py scores each candidate with evalpos (about
   1-2 s; the six worst audit cases now pick the search's choice). Still open for self-play: the replacement matrix game on one-turn
   values instead of static ones (costlier; measure it).
8. **Audit of every turn decision (2026-10-12, `bot/decision_audit.py`, 995 decisions rebuilt with today's builder).** Where the played
   option is known (667), the staged solve flags 73 as 5+ points below the best, but the staged solve gives options outside the mix
   only 2-8 simulations per cell, so the best of many such options reads high (a 62% double switch next to a 50% equilibrium). Solved
   again with every cell at 32 seeds and the game solved exactly (`exact`), and leaving out 3 turns where Rage Powder pulled the bot's
   move (the log shows where a move landed, not where it was aimed): 24 decisions 5+ points worse, 9 by 10+, about 0.4 points per
   decision. Every one had 0% weight in today's mix; most had weight under the earlier builder (beliefs about spreads, the bot's own
   spreads guessed before fb4780f), and the live pipeline reproduces today: the bot's logged weights and values since its 03:33 UTC
   restart match the rebuild within 1-3 points of value. Engine and Showdown move orders agree on all 1,896 active slots checked.
   Forfeits (`bot/forfeit_check.py`, 45 of 46 rebuilt, each played out 40 times by self-play): 0.3% won on average, at most 7.5%.
9. **Perish Song traps.** The planner cannot play the Perish trap from either side: a regional team's Politoed used Perish Song three
   turns running and it failed each time (every Pokemon already had a count). Handled for now by leaving the 13 Perish Song teams out of
   the regional pool (2026-10-12, the user); an opponent's Perish Song is still played without understanding the counts.
10. **One guess at the opponent's unseen back row.** The bot plans each turn against the single most likely pair for the opponent's
   two unseen Pokemon (botpos `topk=1`), not a weighted few, so a wrong guess plans for a back row that is not there.
   Measured (`bot/back_test.py`, 2026-10-12, 464 decisions where the opponent still had unseen Pokemon and the game later showed its
   whole back row): the guess is fully right in 45% (two unseen: both right 41%, one of two 58%, neither 1%; one unseen: 50%). Where it
   is wrong (253 scored), the bot's mix planned on the guess loses a median **0.23 points** against the mix planned on the truth, two
   thirds under 1 point, mean 1.15 (16 decisions by 5+ points, one by 28): about 3.9 points a game in the 74 games that had any (an
   upper estimate, as in 6). The win-chance estimate moves a median 1.6 points (90th percentile 9). Switching barely changes: the bot
   switches in 37% of its mix planned on the guess and 36% on the truth; decisions with 20%+ switching lose a little more (1.3 vs 0.9).
   Fix to measure after the climb: plan against the top three back rows (the eval bar's live mode already averages over three), e.g.
   the bot's mix as the hypotheses' mixes weighted by their odds, at three times the engine time per turn.
   **Measured 2026-10-12 evening (`bot/back3_test.py`, the bot's current settings, 783 decisions with unseen opposing Pokemon, right
   first guesses included):** the top guess loses 0.78 ± 0.09 planner points a decision against planning on the truth; the top three's
   mixes weighted by their odds lose 0.87 ± 0.06 (gain -0.08 ± 0.06: +0.37 where the first guess was wrong, -0.59 where it was right).
   Averaging separate solutions does not help; the bot keeps the top guess. What could: one game over the hypotheses (payoffs averaged
   by their odds, the opposing switches to unseen Pokemon mapped by bench slot), not yet built.

## Where the strength gap is (2026-10-12, the user: even with every issue above fixed the bot would not be near the top players)
- **The bot's estimates hold because two errors cancel** (`bot/ladder_lines.py`, 441 decisions with both plays known). Against the bot's
  equilibrium mix, the opponents' plays should add +4.1 points a decision (the planner's charge for their departures) and the bot's own
  play cost 0.4; what happened was +0.9. When the opponent plays inside the planner's mix the bot still slides -2.1 a decision (most
  with regional teams, about -5; least with the Trick Room six), later in games and in lost positions most; the bot's own top plays do
  about 2 points worse than rated while humans' agreed plays do about 2 better: choosing by the value picks the options it overrates.
  When the opponent plays a line under 5% the bot gains +4.4 (predicted +7.3): attacks the planner dislikes are real mistakes (+7.6 for
  the bot, charged 5.5), Protect (+1.9, charged 9.8) and setup (+1.9, charged 8.4, n 14) are not. pssim/human_lines.py's 12,272 cached
  decisions agree (Protect net +4.9, setup +3.5, support lines +15-20). So the leak is the value, not bugs or depth.
- **Two-turn horizon, fuller version** (2026-10-12, current build, BATTLE_HORIZON=2 with 2 seeds, 8x8 cells, 3 hits, margin 0.1; 400
  starts per side vs 800 baseline): side 0 -2.9 ± 3.1, side 1 +6.5 ± 2.9, pooled **+1.8 ± 2.1**, 2-2.7x the time. Flat, like the
  4,800-game run of 2026-10-07 (+0.2 ± 0.9). Depth with the same leaf value inherits its errors.
- **Best-of-3 memory** (`bot/bo3_carry.py`): on 3,262 cached matches a player brings the same four next game 47% of the time (three of
  four 84%), the same leads 39%; the back row at the next game's turn 1 is guessed right 45% by the population rates, 58% using the
  previous game's four. Game 1 reads 15% of opposing spreads off the start-of-game guess (10% in Speed, by 13 at the median). Worth
  perhaps 1-2 points per later game.
- **Answering how humans actually choose** (`bot/exploit_test.py`): a model fitted on the cached decisions (60% softmax of the planner's
  option values at temperature 0.16, 40% the planner's mix tilted by kind: Protect 1.6x, setup 2.2x, redirection 2x) predicts humans
  far better than the planner's mix (log score -1.64 vs -2.20). On 470 of the bot's decisions (full matrices, exact equilibria, scored
  against the opponents' actual plays): the best answer to the model gains **+0.78 ± 0.49 points a decision** (about +5 a game) at a
  price of 0.52 against a perfect opponent; half and half gains +0.39 at 0.26. A perfect read is worth +9.8 a decision, so a sharper
  model of human play (by situation, by turn, by what the player did earlier in the match) has room. Valued by the planner's own
  matrix, so it inherits the value's errors.
11. **The damage race's memo ignored the attacker's HP for pinch abilities (found 2026-10-12, fixed in the dev build only).** plan.rs
   `race_damage` caches calc results by a key that had the attacker's HP only for Eruption / Water Spout, but calc.rs boosts a move 1.5x
   for Blaze / Torrent / Overgrow / Swarm at 1/3 HP or less. Within one decision the search reaches leaves with that attacker both above
   and below the line, so some leaves read the other's damage (the race features: KO edge, HP edge), depending on which was computed
   first; also made `champ feats` / `vfeats` depend on thread count (2 of 3,968 held-out positions). The key now carries the pinch flag;
   features are identical on 1 and 2 threads. The live bot still runs the frozen build with the bug (rare: those four abilities near the
   line); it goes in with the next approved engine change.
12. **Engine moves without handlers (the Eval bar, 2026-10-12):** Defog (does not clear screens / hazards / terrain), Court Change (does
   not swap side conditions), Tidy Up (does not clear hazards / Substitutes): the move data runs, the special effects do not. Nearly
   unused in Reg M-C (18.8k replays: Defog 4 uses, Tidy Up 4, Court Change 0); fix if a team that matters brings one.
13. **A small order dependence left in evalpos (2026-10-12):** the same position solved twice in one run (a copy, on another thread) gave a
   payoff cell of 0.2906 and 0.2908 with the same seeds. The race memo's pinch-ability key fix removed the large case (thread-count
   dependent features); something else in a memo or cache key still differs by order. Small; find it before trusting cell-level diffs
   under 0.001.
14. **Rare decisive outcomes sampled away (the Eval bar, 2026-10-13).** The one-turn search samples 32 luck seeds a cell, so a 1-in-24 crit
    that is the only out is missing from every sample about a quarter of the time: game 331 (…2697462543) turn 14, Farigiraf 83/225 vs a
    2% Incineroar that moves first, true value ~95.8% (loses only to a crit Throat Chop), evaluated 0.9994, then 0.968 / 0.937 / 0.999 on
    reruns. The same noise can push a ~4% crit-only out under the 2% forfeit line. Ideas: more seeds when one outcome decides the game,
    or exact crit / miss odds on the final hits; check what EVAL_ADAPT already does there. After the v28 net.
15. **Revival Blessing revives nothing in the engine (the Eval bar, 2026-10-13; confirmed; ported for v29 the same evening).** Only its onTryHit (fails with no fainted
    ally) is ported: no slotCondition, no choice of a fainted Pokemon, no revive at half HP, and since it has a handler it is not
    flagged unsupported. Game 349 (Bo1 c-2697493451) turn 4: valued 1.000 with Pawmot left; after the real revive the position is 0.69.
    Reach: Pawmot only, alive in 0.6% of training positions, on 4 bot team sheets, used in 2 games. To port after the v28 net (v29):
    Showdown's slotCondition + the switch-style request to pick the fainted Pokemon, revive at maxhp / 2, instaswitch into an empty
    active slot; differential cases with Pawmot.
16. **Audit for silent gaps like Revival Blessing (2026-10-13, the user: "are there other moves like revival blessing").** (a) Moves
    Showdown special-cases in its core code (battle / battle-actions / side / pokemon / field): Revival Blessing is the only silent gap;
    Feint (a message), Trick / Switcheroo (Leppa staleness), Toxic's Poison sure-hit (in the engine) are fine. (b) Move data fields: the
    engine reads every gameplay field (unread: names, Z / Max data, contest type, noPPBoosts, Curse's nonGhostTarget). Healing Wish is
    complete (the replacement fully healed and cured); Lunar Dance is not in Champions. (c) Not silent but missing (flagged unsupported,
    1.52% of 18,715 evaluated real positions): Cute Charm 34, Beat Up 25, Bug Bite 24, Magician 19, Future Sight 17, Guard Split 17, Sleep
    Talk 16, Unseen Fist 15 (Urshifu through Protect), Defog 12, Poison Point 9, Grass Pelt 8, Flying Press 7, Jaw Lock 7; also Shed Tail,
    Instruct, Curse (no handlers, none in the sample). To port with Revival Blessing in v29, Unseen Fist and Flying Press first.
17. **Moves aimed at the partner are never planned (the Eval bar, 2026-10-13).** plan.rs FOE_TARGETS ("normal", "any", "adjacentFoe")
    get foe targets only; only "adjacentAlly" moves get the partner. So neither side of the search sees Charm onto a Contrary partner
    (game 348, Bo3 …2697490021, turn 6: Raichu Charm -> Mega Staraptor +2, Close Combat KOs Farigiraf, 95% -> 72%), Heal Pulse / Pollen
    Puff / Instruct / Skill Swap / Entrainment / Psych Up on the partner, Beat Up into Justified, or an absorbing partner hit on purpose.
    In the 18,782 Bo3 replays, partner-aimed uses of normal / any moves: Parting Shot 105, Charm 84, Heal Pulse 64, Psych Up 39, U-turn
    37, Instruct 33, Skill Swap 29, Entrainment 23, Beat Up 18. Plan for v29: offer the partner for those moves only where they do
    something (stat drops into Contrary / Defiant / Competitive, heals on a hurt partner, Instruct / Psych Up / Skill Swap / Entrainment,
    Beat Up into Justified, a hit the partner absorbs or that trips its Weakness Policy), so the option count barely grows; self-play.
    **The Eval bar's fuller count (partner uses / all uses, Bo3 replays):** adjacentAlly (offered): Helping Hand 5,420/5,421, Coaching
    510/510, Dragon Cheer 14/14. Normal / any moves played at the partner almost always, so the planner can only misuse them: Decorate
    56/59 (target "normal" in the data: not handled), Heal Pulse 64/66, Instruct 33/36, Entrainment 23/25, Speed Swap 17/17, After You
    17/17 -> offer the partner always (Decorate, After You, Speed Swap, Heal Pulse) or by condition (Instruct, Entrainment). Often:
    Psych Up 39/53, Beat Up 18/24, Simple Beam 13/21 (a boosted or Contrary partner), Charm 84/146, Skill Swap 29/72. Sometimes: Roar
    14/84, Fake Tears 11/90 (Competitive / Defiant / Contrary), Soak 14/285, U-turn 37/2,517, Parting Shot 105/8,887, Grassy Glide
    15/6,240 (Soak / Roar: reasons vary, lowest priority).
    **Scope (the user, 2026-10-13, through the Eval bar): the partner is offered for the moves aimed at it over 10% of the time** —
    Speed Swap, After You, Heal Pulse, Decorate, Entrainment, Instruct, Beat Up, Psych Up, Simple Beam, Charm, Skill Swap, Roar, Fake
    Tears (on 8.5% of the 7,407 Bo3 sheets, 1.5% of Pokemon); not Soak, U-turn, Parting Shot, Grassy Glide (on 64.5% of sheets: an extra
    option in most positions for a rare payoff). The conditions above may narrow the 13 further where they apply.
    **The four under 10% (the user, 2026-10-13, through the Eval bar):** Soak at the partner always (Basculegion soaking its own
    Volcarona to pure Water against Rock: 14 uses, 12 games, one archetype); Parting Shot at a Contrary partner only (Grimmsnarl into its
    Mega Staraptor, 16); U-turn and Grassy Glide at a Weak Armor or Stamina partner only (Annihilape into Armarouge 12; Rillaboom into
    Stamina Archaludon 7 + 5); not Incineroar's Parting Shot at the partner to make sure of the switch (85 uses, but Incineroar is on
    most teams: an option nearly everywhere).
18. **Selective two-turn search (the user, 2026-10-13: "could a pruned model seeing more moves ahead outperform our current model";
    queued after v29).** On 333 real positions (games with a 1450+ player): a slot has a median 8 options (90th pct 12) and 95% of its
    equilibrium mix sits in 3 (4); a side has a median 55 joint options (106) and 95% of the mix in 5 (9); the human's actual move is in
    the search's top 4 by value 85% of the time, top 6 95%, top 8 99%. Plan: (1) a prototype behind an env flag: the one-turn search
    as now at the root, the top ~6-8 joint options per side (~95% of the mix) expanded a turn deeper (a few luck samples a cell, a
    pruned one-turn search at each child, ~4 options a slot, the net at the leaves), unexpanded cells keep their one-turn values;
    est. 4-10x today's cost. (2) Scored on held-out real positions (log loss against results, as for the net) and in self-play against
    the one-turn search, with the time per decision. (3) If it wins, its values become the net's training targets (offline, an AWS
    box), so the climb and the bot get the depth at today's speed: the one-turn distillation was the largest self-play gain so far.
    Caution: earlier depth-like changes (anticipation passes, the full switch matrix) were flat; the equilibrium opponent caps it.
    **Done for v29 (2026-10-13 evening):** Revival Blessing ported (sim.rs: a side that cannot switch keeps the request for a slot with the
    condition, no BeforeSwitchOut for it, the choice names a fainted Pokemon, an order-6 RevivalBlessing action revives it at half HP and
    instaswitches it into an empty active slot; spot.rs switch_opts offers the fainted for such a slot) and the case generator taught to
    answer it (gen_battle_cases.js). 150 battles between the 80 real sheets with Revival Blessing (1,963 turn cases): v28 37% exact on
    the 96 Revival Blessing cases -> 100%; all turns 96.8% -> 100% of supported in lo / hi / real. Found on the way: hidden disables
    (Imprison) shown as usable in the last active slot's request (getMoves' restrictData), as Showdown does; an Imprison mirror read as
    Struggle. 200 random real-team battles (2,674 cases): 99.9% -> 100%.
    **Reshaped as an anytime search (the user, through the Eval bar, 2026-10-13):** one loop under a budget instead of a fixed
    two-turn expansion: score every cell cheaply (few rolls, the net at the next turn), solve, then refine the cell with the highest
    row weight x column weight x remaining uncertainty, either by more rolls (a cell one roll decides: item 14's lone crit) or by one more
    turn as a smaller sub-table on the same loop with a share of the budget; re-solve and repeat; every cell keeps a small floor of
    attention (the mixes move as cells sharpen). Roughly simultaneous-move MCTS with the net at the leaves; back-row hypotheses could
    share the budget by weight (if the user ever wants them). Budgets: ~1 min a position for net training, 15 s for the bot, 5 s for team
    search; counted in search steps (leaf evaluations), not seconds, except the bot, which converts its 15 s at startup (this Mac is
    shared). Each budget needs its own CAL. Engine asks from the Eval bar: an evalpos budget (steps and time), deterministic results for
    a given seed (resuming saved search state only if cheap), and a per-position uncertainty (from the cells' sample variances through
    the solved mixes). Today's EVAL_ADAPT staging is the special case "refine by rolls, top options only". Order: after v29; first cut
    = refine by rolls with the priority rule + value_se output (no depth), then depth for the top cells; the Eval bar scores budgets
    1 / 5 / 15 / 60 s on the 461 bot games and the replays to see where the gain flattens.
