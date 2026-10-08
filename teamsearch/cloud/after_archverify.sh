#!/bin/bash
# On the box: once archverify.py has finished, run the accuracy refinement (accrefine.py) on each archetype's best 2 distinct teams.
# Log: round_accrefine.log; results runs/accrefine.json (pull_loop copies both).
cd ~/champions-sims/teamsearch
until grep -q "verification done" round_archverify.log 2>/dev/null; do sleep 60; done
. cloud/run_env_arch.sh
read P T PF < cloud/threads_climb_arch.txt 2>/dev/null || { P=30; T=3; }
NPROC=32 ../.venv/bin/python3 accrefine.py cells > round_accrefine.log 2>&1
TS_PARALLEL=$P TS_THREADS=$T ../.venv/bin/python3 accrefine.py run 4 >> round_accrefine.log 2>&1
echo "$(date -u +%H:%M) UTC: accuracy refinement done" >> round_accrefine.log
