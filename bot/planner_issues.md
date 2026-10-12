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
   per replacement** on average. Fix for the bot: score the candidates with evalpos (a few seconds); for self-play, the replacement
   matrix game on one-turn values instead of static ones (costlier; measure it).
8. **Audit of every turn decision (2026-10-12, `bot/decision_audit.py`, 995 decisions rebuilt with today's builder).** Where the played
   option is known (667), the staged solve flags 73 as 5+ points below the best, but the staged solve gives options outside the mix
   only 2-8 simulations per cell, so the best of many such options reads high (a 62% double switch next to a 50% equilibrium). Solved
   again with every cell at 32 seeds and the game solved exactly (`exact`), and leaving out 3 turns where Rage Powder pulled the bot's
   move (the log shows where a move landed, not where it was aimed): 24 decisions 5+ points worse, 9 by 10+, about 0.4 points per
   decision. Every one had 0% weight in today's mix; most had weight under the earlier builder (beliefs about spreads, the bot's own
   spreads guessed before fb4780f), and the live pipeline reproduces today: the bot's logged weights and values since its 03:33 UTC
   restart match the rebuild within 1-3 points of value. Engine and Showdown move orders agree on all 1,896 active slots checked.
   Forfeits (`bot/forfeit_check.py`, 45 of 46 rebuilt, each played out 40 times by self-play): 0.3% won on average, at most 7.5%.
