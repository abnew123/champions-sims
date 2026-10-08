# Per-archetype climb (user, 2026-10-08): a strong team per style instead of one global best. Starts: teams/arch_start/index.json
# (build_arch_starts.py: Rain, Rain + Sun, Balance, Sand, Tailwind; each archetype's regional top-16 teams and next best placements,
# plus the user's low-variance six). Every accepted swap keeps the start's archetype (TS_ARCH_LOCK, pssim/pro_replays.arch).
# Opponents: real pool entries weighted half by regional share, half by ladder share (TS_POOL_WEIGHT=blend). Normal accuracy (v20g),
# the plan-aware bring step, the hold batch (default). Its own state, log, progress, cache, round log and tmux session.
#   RUN_ENV=cloud/run_env_arch.sh cloud/relaunch.sh <P> <T>        RUN_ENV=cloud/run_env_arch.sh setsid nohup cloud/auto_rounds.sh <cap> 900 &
export TS_SIM=v20g TS_OPP=pool TS_POOL_WEIGHT=blend TS_ARCH_LOCK=1 TS_BRING_MODE=plan TS_INDEX=teams/arch_start/index.json
export TS_STATE=climb_arch_state.json TS_LOG=climb_arch_log.jsonl TS_PROGRESS=climb_arch_progress.json
export TS_CACHE_DIR=cache_arch CLIMB_SESSION=climb_arch CLIMB_LOG=round_arch.log
unset TS_PERISH TS_BATTLE_BIN
mkdir -p cache_arch
