#!/bin/zsh
# The sheets' setup on the real Perish pairings (TR sheet, 2026-10-16: the sheets run v23 on EG_VALUE, which always had a Perish term, the
# old form; does it misplay Perish?). perish_fix.sh's pairings and report, with sheetkit/sim.json's current setup (v23-dp2-race-eg9-full;
# an empty grid, where the kit uses the team's own): arm sheet as it is, arm sheetp2 with PERISH2=1 (in v23 since v11).
#   SP=<perish_fix.sh's folder> T=1 ./perish_sheet.sh
ME=${0:A}; cd "$(dirname $ME)"
SP=${SP:?folder}; T=${T:-1}; B=$PWD/../native/champ/bin/champ-battle-v23; ED=../native/engine_data_full.json; mkdir -p $SP/emptygrid
F=(BATTLE_ANTICIPATE=1 DP2=1 RACE=1 RACE_TIES=avg CALC_DATA=$PWD/../native/champions_data.json EG_VALUE=$PWD/egvalue9.json GRID_DIR=$SP/emptygrid BATTLE_LOG=1)
ln -sf $B $SP/battlesim-champ-sheet
arm() {
  local a=$1 out=$SP/out_$1; shift; rm -rf $out; echo "Perish check, the sheets' setup: arm $a" > $out.title
  echo "$(date +%H:%M:%S) $SP/starts.jobs.json -> $out, $T threads (the sheets' setup on Perish pairings, arm $a)" > perish_sheet_$a.log
  env $F "$@" nice -n 10 $SP/battlesim-champ-sheet battle $ED $SP/starts.jsonl $out $T >> perish_sheet_$a.log 2>&1
  echo "$(date +%H:%M:%S) done: arm $a" >> perish_sheet_$a.log
}
arm sheet & arm sheetp2 PERISH2=1 & wait
${PY:-../.venv/bin/python3} perish_fix.py report $SP sheet sheetp2
