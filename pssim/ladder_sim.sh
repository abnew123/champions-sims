#!/bin/zsh
# The climb's simulator against the bot's real ladder results (bot/ladder_sim.py has the design): the bot's games rebuilt at turn 1,
# each played out K times with the climb's setup (teamsearch v33n1: v34, sym2 + the h64 net on both sides, one luck seed a cell).
# T threads; a progress card (pssim/ladder_sim.log).
#   (root) .venv/bin/python3 bot/ladder_sim.py build <SP>/ladder 4
#   SP=<folder of the build> T=1 ./ladder_sim.sh
ME=${0:A}; cd "$(dirname $ME)"
SP=${SP:?folder of the build}; T=${T:-1}; B=${BIN:-../native/champ/bin/champ-battle-v34}; ED=../native/engine_data_full.json; mkdir -p $SP/grid
F=(BATTLE_ANTICIPATE=1 DP2=1 RACE=1 RACE_TIES=avg TRSYM=1 RACE_PRIO=1 FEATS22=1 EG_MEGA_TIE=0 CALC_DATA=../native/champions_data_full.json
   EG_VALUE=egvalue9_sym2.json EG_VNET=$PWD/../bot/value/vnet_h64_search_acc.json GRID_DIR=$SP/grid BATTLE_NS=1)
ln -sf $PWD/$B $SP/battlesim-champ-ladder 2>/dev/null || ln -sf $B $SP/battlesim-champ-ladder
out=$SP/ladder_out; rm -rf $out
echo "$(date +%H:%M:%S) $SP/ladder.jobs.json -> $out, $T threads (the climb's sim on the bot's ladder games)" > ladder_sim.log
env $F nice -n 10 $SP/battlesim-champ-ladder battle $ED $SP/ladder.jsonl $out $T >> ladder_sim.log 2>&1
echo "$(date +%H:%M:%S) done:" >> ladder_sim.log
${PY:-../.venv/bin/python3} ../bot/ladder_sim.py report $SP/ladder $out
