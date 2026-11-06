#!/bin/bash
# Score candidate teams against TR sheet's current-meta pool on the Mac, 3 cores (the user, 2026-11-06, via TR sheet: is the Trick Room
# six still the team to play? its bot record fell from 51% to 43%). Setup v41n1 (Battle sim's screen: v33n1's flags on the v41
# binary with VNET_PERISH, VNET_PROGRESS, PERISH_DOOM and TR_HEAD); groups weighted one vote per player (the keys' share) and entries
# within a group by player (TS_POOL_BY_PLAYER). scoreteams.py: each team's own bring search (seed 86000), then 6 fresh batches.
# Progress card from round_scoreteams.log; results in runs/scoreteams_meta_<day>.json.
#   usage, from the repo root: nohup teamsearch/bin/teamsearch-bash teamsearch/cloud/mac_meta_score.sh [teams/meta_2026-11-06.json] [batches=6] &
cd "$(dirname "$0")/.."
TEAMS=${1:-teams/meta_2026-11-06.json}; B=${2:-6}; META=../sheets/trick-room-six/work/meta
export TS_SIM=v41n1 TS_OPP=pool TS_POOL=$META/pool_2026-10-13_2026-11-06.json TS_POOL_KEYS=$META/pool_keys_2026-10-13_2026-11-06.json
export TS_POOL_BY_PLAYER=1 TS_GAME_CACHE=cache_meta/games.sqlite TS_PARALLEL=1 TS_THREADS=3 TS_PREFILTER_PROCS=3 NPROC=3
unset TS_BRING_MODE TS_PERISH TS_POOL_WEIGHT TS_BATTLE_BIN
export PYTHONPATH="$(../.venv/bin/python3 -c 'import site; print(site.getsitepackages()[0])'):$PWD"
export TS_PROC_EXE=$PWD/bin/teamsearch-py                         # multiprocessing workers (the cells' grid_pool.py) keep the name
echo "$(date '+%m-%d %I:%M %p'): scoring $TEAMS, $B batches, $TS_SIM" > round_scoreteams.log
nice -n 10 bin/teamsearch-py scoreteams.py "$TEAMS" "$B" >> round_scoreteams.log 2>&1 || echo "$(date -u '+%m-%d %H:%M UTC'): scoring failed (exit $?)" >> round_scoreteams.log
