#!/bin/bash
# Protect-check decision log (2026-10-05): the sheet's fours vs all archetypes' 6 leads (jobs_dp_test.json), 3 games each (first game index
# 6000), champ-battle-v10 (= v9 + DP2_LOG) with DP2=1 DP2_LOG=1 RACE=1 and egvalue7: every check records the one- and two-turn value and the
# HP outcome of the best Protect-again / other-move / switch option. Threads: $1 (default 2). Analysis: python3 dplog_report.py
cd "$(dirname "$0")"; T=${1:-2}; : > dplog.log
echo "$(date +%H:%M:%S) jobs_dp_test.json -> results/dplog, 3 games, $T threads (full battles, Protect-check log)" >> dplog.log
MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_dp_test.json dplog_starts.jsonl 3 6000 >> dplog.log
DP2=1 DP2_LOG=1 RACE=1 CALC_DATA=../native/champions_data.json BATTLE_TURNS=1 BATTLE_ANTICIPATE=1 EG_VALUE=egvalue7.json GRID_DIR=../mxtr_t22 nice -n 10 \
  ../native/champ/bin/champ-battle-v10 battle ../native/engine_data_spot.json dplog_starts.jsonl results/dplog $T 2>> dplog.err
rm -f dplog_starts.jsonl; echo "$(date +%H:%M:%S) ALL DONE $(ls results/dplog | wc -l)" >> dplog.log
