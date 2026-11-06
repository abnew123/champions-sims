#!/bin/bash
# M-B to M-C self-play backtest on the Mac, 3 cores (the user, 2026-11-06: "go ahead with the M-B to M-C backtest"): the builder
# (backtest/build_mb.py, after backtest/fetch_mb.py), one-on-one cells for its new sets, backtest/selfplay.py run, then compare.py.
# Every process runs as teamsearch-<program>; progress cards from backtest/selfplay.log and the climbs' round_bt.log. A relaunch resumes
# (sp_state.json, the game cache). Stops at the first failure, logged.
#   usage, from the repo root: nohup teamsearch/bin/teamsearch-bash teamsearch/cloud/mac_backtest.sh &
cd "$(dirname "$0")/.."
export TS_PARALLEL=1 TS_THREADS=3 TS_PREFILTER_PROCS=3 NPROC=3
export PYTHONPATH="$(../.venv/bin/python3 -c 'import site; print(site.getsitepackages()[0])'):$PWD"
export TS_PROC_EXE=$PWD/bin/teamsearch-py TS_MOVESET=$PWD/backtest/smogon_mb_2026-08_moveset.txt
PY=$PWD/bin/teamsearch-py; LOG=backtest/selfplay.log
fail() { echo "$(date -u '+%m-%d %H:%M UTC'): $1 failed (exit $2)" >> $LOG; exit $2; }
if [ ! -f backtest/sp_state.json ]; then
  echo "$(date '+%I:%M %p') v41n1: building the M-B field, catalog and blind sets" >> $LOG
  nice -n 10 $PY backtest/build_mb.py >> $LOG 2>&1 || fail build $?
fi
ids=(); while IFS= read -r l; do [ -n "$l" ] && ids+=("$l"); done < cells_mb.txt
if [ ${#ids[@]} -gt 0 ]; then
  echo "$(date '+%I:%M %p') v41n1: one-on-one cells for ${#ids[@]} sets" >> $LOG
  for t in 0 1; do (cd mx && TR=$t NPROC=3 nice -n 10 $PY grid_pool.py "${ids[@]}" >> ../round_cells.log 2>&1) || fail cells $?; done
  : > cells_mb.txt
fi
nice -n 10 $PY backtest/selfplay.py run >> $LOG 2>&1 || fail self-play $?
nice -n 10 $PY backtest/compare.py > backtest/compare.txt 2>&1 || fail compare $?
