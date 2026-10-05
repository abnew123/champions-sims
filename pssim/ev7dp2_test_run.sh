#!/bin/bash
# egvalue7 + two-turn Protect check (DP2=1, champ-battle-v8) behaviour test (2026-10-04): the double-Protect test's games (jobs_dp_test.json, 16 games from index 4000) with
# champ-battle-v8 (v7 + DP2), RACE=1, EG_VALUE=egvalue7.json. Compare with results/dp_test_base (egvalue5) and
# results/ev6b_test (egvalue6b) using value_behaviour.py. 5 threads.
cd "$(dirname "$0")"; : > ev7dp2_test.log
echo "$(date +%H:%M:%S) jobs_dp_test.json -> results/ev7dp2_test, 16 games, 5 threads (full battles)" >> ev7dp2_test.log
MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_dp_test.json ev7dp2_test_starts.jsonl 16 4000 >> ev7dp2_test.log
DP2=1 RACE=1 CALC_DATA=../native/champions_data.json BATTLE_TURNS=1 BATTLE_ANTICIPATE=1 EG_VALUE=egvalue7.json GRID_DIR=../mxtr_t22 nice -n 10 \
  ../native/champ/bin/champ-battle-v8 battle ../native/engine_data_spot.json ev7dp2_test_starts.jsonl results/ev7dp2_test 5 2>> ev7dp2_test.err
rm -f ev7dp2_test_starts.jsonl; echo "$(date +%H:%M:%S) ALL DONE $(ls results/ev7dp2_test | wc -l)" >> ev7dp2_test.log
