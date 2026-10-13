# The v26 climb (user, 2026-10-12): another climb on the improved bot. Starts: the top 8 of every regional in
# regionals/regional_teams.json (Baltimore, Brisbane, Frankfurt, Louisville, Recife: 40 teams, teams/top8_start/index.json from
# build_arch_starts.py), each locked to its archetype. Battle sim's frozen setup v26 (evaluate.SIMS: the Oct 12 engine, the full
# damage-calc data, Mega choice free, the h64 value net; v26s = without the net). Opponents: real pool entries weighted half by
# regional share (pool_keys_2026-10-12.json: all five regionals) and half by ladder share. Plan-aware brings, hold batch, normal accuracy.
#   RUN_ENV=cloud/run_env_v26.sh cloud/relaunch.sh <P> <T>        RUN_ENV=cloud/run_env_v26.sh setsid nohup cloud/auto_rounds.sh <cap> 900 &
export TS_SIM=${TS_SIM:-v26} TS_OPP=pool TS_POOL_WEIGHT=blend TS_POOL_KEYS=pool_keys_2026-10-12.json TS_ARCH_LOCK=1 TS_BRING_MODE=plan
export TS_INDEX=teams/top8_start/index.json
export TS_STATE=climb_v26_state.json TS_LOG=climb_v26_log.jsonl TS_PROGRESS=climb_v26_progress.json
export TS_CACHE_DIR=cache_v26 CLIMB_SESSION=climb_v26 CLIMB_LOG=round_v26.log
unset TS_PERISH TS_BATTLE_BIN
mkdir -p cache_v26
