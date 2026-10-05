#!/bin/bash
# egvalue6 behaviour test (2026-10-04): the double-Protect test's games (jobs_dp_test.json, 16 games from index 4000) played with
# EG_VALUE=egvalue6.json (champ-battle-v5, nothing banned), to compare with results/dp_test_base (egvalue5). 5 threads.
cd "$(dirname "$0")"; : > ev6_test.log
echo "$(date +%H:%M:%S) jobs_dp_test.json -> results/ev6_test, 16 games, 5 threads (full battles)" >> ev6_test.log
MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_dp_test.json ev6_test_starts.jsonl 16 4000 >> ev6_test.log
BATTLE_TURNS=1 BATTLE_ANTICIPATE=1 EG_VALUE=egvalue6.json GRID_DIR=../mxtr_t22 nice -n 10 ../native/champ/bin/champ-battle-v5 battle \
  ../native/engine_data_spot.json ev6_test_starts.jsonl results/ev6_test 5 2>> ev6_test.err
rm -f ev6_test_starts.jsonl; echo "$(date +%H:%M:%S) ALL DONE $(ls results/ev6_test | wc -l)" >> ev6_test.log
