#!/bin/bash
# Overnight battle work (2026-10-03, user away until ~10 am; 13 threads):
#  1. no-switch control of the sheet-plan battles (does mid-game switching change the results?)
#  2. self-play data (7,200 battles) + logistic refit of the position value on 4v4 games -> egvalue4_raw.json
#  3. sheet-plan battles again with the refitted value (switch rate, win rates, Trick Room)
cd "$(dirname "$0")"; set -e
T=$(cat cand_workers)
run() { local name=$1 starts=$2 val=$3; shift 3
  echo "$(date +%H:%M:%S) jobs_battle_sheet.json -> results/$name, 8 games, $T threads (full battles)" > $name.log
  env "$@" BATTLE_LOG=1 EG_VALUE=$val GRID_DIR=../mxtr nice -n 10 ../native/champ/target_spot/release/champ battle ../native/engine_data_spot.json $starts results/$name $T 2> $name.err
  echo "$(date +%H:%M:%S) done: $(ls results/$name | wc -l | tr -d ' ') result files in results/$name" >> $name.log; }
run battle_sheet_nosw battle_sheet_starts.jsonl egvalue2.json BATTLE_NOSWITCH=1
./battle_train.sh egvalue2.json results/battle_train egvalue4_raw.json
run battle_sheet_v4 battle_sheet_starts.jsonl egvalue4_raw.json X=1
echo "$(date +%H:%M:%S) NIGHT DONE" >> battle_train.log
