#!/bin/zsh
# The sparring partner (2026-10-21, the user: test the nets against people's habits in self-play while the Bo1 ladder A/B runs): the bot's
# search (BATTLE_EVAL, BATTLE_EVAL_BUDGET leaf evaluations a decision, one turn) against a side that plays the human model refitted on the
# bot's own Bo3 opponents (battle4 BATTLE_POLICY_<s>=human, HUMAN_MODEL; Protect 18%, setup 3% of slot decisions, as people play the bot),
# the opponent always valued by the deployed net. Arms, the same starts and luck: acc0 / d4_0 the bot on side 0 with that net, the human
# on side 1; acc1 / d4_1 mirrored. sparring.py report compares the d4 net's results with the deployed net's. Each arm on the progress page.
#   ARMS="acc0 d4_0" T=2 ./sparring.sh        (SP: the scratch dir with starts.jsonl / starts.jobs.json)
cd "$(dirname $0)"
SP=${SP:-$PWD/results/sparring}; T=${T:-2}; BUDGET=${BUDGET:-20000}; B=${BIN:-$PWD/../native/champ/bin/battlesim-champ-dev}; ED=../native/engine_data_full.json
ACC=$PWD/../bot/value/vnet_h64_search_acc.json; D4=$PWD/../bot/value/vnet_h64_search_d4.json; mkdir -p $SP/grid
F=(RACE_TIES=avg RACE=1 TRSYM=1 EG_MEGA_TIE=0 GRID_DIR=$SP/grid CALC_DATA=../native/champions_data_full.json RACE_PRIO=1 FEATS22=1
   EG_VALUE=egvalue9_sym2.json BATTLE_NS=1 BATTLE_EVAL=1 BATTLE_EVAL_BUDGET=$BUDGET HUMAN_MODEL=$PWD/../bot/out/contempt/human_model_bot.json BATTLE_LOG=1)
typeset -A X
X[acc0]="EG_VNET=$ACC EG_VNET_B=$ACC BATTLE_POLICY_1=human"; X[d4_0]="EG_VNET=$D4 EG_VNET_B=$ACC BATTLE_POLICY_1=human"
X[acc1]="EG_VNET=$ACC EG_VNET_B=$ACC BATTLE_POLICY_0=human"; X[d4_1]="EG_VNET=$ACC EG_VNET_B=$D4 BATTLE_POLICY_0=human"
arm() {
  local a=$1 out=$SP/out_$1; rm -rf $out; echo "Sparring partner: the bot ($a) against the human model" > $out.title
  echo "$(date +%H:%M:%S) $SP/starts.jobs.json -> $out, $T threads (sparring arm $a)" > sparring_$a.log
  env $F ${=X[$a]} nice -n 10 $B battle $ED $SP/starts.jsonl $out $T >> sparring_$a.log 2>&1
  echo "$(date +%H:%M:%S) done: arm $a" >> sparring_$a.log
}
for a in ${=ARMS:-acc0 d4_0 acc1 d4_1}; do arm $a & done; wait
