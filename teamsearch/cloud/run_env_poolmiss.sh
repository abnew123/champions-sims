# Pool-based climb (poolmiss): opponents are real pool entries, brings per core group (poolmode.py; user, 2026-10-06), the user's side misses twice as often (MISS_DOUBLE=0).
# champ-battle-v20, egvalue9, race with averaged Speed ties, two-turn Protect check, anticipation; Perish is played, not stocked.
# Its own state, log, progress, cache, round log and tmux session, so the two pool climbs can share one box.
#   RUN_ENV=cloud/run_env_poolmiss.sh cloud/relaunch.sh <P> <T>        RUN_ENV=cloud/run_env_poolmiss.sh setsid nohup cloud/auto_rounds.sh <cap> &
export TS_SIM=v20m TS_OPP=pool TS_STATE=climb_poolmiss_state.json TS_LOG=climb_poolmiss_log.jsonl TS_PROGRESS=climb_poolmiss_progress.json
export TS_CACHE_DIR=cache_poolmiss CLIMB_SESSION=climb_poolmiss CLIMB_LOG=round_poolmiss.log
unset TS_PERISH TS_BATTLE_BIN
mkdir -p cache_poolmiss
# Plan-aware bring step (user, 2026-10-08; bringplan.py): validated on 30 teams at +1.0 on average, +4.0 on Rain teams, none worse
# beyond noise. The bring search plays ~728 games per team instead of 168, so a round's screening takes ~4.3x as long.
export TS_BRING_MODE=plan
