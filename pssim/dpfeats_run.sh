#!/bin/bash
# Values at every Protect decision (2026-10-05): the ev7dp2 test's games again (16 games from index 4000, champ-battle-v8, DP2=1 RACE=1,
# egvalue7: identical games) with the per-turn features logged as well (BATTLE_FEATS=1 + BATTLE_TURNS=1), so every position's win chance
# can be computed. Run in parts: ./dpfeats_run.sh <part: a|b> <threads>  (jobs_dpfeats_<part>.json = jobs_dp_test.json split 18 / 42;
# seeds depend on the opponent and game only). Analysis: python3 protect_decided.py sim results/dpfeats
cd "$(dirname "$0")"; P=$1; T=${2:-5}; : > dpfeats_$P.log
echo "$(date +%H:%M:%S) jobs_dpfeats_$P.json -> results/dpfeats_$P, 16 games, $T threads (full battles, features logged)" >> dpfeats_$P.log
MYTEAM=myteam_real.json node ../native/battle_starts.js jobs_dpfeats_$P.json dpfeats_starts_$P.jsonl 16 4000 >> dpfeats_$P.log
DP2=1 RACE=1 CALC_DATA=../native/champions_data.json BATTLE_TURNS=1 BATTLE_FEATS=1 BATTLE_ANTICIPATE=1 EG_VALUE=egvalue7.json GRID_DIR=../mxtr_t22 nice -n 10 \
  ../native/champ/bin/champ-battle-v8 battle ../native/engine_data_spot.json dpfeats_starts_$P.jsonl results/dpfeats_$P $T 2>> dpfeats_$P.err
rm -f dpfeats_starts_$P.jsonl; echo "$(date +%H:%M:%S) ALL DONE $(ls results/dpfeats_$P | wc -l)" >> dpfeats_$P.log
