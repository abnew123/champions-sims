# The climb rerun's sim setup (Battle sim's final setup, 2026-10-05, amended the same day): champ-battle-v13 + egvalue9 (general
# intercept), race with Speed ties averaged (RACE_TIES=avg), two-turn Protect check, anticipation (evaluate.SIMS['v13g']);
# Perish trap scored from real regional data (perish_stock.py).
# Sourced by relaunch.sh and auto_rounds.sh; source it by hand before climb.py / evaluate.py on the box.
export TS_SIM=v13g TS_PERISH=real
unset TS_BATTLE_BIN
