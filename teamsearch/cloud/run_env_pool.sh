# Pool-based climb (pool): opponents are real pool entries, brings per core group (poolmode.py; user, 2026-10-06), no rule (the control).
# champ-battle-v20, egvalue9, race with averaged Speed ties, two-turn Protect check, anticipation; Perish is played, not stocked.
# Its own state, log, progress, cache, round log and tmux session, so the two pool climbs can share one box.
#   RUN_ENV=cloud/run_env_pool.sh cloud/relaunch.sh <P> <T>        RUN_ENV=cloud/run_env_pool.sh setsid nohup cloud/auto_rounds.sh <cap> &
export TS_SIM=v20g TS_OPP=pool TS_STATE=climb_pool_state.json TS_LOG=climb_pool_log.jsonl TS_PROGRESS=climb_pool_progress.json
export TS_CACHE_DIR=cache_pool CLIMB_SESSION=climb_pool CLIMB_LOG=round_pool.log
unset TS_PERISH TS_BATTLE_BIN
mkdir -p cache_pool
