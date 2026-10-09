#!/bin/bash
# On the box (2026-10-08 evening): the accuracy refinement's final check (accrefine.py final: each changed team against its original
# on fresh games), then the exact type-preserving pair probe (pairprobe.py). Needs runs/accrefine.json, runs/archverify.json and
# climb_arch_state.json copied from the earlier box's results. Logs: round_accfinal.log, round_pairprobe.log (pull_loop copies both).
cd ~/champions-sims/teamsearch
. cloud/run_env_arch.sh
read P T PF < cloud/threads_climb_arch.txt 2>/dev/null || { P=30; T=3; }
NPROC=32 TS_PARALLEL=$P TS_THREADS=$T ../.venv/bin/python3 accrefine.py final 4 > round_accfinal.log 2>&1
echo "$(date -u +%H:%M) UTC: final check done" >> round_accfinal.log
TS_PARALLEL=$P TS_THREADS=$T ../.venv/bin/python3 pairprobe.py 4 > round_pairprobe.log 2>&1
echo "$(date -u +%H:%M) UTC: pair probe done" >> round_pairprobe.log
