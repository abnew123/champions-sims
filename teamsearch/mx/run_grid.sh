#!/bin/bash
# One-on-one cells for the start teams + swap pool. Waits until the other thread's sims have been idle for 2 minutes
# (they share the CPU budget), then runs no-Trick-Room then Trick Room with NPROC workers (default 3), low priority.
# Resumes: finished sets are skipped. Log: run_grid.log
cd "$(dirname "$0")"
PY=../../.venv/bin/python3
caffeinate -i -w $$ &
busy() { pgrep -f "run_jobs|champ plan|champ spot|champ battle|champ-battle|battle_night|battle_train|battle_starts|cand_run|rilla2_run|eg_run|final_run|t1sim|sp_run|blast_run" >/dev/null; }
quiet=0
[ -n "$NOWAIT" ] && quiet=2                     # NOWAIT=1: start now (at nice 15, below the other thread's runs)
while [ $quiet -lt 2 ]; do if busy; then quiet=0; else quiet=$((quiet+1)); fi; sleep 60; done
echo "$(date '+%I:%M %p') other runs idle, starting the grid with ${NPROC:-3} workers"
TR=0 NPROC=${NPROC:-3} nice -n 15 $PY grid_pool.py || { echo "GRID FAILED (notr)"; exit 1; }
TR=1 NPROC=${NPROC:-3} nice -n 15 $PY grid_pool.py || { echo "GRID FAILED (tr)"; exit 1; }
$PY merge.py --all
echo "$(date '+%I:%M %p') GRID ALL DONE"
