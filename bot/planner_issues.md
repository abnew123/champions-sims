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
2. **Small weights on clearly worse options.** Fictitious play (400 rounds) leaves a few percent on options several points below the
   best (Fake Out without the Mega at 2%, 5 points worse). The user is fine with these as low-probability rolls; a cleanup would drop
   options more than a point or two below the best against the opponent's mix.
3. **Static value tails.** The position value cannot see that every single-target move is redirected (Rage Powder) or that a +6/+6
   Pokemon is out of reach; lost positions read 2-4% instead of ~0. Handled for now by the forfeit rule (real win chance under 2%).
4. **Dead turns look odd.** A Pokemon about to faint before moving spreads its weight over near-equal options (Wide Guard with no
   spread move on the other side). Invisible to opponents (an unexecuted choice never shows), so left as is.
5. **Team-side, not planner:** Frankfurt-156's Archaludon loses its Electric STAB into Lightning Rod Raichu (absorbed twice, boosting
   Raichu), which is where its Leftovers Protect chains came from.
