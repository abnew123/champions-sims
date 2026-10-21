#!/bin/zsh
# The sparring partner built on the d4 net (2026-10-21): sparring.sh's opponent bases its play (the mix and values the human model tilts)
# on the deployed net, which may favour the bot that shares that net, so the same two bots also play an opponent built on the d4 net;
# averaged over the two opponents neither net plays its own kind. Arms acc0_h4 / d4_0_h4: the bot on side 0 with that net, the human on
# side 1 on the d4 net. sparring.py reports them with the rest.   ARMS="acc0_h4 d4_0_h4" T=2 ./sparring_h4.sh
cd "$(dirname $0)"
SP=${SP:-$PWD/results/sparring}; T=${T:-2}; BUDGET=${BUDGET:-20000}; B=${BIN:-$PWD/../native/champ/bin/battlesim-champ-dev}; ED=../native/engine_data_full.json
ACC=$PWD/../bot/value/vnet_h64_search_acc.json; D4=$PWD/../bot/value/vnet_h64_search_d4.json; mkdir -p $SP/grid
F=(RACE_TIES=avg RACE=1 TRSYM=1 EG_MEGA_TIE=0 GRID_DIR=$SP/grid CALC_DATA=../native/champions_data_full.json RACE_PRIO=1 FEATS22=1
   EG_VALUE=egvalue9_sym2.json BATTLE_NS=1 BATTLE_EVAL=1 BATTLE_EVAL_BUDGET=$BUDGET HUMAN_MODEL=$PWD/../bot/out/contempt/human_model_bot.json BATTLE_LOG=1)
typeset -A X
X[acc0_h4]="EG_VNET=$ACC EG_VNET_B=$D4 BATTLE_POLICY_1=human"; X[d4_0_h4]="EG_VNET=$D4 EG_VNET_B=$D4 BATTLE_POLICY_1=human"
arm() {
  local a=$1 out=$SP/out_$1; rm -rf $out; echo "Sparring partner on the d4 net: the bot ($a) against it" > $out.title
  echo "$(date +%H:%M:%S) $SP/starts.jobs.json -> $out, $T threads (sparring arm $a)" > sparring_$a.log
  env $F ${=X[$a]} nice -n 10 $B battle $ED $SP/starts.jsonl $out $T >> sparring_$a.log 2>&1
  echo "$(date +%H:%M:%S) done: arm $a" >> sparring_$a.log
}
for a in ${=ARMS:-acc0_h4 d4_0_h4}; do arm $a & done; wait
