# Sanity-check climb (user, 2026-10-16: "take random low elo showdown teams to make sure we aren't just too harsh on our swap
# criteria"): 20 random teams rated under 1150 from the real-game pool (teams/lowelo_start, build_lowelo_starts.py). The same acceptance
# rule as the v33 climb (TS_SEQ z 2 + the hold batch), the same screening breadth ("thorough"), archetype lock and field; faster and
# less accurate: one seed per cell (v33n1 on the v34 binary) and the default bring search (top 3 by the bring model, 2 games each)
# instead of the plan-aware one. Its own state, log, cache and session.
#   RUN_ENV=cloud/run_env_lowelo.sh cloud/relaunch.sh <P> <T>     RUN_ENV=cloud/run_env_lowelo.sh setsid nohup cloud/auto_rounds.sh <cap> 600 &
export TS_SIM=${TS_SIM:-v33n1} TS_OPP=pool TS_POOL_WEIGHT=blend TS_POOL_KEYS=pool_keys_2026-10-12.json TS_ARCH_LOCK=1
unset TS_BRING_MODE TS_PERISH
export TS_BATTLE_BIN=$HOME/champions-sims/native/champ/bin/champ-battle-v34
export TS_INDEX=teams/lowelo_start/index.json
export TS_STATE=climb_lowelo_state.json TS_LOG=climb_lowelo_log.jsonl TS_PROGRESS=climb_lowelo_progress.json
export TS_CACHE_DIR=cache_lowelo CLIMB_SESSION=climb_lowelo CLIMB_LOG=round_lowelo.log TS_GAME_CACHE=cache_lowelo/games.sqlite
mkdir -p cache_lowelo
