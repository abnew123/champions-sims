#!/bin/bash
# On the box: Battle sim's two-turn horizon head-to-head at 2,400 games (2026-10-07; pssim/h2test.py): champ-battle-v21 on the same
# starts three times: A as is, B with BATTLE_HORIZON=2 for side 0, C for side 1. Writes pssim/h2big_report.txt.
# Needs native/champ/bin/champ-battle-v21 (teamsearch/cloud/build_battle.sh src_battle_v21.tar.gz).  usage: cloud/h2big.sh [threads=90]
set -e
cd "$(dirname "$0")/../../pssim"
T=${1:-90}; PY=../.venv/bin/python3
BIN=$(cd ../teamsearch && $PY -c "import procs, os; print(procs.battle(os.path.abspath('../native/champ/bin/champ-battle-v21')))")
NODE=$(cd ../teamsearch && $PY -c "import procs; print(procs.node())")
[ -f h2big_jobs.json ] || $PY h2test.py jobs h2big_jobs.json
[ -f h2big_starts.jsonl ] || SEED_PER_JOB=1 $NODE ../native/battle_starts.js h2big_jobs.json h2big_starts.jsonl 1
mkdir -p h2big_grid_empty
FL="RACE_TIES=avg DP2=1 RACE=1 CALC_DATA=../native/champions_data.json BATTLE_ANTICIPATE=1 TRSYM=1 EG_VALUE=egvalue9_sym2.json GRID_DIR=$PWD/h2big_grid_empty"
for r in A B C; do
  case $r in A) X="";; B) X="BATTLE_HORIZON=2 BATTLE_HORIZON_SIDE=0";; C) X="BATTLE_HORIZON=2 BATTLE_HORIZON_SIDE=1";; esac
  mkdir -p out$r; t=$(date +%s)
  env $FL $X nice -n 10 $BIN battle ../native/engine_data_full.json h2big_starts.jsonl out$r $T
  echo "run $r ($X): $(( $(date +%s) - t )) s" | tee -a h2big_times.txt
done
$PY h2test.py report outA outB outC | tee h2big_report.txt
