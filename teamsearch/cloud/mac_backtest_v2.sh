#!/bin/bash
# M-B to M-C self-play backtest v2 on the Mac, 4 cores (the user, 2026-11-07: "fix the set generator and try the second version"):
# backtest/build_mb.py with BLIND=2 (ability-aware blind sets -> mb_swap_pool_v2.json; the M-B pool and field as v1), one-on-one cells
# for its new sets, backtest/selfplay.py run with SP_VER=2 (outputs in backtest/v2/), then compare.py (v1 and v2 side by side).
# Every process runs as teamsearch-<program>; progress cards from backtest/v2/selfplay.log and the climbs' round_bt2.log. A relaunch
# resumes (backtest/v2/sp_state.json, the game cache). "prep" stops after the cells. Stops at the first failure, logged.
#   usage, from the repo root: nohup teamsearch/bin/teamsearch-bash teamsearch/cloud/mac_backtest_v2.sh [prep] &
cd "$(dirname "$0")/.."
export TS_PARALLEL=1 TS_THREADS=4 TS_PREFILTER_PROCS=4 NPROC=4
export PYTHONPATH="$(../.venv/bin/python3 -c 'import site; print(site.getsitepackages()[0])'):$PWD"
export TS_PROC_EXE=$PWD/bin/teamsearch-py TS_MOVESET=$PWD/backtest/smogon_mb_2026-08_moveset.txt
PY=$PWD/bin/teamsearch-py; mkdir -p backtest/v2; LOG=backtest/v2/selfplay.log
fail() { echo "$(date -u '+%m-%d %H:%M UTC'): $1 failed (exit $2)" >> $LOG; exit $2; }
if [ ! -f backtest/mb_swap_pool_v2.json ]; then
  echo "$(date '+%I:%M %p') v41n1 v2: building the v2 blind sets (ability-aware)" >> $LOG
  BLIND=2 nice -n 10 $PY backtest/build_mb.py >> $LOG 2>&1 || fail build $?
fi
ids=(); while IFS= read -r l; do [ -n "$l" ] && ids+=("$l"); done < cells_mb.txt
if [ ${#ids[@]} -gt 0 ]; then
  echo "$(date '+%I:%M %p') v41n1 v2: one-on-one cells for ${#ids[@]} sets" >> $LOG
  for t in 0 1; do (cd mx && TR=$t NPROC=4 nice -n 10 $PY grid_pool.py "${ids[@]}" >> ../round_cells.log 2>&1) || fail cells $?; done
  : > cells_mb.txt
fi
[ "$1" = prep ] && exit 0
SP_VER=2 nice -n 10 $PY backtest/selfplay.py run >> $LOG 2>&1 || fail self-play $?
nice -n 10 $PY backtest/compare.py > backtest/compare.txt 2>&1 || fail compare $?
