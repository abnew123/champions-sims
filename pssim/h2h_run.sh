#!/bin/bash
# Head-to-head tests of position values (2026-10-05, champ-battle-v12: EG_VALUE = side 0's weights, EG_VALUE_B = side 1's, DP2_SIDE).
# The sheet's fours vs all archetypes' 6 leads (jobs_dp_test.json), 8 games each (first game index 9000), settled sets, generic grid,
# RACE=1 (features computed for both; weight files without race weights ignore them). One arm per line of h2h_arms.txt:
#   <name> <side 0 value> <side 1 value> <DP2: none | 0 | 1 | both>
# A value plays better than another if it gains when given to my side and loses when given to theirs, against the same-value baseline.
# Threads: $1 (default 8). Analysis: python3 h2h_report.py
cd "$(dirname "$0")"; T=${1:-8}; : > h2h.log
MYTEAM=myteam_real_tork32.json node ../native/battle_starts.js jobs_dp_test.json h2h_starts.jsonl 8 9000 >> h2h.log
while read -r name va vb dp; do
  [ -z "$name" ] && continue
  case $dp in none) D="";; both) D="DP2=1";; *) D="DP2=1 DP2_SIDE=$dp";; esac
  echo "$(date +%H:%M:%S) jobs_dp_test.json -> results/h2h_$name, 8 games, $T threads (full battles, head to head: $va vs $vb, DP2 $dp)" >> h2h.log
  env $D RACE=1 CALC_DATA=../native/champions_data.json BATTLE_TURNS=1 BATTLE_ANTICIPATE=1 EG_VALUE=$va EG_VALUE_B=$vb GRID_DIR=../sheets/trick-room-six/work/grid nice -n 10 \
    ../native/champ/bin/champ-battle-v12 battle ../native/engine_data_spot.json h2h_starts.jsonl results/h2h_$name $T 2>> h2h_$name.err
  echo "$(date +%H:%M:%S) done: $(ls results/h2h_$name | wc -l | tr -d ' ') result files in results/h2h_$name" >> h2h.log
done < h2h_arms.txt
rm -f h2h_starts.jsonl; echo "$(date +%H:%M:%S) ALL DONE" >> h2h.log
