#!/bin/bash
# Self-play data for a 4v4 position value (2026-10-03): every lead pair of the current six (jobs_inc1.json: 15 leads x 10 archetypes x 6
# opposing leads, default back rows) as full battles, 8 games each, logging the features at the start of every turn; then the
# logistic fit (eg_fitvalue.py) -> egvalue4_raw.json. Usage: ./battle_train.sh <value json to play with> <outdir> <fit out>
cd "$(dirname "$0")"; set -e
VAL=${1:-egvalue2.json}; OUT=${2:-results/battle_train}; FIT=${3:-egvalue4_raw.json}
MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_inc1.json battle_train_starts.jsonl 8 > /dev/null
echo "$(date +%H:%M:%S) jobs_inc1.json -> $OUT, 8 games, $(cat cand_workers) threads (full battles, self-play)" > battle_train.log
BATTLE_FEATS=1 EG_VALUE=$VAL GRID_DIR=../mxtr nice -n 10 ../native/champ/target_spot/release/champ battle ../native/engine_data_spot.json \
  battle_train_starts.jsonl $OUT $(cat cand_workers) 2> battle_train.err
echo "$(date +%H:%M:%S) done: $(ls $OUT | wc -l | tr -d ' ') result files in $OUT" >> battle_train.log
../.venv/bin/python3 eg_fitvalue.py $OUT $FIT >> battle_train.log 2>&1
echo "$(date +%H:%M:%S) TRAIN DONE" >> battle_train.log
