#!/bin/bash
# The sanity-check climb (cloud/run_env_lowelo.sh) in the background on the Mac (user, 2026-10-16: "a background thing on like 3
# cores. if it takes a week to finish, so be it"): one team at a time on 3 battle threads (nice 10), 3 pre-filter processes; the
# one-on-one cells first, then rounds until every start is at a local max, then the verification (archverify.py, 2 batches).
# Every process runs as teamsearch-<program> (progress page: the climb card from climb_lowelo_progress.json and round_lowelo.log).
# Stops at the first failure, logged. usage, from the repo root: nohup teamsearch/bin/teamsearch-bash teamsearch/cloud/mac_lowelo.sh &
cd "$(dirname "$0")/.."
. cloud/run_env_lowelo.sh
export TS_PARALLEL=1 TS_THREADS=3 TS_PREFILTER_PROCS=3
export PYTHONPATH="$(../.venv/bin/python3 -c 'import site; print(site.getsitepackages()[0])'):$PWD"
PY=$PWD/bin/teamsearch-py; LOG=round_lowelo.log
fail() { echo "$(date '+%m-%d %I:%M %p'): $1 failed (exit $2)" >> $LOG; exit $2; }
ids=(); while IFS= read -r l; do [ -n "$l" ] && ids+=("$l"); done < cells_lowelo.txt
if [ ${#ids[@]} -gt 0 ]; then
  echo "$(date '+%m-%d %I:%M %p'): cells for ${#ids[@]} sets" >> $LOG
  for t in 0 1; do (cd mx && TR=$t NPROC=3 nice -n 10 $PY grid_pool.py "${ids[@]}" >> ../round_cells.log 2>&1) || fail cells $?; done
fi
while true; do
  active=$($PY -c "import json; s=json.load(open('$TS_STATE')); print(sum(1 for t in s['teams'].values() if not t['done']))" 2>/dev/null || echo 20)
  if [ "$active" -eq 0 ]; then echo "$(date '+%m-%d %I:%M %p'): every start is at a local max; no more rounds" >> $LOG; break; fi
  echo "--- round, $(date '+%m-%d %I:%M %p'), $active starts" >> $LOG
  $PY climb.py round thorough climb_lowelo >> $LOG 2>&1 || fail round $?
done
[ -f runs/archverify.json ] && mv runs/archverify.json runs/archverify.json.old$(date +%Y%m%d%H%M%S)
$PY archverify.py 2 > round_archverify.log 2>&1 || { echo "verification failed (exit $?)" >> round_archverify.log; exit 1; }
cp runs/archverify.json archverify_lowelo.json && echo "$(date '+%m-%d %I:%M %p'): verification done" >> round_archverify.log
