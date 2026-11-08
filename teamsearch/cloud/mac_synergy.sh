#!/bin/bash
# The synergy check on the current engine, on the Mac (the user, 2026-11-08, before any box scores generated sixes): synergycheck.py
# with TS_SYN_ONE=1 (one plan break and one control swap per team), the climb's bring search, v43n1, 2 confirm batches. Log
# round_synergy_v43.log (progress card); games cached in cache_syn/games.sqlite, so a relaunch with other thread counts resumes.
#   usage, from the repo root: nohup teamsearch/bin/teamsearch-bash teamsearch/cloud/mac_synergy.sh [parallel=1] [threads=2] &
cd "$(dirname "$0")/.."
export TS_SIM=v43n1 TS_SYN_ONE=1 TS_SYN_BRINGS=search TS_PARALLEL=${1:-1} TS_THREADS=${2:-2} TS_GAME_CACHE=$PWD/cache_syn/games.sqlite
export PYTHONPATH="$(../.venv/bin/python3 -c 'import site; print(site.getsitepackages()[0])'):$PWD" TS_PROC_EXE=$PWD/bin/teamsearch-py
mkdir -p cache_syn runs
nice -n 10 bin/teamsearch-py synergycheck.py run 2 >> round_synergy_v43.log 2>&1 \
  && echo "$(date '+%I:%M %p') synergy check done" >> round_synergy_v43.log \
  || echo "$(date -u '+%m-%d %H:%M UTC'): synergy check failed (exit $?)" >> round_synergy_v43.log
