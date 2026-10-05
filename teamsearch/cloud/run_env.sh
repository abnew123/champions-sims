# The climb rerun's sim setup (Battle sim's final setup, 2026-10-05, amended the same day): egvalue9 (general intercept), race with
# Speed ties averaged (RACE_TIES=avg), two-turn Protect check, anticipation; Perish trap scored from real regional data.
# Round 1 started on champ-battle-v13 (evaluate.SIMS['v13g']); v14 plays exactly v13's games ~25-39% faster, so from round 2
# (once round 1 has committed climb_state.json) the climb uses v14g. Keyed on the state file, so a mid-round relaunch keeps the
# round's setup and reuses its finished battles. Sourced from teamsearch/ by relaunch.sh, auto_rounds.sh and by hand.
if [ -f climb_state.json ]; then export TS_SIM=v14g; else export TS_SIM=v13g; fi
export TS_PERISH=real
unset TS_BATTLE_BIN
