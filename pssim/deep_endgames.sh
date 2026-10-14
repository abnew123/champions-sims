#!/bin/zsh
# The endgame sanity check for the anytime search's depth (deep_endgames.py has the design): arms B (depth on side 0) and C (depth on
# side 1) side by side, T threads each, BUDGET leaf evaluations a decision for both sides, DEPTH turns beyond the current one for the
# deep side (ARM_B / ARM_C: other per-arm settings instead, e.g. a control with BATTLE_POLICY_0=random). Each arm shows on the progress
# page (pssim/deep_end_<tag>_<arm>.log). Usage:
#   SP=<scratch dir with starts.jsonl / starts.jobs.json and battlesim-champ-deep> TAG=b20k BUDGET=20000 DEPTH=3 ./deep_endgames.sh
cd "$(dirname $0)"
SP=${SP:?scratch dir}; TAG=${TAG:-b20k}; BUDGET=${BUDGET:-20000}; DEPTH=${DEPTH:-3}; T=${T:-3}
B=${BIN:-$SP/battlesim-champ-deep}; ED=../native/engine_data_full.json; ST=${STARTS:-$SP/deepend/starts}   # STARTS: <prefix> of .jsonl / .jobs.json
# VALUE (default the bot's: sym2 + the h64 net) can be set empty: the planner's crude built-in value, for a control with a weak leaf
F=(RACE_TIES=avg RACE=1 TRSYM=1 EG_MEGA_TIE=0 GRID_DIR=$SP/grid CALC_DATA=../native/champions_data_full.json RACE_PRIO=1 FEATS22=1
   ${=VALUE-EG_VALUE=egvalue9_sym2.json EG_VNET=$PWD/../bot/value/vnet_h64_search_acc.json} BATTLE_NS=1 BATTLE_EVAL=1 BATTLE_EVAL_BUDGET=$BUDGET ${=EXTRA:-})
arm() {
  local a=$1 out=$SP/deepend/${TAG}_$1; mkdir -p $SP/deepend; local x=(${=ARM_B:-BATTLE_EVAL_DEPTH_0=$DEPTH}); [ $a = C ] && x=(${=ARM_C:-BATTLE_EVAL_DEPTH_1=$DEPTH})
  echo "$(date +%H:%M:%S) $ST.jobs.json -> $out, $T threads (depth head-to-head, $TAG arm $a)" > deep_end_${TAG}_$a.log
  env $F $x nice -n 10 $B battle $ED $ST.jsonl $out $T >> deep_end_${TAG}_$a.log 2>&1
  echo "$(date +%H:%M:%S) done: arm $a" >> deep_end_${TAG}_$a.log
}
arm B & arm C & wait
../.venv/bin/python3 deep_endgames.py report $ST $SP/deepend/${TAG}_B $SP/deepend/${TAG}_C
echo "$(date '+%I:%M %p') done"
