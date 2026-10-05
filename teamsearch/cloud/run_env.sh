# The climb rerun's sim setup (Battle sim's final setup, 2026-10-05): champ-battle-v12 + egvalue9 (general intercept), race,
# two-turn Protect check, anticipation (evaluate.SIMS['v12g']); Perish trap scored from real regional data (perish_stock.py).
# Sourced by relaunch.sh and auto_rounds.sh; source it by hand before climb.py / evaluate.py on the box.
export TS_SIM=v12g TS_PERISH=real
unset TS_BATTLE_BIN
