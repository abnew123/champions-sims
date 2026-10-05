#!/bin/bash
# Overnight, part 2 (2026-10-03): the sheet's plans at 32 games per opposing lead with champ-battle-v2:
#   b32_v4a = 4v4 value (egvalue4) + anticipated switches;  b32_v4 = egvalue4, one layer;  b32_v2 = old 2v2 value, one layer (baseline)
# then a second self-play round (egvalue4 + anticipation) -> egvalue5, and b32_v5a. Threads from cand_workers.
cd "$(dirname "$0")"; set -e
until grep -q "NIGHT DONE" battle_train.log 2>/dev/null; do sleep 20; done
T=$(cat cand_workers); BIN=../native/champ/bin/champ-battle-v2; ED=../native/engine_data_spot.json
MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_battle_sheet.json battle_sheet32_starts.jsonl 32 > /dev/null
run() { local name=$1 starts=$2 jobs=$3 val=$4; shift 4
  echo "$(date +%H:%M:%S) $jobs -> results/$name, $(sed -n 1p $starts > /dev/null; echo 32) games, $T threads (full battles)" > $name.log
  env "$@" BATTLE_LOG=1 EG_VALUE=$val GRID_DIR=../mxtr nice -n 10 $BIN battle $ED $starts results/$name $T 2> $name.err
  echo "$(date +%H:%M:%S) done: $(ls results/$name | wc -l | tr -d ' ') result files in results/$name" >> $name.log; }
run b32_v4a battle_sheet32_starts.jsonl jobs_battle_sheet.json egvalue4.json BATTLE_ANTICIPATE=1
run b32_v4 battle_sheet32_starts.jsonl jobs_battle_sheet.json egvalue4.json X=1
run b32_v2 battle_sheet32_starts.jsonl jobs_battle_sheet.json egvalue2.json X=1
# second self-play round, played with the refitted value and anticipation
echo "$(date +%H:%M:%S) jobs_inc1.json -> results/battle_train2, 8 games, $T threads (full battles, self-play 2)" > battle_train2.log
BATTLE_ANTICIPATE=1 BATTLE_FEATS=1 EG_VALUE=egvalue4.json GRID_DIR=../mxtr nice -n 10 $BIN battle $ED battle_train_starts.jsonl results/battle_train2 $T 2> battle_train2.err
echo "$(date +%H:%M:%S) done: $(ls results/battle_train2 | wc -l | tr -d ' ') result files in results/battle_train2" >> battle_train2.log
../.venv/bin/python3 eg_fitvalue.py results/battle_train2 egvalue5_raw.json >> battle_train2.log 2>&1
python3 - <<'PY'
import json
a = json.load(open('egvalue4.json')); b = json.load(open('egvalue5_raw.json')); w = list(b['w']); names = a['names']
for n, v in a['hand_set'].items(): w[names.index(n)] = v
json.dump({'b0': b['b0'], 'w': w, 'names': names, 'n': b['n'], 'hand_set': a['hand_set'],
           'note': 'Second self-play round: fitted on results/battle_train2 (7,200 battles played with egvalue4 + anticipated switches); hand_set as egvalue4.'},
          open('egvalue5.json', 'w'), indent=1)
PY
run b32_v5a battle_sheet32_starts.jsonl jobs_battle_sheet.json egvalue5.json BATTLE_ANTICIPATE=1
echo "$(date +%H:%M:%S) NIGHT2 DONE" >> battle_train2.log
