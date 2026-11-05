#!/bin/zsh
# The rain study's bring matrix (2026-11-05, the user: "let's study the rain matchup in self-play"; bot/rain_study.py has the design):
# every four of the Trick Room six against the rain fours two ladder bots bring (results/rain/jobs.json), G games each on the        
# same luck for every four (native/battle_starts.js explicit mode: seeds from their four and the game index), played by champ battle with
# the bot's settings (the h64 net, its Perish and progress terms and the Trick Room head, BATTLE_EVAL one-turn search at BUDGET leaves).
# Shows on the progress page (pssim/rain_matrix.log). Usage: T=6 G=4 ./rain_matrix.sh
emulate -R zsh   # a renamed argv[0] starting with b or s makes zsh emulate sh
cd "$(dirname $0)"
SP=$PWD/results/rain; T=${T:-6}; G=${G:-4}; G0=${G0:-0}; BUDGET=${BUDGET:-20000}; B=${BIN:-$SP/battlesim-champ-rain}; ED=../native/engine_data_full.json
OUTD=$SP/${TAG:-matrix}; mkdir -p $SP/grid $OUTD
node ../native/battle_starts.js $SP/jobs.json $SP/${TAG:-matrix}_starts.jsonl $G $G0 || exit 1
node -e "const n=JSON.parse(require('fs').readFileSync('$SP/jobs.json')).length; require('fs').writeFileSync('$SP/${TAG:-matrix}_jobs.json', JSON.stringify([...Array(n).keys()]))"
F=(RACE_TIES=avg RACE=1 TRSYM=1 EG_MEGA_TIE=0 GRID_DIR=$SP/grid CALC_DATA=../native/champions_data_full.json RACE_PRIO=1 FEATS22=1
   EG_VALUE=egvalue9_sym2.json EG_VNET=$PWD/../bot/value/vnet_h64_search_acc.json BATTLE_NS=1 BATTLE_EVAL=1 BATTLE_EVAL_BUDGET=$BUDGET
   VNET_PERISH=1 VNET_PROGRESS=1 PERISH_DOOM=1 TR_HEAD=$PWD/../bot/value/trhead_v41.json ${=EXTRA:-})
echo "$(date +%H:%M:%S) $SP/${TAG:-matrix}_jobs.json -> $OUTD, $T threads (rain study: Trick Room six bring matrix, $G games a four)" > rain_${TAG:-matrix}.log
env $F nice -n 10 $B battle $ED $SP/${TAG:-matrix}_starts.jsonl $OUTD $T >> rain_${TAG:-matrix}.log 2>&1
echo "$(date +%H:%M:%S) done: rain ${TAG:-matrix}" >> rain_${TAG:-matrix}.log
