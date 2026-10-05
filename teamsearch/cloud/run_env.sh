# The climb rerun's sim setup (Battle sim's final setup, 2026-10-05, amended the same day): egvalue9 (general intercept), race with
# Speed ties averaged (RACE_TIES=avg), two-turn Protect check, anticipation; Perish trap scored from real regional data.
# Round 1 started on champ-battle-v13 (outputs tagged v13g). v16 plays exactly v13's games ~3x faster (checked: Battle sim's
# 6,900 positions + 120 battles, and 54/54 against cloud/reference_v13g.json on the box), so round 1 finishes on the v16 binary
# under the v13g tag (TS_BATTLE_BIN overrides the binary only; the cache stays valid), and from round 2 (once round 1 has
# committed climb_state.json) the climb runs as v16g. Sourced from teamsearch/ by relaunch.sh, auto_rounds.sh and by hand.
if [ -f climb_state.json ]; then
  export TS_SIM=v16g; unset TS_BATTLE_BIN
else
  export TS_SIM=v13g TS_BATTLE_BIN="$(cd .. && pwd)/native/champ/bin/champ-battle-v16"
fi
export TS_PERISH=real
