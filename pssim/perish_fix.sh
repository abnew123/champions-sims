#!/bin/zsh
# Perish with the learned value (2026-10-16, the user: fix Perish, don't avoid it). The net (the bot's and the climb's leaf since v28) had
# no Perish input, so neither side saw a reason to sing, escape or KO the trapper. The real Bo3 pairings with a Perish side (replay_pairs.py
# jobs, both players' own brings and leads, 4 playouts each) played by the climb's v33n1 setup, once per arm; perish_fix.py report compares
# the sim's Perish-side win share and Perish Song use with the real games'. Arms: base (as now), vp (VNET_PERISH=1), more via ARMS/EXTRA_<arm>.
#   SP=<folder with starts.jsonl / starts.jobs.json / perish_pairs.json> BIN=<champ with VNET_PERISH> T=1 ./perish_fix.sh
ME=${0:A}; cd "$(dirname $ME)"
SP=${SP:?folder}; T=${T:-1}; B=${BIN:?champ binary}; ED=../native/engine_data_full.json; mkdir -p $SP/grid
F=(BATTLE_ANTICIPATE=1 DP2=1 RACE=1 RACE_TIES=avg TRSYM=1 RACE_PRIO=1 FEATS22=1 EG_MEGA_TIE=0 CALC_DATA=../native/champions_data_full.json
   EG_VALUE=egvalue9_sym2.json EG_VNET=$PWD/../bot/value/vnet_h64_search_acc.json GRID_DIR=$SP/grid BATTLE_NS=1 BATTLE_LOG=1)
typeset -A X; X[base]=""; X[vp]="VNET_PERISH=1"
for a in ${=ARMS:-base vp}; do [ -n "${(P)${:-EXTRA_$a}}" ] && X[$a]="${(P)${:-EXTRA_$a}}"; done
ln -sf $B $SP/battlesim-champ-perish
arm() {
  local a=$1 out=$SP/out_$1; rm -rf $out; echo "Perish fix check: real Perish pairings, arm $a" > $out.title
  echo "$(date +%H:%M:%S) $SP/starts.jobs.json -> $out, $T threads (Perish arm $a)" > perish_fix_$a.log
  env $F ${=X[$a]} nice -n 10 $SP/battlesim-champ-perish battle $ED $SP/starts.jsonl $out $T >> perish_fix_$a.log 2>&1
  echo "$(date +%H:%M:%S) done: arm $a" >> perish_fix_$a.log
}
for a in ${=ARMS:-base vp}; do arm $a & done; wait
${PY:-../.venv/bin/python3} perish_fix.py report $SP ${=ARMS:-base vp}
