#!/bin/bash
# On the box (2026-10-08): after the pair probe, score the regional Rain teams with 24/24 sure hits and no Floette-Eternal
# (teams/sure24_rain.json, with Brisbane-4 and refined Baltimore-2 as references). Log: round_score_rain.log.
cd ~/champions-sims/teamsearch
until grep -q "pair probe done" round_pairprobe.log 2>/dev/null; do sleep 30; done
. cloud/run_env_arch.sh
read P T PF < cloud/threads_climb_arch.txt 2>/dev/null || { P=30; T=3; }
NPROC=32 TS_PARALLEL=$P TS_THREADS=$T ../.venv/bin/python3 scoreteams.py teams/sure24_rain.json 6 > round_score_rain.log 2>&1
echo "$(date -u +%H:%M) UTC: scoring done" >> round_score_rain.log
