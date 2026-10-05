#!/bin/bash
# Self-play for egvalue7 (2026-10-04): every lead pair of the six vs every archetype's 6 leads (jobs_inc1.json, default back rows),
# 4 games each (first game index 5000), champ-battle-v6 with the damage-race features on (RACE=1) and logged (BATTLE_FEATS=1), played
# with egvalue6b (the race features unweighted). 5 threads. Then: ../.venv/bin/python3 build_egvalue7.py
cd "$(dirname "$0")"; : > race_train.log
echo "$(date +%H:%M:%S) jobs_inc1.json -> results/race_train, 4 games, 5 threads (full battles)" >> race_train.log
MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_inc1.json race_train_starts.jsonl 4 5000 >> race_train.log
RACE=1 CALC_DATA=../native/champions_data.json BATTLE_FEATS=1 BATTLE_ANTICIPATE=1 EG_VALUE=egvalue6b.json GRID_DIR=../mxtr_t22 nice -n 10 \
  ../native/champ/bin/champ-battle-v6 battle ../native/engine_data_spot.json race_train_starts.jsonl results/race_train 5 2>> race_train.err
rm -f race_train_starts.jsonl; echo "$(date +%H:%M:%S) ALL DONE $(ls results/race_train | wc -l)" >> race_train.log
