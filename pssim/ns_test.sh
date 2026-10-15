#!/bin/zsh
# Could the climb run on fewer luck samples a cell? (2026-10-14, the user: if 4x the budget plays like 1x, maybe 0.5x is decent, and the
# climb could run faster.) Self-play with the climb's exact v33 setup (teamsearch/evaluate.py SIMS['v33']: V26_ENV, sym2 + the h64 net),
# one side on N luck seeds a cell (BATTLE_NS_<side>, battle4.rs), the other on the climb's 2; arm B gives side 0 the N, arm C side 1, on
# the same starts and luck. deep_endgames.py report prints the N side's gain ("the deep side"). T threads an arm; progress page cards.
#   SP=<scratch dir with battlesim-champ-ns and deepmid/starts.*> N=1 ./ns_test.sh
ME=${0:A}; cd "$(dirname $ME)"
SP=${SP:?scratch dir}; N=${N:-1}; T=${T:-2}; B=${BIN:-$SP/battlesim-champ-ns}; ED=../native/engine_data_full.json; ST=${STARTS:-$SP/deepmid/starts}
F=(BATTLE_ANTICIPATE=1 DP2=1 RACE=1 RACE_TIES=avg TRSYM=1 RACE_PRIO=1 FEATS22=1 EG_MEGA_TIE=0 CALC_DATA=../native/champions_data_full.json
   EG_VALUE=egvalue9_sym2.json EG_VNET=$PWD/../bot/value/vnet_h64_search_acc.json GRID_DIR=$SP/grid)
arm() {
  local a=$1 out=$SP/nstest/ns${N}_$1; local x=(BATTLE_NS_0=$N); [ $a = C ] && x=(BATTLE_NS_1=$N); mkdir -p $SP/nstest
  echo "$(date +%H:%M:%S) $ST.jobs.json -> $out, $T threads (luck seeds a cell: $N vs 2, arm $a)" > ns_test_${N}_$a.log
  rm -rf $out; env $F $x nice -n 10 $B battle $ED $ST.jsonl $out $T >> ns_test_${N}_$a.log 2>&1
  echo "$(date +%H:%M:%S) done: arm $a" >> ns_test_${N}_$a.log
}
arm B & arm C & wait
${PY:-../.venv/bin/python3} deep_endgames.py report $ST $SP/nstest/ns${N}_B $SP/nstest/ns${N}_C
echo "$(date '+%I:%M %p') done"
