#!/bin/bash
# The Reg M-C regionals through the sim on the Mac (the user, 2026-11-25: "lets do it locally"): regsim.py sets, every real match
# between known teams, then the report. Waits for
# regionals/fetch_field.py to finish and for AC power before the heavy steps. Game cache cache_reg/: a relaunch resumes.
# usage: teamsearch/bin/teamsearch-bash teamsearch/cloud/mac_regsim.sh [threads=4]
cd "$(dirname "$0")/.."
export TS_SIM=v43n1 TS_THREADS=${1:-4} TS_GAME_CACHE=$PWD/cache_reg/games.sqlite
export PYTHONPATH="$(../.venv/bin/python3 -c 'import site; print(site.getsitepackages()[0])'):$PWD" TS_PROC_EXE=$PWD/bin/teamsearch-py
PY=$PWD/bin/teamsearch-py; mkdir -p cache_reg regsim; LOG=regsim/regsim.log
fail() { echo "$(date -u '+%m-%d %H:%M UTC'): regional sims $1 failed (exit $2)" >> $LOG; exit $2; }
bin/teamsearch-caffeinate -i -w $$ &
grep -q "fetch done" ../regionals/fetch_field.log 2>/dev/null || echo "$(date '+%I:%M %p') paused: waiting for the team sheet fetch" >> $LOG
until grep -q "fetch done" ../regionals/fetch_field.log 2>/dev/null; do
  pgrep -f fetch_field.py >/dev/null || fail "team sheet fetch" 1; sleep 60; done
if ! pmset -g batt | grep -q "AC Power"; then
  echo "$(date '+%I:%M %p') paused: waiting for AC power" >> $LOG
  until pmset -g batt | grep -q "AC Power"; do sleep 60; done
fi
echo "$(date '+%I:%M %p') v43n1: building the field's sets" >> $LOG
[ -s regsim/teams.json ] || nice -n 10 $PY regsim.py sets >> $LOG 2>&1 || fail sets $?
# no cells step: regsim.Brings stands a species' standard set in for a set without cells (3,800 new sets would take ~8 h)
nice -n 10 $PY regsim.py play >> $LOG 2>&1 || fail play $?
nice -n 10 $PY regsim.py report > regsim/report.out 2>&1 || fail report $?
