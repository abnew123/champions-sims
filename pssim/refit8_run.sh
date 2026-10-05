#!/bin/bash
# Self-play for egvalue8 (2026-10-05): every lead pair of the six vs every archetype's 6 leads (jobs_inc1.json, default back rows),
# 4 games each (first game index 7000), with the sets the user settled on (Torkoal back to 32 HP / 2 SpD: myteam_real_tork32.json =
# sheets/trick-room-six/team.json) and the sheet kit's generic one-on-one grid (../sheets/trick-room-six/work/grid). Planner as in the
# candidate setup: champ-battle-v8, DP2=1 RACE=1, played with egvalue7; features and per-turn states logged.
# Threads: $1 (default 5). Then: ../.venv/bin/python3 build_egvalue8.py
cd "$(dirname "$0")"; T=${1:-5}; : > refit8.log
echo "$(date +%H:%M:%S) jobs_inc1.json -> results/refit8, 4 games, $T threads (full battles, self-play for egvalue8)" >> refit8.log
MYTEAM=myteam_real_tork32.json node ../native/battle_starts.js jobs_inc1.json refit8_starts.jsonl 4 7000 >> refit8.log
DP2=1 RACE=1 CALC_DATA=../native/champions_data.json BATTLE_FEATS=1 BATTLE_TURNS=1 BATTLE_ANTICIPATE=1 EG_VALUE=egvalue7.json \
  GRID_DIR=../sheets/trick-room-six/work/grid nice -n 10 ../native/champ/bin/champ-battle-v8 battle ../native/engine_data_spot.json \
  refit8_starts.jsonl results/refit8 $T 2>> refit8.err
rm -f refit8_starts.jsonl; echo "$(date +%H:%M:%S) ALL DONE $(ls results/refit8 | wc -l)" >> refit8.log
