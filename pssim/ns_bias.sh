#!/bin/zsh
# Does one luck seed a cell shift some styles against others? (2026-10-14, Team search before moving the climb to BATTLE_NS=1: inside an
# archetype-locked climb, a style-dependent shift is the failure that would matter.) The real-pairings check (replay_pairs.py: 2,094
# real Bo3 games replayed from both players' own leads and brings, the sim's result against the real one by style) on the climb's v33
# setup with the net on both sides, at BATTLE_NS=2 (the climb now) and BATTLE_NS=1. T threads; each run shows on the progress page.
#   SP=<scratch dir with bias/pairs.json, bias/pairs_starts.jsonl> ./ns_bias.sh
ME=${0:A}; cd "$(dirname $ME)"
SP=${SP:?scratch dir}; T=${T:-4}; B=../native/champ/bin/battlesim-champ-v33; ED=../native/engine_data_full.json
F=(BATTLE_ANTICIPATE=1 DP2=1 RACE=1 RACE_TIES=avg TRSYM=1 RACE_PRIO=1 FEATS22=1 EG_MEGA_TIE=0 CALC_DATA=../native/champions_data_full.json
   EG_VALUE=egvalue9_sym2.json EG_VNET=$PWD/../bot/value/vnet_h64_search_acc.json GRID_DIR=$SP/bias/grid)
for n in 2 1; do
  out=$SP/bias/v33ns$n; rm -rf $out
  echo "$(date +%H:%M:%S) $SP/bias/pairs.json -> $out, $T threads (style bias, v33, luck seeds a cell $n)" > ns_bias_$n.log
  env $F BATTLE_NS=$n nice -n 10 $B battle $ED $SP/bias/pairs_starts.jsonl $out $T >> ns_bias_$n.log 2>&1
  echo "$(date +%H:%M:%S) done: seeds $n" >> ns_bias_$n.log
done
PAIRS=$SP/bias/pairs.json ${PY:-../.venv/bin/python3} replay_pairs.py report $SP/bias/v33ns2 $SP/bias/v33ns1
echo "$(date '+%I:%M %p') done"
