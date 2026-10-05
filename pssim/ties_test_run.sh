#!/bin/bash
# Speed-tie averaging test (2026-10-05, champ-battle-v13): the final setup (egvalue9, RACE=1, DP2=1) on the head-to-head games
# (jobs_dp_test.json, 8 games from index 9000, settled sets, generic grid) with RACE_TIES=avg; compare with results/h2h_g9_g9
# (the same games without it): python3 h2h_report.py g9_g9 ties_avg. Threads: $1 (default 8).
cd "$(dirname "$0")"; T=${1:-8}; : > ties_test.log
echo "$(date +%H:%M:%S) jobs_dp_test.json -> results/h2h_ties_avg, 8 games, $T threads (full battles, Speed-tie averaging)" >> ties_test.log
MYTEAM=myteam_real_tork32.json node ../native/battle_starts.js jobs_dp_test.json ties_test_starts.jsonl 8 9000 >> ties_test.log
RACE_TIES=avg DP2=1 RACE=1 CALC_DATA=../native/champions_data.json BATTLE_TURNS=1 BATTLE_ANTICIPATE=1 EG_VALUE=egvalue9.json GRID_DIR=../sheets/trick-room-six/work/grid nice -n 10 \
  ../native/champ/bin/champ-battle-v13 battle ../native/engine_data_spot.json ties_test_starts.jsonl results/h2h_ties_avg $T 2>> ties_test.err
rm -f ties_test_starts.jsonl; echo "$(date +%H:%M:%S) done: $(ls results/h2h_ties_avg | wc -l | tr -d ' ') result files in results/h2h_ties_avg" >> ties_test.log
