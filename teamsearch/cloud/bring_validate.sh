#!/bin/bash
# On the box: validate the plan-aware bring step (user, 2026-10-07): bringcheck.py (old vs plan-aware brings on the synergy check's
# 31 teams, and the TR six vs the TR sheet's plans; ~85k games), then the synergy check with plan-aware brings (~240k games).
# Logs: round_bringcheck.log, round_synergy_plan.log. usage (from ~/champions-sims/teamsearch): cloud/bring_validate.sh [parallel] [threads]
cd "$(dirname "$0")/.."
P=${1:-30}; T=${2:-3}; PY=../.venv/bin/python3
export TS_SIM=v20g TS_PARALLEL=$P TS_THREADS=$T
$PY bringcheck.py 4 > round_bringcheck.log 2>&1
TS_SYN_BRINGS=plan $PY synergycheck.py run 4 > round_synergy_plan.log 2>&1
echo "$(date -u +%H:%M) UTC: bring validation done" >> round_synergy_plan.log
