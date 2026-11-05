#!/bin/zsh
# The Trick Room study's self-play data (2026-11-04, the user: the engine overrates Trick Room against itself too, so self-play can supply
# the data): every start in results/tr_value/starts (bot/tr_fit.py starts: the Trick Room six's turn 1, our Trick Room just up, the
# opponent's just up) played once by champ battle with the bot's settings (the h64 net with its Perish and progress terms, BATTLE_EVAL
# one-turn search at BUDGET leaves) and BATTLE_VFEATS=1: the net's inputs and static value at every turn's start, for bot/tr_value.py.
# Shows on the progress page (pssim/tr_value_data.log). Usage: T=6 ./tr_value_data.sh
emulate -R zsh   # a renamed argv[0] starting with b or s makes zsh emulate sh
cd "$(dirname $0)"
SP=$PWD/results/tr_value; T=${T:-6}; BUDGET=${BUDGET:-20000}; B=${BIN:-$SP/battlesim-champ-trdata}; ED=../native/engine_data_full.json
F=(RACE_TIES=avg RACE=1 TRSYM=1 EG_MEGA_TIE=0 GRID_DIR=$SP/grid CALC_DATA=../native/champions_data_full.json RACE_PRIO=1 FEATS22=1
   EG_VALUE=egvalue9_sym2.json EG_VNET=$PWD/../bot/value/vnet_h64_search_acc.json BATTLE_NS=1 BATTLE_EVAL=1 BATTLE_EVAL_BUDGET=$BUDGET
   VNET_PERISH=1 VNET_PROGRESS=1 PERISH_DOOM=1 BATTLE_VFEATS=1 ${=EXTRA:-})
echo "$(date +%H:%M:%S) $SP/starts.jobs.json -> $SP/out, $T threads (Trick Room study: self-play data)" > tr_value_data.log
env $F nice -n 10 $B battle $ED $SP/starts.jsonl $SP/out $T >> tr_value_data.log 2>&1
echo "$(date +%H:%M:%S) done: self-play data" >> tr_value_data.log
