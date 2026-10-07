#!/bin/bash
# On the box: the synergy check both ways (user, 2026-10-07): a plumbing test, then human-typical brings, then the climb's bring
# search. Logs: round_synergy_test.log, round_synergy_human.log, round_synergy_search.log (pull_loop copies round*.log and runs/).
# usage (from ~/champions-sims/teamsearch): cloud/synergy_run.sh [parallel=30] [threads=3] [batches=4]
cd "$(dirname "$0")/.."
P=${1:-30}; T=${2:-3}; B=${3:-4}; PY=../.venv/bin/python3
export TS_SIM=v20g TS_PARALLEL=$P TS_THREADS=$T
TS_SYN_TEST=1 TS_SYN_BRINGS=human $PY synergycheck.py run > round_synergy_test.log 2>&1 || { echo "test failed" >> round_synergy_test.log; exit 1; }
for m in human search; do TS_SYN_BRINGS=$m $PY synergycheck.py run $B > round_synergy_$m.log 2>&1; done
echo "$(date -u +%H:%M) UTC: synergy check done" >> round_synergy_search.log
