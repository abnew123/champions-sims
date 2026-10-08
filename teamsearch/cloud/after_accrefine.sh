#!/bin/bash
# On the box: once the accuracy refinement has finished, probe the exact type-preserving pair swaps on the climb's final teams
# (pairprobe.py). Log: round_pairprobe.log; results runs/pairprobe_exact_swap.json (pull_loop copies both).
cd ~/champions-sims/teamsearch
until grep -q "accuracy refinement done" round_accrefine.log 2>/dev/null; do sleep 60; done
. cloud/run_env_arch.sh
read P T PF < cloud/threads_climb_arch.txt 2>/dev/null || { P=30; T=3; }
TS_PARALLEL=$P TS_THREADS=$T ../.venv/bin/python3 pairprobe.py 4 > round_pairprobe.log 2>&1
echo "$(date -u +%H:%M) UTC: pair probe done" >> round_pairprobe.log
